"""Read-only formal population and scheduler observation; writes reports only."""
import argparse, collections, datetime, json, os, pathlib, sqlite3, time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def read(p): return json.loads(p.read_text())
def write(p,obj):
    tmp=p.with_name(p.name+'.pending')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,p)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--hour',required=True,type=int); a=ap.parse_args()
    assert os.uname().nodename=='compute-0-20'
    prefix='formal_hour%d'%a.hour
    sub=read(ROOT/'submission/submitted_jobs.json')
    ids={str(x['job_id']) for x in sub['main']+sub['cleanup']}
    pub=read(ROOT/'reports/observation_latest.json')
    states={k:v for k,v in pub['registered_job_states'].items() if k in ids}
    core=0.0
    for line in pub['sacct']['stdout'].splitlines():
        f=line.split('|')
        if len(f)>=8 and f[0] in ids and f[2]=='zixiao': core+=int(f[5])*int(f[6])/3600
    stop=ROOT/'STOP_NEW_MOLECULES.json'
    obs={'time':time.time(),'publisher_age_seconds':time.time()-pub['time'],
         'formal_states':dict(collections.Counter(states.values())),
         'formal_actual_allocated_core_hours':core,'quota':pub['quota_parsed'],
         'stop':read(stop) if stop.is_file() else None,
         'inventory_state':pub['registered_job_states'].get('4513887'),
         'formal_job_count_observed':len(states),
         'scheduler_stop_states':{k:v for k,v in states.items() if v.startswith(('OUT_OF_MEMORY','TIMEOUT','NODE_FAIL'))}}
    write(ROOT/'reports'/(prefix+'_root_observation_v1.json'),obs)
    con=sqlite3.connect('file:'+str(ROOT/'queue/pending.sqlite')+'?mode=ro',uri=True,timeout=60)
    con.row_factory=sqlite3.Row;con.execute('BEGIN')
    meta=dict(con.execute('SELECT key,value FROM meta'))
    counts=[dict(x) for x in con.execute('SELECT t.node,m.file_group,m.state,count(*) molecules,sum(m.record_count) records FROM molecules m JOIN tasks t ON m.task_id=t.task_id GROUP BY t.node,m.file_group,m.state')]
    durable=[dict(x) for x in con.execute('SELECT state,count(*) molecules,sum(record_count) records FROM molecules WHERE counts_json IS NOT NULL GROUP BY state')]
    rates=[dict(x) for x in con.execute("SELECT j.key calc_type,sum(json_extract(j.value,'$.success')) success,sum(json_extract(j.value,'$.total')) total FROM molecules m,json_each(m.counts_json) j WHERE m.counts_json IS NOT NULL GROUP BY j.key")]
    con.rollback();con.close()
    runtime=[];errors=[]
    for p in sorted((ROOT/'runtime').glob('task_*/job_*/run.json')):
        r=read(p)
        job_id=p.parent.name.split('_')[1]
        if job_id not in ids: continue
        entry={'job_id':job_id,'node':r.get('node'),'run_root':str(p.parent)}
        for name in ['checkpoint.json','completion.json','worker_error.json','runtime_error.json','export_error.json']:
            f=p.parent/name
            if f.is_file():
                entry[name]=read(f)
                if 'error' in name: errors.append({'path':str(f),'detail':entry[name]})
        runtime.append(entry)
    closed=sum(x['molecules'] for x in counts)==int(meta['population_molecules']) and sum(x['records'] for x in counts)==int(meta['population_records'])
    durable_records=sum(x['records'] for x in durable)
    rate_closed=len(rates)==12 and all(x['total']==durable_records for x in rates)
    snap={'time':time.time(),'status':'FORMAL_QUEUE_POPULATION_CLOSED' if closed and rate_closed else 'COUNT_DIFFERENCE',
          'meta':meta,'counts':counts,'durable_states':durable,'task_success_rates':rates,'runtime':runtime,'errors':errors,
          'population_closed':closed,'task_denominators_closed':rate_closed,'durable_records':durable_records}
    write(ROOT/'reports'/(prefix+'_queue_snapshot_v1.json'),snap)
    complete=[x for x in counts if x['state']=='COMPLETE'];retry=[x for x in counts if x['state']=='RETRY_PENDING']
    cm=sum(x['molecules'] for x in complete); cr=sum(x['records'] for x in complete)
    rm=sum(x['molecules'] for x in retry);rr=sum(x['records'] for x in retry)
    stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    lines=['# WP5 每日汇报','',f'更新时间：{stamp}（北京时间），正式第{a.hour}小时。',
           f'正式作业状态：{obs["formal_states"]}；STOP：{obs["stop"]}；运行错误：{len(errors)}。',
           f'COMPLETE：{cm:,}分子 / {cr:,}记录；等待预提交收尾任务一次重试：{rm}分子 / {rr}记录。',
           f'人口计数闭合：{closed}；12任务分母闭合：{rate_closed}。',
           f'正式实际分配核时：{core:.3f}；当前配额余量：{obs["quota"]["remaining_bytes"]/1e9:.3f} GB。',
           f'冻结29槽计划约120小时；已完成分子比例：{cm/int(meta["population_molecules"])*100:.3f}%。',
           '', '| 节点 | COMPLETE分子 | COMPLETE记录 | RSS峰值GB | PSS峰值GB | 本地scratch峰值GB |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    for node in sorted({x['node'] for x in counts}):
        c=[x for x in complete if x['node']==node]
        peaks=[x.get('checkpoint.json',{}).get('resource_peaks',{}) for x in runtime if x['node']==node]
        pv=[max([(x.get(k) or 0) for x in peaks] or [0])/1e9 for k in ['RSS_bytes','PSS_bytes','local_scratch_bytes']]
        lines.append(f'| {node} | {sum(x["molecules"] for x in c)} | {sum(x["records"] for x in c)} | {pv[0]:.3f} | {pv[1]:.3f} | {pv[2]:.3f} |')
    lines+=['','RSS合计重复计入共享页面；PSS按共享分摊。Slurm OOM/硬超时以实际调度状态为准。','',
            '| 文件组 | COMPLETE分子 | COMPLETE记录 |','| --- | ---: | ---: |']
    for group in sorted({x['file_group'] for x in counts}):
        c=[x for x in complete if x['file_group']==group]
        lines.append(f'| {group} | {sum(x["molecules"] for x in c)} | {sum(x["records"] for x in c)} |')
    lines+=['','| 任务 | 成功 / 已完成尝试 | 成功率 |','| --- | ---: | ---: |']
    for x in rates: lines.append(f'| {x["calc_type"]} | {x["success"]} / {x["total"]} | {100*x["success"]/x["total"]:.4f}% |')
    sci=read(ROOT/'reports/formal_daily_science_first_v1/report.json')
    lines+=['','详细SCI统计使用独立快照 formal_daily_science_first_v1/report.json：32,825分子 / 324,662记录、3,895,944任务槽，24 workers全部读取，缺失和读取错误为0。',
            '失败共1,047槽：454性质缺项、592明确SCF/SCC失败、1次anion超时；失败保留并标注。',
            '该完成前缀wholeMol实际耗时691.069小时 / 同批冻结预测3026.842小时 = 0.2283；不是Slurm分配核时或全量完工预测。',
            '', '| QC | 有效数 | p50 | p99 | 最大值 | pilot p99 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for key,item in sci['QC'].items():
        v=item['formal']
        pilot=item['pilot']
        lines.append(f'| {key} | {v.get("finite_count",v.get("n","见JSON"))} | {v.get("p50")} | {v.get("p99")} | {v.get("max")} | {pilot.get("p99")} |')
    lines+=['','Q01最大值与cation spin最大值高于pilot；仅标注，保持原始人口。pilot为平衡面板，与完成前缀比较不作重新加权。',
            '', '新保留策略预算：永久788.126 GB、未来float32预留400 GB、临时733.385 GB，峰值1921.511 GB；本轮保留float64，float32只预留。',
            '已清理16个无依赖TEST复制容器，释放2.273 GB。普通成功输出解析后本地删除；失败与固定约1%审计记录的完整输出归档，输入正文不归档。',
            '最终200条 / 2400任务同环境重算仍须在正式人口闭合后通过。本轮不创建LMDB。','']
    content='\n'.join(lines)
    for name in ['wp5_daily_latest.md',f'wp5_daily_20261011_hour{a.hour}.md']:
        p=ROOT/'reports'/name;tmp=p.with_name(p.name+'.pending');tmp.write_text(content);os.replace(tmp,p)
    print(json.dumps({'hour':a.hour,'complete_molecules':cm,'complete_records':cr,'retry_molecules':rm,
          'durable_records':durable_records,'population_closed':closed,'task_denominators_closed':rate_closed,
          'runtime_errors':len(errors),'scheduler':obs,'minimum_success_rate':min(x['success']/x['total'] for x in rates)},ensure_ascii=False))
if __name__=='__main__':main()