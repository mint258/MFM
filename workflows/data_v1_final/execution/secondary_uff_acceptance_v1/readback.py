"""Guarded Main readback of existing16 Alpha software controls; no UFF/QM/LMDB."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,os,stat,time
from pathlib import Path

from workflows.data_v1_final.conformers.portable_secondary_uff_v1.bridge import scientific_sha
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.prepare_existing_controls import select_metadata
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.contract import (
    canonical,sha,need,read_small,ref,verify,prep_metadata,recipe_equivalence,CONTROL_MODE,MISSING_IDS)

PROJECT=Path('/share/home/zixiao/descriptor_analysis');RUN=PROJECT/'runs/data_v1_20261025';REPO=RUN/'repository'
ALPHA_ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
MAIN_ENDPOINT='202.38.247.57:22';ALPHA_ENDPOINT='218.192.171.238:22'
MAIN_PREP_JOB='4521182';ALPHA_JOB='1884766';ALPHA_NODE='compute-0-6'
SCOPE='secondary_uff_control16_main_acceptance_v1'
PARAMETERS={'existing_control_count':16,'population_members_added':0,'two_missing_replayed':False,
    'alpha_job_id':ALPHA_JOB,'alpha_uid':1264,'main_preparation_job_id':MAIN_PREP_JOB,
    'new_UFF_QM_calls':0,'scientific_comparison':'full_packet_canonical_SHA_except_summary_elapsed_seconds'}
VERSIONS={'python':'3.11.14','numpy':'2.2.6','rdkit':'2025.09.5','torch':'2.5.1+cpu','torch_geometric':'2.7.0'}


def normalized(value):
    out={key:value[key] for key in ('path','bytes','sha256')}
    need(Path(out['path']).is_absolute() and type(out['bytes']) is int and out['bytes']>=0 and
         isinstance(out['sha256'],str) and len(out['sha256'])==64 and set(out['sha256'])<=set('0123456789abcdef'),
         'EXACT_FILE_REFERENCE_REQUIRED')
    return out


def source(value,declared):
    value=normalized(value)
    need(declared.get(value['path'])==value,'SMALL_ACCEPTANCE_INPUT_NOT_IN_MAIN_REQUEST')
    return verify(value)


def small(value,declared):return json.loads(read_small(source(value,declared)))


def copied(item,declared,*,origin=None):
    old,new=normalized(item['origin_reference']),normalized(item['main_copy_reference'])
    need(ALPHA_ROOT in Path(old['path']).parents and RUN in Path(new['path']).parents and
         old['bytes']==new['bytes'] and old['sha256']==new['sha256'],'ORIGINAL_ALPHA_AND_MAIN_COPY_BYTES_DIFFER')
    if origin is not None:need(old==normalized(origin),'ALPHA_COPY_ORIGIN_DIFFERS_FROM_ACTUAL_RECEIPT')
    return small(new,declared)


def read_packet(reference,data_refs,*,expected_identity=None):
    reference=normalized(reference);path=Path(reference['path'])
    need(RUN in path.parents and REPO not in path.parents and path.name.endswith('.json.gz') and
         not any(p.is_symlink() for p in (path,*path.parents)) and data_refs.get(str(path))==reference,
         'EXACT_DECLARED_EXTERNAL_PACKET_ONLY')
    def identity(info):return {'device':info.st_dev,'inode':info.st_ino,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns,'uid':info.st_uid}
    before=path.stat();frame=identity(before)
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==reference['bytes'],'ACTUAL_MAIN_PACKET_OWNER_OR_SIZE_DIFFERS')
    if expected_identity is not None:need(frame==expected_identity,'ORIGINAL_MAIN_BASELINE_PACKET_IDENTITY_CHANGED')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    need(digest.hexdigest()==reference['sha256'] and identity(path.stat())==frame,'FULL_COMPRESSED_PACKET_SHA_OR_IDENTITY_CHANGED')
    # A completed read shorter than cap+1 reaches EOF and validates gzip CRC/trailer.
    with gzip.open(path,'rb') as stream:raw=stream.read((1<<30)+1)
    need(len(raw)<=1<<30 and identity(path.stat())==frame,'PACKET_INFLATED_CAP_OR_IDENTITY_CHANGED')
    packet=json.loads(raw)
    return packet,{'reference':reference,'actual_main_file_identity':frame,'full_compressed_sha_verified':True,
        'gzip_EOF_CRC_verified':True,'uncompressed_bytes':len(raw),'no_pickle_or_scientific_generation_used':True}


def actual_parent(account,raw,job_id,*,endpoint,uid,node):
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
    raw_parent=[row for row in rows if row.get('JobIDRaw')==job_id]
    if endpoint==ALPHA_ENDPOINT:
        need(account.get('schema')=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and
             account.get('endpoint')==endpoint and account.get('uid')==uid and account.get('job_id')==job_id and
             account.get('actual_terminal') is True and account.get('query_returncode')==0 and
             account['command_argv'][0]=='sacct','ACTUAL_ALPHA_TERMINAL_ACCOUNTING_REQUIRED')
        parents=[account['actual_parent']]
    else:
        need(account.get('schema')=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and account.get('query_returncode')==0,
             'ACTUAL_MAIN_OWNED_ACCOUNTING_REQUIRED')
        parents=[row for row in account['actual_parents'] if row.get('JobIDRaw')==job_id]
    need(len(parents)==len(raw_parent)==1,'ONE_EXACT_ENDPOINT_PARENT_AND_RAW_ROW_REQUIRED')
    parent=parents[0]
    for key in ('JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'):
        need(parent[key]==raw_parent[0][key],'ACTUAL_ACCOUNTING_AND_RAW_PARENT_DIFFERS:'+key)
    need(parent['JobIDRaw']==job_id and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and
         parent['NodeList']==node and parent['Partition']=='cpu' and int(parent['AllocCPUS'])==16 and
         int(parent['ElapsedRaw'])>=0,'ACTUAL_C0_CPU16_PARENT_REQUIRED')
    if endpoint==ALPHA_ENDPOINT:
        need(parent['UID']==raw_parent[0]['UID']==str(uid) and parent['User']==raw_parent[0]['User']=='alpha',
             'ACTUAL_ALPHA_PARENT_OWNER_REQUIRED')
    elif 'UID' in raw_parent[0]:need(raw_parent[0]['UID']==str(uid),'ACTUAL_MAIN_PARENT_OWNER_DIFFERS')
    seconds=int(parent['ElapsedRaw'])*16
    if endpoint==ALPHA_ENDPOINT:need(account['allocated_core_seconds_observed']==seconds,'ACTUAL_ALPHA_CORE_COST_DIFFERS')
    return {'endpoint':endpoint,'uid':uid,'job_id':job_id,'actual_parent':parent,'allocated_core_seconds':seconds,
        'raw_steps_retained_not_added_to_parent_cost':[row for row in rows if row.get('JobIDRaw','').startswith(job_id+'.')],
        'zero_integer_seconds_not_claimed_true_zero_cost':True}


def packet_facts(packet,mid,expected):
    summary=packet['summary'];conformers=packet['conformers'];pm7=packet['pm7']
    need(summary['molecule_id']==mid and summary['status']=='SUCCESS' and type(summary['seed']) is int and summary['seed']>0 and
         summary['expected_conformers']==expected['expected_conformers'] and summary['heavy_atoms']==expected['heavy_atoms'] and
         len(conformers)==summary['expected_conformers'] and summary['source_record_id'] and summary['atom_order_sha256'],
         'CONTROL_TASK_SEED_SOURCE_ATOM_ORDER_OR_COUNT_DIFFERS')
    need(len({row['sprime_conf_idx'] for row in conformers})==len(conformers) and
         all(row['status']=='SUCCESS' and row['converged'] is True and row['source_record_id']==summary['source_record_id'] and
             row['atom_order_sha256']==summary['atom_order_sha256'] and len(row['geometry_sha256'])==64 for row in conformers) and
         len({row['record_id'] for row in pm7})==len(pm7) and all(len(row['geometry_sha256'])==64 for row in pm7),
         'CONTROL_GEOMETRY_OR_NATIVE_ANCHOR_IDENTITY_DIFFERS')
    return {'seed':summary['seed'],'cohort':summary['cohort'],'source_record_id':summary['source_record_id'],
        'atom_order_sha256':summary['atom_order_sha256'],'heavy_atoms':summary['heavy_atoms'],'expected_conformers':summary['expected_conformers'],
        'uff_geometry_ids_and_hashes':[(row['sprime_conf_idx'],row['geometry_sha256']) for row in conformers],
        'pm7_native_ids_and_hashes':[(row['record_id'],row['geometry_sha256']) for row in pm7]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','root-preflight','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();started=time.monotonic()
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    entry=Path(__file__).absolute()
    argv=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m',
        'workflows.data_v1_final.execution.secondary_uff_acceptance_v1.readback','--inputs',str(args.inputs.absolute()),
        '--root-preflight',str(args.root_preflight.absolute()),'--output',str(args.output.absolute())]
    proof=require_startup(args.root_preflight,expected_scope_key=SCOPE,expected_scope_parameters=PARAMETERS,
        expected_execution_argv=argv,expected_source=entry,expected_kind='analysis',required_references=(ref(args.inputs.absolute()),))
    need(os.getuid()==1278 and proof['request']['pilot'] is False and
         entry==REPO/'workflows/data_v1_final/execution/secondary_uff_acceptance_v1/readback.py','REAL_MAIN_NONPILOT_READBACK_PRIMARY_REQUIRED')
    need(proof['request']['estimated_peak_output_bytes']>=4<<20,'BOUNDED_READBACK_REPORT_RESERVE_AT_LEAST4MIB_REQUIRED')
    sources={row['path']:normalized(row) for row in proof['request']['source_references']}
    data_refs={row['path']:normalized(row) for row in proof['request'].get('data_references',[])}
    portable=REPO/'workflows/data_v1_final/conformers/portable_secondary_uff_v1'
    for path in [entry,*entry.parent.glob('*.py'),*[portable/name for name in ('__init__.py','bridge.py','contract.py','prepare_existing_controls.py')]]:
        source(ref(path),sources)
    inputs=json.loads(read_small(args.inputs.absolute()))
    need(inputs.get('schema')=='ROOT_SECONDARY_UFF_CONTROL16_MAIN_ACCEPTANCE_INPUTS_V1' and
         inputs.get('status')=='ROOT_STAGED_FOR_MAIN_CPU_READBACK' and inputs.get('reviewer')=='root',
         'ROOT_STAGED_ACTUAL_READBACK_INPUTS_REQUIRED')
    prep=small(inputs['main_preparation'],sources);expected=prep_metadata(prep)
    closed=small(prep['original_complete_packages_reference'],sources)
    need(len(closed)==len({row['molecule_id'] for row in closed})==334 and
         not {row['molecule_id'] for row in closed}&MISSING_IDS,'EXACT_EXISTING334_SELECTION_METADATA_REQUIRED')
    selected,selection=select_metadata(closed)
    need(len(selected)==16 and [row['molecule_id'] for row in selected]==prep['allowed_original_control_ids'],
         'FIXED32_30_60_HASH_SELECTION_DIFFERS')
    for row in selected:
        golden=expected[row['molecule_id']]
        need(normalized(row['reference'])==normalized(golden['baseline_packet_reference']) and
             row['file_identity']==golden['baseline_file_identity'] and row['summary']['heavy_atoms']==golden['heavy_atoms'] and
             row['summary']['expected_conformers']==golden['expected_conformers'] and
             row['science_worker_seconds']==golden['observed_main_elapsed_seconds'],
             'ORIGINAL_SELECTED_METADATA_AND_MAIN_GOLDEN_BASELINE_DIFFERS')
    runtime=prep['main_preparation_runtime']
    need(runtime['uid']==1278 and runtime['job_id']==MAIN_PREP_JOB,'EXACT_ACTUAL_MAIN_PREPARATION_JOB_REQUIRED')
    main_startup=small(prep['root_preflight_reference'],sources)
    need(main_startup['uid']==1278 and str(main_startup['job_id'])==MAIN_PREP_JOB and main_startup['node']==runtime['node'] and
         main_startup['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1','HISTORICAL_MAIN_PREP_IDENTITY_REQUIRED_NOT_FRESH_ACCEPTANCE_PROOF')
    main_account=small(inputs['main_accounting'],sources)
    main_raw=read_small(source(main_account['raw_sacct_reference'],sources)).decode()
    main_cost=actual_parent(main_account,main_raw,MAIN_PREP_JOB,endpoint=MAIN_ENDPOINT,uid=1278,node=runtime['node'])
    submission=small(main_cost['actual_parent']['receipt_reference'],sources)
    need(str(submission['job_id'])==MAIN_PREP_JOB and submission['sbatch_returncode']==0,'ACTUAL_MAIN_PREP_SUBMISSION_REQUIRED')
    alpha=copied(inputs['alpha_receipt'],sources);deployment=copied(inputs['alpha_deployment_map'],sources,origin=alpha['deployment_map_reference'])
    alpha_startup=copied(inputs['alpha_startup_proof'],sources,origin=alpha['startup_proof_reference'])
    alpha_account=copied(inputs['alpha_accounting'],sources)
    alpha_raw_item=inputs['alpha_raw_sacct'];copied_raw=normalized(alpha_raw_item['main_copy_reference'])
    need(normalized(alpha_raw_item['origin_reference'])==normalized(alpha_account['raw_sacct_reference']) and
         ALPHA_ROOT in Path(alpha_raw_item['origin_reference']['path']).parents and
         all(alpha_raw_item['origin_reference'][k]==copied_raw[k] for k in ('bytes','sha256')),
         'EXACT_ALPHA_RAW_ACCOUNTING_COPY_REQUIRED')
    alpha_raw=read_small(source(copied_raw,sources)).decode()
    alpha_cost=actual_parent(alpha_account,alpha_raw,ALPHA_JOB,endpoint=ALPHA_ENDPOINT,uid=1264,node=ALPHA_NODE)
    target=deployment['target'];endpoint_id=sha(canonical(target))
    need(target['ssh_host']=='218.192.171.238' and target['ssh_user']=='alpha' and target['uid']==1264 and
         target['deployment_root']==str(ALPHA_ROOT) and deployment['endpoint_id']==prep['endpoint_id']==endpoint_id and
         alpha['endpoint_id']==alpha_startup['endpoint_id']==endpoint_id and alpha['uid']==alpha_startup['uid']==1264 and
         str(alpha['job_id'])==str(alpha_startup['job_id'])==ALPHA_JOB and alpha['node']==alpha_startup['node']==ALPHA_NODE and
         alpha_startup['schema']=='SECONDARY_PORTABLE_UFF_CONTROL16_STARTUP_V1','DO_NOT_MIX_MAIN_ALPHA_ENDPOINTS_JOBS_OR_UIDS')
    need(normalized(alpha_startup['deployment_map_reference'])==normalized(alpha['deployment_map_reference']),
         'ALPHA_STARTUP_DID_NOT_BIND_ACTUAL_EXECUTION_MAP')
    need(alpha['schema']=='SECONDARY_PORTABLE_UFF_CONTROL16_RECEIPT_V1' and alpha['mode']==deployment['mode']==CONTROL_MODE and
         alpha['status']=='CONTROL16_EXACT_SCIENCE_MATCH_REQUIRES_MAIN_SOFTWARE_ACCEPTANCE' and
         alpha['formal_generation_authorized'] is False and deployment['formal_generation_authorized'] is False and
         alpha['population_members_added']==0 and alpha['two_missing_replayed'] is False and
         alpha['current_main_recovery_2plus14_scope_changed'] is False and alpha['main_lmdb_or_once_ledger_opened'] is False and
         alpha['main_unified_acceptance_granted'] is False and alpha['automatic_retry'] is False and not alpha['errors'] and
         alpha['soft_memavailable_denial'] is False and alpha['actual_target_scientific_sources_verified_byte_identical'] is True,
         'ACTUAL_COMPLETE_BOUND_CONTROL16_ONLY_NO_FORMAL_POPULATION_AUTHORITY')
    need(normalized(deployment['main_preparation_origin_reference'])==normalized(inputs['main_preparation']) and
         normalized(alpha['main_preparation_reference'])==normalized(deployment['main_preparation_target_locator']) and
         all(alpha['main_preparation_reference'][key]==inputs['main_preparation'][key] for key in ('bytes','sha256')),
         'EXACT_MAIN_GOLDEN_PREPARATION_LINEAGE_REQUIRED')
    recipe=small(deployment['original_recipe_reference'],sources)
    need(deployment['original_recipe_reference']['bytes']==3629 and deployment['original_recipe_reference']['sha256']==
         'cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a','EXACT_ORIGINAL_RECIPE_REQUIRED')
    science_rows=deployment['science_sources'];names={'common.py','science.py','selection.py','statistics_tools.py','run_pilot.py','sprime_v6.py','prepare.py'}
    need(len(science_rows)==7 and {row['basename'] for row in science_rows}==names,'EXACT_SEVEN_ORIGINAL_SCIENCE_SOURCES_REQUIRED')
    for row in science_rows:
        source(row['origin_reference'],sources)
        need(all(row['origin_reference'][key]==row['target_locator'][key] for key in ('bytes','sha256')),
             'ORIGINAL_SEVEN_SCIENCE_SOURCE_BYTES_CHANGED')
    deployed_recipe=copied(inputs['alpha_deployed_recipe'],sources,origin=deployment['recipe_target_locator'])
    need(canonical(deployment['original_recipe_value'])==canonical(recipe),'ORIGINAL_RECIPE_VALUE_DIFFERS_FROM_PINNED_BYTES')
    recipe_check=recipe_equivalence(recipe,deployed_recipe,
        {row['origin_reference']['path']:row['target_locator'] for row in science_rows},ALPHA_ROOT/'outputs')
    fee_reference=normalized(inputs['fee_override']);source(fee_reference,sources)
    executions={row['molecule_id']:row for row in alpha['executions']}
    packet_rows={row['molecule_id']:row for row in inputs['packets']}
    need(len(executions)==len(alpha['executions'])==len(packet_rows)==len(inputs['packets'])==16 and
         set(executions)==set(packet_rows)==set(expected) and not set(expected)&MISSING_IDS,'EXACT16_OLD_CONTROLS_NO_MISSING_OR_DUPLICATE')
    need(len({(row['worker_identity']['pid'],row['worker_identity']['start_ticks']) for row in executions.values()})==16,
         'ACTUAL16_DISTINCT_ALPHA_WORKERS_REQUIRED')
    verified=[]
    for mid in prep['allowed_original_control_ids']:
        execution=executions[mid];golden=expected[mid];item=packet_rows[mid];identity=execution['worker_identity']
        need(identity['uid']==1264 and str(identity['job_id'])==ALPHA_JOB and identity['endpoint_id']==endpoint_id and
             execution['main_golden_exact_match'] is True and execution['task_sha256']==golden['task_sha256'] and
             execution['actual_versions']==VERSIONS,'ACTUAL_ALPHA_TASK_ENVIRONMENT_OR_WORKER_DIFFERS')
        need(normalized(item['origin_reference'])==normalized(execution['packet_reference']) and
             ALPHA_ROOT in Path(item['origin_reference']['path']).parents and
             all(item['origin_reference'][key]==item['main_copy_reference'][key] for key in ('bytes','sha256')),
             'SFTP_PACKET_SOURCE_AND_COPY_REFERENCE_DIFFERS')
        actual,copy_check=read_packet(item['main_copy_reference'],data_refs)
        baseline,baseline_check=read_packet(golden['baseline_packet_reference'],data_refs,expected_identity=golden['baseline_file_identity'])
        signature=scientific_sha(actual);baseline_signature=scientific_sha(baseline)
        need(signature==baseline_signature==execution['scientific_sha256_excluding_elapsed_seconds']==
             golden['scientific_sha256_excluding_elapsed_seconds'],'EXACT_FULL_SCIENTIFIC_PACKET_SHA_MISMATCH_NO_TOLERANCE')
        facts=packet_facts(actual,mid,golden);need(canonical(facts)==canonical(packet_facts(baseline,mid,golden)),
                                               'EXACT_SEED_GEOMETRY_NATIVE_PACKET_IDENTITY_DIFFERS')
        verified.append({'molecule_id':mid,'task_sha256':golden['task_sha256'],'scientific_sha256_excluding_elapsed_seconds':signature,
            'alpha_packet_origin_reference':normalized(item['origin_reference']),'alpha_main_copy_readback':copy_check,
            'original_main_baseline_readback':baseline_check,'seed_geometry_and_native_identity':facts})
    output=args.output.absolute();parent=RUN/'artifacts/conformers/secondary_uff_acceptance_v1'
    need(parent in output.parents and not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),
         'NEW_LITERAL_MAIN_ACCEPTANCE_OUTPUT_CHILD_REQUIRED')
    output.mkdir(parents=True,mode=0o700)
    report={'schema':'MAIN_SECONDARY_UFF_CURRENT_CONTROL16_SOFTWARE_ACCEPTANCE_V1',
        'status':'CURRENT_SOURCE_RECIPE_CONTROL16_EXACT_SOFTWARE_COMPATIBILITY_ACCEPTED_BY_MAIN_READBACK',
        'main_acceptance_job_id':str(proof['job_id']),'main_uid':1278,'main_node':proof['request']['node'],
        'inputs_reference':ref(args.inputs.absolute()),'main_preflight_reference':ref(args.root_preflight.absolute()),
        'accepted_scope':CONTROL_MODE,'endpoint_id':endpoint_id,'alpha_endpoint':ALPHA_ENDPOINT,'alpha_uid':1264,
        'alpha_job_id':ALPHA_JOB,'alpha_node':ALPHA_NODE,'actual_alpha_versions':VERSIONS,
        'original_recipe_reference':deployment['original_recipe_reference'],'original_seven_science_sources':science_rows,
        'actual_deployed_recipe_origin_and_main_copy':inputs['alpha_deployed_recipe'],'recipe_equivalence':recipe_check,
        'fixed_selection_rule_reverified':selection['selection_rule'],'eligible_existing_controls':selection['eligible_count'],
        'main_preparation_reference':normalized(inputs['main_preparation']),'alpha_receipt_origin_and_copy':inputs['alpha_receipt'],
        'complete_readback_controls':verified,'controls':16,'comparison_excludes_only':'summary.elapsed_seconds',
        'compressed_full_SHA_and_gzip_EOF_CRC_verified_per_copied_and_original_packet':True,
        'main_preparation_actual_parent_cost':main_cost,'alpha_control16_actual_parent_cost':alpha_cost,
        'this_main_readback_actual_terminal_cost':'PENDING_ROOT_TERMINAL_SACCT_INCLUDING_STARTUP_AND_FAILURES',
        'fee_override_reference_unchanged':fee_reference,'quality_gates_changed_or_waived':False,
        'population_members_added':0,'two_missing_replayed':False,'main_readback_UFF_QM_LMDB_calls':0,
        'main_production_once_ledger_accessed':False,'alpha_original_receipt_map_or_formal_flags_modified':False,
        'formal_generation_authorized':False,'all_molecules_programs_or_formal_data_claimed_passed':False,
        'new_offload_scope_requires_root_control_and_unchanged_scientific_quality_gates':True,
        'elapsed_readback_seconds':time.monotonic()-started}
    raw=canonical(report)+b'\n';need(len(raw)<=2<<20,'SMALL_ACCEPTANCE_REPORT_LIMIT')
    need(len(raw)+output.stat().st_size+65536<=proof['request']['estimated_peak_output_bytes'],'ACTUAL_READBACK_REPORT_OUTPUT_CAP_EXCEEDED')
    with (output/'acceptance.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'status':report['status'],'controls':16,'report':ref(output/'acceptance.json'),
                      'population_members_added':0,'formal_generation_authorized':False}))


if __name__=='__main__':main()
