"""Draft metadata-only binding, after real pending-only replacement and accounting audits."""
from __future__ import annotations
import argparse,json,os,socket
from pathlib import Path
from .owned_costs import ROOT,need,ref,read,verify,load_pin,normalized,owned_related_selection
from .resource_runtime import HERE,POLICY,SCOPE_KEY,PARAMETERS,binding_metadata,producer_argv


def write_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'BOUNDED_NEW_METADATA_OUTPUT')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('historical-plan','historical-approval','new-authority','pending-only-replacement-review',
                 'whole-owned-accounting','output-directory','artifacts-output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--legacy-scope-classification',type=Path)
    parser.add_argument('--wall-seconds',type=int,required=True)
    parser.add_argument('--closure-wall-reserve-seconds',type=int,required=True)
    parser.add_argument('--validation-wall-reserve-seconds',type=int,required=True)
    parser.add_argument('--soft-min-mem-available-bytes',type=int,default=2<<30)
    parser.add_argument('--reviewer',required=True)
    a=parser.parse_args()
    need(os.name=='posix' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and
         a.reviewer=='root' and Path(__file__).absolute()==HERE/'materialize_binding.py','ROOT_INTEGRATED_METADATA_PREPARATION_REQUIRED')
    pins={key:ref(path.absolute()) for key,path in (
        ('historical_plan_reference',a.historical_plan),('historical_approval_reference',a.historical_approval),
        ('new_authority_reference',a.new_authority),('pending_only_replacement_review_reference',a.pending_only_replacement_review),
        ('whole_owned_accounting_reference',a.whole_owned_accounting))}
    if a.legacy_scope_classification is not None:pins['legacy_scope_classification_reference']=ref(a.legacy_scope_classification.absolute())
    plan=load_pin(pins['historical_plan_reference'])
    selection=owned_related_selection(pins['whole_owned_accounting_reference'],require_complete_now=True,
        classification_ref=pins.get('legacy_scope_classification_reference'))
    need(not selection['unclassified_scope_parent_ids_for_root_review'],'ALL_ACTUAL_OWNED_SCOPES_MUST_BE_REVIEWED_BEFORE_REPLACEMENT')
    out=a.output_directory.absolute();output=a.artifacts_output.absolute();root=Path(plan['external_output_root'])
    need((ROOT/'control') in out.parents and not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),
         'NEW_LITERAL_CONTROL_CHILD_REQUIRED')
    need(root in output.parents and not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),
         'NEW_LITERAL_RECOVERY_OUTPUT_CHILD_REQUIRED')
    binding={'schema':'SPRIME_AUTO_MEMORY_RECOVERY_RESOURCE_BINDING_V1',
        'status':'ROOT_APPROVED_FOR_EXACT_RECOVERY_RESOURCE_REPLACEMENT','reviewer':'root',**pins,
        'memory_policy':POLICY,'slurm_memory_requested':False,'historical64GiB_is_not_new_request':True,
        'cpus':16,'allowed_nodes':[f'compute-0-{n}' for n in range(11,20)],'wall_seconds':a.wall_seconds,
        'historical_plan_wall_seconds':plan['wall_seconds'],
        'followup_requested_allocation_reserves':[
            {'stage':'read_only_recovered_closure','cpus':16,'wall_seconds':a.closure_wall_reserve_seconds,'requested_core_seconds':16*a.closure_wall_reserve_seconds},
            {'stage':'readback_validation','cpus':16,'wall_seconds':a.validation_wall_reserve_seconds,'requested_core_seconds':16*a.validation_wall_reserve_seconds}],
        'followup_requested_allocation_reserve_core_seconds':16*(a.closure_wall_reserve_seconds+a.validation_wall_reserve_seconds),
        'future_allocation_reserves_are_not_actual_cost_or_runtime_forecasts':True,
        'scope_key':SCOPE_KEY,'scope_parameters':PARAMETERS,'output':str(output),
        'prior_related_actual_parent_ids':selection['related_parent_ids'],
        'prior_related_actual_core_seconds':sum(row['allocated_core_seconds'] for row in selection['selected_parent_rows']),
        'prior_related_actual_parent_rows':selection['selected_parent_rows'],'related_parent_selection':selection,
        'soft_owned_rss_stop_bytes':24<<30,'soft_min_mem_available_bytes':a.soft_min_mem_available_bytes,
        'original_32GiB_exception_reused':False,'new_seeds':0,'new_logical_retries':0,'scientific_recipe_changed':False,
        'formal_generation_authorized':False,'all_related_final_actual_cost_accepted':False,
        'explanation':'The original plan64 and approval remain immutable historical science/budget evidence. '
            'The actual replacement request omits all Slurm memory options under the new user authority. '
            '24GiB is only an owned-process RSS soft dispatch guard, not reserved or allocated memory. '
            'Current parent actual cost remains pending its real terminal sacct; no runtime forecast is invented.'}
    checked=binding_metadata(binding,require_complete_now=True)
    sources={};data={}
    def source(pin):
        pin=normalized(pin);verify(pin);need(pin['path'] not in sources or sources[pin['path']]==pin,'SOURCE_PIN_CONFLICT')
        sources[pin['path']]=pin
    def locator(pin):
        pin=normalized(pin);need(pin['path'] not in data or data[pin['path']]==pin,'DATA_LOCATOR_CONFLICT');data[pin['path']]=pin
    for pin in pins.values():source(pin)
    source(selection['owned_raw_sacct_reference'])
    for pin in [*selection['all_snapshot_receipt_references'],*selection['known_rejected_related_submission_references'],
                *selection['legacy_scope_evidence_references'],*checked['replacement']['evidence_references']]:source(pin)
    for key in ('partial_audit_report','partial_audit_monitor_closure','recipe_config'):source(plan[key])
    recipe=load_pin(plan['recipe_config'])
    for pin in recipe['science_source_pins']:source(pin)
    repo=ROOT/'repository'
    for rel in plan['required_additional_source_relative_paths']:source(ref(repo/rel))
    for directory in (repo/'workflows/data_v1_final/conformers/recovery_v1',HERE,
                      repo/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2'):
        need(directory.is_dir(),'ACTUAL_INTEGRATED_ADAPTER_AND_CENTRAL_SOURCES_REQUIRED')
        for path in directory.glob('*.py'):source(ref(path))
    source(ref(HERE/'source_edits_v1.json'))
    audit=load_pin(plan['partial_audit_report'])
    complete=next(pin for pin in audit['outputs'] if Path(pin['path']).name=='complete_packages.json')
    for pin in audit['outputs']:source(pin)
    source(audit['prepared_reference'])
    closed=load_pin(complete);need(len(closed)==334,'REAL334_OLD_PACKAGE_LOCATORS_REQUIRED')
    for row in closed:locator(row['reference'])
    locator(plan['tasks_reference'])
    out.mkdir(parents=True,mode=0o700)
    binding_path=out/'resource_binding.json';write_new(binding_path,binding);source(ref(binding_path))
    manifest={'schema':'SPRIME_AUTO_MEMORY_RECOVERY_EXECUTION_MANIFEST_DRAFT_V1',
        'status':'REQUIRES_ROOT_NEW_CENTRAL_STAGE_SPEC_AND_SCOPE_REVIEW_NOT_SUBMITTED',
        'kind':'conformer','pilot':True,'cpus':16,'memory_policy':POLICY,'wall_seconds':a.wall_seconds,
        'scope_key':SCOPE_KEY,'scope_parameters':PARAMETERS,
        'estimated_peak_output_bytes':plan['max_output_bytes']+plan['closure_max_output_bytes']+(64<<20),
        'execution_argv':producer_argv(binding,binding_path,'__ROOT_STARTUP_PROOF__'),
        'source_references':list(sources.values()),'data_references':list(data.values()),
        'resource_binding_reference':ref(binding_path),'prefer_node':'compute-0-17','allowed_nodes':binding['allowed_nodes'],
        'requested_allocation_ceiling_not_actual_cost_core_seconds':16*a.wall_seconds,
        'followup_requested_allocation_reserves':binding['followup_requested_allocation_reserves'],
        'followup_requested_allocation_reserve_core_seconds':binding['followup_requested_allocation_reserve_core_seconds'],
        'original_guide_actual_related_cost_gate_core_seconds':345600,'own_actual_cost':'NOT_SUBMITTED_NO_FUTURE_COST_PIN',
        'source_delta_declaration':ref(HERE/'source_edits_v1.json'),'no_scientific_body_read_or_hash':True,
        'new_registered_job_or_startup_proof_created':False,'scheduler_calls':False,'formal_generation_authorized':False}
    write_new(out/'execution_manifest.json',manifest)
    spec={**manifest,'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',
        'stage_output_cap_bytes':plan['max_output_bytes'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','review':None,'parent_profile':None},
        'source_status_stage':'sprime_recovery_resource_replacement_2plus14',
        'actual_direct_producer_reference':ref(HERE/'run_recovery_auto.py'),
        'root_review_parent_evidence_candidates':[ref(binding_path),*pins.values(),ref(HERE/'source_edits_v1.json')],
        'root_review_requirements':'Root must create a separate EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1 with '
            'bounded_batch_limits_reviewed=true, exact new authority/science scope/argv/wall/whole output/stage cap '
            'and real pending-only, full-owned actual costs and finite followup reserves; then create a new reviewed spec.'}
    write_new(out/'stage_spec_unreviewed.json',spec)
    receipt={'status':manifest['status'],'resource_binding':ref(binding_path),
        'execution_manifest':ref(out/'execution_manifest.json'),'science_executed':False,'scheduler_calls':False,
        'unreviewed_stage_spec':ref(out/'stage_spec_unreviewed.json'),
        'original_registered_files_modified':False,'source_status':'DRAFT_NOT_FROZEN_BY_THIS_HELPER'}
    write_new(out/'materialization_receipt.json',receipt);print(json.dumps(receipt))


if __name__=='__main__':main()
