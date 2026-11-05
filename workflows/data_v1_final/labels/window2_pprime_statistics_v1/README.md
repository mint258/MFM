# P′ 独立全TRAIN统计

先用最终Common、最终固定首2物理构象清单、原D5实际UFF留出ID产生资格表。读取已关闭原P′和新增补算原家族Parquet各一次，在这一生产步直接复用原 `payload_audit.evaluate` 和标签掩码函数，F64/source_mask原样保存到统计cache；EA复用 `window2_validity_v1.policy.apply_ea_entry` 的既有10eV且收敛未确认交集，并输出稀疏false-mask override。没有内容SHA、收据、独立QA、二次原源读回、人工review清单或人工资源停止门。

之后在cache上运行与PM7相同的原TSQR256、精确type7的0.1/99.9百分位、WinsorMoments及median/MAD对象，独立拟合P′参数。算法内部radix refinement属于该次精确统计计算，不是独立重算验收。D20/D3不属于P′12任务，保持原146 field_id中的P字段编号，不重编号。D5 UFF基构象及其全部任务/扰动视图都不参与fit；VAL/FULL及不属最终Common的记录不参与fit。

Root唯一提交：

```bash
python -B -m unittest workflows.data_v1_final.labels.window2_pprime_statistics_v1.test_statistics
python -B -m workflows.data_v1_final.labels.window2_pprime_statistics_v1.run --plan /ABS/plan.json
```

plan字段：`source_index`（full_physical_index_v3已关闭manifest），`additional_pprime_roots`（新增P′已关闭根目录列表，每根有manifest.json），`coverage`（已有PM7 full projection manifest，仅复用fieldmap/元素basis），`science_config`（原compact_numeric_full_v3.../config.json），`common`、`d5`、`first2`（最终Pprime_first2_scope.json），`output`、`workers`。`mask_exclusions`可选，仅原已明确的record_id/field_id/reason清单，不能自行添加物理阈值。

typed cache逐行保存源path/bytes、RG/局部/物理行号、任务、实际MID/confidx和原F64 entries/masks；D6可据此复用已产生掩码并从原CELL提取r73/原子对结构，禁止从flatten数值猜索引。统计normalization_moments流同时输出每MID/field有效叶均值，供P/P′分布相关性比较，不再扫描P′raw源。

代码为准备入口；单测和生产须由Root实际分配内运行，源码存在不代表实际统计完成。
r73：用户2026-11-05已批准pureσ–σ和pureπ–π。调用共享 `labels/window2_r73_views_v1/kernel.py`，派生IDs146/147只加到统计view map，field_key与B2保持为原r73key`.sigma`/`.pi`；原r73有序K值、mask及字段ID完整保留。混合/δ不进入两列；无selected项缺失而非有效0；selected条目的source mask/value mask分别AND。cache只包含P字段及这两个派生目标，不包含UFF D3/SASA或D20；这些D标签不能由P′完成状态冒充。

P/P′摘要比较（在两套statistics完成后，同一或后续实际CPU allocation）：

```bash
python -B -m workflows.data_v1_final.labels.window2_pprime_statistics_v1.compare --pm7 /FINAL_PM7_D4/manifest.json --pprime /FINAL_PPRIME_D4/statistics/manifest.json --output /FRESH_EXTERNAL_COMPARISON
```

只读取原moments流已产生的per-MID field sum/count及完整分位/均值/标准差摘要；不读取原raw源。相同MID/field内先合并有效叶平均值，然后Pearson/Spearman（ties取平均秩），常量/样本不足如实NULL。不同几何的原子/矢量分量相关性仅为存储参考系中的描述统计，不据此改变模型规则或声明旋转等价。