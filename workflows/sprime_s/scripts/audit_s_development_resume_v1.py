"""Audit actual restored cursor, next inputs, config and native persisted history."""
import json,math,os
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    import torch
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    parent=ROOT/'development_s_runner/B1_seed0/segment_4515075'
    resumed=ROOT/'development_s_runner/B1_seed0/segment_4515077'
    p=json.loads((parent/'summary.json').read_text());r=json.loads((resumed/'summary.json').read_text())
    assert p['development_only'] is r['development_only'] is True
    assert p['config_sha256']==r['config_sha256'] and p['gpu_uuid']==r['gpu_uuid']
    a=torch.load(p['final_checkpoint']['path'],map_location='cpu',weights_only=True)
    b=torch.load(r['final_checkpoint']['path'],map_location='cpu',weights_only=True)
    assert a['consumed_records']==1536 and b['consumed_records']==2006
    assert a['optimizer_updates']==3 and b['optimizer_updates']==4
    assert torch.all((a['coverage']==0)|(b['coverage']==1))
    added=torch.where((a['coverage']==0)&(b['coverage']==1))[0]
    assert len(added)==470 and int(b['coverage'].sum())==2006
    assert b['sampler']['committed_records']==2006 and b['scheduler']['consumed_base_exposures']==2006
    assert b['memory_implementation_sha256']==a['memory_implementation_sha256']
    files=list((resumed/'wandb').glob('offline-run-*/run-*.wandb'));assert len(files)==1
    expected=[json.loads(line) for line in (resumed/'metrics.jsonl').read_text().splitlines()];assert len(expected)==1
    history=[];store=DataStore();store.open_for_scan(str(files[0]))
    try:
        while (raw:=store.scan_data()) is not None:
            rec=wandb_internal_pb2.Record();rec.ParseFromString(raw)
            if rec.WhichOneof('record_type')=='history':
                row={item.key or '/'.join(item.nested_key):json.loads(item.value_json) for item in rec.history.item}
                if 'consumed_records' in row:history.append(row)
    finally:store.close()
    assert len(history)==1
    for key,value in expected[0].items():assert math.isclose(history[0][key],value,rel_tol=1e-12,abs_tol=1e-12)
    save(ROOT/'reports/s_runner_development_resume_audit_v1.json',{'status':'DEVELOPMENT_ACTUAL_CURSOR_NEXT_RECORDS_AND_NATIVE_HISTORY_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'parent_development_job':4515075,'resume_development_job':4515077,
        'configuration_sha256':r['config_sha256'],'parent_consumed_records':1536,'resumed_consumed_records':2006,
        'new_distinct_record_positions':470,'parent_positions_retained':True,'new_positions_overlap_parent':False,
        'optimizer_updates':4,'native_history_matches_journal':True,'native_history_rows':1,
        'cpu_rng_equal_between_saved_endpoints':torch.equal(a['cpu_rng'],b['cpu_rng']),
        'cuda_rng_equal_between_saved_endpoints':torch.equal(a['cuda_rng'],b['cuda_rng']),
        'parent_checkpoint_sha256':sha(p['final_checkpoint']['path']),'resumed_checkpoint_sha256':sha(r['final_checkpoint']['path']),
        'uninterrupted_full_runner_parameter_comparison_performed':False,
        'formal_B_training_started':False,'epoch_accepted':False})
    print('DEVELOPMENT_ACTUAL_CURSOR_NEXT_RECORDS_AND_NATIVE_HISTORY_PASS',flush=True)

if __name__=='__main__':main()
