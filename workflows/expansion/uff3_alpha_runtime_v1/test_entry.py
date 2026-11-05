"""Metadata admission/accounting/selection boundaries; no scientific invocation."""
import copy
import os
from pathlib import Path
import random
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from . import entry as E,pilot_membership


def ref(name):return {'path':str(name),'bytes':1,'sha256':str(name)}


class AlphaEntryTests(unittest.TestCase):
    def test_native_proof_binds_job_boot_argv_and_every_actual_source(self):
        plan_path=Path('/plan');proof_path=Path('/proof');argv=[sys.executable,'-I','-B','/entry',E.MODULE,'--plan','/plan','--startup-proof','/proof']
        folder=Path(E.generation.__file__).parent
        paths=list(Path(E.__file__).parent.glob('*.py'))+[folder/name for name in
            ('run.py','resources.py','credit.py','ledger_resume.py','core.py','native.py','store.py','families.py','quality.py')]+[Path('/entry')]
        plan={'execution_argv':argv,'scope_key':'fixture','endpoint':E.Q.ENDPOINT,'code_references':[ref(p)for p in paths]}
        proof={'uid':1264,'endpoint':E.Q.ENDPOINT,'job_id':'fixture','boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'request':{'producer_plan_reference':ref(plan_path),'execution_argv':argv,'scope_key':'fixture','source_references':plan['code_references']}}
        actual={'uid':1264,'job_id':'fixture'}
        def check(p=plan,proof_value=proof):
            with patch.object(E.Q,'load',side_effect=lambda x:p if x==plan_path else proof_value),patch.object(E.Q,'reference',side_effect=ref),\
                    patch.object(E.profile,'admit',return_value=actual),patch.object(E.os,'getuid',return_value=1264),\
                    patch.dict(os.environ,{'SLURM_JOB_ID':'fixture'}),patch.object(sys,'argv',['entry',*argv[5:]]):
                return E.admit(plan_path,proof_path)
        self.assertEqual(check()[1],actual)
        for field,value in [('endpoint','Main'),('boot_id','old-boot'),('job_id','other')]:
            bad=copy.deepcopy(proof);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):check(proof_value=bad)
        bad=copy.deepcopy(plan);bad['code_references'].remove(ref(folder/'core.py'))
        with self.assertRaisesRegex(ValueError,'source must be pinned'):check(p=bad)

    def test_partition_never_expands_global_cap_or_drops_peer_future(self):
        budget={'schema':'ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2','reviewer':'root','endpoint':E.Q.ENDPOINT,'uid':1264,
            'scope_total_caps_bytes':{'UFF':700},'other_future_reserved_bytes_for_each_scope':{'UFF':1000},'minimum_free_after_all_future_bytes':200}
        r={'schema':'ROOT_ALPHA_UFF_PRIVATE_STAGE_STORAGE_PARTITION_V1','status':'APPROVED_PRIVATE_UFF_STAGE_PARTITION',
            'reviewer':'root','endpoint':E.Q.ENDPOINT,'uid':1264,'future_budget_review_reference':ref('budget'),
            'routing_scope_root':'/routing','inner_stage_is_only_child':True,'routing_budget_includes_all_ancestors':True,
            'closed_legacy_allocated_bytes':100,'routing_overhead_reserved_bytes':10,'inner_output_cap_bytes':500,
            'peer_stage_caps_bytes':90,'peer_remaining_reserved_bytes':80,'other_future_reserved_bytes':1090,
            'closed_legacy_census_reference':ref('census')}
        p={'storage_partition':r,'output_scope_root':'/routing',
           'output_cap_bytes':500,'other_future_reserved_bytes':1090,'minimum_free_bytes':200}
        def check(review=r):
            with patch.object(E,'read',side_effect=lambda x:budget if x==ref('budget')else review),patch.object(E.Q,'verify',return_value=Path('/not-read')):
                return E.partition({**p,'storage_partition':review})
        self.assertEqual(check(),r)
        for field,value in [('closed_legacy_allocated_bytes',101),('other_future_reserved_bytes',1089),('routing_overhead_reserved_bytes',11)]:
            bad={**r,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):check(bad)

    def test_derived_scope_preserves_total_reservation_and_rejects_peer_stage(self):
        with tempfile.TemporaryDirectory()as folder:
            routing=Path(folder);out=routing/'inner'
            p={'runtime_action':'generation','schema':'PUBCHEM_UFF3_ALLOCATION_PLAN_V1','mode':'pilot',
               'maximum_conformers':3,'no_fill':True,'no_retry':True,'recipe_sha256':E.C.recipe_sha(),'source_manifest':ref('source'),'output_scope_root':str(routing),
               'output_directory':str(out),'output_cap_bytes':8<<20,'other_future_reserved_bytes':12345,
               'metadata_wrapper_reserved_bytes':1<<20,'quality_reference_review':ref('quality'),
               'quality_bindings_reference':ref('bindings'),'source_capsule_reference':ref('capsule'),
               'parent_transport_manifest':ref('transport'),'generation_actual_accounting_references':[],'generation_receipts':[]}
            binding={k:p[k]for k in('source_capsule_reference','parent_transport_manifest','quality_reference_review')}
            binding['schema']='PUBCHEM_ALPHA_UFF_FULLTRAIN_QUALITY_BINDINGS_V1'
            with patch.object(E,'partition',return_value={}),patch.object(E,'accepted'),patch.object(E,'read',return_value=binding),patch.object(E,'routing_overhead',return_value=0),patch('workflows.expansion.uff3_alpha_runtime_v1.ordered_contract.completed_source'):
                runtime,_=E.derive(p,{},ref('plan'),ref('proof'))
                self.assertEqual(runtime['output_scope_root'],str(out))
                self.assertEqual(runtime['output_cap_bytes']+runtime['other_future_reserved_bytes'],p['output_cap_bytes']+p['other_future_reserved_bytes'])
                (routing/'another-stage').mkdir()
                with self.assertRaisesRegex(ValueError,'another stage'):E.derive(p,{},ref('plan'),ref('proof'))

    def test_source_dispatch_calls_only_ordered_original_and_refuses_rank_bypass(self):
        from . import typed_source_entry as source
        p=Path('/fixture-plan')
        with patch.object(source.ordered_source,'run',return_value={'source':True})as ordered:
            self.assertEqual(source.dispatch({'runtime_action':'ordered_source','schema':'PUBCHEM_TYPED_ORDERED_UFF_SOURCE_PLAN_V1'},p),{'source':True})
            ordered.assert_called_once_with(p)
            with self.assertRaises(ValueError):source.dispatch({'runtime_action':'rank','schema':'PUBCHEM_TYPED_EXACT_RANK_PLAN_V1'},p)
            ordered.assert_called_once_with(p)

    def test_native_routing_ancestor_blocks_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory()as folder:
            global_root=Path(folder);routing=global_root/'routing';routing.mkdir()
            (routing/'uff_alpha_routing.lock').touch()
            expected=sum(p.lstat().st_blocks*512 for p in (global_root,routing,routing/'uff_alpha_routing.lock'))
            review={'global_UFF_scope_root':str(global_root),'routing_ancestor_paths':[str(routing),str(global_root)],
                    'routing_overhead_reserved_bytes':expected}
            self.assertEqual(E.routing_overhead(review,routing),expected)
            with self.assertRaisesRegex(ValueError,'exceed reserved'):
                E.routing_overhead({**review,'routing_overhead_reserved_bytes':expected-1},routing)
            with self.assertRaisesRegex(ValueError,'complete routing'):
                E.routing_overhead({**review,'routing_ancestor_paths':[str(routing)]},routing)
    def test_full_resumes_actual_pilot_not_fresh_or_implicitly_resharded_scope(self):
        review={'pilot_generation_receipt_reference':ref('/actual-pilot/receipt.json')}
        plan={'output_directory':'/actual-pilot','resume_binding':{'previous_allocations':['machine fixture']}}
        E.same_pilot_stage(plan,review)
        for changes in ({'output_directory':'/fresh-stage'},
                        {'resume_binding':None},{'shard_count':2},{'shard_index':1}):
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'actual pilot stage'):
                E.same_pilot_stage({**plan,**changes},review)
    def test_pilot_exact_membership_keeps_zero_or_failed_outcomes_and_rejects_substitution(self):
        db=sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE source(ordinal INTEGER PRIMARY KEY,mid TEXT,stream TEXT,stream_rank INTEGER);CREATE INDEX ranks ON source(stream,stream_rank);CREATE TABLE done(ordinal INTEGER PRIMARY KEY,status TEXT);')
        rng=random.Random(20261025);ordinal=0
        for stream in ('R','N'):
            for rank in rng.sample(range(1,1250001),5000):
                db.execute('INSERT INTO source VALUES(?,?,?,?)',(ordinal,stream+str(rank),stream,rank))
                db.execute('INSERT INTO done VALUES(?,?)',(ordinal,'ZERO_CONFORMERS'if ordinal%2 else'PROPERTY_FAILED'))
                ordinal+=1
        self.assertEqual(pilot_membership.validate(db),10000)
        db.execute('INSERT INTO source VALUES(10000,?,?,?)',('wrong','R',1250001))
        db.execute('DELETE FROM done WHERE ordinal=0');db.execute("INSERT INTO done VALUES(10000,'SUCCESS')")
        with self.assertRaisesRegex(RuntimeError,'NO_DROP_OR_SUBSTITUTION'):pilot_membership.validate(db)
        db.close()


if __name__=='__main__':unittest.main()