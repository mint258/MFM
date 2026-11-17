"""P taskbook stage 0: frozen H, only R1/R3, internal TRAIN epoch selection."""
from dataclasses import replace
import argparse, csv, fcntl, json, os, time
from pathlib import Path
import numpy as np
import torch
from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, task_rows, ridge_probe, error, compare_panel
from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack, _unpack
from phychem_mfm.phase1.v3_dev_readouts import run_probe
from phychem_mfm.phase1.v3_downstream_targets import atomization_rows, ATOMIZATION_TASK_ID, PRIMARY_TASK_IDS
from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore

REPO = Path(__file__).resolve().parents[2]

def feature_path(configuration,dataset):
    source=configuration['features']
    return Path(source[dataset]) if isinstance(source,dict) else Path(source)/(dataset+'.pt')

def produce_missing_features(configuration,dataset,view):
    from torch_geometric.data import Batch,Data
    from phychem_mfm.phase1.v2_s_training import s_model
    path=feature_path(configuration,dataset)
    if path.is_file():return
    checkpoint=torch.load(configuration['checkpoint'],map_location='cpu',weights_only=True)
    cfg=checkpoint['configuration'];spec=checkpoint.get('architecture',{}).get('backbone',{}).get('v3_latent')
    model,_=s_model(cfg['distance_bias'],cfg['views'],latent='none' if spec is None else spec['kind'],latent_config=spec)
    state=checkpoint['model']
    if any(key.startswith('structural.') for key in state):
        state={key.removeprefix('structural.'):value for key,value in state.items() if key.startswith('structural.')}
    from phychem_mfm.model.precision import configure_precision
    model.load_state_dict(state);configure_precision(model,cfg.get('precision','fp32'));encoder=model.encoder.cuda().eval()
    members=[(index,view.get(index,role=role)) for role in ('train','train_inner_validation') for index in view.view(role)]
    members=[(i,s) for i,s in members if s.geometry_ready];records=[];sizes=[];fit=set(view.view('train'))
    with torch.no_grad():
        for start in range(0,len(members),32):
            selected=members[start:start+32]
            batch=Batch.from_data_list([Data(x=s.x.reshape(-1,1),pos=s.pos) for _,s in selected]).cuda()
            if configuration.get('layer',6)==6:
                h=encoder.encode_atoms(batch)
            else:
                _,layers=encoder.encode_atoms(batch,return_intermediates=True)
                h=layers[configuration['layer']-1]
            h=h.detach().cpu().float();offset=0
            for index,sample in selected:
                n=len(sample.x)
                records.append(dict(molecule_uid=sample.member_uid,member_index=index,h0=h[offset:offset+n],source_atom_ids=sample.source_atom_ids))
                if index in fit:sizes.append(n)
                offset+=n
    payload=dict(records=records,n_ref=sum(sizes)/len(sizes))
    del checkpoint,model,encoder,state;torch.cuda.empty_cache()
    if not configuration.get('persist_features',True):
        return payload
    path.parent.mkdir(parents=True,exist_ok=True)
    torch.save(payload,path)

class History:
    disabled = False
    def __init__(self, path): self.path, self.cell = path, ''
    def log(self, row, *, step, commit):
        with self.path.open('a') as stream:
            stream.write(json.dumps(dict(cell=self.cell, step=step, **row))+'\n')

def run(configuration):
    c = configuration
    legacy = c.get('legacy', False)
    output = Path(c['output']); output.mkdir(parents=True, exist_ok=True)
    panel = json.loads((REPO/('configs/dev_panel_v2.json' if legacy else 'configs/dev_panel_v3.json')).read_text())
    tasks = [TaskSpec(**{k:t[k] for k in ('task_id','dataset_id','field','output_level','error_metric','pooling')}) for t in panel['tasks']]
    # R1 is mean(H) even for originally extensive downstream tasks.
    tasks = [replace(t, pooling='mean') if not legacy else t for t in tasks]
    store = TrainOnlyPackedStore(c['store'], verify_digests=False)
    views = {d:GroupedTrainingView(store,d,'official' if d=='expansionrx' else '0',store.group_map)
             for d in ('expansionrx','cyp_isoform','qm9')}
    history = History(output/'probe_history.jsonl')
    torch.set_num_threads(16); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32=False; torch.backends.cudnn.allow_tf32=False
    files, details, label_stds = {}, {}, {}
    for dataset, view in views.items():
        memory_payload=produce_missing_features(c,dataset,view)
        payload=(torch.load(feature_path(c,dataset),map_location='cpu',weights_only=True)
                 if memory_payload is None else memory_payload)
        cached = cached_rows(payload)
        for task in (t for t in tasks if t.dataset_id==dataset):
            rows = atomization_rows if task.task_id==ATOMIZATION_TASK_ID else task_rows
            train = rows(view,cached,task,role='train')
            validation = rows(view,cached,task,role='train_inner_validation')
            labels = torch.cat([r.targets[r.supervision_mask & r.candidate_mask].double() for r in train])
            label_stds[task.task_id] = float(labels.std(unbiased=False))
            for readout in (('R3',) if legacy else ('R1','R3')):
                key = task.task_id+'/'+readout
                path = output/(task.task_id.replace('.','_')+'__'+readout+'.pt')
                if not path.exists():
                    history.cell = key
                    if readout=='R1':
                        prediction, detail = ridge_probe(train,validation,task,relative_std_floor=True)
                    else:
                        prediction, detail = run_probe(train,validation,task,readout='R3',
                            n_ref=payload['n_ref'],seed=0,device='cuda',tracker=history,
                            relative_std_floor=not legacy,internal_epoch_selection=not legacy)
                    # Keep prediction payloads outside Git; CSV is the delivered small output.
                    torch.save(dict(prediction=_pack(prediction),detail=detail),path)
                p = torch.load(path,map_location='cpu',weights_only=True)
                details[key] = {k:v for k,v in p['detail'].items() if k!='state_dict'}
                files[key] = str(path)
                print(json.dumps(dict(run=c['run'],cell=key,error=error(_unpack(p['prediction'])),
                    removed_dimensions=details[key].get('removed_dimensions',0))),flush=True)
    manifest = dict(run=c['run'],files=files,details=details,label_stds=label_stds,
        stage=c.get('stage',0),round=c.get('round',0),arm=c.get('arm',c['run']),samples=c.get('samples',6000000),
        protocol='legacy_validation_only' if legacy else 'p_recipe',source_roles=['train','train_inner_validation'])
    (output/'predictions.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if legacy:
        old=json.loads(Path(c['legacy_predictions']).read_text())
        actual={t.task_id:_unpack(torch.load(files[t.task_id+'/R3'],map_location='cpu',weights_only=True)['prediction']) for t in tasks}
        previous={t.task_id:_unpack(torch.load(old['files'][t.task_id+'/R3'],map_location='cpu',weights_only=True)['prediction']) for t in tasks}
        # One direct published-prediction comparison; no CPU/GPU replay or second pass.
        refs=json.loads(Path(c['legacy_reference']).read_text())['files']
        differences={}
        for key,value in actual.items():
            ref=error(_unpack(torch.load(refs[key+'/R3'],map_location='cpu',weights_only=True)['prediction']))
            differences[key]=dict(recomputed=(ref-error(value))/ref,
                                  published=(ref-error(previous[key]))/ref)
        recomputed=float(np.mean([v['recomputed'] for v in differences.values()]))
        published=float(np.mean([v['published'] for v in differences.values()]))
        passed=abs(recomputed-published)<=max(.005,.02*abs(published))
        result=dict(passed=passed,recomputed=recomputed,published=published,
                    tolerance='max(0.005, 0.02*abs(published_score))',tasks=differences)
        (output/'legacy_validation.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        if not passed: raise RuntimeError('Stage0 legacy reproduction outside taskbook tolerance')
    return manifest

def score(candidate_path, reference_path, csv_path):
    candidate=json.loads(Path(candidate_path).read_text()); reference=json.loads(Path(reference_path).read_text())
    rows=[]; summaries={}
    for readout in ('R1','R3'):
        actual={};random={};included=[]
        for key,path in candidate['files'].items():
            task,name=key.rsplit('/',1)
            if name!=readout:continue
            a=_unpack(torch.load(path,map_location='cpu',weights_only=True)['prediction'])
            b=_unpack(torch.load(reference['files'][key],map_location='cpu',weights_only=True)['prediction'])
            e,ref=error(a),error(b)
            excluded=task not in PRIMARY_TASK_IDS or ref < .05*candidate['label_stds'][task]
            rows.append(dict(run=candidate['run'],stage=candidate['stage'],round=candidate['round'],arm=candidate['arm'],
                samples=candidate['samples'],readout=readout,task=task,error=e,E_ref=ref,
                score=(ref-e)/ref if ref else None,excluded_from_mean=excluded,
                removed_dimensions=candidate['details'][key].get('removed_dimensions',0)))
            if not excluded:actual[task]=a;random[task]=b;included.append(task)
        summary=compare_panel(actual,random,architecture_sha256='C1-0-reference',
            reference_architecture_sha256='C1-0-reference',retain_paired_samples=True,retain_task_samples=True)
        summary['included_tasks']=included
        summaries[readout]=summary
    destination=Path(csv_path);destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('a+',newline='') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0)
        previous=list(csv.DictReader(stream))
        previous=[r for r in previous if r['run']!=candidate['run'] or int(r['samples'])!=candidate['samples']]
        stream.seek(0);stream.truncate();writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(previous+rows)
    (Path(candidate_path).parent/'scores.json').write_text(json.dumps(summaries,indent=2)+'\n')
    return summaries

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--configuration',required=True)
    args=parser.parse_args();configuration=json.loads(Path(args.configuration).read_text())
    run(configuration)
    if configuration.get('reference_manifest'):
        score(Path(configuration['output'])/'predictions.json',configuration['reference_manifest'],
              REPO/'results/p_recipe/scores.csv')
