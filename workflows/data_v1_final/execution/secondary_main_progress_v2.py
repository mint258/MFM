"""Rebuild the current progress report from small saved evidence only."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,on_login,pin,write_new

def main():
 on_login();p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--accounting',type=Path,required=True);a=p.parse_args();assert a.tag.replace('_','').isalnum()
 paths={
  'accounting':a.accounting,
  'cost_policy':REPO/'configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json',
  'all16_actual_review':ROOT/'control/source_status_all16_actual_C0_review_v1.json',
  'labels':ROOT/'artifacts/labels/source_status_v1/auto_memory_v1/reduction/audit.json',
  'identity':ROOT/'artifacts/expansion/identity/sb5_identity_full_closed_units_coverage_v1_v1/receipt.json',
  'golden':ROOT/'control/secondary_cluster_20261026_v1/golden16_1884766/alpha_receipt.json',
  'golden_cost':ROOT/'control/secondary_cluster_20261026_v1/golden16_1884766/alpha_accounting.json',
  'coconut_csv_cost':ROOT/'control/secondary_cluster_20261026_v1/coconut_profile_1884764_actual_cost.json',
  'coconut_csv_structure':ROOT/'control/secondary_cluster_20261026_v1/coconut_profile_1884764_structure.json',
  'sql_spec':ROOT/'control/secondary_coconut_sql_v1/spec.json',
  'model_interface_review':REPO/'docs/data_v1/interface_consumption_remaining_20261026_v1.md',
  'source_check':ROOT/'control/secondary_report2_sources_check_v1.json'}
 refs={k:pin(v) for k,v in paths.items()};x={k:json.loads(v.read_text()) for k,v in paths.items() if v.suffix=='.json'}
 master=x['accounting'];parents={str(v['JobIDRaw']):v for v in master['actual_parents']}
 for jid in ['4521192','4521201','4521182']:assert parents[jid]['State']=='COMPLETED' and parents[jid]['ExitCode']=='0:0'
 ids=[str(v) for v in range(4521139,4521151)];assert all(parents[v]['State']=='COMPLETED' and parents[v]['ExitCode']=='0:0' for v in ids)
 actual=sum(parents[v]['allocated_core_seconds_observed'] for v in ids);forecast=104200.661
 golden=x['golden'];assert len(golden['executions'])==16 and all(v['main_golden_exact_match'] for v in golden['executions'])
 assert x['golden_cost']['actual_terminal'] and x['golden_cost']['actual_parent']['State']=='COMPLETED'
 labels=x['labels'];statistics={'label_records':labels['record_count'],'label_molecules':labels['molecule_count'],'canonical_task_rows':labels['canonical_task_rows'],'physical_files':labels['physical_files'],'task_coverage':labels['task_coverage'],'role_authority':labels['role_authority'],'io_opened':labels['io_handles_opened'],'io_closed':labels['io_handles_closed'],'remaining12_allocated_core_seconds':actual,'remaining12_allocated_core_hours':actual/3600,'remaining12_initial_forecast_core_seconds_rounded':forecast,'remaining12_overrun_multiplier_rounded':actual/forecast,'cost_overrun_action':x['cost_policy']['on_overrun'],'golden_exact_controls':16,'golden_population_added':golden['population_members_added'],'golden_actual_core_seconds':x['golden_cost']['allocated_core_seconds_observed'],'main_actual_parent_count':len(parents),'main_allocated_core_hours_observed':master['allocated_core_hours_observed'],'main_active_at_snapshot':[j for j,v in parents.items() if v['State'] not in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}]}
 statistics['main_active_at_snapshot']=[j for j,v in parents.items() if v['State'].split()[0] not in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}]
 record={'schema':'SECONDARY_MAIN_ACTUAL_PROGRESS_V2','observed_at_utc':datetime.now(timezone.utc).isoformat(),'inputs':refs,'computed_statistics':statistics,'source':pin(Path(__file__).absolute()),'guide_complete':False,'scientific_quality_thresholds_changed':False,'source_or_scientific_data_bodies_read':False,'raw_SQL_completion_claimed':False,'main_and_secondary_accounting_separate':True,'prior_report_active_classification_correction':'Prior20261026_v2 report compared full CANCELLED by UID text; this revision normalizes the base Slurm state. Prior bytes/source snapshot preserved; accounting costs and scientific statuses unchanged.'}
 evidence=ROOT/f'control/secondary_main_actual_progress_{a.tag}.json';write_new(evidence,record)
 lines=['# 双集群数据线实际进度（脚本生成）','',f"观测时间：{record['observed_at_utc']}",'','## 目的与规则','','继续完成数据v1及扩充；用户已明确核时超标报告后继续，质量阈值不变。技能1.0.122保存该授权。每任务至少16CPU，SBATCH不申请内存或exclusive，保留实际RSS/MemAvailable观察、自然收尾、单任务≤48h和200GB存储余量；不动其他或模型作业。Main/Alpha分别按端点和UID1278/1264记录。','','## 实际统计','','```json',json.dumps(statistics,ensure_ascii=False,indent=2),'```','','## 已完成与仍待处理','','16个源状态分片和汇总4521201已C0。覆盖14任务、所有源记录与文件；这不是数组/JSON形状、原生精度、物理范围、跨字段和分子内异常的最终验收。标签未改，新mask、最终D4及共同人口尚未冻结。','','本地全源身份首次4521152在404个单元均落盘后因内存采样耗时>2秒失败，失败和费用保留。新4521192仅重新核验现有404份结果并完成全局唯一性闭合，11,398,552个身份；没有重投影或释放外部去污染池。','','Alpha固定16个UFF软件对照1884766 C0/40秒，全部科学摘要精确匹配Main原有包（只排除summary.elapsed_seconds）。RDKit2025.09.5一致，Torch2.5.1+cpu与Main版本差异明示；population新增0，尚待Main独立CPU读回验收。官方COCONUT完整ZIP1884764 C0/47秒，247,959,854字节、CSV738,794行；不等于规范化唯一分子数或inactive全覆盖。37,876,914,074字节SQL1884765已实际提交，完整EOF/hash/终态仍待核验。','','S′原4520364与恢复4521110均TIMEOUT，334份原包及14个同seed对照保留；2个未决任务不伪造包或科学失败阶段。新334+14+2诚实闭合4521315已提交排队。原成本线只报告，不把低于成本线当科学PASS。','','P′原72项中15个协变矛盾仍保持；原容差不变，2000/full QM继续HOLD。四个小测试先于原始输出的Fraction精度诊断4521293已提交排队。完整PubChem原始空间上的均匀10000成本试点4521316也已提交；它与guide筛选去重后的1M参考集不同，尚无全空间化学成本预测。','','模型候选provider及四条合成串联实际4521005已存在，不能再称尚无实现；真实数据authority、tensor/basis/perturbed支持、D1共同签认及真实50kTRAIN+5kVAL加载验收仍待完成。详见接口核对。','','## 异常、成本与局限','','标签余12分片的最终实际核时及相对初估倍数见上表；先前1.59倍只是运行中快照。完整失败、超时、启动、复核及步骤证据保留，步骤不重复收费。Main总账是指定时点的所有本任务父作业，Alpha另记；活跃作业耗时不是终态费用。','','D1–D7、最终注册表、全量S′/P′、去污染、ordered10M及首2.5M实际生成仍未全部完成。当前无最终验收或最终PR。','','## 输入与哈希','']
 for k,v in refs.items():lines.append(f"- `{k}`：`{v['path']}`；{v['bytes']} B；SHA256 `{v['sha256']}`。")
 lines+=['',f'机器证据：`{evidence}`。','']
 out=REPO/f'docs/data_v1/secondary_main_actual_progress_{a.tag}.md'
 with out.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
 print({'evidence':pin(evidence),'report':pin(out),'statistics':statistics})
if __name__=='__main__':main()
