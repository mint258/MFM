"""Real batches, no optimizer/parameter update: measure execution chunk choices."""
import hashlib,json,math,os,time
from pathlib import Path
from runtime import ROOT,old_configuration,save,sha,setup_imports
from gpu_runtime import gpu_runtime

PLAN=ROOT/'configs/chunk_execution_probe_v1.json'


def main():
    plan=json.loads(PLAN.read_text())
    cfgref=plan['frozen_configuration'];bindingref=plan['frozen_source_binding']
    assert sha(cfgref['path'])==cfgref['sha256'] and sha(bindingref['path'])==bindingref['sha256']
    source=json.loads(Path(bindingref['path']).read_text())
    for item in source['files']:assert sha(item['path'])==item['sha256']
    cfg=json.loads(Path(cfgref['path']).read_text());setup_imports()
    with gpu_runtime('chunk_execution_probe_v1') as (output,status):
        status['host_RSS_cap_GiB']=26;status['requested_host_memory_GiB']=32
        status['official_optimizer_updates']=0;save(output/'runtime.json',status)
        import torch,psutil
        from data import selected_components
        from s_model_memory_v1 import build_memory_bounded_model
        from phychem_mfm.model.heads import EquivariantDenoisingHead
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler,collate_native_views
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1LossPolicy,Phase1JointSchedule
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
        base=old_configuration();index,dataset,counts=selected_components('train',seed=0,epoch_noise=True,local_blocks=True)
        sampler=BlockAtomBatchSampler(counts,seed=0,epoch=0,**base['sampler'])
        groups=list(sampler);largest=max(groups,key=lambda b:len(b)*max(counts.ref(i).native_n_atoms for i in b)**2)
        selected=[groups[0],largest]
        model=build_memory_bounded_model(cfg['model']).cuda()
        heads=[x for x in model.modules() if isinstance(x,EquivariantDenoisingHead)];assert len(heads)==1
        head=heads[0];assert head.pair_chunk_size==8192 and head.message_layers==0
        def state_digest():
            digest=hashlib.sha256()
            for k,v in sorted(model.state_dict().items()):digest.update(k.encode());digest.update(v.detach().cpu().contiguous().numpy().tobytes())
            return digest.hexdigest()
        before=state_digest();policy=Phase1LossPolicy.from_mapping(cfg['loss_policy'])
        supervision=SupervisionConfig.from_variant('S');weights=LossWeights.from_mapping(base['training']['loss'])
        rows=[];began=time.monotonic();parent=psutil.Process();maximum_rss=0
        report=dict(status='CHUNK_EXECUTION_PROBE_IN_PROGRESS',plan_reference=dict(path=str(PLAN),sha256=sha(PLAN)),
            job_id=os.environ['SLURM_JOB_ID'],runtime=status,rows=rows,official_optimizer_updates=0,model_parameter_updates=0)
        def memory():
            nonlocal maximum_rss
            rss=parent.memory_info().rss+sum(p.memory_info().rss for p in parent.children(recursive=True) if p.is_running())
            maximum_rss=max(maximum_rss,rss);assert rss<26*(1<<30),'PROBE_HOST_RSS_CAP'
            assert torch.cuda.memory_reserved()<(status['gpu_memory_total_MiB']-2048)*(1<<20),'PROBE_GPU_CAP'
        def call(batch,training):
            model.train(training);model.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                outputs=model.forward_pretrain(batch,objectives=supervision.objectives)
                loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),0,policy=policy)
                assert torch.isfinite(loss.total),'PROBE_NONFINITE_LOSS'
                if training:loss.total.backward()
            return outputs,loss
        try:
            for number,indices in enumerate(selected):
                preparation=time.monotonic();batch=collate_native_views([dataset[i] for i in indices]).encoder_batch.to('cuda')
                cpu_rng=torch.get_rng_state();cuda_rng=torch.cuda.get_rng_state();reference=None
                prep_seconds=time.monotonic()-preparation
                for chunk in plan['chunk_sizes']:
                    assert time.monotonic()-began<1000,'BOUNDED_PROBE_WALL_REACHED'
                    head.pair_chunk_size=chunk;torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
                    try:
                        out,loss=call(batch,True);torch.cuda.synchronize()
                        gradients={k:p.grad.detach().cpu().clone() for k,p in model.named_parameters() if p.grad is not None}
                        observed=dict(noise=out.noise_pred.detach().cpu().clone(),loss=float(loss.total.detach().cpu()),gradients=gradients)
                        if reference is None:
                            reference=observed;difference=dict(max_output_absolute=0.,relative_loss=0.,relative_gradient_L2=0.,eligible=True)
                        else:
                            assert gradients.keys()==reference['gradients'].keys()
                            error=0.;magnitude=0.
                            for k,g in gradients.items():
                                delta=(g.double()-reference['gradients'][k].double());error+=float(delta.square().sum())
                                magnitude+=float(reference['gradients'][k].double().square().sum())
                            output_delta=float((observed['noise']-reference['noise']).abs().max())
                            loss_delta=abs(observed['loss']-reference['loss'])/max(abs(reference['loss']),1e-12)
                            gradient_delta=math.sqrt(error/max(magnitude,1e-30))
                            difference=dict(max_output_absolute=output_delta,relative_loss=loss_delta,relative_gradient_L2=gradient_delta,
                                eligible=output_delta<=plan['output_absolute_tolerance'] and loss_delta<=plan['loss_relative_tolerance'] and gradient_delta<=plan['gradient_relative_L2_tolerance'])
                        del out,loss,gradients,observed;model.zero_grad(set_to_none=True)
                        for training in [False,True]:
                            for _ in range(plan['warmups']):
                                out,loss=call(batch,training);torch.cuda.synchronize();del out,loss;model.zero_grad(set_to_none=True)
                            torch.cuda.reset_peak_memory_stats();times=[]
                            for _ in range(plan['repeats']):
                                start=time.perf_counter();out,loss=call(batch,training);torch.cuda.synchronize();times.append(time.perf_counter()-start)
                                del out,loss;model.zero_grad(set_to_none=True)
                            memory();rows.append(dict(batch=number,records=len(indices),preparation_seconds=prep_seconds,chunk_size=chunk,
                                mode='forward_backward_no_optimizer' if training else 'eval_forward',seconds=times,
                                mean_seconds=math.fsum(times)/len(times),peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                peak_reserved_bytes=torch.cuda.max_memory_reserved(),numeric_comparison=difference,
                                optimizer_state_memory_not_included=True))
                            save(output/'progress.json',report)
                    except torch.OutOfMemoryError as exc:
                        model.zero_grad(set_to_none=True);torch.cuda.empty_cache()
                        rows.append(dict(batch=number,chunk_size=chunk,status='CANDIDATE_OOM_NOT_ADOPTED',error=str(exc)[:300]))
                        save(output/'progress.json',report)
                del batch,reference;torch.cuda.empty_cache()
            assert state_digest()==before,'BENCHMARK_MODEL_STATE_CHANGED'
            for item in source['files']:assert sha(item['path'])==item['sha256']
            report.update(status='NO_UPDATE_CHUNK_EXECUTION_PROBE_COMPLETE',model_state_sha256=before,model_parameters_and_buffers_unchanged=True)
        except BaseException as exc:
            report.update(status='CHUNK_EXECUTION_PROBE_FAILED',error=repr(exc));raise
        finally:
            dataset.close();report.update(elapsed_seconds=time.monotonic()-began,peak_host_RSS_bytes=maximum_rss)
            save(output/'result.json',report)
        print('CHUNK_EXECUTION_PROBE_COMPLETE',os.environ['SLURM_JOB_ID'],len(rows),flush=True)


if __name__=='__main__':main()
