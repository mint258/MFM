"""One-molecule phase16 SCI startup proof. Never opens the shared queue or LMDB."""
import argparse,collections,os,pickle,socket,time
from pathlib import Path
import wp5_queue_reconcile_v2 as H
from wp5_archive_v5 import ArchiveReader
ROOT=H.ROOT
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if socket.gethostname().split('.')[0]!='compute-0-20' or os.getuid()!=1278:raise ValueError('ACTUAL_COMPUTE20_UID1278_REQUIRED')
    if H.digest(H.__file__)!='fa8ff8c76b8be5de3aca269ad6c155ec18825bc18ab6facece9824c5e8208e84':raise ValueError('FROZEN_H2_CHANGED')
    submitted=ROOT/'submission/recovery_attempt_v16/submitted_jobs.json';phase=H.load(submitted)
    entries=phase['main']+phase['cleanup'];jobs={str(e['job_id']) for e in entries}
    if phase['status']!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or len(entries)!=78 or len(jobs)!=78 or phase['coordination_version']!=16 or phase['runtime_version']!=14 or phase['prepared_plan']['prior_unique_jobs']!=463 or jobs.intersection(phase['prepared_plan']['prior_job_ids']):raise ValueError('EXACT_ACTUAL_PHASE16_78_REQUIRED')
    started=time.time();deadline=time.monotonic()+120;attempts=[]
    for entry in entries:
        jid=str(entry['job_id'])
        for runfile in sorted((ROOT/'runtime'/('task_'+str(entry['task_id']))).glob('job_'+jid+'_*/run.json')):
            run=H.load(runfile);opt=run['options']
            if str(opt['job_id'])!=jid or str(opt['task_id'])!=str(entry['task_id']) or Path(opt['run_root'])!=runfile.parent:raise ValueError('ACTUAL_RUN_JOB_TASK_SCOPE_DIFFERS')
            for lane in sorted((runfile.parent/'temporary_lanes').glob('lane_*.sqlite')):
                if time.monotonic()>deadline:raise TimeoutError('BOUNDED_STARTUP_PROBE_NO_RESULT')
                reader=None
                try:
                    reader=ArchiveReader(lane,opt['dictionaries'])
                    cur=reader.db.execute('SELECT p.molecule_id,p.record_count,p.wire_sha256,p.uncompressed_bytes,p.dict_id,p.wire_frame FROM parsed_molecules p JOIN completion_receipts c USING(molecule_id) ORDER BY p.molecule_id LIMIT 1')
                    try:row=cur.fetchone()
                    finally:cur.close()
                    if row is None:continue
                    dictionary=reader.dicts['pm7_B']
                    if row['dict_id']!=dictionary['dict_id']:raise ValueError('SCI_STAGING_DICT_DIFFERS')
                    wire=reader.zstd.decompress(row['wire_frame'],dictionary['data'],row['uncompressed_bytes'])
                    if H.sha(wire)!=row['wire_sha256']:raise ValueError('SCI_WIRE_SHA_DIFFERS')
                    item={'molecule_id':row['molecule_id'],'record_count':row['record_count'],'wire_sha256':row['wire_sha256'],'payload':pickle.loads(wire)}
                    complete=reader.completion(item['molecule_id'])
                    evidence=H.validate_payload(item,complete,opt,reader.db)
                    ctx=evidence['context']
                    if ctx['attempt_id'] not in (0,1) or not ctx['execution_id'].startswith(opt['session']+':'+str(ctx['lane'])+':'+str(ctx['attempt_id'])+':'):raise ValueError('SCI_EXECUTION_ATTEMPT_DIFFERS')
                    n=evidence['record_count'];status=collections.Counter();trace=0
                    for record in item['payload']['result']['record_results']:
                        for detail in record['tasks']:
                            status[detail['scope_status']]+=1
                            provenance=detail['provenance']
                            if not all(k in provenance for k in ('status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256')):raise ValueError('SIX_TRACE_FIELDS_MISSING')
                            trace+=1
                    if not status['SUCCESS']:raise ValueError('NO_POSITIVE_SCIENTIFIC_SUCCESS_OUTCOME')
                    report={'schema':'WP5_PHASE16_SINGLE_COMPLETE_MOLECULE_STARTUP_PROOF_V1','status':'REAL_PHASE16_DURABLE_SCI_VALIDATED','observed_epoch':time.time(),'started_epoch':started,
                        'processing_node':socket.gethostname(),'processing_pid':os.getpid(),'phase_receipt':{'path':str(submitted),'sha256':H.digest(submitted)},'new_phase_job_id':jid,'actual_science_node':run['node'],
                        'run_json':{'path':str(runfile),'sha256':H.digest(runfile)},'lane':str(lane),'molecule_id':item['molecule_id'],'record_count':n,'requested_outcomes':12*n,
                        'status_counts':dict(status),'trace_fields_validated_rows':trace,'wire_sha256':evidence['wire_sha256'],'receipt_sha256':evidence['receipt_sha256'],'context':ctx,
                        'frozen_validator':{'path':H.__file__,'sha256':H.digest(H.__file__),'function':'validate_payload'},'probe_source':{'path':__file__,'sha256':H.digest(__file__)},
                        'source_queue_SQL':False,'original_LMDB_opened':False,'QM_recomputed':False,'scientific_files_written':False,'whole_root_scanned':False,'completed_molecules_decoded':1,
                        'scope':'Only one indexed COMPLETE SCI stage, frozen wire/context/12N/counts/retained-raw identity checks. Proves positive scientific output; no full-population/final-acceptance claim.'}
                    H.write_json(a.out,report);print(__import__('json').dumps(report));return
                except __import__('sqlite3').OperationalError as exc:
                    attempts.append({'lane':str(lane),'error':str(exc)})
                finally:
                    if reader is not None:reader.close()
    raise RuntimeError('NO_SINGLE_COMPLETE_NEW_PHASE_SCI_FOUND:'+str(attempts[:5]))
if __name__=='__main__':main()
