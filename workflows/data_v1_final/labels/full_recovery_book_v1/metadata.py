"""Root metadata only: actual evidence -> unsigned exact scope -> stage spec.

No scheduler, automatic approval, DATA reads, or old-book mutation. New-book
control metadata is opened only after an actual seed C0 and explicit Root flag.
"""
from __future__ import annotations
import argparse,json,os,socket,time
from pathlib import Path
from . import contract as C,io as I
from .book import Book
from workflows.data_v1_final.labels.full_projection_v1 import materialize as M
from workflows.data_v1_final.labels.bounded_projection_v1.materialize import unique,triple,footer_inputs


def need(ok,code):C.need(ok,code)


def directory(path):
    p=Path(path).absolute();need(C.RUN/'control' in p.parents and not p.exists() and not p.is_symlink(),'NEW_ROOT_METADATA_DIRECTORY')
    p.mkdir(parents=True,mode=0o700);return p


def candidate(out,key,params,argv,refs,data,review,wall,cap,mode,parent,stage,binding=None,deferred=()):
    parents=unique(refs);sources=unique([*parents,*I.sources()])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'estimated_peak_output_bytes':cap,'stage_output_cap_bytes':cap,
      'execution_argv':argv,'scope_key':key,'scope_parameters':params,'source_status_stage':stage,
      'source_references':sources,'data_references':unique(data),'deferred_authority_references':list(deferred),
      'scope':{'mode':mode,'parent_profile':parent,'review':None}}
    if binding is not None:spec['producer_resource_binding_reference']=binding
    template={k:spec[k] for k in ('kind','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes',
      'execution_argv','scope_key','scope_parameters','source_status_stage')}
    template.update(schema='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1',status='UNSIGNED_REQUIRES_ROOT_REVIEW',reviewer=None,reason=None,
      resource_authority_reference=review['resource_authority_reference'],scope_mode=mode,parent_evidence_references=parents,
      final_common_D4_authorized=False,final_masks_authorized=False,normalization_authorized=False)
    if mode=='FULL_SOURCE_AFTER_PROFILE':template.update(profile_reviewed=True,approved_profile_reference=parent)
    I.write_new(out/'scope_review_candidate.json',template)
    I.write_new(out/'candidate.json',{'schema':'UNSIGNED_LABELS_RECOVERED_SCOPE_CANDIDATE_V1','stage_spec_payload':spec,
      'resource_authority_reference':review['resource_authority_reference'],'parent_evidence_references':parents,'future_job_or_proof_pins_created':False})


def finalize(a):
    root=Path(a.metadata_directory);c=I.load(root/'candidate.json');spec=c['stage_spec_payload'];rr=I.pin(a.scope_review);r=I.load(I.require(rr))
    need(r['schema']=='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1' and r['status']=='APPROVED_FOR_EXACT_STAGE'
      and r['reviewer']=='root' and r['reason'].strip() and r['resource_authority_reference']==c['resource_authority_reference'],'ACTUAL_ROOT_EXACT_SCOPE_NOT_SELF_SIGNED')
    for k in ('kind','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','scope_key','scope_parameters','source_status_stage'):
        need(spec[k]==r[k],'EXACT_SCOPE_FIELD:'+k)
    need(r['parent_evidence_references']==c['parent_evidence_references'],
      'ROOT_REVIEW_EXACT_ORDERED_ACTUAL_EVIDENCE')
    spec['scope']['review']=rr;spec['source_references']=unique([*spec['source_references'],rr])
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,c['resource_authority_reference'],read_small=I.OLD.small)
    print(json.dumps({'stage_spec_reference':I.write_new(root/'stage_spec.json',spec),'submitted':False}))


def seed(a):
    refs=I.account_refs(a.inventory_receipt,a.inventory_proof,a.inventory_submission,a.inventory_accounting)
    _,req,_=I.actual(refs,'workflows.data_v1_final.labels.full_timeout_inventory_v1.run','4522748')
    inv=I.load(I.require(refs['receipt']));C.inventory_gate(inv)
    resource=I.pin(a.resource_review);review=I.load(I.require(resource));v=C.budget(review)
    selection=I.pin(a.selection);s=I.load(I.require(selection))
    need(s['schema']==C.SELECTION and s['status']=='ROOT_APPROVED' and s['reviewer']=='root' and s['reason'].strip()
      and s['inventory_receipt_reference']==refs['receipt']==review['inventory_receipt_reference']
      and review['seed_selection_reference']==selection,'ACTUAL_INVENTORY_AND_ROOT_SELECTION_NO_FUTURE_READY')
    original_ref=next(r for r in req['source_references'] if r['path']==req['execution_argv'][req['execution_argv'].index('--plan')+1])
    original=I.load(I.require(original_ref));out=directory(a.metadata_directory);target=Path(a.output).absolute()
    need(not target.exists() and C.RUN/'artifacts/labels/source_status_v1' in target.parents,'NEW_SEED_CPU_OUTPUT')
    params={'original_parent':'4521904','inventory_parent':'4522748','seed_only':True,'workers':16,'new_UFF_QM_calls':0,
      'old_book_mutation':False,'new_output_cap_bytes':v['seed'],'selection_sha256':selection['sha256']}
    small=unique([*original['source_references'],*refs.values(),resource,selection,original_ref,*I.sources()])
    plan={'schema':C.SEED,'inventory_actual_references':refs,'original_inventory_plan_reference':original_ref,
      'selection_reference':selection,'resource_review_reference':resource,'scope_parameters':params,'small_references':small,'output':str(target)}
    pr=I.write_new(out/'plan.json',plan)
    argv=[C.PY,'-B','-m','workflows.data_v1_final.labels.full_recovery_book_v1.seed','--plan',pr['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(target)]
    # A source-pinned receipt authorizes only its immutable registered output.
    # book_inventory is not hashed on login; CPU revalidates old DB directly.
    data=[inv['evidence_reference'],*original['known_data_references']]
    candidate(out,C.SEED_KEY,params,argv,[*small,pr],data,review,review['seed_wall_seconds'],v['seed'],
      'BOUNDED_METADATA_PREPARATION',refs['receipt'],'LABELS_RECOVERED_BOOK_SEED_NO_OLD_C0',
      deferred=[original['closed_locator_inventory_reference']])


def seeded(a):
    refs=I.account_refs(a.seed_receipt,a.seed_proof,a.seed_submission,a.seed_accounting)
    I.actual(refs,'workflows.data_v1_final.labels.full_recovery_book_v1.seed')
    receipt=I.load(I.require(refs['receipt']));need(receipt['schema']=='LABELS_RECOVERED_BOOK_SEED_RECEIPT_V1'
      and receipt['status']=='NEW_BOOK_CREATED_ROOT_CONTINUATION_REVIEW_REQUIRED' and receipt['old_parent_c0'] is False,'ACTUAL_SEED_RECEIPT')
    sr=receipt['summary_reference'];summary=I.load(I.require(sr));review=I.load(I.require(summary['resource_review_reference']));C.budget(review)
    need(summary['schema']==C.SUMMARY and summary['old_parent_state']=='TIMEOUT' and not summary['quality_hold_fields'],'ROOT_ADOPTION_WITHOUT_QUALITY_HOLD')
    book=Book(summary['new_book_path']);need(book.metadata()['recovery_summary_reference']==sr,'ACTUAL_SEED_BOOK_IDENTITY')
    return refs,sr,summary,review,book


def quota(a,review,snapshot,summary_ref):
    qref=I.pin(a.quota_review);q=I.load(I.require(qref))
    need(q['schema']=='ROOT_LABELS_RECOVERY_FRESH_DISPATCH_QUOTA_REVIEW_V1' and q['status']=='ROOT_APPROVED'
      and q['reviewer']=='root' and q['reason'].strip() and q['uid']==1278 and q['endpoint']=='202.38.247.57:22'
      and q['adoption_summary_reference']==summary_ref and q['query_returncode']==0
      and q['query_argv']==['quota','-v','-u','zixiao'] and 0<=time.time()-q['observed_unix_seconds']<=120,
      'ACTUAL_FRESH_LOGIN_QUOTA_REVIEW_BEFORE_NEW_INTENT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import quota_free
    raw=I.OLD.small(I.require(q['raw_quota_reference'])).decode('utf-8-sig');free=quota_free(raw)
    need(q['account_free_bytes']==free and q['other_storage_scope_unwritten_cap_upper_bound_bytes']==review['other_storage_scope_unwritten_cap_upper_bound_bytes']
      and free>=200000000000+C.remaining(snapshot['metadata'],snapshot['batches'])+(2<<30)+q['other_storage_scope_unwritten_cap_upper_bound_bytes'],
      'ALL_FUTURE_CAPS_PLUS_CLOSURE_AND_200GB_CURRENT_QUOTA')
    return qref


def next_batch(a):
    need(a.root_prepare_next and a.reason.strip(),'EXPLICIT_ROOT_ONE_INTENT_NO_AUTO_RETRY')
    seedrefs,sr,summary,review,book=seeded(a)
    try:
        snap=book.snapshot();qr=quota(a,review,snap,sr)
        master=I.load(I.require(summary['master_reference']));M.review_contract(master,review,summary['master_reference'])
        selectors=[]
        for part in master['source_partitions']:
            pending=book.pending(part)
            if pending:selectors.append(pending[0])
        need(selectors,'NO_SAFE_UNSTARTED_SOURCES_NO_NEW_INTENT')
        need(8<<30<=a.output_cap_bytes<=32<<30 and 1<=a.max_RGs<=1024,'ORIGINAL_BOUNDED_TILES_AND_CAPS')
        need(a.wall_seconds==review['production_wall_seconds'],'ROOT_FIXED_PRODUCTION_WALL')
        directory_path=directory(a.metadata_directory);output=Path(a.output).absolute();need(not output.exists(),'NEW_BATCH_OUTPUT')
        selector=I.write_new(directory_path/'selector.json',{'schema':'FULL_LABEL_PHYSICAL_SELECTOR_V1','sources':selectors})
        baseline=I.load(I.require(master['bounded_config_reference']))
        footer=I.load(I.require(master['footer_manifest_reference']));_,_,_,footer_small,_=footer_inputs(footer)
        oldcfg=I.load(I.require(summary['original_config_reference']))
        seed_sources=I.load(I.require(seedrefs['proof']))['request']['source_references']
        code=unique([*oldcfg['source_references'],*seed_sources,*I.sources()])
        small=unique([summary['master_reference'],summary['resource_review_reference'],sr,selector,qr,*seedrefs.values(),
          master['bounded_config_reference'],master['footer_manifest_reference'],*master['bounded_evidence_references'],*footer_small,
          *baseline['small_references'],*[review[k] for k in ('storage_review_reference','Sprime_reservation_closure_reference','resource_authority_reference')]])
        ids={s['file_id'] for s in selectors}
        params={'global_records':11231854,'global_molecules':1220466,'global_label_files':2024,'global_base_files':184,
          'selected_source_files':len(selectors),'selected_file_ids':sorted(ids),'max_actual_RGs_per_source':a.max_RGs,'workers':16,
          'declared_fields':264,'enabled_components':146,'whole_output_cap_bytes':a.output_cap_bytes,'new_UFF_QM_calls':0,
          'normalization':False,'candidate_masks_only':True,'master_sha256':summary['master_reference']['sha256'],
          'recovery_adoption_summary_sha256':sr['sha256'],'old_parent_state':'TIMEOUT'}
        cfg=dict(baseline,schema='FULL_LABEL_PROJECTION_BATCH_CONFIG_V1',scope_parameters=params,workers=16,
          master_reference=summary['master_reference'],full_review_reference=summary['resource_review_reference'],source_references=code,small_references=small,
          selector_reference=selector,previous_manifest_reference=None,parity_cache_references=[],footer_manifest_reference=master['footer_manifest_reference'],
          whole_output_cap_bytes=a.output_cap_bytes,sidecar_reserve_bytes=2<<30,admin_reserve_bytes=1<<30,observer_reserve_bytes=64<<20,
          output_inode_cap=8192,review_calibration_reference=None,calibration_state=M.CALIBRATION,logical_statistics_partition_reference=None,
          norm_fit_allowed=False,full_population_authorized=True,dispatch_book_path=summary['new_book_path'],batch_name=a.batch_name,max_actual_RGs_per_source=a.max_RGs,
          recovery_schema=C.SUMMARY,recovery_resource_review_reference=summary['resource_review_reference'],adoption_summary_reference=sr,
          seed_actual_references=seedrefs,recovery_wall_seconds=a.wall_seconds)
        cr=I.write_new(directory_path/'config.json',cfg)
        book.claim(a.batch_name,selectors,a.output_cap_bytes,cfg['output_inode_cap'],cr)
    finally:book.close()
    # New-book control metadata only, capped small on login. Never old DATA.
    br=I.pin(summary['new_book_path'])
    binding={'schema':'FULL_LABEL_PROJECTION_BATCH_RESOURCE_BINDING_V1','scientific_config_reference':cr,'scope_key':C.RUN_KEY,
      'scope_parameters':params,'resource_authority_reference':review['resource_authority_reference'],'memavailable_soft_floor_bytes':4<<30,
      'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(output)+'_resource_observation','software_scan_worker_cap_bytes':3<<30}
    bp=I.write_new(directory_path/'resource_binding.json',binding)
    sourcebook,index,_,_,_=footer_inputs(footer)
    streamrefs=unique(index[i]['inventory_reference'] for i in ids)
    data=unique([cfg['canonical_index'],br,*streamrefs,*[triple(r) for r in sourcebook['files'] if r['file_id'] in ids]])
    argv=[C.PY,'-B','-m','workflows.data_v1_final.labels.full_recovery_book_v1.run','--config',cr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    candidate(directory_path,C.RUN_KEY,params,argv,[*code,*small,cr,bp],data,review,a.wall_seconds,a.output_cap_bytes,
      'FULL_SOURCE_AFTER_PROFILE',master['bounded_manifest_reference'],None,binding=bp)


def accept(a):
    seedrefs,sr,summary,review,book=seeded(a)
    try:
        refs=I.account_refs(a.manifest,a.proof,a.submission,a.accounting);_,req,_=I.actual(refs,'workflows.data_v1_final.labels.full_recovery_book_v1.run')
        m=I.load(I.require(refs['receipt']));cfg=I.load(I.require(m['config']))
        need(m['schema']=='FULL_LABEL_PROJECTION_BATCH_V1' and m['status']=='BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED'
          and not(m['errors'] or m['unpublished_tickets'] or m['quality_hold_fields']) and cfg['adoption_summary_reference']==sr
          and cfg['dispatch_book_path']==summary['new_book_path'],'ONLY_REAL_NEW_C0_BATCH_NO_UNKNOWN_QUALITY_BYPASS')
        wrapper=I.load(str(Path(req['execution_argv'][req['execution_argv'].index('--output')+1]))+'_recovery_control/receipt.json')
        need(wrapper['status']=='ORIGINAL_FULL_MAIN_RETURNED_PARENT_C0_STILL_REQUIRES_ACCOUNTING' and wrapper['config_reference']==m['config'],
          'ACTUAL_DIRECT_ORIGINAL_WRAPPER_REQUIRED')
        charged=max(m['charged_output_bytes_including_manifest_reserve'],wrapper['charged_output_bytes_including_wrapper_reserves'])
        book.accept(cfg['batch_name'],m['config'],m['source_cursors'],{'manifest':refs['receipt'],'actual_parent_chain':refs},
          charged,m['charged_output_inodes_including_manifest_reserve']+8)
    finally:book.close()


def close(a):
    seedrefs,sr,summary,review,book=seeded(a)
    try:
        snap=book.snapshot();need(not snap['recovery_holds'] and all(s['lease'] is None and s['next_physical_row']==s['physical_row_hi'] for s in snap['sources'])
          and all(b['state']=='ACTUAL_C0_CLOSED' for b in snap['batches']),'ALL_SOURCES_AND_REAL_NEW_C0_BATCHES_CLOSED')
        qr=quota(a,review,snap,sr);remaining=C.remaining(snap['metadata'],snap['batches'])
    finally:book.close()
    out=directory(a.metadata_directory);snapshot=I.write_new(out/'dispatch_snapshot.json',snap)
    params={'source_files':2208,'global_records':11231854,'task_slots':14,'adopted_origin_separate_from_new_C0':True,
      'whole_output_cap_bytes':2<<30,'new_UFF_QM_calls':0,'normalization':False}
    seed_sources=I.load(I.require(seedrefs['proof']))['request']['source_references']
    parents=[r for b in snap['batches'] for r in b['receipt']['actual_parent_chain'].values()]
    manifests=[b['receipt']['manifest'] for b in snap['batches']]
    small=unique([sr,summary['resource_review_reference'],summary['master_reference'],qr,snapshot,*seedrefs.values(),*seed_sources,*parents,*manifests,*I.sources()])
    cfg={'schema':'LABELS_RECOVERED_COVERAGE_CONFIG_V1','scope_parameters':params,'resource_review_reference':summary['resource_review_reference'],
      'master_reference':summary['master_reference'],'adoption_summary_reference':sr,'canonical_index':summary['canonical_index'],
      'seed_actual_references':seedrefs,'dispatch_snapshot_reference':snapshot,'small_references':small,
      'remaining_cache_reservation_bytes':remaining,'wall_seconds':a.wall_seconds}
    # These are producer-declared DATA locators; never open/hash them on login.
    data=[summary['canonical_index'],summary['sidecar']['reference'],summary['adoption_membership_reference']]
    for b in snap['batches']:
        m=I.load(I.require(b['receipt']['manifest']));data.extend([m['sidecar']['reference'],m['closed_window_index_reference']])
    cfg['known_data_references']=unique(data);cfg['transitive_output_authority_references']=[sr,*manifests]
    cr=I.write_new(out/'config.json',cfg)
    argv=[C.PY,'-B','-m','workflows.data_v1_final.labels.full_recovery_book_v1.coverage','--config',cr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(Path(a.output).absolute())]
    candidate(out,C.CLOSE_KEY,params,argv,[*small,cr],data,review,a.wall_seconds,2<<30,'BOUNDED_METADATA_PREPARATION',seedrefs['receipt'],'LABELS_RECOVERED_MIXED_ORIGIN_EXACT_COVERAGE',
      deferred=[sr,*manifests])


def main():
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and Path(__file__).absolute().parent==C.HERE,'ROOT_MAIN_LOGIN_METADATA_HELPER')
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    s=sub.add_parser('seed-candidate')
    for k in ('inventory-receipt','inventory-proof','inventory-submission','inventory-accounting','resource-review','selection','metadata-directory','output'):s.add_argument('--'+k,type=Path,required=True)
    for mode in ('next','accept','close'):
        q=sub.add_parser(mode)
        for k in ('seed-receipt','seed-proof','seed-submission','seed-accounting'):q.add_argument('--'+k,type=Path,required=True)
        if mode in ('next','close'):
            for k in ('quota-review','metadata-directory','output'):q.add_argument('--'+k,type=Path,required=True)
            q.add_argument('--wall-seconds',type=int,required=True)
        if mode=='next':
            q.add_argument('--batch-name',required=True);q.add_argument('--root-prepare-next',action='store_true');q.add_argument('--reason',required=True)
            q.add_argument('--output-cap-bytes',type=int,default=32<<30);q.add_argument('--max-RGs',dest='max_RGs',type=int,default=1024)
        if mode=='accept':
            for k in ('manifest','proof','submission','accounting'):q.add_argument('--'+k,type=Path,required=True)
    f=sub.add_parser('finalize-scope');f.add_argument('--metadata-directory',type=Path,required=True);f.add_argument('--scope-review',type=Path,required=True)
    a=p.parse_args();{'seed-candidate':seed,'next':next_batch,'accept':accept,'close':close,'finalize-scope':finalize}[a.mode](a)

if __name__=='__main__':main()