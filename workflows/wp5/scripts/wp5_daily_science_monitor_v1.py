"""Read-only Step5 SCI monitor: queue snapshot, short lane reads, no raw/LMDB/QM."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,math,multiprocessing,os,pickle,socket,sqlite3,time
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
QC_KEYS=('Q01_gradient_norm_kcal_mol_A','Q02_delta_HOF_kcal_mol','Q02_abs_delta_HOF_kcal_mol','cation_S2_minus_0p75','anion_S2_minus_0p75')
THREADS={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
os.environ.update(THREADS)

def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def readonly(path):
    db=sqlite3.connect('file:'+quote(str(Path(path).absolute()))+'?mode=ro',uri=True,timeout=2,isolation_level=None)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA busy_timeout=2000');return db

def distribution(values,denominator=None):
    import numpy as np
    valid=[float(x) for x in values if finite(x)];a=np.asarray(valid,dtype=np.float64)
    result={'finite_count':len(valid),'observed_count':len(values),'NULL_or_nonfinite_count':len(values)-len(valid),
            'snapshot_denominator':denominator,'snapshot_unread_count':max(0,(denominator or len(values))-len(values)),
            'min':None,'p50':None,'p90':None,'p95':None,'p99':None,'max':None,'mean':None}
    if valid:
        q=np.quantile(a,[.5,.9,.95,.99],method='linear')
        result.update(min=float(a.min()),max=float(a.max()),mean=float(a.mean()),p50=float(q[0]),p90=float(q[1]),p95=float(q[2]),p99=float(q[3]))
    return result

def snapshot(queue):
    db=readonly(queue);started=time.time()
    try:
        db.execute('BEGIN')
        meta=dict(db.execute('SELECT key,value FROM meta'))
        states=[dict(r) for r in db.execute('SELECT state,count(*) molecules,sum(record_count) records FROM molecules GROUP BY state')]
        durable_states=[dict(r) for r in db.execute('SELECT state,count(*) molecules,sum(record_count) records FROM molecules WHERE receipt_json IS NOT NULL AND completion_rank IS NOT NULL GROUP BY state')]
        denominators=[dict(r) for r in db.execute("SELECT j.key calc_type,sum(json_extract(j.value,'$.success')) success,sum(json_extract(j.value,'$.total')) total FROM molecules m,json_each(m.counts_json) j WHERE receipt_json IS NOT NULL AND completion_rank IS NOT NULL GROUP BY j.key")]
        rows=[dict(r) for r in db.execute("SELECT m.molecule_id,m.task_id,t.node,m.state,m.record_count,m.attempt,m.predicted_seconds,m.completion_rank,m.receipt_json FROM molecules m JOIN tasks t USING(task_id) WHERE receipt_json IS NOT NULL AND completion_rank IS NOT NULL ORDER BY completion_rank")]
        db.execute('COMMIT')
    finally:db.close()
    targets={};timing={};errors=[]
    for row in rows:
        receipt=json.loads(row.pop('receipt_json'));ctx=receipt.get('context',{});execution=ctx.get('execution_id')
        path=receipt.get('archive_path');start,end=receipt.get('molecule_started_epoch'),receipt.get('completed_epoch')
        actual=end-start if finite(start) and finite(end) and end>=start else None
        key=(str(row['task_id']),row['node']);g=timing.setdefault(key,{'task_id':key[0],'node':key[1],'molecules':0,'records':0,'actual_end_to_end_wall_seconds':0.,'predicted_allocated_seconds':0.,'paired_molecules':0,'missing_wall_or_prediction':0})
        g['molecules']+=1;g['records']+=row['record_count']
        if finite(actual) and finite(row['predicted_seconds']):
            g['actual_end_to_end_wall_seconds']+=actual;g['predicted_allocated_seconds']+=row['predicted_seconds'];g['paired_molecules']+=1
        else:g['missing_wall_or_prediction']+=1
        if not path or not execution:
            errors.append({'molecule_id':row['molecule_id'],'reason':'DURABLE_RECEIPT_ARCHIVE_OR_EXECUTION_MISSING'});continue
        target={**row,'execution_id':execution,'receipt_attempt_id':ctx.get('attempt_id'),'actual_wall_seconds':actual}
        targets.setdefault(path,[]).append(target)
    for item in timing.values():
        item['actual_to_predicted_ratio']=item['actual_end_to_end_wall_seconds']/item['predicted_allocated_seconds'] if item['predicted_allocated_seconds'] else None
    return {'queue_path':str(queue),'queue_bytes_at_snapshot':Path(queue).stat().st_size,'start_epoch':started,'snapshot_epoch':time.time(),
            'snapshot_max_completion_rank':max((r['completion_rank'] for r in rows),default=0),'meta':meta,'all_queue_states':states,
            'durable_receipt_states':durable_states,'durable_molecules':len(rows),'durable_records':sum(r['record_count'] for r in rows),
            'task_success_denominators':denominators,'whole_molecule_timing_by_formal_task':list(timing.values()),
            'timing_definition':'Measured per-completed-molecule end-to-end wall vs frozen queue planned_allocated_seconds for the SAME snapshot cohort. Per-calculation prediction is unavailable.',
            'snapshot_errors':errors},targets

_W={}
def worker_init(dictionaries,barrier):
    import wp5_archive_v5 as archive
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    _W.update(dicts=archive.load_dictionaries(dictionaries),codec=archive.Zstd())
    if barrier is not None:barrier.wait(timeout=180)

def scan_lane(argument):
    path,targets=argument;path=Path(path);pid=os.getpid();qc={k:[] for k in QC_KEYS};elapsed={k:[] for k in CALCS}
    statuses=collections.Counter();failures=collections.Counter();reasons=collections.Counter();seen=set();records=0;missing=[];errors=[]
    expected={r['molecule_id']:r for r in targets}
    if not path.is_relative_to(ROOT) or not path.exists():
        return {'path':str(path),'worker_pid':pid,'molecules':0,'records':0,'task_statuses':[],'failures':[],'failure_reasons':[],
                'qc':qc,'elapsed':elapsed,'missing':[{'molecule_id':r['molecule_id'],'records':r['record_count'],'reason':'ACTIVE_LANE_PATH_RETIRED_OR_UNAVAILABLE'} for r in targets],'errors':[]}
    if path.name=='raw_archive.sqlite':
        return {'path':str(path),'worker_pid':pid,'molecules':0,'records':0,'task_statuses':[],'failures':[],'failure_reasons':[],
                'qc':qc,'elapsed':elapsed,'missing':[{'molecule_id':r['molecule_id'],'records':r['record_count'],'reason':'SCI_STAGE_ALREADY_RETIRED_TO_PERMANENT_PARQUET'} for r in targets],'errors':[]}
    db=None
    try:
        db=readonly(path)
        if 'parsed_molecules' not in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            raise ValueError('SCI_STAGING_TABLE_UNAVAILABLE')
        ids=list(expected)
        for begin in range(0,len(ids),16):
            selected=ids[begin:begin+16]
            # Autocommit SELECT/fetchall releases the read lock BEFORE decompression.
            frames=db.execute('SELECT molecule_id,record_count,wire_sha256,uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules WHERE molecule_id IN ('+','.join('?' for _ in selected)+')',selected).fetchall()
            for row in frames:
                mid=row['molecule_id'];target=expected[mid]
                try:
                    d=_W['dicts']['pm7_B']
                    if row['dict_id']!=d['dict_id']:raise ValueError('SCI_DICTIONARY_ID_DIFFERS')
                    wire=_W['codec'].decompress(row['wire_frame'],d['data'],row['uncompressed_bytes'])
                    if hashlib.sha256(wire).hexdigest()!=row['wire_sha256']:raise ValueError('SCI_WIRE_SHA_DIFFERS')
                    payload=pickle.loads(wire);del wire
                    if payload['context']['execution_id']!=target['execution_id']:raise ValueError('SCI_EXECUTION_CHANGED_AFTER_SNAPSHOT')
                    results=payload['result']['record_results']
                    if row['record_count']!=target['record_count'] or len(results)!=target['record_count']:raise ValueError('SCI_RECORD_COUNT_DIFFERS')
                    local_qc={k:[] for k in QC_KEYS};local_elapsed={k:[] for k in CALCS};local_status=collections.Counter();local_fail=collections.Counter();local_reason=collections.Counter()
                    import wp5_runner_v10 as runner
                    for record in results:
                        tasks={t['task']:t for t in record['tasks']}
                        if set(tasks)!=set(CALCS) or len(record['tasks'])!=12:raise ValueError('SCI_TWELVE_OUTCOMES_NOT_CLOSED')
                        item=runner.family_row(record,payload['context'],'QC',[])[0]
                        for key in QC_KEYS:
                            v=abs(item['Q02_delta_HOF_kcal_mol']) if key=='Q02_abs_delta_HOF_kcal_mol' and finite(item['Q02_delta_HOF_kcal_mol']) else item.get(key)
                            local_qc[key].append(v)
                        for calc,detail in tasks.items():
                            status=detail.get('scope_status',detail.get('status'));local_status[(calc,status)]+=1
                            local_elapsed[calc].append(detail.get('elapsed_seconds'))
                            if status!='SUCCESS':
                                code=detail.get('failure_code') or 'UNSPECIFIED';source=detail.get('source_status',status);rc=detail.get('returncode',detail.get('return_code'))
                                local_fail[(calc,status,source,code,str(rc))]+=1
                                reason=str(detail.get('failure_reason') or '')[:500]
                                if reason:local_reason[(calc,code,reason)]+=1
                    for key in QC_KEYS:qc[key].extend(local_qc[key])
                    for calc in CALCS:elapsed[calc].extend(local_elapsed[calc])
                    statuses.update(local_status);failures.update(local_fail);reasons.update(local_reason);seen.add(mid);records+=len(results)
                    del payload,results
                except Exception as exc:errors.append({'molecule_id':mid,'records':target['record_count'],'reason':type(exc).__name__+': '+str(exc)})
            del frames
        for mid in expected.keys()-seen:
            if not any(e['molecule_id']==mid for e in errors):missing.append({'molecule_id':mid,'records':expected[mid]['record_count'],'reason':'SCI_STAGE_RETIRED_OR_CHANGED_AFTER_QUEUE_SNAPSHOT'})
    except Exception as exc:
        errors.append({'path':str(path),'reason':type(exc).__name__+': '+str(exc)})
    finally:
        if db is not None:db.close()
    return {'path':str(path),'worker_pid':pid,'molecules':len(seen),'records':records,'qc':qc,'elapsed':elapsed,
            'task_statuses':[{'calc_type':k[0],'status':k[1],'count':v} for k,v in statuses.items()],
            'failures':[{'calc_type':k[0],'status':k[1],'source_status':k[2],'failure_code':k[3],'returncode':k[4],'count':v} for k,v in failures.items()],
            'failure_reasons':[{'calc_type':k[0],'failure_code':k[1],'reason':k[2],'count':v} for k,v in reasons.items()],
            'missing':missing,'errors':errors}

def pilot_reference(baseline_path):
    if not baseline_path or not Path(baseline_path).is_file():return {'status':'PILOT_BASELINE_UNAVAILABLE'}
    baseline=json.loads(Path(baseline_path).read_text());report_path=Path(baseline['source_path'])
    result={'baseline_path':str(baseline_path),'baseline_sha256':sha(baseline_path),'panel_records':baseline.get('panel_records'),
            'panel_molecules':baseline.get('panel_molecules'),'success_rates':baseline.get('success_rates',{}),
            'report_path':str(report_path),'report_expected_sha256':baseline.get('source_sha256'),'QC':{},
            'comparison_scope':'Closed balanced pilot panel vs current completed prefix; no population reweighting or QC-based deletion.'}
    if not report_path.is_file():result['status']='PILOT_QC_REPORT_UNAVAILABLE';return result
    actual=sha(report_path);result['report_actual_sha256']=actual
    if actual!=baseline.get('source_sha256'):result['status']='PILOT_REPORT_BINDING_DIFFERS';return result
    report=json.loads(report_path.read_text());obs=report.get('observations',{})
    names={'Q01_gradient_norm_kcal_mol_A':'Q01_gradient_norm_kcal_mol_A','Q02_delta_HOF_kcal_mol':'Q02_HOF_difference_kcal_mol','Q02_abs_delta_HOF_kcal_mol':'Q02_absolute_HOF_difference_kcal_mol'}
    for current,old in names.items():result['QC'][current]=obs.get(old,{'status':'PILOT_FIELD_NOT_REPORTED'})
    for calc,key in (('pm7_cation','cation_S2_minus_0p75'),('pm7_anion','anion_S2_minus_0p75')):
        source=obs.get('ions',{}).get(calc,{}).get('spin_S2')
        if source is None:result['QC'][key]={'status':'PILOT_SPIN_S2_NOT_REPORTED'};continue
        shifted=dict(source)
        for name,value in source.items():
            if name in {'min','max','mean','median'} or (name.startswith('p') and name[1:].isdigit()):
                if finite(value):shifted[name]=value-.75
        shifted['derived_from']='Pilot ion spin_S2 minus fixed doublet .75; counts/std unchanged.';result['QC'][key]=shifted
    result['status']='PILOT_BASELINE_AND_EXISTING_QC_REPORT_READ';return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queue',type=Path,default=ROOT/'queue/pending.sqlite')
    ap.add_argument('--dictionaries',type=Path,default=ROOT/'dictionaries/job_4513894/dictionary_manifest.json')
    ap.add_argument('--baseline',type=Path,default=ROOT/'configs/pilot_success_baseline.json')
    ap.add_argument('--workers',type=int,default=24);ap.add_argument('--out',type=Path);ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());d=distribution([1.,2.,None])
        assert d['finite_count']==2 and d['NULL_or_nonfinite_count']==1 and d['p50']==1.5
        print('READONLY_SCI_MONITOR_AST_AND_QUANTILE_FIXTURE_PASS_NO_DATA_NO_QM');return
    if socket.gethostname().split('.')[0]!='compute-0-20' or args.workers<16:raise ValueError('Read-only full SCI statistics requires compute-0-20 and >=16 independent workers')
    for path in (args.queue,args.dictionaries):
        if not path.absolute().is_relative_to(ROOT):raise ValueError('Only current WP5 SCI queue/dictionaries')
    began=time.time();out=args.out or ROOT/'reports'/('formal_daily_science_'+time.strftime('%Y%m%dT%H%M%S',time.gmtime()))
    if not out.absolute().is_relative_to(ROOT):raise ValueError('Reports only inside current WP5 root')
    out.mkdir(parents=True,exist_ok=False)
    current,targets=snapshot(args.queue);qc={k:[] for k in QC_KEYS};elapsed={k:[] for k in CALCS}
    status=collections.Counter();failure=collections.Counter();reason=collections.Counter();missing=[];errors=[];lanes=[];pids=set();read_molecules=read_records=0
    if targets:
        context=multiprocessing.get_context('spawn');barrier=context.Barrier(args.workers) if len(targets)>=args.workers else None
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=worker_init,initargs=(str(args.dictionaries),barrier)) as pool:
            for item in pool.map(scan_lane,list(targets.items()),chunksize=1):
                pids.add(item['worker_pid']);read_molecules+=item['molecules'];read_records+=item['records']
                for key in QC_KEYS:qc[key].extend(item['qc'][key])
                for calc in CALCS:elapsed[calc].extend(item['elapsed'][calc])
                for row in item['task_statuses']:status[(row['calc_type'],row['status'])]+=row['count']
                for row in item['failures']:failure[(row['calc_type'],row['status'],row['source_status'],row['failure_code'],row['returncode'])]+=row['count']
                for row in item['failure_reasons']:reason[(row['calc_type'],row['failure_code'],row['reason'])]+=row['count']
                missing.extend(item['missing']);errors.extend(item['errors']);lanes.append({'path':item['path'],'worker_pid':item['worker_pid'],'molecules':item['molecules'],'records':item['records'],'missing_molecules':len(item['missing']),'errors':len(item['errors'])})
    pilot=pilot_reference(args.baseline);full=current['durable_records'];tasks=[]
    for row in current['task_success_denominators']:
        calc=row['calc_type'];rate=row['success']/row['total'] if row['total'] else None;ref=pilot.get('success_rates',{}).get(calc)
        tasks.append({**row,'success_rate':rate,'pilot_success_rate':ref,'difference_percentage_points':100*(rate-ref) if rate is not None and ref is not None else None,
          'detailed_stage_statuses':{name:count for (task,name),count in status.items() if task==calc},
          'actual_elapsed_seconds':distribution(elapsed[calc],full),'actual_elapsed_seconds_sum':sum(x for x in elapsed[calc] if finite(x)),
          'predicted_elapsed_seconds':None,'prediction_missing_reason':'Frozen producer supplies whole-molecule planned_allocated_seconds; per-calculation predicted_seconds is explicitly NULL.'})
    counts={r['state']:r for r in current['all_queue_states']};all_mols=sum(r['molecules'] for r in current['all_queue_states']);all_records=sum(r['records'] for r in current['all_queue_states'])
    population_closed=all_mols==int(current['meta']['population_molecules']) and all_records==int(current['meta']['population_records'])
    slot_closed=sum(r['total'] for r in current['task_success_denominators'])==12*full
    coverage_closed=read_molecules==current['durable_molecules'] and read_records==full and not errors and not current['snapshot_errors']
    report={'schema':'WP5_STEP5_READONLY_SCI_DAILY_V1','status':'FULL_SNAPSHOT_SCI_STATISTICS' if coverage_closed else 'QUEUE_FULL_DETAILED_SCI_COVERAGE_INCOMPLETE',
      'start_epoch':began,'end_epoch':time.time(),'elapsed_seconds':time.time()-began,'node':socket.gethostname(),'monitor_pid':os.getpid(),
      'workers_requested':args.workers,'actual_worker_pids':sorted(pids),'thread_limit':THREADS,'snapshot':current,
      'population_count_closed':population_closed,'durable_12task_count_closed':slot_closed,
      'COMPLETE_state':counts.get('COMPLETE',{'molecules':0,'records':0}),
      'durable_receipt_in_nonCOMPLETE_states':[r for r in current['durable_receipt_states'] if r['state']!='COMPLETE'],
      'denominator_definition':'Queue COMPLETE counts differ from latest durable receipt counts if a full first attempt awaits one cleanup retry. Task success denominators include every snapshot durable receipt exactly once.',
      'detailed_SCI_coverage':{'snapshot_durable_molecules':current['durable_molecules'],'snapshot_durable_records':full,'read_molecules':read_molecules,'read_records':read_records,
        'unread_molecules':current['durable_molecules']-read_molecules,'unread_records':full-read_records,'all_snapshot_durable_SCI_covered':coverage_closed,
        'source_scope':'Only queue and available active lane parsed_molecules SCI blobs, same completion execution. Retired/unavailable stage is disclosed, never sampled or replaced with raw.',
        'missing':missing,'errors':errors,'lanes':lanes},
      'task_statistics':tasks,
      'failure_types':[{'calc_type':k[0],'status':k[1],'source_status':k[2],'failure_code':k[3],'returncode':k[4],'cases':v} for k,v in sorted(failure.items())],
      'failure_reason_counts':[{'calc_type':k[0],'failure_code':k[1],'reason':k[2],'cases':v} for k,v in reason.most_common()],
      'QC':{key:{'formal':distribution(values,full),'pilot':pilot.get('QC',{}).get(key,{'status':'PILOT_FIELD_UNAVAILABLE'})} for key,values in qc.items()},
      'pilot_reference':pilot,'bindings':{'source_path':str(Path(__file__)),'source_sha256':sha(__file__),'dictionary_manifest_sha256':sha(args.dictionaries)},
      'raw_tables_read':False,'original_LMDB_read':False,'QM_started':False,'production_queue_or_sources_modified':False,'stop_flags_written':False}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    lines=['# WP5 Step5 SCI只读日报','',f"状态：{report['status']}；队列人口闭合：{population_closed}；完整receipt×12计数闭合：{slot_closed}。",
      f"COMPLETE：{report['COMPLETE_state']['molecules']} 分子/{report['COMPLETE_state']['records']} 记录；持久SCI receipt：{current['durable_molecules']} 分子/{full} 记录。",
      f"非COMPLETE但已有完整receipt：{json.dumps(report['durable_receipt_in_nonCOMPLETE_states'],ensure_ascii=False)}。",
      f"本次详细SCI覆盖：{read_molecules} 分子/{read_records} 记录；未读取：{full-read_records} 记录，范围和原因见JSON。",
      '', '| 任务 | 成功/分母 | pilot成功率 | actual elapsed p50/p99(s) |','|---|---:|---:|---:|']
    for row in tasks:lines.append(f"| {row['calc_type']} | {row['success']}/{row['total']} | {row['pilot_success_rate']} | {row['actual_elapsed_seconds']['p50']}/{row['actual_elapsed_seconds']['p99']} |")
    lines+=['','逐计算任务预测耗时没有冻结数据，明确NULL；wholeMol同cohort wall/冻结planned_allocated秒对照见JSON。',
      '','| QC | 本轮finite/已读 | p50/p90/p99 | pilot p50/p90/p99 |','|---|---:|---|---|']
    for key,row in report['QC'].items():
        a,b=row['formal'],row['pilot'];lines.append(f"| {key} | {a['finite_count']}/{a['observed_count']} | {a['p50']}/{a['p90']}/{a['p99']} | {b.get('p50')}/{b.get('p90')}/{b.get('p99')} |")
    lines+=['',f"失败类型和具体原因：{sum(failure.values())} 个已读SCI槽，见JSON；全队列失败分母来自counts_json，与详细stage未读范围分开。",'','未读取原始LMDB、raw文件或容器records表；未运行QM、修改生产源/队列或写STOP。']
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'report':str(out/'report.json'),'status':report['status'],'read_records':read_records,'snapshot_records':full,'actual_workers':len(pids)}))
if __name__=='__main__':main()
