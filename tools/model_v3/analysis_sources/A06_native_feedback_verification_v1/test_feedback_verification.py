"""Synthetic metadata/protobuf tests only: no model, geometry, targets or actual SDK scan."""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import feedback_schema as schema
import verify_feedback_sdk as sdk
import report_feedback as report
import prepare_feedback_inputs as preparer


def fixture():
    config={'schema':'A06_native_gradient_feedback_diagnostic_v1','scope':'15_native_updates_diagnostic_only',
        'updates':15,'code_sha':schema.CODE_SHA,'prereg_sha':schema.PREREG_SHA,'seed':0,
        'scientific_acceptance':False,'A06_original_gate_status':'FAILED_UNCHANGED','fixed20_batch_gate_rerun':False,
        'resume_supported':False,'model':{'backbone':{'dim':512,'layers':6}},
        'original_options':{'reference':{'fused_adamw':False},'candidate':{'fused_adamw':True}},
        'environment':{'tracking_mode':'offline','downstream_data_read':False,'original_lmdb_written':False,
            'gpu_name':'NVIDIA GeForce RTX 5090'},'opaque_member_identity':'FORBIDDEN_MEMBER_ID',
        'extra_parameters':['FORBIDDEN_PARAMETER_ARRAY']}
    status={'status':schema.STATUS,'failure':None,'cleanup_errors':[],'job_id':schema.JOB,
        'sdk_run_id':schema.RUN_ID,'code_sha':schema.CODE_SHA,'offline_unsynced':True,
        'input_cleanup':{'errors':[],'input_descriptors_closed':True},'completed_native_updates':15,
        'acknowledged_history_commits':17,'expected_success_HISTORY_rows':17,
        'SDK_native_verification':'PENDING_INDEPENDENT_READBACK_not_inferred_from_mirror',
        'scientific_acceptance':False,'foreign_gpu_risk_observed':False}
    data={'input_kind':'native_s','seed':0,'sampler_contract_sha256':'a'*64}
    summary={'status':schema.STATUS,'native_updates':15,'consumed_base_records':5120,
        'all_replay_points_exact457':True,'shadow_has_model_forward':False,'scientific_acceptance':False,
        'foreign_gpu_risk_observed':False,'A06_original_gate_status':'FAILED_UNCHANGED',
        'attribution':'EVIDENCE_ONLY_NO_AUTOMATIC_CAUSAL_CONCLUSION','fixed20_rerun':False,
        'full500_rerun':False,'resume_supported':False,'first_original_threshold_failure':14,'points':[]}
    histories={key:[] for key in ('reference','candidate')}; originals={key:[] for key in histories}
    details,consumption=[],[]; consumed=0
    expected=[{'step':0,'row':{'event':'START','diagnostic_only':True,'requested_native_updates':15,'scientific_acceptance':False}}]
    for update in range(1,16):
        base=512 if update<=5 else 256; consumed+=base
        receipt=hashlib.sha256(str(update).encode()).hexdigest()
        for role in histories:
            loss=2.0 if role=='reference' else (2.0 if update<14 else 2.006+(update-14)*.002)
            row={'optimizer_updates':update,'loss':loss,'gradient_norm':3.0,'base_records':base,
                'native_atoms':base*10,'consumed_base_records':consumed,'input_receipt_sha256':receipt,
                'valid_label_counts':{'graphs':base*3,'atoms':base*30}}
            histories[role].append(row); originals[role].append({**row,'compute_seconds':.01})
        left,right=(histories[key][-1] for key in ('reference','candidate'))
        gap=abs(right['loss']-left['loss'])/max(abs(left['loss']),1e-12)
        comp={role:{component:{'max_relative_l2':.001*update,
            'global_difference_l2_diagnostic_only':.0001*update,
            'parameters':['FORBIDDEN_PARAMETER_ARRAY']} for component in schema.COMPONENTS} for role in schema.ROLES}
        shared={'unchanged':True,'alias_same_tensor_and_none':True,
            'before':{'sha256':'b'*64,'none_count':1},'after':{'sha256':'b'*64,'none_count':1},
            'reference_after':{'sha256':'b'*64,'none_count':1}}
        point={'update':update,'loss_relative_difference':gap,'original_point_pass':gap<=.001,
            'raw_gradient_max_relative_l2':.5,
            **{role:{component:comp[role][component]['global_difference_l2_diagnostic_only']
                for component in schema.COMPONENTS} for role in schema.ROLES}}
        summary['points'].append(point)
        details.append({'update':update,'scientific_acceptance':False,
            'replay':{role:{'comparison':'exact_saved457_scalar_and_input_receipt','differences':{},'pass':True}
                for role in histories},'original_trajectory_threshold_point_check':{
                    'pass':gap<=.001,'relative_difference':gap,'step':update,'threshold':.001},
            'execution_order':['reference','candidate','shadow'] if update%2 else ['candidate','reference','shadow'],
            'dispatch':{'reference/_multi_tensor_adam':1,'candidate/_fused_adam':1,'shadow/_fused_adam':1},
            'shared_clipped_reference_gradient':shared,'step_state_representation':{
                role:{'value':float(update),'dtype':'torch.float32','device':'cpu' if role=='reference' else 'cuda:0',
                    'representative_parameter':'FORBIDDEN_PARAMETER_NAME'} for role in ('reference','candidate','shadow')},
            'raw_native_gradient_comparison':{'max_relative_l2':.5},'comparisons':comp,
            'fixed_six_distance_bias_scalars':['FORBIDDEN_PARAMETER_ARRAY']})
        consumption.append({'update':update,'base_records':base,'input_receipt_sha256':receipt,
            'committed_stream':{'committed_base_samples':consumed,'sampler':{'samples_consumed':consumed,
                'batches_consumed':update,'contract_sha256':'a'*64,'schema_version':'phase1_block_atom_sampler_v1'}}})
        row={'event':'NATIVE_GRADIENT_FEEDBACK_UPDATE','native_updates':update,'reference/loss':left['loss'],
            'free_fused/loss':right['loss'],'reference/preclip_gradient_norm':3.0,'free_fused/preclip_gradient_norm':3.0,
            'trajectory/relative_difference':gap,'trajectory/original_point_pass':gap<=.001,'replay/exact457':True,
            'shadow/borrowed_gradients_unchanged':True,'gradient/free_vs_reference_max_parameter_relative_l2':.5,
            'consumed_base_records':consumed,'scientific_acceptance':False}
        for role in schema.ROLES:
            for component in schema.COMPONENTS:
                row[role+'/'+component+'/max_parameter_relative_l2']=comp[role][component]['max_relative_l2']
                row[role+'/'+component+'/global_difference_l2_diagnostic_only']=comp[role][component]['global_difference_l2_diagnostic_only']
        expected.append({'step':update,'row':row})
    for role in originals:
        for update in range(16,501): originals[role].append({**originals[role][-1],'optimizer_updates':update})
    expected.append({'step':16,'row':{'event':'COMPLETE','native_updates':15,'first_original_threshold_failure':14,
        'all_replay_points_exact457':True,'scientific_acceptance':False}})
    return {'config':config,'summary':summary,'status':status,'data':data,'mirrors':expected,
        'histories':histories,'originals':originals,'consumption':consumption,'details':details}


def validate(values):
    return schema.validate_outputs(*(values[key] for key in ('config','summary','status','data','mirrors',
        'histories','originals','consumption','details')))


def context(values=None):
    values=fixture() if values is None else values
    return {'run_id':schema.RUN_ID,'run_name':schema.RUN_NAME,'expected_config':values['config'],
        'expected_rows':validate(values),'summary':values['summary'],'accounting':{
            'job_id':schema.JOB,'state':'COMPLETED','exit_code':'0:0','elapsed_seconds':106,'allocated_cpus':16},
        'configuration_ref':{'path':'/unit/configuration.json','bytes':1,'sha256':'c'*64},
        'data_version':'native_s_'+'a'*64,'sources':{'summary':{'path':'/unit/original/summary.json'}},
        'SDK_file':{'path':'/unit/original/wandb/run-'+schema.RUN_ID+'.wandb','bytes':10,'sha256':'d'*64}}


def test_all_seventeen_rows_reconstructed_from_all_saved_metadata():
    values=fixture(); rows=validate(values)
    assert rows==values['mirrors'] and [row['step'] for row in rows]==list(range(17))
    assert rows[-2]['row']['consumed_base_records']==5120
    assert values['summary']['first_original_threshold_failure']==14


@pytest.mark.parametrize('corruption',('mirror_extra','mirror_missing','mirror_step','numeric_type','old457',
    'data_consumption','cursor','summary','shared_gradient','dispatch','threshold','cleanup','scientific','downstream'))
def test_rejects_independent_metadata_contradictions(corruption):
    values=fixture()
    if corruption=='mirror_extra': values['mirrors'][1]['row']['new_metric']=1
    elif corruption=='mirror_missing': del values['mirrors'][1]['row']['reference/loss']
    elif corruption=='mirror_step': values['mirrors'][1]['step']=2
    elif corruption=='numeric_type': values['mirrors'][1]['row']['native_updates']=1.0
    elif corruption=='old457': values['originals']['candidate'][1]['loss']+=.01
    elif corruption=='data_consumption': values['consumption'][3]['base_records']+=1
    elif corruption=='cursor': values['consumption'][3]['committed_stream']['sampler']['batches_consumed']=3
    elif corruption=='summary': values['summary']['points'][2]['free_vs_shadow']['exp_avg']+=.1
    elif corruption=='shared_gradient': values['details'][2]['shared_clipped_reference_gradient']['after']['sha256']='c'*64
    elif corruption=='dispatch': values['details'][2]['dispatch']['shadow/_fused_adam']=0
    elif corruption=='threshold': values['details'][13]['original_trajectory_threshold_point_check']['threshold']=.01
    elif corruption=='cleanup': values['status']['input_cleanup']['errors'].append('bad')
    elif corruption=='scientific': values['summary']['scientific_acceptance']=True
    else: values['config']['environment']['downstream_data_read']=True
    with pytest.raises(ValueError): validate(values)


def packets(ctx, ancillary=0):
    from wandb.proto import wandb_internal_pb2 as pb
    first=pb.Record(); first.run.run_id=ctx['run_id']; first.run.display_name=ctx['run_name']
    for key,value in ctx['expected_config'].items():
        item=first.run.config.update.add(); item.key=key; item.value_json=json.dumps(value)
    yield first
    for _ in range(ancillary):
        item=pb.Record(); item.metric.name='ancillary_definition'; yield item
    summary={}
    for expected in ctx['expected_rows']:
        rec=pb.Record()
        for key,value in {'_step':expected['step'],**expected['row']}.items():
            item=rec.history.item.add(); item.key=key; item.value_json=json.dumps(value)
        summary.update(expected['row']); yield rec
    rec=pb.Record()
    for key,value in {**summary,'_step':16}.items():
        item=rec.summary.update.add(); item.key=key; item.value_json=json.dumps(value)
    yield rec
    rec=pb.Record(); rec.exit.exit_code=0; yield rec


class Stream:
    def __init__(self, records): self.records=iter(records)
    def scan_data(self):
        item=next(self.records,None); return None if item is None else item.SerializeToString()


def compare(records=None,ctx=None,**limits):
    from wandb.proto import wandb_internal_pb2 as pb
    ctx=context() if ctx is None else ctx
    return sdk.compare(Stream(packets(ctx) if records is None else records),pb.Record,ctx,**limits)


def test_native_ancillary_records_do_not_consume_history_quota():
    ctx=context(); verdict=compare(packets(ctx,50),ctx,max_native_records=70,max_history_rows=17)
    assert verdict['native_packets']==70 and verdict['history_rows']==17 and verdict['native_closed']
    assert verdict['native_packets']!=verdict['history_rows']


@pytest.mark.parametrize('corruption',('metric','missing_metric','config','late_config','summary','name','run',
    'exit','no_exit','duplicate_step','partial','decode'))
def test_native_rejects_field_config_summary_identity_and_closure_drift(corruption):
    from wandb.proto import wandb_internal_pb2 as pb
    ctx=context(); records=list(packets(ctx))
    if corruption=='metric': records[2].history.item[2].value_json='999'
    elif corruption=='missing_metric': del records[2].history.item[-1]
    elif corruption=='config': records[0].run.config.update[0].value_json='"changed"'
    elif corruption=='late_config':
        extra=pb.Record(); item=extra.config.update.add(); item.key='updates'; item.value_json='16'; records.insert(3,extra)
    elif corruption=='summary': records[-2].summary.update[0].value_json='"changed"'
    elif corruption=='name': records[0].run.display_name='other_name'
    elif corruption=='run': records[0].run.run_id='other_id'
    elif corruption=='exit': records[-1].exit.exit_code=1
    elif corruption=='no_exit': records.pop()
    elif corruption=='duplicate_step': records[2].history.item[0].value_json='0'
    elif corruption=='partial':
        extra=pb.Record(); extra.request.partial_history.item.add().key='uncommitted'; records.insert(2,extra)
    else:
        class Broken(Stream):
            def scan_data(self): raise EOFError('fixture truncated native tail')
        with pytest.raises(ValueError): sdk.compare(Broken(records),pb.Record,ctx)
        return
    with pytest.raises(ValueError): compare(records,ctx)


@pytest.mark.parametrize('limit',('native','history','record','export','wall'))
def test_native_limits_fail_closed_instead_of_truncating(limit):
    kwargs={'native':{'max_native_records':19},'history':{'max_history_rows':16},
        'record':{'max_record_bytes':1},'export':{'max_export_bytes':1},'wall':{'deadline':time.monotonic()-1}}[limit]
    with pytest.raises(ValueError): compare(**kwargs)


def test_raw_binding_rejects_hash_size_and_duplicate_json(tmp_path):
    file=tmp_path/'evidence.json'; file.write_bytes(b'{"ok":true}\n'); ref=schema.file_ref(file)
    assert schema.read(ref)=={'ok':True}
    with pytest.raises(ValueError): schema.bind({**ref,'bytes':ref['bytes']+1})
    with pytest.raises(ValueError): schema.bind({**ref,'sha256':'0'*64})
    file.write_bytes(b'{"ok":true,"ok":false}\n')
    with pytest.raises(ValueError): schema.read(schema.file_ref(file))
    with pytest.raises(ValueError): schema.strict_json('{"bad":1e309}')


def test_actual_sacct_parent_required_and_steps_not_substituted():
    header='JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS\n'
    raw=header+schema.JOB+'|COMPLETED|0:0|106|16\n'+schema.JOB+'.batch|COMPLETED|0:0|105|16\n'
    assert schema.slurm_row(raw,schema.JOB)['ElapsedRaw']=='106'
    for invalid in (raw.replace('|0:0|106','|1:0|106'),raw.replace('|COMPLETED|0:0|106','|FAILED|0:0|106'),
            raw.replace(schema.JOB+'|',schema.JOB+'.extern|',1),raw.replace('|106|16','|106|8')):
        with pytest.raises(ValueError): schema.slurm_row(invalid,schema.JOB)


def actual_root_accounting_frame():
    import os
    raw=schema.JOB+'|zixiao|COMPLETED|0:0|106|16|compute-0-21\n'
    return {'schema':'model_v3_actual_closed_A06_native_feedback_inputs_v1',
        'status':'ACTUAL_PARENT_C0_SDK_PENDING_INDEPENDENT_READBACK','actual_job_id':schema.JOB,
        'sdk_run_id':schema.RUN_ID,'root_uid':os.getuid(),'root_hostname':'sonmi',
        'expected_history_rows':17,'native_updates':15,'original_gate_unchanged':'FAILED',
        'no_SDK_success_inferred_from_mirror':True,'raw_sacct':raw,
        'accounting':{'argv':['sacct','-X','-n','-P','-j',schema.JOB,
            '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],
            'returncode':0,'stdout':raw,'stderr':''}}


@pytest.mark.parametrize('corruption',('argv','rc','stdout','user','state','uid','pending','mirror'))
def test_Root_actual_headerless_sacct_frame_fails_closed(corruption):
    frame=actual_root_accounting_frame()
    assert schema.root_frame_sacct(frame).startswith('JobIDRaw|User|State|ExitCode|ElapsedRaw|AllocCPUS|NodeList\n')
    if corruption=='argv': frame['accounting']['argv'][-1]='--format=JobIDRaw,State'
    elif corruption=='rc': frame['accounting']['returncode']=1
    elif corruption=='stdout': frame['accounting']['stdout']+='extra'
    elif corruption in ('user','state'):
        frame['raw_sacct']=frame['raw_sacct'].replace('zixiao','foreign') if corruption=='user' else frame['raw_sacct'].replace('COMPLETED','FAILED')
        frame['accounting']['stdout']=frame['raw_sacct']
    elif corruption=='uid': frame['root_uid']=-1
    elif corruption=='pending': frame['status']='SDK_ALREADY_VERIFIED'
    else: frame['no_SDK_success_inferred_from_mirror']=False
    with pytest.raises(ValueError): schema.root_frame_sacct(frame)


def test_report_exports_only_aggregate_allowlist_and_typed_csv(tmp_path):
    ctx=context(); certificate={'status':'VERIFIED_DIAGNOSTIC_ONLY',
        'all_public_metrics_config_summary_steps_exact':True,'native':{'native_closed':True,'history_rows':17,'native_packets':70}}
    root=tmp_path/'original'; root.mkdir(); ctx['sources']['summary']['path']=str(root/'summary.json')
    result=report.publish(tmp_path/'report',ctx,certificate,{'sha256':'a'*64},{'sha256':'b'*64})
    all_bytes=b''.join(Path(ref['path']).read_bytes() for ref in result['files'])
    for forbidden in (b'FORBIDDEN_MEMBER_ID',b'FORBIDDEN_PARAMETER_ARRAY',b'FORBIDDEN_PARAMETER_NAME'):
        assert forbidden not in all_bytes
    rows=list(csv.DictReader(io.StringIO((tmp_path/'report/summary.csv').read_text())))
    assert len(rows)==1 and rows[0]['status']=='NOT_ACCEPTED' and rows[0]['metric__native_history_rows']=='17'
    assert len(all_bytes)<128<<10 and result['archive_automatically_modified'] is False
    with pytest.raises(ValueError): report.publish(tmp_path/'report',ctx,certificate,{}, {})
    with pytest.raises(ValueError): report.publish(root/'nested',ctx,certificate,{}, {})
    denied={**certificate,'status':'PENDING'}
    with pytest.raises(ValueError): report.publish(tmp_path/'unverified',ctx,denied,{}, {})


def test_typed_csv_accepted_by_actual_repository_checker():
    import importlib.util
    import os
    path=Path(os.environ.get('SA3_REPOSITORY_CHECKER',str(schema.BASE/'MFM_model_v3/tools/check_repository.py')))
    spec=importlib.util.spec_from_file_location('a06_report_repository_checker',path)
    checker=importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    assert checker.model_summary_csv('docs/model_v3/results/A06_native_feedback_4521091.csv',report.csv_bytes(context()))


def test_full_raw_byte_bound_metadata_preparation(tmp_path,monkeypatch):
    values=fixture(); root=tmp_path/('A06_native_feedback_v4_'+schema.JOB); root.mkdir()
    def save(path,value,raw=False):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value if raw else schema.encoded(value)); return schema.file_ref(path)
    def journal(path,rows): return save(path,b''.join(schema.encoded(row) for row in rows),True)
    producer=tmp_path/'producer/diagnose_native_feedback.py'; producer_ref=save(producer,b'# synthetic source only\n',True)
    monkeypatch.setattr(schema,'PRODUCER',producer); monkeypatch.setattr(schema,'PRODUCER_SHA',producer_ref['sha256'])
    repo=tmp_path/'repo'; monkeypatch.setattr(schema,'REPO',repo)
    old_ref=journal(tmp_path/'old/reference_history.jsonl',values['originals']['reference'])
    old_free=journal(tmp_path/'old/candidate_history.jsonl',values['originals']['candidate'])
    supervisor_source=save(repo/'tools/model_v3/run_supervised.py',b'# synthetic supervisor source\n',True)
    entries=[{**producer_ref,'role':'script'},{**old_ref,'role':'457_reference_history'},
        {**old_free,'role':'457_candidate_history'}]
    pins={'schema':'A06_native_feedback_source_pins_v1','base_code_sha':schema.CODE_SHA,'files':entries,
        'original_repo_source_sha256':{'tools/model_v3/run_supervised.py':supervisor_source['sha256']}}
    pins_ref=save(producer.parent/'source_pins_v1.json',pins)
    monkeypatch.setattr(schema,'PRODUCER_PINS_SHA',pins_ref['sha256'])
    inventory=entries+[{**supervisor_source,'role':'original_repo/tools/model_v3/run_supervised.py'}]
    values['config'].update(source_pins=pins_ref,original_evidence_and_sources=inventory)
    src={'before':inventory,'after':inventory,'unchanged':True,'source_pins_sha256':pins_ref['sha256']}
    refs={key:save(root/(key+'.json'),values[value]) for key,value in
        (('configuration','config'),('summary','summary'),('run_status','status'),('data_binding','data'))}
    refs['source_closure']=save(root/'source_closure.json',src)
    refs['history']=journal(root/'history.jsonl',values['mirrors'])
    refs['consumption']=journal(root/'consumption.jsonl',values['consumption'])
    for role in ('reference','candidate'): refs[role+'_history']=journal(root/(role+'_history.jsonl'),values['histories'][role])
    refs.update(producer=producer_ref,source_pins=pins_ref,original_reference_history=old_ref,original_candidate_history=old_free)
    command=['python',str(producer),'--output',str(root),'--code-sha',schema.CODE_SHA,'--updates','15',
        '--source-pins',pins_ref['path'],'--pins-sha256',pins_ref['sha256']]
    supervisor={'job_id':schema.JOB,'status':'COMPLETED','exit_code':0,'first_failure':None,'retirement':None,
        'remaining_recorded_processes_before_retirement':[],'private_storage_cleanup_errors':[],
        'foreign_gpu_processes_signalled':False,'private_storage_final':{'first_sampling_failure':None,
            'last':{'bytes':1,'root_bytes':{'/tmp/unit':1}},'sampled_max_bytes':2,'budget_bytes':4096},
        'command':command,'supervisor_source_sha256':supervisor_source['sha256']}
    supervisor_ref=save(tmp_path/'supervisor.json',supervisor)
    sacct_ref=save(tmp_path/'sacct.txt',('JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS\n'+schema.JOB+'|COMPLETED|0:0|106|16\n').encode(),True)
    refs['root_closure']=save(tmp_path/'closure.json',{'schema':'model_v3_A06_feedback_root_closure_v1',
        'job_id':schema.JOB,'supervisor':supervisor_ref,'raw_sacct':sacct_ref})
    sdk_path=root/'wandb/offline-run-unit'/('run-'+schema.RUN_ID+'.wandb'); refs['sdk']=save(sdk_path,b'not an SDK; metadata preparation never scans it',True)
    updates=[save(root/f'update_{index:02d}.json',detail) for index,detail in enumerate(values['details'],1)]
    manifest={'schema':'model_v3_A06_feedback_verification_inputs_v1','expected_job_id':schema.JOB,
        'expected_run_id':schema.RUN_ID,'files':refs,'update_files':updates}
    prepared=schema.prepare(manifest)
    assert prepared['expected_rows']==values['mirrors'] and prepared['source_inventory_count']==4
    assert preparer.build_manifest(root,refs['root_closure'])==manifest
    assert compare(ctx=prepared)['native_closed'] is True
    # The actual Root schema is accepted directly, retaining its original bytes.
    # These remain synthetic receipts and are never mistaken for actual C0.
    frame=actual_root_accounting_frame(); frame['run_root']=str(root); frame['sdk_file']=refs['sdk']
    frame['source_pin_inventory']=pins
    frame['files']={Path(ref['path']).name:ref for key,ref in refs.items() if key in
        ('configuration','summary','run_status','source_closure','data_binding','history',
            'reference_history','candidate_history','consumption')}
    frame['files']['resources.jsonl']=save(root/'resources.jsonl',b'{}\n',True)
    frame['files'].update({Path(ref['path']).name:ref for ref in updates})
    frame['references']={'supervisor':supervisor_ref,'producer':producer_ref,'source_pins':pins_ref,
        **{role:save(tmp_path/(role+'.json'),{'synthetic':True}) for role in ('publication','submission','prelaunch')}}
    frame_ref=save(tmp_path/'actual_root_shape.json',frame)
    direct=schema.prepare(frame,frame_ref)
    assert direct['expected_rows']==values['mirrors'] and direct['root_operational_bindings']==frame['references']
    with pytest.raises(ValueError): schema.prepare(frame)
    Path(updates[13]['path']).write_bytes(b'{}\n')
    with pytest.raises(ValueError,match='binding differs'): schema.prepare(manifest)
