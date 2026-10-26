"""One actual WSD run with long-run accounting enabled, all data engineering.

This is an additional source/test request, separate from the frozen21 cases.
Root provides actual compute execution; no scientific quota/profile is claimed.
"""
from copy import deepcopy
import json
import time

import torch

from test_model_v3_trainer import UnitTracker
from test_model_v3_long_run_storage import prepare,AUTH,BASE,update_fixture_feed
from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1 import v3_long_run_storage as storage
from phychem_mfm.phase1 import v3_wsd_fork as wsd
from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound,write_once,encoded


def test_long_mode_WSD_parent_and_child_share_finite_principal_counts_and_roots(tmp_path):
    previous = torch.get_num_threads(),torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32,torch.are_deterministic_algorithms_enabled()
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False; torch.use_deterministic_algorithms(True)
    try:
        _,parent,config = prepare(tmp_path)
        config['long_run_policy']['counts']['wsd_children'] = 1
        old = config['proxy_contract']; old['sample_budget'] = 8; old['milestones'] = [2,4,8]
        old['schedule'] = {'mode':'wsd','warmup_samples':0,'decay_start_samples':6,'minimum_ratio':0.}
        old['sample_plan'].update(sample_budget=8,panel_samples=[2,4,8],validation_samples=[2,4,8])
        parent['configuration'] = write_once(tmp_path/'long_stable_parent.json',config)
        child_config = deepcopy(config); child = child_config['proxy_contract']
        child['sample_budget'] = 4; child['schedule'] = {'mode':'wsd','warmup_samples':0,'decay_start_samples':2,'minimum_ratio':0.}
        child['sample_plan'].update(sample_budget=4,panel_samples=[2,4],validation_samples=[2,4])
        additions = {key:sha for key,sha in wsd.fork_sources().items() if key not in parent['sources']['runtime_files']}
        child_config['wsd_fork'] = {'schema':'model_v3_wsd_fork_policy_v1',
            'parent_configuration_identity_sha256':proxy.identity(config),'fork_samples':2,'decay_samples':2,
            'minimum_ratio':0.,'source_additions':additions,'family_ledger_bytes':2 << 20,'maximum_forks':1}
        child_config_ref = write_once(tmp_path/'long_child.json',child_config)
        # Root's finite family scope must be declared before either lineage.
        principal = read_bound(parent['long_run']['reservation_principal'])
        record = read_bound(principal['Root_reservation_record'])
        record['initial_counts'] = principal['initial_counts']
        principal.update(policy_sha256=proxy.canonical_hash(config['long_run_policy']),
            counts=config['long_run_policy']['counts'],science_identities=[proxy.identity(config),proxy.identity(child_config)],
            Root_reservation_record=write_once(tmp_path/'family_Root_record.json',record))
        principal.pop('science_identity_sha256')
        principal_ref = write_once(tmp_path/'family_principal.json',principal)
        profile = read_bound(parent['long_run']['profile'])
        profile['profile_identity_sha256'] = storage.profile_identity(config,parent)
        profile_ref = write_once(tmp_path/'family_profile.json',profile)
        parent['long_run'].update(reservation_principal=principal_ref,profile=profile_ref)
        descriptor = read_bound(parent['long_run']['quota_feed_descriptor'])
        from pathlib import Path
        feed_path = Path(descriptor['feed_path']); feed = json.loads(feed_path.read_text())
        feed['reservations']['fixture-slot']['principal_sha256'] = principal_ref['sha256']
        feed_path.write_bytes(encoded(feed)); update_fixture_feed(parent)
        old_admission = read_bound(parent['long_run']['Root_segment_admission'])
        parent['long_run']['Root_segment_admission'] = write_once(tmp_path/'parent_admission.json',{
            **old_admission,'stable_request_identity_sha256':storage.stable_request_identity(parent),'reservation_principal':principal_ref,
            'segment_id':'parent','job_root':str(tmp_path/'parent_job'),'lineage_root':str(tmp_path/'parent_ledger')})
        parent_ref = write_once(tmp_path/'parent_request.json',parent)
        _,parent_plan,_ = proxy.validate_request(parent,input_kind='synthetic',engineering_only=True)
        account = storage.DurableLedger(parent,config); parent_job = tmp_path/'parent_job'; parent_job.mkdir()
        account.allocate_segment(request_ref=parent_ref,segment_id='parent',job_root=parent_job,lineage_root=tmp_path/'parent_ledger')
        storage.allocate_long_launch(tmp_path/'parent_ledger',request_ref=parent_ref,lineage='parent',job_root=parent_job,
            segment_id='parent',maximum_attempts=parent_plan.max_total_checkpoints,maximum_bytes=16 << 20)
        exp = proxy.build_experiment(parent,config,parent_plan,proxy.bind_inputs(parent,config),UnitTracker('long-parent'),
            output_root=parent_job/'training',lineage_root=tmp_path/'parent_ledger',lineage='parent',device='cpu',allow_unit_tracker=True)
        storage.attach_experiment(exp,account); exp.joint_remaining_bytes = lambda: account.remaining(job_root=parent_job)-(224 << 20)
        result = exp.run_segment(segment_id='parent',until_samples=2,request_ref=parent_ref,preflight=lambda *args:account.refresh())
        closure = write_once(tmp_path/'parent_fixture_closed.json',dict(schema='model_v3_Root_storage_segment_closure_v1',authority=AUTH,job_root=str(parent_job)))
        account.seal_segment(job_root=parent_job,Root_closure_ref=closure)
        child_request = deepcopy(parent); child_request['configuration'] = child_config_ref
        child_request['fork'] = {'parent_request':parent_ref,'parent_complete':result['last_checkpoint'],
            'parent_ledger':str(tmp_path/'parent_ledger'),'parent_segment_registration':binding(tmp_path/'parent_ledger/segments/parent.json'),
            'family_root':str(tmp_path/'family')}
        child_request['long_run']['Root_segment_admission'] = write_once(tmp_path/'child_admission.json',{
            **old_admission,'stable_request_identity_sha256':storage.stable_request_identity(child_request),
            'reservation_principal':principal_ref,'segment_id':'child','job_root':str(tmp_path/'child_job'),
            'lineage_root':str(tmp_path/'child_ledger')})
        child_ref = write_once(tmp_path/'child_request.json',child_request)
        update_fixture_feed(child_request)
        cfg,plan,_,old_request,old_config,state,_ = wsd.validate_fork(child_request,input_kind='synthetic',engineering_only=True)
        shared = storage.DurableLedger(child_request,cfg); job = tmp_path/'child_job'; job.mkdir()
        family = wsd.ForkFamily(tmp_path/'family',fork=child_request['fork'],policy=cfg['wsd_fork'],
            child_identity=proxy.identity(cfg),maximum_checkpoints=plan.max_total_checkpoints)
        shared.register_root(tmp_path/'family',kind='management')
        shared.append('wsd_children',str(tmp_path/'child_ledger'),{'fixture':True})
        shared.allocate_segment(request_ref=child_ref,segment_id='child',job_root=job,lineage_root=tmp_path/'child_ledger')
        family.register_child(lineage='child',ledger=tmp_path/'child_ledger',request_ref=child_ref)
        family.reserve_launch(tmp_path/'child_ledger',request_ref=child_ref,lineage='child',job_root=job,segment_id='child',
            maximum_attempts=plan.max_total_checkpoints,maximum_bytes=16 << 20)
        forked = wsd.restore_and_fork(child_request,cfg,plan,proxy.bind_inputs(old_request,old_config),UnitTracker('long-child'),
            output_root=job,lineage_root=tmp_path/'child_ledger',lineage='child',family=family,parent=old_request,
            parent_config=old_config,parent_state=state,allow_unit_tracker=True)
        storage.attach_experiment(forked,shared); forked.joint_remaining_bytes = lambda: shared.remaining(job_root=job)-(224 << 20)
        final = forked.run_segment(segment_id='child',until_samples=4,request_ref=child_ref,preflight=lambda *args:shared.refresh())
        assert final['samples_consumed'] == 4 and final['optimizer_updates'] == 2
        assert wsd.verify_fork_chain(forked,final['last_checkpoint'])['parent_complete'] == result['last_checkpoint']
        rows = shared.records()
        assert sum(row['kind'] == 'launch_attempts' for row in rows) == 2
        assert sum(row['kind'] == 'complete_checkpoints' for row in rows) == 3  # parent + child start/final
        assert sum(row['kind'] == 'wsd_children' for row in rows) == 1
        assert parent_job in {Path(row['path']) for row in shared.root_records()}
        assert shared.configuration['long_run_policy']['durable_bytes'] == 8 << 30
        exp.trainer.provider.close(); forked.trainer.provider.close()
    finally:
        torch.set_num_threads(previous[0]); torch.set_float32_matmul_precision(previous[1])
        torch.backends.cuda.matmul.allow_tf32 = previous[2]; torch.backends.cudnn.allow_tf32 = previous[3]
        torch.use_deterministic_algorithms(previous[4])
