"""Managed short CPU worker: new delivery tests, then one P seal/hash producer."""
import argparse,fcntl,json,os,time
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json
from cpu_ssh_runtime import execution_handle


def run(c):
    if c.get('ready') is not True or os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('Activated CPU-only delivery worker required')
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c['output']);output.mkdir(parents=True,exist_ok=True)
        with (output/'owner.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/'primary_complete.json').exists():raise ValueError('Delivery producer already complete; reuse it')
            tests=output/'new_logic_tests.json'
            if not tests.exists():
                import pytest
                started=time.monotonic()
                result=pytest.main(['-q','-p','no:cacheprovider','--basetemp',str(output/'test_scratch'),str(Path(__file__).with_name('test_independent_delivery.py'))])
                atomic_json(tests,dict(status='PASS' if result==0 else 'FAIL',exit_code=int(result),seconds=time.monotonic()-started,new_test_cases=4,old_scientific_tests_repeated=False))
            if json.loads(tests.read_text())['status']!='PASS':raise ValueError('New delivery controls failed')
            def should_stop():
                return stop.requested or time.time()+c['work_unit_seconds']>=float(os.environ['P_MANAGED_STOP_NEW_UNITS_AT'])
            if should_stop():return 75
            require_cpu_admission(c)
            from independent_delivery import seal_independent
            value=seal_independent(c['repo'],c,should_stop=should_stop)
            if value is None:return 75
            atomic_json(output/'primary_complete.json',dict(status='P_INDEPENDENT_DELIVERY_COMPLETE_WAIT_A4',execution_id=execution_handle(),seal='results/p_recipe/independent_delivery_20261126.json',new_logic_tests=str(tests),new_fits=0,new_bootstrap_draws=0,new_plots=0,final_REPORT_generated=False))
            return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--configuration',required=True);a=parser.parse_args()
    raise SystemExit(run(json.loads(Path(a.configuration).read_text())))