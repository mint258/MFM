"""Private stdlib fixture for interval keyset observation. Zero QM/production DB access."""
import argparse,ast,copy,hashlib,json,pathlib,sqlite3,tempfile,time
from wp5_observer_scan_v2 import scan_queue_readonly
import wp5_recovery_hourly_watch_v9 as watch
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    if a.output.exists():raise ValueError('FIXTURE_OUTPUT_ALREADY_EXISTS')
    original=ast.parse((ROOT/'scripts/wp5_recovery_hourly_watch_v7.py').read_text())
    current=ast.parse((ROOT/'scripts/wp5_recovery_hourly_watch_v9.py').read_text())
    select=lambda t:next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_stop_conditions')
    assert ast.dump(select(original),include_attributes=False)==ast.dump(select(current),include_attributes=False)
    names=sorted(watch.CALCS);counts=lambda success:json.dumps({k:{'success':success,'total':1} for k in names})
    callbacks=[]
    with tempfile.TemporaryDirectory(prefix='wp5_observer7_private_') as directory:
        p=pathlib.Path(directory)/'fixture.sqlite'
        writer=sqlite3.connect(p,isolation_level=None,timeout=.05)
        writer.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE tasks(task_id TEXT PRIMARY KEY,node TEXT);CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,task_id TEXT,file_group INTEGER,state TEXT,record_count INTEGER,counts_json TEXT);')
        writer.executemany('INSERT INTO meta VALUES(?,?)',[('population_molecules','1026'),('population_records','1026')])
        writer.execute("INSERT INTO tasks VALUES('taskA','fixture-node')")
        writer.executemany('INSERT INTO molecules VALUES(?,?,?,?,?,?)',[
            ('%06d'%i,'taskA',1,'COMPLETE' if i==1 else 'PENDING',1,counts(1) if i==1 else None) for i in range(1,1027)])
        def update(chunk,last):
            # These writes occur while the observer connection is still open.
            # BEGIN IMMEDIATE+COMMIT would fail if it retained its SHARED txn.
            writer.execute('BEGIN IMMEDIATE')
            if chunk==1:
                for i in (2,513,514):writer.execute("UPDATE molecules SET state='COMPLETE',counts_json=? WHERE molecule_id=?",(counts(1),'%06d'%i))
            elif chunk==2:
                for i in (1025,):writer.execute("UPDATE molecules SET state='COMPLETE',counts_json=? WHERE molecule_id=?",(counts(1),'%06d'%i))
            writer.execute('COMMIT');callbacks.append({'chunk':chunk,'last':last,'write_committed_between_chunks':True})
        observed=scan_queue_readonly(p,on_chunk=update)
        assert observed['scan_interval']['molecules_visited_once']==1026
        complete=sum(x['molecules'] for x in observed['counts'] if x['state']=='COMPLETE')
        pending=sum(x['molecules'] for x in observed['counts'] if x['state']=='PENDING')
        persisted=sum(x['records'] for x in observed['durable_states'])
        assert (complete,pending,persisted)==(4,1022,4)
        assert len(observed['task_success_rates'])==12
        assert all(x['success']==4 and x['total']==4 for x in observed['task_success_rates'])
        actual_complete=writer.execute("SELECT count(*) FROM molecules WHERE state='COMPLETE'").fetchone()[0]
        assert actual_complete==5 and actual_complete>complete
        failure=None
        try:scan_queue_readonly(p,statement_seconds=1e-12)
        except (TimeoutError,sqlite3.OperationalError) as error:failure=type(error).__name__
        assert failure is not None
        writer.close()
    # Source and interval pairing uses actual control source refs, never a
    # fake production queue or fabricated whole-population observation.
    refs={name:{'path':str(ROOT/'scripts'/filename),'sha256':hashlib.sha256((ROOT/'scripts'/filename).read_bytes()).hexdigest()} for name,filename in [('observer','wp5_hourly_observe_v8.py'),('queue_scan_helper','wp5_observer_scan_v2.py'),('production_runtime','wp5_runner_v13.py')]}
    interval=copy.deepcopy(observed['scan_interval'])
    now=time.time()
    snapshot={**observed,'time':now,'scan_interval':interval,'control_sources':refs,
        'durable_records':persisted,'population_closed':True,'task_denominators_closed':True}
    observation={'time':now,'complete_molecules':complete,'cumulative_actual_allocated_core_hours_known_sum':1.0,'scan_interval':interval,'control_sources':refs}
    summary={'complete_molecules':complete,'complete_records':complete,'retry_molecules':0,'durable_records':persisted,
        'population_closed':True,'task_denominators_closed':True,'effective_selection_ready':True,'effective_job_count':78,
        'cumulative_actual_allocated_core_hours_known_sum':1.0,'scan_interval':interval,'control_sources':refs}
    proof=watch.paired_observer_proof(observation,snapshot,summary,now,now)
    assert proof['valid'],proof
    wrong=copy.deepcopy(summary);wrong['scan_interval']['scan_start_epoch']=now+10
    assert not watch.paired_observer_proof(observation,snapshot,wrong,now,now)['valid']
    wrong=copy.deepcopy(snapshot);wrong['control_sources']['observer']['sha256']='0'*64
    assert not watch.paired_observer_proof(observation,wrong,summary,now,now)['valid']
    missing=copy.deepcopy(snapshot)
    missing['meta']['population_molecules']='1027';missing['meta']['population_records']='1027'
    missing['population_closed']=False
    missing_summary=copy.deepcopy(summary);missing_summary['population_closed']=False
    missing_proof=watch.paired_observer_proof(observation,missing,missing_summary,now,now)
    assert missing_proof['valid'],missing_proof
    # Only this private fixture temporarily scales the original constants to
    # 1027; production source/functions and formal expectations are untouched.
    expected_old=(watch.EXPECTED_MOLECULES,watch.EXPECTED_RECORDS)
    try:
        watch.EXPECTED_MOLECULES=1027;watch.EXPECTED_RECORDS=1027
        fixture_publisher={'uid':1278,'hostname':'sonmi','time':now,
            'quota_parsed':{'remaining_bytes':1_000_000_000_000},'sacct':{'returncode':0,'stdout':''}}
        missing_evaluation=watch.evaluate_stop_conditions(fixture_publisher,observation,missing,
            {'ready':True,'actual_cost_job_ids':[]},missing_proof['valid'],now)
        assert missing_evaluation['eligible']
        assert any(c['guide_condition']==2 and c['details'].get('observed_molecules')==1026
            and c['details'].get('population_molecules')==1027 for c in missing_evaluation['conditions']),missing_evaluation
        missing_dry_stop=watch.write_guide_stop(missing_evaluation,{'private_fixture':True},dry_run=True)
        assert missing_dry_stop['written'] is False
    finally:watch.EXPECTED_MOLECULES,watch.EXPECTED_RECORDS=expected_old
    result={'schema':'WP5_OBSERVER7_PRIVATE_INTERVAL_FIXTURE_V2','status':'PRIVATE_INTERVAL_FIXTURE_PASS',
        'QM_calls':0,'production_queue_read':False,'production_queue_written':False,'Slurm_submitted':False,'STOP_written':False,
        'original_guide_stop_evaluator_AST_identical':True,'observed_molecules':1026,'observed_records':1026,
        'observed_complete_molecules':complete,'end_of_scan_actual_complete_molecules':actual_complete,
        'persisted_records_observed':persisted,'twelve_task_totals_closed':True,'callbacks':callbacks,
        'SQL_deadline_failure_reported_without_partial_counts':failure,'paired_interval_and_source_proof':proof,
        'wrong_interval_rejected':True,'wrong_source_rejected':True,
        'missing_one_row_proof':missing_proof,'missing_one_row_evaluation':missing_evaluation,
        'missing_one_row_dry_stop':missing_dry_stop,'private_fixture_expected_population':1027,
        'private_fixture_actual_population':1026,'full_primary_key_scan_EOF':interval['full_primary_key_scan_EOF'],
        'Guide2_population_mismatch_not_masked':True,'issues':[]}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
