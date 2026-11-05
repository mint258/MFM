"""Generate the sampling-adapter report from closed small metadata only."""
import argparse,datetime,json,pathlib,re,socket,os
from workflows.data_v1_final.execution.cpu_export_fixture_v1 import policy

def write_new(path,obj):
    raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
    policy.require(len(raw)<128*1024,'SMALL_OUTPUT_REQUIRED')
    with path.open('xb') as f:f.write(raw)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accounting',type=pathlib.Path,required=True);a=p.parse_args()
    policy.require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','LOGIN_METADATA_ONLY')
    root=policy.ROOT;repo=policy.REPO;name='dv1_sampling_projection_fixtures_cpu_v1'
    out=root/'artifacts/export/sampling_projection_fixtures_cpu_v1'
    report=repo/'docs/data_v1/model_adapter_sampling_actual_v1.md';proofpath=out/'actual_closure.json'
    policy.require(not report.exists() and not proofpath.exists(),'NEW_OUTPUTS_REQUIRED')
    paths=[a.accounting,root/'control/submissions'/(name+'.json'),out/'stage_receipt.json',
        root/'artifacts/cpu_analysis_guards'/name/'closure.json',pathlib.Path(__file__).absolute()]
    account=policy.load(paths[0]);sub=policy.load(paths[1]);stage=policy.load(paths[2]);monitor=policy.load(paths[3])
    jid=sub['job_id'];policy.require(str(jid).isdecimal() and sub['sbatch_returncode']==0,'ACTUAL_SUBMISSION_REQUIRED')
    intentpath=root/'control/submissions'/(name+'.intent.json');intent=policy.load(intentpath);paths.append(intentpath)
    req=intent['request'];policy.scope(req)
    policy.require(req==sub['request'] and req['scope_key']=='sampling_index_adapter_fixtures' and not req['data_references'],'EXACT_SYNTHETIC_SCOPE')
    expected={'fixture_tests':6,'test_module':'workflows.data_v1_final.export.wire_v1.test_sampling_projection_v1',
        'input_corpus_records':0,'new_UFF_QM_calls':0,'real_export_release':False}
    policy.require(req['scope_parameters']==expected and req['cpus']==16 and req['memory_gib']==4,'EXPECTED_BOUNDARIES')
    paths.extend(pathlib.Path(pin['path']) for pin in req['source_references'])
    logfile=root/'control'/(name+'_'+str(jid)+'.out');log=policy.read_small(logfile).decode();paths.append(logfile)
    tests=re.findall(r'^test_\S+ \(workflows\.data_v1_final\.export\.wire_v1\.test_sampling_projection_v1\.[^\n]+\) \.\.\. ok$',log,re.M)
    ran=re.search(r'\nRan 6 tests in ([0-9.]+)s\n\nOK\n',log)
    policy.require(len(set(tests))==len(tests)==6 and ran,'ACTUAL_SIX_TESTS_AND_OK_REQUIRED')
    policy.require(stage['status']=='ALL_STAGES_COMPLETED' and len(stage['stages'])==1 and stage['stages'][0]['returncode']==0,
        'ACTUAL_STAGE_COMPLETION_REQUIRED')
    expected_argv=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m','unittest',expected['test_module'],'-v']
    policy.require(stage['stages'][0]['argv']==expected_argv and stage['root_preflight']==policy.ref(intentpath),'ACTUAL_COMMAND_BINDING')
    policy.require(monitor['job_id']==str(jid) and monitor['status']=='COMPLETED_NO_MEMORY_DENIAL' and monitor['child_returncode']==0
        and monitor['first_denial'] is None and monitor['failure'] is None and monitor['monitor_io_failure'] is None
        and monitor['durable_evidence_exported'] and monitor['monitor_thread_closed'] and not monitor['signals_sent'],
        'ACTUAL_MONITOR_CLOSURE_REQUIRED')
    for pin in monitor['evidence_exports']:policy.verify(pin);paths.append(pathlib.Path(pin['path']))
    rows=[r for r in account['actual_parents'] if r['JobIDRaw']==str(jid)]
    policy.require(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
        and rows[0]['NodeList']==req['node'] and rows[0]['Partition']=='cpu' and int(rows[0]['AllocCPUS'])==16,'ACTUAL_CPU_PARENT_REQUIRED')
    row=rows[0];cost=int(row['ElapsedRaw'])*int(row['AllocCPUS'])
    policy.require(row['allocated_core_seconds_observed']==cost and account['query_returncode']==0,'ACTUAL_COST_REQUIRED')
    policy.verify(account['raw_sacct_reference']);paths.append(pathlib.Path(account['raw_sacct_reference']['path']))
    refs={str(path):policy.ref(path) for path in paths}
    observed=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    lines=['# 按来源采样桥接的实际边界验证','',
        '目的：分别投影 PM7/UFF 的构象身份与采样顺序，并阻止诊断构象进入训练清单。输入仅为新增合成fixture，没有读取真实语料。','',
        f"实际 CPU 父任务 {jid}，节点 {req['node']}，16CPU/4GiB；6项新增测试均PASS，日志测试耗时{ran.group(1)}秒，监控闭合无内存拒绝。",'',
        '验证覆盖：两来源独立ID及三种顺序；诊断base和child排除；保留energy training_rank=0作为最低能ID；跨来源碰撞与引用拒绝；重复物理身份拒绝；view不作基础构象；原子数、角色、布尔exposure与单分子内存边界。','',
        f"实际父ElapsedRaw={row['ElapsedRaw']}秒，分配核秒={cost}，分配核时={cost/3600}。成本从实际sacct父记录计算；整秒0不表示真实零耗时，steps不重复计入。",'',
        '限制：这是候选桥接的合成数据边界验证。D1仍draft.3，tensor参考系/模型tensor消费、审计原因sidecar、真实provider及最终共同人群/D5/export均未验收；没有改模型文件，没有宣称D3/D5完成。','',
        '来源与完整path/bytes/SHA见外部 '+str(proofpath)+'；本报告由 '+str(pathlib.Path(__file__).absolute())+' 从已闭合小型元数据重建。','',
        '生成时间：'+observed+'。','']
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    obj={'schema':'SAMPLING_ADAPTER_SYNTHETIC_ACTUAL_CLOSURE_V1','status':'SIX_NEW_BOUNDARIES_ACTUAL_PASS_NOT_REAL_EXPORT',
        'observed_at':observed,'actual_parent':row,'fixtures':6,'actual_ok_lines':tests,'test_seconds':float(ran.group(1)),
        'input_corpus_records':0,'new_UFF_QM_calls':0,'real_export_release':False,'contract_finalized':False,
        'model_files_modified':False,'allocated_core_seconds':cost,'input_references':list(refs.values()),'report':policy.ref(report)}
    write_new(proofpath,obj);print(json.dumps({'report':policy.ref(report),'closure':policy.ref(proofpath),'job_id':jid,'allocated_core_seconds':cost}))
if __name__=='__main__':main()
