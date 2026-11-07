"""Pure selection fixtures. No data access or scientific execution."""
import unittest
from policy_v1 import audit_key,pilot_union


class StablePolicyProposal(unittest.TestCase):
    def rows(self):
        return [{'record_id':f'r{i}','molecule_id':f'm{i}','source_shard_id':3,'size_stratum':'21_40',
                 'physical_identity':{'namespace':'accepted_original_sprime','source_conformer_id':i}} for i in range(2000)]

    def test_membership_does_not_depend_on_order_or_population_size(self):
        rows=self.rows();pick=lambda row:audit_key(row['molecule_id'],row['source_shard_id'],row['size_stratum'],row['physical_identity'])
        before={r['record_id']:pick(r) for r in rows[:100]}
        after={r['record_id']:pick(r) for r in reversed(rows)}
        self.assertEqual(before,{k:after[k] for k in before})
        self.assertTrue(all(0<=row['bucket']<10000 and row['selected']==(row['bucket']<100) for row in after.values()))

    def test_union_keeps_original20_and_every_stable_hit_with_full12_raw(self):
        rows=self.rows();old=[r['record_id'] for r in rows[:20]]
        selected=pilot_union(rows,old);ids={r['record_id'] for r in selected}
        self.assertTrue(set(old)<=ids)
        hits={r['record_id'] for r in rows if audit_key(r['molecule_id'],r['source_shard_id'],r['size_stratum'],r['physical_identity'])['selected']}
        self.assertEqual(ids,set(old)|hits)
        self.assertTrue(all(r['retain_all_twelve_raw'] for r in selected))

    def test_native_trace_or_unapproved_n1_cannot_be_used_as_uff_identity(self):
        for identity in ({'namespace':'native','source_record_id':'r'},
                         {'namespace':'accepted_original_sprime','source_conformer_id':'0'},
                         {'namespace':'n1_pprime2','seed':123,'candidate_id':0}):
            with self.assertRaises(ValueError):audit_key('m',0,'0_20',identity)

    def test_fill_requires_explicit_real_candidate_identity(self):
        identity={'namespace':'data_v1_fill','seed':321,'candidate_id':2,'task_key':'a'*64}
        self.assertEqual(audit_key('m',0,'0_20',identity),audit_key('m',0,'0_20',dict(reversed(list(identity.items())))))
        with self.assertRaises(ValueError):audit_key('m',0,'0_20',{'namespace':'data_v1_fill','candidate_id':2})


if __name__=='__main__':unittest.main(verbosity=2)
