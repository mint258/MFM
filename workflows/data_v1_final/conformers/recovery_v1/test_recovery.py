"""Six new recovery metadata boundaries; run only in a Root CPU allocation."""
from __future__ import annotations
import argparse,copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from recovery_common import MISSING,load_plan,scientific_sha,task_sha,terminal_parents
from close_recovered import merged_refs

class RecoveryBoundaries(unittest.TestCase):
    def old(self):
        return [{'molecule_id':f'old{i}','reference':{'molecule_id':f'old{i}','path':f'/old/{i}'}} for i in range(334)]
    def new(self):
        return [{'molecule_id':mid,'path':'/new/'+mid} for mid in MISSING]
    def test_old334_plus_only_missing_two_conserves336(self):
        old=self.old();before=copy.deepcopy(old)
        refs=merged_refs(old,self.new())
        self.assertEqual(len(refs),336);self.assertEqual(old,before)
        self.assertEqual({r['path'] for r in refs if r['molecule_id'].startswith('old')},{f'/old/{i}' for i in range(334)})
    def test_control_and_duplicate_paths_cannot_enter_union(self):
        with self.assertRaises(ValueError):merged_refs(self.old(),self.new()+[{'molecule_id':'control','path':'/control'}])
        new=self.new();new[0]['path']='/old/0'
        with self.assertRaises(ValueError):merged_refs(self.old(),new)
    def test_elapsed_is_only_comparison_exclusion(self):
        packet={'summary':{'elapsed_seconds':1.,'seed':4},'conformers':[{'coordinates':[[1.,2.,3.]]}], 'statistics':{'x':2}}
        other=copy.deepcopy(packet);other['summary']['elapsed_seconds']=999.
        self.assertEqual(scientific_sha(packet),scientific_sha(other))
        for part in ('seed','coordinates','statistics'):
            changed=copy.deepcopy(packet)
            if part=='seed':changed['summary']['seed']=5
            elif part=='coordinates':changed['conformers'][0]['coordinates'][0][0]=1.0000000001
            else:changed['statistics']['x']=3
            self.assertNotEqual(scientific_sha(packet),scientific_sha(changed))
    def test_original_task_digest_preserves_seed_inputs(self):
        task={'meta':{'molecule_id':'m','cohort':'retry_once'},'records':[{'record_id':'old:4'}],'existing_conformers':[]}
        changed=copy.deepcopy(task);changed['meta']['cohort']='retry_twice'
        self.assertNotEqual(task_sha(task),task_sha(changed))
    def test_timeout_exit_zero_and_steps_not_double_charged(self):
        text='JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS\n4520364|TIMEOUT|0:0|14425|16\n4520364.batch|CANCELLED|0:15|14429|16\n99|COMPLETED|0:0|2|16\n'
        rows=terminal_parents(text)
        self.assertEqual(rows['4520364']['state'],'TIMEOUT')
        self.assertEqual(sum(r['allocated_core_seconds'] for r in rows.values()),230832)
        self.assertEqual(set(rows),{'4520364','99'})
    def test_pending_plan_cannot_start_science(self):
        plan={'schema':'SPRIME_MISSING_RECOVERY_PLAN_V1','original_job_id':'4520364',
            'expected_original_molecules':336,'expected_missing_molecules':MISSING,
            'replay_control_count':14,'workers':16,'cpus':16,'memory_gib':64,
            'new_logical_retry_count':0,'scientific_recipe_changed':False,
            'formal_generation_authorized':False,'max_output_bytes':8*1024**3,
            'closure_max_output_bytes':1024**3,'quota_reserve_bytes':200000000000,
            'status':'PENDING_ROOT_BUDGET_AND_RESOURCE_REVIEW'}
        with patch.object(Path,'read_text',return_value=json.dumps(plan)):
            with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):load_plan('/fixture',approved=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root-preflight',type=Path,required=True)
    a=p.parse_args()
    from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as runtime
    runtime.root_guard(a.root_preflight,Path(__file__),1024**3,3600)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryBoundaries)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    runtime.checkpoint();return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())