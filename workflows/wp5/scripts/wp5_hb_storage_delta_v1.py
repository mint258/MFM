#!/usr/bin/env python3
"""Read-only HB parser2 storage overlay on the actual same50 double-run rows.
No QM, raw rewrite, production edits, or full G3 recalibration.
The stage allowance reserves uncompressed standalone insertion fragments for
all five MOPAC calls per record; JSON/zstd sizes are diagnostic, not extra copies.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,copy,hashlib,json,multiprocessing,os,pickle,socket
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
HB='hydrogen_bond_energy_kcal_mol'
_WORK={}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':sha(p)}
def init(entries,barrier):
    global _WORK
    import pyarrow as pa
    import wp5_parquet_v2 as wire
    import wp5_registry_coverage_v2 as coverage
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    _WORK={'entries':entries,'wire':wire,'coverage':coverage}
    barrier.wait(timeout=180)
def detail_from_row(row):
    wire=_WORK['wire'];by={e['registry_id']:e for e in _WORK['entries']}
    detail={'task':row['calc_type'],'record_id':row['record_id'],'values':{}}
    for cell in row['values']:
        value=wire.decode(cell)
        if value is wire.MISSING:continue
        parts=by[cell['registry_id']]['source_path'].split('.')
        if parts[0] in ('detail','details'):parts=parts[1:]
        target=detail
        for part in parts[:-1]:target=target.setdefault(part,{})
        target[parts[-1]]=value
    return detail
def production_evidence(row):
    detail=detail_from_row(row);coverage=_WORK['coverage']
    previous=json.loads(row.get('registry_source_evidence_json') or '{}') or {}
    prior={int(r[0]):r for r in previous.get('rows',[])}
    audit=coverage.audit_task(detail,_WORK['entries'],serialized_row=row,files=None)
    rows=[]
    for r in audit['rows']:
        reason=r['source_reason']
        if r['observed_state'] not in ('VALUE','EMPTY') and r['source_spec'].get('applicable') is not False and r['registry_id'] in prior and r['source_spec']['artifacts']:
            reason=prior[r['registry_id']][2]
        rows.append([r['registry_id'],r['observed_state'],reason])
    result={'status':audit['status'],'expected_active_registry_fields':audit['expected_active_registry_fields'],
        'rows':rows,'issues':audit['issues'],
        'source_token_proof_retained_without_raw_text':previous.get('source_token_proof_retained_without_raw_text',True)}
    return json.dumps(result,sort_keys=True,separators=(',',':'))
def parquet_bytes(rows):
    import pyarrow as pa,pyarrow.parquet as pq
    wire=_WORK['wire'];table=pa.Table.from_pylist(rows,schema=wire.SCHEMA)
    sink=pa.BufferOutputStream()
    pq.write_table(table,sink,compression='zstd',compression_level=3,row_group_size=32768)
    buffer=sink.getvalue()
    wire.exact(table.to_pylist(),pq.read_table(pa.BufferReader(buffer)).to_pylist())
    return buffer.size
def profile_record(item):
    old_rows,new_rows=item['old'],item['new']
    wire=_WORK['wire'];old={r['calc_type']:r for r in old_rows}
    new={r['calc_type']:copy.deepcopy(r) for r in new_rows}
    if len(old)!=12 or old.keys()!=new.keys():raise ValueError('Twelve actual calls not closed')
    for calc,row in new.items():
        original=old[calc]
        by_old={c['registry_id']:c for c in original['values']}
        by_new={c['registry_id']:c for c in row['values']}
        if by_old.keys()!=by_new.keys():raise ValueError('Registry cell set changed')
        for rid in by_old:
            entry=next(e for e in _WORK['entries'] if e['registry_id']==rid)
            if calc=='pm7_B' and entry['source_path']=='values.'+HB:continue
            wire.exact(by_old[rid],by_new[rid])
        for key in original:
            if key not in ('values','precision_by_field_json','registry_source_evidence_json'):wire.exact(original[key],row[key])
        row['registry_source_evidence_json']=production_evidence(row)
    families=sorted({wire.FAMILIES[c] for c in old})
    sizes=[]
    for family in families:
        before=[old[c] for c in sorted(old) if wire.FAMILIES[c]==family]
        after=[new[c] for c in sorted(new) if wire.FAMILIES[c]==family]
        b,a=parquet_bytes(before),parquet_bytes(after)
        sizes.append({'family':family,'old_bytes':b,'new_bytes':a,'delta_bytes':a-b})
    proof=item['proof']
    if proof['proof']['field']!=HB:raise ValueError('Wrong native HB proof')
    fragment={'values':{HB:proof['new_value']},
       'parser_context':{'hydrogen_bond_energy_source':proof['proof']},
       'precision_by_field':{}}
    dp=proof['proof'].get('rounding_decimal_places')
    if dp is not None:
        fragment['parser_context']['rounding_decimal_places']={HB:dp}
        fragment['precision_by_field']={HB:dp}
    raw=pickle.dumps(fragment,protocol=5)
    try:
        import zstandard
        compressed=zstandard.ZstdCompressor(level=3).compress(raw)
    except ImportError:
        from wp5_archive_v5 import Zstd
        codec=Zstd();dictionary=b''
        try:compressed=codec.compress(raw,dictionary)
        finally:codec.close()
    return {'record_id':item['record_id'],'run':item['run'],'worker_pid':os.getpid(),
       'family_sizes':sizes,'positive_family_delta_bytes':sum(max(0,r['delta_bytes']) for r in sizes),
       'signed_family_delta_bytes':sum(r['delta_bytes'] for r in sizes),
       'stage_insert_pickle_bytes':len(raw),'stage_insert_zstd_bytes':len(compressed),
       'stage_insert_json_bytes':len(json.dumps(fragment,sort_keys=True,separators=(',',':')).encode()),
       'new_HB_value':proof['new_value']}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--replay-root',default=str(ROOT/'gates/reproduction50_replay/job_4513969'))
    p.add_argument('--budget',default=str(ROOT/'gates/g3/new_policy_budget_v11_job_4513959.json'))
    p.add_argument('--tasks',default=str(ROOT/'packing/node_assignment_v3/tasks.json'))
    p.add_argument('--registry',default='/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/reports/label_registry_v2.json')
    p.add_argument('--quota');p.add_argument('--workers',type=int,default=16);p.add_argument('--output')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('HB_STORAGE_DELTA_AST_PASS_NO_QM');return
    if not a.output:p.error('--output required')
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('16 actual metadata workers required')
    if socket.gethostname().split('.')[0] not in {'compute-0-12','compute-0-13','compute-0-14','compute-0-17','compute-0-18','compute-0-19','compute-0-20'}:raise ValueError('Compute node only')
    import pyarrow.parquet as pq,wp5_parquet_v2 as wire,wp5_parser_v2 as parser
    replay=Path(a.replay_root);report=read(replay/'report.json')
    if report['status']!='PASS' or report['records']!=50 or report['non_HB_cells_exact_original']!=62100 or report['only_changed_physical_field']!='values.'+HB:raise ValueError('Actual offline50 PASS required')
    entries=wire.registry(a.registry)
    proofs={(r['run'],r['record_id']):r for r in read(replay/'HB_delta_proofs.json')['rows']}
    jobs=[]
    for run,export_ref in enumerate(report['original_run_exports'],1):
        if sha(export_ref['path'])!=export_ref['sha256']:raise ValueError('Original export SHA differs')
        old={};completion=read(export_ref['path'])
        for r in completion['families']:
            if r['family'] not in set(wire.FAMILIES.values()):continue
            if sha(r['path'])!=r['sha256']:raise ValueError('Original family SHA differs')
            for row in pq.read_table(r['path']).to_pylist():old[(row['record_id'],row['calc_type'])]=row
        new_ref=report['reprocessed_parquets'][run-1]
        if sha(new_ref['path'])!=new_ref['sha256']:raise ValueError('Replayed Parquet SHA differs')
        new={(r['record_id'],r['calc_type']):r for r in pq.read_table(new_ref['path']).to_pylist()}
        if len(old)!=600 or old.keys()!=new.keys():raise ValueError('Original/replayed600 closure differs')
        for rid in sorted({key[0] for key in old}):
            jobs.append({'record_id':rid,'run':run,'old':[r for (record,c),r in old.items() if record==rid],
                'new':[r for (record,c),r in new.items() if record==rid],'proof':proofs[(run,rid)]})
    if len(jobs)!=100:raise ValueError('Actual same50 twice scope differs')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(entries,barrier)) as pool:
        results=list(pool.map(profile_record,jobs,chunksize=1))
    pids=sorted({r['worker_pid'] for r in results})
    if len(pids)<16:raise ValueError('Effective workers below16')
    # Parser2 also adds an explicit no-number proof on non-B calls. Reserve the
    # larger of that exact generator template and all actual B insert fragments
    # for EACH of the five MOPAC calls, including calls which fail before parsing.
    null_proof=parser.hydrogen_bond_fallback({HB:None},'')
    null_fragment={'values':{HB:None},'parser_context':{'hydrogen_bond_energy_source':null_proof},'precision_by_field':{}}
    null_pickle=len(pickle.dumps(null_fragment,protocol=5))
    stage_per_call=max([null_pickle]+[max(r['stage_insert_pickle_bytes'],r['stage_insert_zstd_bytes']) for r in results])
    permanent_per_record=max(r['positive_family_delta_bytes'] for r in results)
    budget=read(a.budget);tasks=read(a.tasks)['tasks'];n=budget['formal_records']
    if (n,budget['formal_molecules'],len(tasks),sum(t['records'] for t in tasks))!=(11231854,1220466,72,11231854):raise ValueError('Formal allocation closure differs')
    records29=sum(sorted((t['records'] for t in tasks),reverse=True)[:29])
    permanent_increment=n*permanent_per_record
    stage_increment=records29*5*stage_per_call
    delta=permanent_increment+stage_increment
    free=budget['fresh_quota_remaining_bytes'];quota=None
    if a.quota:
        quota=read(a.quota);free=quota.get('quota_parsed',{}).get('remaining_bytes',quota.get('remaining_bytes'))
        if free is None:raise ValueError('Actual fresh remaining quota missing')
    peak=budget['writeback_peak_bytes']+delta;head=free-peak
    output={'schema':'WP5_HB_STORAGE_DELTA_OVERLAY_V1','status':'SAME50_HB_STORAGE_DELTA_CLOSED',
      'scientific_rows_unchanged_except_HB':True,'new_QM_calls':0,'actual_worker_pids':pids,
      'sample_record_observations':100,'unique_records':50,'sample_task_rows_per_run':600,
      'source_replay_report':ref(replay/'report.json'),'source_budget':ref(a.budget),'source_tasks':ref(a.tasks),
      'source_registry':ref(a.registry),'source_proofs':ref(replay/'HB_delta_proofs.json'),
      'measurements':results,'null_native_proof_pickle_bytes':null_pickle,
      'max_positive_Parquet_increment_bytes_per_record':permanent_per_record,
      'max_standalone_stage_insert_reserve_bytes_per_MOPAC_call':stage_per_call,
      'top29_records_upper':records29,'permanent_increment_bytes':permanent_increment,
      'temporary_stage_increment_bytes':stage_increment,'output_archive_increment_bytes':0,
      'canonical_increment_bytes':0,'pending_family_additional_bytes':0,
      'total_increment_bytes':delta,'old_writeback_peak_bytes':budget['writeback_peak_bytes'],
      'new_writeback_peak_bytes':peak,'fresh_quota_remaining_bytes':free,'headroom_bytes':head,
      'storage_capacity_estimate_pass':head>=200_000_000_000,'required_headroom_bytes':200_000_000_000,
      'quota_source':ref(a.quota) if a.quota else budget.get('fresh_quota'),
      'production_G3_G6_PASS_not_inferred':True,
      'method':'Permanent: formalN times max positive paired same-record family Parquet growth, no decreases credited. Stage: sum29 largest task record counts times5 times max uncompressed standalone exact HB insert or its zstd frame; no claim that retired full wholeMol wires were recovered. JSON size diagnostic only, not charged as a second stored format. Original raw metadata excludes parsed values/context; outputs, keywords and raw body policy unchanged. Pending/final family and canonical count once by frozen lifecycle.',
      'source_sha256':sha(__file__)}
    out=Path(a.output)
    if not out.is_absolute() or not out.is_relative_to(ROOT) or out.exists():raise ValueError('New immutable own output required')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(output,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'path':str(out),'delta_GB_decimal':delta/1e9,'headroom_GB_decimal':head/1e9,'capacity_estimate_pass':head>=2e11}))
if __name__=='__main__':main()
