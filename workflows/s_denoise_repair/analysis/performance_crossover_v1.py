"""D3 cost evidence: paired real-batch crossover, frozen parameter copies."""
import argparse
import json
from pathlib import Path
import time
from runtime import ROOT,old_configuration,save,sha,setup_imports
from gpu_runtime import gpu_runtime,check_memory


def read_result(pointer):
    ref=json.loads(Path(pointer).read_text());assert sha(ref['path'])==ref['sha256']
    result=json.loads(Path(ref['path']).read_text())
    assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--selected',required=True);args=parser.parse_args()
    assert not (ROOT/'GUIDE_STOP.json').exists()
    binding=ROOT/'configs/D3_source_binding_v4.json'
    for item in json.loads(binding.read_text())['files']:assert sha(item['path'])==item['sha256']
    plan_path=ROOT/'configs/performance_crossover_plan_v1.json';plan=json.loads(plan_path.read_text())
    results={key:read_result(ROOT/'reports'/(group+'_seed0_latest.json')) for key,group in [('A0','A0'),('selected',args.selected)]}
    cfgs={key:json.loads((ROOT/'source_v3/workflows/s_denoise/configs'/(result['condition']+'_seed0_v3.json')).read_text()) for key,result in results.items()}
    assert cfgs['selected']['model']['head']['geometry_head']=='equivariant_noise'
    setup_imports()
    with gpu_runtime('performance_crossover_v1') as (output,status):
        import torch,wandb
        from data import selected_components
        from s_model_memory_v1 import build_memory_bounded_model
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler,collate_native_views
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1LossPolicy,Phase1JointSchedule
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
        base=old_configuration();weights=LossWeights.from_mapping(base['training']['loss']);supervision=SupervisionConfig.from_variant('S')
        index,dataset,counts=selected_components('train',seed=0,epoch_noise=True,local_blocks=True)
        sampler=BlockAtomBatchSampler(counts,seed=0,epoch=0,**base['sampler'])
        batches=list(sampler)
        largest=max(batches,key=lambda ids:len(ids)*max(counts.ref(i).native_n_atoms for i in ids)**2)
        selected=[batches[0],largest]
        cpu_batches=[collate_native_views([dataset[i] for i in ids]).encoder_batch for ids in selected]
        dataset.close()
        tracking=wandb.init(project='phychem-mfm-s-denoise-repair',mode='offline',dir=str(output),name='D3_cost_crossover',
            config=dict(plan=plan,plan_sha256=sha(plan_path),selected=args.selected,source_binding_sha256=sha(binding)))
        tracking_exit=1;rows=[]
        journal=(output/'metrics.jsonl').open('x')
        try:
            for block,key in enumerate(plan['crossover_order']):
                cfg=cfgs[key];reference=results[key]['checkpoint'];assert sha(reference['path'])==reference['sha256']
                payload=torch.load(reference['path'],map_location='cpu',weights_only=True)
                model=build_memory_bounded_model(cfg['model']);model.load_state_dict(payload['model'],strict=True)
                before={name:value.clone() for name,value in model.state_dict().items()};del payload
                model=model.cuda().train();policy=Phase1LossPolicy.from_mapping(cfg['loss_policy'])
                # No model learning: this is a compute microbenchmark, not extra D3 updates.
                optimizer=torch.optim.AdamW(model.parameters(),**{**cfg['optimizer'],'lr':0.})
                for step in range(plan['warmup_steps_per_block']+plan['timed_steps_per_block']):
                    batch_number=step%2;batch=cpu_batches[batch_number].clone().to('cuda')
                    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();started=time.perf_counter()
                    optimizer.zero_grad(set_to_none=True)
                    outputs=model.forward_pretrain(batch,supervision.objectives)
                    loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),0,policy=policy)
                    objective=loss.total*cfg['total_loss_scale'];objective.backward()
                    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                    assert bool(torch.isfinite(objective)) and bool(torch.isfinite(norm)),'GUIDE_STOP_NAN_OR_DIVERGENCE'
                    optimizer.step();torch.cuda.synchronize();elapsed=time.perf_counter()-started
                    if step>=plan['warmup_steps_per_block']:
                        row=dict(block=block,case=key,step=step,batch=batch_number,records=len(selected[batch_number]),
                            compute_step_seconds=elapsed,**check_memory(torch,status))
                        rows.append(row);journal.write(json.dumps(row,allow_nan=False)+'\n');journal.flush()
                        tracking.log({k:v for k,v in row.items() if isinstance(v,(float,int))},step=len(rows),commit=True)
                    del outputs,loss,objective,batch
                for name,value in model.state_dict().items():assert torch.equal(value.cpu(),before[name]),'BENCHMARK_MODEL_CHANGED'
                del optimizer,model,before;torch.cuda.empty_cache()
            aggregate={}
            for key in ['A0','selected']:
                subset=[row for row in rows if row['case']==key]
                aggregate[key]=dict(records=sum(r['records'] for r in subset),seconds=sum(r['compute_step_seconds'] for r in subset),
                    records_per_second=sum(r['records'] for r in subset)/sum(r['compute_step_seconds'] for r in subset),
                    peak_allocated_bytes=max(r['gpu_peak_allocated_bytes'] for r in subset),peak_reserved_bytes=max(r['gpu_peak_reserved_bytes'] for r in subset))
            report=dict(status='PAIRED_COMPUTE_CROSSOVER_COMPLETE_PARAMETERS_BITEXACT_UNCHANGED',runtime=status,rows=rows,aggregate=aggregate,
                throughput_selected_over_A0=aggregate['selected']['records_per_second']/aggregate['A0']['records_per_second'],
                allocated_VRAM_delta_bytes=aggregate['selected']['peak_allocated_bytes']-aggregate['A0']['peak_allocated_bytes'],
                reserved_VRAM_delta_bytes=aggregate['selected']['peak_reserved_bytes']-aggregate['A0']['peak_reserved_bytes'],
                foreign_GPU_activity_observed=any(row['foreign_gpu_process_count'] for row in rows),
                source_binding_sha256=sha(binding),plan_reference=dict(path=str(plan_path),sha256=sha(plan_path)),
                checkpoints={key:result['checkpoint'] for key,result in results.items()},
                official_training_updates_added=0,scope='Repair-step compute microbenchmark on two fixed real batch shapes. Full-epoch cost uses actual D3 loader-inclusive rate, not this benchmark.')
            save(output/'result.json',report);save(ROOT/'reports/performance_crossover_latest.json',dict(path=str(output/'result.json'),sha256=sha(output/'result.json')))
            tracking_exit=0
        except Exception as exc:
            if 'GUIDE_STOP_NAN_OR_DIVERGENCE' in str(exc) and not (ROOT/'GUIDE_STOP.json').exists():
                save(ROOT/'GUIDE_STOP.json',dict(reason='GUIDE_STOP_NAN_OR_DIVERGENCE',context='zero-LR performance diagnostic',error=repr(exc)))
            raise
        finally:journal.close();tracking.finish(exit_code=tracking_exit)


if __name__=='__main__':main()
