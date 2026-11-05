"""Finite metadata accounting + actual engineering runner integration.

Native quota/profile receipts here are labelled engineering fixtures. No real
quota reservation, final-D evidence or scientific acceptance is asserted.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1 import v3_long_run_storage as storage
from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound,write_once,encoded

BASE = '5ac19e805a9ebab9dca516ba7201bae0666d2515'
AUTH = 'ENGINEERING_METADATA_FIXTURE'


def prepare(root,*,segment='one',job=None,launches=160,old_roots=None):
    root.mkdir(parents=True,exist_ok=True)
    ref = proxy.engineering_request(root/'proxy',code_sha=BASE,budget=3)
    request = read_bound(ref); config = read_bound(request['configuration'])
    counts = dict(launch_attempts=launches,successful_segments=max(0,launches-32),failed_attempts=min(32,launches),
        checkpoint_attempts=192,complete_checkpoints=128,successful_panels=16,failed_panels=8,wsd_children=0,events=192,ack_attempts=256)
    config['long_run_policy'] = dict(schema='model_v3_long_run_policy_v1',segment_bytes=2 << 30,segment_seconds=300,
        durable_bytes=8 << 30,metadata_bytes=64 << 20,metadata_records=20000,managed_roots=512,inode_limit=50000,
        quota_max_age_seconds=90,checkpoint_bytes=256 << 20,counts=counts)
    config['proxy_contract']['sample_plan']['max_total_checkpoints'] = 192
    request['configuration'] = write_once(root/'configuration.json',config)
    registry = write_once(root/'initial_roots.json',{'schema':'model_v3_long_run_initial_roots_v1','roots':old_roots or []})
    zeros = {key:0 for key in storage.COUNTS}
    phase = write_once(root/'Root_record.json',dict(reservation_id='fixture-slot',uid=os.getuid(),durable_root=str(root/'durable'),
        reserved_additional_bytes=8 << 30,authority=AUTH,phase_ledger_id='fixture-phase',initial_counts=zeros))
    principal = write_once(root/'principal.json',dict(schema='model_v3_Root_durable_reservation_v1',reservation_id='fixture-slot',uid=os.getuid(),
        status='ROOT_COORDINATOR_RESERVED_FINITE',policy_sha256=proxy.canonical_hash(config['long_run_policy']),max_bytes=8 << 30,
        counts=counts,science_identity_sha256=proxy.identity(config),initial_existing_bytes=0,reserved_additional_bytes=8 << 30,
        authority=AUTH,Root_reservation_record=phase,durable_root=str(root/'durable'),filesystem='/dev/sda1',initial_counts=zeros))
    profile = write_once(root/'profile.json',dict(schema='model_v3_Root_long_run_profile_v1',authority=AUTH,
        profile_identity_sha256=storage.profile_identity(config,request),code_sha=BASE,checkpoint_bytes=100 << 20,
        SDK_bytes_per_segment=1 << 20,save_seconds=1.,validation_seconds=1.,panel_seconds=1.,cleanup_seconds=1.,
        provider_future_state_bound_bytes=1024,optimizer_future_state_bound_bytes=1024,
        actual_final_D_profile=False,final_D_authority_verified=False,status='ENGINEERING_ONLY'))
    producer = root/'fixture_producer.py'; producer.write_text('# metadata fixture, not an actual publisher\n')
    feed = root/'live_quota.json'
    feed.write_bytes(encoded(dict(schema='model_v3_Root_live_quota_v1',uid=os.getuid(),host='sonmi',filesystem='/dev/sda1',returncode=0,
        captured_unix=time.time(),authority=AUTH,stdout='/dev/sda1 1000 1000000000 1000000000 0 0 0\n',
        inodes={'filesystem':'/dev/sda1','uid':os.getuid(),'captured_unix':time.time(),'available':1000000},
        producer_source_sha256=binding(producer)['sha256'],phase_ledger_id='fixture-phase',headroom_bytes=1 << 20,
        reservations={'fixture-slot':{'durable_root':str(root/'durable'),'principal_sha256':principal['sha256'],'remaining_bytes':8 << 30}})))
    descriptor = write_once(root/'feed_descriptor.json',dict(schema='model_v3_Root_quota_feed_descriptor_v1',uid=os.getuid(),
        filesystem='/dev/sda1',authority=AUTH,producer_source=binding(producer),feed_path=str(feed)))
    lease = write_once(root/'lease.json',dict(reservation_id='fixture-slot',authority=AUTH,created_unix=time.time()-1,expires_unix=time.time()+900))
    request['long_run'] = {'reservation_principal':principal,'profile':profile,'initial_roots':registry,
        'quota_feed_descriptor':descriptor,'lease':lease}
    job = job or root/'job1'
    admission = write_once(root/'admission.json',dict(schema='model_v3_Root_long_run_segment_admission_v1',
        stable_request_identity_sha256=storage.stable_request_identity(request),reservation_principal=principal,authority=AUTH,
        lease=lease,quota_feed_descriptor=descriptor,segment_id=segment,job_root=str(job),lineage_root=str(root/'canonical'),external_roots=[]))
    request['long_run']['Root_segment_admission'] = admission
    result = write_once(root/'request.json',request)
    return result,request,config


def renewal(root,request,*,segment,job,folder):
    folder.mkdir()
    value = deepcopy(request); old = read_bound(value['long_run']['Root_segment_admission'])
    feed_path = Path(read_bound(value['long_run']['quota_feed_descriptor'])['feed_path'])
    feed = json.loads(feed_path.read_text()); assert feed['authority'] == AUTH
    feed['captured_unix'] = time.time(); feed['inodes']['captured_unix'] = time.time()
    feed_path.write_bytes(encoded(feed))  # Explicit mutable engineering feed, not SDK/source/history.
    lease = write_once(folder/'lease.json',{**read_bound(value['long_run']['lease']),
        'created_unix':time.time()-1,'expires_unix':time.time()+900})
    value['long_run']['lease'] = lease
    value['long_run']['Root_segment_admission'] = write_once(folder/'admission.json',{**old,'lease':lease,
        'segment_id':segment,'job_root':str(job)})
    return write_once(folder/'request.json',value),value


def update_fixture_feed(request):
    path = Path(read_bound(request['long_run']['quota_feed_descriptor'])['feed_path'])
    value = json.loads(path.read_text()); assert value['authority'] == AUTH
    value['captured_unix'] = time.time(); value['inodes']['captured_unix'] = time.time()
    path.write_bytes(encoded(value))


def test_opt_in_policy_preserves_segment_limits_and_independent_caps(tmp_path):
    _,request,config = prepare(tmp_path)
    _,plan,_ = proxy.validate_request(request,input_kind='synthetic',engineering_only=True)
    assert plan.max_total_checkpoints == 192  # no prototype128 rejection
    assert storage.policy(config,plan)['counts']['launch_attempts'] == 160
    default = deepcopy(config); default.pop('long_run_policy')
    original_request = deepcopy(request); original_request['configuration'] = write_once(tmp_path/'default.json',default)
    with pytest.raises(ValueError,match='Bounded global checkpoint'):
        proxy.validate_request(original_request,input_kind='synthetic',engineering_only=True)
    for key,value in [('segment_bytes',(2 << 30)+1),('segment_seconds',7201)]:
        bad = deepcopy(config); bad['long_run_policy'][key] = value
        with pytest.raises(ValueError,match='segment2GiB/2h'): storage.policy(bad)


@pytest.mark.parametrize('part',['lease','quota_age','quota_zero','UID','filesystem','outstanding','profile','source'])
def test_missing_or_stale_authority_rejects_before_any_ledger(tmp_path,part):
    _,request,config = prepare(tmp_path)
    if part == 'lease':
        value = read_bound(request['long_run']['lease']); value['expires_unix'] = 1
        request['long_run']['lease'] = write_once(tmp_path/'bad_lease.json',value)
    elif part == 'profile':
        value = read_bound(request['long_run']['profile']); value['SDK_bytes_per_segment'] = 0
        request['long_run']['profile'] = write_once(tmp_path/'bad_profile.json',value)
    elif part == 'source': Path(read_bound(request['long_run']['quota_feed_descriptor'])['producer_source']['path']).write_text('changed')
    else:
        path = Path(read_bound(request['long_run']['quota_feed_descriptor'])['feed_path']); value = json.loads(path.read_text())
        if part == 'quota_age': value['captured_unix'] -= 1000
        elif part == 'quota_zero': value['stdout'] = '/dev/sda1 1000 0 0\n'
        elif part == 'UID': value['uid'] += 1
        elif part == 'filesystem': value['filesystem'] = '/other'
        else: value['reservations']['other'] = {'remaining_bytes':2 << 40}
        path.write_bytes(encoded(value))
    with pytest.raises(ValueError): storage.validate_admission(request,config)
    assert not (tmp_path/'durable').exists()


def test_synthetic_profile_cannot_be_promoted_to_science(tmp_path):
    _,request,config = prepare(tmp_path)
    config['engineering_only'] = False
    with pytest.raises(ValueError): storage.validate_admission(request,config)


def test_even_consistent_Root_labels_cannot_replace_actual_final_D_profile(tmp_path):
    _,request,config = prepare(tmp_path)
    config['engineering_only'] = False
    principal = read_bound(request['long_run']['reservation_principal'])
    root_record = read_bound(principal['Root_reservation_record']); root_record['authority'] = 'ROOT_ACTUAL'
    principal.update(authority='ROOT_ACTUAL',science_identity_sha256=proxy.identity(config),
        Root_reservation_record=write_once(tmp_path/'hypothetical_root_record.json',root_record))
    request['long_run']['reservation_principal'] = write_once(tmp_path/'hypothetical_principal.json',principal)
    profile = read_bound(request['long_run']['profile']); profile['authority'] = 'ROOT_ACTUAL'
    request['long_run']['profile'] = write_once(tmp_path/'still_not_final_D.json',profile)
    with pytest.raises(ValueError,match='Final-D actual profile missing'): storage.validate_admission(request,config)
    assert not (tmp_path/'durable').exists()


def test_all_old_failed_SDK_guard_cache_H0_roots_are_counted_and_nested_rejected(tmp_path):
    entries = []
    for name,kind in [('old','training'),('failed','failed'),('sdk','SDK'),('guard','external_guard'),('cache','cache'),('panel','H0_panel')]:
        folder = tmp_path/name; folder.mkdir(); (folder/'retained').write_bytes(b'x'*37)
        entries.append(dict(path=str(folder),kind=kind,must_exist=True,type='directory'))
    _,request,config = prepare(tmp_path/'meta',old_roots=entries)
    ledger = storage.DurableLedger(request,config)
    assert ledger.census() >= 6*37
    with pytest.raises(ValueError,match='nested'): ledger.register_root(tmp_path/'old/child',kind='cache')
    (tmp_path/'failed/retained').unlink()  # Only a synthetic test fixture; root remains.
    assert ledger.census() >= 5*37
    (tmp_path/'failed').rmdir()
    with pytest.raises(ValueError,match='disappeared'): ledger.census()


def test_65_segment_metadata_simulation_can_cross_prototype_lifetime_2GiB(tmp_path,monkeypatch):
    old = tmp_path/'old'; old.mkdir(); (old/'fixture').write_bytes(b'fixture')
    _,request,config = prepare(tmp_path/'meta',old_roots=[dict(path=str(old),kind='training',must_exist=True,type='directory')])
    ledger = storage.DurableLedger(request,config)
    actual = storage._runtime_census
    # Simulated historical byte count, not a physical>2GiB pytest artifact and
    # not evidence that64M or final-D training has run.
    monkeypatch.setattr(storage,'_runtime_census',lambda path: (3 << 30) if Path(path) == old else actual(path))
    assert ledger.census() > 2 << 30
    for number in range(65):
        update_fixture_feed(request); ledger.append('successful_segments','simulated-'+str(number),{'fixture_only':True})
    for number in range(71):
        update_fixture_feed(request); ledger.append('checkpoint_attempts','simulated-cp-'+str(number),{'fixture_only':True})
    assert sum(row['kind'] == 'successful_segments' for row in ledger.records()) == 65
    monkeypatch.setattr(storage,'_runtime_census',lambda path: (9 << 30) if Path(path) == old else actual(path))
    with pytest.raises(ValueError,match='durable'): ledger.census()


def test_operational_renewal_does_not_change_science_or_reset_counters(tmp_path):
    ref,request,config = prepare(tmp_path)
    ledger = storage.DurableLedger(request,config); ledger.append('failed_attempts','old-failure',{'fixture':True})
    _,next_request = renewal(tmp_path,request,segment='two',job=tmp_path/'job2',folder=tmp_path/'next')
    assert storage.stable_request_identity(next_request) == storage.stable_request_identity(request)
    again = storage.DurableLedger(next_request,config)
    assert sum(row['kind'] == 'failed_attempts' for row in again.records()) == 1
    changed = deepcopy(next_request); changed['input_projection']['adapter_sha256'] = '0'*64
    assert storage.stable_request_identity(changed) != storage.stable_request_identity(next_request)
    assert storage.profile_identity(config,changed) != storage.profile_identity(config,next_request)
    with pytest.raises(ValueError): storage.validate_admission(changed,config)


def test_active_holds_require_Root_closure_and_never_delete_actual_bytes(tmp_path):
    ref,request,config = prepare(tmp_path); job = tmp_path/'job1'; job.mkdir(); (job/'retained').write_bytes(b'x'*73)
    ledger = storage.DurableLedger(request,config)
    before = ledger.remaining()
    ledger.allocate_segment(request_ref=ref,segment_id='one',job_root=job,lineage_root=tmp_path/'canonical')
    after = ledger.remaining()
    assert before-after > 1 << 30
    closure = write_once(tmp_path/'closure.json',dict(schema='model_v3_Root_storage_segment_closure_v1',authority=AUTH,job_root=str(job)))
    ledger.seal_segment(job_root=job,Root_closure_ref=closure)
    assert ledger.remaining() > after+(1 << 30) and (job/'retained').read_bytes() == b'x'*73
    assert sum(row['kind'] == 'launch_attempts' for row in ledger.records()) == 1


def test_concurrent_clients_cannot_double_consume_one_finite_counter_slot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    _,request,config = prepare(tmp_path,launches=1)
    first,second = storage.DurableLedger(request,config),storage.DurableLedger(request,config)
    def consume(pair):
        ledger,name = pair
        try: ledger.append('failed_attempts',name,{'fixture':True}); return 'accepted'
        except ValueError: return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(consume,[(first,'one'),(second,'two')]))
    assert sorted(results) == ['accepted','rejected']
    assert sum(row['kind'] == 'failed_attempts' for row in first.records()) == 1


def test_counter_intent_survives_interrupted_materialization_without_reset(tmp_path):
    _,request,config = prepare(tmp_path,launches=1)
    ledger = storage.DurableLedger(request,config)
    ref = ledger.append('failed_attempts','one',{'fixture':True})
    Path(ref['path']).unlink()  # Synthetic interruption fixture; immutable intent retained.
    assert sum(row['kind'] == 'failed_attempts' for row in ledger.records()) == 1
    with pytest.raises(ValueError,match='failed_attempts cap'):
        ledger.append('failed_attempts','two',{'fixture':True})
    assert ledger.append('failed_attempts','one',{'fixture':True}) == ref


def test_reservation_refs_stay_out_of_shared_recipe_identity(tmp_path):
    _,request,config = prepare(tmp_path)
    other_request = deepcopy(request); other_request['long_run']['Root_segment_admission']['sha256'] = '0'*64
    assert proxy.identity(config) == proxy.identity(deepcopy(config))
    assert storage.stable_request_identity(request) == storage.stable_request_identity(other_request)
    other = deepcopy(config); other['proxy_contract']['validation']['seed'] += 1
    assert proxy.identity(config) != proxy.identity(other)


def test_metadata_CLI_validates_but_does_not_claim_real_reservation(tmp_path):
    ref,_,_ = prepare(tmp_path)
    tool = proxy.REPOSITORY/'tools/model_v3/storage_control.py'
    command = [sys.executable,str(tool),'validate','--request',ref['path'],'--request-sha256',ref['sha256']]
    missing = subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
    assert missing.returncode != 0
    result = subprocess.run([*command,'--input','synthetic','--engineering-only'],stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
    assert result.returncode == 0,result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['reservation_created_by_this_tool'] is False and receipt['scientific_acceptance'] is False


def test_long_accounting_preserves_true_model_Adam_provider_RNG_resume(tmp_path):
    import torch
    from test_model_v3_trainer import UnitTracker
    from test_model_v3_training import assert_tree_equal
    from phychem_mfm.phase1.v3_training import capture_rng_state
    old = torch.get_num_threads(),torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32,torch.are_deterministic_algorithms_enabled()
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False; torch.use_deterministic_algorithms(True)
    try:
        ref,request,config = prepare(tmp_path); plan = storage.policy(config)  # validates explicit finite envelope
        sample_plan = proxy.validate_request(request,input_kind='synthetic',engineering_only=True)[1]
        def build(request_ref,req,segment,name):
            job = tmp_path/name; job.mkdir()
            ledger = storage.DurableLedger(req,config)
            ledger.allocate_segment(request_ref=request_ref,segment_id=segment,job_root=job,lineage_root=tmp_path/'canonical')
            storage.allocate_long_launch(tmp_path/'canonical',request_ref=request_ref,lineage='numeric',job_root=job,
                segment_id=segment,maximum_attempts=sample_plan.max_total_checkpoints,maximum_bytes=16 << 20)
            exp = proxy.build_experiment(req,config,sample_plan,proxy.bind_inputs(req,config),UnitTracker(name),output_root=job/'training',
                lineage_root=tmp_path/'canonical',lineage='numeric',device='cpu',allow_unit_tracker=True)
            storage.attach_experiment(exp,ledger); exp.joint_remaining_bytes = lambda: ledger.remaining(job_root=job)-(224 << 20)
            return exp,ledger
        first,ledger = build(ref,request,'one','job1')
        outcome = first.run_segment(segment_id='one',until_samples=2,request_ref=ref,preflight=lambda *args:ledger.refresh())
        closure = write_once(tmp_path/'numeric_fixture_closure.json',dict(schema='model_v3_Root_storage_segment_closure_v1',authority=AUTH,job_root=str(tmp_path/'job1')))
        ledger.seal_segment(job_root=tmp_path/'job1',Root_closure_ref=closure)
        first.trainer.next_step(1)
        for role in proxy.ROLES: first.trainer.validate(role)
        expected = (deepcopy(first.trainer.model.state_dict()),deepcopy(first.trainer.optimizer.state_dict()),
            deepcopy(first.trainer.provider.state_dict()),deepcopy(first.trainer.scheduler.state_dict()),capture_rng_state())
        next_ref,next_request = renewal(tmp_path,request,segment='two',job=tmp_path/'job2',folder=tmp_path/'renew')
        resumed,other = build(next_ref,next_request,'two','job2')
        resumed.run_segment(segment_id='two',until_samples=3,request_ref=next_ref,parent=outcome['last_checkpoint'],preflight=lambda *args:other.refresh())
        for left,right in zip(expected,(resumed.trainer.model.state_dict(),resumed.trainer.optimizer.state_dict(),
            resumed.trainer.provider.state_dict(),resumed.trainer.scheduler.state_dict(),capture_rng_state())): assert_tree_equal(left,right)
        assert resumed.trainer.clock.samples_consumed == 3 and resumed.trainer.log_cursor == first.trainer.log_cursor
        first.trainer.provider.close(); resumed.trainer.provider.close()
    finally:
        torch.set_num_threads(old[0]); torch.set_float32_matmul_precision(old[1]); torch.backends.cuda.matmul.allow_tf32 = old[2]
        torch.backends.cudnn.allow_tf32 = old[3]; torch.use_deterministic_algorithms(old[4])


def test_real_runner_native_SDK_fresh_request_resume_with_long_accounting(tmp_path):
    if not os.environ.get('SLURM_JOB_ID'): pytest.fail('Root must execute actual owned Slurm allocation')
    ref,request,config = prepare(tmp_path)
    cli = proxy.REPOSITORY/'tools/model_v3/run_proxy_experiment.py'
    environment = {**os.environ,'CUDA_VISIBLE_DEVICES':'','WANDB_SILENT':'true',
        'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES':str((2 << 30)-(16 << 20)-(96 << 20))}
    checkpoint = None
    for number,endpoint in [(1,2),(2,3)]:
        job = tmp_path/('job'+str(number)); segment = 'one' if number == 1 else 'two'
        if number == 2: ref,request = renewal(tmp_path,request,segment=segment,job=job,folder=tmp_path/'renewed')
        command = [sys.executable,str(cli),'run','--request',ref['path'],'--request-sha256',ref['sha256'],'--input','synthetic',
            '--engineering-only','--output',str(job),'--lineage-root',str(tmp_path/'canonical'),'--lineage','long-engineering',
            '--segment-id',segment,'--until-samples',str(endpoint)]
        if checkpoint: command += ['--resume-complete',checkpoint['path']]
        result = subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
        assert result.returncode == 0,result.stdout+'\n'+result.stderr
        receipt = read_bound(binding(job/'CHILD_RECEIPT.json')); checkpoint = receipt['outcome']['last_checkpoint']
        assert receipt['status'] == 'CHILD_FINISHED_PENDING_ROOT_CLOSURE'
        assert len(list((job/'wandb').glob('offline-run-*/run-*.wandb'))) == 1
        ledger = storage.DurableLedger(request,config)
        closure = write_once(tmp_path/('fixture-closure'+str(number)+'.json'),
            dict(schema='model_v3_Root_storage_segment_closure_v1',authority=AUTH,job_root=str(job)))
        ledger.seal_segment(job_root=job,Root_closure_ref=closure)
    records = ledger.records()
    assert sum(row['kind'] == 'launch_attempts' for row in records) == 2
    assert sum(row['kind'] == 'complete_checkpoints' for row in records) == 2
    assert receipt['outcome']['samples_consumed'] == 3 and not receipt['scientific_acceptance']
