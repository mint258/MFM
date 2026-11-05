"""Native-S C1-0 versus existing C1-a: fixed real batches, full train-step ABBA engineering only.
Run only under the existing GPU supervisor/Root admission. No D5 or scientific selection.
"""
from __future__ import annotations
import argparse,copy,csv,fcntl,gc,hashlib,json,os,re,socket,subprocess,sys,time
from pathlib import Path
from dataclasses import asdict

B=Path('/share/home/zixiao/descriptor_analysis')
W=B/'MFM_model_v3_runtime_integration_v1'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
SNAPSHOT='d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f'

def need(ok,message):
    if not ok:raise ValueError(message)
def save(path,value):
    with Path(path).open('w') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--warmup',type=int,default=2)
    parser.add_argument('--steps',type=int,default=5)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args()
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
         and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16,'Owned Slurm16CPU allocation required')
    need(socket.gethostname().split('.')[0]=='compute-0-21' and os.environ.get('CUDA_VISIBLE_DEVICES')==GPU,'Exact Root-admitted node21/C35 required')
    need(1<=args.warmup<=10 and 3<=args.steps<=30 and 0<=args.workers<=8,'Bounded explicit warmup/measurement/loader settings required')
    out=args.output.absolute();need(out.resolve()==out and out.is_relative_to(B/'runs/model_v3_20261026')
         and not out.is_relative_to(B/'runs/model_v3_20261026/native_S_B20k_v3') and not out.exists(),'Fresh independent output required')
    out.mkdir(parents=True)
    need(os.environ.get('CUBLAS_WORKSPACE_CONFIG') in (None,':4096:8'),'Conflicting CUBLAS policy')
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    os.environ['WANDB_MODE']='offline'
    for name,sub in (('WANDB_CACHE_DIR','cache'),('WANDB_DATA_DIR','wandb_data'),('WANDB_CONFIG_DIR','wandb_config')):
        os.environ[name]=str(out/sub)
    sys.path[:0]=[str(W/'current'),str(W/'tools/model_v3'),str(W/'workflows/sprime_s/scripts')]
    import torch
    import wandb
    from phychem_mfm.model.v3_architecture import ArchitectureOptions,build_source_s_architecture_model,SharedPairBackbone
    from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1JointSchedule,Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from s_input_stream import SInputStream
    from a_execution_runtime import guard_resources,install_termination_handler
    torch.set_num_threads(8);torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    torch.set_float32_matmul_precision('highest');torch.backends.cudnn.allow_tf32=False
    need(torch.cuda.device_count()==1 and '5090' in torch.cuda.get_device_name(0),'One actual5090 required')
    prop=torch.cuda.get_device_properties(0)
    need(str(prop.uuid).removeprefix('GPU-').lower()==GPU.removeprefix('GPU-').lower(),'Torch physical UUID differs')
    install_termination_handler()
    reference=json.loads((W/'workflows/sprime_s/formal_s/B1_seed0_v2.json').read_bytes())
    a4=json.loads((W/'workflows/s_denoise/configs/A4_seed0_v3.json').read_bytes())
    config=copy.deepcopy(a4['model']);config['backbone'].update(dim=512,layers=6,heads=8);config['expert']['heads']=8
    need(config['backbone']['activation_checkpointing'] is True and config['backbone']['dropout']==0
         and config['backbone']['use_dist_bias'] is True and config['backbone']['use_radius_mask'] is False,'Original global/checkpoint/dropout S policy required')
    weights=LossWeights.from_mapping({**reference['training']['loss'],'denoise_sigma':.1,'geom_angle_std_deg':0.,'geom_bond_scale_std':0.})
    policy=Phase1LossPolicy.from_mapping(a4['loss_policy']);supervision=SupervisionConfig.from_variant('S')
    git=B/'runs/model_v3_20261025/cpu_git_tools_v1/bin/git'
    def code_observation(arguments):
        command=[str(git),'-C',str(W),*arguments]
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        need(result.returncode==0,'Actual code Git observation failed: '+result.stderr)
        return dict(argv=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    actual_head=code_observation(['rev-parse','HEAD'])
    actual_tree=code_observation(['rev-parse','HEAD^{tree}'])
    actual_clean=code_observation(['status','--porcelain=v1','--untracked-files=all'])
    need(re.fullmatch('[a-f0-9]{40}',actual_head['stdout'].strip()) and
         re.fullmatch('[a-f0-9]{40}',actual_tree['stdout'].strip()) and actual_clean['stdout']=='','Exact clean code required')
    formal_sources=[]
    for path in (Path(__file__).absolute(),W/'current/phychem_mfm/model/v3_architecture.py',
                 W/'workflows/sprime_s/formal_s/B1_seed0_v2.json',W/'workflows/s_denoise/configs/A4_seed0_v3.json'):
        raw=path.read_bytes();need(len(raw)<=2<<20,'Formal source/config bound')
        formal_sources.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    need(torch.get_float32_matmul_precision()=='highest' and not torch.backends.cuda.matmul.allow_tf32
         and not torch.backends.cudnn.allow_tf32,'Actual matched highest/TF32-off policy required')
    common=dict(worktree=str(W),actual_code_head=actual_head['stdout'].strip(),actual_code_tree=actual_tree['stdout'].strip(),
        actual_code_Git=[actual_head,actual_tree,actual_clean],formal_output_source_refs=formal_sources,
        architecture_options={mode:asdict(ArchitectureOptions(distance_bias=mode)) for mode in ('C1-0','C1-a')},
        attention_domain='global, radius_mask=False, cutoff=None; RBF center range8A is not a cutoff',
        seed=args.seed,job_id=os.environ['SLURM_JOB_ID'],node=socket.gethostname(),gpu_uuid=GPU,
        gpu_name=torch.cuda.get_device_name(0),torch=str(torch.__version__),cuda=torch.version.cuda,model=config,
        optimizer=a4['optimizer'],loss_weights=weights.__dict__,loss_policy=a4['loss_policy'],
        precision='fp32',AMP=False,TF32=False,deterministic=True,warmup=args.warmup,measured_steps=args.steps,
        order=['C1-0','C1-a','C1-a','C1-0'],pair_rows=65536,
        scope='Real S engineering training throughput/memory only; fixed repeated batches, not sampler throughput, A equivalence, D5, architecture selection or adoption.')
    rows=[];windows=[];batches={};failure=None;status='FAILED'
    lock_path=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
    columns=['case','position','architecture','update','measured','base_records','molecule_presentations','native_atoms',
             'physical_graphs','physical_atoms','max_native_atoms','padded_pairs','step_ms','samples_per_s','molecules_per_s',
             'native_atoms_per_s','peak_allocated_bytes','peak_reserved_bytes','shared_pair_forward_calls','loss','gradient_norm']
    def resources():
        value=guard_resources(out,GPU);g=value['gpu_observation']
        need(type(g['total_bytes']) is int and g['total_bytes']>0,'Unknown GPU total memory')
        need(all(type(p['own']) is bool and type(p['used_memory_bytes']) is int and p['used_memory_bytes']>=0
                 for p in g['compute_processes']),'Unknown GPU process ownership/memory')
        need(not value['foreign_gpu_risk_observed'],'Foreign selected-GPU process; stop without signalling')
        return value
    def stage(case):
        ref=copy.deepcopy(reference);cost=8000000
        if case=='small':ref['sampler']['max_molecules']=min(4,int(ref['sampler']['max_molecules']));cost=500000
        stream=None
        try:
            stream=SInputStream(ref,seed=args.seed,input_kind='native_s',workers=args.workers,
                                max_padded_cost=cost,snapshot_sha256=SNAPSHOT)
            corpus=stream.next();native=list(map(int,corpus.native_atom_counts));batch=corpus.encoder_batch.clone()
            stats=dict(base_records=len(native),native_atoms=sum(native),molecule_presentations=len({stream.index.ref(i).molecule_id for i in corpus.logical_indices}),
                physical_graphs=int(batch.num_graphs),physical_atoms=int(batch.num_nodes),max_native_atoms=max(native),
                padded_pairs=int(batch.num_graphs)*max(native)**2,sampler_padded_cost=cost)
            need(stats['physical_graphs']==3*len(native) and stats['physical_atoms']==3*sum(native),'Actual native three-view expansion differs')
            stream.commit(corpus)
            return batch,stats
        finally:
            if stream is not None:stream.close()
    def window(case,position,mode,cpu_batch,stats):
        model=optimizer=tracker=outputs=loss=batch=hook=None;calls={'n':0}
        record=dict(case=case,position=position,architecture=mode,status='FAILED',completed_updates=0,measurement_rows=0,**stats)
        try:
            torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
            torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
            model=build_source_s_architecture_model(copy.deepcopy(config),ArchitectureOptions(distance_bias=mode)).cuda().train()
            need(all(p.dtype==torch.float32 for p in model.parameters()),'Model Parameters must stayFP32')
            need(all(getattr(m,'numeric_mode',None) in (None,'legacy') and getattr(m,'attention_aggregation_mode',None) in (None,'legacy')
                     for m in model.modules()),'No compensated/centered/geometry candidate modes')
            need(len(model.backbone.layers)==6 and model.backbone.dim==512 and model.backbone.activation_checkpointing,'Original6x512 checkpoint policy differs')
            if mode=='C1-0':
                tiled=[m for m in model.backbone.modules() if type(m).__name__=='TiledDistanceMLP']
                need(len(tiled)==6 and all(m.pair_rows==65536 for m in tiled),'Baseline must execute real six tiled65536 distanceMLPs')
                record['baseline_memory_implementation']=model.s_memory_implementation
            else:
                need(isinstance(model.backbone,SharedPairBackbone) and model.backbone.options.cutoff is None,'Actual global existing shared C1-a required')
                def count_pair(module,inputs,output):calls['n']+=1
                hook=model.backbone.pair_encoder.register_forward_hook(count_pair)
            optimizer=torch.optim.AdamW(model.parameters(),**a4['optimizer'])
            tracker=wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(out),reinit=True,
                name=f'C1a_S_{case}_{position}_{os.environ["SLURM_JOB_ID"]}',config={**common,'case':case,'position':position,'architecture':mode,'batch':stats})
            record['tracking_run_id']=tracker.id;record['parameter_count']=sum(p.numel() for p in model.parameters())
            resources()
            for ordinal in range(args.warmup+args.steps):
                batch=cpu_batch.clone().to('cuda',non_blocking=False)
                torch.cuda.synchronize();calls['n']=0;tick=time.perf_counter()
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type='cuda',enabled=False):
                    outputs=model.forward_pretrain(batch,supervision.objectives)
                    loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),ordinal,policy=policy)
                    need(bool(torch.isfinite(loss.total)),'Nonfinite training loss')
                    loss.total.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                    need(bool(torch.isfinite(norm)),'Nonfinite gradient norm');optimizer.step()
                torch.cuda.synchronize();seconds=time.perf_counter()-tick
                record['completed_updates']=ordinal+1
                need(calls['n']==(1 if mode=='C1-a' else 0),'Shared pair encoder must run exactly once per complete trainingstep, including backward recomputation')
                observation=resources()
                row=dict(case=case,position=position,architecture=mode,update=ordinal+1,measured=ordinal>=args.warmup,**stats,
                    step_ms=seconds*1000,samples_per_s=stats['base_records']/seconds,
                    molecules_per_s=stats['molecule_presentations']/seconds,native_atoms_per_s=stats['native_atoms']/seconds,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                    shared_pair_forward_calls=calls['n'],loss=float(loss.total.detach().cpu()),gradient_norm=float(norm.detach().cpu()))
                rows.append({k:row[k] for k in columns})
                tracker.log({**{k:row[k] for k in columns if k not in ('case','architecture')},'optimizer_lr':optimizer.param_groups[0]['lr']},step=ordinal+1,commit=True)
                outputs=loss=batch=None
                print(json.dumps({k:row[k] for k in ('case','position','architecture','update','measured','step_ms','peak_allocated_bytes','shared_pair_forward_calls')}),flush=True)
            measured=[r for r in rows if r['case']==case and r['position']==position and r['measured']]
            elapsed=sum(r['step_ms'] for r in measured)/1000
            record.update(status='COMPLETED',measurement_rows=len(measured),mean_step_ms=1000*elapsed/len(measured),
                samples_per_s=stats['base_records']*len(measured)/elapsed,molecules_per_s=stats['molecule_presentations']*len(measured)/elapsed,
                native_atoms_per_s=stats['native_atoms']*len(measured)/elapsed)
        except torch.cuda.OutOfMemoryError as exc:
            record.update(status='CUDA_OOM',failure=dict(type=type(exc).__name__,message=str(exc)))
        except MemoryError as exc:
            if str(exc)!='A diagnostic exceeded85% of physical GPU capacity':raise
            record.update(status='GPU_MEMORY_BUDGET_EXCEEDED',failure=dict(type=type(exc).__name__,message=str(exc)))
        finally:
            record.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                          peaks_include_warmup_firstAdam_and_measurement=True)
            if hook is not None:hook.remove()
            if tracker is not None:
                tracker.summary.update(record);tracker.finish(exit_code=0 if record['status']=='COMPLETED' else 1)
            outputs=loss=batch=optimizer=model=None;gc.collect();torch.cuda.empty_cache()
        return record
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            resources();save(out/'configuration.json',common)
            for case in ('small','production'):
                cpu_batch,stats=stage(case);batches[case]=stats
                for pos,mode in enumerate(common['order'],1):
                    windows.append(window(case,pos,mode,cpu_batch,stats))
                    save(out/'summary.json',dict(status='RUNNING',configuration=common,batches=batches,windows=windows,engineering_only=True))
                del cpu_batch
            status=('COMPLETE_WITH_RESOURCE_LIMIT' if any(w['status']=='GPU_MEMORY_BUDGET_EXCEEDED' for w in windows)
                    else 'COMPLETE_WITH_OOM' if any(w['status']=='CUDA_OOM' for w in windows) else 'COMPLETE')
        except BaseException as exc:
            failure=dict(type=type(exc).__name__,message=str(exc))
        finally:
            with (out/'steps.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
            save(out/'summary.json',dict(status=status,failure=failure,configuration=common,batches=batches,windows=windows,
                CSV='steps.csv',engineering_only=True,A_numeric_equivalence=False,scientific_selection=False,
                includes_input_loader_time=False,timing='CUDA-synchronized zero_grad/forward/loss/backward/clip/Adam step; H2D,SDK,monitor excluded',
                memory='Torch peaks include full warmup+measurement, firstAdam; original85pct supervisor remains active',
                fixed_same_CPU_batch_recloned_for_every_step=True,model_checkpoint_written=False))
    return int(failure is not None)
if __name__=='__main__':raise SystemExit(main())
