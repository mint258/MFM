"""Real frozen-encoder v2-panel production with shared target-free H0 caches."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from .v2_disk import save_checkpoint, save_metadata_json
from .v2_s_training import s_model
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_panel import MoleculeH0
from .v3_dev_evaluation import (TaskSpec,TaskPrediction,task_rows,mlp_pooled_probe,
                               deep_atom_probe,compare_panel,error)

REPO = Path(__file__).resolve().parents[3]
BASE = Path('/lfshome/zixiao/model_v31_20261105/DEV_PANEL_V2_20261111')
DATASETS = ('expansionrx','cyp_isoform','qm9')


def _json(value,path):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text())!=value:
            raise ValueError('Retain existing metadata from a different configuration')
        return
    save_metadata_json(value,path)


def _save_once(value,path):
    path = Path(path)
    if path.exists():
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    partial = path.with_name(path.name+'.partial.'+os.environ.get('SLURM_JOB_ID',str(os.getpid())))
    if partial.exists():
        raise FileExistsError('Retain the previous partial; use a fresh actual execution')
    save_checkpoint(value,partial)
    partial.rename(path)


def _pack(prediction):
    return dict(task=asdict(prediction.task),molecule_uids=list(prediction.molecule_uids),
        source_record_uids=list(prediction.source_record_uids),
        targets=torch.as_tensor(prediction.targets),predictions=torch.as_tensor(prediction.predictions),
        valid=torch.as_tensor(prediction.valid))


def _unpack(value):
    return TaskPrediction(TaskSpec(**value['task']),tuple(value['molecule_uids']),
        value['targets'].numpy(),value['predictions'].numpy(),value['valid'].numpy(),
        tuple(value['source_record_uids']))


class ProbeHistory:
    disabled = False
    def __init__(self,stream,run):
        self.stream,self.run,self.step = stream,run,0
        self.cell,self.losses = '',{}

    def log(self,row,*,step,commit):
        value = dict(cell=self.cell,local_step=step,**row)
        losses = self.losses.setdefault(self.cell,[])
        if 'readout/loss' in row:
            losses.append(row['readout/loss'])
            if len(losses)==1000:
                value['readout/loss_mean_1000_updates'] = sum(losses)/1000
                losses.clear()
        self.stream.write(json.dumps(value)+'\n')
        self.run.log(value,step=self.step,commit=True)
        self.step += 1


def _h0_payload(encoder,view,encode):
    rows = encode(encoder,view)
    optimization = set(view.view('train'))
    sizes = [len(r.h0) for r in rows if r.member_index in optimization]
    return dict(n_ref=sum(sizes)/len(sizes),records=[dict(molecule_uid=r.molecule_uid,
        member_index=r.member_index,h0=r.h0,source_atom_ids=r.source_atom_ids) for r in rows])


def _cached_rows(payload):
    return [MoleculeH0(r['molecule_uid'],r['member_index'],r['h0'],r['source_atom_ids'])
            for r in payload['records']]


def _produce(config,checkpoint,destination,cache_root,views,tasks,encode,history):
    reference = checkpoint is None
    seed = 20261025 if reference else config['seed']
    key = ('random__'+config['distance_bias']+'__'+config['views'] if reference else
           Path(checkpoint).parent.name+'__'+Path(checkpoint).stem)
    cache_root = Path(cache_root)/key
    cache_paths = {d:cache_root/(d+'.pt') for d in DATASETS}
    if not all(p.exists() for p in cache_paths.values()):
        torch.manual_seed(seed)
        model,_ = s_model(config['distance_bias'],config['views'])
        if not reference:
            state = torch.load(checkpoint,map_location='cpu',weights_only=True)['model']
            if any(k.startswith('structural.') for k in state):
                state = {k.removeprefix('structural.'):v for k,v in state.items()
                         if k.startswith('structural.')}
            model.load_state_dict(state)
        encoder = model.encoder.cuda().eval()
        for dataset,view in views.items():
            if not cache_paths[dataset].exists():
                _save_once(_h0_payload(encoder,view,encode),cache_paths[dataset])
        del encoder,model
        torch.cuda.empty_cache()
    files,n_refs = {},{}
    for dataset,view in views.items():
        payload = torch.load(cache_paths[dataset],map_location='cpu',weights_only=True)
        cached = _cached_rows(payload)
        n_refs[dataset] = payload['n_ref']
        for task in (t for t in tasks if t.dataset_id==dataset):
            train = task_rows(view,cached,task,role='train')
            validation = task_rows(view,cached,task,role='train_inner_validation')
            for name,probe in (('R2',mlp_pooled_probe),('R3',deep_atom_probe)):
                cell = task.task_id+'/'+name
                if name=='R3' and task.output_level=='atom':
                    files[cell] = files[task.task_id+'/R2']
                    continue
                path = destination/'probes'/(task.task_id.replace('.','_')+'__'+name+'.pt')
                if not path.exists():
                    history.cell = ('reference' if reference else 'candidate')+'/'+config['distance_bias']+'/'+cell
                    prediction,detail = probe(train,validation,task,n_ref=payload['n_ref'],
                                               seed=0,device='cuda',tracker=history)
                    history.log({'readout/native_error':error(prediction),
                                 'readout/error_metric':task.error_metric},
                                step=detail['updates'],commit=True)
                    _save_once(dict(prediction=_pack(prediction),detail=detail),path)
                files[cell] = str(path)
        del cached,payload
    _json(dict(checkpoint=None if reference else str(checkpoint),architecture=config['distance_bias'],
        views=config['views'],files=files,n_refs=n_refs,panel='v2',
        source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
        status='FROZEN_H0_PROBES_COMPLETE_REFERENCE_SCORES_NOT_YET_AGGREGATED'),destination/'predictions.json')


def evaluate(args,*,store_factory,encode):
    output = Path(args.output)
    from importlib.util import spec_from_file_location,module_from_spec
    spec = spec_from_file_location('existing_development_registry',REPO/'tools/model_v3/v2_run_development.py')
    registry = module_from_spec(spec)
    spec.loader.exec_module(registry)
    registry.require_registered_output(args.cache_root,json.loads(registry.REGISTRY.read_text()))
    output.mkdir(parents=True,exist_ok=True)
    panel = json.loads((REPO/'configs/dev_panel_v2.json').read_text())
    checkpoint = torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    config = checkpoint['configuration']
    if config.get('stage') in ('T0','T1','T2'):
        from .v3_latent_evaluation import produce
        return produce(args,checkpoint,store_factory=store_factory,encode=encode)
    specification = dict(checkpoint=str(args.checkpoint),panel='v2',reference_only=args.reference_only,
                         store=str(args.store),readout_seed=0)
    _json(specification,output/'configuration.json')
    store = store_factory(args.store)
    views = {dataset:GroupedTrainingView(store,dataset,
        'official' if dataset=='expansionrx' else '0',store.group_map) for dataset in DATASETS}
    tasks = [TaskSpec(**{key:item[key] for key in
        ('task_id','dataset_id','field','output_level','error_metric','pooling')}) for item in panel['tasks']]
    torch.set_num_threads(16)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started = time.monotonic()
    sdk_dir = output/'offline_wandb'/os.environ.get('SLURM_JOB_ID',str(os.getpid()))
    sdk_dir.mkdir(parents=True,exist_ok=False)
    for variable,name in (('WANDB_CACHE_DIR','cache'),('WANDB_CONFIG_DIR','config'),
                          ('WANDB_DATA_DIR','data')):
        path = sdk_dir/name
        path.mkdir()
        os.environ[variable] = str(path)
    import wandb
    run = wandb.init(project='MFM-model-v3',group='dev-panel-v2',mode='offline',dir=str(sdk_dir),
        config=specification,settings=wandb.Settings(init_timeout=30,x_disable_stats=False,
                                                   x_stats_sampling_interval=30))
    if run is None or run.disabled:
        raise RuntimeError('A real offline W&B SDK run is required')
    completed = False
    try:
        with (sdk_dir/'readout_history.jsonl').open('x',buffering=1) as stream:
            history = ProbeHistory(stream,run)
            if args.reference_only:
                for architecture in ('C1-0','C1-a','C1-b'):
                    reference_config = dict(config,distance_bias=architecture,seed=20261025)
                    destination = output/architecture
                    destination.mkdir(parents=True,exist_ok=True)
                    _produce(reference_config,None,destination,args.cache_root,views,tasks,encode,history)
            else:
                _produce(config,args.checkpoint,output,args.cache_root,views,tasks,encode,history)
        completed = True
    finally:
        run.finish(exit_code=0 if completed else 1)
        _json(dict(native_sdk_finished=True,producer_complete=completed,
                   seconds=time.monotonic()-started),sdk_dir/'sdk_finished.json')
    _json(dict(status='PREDICTIONS_COMPLETE',seconds=time.monotonic()-started,
               reference_only=args.reference_only,panel='v2',selection_use=True),output/'producer_complete.json')
    print(json.dumps(dict(status='PREDICTIONS_COMPLETE',output=str(output),
                         seconds=time.monotonic()-started)),flush=True)


def score_evaluation(directory,reference_directory,legacy_summary):
    directory,reference_directory = Path(directory),Path(reference_directory)
    manifest = json.loads((directory/'predictions.json').read_text())
    reference = json.loads((reference_directory/'predictions.json').read_text())
    summaries = {}
    for readout in ('R2','R3'):
        path = directory/(readout+'_summary.json')
        if path.exists():
            summaries[readout] = json.loads(path.read_text())
            continue
        candidate,controls = {},{}
        for key,path_name in manifest['files'].items():
            if not key.endswith('/'+readout):
                continue
            task_id = key.rsplit('/',1)[0]
            candidate[task_id] = _unpack(torch.load(path_name,map_location='cpu',weights_only=True)['prediction'])
            controls[task_id] = _unpack(torch.load(reference['files'][key],map_location='cpu',weights_only=True)['prediction'])
        identity = manifest['architecture']+':'+manifest['views']
        summary = compare_panel(candidate,controls,architecture_sha256=identity,
            reference_architecture_sha256=reference['architecture']+':'+reference['views'],
            retain_paired_samples=readout=='R3')
        summary.update(readout=readout,panel='v2',source_roles=['train','train_inner_validation'],
                       downstream_TEST_read=False)
        _json(summary,directory/(readout+'_summary.json'))
        summaries[readout] = summary
    legacy = json.loads(Path(legacy_summary).read_text())
    ridge = [r['normalized_improvement'] for key,r in legacy['tasks'].items() if key.endswith('/ridge')]
    summary = dict(panel='v2',complete=all(v['complete'] for v in summaries.values()),
        primary='R3',mean_normalized_improvement=summaries['R3']['mean_normalized_improvement'],
        R1_mean_normalized_improvement=float(np.mean(ridge)),
        R2_mean_normalized_improvement=summaries['R2']['mean_normalized_improvement'],
        historical_18_cell_mean=legacy['mean_normalized_improvement'],legacy_summary=str(legacy_summary),
        checkpoint=manifest['checkpoint'],source_roles=['train','train_inner_validation'],downstream_TEST_read=False)
    _json(summary,directory/'summary.json')
    return summary,summaries['R3']
