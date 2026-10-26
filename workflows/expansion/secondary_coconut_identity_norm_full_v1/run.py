"""All2939137 physical rows via original profile objects; unknowns never dropped."""
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,sqlite3,time,unittest
from collections import Counter
from pathlib import Path
from . import contracts as c
from .runtime import Budget,profile,source_scope_proof,profile_forecast

def encoded(value):return (json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()

class ArtifactFailure(RuntimeError):pass

class Sink:
    def __init__(self,out,budget):
        import pyarrow as pa
        self.out=out;self.budget=budget;self.table=None;self.part=0;self.journal=None;self.writer=None;self.buffer=[];self.n=0;self.bytes=0;self.paths=[];self.part_rows=0
        self.schema=pa.schema([('source_table',pa.string()),('copy_block',pa.int64()),('source_row_ordinal',pa.int64()),('observation_json',pa.string())])
        scratch=out/'sqlite_scratch';scratch.mkdir();os.environ['SQLITE_TMPDIR']=str(scratch)
        self.db=sqlite3.connect(out/'coverage.sqlite');self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA cache_size=-65536');self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('CREATE TABLE physical_rows(source_table TEXT,copy_block INTEGER,row_ordinal INTEGER,status TEXT,active TEXT,is_invalid TEXT,has_key INTEGER,invalid_keys INTEGER,unresolved INTEGER,missing INTEGER,disagreement INTEGER,PRIMARY KEY(source_table,copy_block,row_ordinal))')
    def start(self,table):
        import pyarrow.parquet as pq
        self.table=table;folder=self.out/table;folder.mkdir(exist_ok=True);stem=folder/('part_%06d'%self.part)
        self.journal_path=stem.with_suffix('.observations.jsonl');self.parquet_path=stem.with_suffix('.observations.parquet')
        self.journal=self.journal_path.open('xb');self.writer=pq.ParquetWriter(self.parquet_path,self.schema,compression='zstd');self.bytes=0;self.part_rows=0;self.buffer=[]
    def flush(self):
        import pyarrow as pa
        if self.buffer:self.writer.write_table(pa.Table.from_pylist(self.buffer,schema=self.schema));self.buffer.clear()
        self.db.commit()
    def finish(self):
        if self.journal is None:return
        self.flush();self.writer.close();self.writer=None;self.journal.flush();os.fsync(self.journal.fileno());self.journal.close();self.journal=None
        with self.parquet_path.open('rb') as stream:os.fsync(stream.fileno())
        import pyarrow.parquet as pq
        c.need(pq.ParquetFile(self.parquet_path).metadata.num_rows==self.part_rows,'PART_PARQUET_FOOTER_ROWS')
        value={'schema':'COCONUT_NORM_FULL_CLOSED_PART_V1','table':self.table,'part':self.part,'rows':self.part_rows,
          'journal_path':str(self.journal_path),'journal_bytes':self.bytes,'Parquet_path':str(self.parquet_path),
          'journal_fsynced_before_SQL_aggregation':True,'whole_file_SHA_pending_final_stream_verification':True}
        c.write_new(self.journal_path.with_suffix('.closed.json'),value);self.paths.append(value);self.part+=1
    def add(self,value):
        try:
            observation=value['observation'];row=observation['source'];table=row['source_table'];raw=encoded(value)
            c.need(len(raw)<=8*1024**2,'SAME_PROFILE_RESULT_CONTAINER_LIMIT_NO_DROP')
            self.budget.capacity(2*len(raw))
            if self.journal is not None and (table!=self.table or self.part_rows>=65536 or self.bytes+len(raw)>256*1024**2):self.finish()
            if self.journal is None:self.start(table)
            self.journal.write(raw);self.journal.flush();os.fsync(self.journal.fileno());self.bytes+=len(raw)
            # Durability precedes aggregation. Never turn a write failure into a chemistry rejection.
            fields=json.loads(row['identity_fields_json'])
            self.db.execute('INSERT INTO physical_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)',(table,row['copy_block'],row['source_row_ordinal'],
              fields.get('status'),fields.get('active'),fields.get('is_invalid'),int(observation['has_any_valid_full_key']),
              len(observation['source_full_keys_invalid']),observation['unresolved_present_variants'],observation['missing_variants'],int(observation['stored_vs_computed_disagreement'])))
            self.buffer.append({'source_table':table,'copy_block':row['copy_block'],'source_row_ordinal':row['source_row_ordinal'],
              'observation_json':json.dumps(observation,ensure_ascii=False,separators=(',',':'),allow_nan=False)})
            self.n+=1;self.part_rows+=1
            if len(self.buffer)>=16:self.flush()
        except Exception as exc:raise ArtifactFailure(type(exc).__name__+': '+str(exc)) from exc
    def close_partial(self):
        errors=[]
        try:self.finish()
        except Exception as exc:errors.append({'stage':'close_partial_output','type':type(exc).__name__,'error':str(exc)})
        for name in ('writer','journal'):
            obj=getattr(self,name,None)
            if obj is not None:
                try:obj.close()
                except Exception as exc:errors.append({'stage':'close_partial_'+name,'type':type(exc).__name__,'error':str(exc)})
                setattr(self,name,None)
        try:self.db.commit();self.db.close()
        except Exception as exc:errors.append({'stage':'close_partial_SQLite','type':type(exc).__name__,'error':str(exc)})
        return errors

def file_pin(path):
    h=hashlib.sha256();before=path.stat()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    c.need(c.frame(before)==c.frame(path.stat()),'OWNED_ARTIFACT_CHANGED_DURING_FINAL_SHA')
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,prior,a=c.startup(args.plan,args.startup_proof,__file__)
    out=c.literal(plan['output_directory']);c.need(c.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_FULL_OUTPUT_ONLY');out.mkdir(parents=True)
    started=time.monotonic();cpu=time.process_time();budget=Budget(plan,proof,out);sink=None;errors=[];worker_counts=Counter();worker_proofs={};worker_CPU=Counter();worker_wall=Counter()
    dispatched=Counter();saved=Counter();dispatch_blocks={};verified=[];phase_times={};stop=False;salvage_count=0;salvage_failures=0;cost_reported=False
    forecast=profile_forecast(prior);c.write_new(out/'forecast.json',forecast)
    def error(stage,exc,row=None):
        nonlocal stop
        stop=True;budget.set_stop(stage)
        value={'stage':stage,'type':type(exc).__name__,'error':str(exc),'scientific_regression_claimed':False}
        if row:value['source_locator']={k:row[k] for k in ('source_table','copy_block','source_row_ordinal','source_row_sha256')}
        errors.append(value)
        try:
            with (out/'technical_failures.jsonl').open('ab') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        except Exception as failure:value['technical_log_write_failed']=type(failure).__name__
    def salvage(value):
        nonlocal salvage_count,salvage_failures
        row=value['observation']['source'];folder=out/'completed_after_output_failure'
        try:
            folder.mkdir(exist_ok=True);path=folder/('%s_%06d_%012d.json'%(row['source_table'],row['copy_block'],row['source_row_ordinal']))
            raw=encoded(value);budget.capacity(len(raw))
            with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            salvage_count+=1
        except Exception as exc:
            salvage_failures+=1;errors.append({'stage':'durability_of_completed_result_failed','type':type(exc).__name__,
              'source_locator':{k:row[k] for k in ('source_table','copy_block','source_row_ordinal','source_row_sha256')},'original_A_input_unchanged':True})
    try:
        environment=profile.observe_environment();c.need(environment['actual_versions']==c.ENV,'SAME_ACTUAL_PROFILE_ENVIRONMENT_REQUIRED')
        c.write_new(out/'actual_environment.json',environment);scope_proof=source_scope_proof(plan);functions,kernel=profile.load_kernel(plan)
        profile.KernelFixtures.functions=functions;suite=unittest.defaultTestLoader.loadTestsFromTestCase(profile.KernelFixtures);c.need(suite.countTestCases()==3,'EXACT_THREE_OLD_PROFILE_FIXTURES')
        tested=unittest.TextTestRunner(verbosity=2).run(suite);fixtures={'tests_run':tested.testsRun,'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped),'before_both_A_body_hashes':True}
        c.write_new(out/'fixtures.json',fixtures);c.need(tested.wasSuccessful() and tested.testsRun==3 and not tested.skipped,'ORIGINAL_THREE_FIXTURES_BEFORE_BODY_HASHES')
        budget.thread.start();budget.dispatch_check()
        for table,ref,old in zip(c.COUNTS,plan['data_references'],prior['source_SHA_footer_phases']):
            current=profile.verify_source(ref,table,c.COUNTS[table],budget)
            c.need(all(current['current_frame'][k]==old['current_frame'][k] for k in ('inode','size','mtime_ns','uid')),'PORTABLE_SOURCE_FRAME_SINCE_ACTUAL_PROFILE')
            verified.append(current)
        c.write_new(out/'source_SHA_footer_verification.json',verified);sink=Sink(out,budget)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=profile.init_worker,initargs=(plan,)) as pool:
            pending={}
            for source in verified:
                table=source['table'];began=time.monotonic();phase_CPU=time.process_time();iterator=iter(profile.selected_rows(source,range(c.COUNTS[table]),budget));exhausted=False;last=None
                while pending or not exhausted:
                    if not cost_reported and time.monotonic()-started>1.5*forecast['nominal_table_pipeline_wall_seconds']:
                        c.write_new(out/'cost_overrun_report_continue.json',{'elapsed_seconds':time.monotonic()-started,'forecast':forecast,'action':'REPORT_AND_CONTINUE','cost_stop_applied':False});cost_reported=True
                    if not stop:
                        try:budget.dispatch_check()
                        except Exception as exc:error('runtime_stop_new_dispatch_natural_drain',exc)
                    while not stop and not exhausted and len(pending)<32:
                        try:
                            row=next(iterator);block,ordinal=row['copy_block'],row['source_row_ordinal']
                            c.need(type(block) is int and type(ordinal) is int and block>0 and ordinal>0 and
                              (last is None and (block,ordinal)==(1,1) or last is not None and ((block==last[0] and ordinal==last[1]+1) or (block==last[0]+1 and ordinal==1))),
                              'EXACT_SOURCE_PHYSICAL_BLOCK_ORDINAL_CHAIN')
                            c.need(len(row['identity_fields_json'].encode())<=2*1024**2,'SAME_PROFILE_INPUT_CONTAINER_LIMIT_NO_DROP')
                            future=pool.submit(profile.work,row);pending[future]=row;budget.workers=list(pool._processes.values());last=(block,ordinal)
                            dispatched[table]+=1;dispatch_blocks[(table,block)]=ordinal
                        except StopIteration:exhausted=True;break
                        except Exception as exc:error('source_or_dispatch_technical_failure',exc,locals().get('row'));break
                    if not pending:break
                    done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        original=pending.pop(future)
                        try:
                            value=future.result();c.need(value['observation']['source']==original,'RESULT_SOURCE_BINDING_CHANGED')
                            pid=value['worker_pid'];worker_counts[pid]+=1;worker_proofs.setdefault(pid,value['worker_kernel_proof'])
                            worker_CPU[table]+=value['CPU_seconds'];worker_wall[table]+=value['wall_seconds']
                        except Exception as exc:error('worker_or_source_binding_technical_failure',exc,original);continue
                        if any(x['stage']=='artifact_write_or_aggregation_failure' for x in errors):salvage(value);continue
                        try:sink.add(value);saved[table]+=1
                        except ArtifactFailure as exc:error('artifact_write_or_aggregation_failure',exc,original);salvage(value)
                phase_times[table]={'read_dispatch_fsync_write_wall_seconds':time.monotonic()-began,'parent_CPU_seconds':time.process_time()-phase_CPU,
                  'worker_key_CPU_seconds':worker_CPU[table],'worker_key_wall_sum_not_parent_wall':worker_wall[table]}
                if stop:break
        sink.finish()
        for source in verified:c.need(c.frame(Path(source['reference']['path']).stat())==source['current_frame'],'A_INPUT_FINAL_FRAME_CHANGED')
        budget.dispatch_check();aggregate_started=time.monotonic();db=sink.db
        block_rows=db.execute('SELECT source_table,copy_block,count(*),min(row_ordinal),max(row_ordinal) FROM physical_rows GROUP BY source_table,copy_block').fetchall()
        block_actual={(t,b):n for t,b,n,low,high in block_rows};block_contiguous=all(low==1 and high==n for t,b,n,low,high in block_rows)
        sql_counts=dict(db.execute('SELECT source_table,count(*) FROM physical_rows GROUP BY source_table').fetchall())
        stats=dict(zip(('rows_with_any_valid_full_key','rows_without_any_valid_full_key','invalid_stored_key_values','unresolved_present_variants','missing_variants','rows_stored_vs_computed_disagreement'),
          db.execute('SELECT coalesce(sum(has_key),0),coalesce(sum(1-has_key),0),coalesce(sum(invalid_keys),0),coalesce(sum(unresolved),0),coalesce(sum(missing),0),coalesce(sum(disagreement),0) FROM physical_rows').fetchone()))
        with (out/'status_counts.jsonl').open('xb') as stream:
            for row in db.execute('SELECT source_table,status,active,is_invalid,count(*) FROM physical_rows GROUP BY source_table,status,active,is_invalid'):
                stream.write(encoded(dict(zip(('source_table','status','active','is_invalid','records'),row))))
            stream.flush();os.fsync(stream.fileno())
        with (out/'unknown_identity_locators.jsonl').open('xb') as stream:
            for row in db.execute('SELECT source_table,copy_block,row_ordinal,has_key,invalid_keys,unresolved,missing,disagreement FROM physical_rows WHERE has_key=0 OR invalid_keys>0 OR unresolved>0 OR missing>0 OR disagreement>0 ORDER BY source_table,copy_block,row_ordinal'):
                stream.write(encoded(dict(zip(('source_table','copy_block','source_row_ordinal','has_any_valid_full_key','invalid_keys','unresolved','missing','disagreement'),row))))
            stream.flush();os.fsync(stream.fileno())
        db.commit();db.close();sink.db=None;phase_times['aggregation']={'wall_seconds':time.monotonic()-aggregate_started}
        complete=not errors and budget.stop is None and dict(dispatched)==dict(saved)==sql_counts==c.COUNTS and sink.n==c.TOTAL and block_actual==dispatch_blocks and block_contiguous and len(worker_counts)==16
        files=[]
        for folder,dirs,names in os.walk(out):
            for name in sorted(names):
                budget.dispatch_check();path=Path(folder)/name
                if path.is_file():files.append(file_pin(path))
        if not cost_reported and time.monotonic()-started>1.5*forecast['nominal_table_pipeline_wall_seconds']:
            c.write_new(out/'cost_overrun_report_continue.json',{'elapsed_seconds':time.monotonic()-started,'forecast':forecast,'action':'REPORT_AND_CONTINUE','cost_stop_applied':False});cost_reported=True
            files.append(file_pin(out/'cost_overrun_report_continue.json'))
        c.write_new(out/'outputs.json',files);budget.close();budget.capacity()
        c.write_new(out/'receipt.json',{'schema':'SECONDARY_COCONUT_IDENTITY_NORM_FULL_RECEIPT_V1',
          'status':'FULL_PHYSICAL_IDENTITY_KEY_OBSERVATIONS_COMPLETE_UNKNOWNS_PRESERVED' if complete else 'INCOMPLETE_FULL_IDENTITY_OBSERVATIONS_PARTIALS_PRESERVED',
          'mode':'full','job_id':str(proof['job_id']),'uid':c.UID,'node':plan['node'],'endpoint':c.q.ENDPOINT,'allocated_cpus':16,'plan':c.pin(args.plan),'startup_proof':c.pin(args.startup_proof),
          'accepted_profile':plan['accepted_profile_receipt_reference'],'A_full_receipt':plan['a_full_receipt_reference'],'actual_environment':environment,'source_scope_proof':scope_proof,'kernel_proof':kernel,
          'source_SHA_footer_phases':verified,'expected_physical_rows_by_table':c.COUNTS,'dispatched_rows_by_table':dict(dispatched),'saved_rows_by_table':dict(saved),'SQLite_unique_physical_rows_by_table':sql_counts,
          'physical_rows':sink.n,'source_block_ordinal_coverage':block_contiguous and block_actual==dispatch_blocks,'actual_nonempty_worker_processes':dict(worker_counts),'worker_kernel_proofs':worker_proofs,
          'identity_observation_counts_not_exclusions':stats,'A_original_all_table_status_orphan_observations':a['inventory']['reconciliation'],
          'A_other_identity_outputs_preserved':a['physical_output_references'],'own_status_counts_reference':file_pin(out/'status_counts.jsonl'),
          'actual_unknown_locators_reference':file_pin(out/'unknown_identity_locators.jsonl'),'outputs_manifest':c.pin(out/'outputs.json'),'closed_parts':sink.paths,
          'fixtures':fixtures,'technical_errors':errors,'completed_after_write_failure_preserved':salvage_count,'durability_failures':salvage_failures,
          'forecast':forecast,'cost_overrun_reported':cost_reported,'cost_overrun_action':'REPORT_AND_CONTINUE','phase_times':phase_times,
          'wall_seconds':time.monotonic()-started,'parent_process_CPU_seconds':time.process_time()-cpu,'runtime':budget.receipt(),'actual_terminal_parent_cost_closure_required':True,
          'all_physical_status_invalid_variants_and_no_key_rows_retained':complete,'scientific_failure_inferred_from_artifact_write_error':False,
          'raw_inputs_or_profile_outputs_modified':False,'global_decontamination_or_pool_UFF_QM_training_release':False,'signals_sent':False})
        return 0 if complete else 1
    except BaseException as exc:
        close_errors=sink.close_partial() if sink is not None and sink.db is not None else []
        c.write_new(out/'failure.json',{'status':'FULL_IDENTITY_TECHNICAL_STOP_PARTIALS_PRESERVED','type':type(exc).__name__,'error':str(exc),'technical_errors':errors,
          'close_errors':close_errors,'dispatched':dict(dispatched),'saved':dict(saved),'closed_parts':sink.paths if sink else [],'salvaged_completed_results':salvage_count,
          'durability_failures':salvage_failures,'original_inputs_unchanged':True,'scientific_quality_failure_claimed':False,'signals_sent':False})
        raise
    finally:
        if budget.thread.ident is not None and budget.thread.is_alive():budget.close()

if __name__=='__main__':raise SystemExit(main())
