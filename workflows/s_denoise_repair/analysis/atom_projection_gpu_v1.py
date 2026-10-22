"""Bounded independent execution validation; zero official training updates."""
import argparse,copy,hashlib,json,math,os,time
from pathlib import Path
from runtime import ROOT,SOURCE,old_configuration,save,sha,setup_imports
from gpu_runtime import gpu_runtime,check_memory

PLAN=ROOT/'configs/atom_projection_gpu_plan_v1.json'
CLOSURE=ROOT/'configs/atom_projection_cpu_closure_v1.json'

def main():
    plan=json.loads(PLAN.read_text());closure=json.loads(CLOSURE.read_text())
    assert closure['status']=='ACTUAL_CPU_C6_AND_LEGACY_CLOSED_NOT_ADOPTED'
    assert closure['actual_parent']['State']=='COMPLETED' and closure['actual_parent']['ExitCode']=='0:0'
    qa=json.loads(Path(closure['result_reference']['path']).read_text())
    references=qa['source_references']+plan['source_references']
    original=json.loads((ROOT/'configs/D3_source_binding_v4.json').read_text())['files']
    for item in references+original:assert sha(item['path'])==item['sha256']
    assert SOURCE==ROOT/'source_v4' and not (ROOT/'GUIDE_STOP.json').exists()
    setup_imports()
    with gpu_runtime('atom_projection_gpu_v1') as (output,status):
        import torch,psutil,wandb
        from data import selected_components
        from s_model_memory_v1 import build_memory_bounded_model
        from phychem_mfm.model.heads import EquivariantDenoisingHead
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler,collate_native_views
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1LossPolicy,Phase1JointSchedule
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        assert status['node'].split('.')[0]=='compute-0-21' and '5090' in status['gpu_model']
        status.update(host_RSS_cap_GiB=26,requested_host_memory_GiB=32,official_optimizer_updates=0)
        save(output/'runtime.json',status)
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        base=old_configuration();cfg=json.loads(Path(plan['configuration']['path']).read_text())
        weights=LossWeights.from_mapping(base['training']['loss']);supervision=SupervisionConfig.from_variant('S')
        policy=Phase1LossPolicy.from_mapping(cfg['loss_policy'])
        _,dataset,counts=selected_components('train',seed=0,epoch_noise=True,local_blocks=True)
        groups=list(BlockAtomBatchSampler(counts,seed=0,epoch=0,**base['sampler']))
        largest=max(groups,key=lambda ids:len(ids)*max(counts.ref(i).native_n_atoms for i in ids)**2)
        selected=[groups[0],largest]
        batches=[collate_native_views([dataset[i] for i in ids]).encoder_batch for ids in selected]
        dataset.close()
        rows=[];comparisons=[];optimizer_checks=[];dev_updates=0;began=time.monotonic();peak_rss=0
        report=dict(status='ATOM_PROJECTION_GPU_VALIDATION_IN_PROGRESS_NOT_ADOPTED',job_id=os.environ['SLURM_JOB_ID'],
            plan_reference=dict(path=str(PLAN),sha256=sha(PLAN)),cpu_closure_reference=dict(path=str(CLOSURE),sha256=sha(CLOSURE)),
            runtime=status,rows=rows,numeric_comparisons=comparisons,optimizer_checkpoint_checks=optimizer_checks,
            official_optimizer_updates=0,development_optimizer_updates=0,
            batch_references=[dict(case=n,local_record_indices=ids,records=len(ids),padded_quadratic_cost=len(ids)*max(counts.ref(i).native_n_atoms for i in ids)**2) for n,ids in enumerate(selected)])
        tracking=wandb.init(project='phychem-mfm-s-denoise-repair',mode='offline',dir=str(output),
            name='development_atom_projection_gpu_v1',config=dict(plan=plan,plan_sha256=sha(PLAN),official_updates=0,planned_development_updates=12))
        tracking_exit=1;log_step=0
        def memory():
            nonlocal peak_rss
            assert time.monotonic()-began<1000,'BOUNDED_DEVELOPMENT_WALL'
            memory_row=check_memory(torch,status);peak_rss=max(peak_rss,memory_row['host_tree_RSS_bytes'])
            assert memory_row['host_tree_RSS_bytes']<26*(1<<30),'DEVELOPMENT_HOST_RSS_CAP'
            assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file() and not p.is_symlink())<2*(1<<30),'DEVELOPMENT_OUTPUT_CAP'
            return memory_row
        def state_hash(model):
            digest=hashlib.sha256()
            for name,value in sorted(model.state_dict().items()):digest.update(name.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
            return digest.hexdigest()
        def call(model,batch,training):
            model.train(training);model.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                outputs=model.forward_pretrain(batch,objectives=supervision.objectives)
                loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),0,policy=policy)
                objective=loss.total*cfg['total_loss_scale'];assert bool(torch.isfinite(objective))
                if training:objective.backward()
            return outputs,objective
        def capture(model,batch,cpu_rng,cuda_rng):
            torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
            out,objective=call(model,batch,True);torch.cuda.synchronize()
            result=dict(noise=out.noise_pred.detach().cpu().clone(),loss=float(objective.detach()),
                gradients={k:p.grad.detach().cpu().clone() for k,p in model.named_parameters() if p.grad is not None})
            del out,objective;model.zero_grad(set_to_none=True)
            return result
        def compare(a,b):
            assert a['gradients'].keys()==b['gradients'].keys()
            error=magnitude=0.
            for key,value in a['gradients'].items():
                other=b['gradients'][key];assert bool(torch.isfinite(value).all() and torch.isfinite(other).all())
                error+=float((value.double()-other.double()).square().sum());magnitude+=float(value.double().square().sum())
            values=dict(max_output_absolute=float((a['noise']-b['noise']).abs().max()),
                loss_relative=abs(a['loss']-b['loss'])/max(abs(a['loss']),1e-12),gradient_relative_L2=math.sqrt(error/max(magnitude,1e-30)))
            limits=plan['numeric_acceptance'];values['eligible']=all(values[key]<=limits[key] for key in values)
            return values
        def check_tree(a,b):
            if isinstance(a,torch.Tensor):assert isinstance(b,torch.Tensor) and torch.equal(a.detach().cpu(),b.detach().cpu())
            elif isinstance(a,dict):
                assert a.keys()==b.keys()
                for key in a:check_tree(a[key],b[key])
            elif isinstance(a,(list,tuple)):
                assert len(a)==len(b)
                for x,y in zip(a,b):check_tree(x,y)
            else:assert a==b
        try:
            for layers in plan['message_layer_cases']:
                torch.manual_seed(731);torch.cuda.manual_seed_all(731)
                model_cfg=copy.deepcopy(cfg['model']);model_cfg['head']['geometry_message_layers']=layers
                model_cfg['head']['geometry_cache_atom_projections']=False
                model=build_memory_bounded_model(model_cfg)
                if layers==0:
                    payload=torch.load(plan['trained_checkpoint']['path'],map_location='cpu',weights_only=True)
                    model.load_state_dict(payload['model'],strict=True);del payload
                model=model.cuda();heads=[h for h in model.modules() if isinstance(h,EquivariantDenoisingHead)];assert len(heads)==1
                head=heads[0];assert head.pair_chunk_size==8192 and head.message_layers==layers and not head.cache_atom_projections
                initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};before=state_hash(model)
                for case,cpu_batch in enumerate(batches):
                    batch=cpu_batch.clone().to('cuda');cpu_rng=torch.get_rng_state();cuda_rng=torch.cuda.get_rng_state()
                    head.cache_atom_projections=False;reference=capture(model,batch,cpu_rng,cuda_rng)
                    head.cache_atom_projections=True;optimized=capture(model,batch,cpu_rng,cuda_rng)
                    comparison=dict(message_layers=layers,batch=case,**compare(reference,optimized));comparisons.append(comparison)
                    del reference,optimized
                    for block,cached in enumerate(plan['crossover_order']):
                        head.cache_atom_projections=cached
                        for training in [False,True]:
                            for _ in range(plan['warmups']):
                                out,objective=call(model,batch,training);torch.cuda.synchronize();del out,objective
                            model.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats();times=[]
                            for _ in range(plan['timed_repeats']):
                                torch.cuda.synchronize();start=time.perf_counter();out,objective=call(model,batch,training)
                                torch.cuda.synchronize();times.append(time.perf_counter()-start);del out,objective
                            model.zero_grad(set_to_none=True)
                            row=dict(message_layers=layers,batch=case,block=block,cache_atom_projections=cached,
                                mode='forward_backward_no_optimizer' if training else 'eval_forward',records=len(selected[case]),
                                seconds=times,mean_seconds=math.fsum(times)/len(times),**memory())
                            rows.append(row);log_step+=1;tracking.log({k:v for k,v in row.items() if isinstance(v,(int,float,bool))},step=log_step,commit=True)
                            save(output/'progress.json',report)
                    del batch;torch.cuda.empty_cache()
                assert state_hash(model)==before,'NO_UPDATE_TIMING_MODEL_STATE_CHANGED'
                # Each mode receives the exact same initial weights, input batches, optimizer and RNG.
                # The 12 development updates do not enter any official D3/full epoch counter.
                cpu_rng=torch.get_rng_state();cuda_rng=torch.cuda.get_rng_state();updated_states=[]
                for cached in [False,True]:
                    model.load_state_dict(initial,strict=True);head.cache_atom_projections=cached
                    torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
                    optimizer=torch.optim.AdamW(model.parameters(),**cfg['optimizer'])
                    mode_start=state_hash(model);losses=[]
                    for case,cpu_batch in enumerate(batches):
                        batch=cpu_batch.clone().to('cuda');out,objective=call(model,batch,True)
                        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);assert bool(torch.isfinite(norm))
                        optimizer.step();dev_updates+=1;report['development_optimizer_updates']=dev_updates
                        losses.append(float(objective.detach()));del batch,out,objective;memory()
                    assert state_hash(model)!=mode_start,'DEVELOPMENT_OPTIMIZER_DID_NOT_UPDATE'
                    state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                    assert all(bool(torch.isfinite(v).all()) for v in state.values())
                    opt=copy.deepcopy(optimizer.state_dict())
                    for entries in opt['state'].values():
                        for key,value in list(entries.items()):
                            if isinstance(value,torch.Tensor):assert bool(torch.isfinite(value).all());entries[key]=value.detach().cpu()
                    checkpoint=output/('development_msg'+str(layers)+'_cached'+str(int(cached))+'.pt')
                    effective_cfg=copy.deepcopy(model_cfg);effective_cfg['head']['geometry_cache_atom_projections']=cached
                    payload=dict(model=state,optimizer=opt,configuration=effective_cfg,cache_atom_projections=cached,
                        CPU_RNG=torch.get_rng_state(),CUDA_RNG=torch.cuda.get_rng_state(),development_updates=2,official_updates=0)
                    torch.save(payload,checkpoint);restored=torch.load(checkpoint,map_location='cpu',weights_only=True);check_tree(payload,restored)
                    resumed=build_memory_bounded_model(restored['configuration']).cuda();resumed.load_state_dict(restored['model'],strict=True)
                    resumed_opt=torch.optim.AdamW(resumed.parameters(),**cfg['optimizer']);resumed_opt.load_state_dict(restored['optimizer'])
                    check_tree(restored['optimizer'],resumed_opt.state_dict())
                    probe_batch=batches[0].clone().to('cuda')
                    torch.set_rng_state(restored['CPU_RNG']);torch.cuda.set_rng_state(restored['CUDA_RNG'])
                    out_before,loss_before=call(model,probe_batch,False)
                    torch.set_rng_state(restored['CPU_RNG']);torch.cuda.set_rng_state(restored['CUDA_RNG'])
                    out_after,loss_after=call(resumed,probe_batch,False)
                    resume_delta=float((out_before.noise_pred-out_after.noise_pred).abs().max())
                    resume_loss_delta=abs(float(loss_before)-float(loss_after))/max(abs(float(loss_before)),1e-12)
                    assert resume_delta<=plan['numeric_acceptance']['max_output_absolute'] and resume_loss_delta<=plan['numeric_acceptance']['loss_relative']
                    optimizer_checks.append(dict(message_layers=layers,cache_atom_projections=cached,development_updates=2,losses=losses,
                        safe_weights_only_checkpoint_bitexact_roundtrip=True,fresh_model_and_optimizer_restored=True,
                        restored_prediction_max_abs=resume_delta,restored_loss_relative=resume_loss_delta,
                        checkpoint=dict(path=str(checkpoint),sha256=sha(checkpoint),bytes=checkpoint.stat().st_size)))
                    updated_states.append(state)
                    del payload,restored,opt,optimizer,resumed,resumed_opt,probe_batch,out_before,out_after,loss_before,loss_after
                    model.zero_grad(set_to_none=True);torch.cuda.empty_cache()
                differences={k:float((updated_states[0][k]-updated_states[1][k]).abs().max()) for k in updated_states[0] if updated_states[0][k].is_floating_point()}
                report.setdefault('post_development_update_max_abs_differences',{})[str(layers)]=max(differences.values())
                del updated_states,model,head,heads,initial;torch.cuda.empty_cache()
            aggregate=[]
            for layers in plan['message_layer_cases']:
                for case in range(2):
                    for mode in ['forward_backward_no_optimizer','eval_forward']:
                        group=[r for r in rows if r['message_layers']==layers and r['batch']==case and r['mode']==mode]
                        means={str(flag):math.fsum(t for r in group if r['cache_atom_projections']==flag for t in r['seconds'])/sum(len(r['seconds']) for r in group if r['cache_atom_projections']==flag) for flag in [False,True]}
                        aggregate.append(dict(message_layers=layers,batch=case,mode=mode,mean_seconds=means,speedup=means['False']/means['True']))
            report['aggregate']=aggregate
            eligible={str(layers):not any(r['foreign_gpu_process_count'] for r in rows) and all(c['eligible'] for c in comparisons if c['message_layers']==layers) and
                all(a['speedup']>=plan['minimum_forward_backward_speedup_to_adopt'] for a in aggregate if a['message_layers']==layers and a['mode']=='forward_backward_no_optimizer') for layers in plan['message_layer_cases']}
            for item in references+original:assert sha(item['path'])==item['sha256']
            assert dev_updates==12 and len(optimizer_checks)==6 and len(comparisons)==6 and len(rows)==48
            report.update(status='ATOM_PROJECTION_GPU_VALIDATION_COMPLETE_NOT_ADOPTED',eligible_by_message_layer=eligible,
                benchmark_parameters_and_buffers_unchanged_before_development_updates=True,
                foreign_GPU_activity_observed=any(r['foreign_gpu_process_count'] for r in rows),original_99_sources_unchanged=True)
            tracking_exit=0
        except BaseException as exc:
            report.update(status='ATOM_PROJECTION_GPU_VALIDATION_FAILED_NOT_ADOPTED',error=repr(exc));raise
        finally:
            report.update(elapsed_seconds=time.monotonic()-began,peak_host_RSS_bytes=peak_rss)
            save(output/'result.json',report);tracking.finish(exit_code=tracking_exit)
        print('ATOM_PROJECTION_GPU_VALIDATION_COMPLETE',os.environ['SLURM_JOB_ID'],json.dumps(report['eligible_by_message_layer']),flush=True)

if __name__=='__main__':main()
