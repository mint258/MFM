"""Four metadata-only Native resource wiring cases; no scheduler/model/data."""
from copy import deepcopy
import pytest
import native_resources as r


def test_auto_allocation_records_actual_memory_without_claiming_software_is_allocated():
    env={'SLURM_JOB_ID':'12345','SLURM_CPUS_PER_TASK':'16','CUDA_VISIBLE_DEVICES':r.GPU,
         'SLURM_MEM_PER_NODE':'375000'}
    value=r.validate_allocation('12345',env,r.NODE,1278,'0::/slurm/uid_1278/job_12345/step_batch\n')
    assert value['actual_Slurm_memory_environment']['SLURM_MEM_PER_NODE']=='375000'
    assert value['software_memory_budget_bytes']==32<<30 and value['software_RSS_limit_bytes']==28<<30
    assert value['fixed_memory_request_claimed'] is False
    env.pop('SLURM_MEM_PER_NODE')
    assert r.validate_allocation('12345',env,r.NODE,1278,'0::/job_12345/step_batch\n')[
        'actual_Slurm_memory_environment']['SLURM_MEM_PER_NODE'] is None
    for change in ({'SLURM_CPUS_PER_TASK':'8'},{'CUDA_VISIBLE_DEVICES':'foreign'},{'SBATCH_MEM_PER_NODE':'32768'}):
        with pytest.raises(ValueError):
            r.validate_allocation('12345',{**env,**change},r.NODE,1278,'0::/job_12345/step_batch\n')
    with pytest.raises(ValueError):r.validate_allocation('12345',env,r.NODE,1278,'0::/foreign/step_batch\n')


def test_sbatch_and_environment_forbid_memory_override_but_keep_original_other_resources(monkeypatch):
    argv=['sbatch','--parsable','--partition=all','--nodelist='+r.NODE,'--cpus-per-task=16','--time=02:00:00','/script']
    r.validate_sbatch(argv)
    for item in ('--mem=32G','--mem=0','--mem','--mem-per-cpu=2G','--mem-per-gpu=32G','--exclusive','--oversubscribe'):
        with pytest.raises(ValueError):r.validate_sbatch(argv+[item])
    monkeypatch.setenv('SBATCH_MEM_PER_NODE','32768');monkeypatch.setenv('SBATCH_EXCLUSIVE','1')
    monkeypatch.setenv('NATIVE_METADATA_UNIT_PRESERVED','yes')
    env=r.clean_environment()
    assert not any(key.startswith('SBATCH_') for key in env)
    assert env['NATIVE_METADATA_UNIT_PRESERVED']=='yes'


def test_both_root_and_worker_delegate_exact_original_budget_to_the_same_shared_policy(monkeypatch):
    calls=[]
    class Policy:
        def assess(self,*args,**kwargs):
            calls.append((args,kwargs));return {'actual_shared_policy_called':True}
    monkeypatch.setattr(r,'shared',lambda:Policy())
    for job in (None,'12345'):
        assert r.assess_raw('node','queue','meminfo',registry='/bound_registry.json',record_id='own_slot',job=job)=={
            'actual_shared_policy_called':True}
    assert [row[1]['current_job_id'] for row in calls]==[None,'12345']
    assert all(row[0]==('node','queue','meminfo') and row[1]==dict(node=r.NODE,software_budget_bytes=32<<30,
        rss_limit_bytes=28<<30,registry_path='/bound_registry.json',current_job_id=job,current_reservation_id='own_slot')
        for row,job in zip(calls,(None,'12345')))


def test_actual_shared_registration_changes_only_optional_gpu_map_and_rejects_slot_reuse():
    api=r.shared()
    record=api.make_registration(registration_id=r.registration_id(r.N/'native_S_B20k_v3',27),
        node=r.NODE,gpu_uuid=r.GPU,software_budget_bytes=32<<30,rss_limit_bytes=28<<30,
        Root_source=r.binding(r.HERE/'long_operations.py'),source_pins=r.binding(r.HERE/'source_pins.json'),
        job_id_field='actual_sbatch_job_id')
    value={'schema':'metadata_fixture','reservations':{'own':{'remaining_bytes':2<<30,'principal':'preserved'}}}
    before=deepcopy(value);api.put_registration(value,record)
    assert {key:item for key,item in value.items() if key!='GPU_software_memory'}==before
    assert value['GPU_software_memory'][record['registration_id']]==record
    with pytest.raises(ValueError):api.put_registration(value,{**record,'software_budget_bytes':64<<30})
    for slot in (True,0,109):
        with pytest.raises(ValueError):r.registration_id(r.N/'native_S_B20k_v3',slot)
