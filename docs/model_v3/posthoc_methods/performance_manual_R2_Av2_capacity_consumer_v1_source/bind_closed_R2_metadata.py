"""Post-C0 current manual R2 metadata binding. No Torch/model, hardware query or payload import."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, os, stat
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
CODE=B/'MFM_model_v3_A_acceptance_v2_candidate_v1';HERE=Path(__file__).absolute().parent
FAMILY=N/'performance_manual_R2_Av2_v1';OUT=FAMILY/'child';JOB='4524712'
LOCAL_CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50';PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
METHOD_PUBLIC='cf816e1441a245b80d90bc409a6fdc94cd3eea41'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243';NODE='compute-0-21';META=2<<20;LARGE=16<<20
ZERO={f'backbone.layers.{i}.attn.dist_mlp.2.bias' for i in range(6)}
FILES={'bind_closed_R2_metadata.py','audit_closed_R2_metadata.py','dependencies.json','README.md'}
def need(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def number(value):
    need(type(value) in (int,float) and math.isfinite(value) and value>=0,'Finite nonnegative observation required');return value
def reference(path):
    path=Path(path).absolute();before=path.lstat()
    limit=LARGE if path in (OUT/'fixed_batch_gate.json',OUT/'resources.jsonl') else META
    need(path.resolve()==path and stat.S_ISREG(before.st_mode) and before.st_uid==1278
         and before.st_nlink==1 and before.st_size<=limit,'Owned canonical bounded source/metadata required: '+str(path))
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    after=path.lstat()
    need(tuple(getattr(before,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns'))==
         tuple(getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns')),'Metadata/source changed')
    return dict(path=str(path),bytes=before.st_size,sha256=h.hexdigest())
def read(path):
    path=Path(path).absolute();need(path!=OUT/'resources.jsonl','Binder never decodes resources journal')
    ref=reference(path);value=json.loads(path.read_bytes(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path)==ref,'Metadata changed during parse');return value,ref
def bound(ref):
    value,current=read(ref['path']);need(current==ref,'Actual rawref differs');return value
def verify_package(pin_sha):
    pins,ref=read(HERE/'source_pins.json')
    need(ref['sha256']==pin_sha and pins['schema']=='model_v3_current_Av2_R2_capacity_consumer_sources_v1'
         and len(pins['files'])==4 and {Path(r['path']).name for r in pins['files']}==FILES,'Exact frozen four-leaf package required')
    for row in pins['files']:need(Path(row['path']).parent==HERE and reference(row['path'])==row,'Frozen leaf differs')
    deps,_=read(HERE/'dependencies.json')
    for row in deps['metadata_source_refs'].values():need(reference(row['path'])==row,'Fixed metadata/source differs')
    return pins,deps
def current_manual_guard(deps):
    ref=deps['metadata_source_refs']['manual_source_guard'];need(reference(ref['path'])==ref,'Manual guard differs')
    spec=importlib.util.spec_from_file_location('current_manual_R2_capacity_source_guard',ref['path'])
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.verify_package(deps['metadata_source_refs']['manual_package']['sha256']);return guard

def audit_fixed_gate(gate,rule):
    need(gate['gate']=='A_fixed_batch_equivalence' and gate['batches']==20
         and gate['acceptance_rules']==rule and len(gate['results'])==20,'Original full fixed20 required')
    need(rule['version']=='v2' and rule['fixed_batch_only'] is False
         and rule['semantic_contract_sha256']==canonical(rule['semantic_contract']),'Versioned v2 semantic contract differs')
    contract=rule['semantic_contract']
    need(contract['elementwise']==dict(atol=1e-8,rtol=1e-4,formula='abs(a-b)<=atol+rtol*abs(b)',all_elements=True)
         and contract['analytic_zero']['both_L2_norm_max']==1e-8,'User-approved v2 thresholds differ')
    proofs=rule['analytic_zero_parameter_proofs']
    for rows in proofs.values():
        need(len(rows)==6 and {r['name'] for r in rows}==ZERO
             and all(r['shape']==[8] and r['heads']==8 and r['dimension']==512
             and r['parameter_identity_checked'] is True for r in rows),'Actual complete six per-head analytic-zero proofs required')
    need(set(proofs)=={'reference','candidate'},'Both actual model proof sets required')
    names=forward_names=None;passed=True;max_forward=max_ratio=max_abs=max_zero=0.;disabled=0
    for index,batch in enumerate(gate['results']):
        need(batch['batch']==index,'Exact original fixed batch order differs')
        f,g=batch['forward'],batch['gradient'];fs=f['tensors'];gs=g['tensors']
        current={r['name'] for r in gs};fn={r['name'] for r in fs}
        need(len(gs)==len(current)==329 and len(fs)==len(fn)==8
             and (names is None or names==current) and (forward_names is None or forward_names==fn),
             'All329 named parameters and all8 outputs must be retained in every batch')
        names,forward_names=current,fn;fp=gp=True
        need(f['tolerance']==1e-5 and g['atol']==1e-8 and g['rtol']==1e-4
             and g['zero_norm_tolerance']==1e-8 and g['acceptance_version']=='v2'
             and g['semantic_contract_sha256']==rule['semantic_contract_sha256']
             and len(g['analytic_zero_names'])==6 and set(g['analytic_zero_names'])==ZERO,'Actual gate version/tolerances differ')
        for row in fs:
            value=number(row['relative_l2']);max_forward=max(max_forward,value)
            ok=value<=1e-5;need(row['pass'] is ok,'Output pass differs from original relative gate');fp=fp and ok
        for row in gs:
            zero=row['name'] in ZERO;need(row['analytic_zero'] is zero,'Analytic-zero declaration is not actual parameter identity')
            if row.get('reason')=='both_disabled':
                need(not zero and row['reference_shape'] is None and row['candidate_shape'] is None
                     and row['reference_norm'] is None and row['candidate_norm'] is None
                     and row['pass'] is True,'Only both-None inactive parameters are legal')
                disabled+=1;continue
            need(row['reference_shape']==row['candidate_shape']==row['shape']
                 and row['finite'] is True and type(row['elements']) is int and row['elements']>=0
                 and math.prod(row['shape'])==row['elements'],'Actual finite same-shape gradients required')
            nr,nc,nd=(number(row[k]) for k in ('reference_norm','candidate_norm','difference_norm'))
            count=row['violating_elements'];need(type(count) is int and 0<=count<=row['elements'],'Element violation count required')
            absolute=number(row['max_absolute']);lo=number(row['minimum_combined_threshold']);hi=number(row['maximum_combined_threshold'])
            ratio=number(row['maximum_error_to_threshold'])
            need(lo<=hi and (lo>=1e-8 or row['elements']==0) and row['zero_threshold_failure'] is False,'Finite exact combined threshold audit required')
            element_pass=count==0 and ratio<=1
            zero_pass=not zero or (nr<=1e-8 and nc<=1e-8);ok=element_pass and zero_pass
            need(row['elementwise_pass'] is element_pass and row['pass'] is ok
                 and row['analytic_zero_norm_pass']==(zero_pass if zero else None),'Per-element/zero-norm reported decision differs')
            max_ratio=max(max_ratio,ratio);max_abs=max(max_abs,absolute)
            if zero:max_zero=max(max_zero,nr,nc)
            gp=gp and ok
        need(f['pass'] is fp and g['pass'] is gp and batch['pass'] is (fp and gp),'Batch aggregate differs')
        passed=passed and fp and gp
    need(gate['pass'] is passed,'Fixed gate aggregate differs')
    return dict(passed=passed,batches=20,parameters_each=329,outputs_each=8,both_disabled_records=disabled,
                maximum_forward_relative_l2=max_forward,maximum_error_to_threshold=max_ratio,
                maximum_gradient_absolute=max_abs,maximum_analytic_zero_norm=max_zero)


def qualify_artifacts(parent_ref,deps):
    guard=current_manual_guard(deps);qualified=guard.validate_sources()
    submission,sref=read(FAMILY/'control/Root_submission_actual_v1.json')
    need(sref==deps['actual_GPU_submission'] and submission['status']=='SUBMITTED'
         and submission['schema']=='model_v3_manual_R2_Av2_Root_single_submission_v1' and submission['job_id']==JOB
         and submission['source_package']==deps['metadata_source_refs']['manual_package'],'Exact actual manual submission required')
    need(guard.verify_method(submission['operations_publication'])['public_code_sha']==METHOD_PUBLIC,'Exact actual manual method publication required')
    guard.parent(bound(parent_ref),JOB,node=NODE)
    six={name:reference(path) for name,path in dict(configuration=OUT/'configuration.json',summary=OUT/'summary.json',
        run_status=OUT/'run_status.json',supervisor=FAMILY/'supervisor.json',parent_sacct=Path(parent_ref['path']),steps=OUT/'resources.jsonl').items()}
    cfg,summary,status,sup=(bound(six[name]) for name in ('configuration','summary','run_status','supervisor'))
    need(str(cfg['job_id'])==JOB and cfg['code_sha']==LOCAL_CODE and cfg['prereg_sha']==PUBLIC
         and cfg['gpu_uuid']==GPU and cfg['node'].split('.')[0]==NODE and cfg['seed']==0 and cfg['input']=='native_s'
         and cfg['smoke'] is False and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500,'Actual current manual R2 full20+500 identity required')
    anchor=qualified['anchor']
    need(all(cfg[k]==anchor[k] for k in ('model','candidate','reference','optimizer','loss_policy','loss_weights','supervision'))
         and cfg['data_version']['sampler']['max_padded_cost']==8000000 and cfg['data_version']['sampler']['padded_cost_multiplier']==3
         and cfg['data_version']['loader']['num_workers']==8
         and cfg['original_shard_snapshot_prejob_sha256']==qualified['refs']['S_original_snapshot']['sha256']
         and cfg['candidate_options_sha256']==qualified['refs']['candidate_options']['sha256']
         and cfg['performance_execution_request']==qualified['refs']['manual_execution'],'Original model/input/loss/options/manual execution differ')
    execution=cfg['performance_execution'];requested=execution['requested']
    need(requested['checkpoint_policy']=='manual' and requested['capacity_profile'] is None and requested['padding'] is None
         and requested['resident_models']==2 and requested['batch_padded_cost']==8000000 and execution['selection'] is None
         and execution['resolved_options']==cfg['candidate'],'Only actual manual/no-packing/R2 measurement qualifies')
    need(canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})==cfg['configuration_sha256'],'Canonical actual config differs')
    rule=cfg['acceptance_rules']
    need(cfg['acceptance_scope']=='V2_FULL20_AND500' and rule['rule_publication']==qualified['refs']['rule_publication']
         and rule['rule_document']==qualified['refs']['rule_document'],'Actual published v2 rules required')
    gate,gref=read(OUT/'fixed_batch_gate.json');fixed=audit_fixed_gate(gate,rule);need(fixed['passed'],'Actual full fixed20v2 not passed')
    trajectory,tref=read(OUT/'trajectory_gate.json')
    need(trajectory['gate']=='A_500_update_loss_trajectory' and trajectory['updates']==500 and len(trajectory['results'])==500,'Actual full500 required')
    maximum_loss=0.
    for index,row in enumerate(trajectory['results'],1):
        value=number(row['relative_difference']);maximum_loss=max(maximum_loss,value)
        need(row['step']==index and row['pass'] is True and value<=1e-3,'Original ordered500 loss gate differs')
    need(trajectory['pass'] is True and summary['status']=='PAIRED_GATES_PASS'
         and all(summary[k] is True for k in ('full_A_numeric_acceptance','fixed_batch_pass','trajectory_pass'))
         and summary['code_sha']==LOCAL_CODE and summary['prereg_sha']==PUBLIC and summary['gpu_uuid']==GPU
         and summary['configuration_sha256']==cfg['configuration_sha256'] and summary['acceptance_rules']==rule
         and summary['acceptance_scope']=='V2_FULL20_AND500' and summary['consumed_trajectory_base_records']==201216,'Actual complete summary differs')
    need(status['status']==summary['status'] and status['failure'] is None and status['cleanup_errors']==[]
         and status['stream_cleanup']['input_descriptors_closed'] is True and status['stream_cleanup']['errors']==[]
         and status['acceptance_rules']==rule and status['acceptance_scope']=='V2_FULL20_AND500'
         and status['trajectory_started'] is True and status['committed_trajectory_updates']==500 and status['trajectory_completed'] is True,
         'Actual complete run/stream closure required')
    need(str(sup['job_id'])==JOB and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
         and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
         and sup['launch_identity']['uid']==1278,'Original GPU supervision/private/process closure required')
    storage,storage_ref=read(FAMILY/'supervisor.json.storage.json')
    need(storage['schema']=='model_v3_private_storage_v1' and str(storage['job_id'])==JOB and storage['uid']==1278
         and sup['private_storage_bindings_path']==storage_ref['path'] and cfg['private_storage_bindings']['receipt_path']==storage_ref['path']
         and cfg['private_storage_bindings']['receipt_sha256']==storage_ref['sha256'],'Actual private receipt differs')
    return dict(six=six,config=cfg,fixed=fixed,fixed_gate=gref,trajectory=tref,maximum_loss=maximum_loss,
        private_receipt=storage_ref,submission=sref,operations_publication=submission['operations_publication'])
def output_directory(path,fresh=False):
    path=Path(path).absolute()
    need(path.resolve()==path and path.is_relative_to(N) and not path.is_relative_to(FAMILY) and not path.is_relative_to(HERE),'Independent canonical N metadata root required')
    if fresh:need(not path.exists() and not path.is_symlink(),'Fresh metadata output required');path.mkdir(parents=True,exist_ok=False)
    else:need(path.is_dir() and not path.is_symlink(),'Actual bound directory absent')
    return path
def write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=META,'Bound output cap')
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return reference(path)
def validate_bound(root,pin_sha):
    _,deps=verify_package(pin_sha);root=output_directory(root);binding,bref=read(root/'BINDING.json')
    need(binding['status']=='ACTUAL_SOURCE_R2_METADATA_BOUND_PENDING_CPU_CONSUMER'
         and binding['source_package']==reference(HERE/'source_pins.json'),'Actual completed metadata binding required')
    data=qualify_artifacts(binding['parent_sacct'],deps)
    profile=bound(binding['profile']);execution=bound(binding['auto_execution_DRAFT']);options=bound(binding['auto_options_DRAFT'])
    need(profile==dict(schema='model_v3_closed_checkpoint_capacity_profiles_v1',observations=[data['six']]),'Original exact six-ref profile schema required')
    need(execution==dict(schema='model_v3_performance_execution_v1',checkpoint_policy='auto_closed_profile_v1',padding=None,
         capacity_profile=binding['profile'],batch_padded_cost=8000000,resident_models=2,
         workload_sha256=data['config']['performance_execution']['requested']['workload_sha256']),'Existing auto request differs')
    expected=dict(data['config']['candidate']);expected['backbone_checkpointing']=None;need(options==expected,'Only original auto None may differ')
    for key,name in (('profile','closed_R2_capacity_profile_v1.json'),('auto_execution_DRAFT','auto_R2_execution_DRAFT_v1.json'),('auto_options_DRAFT','auto_R2_options_DRAFT_v1.json')):
        need(Path(binding[key]['path'])==root/name,'One actual bound metadata directory required')
    return binding,bref
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--parent-sacct-json',type=Path,required=True);parser.add_argument('--parent-sacct-sha256',required=True)
    parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args();need(os.getuid()==1278,'Root account required')
    _,deps=verify_package(args.source_pins_sha256);out=output_directory(args.output_root,fresh=True)
    result=dict(status='REJECTED_NO_CAPACITY_PROFILE',failure=None,profile=None,auto_execution_DRAFT=None,auto_options_DRAFT=None,
        models_CUDA_SDK_weights_or_data_payload_opened=False)
    try:
        pref=reference(args.parent_sacct_json);need(pref['sha256']==args.parent_sacct_sha256,'Actual saved Root sacct rawSHA differs')
        data=qualify_artifacts(pref,deps)
        profile=write(out/'closed_R2_capacity_profile_v1.json',dict(schema='model_v3_closed_checkpoint_capacity_profiles_v1',observations=[data['six']]))
        options=dict(data['config']['candidate']);options['backbone_checkpointing']=None
        opref=write(out/'auto_R2_options_DRAFT_v1.json',options)
        exref=write(out/'auto_R2_execution_DRAFT_v1.json',dict(schema='model_v3_performance_execution_v1',checkpoint_policy='auto_closed_profile_v1',
            padding=None,capacity_profile=profile,batch_padded_cost=8000000,resident_models=2,
            workload_sha256=data['config']['performance_execution']['requested']['workload_sha256']))
        binding=dict(status='ACTUAL_SOURCE_R2_METADATA_BOUND_PENDING_CPU_CONSUMER',source_package=reference(HERE/'source_pins.json'),
            parent_sacct=pref,profile=profile,auto_execution_DRAFT=exref,auto_options_DRAFT=opref,
            fixed20=data['fixed'],fixed_gate=data['fixed_gate'],trajectory_gate=data['trajectory'],maximum_loss=data['maximum_loss'],
            private_receipt=data['private_receipt'],submission=data['submission'],operations_publication=data['operations_publication'],
            automatic_policy_selected=False,auto_GPU_R1_ABBA_accepted=False)
        write(out/'BINDING.json',binding);result.update(status=binding['status'],profile=profile,auto_execution_DRAFT=exref,auto_options_DRAFT=opref)
    except BaseException as exc:result['failure']=dict(type=type(exc).__name__,message=str(exc))
    rref=write(out/'BIND_RESULT.json',result);print(json.dumps(dict(status=result['status'],failure=result['failure'],result=rref),sort_keys=True),flush=True)
    return int(result['failure'] is not None)
if __name__=='__main__':raise SystemExit(main())

