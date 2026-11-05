"""Use original pilot lanes/recipe with independently registered extra raw retention."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import multiprocessing as mp
import os
from pathlib import Path
import time

from retention_policy_v1 import IO,load,prove_raw
from run_pilot import run_lane


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','retention','root-preflight','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--retention-sha256',required=True);p.add_argument('--execute',action='store_true',required=True)
    a=p.parse_args();c,pilot=load(a.config);observed=IO.runtime()
    IO.require_preflight(a.root_preflight,a.config,c)
    request=json.loads(a.root_preflight.read_text())['request']
    if request['kind']!='qm' or request['memory_gib']!=64 or request['cpus']!=16 or request['wall_seconds']>7200 or request.get('memory_basis'):
        raise ValueError('PILOT_QM_REQUIRES_ORDINARY_16CPU64G_MAX2H_NO_SMALL_UFF_EXCEPTION')
    retention_path=a.retention/'retention_manifest.json'
    if IO.digest(retention_path)!=a.retention_sha256:raise ValueError('EXACT_RETENTION_MANIFEST_SHA_REQUIRED')
    saved=json.loads(retention_path.read_text())
    if saved['status']!='PREPARED_NOT_QM_EXECUTED' or saved['audit_policy']!=IO.reference(a.config):
        raise ValueError('EXACT_NEW_RETENTION_BINDING_REQUIRED')
    for key in ('original_prepared','original_pairs','original_audit_membership','original_audit_selected20',
                'source_audit','stable_full_hits','pilot_retention_union','engine_record_audit_membership','engine_selected'):
        IO.require_pin(saved[key])
    source_rows=json.loads(Path(saved['source_audit']['path']).read_text())
    pairs=[json.loads(line) for line in Path(saved['original_pairs']['path']).read_text().splitlines()]
    grouped={}
    for pair in pairs:grouped.setdefault(pair['molecule_id'],[]).append(pair)
    if len(pairs)!=2000 or len(grouped)!=1000 or any(len(rows)!=2 for rows in grouped.values()):
        raise ValueError('UNCHANGED_EXACT1000_BY_TWO_PILOT_REQUIRED')
    out=IO.new_output(a.output,c);e,contract,protocol=IO.load_engine(pilot);e.CONFIG=protocol
    ledger=Path(c['pilot_once_ledger_root'])
    if Path(c['external_output_root']) not in ledger.parents or any(p.is_symlink() for p in (ledger,*ledger.parents)):
        raise ValueError('PILOT_ONCE_LEDGER_OUTSIDE_OWN_RETENTION_ROOT')
    ledger.mkdir(mode=0o700,parents=True,exist_ok=True)
    once_key=__import__('hashlib').sha256(IO.canonical(['original2000-pilot-science-once-v1',
        saved['original_pairs']['sha256'],contract['protocol']['sha256']])).hexdigest()
    # Changing retention or output directory does not permit repeating this pilot.
    once_ref=IO.write_json(ledger/(once_key+'.json'),{'status':'PILOT_STARTED_OUTCOME_UNKNOWN_UNTIL_CLOSED',
        'job_id':observed['job_id'],'original_pairs':saved['original_pairs'],'protocol':contract['protocol'],
        'retention':IO.reference(retention_path),'output':str(out)})
    reproduction=IO.write_json(out/'reproduction_manifest.json',{'schema':'PPRIME_PILOT_RETENTION_REPRODUCTION_V1',
       'status':'INPUT_AND_SCIENCE_REFERENCES_FROZEN_BEFORE_QM','config':c['pilot_config'],
       'audit_policy':IO.reference(a.config),'retention':IO.reference(retention_path),
       'original_prepared':saved['original_prepared'],'original_pairs':saved['original_pairs'],
       'original_source_audit':saved['original_audit_selected20'],'stable_source_audit':saved['source_audit'],
       'sources':[IO.reference(s) for s in sorted(Path(__file__).parent.glob('*.py'))],
       'parent_sources':c['parent_source_pins'],'legacy_contract':pilot['legacy_contract'],
       'legacy_reproduction_package':contract['reproduction_package'],
       'geometry_source':'uff_sprime','Q02_applicable':False,'scientific_input_or_numerics_changed':False,
       'retention_overhead_included_in_actual_parent_pilot_cost':True})
    short=Path('/tmp')/f'pr_{observed["job_id"]}_{os.getpid()}';short.mkdir(mode=0o700)
    os.environ['TMPDIR']=str(short);__import__('tempfile').tempdir=None
    molecules=[sorted(rows,key=lambda r:r['random_order_rank']) for _,rows in sorted(grouped.items())]
    started=time.time();deadline=started+pilot['worker_wall_seconds'];closed=[]
    pool=ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'))
    futures=[pool.submit(run_lane,lane,molecules[lane::16],c['pilot_config']['path'],str(a.retention),str(out),
               str(short),reproduction['sha256'],deadline) for lane in range(16)]
    processes=list(pool._processes.values())
    try:
        for future in as_completed(futures):
            try:closed.append(future.result())
            except Exception as exc:closed.append({'status':'WORKER_FAILED_BEFORE_CLOSURE','error':str(exc)})
    finally:pool.shutdown(wait=True,cancel_futures=False)
    pc=[{'pid':r.pid,'exitcode':r.exitcode,'alive':r.is_alive()} for r in processes]
    joined=len(pc)==16 and len({r.get('pid') for r in closed})==16 and all(not r['alive'] and r['exitcode']==0 for r in pc)
    failures=[r for r in closed if r['status']!='COMPLETE'];records=[]
    for row in closed:
        if row.get('staged'):
            with IO.require_pin(row['staged']).open('rb') as stream:records.extend(IO.read_staging(line) for line in stream)
    records.sort(key=lambda r:r['record_id']);families=[];qc=[]
    if len(records)==2000 and joined and not failures:
        from export_families import export
        families,qc=export(records,out/'parquet',e,reproduction['sha256'],pilot)
    proof=prove_raw(closed,source_rows,records,e)
    proof.update(audit_policy=IO.reference(a.config),retention=IO.reference(retention_path),source_audit=saved['source_audit'])
    proof_ref=IO.write_json(out/'stable_raw_all12_proof.json',proof)
    if proof['missing']:failures.append({'status':'STABLE_RAW_FULL12_PROOF_INCOMPLETE'})
    success=sum(r['all_twelve_tasks_success'] for r in qc) if qc else 0
    status='PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' if families and joined and not failures else 'PPRIME_PILOT_FAILED_NO_FULL_AUTHORITY'
    IO.write_json(out/'result.json',{'status':status,'runtime':observed,'config':c['pilot_config'],
       'retention_policy':IO.reference(a.config),'retention':IO.reference(retention_path),'stable_raw_retention_proof':proof_ref,
       'pilot_once_ledger':once_ref,
       'prepared':saved['original_prepared'],'reproduction_manifest':reproduction,'root_preflight':IO.reference(a.root_preflight),
       'completed_records':len(records),'requested_records':2000,'all_twelve_tasks_success_records':success,
       'record_success_rate':success/2000,'all_workers_joined':joined,'workers':closed,'process_closure':pc,
       'failures':failures,'family_parquets':families,
       'failure_reasons':[{'task':k[0],'code':k[1],'count':v} for k,v in sorted(Counter((d['task'],d.get('failure_code') or 'UNSPECIFIED') for r in records for d in r['tasks'] if d['scope_status']!='SUCCESS').items())],
       'all_2000_elapsed_seconds':[{'record_id':r['record_id'],'elapsed_seconds':r['elapsed_seconds']} for r in records],
       'allocated_core_seconds_per_conformer':None,'retention_overhead_deducted':False,
       'accounting_reason':'actual complete parent AllocCPUS*ElapsedRaw including all startup/export/retention/failures; close_pilot.py unchanged',
       'Pprime_outlier_scan_completed':False,'P_vs_Pprime_comparison_completed':False,
       'scientific_inputs_or_parameters_changed':False,'full_run_authorized':False,
       'output_bytes_before_report':IO.output_guard(out,c,reserve=2<<20)})
    if not any(short.iterdir()):short.rmdir()
    return 0 if status=='PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' else 1


if __name__=='__main__':raise SystemExit(main())
