# 双集群数据线实际进度（脚本生成）

观测时间：2026-10-26T02:27:41.949187+00:00

## 目的与规则

继续完成数据v1及扩充；用户已明确核时超标报告后继续，质量阈值不变。技能1.0.122保存该授权。每任务至少16CPU，SBATCH不申请内存或exclusive，保留实际RSS/MemAvailable观察、自然收尾、单任务≤48h和200GB存储余量；不动其他或模型作业。Main/Alpha分别按端点和UID1278/1264记录。

## 实际统计

```json
{
  "label_records": 11231854,
  "label_molecules": 1220466,
  "canonical_task_rows": 157245956,
  "physical_files": 2024,
  "task_coverage": {
    "D20": 11231854,
    "D3": 11231854,
    "pm7_B": 11231854,
    "pm7_anion": 11231854,
    "pm7_cation": 11231854,
    "pm7_octanol": 11231854,
    "pm7_water": 11231854,
    "xtb_ALPB_octanol": 11231854,
    "xtb_ALPB_water": 11231854,
    "xtb_fod": 11231854,
    "xtb_perturbed_gradient": 11231854,
    "xtb_singlepoint": 11231854,
    "xtb_vfukui": 11231854,
    "xtb_vipea": 11231854
  },
  "role_authority": {
    "FULL": {
      "molecules": 6248,
      "records": 54557
    },
    "TRAIN": {
      "molecules": 1206608,
      "records": 11104772
    },
    "VAL": {
      "molecules": 7610,
      "records": 72525
    }
  },
  "io_opened": 2024,
  "io_closed": 2024,
  "remaining12_allocated_core_seconds": 392736,
  "remaining12_allocated_core_hours": 109.09333333333333,
  "remaining12_initial_forecast_core_seconds_rounded": 104200.661,
  "remaining12_overrun_multiplier_rounded": 3.769035591818367,
  "cost_overrun_action": "REPORT_AND_CONTINUE",
  "golden_exact_controls": 16,
  "golden_population_added": 0,
  "golden_actual_core_seconds": 640,
  "main_actual_parent_count": 123,
  "main_allocated_core_hours_observed": 231.2888888888889,
  "main_active_at_snapshot": [
    "4520959",
    "4520960",
    "4520961",
    "4520962",
    "4521022",
    "4521023",
    "4521036",
    "4521037",
    "4521044",
    "4521077",
    "4521109",
    "4521293",
    "4521315",
    "4521316"
  ]
}
```

## 已完成与仍待处理

16个源状态分片和汇总4521201已C0。覆盖14任务、所有源记录与文件；这不是数组/JSON形状、原生精度、物理范围、跨字段和分子内异常的最终验收。标签未改，新mask、最终D4及共同人口尚未冻结。

本地全源身份首次4521152在404个单元均落盘后因内存采样耗时>2秒失败，失败和费用保留。新4521192仅重新核验现有404份结果并完成全局唯一性闭合，11,398,552个身份；没有重投影或释放外部去污染池。

Alpha固定16个UFF软件对照1884766 C0/40秒，全部科学摘要精确匹配Main原有包（只排除summary.elapsed_seconds）。RDKit2025.09.5一致，Torch2.5.1+cpu与Main版本差异明示；population新增0，尚待Main独立CPU读回验收。官方COCONUT完整ZIP1884764 C0/47秒，247,959,854字节、CSV738,794行；不等于规范化唯一分子数或inactive全覆盖。37,876,914,074字节SQL1884765已实际提交，完整EOF/hash/终态仍待核验。

S′原4520364与恢复4521110均TIMEOUT，334份原包及14个同seed对照保留；2个未决任务不伪造包或科学失败阶段。新334+14+2诚实闭合4521315已提交排队。原成本线只报告，不把低于成本线当科学PASS。

P′原72项中15个协变矛盾仍保持；原容差不变，2000/full QM继续HOLD。四个小测试先于原始输出的Fraction精度诊断4521293已提交排队。完整PubChem原始空间上的均匀10000成本试点4521316也已提交；它与guide筛选去重后的1M参考集不同，尚无全空间化学成本预测。

模型候选provider及四条合成串联实际4521005已存在，不能再称尚无实现；真实数据authority、tensor/basis/perturbed支持、D1共同签认及真实50kTRAIN+5kVAL加载验收仍待完成。详见接口核对。

## 异常、成本与局限

标签余12分片的最终实际核时及相对初估倍数见上表；先前1.59倍只是运行中快照。完整失败、超时、启动、复核及步骤证据保留，步骤不重复收费。Main总账是指定时点的所有本任务父作业，Alpha另记；活跃作业耗时不是终态费用。

D1–D7、最终注册表、全量S′/P′、去污染、ordered10M及首2.5M实际生成仍未全部完成。当前无最终验收或最终PR。

## 输入与哈希

- `accounting`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/owned_accounting_checkpoint21_cpu_auto_memory_20261026_v1.json`；126140 B；SHA256 `55067d59458cb83761b0a7bd269bf2a0b5af4e270251bab5eb2d8be8f2512729`。
- `cost_policy`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json`；1331 B；SHA256 `aa333f4eb26f69abae9600d11be47384919d8031af99dadf0e843feb1f25a7fd`。
- `all16_actual_review`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/source_status_all16_actual_C0_review_v1.json`；14704 B；SHA256 `9bd90948b3081a42343a05cea0e5ec7405bc7cbe9f5b16bdd2ebb50e4183ddfb`。
- `labels`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/auto_memory_v1/reduction/audit.json`；1038256 B；SHA256 `1fe916db16969b3b43274493f79e82ef7c29381bd9ca051aa24dd170a16b96e0`。
- `identity`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/identity/sb5_identity_full_closed_units_coverage_v1_v1/receipt.json`；174343 B；SHA256 `ff2d353c26f3558d4cea7e9e50cda1b8a842d72c1a51282849269862d0aa564e`。
- `golden`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_cluster_20261026_v1/golden16_1884766/alpha_receipt.json`；20138 B；SHA256 `c35684bc7ad4516a0aa6a675775984172a358c2bdda37a7f06b5c04d0858e58b`。
- `golden_cost`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_cluster_20261026_v1/golden16_1884766/alpha_accounting.json`；1655 B；SHA256 `0d31f4be29ac7ba00e1799bd5a811d881fb667a04b4c391c05e3c64d4290d4f0`。
- `coconut_csv_cost`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_cluster_20261026_v1/coconut_profile_1884764_actual_cost.json`；2258 B；SHA256 `5d727e132607c78854e240bbea5863b2340104d15735cba56c369af21aa51b2c`。
- `coconut_csv_structure`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_cluster_20261026_v1/coconut_profile_1884764_structure.json`；2921 B；SHA256 `db90487c662b05aa1be45a1cf4255a5588a11c1fea663ad78c1caddfe95b6afe`。
- `sql_spec`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_coconut_sql_v1/spec.json`；5792 B；SHA256 `8bc4f92cf4d791098770e4d71b8a06e484f32bb9b1e7f2a98d10d81a1a3e4530`。
- `model_interface_review`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/docs/data_v1/interface_consumption_remaining_20261026_v1.md`；9402 B；SHA256 `67948e933be15759d2e6bb6faa3c8f1a4511ece90d40fa0d2cc699902ddc3b1b`。
- `source_check`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_report2_sources_check_v1.json`；177 B；SHA256 `2519f137b1c1068892902fe85e4d80333425cf0e7650084c5c8de26ced374243`。

机器证据：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_main_actual_progress_20261026_v2.json`。
