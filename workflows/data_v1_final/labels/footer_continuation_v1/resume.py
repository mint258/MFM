"""Metadata-only footer continuation plan. No original Parquet IO or submission."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';SCOPE='labels_wp5_footer_continuation_v1'


def need(ok,code):
    if not ok:raise ValueError(code)


def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def pin(path):
    p=Path(path).absolute();need(p.stat().st_size<=2<<20,'SMALL_METADATA_PIN_ONLY')
    raw=p.read_bytes();need(len(raw)<=2<<20,'SMALL_METADATA_PIN_ONLY')
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def load(path):
    need(Path(path).stat().st_size<=2<<20,'SMALL_METADATA_INPUT_ONLY')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require(r):
    need(pin(r['path'])==triple(r),'ACTUAL_SMALL_METADATA_PIN_DIFFERS:'+r['path']);return Path(r['path'])


def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'GENERATED_METADATA_CAP')
    with Path(path).open('xb') as f:f.write(raw)
    return pin(path)


def unique(refs):
    result={}
    for r in refs:
        r=triple(r);need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_EXACT_REFERENCES')
        result[r['path']]=r
    return list(result.values())


def partition(book,layers,reports):
    """Source IDs can be pending repeatedly, but completed exactly once."""
    sources={r['file_id']:r for r in book['files']};need(len(sources)==len(book['files']),'UNIQUE_SOURCE_IDS')
    completed={};remaining=set(sources);streams=[];jobs=set()
    for layer in layers:
        report=reports[layer['report']['path']];assigned=layer['assigned_file_ids'];owned=set(assigned)
        need(report['schema']=='WP5_FOOTER_SHARD_V1' and report['actual_wholebody_SHA_computed'] is False
          and report['source_values_or_data_pages_read'] is False,'ACTUAL_FOOTER_ONLY_REPORT_SCHEMA')
        need(len(owned)==len(assigned) and owned<=remaining,'LAYER_REASSIGNED_COMPLETED_OR_DUPLICATE_SOURCE')
        need(not report['errors'],'SOURCE_FOOTER_ERROR_REQUIRES_SEPARATE_REVIEW_NOT_RETRY')
        done=[r['file_id'] for r in report['completed']];pending=report['pending_file_ids']
        need(len(done)==len(set(done)) and len(pending)==len(set(pending)),'DUPLICATE_LAYER_COVERAGE')
        need(not(set(done)&set(pending)) and set(done)|set(pending)==owned
          and report['expected_files']==len(assigned),'EXACT_LAYER_COMPLETED_PENDING_CONSERVATION')
        cursor=0
        for row in report['completed']:
            source=sources[row['file_id']]
            need(row['producer_reference']==triple(source) and row['source_kind']==source['source_kind']
              and row['family']==source['family'] and row['physical_rows']==source['rows'],'REUSED_SOURCE_LINEAGE_OR_ROW_MASS_DIFFERS')
            need(row['gzip_member_byte_lo']==cursor and row['gzip_member_byte_hi']>cursor,'CLOSED_GZIP_MEMBERS_EXACT_ORDER')
            cursor=row['gzip_member_byte_hi'];completed[row['file_id']]=dict(row,inventory_reference=report['inventory'])
        need(cursor==report['inventory']['bytes'],'CLOSED_MEMBERS_EXACT_STREAM_BYTES')
        remaining.difference_update(done);streams.append(report['inventory']);jobs.add(str(report['runtime']['job_id']))
    return completed,sorted(remaining),unique(streams),sorted(jobs)


def data_cap(whole,streams,reports,prior_jobs):
    # All reused streams/reports are charged once, plus conservative per-job
    # observer/admin envelopes. They stay in place; no copy or hardlink.
    inherited=sum(r['bytes'] for r in unique(streams))+sum(r['bytes'] for r in unique(reports))+(80<<20)*len(prior_jobs)
    available=whole-inherited-(80<<20)
    need(whole==8<<30 and available>0,'EIGHT_GIB_CUMULATIVE_CAP_NOT_A_FULL_GUARANTEE')
    return available,inherited


def terminal_accounting(path,raw_path,proof,manifest,manifest_path):
    accounting=load(path);need(accounting['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and accounting['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and accounting['query_returncode']==0
      and accounting['uid']==1278,'ACTUAL_MAIN_TERMINAL_ACCOUNTING_REQUIRED')
    raw=pin(raw_path);need(raw==accounting['raw_sacct_reference'],'EXACT_RAW_ACCOUNTING_REQUIRED')
    parents=[p for p in accounting['parents'] if str(p['job_id'])==str(proof['job_id'])]
    need(len(parents)==1,'ONE_EXACT_OLD_ACTUAL_PARENT')
    parent=parents[0]
    need(parent['state'] in ('FAILED','COMPLETED') and parent['alloc_cpus']==16,'TERMINAL_OLD_PARENT_NOT_FAKE_C0')
    if parent['state']=='COMPLETED':need(parent['exit_code']=='0:0','COMPLETED_REQUIRES_ACTUAL_ZERO')
    text=Path(raw_path).read_text(encoding='utf-8-sig').splitlines();need(text,'RAW_SACCT_HEADER_REQUIRED')
    header=text[0].split('|');rows=[dict(zip(header,line.split('|'))) for line in text[1:] if line.split('|')[0]==str(proof['job_id'])]
    need(len(rows)==1 and rows[0]['State']==parent['state'] and rows[0]['ExitCode']==parent['exit_code']
      and rows[0]['AllocCPUS']=='16' and rows[0]['UID']=='1278','RAW_TERMINAL_FIELDS_DIFFER')
    request=proof['request'];need(load(require(proof['request_reference']))==request,'ACTUAL_HISTORICAL_REQUEST_COPY')
    argv=request['execution_argv'];need(argv.count('--output')==1
      and Path(argv[argv.index('--output')+1])==Path(manifest_path).parent,'HISTORICAL_JOB_OUTPUT_BINDING')
    need(argv.count('--config')==1 and argv[argv.index('--config')+1]==manifest['config']['path']
      and manifest['config'] in request['source_references'] and request['cpus']==16
      and request['kind']=='analysis','HISTORICAL_JOB_CONFIG_SOURCE_BINDING')
    need(manifest['status']=='FOOTER_INVENTORY_PARTIAL_PENDING' and not manifest['errors'],'RESOURCE_PARTIAL_ONLY_NOT_SOURCE_ERRORS')
    return parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('previous-manifest','previous-startup-proof','previous-accounting','previous-raw-accounting',
              'resource-authority','metadata-directory','output','reason'):p.add_argument('--'+k,required=True)
    p.add_argument('--approve',action='store_true');a=p.parse_args()
    need(a.approve and a.reason.strip(),'EXPLICIT_ROOT_REVIEW_REQUIRED')
    need(Path(__file__).absolute().parent==REPO/'workflows/data_v1_final/labels/footer_continuation_v1','ACTUAL_ROOT_METADATA_ENTRY')
    manifest=load(a.previous_manifest);proof=load(a.previous_startup_proof)
    parent=terminal_accounting(a.previous_accounting,a.previous_raw_accounting,proof,manifest,a.previous_manifest)
    config_ref=manifest['config'];old=load(require(config_ref));book_ref=manifest['source_inventory_reference'];book=load(require(book_ref))
    need(len(book['files'])==2208 and len({r['path'] for r in book['files']})==2208,'UNCHANGED_SOURCE_BOOK')
    need(old['one_footer_cap_bytes']==128<<20 and old['one_source_serialized_cap_bytes']==64<<20
      and old['worker_rss_soft_cap_bytes']==3<<30,'UNCHANGED_FOOTER_AND_WORKER_SOFTWARE_CAPS')
    if manifest['schema']=='WP5_FOOTER_INVENTORY_V1':
        byid={s['shard_id']:s['file_ids'] for s in book['shards']}
        layers=[{'report':r['report'],'assigned_file_ids':byid[r['shard_id']]} for r in manifest['shards']]
    else:
        need(manifest['schema']=='WP5_FOOTER_CONTINUATION_V1','EXPLICIT_SUPPORTED_PARENT_SCHEMA');layers=manifest['layers']
    reports={r['report']['path']:load(require(r['report'])) for r in layers}
    completed,pending,streams,jobs=partition(book,layers,reports)
    need(len(completed)==manifest['observed_files'] and set(pending)==set(manifest['pending_file_ids'])
      and len(pending)>0 and len(jobs)>=1,'OLD_ACTUAL_PARTIAL_COVERAGE_DIFFERS')
    current_layers=[r for r in layers if str(reports[r['report']['path']]['runtime']['job_id'])==str(proof['job_id'])]
    need(len(current_layers)==16 and len({reports[r['report']['path']]['pid'] for r in current_layers})==16
      and all(reports[r['report']['path']]['runtime']['uid']==1278 for r in current_layers),'OLD_SIXTEEN_ACTUAL_WORKERS')
    fixture_ref=manifest.get('fixture_gate',manifest.get('original_three_fixture_gate'))
    fixture=load(require(fixture_ref));need(fixture['status']=='PASS' and fixture['tests_run']==3,'OLD_THREE_BOUNDARIES_ACTUAL_PASS')
    cap,inherited=data_cap(8<<30,streams,[r['report'] for r in layers],jobs)
    bysource={r['file_id']:r for r in book['files']};shards=[{'shard_id':i,'file_ids':[]} for i in range(16)];cost=[0]*16
    for i in sorted(pending,key=lambda i:(-bysource[i]['rows'],i)):
        target=min(range(16),key=lambda j:(cost[j],j));shards[target]['file_ids'].append(i);cost[target]+=bysource[i]['rows']
    parameters={'files':2208,'label_files':2024,'base_files':184,'workers':16,'reused_completed_files':len(completed),
      'pending_sources_only':len(pending),'previous_manifest_sha256':pin(a.previous_manifest)['sha256'],
      'previous_actual_parent_job_id':str(proof['job_id']),'new_masks':False,'payload_values_read':False,'final_D4':False}
    out=Path(a.output).absolute();directory=Path(a.metadata_directory).absolute()
    need(RUN/'artifacts/labels/source_status_v1' in out.parents and not out.exists()
      and RUN in directory.parents and not directory.exists(),'FRESH_OWNED_METADATA_AND_OUTPUT')
    directory.mkdir(parents=True,mode=0o700)
    history=unique([pin(a.previous_manifest),config_ref,book_ref,pin(a.previous_startup_proof),proof['request_reference'],
      pin(a.previous_accounting),pin(a.previous_raw_accounting),fixture_ref,*[r['report'] for r in layers],pin(a.resource_authority)])
    small=[*history,*old['small_references']]
    for r in unique(small):require(r)
    sources=unique([*old['source_references'],*small,*[pin(q) for q in Path(__file__).parent.glob('*.py')],
      *[pin(q) for q in (REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')]])
    for r in sources:require(r)
    plan=save(directory/'pending_plan.json',{'schema':'WP5_FOOTER_PENDING_PLAN_V1','shards':shards,'layers':layers,
      'previous_manifest_reference':pin(a.previous_manifest),'history_references':history,'inherited_jobs':jobs,
      'completed_files':len(completed),'pending_files':len(pending),'inherited_stream_references':streams})
    cfg={'schema':'WP5_FOOTER_CONTINUATION_CONFIG_V1','scope_parameters':parameters,'workers':16,
      'source_inventory_reference':book_ref,'pending_plan_reference':plan,'previous_manifest_reference':pin(a.previous_manifest),
      'source_references':sources,'small_references':unique(small+[plan]),
      'one_footer_cap_bytes':old['one_footer_cap_bytes'],'one_source_serialized_cap_bytes':old['one_source_serialized_cap_bytes'],
      'worker_rss_soft_cap_bytes':old['worker_rss_soft_cap_bytes'],'whole_output_cap_bytes':8<<30,
      'compressed_member_data_cap_bytes':cap,'charged_inherited_metadata_bytes':inherited,
      'observer_reserve_bytes':64<<20,'summary_admin_reserve_bytes':16<<20,'output_inode_cap':128}
    config=save(directory/'config.json',cfg)
    binding={'schema':'WP5_FOOTER_CONTINUATION_RESOURCE_BINDING_V1','scientific_config_reference':config,'scope_key':SCOPE,
      'scope_parameters':parameters,'resource_authority_reference':pin(a.resource_authority),'memavailable_soft_floor_bytes':4<<30,
      'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(out)+'_resource_observation','software_scan_worker_cap_bytes':3<<30}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.footer_continuation_v1.run','--config',config['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(out)]
    parents=[pin(a.previous_manifest),pin(a.previous_accounting),pin(a.previous_raw_accounting),pin(a.previous_startup_proof)]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'reason':a.reason,'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':False,
      'scope_key':SCOPE,'scope_parameters':parameters,'scope_mode':'BOUNDED_METADATA_PREPARATION','wall_seconds':3600,
      'estimated_peak_output_bytes':8<<30,'stage_output_cap_bytes':8<<30,'execution_argv':argv,'source_status_stage':None,
      'parent_evidence_references':parents,'previous_actual_parent':parent,'inherited_outputs_not_rewritten':True,
      'eight_GiB_is_ceiling_not_full_inventory_guarantee':True}
    rp=save(directory/'scope_review.json',review)
    data=unique([*streams,*[triple(bysource[i]) for i in pending]])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':3600,'estimated_peak_output_bytes':8<<30,
      'stage_output_cap_bytes':8<<30,'source_status_stage':None,'execution_argv':argv,'source_references':unique(sources+[plan,config,bp,rp]),
      'data_references':data,'scope_key':SCOPE,'scope_parameters':parameters,
      'scope':{'mode':'BOUNDED_METADATA_PREPARATION','review':rp,'parent_profile':None},'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec)
    save(directory/'preparation_receipt.json',{'status':'METADATA_ONLY_NOT_SUBMITTED','reused_files':len(completed),'pending_sources':len(pending),
      'whole_cap_bytes':8<<30,'new_compressed_member_cap_bytes':cap,'charged_inherited_metadata_bytes':inherited,
      'inherited_streams_BODY_not_statted_or_hashed_in_helper':True,'original_Parquet_not_opened_or_statted':True,
      'previous_actual_parent':parent,'old_FAILED_and_cost_retained':True,'SOURCEFINAL_not_actual_continuation_result':True})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','directory':str(directory),'reused':len(completed),'pending':len(pending)}))

if __name__=='__main__':main()
