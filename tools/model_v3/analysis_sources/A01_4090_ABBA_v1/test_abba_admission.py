"""Pure metadata tests. No CUDA, model, corpus, Slurm/SSH command or reservation."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import abba_contract as c
import admit_abba as launch


def numeric_values():
    options={'backbone_checkpointing':None,'precision':'fp32','tf32':False,'fused_adamw':False}
    sources={'tools/model_v3/single_a_benchmark.py':'a'*64}
    config={'code_sha':c.CODE,'prereg_sha':c.PREREG,'candidate_options_sha256':c.OPTIONS_SHA,
        'gpu_uuid':c.GPU,'gpu_name':'NVIDIA GeForce RTX 4090','node':c.NODE,'seed':0,
        'gpu':{'uuid':c.GPU,'name':'NVIDIA GeForce RTX 4090','driver_version':'560.35.05','total_bytes':49140<<20},
        'gpu_total_bytes':48538<<20,'model':{'backbone':{'dim':512,'layers':6}},
        'reference':options,'candidate':{**options,'backbone_checkpointing':False},'source_sha256':sources}
    config['configuration_sha256']=c.canonical(config)
    summary={'status':'PAIRED_GATES_PASS','full_A_numeric_acceptance':True,'fixed_batch_pass':True,
        'trajectory_pass':True,'smoke':False,'input':'native_s',
        'timing_kind':'paired_two_resident_models_diagnostic_not_standalone_speed',
        **{key:config[key] for key in ('code_sha','prereg_sha','candidate_options_sha256','gpu_uuid','configuration_sha256')}}
    return {'configuration':config,'summary':summary,'run_status':{'status':'PAIRED_GATES_PASS','failure':None,
        'cleanup_errors':[],'job_id':'4520456','stream_cleanup':{'errors':[],'input_descriptors_closed':True}},
        'provenance':{'source_files':sources,'source_inventory_sha256':c.canonical(sources),'code_sha':c.CODE,
            'full_native_A_numeric_gates_passed':True},
        'ready':{'source_inventory_sha256':c.canonical(sources),'code_sha':c.CODE,'optimizer_updates':500,
            'status':'H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL'},
        'fixed_batch_gate':{'pass':True,'batches':20,'results':[{'pass':True} for _ in range(20)]},
        'trajectory_gate':{'pass':True,'updates':500,'results':[{'pass':True} for _ in range(500)]}}


def node(alloc=0,cpu_alloc=16,total=256000):
    return f'NodeName={c.NODE} CPUAlloc={cpu_alloc} CPUTot=128 RealMemory={total} AllocMem={alloc} State=MIXED'


def test_complete_numeric_proof_does_not_grant_speed_or_guess_commercial_capacity():
    result=c.numeric_gate(numeric_values())
    assert result['full_A_numeric_acceptance'] is True and result['standalone_speed_inferred'] is False
    assert result['original_GPU_observation']['total_bytes']==49140<<20
    assert result['original_torch_GPU_total_bytes']==48538<<20
    assert result['SDK_verification_inferred'] is False


@pytest.mark.parametrize('corruption',('hardware3090','uuid','candidate','fixed_missing','trajectory_failure',
    'source_closure','config_hash','cleanup','gate_only','half_run'))
def test_numeric_gate_rejects_incomplete_or_mismatched_source_proofs(corruption):
    values=numeric_values()
    if corruption=='hardware3090': values['configuration']['gpu_name']='NVIDIA GeForce RTX 3090'
    elif corruption=='uuid': values['summary']['gpu_uuid']='GPU-'+'0'*8+'-'+'0'*4+'-'+'0'*4+'-'+'0'*4+'-'+'0'*12
    elif corruption=='candidate': values['configuration']['candidate']['fused_adamw']=True
    elif corruption=='fixed_missing': values['fixed_batch_gate']['results'].pop()
    elif corruption=='trajectory_failure': values['trajectory_gate']['results'][-1]['pass']=False
    elif corruption=='source_closure': values['provenance']['source_inventory_sha256']='0'*64
    elif corruption=='config_hash': values['configuration']['configuration_sha256']='0'*64
    elif corruption=='cleanup': values['run_status']['cleanup_errors']=['bad']
    elif corruption=='gate_only': values['summary']['timing_kind']='standalone'
    else: values['ready']['optimizer_updates']=499
    with pytest.raises(ValueError): c.numeric_gate(values)


def test_AllocMem_is_used_even_when_queue_declarations_are_small():
    with pytest.raises(ValueError,match='85%'): c.node_memory(node(alloc=170000),'1|foreign|R|1G|16\n')
    result=c.node_memory(node(alloc=80000),'1|foreign|R|1G|16\n')
    assert result['commitment_MiB']=='80000' and result['with_this_job_MiB']=='145536'


def test_all_users_per_cpu_pending_requests_and_own_allocation_are_counted():
    queue='1|foreign|R|2Gc|16\n2|other|PD|16Gn|16\n'
    result=c.node_memory(node(alloc=0),queue)
    assert Decimal(result['all_user_declared_MiB'])==49152
    allocated=c.node_memory(node(alloc=80000),queue,already_allocated=True)
    assert allocated['new_request_added'] is False and allocated['with_this_job_MiB']=='80000'


@pytest.mark.parametrize('corruption',('duplicate','unknown_memory','cpu','down','node','missing_AllocMem','equal85'))
def test_controller_and_queue_unknowns_fail_closed(corruption):
    raw=node(); queue='1|foreign|R|1G|16\n'
    if corruption=='duplicate': raw+=' AllocMem=1'
    elif corruption=='unknown_memory': queue='1|foreign|R|unknown|16\n'
    elif corruption=='cpu': raw=node(cpu_alloc=120)
    elif corruption=='down': raw+=' DRAIN'
    elif corruption=='node': raw=raw.replace(c.NODE,'compute-0-21')
    elif corruption=='missing_AllocMem': raw=raw.replace(' AllocMem=0','')
    else: raw=node(alloc=152064)  # 152064+65536 == .85*256000.
    with pytest.raises(ValueError): c.node_memory(raw,queue)


def test_physical_memory_reserve_is_after_new64GiB_working_set():
    value=c.physical_memory('MemTotal: 262144000 kB\nMemAvailable: 220000000 kB\n')
    assert value['planned_working_set_MiB']==65536
    with pytest.raises(ValueError): c.physical_memory('MemTotal: 262144000 kB\nMemAvailable: 80000000 kB\n')


def test_quota_requires_fresh_success_and64GiB_after_new_output():
    raw='/dev/sda1 1000 100000000 120000000 0 10 0 0\n'
    result=c.quota(raw); assert result['available_bytes']-c.OUTPUT_BUDGET>=64<<30
    with pytest.raises(ValueError): c.quota('/dev/sda1 1000 67109864 67109864 0 10 0 0\n')
    c.fresh({'returncode':0,'captured_unix':100,'completed_unix':101},now=150)
    with pytest.raises(ValueError): c.fresh({'returncode':0,'captured_unix':100,'completed_unix':101},now=191)
    with pytest.raises(ValueError): c.fresh({'returncode':1,'captured_unix':100,'completed_unix':101},now=150)


@pytest.mark.parametrize('corruption',('foreign','name','capacity','driver','duplicate'))
def test_selected_UUID_must_be_idle_and_match_observed_original_NVML(corruption):
    original=numeric_values()['configuration']['gpu']
    query=c.GPU+', NVIDIA GeForce RTX 4090, 560.35.05, 49140, 49000\n'; apps=''
    assert c.gpu_idle(query,apps,original)['NVML_total_bytes']==original['total_bytes']
    if corruption=='foreign': apps=c.GPU+', 123, python, 100\n'
    elif corruption=='name': query=query.replace('4090','3090')
    elif corruption=='capacity': query=query.replace('49140','24576')
    elif corruption=='driver': query=query.replace('560.35.05','590.44.01')
    else: query+=query
    with pytest.raises(ValueError): c.gpu_idle(query,apps,original)


def test_exact_parent_C0_cannot_be_replaced_by_batch_or_failed_parent():
    raw='4520456|zixiao|COMPLETED|0:0|3043|16\n'
    assert c.parent_c0(raw,'4520456')['elapsed_seconds']==3043
    for bad in (raw.replace('4520456|','4520456.batch|'),raw.replace('0:0','1:0'),raw.replace('zixiao','foreign')):
        with pytest.raises(ValueError): c.parent_c0(bad,'4520456')


@pytest.mark.parametrize('change',('memory','cpu','node','cgroup','UUID'))
def test_actual_worker_process_and_controller_memory_must_match(change):
    env={'SLURM_JOB_ID':'9001','SLURM_CPUS_PER_TASK':'16','CUDA_VISIBLE_DEVICES':c.GPU}
    raw='JobId=9001 NodeList='+c.NODE+' NumCPUs=16 AllocTRES=cpu=16,mem=64G MinMemoryNode=64G '
    group='1:freezer:/slurm/uid_1278/job_9001/step_batch\n'
    assert launch.own_allocation(raw,env,group,set(range(16)))['allocated_memory_TRES_readback_claimed']
    if change=='memory': raw=raw.replace('mem=64G','mem=32G')
    elif change=='cpu': env['SLURM_CPUS_PER_TASK']='8'
    elif change=='node': raw=raw.replace(c.NODE,'compute-0-21')
    elif change=='cgroup': group=group.replace('9001','9002')
    else: env['CUDA_VISIBLE_DEVICES']='0'
    with pytest.raises(ValueError): launch.own_allocation(raw,env,group,set(range(16)))


def test_minimum_node_memory_is_not_misreported_as_allocated_TRES():
    env={'SLURM_JOB_ID':'9001','SLURM_CPUS_PER_TASK':'16','CUDA_VISIBLE_DEVICES':c.GPU}
    proof=launch.own_allocation('JobId=9001 NodeList='+c.NODE+' NumCPUs=16 TRES=cpu=16 MinMemoryNode=64G ',
        env,'1:freezer:/slurm/uid_1278/job_9001/step_batch\n',set(range(16)))
    assert proof['allocated_memory_TRES_readback_claimed'] is False and proof['MinMemoryNode']==['64G']


def test_transport_outage_does_not_fabricate_allocated_memory_or_override_semantic_failures():
    env={'SLURM_JOB_ID':'9001','SLURM_CPUS_PER_TASK':'16','CUDA_VISIBLE_DEVICES':c.GPU,'SLURM_MEM_PER_NODE':'65536'}
    proof=launch.own_allocation(None,env,'1:freezer:/slurm/uid_1278/job_9001/step_batch\n',set(range(16)))
    assert proof['allocated_memory_TRES_readback_claimed'] is False
    assert proof['requested_memory_from_exact_bound_Root_sbatch_MiB']==65536
    assert launch.backend_unavailable({'returncode':1,'stdout':'','stderr':'Unable to contact slurm controller: Connection refused'})
    assert not launch.backend_unavailable({'returncode':1,'stdout':'','stderr':'Invalid user or bad memory'})
    assert not launch.backend_unavailable({'returncode':0,'stdout':'','stderr':'Connection refused'})
    env['SLURM_MEM_PER_NODE']='32768'
    with pytest.raises(ValueError): launch.own_allocation(None,env,'job_9001/step_batch',set(range(16)))
    now=launch.time.time(); argv=['scontrol','show','node',c.NODE]
    raw={'argv':argv,'captured_unix':now,'completed_unix':now,'returncode':0,'stdout':node(),'stderr':''}
    class Own:
        def __init__(self): self.reason='Unable to contact slurm controller: Connection refused'; self.rows=[]
        def command(self,argv,**kwargs):
            return {**raw,'argv':argv,'returncode':1,'stdout':'','stderr':self.reason}
        def add(self,row): self.rows.append(row)
    own=Own(); frame={'observations':[raw]}; bound=launch.WorkerObserve(own,frame)
    reused=bound.command(argv)
    assert reused['reused_Root_observation'] is True and own.rows==[reused]
    c.node_memory(reused['stdout'],'',already_allocated=False)
    own.reason='Invalid job memory contract'
    with pytest.raises(ValueError): bound.command(argv)
    own.reason='Connection refused'; frame['observations']=[{**raw,'captured_unix':now-100}]
    with pytest.raises(ValueError): bound.command(argv)


def member_values():
    config={'job_id':'9001','source_sha256':{'unit_source.py':'a'*64}}
    config['configuration_sha256']=c.canonical(config)
    summary={'status':'STANDALONE_TIMING_COMPLETED','abba_position':2,'role':'candidate','series_id':c.SERIES,
        'seed':0,'input':'native_s','smoke':False,'measured_updates':20,'warmup_updates':2,'gpu_uuid':c.GPU,
        'code_sha':c.CODE,'prereg_sha':c.PREREG,'candidate_options_sha256':c.OPTIONS_SHA,
        'foreign_gpu_risk_observed':False,'padding_exploration':False,'configuration_sha256':config['configuration_sha256']}
    status={'status':'STANDALONE_TIMING_COMPLETED','failure':None,'cleanup_errors':[],
        'stream_cleanup':{'errors':[],'input_descriptors_closed':True}}
    supervisor={'job_id':'9001','status':'COMPLETED','exit_code':0,'first_failure':None,'retirement':None,
        'remaining_recorded_processes_before_retirement':[],'private_storage_cleanup_errors':[],
        'foreign_gpu_processes_signalled':False,'gpu_uuid':c.GPU,'private_storage_final':{'first_sampling_failure':None}}
    return summary,status,config,supervisor,{'job_id':'9001'}


@pytest.mark.parametrize('corruption',('position','role','updates','warmup','foreign','cleanup','residual','config'))
def test_sequential_member_requires_closed_full_standalone_contract(corruption):
    summary,status,config,supervisor,account=member_values()
    assert c.member_closed(2,summary,status,config,supervisor,account)=='9001'
    if corruption=='position': summary['abba_position']=3
    elif corruption=='role': summary['role']='reference'
    elif corruption=='updates': summary['measured_updates']=500
    elif corruption=='warmup': summary['warmup_updates']=0
    elif corruption=='foreign': summary['foreign_gpu_risk_observed']=True
    elif corruption=='cleanup': status['cleanup_errors']=['bad']
    elif corruption=='residual': supervisor['remaining_recorded_processes_before_retirement']=[{'pid':123}]
    else: config['configuration_sha256']='0'*64
    with pytest.raises(ValueError): c.member_closed(2,summary,status,config,supervisor,account)


def submitted():
    family=launch.OUT/'position2_unitnonce'
    return {'schema':'model_v3_A01_4090_ABBA_submission_v1','status':'SUBMITTED','actual_job_id':'9001','nonce':'unitnonce',
        'source_pins_sha256':'a'*64,'position':2,'series_id':c.SERIES,'root_uid':1278,'root_hostname':'sonmi',
        'submission':{'returncode':0,'argv':['sbatch','--parsable','--partition=all','--nodelist='+c.NODE,
            '--cpus-per-task=16','--mem=64G','--time=00:20:00','--output='+str(family/'slurm.log'),str(c.HERE/'A01_4090_ABBA_member_v1.sbatch')],
            'stdout':'9001\n'},'output_root':str(family),'benchmark_root':str(family/'benchmark')}


@pytest.mark.parametrize('corruption',('nonce','position','source','time','receipt_job','output','host'))
def test_bound_actual_submission_cannot_change_worker_identity_or_budget(corruption):
    value=submitted(); launch.validate_submission(value,2,'unitnonce','a'*64,'9001')
    if corruption=='nonce': value['nonce']='wrong'
    elif corruption=='position': value['position']=3
    elif corruption=='source': value['source_pins_sha256']='b'*64
    elif corruption=='time': value['submission']['argv'][-3]='--time=00:45:00'
    elif corruption=='receipt_job': value['submission']['stdout']='9002\n'
    elif corruption=='output': value['output_root']='/tmp/hidden_output'
    else: value['root_hostname']=c.NODE
    with pytest.raises(ValueError): launch.validate_submission(value,2,'unitnonce','a'*64,'9001')


def test_raw_metadata_binding_and_immutable_receipts(tmp_path):
    file=tmp_path/'receipt.json'; c.save(file,{'value':1}); bound=c.ref(file)
    assert c.read(bound)=={'value':1}
    with pytest.raises(FileExistsError): c.save(file,{'value':2})
    file.write_bytes(b'{}\n')
    with pytest.raises(ValueError): c.read(bound)
    with pytest.raises(ValueError): c.strict_json('{"x":1,"x":2}')


def test_template_preserves_real20minute_cap_and22_update_frozen_entry():
    raw=(Path(__file__).parent/'A01_4090_ABBA_member_v1.sbatch').read_text()
    assert '#SBATCH --mem=64G' in raw and '#SBATCH --time=00:20:00' in raw
    assert c.GPU in raw and c.NODE in raw and '/chemprop/bin/python' in raw
    source=(Path(__file__).parent/'admit_abba.py').read_text()
    assert "'--expected-gpu','4090'" in source and 'single_a_benchmark.py' in source
    assert c.JOB_WALL==1200 and c.SUPERVISOR_WALL==1100
