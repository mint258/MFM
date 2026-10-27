"""Metadata-only master/next/accept commands; never read scientific source bodies."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from .control import SCHEMA,SCOPE,CLOSE_SCOPE,CALIBRATION,DispatchBook,need,partition_sources,review_contract,source_contract
from workflows.data_v1_final.labels.bounded_projection_v1.materialize import (
 RUN,REPO,PY,actual_parent,footer_inputs,load,pin,require,save,triple,unique)


def accepted_bounded(path,proof,accounting,raw):
    _,refs=actual_parent(path,proof,accounting,raw);m=load(path);p=m['parity']
    need(m['schema']=='BOUNDED_LABEL_PROJECTION_BATCH_V1' and m['status']=='BATCH_CACHE_CLOSED_FULL_COVERAGE_PENDING'
      and not m['errors'] and not m['unpublished_tickets'] and all(c['complete'] for c in m['cursors']),
      'ACTUAL_C0_BOUNDED_BODY_MUST_BE_CLOSED')
    need(p['matched_rows']>0 and all(p['matched_rows_by_task'].get(str(i),0)>0 for i in [*range(14),255])
      and p['source_new_mask_and_source_review_axis']=='PASS' and p['mismatch_count']==0
      and not p['missing_witness_rows'] and not p['mismatched_witness_rows'] and not p['missing_encoding_keys']
      and not p['unwitnessed_current_CELL_kinds'] and not p['unwitnessed_current_float_widths'],
      'ACTUAL_NONZERO_ALL_TASK_WITNESS_PARITY_NOT_EMPTY_PASS')
    need(not m['quality_stop_fields_global_lower_bound'] and not m['partial_observed_rate_review_fields']
      and m['coverage']['duplicate_keys']==0,'BOUNDED_QUALITY_AND_DUPLICATE_HOLD_NOT_RELEASED')
    return m,refs


def candidate(a):
    m,parents=accepted_bounded(a.bounded_manifest,a.bounded_proof,a.bounded_accounting,a.bounded_raw)
    cfg=load(require(m['config']));footer=load(require(cfg['footer_manifest_reference']))
    book,_,_,footer_small,_=footer_inputs(footer);mass=source_contract(book['files'])
    directory=Path(a.metadata_directory).absolute();need(RUN in directory.parents and not directory.exists(),'NEW_MASTER_DIRECTORY')
    directory.mkdir(parents=True,mode=0o700)
    master={'schema':SCHEMA,'status':'CANDIDATE_ONLY_AWAITING_ROOT_FULL_STORAGE_AND_COST_REVIEW','executable':False,
      'scope':mass,'footer_manifest_reference':cfg['footer_manifest_reference'],'source_inventory_reference':footer['source_inventory_reference'],
      'sources':book['files'],'source_partitions':partition_sources(book['files']),
      'bounded_manifest_reference':pin(a.bounded_manifest),'bounded_config_reference':m['config'],
      'bounded_evidence_references':unique(parents),'footer_small_references':unique(footer_small),
      'full_source_label_bytes_inherited':sum(r['bytes'] for r in book['files'] if r['source_kind']=='label'),
      'full_source_base_bytes_inherited':sum(r['bytes'] for r in book['files'] if r['source_kind']=='base'),
      'producer_wholebody_SHA_not_current_rehash':True,'numeric_values_or_SQLite_body_read':False,
      'calibration_state':CALIBRATION,'logical_statistics_partition_reference':None,
      'final_common_D4':False,'final_masks_authorized':False,'default_full_cache_cap_bytes':None,
      'next_batch_default_cap_bytes':32<<30,'next_batch_max_RGs_per_source':1024,
      'full_cache_linear_estimate_is_not_approved_reservation':True}
    save(directory/'master.json',master);print(json.dumps({'status':master['status'],'metadata':str(directory)}))


def next_batch(a):
    need(a.approve and a.reason.strip(),'EXPLICIT_ROOT_NEXT_BATCH_REVIEW')
    master=load(a.master);mr=pin(a.master);review=load(a.full_review);rr=pin(a.full_review);review_contract(master,review,mr)
    for key in ('storage_review_reference','Sprime_reservation_closure_reference','resource_authority_reference'):require(review[key])
    need(pin(a.resource_authority)==review['resource_authority_reference'],'FULL_AND_CURRENT_RESOURCE_AUTHORITY_MATCH')
    source_contract(master['sources']);dbpath=Path(a.dispatch_book).absolute()
    need(RUN in dbpath.parents and not dbpath.is_symlink(),'ROOT_OWNED_METADATA_BOOK')
    db=DispatchBook(dbpath,not dbpath.exists(),files=master['sources'],cap=review['approved_whole_cache_cap_bytes'],
      inodes=review['approved_whole_cache_inode_cap'],master_reference=mr,review_reference=rr)
    try:
        need(db.metadata()['master']==mr and db.metadata()['review']==rr,'UNCHANGED_MASTER_AND_FULL_APPROVAL')
        selectors=[]
        for partition in master['source_partitions']:
            pending=db.pending(partition)
            if pending:selectors.append(pending[0])
        need(selectors,'NO_REMAINING_UNLEASED_SOURCE_NO_NEW_JOB')
        directory=Path(a.metadata_directory).absolute();output=Path(a.output).absolute()
        need(RUN in directory.parents and not directory.exists() and RUN/'artifacts/labels/source_status_v1' in output.parents
          and not output.exists(),'NEW_BATCH_METADATA_AND_OUTPUT')
        need(8<<30<=a.whole_output_cap_bytes<=32<<30 and 1<=a.max_row_groups_per_source<=1024,'FINITE_EXPLICIT_BATCH_LIMITS')
        directory.mkdir(parents=True,mode=0o700);selector=save(directory/'selector.json',{'sources':selectors,
          'max_row_groups_per_source':a.max_row_groups_per_source,'physical_cursor_is_not_record_ordinal':True})
        baseline=load(require(master['bounded_config_reference']));footer=load(require(master['footer_manifest_reference']))
        book,index,streams,footer_small,_=footer_inputs(footer);ids={r['file_id'] for r in selectors}
        selected_streams=unique(index[i]['inventory_reference'] for i in ids)
        sources=unique(baseline['source_references']+[pin(q) for q in Path(__file__).parent.iterdir() if q.suffix in ('.py','.md')]
          +[pin(REPO/'workflows/data_v1_final/labels/source_status_v1'/name) for name in ('reduce.py','support.py')])
        small=unique([mr,rr,selector,master['bounded_config_reference'],master['footer_manifest_reference'],
          *master['bounded_evidence_references'],*footer_small,*[review[k] for k in ('storage_review_reference','Sprime_reservation_closure_reference','resource_authority_reference')],
          *baseline['small_references']])
        params={'global_records':11231854,'global_molecules':1220466,'global_label_files':2024,'global_base_files':184,
          'selected_source_files':len(selectors),'selected_file_ids':sorted(ids),'max_actual_RGs_per_source':a.max_row_groups_per_source,
          'workers':16,'declared_fields':264,'enabled_components':146,'whole_output_cap_bytes':a.whole_output_cap_bytes,
          'new_UFF_QM_calls':0,'normalization':False,'candidate_masks_only':True,'master_sha256':mr['sha256']}
        config=dict(baseline,schema='FULL_LABEL_PROJECTION_BATCH_CONFIG_V1',scope_parameters=params,
          master_reference=mr,full_review_reference=rr,source_references=sources,small_references=small,
          selector_reference=selector,previous_manifest_reference=None,parity_cache_references=[],
          footer_manifest_reference=master['footer_manifest_reference'],whole_output_cap_bytes=a.whole_output_cap_bytes,
          sidecar_reserve_bytes=2<<30,admin_reserve_bytes=1<<30,observer_reserve_bytes=64<<20,
          output_inode_cap=8192,review_calibration_reference=None,calibration_state=CALIBRATION,
          logical_statistics_partition_reference=None,norm_fit_allowed=False,full_population_authorized=True,
          dispatch_book_path=str(dbpath),batch_name=a.batch_name,max_actual_RGs_per_source=a.max_row_groups_per_source)
        config_ref=save(directory/'config.json',config)
        db.claim(a.batch_name,selectors,a.whole_output_cap_bytes,config['output_inode_cap'],config_ref)
    finally:db.close()
    # Mutable metadata book is pinned at the post-claim/pre-dispatch state. The
    # serial chain prevents a second preparer changing it before this startup.
    from workflows.data_v1_final.labels.bounded_projection_v1.parts import pin as metadata_db_pin
    dbref=metadata_db_pin(dbpath)
    binding={'schema':'FULL_LABEL_PROJECTION_BATCH_RESOURCE_BINDING_V1','scientific_config_reference':config_ref,
      'scope_key':SCOPE,'scope_parameters':params,'resource_authority_reference':pin(a.resource_authority),
      'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':str(output)+'_resource_observation','software_scan_worker_cap_bytes':3<<30}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.full_projection_v1.run','--config',config_ref['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    parents=unique([*master['bounded_evidence_references'],mr,rr,review['storage_review_reference'],review['Sprime_reservation_closure_reference']])
    scope_review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'reason':a.reason,'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':False,
      'scope_key':SCOPE,'scope_parameters':params,'scope_mode':'FULL_SOURCE_AFTER_PROFILE','wall_seconds':a.wall_seconds,
      'estimated_peak_output_bytes':a.whole_output_cap_bytes,'stage_output_cap_bytes':a.whole_output_cap_bytes,
      'source_status_stage':None,'execution_argv':argv,'profile_reviewed':True,
      'approved_profile_reference':master['bounded_manifest_reference'],'parent_evidence_references':parents,
      'full_source_cache_only_not_final_masks_or_D4':True}
    need(0<a.wall_seconds<=172800,'MAX48H_STAGE')
    rp=save(directory/'scope_review.json',scope_review)
    data=unique([config['canonical_index'],dbref,*selected_streams,*[triple(r) for r in book['files'] if r['file_id'] in ids]])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':a.wall_seconds,
      'estimated_peak_output_bytes':a.whole_output_cap_bytes,'stage_output_cap_bytes':a.whole_output_cap_bytes,
      'source_status_stage':None,'execution_argv':argv,'source_references':unique([*sources,*small,config_ref,bp,rp]),
      'data_references':data,'scope_key':SCOPE,'scope_parameters':params,
      'scope':{'mode':'FULL_SOURCE_AFTER_PROFILE','review':rp,'parent_profile':master['bounded_manifest_reference']},
      'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec);print(json.dumps({'status':'ROOT_REVIEWED_METADATA_ONLY_NOT_SUBMITTED','stage_spec':str(directory/'stage_spec.json')}))


def accept_batch(a):
    _,parents=actual_parent(a.manifest,a.proof,a.accounting,a.raw);m=load(a.manifest)
    need(m['schema']=='FULL_LABEL_PROJECTION_BATCH_V1' and m['status']=='BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED'
      and m['errors']==[] and m['unpublished_tickets']==[] and m['quality_hold_fields']==[],
      'ONLY_ACTUAL_C0_CLOSED_NO_UNKNOWN_NO_QUALITY_HOLD_CAN_ADVANCE')
    cfg=load(require(m['config']));db=DispatchBook(a.dispatch_book)
    try:
        need(str(Path(a.dispatch_book).absolute())==cfg['dispatch_book_path'],'ACTUAL_BATCH_BOOK')
        db.accept(cfg['batch_name'],m['config'],m['source_cursors'],{'manifest':pin(a.manifest),'actual_C0_evidence':unique(parents)},
          m['charged_output_bytes_including_manifest_reserve'],m['charged_output_inodes_including_manifest_reserve'])
    finally:db.close()
    print(json.dumps({'status':'ACTUAL_C0_CURSOR_ACCEPTED_NO_AUTOMATIC_NEXT_JOB','batch':cfg['batch_name']}))


def closure(a):
    need(a.approve and a.reason.strip(),'EXPLICIT_ROOT_WHOLE_COVERAGE_REVIEW')
    master=load(a.master);mr=pin(a.master);review=load(a.full_review);rr=pin(a.full_review);review_contract(master,review,mr)
    need(pin(a.resource_authority)==review['resource_authority_reference'],'EXACT_COVERAGE_RESOURCE_AUTHORITY')
    db=DispatchBook(a.dispatch_book)
    try:state=db.snapshot()
    finally:db.close()
    need(state['metadata']['master']==mr and state['metadata']['review']==rr and len(state['sources'])==2208
      and all(s['lease'] is None and s['next_physical_row']==s['physical_row_hi'] for s in state['sources'])
      and all(b['state']=='ACTUAL_C0_CLOSED' for b in state['batches']),'NO_FULL_CLOSE_WHILE_SOURCE_OR_ATTEMPT_PENDING')
    directory=Path(a.metadata_directory).absolute();output=Path(a.output).absolute()
    need(RUN in directory.parents and not directory.exists() and RUN/'artifacts/labels/source_status_v1' in output.parents
      and not output.exists(),'NEW_COVERAGE_METADATA_OUTPUT');directory.mkdir(parents=True,mode=0o700)
    snapshot=save(directory/'closed_dispatch_snapshot.json',state)
    baseline=load(require(master['bounded_config_reference']));data=[baseline['canonical_index']];parents=list(master['bounded_evidence_references'])
    for batch in state['batches']:
        receipt=batch['receipt'];require(receipt['manifest']);m=load(receipt['manifest']['path'])
        need(m['status']=='BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED' and not m['quality_hold_fields'],'ACCEPTED_CLOSED_BATCH_NOT_QUALITY_HOLD')
        data.append(m['sidecar']['reference']);parents.extend([receipt['manifest'],*receipt['actual_C0_evidence']])
    small=unique([mr,rr,snapshot,master['bounded_config_reference'],*parents,
      *[review[k] for k in ('storage_review_reference','Sprime_reservation_closure_reference','resource_authority_reference')]])
    sources=unique(baseline['source_references']+[pin(q) for q in Path(__file__).parent.iterdir() if q.suffix in ('.py','.md')]
      +[pin(REPO/'workflows/data_v1_final/labels/source_status_v1'/name) for name in ('reduce.py','support.py')])
    parameters={'source_files':2208,'label_files':2024,'base_files':184,'global_records':11231854,'task_slots':14,
      'accepted_actual_C0_batches':len(state['batches']),'new_UFF_QM_calls':0,'normalization':False,'final_mask_release':False}
    config={'schema':'FULL_LABEL_PROJECTION_COVERAGE_CONFIG_V1','scope_parameters':parameters,'master_reference':mr,'full_review_reference':rr,
      'dispatch_snapshot_reference':snapshot,'canonical_index':baseline['canonical_index'],'whole_output_cap_bytes':2<<30,
      'remaining_cache_reservation_bytes':state['metadata']['cap']-sum(b['charged_bytes'] for b in state['batches']),
      'normalization_allowed':False,'source_references':sources,'small_references':small}
    cr=save(directory/'config.json',config)
    binding={'schema':'FULL_LABEL_PROJECTION_COVERAGE_RESOURCE_BINDING_V1','scientific_config_reference':cr,
      'scope_key':CLOSE_SCOPE,'scope_parameters':parameters,'resource_authority_reference':pin(a.resource_authority),
      'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(output)+'_resource_observation'}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.full_projection_v1.close','--config',cr['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    rootreview={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root','reason':a.reason,
      'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':False,'scope_key':CLOSE_SCOPE,'scope_parameters':parameters,
      'scope_mode':'FULL_SOURCE_AFTER_PROFILE','wall_seconds':a.wall_seconds,'estimated_peak_output_bytes':2<<30,'stage_output_cap_bytes':2<<30,
      'source_status_stage':None,'execution_argv':argv,'profile_reviewed':True,'approved_profile_reference':master['bounded_manifest_reference'],
      'parent_evidence_references':unique(parents+[mr,rr])}
    need(0<a.wall_seconds<=172800,'MAX48H_COVERAGE');rp=save(directory/'scope_review.json',rootreview)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'wall_seconds':a.wall_seconds,'estimated_peak_output_bytes':2<<30,'stage_output_cap_bytes':2<<30,'source_status_stage':None,'execution_argv':argv,
      'source_references':unique([*sources,*small,cr,bp,rp]),'data_references':unique(data),'scope_key':CLOSE_SCOPE,'scope_parameters':parameters,
      'scope':{'mode':'FULL_SOURCE_AFTER_PROFILE','review':rp,'parent_profile':master['bounded_manifest_reference']},'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec);print(json.dumps({'status':'METADATA_ONLY_COVERAGE_NOT_SUBMITTED','stage_spec':str(directory/'stage_spec.json')}))


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    c=s.add_parser('candidate')
    for key in ('bounded-manifest','bounded-proof','bounded-accounting','bounded-raw','metadata-directory'):c.add_argument('--'+key,required=True)
    n=s.add_parser('next')
    for key in ('master','full-review','resource-authority','dispatch-book','batch-name','metadata-directory','output','reason'):n.add_argument('--'+key,required=True)
    n.add_argument('--approve',action='store_true');n.add_argument('--whole-output-cap-bytes',type=int,default=32<<30)
    n.add_argument('--max-row-groups-per-source',type=int,default=1024);n.add_argument('--wall-seconds',type=int,default=7200)
    c=s.add_parser('accept')
    for key in ('manifest','proof','accounting','raw','dispatch-book'):c.add_argument('--'+key,required=True)
    c=s.add_parser('close')
    for key in ('master','full-review','resource-authority','dispatch-book','metadata-directory','output','reason'):c.add_argument('--'+key,required=True)
    c.add_argument('--approve',action='store_true');c.add_argument('--wall-seconds',type=int,default=7200)
    a=p.parse_args();need(Path(__file__).absolute().parent==REPO/'workflows/data_v1_final/labels/full_projection_v1','ACTUAL_ROOT_CODE_ONLY')
    {'candidate':candidate,'next':next_batch,'accept':accept_batch,'close':closure}[a.mode](a)

if __name__=='__main__':main()
