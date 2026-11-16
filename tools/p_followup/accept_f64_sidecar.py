"""B3: fixed42961 physical records, actual current/baseline loaders, two target recipes."""
import importlib,importlib.util,pathlib,pickle,sys,time
import numpy as np
import pyarrow.dataset as pad
from resources import REPO,R,CONTROL,OLD,SIDE,load,save,guard
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset


def same(a,b):
    return a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()

def baseline_dataset_class():
    name='followup_existing_p_recipe';directory=R/'MFM_p_recipe/current/phychem_mfm'
    spec=importlib.util.spec_from_file_location(name,directory/'__init__.py',submodule_search_locations=[str(directory)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return importlib.import_module(name+'.phase1.p_recipe_data').PRecipeDataset


def identities(c):
    path=CONTROL/'B3_frozen_current_identities.pkl'
    if path.exists():
        with path.open('rb') as stream:return pickle.load(stream)
    ids=load(OLD/'pilot_physical_ids.json');panels=load(OLD/'panel.json');manifest=load(pathlib.Path(c['root'])/'manifest.json');result={}
    for role,panel in panels.items():
        wanted={(r['molecule_id'],ids[role][r['molecule_id']][str(ci)]):int(ci) for r in panel for ci in r['allowed_conformers']}
        with (OLD/('current_graph_identities_'+role+'.pkl')).open('rb') as stream:cached=pickle.load(stream)
        mapping={k:v for k,v in cached['mapping'].items() if k in wanted};ambiguous=set(cached['ambiguous'])&wanted.keys();missing=set(wanted)-mapping.keys()
        split='TRAIN' if role=='TRAIN' else 'FULL';directory=pathlib.Path(manifest['split_roots'][split])
        if missing:
            expr=(pad.field('record_kind')=='P')&pad.field('molecule_id').isin(sorted({k[0] for k in missing}))&pad.field('native_record_id').isin(sorted({k[1] for k in missing}))
            options=pad.ParquetFragmentScanOptions(pre_buffer=False,buffer_size=1048576)
            scanner=pad.dataset(directory/'id_map.parquet',format='parquet').scanner(columns=['molecule_id','native_record_id','molecule_index','conformer_index'],filter=expr,batch_size=1024,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=options)
            for batch in scanner.to_batches():
                for r in batch.to_pylist():
                    key=(r['molecule_id'],r['native_record_id'])
                    if key not in missing:continue
                    if key in mapping:ambiguous.add(key)
                    else:mapping[key]=(int(r['molecule_index']),int(r['conformer_index']))
                guard()
        if ambiguous or set(mapping)!=set(wanted):raise ValueError(('Frozen physical identity incomplete/ambiguous',role,len(ambiguous),len(wanted)-len(mapping)))
        result[role]=[(mid,rid,oldci,int(mapping[(mid,rid)][0]),int(mapping[(mid,rid)][1])) for (mid,rid),oldci in wanted.items()]
        print('B3_POINT_IDENTITIES',role,len(result[role]),'reused',len(cached['mapping']),'new narrow metadata only',len(missing),flush=True)
    assert sum(map(len,result.values()))==42961
    guard()
    with path.open('wb') as stream:pickle.dump(result,stream,protocol=5)
    return result


def same(a,b):
    if a.dtype!=b.dtype or a.shape!=b.shape:return False
    return np.array_equal(a.view(np.uint8),b.view(np.uint8))


def main():
    guard(force=True);started=time.monotonic();c=load(REPO/'configs/p_followup/C_dedup.json')
    production=load(SIDE/'manifest.json');assert production['status']=='COMPLETE'
    requested=production['requested_fields'];enabled=production['enabled_fields']
    manifest=CONTROL/'B1_manifest_for_B3.json';save(manifest,production)
    records=identities(c);Baseline=baseline_dataset_class()
    with (OLD/'source_graph_scalars.pkl').open('rb') as stream:source=pickle.load(stream)
    pairs=load(OLD/'pairs.json');ids=load(OLD/'pilot_physical_ids.json');result=dict(status='RUNNING',records=sum(map(len,records.values())),source_baseline=str(R/'MFM_p_recipe/current/phychem_mfm/phase1/p_recipe_data.py'),B1_field_status=production['field_status'],recipes={})
    target_values={};target_valid={};valid_points={};times={};kwargs_by_role={}
    for recipe in ['D4','A1']:
        checks=dict(baseline_off_fields_checked=0,baseline_off_mismatch_records=0,baseline_off_fields={},nonselected_on_mismatch_records=0,nonselected_on_fields={},records=0)
        values_by_role={};valid_by_role={};norms={}
        for role,rows in records.items():
            kwargs=dict(root=c['root'],split='TRAIN' if role=='TRAIN' else 'FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),source='PM7',k=10,molecule_indices=sorted({r[3] for r in rows}),label_parameters=c.get('label_parameters') if recipe=='A1' else None)
            off=PRecipeDataset(**kwargs);on=PRecipeDataset(**kwargs,p_f64_sidecar=str(manifest));baseline=Baseline(**kwargs)
            values={};valid={}
            for i,(mid,rid,oldci,mi,ci) in enumerate(rows):
                a=off.read(mi,ci);b=on.read(mi,ci);original=baseline.read(mi,ci)
                fields={n:t for n,t in a['targets'].items() if t.group=='P'};assert len(fields)==109
                baseline_bad=[];unchanged_bad=[]
                for name,t in fields.items():
                    u=original['targets'][name];v=b['targets'][name]
                    if not all([same(t.raw,u.raw),same(t.values,u.values),same(t.valid,u.valid)]):baseline_bad.append(name)
                    checks['baseline_off_fields_checked']+=1
                    if name not in requested and not all([same(t.raw,v.raw),same(t.values,v.values),same(t.valid,v.valid)]):unchanged_bad.append(name)
                for n in baseline_bad:checks['baseline_off_fields'][n]=checks['baseline_off_fields'].get(n,0)+1
                for n in unchanged_bad:checks['nonselected_on_fields'][n]=checks['nonselected_on_fields'].get(n,0)+1
                checks['baseline_off_mismatch_records']+=bool(baseline_bad);checks['nonselected_on_mismatch_records']+=bool(unchanged_bad);checks['records']+=1
                key=(mid,rid);values[key]={};valid[key]={}
                for name in requested:
                    t=b['targets'][name];values[key][name]=float(t.values.flat[0]);valid[key][name]=bool(t.valid.all())
                    f=next(f for f in on.view.fields if f['name']==name);norms[name]=f.get('normalization',on.view.normalizations.get(name))
                if i%1000==0:guard();print('B3_READ',recipe,role,i,len(rows),flush=True)
            off.close();on.close();baseline.close();values_by_role[role]=values;valid_by_role[role]=valid;kwargs_by_role[role]=kwargs
        fields={n:dict(source_nonzero_pairs=0,normalized_zero_pairs=0,numerical_failures=0,max_absolute_error=0.) for n in requested}
        for role,conformer in pairs.items():
            for pair in conformer['conformer']:
                mid=pair['molecule_id'];ra=ids[role][mid][str(pair['a'])];rb=ids[role][mid][str(pair['b'])]
                ka,kb=(mid,ra),(mid,rb)
                for name in requested:
                    va=source[role][mid][ra].get(name);vb=source[role][mid][rb].get(name)
                    if va is None or vb is None or not np.isfinite(va) or not np.isfinite(vb) or va==vb:continue
                    if not valid_by_role[role][ka][name] or not valid_by_role[role][kb][name]:continue
                    reference=(float(va)-float(vb))/float(np.asarray(norms[name]['scale']).flat[0]);actual=values_by_role[role][ka][name]-values_by_role[role][kb][name]
                    error=abs(actual-reference);f=fields[name];f['source_nonzero_pairs']+=1;f['normalized_zero_pairs']+=int(actual==0);f['numerical_failures']+=int(error>1e-6+1e-5*abs(reference));f['max_absolute_error']=max(f['max_absolute_error'],error)
        for name,f in fields.items():f['passed']=bool(name in enabled and f['source_nonzero_pairs'] and f['normalized_zero_pairs']==0 and f['numerical_failures']==0 and not checks['baseline_off_mismatch_records'] and not checks['nonselected_on_mismatch_records'])
        result['recipes'][recipe]=dict(checks=checks,fields=fields);save(REPO/'results/p_followup/B3_acceptance.json',result);print('B3_RECIPE',recipe,fields,flush=True)
    # One20k pass per switch mode, same fixed physical records, A1 recipe, CPU only.
    benchmark=[(role,*row) for role,rows in records.items() for row in rows]
    order=np.random.default_rng(20261025).permutation(len(benchmark))[:20000];result['throughput']={}
    for mode in ['off','on']:
        data={role:PRecipeDataset(**kwargs,**({'p_f64_sidecar':str(manifest)} if mode=='on' else {})) for role,kwargs in kwargs_by_role.items()}
        begin=time.monotonic()
        for i in order:
            role,mid,rid,oldci,mi,ci=benchmark[int(i)];data[role].read(mi,ci)
        elapsed=time.monotonic()-begin;result['throughput'][mode]=dict(samples=20000,seconds=elapsed,samples_per_second=20000/elapsed,recipe='A1',population='frozen TRAIN+VAL physical records',order_seed=20261025,passes=1)
        for ds in data.values():ds.close()
        print('B3_THROUGHPUT',mode,result['throughput'][mode],flush=True)
    passed=[n for n in requested if all(result['recipes'][r]['fields'][n]['passed'] for r in ['D4','A1'])]
    result.update(status='COMPLETE' if len(passed)==len(requested) else 'UNRESOLVED_FIELDS',accepted_fields=passed,seconds=time.monotonic()-started)
    save(REPO/'results/p_followup/B3_acceptance.json',result)
    production['B3_acceptance']=str(REPO/'results/p_followup/B3_acceptance.json');production['B1_enabled_fields']=list(enabled);production['enabled_fields']=passed
    for name in requested:
        production['field_status'][name]['B3_status']='COMPLETE' if name in passed else 'UNRESOLVED'
    save(SIDE/'manifest.json',production);save(REPO/'configs/p_followup/B_sidecar_manifest.json',production)
    print('B3_COMPLETE',result['status'],passed,flush=True)
if __name__=='__main__':main()