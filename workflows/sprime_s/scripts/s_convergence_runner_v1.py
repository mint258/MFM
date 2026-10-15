"""Explicit S-only runner. Formal execution requires a resolved frozen protocol.

Development mode is bounded and cannot produce an epoch/convergence acceptance.
"""
from __future__ import annotations
import argparse,csv,fcntl,json,math,os,signal,socket,subprocess,tempfile,time,shutil
from pathlib import Path
from prepare import ROOT,PROJECT,sha,save

def query(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout

def cpu_tree(value,torch):
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {k:cpu_tree(v,torch) for k,v in value.items()}
    if isinstance(value,list):return [cpu_tree(v,torch) for v in value]
    if isinstance(value,tuple):return tuple(cpu_tree(v,torch) for v in value)
    assert value is None or type(value) in (int,float,str,bool),type(value)
    return value

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--configuration',required=True);ap.add_argument('--resume')
    ap.add_argument('--development-steps',type=int);args=ap.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-20','compute-0-21','compute-0-22']
    config_path=Path(args.configuration);cfg=json.loads(config_path.read_text());config_sha=sha(config_path)
    development=args.development_steps is not None
    if development:assert cfg['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY' and 0<args.development_steps<=8
    else:
        assert cfg['status']=='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN'
        assert cfg['frozen_reference_resolution']['resolved'] is True
    assert cfg['variant']=='S' and cfg['dynamic_balancer_enabled'] is False
    assert cfg['kind'] in ['B1','B3'] and cfg['epochs']==(1 if cfg['kind']=='B1' else 3)
    assert cfg['train_records']==11104772 and cfg['train_molecules']==1206608
    assert sha(cfg['frozen_protocol_reference']['path'])==cfg['frozen_protocol_reference']['sha256']
    protocol=json.loads(Path(cfg['frozen_protocol_reference']['path']).read_text())
    assert cfg['model']==protocol['model'] and cfg['views']==protocol['views'] and cfg['sampler']==protocol['sampler']
    for key in ['optimizer','loss','loss_policy','gradient_clip_norm','schedule','metric_interval','caps','validation']:
        assert cfg['training'][key]==protocol['training'][key]
    for ref in cfg['source_references']:assert sha(ref['path'])==ref['sha256']
    assert sha(ROOT/'training_inputs_v1/manifest.json')==cfg['input_manifest_sha256']
    assert sha(ROOT/'scripts/s_model_memory_v1.py')==cfg['memory_implementation_sha256']
    proof=json.loads((ROOT/'reports/s_model_memory_equivalence_v1.json').read_text())
    assert proof['implementation_sha256']==cfg['memory_implementation_sha256'] and proof['status'].endswith('_PASS')
    job=os.environ['SLURM_JOB_ID'];condition=cfg['kind']+'_seed'+str(cfg['seed'])
    root=ROOT/('development_s_runner' if development else 's_training')/condition
    segment=root/('segment_'+job);segment.mkdir(parents=True,exist_ok=False)
    applications=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    occupied={r.split(',')[0].strip() for r in applications.splitlines() if r.strip()}
    gpu_rows=list(csv.reader(query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()))
    locks=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks';locks.mkdir(exist_ok=True)
    lock=None;selected=None
    for row in gpu_rows:
        if row[0].strip() in occupied or int(row[3])<.95*int(row[2]):continue
        trial=(locks/(row[0].strip()+'.lock')).open('a')
        try:fcntl.flock(trial,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:trial.close();continue
        lock=trial;selected=row;break
    if selected is None:raise RuntimeError('No currently idle own-unlocked GPU')
    os.environ['CUDA_VISIBLE_DEVICES']=selected[0].strip()
    scratch=Path(tempfile.mkdtemp(prefix='sconv_runner_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    os.environ['CUDA_CACHE_PATH']=str(scratch/'cuda_cache');os.environ['WANDB_MODE']='offline'
    requested_stop=False
    def request_stop(signum,frame):
        nonlocal requested_stop
        requested_stop=True
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGUSR1,request_stop)
    status={'status':'STARTING','job_id':job,'node':socket.gethostname(),'condition':condition,'development_only':development,
        'config_sha256':config_sha,'gpu_uuid':selected[0].strip(),'gpu_model':selected[1].strip(),
        'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK','original_lmdb_written':False,'new_lmdb_created':False}
    iterator=dataset=tracking=None;started=time.monotonic();journal=None
    try:
        import numpy as np,torch,wandb
        from s_native_adapter_v2 import MappedRecordIndex,ManifestViewsDataset,CountIndex,identity
        from s_model_memory_v1 import build_memory_bounded_model
        from s_training_components_v1 import ExposureBoundedSampler,EpochCoverage,SMeter,TASKS
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler,make_prefetch_loader,close_prefetch_iterator,_load_bound_native_transport,NATIVE_TRANSPORT_POLICY
        from phychem_mfm.phase1.full_corpus_training import BaseExposureCosine
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1JointSchedule,Phase1LossPolicy
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(8);torch.set_num_interop_threads(1);torch.manual_seed(cfg['seed']);torch.cuda.manual_seed_all(cfg['seed'])
        assert torch.cuda.device_count()==1 and torch.get_default_dtype()==torch.float32
        transport=protocol['draft_provenance']['runner_artifacts']['native_transport']
        binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
        function=_load_bound_native_transport(Path(transport['path']),binding,identity(transport['path']))
        shard_snapshot=json.loads((ROOT/'training_inputs_v1/shard_snapshot_v1.json').read_text())
        index=MappedRecordIndex('train',binding,shard_snapshot,verify_hashes=True);count_index=CountIndex(index)
        dataset=ManifestViewsDataset(index,native_transport=function,native_transport_binding=binding,seed=cfg['seed'],**cfg['views'])
        original_sampler=BlockAtomBatchSampler(count_index,seed=cfg['seed'],epoch=0,**cfg['sampler'])
        events=[math.ceil(.1*len(index)),math.ceil(.25*len(index)),math.ceil(.5*len(index))]
        sampler=ExposureBoundedSampler(original_sampler,events)
        model=build_memory_bounded_model(cfg['model']).cuda().train()
        optimizer=torch.optim.AdamW(model.parameters(),**cfg['training']['optimizer'])
        scheduler=BaseExposureCosine(optimizer,total_base_exposures=len(index)*cfg['epochs'],**cfg['training']['schedule'])
        supervision=SupervisionConfig.from_variant('S');weights=LossWeights.from_mapping(cfg['training']['loss'])
        policy=Phase1LossPolicy.from_mapping(cfg['training']['loss_policy']);coverage=EpochCoverage(len(index))
        consumed=updates=0;completed_epochs=[];validation_history=[];zero_label_batches=0
        if args.resume:
            payload=torch.load(args.resume,map_location='cpu',weights_only=True)
            assert payload.get('scientific_stop',False) is False,'Scientific stop requires a new explicit scientific decision'
            assert payload['config_sha256']==config_sha and payload['memory_implementation_sha256']==cfg['memory_implementation_sha256']
            model.load_state_dict(payload['model'],strict=True);optimizer.load_state_dict(payload['optimizer'])
            while original_sampler.epoch<payload['sampler']['base']['epoch']:
                original_sampler.epoch+=1;original_sampler._block_cache=None
            sampler.load_state_dict(payload['sampler']);scheduler.load_state_dict(payload['scheduler'])
            consumed=payload['consumed_records'];updates=payload['optimizer_updates'];completed_epochs=payload['completed_epochs']
            validation_history=payload['validation_history'];zero_label_batches=payload['zero_label_batches']
            coverage.visited=payload['coverage'].numpy().copy();coverage.consumed=int(coverage.visited.sum());coverage.molecules=set(payload['covered_molecules'])
            assert consumed==len(index)*sampler.epoch+sampler.samples_consumed
            assert coverage.consumed==sampler.samples_consumed
            torch.set_rng_state(payload['cpu_rng']);torch.cuda.set_rng_state(payload['cuda_rng'])
        tracking=wandb.init(project=cfg['tracking']['project'],entity=cfg['tracking'].get('entity'),mode='offline',
            dir=str(segment),group='s_convergence_'+condition,name=condition+'_'+job,
            config={'configuration':cfg,'configuration_sha256':config_sha,'gpu_uuid':selected[0].strip(),'job_id':job,'development_only':development})
        assert tracking is not None and tracking.id and not tracking.disabled
        status['tracking_run_id']=str(tracking.id);status['tracking_mode']='offline'
        journal=(segment/'metrics.jsonl').open('a',encoding='utf-8')
        tracking_step=0;scientific_stop=False
        def log(row):
            nonlocal tracking_step
            row={'consumed_records':consumed,'optimizer_updates':updates,'epoch':consumed/len(index),**row}
            tracking.log(row,step=tracking_step,commit=True);tracking_step+=1
            journal.write(json.dumps(row,allow_nan=False)+'\n');journal.flush();os.fsync(journal.fileno())
        def loss_for(outputs,batch):
            return compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),consumed,policy=policy)
        def checkpoint(label):
            path=segment/(label+'.pt');pending=Path(str(path)+'.pending')
            value={'model':cpu_tree(model.state_dict(),torch),'optimizer':cpu_tree(optimizer.state_dict(),torch),
                'sampler':sampler.state_dict(),'scheduler':scheduler.state_dict(),'coverage':torch.from_numpy(coverage.visited.copy()),
                'covered_molecules':sorted(coverage.molecules),'cpu_rng':torch.get_rng_state().cpu(),'cuda_rng':torch.cuda.get_rng_state().cpu(),
                'config_sha256':config_sha,'memory_implementation_sha256':cfg['memory_implementation_sha256'],
                'consumed_records':consumed,'optimizer_updates':updates,'completed_epochs':completed_epochs,
                'validation_history':validation_history,'zero_label_batches':zero_label_batches,'torch_version':str(torch.__version__),
                'tracking_run_id':str(tracking.id),'development_only':development,'scientific_stop':scientific_stop}
            with pending.open('wb') as stream:torch.save(value,stream);stream.flush();os.fsync(stream.fileno())
            readback=torch.load(pending,map_location='cpu',weights_only=True)
            assert readback['consumed_records']==consumed and readback['optimizer_updates']==updates
            assert readback['sampler']==value['sampler'];pending.replace(path)
            ref={'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'consumed_records':consumed,'optimizer_updates':updates,'label':label}
            save(segment/(label+'.json'),ref);save(root/'latest_checkpoint.json',ref);return ref
        def evaluate(role):
            model.eval();val_index=MappedRecordIndex(role,binding,shard_snapshot,verify_hashes=True)
            val_count=CountIndex(val_index);val_dataset=ManifestViewsDataset(val_index,native_transport=function,native_transport_binding=binding,
                seed=cfg['validation_seed'],**cfg['views'])
            val_sampler=BlockAtomBatchSampler(val_count,seed=cfg['validation_seed'],epoch=0,**cfg['sampler'])
            val_iterator=None;seen=np.zeros(len(val_index),dtype=np.uint8);val_meter=SMeter(weights.cutoff);actual_records=0
            try:
                val_loader=make_prefetch_loader(val_dataset,val_sampler,**cfg['loader'])
                val_iterator=iter(val_loader)
                with torch.no_grad():
                    for corpus in val_iterator:
                        ids=np.asarray(corpus.logical_indices,dtype=np.int64)
                        assert len(np.unique(ids))==len(ids) and not np.any(seen[ids]),'VALIDATION_RECORD_COVERAGE_MISMATCH'
                        refs=[val_index.ref(i) for i in ids]
                        assert tuple(r.record_id for r in refs)==corpus.record_keys,'ACTUAL_RECORD_MANIFEST_MISMATCH'
                        batch=corpus.encoder_batch.to('cuda',non_blocking=True)
                        outputs=model.forward_pretrain(batch,objectives=supervision.objectives);loss=loss_for(outputs,batch)
                        assert bool(torch.isfinite(loss.total)),'NONFINITE_VALIDATION_LOSS'
                        val_meter.add_loss(loss);val_meter.add_outputs(batch,outputs)
                        seen[ids]=1;actual_records+=len(ids)
                        del batch,outputs,loss,corpus
                assert actual_records==len(val_index) and np.all(seen)
                return {'records':actual_records,'missing':0,'duplicates':0,**val_meter.result()}
            finally:
                if val_iterator is not None:close_prefetch_iterator(val_iterator)
                val_dataset.close();val_count.close();model.train()
        def validate():
            values={role:evaluate(role) for role in ['full','routine']}
            row={'consumed_records':consumed,'optimizer_updates':updates,'values':values}
            validation_history.append(row)
            log({'validation/'+role+'/'+key:value for role,items in values.items() for key,value in items.items() if type(value) in (float,int)})
            for role,items in values.items():
                for key,value in items['raw_losses'].items():log({'validation/'+role+'/raw_'+key:value})
            primary=values['full']['geometry_local_pair_A_rmse']
            assert primary is not None
            return consumed>.1*len(index) and primary>=.141
        interval=cfg['training']['metric_interval'];validation_interval=cfg['training']['validation']['every_base_exposures']
        next_validation=(consumed//validation_interval+1)*validation_interval
        named_endpoints={math.ceil(.25*len(index)):'epoch_0p25',math.ceil(.5*len(index)):'epoch_0p5',
                        len(index):'epoch_1',2*len(index):'epoch_2',3*len(index):'epoch_3'}
        meter=SMeter(weights.cutoff);wait_total=step_total=0.;segment_updates=0;scientific_stop=False
        while len(completed_epochs)<cfg['epochs']:
            loader=make_prefetch_loader(dataset,sampler,**cfg['loader']);iterator=iter(loader)
            try:
                while True:
                    if requested_stop or time.monotonic()-started>=cfg['training']['caps']['segment_wall_seconds']-cfg['training']['caps']['finalization_reserve_seconds']:break
                    try:
                        wait_started=time.perf_counter();corpus=next(iterator);wait=time.perf_counter()-wait_started
                    except StopIteration:break
                    refs=[index.ref(i) for i in corpus.logical_indices]
                    assert tuple(r.record_id for r in refs)==corpus.record_keys,'ACTUAL_RECORD_MANIFEST_MISMATCH'
                    optimizer.zero_grad(set_to_none=True);lr_used=float(optimizer.param_groups[0]['lr'])
                    step_started=time.perf_counter();batch=corpus.encoder_batch.to('cuda',non_blocking=True)
                    outputs=model.forward_pretrain(batch,objectives=supervision.objectives);loss=loss_for(outputs,batch)
                    assert bool(torch.isfinite(loss.total)),'SCIENTIFIC_STOP_NONFINITE_TRAINING_LOSS'
                    if any(loss.counts.get(key,0)>0 for key in TASKS):
                        loss.total.backward();gradient=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['training']['gradient_clip_norm'])
                        assert bool(torch.isfinite(gradient)),'SCIENTIFIC_STOP_NONFINITE_GRADIENT'
                        optimizer.step();updates+=1;segment_updates+=1;gradient_value=float(gradient.detach().cpu())
                    else:zero_label_batches+=1;gradient_value=0.
                    torch.cuda.synchronize();elapsed_step=time.perf_counter()-step_started
                    meter.add_loss(loss)
                    meter.add_outputs(batch,outputs)
                    sampler.commit_batch(corpus.logical_indices)
                    coverage.add(corpus.logical_indices,[r.molecule_id for r in refs]);consumed+=len(refs);scheduler.set_consumed(consumed)
                    wait_total+=wait;step_total+=elapsed_step
                    if updates%interval==0 or development:
                        metrics=meter.result();row={'train/raw_'+key:value for key,value in metrics['raw_losses'].items() if value is not None}
                        row.update({'train/'+key:value for key,value in metrics.items() if type(value) in (float,int)})
                        row.update({'lr_used':lr_used,'lr_next':float(optimizer.param_groups[0]['lr']),
                            'gradient_norm_before_clip':gradient_value,'segment_records_per_second':(consumed-(payload['consumed_records'] if args.resume else 0))/(time.monotonic()-started),
                            'loader_wait_fraction':wait_total/max(wait_total+step_total,1e-12),
                            'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'gpu_peak_reserved_bytes':torch.cuda.max_memory_reserved()})
                        log(row);meter=SMeter(weights.cutoff)
                    del corpus,batch,outputs,loss;optimizer.zero_grad(set_to_none=True)
                    endpoint=consumed in named_endpoints and (cfg['kind']=='B3' or consumed==len(index))
                    crossing_stop=consumed==math.ceil(.1*len(index))
                    if not development and (consumed>=next_validation or endpoint or crossing_stop):
                        scientific_stop=validate();next_validation=(consumed//validation_interval+1)*validation_interval
                        checkpoint('validated_'+str(consumed))
                        if endpoint:checkpoint(named_endpoints[consumed])
                        if scientific_stop:break
                    if development and segment_updates>=args.development_steps:break
            finally:close_prefetch_iterator(iterator);iterator=None
            if scientific_stop or development and segment_updates>=args.development_steps:break
            if sampler.samples_consumed==len(index):
                folded=coverage.finish(cfg['train_molecules']);completed_epochs.append({'epoch':sampler.epoch+1,**folded})
                checkpoint('completed_epoch_'+str(sampler.epoch+1))
                if len(completed_epochs)==cfg['epochs']:break
                sampler.advance_epoch();coverage=EpochCoverage(len(index))
            else:break
        if scientific_stop:final_status='SCIENTIFIC_STOP_DENOISER_NOT_BELOW_NOISY_REFERENCE'
        elif development:final_status='DEVELOPMENT_ONLY_NO_EPOCH_ACCEPTANCE'
        elif len(completed_epochs)==cfg['epochs']:final_status='TRAINING_EXPOSURES_COMPLETE_AWAITING_H0_PROBES'
        else:final_status='PARTIAL_CHECKPOINT_REQUIRES_CONTINUATION'
        status.update(status=final_status,consumed_records=consumed,optimizer_updates=updates,completed_epochs=completed_epochs,
            scientific_stop=scientific_stop,zero_label_batches=zero_label_batches,validation_history=validation_history,
            epoch_accepted=not development and len(completed_epochs)==cfg['epochs'])
        status['final_checkpoint']=checkpoint('segment_final')
    except Exception as exc:status.update(status='RUNNER_FAILED',error=repr(exc));raise
    finally:
        if iterator is not None:
            try:close_prefetch_iterator(iterator)
            except Exception as exc:status['loader_cleanup_error']=repr(exc)
        if dataset is not None:dataset.close()
        if journal is not None:journal.close()
        if tracking is not None:
            try:tracking.finish(exit_code=0 if 'error' not in status and 'loader_cleanup_error' not in status else 1)
            except Exception as exc:status['tracking_finish_error']=repr(exc)
        status['elapsed_seconds']=time.monotonic()-started
        save(segment/'summary.json',status);shutil.rmtree(scratch);lock.close()
    if 'loader_cleanup_error' in status:raise RuntimeError(status['loader_cleanup_error'])
    if 'tracking_finish_error' in status:raise RuntimeError(status['tracking_finish_error'])

if __name__=='__main__':main()
