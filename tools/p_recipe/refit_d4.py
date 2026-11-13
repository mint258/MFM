"""Refit the existing D4 algorithms after the user-approved molecule exclusion.

Original F64 typed sources, physical masks, TSQR groups, exact type7 tails,
WinsorMoments and median/MAD are reused. Only fit eligibility changes.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures as cf, json, multiprocessing as mp
import os, types
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/p_recipe_20261113'
REPO=Path(__file__).resolve().parents[2]

def fitted_owner(owner,excluded):
    if owner['molecule_id'] in excluded:
        return dict(owner,fit_eligible=False,fit_reason='P_RECIPE_APPROVED_DOWNSTREAM_EXCLUSION')
    return owner

def pm7_observations(cfg,group,fields,**unused):
    from workflows.data_v1_final.labels.window2_normalization_v1 import reader
    excluded=set(cfg['excluded_molecule_ids'])
    def effective(owner,side):return fitted_owner(reader.effective_owner(owner,side),excluded)
    source=reader.observations
    fn=types.FunctionType(source.__code__,dict(source.__globals__,effective_owner=effective),
        source.__name__,source.__defaults__,source.__closure__)
    yield from fn(cfg,group,fields,**unused)

def pprime_observations(cfg,group,fields,**unused):
    import pyarrow as pa,pyarrow.parquet as pq
    from workflows.data_v1_final.labels.window2_normalization_v1 import io as I
    from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
    byid={f['field_id']:f for f in fields};excluded=set(cfg['excluded_molecule_ids'])
    means=collections.defaultdict(lambda:[0,0.])
    for reference in group['typed_parts']:
        pf=pq.ParquetFile(I.require(reference),pre_buffer=False)
        try:
            for batch in pf.iter_batches(batch_size=32,use_threads=False):
                for row in batch.to_pylist():
                    owner=fitted_owner(dict(record_id=row['record_id'],molecule_id=row['molecule_id'],
                        fit_eligible=row['fit_eligible'],geometry_source='uff_sprime'),excluded)
                    entries=K.unpack_entries(row,byid)
                    for entry in entries:entry['field']=byid[entry['field_id']]
                    if cfg['statistics_purpose']=='normalization_moments' and owner['fit_eligible']:
                        for entry in entries:
                            values=[v for v,keep in zip(entry['values_float64'],entry['value_mask']) if keep]
                            if values:
                                item=means[owner['molecule_id'],entry['field_id']]
                                item[0]+=len(values);item[1]+=sum(values)
                    yield owner,row['atomic_numbers'],entries
        finally:pf.close()
    if cfg['statistics_purpose']=='normalization_moments':
        schema=pa.schema([('molecule_id',pa.string()),('field_id',pa.uint16()),('n',pa.uint64()),('sum',pa.float64()),('mean',pa.float64())])
        path=Path(cfg['group_output_root'])/'molecule_field_means.parquet'
        with pq.ParquetWriter(path,schema,compression='zstd') as writer:
            rows=[]
            for (mid,fid),(n,total) in sorted(means.items()):
                rows.append(dict(molecule_id=mid,field_id=fid,n=n,sum=total,mean=total/n))
                if len(rows)>=8192:writer.write_table(pa.Table.from_pylist(rows,schema=schema));rows=[]
            if rows:writer.write_table(pa.Table.from_pylist(rows,schema=schema))

def group_pass(work):
    import pyarrow as pa
    from workflows.data_v1_final.labels.window2_normalization_v1 import statistics as T,io as I
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    cfg,stage,root,group=work
    state=dict(cfg=cfg,stage=stage,root=Path(root),fields=I.load_data(cfg['field_map_reference']))
    source=T._group_pass
    reader=pm7_observations if cfg['dataset']=='P_D' else pprime_observations
    fn=types.FunctionType(source.__code__,dict(source.__globals__,WORK=state,observations=reader),
        source.__name__,source.__defaults__,source.__closure__)
    return fn((group,False))

def fit(dataset,output,workers):
    from workflows.data_v1_final.labels.window2_normalization_v1 import run as Original,io as I,statistics as T
    inputs=I.load(CONTROL/'refit_source_inputs.json')[dataset]
    corpus=I.load('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json')
    cfg=dict(inputs['inputs'],dataset=dataset,excluded_molecule_ids=corpus['excluded_molecule_ids'],workers=workers)
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    checkpoint=root/'checkpoint.json'
    if checkpoint.exists():
        state=I.load(checkpoint)
        scientific=lambda value:{k:v for k,v in value.items() if k!='workers'}
        if scientific(state['inputs'])!=scientific(cfg):
            raise ValueError('Retain the original closed inputs when resuming D4')
        state['inputs']=cfg
    else:
        state=dict(inputs=cfg,purpose_index=0,pass_index=0,active_stage=None,groups={},results={})
        I.save(checkpoint,state)
    groups=I.load_data(cfg['logical_group_plan_reference'])['groups']
    fields=I.load_data(cfg['field_map_reference'])
    with cf.ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn')) as pool:
        while state['purpose_index']<len(Original.ROUTES):
            purpose=Original.ROUTES[state['purpose_index']]
            current=dict(cfg,statistics_purpose=purpose)
            current.update({k:v for k,v in state['results'].items() if k in (
                'element_models_reference','exact_tail_reference','query_stage_reference','mask_overrides_reference','r73_derived_reference')})
            if state['active_stage'] is None:
                state['pass_index']+=1;stage_root=root/('pass_%04d'%state['pass_index']);stage_root.mkdir()
                stage=T.initial_stage(current,fields);stage['element_basis']=cfg['element_basis']
                state['active_stage']=I.save(stage_root/'stage.json',stage);state['groups']={};I.save(checkpoint,state)
            else:
                stage=I.load_data(state['active_stage']);stage_root=Path(state['active_stage']['path']).parent
            # A worker may finish before the interrupted parent records its reference.
            # Reports are atomically published only after all group outputs close.
            recovered={}
            for g in groups:
                key=str(g['group_index'])
                if key in state['groups']:continue
                for path in sorted(stage_root.glob('attempt_*/group_%04d/report.json'%g['group_index'])):
                    try:report=I.load(path)
                    except (OSError,ValueError):continue
                    if report.get('group_index')!=g['group_index'] or report.get('statistics_purpose')!=purpose:continue
                    state['groups'][key]=I.ref(path);recovered[key]=report;break
            I.save(checkpoint,state)
            print(json.dumps(dict(dataset=dataset,purpose=purpose,pass_index=state['pass_index'],
                resumed_groups=len(state['groups']),recovered_groups=len(recovered),workers=workers)),flush=True)
            attempt=0
            while (stage_root/('attempt_%03d'%attempt)).exists():attempt+=1
            attempt_root=stage_root/('attempt_%03d'%attempt);attempt_root.mkdir()
            pending={pool.submit(group_pass,(current,stage,str(attempt_root),g)):str(g['group_index'])
                     for g in groups if str(g['group_index']) not in state['groups']}
            for future in cf.as_completed(pending):
                key=pending[future];state['groups'][key]=future.result();I.save(checkpoint,state)
                print(json.dumps(dict(dataset=dataset,purpose=purpose,pass_index=state['pass_index'],
                    closed_groups=len(state['groups']),groups=len(groups))),flush=True)
            reports=[recovered[str(g['group_index'])] if str(g['group_index']) in recovered
                     else I.load_data(state['groups'][str(g['group_index'])]) for g in groups]
            if purpose=='element_reference' and dataset=='Pprime':
                models={str(f['field_id']):Original.B.merge_qr([r['energy_TSQR'][str(f['field_id'])]
                    for r in reports]) for f in fields if f['element_reference_eligible']}
                counts=collections.defaultdict(collections.Counter)
                for report in reports:
                    for fid,value in report['field_counts'].items():counts[fid].update(value)
                result=dict(element_models_reference=I.save(stage_root/'element_models.json',models),
                    validity_mask_counts_reference=I.save(stage_root/'validity_mask_counts.json',
                        dict(fields={fid:dict(v) for fid,v in counts.items()},geometry_source='uff_sprime',
                             physical_masks_reused=True,excluded_molecules=323)))
            else:
                result=Original.finish_stage(current,stage,stage_root,reports)
            state['results'].update(result)
            if 'query_stage_reference' not in result:
                state['purpose_index']+=1;state['results'].pop('query_stage_reference',None)
            state['active_stage']=None;state['groups']={};I.save(checkpoint,state)
    manifest=dict(schema='P_RECIPE_REPAIRED_D4',dataset=dataset,fit_role='TRAIN',
        status='PM7_P_D_TRAIN_STATISTICS_COMPLETE' if dataset=='P_D' else 'PPRIME_INDEPENDENT_TRAIN_STATISTICS_COMPLETE',
        inputs=cfg,statistics=state['results'],train_molecules=corpus['train_molecules'],excluded_molecules=323,
        algorithms='Original TSQR256/logical group reduction/exact type7 .001,.999/WinsorMoments/median MAD',
        original_labels_modified=False,identity_audit_repeated=False)
    I.save(root/'manifest.json',manifest)
    # Publish the small numerical products; large histograms remain in local scratch.
    shared=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED')/dataset
    shared.mkdir(parents=True,exist_ok=True)
    from shutil import copy2
    for key in ('element_models_reference','winsorized_statistics_reference','diagnostic_median_MAD_reference'):
        ref=manifest['statistics'][key];destination=shared/Path(ref['path']).name
        copy2(ref['path'],destination);manifest['statistics'][key]=I.ref(destination)
    I.save(shared/'manifest.json',manifest)
    return manifest

def publish_routes():
    from copy import deepcopy
    from workflows.data_v1_final.labels.window2_normalization_v1 import io as I
    from workflows.data_v1_final.labels.window2_normalization_publish_v1.run import build_dataset,pointer
    base=ROOT/'runs/data_v1_20261025/repository'
    cfg=I.load(ROOT/'runs/model_v31_20261105/M3_P_C1_0_seed0_micro32.APPROVED.json')
    routes=deepcopy(I.load(cfg['normalizations']))
    schema=I.load(Path(cfg['root'])/'schema.json')
    policy_path=base/'configs/data_v1/interfaces/D1_v3_0_user_frozen_design_policy_20261029_v1.json'
    policy=I.load(policy_path);policy_reference={'path':str(policy_path)}
    rules={}
    for tid,binding in I.load(base/'configs/data_v1/window2_D4_physical_route_bindings_v1.json')['targets'].items():
        ref=binding['policy_reference'];source=ref['path'] if isinstance(ref,dict) else ref
        rules[tid]=dict(binding,recipe=pointer(I.load(source),binding['json_pointer']))
    destination=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED')
    for name in ('P_D','Pprime'):
        manifest=I.load(destination/name/'manifest.json');cfg=manifest['inputs']
        fields=I.load_data(cfg['field_map_reference'])
        numerical=I.load_data(manifest['statistics']['winsorized_statistics_reference'])
        models=I.load_data(manifest['statistics']['element_models_reference'])
        routes['datasets'][name]=build_dataset(name,fields,numerical,models,schema,policy,policy_reference,rules)
        # Mask predicates are unchanged; retain their original shared catalogs.
        old=routes.get('source_references',{}).get(name,{})
        inherited=old.get('closed_training_stage_references',{}).get('mask_overrides_reference')
        ref=dict(manifest=str(destination/name/'manifest.json'),
            statistics=manifest['statistics']['winsorized_statistics_reference'],
            element_models=manifest['statistics']['element_models_reference'],fields=cfg['field_map_reference'])
        if inherited:ref['closed_training_stage_references']={'mask_overrides_reference':inherited}
        routes['source_references'][name]=ref
    routes.update(numeric_statistics_refitted=True,D4_complete=True,PM7_diagnostic_status='COMPLETE',
        PM7_diagnostics_continue=False,p_recipe_user_authorization='Exclude323, revise affected TRAIN/D4, continue',
        train_molecules=1194228,excluded_molecules=323,
        p_recipe_corpus='/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json')
    I.save(destination/'routes.json',routes)
    print(json.dumps(dict(status='REPAIRED_D4_ROUTES_PUBLISHED',path=str(destination/'routes.json'),
        train_molecules=1194228)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['P_D','Pprime'])
    p.add_argument('--output');p.add_argument('--workers',type=int,default=16);p.add_argument('--publish',action='store_true')
    a=p.parse_args()
    if a.publish:publish_routes()
    else:
        import fcntl
        # One dataset producer; a completed parallel fit is an ordinary resume.
        with (CONTROL/('D4_'+a.dataset+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            shared=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED')/a.dataset/'manifest.json'
            corpus=json.loads(Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json').read_text())
            expected=dict(json.loads((CONTROL/'refit_source_inputs.json').read_text())[a.dataset]['inputs'],dataset=a.dataset,excluded_molecule_ids=corpus['excluded_molecule_ids'])
            expected.pop('workers',None)
            prior=json.loads(shared.read_text()) if shared.is_file() else None
            if prior and {k:v for k,v in prior['inputs'].items() if k!='workers'}==expected:
                print(json.dumps(dict(status='REUSED_COMPLETED_D4',dataset=a.dataset,manifest=str(shared))),flush=True)
            else:fit(a.dataset,a.output,a.workers)
