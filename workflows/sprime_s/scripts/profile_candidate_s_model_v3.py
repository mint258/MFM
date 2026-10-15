"""Bounded actual S-model interface profile; historical candidate is not selected."""
import concurrent.futures as cf,csv,fcntl,json,os,socket,subprocess,tempfile,time,shutil
from pathlib import Path
from prepare import ROOT,PROJECT,sha,save

RUNTIME=Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime')
CANDIDATE=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'

def query(argv):
    value=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    if value.returncode:raise RuntimeError(value.stderr)
    return value.stdout

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0]=='compute-0-21'
    start=time.time();job=os.environ['SLURM_JOB_ID'];cfg=json.loads(CANDIDATE.read_text())
    assert sha(CANDIDATE)=='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    applications=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    occupied={r.split(',')[0].strip() for r in applications.splitlines() if r.strip()}
    gpus=list(csv.reader(query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()))
    lockdir=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks';lockdir.mkdir(exist_ok=True)
    lock=None;selected=None
    for gpu in gpus:
        uuid=gpu[0].strip()
        if uuid in occupied or int(gpu[3])<int(gpu[2])*.95:continue
        candidate_lock=(lockdir/(uuid+'.lock')).open('a')
        try:fcntl.flock(candidate_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:candidate_lock.close();continue
        lock=candidate_lock;selected=gpu;break
    if selected is None:raise RuntimeError('No idle unlocked GPU for this bounded owned profile')
    uuid=selected[0].strip();os.environ['CUDA_VISIBLE_DEVICES']=uuid
    scratch=Path(tempfile.mkdtemp(prefix='sconv_model_profile_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    os.environ['CUDA_CACHE_PATH']=str(scratch/'cuda_cache')
    result={'status':'RUNNING_CANDIDATE_INTERFACE_PROFILE','job_id':job,'node':socket.gethostname(),
        'gpu_uuid':uuid,'gpu_model':selected[1].strip(),'total_memory_mib':int(selected[2]),'start_free_memory_mib':int(selected[3]),
        'logical_interpreter':os.path.abspath(os.sys.executable),'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK',
        'candidate_protocol':{'path':str(CANDIDATE),'sha256':sha(CANDIDATE),'selected_for_B_training':False},
        'input_manifest_sha256':sha(ROOT/'training_inputs_v1/manifest.json'),'cases':[],'optimizer_updates':0,
        'formal_B_training_started':False,'original_lmdb_written':False,'new_lmdb_created':False}
    iterator=dataset=None
    try:
        source_files={name:digest for name,digest in cfg['source_reuse_proof']['unchanged_file_sha256'].items() if name=='phychem_mfm/factory.py' or name.startswith('phychem_mfm/model/')}
        assert source_files and 'phychem_mfm/factory.py' in source_files
        def source_check(item):
            name,digest=item;assert sha(RUNTIME/name)==digest;return {'path':str(RUNTIME/name),'sha256':digest}
        with cf.ThreadPoolExecutor(max_workers=16) as pool:result['model_source_references']=list(pool.map(source_check,source_files.items()))
        import torch,numpy as np
        from torch.utils.data import DataLoader
        from phychem_mfm.factory import build_model
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1LossPolicy,Phase1JointSchedule
        from phychem_mfm.phase1.full_corpus_loader import _load_bound_native_transport,NATIVE_TRANSPORT_POLICY,collate_native_views,_worker_threads_one,close_prefetch_iterator
        from s_native_adapter_v2 import MappedRecordIndex,ManifestViewsDataset,identity
        torch.set_num_threads(8);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
        assert torch.cuda.device_count()==1
        assert os.environ.get('PYTORCH_ALLOC_CONF')=='expandable_segments:True'
        allocator_probe=torch.empty((1024,1024),dtype=torch.float32,device='cuda').fill_(1)
        torch.cuda.synchronize();segments=torch.cuda.memory_snapshot()
        assert any(segment.get('is_expandable') is True for segment in segments),'Native expandable segment was not observed'
        result['allocator_compatibility']={'status':'SMALL_OWNED_ALLOCATION_EXPANDABLE_SEGMENT_OBSERVED','backend':torch.cuda.memory.get_allocator_backend(),'configuration':os.environ['PYTORCH_ALLOC_CONF']}
        del allocator_probe;torch.cuda.empty_cache()
        result.update(torch=str(torch.__version__),cuda_runtime=torch.version.cuda,cpu_threads=8,loader_workers=8,precision='FP32')
        transport=cfg['draft_provenance']['runner_artifacts']['native_transport'];binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
        function=_load_bound_native_transport(Path(transport['path']),binding,identity(transport['path']))
        snapshot=json.loads((ROOT/'training_inputs_v1/shard_snapshot_v1.json').read_text())
        index=MappedRecordIndex('train',binding,snapshot,verify_hashes=True);index._open()
        result['cross_node_device_observations']=index.cross_node_device_observations
        result['cross_node_identity_proof_sha256']=sha(ROOT/'reports/cross_node_native_identity_v1.json')
        largest_indices=np.argpartition(index._atoms,-64)[-64:];largest_indices=sorted([int(i) for i in largest_indices],key=lambda i:(-int(index._atoms[i]),i))
        boundary=[];largest_n=0;native_sum=0
        for i in largest_indices:
            n=int(index._atoms[i]);new_largest=max(largest_n,n)
            if boundary and (3*(len(boundary)+1)*new_largest**2>cfg['sampler']['max_padded_cost'] or native_sum+n>cfg['sampler']['max_native_atoms']):break
            boundary.append(i);largest_n=new_largest;native_sum+=n
        batches=[list(range(32)),[largest_indices[0]],boundary]
        labels=['typical_32_distinct_native_records','largest_native_record_singleton','actual_large_records_near_padding_budget']
        dataset=ManifestViewsDataset(index,native_transport=function,native_transport_binding=binding,seed=0,**cfg['views'])
        loader=DataLoader(dataset,batch_sampler=batches,collate_fn=collate_native_views,num_workers=8,pin_memory=True,
                          worker_init_fn=_worker_threads_one,multiprocessing_context='spawn',prefetch_factor=2,persistent_workers=False,
                          generator=torch.Generator().manual_seed(0),timeout=60)
        model=build_model(cfg['model']).cuda().train();supervision=SupervisionConfig.from_variant('S')
        optimizer=torch.optim.AdamW(model.parameters(),**cfg['training']['optimizer'])
        weights=LossWeights.from_mapping(cfg['training']['loss']);policy=Phase1LossPolicy.from_mapping(cfg['training']['loss_policy'])
        result['fixed_task_weights']={name:policy.task_weights[name] for name in ['element','distance','bond_order']}
        result['dynamic_balancer_enabled']=False;iterator=iter(loader)
        for label in labels:
            wait_start=time.perf_counter();corpus=next(iterator);load_wait=time.perf_counter()-wait_start
            case={'label':label,'records':len(corpus.record_keys),'record_ids':list(corpus.record_keys),
                  'max_native_atoms':max(corpus.native_atom_counts),'native_atom_sum':sum(corpus.native_atom_counts),
                  'padded_cost':corpus.padded_cost(3),'load_wait_seconds':load_wait}
            result['cases'].append(case);assert len(set(corpus.record_keys))==len(corpus.record_keys)
            assert len(corpus.record_keys)==1 or (case['padded_cost']<=cfg['sampler']['max_padded_cost'] and case['native_atom_sum']<=cfg['sampler']['max_native_atoms'])
            torch.cuda.reset_peak_memory_stats();step_start=time.perf_counter();batch=corpus.encoder_batch.to('cuda',non_blocking=True)
            optimizer.zero_grad(set_to_none=True);outputs=model.forward_pretrain(batch,objectives=supervision.objectives)
            loss=compute_phase1_loss(outputs,batch,None,supervision,weights,Phase1JointSchedule(),0,policy=policy)
            assert bool(torch.isfinite(loss.total))
            loss.total.backward();gradient=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['training']['gradient_clip_norm'])
            assert bool(torch.isfinite(gradient));optimizer.step();torch.cuda.synchronize()
            result['optimizer_updates']+=1
            case.update(status='FORWARD_BACKWARD_OPTIMIZER_PASS',loss_total=float(loss.total.detach().cpu()),
                raw_losses={key:float(value.detach().cpu()) for key,value in loss.raw.items()},gradient_norm_before_clip=float(gradient.detach().cpu()),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                step_seconds=time.perf_counter()-step_start,supervision=supervision.to_dict())
            save(ROOT/'reports'/('candidate_s_model_profile_'+job+'.json'),result)
            del outputs,loss,batch,corpus;optimizer.zero_grad(set_to_none=True);torch.cuda.empty_cache()
        result['status']='BOUNDED_CANDIDATE_S_MODEL_PATH_PASS'
        result['capacity_scope']='Three actual native-record cases under the candidate FP32 architecture and batch budget; not exhaustive future-batch or formal convergence acceptance.'
    except Exception as exc:
        result.update(status='CANDIDATE_S_MODEL_PROFILE_FAILED',error=repr(exc));raise
    finally:
        if iterator is not None:
            try:close_prefetch_iterator(iterator)
            except Exception as exc:result['loader_cleanup_error']=repr(exc)
        if dataset is not None:dataset.close()
        if 'loader_cleanup_error' in result and result['status']=='BOUNDED_CANDIDATE_S_MODEL_PATH_PASS':
            result['status']='MODEL_PATH_PASS_OWNED_LOADER_CLEANUP_FAILED'
        result['elapsed_seconds']=time.time()-start
        save(ROOT/'reports'/('candidate_s_model_profile_'+job+'.json'),result)
        shutil.rmtree(scratch);lock.close()
    print(json.dumps({'status':result['status'],'optimizer_updates':result['optimizer_updates'],'gpu_uuid':uuid}),flush=True)
    if 'loader_cleanup_error' in result:raise RuntimeError('Owned loader cleanup failed: '+result['loader_cleanup_error'])

if __name__=='__main__':main()
