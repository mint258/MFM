"""Small controlled tests only: no LMDB, RDKit, QM, GPU or Slurm calls."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common_v1 import IO, begin, require_budget, task_key
from prepare_v1 import coordinate_sha, order_contract
from close_batch_v1 import assess, actual_parent
from finalize_v1 import coverage
from run_batch_v1 import split_imports


class FormalBoundaries(unittest.TestCase):
    def test_order_exactly_matches_frozen_sb2_and_rejects_n1_opaque_ids(self):
        rows=[{'sprime_conf_idx':i} for i in range(7)]
        order=sorted(rows,key=lambda r:(IO.stable_key(20261025,'m','uff_sprime',r['sprime_conf_idx']),str(r['sprime_conf_idx'])))
        for rank,row in enumerate(order):row['rank']=rank
        self.assertEqual(order_contract(list(reversed(order)),'m'),order[:2])
        wrong=[dict(r) for r in order];wrong[0]['rank']=6
        with self.assertRaises(ValueError):order_contract(wrong,'m')
        with self.assertRaises(ValueError):order_contract([{'sprime_conf_idx':'n1p2:31:0','rank':0}],'m')
        with self.assertRaises(ValueError):order_contract([{'sprime_conf_idx':None,'rank':0}],'m')

    def test_geometry_and_scientific_seed_identity(self):
        xyz=[[0.,1.,2.],[3.,4.,5.]]
        self.assertEqual(coordinate_sha(xyz),coordinate_sha([[0,1,2],[3,4,5]]))
        k=task_key('m','a'*64,coordinate_sha(xyz),'p'*64,'pprime:m:0')
        self.assertNotEqual(k,task_key('m','a'*64,coordinate_sha(xyz),'p'*64,'pprime:m:1'))
        changed=[row[:] for row in xyz];changed[0][0]=1e-12
        self.assertNotEqual(k,task_key('m','a'*64,coordinate_sha(changed),'p'*64,'pprime:m:0'))
        with self.assertRaises(ValueError):coordinate_sha([[float('nan'),0,0]])

    def test_exclusive_attempt_never_retries_an_unknown_start(self):
        with tempfile.TemporaryDirectory() as folder:
            c={'external_output_root':folder,'attempt_ledger_root':str(Path(folder)/'attempts')}
            pair={'once_key':'a'*64,'record_id':'pprime:m:0','canonical_geometry_id':'opaque'}
            with patch.dict(os.environ,{'SLURM_JOB_ID':'4242'}):
                ref=begin(c,pair,{'fixture':True})
                with self.assertRaises(FileExistsError):begin(c,pair,{'fixture':True})
            self.assertEqual(json.loads(Path(ref['path']).read_text())['status'],'STARTED_OUTCOME_NOT_YET_CLOSED')

    def test_root_over500_budget_is_explicit_and_finite(self):
        with self.assertRaises(ValueError):require_budget(501,{'approved_total_core_hours_cap':600})
        with self.assertRaises(ValueError):require_budget(float('nan'),{'approved_total_core_hours_cap':600,'approved_over_500_core_hours':True})
        require_budget(501,{'approved_total_core_hours_cap':600,'approved_over_500_core_hours':True})

    def result(self):
        return {'runtime':{'job_id':'42','node':'compute-0-17'},'requested_new_records':100,
                'new_records':100,'status':'PPRIME_FORMAL_BATCH_CLOSED_AWAITING_ACTUAL_PARENT_ACCOUNTING',
                'all_workers_joined':True,'failures':[]}

    def parent(self,**kwargs):
        row={'JobIDRaw':'42','User':'zixiao','NodeList':'compute-0-17','AllocCPUS':'16','ElapsedRaw':'100','State':'COMPLETED','ExitCode':'0:0'}
        row.update(kwargs);return row

    def test_actual_parent_cost_ignores_steps_and_includes_setup(self):
        rows=[self.parent(),self.parent(JobIDRaw='42.batch',ElapsedRaw='9000'),self.parent(JobIDRaw='42.extern')]
        report=assess(self.result(),rows,11.7)
        self.assertEqual(report['allocated_core_seconds'],1600)
        self.assertTrue(all(report['gates'].values()))
        with self.assertRaises(ValueError):actual_parent(self.result(),[self.parent(),self.parent()])
        with self.assertRaises(ValueError):actual_parent(self.result(),[self.parent(User='other')])

    def test_failed_parent_still_costs_and_cost_stop_is_not_relaxed(self):
        report=assess(self.result(),[self.parent(State='TIMEOUT',ExitCode='0:9',ElapsedRaw='200')],11.7)
        self.assertEqual(report['allocated_core_seconds'],3200)
        self.assertEqual(report['status'],'PPRIME_FORMAL_STOP_REPORT_ROOT_NO_FURTHER_DISPATCH')
        self.assertFalse(report['gates']['actual_allocated_cost_within_1_5x_pilot_estimate'])

    def test_common_n1_is_never_removed_from_full_acceptance_denominator(self):
        p=coverage(['a','b'],['a','b'],1)
        self.assertTrue(p['baseline_coverage_complete']);self.assertFalse(p['whole_common_coverage_complete'])
        self.assertEqual(coverage(['a','b'],['a'],0)['missing_records'],1)
        with self.assertRaises(ValueError):coverage(['a'],['a','a'],0)

    def test_failed_pilot_outcomes_reused_as_failures_not_filled_labels(self):
        pair={'once_key':'k','record_id':'r','canonical_geometry_id':'g','molecule_id':'m','stable_raw_audit_key_sha256':'s','stable_raw_audit_selected':False}
        entry={'record_id':'r','all_twelve_success':False,'all_twelve_raw_retained_verified':False,'ledger':{'fixture':True},'stable_raw_audit_key_sha256':'s','stable_raw_audit_selected':False}
        reused,new=split_imports([pair],{'k':entry},set())
        self.assertFalse(reused[0]['all_twelve_success']);self.assertFalse(new)
        with self.assertRaises(ValueError):split_imports([pair],{'k':entry},{'r'})
        self.assertEqual(split_imports([pair],{},set())[1],[pair])


if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('NO_SUBPROCESS_ALLOWED_IN_CONTROLLED_TESTS')):
        unittest.main(verbosity=2)
