"""Independent native W&B history and physical checkpoint audit of development."""
import concurrent.futures as cf,json,math,os,time
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2
    import torch
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    start=time.time();segment=ROOT/'development_s_runner/B1_seed0/segment_4515075'
    summary=json.loads((segment/'summary.json').read_text());assert summary['status']=='DEVELOPMENT_ONLY_NO_EPOCH_ACCEPTANCE'
    assert summary['development_only'] is True and summary['consumed_records']==1536 and summary['optimizer_updates']==3
    journal=[json.loads(line) for line in (segment/'metrics.jsonl').read_text().splitlines()]
    assert len(journal)==3 and [r['consumed_records'] for r in journal]==[512,1024,1536]
    files=list((segment/'wandb').glob('offline-run-*/run-*.wandb'));assert len(files)==1
    store=DataStore();store.open_for_scan(str(files[0]));history=[]
    try:
        while (raw:=store.scan_data()) is not None:
            record=wandb_internal_pb2.Record();record.ParseFromString(raw)
            if record.WhichOneof('record_type')!='history':continue
            row={}
            for item in record.history.item:
                key=item.key or '/'.join(item.nested_key);row[key]=json.loads(item.value_json)
            if 'consumed_records' in row:history.append(row)
    finally:store.close()
    assert len(history)==3
    for actual,expected in zip(history,journal):
        for key,value in expected.items():
            assert key in actual,(key,actual.keys())
            if isinstance(value,(float,int)):assert math.isclose(actual[key],value,rel_tol=1e-12,abs_tol=1e-12),(key,actual[key],value)
            else:assert actual[key]==value
    checkpoint=Path(summary['final_checkpoint']['path']);assert sha(checkpoint)==summary['final_checkpoint']['sha256']
    payload=torch.load(checkpoint,map_location='cpu',weights_only=True)
    assert payload['development_only'] is True and payload['consumed_records']==1536 and payload['optimizer_updates']==3
    assert payload['completed_epochs']==[] and payload['coverage'].dtype==torch.uint8
    assert int(payload['coverage'].sum())==1536 and payload['sampler']['committed_records']==1536
    assert payload['scheduler']['consumed_base_exposures']==1536
    paths=[files[0],checkpoint,segment/'summary.json',segment/'metrics.jsonl',ROOT/'configs/s_runner_development_v2.json',ROOT/'scripts/s_convergence_runner_v2.py']
    with cf.ThreadPoolExecutor(max_workers=16) as pool:digests=list(pool.map(sha,paths))
    save(ROOT/'reports/s_runner_development_history_audit_v1.json',{'status':'DEVELOPMENT_NATIVE_HISTORY_AND_CHECKPOINT_AUDIT_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'development_job_id':4515075,'native_WandB_history_rows':len(history),
        'journal_rows':len(journal),'native_history_matches_journal':True,'consumed_records':1536,'optimizer_updates':3,
        'actual_checkpoint_coverage_positions':1536,'weights_only_checkpoint_readback':'PASS',
        'formal_B_training_started':False,'epoch_accepted':False,
        'references':[{'path':str(path),'sha256':digest,'bytes':path.stat().st_size} for path,digest in zip(paths,digests)],
        'elapsed_seconds':time.time()-start})
    print('DEVELOPMENT_NATIVE_HISTORY_AND_CHECKPOINT_AUDIT_PASS',flush=True)

if __name__=='__main__':main()
