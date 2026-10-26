"""Read-only A06 diagnostic metadata admission. Never import a model or dataset."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

BASE = Path('/share/home/zixiao/descriptor_analysis')
PRODUCER = BASE/'runs/model_v3_20261026/a06_gradient_feedback_diagnostic_v1/diagnose_native_feedback.py'
PRODUCER_SHA = 'b8fb0c05feda698d35a56de40c62d060feb3fc5b3ae2eab7bd593ae95b926004'
PRODUCER_PINS_SHA = '7daacc3e9b465f007a10cd0b0644c4f1e8f96f8801d76b6a3943c8c4981e269d'
READER = BASE/'runs/model_v3_20261025/archive_closed_v7_source/bounded_history_v7.py'
READER_SHA = '6aee76e16c182be97b7f88e635b43948510d0fc335e0ccfbf9ba107a1c29ab95'
REPO = BASE/'MFM_model_v3_a_checkpoint'
CODE_SHA = '8ece64c685fe287d6863fbbe2f6f52006632a5cc'
PREREG_SHA = '61658a4c1f472de035601dbedc17809315774784'
JOB, RUN_ID = '4521091', 'bb3fue46'
RUN_NAME = 'A06_native_feedback_'+JOB
STATUS = 'DIAGNOSTIC_COMPLETED_PENDING_SDK_AND_OUTER_TERMINAL'
UPDATES, TOTAL_BASE = 15, 5120
FILE_CAP, LINE_CAP = 4 << 20, 128 << 10
LIMITS = {'max_source_bytes': 128 << 20, 'max_native_records': 500000,
    'max_history_rows': 100000, 'max_record_bytes': 4 << 20,
    'max_export_bytes': 64 << 20, 'max_wall_seconds': 180}
REPLAY_FIELDS = ('optimizer_updates','loss','gradient_norm','base_records','native_atoms',
    'consumed_base_records','input_receipt_sha256','valid_label_counts')
ROLES = ('free_vs_reference','shadow_vs_reference','free_vs_shadow')
COMPONENTS = ('parameters','exp_avg','exp_avg_sq','step')
SOURCE_KEYS = ('configuration','summary','run_status','source_closure','data_binding','history',
    'reference_history','candidate_history','consumption','source_pins','producer',
    'original_reference_history','original_candidate_history','root_closure','sdk')


def require(ok, message):
    if not ok: raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def canonical(value): return hashlib.sha256(encoded(value)).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key'); result[key] = value
        return result
    def illegal(value): raise ValueError('Nonfinite JSON literal: '+value)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=illegal)
    def finite(item):
        if type(item) is float: require(math.isfinite(item), 'Nonfinite JSON number')
        elif type(item) is dict:
            for child in item.values(): finite(child)
        elif type(item) is list:
            for child in item: finite(child)
    finite(value)
    return value


def file_ref(path, cap=FILE_CAP):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and path == path.resolve(strict=True),
        'Physical absolute path without symlinks required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'Bounded ordinary file required')
    digest, size = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev,opened.st_ino) == (before.st_dev,before.st_ino), 'Input replaced while opening')
        for block in iter(lambda: stream.read(1 << 20), b''):
            size += len(block); require(size <= cap, 'Input grew beyond byte limit'); digest.update(block)
    after = path.lstat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
        == (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and size == before.st_size,
        'Input changed while hashing')
    return {'path':str(path),'bytes':size,'sha256':digest.hexdigest()}


def bind(ref, cap=FILE_CAP):
    require(type(ref) is dict and set(ref) == {'path','bytes','sha256'}
        and type(ref['bytes']) is int and 0 <= ref['bytes'] <= cap
        and re.fullmatch('[0-9a-f]{64}',ref['sha256']), 'Exact bounded raw-byte reference required')
    require(file_ref(ref['path'],cap) == ref, 'Raw-byte input binding differs')
    return Path(ref['path'])


def read(ref):
    path = bind(ref); value = strict_json(path.read_bytes())
    require(file_ref(path) == ref, 'Metadata changed during parsing')
    return value


def lines(ref, count):
    path = bind(ref); result = []
    with path.open('rb') as stream:
        for _ in range(count+1):
            raw = stream.readline(LINE_CAP+1)
            if not raw: break
            require(len(result) < count and raw.endswith(b'\n') and len(raw) <= LINE_CAP,
                'Truncated/oversized/excess metadata rows')
            result.append(strict_json(raw))
    require(len(result) == count and file_ref(path) == ref, 'Metadata row count or byte binding differs')
    return result


def reader():
    require(file_ref(READER)['sha256'] == READER_SHA, 'Frozen bounded reader SHA differs')
    key = 'a06_feedback_frozen_archive_v7'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key,READER)
        module = importlib.util.module_from_spec(spec); sys.modules[key] = module; spec.loader.exec_module(module)
    return sys.modules[key]


def exact(actual, expected, message):
    # Canonical JSON retains bool/int/float distinctions in saved metadata.
    require(encoded(actual) == encoded(expected), message)


def number(value, message):
    require(type(value) in (int,float) and math.isfinite(value), message); return value


def validate_outputs(config, summary, status, data, mirrors, histories, originals, consumption, details):
    """Pure metadata cross-check; does not perform target, tensor or SDK access."""
    require(config['schema'] == 'A06_native_gradient_feedback_diagnostic_v1'
        and config['scope'] == '15_native_updates_diagnostic_only' and config['updates'] == UPDATES
        and config['code_sha'] == CODE_SHA and config['prereg_sha'] == PREREG_SHA
        and type(config['seed']) is int and config['seed'] == 0, 'Fixed diagnostic configuration differs')
    require(config['scientific_acceptance'] is False and config['A06_original_gate_status'] == 'FAILED_UNCHANGED'
        and config['fixed20_batch_gate_rerun'] is False and config['resume_supported'] is False,
        'Diagnostic must not acquire scientific acceptance')
    require(config['model']['backbone']['dim'] == 512 and config['model']['backbone']['layers'] == 6,
        'Original 6x512 model required')
    require(config['original_options']['reference']['fused_adamw'] is False
        and config['original_options']['candidate']['fused_adamw'] is True,
        'Reference foreach and free fused identities differ')
    env = config['environment']
    require(env['tracking_mode'] == 'offline' and env['downstream_data_read'] is False
        and env['original_lmdb_written'] is False, 'Read-only native-S diagnostic environment required')
    require(summary['status'] == STATUS and status['status'] == STATUS and status['failure'] is None
        and status['cleanup_errors'] == [] and status['job_id'] == JOB and status['sdk_run_id'] == RUN_ID
        and status['code_sha'] == CODE_SHA and status['offline_unsynced'] is True,
        'Successful diagnostic cleanup/run identity required')
    require(status['input_cleanup'] == {'errors':[],'input_descriptors_closed':True}
        and status['completed_native_updates'] == UPDATES and status['acknowledged_history_commits'] == UPDATES+2
        and status['expected_success_HISTORY_rows'] == UPDATES+2
        and status['SDK_native_verification'] == 'PENDING_INDEPENDENT_READBACK_not_inferred_from_mirror'
        and status['scientific_acceptance'] is False and status['foreign_gpu_risk_observed'] is False,
        'Pending independent SDK/clean input closure required')
    require(summary['native_updates'] == UPDATES and summary['consumed_base_records'] == TOTAL_BASE
        and summary['all_replay_points_exact457'] is True and summary['shadow_has_model_forward'] is False
        and summary['scientific_acceptance'] is False and summary['foreign_gpu_risk_observed'] is False
        and summary['A06_original_gate_status'] == 'FAILED_UNCHANGED'
        and summary['attribution'] == 'EVIDENCE_ONLY_NO_AUTOMATIC_CAUSAL_CONCLUSION'
        and summary['fixed20_rerun'] is False and summary['full500_rerun'] is False
        and summary['resume_supported'] is False, 'Diagnostic interpretation/consumption differs')
    require(data['input_kind'] == 'native_s' and data['seed'] == 0, 'Original native-S input identity required')
    require(len(mirrors) == 17 and len(consumption) == len(details) == UPDATES
        and all(len(histories[role]) == UPDATES and len(originals[role]) == 500 for role in ('reference','candidate')),
        'Complete bounded diagnostic populations required')
    expected = [{'step':0,'row':{'event':'START','diagnostic_only':True,
        'requested_native_updates':UPDATES,'scientific_acceptance':False}}]
    points, consumed = [], 0
    for update in range(1,UPDATES+1):
        detail, used = details[update-1], consumption[update-1]
        left, right = (histories[role][update-1] for role in ('reference','candidate'))
        require(detail['update'] == used['update'] == update and detail['scientific_acceptance'] is False,
            'Update identity differs')
        require(set(detail['replay']) == {'reference','candidate'}, 'Replay role population differs')
        for role, current in (('reference',left),('candidate',right)):
            require(set(current) == set(REPLAY_FIELDS) and current['optimizer_updates'] == update,
                'Saved native scalar fields differ')
            old = originals[role][update-1]
            exact(current,{key:old[key] for key in REPLAY_FIELDS},'Saved457 native scalar/input replay differs')
            require(detail['replay'][role] == {'comparison':'exact_saved457_scalar_and_input_receipt',
                'differences':{},'pass':True}, 'Replay diagnostic contradicts saved scalars')
            for key in ('loss','gradient_norm'): number(current[key],'Nonfinite native scalar')
            require(type(current['base_records']) is int and current['base_records'] > 0
                and type(current['native_atoms']) is int and current['native_atoms'] > 0, 'Positive native population required')
        for key in ('base_records','native_atoms','consumed_base_records','input_receipt_sha256','valid_label_counts'):
            exact(left[key],right[key],'Reference/free data consumption differs')
        consumed += left['base_records']
        require(left['consumed_base_records'] == consumed and used['base_records'] == left['base_records']
            and used['input_receipt_sha256'] == left['input_receipt_sha256'], 'Committed consumption differs')
        stream = used['committed_stream']; sampler = stream['sampler']
        require(stream['committed_base_samples'] == sampler['samples_consumed'] == consumed
            and sampler['batches_consumed'] == update and sampler['contract_sha256'] == data['sampler_contract_sha256']
            and sampler['schema_version'] == 'phase1_block_atom_sampler_v1', 'Sampler cursor/contract differs')
        relative = abs(right['loss']-left['loss'])/max(abs(left['loss']),1e-12)
        gate = {'pass':relative <= .001,'relative_difference':relative,'step':update,'threshold':.001}
        exact(detail['original_trajectory_threshold_point_check'],gate,'Original unchanged trajectory threshold differs')
        require(detail['execution_order'] == (['reference','candidate','shadow'] if update%2 else ['candidate','reference','shadow'])
            and detail['dispatch'] == {'reference/_multi_tensor_adam':1,'candidate/_fused_adam':1,'shadow/_fused_adam':1},
            'Three-path execution/dispatch differs')
        shared = detail['shared_clipped_reference_gradient']
        require(shared['unchanged'] is True and shared['alias_same_tensor_and_none'] is True,
            'Borrowed reference gradients changed')
        exact(shared['before'],shared['after'],'Borrowed gradient digest differs')
        exact(shared['before'],shared['reference_after'],'Reference gradients changed in shadow step')
        for role in ('reference','candidate','shadow'):
            step = detail['step_state_representation'][role]
            require(step['value'] == float(update) and step['dtype'] == 'torch.float32'
                and step['device'] == ('cpu' if role == 'reference' else 'cuda:0'), 'Optimizer step representation differs')
        raw = detail['raw_native_gradient_comparison']
        row = {'event':'NATIVE_GRADIENT_FEEDBACK_UPDATE','native_updates':update,
            'reference/loss':left['loss'],'free_fused/loss':right['loss'],
            'reference/preclip_gradient_norm':left['gradient_norm'],'free_fused/preclip_gradient_norm':right['gradient_norm'],
            'trajectory/relative_difference':relative,'trajectory/original_point_pass':gate['pass'],
            'replay/exact457':True,'shadow/borrowed_gradients_unchanged':True,
            'gradient/free_vs_reference_max_parameter_relative_l2':number(raw['max_relative_l2'],'Nonfinite gradient aggregate'),
            'consumed_base_records':consumed,'scientific_acceptance':False}
        point = {'update':update,'loss_relative_difference':relative,'original_point_pass':gate['pass'],
            'raw_gradient_max_relative_l2':raw['max_relative_l2']}
        require(set(detail['comparisons']) == set(ROLES), 'Comparison roles differ')
        for role in ROLES:
            require(set(detail['comparisons'][role]) == set(COMPONENTS), 'Moment/parameter components differ')
            point[role] = {}
            for component in COMPONENTS:
                value = detail['comparisons'][role][component]
                for source, field in (('max_relative_l2','max_parameter_relative_l2'),
                        ('global_difference_l2_diagnostic_only','global_difference_l2_diagnostic_only')):
                    row[role+'/'+component+'/'+field] = number(value[source],'Nonfinite comparison aggregate')
                point[role][component] = value['global_difference_l2_diagnostic_only']
        points.append(point); expected.append({'step':update,'row':row})
    first_failure = next((point['update'] for point in points if not point['original_point_pass']),None)
    require(consumed == TOTAL_BASE and first_failure == summary['first_original_threshold_failure'] == 14,
        'Original first failure14/5120base evidence differs')
    exact(summary['points'],points,'Summary points differ from detailed diagnostic aggregates')
    expected.append({'step':16,'row':{'event':'COMPLETE','native_updates':UPDATES,
        'first_original_threshold_failure':first_failure,'all_replay_points_exact457':True,'scientific_acceptance':False}})
    exact(mirrors,expected,'All mirror metrics/steps must match code-derived saved outputs')
    return expected


def slurm_row(raw, job):
    rows = [line.split('|') for line in raw.strip().splitlines()]
    require(rows and {'JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS'} <= set(rows[0]), 'Actual sacct columns required')
    columns = rows[0]; records = [dict(zip(columns,row)) for row in rows[1:] if len(row) == len(columns)]
    matches = [row for row in records if row['JobIDRaw'] == job]
    require(len(matches) == 1, 'Exactly one actual Slurm parent row required')
    row = matches[0]
    require(row['State'] == 'COMPLETED' and row['ExitCode'] == '0:0'
        and row['ElapsedRaw'].isdecimal() and int(row['ElapsedRaw']) > 0
        and row['AllocCPUS'].isdecimal() and int(row['AllocCPUS']) >= 16, 'Actual parent C0/CPU allocation required')
    return row


def root_frame_sacct(frame):
    columns='JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'
    require(frame['schema']=='model_v3_actual_closed_A06_native_feedback_inputs_v1'
        and frame['status']=='ACTUAL_PARENT_C0_SDK_PENDING_INDEPENDENT_READBACK'
        and frame['actual_job_id']==JOB and frame['sdk_run_id']==RUN_ID and frame['root_uid']==os.getuid()
        and frame['root_hostname']=='sonmi' and frame['expected_history_rows']==17 and frame['native_updates']==15
        and frame['original_gate_unchanged']=='FAILED' and frame['no_SDK_success_inferred_from_mirror'] is True,
        'Actual Root frame identity/scope differs')
    record=frame['accounting']
    require(record['argv']==['sacct','-X','-n','-P','-j',JOB,'--format='+columns]
        and type(record['returncode']) is int and record['returncode']==0 and record['stderr']==''
        and record['stdout']==frame['raw_sacct'], 'Actual sacct command/rc/rawstdout differs')
    raw=columns.replace(',','|')+'\n'+frame['raw_sacct']
    row=slurm_row(raw,JOB)
    require(row['User']=='zixiao' and row['NodeList']=='compute-0-21', 'Actual parent user/node differs')
    return raw


def validate_closure(closure, supervisor, raw_sacct, root, config, source_inventory):
    if closure['schema']=='model_v3_actual_closed_A06_native_feedback_inputs_v1':
        require(raw_sacct==root_frame_sacct(closure) and closure['run_root']==str(root), 'Actual Root accounting/root differs')
    else:
        require(closure['schema'] == 'model_v3_A06_feedback_root_closure_v1' and closure['job_id'] == JOB,
            'Root closure schema/job differs')
    row = slurm_row(raw_sacct,JOB)
    require(supervisor['job_id'] == JOB and supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
        and supervisor['first_failure'] is None and supervisor['retirement'] is None
        and supervisor['remaining_recorded_processes_before_retirement'] == []
        and supervisor['private_storage_cleanup_errors'] == [] and supervisor['foreign_gpu_processes_signalled'] is False,
        'Actual supervisor/process cleanup did not close successfully')
    private = supervisor['private_storage_final']
    require(private['first_sampling_failure'] is None and private['last']['bytes'] == sum(private['last']['root_bytes'].values())
        and private['sampled_max_bytes'] <= private['budget_bytes'], 'Private storage closure differs')
    command = supervisor['command']
    def option(name):
        require(command.count(name) == 1 and command.index(name)+1 < len(command), 'Missing/duplicate supervisor argument')
        return command[command.index(name)+1]
    require(command.count(str(PRODUCER)) == 1 and option('--output') == str(root)
        and option('--code-sha') == CODE_SHA and option('--updates') == '15'
        and option('--source-pins') == config['source_pins']['path']
        and option('--pins-sha256') == PRODUCER_PINS_SHA, 'Supervisor launched a different producer/configuration')
    source = next(entry for entry in source_inventory if entry['role'] == 'original_repo/tools/model_v3/run_supervised.py')
    require(supervisor['supervisor_source_sha256'] == source['sha256'], 'Supervisor implementation/source closure differs')
    return {'job_id':JOB,'state':row['State'],'exit_code':row['ExitCode'],
        'elapsed_seconds':int(row['ElapsedRaw']),'allocated_cpus':int(row['AllocCPUS'])}


def prepare(manifest, manifest_ref=None):
    if manifest.get('schema')=='model_v3_actual_closed_A06_native_feedback_inputs_v1':
        require(manifest_ref is not None, 'Root original frame needs its raw-byte input reference')
        exact(read(manifest_ref),manifest,'Actual Root manifest bytes differ')
        root_frame_sacct(manifest)
        root=Path(manifest['run_root']); files=manifest['files']; refs={}
        expected_names={role+'.'+('jsonl' if role in ('history','reference_history','candidate_history','consumption')
            else 'json') for role in SOURCE_KEYS if role not in
            ('sdk','producer','source_pins','original_reference_history','original_candidate_history','root_closure')}
        expected_names |= {'resources.jsonl'} | {f'update_{update:02d}.json' for update in range(1,16)}
        require(set(files)==expected_names and all(ref['path']==str(root/name) for name,ref in files.items()),
            'Actual Root top-level artifact roles/paths differ')
        references=manifest['references']
        require(set(references)=={'supervisor','source_pins','producer','publication','submission','prelaunch'},
            'Actual Root launch/source reference roles differ')
        pins=read(references['source_pins']); exact(pins,manifest['source_pin_inventory'],'Root pinned inventory snapshot differs')
        pinned_roles={row['role']:row for row in pins['files']}
        for role in SOURCE_KEYS:
            if role in ('producer','source_pins'): refs[role]=references[role]
            elif role=='sdk': refs[role]=manifest['sdk_file']
            elif role=='root_closure': refs[role]=manifest_ref
            elif role.startswith('original_'):
                entry=pinned_roles['457_'+role.removeprefix('original_')]
                refs[role]={key:entry[key] for key in ('path','bytes','sha256')}
            else:
                extension='jsonl' if role in ('history','reference_history','candidate_history','consumption') else 'json'
                refs[role]=files[role+'.'+extension]
        normalized={'schema':'model_v3_A06_feedback_verification_inputs_v1','expected_job_id':JOB,
            'expected_run_id':RUN_ID,'files':refs,'update_files':[files[f'update_{update:02d}.json'] for update in range(1,16)]}
        context=prepare(normalized)
        extra=list(references.values())+[files['resources.jsonl']]
        for ref in extra: bind(ref)
        context['all_refs']+=extra
        context['root_operational_bindings']=references
        return context
    require(manifest['schema'] == 'model_v3_A06_feedback_verification_inputs_v1'
        and manifest['expected_job_id'] == JOB and manifest['expected_run_id'] == RUN_ID,
        'Only the declared A06 diagnostic is admitted')
    refs = manifest['files']; require(set(refs) == set(SOURCE_KEYS), 'Exact metadata role allowlist required')
    root = Path(refs['summary']['path']).parent
    require(root.name == 'A06_native_feedback_v4_'+JOB, 'Declared v4 diagnostic root required')
    for role in SOURCE_KEYS:
        if role not in ('sdk','producer','source_pins','original_reference_history','original_candidate_history','root_closure'):
            require(Path(refs[role]['path']).parent == root and Path(refs[role]['path']).name == role+'.'+('jsonl' if role in
                ('history','reference_history','candidate_history','consumption') else 'json'), 'Metadata role path differs')
    require(refs['producer']['path'] == str(PRODUCER) and refs['producer']['sha256'] == PRODUCER_SHA
        and refs['source_pins']['sha256'] == PRODUCER_PINS_SHA, 'Fixed logger/source manifest differs')
    bind(refs['producer']); pins = read(refs['source_pins'])
    config, summary, status, closure, data, root_closure = (read(refs[key]) for key in
        ('configuration','summary','run_status','source_closure','data_binding','root_closure'))
    require(closure['unchanged'] is True and closure['source_pins_sha256'] == PRODUCER_PINS_SHA
        and closure['before'] == closure['after'] == config['original_evidence_and_sources']
        and config['source_pins'] == refs['source_pins'], 'Producer before/after source closure differs')
    require(pins['schema'] == 'A06_native_feedback_source_pins_v1' and pins['base_code_sha'] == CODE_SHA,
        'Fixed producer source manifest schema differs')
    saved_sources = closure['before']; roles = {entry['role']:entry for entry in saved_sources}
    require(len(roles) == len(saved_sources), 'Unique source roles required')
    expected_roles = {entry['role'] for entry in pins['files']} | {'original_repo/'+name for name in pins['original_repo_source_sha256']}
    require(set(roles) == expected_roles, 'Complete frozen source inventory required')
    for entry in pins['files']:
        exact(roles[entry['role']],{key:entry[key] for key in ('path','bytes','sha256','role')},'Pinned evidence/source closure differs')
    for name, digest in pins['original_repo_source_sha256'].items():
        entry = roles['original_repo/'+name]
        require(entry['path'] == str(REPO/name) and entry['sha256'] == digest, 'Original repository source binding differs')
    source_total = sum(entry['bytes'] for entry in saved_sources)
    require(source_total <= 32 << 20, 'Frozen source/evidence inventory exceeds32MiB')
    # Inventory contains only the fixed source/configuration/history metadata roles;
    # no native corpus shard, target payload, checkpoint or parameter file is opened.
    for entry in saved_sources: bind({key:entry[key] for key in ('path','bytes','sha256')})
    for role in ('reference','candidate'):
        exact(refs['original_'+role+'_history'],{key:roles['457_'+role+'_history'][key] for key in ('path','bytes','sha256')},
            'Original457 history binding differs')
    details_ref = manifest['update_files']
    require(len(details_ref) == UPDATES, 'Fifteen detailed diagnostic refs required')
    for update, ref in enumerate(details_ref,1):
        require(ref['path'] == str(root/f'update_{update:02d}.json'), 'Ordered detailed update path differs')
    details = [read(ref) for ref in details_ref]
    histories = {role:lines(refs[role+'_history'],15) for role in ('reference','candidate')}
    originals = {role:lines(refs['original_'+role+'_history'],500) for role in ('reference','candidate')}
    expected = validate_outputs(config,summary,status,data,lines(refs['history'],17),histories,originals,
        lines(refs['consumption'],15),details)
    if root_closure['schema']=='model_v3_actual_closed_A06_native_feedback_inputs_v1':
        supervisor_ref=root_closure['references']['supervisor']; raw_sacct=root_frame_sacct(root_closure)
        closure_refs=[supervisor_ref]
    else:
        supervisor_ref=root_closure['supervisor']; raw_sacct_path=bind(root_closure['raw_sacct'])
        raw_sacct=raw_sacct_path.read_text(encoding='utf-8')
        require(file_ref(raw_sacct_path)==root_closure['raw_sacct'],'Sacct changed during parsing')
        closure_refs=[supervisor_ref,root_closure['raw_sacct']]
    supervisor=read(supervisor_ref)
    accounting = validate_closure(root_closure,supervisor,raw_sacct,root,config,saved_sources)
    sdk = bind(refs['sdk'],LIMITS['max_source_bytes'])
    require(sdk.is_relative_to(root/'wandb') and sdk.name == 'run-'+RUN_ID+'.wandb', 'Exact native offline run SDK required')
    all_refs = list(refs.values())+details_ref+closure_refs
    all_refs += [{key:entry[key] for key in ('path','bytes','sha256')} for entry in saved_sources]
    return {'expected_config':config,'expected_rows':expected,'run_id':RUN_ID,'run_name':RUN_NAME,
        'SDK_file':refs['sdk'],'sources':refs,'update_refs':details_ref,'all_refs':all_refs,
        'source_inventory_sha256':canonical(saved_sources),'source_inventory_count':len(saved_sources),
        'source_inventory_bytes':source_total,'accounting':accounting,'summary':summary,
        'data_version':'native_s_'+data['sampler_contract_sha256'],'configuration_ref':refs['configuration']}
