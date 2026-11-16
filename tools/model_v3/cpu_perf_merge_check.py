"""Validate only modules affected by the model-v3 advance after the full suite."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

import cpu_perf_regression as suite
from private_runtime_storage import PrivateStorage, _write_exclusive
import v2_run_development as dispatch


def main():
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':
        raise ValueError('CPU-only merge validation required')
    cores=suite.allocated_cpus()
    if len(cores)<16:
        raise ValueError('Existing integration fixtures require actual sixteen CPUs')
    os.sched_setaffinity(0,cores)
    root=suite.BASE/'runs/model_v3_cpu_perf_20261112'/('merge_'+os.environ['SLURM_JOB_ID'])
    suite.storage(root);root.mkdir(parents=True,exist_ok=False)
    suite.require_capacity(suite.filesystem_status('/tmp'),2*1024**3,10000)
    suite.PRIVATE=PrivateStorage(Path('/tmp')/('mv3n_'+os.environ['SLURM_JOB_ID']),budget_bytes=2*1024**3)
    receipt=root/'private_storage.json';pin=_write_exclusive(receipt,suite.PRIVATE.bindings)
    os.environ.update(suite.PRIVATE.bindings['environment'])
    os.environ.update(MODEL_V3_STORAGE_BINDINGS_PATH=str(receipt),MODEL_V3_STORAGE_BINDINGS_SHA256=pin)
    suite.PRIVATE.start()
    try:
        output=dispatch.BASE/('UNIT_merge_'+os.environ['SLURM_JOB_ID'])
        config=dict(output=str(output),checkpoint='/synthetic/unopened.pt',panel='v3',
                    reuse_predictions='/synthetic/unopened-cache',condition='P',evaluation_scope='forward')
        path=root/'configuration.json';path.write_text(json.dumps(config)+'\n')
        budget=root/'output_budget.json';budget.write_text(json.dumps(dict(schema='MODEL_OUTPUT_BUDGET_V1',roots=[str(output)]))+'\n')
        args=dispatch.command('dev',config,path)
        assert '--reuse-predictions' in args and '--condition' in args
        gpu='GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        with patch.object(dispatch,'REGISTRY',budget),patch.object(sys,'argv',['dispatch','--mode','dev','--configuration',str(path)]),patch.dict(os.environ,CUDA_VISIBLE_DEVICES=gpu):
            with patch.object(dispatch.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
                assert dispatch.main()==0
                invoked=run.call_args.args[0]
                assert invoked[3]=='tools/model_v3/model_gpu_registry.py' and invoked[4:6]==['--gpu',gpu]
                assert '--reuse-predictions' in invoked and '--condition' in invoked
        subprocess.run(['bash','-n',str(suite.REPO/'tools/model_v3/v2_run_development.sbatch')],check=True)
        launch=(suite.REPO/'tools/model_v3/v2_run_development.sbatch').read_text()
        assert 'MODEL_V3_FOLLOWON_PLAN' in launch and 'UUID lock shared' in launch
        names=['test_model_v2_archive_wandb','test_model_v3_decision_evidence','test_model_v3_dev_evaluation',
               'test_model_v3_dev_membership','test_model_v3_downstream_targets','test_model_v3_reselection',
               'test_model_v3_seven_task_selection','test_model_v3_condition_clip','test_v2_development_dispatch',
               'test_cpu_perf_concurrency','test_v3_r3_invariance','test_model_v3_wandb_layout']
        files=[suite.REPO/'current/tests'/(name+'.py') for name in names]
        assert all(path.is_file() for path in files)
        xml=root/'junit.xml'
        argv=[sys.executable,'-B','-m','pytest',*map(str,files),'-q','-p','no:cacheprovider',
              f'--junitxml={xml}',f'--basetemp={root/"test_tmp"}']
        execution=suite.supervise(argv,root,root/'pytest.log')
        counts={key:sum(int(node.get(key,0)) for node in ET.parse(xml).getroot().iter('testsuite'))
                for key in ('tests','failures','errors','skipped')}
        passed=execution['returncode']==0 and counts['tests']>0 and not counts['failures'] and not counts['errors']
        value=dict(status='PASS' if passed else 'FAIL',job=os.environ['SLURM_JOB_ID'],node=os.environ['MFM_CPU_EXPECTED_NODE'],
                   native_source_revision=os.environ['MFM_CPU_SOURCE_REVISION'],base_commit='42b75b98a4d044b968c8fdec6294446bef3a1a1b',
                   original_full_regression_job='4530454',counts=counts,test_files=names,cpu_affinity=cores,
                   checks=['panel_v3_arguments_preserved','registered_GPU_wrapper_preserved','followon_and_shell_syntax_preserved'],
                   execution=execution,final_capacity=suite.storage(root))
        (root/'summary.json').write_text(json.dumps(value,indent=2)+'\n')
        print(json.dumps({k:value[k] for k in ('status','job','counts')}),flush=True)
        return int(not passed)
    finally:
        suite.PRIVATE.stop()


if __name__=='__main__':
    raise SystemExit(main())
