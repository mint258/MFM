"""B2 engineering smoke on64 existing mapped MIDs; not the full B3 acceptance."""
import itertools,pickle,time
import numpy as np
from resources import REPO,OLD,CONTROL,load,save,guard
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset
from phychem_mfm.phase1.v31_loader import record_key,split_metadata

def main():
    guard(force=True);c=load(REPO/'configs/p_followup/C_dedup.json');names=load(REPO/'results/p_followup/B_field_selection.json')['selected_fields']
    with (OLD/'current_graph_identities_TRAIN.pkl').open('rb') as stream:mapping=pickle.load(stream)['mapping']
    with (OLD/'source_graph_scalars.pkl').open('rb') as stream:source=pickle.load(stream)['TRAIN']
    mids=set(sorted({k[0] for k in mapping})[:64]);records=sorted([(mi,ci,mid,rid) for (mid,rid),(mi,ci) in mapping.items() if mid in mids])
    path=CONTROL/'B2_subset';path.mkdir(exist_ok=True)
    dtype=[('molecule_index','<u4'),('conformer_index','<u2'),('record_handle','S7')]+[(n,'<f8') for n in names]
    table=np.zeros(len(records),dtype=dtype);directory,meta=split_metadata(__import__('pathlib').Path(c['root']),'TRAIN')
    offsets=np.zeros(meta['molecule_count']+1,dtype=np.int64)
    for i,(mi,ci,mid,rid) in enumerate(records):
        table[i]['molecule_index']=mi;table[i]['conformer_index']=ci;table[i]['record_handle']=record_key('P',mi,ci);offsets[mi+1]+=1
        for n in names:
            value=source[mid][rid].get(n);table[i][n]=value if value is not None else np.nan
    np.cumsum(offsets,out=offsets);np.save(path/'values.npy',table);np.save(path/'offsets.npy',offsets)
    manifest=path/'manifest.json';save(manifest,dict(status='SUBSET_TEST',enabled_fields=names,splits=dict(TRAIN=dict(D6_directory=str(directory),values=str(path/'values.npy'),molecule_offsets=str(path/'offsets.npy')))))
    results={}
    for route in ['D4','A1']:
        kwargs=dict(root=c['root'],split='TRAIN',training_view=c['training_view'],normalizations=load(c['normalizations']),source='PM7',k=10,molecule_indices=sorted({r[0] for r in records}),label_parameters=c['label_parameters'] if route=='A1' else None)
        off=PRecipeDataset(**kwargs);on=PRecipeDataset(**kwargs,p_f64_sidecar=str(manifest));stats={n:dict(comparable_pairs=0,normalized_zero_pairs=0,normalization_error_failures=0) for n in names};saved={};count=0
        for mi,ci,mid,rid in records:
            if ci not in off.choices(mi):continue
            a=off.read(mi,ci);b=on.read(mi,ci);count+=1
            targets={n:t for n,t in a['targets'].items() if t.group=='P'};assert len(targets)==109
            for n,t in targets.items():
                u=b['targets'][n];assert np.array_equal(t.valid,u.valid)
                if n not in names:np.testing.assert_array_equal(t.values.view('u4'),u.values.view('u4'))
                elif t.valid.all() and np.isfinite(table[n][offsets[mi]+next(j for j,x in enumerate(table[offsets[mi]:offsets[mi+1]]) if int(x['conformer_index'])==ci)]):
                    value=source[mid][rid][n]
                    np.testing.assert_array_equal(np.asarray(value,np.float32).reshape(t.raw.shape).view('u4'),t.raw.astype(np.float32).view('u4'))
                    assert u.raw.dtype==np.float64 and float(u.raw.flat[0])==value
            saved.setdefault(mid,[]).append((rid,{n:float(b['targets'][n].values.flat[0]) for n in names if b['targets'][n].valid.all()}))
        for mid,rows in saved.items():
            for (ra,va),(rb,vb) in itertools.combinations(rows,2):
                for n in names:
                    if n not in va or n not in vb:continue
                    delta=source[mid][ra][n]-source[mid][rb][n]
                    if delta==0:continue
                    spec=next(f for f in on.view.fields if f['name']==n);spec=spec.get('normalization',on.view.normalizations.get(n));reference=delta/float(np.asarray(spec['scale']).flat[0]);actual=va[n]-vb[n]
                    stats[n]['comparable_pairs']+=1;stats[n]['normalized_zero_pairs']+=int(actual==0);stats[n]['normalization_error_failures']+=int(abs(actual-reference)>1e-6+1e-5*abs(reference))
        results[route]=dict(records=count,fields=stats,nonselected_bitwise_unchanged=True,selected_F64_raw_and_F32_alignment=True);off.close();on.close()
    save(REPO/'results/p_followup/B2_subset_smoke.json',dict(status='ENGINEERING_SMOKE_COMPLETE',MIDs=64,scope='Existing partial current-identity map and cached originalF64 only; full B3 still pending',routes=results))
    print('B2_SUBSET',results,flush=True)
if __name__=='__main__':main()