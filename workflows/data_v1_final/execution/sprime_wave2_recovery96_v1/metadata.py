"""Root-approved96 metadata only; original run/close scientific code is reused."""
import argparse,copy,json,pathlib,re
from . import contract as K
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F

HERE=pathlib.Path(__file__).absolute().parent
FILES=('contract.py','metadata.py','test_contract.py','README.md')
CLOSER=G.REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_close_index_v2'


def selected(value,path):
    F.need(type(path) is list and all(type(k) is str for k in path),'EXPLICIT_SMALL_REPORT_KEY_SELECTOR_REQUIRED')
    for key in path:value=value[key]
    return value


def add_account(refs,reference,required,c0=()):
    F.need(G.meta_pin(reference['path'])==reference,'CURRENT_ACTUAL_ACCOUNTING_REFERENCE')
    ar,av,rows=G.account(pathlib.Path(reference['path']),required,c0=c0);G.add_account(refs,ar,av);return rows


def inputs(args):
    decision_ref,decision=G.metadata(args.decision,'ROOT_EXPLICIT_SPRIME96_UNSTARTED_CONTINUATION_DECISION_V1')
    F.need(args.root_approve_exact_stage and args.root_reason.strip() and decision['reviewer']=='root'
      and decision['status']=='APPROVED_EXACT_OLD500_UNSTARTED_NEW_ATTEMPT'
      and decision['batch_id']==K.BID and decision['automatic_retry'] is False
      and decision['once_ledger_keys_removed_or_changed'] is False
      and decision['original_scientific_recipe_taskkeys_seeds_unchanged'] is True,
      'ROOT_EXPLICIT_SINGLE_NEW_ATTEMPT_NOT_AUTOMATIC_RETRY')
    hold=G.metadata(decision['original_HOLD_reference']['path'])[1]
    F.need(G.meta_pin(decision['original_HOLD_reference']['path'])==decision['original_HOLD_reference']
      and hold['status']=='HOLD_ROOT_REVIEW_REQUIRED_NO_NEW_DISPATCH'
      and hold['stages'][K.BID]['run']['job_id']==K.FAILED_RUN
      and hold['stages'][K.BID]['close']['job_id']==K.OLD_CLOSE,'ACTUAL_ORIGINAL96_HOLD_HISTORY')
    original=G.metadata(decision['original_closed_reference']['path'])[1]
    F.need(G.meta_pin(decision['original_closed_reference']['path'])==decision['original_closed_reference']
      and hold['stages'][K.BID]['close']['report_reference']==decision['original_closed_reference'],
      'EXACT_OLD_ZERO_PACKET_CLOSE_PIN')
    plan_ref=original['plan'];header_ref=original['prepared'];plan=G.metadata(plan_ref['path'])[1];header=G.metadata(header_ref['path'])[1]
    F.need(G.meta_pin(plan_ref['path'])==plan_ref and G.meta_pin(header_ref['path'])==header_ref,'CURRENT_ORIGINAL_PLAN_PREPARED')
    K.zero_consumption(original,header,plan_ref)
    spec_ref=hold['stages'][K.BID]['run']['actual_registered_references']['stage_spec_reference']
    F.need(G.meta_pin(spec_ref['path'])==spec_ref,'ORIGINAL96_STAGE_SPEC_PIN')
    refs=G.References(G.load(spec_ref['path']));refs.add(spec_ref);G.original_sources(refs)
    for name in FILES:refs.small(HERE/name)
    for name in ('__init__.py','admission.py','run.py','test_admission.py','README.md'):refs.small(CLOSER/name)
    for ref in (decision_ref,decision['original_HOLD_reference'],decision['original_closed_reference'],plan_ref,header_ref):refs.add(ref)
    failed=add_account(refs,original['accounting'],[K.FAILED_RUN])[K.FAILED_RUN]
    F.need(failed['state']=='FAILED' and failed['exit_code']=='1:0' and int(failed['alloc_cpus'])==16,'OLD_FAILED96_COST_RETAINED')
    add_account(refs,decision['original_close_accounting_reference'],[K.OLD_CLOSE],c0=[K.OLD_CLOSE])
    add_account(refs,decision['original_prepare_accounting_reference'],[K.PREPARE],c0=[K.PREPARE])
    probe_ref=decision['probe_report_reference'];probe=G.metadata(probe_ref['path'])[1]
    F.need(G.meta_pin(probe_ref['path'])==probe_ref,'ACTUAL_PROBE_REPORT_PIN')
    report=selected(probe,decision['probe_budget_report_selector'])
    F.need(report['stop_new_dispatch'] is None and report['observation_failure'] is None
      and report['signals_sent_to_science'] is False and report['natural_drain'] is True
      and report['whole_wave_output_reserved_bytes']==G.WAVE_RESERVE and report['publisher_reserved_bytes']==64<<20
      and report['actual_quota_observations'] and report['actual_memory_observations'],
      'ACTUAL_UNRELAXED_FIRST_BUDGET_REPORT_REQUIRED_NOT_HISTORICAL_CAUSE_INFERENCE')
    probe_proof_ref=decision['probe_startup_proof_reference'];proof=G.metadata(probe_proof_ref['path'])[1]
    F.need(G.meta_pin(probe_proof_ref['path'])==probe_proof_ref and proof['uid']==1278
      and proof['request']['node']=='compute-0-13' and proof['request']['cpus']==16
      and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_CPU13_PROBE_IDENTITY')
    add_account(refs,decision['probe_accounting_reference'],[str(proof['job_id'])],c0=[str(proof['job_id'])])
    F.need(G.meta_pin(proof['request_reference']['path'])==proof['request_reference']
      and G.load(proof['request_reference']['path'])==proof['request'],'ACTUAL_PROBE_REQUEST_BINDING')
    # Root states the exact location of its small report; no inferred selector,
    # alternate field fallback or historical first-failure explanation is used.
    F.need(selected(probe,decision['probe_job_id_selector'])==str(proof['job_id'])
      and selected(probe,decision['probe_new_science_calls_selector'])==0,'EXACT_ZERO_SCIENCE_PROBE_JOB_AND_CALL_COUNT')
    for ref in (probe_ref,probe_proof_ref,proof['request_reference']):refs.add(ref)
    storage=decision['storage_review_reference'];F.need(G.meta_pin(storage['path'])==storage,'ACTUAL_ROOT_STORAGE_REVIEW_PIN');refs.add(storage)
    review_ref,review=G.metadata(args.wave_review,F.SCHEMAS['wave_review'])
    F.need(G.meta_pin(review_ref['path'])==review_ref,'ACTUAL_INDEPENDENT_NEW96_WAVE_REVIEW');refs.add(review_ref)
    F.approve_wave(plan['draft'],F.read(plan['draft']),review_ref,header['config'])
    F.need(review['unstarted_continuation_decision_reference']==decision_ref
      and review['storage_review_reference']==storage,'REPLACEMENT_WAVE_EXPLICITLY_BINDS_OLD_FAILURE_AND_STORAGE_DECISION')
    for field in ('terminal_outcomes','unstarted_metas'):refs.add(original[field],data=True)
    refs.add(header['tasks'],data=True)
    return decision_ref,decision,refs,plan_ref,plan,header_ref,header,review_ref,review,report


def exact_stage(out,refs,stage,config_ref,argv,parents,args):
    authority=F.sources()['resource_authority'];cost=F.sources()['cost_authority'];refs.add(cost)
    parents=list({r['path']:F.triple(r) for r in [*parents,cost]}.values())
    for ref in parents:refs.add(ref)
    pilot_ref=refs.small(G.ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json')
    wall=28800 if stage=='run' else 7200;mode='FULL_SOURCE_AFTER_PROFILE' if stage=='run' else 'BOUNDED_METADATA_PREPARATION'
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'resource_authority_reference':authority,'kind':'conformer' if stage=='run' else 'analysis',
      'scope_key':'sprime_formal_cpu_auto_v3_'+stage,'scope_parameters':F.scope(stage,config_ref),'pilot':False,
      'wall_seconds':wall,'estimated_peak_output_bytes':F.CAP,'stage_output_cap_bytes':F.CAP,'execution_argv':argv,
      'scope_mode':mode,'parent_evidence_references':parents,'root_review_reason':args.root_reason,
      'scientific_quality_thresholds_unchanged':True,'full_forecast_status':F.FORECAST,'estimated_full_core_hours':None,
      'no_scientific_data_read_or_hashed_on_login':True,'provider_launched_or_renewed':False,'automatic_retry':False,
      'old_failed96_history_and_cost_retained':True,'single96_requested_science_ceiling_core_seconds':16*28800,
      'request_ceiling_is_not_forecast_or_actual_cost_guarantee':True}
    if stage=='run':review.update(profile_reviewed=True,approved_profile_reference=pilot_ref)
    rr=G.write_new(out/'scope_review.json',review);refs.add(rr);refs.validate_small_sources()
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv')}
    spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
      source_references=list(refs.sources.values()),data_references=list(refs.data.values()),
      scope={'mode':mode,'review':rr,'parent_profile':pilot_ref if stage=='run' else None})
    result=G.write_new(out/'stage_spec.json',spec)
    print(json.dumps({'stage_spec':result,'stage':stage,'scientific_body_reads':0,'jobs_submitted':0,'old_once_keys_changed':0}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('run','close'))
    p.add_argument('--decision',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--wave-review',type=pathlib.Path,required=True)
    p.add_argument('--root-approve-exact-stage',action='store_true');p.add_argument('--root-reason',required=True)
    for key in ('continuation-bundle','request','submission','accounting'):p.add_argument('--'+key,type=pathlib.Path)
    a=p.parse_args();G.on_login();F.need(HERE==G.REPO/'workflows/data_v1_final/execution/sprime_wave2_recovery96_v1','ACTUAL_ROOT_METADATA_HELPER')
    out=a.output;F.need(out.is_absolute() and G.ROOT/'control' in out.parents and not out.exists()
      and '..' not in out.parts and not any(q.is_symlink() for q in (out,*out.parents)),'FRESH_CONTROL_METADATA_DIRECTORY')
    dr,d,refs,pr,plan,hr,header,wr,wave,probe=inputs(a);out.mkdir(parents=True,mode=0o700)
    if a.mode=='run':
        derived=K.derive_plan(plan,pr,wr,wave,dr);new_plan=G.write_new(out/'derived_plan.json',derived)
        new_header=G.write_new(out/'derived_prepared.json',K.derive_prepared(header,hr,new_plan,dr));slot=derived['jobs'][0]
        bundle=G.write_new(out/'continuation_bundle.json',{'schema':'SPRIME96_ORIGINAL500_CONTINUATION_METADATA_V1',
          'decision_reference':dr,'origin_plan_reference':pr,'origin_prepared_reference':hr,'plan_reference':new_plan,
          'prepared_reference':new_header,'replacement_wave_review_reference':wr,'slot':slot,
          'science_primary_reference':G.meta_pin(G.FORMAL/'run_batch.py'),'old_tasks_reference_unchanged':header['tasks'],
          'new_task_keys_or_seeds':False,'new_CPU_freeze_or_prepare_claimed':False,'jobs_submitted':0})
        refs.add(new_plan);refs.add(new_header);refs.add(bundle)
        argv=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',header['config']['path'],'--prepared',new_header['path'],
          '--root-preflight',G.PROOF_PLACEHOLDER,'--quota-reuse-review',V.fixed_inputs()[0]['quota_reuse_review_reference']['path'],
          '--output',slot['output_root']]
        parents=[dr,pr,hr,wr,new_plan,new_header,bundle,d['probe_report_reference'],d['probe_accounting_reference'],d['storage_review_reference']]
    else:
        F.need(a.continuation_bundle and a.request and a.submission and a.accounting,'ACTUAL_NEW_RUN_REGISTRATION_AND_ACCOUNTING_REQUIRED')
        br,b=G.metadata(a.continuation_bundle,'SPRIME96_ORIGINAL500_CONTINUATION_METADATA_V1')
        F.need(b['decision_reference']==dr and b['origin_plan_reference']==pr and b['origin_prepared_reference']==hr,'SAME_ROOT_CONTINUATION_BUNDLE')
        new_plan=b['plan_reference'];new_header=b['prepared_reference'];slot=b['slot']
        F.need(G.meta_pin(new_plan['path'])==new_plan and G.meta_pin(new_header['path'])==new_header,'ACTUAL_DERIVED_INPUT_PINS')
        F.need(G.load(new_plan['path'])==K.derive_plan(plan,pr,wr,wave,dr)
          and G.load(new_header['path'])==K.derive_prepared(header,hr,new_plan,dr) and slot==wave['jobs'][0],
          'ALL_DERIVED_METADATA_AND_SINGLE_SLOT_MATCH_THE_REVIEWED_INVERSE_DELTA')
        rq,request=G.metadata(a.request);sr,sub=G.metadata(a.submission,'CPU_AUTO_MEMORY_SUBMISSION_V1')
        F.need(sub['request_reference']==rq and sub['request']==request and sub['sbatch_returncode']==0 and sub['uid']==1278
          and request['job_name']==slot['job_name'],'EXACT_ACTUAL_NEW_RUN_REQUEST_SUBMISSION')
        ar,av,parents_actual=G.account(a.accounting,[sub['job_id']]);G.add_account(refs,ar,av)
        expected=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',header['config']['path'],'--prepared',new_header['path'],
          '--root-preflight',request['startup_proof_path'],'--quota-reuse-review',V.fixed_inputs()[0]['quota_reuse_review_reference']['path'],'--output',slot['output_root']]
        F.need(request['execution_argv']==expected and request['scope_key']=='sprime_formal_cpu_auto_v3_run'
          and request['scope_parameters']==F.scope('run',header['config']),'EXACT_OLD_UNMODIFIED_RUN_PRIMARY_AND_ALL_OPTIONS')
        descriptor=G.write_new(out/'descriptor.json',{'plan':new_plan,'prepared':new_header,'request':rq,'submission':sr,'accounting':ar})
        for ref in (br,new_plan,new_header,rq,sr,descriptor):refs.add(ref)
        close_name=d['replacement_closed_directory_name']
        F.need(type(close_name) is str and re.fullmatch('[a-z][a-z0-9_]{1,127}',close_name),'SAFE_LITERAL_NEW_CLOSED_DIRECTORY_NAME')
        output=pathlib.Path(slot['output_root']).parent/close_name
        F.need(output not in {pathlib.Path(d['original_closed_reference']['path']).parent,pathlib.Path(slot['output_root'])},
          'DISTINCT_REPLACEMENT_CLOSE_OUTPUT')
        argv=[G.PY,'-B',str(CLOSER/'run.py'),'close','--config',header['config']['path'],'--root-preflight',G.PROOF_PLACEHOLDER,
          '--quota-reuse-review',V.fixed_inputs()[0]['quota_reuse_review_reference']['path'],'--descriptor',descriptor['path'],'--output',str(output)]
        parents=[dr,pr,hr,wr,br,new_plan,new_header,rq,sr,ar,descriptor,d['storage_review_reference']]
    exact_stage(out,refs,a.mode,header['config'],argv,parents,a)


if __name__=='__main__':main()
