"""Actual final-TRAIN heavy-count pairs, original views and original rho object."""
import collections,concurrent.futures as cf,hashlib,multiprocessing as mp,struct
from pathlib import Path
from . import contract as C,originals as O
from workflows.data_v1_final.labels.common_train_normalization_day_v1 import bindings as B,reader as R,io as I
WORK={}

def initialize(cfg,fields,models,rules,root):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);I.configure(cfg)
    catalog,physical=B.inventory({'fields':fields,'plan':{'element_basis':cfg['element_basis']}})
    available={row['key'] for row in catalog}
    for f in fields:
        rule=rules[f['field_key']]
        C.need(rule['method'] in ('ORIGINAL_VIEW_WEIGHTED_SPEARMAN','PHYSICAL_LOCAL_NOT_MOLECULE_SIZE_APPLICABLE'),
          'NO_UNAGREED_NONSCALAR_SIZE_AGGREGATION')
        if rule['method']=='ORIGINAL_VIEW_WEIGHTED_SPEARMAN':
            C.need(rule['series_key'] in available,'SIZE_VIEW_REQUIRES_ACTUAL_ORIGINAL_SERIES_BUILDER')
            if 'heat_of_formation' in f['source_path']:
                C.need(rule['series_key']==str(f['field_id'])+'/residual' and str(f['field_id']) in models,
                  'HOF_SIZE_RHO_ONLY_AFTER_REAL_TRAIN_ELEMENT_REFERENCE')
        else:C.need(f['level']!='molecule' and rule['definition_reference'],'NO_UNDEFINED_MOLECULE_SCALAR_SIZE_CLASSIFICATION')
    WORK.update(cfg=cfg,fields=fields,models=models,rules=rules,physical=physical,root=Path(root))

def group(group):
    import numpy as np,pyarrow as pa
    from workflows.data_v1_final.labels.common_train_normalization_day_v1.audit import Sink
    C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_FINAL_RHO_GROUP')
    root=WORK['root']/('group_%04d'%group['group_index']);root.mkdir()
    schema=pa.schema([('field_id',pa.uint16()),('value',pa.float64()),('heavy_atoms',pa.uint16()),('n',pa.uint64())])
    sink=Sink(root,'TRAIN_scalar_or_agreed_view_heavy_hist',schema);buffers=collections.defaultdict(list);counts=collections.Counter();digest=hashlib.sha256();records=0
    def flush(fid):
        pairs=buffers[fid]
        if not pairs:return
        a=np.asarray(pairs,dtype=[('value','<f8'),('heavy','<u2')]);unique,n=np.unique(a,return_counts=True)
        sink.add([{'field_id':fid,'value':float(v['value']),'heavy_atoms':int(v['heavy']),'n':int(k)} for v,k in zip(unique,n)]);pairs.clear()
    for owner,numbers,entries in R.observations(WORK['cfg'],group,WORK['fields'],hash_sources=True,include_all_roles=False):
        C.need(owner['fit_eligible'] and owner['effective_role']=='TRAIN' and owner['common_population'],'TRUE_FINAL_COMMON_TRAIN_ONLY_RHO')
        C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_FINAL_RHO_INCOMPLETE_GROUP')
        values,joint=B.views(entries,numbers,WORK['physical'],WORK['models']);heavy=sum(z>1 for z in numbers)
        C.need(0<=heavy<65536,'ORIGINAL_HEAVY_COUNT_HISTOGRAM_TYPE');records+=1
        for e in entries:
            f=e['field'];fid=f['field_id'];rule=WORK['rules'][f['field_key']]
            if rule['method']!='ORIGINAL_VIEW_WEIGHTED_SPEARMAN':continue
            key=rule['series_key'];C.need(key in values,'REGISTERED_SIZE_VIEW_AVAILABLE_IN_THIS_ORIGINAL_TASK')
            for v in values[key]:
                buffers[fid].append((v,heavy));counts[str(fid)]+=1;digest.update(struct.pack('<QHdH',owner['record_ordinal'],fid,v,heavy))
            if len(buffers[fid])>=4096:flush(fid)
    for fid in buffers:flush(fid)
    refs=sink.finish()
    return I.save(root/'report.json',{'schema':'FINAL_TRAIN_RHO_ORIGINAL_GROUP_V1','group_index':group['group_index'],
      'source_job_id':group['source_job_id'],'fit_task_rows':records,'field_pair_counts':dict(counts),'source_fit_value_sha256':digest.hexdigest(),
      'histogram_parts':refs,'no_VAL_FULL_EMBARGO_or_D5_heldout_fit':True,'new_scientific_formula':False})

def run(cfg,fields,models,rules,root,budget):
    import duckdb
    root=Path(root);root.mkdir();groups=C.D4.logical(I.load_data(cfg['logical_group_plan_reference'],2<<20)['groups'])
    refs=[];ctx=mp.get_context('spawn')
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,fields,models,rules,str(root))) as pool:
        iterator=iter(groups);pending={}
        def fill():
            budget.check()
            if I.stop_requested():return
            while len(pending)<16:
                try:g=next(iterator)
                except StopIteration:return
                pending[pool.submit(group,g)]=g['group_index']
        fill();saved={}
        while pending:
            done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
            for f in done:saved[pending.pop(f)]=f.result()
            I.save(root/('checkpoint_%04d.json'%len(saved)),{'schema':'FINAL_RHO_COMMITTED_GROUPS_V1','reports':[saved[k] for k in sorted(saved)],'no_independent_C0':True})
            fill()
        C.need(len(saved)==171,'SOFT_RESOURCE_STOP_FINAL_RHO_INCOMPLETE_NO_PUBLICATION');refs=[saved[k] for k in range(171)]
    reports=[I.load_data(r,16<<20) for r in refs];files=[ref['path'] for row in reports for ref in row['histogram_parts']]
    for row in reports:
        for ref in row['histogram_parts']:I.require(ref)
    registry,reducer,series,compact,masks=O.objects();db=duckdb.connect();db.execute('SET threads=1');results={}
    try:
        for field in fields:
            budget.check();rule=rules[field['field_key']]
            if rule['method']=='PHYSICAL_LOCAL_NOT_MOLECULE_SIZE_APPLICABLE':
                results[field['field_key']]={'rho':None,'pair_n':None,'status':'EXPLICIT_PHYSICAL_LOCAL_SIZE_CLASSIFICATION_NOT_APPLICABLE','definition_reference':rule['definition_reference']}
            else:
                value=reducer.rho_external(db,files,field['field_id'])
                C.need(value['status']=='DEFINED','UNDEFINED_REQUIRED_SIZE_RHO_NO_SILENT_NON_SIZE_DEFAULT')
                results[field['field_key']]={**value,'series_key':rule['series_key'],'HOF_element_reference_applied':'heat_of_formation' in field['source_path']}
    finally:db.close()
    return I.save(root/'TRAIN_size_spearman.json',{'schema':'FINAL_COMMON_TRAIN_SIZE_RHO_V1','fields':results,'threshold_abs_rho':.95,
      'original_weighted_rho_function_source':C.Q.pin(C.REPO/'workflows/data_v1_final/labels/streaming_v1/reduce.py'),
      'group_reports':refs,'fit_population':'FINAL_COMMON_EFFECTIVE_TRAIN_ANTI_D5','Root_Model_size_view_policy_explicit':True})
