"""Real H0/mask integration and held-out-target independence on private fixtures."""
import json,os,multiprocessing as mp,tempfile,shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from prepare import ROOT,save,sha
from run_s_linear_probes_v1 import fit_cell,init_probe_worker,DATASETS

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import pyarrow as pa,pyarrow.parquet as pq
    scratch=Path(tempfile.mkdtemp(prefix='sprobe_linear_fixture_',dir='/tmp'))
    try:
        requests=[];paths={}
        for dataset in DATASETS:
            original=ROOT/'probe_h0_development/4515114'/(dataset+'.parquet')
            table=pq.read_table(original).sort_by('member_order');rows=table.to_pylist()
            for index,row in enumerate(rows):row['fold']=index%10
            path=scratch/(dataset+'.parquet');pq.write_table(pa.Table.from_pylist(rows,schema=table.schema),path)
            paths[dataset]=path
            # Fixture split is not a scientific scaffold result or formal endpoint.
            requests.extend({'dataset':dataset,'fold':fold,'path':str(path),'sha256':sha(path)} for fold in [0,1])
        changed=pq.read_table(paths['qm7']).to_pylist()
        for row in changed:
            if row['fold']==0:row['targets']=[v+1e6 if v is not None else None for v in row['targets']]
        altered=scratch/'qm7_heldout_changed.parquet'
        pq.write_table(pa.Table.from_pylist(changed,schema=pq.read_schema(paths['qm7'])),altered)
        requests.append({'dataset':'qm7','fold':0,'path':str(altered),'sha256':sha(altered)})
        # More than16 cells exercise reuse of worker processes and one-time interop init.
        requests+=requests[:10]
        with ProcessPoolExecutor(16,mp_context=mp.get_context('spawn'),initializer=init_probe_worker) as pool:
            results=list(pool.map(fit_cell,requests))
        baseline=results[0];modified=results[10]
        assert baseline['normalizers']==modified['normalizers']
        assert baseline['readout_weight']==modified['readout_weight'] and baseline['readout_bias']==modified['readout_bias']
        assert baseline['test']['actual_score_float32_sha256']==modified['test']['actual_score_float32_sha256']
        assert baseline['test']['tasks'][0]['primary_metric']!=modified['test']['tasks'][0]['primary_metric']
        for index in range(10):
            assert results[index]['readout_weight']==results[index+11]['readout_weight']
            assert results[index]['test']==results[index+11]['test']
        assert all(r['epochs']==20 for r in results)
        result={'status':'ACTUAL_H0_LINEAR_INTEGRATION_AND_HELDOUT_TARGET_INDEPENDENCE_PASS',
            'job_id':os.environ['SLURM_JOB_ID'],'actual_cells':len(results),'datasets':DATASETS,
            'worker_reuse_pass':True,'same_fixture_repeat_weights_and_scores_exact':True,
            'heldout_target_change_does_not_change_train_normalizer_weights_or_scores':True,
            'fixtures':'private remapped development membership; not scientific scaffold/epoch endpoints',
            'formal_probe_results_created':False,'source_sha256':sha(ROOT/'scripts/run_s_linear_probes_v1.py')}
        save(ROOT/'reports/s_linear_probe_integration_v1.json',result);print(json.dumps(result),flush=True)
    finally:shutil.rmtree(scratch)

if __name__=='__main__':main()
