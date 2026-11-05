"""Original exact normalization math; taskbook v2 source and scheduling seams."""
import collections,json,os,time
from pathlib import Path
from ..common_train_normalization_day_v1 import bindings as B
from ..normalization_compact_runtime_v3 import codec as K
from . import io as I
from .reader import observations
from .io import ParquetSink

class C:
    @staticmethod
    def need(value,message):
        if not value:raise ValueError(message)

WORK={}

def initialize(cfg,stage,root):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    WORK.update(cfg=cfg,stage=stage,root=Path(root),fields=I.load_data(cfg['field_map_reference']))


def group_pass(work):
    cfg,stage,root,group=work
    initialize(cfg,stage,root)
    return _group_pass((group,False))

def _group_pass(item):
    group,first=item;cfg=WORK['cfg'];stage=WORK['stage'];purpose=cfg['statistics_purpose']
    out=WORK['root']/('group_%04d'%group['group_index']);out.mkdir();cfg['group_output_root']=str(out)
    hist={name:B.RadixCounts(query) for name,query in stage['queries'].items()}
    # Created once here, outside the continuous source generator; never reset at a part/RG/window.
    qr={str(f['field_id']):B.TSQR(cfg['element_basis']) for f in WORK['fields'] if f['element_reference_eligible'] and purpose=='element_reference'}
    counts=collections.defaultdict(collections.Counter);rows=0;roles=collections.Counter()
    bykey={r['key']:r['field_id'] for r in stage['catalog']};moments={};joint={};series_mass=collections.Counter()
    if purpose=='normalization_moments':
        moments={sid:B.WinsorMoments(q['lower'],q['upper']) for sid,q in stage['quantiles'].items() if q['n']}
    started=time.monotonic()
    for owner,numbers,entries in observations(cfg,group,WORK['fields'],hash_sources=False,include_all_roles=True):
        rows+=1;role='TRAIN' if owner['fit_eligible'] else 'FULL';roles[role]+=1
        for e in entries:
            fid=str(e['field_id']);valid=B.train_values(role,e['values_float64'],e['value_mask']);s=counts[fid]
            s['records']+=1;s['source_valid_records']+=bool(any(e['source_value_mask']));s['valid_records']+=bool(any(e['value_mask']))
            s['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']));s['TRAIN_valid_leaves']+=len(valid)
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
    import pyarrow as pa
    schema=pa.schema([('query',pa.string()),('field_id',pa.uint32()),('node_id',pa.string()),('prefix_bits',pa.uint8()),('prefix',pa.uint64()),('n',pa.uint64())])
    histogram=None
    if hist:
        sink=ParquetSink(schema,8<<20)
        for name,counter in hist.items():sink.add([dict(r,query=name) for r in counter.rows()])
        histogram=sink.close(out/'radix_counts.parquet',WORK['root'],None)
    record={'group_index':group['group_index'],'source_job_id':group['source_job_id'],'pid':os.getpid(),'task_rows':rows,'role_task_counts':dict(roles),
      'field_counts':{k:dict(v) for k,v in counts.items()},
      'r73_derived_reference':dict(I.ref(out/'r73_derived.sqlite'),group_index=group['group_index']) if (out/'r73_derived.sqlite').is_file() else None,
      'mask_override_reference':dict(I.ref(out/'mask_overrides.parquet'),group_index=group['group_index'],records=cfg.get('mask_override_rows',0),newly_masked_records=cfg.get('EA_newly_masked_records',0)) if (out/'mask_overrides.parquet').is_file() else None,
      'molecule_field_means_reference':I.ref(out/'molecule_field_means.parquet') if (out/'molecule_field_means.parquet').is_file() else None,
      'energy_TSQR':{k:v.state() for k,v in qr.items()},'radix_histogram':histogram,'series_mass':dict(series_mass),
      'moments':{sid:B.moment_state(m) for sid,m in moments.items()},'joint':{key:m.state() for key,m in joint.items()},
      'TSQR_chunk':256,'QR_created_once_per_original_group':True,'physical_parts_do_not_create_QR_groups':True,
      'elapsed_seconds':time.monotonic()-started,'statistics_purpose':purpose,'final_Common_D4':False}
    return I.save(out/'report.json',record)



def initial_stage(cfg,fields):
    purpose=cfg['statistics_purpose'];catalog,physical=B.inventory({'fields':fields,'plan':{'element_basis':cfg['element_basis']}})
    models=I.load_data(cfg['element_models_reference']) if cfg.get('element_models_reference') else {}
    if cfg.get('query_stage_reference'):
        stage=I.load_data(cfg['query_stage_reference']);C.need(stage['coverage_reference']==cfg['coverage_reference'] and stage['field_map_reference']==cfg['field_map_reference']
          and stage['eligibility_reference']==cfg['eligibility_reference'] and stage['input_release_reference']==cfg['input_release_reference'] and stage['statistics_purpose']==purpose and stage['element_models_reference']==cfg.get('element_models_reference'),'EXACT_QUERY_SOURCE_FIELD_MODEL_AND_PURPOSE_CONTINUATION')
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
          and tail['eligibility_reference']==cfg['eligibility_reference'] and tail['input_release_reference']==cfg['input_release_reference'] and tail['element_models_reference']==cfg['element_models_reference'] and tail['catalog']==catalog,'EXACT_001_999_SERIES_AND_TRAIN_ELEMENT_MODEL')
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


