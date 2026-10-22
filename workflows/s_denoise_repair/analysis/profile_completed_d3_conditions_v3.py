"""Profile complete D3 groups with the original cost function; never declares a gate or submits."""
from concurrent.futures import ThreadPoolExecutor
import argparse,csv,hashlib,json,math,os,socket,time
from pathlib import Path
from stage3_gate_v4 import estimate_cost,query_parents
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
GUIDE='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'
def ref(path):
    path=Path(path);raw=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def check(row):assert ref(row['path'])['sha256']==row['sha256'];return row
def mean_defined_cosines(grads,pairs):
    """Zero-norm gradient angles are undefined, not numeric zero."""
    means,counts={},{}
    assert len(grads)==20
    for pair in sorted(pairs):
        values=[g['diagnostics']['cosine_similarities'][pair] for g in grads]
        assert all(v is None or (isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<=1.000001) for v in values)
        defined=[v for v in values if v is not None]
        counts[pair]={'defined_batches':len(defined),'total_batches':20}
        means[pair]=math.fsum(defined)/len(defined) if defined else None
    return means,counts

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',required=True);ap.add_argument('--conditions',nargs='+',required=True)
    ap.add_argument('--parent-snapshot',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]]
    assert a.phase.isidentifier() and all(c.isidentifier() for c in a.conditions)
    assert a.output.is_absolute() and a.output.is_relative_to(ROOT/'reports') and not a.output.exists()
    assert ref(ROOT/'user_repair_guide.md')['sha256']==GUIDE
    started=time.monotonic();binding=ROOT/'configs/D3_source_binding_v4.json'
    with ThreadPoolExecutor(16) as pool:list(pool.map(check,json.loads(binding.read_text())['files']))
    ledger_path=ROOT/'control'/a.phase/'jobs.json';ledger=json.loads(ledger_path.read_text())
    keys=[c+'_seed'+str(s) for c in a.conditions for s in [0,1]]
    actual=query_parents({ledger[key]['job_id'] for key in keys},a.parent_snapshot)
    estimator_path=ROOT/'configs/cost_estimator_v2.json';estimator=json.loads(estimator_path.read_text())
    rows=[];sources=[ref(binding),ref(a.parent_snapshot),ref(estimator_path),ref(ROOT/'analysis/stage3_gate_v4.py'),ref(Path(__file__))]
    for key in keys:
        entry=ledger[key];pointer=json.loads((ROOT/'reports'/(key+'_latest.json')).read_text());check(pointer)
        path=Path(pointer['path']);result=json.loads(path.read_text());curve_path=path.with_name('curve.json');curve=json.loads(curve_path.read_text())
        cfg=json.loads(Path(entry['configuration']).read_text());check({'path':entry['configuration'],'sha256':entry['configuration_sha256']})
        assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000
        assert result['condition']==cfg['condition'] and result['seed']==cfg['seed'] and result['runtime']['job_id']==entry['job_id']
        assert result['configuration_sha256']==entry['configuration_sha256']
        grads=result['final_gradient_rows'];assert len(grads)==20 and [g['optimizer_update'] for g in grads]==list(range(3980,4000))
        tasks=set(grads[0]['diagnostics']['norms']);assert tasks
        means={};fractions={}
        for task in sorted(tasks):
            norms=[g['diagnostics']['norms'][task] for g in grads]
            shares=[g['diagnostics']['fractions_of_sum_of_norms'][task] for g in grads]
            assert all(math.isfinite(v) and v>=0 for v in norms+shares)
            means[task]=math.fsum(norms)/20;fractions[task]=math.fsum(shares)/20
        assert abs(math.fsum(fractions.values())-1)<1e-5
        pairs=set(grads[0]['diagnostics']['cosine_similarities'])
        cos,cos_counts=mean_defined_cosines(grads,pairs)
        cost=estimate_cost(result,curve,int(actual[entry['job_id']][2]),estimator)
        row={'condition':cfg['condition'],'seed':cfg['seed'],'job_id':entry['job_id'],'LR':cfg['optimizer']['lr'],
          'optimizer_updates':4000,'consumed_records':result['consumed_records'],'final':result['final'],
          'recorded_shared_gradient_norm_means':means,'mean_of_per_batch_shared_gradient_fractions':fractions,
          'mean_pair_gradient_cosines':cos,'pair_gradient_cosine_defined_batch_counts':cos_counts,'clip_trigger_fraction':result['clip_trigger_fraction'],
          'cost':cost,'actual_parent':actual[entry['job_id']],
          'original_run_runtime':result['runtime'],'not_a_scientific_gate':True}
        rows.append(row);sources.extend([ref(path),ref(curve_path),ref(entry['configuration'])])
    doc={'status':'COMPLETED_CONDITION_COST_AND_GRADIENT_PROFILES_ONLY_NOT_STAGE3_GATE','job_id':os.environ['SLURM_JOB_ID'],
      'phase':a.phase,'conditions':a.conditions,'rows':rows,'source_references':sources,'elapsed_seconds':time.monotonic()-started,
      'cost_estimator_modified':False,'LR_selected_by_this_report':False,'formal_training_authorized':False}
    a.output.mkdir()
    with (a.output/'profiles.json').open('x') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')
    flat=[]
    for row in rows:
        values={k:row[k] for k in ['condition','seed','job_id','LR','optimizer_updates','consumed_records','clip_trigger_fraction']}
        values.update({k:row['final'][k] for k in ['local_rmse_A','bond_rmse_A','noise_mse_normalized','masked_element_accuracy','masked_element_nll','bond_order_accuracy']})
        values.update(row['cost'])
        for task,value in row['mean_of_per_batch_shared_gradient_fractions'].items():values['gradient_fraction_'+task]=value
        flat.append(values)
    columns=list(dict.fromkeys(k for row in flat for k in row))
    with (a.output/'profiles.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(flat)
    print(json.dumps({'status':doc['status'],'rows':len(rows),'output':str(a.output)}),flush=True)
if __name__=='__main__':main()
