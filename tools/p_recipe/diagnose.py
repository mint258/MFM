"""The P0 diagnostics; D6 reads frozen identity metadata and no targets."""
from __future__ import annotations
import argparse, csv, json, time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/p_recipe_20261113'
REPO=Path(__file__).resolve().parents[2]

def validation_indices():
    corpus=json.loads(Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json').read_text())
    source=Path(corpus['source_root']);manifest=json.loads((source/'manifest.json').read_text())
    common=json.loads(Path(manifest['full_source_dependencies']['common']).read_text())
    mids=[]
    for ref in common['membership_tables']:
        table=pq.read_table(ref['path'],columns=['molecule_id','effective_role','common_population_v1'])
        mids.extend(r['molecule_id'] for r in table.to_pylist() if r['effective_role']=='VAL' and r['common_population_v1'])
    chosen=set(np.random.default_rng(20261112).choice(sorted(mids),5000,replace=False).tolist())
    table=pq.read_table(Path(manifest['split_roots']['FULL'])/'id_map.parquet',
        columns=['molecule_id','molecule_index'],filters=[('record_kind','=','M')])
    return [r['molecule_index'] for r in table.to_pylist() if r['molecule_id'] in chosen]

def csv_output(name,rows):
    path=REPO/'results/p_recipe/diagnostics'/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def representation_diagnostic():
    import torch
    from phychem_mfm.phase1.v2_s_training import s_model
    from phychem_mfm.phase1.v31_loader import MFM4Dataset,collate_samples
    torch.set_num_threads(16)
    corpus=json.loads(Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json').read_text())
    data=MFM4Dataset(corpus['source_root'],split='FULL',geometry_only=True,k=10,
        molecule_indices=validation_indices())
    inputs=json.loads((CONTROL/'input_metadata.json').read_text())['features']
    spectra=[];summary=[];gains=[];gamma=None
    for condition in ('S','P'):
        source=next(r for r in inputs if r['candidate']=='C1-0' and r['condition']==condition)
        payload=torch.load(source['checkpoint'],map_location='cpu',weights_only=True)
        model,_=s_model('C1-0','three');state=payload['model']
        if any(k.startswith('structural.') for k in state):
            state={k.removeprefix('structural.'):v for k,v in state.items() if k.startswith('structural.')}
        model.load_state_dict(state);encoder=model.encoder.cuda().eval()
        totals={name:dict(n=0,s=np.zeros(512),outer=np.zeros((512,512))) for name in ('atom','mean')}
        for start in range(0,len(data.indices),32):
            samples=[data.read(int(index),int(data.choices(int(index))[0])) for index in data.indices[start:start+32]]
            batch=collate_samples(samples,device='cuda')
            with torch.no_grad():h=encoder.encode_atoms(batch).cpu().double().numpy()
            ptr=batch.ptr.cpu().tolist();means=np.stack([h[a:b].mean(0) for a,b in zip(ptr,ptr[1:])])
            for name,values in (('atom',h),('mean',means)):
                total=totals[name];total['n']+=len(values);total['s']+=values.sum(0);total['outer']+=values.T@values
        for name,total in totals.items():
            mean=total['s']/total['n'];cov=total['outer']/total['n']-np.outer(mean,mean)
            spectrum=np.linalg.eigvalsh(cov)[::-1];std=np.sqrt(np.maximum(np.diag(cov),0.))
            threshold=max(1e-12,1e-4*float(np.median(std)))
            pr=float(spectrum.sum()**2/(spectrum@spectrum))
            summary.append(dict(condition=condition,representation=name,observations=total['n'],
                participation_ratio=pr,near_constant_dimensions=int((std<threshold).sum()),
                std_median=float(np.median(std)),near_constant_threshold=threshold))
            spectra.extend(dict(condition=condition,representation=name,rank=i+1,eigenvalue=float(value))
                           for i,value in enumerate(spectrum))
            if condition=='S' and name=='atom':gamma=float(np.median(std))
        gain=encoder.backbone.out_norm.weight.detach().cpu().tolist()
        gains.extend(dict(condition=condition,dimension=i,gain=value) for i,value in enumerate(gain))
        del encoder,model,payload,state;torch.cuda.empty_cache()
    data.close();csv_output('D4_spectrum.csv',spectra);csv_output('D4_summary.csv',summary)
    csv_output('D4_layernorm_gain.csv',gains)
    (CONTROL/'D4_gamma.json').write_text(json.dumps(dict(gamma=gamma,source='S atom H std median on fixed5000VAL'),indent=2)+'\n')
    print(json.dumps(dict(diagnostic='D4',gamma=gamma,summary=summary)),flush=True)

def identity_gate():
    d=json.loads((CONTROL/'D6_metadata.json').read_text())
    train_ids,set_val=set(),set()
    for ref in d['common']['membership_tables']:
        table=pq.read_table(ref['path'],columns=['molecule_id','effective_role','common_population_v1'])
        for row in table.to_pylist():
            if not row['common_population_v1']:continue
            if row['effective_role']=='TRAIN':train_ids.add(row['molecule_id'])
            elif row['effective_role']=='VAL':set_val.add(row['molecule_id'])
    refs=json.loads((CONTROL/'identity_source_refs.json').read_text())
    summary=json.loads(Path(refs['membership_summary']['path']).read_text())
    downstream={}
    # Existing target-free memberships include all folds; no test labels opened.
    members=Path(summary['artifacts']['members.jsonl']['path'])
    with members.open() as stream:
        for line in stream:
            row=json.loads(line)
            if row['dataset'] in ('qm9','cyp_isoform') and row.get('inchikey'):
                downstream.setdefault(row['inchikey'],set()).add(row['dataset'])
    geometry=json.loads(Path(refs['expansion_geometry']['path']).read_text())
    for row in geometry['records']:
        if row.get('full_inchikey'):
            downstream.setdefault(row['full_inchikey'],set()).add('expansionrx')
    projection={key[:14]+':'+key[-1] for key in downstream}
    train_keys,val_keys=set(),set()
    hits={};seen=set()
    formal=ROOT/'runs/phase1_wp5_20261011/population/formal_record_index.parquet'
    for batch in pq.ParquetFile(formal).iter_batches(batch_size=65536,
            columns=['molecule_id','stored_inchikey','reidentified_inchikey']):
        for mid,source,reidentified in zip(*(batch.column(i).to_pylist() for i in range(3))):
            keys={key for key in (source,reidentified) if key}
            if mid in train_ids:
                seen.add(mid);train_keys.update(keys)
                for key in keys:
                    if key in downstream or key[:14]+':'+key[-1] in projection:
                        hits.setdefault(mid,set()).add(key)
            elif mid in set_val:val_keys.update(keys)
    result=dict(TRAIN_molecules=len(train_ids),VAL_molecules=len(set_val),
        TRAIN_molecules_with_identity=len(seen),downstream_unique_full_keys=len(downstream),
        TRAIN_VAL_molecule_id_overlap=len(train_ids&set_val),
        TRAIN_VAL_full_key_overlap=len(train_keys&val_keys),
        TRAIN_VAL_wp5_key_overlap=len({k[:14]+':'+k[-1] for k in train_keys}&{k[:14]+':'+k[-1] for k in val_keys}),
        TRAIN_downstream_overlap_molecules=len(hits),
        overlapping_molecules={mid:sorted(keys) for mid,keys in hits.items()},
        target_values_read=False,new_identity_computation=False)
    result['passed']=not any(result[k] for k in ('TRAIN_VAL_molecule_id_overlap',
        'TRAIN_VAL_full_key_overlap','TRAIN_VAL_wp5_key_overlap','TRAIN_downstream_overlap_molecules'))
    (CONTROL/'D6_identity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='overlapping_molecules'}),flush=True)
    return result


def layer_diagnostic():
    import torch
    from evaluate import run,score
    from phychem_mfm.phase1.p_recipe import paired_decision
    base=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')
    metadata=json.loads((CONTROL/'input_metadata.json').read_text())['features']
    summaries=[]
    for condition in ('S','P'):
        source=next(r for r in metadata if r['candidate']=='C1-0' and r['condition']==condition)
        original=json.loads((CONTROL/('C1_0_'+condition+'.json')).read_text())
        last=json.loads((base/('C1_0_'+condition)/'scores.json').read_text())
        for layer in (3,4,5):
            name=f'D5_{condition}_layer{layer}'
            configuration={**original,'run':name,'stage':1,'arm':f'layer{layer}',
                'layer':layer,'checkpoint':source['checkpoint'],
                'features':str(base/'layer_features'/name),'output':str(base/name)}
            run(configuration)
            result=score(Path(configuration['output'])/'predictions.json',
                configuration['reference_manifest'],REPO/'results/p_recipe/scores.csv')
            for readout in ('R1','R3'):
                a,b=result[readout],last[readout]
                decision=paired_decision(a['mean_normalized_improvement'],b['mean_normalized_improvement'],
                    a['paired_bootstrap']['values'],b['paired_bootstrap']['values'])
                summaries.append(dict(condition=condition,layer=layer,readout=readout,
                    score=a['mean_normalized_improvement'],layer6_score=b['mean_normalized_improvement'],**decision))
            torch.cuda.empty_cache()
        for readout in ('R1','R3'):
            summaries.append(dict(condition=condition,layer=6,readout=readout,
                score=last[readout]['mean_normalized_improvement'],layer6_score=last[readout]['mean_normalized_improvement'],
                delta=0.,ci_lower=0.,ci_upper=0.,verdict='reference'))
    csv_output('D5_layers.csv',summaries)
    import csv
    with (REPO/'results/p_recipe/scores.csv').open() as stream:
        rows=[r for r in csv.DictReader(stream) if r['run'].startswith('D5_') or r['run'] in ('C1_0_S','C1_0_P')]
    csv_output('D5_layer_tasks.csv',rows)
    (CONTROL/'D5_decision.json').write_text(json.dumps(dict(B1_priority=any(
        r['condition']=='P' and r['readout']=='R3' and r['verdict']=='win' for r in summaries)),indent=2)+'\n')
    print(json.dumps(dict(diagnostic='D5',summary=summaries)),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['D4','D5','D6'],required=True)
    args=p.parse_args()
    if args.stage=='D4':representation_diagnostic()
    elif args.stage=='D5':layer_diagnostic()
    else:identity_gate()
