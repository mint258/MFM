"""Budget arithmetic/credit boundary fixtures, no DATA census or scientific run."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from . import budget,prepare


def ref(name):return {'path':name,'bytes':1,'sha256':name}


class PrepareBudgetTests(unittest.TestCase):
    def test_new_closed_exact_blocks_reduce_other_future_once(self):
        caps={'UFF':700,'exact':300,'bulk':350,'reports':5,'source_transport':20}
        old={'UFF':0,'exact':33,'bulk':80,'reports':1,'source_transport':12}
        new={**old,'exact':200}
        r0,o0=budget.totals(caps,old);r1,o1=budget.totals(caps,new)
        self.assertEqual(o0['UFF']-o1['UFF'],167)
        self.assertEqual(r1['exact'],100);self.assertEqual(r1['UFF'],700)
        with self.assertRaises(ValueError):budget.totals(caps,{**new,'exact':301})

    def test_inline_cannot_expand_cap_lower_floor_or_use_postquery_credit(self):
        base={'endpoint':budget.Q.ENDPOINT,'uid':1264,'scope_total_caps_bytes':{'UFF':700,'exact':300},
              'minimum_free_after_all_future_bytes':200}
        c={'endpoint':budget.Q.ENDPOINT,'uid':1264,'baseline_budget_reference':ref('base'),
           'records':[{'dev_u64':'0','ino_u64':'1','uid':1264,'scope':'exact','path':'/closed',
                       'allocated_bytes':100,'mtime_ns':1000000000,'ctime_ns':1000000000}],
           'closed_credit_bytes_by_scope':{'UFF':0,'exact':100},'maximum_eligible_ns':1000000000,
           'closed_allocations':[],'excluded_active_allocations':[]}
        docs={'base':base,'census':c}
        value={'endpoint':budget.Q.ENDPOINT,'uid':1264,'baseline_budget_reference':ref('base'),
               'closed_census_reference':ref('census'),'scope_total_caps_bytes':base['scope_total_caps_bytes'],
               'minimum_free_after_all_future_bytes':200,'closed_credit_bytes_by_scope':c['closed_credit_bytes_by_scope'],
               'remaining_reserved_bytes_by_scope':{'UFF':700,'exact':200},
               'other_future_reserved_bytes_for_each_scope':{'UFF':200,'exact':700},'total_remaining_reserved_bytes':900}
        def check(v=value,cutoff=2):
            with patch.object(budget,'read',side_effect=lambda r:docs[r['sha256']]),\
                 patch.object(budget,'read_census',side_effect=lambda r:docs[r['sha256']]),\
                 patch.object(budget,'excluded_201',return_value=[Path('/active201')]),\
                 patch.object(budget.Q,'load',return_value={}),\
                 patch.object(budget,'validate_snapshot',return_value={'quota_query_started_unix_seconds':cutoff}):
                return budget.validate(v,{'quota_snapshot':'actual','quota_authority':{}})
        self.assertEqual(check(),value)
        with self.assertRaises(ValueError):check(cutoff=1)
        bad=copy.deepcopy(value);bad['scope_total_caps_bytes']['UFF']=701
        with self.assertRaises(ValueError):check(bad)
        bad={**value,'minimum_free_after_all_future_bytes':199}
        with self.assertRaises(ValueError):check(bad)
        docs['census']={**c,'records':[{**c['records'][0],'path':'/active201/queries.sqlite'}]}
        with self.assertRaisesRegex(ValueError,'Active201'):check()

    def test_real_census_JSON_over_two_MiB_uses_only_bounded_census_path(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);padding='metadata-padding-'*(140000)
            old={'endpoint':budget.Q.ENDPOINT,'uid':1264,'whole_DATA_SHA_reread':False,
                 'entries':[{'scope':'exact','basis':'closed','path':'/closed',
                             'allocated_bytes':100,'frame':{'st_ctime_ns':1,'st_dev':41,'st_ino':2,
                             'st_mtime_ns':1,'st_nlink':1,'st_size':99,'st_uid':1264}}],
                 'notes':padding}
            def put(name,value):
                path=root/name;path.write_text(json.dumps(value));return budget.Q.reference(path)
            oldref=put('old_census.json',old)
            self.assertGreater(oldref['bytes'],2<<20)
            self.assertEqual(budget.read_census(oldref)['entries'][0]['frame'],old['entries'][0]['frame'])
            base={'endpoint':budget.Q.ENDPOINT,'uid':1264,'scope_total_caps_bytes':{'UFF':700,'exact':300},
                  'minimum_free_after_all_future_bytes':200}
            baseref=put('base.json',base)
            current={'endpoint':budget.Q.ENDPOINT,'uid':1264,'whole_DATA_SHA_reread':False,
                     'baseline_budget_reference':baseref,'notes':padding,
                     'records':[{'dev_u64':'0000000000000029','ino_u64':'0000000000000002','uid':1264,
                                 'scope':'exact','path':'/closed','allocated_bytes':100,'mtime_ns':1,'ctime_ns':1}],
                     'closed_credit_bytes_by_scope':{'UFF':0,'exact':100},'maximum_eligible_ns':1,
                     'closed_allocations':[],'excluded_active_allocations':[]}
            currentref=put('current_census.json',current);self.assertGreater(currentref['bytes'],2<<20)
            original=budget.read
            def small_only(ref):
                if ref['bytes']>2<<20:raise AssertionError('Census passed to the small metadata reader')
                return original(ref)
            # Keep real Q.verify/Q.load and actual >2MiB bytes/hash in both
            # inline and validate. Only quota/source exclusion is isolated.
            with patch.object(budget,'read',side_effect=small_only):
                value=budget.inline(baseref,currentref)
                snapshot=root/'quota.json';snapshot.write_text('{}')
                with patch.object(budget,'excluded_201',return_value=[Path('/active201')]),\
                     patch.object(budget,'validate_snapshot',return_value={'quota_query_started_unix_seconds':1}):
                    self.assertEqual(budget.validate(value,{'quota_snapshot':str(snapshot),'quota_authority':{}}),value)
            self.assertEqual(value['other_future_reserved_bytes_for_each_scope']['UFF'],200)
            with patch.object(budget.Q,'verify',side_effect=AssertionError('oversize must fail before body hash')):
                with self.assertRaisesRegex(ValueError,'64MiB'):
                    budget.read_census({**currentref,'bytes':(64<<20)+1})
    def test_same_generation_prefix_is_not_double_charged_as_legacy_B(self):
        config={'private_caps_bytes':{'generation':600,'quality':50,'finalizer':20},
                'global_UFF_scope_root':'/uff','routing_overhead_reserved_bytes':5}
        inline={'scope_total_caps_bytes':{'UFF':700},'other_future_reserved_bytes_for_each_scope':{'UFF':1000},
                'closed_census_reference':ref('actual-census')}
        c={'records':[{'scope':'UFF','path':'/uff/generation/old/cache','allocated_bytes':100},
                      {'scope':'UFF','path':'/uff/legacy','allocated_bytes':10}]}
        p=prepare.partition_for(config,inline,c,'quality','/uff/qa','/uff/qa/next','/uff/generation/old')
        self.assertEqual(p['closed_legacy_allocated_bytes'],10)
        self.assertEqual(p['peer_stage_caps_bytes'],620)
        self.assertEqual(p['peer_remaining_reserved_bytes'],520)
        self.assertEqual(p['other_future_reserved_bytes'],1525)
        bad={**config,'private_caps_bytes':{'generation':650,'quality':50,'finalizer':20}}
        with self.assertRaises(ValueError):prepare.partition_for(bad,inline,c,'quality','/uff/qa','/uff/qa/next','/uff/generation/old')


if __name__=='__main__':unittest.main()