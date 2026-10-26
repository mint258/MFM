"""Point-in-time actual receipts only; never opens a scientific data body."""
import csv,io,json,hashlib,datetime
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,on_login
on_login()

def load(p):
 assert p.stat().st_size<=2<<20
 return json.loads(p.read_text())

def pin(p):
 assert p.stat().st_size<=2<<20
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

D=ROOT/'control/secondary_cluster_20261026_v1/continuation_1884783_1884786/exact_Alpha_metadata_copies'
main=load(ROOT/'control/owned_accounting_checkpoint23_cpu_auto_memory_20261026_v1.json')
alpha=load(ROOT/'control/secondary_cluster_20261026_v1/alpha_owned_accounting_checkpoint24_v1.json')
raw=ROOT/'control/secondary_cluster_20261026_v1/alpha_owned_sacct_checkpoint24_v1.txt'
assert pin(raw)['sha256']==alpha['raw_sacct_reference']['sha256']
source=load(D/'artifacts/coconut_sql_identity_full_v1/v1/receipt.json')
norm=load(D/'artifacts/coconut_identity_norm_profile_v1/v1/receipt.json')
ext=load(D/'artifacts/moleculenet_missing11_full_v1/v1/receipt.json')
rawprof=load(ROOT/'artifacts/expansion/cost_profiles/sb5_pubchem_raw_uniform_cost_10000_v1_v1/receipt.json')
n1=load(ROOT/'artifacts/conformers/n1_pprime2_pilot_v2/prepared_v1/prepared.json')
closed=load(ROOT/'artifacts/conformers/recovery_timeout_closure_v2/v1/joint_timeout_audit_report.json')
value={'schema':'DATA_V1_SECONDARY_MAIN_PROGRESS_V5','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_complete':False,'guide_complete':False,'main_actual_parent_count':len(main['actual_parents']),'main_actual_allocated_core_hours':main['allocated_core_hours_observed'],'alpha_actual_parent_count':alpha['parent_count'],'alpha_actual_allocated_core_hours':alpha['allocated_core_seconds']/3600,'source_SQL_all15_full_EOF':source['inventory']['full_EOF_and_all_tables_proven'],'SQL_rows':source['inventory']['physical_COPY_rows_by_table'],'COCONUT_norm_profile_rows':norm['observed_rows'],'COCONUT_norm_profile_by_table':norm['observed_rows_by_table'],'COCONUT_norm_profile_observations':norm['identity_observation_counts_not_exclusions'],'COCONUT_norm_profile_workers':len(norm['actual_nonempty_workers']),'external11_source_statuses':{x['source_id']:x['status'] for x in ext['sources']},'raw_uniform10000':rawprof['uniform']['counts'],'N1_actual_source_mother_count':n1['mother_count'],'N1_actual_eligible_count_before_corrected_recount':n1['eligible_count'],'N1_reason_counts':n1['reason_counts'],'Pprime_original_covariance_FAIL':15,'Pprime_2000_full_QM':'HOLD','native_invariants_1884786_failure':'GUARD_RAW_STORAGE_VS_EFFECTIVE_SUMMARY_SCHEMA_MISMATCH_BEFORE_FIXTURES_OR_BODY_IO','Sprime_closed_packages':closed['readback334_real_packages'],'Sprime_same_seed_controls':closed['controls_validated_exact_excluding_only_summary_elapsed'],'Sprime_unresolved':closed['unresolved_execution_failures'],'scope':'Point-in-time evidence, not final data or identity/pool acceptance','source_references':[pin(ROOT/'control/owned_accounting_checkpoint23_cpu_auto_memory_20261026_v1.json'),pin(ROOT/'control/secondary_cluster_20261026_v1/alpha_owned_accounting_checkpoint24_v1.json'),pin(D/'artifacts/coconut_sql_identity_full_v1/v1/receipt.json'),pin(D/'artifacts/coconut_identity_norm_profile_v1/v1/receipt.json'),pin(D/'artifacts/moleculenet_missing11_full_v1/v1/receipt.json'),pin(ROOT/'artifacts/conformers/n1_pprime2_pilot_v2/prepared_v1/prepared.json')]}
p=ROOT/'control/secondary_main_actual_progress_20261026_v5.json'
with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
text=f'''# 数据线实际进度 v5

## 目的与输入

本报告只汇总实际CPU产物和父作业会计。机器证据为`{p}`，源码为本报告生成器；其中source_references保存各输入的小回执完整SHA。大数据仍在仓库外。

## 规则和参数

CPU-only、至少16CPU、SBATCH不申请内存、最长48小时、保留200GB余量；核时超标报告后继续。数据质量门槛及Se唯一元素例外保持。TRAIN拟合和ROUTINE整分子VAL保持；当前不释放最终mask、common、D4或候选池。

## 实际统计

| 实际任务 | 结果 |
|---|---|
| Main 4521316 | C0/293秒，原空间均匀10000：{rawprof['uniform']['counts']}；另独立longest16，不冒充指南的筛选后1M |
| Main 4521321 | C0/69秒，334原包与14同seed控制闭合，2个超时未决保留；未生成新UFF |
| Main 4521326 | FAILED3/123秒：实际N1母群{n1['mother_count']}；旧5040全局比较导致eligible0，不是全部baseline失败 |
| Alpha 1884772 | C0/2055秒，全部15 SQL表EOF/整源SHA，molecules {source['inventory']['physical_COPY_rows_by_table']['molecules']}，entries {source['inventory']['physical_COPY_rows_by_table']['entries']} |
| Alpha 1884783/1884784 | 单文件试点C0/10秒；正式C0/338秒，11官方载荷共2501171487B，逐容器完整性核验，Sider复用 |
| Alpha 1884785 | C0/222秒，标准化{norm['observed_rows']}条物理记录、{len(norm['actual_nonempty_workers'])}个实际worker；观察{norm['identity_observation_counts_not_exclusions']} |
| Alpha 1884786 | FAILED1/8秒，启动guard误比较原始storage与归一化摘要，未运行fixture或读取科学body；新独立版本修复中 |

Main已记录{len(main['actual_parents'])}父、{main['allocated_core_hours_observed']:.8f}分配核时；Alpha已记录{alpha['parent_count']}父、{alpha['allocated_core_seconds']/3600:.8f}分配核时。两端点独立，失败、超时、启动费用均纳入，batch/extern不重复相加；这不是最终总成本。

## 异常与后续

N1保留全部5105行，旧5040仅为未证常量；差65的组成待新CPU交叉聚合，不能猜作FULL/VAL/失败。新版本使用同task/seed及原once账本，不复制第二几何。P′原15协变FAIL和2000/full HOLD保持；只读诊断C0不等于科学PASS。20条无有效身份键的标准化试点行保留，不删除、不用作筛选放行。

标签281件原件继续按原清单接入Alpha；6原测试通过后同allocation校验227正文SHA，才扫描512分子/4251记录，Arrow17实际兼容性须由该运行证明。正式COCONUT全表标准化和N1校正尚待实际新作业。

## 已知限制

D1草案尚未共同冻结，D1–D7、全S′/P′、共同人群、真实导出、全部下游去污染、ordered10M与首2.5M仍有未完成项。11载荷容器完整不等于身份覆盖；COCONUT物理全表清点不等于化学标准化或去污染已完成。未开最终PR，也未开始训练或使用GPU/学校付费服务器。
'''
out=REPO/'docs/data_v1/secondary_main_actual_progress_20261026_v5.md'
with out.open('x',encoding='utf-8') as f:f.write(text)
status=REPO/'docs/interfaces/STATUS.md';old=status.read_text()
status.write_text('## 2026-10-26 最新实际进度：SQL全表与十一源载荷闭合\n\n详见[实际进度v5](../data_v1/secondary_main_actual_progress_20261026_v5.md)。COCONUT全15表清点1884772 C0、十一源载荷1884784 C0、20000身份标准化试点1884785 C0；均不冒充去污染或最终数据完成。Main原空间成本4521316与S′历史产物闭合4521321 C0。N1 4521326实际母群5105与旧5040硬值不符，保留全母群作新版本核清；P′原15FAIL与2000/full HOLD不变。Native不变量首次1884786在启动storage-schema比较时退出，未读科学body，新版本修正中。标签Alpha原6测试后校验227正文并扫描，尚待实际结果。\n\n核时超标报告后继续，质量门槛保持；下列历史快照按其时间保留。\n\n'+old,encoding='utf-8')
print(json.dumps({'machine_reference':pin(p),'report_reference':pin(out),'guide_complete':False}))