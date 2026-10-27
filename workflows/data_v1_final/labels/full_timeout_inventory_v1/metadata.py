"""Main-login metadata/lstat only. No data hash, approval, Slurm or submission."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from . import contract as C,io as I


def unique(refs):
    out={}
    for ref in refs:
        ref=C.triple(ref);C.need(ref['path'] not in out or out[ref['path']]==ref,'NO_CONFLICTING_SOURCE_PINS');out[ref['path']]=ref
    return list(out.values())


def candidate(a):
    metadata=I.load(a.post_terminal_metadata)
    C.need(metadata['schema']=='ROOT_POST_TERMINAL_LABELS_TIMEOUT_METADATA_LSTAT_ONLY_V1'
      and metadata['scientific_body_files_read_or_hashed']==0 and metadata['old_batch_or_book_accepted'] is False,
      'ACTUAL_POST_TERMINAL_LSTAT_AUTHORITY')
    subref=metadata['original_submission_reference'];sub=I.load(I.require(subref));reqref=sub['request_reference']
    request=I.load(I.require(reqref));C.need(request==sub['request'],'ACTUAL_ORIGINAL_REQUEST')
    proofref=I.pin(request['startup_proof_path']);proof=I.load(I.require(proofref))
    configref=next(r for r in request['source_references'] if r['path']==C.option(request['execution_argv'],'--config'))
    cfg=I.load(I.require(configref));accountref=metadata['actual_parent_accounting_reference'];account=I.load(I.require(accountref))
    rawref=account['raw_sacct_reference'];raw=I.small(I.require(rawref)).decode('utf-8-sig')
    C.parent_chain(account,raw,request,proof,sub,cfg,configref)
    stageref=metadata['original_full_stage_spec_reference'];I.require(stageref)
    C.need(request['root_review']['stage_spec_reference']==stageref,'EXACT_ACTUAL_ORIGINAL_STAGE_BINDING')
    C.need(metadata['original_output_directory']==str(C.OLD) and metadata['original_dispatcher_book_path']==str(C.BOOK),
      'NO_ARBITRARY_TRANSITIVE_ARCHIVE')
    observed={r['path']:r for r in metadata['lstat_frames']}
    for path in (C.OLD,C.BOOK,C.OLD/'state.sqlite'):I.original_match(I.frame(path.lstat()),observed[str(path)])
    root=Path(a.metadata_directory).absolute();output=Path(a.output).absolute()
    C.need(C.RUN in root.parents and not root.exists() and C.RUN/'artifacts/labels/source_status_v1' in output.parents
      and output!=C.OLD and C.OLD not in output.parents and not output.exists(),'NEW_METADATA_AND_NEW_INDEPENDENT_OUTPUT')
    C.need(a.other_storage_cap_bytes>=0,'EXPLICIT_ALL_OTHER_STORAGE_RESERVE_UPPER_BOUND')
    root.mkdir(parents=True,mode=0o700)
    locators=I.locator_inventory(C.OLD,C.BOOK)
    locatorref=I.write_new(root/'closed_locator_inventory.json',locators)
    originals={'post_terminal_lstat':I.pin(a.post_terminal_metadata),'submission':subref,'request':reqref,'proof':proofref,
      'config':configref,'accounting':accountref,'raw':rawref,'stage_spec':stageref}
    own=[I.pin(p) for p in sorted(C.HERE.iterdir()) if p.suffix in ('.py','.md')]
    C.need(len(own)==8,'EXACT_SEVEN_PY_PLUS_README_SOURCE_SET')
    sources=unique([*request['source_references'],*originals.values(),locatorref,I.pin(a.resource_authority),*own])
    for ref in sources:I.require(ref)
    # These fourteen hashes already exist in Root's actual post-terminal small metadata.
    # They are DATA locators: this helper neither opens nor independently verifies them.
    known=[C.triple(ref) for ref in metadata['already_closed_worker_small_metadata_references']]
    C.need(len(known)==metadata['worker_metadata_count']==14 and all(Path(r['path']).parent==C.OLD for r in known),'EXACT_OBSERVED_WORKER_DATA_LOCATORS')
    parameters=dict(C.PARAMETERS,other_storage_scope_unwritten_cap_upper_bound_bytes=a.other_storage_cap_bytes)
    plan={'schema':C.SCHEMA,'scope_key':C.KEY,'scope_parameters':parameters,'original_references':originals,
      'root_post_terminal_lstat_reference':originals['post_terminal_lstat'],'closed_locator_inventory_reference':locatorref,
      'known_data_references':known,'source_references':sources,'resource_authority_reference':I.pin(a.resource_authority),
      'other_storage_scope_unwritten_cap_upper_bound_bytes':a.other_storage_cap_bytes,'output':str(output),
      'pending_cpu_whole_SHA':True,'transitive_closed_output_authority':{
        'basis':'ACTUAL_REGISTERED_TERMINAL_PARENT_OUTPUT_PLUS_ROOT_POST_TERMINAL_LSTAT',
        'original_parent_job_id':'4521904','original_parent_state':'TIMEOUT','original_parent_c0':False,
        'locator_inventory_reference':locatorref,'new_cpu_observed_hash_is_not_an_original_producer_hash':True},
      'dispatcher_recovery_or_next_job_authorized':False,'full_quality_release_authorized':False}
    planref=I.write_new(root/'plan.json',plan)
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',planref['path'],'--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    sources=unique([*sources,planref])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':1800,'estimated_peak_output_bytes':2<<30,
      'stage_output_cap_bytes':2<<30,'execution_argv':argv,'scope_key':C.KEY,'scope_parameters':parameters,
      'source_status_stage':C.STAGE,'source_references':sources,'data_references':known,
      'deferred_authority_references':[locatorref],
      'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':accountref,'review':None},
      'closed_locator_inventory_reference':locatorref}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'UNSIGNED_REQUIRES_ROOT_REVIEW',
      'reviewer':None,'resource_authority_reference':I.pin(a.resource_authority),'scope_mode':'BOUNDED_METADATA_PREPARATION',
      'reason':None,'parent_evidence_references':unique(originals.values()),'partial_timeout_inventory_only':True,
      'original_parent_c0':False,'original_batch_acceptance_authorized':False,'dispatcher_recovery_authorized':False,
      'node':'compute-0-17','all_other_storage_reservations_reviewed':False,
      'other_storage_scope_unwritten_cap_upper_bound_bytes':a.other_storage_cap_bytes}
    for key in ('kind','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv',
      'scope_key','scope_parameters','source_status_stage'):template[key]=spec[key]
    I.write_new(root/'scope_review_template.json',template)
    I.write_new(root/'candidate.json',{'schema':'UNSIGNED_LABELS_TIMEOUT_READONLY_STAGE_CANDIDATE_V1',
      'not_executable_until_actual_Root_scope_review':True,'node':'compute-0-17','stage_spec_payload':spec,
      'plan_reference':planref,'scientific_input_bodies_opened_or_hashed':0})
    print(json.dumps({'candidate_directory':str(root),'plan_reference':planref,'status':'UNSIGNED_NO_SUBMISSION'}))


def finalize(a):
    root=Path(a.candidate_directory).absolute();candidate=I.load(root/'candidate.json');spec=candidate['stage_spec_payload']
    reviewref=I.pin(a.root_scope_review);review=I.load(I.require(reviewref))
    C.need(review['schema']=='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1'
      and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root' and review['reason'].strip(),
      'ACTUAL_INDEPENDENT_ROOT_REVIEW_REQUIRED')
    C.need(review.get('partial_timeout_inventory_only') is True and review.get('original_parent_c0') is False
      and review.get('original_batch_acceptance_authorized') is False and review.get('dispatcher_recovery_authorized') is False
      and review.get('node')=='compute-0-17' and review.get('all_other_storage_reservations_reviewed') is True,
      'ROOT_REVIEW_IS_ONLY_THIS_READONLY_PARTIAL_STAGE')
    plan=I.load(I.require(candidate['plan_reference']))
    C.need(review['resource_authority_reference']==plan['resource_authority_reference']
      and review['other_storage_scope_unwritten_cap_upper_bound_bytes']==plan['other_storage_scope_unwritten_cap_upper_bound_bytes'],
      'EXACT_RESOURCE_AUTHORITY_AND_ALL_OTHER_RESERVATIONS')
    for key in ('kind','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv',
      'scope_key','scope_parameters','source_status_stage'):C.need(spec[key]==review[key],'ROOT_EXACT_FIELD:'+key)
    C.need(review['parent_evidence_references']==unique(plan['original_references'].values()),'ALL_ACTUAL_PARENT_EVIDENCE_REVIEWED')
    spec['scope']['review']=reviewref;spec['source_references']=unique([*spec['source_references'],reviewref])
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,plan['resource_authority_reference'],read_small=I.small)
    ref=I.write_new(root/'stage_spec.json',spec)
    print(json.dumps({'stage_spec_reference':ref,'status':'ROOT_REVIEWED_INPUT_NOT_SUBMITTED','node':'compute-0-17'}))


def main():
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import on_login
    on_login();C.need(Path(__file__).absolute().parent==C.HERE,'ACTUAL_ROOT_INSTALLED_HELPER_ONLY')
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    c=s.add_parser('candidate')
    for key in ('post-terminal-metadata','resource-authority','metadata-directory','output'):c.add_argument('--'+key,required=True)
    c.add_argument('--other-storage-cap-bytes',type=int,required=True)
    f=s.add_parser('finalize');f.add_argument('--candidate-directory',required=True);f.add_argument('--root-scope-review',required=True)
    a=p.parse_args();{'candidate':candidate,'finalize':finalize}[a.mode](a)

if __name__=='__main__':main()