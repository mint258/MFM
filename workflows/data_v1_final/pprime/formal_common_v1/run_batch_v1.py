"""Execute one reviewed baseline common batch on 14-19. Root is the sole submitter."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
import traceback

from common_v1 import IO, begin, formal_review, ledger_file, load, pilot_review, runtime, task_key


def split_imports(pairs, entries, audited):
    """A reused scientific failure remains a failure outcome, never a filled label."""
    reused, pending = [], []
    for pair in pairs:
        prior=entries.get(pair['once_key'])
        if prior is None:
            pending.append(pair)
        else:
            if prior['record_id']!=pair['record_id']:
                raise ValueError('PILOT_INPUT_SEED_ID_MISMATCH')
            if prior['stable_raw_audit_key_sha256']!=pair['stable_raw_audit_key_sha256'] or prior['stable_raw_audit_selected']!=pair['stable_raw_audit_selected']:
                raise ValueError('PILOT_AND_FORMAL_STABLE_PHYSICAL_AUDIT_IDENTITY_MISMATCH')
            if pair['record_id'] in audited and not prior['all_twelve_raw_retained_verified']:
                raise ValueError('NEW_AUDIT_MEMBERSHIP_NEEDS_MISSING_PILOT_RAW_ROOT_REVIEW_NO_RECOMPUTE')
            reused.append({'once_key':pair['once_key'],'record_id':pair['record_id'],
               'canonical_geometry_id':pair['canonical_geometry_id'],'molecule_id':pair['molecule_id'],
               'source':'closed_real_pilot','all_twelve_success':prior['all_twelve_success'],
               'ledger':prior['ledger']})
    return reused,pending


def lane(lane_id,pairs,config_path,prepared,output,scratch_parent,reproduction_sha,deadline,cost_deadline):
    c,pilot=load(config_path)
    root=Path(output)/f'lane-{lane_id:02d}';root.mkdir(mode=0o700)
    scratch=Path(scratch_parent)/f'lane-{lane_id:02d}';scratch.mkdir(mode=0o700)
    os.environ.update(TMPDIR=str(scratch),TMP=str(scratch),CUDA_VISIBLE_DEVICES='',
       OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    e=sink=None;closed={'lane':lane_id,'pid':os.getpid(),'status':'FAILED','records':0}
    n=staged=0;outcomes=[]
    try:
        from engine_adapter import compute_pair
        from raw_archive import RawSink
        e,contract,_=IO.load_engine(pilot)
        e.initialize_worker(pilot['source_plan']['path'],protocol=contract['protocol']['path'],
            node_scratch_root=str(scratch),deadline=deadline,
            audit_membership=str(Path(prepared)/'audit_membership.json'),
            reproduction_package=contract['reproduction_package']['path'])
        sink=RawSink(root/'raw_outputs.sqlite',e.OUTPUT_ARCHIVE,c['max_retained_raw_bytes_per_worker'])
        import wp5_parquet_v2 as wire
        with (root/'parsed_records.jsonl').open('xb') as stream:
            for pair in pairs:
                if time.time()>=min(deadline-60,cost_deadline):
                    raise RuntimeError('COST_OR_WALL_ADMISSION_CLOSED_NO_NEW_RECORDS_NATURAL_DRAIN')
                started=begin(c,pair,{'prepared':IO.reference(Path(prepared)/'prepared.json'),
                                    'pprime_reproduction_manifest_sha256':reproduction_sha})
                record=compute_pair(e,pair,sink,{'job_id':int(os.environ['SLURM_JOB_ID']),
                   'lane':lane_id,'pprime_reproduction_manifest_sha256':reproduction_sha})
                record.update(lane=lane_id,canonical_geometry_id=pair['canonical_geometry_id'],
                              parent_view_id=pair['parent_view_id'],once_key=pair['once_key'])
                body=IO.staging_bytes(wire.native(record))+b'\n'
                if staged+len(body)>c['max_staging_bytes_per_worker']:
                    raise RuntimeError('FORMAL_BATCH_STAGING_CAP')
                stream.write(body);stream.flush();os.fsync(stream.fileno());staged+=len(body)
                success=len(record['tasks'])==12 and all(r['scope_status']=='SUCCESS' for r in record['tasks'])
                outcome={'record_id':pair['record_id'],'molecule_id':pair['molecule_id'],
                   'once_key':pair['once_key'],'canonical_geometry_id':pair['canonical_geometry_id'],
                   'all_twelve_success':success,'elapsed_seconds':record['elapsed_seconds'],
                   'started_ledger':started,'parsed_staging_path':str(root/'parsed_records.jsonl'),
                   'raw_container_path':str(root/'raw_outputs.sqlite'),
                   'task_statuses':[{k:d.get(k) for k in ('task','scope_status','failure_code','elapsed_seconds')} for d in record['tasks']]}
                outcome_dir=Path(c['attempt_ledger_root'])/'outcomes';outcome_dir.mkdir(exist_ok=True)
                outcome_ref=IO.write_json(outcome_dir/(pair['once_key']+'.json'),outcome)
                outcomes.append(dict(outcome,outcome=outcome_ref));n+=1
        closed.update(status='COMPLETE',records=n)
    except Exception as exc:
        closed.update(error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),records=n)
        if e is not None:e.PRESERVE_ARCHIVE_FAILURE=True
    finally:
        if sink is not None:sink.close()
        closed['engine_close']=e.close_worker() if e is not None else {'initialized':False}
        closed['outcomes']=outcomes
        for name,key in (('parsed_records.jsonl','staged'),('raw_outputs.sqlite','raw_container')):
            if (root/name).is_file():closed[key]=IO.reference(root/name)
        closed['scratch_path']=str(scratch);closed['scratch_preserved']=any(scratch.iterdir())
        if not closed['scratch_preserved']:scratch.rmdir()
        IO.write_json(root/'worker_closed.json',closed)
    return closed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','prepared','root-review','root-preflight','pilot-import','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--prepared-sha256',required=True);p.add_argument('--execute',action='store_true',required=True)
    a=p.parse_args();c,pilot=load(a.config);observed=runtime(c,a.root_preflight,a.config,science=True)
    prepared_path=a.prepared/'prepared.json'
    if IO.digest(prepared_path)!=a.prepared_sha256:raise ValueError('EXACT_PREPARED_SHA_REQUIRED')
    prepared=json.loads(prepared_path.read_text())
    if prepared['status']!='PPRIME_FORMAL_BATCH_INPUTS_READY_NOT_QM_EXECUTED' or prepared['config']!=IO.reference(a.config):
        raise ValueError('CLOSED_BASELINE_ONLY_BATCH_REQUIRED')
    IO.require_pin(prepared['plan']);decision,plan=formal_review(a.root_review,prepared['plan']['path'],c)
    if decision['pilot_import']!=IO.reference(a.pilot_import):raise ValueError('ROOT_REVIEW_PILOT_IMPORT_SHA_MISMATCH')
    imported=json.loads(a.pilot_import.read_text())
    if imported['status']!='REAL2000_PILOT_KEYS_IMPORTED_NO_QM' or imported['config']!=IO.reference(a.config) or imported['pilot_review']!=plan['pilot_review'] or imported['raw_policy']!=c['raw_policy']:
        raise ValueError('EXACT_CLOSED_REAL_PILOT_IMPORT_REQUIRED')
    entries={r['key']:r for r in imported['entries']}
    for row in imported['entries']:IO.require_pin(row['ledger'])
    if len(entries)!=2000:raise ValueError('EXACT2000_IMPORTED_PILOT_KEYS_REQUIRED')
    IO.require_pin(prepared['pairs']);IO.require_pin(prepared['audit_membership'])
    pairs=[json.loads(line) for line in Path(prepared['pairs']['path']).read_text().splitlines()]
    if not 0<len(pairs)<=1024 or len(pairs)!=prepared['records'] or len(pairs)%2:
        raise ValueError('BOUNDED_TWO_PER_MOLECULE_BATCH_REQUIRED')
    for pair in pairs:
        if pair['parent_view_id']!='baseline_common_v1' or type(pair['conformer']['sprime_conf_idx']) is not int:
            raise ValueError('N1_EXPANDED_VIEW_NOT_APPROVED_BY_BASELINE_VALIDATOR')
        if __import__('hashlib').sha256(IO.canonical(pair['conformer'])).hexdigest()!=pair['conformer_row_sha256']:
            raise ValueError('PREPARED_CONFORMER_ROW_CHANGED')
        if task_key(pair['molecule_id'],pair['conformer']['atom_order_sha256'],pair['uff_coordinate_sha256'],prepared['protocol']['sha256'],pair['record_id'])!=pair['once_key']:
            raise ValueError('SCIENTIFIC_ONCE_KEY_CHANGED')
    membership=json.loads(Path(prepared['audit_membership']['path']).read_text())
    import pyarrow.parquet as pq
    audited=set(pq.read_table(IO.require_pin(membership['selected_records']),columns=['record_id'])['record_id'].to_pylist())
    reused,pending=split_imports(pairs,entries,audited)
    if not pending:
        raise ValueError('ALL_RECORDS_REUSED_NO_QM_JOB_NEEDED_USE_IMPORT_EVIDENCE_AT_FINALIZE')
    # Inspect the entire batch before any start; a timeout/unknown attempt cannot be rerun.
    if any(ledger_file(c,r['once_key']).exists() for r in pending):
        raise ValueError('CONSUMED_OR_UNKNOWN_ATTEMPT_REQUIRES_ROOT_REVIEW_NO_AUTO_RETRY')
    out=IO.new_output(a.output,c)
    e,contract,protocol=IO.load_engine(pilot);e.CONFIG=protocol
    if prepared['protocol']!=contract['protocol']:raise ValueError('PREPARED_AND_ACTUAL_FROZEN_TASK_PROTOCOL_DIFFER')
    reproduction=IO.write_json(out/'reproduction_manifest.json',{'schema':'PPRIME_FORMAL_REPRODUCTION_V1',
       'prepared':IO.reference(prepared_path),'config':IO.reference(a.config),'root_review':IO.reference(a.root_review),
       'pilot_import':IO.reference(a.pilot_import),'parent_source_pins':c['parent_source_pins'],
       'actual_formal_sources':[IO.reference(s) for s in sorted(Path(__file__).parent.glob('*.py'))],
       'actual_retention_sources':[IO.reference(s) for s in sorted((Path(__file__).parent.parent/'retention_v1').glob('*.py'))],
       'legacy_contract':pilot['legacy_contract'],'protocol':contract['protocol'],
       'legacy_reproduction_package':contract['reproduction_package'],'Q02_applicable':False,
       'geometry_source':'uff_sprime','task_recipe_or_keywords_changed':False})
    started=time.time();closed=[];processes=[]
    short=Path('/tmp')/f'pf_{observed["job_id"]}_{os.getpid()}';short.mkdir(mode=0o700)
    os.environ['TMPDIR']=str(short);__import__('tempfile').tempdir=None
    if pending:
        cost_seconds=plan['actual_pilot_core_seconds_per_conformer']*len(pending)*1.5/16
        # Floor covers setup for small final batches; final actual sacct has no floor.
        cost_deadline=started+max(120,cost_seconds)
        pool=ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'))
        futures=[pool.submit(lane,i,pending[i::16],str(a.config),str(a.prepared),str(out),str(short),
                  reproduction['sha256'],started+c['worker_wall_seconds'],cost_deadline) for i in range(16)]
        processes=list(pool._processes.values())
        try:
            for future in as_completed(futures):
                try:closed.append(future.result())
                except Exception as exc:closed.append({'status':'WORKER_FAILED_BEFORE_CLOSURE','error':str(exc)})
        finally:pool.shutdown(wait=True,cancel_futures=False)
    process_closure=[{'pid':r.pid,'exitcode':r.exitcode,'alive':r.is_alive()} for r in processes]
    joined=(not pending) or (len(process_closure)==16 and len({r.get('pid') for r in closed})==16 and all(not r['alive'] and r['exitcode']==0 for r in process_closure))
    failures=[r for r in closed if r['status']!='COMPLETE']
    records=[]
    for row in closed:
        if row.get('staged'):
            with IO.require_pin(row['staged']).open('rb') as stream:records.extend(IO.read_staging(line) for line in stream)
    actual_keys={r['once_key'] for r in records}
    if actual_keys!={r['once_key'] for r in pending}:failures.append({'status':'COMPLETED_KEY_SET_INCOMPLETE'})
    families=[];qc=[]
    if joined and not failures and records:
        from export_v1 import export
        families,qc=export(records,out/'parquet',e,reproduction['sha256'],c)
    from retention_policy_v1 import prove_raw
    source_rows=[{'record_id':pair['record_id'],'source_shard_id':pair['source']['shard_id'],
        'legacy_engine_file_group':pair['source']['file_group'],
        'retain_all_twelve_raw':pair['stable_raw_audit_selected']} for pair in pending]
    proof=prove_raw(closed,source_rows,records,e)
    proof.update(audit_policy=c['raw_policy'],prepared=IO.reference(prepared_path))
    proof_ref=IO.write_json(out/'stable_raw_all12_proof.json',proof)
    if proof['missing']:failures.append({'status':'STABLE_AUDIT_OR_FAILED_CALL_RAW_MISSING'})
    outcomes=[r for worker in closed for r in worker.get('outcomes',[])]+reused
    status='PPRIME_FORMAL_BATCH_CLOSED_AWAITING_ACTUAL_PARENT_ACCOUNTING' if joined and not failures else 'PPRIME_FORMAL_BATCH_INCOMPLETE_STOP_NO_AUTO_RETRY'
    IO.write_json(out/'result.json',{'status':status,'runtime':observed,'config':IO.reference(a.config),
       'prepared':IO.reference(prepared_path),'plan':prepared['plan'],'root_review':IO.reference(a.root_review),
       'pilot_import':IO.reference(a.pilot_import),'batch_id':prepared['batch_id'],'requested_records':len(pairs),
       'requested_new_records':len(pending),'new_records':len(records),'reused_pilot_records':len(reused),
       'outcomes':outcomes,'family_parquets':families,'workers':closed,'process_closure':process_closure,
       'stable_raw_retention_proof':proof_ref,
       'all_workers_joined':joined,'failures':failures,'reproduction_manifest':reproduction,
       'whole_common_complete':False,'outlier_scan_completed':False,'P_vs_Pprime_comparison_completed':False,
       'scratch_parent':str(short),'actual_cost_pending':True,
       'output_bytes_before_report':IO.output_guard(out,c,reserve=2<<20)})
    if not any(short.iterdir()):short.rmdir()
    return 0 if not failures and joined else 1


if __name__=='__main__':raise SystemExit(main())
