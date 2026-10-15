"""Bounded native S-path output/gradient/RNG/optimizer/save-resume comparison."""
import csv,fcntl,json,os,socket,subprocess,tempfile,time,shutil,hashlib
from pathlib import Path
from prepare import ROOT,PROJECT,sha,save

CANDIDATE=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'

def query(argv):
    value=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    if value.returncode:raise RuntimeError(value.stderr)
    return value.stdout

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0]=='compute-0-21'
    job=os.environ['SLURM_JOB_ID'];start=time.time();cfg=json.loads(CANDIDATE.read_text())
    assert sha(CANDIDATE)=='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    tolerance_path=ROOT/'configs/s_memory_validation_tolerances_v1.json';tol=json.loads(tolerance_path.read_text())
    apps=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    occupied={row.split(',')[0].strip() for row in apps.splitlines() if row.strip()}
    rows=list(csv.reader(query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()))
    lockdir=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks';lockdir.mkdir(exist_ok=True)
    lock=None;selected=None
    for row in rows:
        if row[0].strip() in occupied or int(row[3])<int(row[2])*.95:continue
        candidate=(lockdir/(row[0].strip()+'.lock')).open('a')
        try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:candidate.close();continue
        lock=candidate;selected=row;break
    assert selected is not None,'No currently idle own-unlocked GPU'
    os.environ['CUDA_VISIBLE_DEVICES']=selected[0].strip()
    scratch=Path(tempfile.mkdtemp(prefix='sconv_memory_equiv_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    os.environ['CUDA_CACHE_PATH']=str(scratch/'cuda_cache')
    report={'status':'RUNNING','job_id':job,'node':socket.gethostname(),'gpu_uuid':selected[0].strip(),
        'gpu_model':selected[1].strip(),'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK',
        'candidate_protocol_sha256':sha(CANDIDATE),'candidate_selected_for_B_training':False,
        'implementation_sha256':sha(ROOT/'scripts/s_model_memory_v1.py'),'tolerance_sha256':sha(tolerance_path),
        'tolerances':tol,'precision':'FP32','formal_B_training_started':False,'original_lmdb_written':False,'new_lmdb_created':False}
    dataset=iterator=None
    try:
        import torch
        from torch.utils.data import DataLoader
        from torch_geometric.data import Batch
        from phychem_mfm.factory import build_model
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1JointSchedule,Phase1LossPolicy
        from phychem_mfm.phase1.full_corpus_loader import _load_bound_native_transport,NATIVE_TRANSPORT_POLICY,collate_native_views,_worker_threads_one,close_prefetch_iterator
        from s_native_adapter_v2 import MappedRecordIndex,ManifestViewsDataset,identity
        from s_model_memory_v1 import build_memory_bounded_model,TiledDistanceMLP
        torch.set_num_threads(8);torch.set_num_interop_threads(1);torch.cuda.init()
        assert torch.cuda.device_count()==1
        seed=lambda:(torch.manual_seed(0),torch.cuda.manual_seed_all(0))
        def rng():return torch.get_rng_state().clone(),torch.cuda.get_rng_state().clone()
        def same_rng(a,b):return all(torch.equal(x,y) for x,y in zip(a,b))
        def compare(a,b,key):
            assert a.shape==b.shape and a.dtype==b.dtype
            maximum=float((a-b).abs().max().detach().cpu()) if a.numel() else 0.0
            assert torch.allclose(a,b,**tol[key]),{'kind':key,'maximum_absolute_difference':maximum}
            return maximum
        # Production tile size is exercised directly on a rowwise MLP larger than 65536 pairs.
        seed();original=torch.nn.Sequential(torch.nn.Linear(1,384),torch.nn.SiLU(),torch.nn.Linear(384,6)).cuda()
        tiled=TiledDistanceMLP(original,tol['production_pair_rows'])
        values=torch.linspace(0,16,131073,device='cuda').reshape(1,1,-1,1).requires_grad_()
        before_rng=rng();expected=original(values);expected.square().mean().backward()
        gradients={n:p.grad.detach().clone() for n,p in original.named_parameters()};input_gradient=values.grad.detach().clone()
        expected=expected.detach();after_original_rng=rng();original.zero_grad(set_to_none=True);values.grad=None
        actual=tiled(values);actual.square().mean().backward();after_tiled_rng=rng()
        mlp={'output_max_abs':compare(expected,actual.detach(),'forward_fp32'),
             'input_gradient_max_abs':compare(input_gradient,values.grad,'gradient_fp32'),
             'parameter_gradient_max_abs':max(compare(gradients[n],p.grad,'gradient_fp32') for n,p in original.named_parameters()),
             'rng_exact':same_rng(before_rng,after_original_rng) and same_rng(before_rng,after_tiled_rng),
             'pair_rows':tol['production_pair_rows'],'input_pairs':131073}
        assert mlp['rng_exact'];report['production_tile_MLP']=mlp
        del original,tiled,values,expected,actual,gradients,input_gradient;torch.cuda.empty_cache()
        transport=cfg['draft_provenance']['runner_artifacts']['native_transport'];binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
        fn=_load_bound_native_transport(Path(transport['path']),binding,identity(transport['path']))
        index=MappedRecordIndex('train',binding,json.loads((ROOT/'training_inputs_v1/shard_snapshot_v1.json').read_text()),verify_hashes=True)
        dataset=ManifestViewsDataset(index,native_transport=fn,native_transport_binding=binding,seed=0,**cfg['views'])
        loader=DataLoader(dataset,batch_sampler=[list(range(32)),list(range(32,64))],collate_fn=collate_native_views,
            num_workers=8,pin_memory=True,worker_init_fn=_worker_threads_one,multiprocessing_context='spawn',prefetch_factor=2,
            persistent_workers=False,timeout=60,generator=torch.Generator().manual_seed(0))
        iterator=iter(loader);first=next(iterator);second=next(iterator)
        batch=first.encoder_batch.to('cuda');next_batch=second.encoder_batch.to('cuda')
        report['actual_record_ids']=[list(first.record_keys),list(second.record_keys)]
        seed();baseline=build_model(cfg['model']).cuda();base_construction_rng=rng()
        seed();bounded=build_memory_bounded_model(cfg['model'],pair_rows=tol['production_pair_rows']).cuda();bounded_construction_rng=rng()
        assert same_rng(base_construction_rng,bounded_construction_rng)
        base_state=baseline.state_dict();bounded_state=bounded.state_dict()
        assert list(base_state)==list(bounded_state) and all(torch.equal(base_state[k],bounded_state[k]) for k in base_state)
        report['paired_initialization_parameter_keys_and_bytes_exact']=True
        supervision=SupervisionConfig.from_variant('S');weights=LossWeights.from_mapping(cfg['training']['loss']);policy=Phase1LossPolicy.from_mapping(cfg['training']['loss_policy'])
        loss_for=lambda model,data:compute_phase1_loss(model.forward_pretrain(data,objectives=supervision.objectives),data,None,supervision,weights,Phase1JointSchedule(),0,policy=policy)
        base_optimizer=torch.optim.AdamW(baseline.parameters(),**cfg['training']['optimizer'])
        optimizer=torch.optim.AdamW(bounded.parameters(),**cfg['training']['optimizer'])
        begin=rng();base_loss=loss_for(baseline,batch);base_loss.total.backward();base_after=rng()
        reference_grad={n:p.grad.detach().clone() for n,p in baseline.named_parameters() if p.grad is not None}
        reference_loss={n:value.detach().clone() for n,value in base_loss.raw.items()}
        bounded_loss=loss_for(bounded,batch);bounded_loss.total.backward();bounded_after=rng()
        actual_grad={n:p.grad for n,p in bounded.named_parameters() if p.grad is not None};assert reference_grad.keys()==actual_grad.keys()
        report['native_full_model']={'loss_max_abs':max(compare(reference_loss[n],v,'forward_fp32') for n,v in bounded_loss.raw.items()),
            'gradient_max_abs':max(compare(reference_grad[n],actual_grad[n],'gradient_fp32') for n in reference_grad),
            'active_gradient_names_equal':True,'rng_exact':same_rng(begin,base_after) and same_rng(begin,bounded_after),
            'implementation':bounded.s_memory_implementation}
        assert report['native_full_model']['rng_exact']
        torch.nn.utils.clip_grad_norm_(baseline.parameters(),cfg['training']['gradient_clip_norm']);torch.nn.utils.clip_grad_norm_(bounded.parameters(),cfg['training']['gradient_clip_norm'])
        base_optimizer.step();optimizer.step()
        report['native_full_model']['optimizer_parameter_max_abs']=max(compare(base_state[n],bounded_state[n],'optimizer_parameter_fp32') for n in base_state)
        del baseline,base_optimizer,base_state,bounded_state,reference_grad,reference_loss,base_loss,bounded_loss;torch.cuda.empty_cache()
        optimizer.zero_grad(set_to_none=True)
        checkpoint_path=scratch/'safe_checkpoint.pt'
        def cpu_tree(value):
            if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
            if isinstance(value,dict):return {k:cpu_tree(v) for k,v in value.items()}
            if isinstance(value,list):return [cpu_tree(v) for v in value]
            if isinstance(value,tuple):return tuple(cpu_tree(v) for v in value)
            assert value is None or type(value) in (str,int,float,bool);return value
        cpu_rng,cuda_rng=rng()
        torch.save({'model':cpu_tree(bounded.state_dict()),'optimizer':cpu_tree(optimizer.state_dict()),'cpu_rng':cpu_rng.cpu(),
                    'cuda_rng':cuda_rng.cpu(),'cursor_records':32,'torch_version':str(torch.__version__),
                    'implementation_sha256':report['implementation_sha256'],'input_manifest_sha256':sha(ROOT/'training_inputs_v1/manifest.json')},checkpoint_path)
        payload=torch.load(checkpoint_path,map_location='cpu',weights_only=True);assert payload['cursor_records']==32
        resumed=build_memory_bounded_model(cfg['model'],pair_rows=tol['production_pair_rows']).cuda();resumed.load_state_dict(payload['model'],strict=True)
        resumed_optimizer=torch.optim.AdamW(resumed.parameters(),**cfg['training']['optimizer']);resumed_optimizer.load_state_dict(payload['optimizer'])
        def advance(model,opt):
            opt.zero_grad(set_to_none=True);loss=loss_for(model,next_batch);loss.total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['training']['gradient_clip_norm']);opt.step();return rng()
        torch.set_rng_state(payload['cpu_rng']);torch.cuda.set_rng_state(payload['cuda_rng']);uninterrupted_rng=advance(bounded,optimizer)
        torch.set_rng_state(payload['cpu_rng']);torch.cuda.set_rng_state(payload['cuda_rng']);resumed_rng=advance(resumed,resumed_optimizer)
        a=bounded.state_dict();b=resumed.state_dict()
        report['safe_save_resume']={'weights_only_readback':'PASS','cursor_records':32,
            'next_update_parameter_max_abs':max(compare(a[n],b[n],'resume_parameter_fp32') for n in a),
            'next_update_rng_exact':same_rng(uninterrupted_rng,resumed_rng),'checkpoint_sha256':sha(checkpoint_path)}
        assert report['safe_save_resume']['next_update_rng_exact']
        report['status']='CANDIDATE_MEMORY_IMPLEMENTATION_NUMERICAL_GRADIENT_RNG_RESUME_PASS'
        report['capacity_acceptance']=False
    except Exception as exc:report.update(status='MEMORY_IMPLEMENTATION_VALIDATION_FAILED',error=repr(exc));raise
    finally:
        if iterator is not None:
            try:close_prefetch_iterator(iterator)
            except Exception as exc:report['loader_cleanup_error']=repr(exc)
        if dataset is not None:dataset.close()
        if 'loader_cleanup_error' in report:report['status']='MEMORY_VALIDATION_OWNED_LOADER_CLEANUP_FAILED'
        report['elapsed_seconds']=time.time()-start
        save(ROOT/'reports/s_model_memory_equivalence_v1.json',report);shutil.rmtree(scratch);lock.close()
    if 'loader_cleanup_error' in report:raise RuntimeError(report['loader_cleanup_error'])
    print(json.dumps({'status':report['status'],'gpu_uuid':report['gpu_uuid']}),flush=True)

if __name__=='__main__':main()
