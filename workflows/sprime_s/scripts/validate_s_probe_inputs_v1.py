"""Close all common benchmark members and typed UFF coordinates before probing."""
import json,os
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import numpy as np,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(16);pa.set_io_thread_count(4)
    result=[];widths={'qm7':1,'qm9':15,'cyp_isoform':9,'az_exactsom':1,'expansionrx':9}
    for dataset,width in widths.items():
        path=ROOT/'probe_data_v3'/(dataset+'_receipt.json');receipt=json.loads(path.read_text())
        assert receipt['status']=='DATASET_MEMBERS_AND_COMMON_UFF_GEOMETRY_CLOSED'
        assert receipt['declared_members']==receipt['processed_members']
        assert receipt['generator_sha256']==sha(ROOT/'scripts/prepare_s_probe_data_v3.py')
        for ref in receipt['sources']:assert sha(ref['path'])==ref['sha256']
        assert sha(receipt['output']['path'])==receipt['output']['sha256']
        table=pq.read_table(receipt['output']['path']);assert table.schema.field('coordinates').type.value_type==pa.float64()
        order=set();ids=set();ready=unknown=0
        for batch in table.to_batches(max_chunksize=1024):
            for row in batch.to_pylist():
                assert row['record_id'] not in ids and row['member_order'] not in order
                ids.add(row['record_id']);order.add(row['member_order'])
                assert row['geometry_status']!='IMPLEMENTATION_ERROR',row['error']
                assert 0<=row['fold']<=9
                if row['geometry_status']=='GEOMETRY_READY':
                    n=len(row['atomic_numbers']);coordinates=np.asarray(row['coordinates'],dtype=np.float64)
                    assert coordinates.shape==(3*n,) and np.isfinite(coordinates).all()
                    assert row['uff_converged'] and 0<row['uff_iterations']<=500
                    expected=n*width if dataset in ['cyp_isoform','az_exactsom'] else width
                    assert len(row['targets'])==len(row['candidate_mask'])==len(row['supervision_mask'])==expected
                    for value,candidate,observed in zip(row['targets'],row['candidate_mask'],row['supervision_mask']):
                        if observed:assert candidate and value is not None and np.isfinite(value)
                    ready+=1
                if row['annotation_status']=='SOURCE_ANNOTATION_FLAGGED_UNKNOWN':unknown+=1
        assert len(ids)==receipt['processed_members'] and order==set(range(len(ids)))
        result.append({'dataset':dataset,'members':len(ids),'geometry_ready':ready,'flagged_annotation_unknown_members':unknown,
            'geometry_status_counts':receipt['geometry_status_counts'],'source_receipt_sha256':sha(path),'data_sha256':receipt['output']['sha256']})
    value={'status':'ALL_FIVE_COMMON_PROBE_INPUT_DATASETS_ACCEPTED','job_id':os.environ['SLURM_JOB_ID'],
        'datasets':result,'script_sha256':sha(__file__),'no_members_deleted':True,'coordinates_dtype':'float64',
        'formal_checkpoint_probe_scores_computed':False}
    save(ROOT/'probe_data_v3/acceptance.json',value);print(json.dumps(value),flush=True)

if __name__=='__main__':main()
