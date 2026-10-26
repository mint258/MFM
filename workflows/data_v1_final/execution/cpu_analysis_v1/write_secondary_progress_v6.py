"""Actual stage receipts and terminal/in-flight cost, no scientific body opens."""
import datetime,hashlib,json
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,on_login

def load(path):
    assert path.stat().st_size<=2<<20
    return json.loads(path.read_text())

def pin(path):
    assert path.stat().st_size<=2<<20
    raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    on_login()
    main_path=ROOT/'control/owned_accounting_checkpoint25_cpu_auto_memory_20261027_v1.json'
    alpha_path=ROOT/'control/secondary_cluster_20261026_v1/alpha_owned_accounting_checkpoint26_v1.json'
    alpha_raw=ROOT/'control/secondary_cluster_20261026_v1/alpha_owned_sacct_checkpoint26_v1.txt'
    main=load(main_path);alpha=load(alpha_path)
    assert pin(alpha_raw)['sha256']==alpha['raw_sacct_reference']['sha256']
    labels_dir=ROOT/'control/secondary_cluster_20261026_v1/labels_reducer791/artifacts/labels_payload512_readonly_v1/reduction_v1'
    labels=load(labels_dir/'stage_closure.json');hashed=load(labels_dir/'input_verification.json');fixtures=load(labels_dir/'pre_scan_fixture_gate.json')
    n1dir=ROOT/'artifacts/conformers/n1_pprime2_pilot_v4'
    prep=load(n1dir/'prepared_v1/prepared.json');n1=load(n1dir/'actual32_v1/receipt.json')
    review_path=ROOT/'control/n1_actual32_pilot_science_cost_root_review_v1.json';review=load(review_path)
    assert labels['job_id']=='1884791' and labels['quality_stop_fields']==[] and labels['records']==4251
    assert hashed['status']=='ACTUAL_ALL65_SHA_PASS' and hashed['body_count']==65 and fixtures['counts']['run']==6
    assert n1['job_id']=='4521418' and n1['statistics']['Pprime_actual2_molecules']==32 and prep['eligible_count']==4631
    latest=ROOT/'control/secondary_main_actual_progress_20261027_v6.json'
    value={'schema':'DATA_V1_SECONDARY_MAIN_PROGRESS_V6','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'guide_complete':False,'goal_complete':False,'main_actual_parent_count':main['parent_count'],
      'main_actual_allocated_core_hours':main['allocated_core_hours_observed'],'main_active_parents':main['actual_active_job_ids'],
      'alpha_actual_parent_count':alpha['parent_count'],'alpha_observed_all_parent_core_hours':alpha['allocated_core_seconds']/3600,
      'alpha_terminal_parent_core_hours':alpha['terminal_allocated_core_seconds']/3600,'alpha_active_parents':alpha['active_job_ids'],
      'labels_actual_scan_parent':'1884788','labels_actual_reduce_parent':'1884791','labels_molecules':512,'labels_records':4251,
      'labels_reduce_actual_body_count':hashed['body_count'],'labels_reduce_actual_body_bytes':hashed['body_bytes'],
      'labels_original_tests_passed':fixtures['counts']['run'],'labels_stop_fields':labels['quality_stop_fields'],
      'labels_final_D4_or_normalization_release':False,'N1_prepare_actual_parent':'4521417','N1_actual_mother':prep['mother_count'],
      'N1_all_physically_validated_eligible':prep['eligible_count'],'N1_prepare_reason_counts':prep['reason_counts'],
      'N1_real_UFF_pilot_actual_parent':'4521418','N1_pilot_statistics':n1['statistics'],'N1_full_roster':4631,
      'N1_consumed_pilot_attempts_preserve_without_retry':32,'N1_remaining_unconsumed':4599,
      'N1_full_jobs_submitted':False,'N1_final_common_or_production_release':False,
      'N1_pilot_parent_core_seconds_per_molecule':review['pilot_parent_allocated_core_seconds_per_molecule'],
      'N1_descriptive_mean_full_core_hours_not_tail_bound':review['descriptive_linear_4631_parent_core_hours'],
      'Pprime_original_covariance_FAIL':15,'Pprime_2000_full_QM':'HOLD','COCONUT_B_full_actual_parent':'1884790',
      'COCONUT_B_full_required_physical_records':2939137,'COCONUT_B_full_terminal_at_snapshot':False,
      'source_references':[pin(main_path),pin(alpha_path),pin(alpha_raw),pin(labels_dir/'stage_closure.json'),pin(labels_dir/'input_verification.json'),pin(n1dir/'prepared_v1/prepared.json'),pin(n1dir/'actual32_v1/receipt.json'),pin(review_path)]}
    with latest.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    text=f'''# 数据线实际进度 v6

本报告仅从已保存的小回执与真实父作业会计生成，机器证据为 `{latest}`。源码为本生成器，输入SHA见机器文件的source_references。数据集工作尚未完成。

| 阶段 | 实际结果 |
|---|---|
| Alpha 1884788 | C0/57秒/16CPU6；原6测试后核验全部227正文SHA，16进程扫描512分子、4251记录 |
| Alpha 1884791 | C0/18秒/16CPU6；重新通过原6测试，再核验65正文共{hashed['body_bytes']}B，原数学核心汇总4251记录、59514任务槽；quality_stop_fields=[] |
| Main 4521415 | C0/60秒/16CPU13；6项纯资源边界测试通过，覆盖配额、身份、新鲜度和真实autofs/NFS叠层 |
| Main 4521417 | C0/100秒/16CPU13；全5105母群守恒，4631原source/baseline通过物理校验，固定32输入准备完成；未运行UFF |
| Main 4521418 | C0/90秒/16CPU13；原10科学测试通过，32真实第二几何；308次实际UFF优化完成；30个在0.5Å上unique2，2个按原规则标记below_threshold补齐；32包全部保存并逐项float64 SHA读回 |
| Alpha 1884790 | 仍在运行；须完成全部2939137物理记录的原规则身份归一化及实际闭合，当前不释放去污染结果 |

N1原母群角色实测为5036TRAIN、4VAL、65FULL；65FULL、176UFF_UNSUPPORTED及233原baseline非1均按原因保留，未把它们计作新生成失败或共同人群。实际符合条件4631个。旧5040常量的历史来源仍未证实；当前独立角色过滤计数恰为5040，不能据此改写历史来源。正式全部源仍需独立实现/冻结/Root审查；已消费32必须导入旧once账本，不能再计算。32试点按父分配时间均值为45核秒/分子，线性4631约{review['descriptive_linear_4631_parent_core_hours']:.4f}核时；这是描述均值，不是尾部或剩余全体运行上界。

Main当前130个真实父共{main['allocated_core_hours_observed']:.8f}分配核时，快照时本线无活动父；原1293/1327只读重复任务经核实仍PENDING后hold并取消，因为对应Alpha已完成相同源/fixture/输入校验。原请求与会计保留，取消不冒充Main C0，也未向运行科学任务发送终止信号。Alpha24个父观察累计{alpha['allocated_core_seconds']/3600:.8f}核时，其中终态{alpha['terminal_allocated_core_seconds']/3600:.8f}核时；1884790活动分配仍增长，不能当最终成本。两端点及UID分开统计，batch/extern不重复加总。

CPU-only、至少16CPU、SBATCH不申请内存、最长48小时、实际RSS/节点可用内存观察、200GB配额余量与自然排空规则继续。N1新资源provider只读取经实际双端同marker/DNS/挂载审查的Main账户配额，限定node13，30秒刷新、120秒新鲜度、24小时有限寿命；未知/过期停止新派发，不把compute节点df冒充账户配额。核时超标报告后继续，所有科学质量阈值和Se唯一例外保持。

标签结果仍只是使用匹配TRAIN试点参考值的只读候选汇总，未重拟合median/MAD，不能冒充全量掩码、原生单位/帧确认或最终D4。P′原15个协变FAIL与2000/full HOLD保持，后续只读检查已有raw的SCF、终止和自身帧；不重新运行QM或改容差。S′旧334包/14控制/2UNKNOWN事实保留，新正式规划/执行尚在实现。D1共同冻结、全S′、共同人群、D1–D7真实导出/模型实际验收、全下游身份去污染、筛选后1M、ordered10M及首2.5M UFF+D仍有未完成项。未开最终PR，未训练，也未使用GPU或学校付费服务器。
'''
    report=REPO/'docs/data_v1/secondary_main_actual_progress_20261027_v6.md'
    with report.open('x',encoding='utf-8') as f:f.write(text)
    status=REPO/'docs/interfaces/STATUS.md';old=status.read_text()
    intro='## 2026-10-27 最新实际进度：N1真实第二几何与标签汇总\n\n详见[实际进度v6](../data_v1/secondary_main_actual_progress_20261027_v6.md)。N1准备4521417 C0验证4631原baseline，真实UFF试点4521418 C0得到32/32真实第二几何，308优化完成，2个合法below0.5Å补齐；旧once账本保留。Alpha标签扫描1884788和原核汇总1884791均C0，6测试与227/65正文SHA实际通过；不是最终mask或D4。COCONUT全物理身份归一化1884790仍运行；P′15FAIL与2000/full HOLD保持。原Main两个只读重复排队任务仅在PENDING时hold并取消，绝不冒充Main C0。所有核时含失败/启动如实记录，质量阈值不变。\n\n'
    status.write_text(intro+old,encoding='utf-8')
    print(json.dumps({'machine_reference':pin(latest),'report_reference':pin(report),'guide_complete':False}))

if __name__=='__main__':main()