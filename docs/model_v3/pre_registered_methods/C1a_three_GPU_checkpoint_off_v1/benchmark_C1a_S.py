"""One original production S batch, C1-a, checkpoints off: engineering only."""
from __future__ import annotations
import argparse, copy, fcntl, gc, hashlib, json, os, re, socket, sys, time
from dataclasses import asdict
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
SNAPSHOT='d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f'
BASE='e92b6125e0b3ea430970bc7ee24fc152e26919c5'

def need(ok,message):
    if not ok:raise ValueError(message)

def save(path,value):
    with Path(path).open('w') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--expected-gpu',choices=('3090','4090','5090'),required=True)
    parser.add_argument('--gpu-uuid',required=True);parser.add_argument('--expected-node',required=True)
    parser.add_argument('--code-sha',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();W=args.source_root.absolute();out=args.output.absolute();GPU=args.gpu_uuid
    need(os.getuid()==os.geteuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16','Owned Slurm16CPU allocation required')
    need(socket.gethostname().split('.')[0]==args.expected_node and os.environ.get('CUDA_VISIBLE_DEVICES')==GPU
        and re.fullmatch(r'GPU-[0-9a-f-]+',GPU) and re.fullmatch(r'[0-9a-f]{40}',args.code_sha),'Actual node/UUID/code identity required')
    need(W.resolve()==W and W.is_relative_to(B) and (W/'current/phychem_mfm').is_dir(),'Explicit actual canonical runtime source required')
    need(out.resolve()==out and out.is_relative_to(N) and not out.exists()
        and not out.is_relative_to(N/'native_S_B20k_v3'),'Fresh independent production-batch output required')
    out.mkdir(parents=True);os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';os.environ['WANDB_MODE']='offline'
    for key,sub in (('WANDB_CACHE_DIR','cache'),('WANDB_DATA_DIR','wandb_data'),('WANDB_CONFIG_DIR','wandb_config')):
        os.environ[key]=str(out/sub)
    sys.path[:0]=[str(W/'current'),str(W/'tools/model_v3'),str(W/'workflows/sprime_s/scripts')]
    import torch
    from phychem_mfm.model.v3_architecture import ArchitectureOptions,build_source_s_architecture_model,SharedPairBackbone,SharedGaussianPairEncoder
    from phychem_mfm.model.v3_performance import ConfigurableDenoisingHead
    from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1JointSchedule,Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from s_input_stream import SInputStream
    from a_execution_runtime import guard_resources,install_termination_handler,corpus_receipt
    torch.set_num_threads(8);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    need(torch.cuda.device_count()==1 and args.expected_gpu in torch.cuda.get_device_name(0),'One actual requested GPU family required')
    prop=torch.cuda.get_device_properties(0)
    need(str(prop.uuid).removeprefix('GPU-').lower()==GPU.removeprefix('GPU-').lower(),'Torch physical UUID differs')
    install_termination_handler()
    reference=json.loads((W/'workflows/sprime_s/formal_s/B1_seed0_v2.json').read_bytes())
    a4=json.loads((W/'workflows/s_denoise/configs/A4_seed0_v3.json').read_bytes())
    config=copy.deepcopy(a4['model']);config['backbone'].update(dim=512,layers=6,heads=8,
        activation_checkpointing=False,distance_bias_projection_bias=False);config['expert']['heads']=8
    need(config['backbone']['dropout']==0 and config['backbone']['use_dist_bias'] is True
        and config['backbone']['use_radius_mask'] is False,'Original global/dropout S policy required')
    weights=LossWeights.from_mapping({**reference['training']['loss'],'denoise_sigma':.1,'geom_angle_std_deg':0.,'geom_bond_scale_std':0.})
    policy=Phase1LossPolicy.from_mapping(a4['loss_policy']);supervision=SupervisionConfig.from_variant('S')
    options=ArchitectureOptions(distance_bias='C1-a');common=dict(runtime_base_code=BASE,actual_code_sha=args.code_sha,
        source_root=str(W),seed=0,job_id=os.environ['SLURM_JOB_ID'],node=socket.gethostname(),gpu_uuid=GPU,
        gpu_name=torch.cuda.get_device_name(0),gpu_total_bytes=int(prop.total_memory),torch=str(torch.__version__),cuda=torch.version.cuda,
        model=config,architecture=asdict(options),optimizer=a4['optimizer'],loss_weights=weights.__dict__,loss_policy=a4['loss_policy'],
        precision='fp32',AMP=False,TF32=False,deterministic=True,warmup=2,measured_steps=5,
        checkpoint_scopes={'backbone':False,'shared_pair_encoder':False,'denoising_head':False},
        sampler_max_padded_cost=8000000,snapshot_sha256=SNAPSHOT,small_batch_or_ABBA=False,
        scope='C1-a engineering throughput/peak only, not A qualification, D5, architecture winner or recipe adoption')
    rows=[];failure=None;status='FAILED';stream=model=optimizer=tracker=hook=batch=loss=outputs=cpu_batch=None
    logging_failures=[];calls={'n':0};stats={};receipt=None
    def resource():
        value=guard_resources(out,GPU);g=value['gpu_observation']
        need(type(g['total_bytes']) is int and g['total_bytes']>0,'Unknown GPU total memory')
        need(all(type(p['own']) is bool and type(p['used_memory_bytes']) is int and p['used_memory_bytes']>=0
            for p in g['compute_processes']),'Unknown GPU process ownership/memory')
        need(not value['foreign_gpu_risk_observed'],'Foreign selected-GPU process; stop without signalling')
        return value
    lock_path=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            resource();save(out/'configuration.json',common)
            # Byte-identical production-stage sampler call from4731. No small
            # case, molecule cap, bucket override, trim or OOM retry exists.
            stream=SInputStream(reference,seed=0,input_kind='native_s',workers=8,max_padded_cost=8000000,snapshot_sha256=SNAPSHOT)
            corpus=stream.next();native=list(map(int,corpus.native_atom_counts));cpu_batch=corpus.encoder_batch.clone()
            receipt=corpus_receipt(corpus,stream.index)
            stats=dict(base_records=len(native),native_atoms=sum(native),molecule_presentations=receipt['molecule_presentations'],
                physical_graphs=int(cpu_batch.num_graphs),physical_atoms=int(cpu_batch.num_nodes),max_native_atoms=max(native),
                padded_pairs=int(cpu_batch.num_graphs)*max(native)**2,sampler_padded_cost=8000000)
            need(stats['physical_graphs']==3*len(native) and stats['physical_atoms']==3*sum(native),'Actual native three-view expansion differs')
            save(out/'batch_identity.json',dict(schema='model_v3_C1a_same_production_batch_v1',receipt=receipt,stats=stats,
                source_snapshot_sha256=SNAPSHOT,seed=0,sampler_epoch=0,sampler_batch_ordinal=0,
                batch_reduced_or_regenerated_after_OOM=False))
            stream.commit(corpus);stream.close();stream=None;corpus=None
            torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();torch.manual_seed(0);torch.cuda.manual_seed_all(0)
            model=build_source_s_architecture_model(copy.deepcopy(config),options)
            # Reuse the already qualified head recomputation switch only. No
            # RuntimeDense attention/packing/compile or C mathematics is installed.
            model.geometry_head=ConfigurableDenoisingHead(model.geometry_head,activation_checkpointing=False)
            model=model.cuda().train()
            need(type(model.backbone) is SharedPairBackbone and type(model.backbone.pair_encoder) is SharedGaussianPairEncoder
                and len(model.backbone.layers)==6 and model.backbone.dim==512 and model.backbone.activation_checkpointing is False
                and model.geometry_head.activation_checkpointing is False,'Actual C1-a complete checkpoint-off scopes required')
            need(all(p.dtype==torch.float32 for p in model.parameters()),'Model Parameters must stay FP32')
            def count_pair(module,inputs,output):calls['n']+=1
            hook=model.backbone.pair_encoder.register_forward_hook(count_pair)
            optimizer=torch.optim.AdamW(model.parameters(),**a4['optimizer']);resource()
            try:
                import wandb
                tracker=wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(out),reinit=True,
                    name='C1a_checkpoint_off_'+args.expected_gpu+'_'+os.environ['SLURM_JOB_ID'],config={**common,'batch':stats})
            except Exception as error:logging_failures.append(dict(stage='init',type=type(error).__name__))
            for ordinal in range(7):
                batch=cpu_batch.clone().to('cuda',non_blocking=False);torch.cuda.synchronize();calls['n']=0;tick=time.perf_counter()
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type='cuda',enabled=False):
                    outputs=model.forward_pretrain(batch,supervision.objectives)
                    loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),ordinal,policy=policy)
                    need(bool(torch.isfinite(loss.total)),'Nonfinite training loss');loss.total.backward()
                    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);need(bool(torch.isfinite(norm)),'Nonfinite gradient norm');optimizer.step()
                torch.cuda.synchronize();seconds=time.perf_counter()-tick
                need(calls['n']==1,'Shared pair encoder must run once per full train step including backward')
                resource();row=dict(update=ordinal+1,measured=ordinal>=2,step_ms=seconds*1000,
                    samples_per_s=stats['base_records']/seconds,molecules_per_s=stats['molecule_presentations']/seconds,
                    native_atoms_per_s=stats['native_atoms']/seconds,peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),shared_pair_forward_calls=calls['n'],
                    loss=float(loss.total.detach().cpu()),gradient_norm=float(norm.detach().cpu()))
                rows.append(row);save(out/'measurement_rows.json',rows)
                if tracker is not None:
                    try:tracker.log(row,step=ordinal+1,commit=True)
                    except Exception as error:logging_failures.append(dict(stage='log',update=ordinal+1,type=type(error).__name__))
                outputs=loss=batch=None
            status='COMPLETED'
        except torch.cuda.OutOfMemoryError as error:status='CUDA_OOM';failure={'type':type(error).__name__}
        except MemoryError as error:status='RESOURCE_LIMIT';failure={'type':type(error).__name__,'reason':str(error)}
        except BaseException as error:failure={'type':type(error).__name__,'reason':str(error)}
        finally:
            if stream is not None:
                try:stream.close()
                except Exception as error:failure=failure or {'type':type(error).__name__,'stage':'input_close'};status='FAILED'
            measured=[r for r in rows if r['measured']];elapsed=sum(r['step_ms'] for r in measured)/1000
            summary=dict(status=status,failure=failure,configuration=common,batch=stats,batch_identity_receipt_sha256=None if receipt is None else receipt['receipt_sha256'],
                completed_updates=len(rows),measurement_rows=len(measured),parameter_count=None if model is None else sum(p.numel() for p in model.parameters()),
                tracking_run_id=None if tracker is None else tracker.id,logging_failures=logging_failures,
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                peaks_include_warmup_firstAdam_and_measurement=True,engineering_only=True,A_numeric_equivalence=False,
                scientific_selection=False,batch_reduced_or_retried=False,model_checkpoint_written=False,
                timing='Same4731 synchronized zero_grad/forward/loss/backward/clip/Adam; H2D,loader,SDK,monitor excluded',
                memory='Actual full warmup+measurement peaks; original85pct/foreign/RSS/private/output protections remain final')
            if len(measured)==5 and status=='COMPLETED':summary.update(mean_step_ms=1000*elapsed/5,
                samples_per_s=stats['base_records']*5/elapsed,molecules_per_s=stats['molecule_presentations']*5/elapsed,
                native_atoms_per_s=stats['native_atoms']*5/elapsed)
            if hook is not None:hook.remove()
            if tracker is not None:
                try:tracker.summary.update(summary);tracker.finish(exit_code=0 if status=='COMPLETED' else 1)
                except Exception as error:logging_failures.append(dict(stage='finish',type=type(error).__name__))
            save(out/'summary.json',summary);outputs=loss=batch=cpu_batch=optimizer=model=None;gc.collect();torch.cuda.empty_cache()
    return 0 if status=='COMPLETED' else 1

if __name__=='__main__':raise SystemExit(main())
