"""Actual fixed-partition routing and train-only normalizer/optimizer verification."""
import json,os,multiprocessing as mp,tempfile,shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from prepare import ROOT,save,sha
from run_s_linear_probes_v2 import fit_cell,init_probe_worker,partition_roles,DATASETS

def assert_independent(baseline,changed):
    assert baseline['normalizers']==changed['normalizers']
    assert baseline['readout_weight']==changed['readout_weight'] and baseline['readout_bias']==changed['readout_bias']
    assert baseline['fixed_train_order_int32_sha256']==changed['fixed_train_order_int32_sha256']
    assert baseline['test']['actual_score_float32_sha256']==changed['test']['actual_score_float32_sha256']
    before=[row['primary_metric'] for row in baseline['test']['tasks']]
    after=[row['primary_metric'] for row in changed['test']['tasks']]
    assert any(a!=b for a,b in zip(before,after) if a is not None and b is not None)

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=17
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    # Check real official membership with IDs only; official test targets are not loaded here.
    inventory=pq.read_table(ROOT/'probe_data_v3/expansionrx.parquet',columns=['record_id','fold']).to_pylist()
    roles,recipe=partition_roles(inventory,{'dataset':'expansionrx','fold':0})
    assert sum(role=='train' for role in roles.values())==5326
    assert sum(role=='test' for role in roles.values())==2282
    altered_inventory=[dict(row,fold=(row['fold']+3)%10) for row in inventory]
    assert partition_roles(altered_inventory,{'dataset':'expansionrx','fold':0})[0]==roles
    scratch=Path(tempfile.mkdtemp(prefix='sprobe_linear_v2_fixture_',dir='/tmp'))
    try:
        requests=[];paths={}
        for dataset in DATASETS[:-1]:
            original=ROOT/'probe_h0_development/4515114'/(dataset+'.parquet')
            table=pq.read_table(original).sort_by('member_order');rows=table.to_pylist()
            for index,row in enumerate(rows):row['fold']=index%10
            path=scratch/(dataset+'.parquet');pq.write_table(pa.Table.from_pylist(rows,schema=table.schema),path)
            paths[dataset]=path
            requests.extend({'dataset':dataset,'fold':fold,'path':str(path),'sha256':sha(path)} for fold in [0,1])
        original=ROOT/'probe_h0_development/4515114/expansionrx.parquet'
        table=pq.read_table(original).sort_by('member_order');rows=table.to_pylist()
        assert all(row['record_id'].startswith('expansionrx:log_train_data.csv:') for row in rows)
        private_roles={row['record_id']:('train' if index<12 else 'test') for index,row in enumerate(rows)}
        request={'dataset':'expansionrx','fold':0,'path':str(original),'sha256':sha(original),
            'development_roles':private_roles,'scope':'DEVELOPMENT_TRAIN_ONLY_ROLE_FIXTURE'}
        requests.append(request)
        changed=[]
        for row in rows:
            copy=dict(row);copy['fold']=(row['fold']+3)%10
            if private_roles[row['record_id']]=='test':copy['targets']=[v+1e6 if v is not None else None for v in row['targets']]
            changed.append(copy)
        altered=scratch/'expansion_private_holdout_changed.parquet';pq.write_table(pa.Table.from_pylist(changed,schema=table.schema),altered)
        requests.append(dict(request,path=str(altered),sha256=sha(altered)))
        changed=pq.read_table(paths['qm7']).to_pylist()
        for row in changed:
            if row['fold']==0:row['targets']=[v+1e6 if v is not None else None for v in row['targets']]
        altered=scratch/'qm7_private_holdout_changed.parquet';pq.write_table(pa.Table.from_pylist(changed,schema=pq.read_schema(paths['qm7'])),altered)
        requests.append({'dataset':'qm7','fold':0,'path':str(altered),'sha256':sha(altered)})
        requests+=requests[:9]
        with ProcessPoolExecutor(16,mp_context=mp.get_context('spawn'),initializer=init_probe_worker) as pool:
            results=list(pool.map(fit_cell,requests))
        assert_independent(results[0],results[10]);assert_independent(results[8],results[9])
        for index in range(9):
            assert results[index]['readout_weight']==results[index+11]['readout_weight']
            assert results[index]['test']==results[index+11]['test']
        assert all(row['epochs']==20 for row in results)
        result={'status':'STAGE59_OFFICIAL_ROUTING_AND_ACTUAL_LINEAR_HELDOUT_INDEPENDENCE_PASS',
            'job_id':os.environ['SLURM_JOB_ID'],'actual_cells':len(results),'worker_reuse_pass':True,
            'actual_official_train_inventory':5326,'actual_official_test_inventory':2282,
            'unused_derived_scaffold_fields_do_not_change_official_partition':True,
            'QM7_and_private_Expansion_holdout_target_changes_leave_train_normalizers_weights_orders_scores_exact':True,
            'official_test_targets_used_in_this_development_check':False,
            'fixture_scope':'Actual H0 development features and original TRAIN labels only; private heldout roles; no formal checkpoint scores',
            'formal_probe_results_created':False,'probe_source_sha256':sha(ROOT/'scripts/run_s_linear_probes_v2.py'),
            'probe_policy_sha256':sha(ROOT/'configs/s_probe_protocol_v2.json'),'validator_source_sha256':sha(__file__)}
        save(ROOT/'reports/s_linear_probe_integration_v2.json',result);print(json.dumps(result),flush=True)
    finally:shutil.rmtree(scratch)

if __name__=='__main__':main()
