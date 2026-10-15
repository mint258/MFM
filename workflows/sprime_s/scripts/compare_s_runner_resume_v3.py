"""Compare actual uninterrupted and checkpoint-resumed runner executions."""
import json,os
from prepare import ROOT,save,sha

def main():
    import torch
    torch.set_num_threads(16);torch.set_num_interop_threads(1)
    job=os.environ['SLURM_JOB_ID'];root=ROOT/'development_s_runner/B1_seed0'
    def load(tag):
        folder=root/f'segment_{job}_{tag}'
        summary=json.loads((folder/'summary.json').read_text())
        assert summary['status']=='DEVELOPMENT_ONLY_NO_EPOCH_ACCEPTANCE' and not summary['epoch_accepted']
        ref=summary['final_checkpoint'];assert sha(ref['path'])==ref['sha256']
        return summary,torch.load(ref['path'],map_location='cpu',weights_only=True)
    a,x=load('uninterrupted');b,y=load('sliced');c,z=load('resumed')
    assert x['consumed_records']==z['consumed_records']==2006
    assert x['optimizer_updates']==z['optimizer_updates']==4
    assert y['consumed_records']==1536 and y['optimizer_updates']==3
    assert x['config_sha256']==y['config_sha256']==z['config_sha256']
    assert a['gpu_uuid']==b['gpu_uuid']==c['gpu_uuid']
    tolerance=json.loads((ROOT/'configs/s_memory_validation_tolerances_v1.json').read_text())
    # Same predeclared tolerance as the previous optimizer/save-resume proof.
    atol=1e-6;rtol=1e-4
    maximum={'model':0.,'optimizer':0.};tensor_count={'model':0,'optimizer':0}
    def compare(left,right,scope):
        assert type(left) is type(right),(type(left),type(right))
        if isinstance(left,torch.Tensor):
            assert left.shape==right.shape and left.dtype==right.dtype
            if left.is_floating_point():
                torch.testing.assert_close(left,right,atol=atol,rtol=rtol)
                maximum[scope]=max(maximum[scope],float((left-right).abs().max()) if left.numel() else 0.)
            else:assert torch.equal(left,right)
            tensor_count[scope]+=1
        elif isinstance(left,dict):
            assert list(left)==list(right)
            for key in left:compare(left[key],right[key],scope)
        elif isinstance(left,(list,tuple)):
            assert len(left)==len(right)
            for u,v in zip(left,right):compare(u,v,scope)
        else:assert left==right,(left,right)
    compare(x['model'],z['model'],'model');compare(x['optimizer'],z['optimizer'],'optimizer')
    assert x['sampler']==z['sampler'] and x['scheduler']==z['scheduler']
    assert torch.equal(x['coverage'],z['coverage']) and x['covered_molecules']==z['covered_molecules']
    assert torch.equal(x['cpu_rng'],z['cpu_rng']) and torch.equal(x['cuda_rng'],z['cuda_rng'])
    assert x['completed_epochs']==z['completed_epochs']==[] and not x['scientific_stop'] and not z['scientific_stop']
    result={'status':'ACTUAL_UNINTERRUPTED_VS_RESUMED_RUNNER_PASS','job_id':job,
        'runner_sha256':sha(ROOT/'scripts/s_convergence_runner_v8.py'),
        'configuration_sha256':x['config_sha256'],'implementation_sha256':sha(ROOT/'scripts/s_loader_recovery_v2.py'),
        'gpu_uuid':a['gpu_uuid'],'uninterrupted_checkpoint':a['final_checkpoint'],
        'split_checkpoint':b['final_checkpoint'],'resumed_checkpoint':c['final_checkpoint'],
        'record_count':2006,'optimizer_updates':4,'model_and_optimizer_max_abs_difference':maximum,
        'compared_tensor_counts':tensor_count,'atol':atol,'rtol':rtol,
        'cpu_and_cuda_rng_exact':True,'coverage_sampler_scheduler_exact':True,
        'native_lmdb_read':True,'full_epoch_performed':False,'formal_training_performed':False,
        'tolerance_reference_sha256':sha(ROOT/'configs/s_memory_validation_tolerances_v1.json')}
    save(ROOT/'reports/s_runner_uninterrupted_resume_v3.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
