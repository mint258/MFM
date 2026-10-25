# 首次 mask I/O 试点：自动构建 canonical owners

`prepare_owner_manifest.py` 补齐旧草案中需要外部提供 owner records 的入口。无需手工造 manifest，也不打开原 LMDB。该步骤与 mask 扫描均为 CPU `analysis`，按当前 AGENTS 在 compute-0-20 运行；量化/P′计算及UFF生成仍限定14–19。此次执行角色修正不改变标签来源、mask阈值或科学结果。

## 准备任务

Root 将 `prepare_owner_manifest.sbatch.in` 物化成新LF脚本，填入日志、即将创建的 Root intent 和新的外部目录。默认16CPU、32GiB、1小时、partition=all、node20，CUDA可见设备为空。

统一提交请求使用 `kind=analysis`、`pilot=true`，`estimated_peak_output_bytes>=4294967296`。source references 至少绑定 `owner_pilot_v1.json`、`prepare_owner_manifest.py`、`common.py`、`prepare_pilot_plan.py`、`test_prepare_owner_manifest.py`。脚本内先运行8个语义测试，再运行生产准备；实际运行和记账一律由Root处理。

生产配置在 `configs/data_v1/labels/owner_pilot_v1.json`，已经填好全部来源路径及已知 SHA。ROUTINE角色权威为 job4520334 的 manifest，22642字节，SHA256 `16619f25f2bec53ed2d3c5e8e8381faa746e03f141d9fba87f93b6ec1e8ef8a1`。

程序自动执行：

1. 验证16个角色分片及TRAIN1206608分子/11104772记录、VAL7610分子/72525记录、剩余FULL6248分子/54557记录。TRAIN不重新抽分组。
2. 将角色、严格S′计数和 latest COMPLETE owner 联接，要求receipt一致且已发布。只保留TRAIN或VAL中PM7完整、S′状态SUCCESS且严格成功并收敛的构象数不少于PM7全记录数的分子。
3. 优先科学标签 family 容器总字节最少的单个owner job；其内部用固定seed和molecule_id排序，完整选择32–128条记录，默认目标64。绝不截断分子。标签容器预估投影上限8GiB，base_geometry容器上限1GiB。
4. 从原authority population投影这些分子的全部记录，逐分子核对期望构象数；在该owner的base_geometry投影 atomic_numbers、geometry status、source payload SHA和native atom order SHA。核对record/owner/natom，按little-endian int64重算原子序SHA。

小型冻结输入实际重算SHA；原population的完整SHA继承SHA绑定的WP5 authority，读取前后核对身份。latest_molecules是catalog指定的小型元数据索引，运行时记录实际SHA并核对前后身份。base_geometry完整SHA继承最终全量读回，实际选中行再做上面所列核验，不重新hash整个科学容器。

## 输出与边界

`owner_records.parquet` 兼容canonical reader的record/molecule/attempt/job/task、lane、total_atoms、new_role、common标记与atomic_numbers。`common_population_v1=true` 明确仅表示这些试点分子经过local strict common检查，不表示全体共同人群已冻结。`common_population_scope`保存此范围。

所有记录的 `training_eligible=false`，原因是最终diagnostic geometry排除尚未冻结。它们只用于标签I/O和mask试点，不能误用为训练清单或归一化输入。

另保存selected_molecules、该owner的label_source_files、已绑定的mask_plan、Root quota证据投影及owner_receipt。失败证据保留，无删除行为。

身份表述保持原证据边界：molecule ID与既有component的TRAIN/VAL交叉为本次已冻结结果中的直接零交叉；literal化学key零交叉继承原WP5 TRAIN/FULL验收，本步骤不声称重新扫描了literal key，也不声称对未来下游数据集完成去污染。

## 最小 mask 任务

Root确认owner_receipt状态和32–128条完整记录后，将 `mask_io_pilot.sbatch.in` 物化为第二个新脚本。仍是 `kind=analysis`、node20、16CPU、32GiB、最长1小时，不申请GPU。source references 至少包括owner_receipt、run_mask_io.py、prepare_owner_manifest.py、canonical_reader.py、pilot_masks.py、common.py及被继承的mask rules/registry。

请求峰值预算至少为mask_plan.storage_budget.total_declared_new_bytes，即默认8GiB＋64MiB。新的Root intent重新核验当时全部用户声明内存与实际账户quota。

`run_mask_io.py` 核验不可变owner receipt的所有输出引用，消费这次mask job的新鲜Root intent，在新run目录派生runtime_plan，仅刷新quota证据及记录派生关系；不改旧owner plan。随后调用既有16-worker pilot。不会因为准备任务或排队超过一小时而沿用过期quota快照。

实际结果在新run的`results/pilot_report.json`及wrapper_receipt中。任一字段新增mask比例>1%保留原停止规则并退出2。首先验收实际I/O、内存、退出状态、canonical coverage和新增mask原因，再决定下一试点规模。没有把准备成功、8个合成测试或元数据源数量当成科学mask通过。
