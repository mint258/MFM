# ROUTINE 分子验证集：角色冻结任务

状态：实现与定向边界自测已准备；实际Slurm角色冻结尚未执行或验收。用户最新决定为ROUTINE用作VAL，先前从TRAIN整家族划分的方案已被替代。

## 目的

从既有ROUTINE成员提取分子级VAL角色，保留原TRAIN/FULL来源和原11,322条record成员，不复制11,231,854条记录总表。后续PM7、S′及P/Pprime条件均按同一molecule_id角色连接。

## 输入及哈希

完整精确pins在 configs/data_v1/export/routine_roles_v1.json，实际任务对六份输入核SHA256与字节数，并与原training manifest/population binding及用户决定交叉核对：

|输入|bytes|SHA256|
|---|---:|---|
|WP5 population/manifest.json|6767|d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e|
|S training_inputs_v1/manifest.json|4238|2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997|
|S prepared/population_binding.json|2116|b57343f575cf4b600a17dba416a234d1f93aab1839e2435091f790ce87686dbd|
|WP5 population/molecule_index.parquet|8822311|360ee138bb717449dfa0fe4f0cfed8622e12cb9c46ceadf9bb95354b996cb063|
|S training_inputs_v1/routine.arrow|2636514|29b153bd734dba010035af83cc76d80447c85b17c3da953cb77f2da1713e7e58|
|用户run_decisions_v2.json|1940|f62f3938f3449a652dfa4f02b5dfc667f9e8f3efaecda73911828b582815fec2|

角色任务不读取1.24GB的formal_record_index，不打开原LMDB或科学family parquet。molecule_index仅投影molecule_id、records、split、original_routine、component_id、file_group。

## 规则和参数

- 精确检查ROUTINE为11,322个唯一record_id、7,610个唯一molecule_id、原member_routine全部true。
- 这7,610个分子必须在molecule_index中恰好各出现一次，source split全部full；按整个分子指定effective_role=VAL。原TRAIN 1,206,608个分子／11,104,772条记录保持；其他FULL分子保留FULL。
- 原11322条record另输出legacy_routine_records.parquet，标记legacy_routine_member；它不限制VAL的全部构象数量。
- 直接检查TRAIN/VAL molecule ID及已计算identity component无交叉。molecule_index没有字面完整InChIKey或骨架/质子化key，因此三路身份零交叉仅明确继承已绑定WP5 manifest的TRAIN/FULL identity_checks，不宣称新的全record化学身份重扫。
- source_role、source_split、原record计数与component ID均保留。被原authority排除的490个分子／4900条记录继续处于embargo，不加入角色表。
- 16个spawn worker各处理一份互不重叠的Arrow slice。barrier确保16个worker真实参与；每worker写独立shard，记录PID、start time、耗时、最大RSS。关闭pool后逐PID/start time确认实际退出。
- 新角色表是共同人群筛选之前的来源角色；最终共同人群的VAL数须等S′补齐和有效性规则后另算。

## 运行入口及预算

Root统一审核并提交，不由子agent提交。

~~~bash
python workflows/data_v1_final/export/freeze_routine_roles.py \
  --config configs/data_v1/export/routine_roles_v1.json \
  --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/roles/routine_v1_job<job_id>
~~~

Slurm模板为 workflows/data_v1_final/export/freeze_routine_roles_v1.sbatch，使用既有all分区、compute-0-20、16CPU、32GiB、1小时；显式禁用可见CUDA设备。模板使用chemprop Python及已核验依赖overlay；source SHA和配置由Root提交审阅清单绑定。

只读输入约11.5MB；预计聚合RSS低于4GiB，实际值待实测。申请32GiB，记录worker处理期间0.2秒采样的自有进程总RSS，并以24GiB采样上限校验；该采样不是瞬时精确峰，另记父进程全任务MaxRSS和各worker MaxRSS。

输出硬预算128MiB。每个分片在编码后检查不超过4MiB，两个附加parquet各不超过16MiB，JSON各不超过1MiB；最终实测总量再次核对。所有输出只写全新外部目录，保留失败证据，不删除已有文件。

## 输出与验收

外部输出包含16个molecule_roles/part-*.parquet、validation_molecules.parquet、legacy_routine_records.parquet及manifest.json。manifest保存所有输入/源码/配置/输出SHA、实际有效角色计数、sorted-ID摘要、16个worker统计、退出核验、RSS与耗时。

实际VAL所有PM7 record总数由molecule_index.records汇总，而非提前假定为11,322。任务输出记录数、分子数和分片footer需守恒；所有PM7/S′几何在后续导出按此molecule roles连接。manifest未闭合前不能将候选配置称为已冻结角色。

## 异常及已知限制

compute20的定向边界自测已实际退出0：整个分子及7条来源记录保持VAL、ROUTINE误入TRAIN拒绝、跨TRAIN/VAL identity component拒绝、排序ID摘要稳定。真实16进程运行与数据输出仍须由实际Slurm任务验收，单元自测不代替它。

任务保留错误JSON及部分输出，不自动重试或修改原清单。原ROUTINE过去已用于监控；本轮继续使用的是用户明确指定的验证来源，不声称它是从未使用过的盲测集。下游去污染、新字段掩码、共同人群验收、训练导出及归一化均另行执行。

## 实际作业闭合（2026-10-25）

作业4520334在compute-0-20实际COMPLETED/0:0，16CPU×23秒=368分配核秒（0.102222核时）。16个并行worker均真实退出；18个输出文件全部SHA读回匹配。总输出11,798,874B。

最终角色：TRAIN 1,206,608分子/11,104,772记录；VAL 7,610分子/72,525完整PM7构象；剩余FULL 6,248分子/54,557记录。原ROUTINE 11,322条记录另保留legacy_routine_member。TRAIN–VAL分子ID及预计算身份component交叉均为0；原始字面化学键零交叉明确继承WP5验收，不冒充本次重扫。

实际manifest：roles/routine_v1_job4520334/manifest.json，SHA256 16619f25f2bec53ed2d3c5e8e8381faa746e03f141d9fba87f93b6ec1e8ef8a1。Root收尾证据为仓库外control/routine_roles_actual_closure_v1.json。供后续计划消费的角色适配契约为configs/data_v1/export/roles_authority_v1.json；仅角色FROZEN，共同人群、diagnostic和最终归一化尚未冻结。
