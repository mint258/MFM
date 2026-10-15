"""Check exposure splitting/resume and native S metrics against audited evaluator."""
import csv,fcntl,json,os,socket,subprocess,tempfile,shutil,time
from pathlib import Path
from types import SimpleNamespace
from prepare import ROOT,PROJECT,sha,save

def query(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr;return p.stdout

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0]=='compute-0-21'
    job=os.environ['SLURM_JOB_ID'];start=time.time()
    apps=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    occupied={r.split(',')[0].strip() for r in apps.splitlines() if r.strip()}
    rows=list(csv.reader(query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()))
    lockdir=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks';lockdir.mkdir(exist_ok=True)
    lock=None;selected=None
    for row in rows:
        if row[0].strip() in occupied or int(row[3])<.95*int(row[2]):continue
        candidate=(lockdir/(row[0].strip()+'.lock')).open('a')
        try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:candidate.close();continue
        lock=candidate;selected=row;break
    assert selected is not None;os.environ['CUDA_VISIBLE_DEVICES']=selected[0].strip()
    scratch=Path(tempfile.mkdtemp(prefix='sconv_components_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    os.environ['CUDA_CACHE_PATH']=str(scratch/'cuda_cache')
    report={'status':'RUNNING','job_id':job,'gpu_uuid':selected[0].strip(),'node':socket.gethostname(),
        'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK','optimizer_updates':0,'formal_B_training_started':False,
        'component_sha256':sha(ROOT/'scripts/s_training_components_v1.py')}
    iterator=dataset=None
    try:
        import torch,numpy as np
        from torch.utils.data import DataLoader
        from s_training_components_v1 import ExposureBoundedSampler,EpochCoverage,SMeter
        from s_model_memory_v1 import build_memory_bounded_model
        from s_native_adapter_v2 import MappedRecordIndex,ManifestViewsDataset,identity
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler,_load_bound_native_transport,NATIVE_TRANSPORT_POLICY,collate_native_views,_worker_threads_one,close_prefetch_iterator
        from phychem_mfm.phase1.evaluation import OriginalUnitEvaluator
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.phase1.objectives import compute_phase1_loss,Phase1LossPolicy,Phase1JointSchedule
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(8);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
        class FixtureIndex:
            content_sha256='1'*64
            def __len__(self):return 73
            def ref(self,i):return SimpleNamespace(native_n_atoms=3+(i%11))
        index=FixtureIndex();params={'block_size':17,'max_molecules':9,'max_native_atoms':100,'atom_bucket_width':4,'max_padded_cost':1500,'padded_cost_multiplier':3}
        def sampler():return ExposureBoundedSampler(BlockAtomBatchSampler(index,seed=0,epoch=0,**params),[8,19,36,52])
        first_sampler=sampler();prefetched=list(first_sampler);assert first_sampler.samples_consumed==0
        expected=[i for batch in prefetched for i in batch];assert len(expected)==73 and len(set(expected))==73
        for batch in prefetched[:3]:first_sampler.commit_batch(batch)
        state=json.loads(json.dumps(first_sampler.state_dict()));resumed=sampler();resumed.load_state_dict(state)
        suffix=list(resumed);assert suffix==prefetched[3:]
        coverage=EpochCoverage(73)
        for batch in prefetched:coverage.add(batch,[str(i//2) for i in batch])
        assert coverage.finish(37)['records']==73
        actual_events=[];s=sampler()
        for batch in s:
            s.commit_batch(batch)
            if s.samples_consumed in s.events:actual_events.append(s.samples_consumed)
        assert actual_events==[8,19,36,52] and s.samples_consumed==73
        s.advance_epoch();assert s.epoch==1 and s.samples_consumed==0
        report['exposure_sampler']={'prefetch_committed_records':0,'records':73,'duplicates':0,'missing':0,
            'exact_events':actual_events,'split_cursor_resume_suffix_exact':True,'epoch_advance':'PASS'}
        cfgpath=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'
        cfg=json.loads(cfgpath.read_text());assert sha(cfgpath)=='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
        transport=cfg['draft_provenance']['runner_artifacts']['native_transport'];binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
        fn=_load_bound_native_transport(Path(transport['path']),binding,identity(transport['path']))
        native_index=MappedRecordIndex('train',binding,json.loads((ROOT/'training_inputs_v1/shard_snapshot_v1.json').read_text()),verify_hashes=True)
        dataset=ManifestViewsDataset(native_index,native_transport=fn,native_transport_binding=binding,seed=0,**cfg['views'])
        loader=DataLoader(dataset,batch_sampler=[list(range(32))],collate_fn=collate_native_views,num_workers=8,pin_memory=True,
            worker_init_fn=_worker_threads_one,multiprocessing_context='spawn',prefetch_factor=2,persistent_workers=False,timeout=60,
            generator=torch.Generator().manual_seed(0))
        iterator=iter(loader);corpus=next(iterator);batch=corpus.encoder_batch.to('cuda')
        model=build_memory_bounded_model(cfg['model']).cuda().eval();supervision=SupervisionConfig.from_variant('S')
        with torch.no_grad():
            outputs=model.forward_pretrain(batch,objectives=supervision.objectives)
            loss=compute_phase1_loss(outputs,batch,None,supervision,LossWeights.from_mapping(cfg['training']['loss']),Phase1JointSchedule(),0,
                policy=Phase1LossPolicy.from_mapping(cfg['training']['loss_policy']))
            meter=SMeter(2.);meter.add_loss(loss);meter.add_outputs(batch,outputs);values=meter.result()
            baselines=SimpleNamespace(element_majority=None,bond_majority=None,unavailable={})
            audited=OriginalUnitEvaluator(model,baselines,cutoff=2.);audited.add(batch,outputs);reference=audited.result()['targets']
        for our,old in [('geometry_local_pair_A_rmse','geometry_local_pair_A'),('geometry_all_pair_A_rmse','geometry_all_pair_A')]:
            assert values[our] is not None and abs(values[our]-reference[old]['model']['rmse'])<1e-10
        assert values['geometry_local_pair_count']==reference['geometry_local_pair_A']['model']['count']
        assert values['geometry_all_pair_count']==reference['geometry_all_pair_A']['model']['count']
        assert values['element_accuracy']==reference['element']['model']['accuracy']
        assert values['bond_order_accuracy']==reference['bond_order']['model']['accuracy']
        assert abs(values['actual_noisy_local_pair_A_rmse']-reference['geometry_local_pair_A']['baseline']['rmse'])<1e-10
        report['native_metric_comparison']={'records':len(corpus.record_keys),'status':'S_METRICS_MATCH_AUDITED_EVALUATOR','actual_metrics':values}
        report['status']='S_TRAINING_COMPONENTS_ONLY_PASS'
    except Exception as exc:report.update(status='S_COMPONENTS_CHECK_FAILED',error=repr(exc));raise
    finally:
        if iterator is not None:
            try:close_prefetch_iterator(iterator)
            except Exception as exc:report['loader_cleanup_error']=repr(exc)
        if dataset is not None:dataset.close()
        if 'loader_cleanup_error' in report:report['status']='S_COMPONENTS_LOADER_CLEANUP_FAILED'
        report['elapsed_seconds']=time.time()-start
        save(ROOT/'reports/s_training_components_check_v2.json',report);shutil.rmtree(scratch);lock.close()
    if 'loader_cleanup_error' in report:raise RuntimeError(report['loader_cleanup_error'])
    print('S_TRAINING_COMPONENTS_ONLY_PASS',flush=True)

if __name__=='__main__':main()
