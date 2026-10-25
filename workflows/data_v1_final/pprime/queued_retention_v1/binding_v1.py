"""Pure metadata boundaries for a strict queued retention preparation."""
from __future__ import annotations
import ast,datetime,re
OLD_CALL=b'observed=IO.runtime(prepare=True)'
NEW_CALL=b'observed=IO.runtime()'

def need(ok,message):
    if not ok:raise ValueError(message)

def prove_runtime_copy(original,variant):
    need(original.count(OLD_CALL)==1 and variant.count(NEW_CALL)==1,'UNIQUE_CPU_BINDING_EDIT_REQUIRED')
    need(original.replace(OLD_CALL,NEW_CALL)==variant,'NON_BINDING_SOURCE_EDIT_REJECTED')
    inverse=variant.replace(NEW_CALL,OLD_CALL)
    need(inverse==original,'INVERSE_FULL_FILE_BYTES_DIFFER')
    need(ast.dump(ast.parse(inverse),include_attributes=False)==ast.dump(ast.parse(original),include_attributes=False),'NORMALIZED_FULL_AST_DIFFERS')
    return {'declared_edit_count':1,'inverse_full_file_bytes_equal':True,'normalized_AST_identical':True,
        'retention_selection_source_audit_union_and_parquet_logic_unchanged':True}

def validate_start(plan,proof,env,node,uid,now):
    need(plan['schema']=='PPRIME_QUEUED_RETENTION_PREPARATION_PLAN_V1' and plan['expected_molecules']==1000
        and plan['expected_pairs']==2000 and plan['new_UFF_QM_calls']==0,'EXACT_ORIGINAL_INPUT_PREPARATION_REQUIRED')
    request=proof['request']
    need(uid==proof['uid']==1278 and node in plan['allowed_nodes'] and env.get('SLURM_JOB_ID','').isdecimal(),'ACTUAL_CPU_OWNER_AND_JOB_REQUIRED')
    need(env.get('SLURM_JOB_PARTITION')=='cpu' and int(env.get('SLURM_CPUS_PER_TASK','0'))==16
        and int(env.get('SLURM_MEM_PER_NODE','0'))>=64*1024,'ACTUAL16CPU64G_CPU_ALLOCATION_REQUIRED')
    need(env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'CPU_ONLY_ONE_THREAD_ENV_REQUIRED')
    need(request['kind']=='analysis' and request['pilot'] is True and request['node']==node and request['cpus']==16
        and request['memory_gib']==64 and request['wall_seconds']==plan['wall_seconds']
        and not request.get('resource_policy') and not request.get('memory_basis'),'STRICT_FRESH_ANALYSIS_REQUEST_REQUIRED')
    need(request['root_review']['status']=='APPROVED' and 0<=now-datetime.datetime.fromisoformat(proof['observed_at']).timestamp()<=3600,'FRESH_EXECUTION_ADMISSION_REQUIRED')
    for job in proof['existing_jobs_all_users']:
        values=re.findall(r'(?:^|\s)MinMemory(?:Node|CPU)=([^\s]+)',job['metadata'])
        need(len(values)==1 and not re.fullmatch(r'0[KMGTP]?',values[0]),'FOREIGN_UNBOUNDED_MEMORY_BLOCKS_PREPARATION')
    real=re.search(r'(?:^|\s)RealMemory=(\d+)(?:\s|$)',proof['node_metadata'])
    need(real and proof['committed_memory_mib']+64*1024<=.85*int(real[1]),'ALL_USER_DECLARED_MEMORY85_REQUIRED')
    need(proof['account_free_bytes']-plan['estimated_peak_output_bytes']>=plan['quota_reserve_bytes'],'WHOLE_RUN_QUOTA_RESERVE_REQUIRED')

def validate_closed(manifest,source_rows,union_rows,stable_rows,engine_rows,original20_ids,plan):
    need(manifest['schema']=='PPRIME_STABLE_RAW_RETENTION_EXECUTION_BINDING_V1' and manifest['status']=='PREPARED_NOT_QM_EXECUTED'
        and manifest['QM_started'] is False and manifest['scientific_input_or_numerics_changed'] is False
        and manifest['original_prepared_or_config_bytes_changed'] is False,'ACTUAL_NON_QM_PREPARATION_CLOSURE_REQUIRED')
    need(manifest['original_prepared']==plan['original_prepared'] and manifest['original_pairs']==plan['original_pairs']
        and manifest['audit_policy']==plan['config'],'EXACT_ORIGINAL_PAIRS_AND_POLICY_REQUIRED')
    by_id={r['record_id']:r for r in source_rows};old_ids=set(original20_ids)
    need(len(source_rows)==len(by_id)==2000 and len(old_ids)==manifest['original_frozen_audit_records']==20,'ORIGINAL2000_AND20_AUDITS_REQUIRED')
    need(all(r['geometry_source']=='uff_sprime' and r['physical_identity']['namespace']=='accepted_original_sprime'
        and type(r['physical_identity']['source_conformer_id']) is int and r['physical_identity']['source_conformer_id']>=0 for r in source_rows),'EXPLICIT_ORIGINAL_UFF_IDENTITIES_REQUIRED')
    source_old={r['record_id'] for r in source_rows if r['original_frozen_audit']}
    stable_ids={r['record_id'] for r in source_rows if r['selected']}
    union_ids={r['record_id'] for r in union_rows};engine_ids={r['record_id'] for r in engine_rows}
    need(source_old==old_ids and old_ids<=set(by_id) and stable_ids<=set(by_id),'SOURCE_AUDIT_SET_CHANGED')
    need(len(union_rows)==len(union_ids)==manifest['union_records'] and union_ids==old_ids|stable_ids,'EXACT_OLD20_UNION_STABLE_HITS_REQUIRED')
    need(len(stable_rows)==len({r['record_id'] for r in stable_rows})==manifest['stable_full_hits_count']
        and {r['record_id'] for r in stable_rows}==stable_ids,'ACTUAL_STABLE_HIT_SET_REQUIRED')
    need({r['record_id'] for r in source_rows if r['retain_all_twelve_raw']}==union_ids
        and manifest['required_full_raw_calls']==12*len(union_ids),'ALL_TWELVE_RAW_RETENTION_REQUIRED')
    need(len(engine_rows)==len(engine_ids)==len(union_rows) and engine_ids==union_ids,'ENGINE_PARQUET_READBACK_SET_REQUIRED')
    need(all(r['file_group']==by_id[r['record_id']]['legacy_engine_file_group']
        and r['size_stratum']==by_id[r['record_id']]['size_stratum'] for r in engine_rows),'ENGINE_GUARD_STRATA_MUST_NOT_REPLACE_SOURCE_SHARD')
    return {'original_pairs':2000,'source_rows':len(source_rows),'original_frozen_audit_records':len(old_ids),
        'stable_full_hits':len(stable_ids),'union_records':len(union_ids),'required_full_raw_calls':12*len(union_ids),
        'engine_parquet_independent_readback_records':len(engine_rows),'new_UFF_QM_calls':0}
