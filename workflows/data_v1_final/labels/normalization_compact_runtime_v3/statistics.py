"""Exact SOURCE-TRAIN references, tails and winsorized descriptive moments. Not final Common."""
import argparse,collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,struct,time
from pathlib import Path
from . import contract as C,runtime as I,bindings as B,codec as K
from .reader import observations
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import stop_requested,soft_worker_rss,mark_stop
from workflows.data_v1_final.labels.streaming_v1.support import ParquetSink
WORK={}


def initialize(cfg,stage,root,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);fields=I.load(I.require(cfg['field_map_reference']))
    WORK.update(cfg=cfg,stage=stage,root=Path(root),barrier=barrier,fields=fields)


def _group_pass(item):
    group,first=item;cfg=WORK['cfg'];stage=WORK['stage'];purpose=cfg['statistics_purpose']
    if first:WORK['barrier'].wait(timeout=300)
    C.need(not stop_requested(),'SOFT_RESOURCE_STOP_NO_NEW_LOGICAL_GROUP');out=WORK['root']/('group_%04d'%group['group_index']);out.mkdir()
    hist={name:B.RadixCounts(query) for name,query in stage['queries'].items()}
    # Created once here, outside the continuous source generator; never reset at a part/RG/window.
    qr={str(f['field_id']):B.TSQR(cfg['element_basis']) for f in WORK['fields'] if f['element_reference_eligible']}
    counts=collections.defaultdict(collections.Counter);hashes={str(f['field_id']):hashlib.sha256() for f in WORK['fields']};mass=hashlib.sha256();rows=0;roles=collections.Counter()
    bykey={r['key']:r['field_id'] for r in stage['catalog']};moments={};joint={};series_mass=collections.Counter()
    if purpose=='normalization_moments':
        moments={sid:B.WinsorMoments(q['lower'],q['upper']) for sid,q in stage['quantiles'].items() if q['n']}
    started=time.monotonic()
    for owner,numbers,entries in observations(cfg,group,WORK['fields'],hash_sources=True,include_all_roles=True):
        C.need(not stop_requested(),'SOFT_RESOURCE_STOP_INCOMPLETE_GROUP_NO_STATISTIC_ACCEPTANCE');rows+=1;role=owner['new_role'];roles[role]+=1
        for e in entries:
            fid=str(e['field_id']);valid=B.train_values(role,e['values_float64'],e['value_mask']);s=counts[fid]
            s['records']+=1;s['source_valid_records']+=bool(any(e['source_value_mask']));s['valid_records']+=bool(any(e['value_mask']))
            s['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']));s['TRAIN_valid_leaves']+=len(valid)
            header=struct.pack('<QBHI',owner['record_ordinal'],B.TASKS[e['field']['task']],e['field_id'],len(e['value_mask']))+role.encode()+bytes(e['value_mask'])
            hashes[fid].update(header);mass.update(header)
            for v in valid:raw=struct.pack('<d',v);hashes[fid].update(raw);mass.update(raw)
            if purpose in ('legacy512','diagnostic_median_MAD'):
                for counter in hist.values():counter.add(e['field_id'],valid)
            if fid in qr and valid:C.need(len(valid)==1,'ORIGINAL_ENERGY_MOLECULE_SCALAR');qr[fid].add(numbers,valid[0])
        if purpose.startswith('normalization_') and role=='TRAIN':
            # Direct original views: raw, energy residual, atomic-by-Z and physical invariant series.
            values,physical_rows=B.views(entries,numbers,stage['physical'],stage['models'])
            for key,vals in values.items():
                C.need(key in bykey,'REGISTERED_ORIGINAL_SERIES_ONLY');sid=bykey[key];series_mass[str(sid)]+=len(vals)
                for counter in hist.values():counter.add(sid,vals)
                if purpose=='normalization_moments' and vals:moments[str(sid)].add(vals)
            if purpose=='normalization_moments':
                for key,vals in physical_rows.items():
                    if vals:joint.setdefault(key,B.JointMoments(len(vals[0]))).add(vals)
        soft_worker_rss(cfg['worker_rss_stop_bytes']);C.need(sum(len(h.counts) for h in hist.values())<=cfg['worker_histogram_row_cap'],'EXACT_RADIX_ROW_CAP_NOT_APPROXIMATION')
    import pyarrow as pa
    schema=pa.schema([('query',pa.string()),('field_id',pa.uint32()),('node_id',pa.string()),('prefix_bits',pa.uint8()),('prefix',pa.uint64()),('n',pa.uint64())])
    histogram=None
    if hist:
        sink=ParquetSink(schema,cfg['worker_serialized_buffer_cap_bytes'])
        for name,counter in hist.items():sink.add([dict(r,query=name) for r in counter.rows()])
        histogram=sink.close(out/'radix_counts.parquet',WORK['root'],cfg['whole_output_cap_bytes'])
    record={'group_index':group['group_index'],'source_job_id':group['source_job_id'],'pid':os.getpid(),'task_rows':rows,'role_task_counts':dict(roles),
      'field_counts':{k:dict(v) for k,v in counts.items()},'field_input_sha256':{k:v.hexdigest() for k,v in hashes.items()},'masked_source_TRAIN_input_sha256':mass.hexdigest(),
      'energy_TSQR':{k:v.state() for k,v in qr.items()},'radix_histogram':histogram,'series_mass':dict(series_mass),
      'moments':{sid:B.moment_state(m) for sid,m in moments.items()},'joint':{key:m.state() for key,m in joint.items()},
      'TSQR_chunk':256,'QR_created_once_per_original_group':True,'physical_parts_do_not_create_QR_groups':True,
      'elapsed_seconds':time.monotonic()-started,'statistics_purpose':purpose,'final_Common_D4':False}
    return I.save(out/'report.json',record)


def group_pass(item):
    try:return _group_pass(item)
    except BaseException as exc:
        mark_stop('COMPACT_STATISTICS_GROUP_PENDING_NO_NEW_GROUP',{'error':repr(exc),'group_index':item[0]['group_index']})
        raise


def histogram_rows(reports,name):
    import pyarrow.parquet as pq
    merged=collections.Counter()
    for report in reports:
        if report['radix_histogram'] is None:continue
        src=pq.ParquetFile(I.require(report['radix_histogram']))
        try:
            for batch in src.iter_batches(batch_size=4096,use_threads=False):
                for row in batch.to_pylist():
                    if row['query']==name:merged[(row['field_id'],row['node_id'],row['prefix_bits'],int(row['prefix']))]+=row['n']
                C.need(len(merged)<=1000000,'BOUNDED_EXACT_PARENT_HISTOGRAM_KEYS')
        finally:src.close()
    return [{'field_id':f,'node_id':n,'prefix_bits':b,'prefix':p,'n':v} for (f,n,b,p),v in sorted(merged.items())]


def legacy_compare(cfg,reports):
    import pyarrow.parquet as pq
    old=I.load_data(cfg['matched_legacy_profile_reference']);C.need(old['mode']=='pilot' and old['phase']=='profile','REAL_ORIGINAL512_PROFILE_ORACLE')
    expected={}
    for ref in old['group_receipts']:
        row=I.load_data(ref);C.need(row['status']=='SOURCE_GROUP_SCANNED' and row['group_index'] not in expected,'ALL_ORIGINAL_LEGACY_GROUPS');expected[row['group_index']]=row
    C.need(set(expected)=={r['group_index'] for r in reports},'EXACT16_ORIGINAL_GROUPS')
    for row in reports:
        oracle=expected[row['group_index']];src=pq.ParquetFile(I.require(oracle['radix_histogram']))
        try:oldrows=[r for batch in src.iter_batches(batch_size=4096,use_threads=False) for r in batch.to_pylist()]
        finally:src.close()
        observed=histogram_rows([row],'raw');key=lambda r:(r['field_id'],r['node_id'],r['prefix_bits'],int(r['prefix']))
        C.need(sorted(observed,key=key)==sorted(oldrows,key=key) and row['energy_TSQR']==oracle['energy_TSQR'],'EXACT_LEGACY_HISTOGRAM_AND256_TSQR_STATE_NO_TOLERANCE')
    return True


def initial_stage(cfg,fields):
    purpose=cfg['statistics_purpose'];catalog,physical=B.inventory({'fields':fields,'plan':{'element_basis':cfg['element_basis']}})
    C.need(len(catalog)<=100000,'FROZEN_SERIES_SOFTWARE_CAP');models=I.load_data(cfg['element_models_reference']) if cfg.get('element_models_reference') else {}
    if cfg.get('query_stage_reference'):
        stage=I.load_data(cfg['query_stage_reference']);C.need(stage['coverage_reference']==cfg['coverage_reference'] and stage['field_map_reference']==cfg['field_map_reference']
          and stage['statistics_purpose']==purpose and stage['element_models_reference']==cfg.get('element_models_reference'),'EXACT_QUERY_SOURCE_FIELD_MODEL_AND_PURPOSE_CONTINUATION')
        C.need(stage['queries'],'NO_REEXECUTION_OF_FINISHED_QUERY_STAGE');return dict(stage,models=models,catalog=catalog,physical=physical)
    queries={};finished={}
    if purpose=='legacy512':
        q=I.load_data(cfg['matched_legacy_query_reference']);C.need(q['purpose']=='median' and q['round']==0,'EXACT_LEGACY_INITIAL_QUERY');queries={'raw':q};finished={'median':[],'MAD':[]}
    elif purpose=='diagnostic_median_MAD':queries={'raw':B.initial_queries(fields,'median')};finished={'median':[],'MAD':[]}
    elif purpose=='normalization_quantiles':
        queries={'lower':B.initial_queries(catalog,'lower_tail',probability='0.001'),'upper':B.initial_queries(catalog,'upper_tail',probability='0.999')};finished={'lower':[],'upper':[]}
    quantiles={}
    if purpose=='normalization_moments':
        tail=I.load_data(cfg['exact_tail_reference']);C.need(tail['coverage_reference']==cfg['coverage_reference'] and tail['field_map_reference']==cfg['field_map_reference']
          and tail['element_models_reference']==cfg['element_models_reference'] and tail['catalog']==catalog,'EXACT_001_999_SERIES_AND_TRAIN_ELEMENT_MODEL')
        quantiles=tail['quantiles']
    return {'queries':queries,'finished':finished,'models':models,'catalog':catalog,'physical':physical,'quantiles':quantiles}


def exact_tails(catalog,finished):
    low={r['field_id']:r for r in finished['lower']};high={r['field_id']:r for r in finished['upper']}
    C.need(set(low)==set(high)=={r['field_id'] for r in catalog},'ALL_ORIGINAL_SERIES_EXACT_TAIL_COVERAGE')
    out={}
    for sid in sorted(low):
        a,b=low[sid],high[sid];C.need(a['n']==b['n'] and (not a['n'] or a['value'] is not None and b['value'] is not None and a['value']<=b['value']),'EXACT_TAIL_MASS_AND_ORDER')
        out[str(sid)]={'n':a['n'],'lower':a['value'],'upper':b['value'],'lower_probability':'0.001','upper_probability':'0.999','method':'exact float64 type-7 quantiles'}
    return out


def moment_result(stage,reports,fields):
    series=[]
    for row in stage['catalog']:
        sid=str(row['field_id']);q=stage['quantiles'][sid]
        states=[r['moments'].get(sid,{'n':0,'mean':'0','M2':'0'}) for r in reports];value=B.combine(states)
        C.need(value['n']==q['n']==sum(r['series_mass'].get(sid,0) for r in reports),'EXACT_WINSORIZED_MOMENT_TAIL_AND_LEAF_MASS')
        series.append({**row,**q,**value})
    bykey={r['key']:r for r in series}
    for f in fields:
        if f['level'] in ('atom','atom_vector'):
            fid=str(f['field_id']);C.need(sum(bykey[fid+'/raw/Z'+str(z)]['n'] for z in stage['element_basis'])==bykey[fid+'/raw']['n'],'GLOBAL_ATOM_AND_ELEMENT_LEAF_MASS')
    keys=sorted({k for r in reports for k in r['joint']});joint={k:B.combine_joint([r['joint'][k] for r in reports if k in r['joint']]) for k in keys}
    return {'series':series,'raw_complete_physical_joint_audit':joint,'fit_role':'TRAIN_ONLY','source_labels_modified':False,
      'winsorization':'q0.001/q0.999 only statistical copies; original cache/labels unchanged','element_reference_models':stage['models'],
      'per_element_atomic_statistics':True,'final_Common_D4':False,'joint_model_policy_release_reference':None,
      'vector_tensor_single_scale_training_route':'PENDING_ACTUAL_JOINT_POLICY_RELEASE','Pprime_status':'PENDING_REAL_INDEPENDENT_SOURCE'}


def execute(cfg,proof,root,gate):
    coverage=I.load(I.require(cfg['coverage_reference']));C.need(coverage['status']=='EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS' and not coverage['quality_hold_fields'] and not coverage['errors'],'FULL_BOUND_CACHE_AUTHORITY')
    path=I.require(coverage['parts_catalog']);cfg['catalog_frame']=identity(path);I.require(cfg['canonical_index'])
    plan=I.load(I.require(cfg['logical_group_plan_reference']));groups=plan['groups'];fields=I.load(I.require(cfg['field_map_reference']))
    C.need(len(groups)>=16 and len({g['source_job_id'] for g in groups})==len(groups),'UNSPLIT_ORIGINAL_LOGICAL_GROUPS')
    stage=initial_stage(cfg,fields);stage['element_basis']=cfg['element_basis'];ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,stage,str(root),barrier)) as pool:
        refs=list(pool.map(group_pass,[(g,k<16) for k,g in enumerate(groups)],chunksize=1))
    reports=[I.load(I.require(r)) for r in refs];C.need(len(reports)==len(groups) and len({r['pid'] for r in reports})==16,'ACTUAL16_WORKERS_AND_COMPLETE_ORIGINAL_GROUPS')
    # Original list order, not arrival/physical parts: exact original ordered left fold.
    models={str(f['field_id']):B.merge_qr([r['energy_TSQR'][str(f['field_id'])] for r in reports]) for f in fields if f['element_reference_eligible']}
    if cfg['statistics_purpose'].startswith('normalization_'):C.need(K.canonical(models)==K.canonical(stage['models']),'RECOMPUTED_ORIGINAL_GROUP_REFERENCE_MUST_MATCH_ACTUAL_PARENT_MODELS')
    model_ref=I.save(root/'SOURCE_TRAIN_element_models.json',models)
    legacy=legacy_compare(cfg,reports) if cfg['statistics_purpose']=='legacy512' else None
    masses=[{'group_index':r['group_index'],'field_input_sha256':r['field_input_sha256'],'masked_source_TRAIN_input_sha256':r['masked_source_TRAIN_input_sha256']} for r in reports]
    if 'source_mass_signature' in stage:C.need(stage['source_mass_signature']==masses,'SOURCE_ROLE_VALUE_MASK_ORDER_MASS_CHANGED_BETWEEN_RADIX_PASSES')
    queries={};finished={k:list(v) for k,v in stage['finished'].items()}
    for name,q in stage['queries'].items():
        nxt,done=B.advance(q,histogram_rows(reports,name));key=q['purpose'] if name=='raw' else name;finished[key].extend(done)
        if nxt['fields']:queries[name]=nxt
    diagnostic_ref=tail_ref=statistics_ref=None
    if cfg['statistics_purpose'] in ('legacy512','diagnostic_median_MAD') and not queries:
        purpose=stage['queries']['raw']['purpose']
        if purpose=='median':queries={'raw':B.initial_queries(fields,'MAD',{r['field_id']:r['value'] for r in finished['median'] if r['value'] is not None})}
        else:
            med={r['field_id']:r for r in finished['median']};mad={r['field_id']:r for r in finished['MAD']}
            # Undefined median/MAD remain explicit; no invented scale.
            vals={str(f['field_id']):{'median':med[f['field_id']]['value'],'MAD':mad.get(f['field_id'],{}).get('value'),
              'TRAIN_n':med[f['field_id']]['n'],'MAD_n':mad.get(f['field_id'],{}).get('n',0)} for f in fields}
            diagnostic_ref=I.save(root/'SOURCE_TRAIN_diagnostic_median_MAD.json',{'fields':vals,'purpose':'GUIDE1_5_DIAGNOSTICS_NOT_D4_NORMALIZER','coverage_reference':cfg['coverage_reference']})
    if cfg['statistics_purpose']=='normalization_quantiles' and not queries:
        tail_ref=I.save(root/'SOURCE_TRAIN_exact001_999.json',{'coverage_reference':cfg['coverage_reference'],'field_map_reference':cfg['field_map_reference'],
          'element_models_reference':cfg['element_models_reference'],'catalog':stage['catalog'],'quantiles':exact_tails(stage['catalog'],finished),'source_labels_modified':False})
    if cfg['statistics_purpose']=='normalization_moments':statistics_ref=I.save(root/'SOURCE_TRAIN_winsorized_statistics.json',moment_result(stage,reports,fields))
    next_ref=None
    if queries:
        next_ref=I.save(root/'next_query_stage.json',{'schema':'COMPACT_NUMERIC_SOURCE_TRAIN_RADIX_STAGE_V1','coverage_reference':cfg['coverage_reference'],
          'field_map_reference':cfg['field_map_reference'],'statistics_purpose':cfg['statistics_purpose'],'element_models_reference':cfg.get('element_models_reference'),
          'queries':queries,'finished':finished,'source_mass_signature':masses,'final_Common_D4':False})
    result={'schema':'COMPACT_NUMERIC_TRAIN_STATISTICS_V1','status':'EXACT_SOURCE_TRAIN_STAGE_NOT_FINAL_COMMON_D4','config':I.small_ref(cfg['config_path']),
      'job_id':str(proof['job_id']),'mode':cfg['mode'],'statistics_purpose':cfg['statistics_purpose'],'coverage_reference':cfg['coverage_reference'],'fixture_gate':gate,
      'group_reports':refs,'legacy_exact_comparison':legacy,'next_query_stage':next_ref,'diagnostic_median_MAD_reference':diagnostic_ref,
      'element_reference_models_reference':model_ref,'element_models_reference':cfg.get('element_models_reference'),'exact_tail_reference':tail_ref,'winsorized_statistics_reference':statistics_ref,
      'statistic_scope':'SOURCE_TRAIN_ONLY_ALL_ROLE_SOURCE_CACHE_PRESERVED','TSQR_chunk':256,'QR_merge_order':'ORIGINAL_LOGICAL_OWNER_GROUP_LEFT_FOLD',
      'old1904_stays_TIMEOUT':True,'common_or_diagnostic_filters_applied':False,'Pprime_status':'PENDING_REAL_INDEPENDENT_SOURCE',
      'joint_model_policy_release_reference':None,'per_component_median_is_final_training_normalization':False,
      'vector_tensor_Frobenius_radial_single_scale_route':'PENDING_ACTUAL_JOINT_POLICY_RELEASE','normalization_completed':False,'D4_published':False,
      'automatic_next_stage_or_retry':False}
    C.need(I.unique_bytes(root)+(64<<20)+(2<<20)<=cfg['whole_output_cap_bytes'],'WHOLE_STATISTICS_OUTPUT_CAP');I.save(root/'manifest.json',result);return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','startup-proof','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();cfg,proof,binding=I.guard(a.config,a.startup_proof,'statistics');root=I.new_root(a.output)
    try:
        gate=I.fixtures(root);cfg['config_path']=a.config;budget=I.Budget(cfg,proof,binding,root)
        try:return execute(cfg,proof,root,gate)
        finally:budget.close()
    except BaseException as exc:I.failed(root,exc);raise

if __name__=='__main__':raise SystemExit(main())