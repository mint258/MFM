"""Close the original lookup against actual Sonmi accounting and pinned recipe bytes.

Standard-library metadata only. Does not fit, evaluate or submit any experiment.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,math,os,socket,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
GUIDE='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'
def ref(path):
    path=Path(path);raw=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def check(row):
    value=ref(row['path']);assert value['sha256']==row['sha256'],('PINNED_RECIPE_CHANGED',row['path']);return value
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert ref(ROOT/'user_repair_guide.md')['sha256']==GUIDE
    snapshot=ROOT/'control/accounting_snapshots/lookup_complete_v1.json';d=json.loads(snapshot.read_text())
    assert d['status']=='ACTUAL_SONMI_SACCT_SNAPSHOT' and d['uid']==1278 and d['host'].split('.')[0]=='sonmi'
    assert d['columns']==['State','ExitCode','ElapsedRaw','AllocCPUS']
    row=d['rows']['4515527'];raw={v[0]:v[1:] for v in (x.split('|') for x in d['raw_stdout'].splitlines())}
    assert row==raw['4515527'] and row[:2]==['COMPLETED','0:0']
    pointer=json.loads((ROOT/'reports/lookup_latest.json').read_text());check(pointer)
    result=json.loads(Path(pointer['path']).read_text())
    assert result['status']=='NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE'
    assert result['TRAIN_records']==11104772 and result['validation_values_used_for_fit'] is False
    assert result['view_seed']==0 and result['evaluation_epoch']==0 and result['sigma_A']==.1 and result['noise_seed_includes_epoch'] is True
    for role,n in [('full',127082),('D3_FULL2000',18486)]:
        value=result['metrics'][role];assert value['records']==n and value['pairs']>0
        assert math.isfinite(value['lookup_rmse_A']) and value['lookup_rmse_A']>0
        assert 0<=value['lookup_used_pairs']<=value['pairs']
    plan_path=ROOT/'configs/lookup_refit_v2_plan.json';plan=json.loads(plan_path.read_text())
    canonical=[x for x in plan['sources'] if not x['path'].endswith(('lookup_refit_chunks_v2.py','reduce_lookup_chunks_v2.py'))]
    with ThreadPoolExecutor(16) as pool:sources=list(pool.map(check,canonical))
    manifest=next(x for x in sources if x['path'].endswith('/training_inputs_v1/manifest.json'))
    assert result['input_manifest_sha256']==manifest['sha256']
    receipt_path=ROOT/'submission/lookup_v1.json';receipt=json.loads(receipt_path.read_text())
    assert receipt['job_id']=='4515527';check({'path':receipt['script'],'sha256':receipt['sha256']})
    outputs=[ref(ROOT/'diagnostics/lookup_refit_v1'/name) for name in ['TRAIN_only_bin_statistics.json','TRAIN_only_lookup.json','result.json']]
    doc={'status':'ACTUAL_FULL_TRAIN_LOOKUP_REFIT_CLOSED','job_id':'4515527','uid':1278,'host':'sonmi','timestamp_unix':time.time(),
       'guide_sha256':GUIDE,'actual_parent':row,'actual_parent_snapshot':ref(snapshot),'result_reference':pointer,
       'source_plan_reference':ref(plan_path),'canonical_recipe_sources':sources,'output_references':outputs,
       'submission_reference':ref(receipt_path),'TRAIN_records':result['TRAIN_records'],'metrics':result['metrics'],
       'producer':'original refit_lookup.py; alternative v2 pilot and parts did not produce this baseline',
       'new_fit_performed_by_this_closure':False,'formal_training_authorized_by_this_closure':False}
    path=ROOT/'configs/lookup_refit_closure_v1.json'
    with path.open('x') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':doc['status'],'reference':ref(path),'metrics':doc['metrics']}),flush=True)
if __name__=='__main__':main()
