"""Read-only four-phase cost observation, actual latest R12 jobs and one queue."""
import argparse, collections, datetime, hashlib, json, os, pathlib, sqlite3, time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')

def read(p): return json.loads(p.read_text())
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.'+str(os.getpid())+'.pending')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,p)

def submission(path):
    if not path.is_file():
        return set(),{'path':str(path),'present':False,'status':'SUBMISSION_MANIFEST_NOT_YET_PRESENT'}
    raw=path.read_bytes();obj=json.loads(raw)
    ids={str(x['job_id']) for x in obj.get('main',[])+obj.get('cleanup',[]) if x.get('job_id') is not None}
    return ids,{'path':str(path),'present':True,'sha256':hashlib.sha256(raw).hexdigest(),
               'manifest_status':obj.get('status'),'actual_job_count':len(ids)}


SUBMISSIONS=(ROOT/'submission/submitted_jobs.json',
             ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',
             ROOT/'submission/startup_replacement_v1/submitted_jobs.json',
             ROOT/'submission/recovery_attempt_v12/submitted_jobs.json')
STARTUP_FINAL_STATUS='ALL_69_MAIN_4_CLEANUP_AND_2_DEPENDENCY_UPDATES_COMPLETE'

def effective_jobs(paths=SUBMISSIONS):
    objects=[read(p) if p.is_file() else {} for p in paths]
    if len(objects)!=4:raise ValueError('FOUR_ACTUAL_SUBMISSION_PATHS_REQUIRED')
    original,recovery,startup,r12=objects
    cost_ids={str(row['job_id']) for obj in objects for key in ('main','cleanup')
              for row in obj.get(key,[]) if row.get('job_id') is not None}
    mains={str(row['task_id']):row for row in r12.get('main',[]) if row.get('job_id') is not None}
    cleanup={row['node']:row for row in r12.get('cleanup',[]) if row.get('job_id') is not None}
    current={str(row['job_id']) for row in list(mains.values())+list(cleanup.values())}
    expected_tasks={str(row['task_id']):row['node'] for row in original.get('main',[])}
    expected_nodes={row['node'] for row in original.get('cleanup',[])}
    unresolved=[]
    if r12 and {task:row.get('node') for task,row in mains.items()}!=expected_tasks:
        unresolved.append({'reason':'ACTUAL_R12_TASK_NODE_MANIFEST_NOT_YET_CLOSED'})
    ready=(r12.get('status')=='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED'
           and r12.get('prepared_plan',{}).get('version')==12
           and len(r12.get('main',[]))==72 and len(mains)==72 and len(expected_tasks)==72
           and {task:row.get('node') for task,row in mains.items()}==expected_tasks
           and len(r12.get('cleanup',[]))==6 and len(cleanup)==6 and set(cleanup)==expected_nodes
           and len(current)==78 and len(cost_ids)==307)
    return {'ready':ready,'r12_manifest_status':r12.get('status'),
        'waiting_reason':None if ready else ('WAITING_FOR_R12_FORMAL_SUBMISSION' if not r12 else 'WAITING_FOR_R12_ACTUAL72_PLUS6_MANIFEST_CLOSURE'),
        'effective_job_ids':sorted(current,key=int),'effective_main':mains,'effective_cleanup':cleanup,
        'actual_cost_job_ids':sorted(cost_ids,key=int),'superseded_historical_job_ids':sorted(cost_ids-current,key=int),
        'unresolved_actual_job_references':unresolved,
        'termination_scope':'Actual_R12_72logicalmains_and6cleanup_from_fourth_receipt',
        'cost_scope':'Union_of_actualIDs_from_all4submissions_once_no_fake_futureIDs'}

def accounting(pub,ids):
    rows={};duplicates=collections.Counter();conflicts=[]
    for line in pub.get('sacct',{}).get('stdout','').splitlines():
        f=[value.strip() for value in line.split('|')]
        if len(f)<8 or f[0] not in ids or f[2]!='zixiao':continue
        try:cores=int(f[5]);seconds=int(f[6])
        except ValueError:continue
        if cores<0 or seconds<0:continue
        item={'job_id':f[0],'allocated_cpus':cores,'elapsed_seconds':seconds,
              'allocated_core_hours':cores*seconds/3600}
        duplicates[f[0]]+=1
        if f[0] in rows and rows[f[0]]!=item:conflicts.append(f[0])
        rows[f[0]]=item
    return rows,{'duplicate_accounting_job_ids':sorted(k for k,v in duplicates.items() if v>1),
                 'different_duplicate_accounting_job_ids':sorted(set(conflicts)),
                 'duplicate_rule':'One top-level record per actual JobID; last valid publisher row wins. Job steps are excluded.'}

def phase(name,ids,manifest,pub,ledger):
    states={k:v for k,v in pub.get('registered_job_states',{}).items() if k in ids}
    known={k:v for k,v in ledger.items() if k in ids}
    return {'phase':name,'submission':manifest,'actual_job_ids':sorted(ids,key=int),
        'state_counts':dict(collections.Counter(states.values())),'states_by_job_id':states,
        'observed_job_count':len(states),'unobserved_job_ids':sorted(ids-set(states),key=int),
        'actual_allocated_core_hours_known_sum':sum(x['allocated_core_hours'] for x in known.values()) if known else None,
        'accounting_complete':bool(ids) and set(known)==ids,'accounting_missing_job_ids':sorted(ids-set(known),key=int),
        'scheduler_stop_states':{k:v for k,v in states.items() if v.startswith(('OUT_OF_MEMORY','TIMEOUT','NODE_FAIL'))}}

def show(value,decimals=3):
    return '未知' if value is None else f'{value:.{decimals}f}'

def node_peak(runtime,node,key):
    values=[]
    for entry in runtime:
        if entry.get('node')!=node:continue
        for name in ('checkpoint.json','completion.json'):
            value=entry.get(name,{}).get('resource_peaks',{}).get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool):values.append(value)
    return max(values)/1e9 if values else None

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hour',type=int)
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--historical-submission',type=pathlib.Path,default=ROOT/'submission/submitted_jobs.json')
    ap.add_argument('--current-submission',type=pathlib.Path,default=ROOT/'submission/recovery_attempt_v11/submitted_jobs.json')
    ap.add_argument('--startup-submission',type=pathlib.Path,default=ROOT/'submission/startup_replacement_v1/submitted_jobs.json')
    ap.add_argument('--r12-submission',type=pathlib.Path,default=ROOT/'submission/recovery_attempt_v12/submitted_jobs.json')
    ap.add_argument('--write-latest',action='store_true',help='Also publish the read-only observation as wp5_daily_latest.md')
    a=ap.parse_args()
    if a.check:
        import ast
        ast.parse(pathlib.Path(__file__).read_text());print('OBSERVER4_AST_PASS_NO_QUEUE_NO_OBSERVATION');return
    if a.hour is None:ap.error('--hour required for actual observation')
    assert os.uname().nodename=='compute-0-20'
    prefix='formal_hour%d'%a.hour
    historical_ids,historical_manifest=submission(a.historical_submission)
    current_ids,current_manifest=submission(a.current_submission)
    recovery_ids=current_ids;recovery_manifest=current_manifest
    startup_ids,startup_manifest=submission(a.startup_submission)
    r12_ids,r12_manifest=submission(a.r12_submission)
    selection=effective_jobs((a.historical_submission,a.current_submission,a.startup_submission,a.r12_submission))
    if not selection['ready']:
        waiting={'schema':'WP5_FOUR_PHASE_EFFECTIVE_HOURLY_OBSERVATION_V4',
            'status':selection['waiting_reason'],'time':time.time(),'effective_selection':selection,
            'actual_unique_job_ids':selection['actual_cost_job_ids'],'actual_unique_job_count':len(selection['actual_cost_job_ids']),
            'r12_submission':r12_manifest,'effective_job_count':len(selection['effective_job_ids']),
            'population_scope':'ONE_EXISTING_SHARED_QUEUE_NOT_SUMMED_ACROSS_PHASES',
            'queue_read_in_this_waiting_call':False,'queue_written':False,'Slurm_submitted':False}
        write(ROOT/'reports'/(prefix+'_root_observation_v4.json'),waiting)
        print(json.dumps(waiting,ensure_ascii=False));return
    ids=set(selection['actual_cost_job_ids']);current_ids=set(selection['effective_job_ids'])
    current_manifest={'present':r12_manifest['present'],'effective_selection_ready':selection['ready'],'r12_submission':r12_manifest}
    pub=read(ROOT/'reports/observation_latest.json')
    ledger,ledger_notes=accounting(pub,ids)
    history=phase('historical_original_submission',historical_ids,historical_manifest,pub,ledger)
    recovery_phase=phase('recovery_submission_cost_ledger',recovery_ids,recovery_manifest,pub,ledger)
    startup_phase=phase('startup_replacement_submission_cost_ledger',startup_ids,startup_manifest,pub,ledger)
    r12_phase=phase('r12_recovery_submission_cost_ledger',r12_ids,r12_manifest,pub,ledger)
    current=phase('current_effective_72main_6cleanup',current_ids,current_manifest,pub,ledger)
    core=sum(item['allocated_core_hours'] for item in ledger.values()) if ledger else None
    stop=ROOT/'STOP_NEW_MOLECULES.json'
    obs={'schema':'WP5_FOUR_PHASE_EFFECTIVE_HOURLY_OBSERVATION_V4','time':time.time(),
         'publisher_age_seconds':time.time()-pub['time'],'historical_phase':history,'recovery_submission_phase':recovery_phase,'startup_submission_phase':startup_phase,'r12_submission_phase':r12_phase,'current_phase':current,
         'effective_selection':selection,
         'actual_unique_job_ids':sorted(ids,key=int),'actual_unique_job_count':len(ids),
         'job_ids_shared_between_manifests':sorted((historical_ids&recovery_ids)|(historical_ids&startup_ids)|(recovery_ids&startup_ids)|(r12_ids&(historical_ids|recovery_ids|startup_ids)),key=int),
         'formal_states':current['state_counts'],'formal_actual_allocated_core_hours':core,
         'cumulative_actual_allocated_core_hours_known_sum':core,
         'cumulative_accounting_complete':bool(ids) and set(ledger)==ids,
         'cumulative_accounting_missing_job_ids':sorted(ids-set(ledger),key=int),
         'accounting_by_actual_job_id':ledger,'accounting_notes':ledger_notes,'quota':pub['quota_parsed'],
         'stop':read(stop) if stop.is_file() else None,
         'inventory_state':pub.get('registered_job_states',{}).get('4513887'),
         'formal_job_count_observed':current['observed_job_count'],
         'scheduler_stop_states_current':current['scheduler_stop_states'],
         'scheduler_stop_states_historical':history['scheduler_stop_states'],
         'original_data_written':False,'queue_written':False,'LMDB_opened':False}
    write(ROOT/'reports'/(prefix+'_root_observation_v4.json'),obs)
    con=sqlite3.connect('file:'+str(ROOT/'queue/pending.sqlite')+'?mode=ro',uri=True,timeout=60)
    con.row_factory=sqlite3.Row
    try:
        con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
        meta=dict(con.execute('SELECT key,value FROM meta'))
        counts=[dict(x) for x in con.execute('SELECT t.node,m.file_group,m.state,count(*) molecules,sum(m.record_count) records FROM molecules m JOIN tasks t ON m.task_id=t.task_id GROUP BY t.node,m.file_group,m.state')]
        durable=[dict(x) for x in con.execute('SELECT state,count(*) molecules,sum(record_count) records FROM molecules WHERE counts_json IS NOT NULL GROUP BY state')]
        rates=[dict(x) for x in con.execute("SELECT j.key calc_type,sum(json_extract(j.value,'$.success')) success,sum(json_extract(j.value,'$.total')) total FROM molecules m,json_each(m.counts_json) j WHERE m.counts_json IS NOT NULL GROUP BY j.key")]
    finally:
        con.rollback();con.close()
    runtime_current=[];runtime_historical=[];errors_current=[];errors_historical=[]
    for p in sorted((ROOT/'runtime').glob('task_*/job_*/run.json')):
        job_id=p.parent.name.split('_')[1]
        if job_id not in ids:continue
        r=read(p);is_current=job_id in current_ids
        entry={'job_id':job_id,'node':r.get('node'),'run_root':str(p.parent),
               'phase':'current_effective_logical_job' if is_current else ('historical_recovery_startup_attempt' if job_id in recovery_ids|startup_ids else 'historical_original_submission')}
        for name in ('checkpoint.json','completion.json','worker_error.json','runtime_error.json','export_error.json'):
            f=p.parent/name
            if f.is_file():
                entry[name]=read(f)
                if 'error' in name:
                    (errors_current if is_current else errors_historical).append({'path':str(f),'job_id':job_id,'detail':entry[name]})
        (runtime_current if is_current else runtime_historical).append(entry)
    closed=sum(x['molecules'] for x in counts)==int(meta['population_molecules']) and sum(x['records'] for x in counts)==int(meta['population_records'])
    durable_records=sum(x['records'] for x in durable)
    rate_closed=len(rates)==12 and all(x['total']==durable_records for x in rates)
    first_sci=ROOT/'reports/formal_daily_science_first_v1/report.json'
    sci_history={'path':str(first_sci),'scope':'HISTORICAL_FIRST_COMPLETED_SCI_PREFIX_NOT_CURRENT_POPULATION',
                 'molecules':32825,'records':324662,'scientific_task_slots':3895944}
    snap={'time':time.time(),'status':'FORMAL_QUEUE_POPULATION_CLOSED' if closed and rate_closed else 'COUNT_DIFFERENCE',
          'population_scope':'ONE_EXISTING_SHARED_QUEUE_ALL_PHASES_NO_POPULATION_DOUBLE_COUNT',
          'queue_path':str(ROOT/'queue/pending.sqlite'),'meta':meta,'counts':counts,'durable_states':durable,
          'task_success_rates':rates,'runtime_current':runtime_current,'runtime_historical':runtime_historical,
          'errors_current':errors_current,'errors_historical':errors_historical,
          'population_closed':closed,'task_denominators_closed':rate_closed,'durable_records':durable_records,
          'historical_first_science_snapshot':sci_history,'queue_written':False}
    write(ROOT/'reports'/(prefix+'_queue_snapshot_v4.json'),snap)
    complete=[x for x in counts if x['state']=='COMPLETE'];retry=[x for x in counts if x['state']=='RETRY_PENDING']
    cm=sum(x['molecules'] for x in complete);cr=sum(x['records'] for x in complete)
    rm=sum(x['molecules'] for x in retry);rr=sum(x['records'] for x in retry)
    projection_ready=(cm>=int(meta['population_molecules'])*.1 and core is not None and obs['cumulative_accounting_complete'])
    projected=core*int(meta['population_molecules'])/cm if projection_ready else None
    obs.update(complete_molecules=cm,
        cumulative_allocated_core_hours_extrapolated_at10pct=projected,
        core_hours_projection_scope='All4actualsubmissionphases_including_superseded_startup_cost;one_queue_COMPLETEdenominator',
        core_hours_projection_status='AVAILABLE' if projection_ready else ('BELOW10PCT_COMPLETE' if cm<int(meta['population_molecules'])*.1 else 'ACCOUNTING_INCOMPLETE'),
        monitor_does_not_write_STOP=True)
    write(ROOT/'reports'/(prefix+'_root_observation_v4.json'),obs)
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    stamp=now.strftime('%Y-%m-%d %H:%M:%S')
    quota=obs['quota'].get('remaining_bytes')
    lines=['# WP5 每日汇报','',f'更新时间：{stamp}（北京时间），正式观察第{a.hour}小时。',
        f'当前有效72主+6收尾状态：{current["state_counts"]}；已观测{current["observed_job_count"]}/{len(current_ids)}个实际作业。',
        f'第一轮历史提交阶段状态：{history["state_counts"]}；已观测{history["observed_job_count"]}/{len(historical_ids)}个实际作业。',
        f'STOP：{obs["stop"]}；当前阶段已观测运行错误：{len(errors_current)}；历史阶段运行错误：{len(errors_historical)}。',
        f'同一队列当前COMPLETE：{cm:,}分子 / {cr:,}记录；RETRY_PENDING：{rm:,}分子 / {rr:,}记录。',
        f'人口计数闭合：{closed}；12任务分母闭合：{rate_closed}；人口按同一队列统计一次。',
        f'四轮实际JobID去重累计分配核时：{show(core)}；记账闭合：{obs["cumulative_accounting_complete"]}；缺记账ID：{obs["cumulative_accounting_missing_job_ids"]}。',
        f'当前有效作业分配核时：{show(current["actual_allocated_core_hours_known_sum"])}；历史分配核时：{show(history["actual_allocated_core_hours_known_sum"])}；当前配额余量：{show(quota/1e9 if quota is not None else None)} GB。',
        f'≥10% COMPLETE 时全阶段累计核时外推：{show(projected)} coreh；仅指标，不写STOP。',
        f'第二轮完整成本账本状态：{recovery_phase["state_counts"]}；第三轮新增73项状态：{startup_phase["state_counts"]}；第四轮R12实际状态：{r12_phase["state_counts"]}；有效清单ready：{selection["ready"]}。',
        f'已完成分子比例：{cm/int(meta["population_molecules"])*100:.3f}%。',
        '', '| 节点 | 同一队列COMPLETE分子 | COMPLETE记录 | 当前阶段RSS峰值GB | 当前阶段PSS峰值GB | 当前阶段scratch峰值GB |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    if not selection['ready']:lines.insert(3,'最新有效72主+6收尾实际清单尚未闭合；不以历史78作业终态判定完成。')
    for node in sorted({x['node'] for x in counts}):
        c=[x for x in complete if x['node']==node]
        pv=[show(node_peak(runtime_current,node,key)) for key in ('RSS_bytes','PSS_bytes','local_scratch_bytes')]
        lines.append(f'| {node} | {sum(x["molecules"] for x in c)} | {sum(x["records"] for x in c)} | {pv[0]} | {pv[1]} | {pv[2]} |')
    lines+=['','RSS重复计入共享页面；PSS按共享分摊。当前阶段峰值仅来自新实际作业，未观测值显示未知。','',
            '| 文件组 | 同一队列COMPLETE分子 | COMPLETE记录 |','| --- | ---: | ---: |']
    for group in sorted({x['file_group'] for x in counts}):
        c=[x for x in complete if x['file_group']==group]
        lines.append(f'| {group} | {sum(x["molecules"] for x in c)} | {sum(x["records"] for x in c)} |')
    lines+=['','| 任务 | 成功 / 队列当前已持久化尝试 | 成功率 |','| --- | ---: | ---: | ---: |']
    for x in rates:
        rate=100*x['success']/x['total'] if x['total'] else None
        lines.append(f'| {x["calc_type"]} | {x["success"]} / {x["total"]} | {show(rate,4)}% |')
    lines+=['','历史首次SCI快照：formal_daily_science_first_v1/report.json，32,825分子 / 324,662记录 / 3,895,944任务槽。这是历史完成前缀，不是当前人口总量或本次续算统计。',
        '历史首次前缀失败1,047槽：454性质缺项、592明确SCF/SCC失败、1次anion超时；历史wholeMol耗时691.069h / 同批冻结预测3026.842h=0.2283。此比值不是Slurm核时或当前全量完工预测。']
    if first_sci.is_file():
        sci=read(first_sci)
        lines+=['','| 历史首次前缀QC | 有效数 | p50 | p99 | 最大值 | 历史pilot p99 |','| --- | ---: | ---: | ---: | ---: | ---: |']
        for key,item in sci.get('QC',{}).items():
            v=item['formal'];pilot=item['pilot']
            lines.append(f'| {key} | {v.get("finite_count",v.get("n","见JSON"))} | {v.get("p50")} | {v.get("p99")} | {v.get("max")} | {pilot.get("p99")} |')
    lines+=['','历史首次前缀Q01与cation spin最大值高于pilot；保持原始人口。pilot为平衡面板，历史完成前缀比较不作重新加权。',
        '新保留策略预算：永久788.126 GB、未来float32预留400 GB、临时733.385 GB，峰值1921.511 GB；本轮保留float64，float32只预留。',
        '普通成功输出解析后本地删除；失败与固定约1%审计记录的完整输出归档，输入正文不归档。',
        '最终200条 / 2400任务同环境重算仍须在正式人口闭合后通过。本轮不创建LMDB。','']
    content='\n'.join(lines)
    names=[f'wp5_daily_{now:%Y%m%d}_hour{a.hour}_v4.md']
    if a.write_latest:names.append('wp5_daily_latest.md')
    for name in names:
        p=ROOT/'reports'/name;tmp=p.with_name(p.name+'.'+str(os.getpid())+'.pending')
        tmp.write_text(content);os.replace(tmp,p)
    print(json.dumps({'hour':a.hour,'complete_molecules':cm,'complete_records':cr,'retry_molecules':rm,
        'durable_records':durable_records,'population_closed':closed,'task_denominators_closed':rate_closed,
        'runtime_errors_current':len(errors_current),'runtime_errors_historical':len(errors_historical),
        'cumulative_actual_allocated_core_hours_known_sum':core,'current_phase':current,'historical_phase':history,
        'effective_selection_ready':selection['ready'],'effective_job_count':len(current_ids),
        'cumulative_allocated_core_hours_extrapolated_at10pct':projected,'core_hours_projection_status':obs['core_hours_projection_status'],
        'latest_daily_updated':a.write_latest,'minimum_success_rate':min((x['success']/x['total'] for x in rates if x['total']),default=None)},
        ensure_ascii=False))
if __name__=='__main__':main()

