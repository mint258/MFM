#!/usr/bin/env python3
"""Correct HB delta by production128-row groups on the same actual50 rows.
No QM, schema/production changes or full G3 recalibration. Single-record stats
overheads are charged per row group/file, never multiplied by record count.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,copy,json,multiprocessing,os,socket
from pathlib import Path
import wp5_hb_storage_delta_v1 as BASE
ROOT=BASE.ROOT
def profile_buffer(rows,groups):
    import pyarrow as pa,pyarrow.parquet as pq
    wire=BASE._WORK['wire'];sink=pa.BufferOutputStream()
    writer=pq.ParquetWriter(sink,wire.SCHEMA,compression='zstd',compression_level=3)
    expected=[]
    try:
        for g in range(groups):
            batch=[rows[(g*128+i)%len(rows)] for i in range(128)]
            expected.append(batch)
            writer.write_table(pa.Table.from_pylist(batch,schema=wire.SCHEMA),row_group_size=32768)
    finally:writer.close()
    buffer=sink.getvalue();file=pq.ParquetFile(pa.BufferReader(buffer));m=file.metadata
    if m.num_row_groups!=groups or m.num_rows!=128*groups:raise ValueError('Actual128 writer groups differ')
    for actual,reference in zip(file.iter_batches(batch_size=128),expected):wire.exact(reference,actual.to_pylist())
    columns=collections.defaultdict(int);stats=[]
    for gi in range(groups):
        rg=m.row_group(gi)
        if rg.num_rows!=128:raise ValueError('Writer rowgroup not128')
        for ci in range(rg.num_columns):
            col=rg.column(ci);columns[col.path_in_schema]+=col.total_compressed_size
            if col.path_in_schema in ('registry_source_evidence_json','precision_by_field_json','values.list.element.f64'):
                stat=col.statistics
                size=lambda value:len(value.encode()) if isinstance(value,str) else len(value) if isinstance(value,bytes) else None
                stats.append({'row_group':gi,'column':col.path_in_schema,'compressed_bytes':col.total_compressed_size,
                    'has_min_max':bool(stat and stat.has_min_max),
                    'min_bytes':size(stat.min) if stat and stat.has_min_max else None,
                    'max_bytes':size(stat.max) if stat and stat.has_min_max else None})
    return {'physical_bytes':buffer.size,'footer_bytes':m.serialized_size,'rows':m.num_rows,
       'row_groups':m.num_row_groups,'columns_compressed':dict(columns),'statistics':stats}
def profile_case(arg):
    wire=BASE._WORK['wire'];before=arg['old'];after=copy.deepcopy(arg['new'])
    if (before['record_id'],before['calc_type'])!=(after['record_id'],after['calc_type']):raise ValueError('Paired actual rows differ')
    cb={c['registry_id']:c for c in before['values']};ca={c['registry_id']:c for c in after['values']}
    if cb.keys()!=ca.keys():raise ValueError('Registry cells changed')
    payload=0
    for rid in cb:
        entry=next(e for e in BASE._WORK['entries'] if e['registry_id']==rid)
        if before['calc_type']=='pm7_B' and entry['source_path']=='values.'+BASE.HB:
            if cb[rid]['f64'] is None and ca[rid]['f64'] is not None:payload+=8
        else:wire.exact(cb[rid],ca[rid])
    for key in before:
        if key not in ('values','precision_by_field_json','registry_source_evidence_json'):wire.exact(before[key],after[key])
    after['registry_source_evidence_json']=BASE.production_evidence(after)
    json_delta={}
    for key in ('precision_by_field_json','registry_source_evidence_json'):
        delta=len((after[key] or '').encode())-len((before[key] or '').encode())
        json_delta[key]=delta;payload+=max(0,delta)
    common={'family':arg['family'],'file_group':arg['file_group'],'run':arg['run'],
       'record_id':before['record_id'],'calc_type':before['calc_type'],'worker_pid':os.getpid(),
       'positive_logical_payload_bytes_per_task_row':payload,'json_delta_bytes':json_delta,
       'same_actual_row_repeated_only_for_writer_geometry':True}
    try:wire.exact(before,after);unchanged=True
    except ValueError:unchanged=False
    if unchanged:
        return {**common,'typed_row_exactly_unchanged':True,'profiles':{},
          'charge_bytes_per_128_rowgroup_upper':0,'per_file_extra_bytes_upper':0}
    profiles={}
    for groups in (1,2):
        left,right=profile_buffer([before],groups),profile_buffer([after],groups)
        profiles[str(groups)]={'old':left,'new':right,
          'physical_delta_bytes':right['physical_bytes']-left['physical_bytes'],
          'footer_delta_bytes':right['footer_bytes']-left['footer_bytes'],
          'column_compressed_delta_bytes':sum(right['columns_compressed'].values())-sum(left['columns_compressed'].values()),
          'per_column_delta':{k:right['columns_compressed'][k]-left['columns_compressed'][k]
              for k in left['columns_compressed'] if right['columns_compressed'][k]!=left['columns_compressed'][k]}}
    d1=profiles['1']['physical_delta_bytes'];d2=profiles['2']['physical_delta_bytes']
    charge=max(0,d1,d2-d1,(d2+1)//2)
    return {**common,'typed_row_exactly_unchanged':False,'profiles':profiles,
       'charge_bytes_per_128_rowgroup_upper':charge,
       'per_file_extra_bytes_upper':max(0,2*d1-d2)}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--replay-root',default=str(ROOT/'gates/reproduction50_replay/job_4513969'))
    p.add_argument('--budget',default=str(ROOT/'gates/g3/new_policy_budget_v11_job_4513959.json'))
    p.add_argument('--previous-overlay',default=str(ROOT/'gates/g3/HB_delta_job_4513972.json'))
    p.add_argument('--tasks',default=str(ROOT/'packing/node_assignment_v3/tasks.json'))
    p.add_argument('--registry',default='/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/reports/label_registry_v2.json')
    p.add_argument('--quota');p.add_argument('--workers',type=int,default=16);p.add_argument('--output')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('HB_STORAGE_DELTA_V2_WRITER_GEOMETRY_AST_PASS_NO_QM');return
    if not a.output:p.error('--output required')
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('16 actual workers required')
    if socket.gethostname().split('.')[0] not in {'compute-0-12','compute-0-13','compute-0-14','compute-0-17','compute-0-18','compute-0-19','compute-0-20'}:raise ValueError('Compute only')
    import pyarrow.parquet as pq,wp5_parquet_v2 as wire
    replay=Path(a.replay_root);report=BASE.read(replay/'report.json');budget=BASE.read(a.budget)
    prior=BASE.read(a.previous_overlay);tasks=BASE.read(a.tasks)['tasks'];entries=wire.registry(a.registry)
    if report['status']!='PASS' or report['records']!=50 or report['non_HB_cells_exact_original']!=62100:raise ValueError('Actual same50 replay proof absent')
    if prior['status']!='SAME50_HB_STORAGE_DELTA_CLOSED' or prior['temporary_stage_increment_bytes']!=13312648270:raise ValueError('Preserve actual stage reserve13.312648270GB')
    if BASE.sha(a.budget)!=prior['source_budget']['sha256']:raise ValueError('Original G3 changed')
    if (budget['formal_records'],budget['formal_molecules'],len(tasks),sum(t['records'] for t in tasks))!=(11231854,1220466,72,11231854):raise ValueError('Formal population/task closure differs')
    jobs=[];seen=set();observed_records=set()
    for run,export_ref in enumerate(report['original_run_exports'],1):
        if BASE.sha(export_ref['path'])!=export_ref['sha256']:raise ValueError('Original export SHA differs')
        completion=BASE.read(export_ref['path']);new_ref=report['reprocessed_parquets'][run-1]
        if BASE.sha(new_ref['path'])!=new_ref['sha256']:raise ValueError('Replay source changed')
        new={(r['record_id'],r['calc_type']):r for r in pq.read_table(new_ref['path']).to_pylist()}
        if len(new)!=600:raise ValueError('Replayed600 missing')
        for ref in completion['families']:
            if ref['family'] not in set(wire.FAMILIES.values()):continue
            if BASE.sha(ref['path'])!=ref['sha256']:raise ValueError('Original family changed')
            old=pq.read_table(ref['path']).to_pylist()
            for r in old:
                key=(run,r['record_id'],r['calc_type'])
                if key in seen:raise ValueError('Original call repeated')
                seen.add(key);observed_records.add(r['record_id'])
            for row in old:
                jobs.append({'family':ref['family'],'file_group':ref['file_group'],'run':run,'old':row,
                    'new':new[(row['record_id'],row['calc_type'])]})
    if len(seen)!=1200 or len(observed_records)!=50:raise ValueError('Actual50/1200 call scope differs')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=BASE.init,initargs=(entries,barrier)) as pool:
        measurements=list(pool.map(profile_case,jobs,chunksize=1))
    pids=sorted({m['worker_pid'] for m in measurements})
    if len(pids)<16:raise ValueError('Actual effective workers below16')
    families=collections.Counter(wire.FAMILIES.values());projection=[];permanent=0
    payload_by_calc={calc:max(m['positive_logical_payload_bytes_per_task_row'] for m in measurements if m['calc_type']==calc)
       for calc in wire.FAMILIES}
    # No repeated-value/dictionary savings are projected across the population.
    # Reserve all positive new scalar/JSON payload uncompressed per genuine row,
    # in addition to the measured page+footer128-group upper charges.
    logical_payload_increment=11231854*sum(payload_by_calc.values())
    for family,mult in sorted(families.items()):
        samples=[m for m in measurements if m['family']==family]
        charge=max(m['charge_bytes_per_128_rowgroup_upper'] for m in samples)
        file_extra=max(m['per_file_extra_bytes_upper'] for m in samples)
        groups=sum((t['records']*mult+127)//128 for t in tasks)
        # Main72 files/family plus up to five group tails for each six cleanup jobs.
        # Each extra short tail charges a full measured128 group: no tail savings.
        cleanup_tail_groups=6*5;files=72+cleanup_tail_groups
        amount=(groups+cleanup_tail_groups)*charge+files*file_extra;permanent+=amount
        projection.append({'family':family,'task_rows_per_record':mult,'formal_task_rows':11231854*mult,
           'planned_main_files':72,'planned_cleanup_file_tail_allowance':cleanup_tail_groups,
           'main_rowgroups_at_actual128_writer_batch':groups,'charge_bytes_per_128_group_upper':charge,
           'per_file_extra_bytes_upper':file_extra,'permanent_increment_bytes':amount})
    rowgroup_file_increment=permanent;permanent+=logical_payload_increment
    stage=prior['temporary_stage_increment_bytes'];delta=permanent+stage
    free=budget['fresh_quota_remaining_bytes'];quota_source=budget.get('fresh_quota')
    if a.quota:
        quota=BASE.read(a.quota);free=quota.get('quota_parsed',{}).get('remaining_bytes',quota.get('remaining_bytes'));quota_source=BASE.ref(a.quota)
        if free is None:raise ValueError('Actual fresh quota required')
    peak=budget['writeback_peak_bytes']+delta;head=free-peak
    output={'schema':'WP5_HB_STORAGE_DELTA_OVERLAY_V2','status':'SAME50_HB_PRODUCTION_ROWGROUP_DELTA_CLOSED',
       'new_QM_calls':0,'sample_unique_records':50,'actual_task_calls_read':1200,'actual_worker_pids':pids,
       'source_replay_report':BASE.ref(replay/'report.json'),'source_budget':BASE.ref(a.budget),
       'source_previous_overlay_NOT_PASS_preserved':BASE.ref(a.previous_overlay),
       'source_footer_case':BASE.ref(ROOT/'reports/HB_delta_footer_case_v1.json'),
       'source_tasks':BASE.ref(a.tasks),'source_registry':BASE.ref(a.registry),
       'measurements':measurements,'family_projections':projection,'permanent_increment_bytes':permanent,
       'positive_logical_payload_bytes_per_task_row_by_calc':payload_by_calc,
       'uncompressed_logical_payload_increment_bytes':logical_payload_increment,
       'measured_page_rowgroup_file_increment_bytes':rowgroup_file_increment,
       'temporary_stage_increment_bytes':stage,'output_archive_increment_bytes':0,'canonical_increment_bytes':0,
       'pending_additional_bytes':0,'total_increment_bytes':delta,
       'old_writeback_peak_bytes':budget['writeback_peak_bytes'],'new_writeback_peak_bytes':peak,
       'fresh_quota_remaining_bytes':free,'headroom_bytes':head,'quota_source':quota_source,
       'required_headroom_bytes':200_000_000_000,'storage_capacity_estimate_pass':head>=2e11,
       'production_G3_G6_PASS_not_inferred':True,
       'method':'True fixed4096-byte statistics threshold: same record source JSON4111->4074 activates two4074-byte min/max strings in page and footer. Paired current-schema ParquetWriter writes actual128 rows per write_table,1 and2 rowgroups. Each individual genuine same50 task row is repeated128/256 solely for writer geometry, not new scientific samples; this preserves worst4096-byte statistics threshold instead of masking it with mixed rows. All compressed column page growth plus rowgroup/footer growth charged together per actual rowgroup count, not per record. Positive measured file intercept and six cleanup jobs timesfive group tail allowance retained. Stage13.312648270GB unchanged. Positive actual new f64 and JSON payload is additionally charged uncompressed for every formal task row, so repeated-value/dictionary compression is not treated as population savings. No negative family savings credited, production/data/precision/raw policy unchanged.',
       'source_sha256':BASE.sha(__file__)}
    out=Path(a.output)
    if not out.is_absolute() or not out.is_relative_to(ROOT) or out.exists():raise ValueError('New immutable own output required')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(output,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'path':str(out),'permanent_delta_GB_decimal':permanent/1e9,'stage_delta_GB_decimal':stage/1e9,'headroom_GB_decimal':head/1e9,'capacity_estimate_pass':head>=2e11}))
if __name__=='__main__':main()
