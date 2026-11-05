"""Draft resource-only replacement: CPU16, nodes11--19, Slurm memory omitted."""
from __future__ import annotations
import os,re,socket,time
from pathlib import Path
from .owned_costs import ROOT,COST_GATE,need,read,ref,verify,load_pin,normalized,owned_related_selection

HERE=ROOT/'repository/workflows/data_v1_final/conformers/recovery_auto_memory_v1'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
MODULE='workflows.data_v1_final.conformers.recovery_auto_memory_v1.run_recovery_auto'
SCOPE_KEY='sprime_recovery_auto_memory_2plus14'
PARAMETERS={'original_pilot_job':'4520364','expected_molecules':336,'reused_old_packages':334,
    'missing_original_tasks':2,'independent_same_seed_controls':14,'new_seeds':0,'new_logical_retries':0}
POLICY='SLURM_DEFAULT_UNSPECIFIED'
CACHE=None


def producer_argv(binding,binding_path,proof_path):
    return [PY,'-B','-m',MODULE,'--plan',binding['historical_plan_reference']['path'],
        '--approval',binding['historical_approval_reference']['path'],'--resource-binding',str(binding_path),
        '--root-preflight',str(proof_path),'--output',binding['output']]


def binding_metadata(binding,*,current_job_id=None,require_complete_now=False):
    """Real small metadata only; the original plan64 field remains historical."""
    need(binding.get('schema')=='SPRIME_AUTO_MEMORY_RECOVERY_RESOURCE_BINDING_V1' and
         binding.get('status')=='ROOT_APPROVED_FOR_EXACT_RECOVERY_RESOURCE_REPLACEMENT' and
         binding.get('reviewer')=='root' and binding.get('memory_policy')==POLICY and
         binding.get('slurm_memory_requested') is False and binding.get('historical64GiB_is_not_new_request') is True,
         'EXACT_NEW_RESOURCE_BINDING_REQUIRED')
    need('memory_gib' not in binding and binding['cpus']==16 and
         set(binding['allowed_nodes'])=={f'compute-0-{n}' for n in range(11,20)} and
         binding['scope_key']==SCOPE_KEY and binding['scope_parameters']==PARAMETERS,
         'EXACT_CPU16_11_TO19_NO_MEMORY_REQUEST_AND_SCIENCE_SCOPE_REQUIRED')
    plan=load_pin(binding['historical_plan_reference']);approval=load_pin(binding['historical_approval_reference'])
    need(plan['schema']=='SPRIME_MISSING_RECOVERY_PLAN_V1' and plan['status']=='ROOT_APPROVED_RECOVERY_EXECUTION' and
         plan['original_job_id']=='4520364' and plan['expected_original_molecules']==336 and
         plan['expected_missing_molecules']=={'principal_01112964':7,'principal_00509656':10} and
         plan['workers']==plan['cpus']==16 and plan['memory_gib']==64 and plan['replay_control_count']==14 and
         len(plan['replay_control_ids'])==len(set(plan['replay_control_ids']))==14 and
         plan['new_logical_retry_count']==0 and plan['scientific_recipe_changed'] is False and
         plan['formal_generation_authorized'] is False,'UNCHANGED_HISTORICAL_RECOVERY_PLAN_REQUIRED')
    need(approval['schema']=='SPRIME_MISSING_RECOVERY_USER_AND_ROOT_DECISION_V1' and
         approval['status']=='APPROVED_FOR_THIS_RECOVERY_ONLY' and
         approval['plan_reference']==normalized(binding['historical_plan_reference']) and
         approval['cost_ceiling_not_forecast']==plan['additional_allocated_core_seconds_cap'] and
         approval['original_336_approval_reused'] is False,'ORIGINAL_INDEPENDENT_SCIENCE_AND_BUDGET_APPROVAL_REQUIRED')
    need(type(binding['wall_seconds']) is int and 0<binding['wall_seconds']<=plan['wall_seconds']<=48*3600 and
         binding['historical_plan_wall_seconds']==plan['wall_seconds'] and
         type(plan['additional_allocated_core_seconds_cap']) is int and
         plan['additional_allocated_core_seconds_cap']>=16*plan['wall_seconds'] and
         plan['runtime_forecast']=='RIGHT_CENSORED_NO_DEFENSIBLE_POINT_ESTIMATE','FINITE_NEW_RESOURCE_WALL_WITHIN_HISTORICAL_BUDGET_NOT_FORECAST')
    reserves=binding.get('followup_requested_allocation_reserves')
    need(isinstance(reserves,list) and len(reserves)==2 and
         {row.get('stage') for row in reserves}=={'read_only_recovered_closure','readback_validation'} and
         all(row.get('cpus')==16 and type(row.get('wall_seconds')) is int and row['wall_seconds']>0 and
             row.get('requested_core_seconds')==16*row['wall_seconds'] for row in reserves),
         'EXPLICIT_FINITE_CLOSURE_AND_VALIDATION_ALLOCATION_RESERVES_REQUIRED')
    followup_reserve=sum(row['requested_core_seconds'] for row in reserves)
    need(binding['followup_requested_allocation_reserve_core_seconds']==followup_reserve and
         binding['future_allocation_reserves_are_not_actual_cost_or_runtime_forecasts'] is True,
         'FUTURE_RESERVES_MUST_NOT_MASQUERADE_AS_ACTUAL_COST_OR_FORECAST')
    authority=load_pin(binding['new_authority_reference'])
    need(authority.get('schema')=='USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1' and
         authority.get('status')=='USER_AUTHORIZED','ACTUAL_NEW_USER_CPU_AUTO_MEMORY_AUTHORITY_REQUIRED')
    replacement=load_pin(binding['pending_only_replacement_review_reference'])
    need(replacement.get('schema')=='SPRIME_PENDING_ONLY_RESOURCE_REPLACEMENT_ROOT_REVIEW_V1' and
         replacement.get('status')=='APPROVED_NO_PRIOR_PHYSICAL_EXECUTION' and replacement.get('reviewer')=='root' and
         replacement.get('historical_plan_reference')==normalized(binding['historical_plan_reference']) and
         replacement.get('historical_approval_reference')==normalized(binding['historical_approval_reference']) and
         replacement.get('no_prior_worker_execution_verified') is True and
         replacement.get('no_recovery_output_directory_verified') is True,
         'ACTUAL_PENDING_ONLY_REPLACEMENT_AUDIT_REQUIRED')
    evidence=replacement.get('evidence_references')
    need(isinstance(evidence,list) and evidence,'ACTUAL_REPLACEMENT_STATUS_AND_OUTPUT_AUDIT_PINS_REQUIRED')
    for pin in evidence:verify(pin)
    selection=owned_related_selection(binding['whole_owned_accounting_reference'],current_job_id=current_job_id,
        require_complete_now=require_complete_now,classification_ref=binding.get('legacy_scope_classification_reference'))
    need(not selection['unclassified_scope_parent_ids_for_root_review'],'ALL_CURRENT_OWNED_SCOPES_MUST_BE_EXPLICIT')
    rows={row['job_id']:row for row in selection['selected_parent_rows']}
    need(all(row['state'] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}
             for row in rows.values()),'EVERY_PRIOR_RELATED_PARENT_MUST_BE_ACTUALLY_TERMINAL')
    need(rows['4520364']['state']=='TIMEOUT' and rows['4520364']['allocated_core_seconds']==230800 and
         rows['4520527']['state']=='COMPLETED' and rows['4520527']['exit_code']=='0:0','ORIGINAL_TIMEOUT_AND_PARTIAL_AUDIT_COST_FACTS_REQUIRED')
    preparation=rows.get('4520335')
    need(preparation is not None and preparation['alloc_cpus']==16 and preparation['elapsed_raw_seconds']==606 and
         preparation['allocated_core_seconds']==9696,'ACTUAL_ORIGINAL_SPRIME_PREPARATION_COST_MUST_BE_INCLUDED')
    replaced=replacement.get('replaced_parent_job_ids')
    need(isinstance(replaced,list) and replaced and len(replaced)==len(set(replaced)) and
         all(isinstance(jid,str) and jid.isdecimal() and jid in rows and rows[jid]['state']=='CANCELLED' and
             rows[jid]['elapsed_raw_seconds']==rows[jid]['allocated_core_seconds']==0 for jid in replaced),
         'REPLACED_RECOVERY_MUST_BE_REAL_CANCELLED_ZERO_ELAPSED_PARENT_NOT_EXECUTED_RETRY')
    total=sum(row['allocated_core_seconds'] for row in rows.values())
    need(selection['related_parent_ids']==binding['prior_related_actual_parent_ids'] and
         selection['selected_parent_rows']==binding['prior_related_actual_parent_rows'] and
         total==binding['prior_related_actual_core_seconds'] and
         total+binding['wall_seconds']*16+followup_reserve<=COST_GATE,
         'COMPLETE_ACTUAL_COST_PLUS_NEW_CEILING_AND_FOLLOWUP_RESERVES_MUST_FIT_ORIGINAL96H')
    need(binding.get('formal_generation_authorized') is False and binding.get('new_seeds')==0 and
         binding.get('new_logical_retries')==0 and binding.get('original_32GiB_exception_reused') is False,
         'NO_NEW_SCIENTIFIC_AUTHORITY_SEED_OR_LOGICAL_RETRY')
    need(binding['soft_owned_rss_stop_bytes']==24<<30 and type(binding['soft_min_mem_available_bytes']) is int and
         0<=binding['soft_min_mem_available_bytes']<=8<<30,'EXPLICIT_ALGORITHM_SOFT_GUARDS_NOT_SLURM_RESERVATIONS')
    return {'plan':plan,'approval':approval,'selection':selection,'prior_actual_core_seconds':total,'replacement':replacement}


def generation_admit(plan_path,value,proof_path,approval_path,*,resource_binding_path,output):
    global CACHE
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
    binding_ref=ref(Path(resource_binding_path).absolute());binding=load_pin(binding_ref)
    need(normalized(binding['historical_plan_reference'])==ref(Path(plan_path).absolute()) and
         normalized(binding['historical_approval_reference'])==ref(Path(approval_path).absolute()) and
         str(Path(output).absolute())==binding['output'],'EXACT_ORIGINAL_PLAN_APPROVAL_AND_NEW_OUTPUT_ARGUMENTS_REQUIRED')
    required=[binding_ref,binding['historical_plan_reference'],binding['historical_approval_reference'],
        binding['new_authority_reference'],binding['pending_only_replacement_review_reference'],binding['whole_owned_accounting_reference']]
    if binding.get('legacy_scope_classification_reference') is not None:required.append(binding['legacy_scope_classification_reference'])
    proof=central.require_startup(proof_path,expected_scope_key=SCOPE_KEY,expected_scope_parameters=PARAMETERS,
        expected_execution_argv=producer_argv(binding,Path(resource_binding_path).absolute(),Path(proof_path).absolute()),
        expected_source=HERE/'run_recovery_auto.py',expected_kind='conformer',required_references=tuple(required))
    request=proof['request']
    need(request.get('memory_policy')==POLICY and 'memory_gib' not in request and
         request['queue_authority_reference']==normalized(binding['new_authority_reference']) and
         request['cpus']==16 and request['wall_seconds']==binding['wall_seconds']<=value['wall_seconds'] and
         request['node'] in {f'compute-0-{n}' for n in range(11,20)},'ACTUAL_CPU16_11_TO19_MEMORY_UNSPECIFIED_REQUEST_REQUIRED')
    need(os.getuid()==1278 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and
         os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('CUDA_VISIBLE_DEVICES')=='' and
         int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16 and socket.gethostname().split('.')[0]==request['node'],
         'ACTUAL_CPU16_JOB_NODE_OWNER_AND_NO_GPU_REQUIRED')
    need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
         'ONE_LIBRARY_THREAD_PER_WORKER_REQUIRED')
    checked=binding_metadata(binding,current_job_id=str(proof['job_id']))
    need(checked['plan']==value and value['recipe_config'] in request['source_references'] and
         request['estimated_peak_output_bytes']>=value['max_output_bytes']+value['closure_max_output_bytes']+(64<<20) and
         proof['account_free_bytes']-request['estimated_peak_output_bytes']>=value['quota_reserve_bytes']==200000000000,
         'EXACT_RECIPE_PLAN_WHOLE_OUTPUT_AND200GB_RESERVE_REQUIRED')
    from recovery_common import require_sources
    require_sources(request['source_references'])
    refs={pin['path']:normalized(pin) for pin in request['source_references']}
    for path in HERE.glob('*.py'):
        need(refs.get(str(path))==ref(path),'ACTUAL_NEW_ADAPTER_SOURCE_NOT_PINNED:'+path.name)
    declaration=HERE/'source_edits_v1.json'
    need(refs.get(str(declaration))==ref(declaration),'ACTUAL_NEW_SOURCE_DELTA_NOT_PINNED')
    raw=proof['job_metadata'];runtimes=re.findall(r'(?:^|\s)RunTime=([^\s]+)',raw) if isinstance(raw,str) else [raw['RunTime']]
    need(len(runtimes)==1,'REAL_STARTUP_SLURM_RUNTIME_REQUIRED')
    parts=list(map(int,runtimes[0].split(':')))
    need(len(parts)==3 and all(v>=0 for v in parts) and parts[1]<60 and parts[2]<60,'FINITE_STARTUP_RUNTIME_OBSERVATION')
    CACHE={'proof':proof,'binding':binding,'binding_reference':binding_ref,'selection':checked['selection'],
        'prior_actual_core_seconds':checked['prior_actual_core_seconds'],'started':time.monotonic(),
        'startup_runtime_floor_seconds':parts[0]*3600+parts[1]*60+parts[2]}
    runtime={'job_id':str(proof['job_id']),'hostname':request['node'],'allocated_cpus':16,'workers':16,
        'memory_policy':POLICY,'slurm_memory_requested':False,'resource_binding_reference':binding_ref}
    return runtime,proof


def related_cost_lower_bound(proof):
    need(CACHE is not None and proof==CACHE['proof'],'OWN_AUTO_MEMORY_RECOVERY_PROOF_REQUIRED')
    return CACHE['prior_actual_core_seconds']+16*(CACHE['startup_runtime_floor_seconds']+max(0,time.monotonic()-CACHE['started']))


class RecoverySampler:
    """Reuse stable owned-process measurements; discard old32G/85 admission flags."""
    def __init__(self,job,proof):
        need(CACHE is not None and proof==CACHE['proof'],'OWN_AUTO_MEMORY_RECOVERY_PROOF_REQUIRED')
        from live_memory_policy_32g_v1 import ProcSampler,parse_meminfo
        actual=parse_meminfo(Path('/proc/meminfo').read_text())
        self.old=ProcSampler(job,actual['MemTotal']) # observed physical total, never a memory allocation claim
        self.soft_rss=CACHE['binding']['soft_owned_rss_stop_bytes']
        self.available_floor=CACHE['binding']['soft_min_mem_available_bytes']
    def __call__(self):
        try:
            old=self.old()
            row={k:old[k] for k in ('node_used_bytes','mem_total_bytes','mem_available_bytes','capacity_bytes',
                'owned_rss_bytes','observed_epoch','observed_monotonic','sample_seconds','processes')}
            row.update(memory_basis='SLURM_DEFAULT_UNSPECIFIED_SOFT_RSS_AND_MEMAVAILABLE',slurm_memory_requested=False,
                legacy_sampler_admission_flags_discarded=True,declared_memory_admission_applied=False,
                soft_owned_rss_stop_bytes=self.soft_rss,soft_min_mem_available_bytes=self.available_floor,
                dispatch_allowed=row['owned_rss_bytes']<self.soft_rss and row['mem_available_bytes']>=self.available_floor)
            return row
        except Exception as exc:
            return {'dispatch_allowed':False,'observed_epoch':time.time(),'observed_monotonic':time.monotonic(),
                'metric_invalid':True,'memory_basis':'SLURM_DEFAULT_UNSPECIFIED_SOFT_RSS_AND_MEMAVAILABLE','error':repr(exc)}


def memory_evidence_metadata(monitor):
    need(CACHE is not None,'ACTUAL_AUTO_MEMORY_RECOVERY_STARTUP_REQUIRED')
    return {'samples':monitor.samples,'first_denial':monitor.first_denial,'memory_policy':POLICY,
        'slurm_memory_requested':False,'legacy32G_policy_approval_reused':False,'declared_memory_admission_applied':False,
        'soft_owned_rss_stop_bytes':CACHE['binding']['soft_owned_rss_stop_bytes'],
        'soft_min_mem_available_bytes':CACHE['binding']['soft_min_mem_available_bytes'],
        'resource_binding_reference':CACHE['binding_reference'],'prior_related_actual_core_seconds':CACHE['prior_actual_core_seconds'],
        'prior_related_actual_parent_rows':CACHE['selection']['selected_parent_rows'],
        'own_actual_parent_cost':'PENDING_ROOT_REAL_TERMINAL_SACCT','signals_sent':False}
