"""Independent typed shape/mask review of the actual five-dataset smoke output."""
import json,os
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import numpy as np,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(16)
    results={};folder=ROOT/'probe_data_development_v2'
    tasks={'qm7':1,'qm9':15,'cyp_isoform':9,'az_exactsom':1,'expansionrx':9}
    for dataset,width in tasks.items():
        receipt=json.loads((folder/(dataset+'_receipt.json')).read_text());ref=receipt['output'];assert sha(ref['path'])==ref['sha256']
        table=pq.read_table(ref['path']);assert table.schema.field('coordinates').type.value_type==pa.float64()
        rows=table.to_pylist();assert len(rows)==16 and len({r['member_order'] for r in rows})==16
        errors=[];supervised=0;ready=0
        for row in rows:
            if row['geometry_status']=='GEOMETRY_READY':
                n=len(row['atomic_numbers']);positions=np.array(row['coordinates'],dtype=np.float64)
                assert positions.shape==(3*n,) and np.isfinite(positions).all()
                assert row['uff_converged'] and 0<row['uff_iterations']<=500
                expected=n*width if dataset in ['cyp_isoform','az_exactsom'] else width
                assert len(row['targets'])==len(row['candidate_mask'])==len(row['supervision_mask'])==expected
                for value,candidate,mask in zip(row['targets'],row['candidate_mask'],row['supervision_mask']):
                    if mask:assert candidate and value is not None and np.isfinite(value);supervised+=1
                ready+=1
            else:errors.append({'record_id':row['record_id'],'status':row['geometry_status'],'error':row['error']})
        results[dataset]={'members':16,'geometry_ready':ready,'supervised_labels':supervised,'flags':errors,'data_sha256':ref['sha256']}
    result={'status':'ACTUAL_FIVE_DATASET_SMOKE_TYPED_SHAPES_AND_MASKS_REVIEWED','job_id':os.environ['SLURM_JOB_ID'],
        'source_smoke_job':'4515113','results':results,'generator_sha256':sha(ROOT/'scripts/prepare_s_probe_data_v2.py'),
        'formal_full_probe_inputs_generated':False,'full_epoch_checkpoint_evaluated':False}
    save(ROOT/'reports/s_probe_smoke_review_v2.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
