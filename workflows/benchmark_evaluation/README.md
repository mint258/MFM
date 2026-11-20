# Downstream benchmark execution

Authority: `docs/benchmark/USER_DIRECTIVE_20261119.md` and unchanged requirements of the 2026-11-18 directive and BENCHMARK_PLAN. Current work covers B1, C1, and B2 environment/fixed100 acceptance only.

Data enter through `configs/benchmark_data/B0.DELIVERY.json`. Shared geometry/labels use `SharedB0Reader`; P′ uses `PprimeReader` only after the corresponding source is sealed. No database copies are made. The complete five-deferred-endpoint inventory was verified before fits; its anonymous identities are never published here.

The server worktree remains based on B0 commit `6d056a41f379b921d31017ecfed9ce84d1a5c71a`. GitHub publication uses the connector; the equivalent scripts were submitted inline to Slurm because X: source editing is unavailable. These files archive the submitted logic; they have not yet been merged/deployed into that server worktree. Output paths contain native job IDs. For later fresh submissions, update an input job path only to the corresponding closed producer, preserve the frozen science, and retain the original artifacts.

| Scripts / logic | Current native execution |
|---|---|
| endpoint_catalog.sbatch | 4536889: 96 active candidate endpoints across 11 source groups; no decisions |
| b1_molecular_features.sbatch | 4536908: MoleculeACE and PharmaBench closed |
| b1_more_molecular_features.sbatch | 4536920: five additional source groups closed |
| b1_rf_lightgbm_official.sbatch | 4536910: 80/80 task-model pairs closed, no failures |
| b1_chemprop_official.sbatch | 4536913: fixed-default final-epoch fits in progress |
| c1_d_features.sbatch | 4536892: native D20 + six global D3 fields for eight tabular groups |
| c1_d_lightgbm_moleculeace.sbatch / c1_d_tabpfn_moleculeace.sbatch | 4536894 / 4536899: 30/30 each |
| c1_d_lightgbm_pharmabench.sbatch / c1_d_tabpfn_pharmabench.sbatch | 4536912: 10/10; 4536921 in progress |
| c1_d_lightgbm_tdc_asap.sbatch | 4536929: 23/23, original endpoint masks and split metadata |
| pka_macro_binding.sbatch | 4536926: frozen macro labels, dataset+rawdataID SAMPL join, full-key TRAIN exclusions |
| c1_d_lightgbm_pka.sbatch | 4536951 continues pre-import I/O failure 4536932; native logs retain both job identities |
| b1_rf_lightgbm_tdc_asap.sbatch / b1_chemprop_tdc_asap.sbatch | 4536953/4536954 continue pre-import I/O failures 4536935/4536937; no prior fit was restarted |
| reference_source_schema.sbatch | 4536945: original NMR label/atom interface and reference/PPE/Biogen source metadata for consumers |
| selection.py / test_selection.py | 4536943: 14 new-logic tests passed; no produced model result was replayed |
| B2 scripts | Native acceptance and unresolved attempts indexed in BASELINE_AVAILABILITY.md |

Primary official-split fits use the original TRAIN/TEST population, seed 20261025, default RF/LightGBM settings, 1000 whole-molecule paired bootstrap draws, and a TRAIN-mean reference. Binary tasks predict class-1 probabilities; their RAE uses absolute probability error against TRAIN prevalence. Filter-impact diagnostics fit on the full processable TRAIN and report full/retained/excluded TEST populations separately. Blind ASAP/ExpansionRx main predictions retain all official evaluable TEST rows and use the registered TRAIN-mean fallback outside the domain.

Chemprop uses the default graph architecture and learning-rate schedule, batch64, 50 epochs, and final-epoch weights; no validation or TEST checkpoint selection or parameter search. Regression scaling is fitted on TRAIN only and inverted in prediction. Every completed epoch has a last checkpoint, and completed task fits write closed prediction/result files.

The selection module refuses missing baselines or different evaluation IDs, original labels, molecular groups, or TRAIN references. Its official-split statistics resample the same whole molecules in all models, using 1000 draws. The discrimination SE is for the observed worst-minus-best RAE pair. The <30 rule takes the total labeled points in the filtered endpoint, explicitly supplied by the task binding. For tasks lacking an official split, five repetitions of five scaffold-group folds are mandatory; optical folds group by chromophore scaffolds across every solvent observation. Tukey HSD requires the same complete 25 fold scores for all three baselines. The final B1 roster is not yet produced or frozen.

P′ and P′+D remain conditional on B0 sealing; atom-site pKa labels are not inferred from predicted microspecies. Standard NMR uses the original Jonas release, not a DFT-only substitution. No B2 full extraction, B3/B4, pretraining, paid school-server work, or PM7 geometry reconstruction has been launched.

## 原子任务、参考任务和公开标签补充

NMR 的原始谱和原子标签由 `b1_nmr_features.sbatch` 消费；4536971 因旧 RDKit pickles 未含 ring cache 报错。后续 `b1_nmr_features_cache_repair.sbatch`（4536984）只初始化 property/ring caches，不重排原子，`b1_nmr_rf_lightgbm.sbatch`（4536985）在该特征步骤成功后拟合原子中心 ECFP4 和 RDKit2D+37 原子特征。两种核素独立，重复谱不平均，统计仍以完整分子为组。

参考数据特征（4536983）保留 B0 原生 D20/D3、参考几何与缺失掩码。`ppe_benson.sbatch`（4536988）固定 pGrAdd 2.9.14 源码 commit cecd9819ba60884efce483ceb3fb18d03ac27f84 的 BensonGA 库，298.15 K、kcal/mol，按原始实验生成焓构造实验值减 Benson 残差；不拟合新的基团参数。未启动的 4536986 已取消后修正原生 group 对象传递，不涉及数值重算或训练回滚。

ExpansionRx 官方九终点公开释放源由 4536975 获取，以 `B0.DELIVERY.json` 的 `supplemental_sources.ExpansionRx_official_release` 统一登记。`expansion_release_binding.sbatch` 将使用本分支对应配置的不可变内嵌快照，写出运行时入口到自身 artifact 后消费；原服务器工作树未同步这一新配置。仅当官方 ID、完整原始结构与原官方划分匹配才接入 TEST 标签，TRAIN 使用 B0 原标签，无新增 RLM 终点。

4536983/84/85 的未启动调度请求已从固定 node17 改为 cpu 分区的任一允许 CPU 节点（排除 node2、18、21）。该分区现场成员为 2、8–19，故候选为 8–17、19；node18 暂因 Python/NFS 阻塞不参与。实际目标节点仍先执行容量/inode/quota 准入，不更改现有训练。

## 本批执行索引与共享协议

原生作业、重提关系、数组和参数选择保存在 `native_jobs_20261120.json`。C7/PPE 的每个模型使用同一冻结折；Joung 按发色团 scaffold 保持全部溶剂观测在同一折。RF / LightGBM / C1 的 Joung 通用脚本以 `BENCHMARK_MODEL`、`BENCHMARK_TASK_INDEX` 选择固定配置；索引给出各已提交作业的值。Chemprop 的九个端点数组脚本各用 index0–4 对应五次既定重复，并没有加种子或重复。新增 CV 任务按40GiB本线并发峰值执行磁盘准入，原有运行保持其已记录24GiB预算；新鲜 UID 配额已包含所有现存失败环境和文件。

新接口测试的原生身份：4536913.2 原子接口8项；4536913.3 两组分接口2项；4536913.5 ExpansionRx指标7项；4536913.6 气相两组分接口3项。它们是无真实评测数据、无模型拟合的新逻辑测试。原先4536913.1因测试步少设依赖路径而导入失败，补齐与正式脚本相同路径后测试通过，不涉及科学拟合。

执行中保留的失败：4536996未识别原B0 `test_blinded` 别名，由4537017绑定同一官方TEST，未改成员；4536992为源码字符串拼接错误，4537022完成修复后的pKa特征；4537020为RDKit导入位置错误，4537021完成已声明气相条件的特征接入。相关未启动下游请求已从零计算边界替换，未停止任何已运行训练。Biogen Chemprop的临时Nice调度已恢复0。

[ExpansionRx评分](../../docs/benchmark/EXPANSIONRX_METRIC_PROTOCOL.md)、[Joung输入](../../docs/benchmark/JOUNG_INPUT_PROTOCOL.md)、[NMR划分与文献](../../docs/benchmark/NMR_SPLIT_AND_LITERATURE.md) 和 [报告说明](../../docs/benchmark/REPORTING_NOTES.md) 固定了本批含义。表内“可用”、部分结果、源准备关闭和最终科学结论分开标注；没有生成 B1_task_screen.csv 或声称 C1 最终表已完成。

### Final reporting and current UFF C1 binding

`reporting.py` and `b1_final_task_screen.sbatch` consume closed native B1 predictions for the single registered screen. The batch source binds all 45 producer handles, including nine five-element Chemprop repetition arrays. It is prepared but has not been submitted; finish producer-error recovery before final execution. It refuses to revise an existing final CSV. Incomplete/unaligned comparisons raise until an explicit final UNRESOLVED reason is bound. Only the final screen CSV receives a SHA; diagnostic/Tukey tables do not.

`c1_uniform_uff_d_binding.sbatch` consumes the newly sealed B0 uniform UFF scope, through SharedB0Reader, for C7/PPE C1-D. It preserves existing labels and frozen folds, and writes matching native values/masks/state. Its four `c1_uniform_uff_*` drivers supersede historical reference-D3 C1 outputs, which remain preserved. `pprime_features.py` reuses the original pretraining component reader and original task paths/units; no P′ database is consumed before its own native seal. Exact current native job bindings are in `native_jobs_20261120.json`.

### P-prime execution chain

Native feature job4537124 waits for the existing B0 all-scopes handoff4536961; its24 table-model configurations wait for that actual closed feature job. It writes Pprime and Pprime_plus_D vectors for the eight existing molecular groups, retaining every original row, native missingness and feature masks. Both names are property-label features, not B2 learned representations.

Job4537149 waits for B0 closure, the corrected UFF-D source4537119 and tabular Pprime binding4537124. It binds C7/PPE and the unchanged optical solvent/gas context, and maps NMR native Pprime atoms back to the exact original experimental atom IDs. Its44 scaffold model configurations retain the original25 folds. NMR atomic job4537321 supersedes unstarted4537194 and uses only native atomic Pprime plus original RDKit atom37 with LightGBM; no atomic TabPFN or invented atomic D. Unmapped native appended hydrogens remain missing. All corresponding shared SQLite access declarations must be immutable and cross-node-readable before consumption.

Every model configuration defaults to seed20261025 only. Native calculations/geometries are never repeated by this chain; native quantum failures stay missing. Official TabPFN preprocessing is disclosed and optional second seeds remain conditional on a significant improvement that will enter final results. The native registry records the concrete source and model handles; queued jobs are not completed results.

### Original NMR atom order repair and actual GPU execution

Actual Chemprop source job4537205 exposed a source-feature cache collision: equal noncanonical SMILES can come from different original atom orders. Feature producer4537317 keys its cache by the exact original graph binary and keeps every original binary/atom index/experimental value. It supersedes4536984. Affected RF job4536985 was cancelled for this confirmed input error at2:39:36; all old outputs remain. Corrected RF/LightGBM4537322 and Chemprop4537337 have closed with zero task failures. The trained1H samples must be redone, so the user's training-redo exception independently requires confirmation seed20261026(job4537338, closed with zero task failures). Traditional ML remains one seed. C1 atomic4537321 combines original native Pprime with corrected original graph/RDKit atom fields; original target/split/mask changes are rejected.

Neural GPU jobs use the existing cross-window UUID lock on actual idle development cards, demand CPUs and native sbatch. GPU hosts only load/train/predict; environment preparation, tests and bootstrap/report statistics run on CPU nodes. The private cu118 environment reuses existing packages for the actual older driver, preserves Chemprop2.2.2/TabPFN10.2.0, and leaves original environments untouched. An empty-context driver-utilization cooldown can wait at most60seconds; on0–7 an existing context prevents launch. Authorized20/22 sharing permits existing verified foreign-UID contexts at up to30% memory usage when free memory covers the job; high foreign compute utilization is recorded and never assumed idle. Existing contexts are never interrupted. Exact current replacement jobs and preserved preflight failures are recorded in the native registry.

### Primary comparisons and conditional confirmation

The B1 consumer runs only after every declared baseline source closes, including all five elements of each original scaffold repetition array. It freezes the complete96-endpoint roster exactly once. Conditional Chemprop plans bind actual original source task names; only significant final retained/appendix winners receive seed2, apart from the actual NMR1H sample-redo exception. A confirmation cannot revise the task roster.

The C1 primary consumer is prepared but not submitted. It requires that frozen B1 roster and all103 native C1 producer configurations. Each available cell reports native-feature coverage, original TRAIN-reference MAE/RAE and1000 complete-molecule bootstrap draws. Registered contrasts use paired original labels/IDs; scaffold contrasts require all25 original folds and Tukey HSD. Missing native features remain missing; a producer must explicitly declare an unavailable native population before it can become UNRESOLVED. Atomic tasks acquire no invented D/TabPFN arms.

The confirmation adapter changes the neural model seed to20261026, keeps split/statistics seed20261025, consumes frozen folds and filters to the required original task identities. It preserves model budgets and fits only the primary retained population. Primary C1 output has no SHA and is not the final table. The final C1 table will be produced after the required actual second seeds close.

### Pending RF input storage

For corrected NMR and the still-unstarted Joung e1–e8 forests, the original packed fingerprints are stored as sklearn's native sparse CSC float32 input. The same2048 little-endian bits, ordered chromophore/solvent blocks, explicit gas bit, rows, labels and estimator parameters remain. Dense C7 and Joung e0 forests already running continue unchanged. This is a storage change; no extra real-data comparison run or hyperparameter candidate is introduced. Four new fixture contracts passed, including the role/gas layout and a same-parameter RF case.

The current corrected NMR RF/LightGBM handle is4537322, superseding unstarted4537318. New optical RF handles are4537323–4537330. Native queue ordering uses after:4537322 for the27 formerly held CPU jobs: their user holds have already been released, and their dependencies clear when the corrected NMR job starts, without waiting for its forest to finish. Only originally satisfied source dependencies were replaced by this scheduling order; other windows and running jobs remain unchanged.

### Conditional finalization

confirmation_dispatch.py groups only required original dataset/task/configuration bindings; completed NMR1H confirmation4537338 is reused. Source preparation runs on CPU, preserves frozen folds and original model budgets, and changes only the neural model seed to20261026. confirmation_consumer.py checks the unchanged candidate TEST/labels/folds/native missingness and actual TRAIN means before producing first-time seed2 statistics. Existing seed1 control predictions retain their seed20261025 in confirmation contrasts.

finalization.py copies original primary estimates into the final table and adds separate seed2 rows. It explicitly reports reproduced significance, nonreplication, or a documented native failure without changing the frozen B1 role. Missing required confirmations cannot finalize a table. Traditional ML receives no second seed. final_results_export.sbatch remains unsubmitted until actual conditional report evidence closes; only its final C1 table receives a SHA.
