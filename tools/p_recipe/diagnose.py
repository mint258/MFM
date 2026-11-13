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

def p_context():
    import torch
    from phychem_mfm.phase1.v31_loader import TrainingView
    from phychem_mfm.phase1.v31_training import V31PDModel
    from phychem_mfm.phase1.v2_s_training import s_model
    from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration,read_json
    c=read_json(REPO/'configs/p_recipe/base.json')
    train=PRecipeDataset(**dataset_configuration(c))
    old=read_json(ROOT/'runs/model_v31_20261105/M3_P_C1_0_seed0_micro32.APPROVED.json')
    oldview=TrainingView(train.schema,read_json(old['training_view']),read_json(old['normalizations']))
    source=next(r for r in read_json(CONTROL/'input_metadata.json')['features'] if r['candidate']=='C1-0' and r['condition']=='P')
    torch.set_num_threads(1);structural,_=s_model('C1-0','three');pd=V31PDModel(structural.encoder,train.view)
    model=torch.nn.ModuleDict(dict(structural=structural,pd=pd));checkpoint=torch.load(source['checkpoint'],map_location='cpu',weights_only=True)
    model.load_state_dict(checkpoint['model']);model.cuda().eval()
    fields=tuple(f.name for f in pd.registry.enabled(('P',)))
    return c,train,model,pd,oldview.normalizations,fields

def corrected_prediction(pd,samples,oldnorm,fields):
    import torch
    from phychem_mfm.phase1.v31_training import element_offset
    prediction=pd.predict(samples,groups=('P',),fields=fields)
    # Preserve the old checkpoint's physical predictions under the repaired D4.
    for name,value in prediction.items():
        if pd.by_name[name].level!='graph':continue
        oldspec=oldnorm[name];new=pd.definitions[name].get('normalization',pd.view.normalizations[name])
        offset=[np.float32(element_offset(s['Z'],oldspec))-np.float32(element_offset(s['Z'],new)) for s in samples]
        prediction[name]=value+value.new_tensor(offset)[:,None]
    return prediction

def field_diagnostic():
    import torch
    from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,validation_indices as choose_val,dataset_configuration
    from phychem_mfm.phase1.v31_training import torch_affine
    c,train,model,pd,oldnorm,fields=p_context();valcfg=dataset_configuration(c,validation=True)
    valcfg['molecule_indices']=choose_val(c,5000);val=PRecipeDataset(**valcfg)
    chosen=np.random.default_rng(20261112).choice(train.indices,5000,replace=False)
    rows=[]
    for role,data,indices in (('TRAIN',train,chosen),('VAL',val,val.indices)):
        totals={n:dict(n=0,absolute=0.,squared=0.,sum_y=0.,squared_y=0.) for n in fields}
        with torch.no_grad():
            for start in range(0,len(indices),c['batch_size']):
                samples=[data.read(int(i),int(data.choices(int(i))[0])) for i in indices[start:start+c['batch_size']]]
                pred=corrected_prediction(pd,samples,oldnorm,fields)
                for name,value in pred.items():
                    spec=pd.definitions[name].get('normalization',pd.view.normalizations[name])
                    predicted=torch_affine(value,spec).cpu().double().numpy()
                    truth=np.concatenate([s['targets'][name].values for s in samples]).astype(np.float64)
                    valid=np.concatenate([s['targets'][name].valid for s in samples]);a,y=predicted[valid],truth[valid];t=totals[name]
                    t['n']+=len(y);t['absolute']+=float(np.abs(a-y).sum());t['squared']+=float(np.square(a-y).sum());t['sum_y']+=float(y.sum());t['squared_y']+=float(y@y)
        for name,t in totals.items():
            denominator=t['squared_y']-t['sum_y']**2/t['n'] if t['n'] else 0.
            rows.append(dict(role=role,field=name,family=pd.by_name[name].family,observations=t['n'],MAE_standardized=t['absolute']/t['n'] if t['n'] else None,R2_standardized_target=1-t['squared']/denominator if denominator>0 else None))
    csv_output('D1_fields.csv',rows);families=sorted({r['family'] for r in rows});summary=[]
    for family in families:
        row=dict(family=family)
        for role in ('TRAIN','VAL'):
            selected=[r for r in rows if r['family']==family and r['role']==role]
            maes=[r['MAE_standardized'] for r in selected if r['MAE_standardized'] is not None];r2=[r['R2_standardized_target'] for r in selected if r['R2_standardized_target'] is not None]
            row[role+'_MAE_standardized']=float(np.mean(maes)) if maes else None;row[role+'_R2_standardized_target']=float(np.mean(r2)) if r2 else None
        summary.append(row)
    csv_output('D1_families.csv',summary);train.close();val.close();print(json.dumps(dict(diagnostic='D1',summary=summary)),flush=True)

def correlation_diagnostic():
    from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration,read_json,physical_state_groups
    c=read_json(REPO/'configs/p_recipe/base.json');data=PRecipeDataset(**dataset_configuration(c))
    fields=[f for f in data.view.fields if f['group']=='P' and f.get('loss_enabled',True)]
    names=[f['name'] for f in fields];groups=physical_state_groups(data.view,set(names))
    graph=[f['name'] for f in fields if f['level'] in ('graph','molecule')
        and f.get('representation','scalar')!='vector'
        and data.schema.get('target_layout',{}).get(f.get('target_id'),{}).get('kind')!='vector']
    blocks={'overall_graph_scalars':graph}
    for key,members in groups.items():
        if key[0]!='PM7':continue
        blocks['|'.join(key)]=[members[s] for s in ('neutral','anion','cation','water','octanol') if s in members]
    chunks={k:[] for k in blocks};chosen=np.random.default_rng(20261112).choice(data.indices,20000,replace=False)
    for i,index in enumerate(chosen):
        sample=data.read(int(index),int(data.choices(int(index))[0]))
        for key,columns in blocks.items():
            values=[sample['targets'][name].values.reshape(-1) for name in columns]
            chunks[key].append(np.stack(values,axis=1).astype(np.float64))
        if (i+1)%5000==0:print(json.dumps(dict(diagnostic='D3',molecules=i+1)),flush=True)
    rows=[]
    for key,columns in blocks.items():
        values=np.concatenate(chunks[key]);complete=values[np.isfinite(values).all(1)]
        std=complete.std(0) if len(complete)>1 else np.zeros(len(columns));active=std>0
        if active.any() and len(complete)>1:
            z=(complete[:,active]-complete[:,active].mean(0))/std[active];corr=z.T@z/len(z);pr=float(np.trace(corr)**2/np.square(corr).sum())
        else:pr=None
        rows.append(dict(block=key,molecules=len(chosen),observations=len(values),complete_observations=len(complete),fields=len(columns),constant_fields=int((~active).sum()),participation_ratio=pr,source_fields=';'.join(columns)))
    csv_output('D3_target_correlation.csv',rows);data.close();print(json.dumps(dict(diagnostic='D3',summary=rows)),flush=True)

def gradient_diagnostic():
    import torch,math
    from phychem_mfm.phase1.p_recipe_training import family_losses
    c,data,model,pd,oldnorm,fields=p_context();rng=np.random.default_rng(20261112);batch_size=c['batch_size']
    chosen=rng.choice(data.indices,50*batch_size,replace=False)
    choices=[(int(i),int(rng.choice(data.choices(int(i))))) for i in chosen]
    parameters=tuple(pd.encoder.backbone.parameters());families={f.name:f.family for f in pd.head_registry.enabled(('P',))}
    norms={};field_energy={};molecules=[]
    def norm(value,retain=False):
        gradient=torch.autograd.grad(value,parameters,retain_graph=retain,allow_unused=True)
        return float(torch.sqrt(sum((g.detach().double().square().sum() for g in gradient if g is not None),value.new_zeros((),dtype=torch.float64))))
    for batch in range(50):
        samples=[data.read(i,conf) for i,conf in choices[batch*batch_size:(batch+1)*batch_size]]
        pred=corrected_prediction(pd,samples,oldnorm,fields);loss=pd.loss(pred,samples,groups=('P',),fields=fields)
        for family,value in family_losses(loss,families).items():norms.setdefault(family,[]).append(norm(value,True))
        for name,value in loss.fields.items():
            if loss.counts[name]:field_energy[name]=field_energy.get(name,0.)+norm(value,True)**2
        del pred,loss,value
        for molecule,conformer in choices[batch*batch_size:(batch+1)*batch_size]:
            sample=data.read(molecule,conformer);pred=corrected_prediction(pd,[sample],oldnorm,fields);loss=pd.loss(pred,[sample],groups=('P',),fields=fields)
            g=norm(loss.total);molecules.append(dict(molecule_index=molecule,conformer_index=conformer,gradient_norm=g,gradient_norm_squared=g*g));del pred,loss
        print(json.dumps(dict(diagnostic='D2',closed_batches=batch+1,batches=50)),flush=True)
    rows=[dict(family=n,batches=len(v),mean_gradient_norm=float(np.mean(v)),mean_gradient_norm_squared=float(np.mean(np.square(v)))) for n,v in norms.items()]
    csv_output('D2_family_gradients.csv',rows);ranked=sorted(field_energy,key=field_energy.get,reverse=True);denominator=sum(field_energy.values());cumulative=0.;marked=[]
    for name in ranked:
        marked.append(name);cumulative+=field_energy[name]
        if cumulative>.5*denominator:break
    field_rows=[dict(field=n,family=families[n],gradient_norm_squared=field_energy[n],fraction=field_energy[n]/denominator,source_fields=';'.join(k for k,v in pd.selections.items() if v[0]==n)) for n in ranked]
    csv_output('D2_field_gradients.csv',field_rows)
    molecules.sort(key=lambda r:r['gradient_norm_squared'],reverse=True);top=molecules[:math.ceil(.01*len(molecules))]
    fraction=sum(r['gradient_norm_squared'] for r in top)/sum(r['gradient_norm_squared'] for r in molecules)
    csv_output('D2_top_one_percent_molecules.csv',top)
    decision=dict(A5=len(marked)<=5 or fraction>.5,marked_fields=marked,top_fields_for_half_energy=len(marked),top_one_percent_molecule_fraction=fraction,batches=50,batch_size=batch_size,molecules=len(molecules),gradient_energy_definition='Sum of individual field/molecule squared shared-backbone gradient norms')
    (CONTROL/'D2_decision.json').write_text(json.dumps(decision,indent=2)+'\n');data.close();print(json.dumps(dict(diagnostic='D2',decision=decision)),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['D1','D2','D3','D4','D5','D6'],required=True)
    args=p.parse_args()
    if args.stage=='D1':field_diagnostic()
    elif args.stage=='D2':gradient_diagnostic()
    elif args.stage=='D3':correlation_diagnostic()
    elif args.stage=='D4':representation_diagnostic()
    elif args.stage=='D5':layer_diagnostic()
    else:identity_gate()
