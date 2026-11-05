# 构象统计：实际有界试点

状态：**D7 全共同人群报告尚未完成**。以下仅为2026-10-25实际256个完整分子的只读试点，非总体估计；不会因本报告冻结common或训练构象顺序。

准备job4520383实际COMPLETED0/180s/16CPU；统计job4520390实际COMPLETED0/40s/16CPU。原PM7记录1,344条。没有嵌入、优化或量化调用，没有修改原数据。

试点限定至多16个canonical owner jobs，先覆盖原来源角色、大小和N分层，再固定hash抽样；存在I/O与来源选择偏差。角色仍为原TRAIN/FULL，尚非最终TRAIN＋ROUTINE VAL共同人群。

## 原子映射与去重定义

PM7和S′均按固定源重原子索引、proper Kabsch、0.5 Å RMSD判重，不进行反射、对称原子置换或原子重排。两侧均按seed20261025的固定随机顺序做贪心判重。来源图、原子序、立体化学检查错误为0；逐分子坐标摘要、三种顺序、代表ID和全交叉RMSD保存在外部压缩JSON。

配置与代码使用16进程池；当前receipt未保存每个实际worker PID/任务数，故不把配置16声明为16 distinct PID实测证据。正式统计需补上这一观测。

## 不重复构象数

|不重复数|PM7分子数|S′分子数|
|---:|---:|---:|
|1|107|59|
|2|36|24|
|3|24|20|
|4|16|17|
|5|15|35|
|6|10|9|
|7|23|7|
|8|12|3|
|9|9|13|
|10|4|69|

|达到的构象数|PM7比例|S′比例|
|---|---:|---:|
|≥2|58.203125%|76.953125%|
|≥5|28.515625%|53.125000%|
|≥10|1.562500%|26.953125%|

PM7含重复构象的分子占52.734375%；重复构象占原构象38.392857%。S′对应重复构象比例0.000000%。这是本试点、指定贪心顺序下的比例，不能外推为全量优化收敛比例。

## 构象数相关性

|相关性|Spearman ρ|有效分子数|
|---|---:|---:|
|pm7_unique_vs_heavy_atoms|0.079178410|256|
|pm7_unique_vs_rings|0.158996178|256|
|pm7_unique_vs_rotatable_bonds|0.078242901|256|
|uff_sprime_unique_vs_heavy_atoms|-0.004213718|256|
|uff_sprime_unique_vs_rings|-0.041988239|256|
|uff_sprime_unique_vs_rotatable_bonds|0.021018222|256|

## PM7生成热范围和PM7—S′交叉RMSD

256个分子的全部PM7几何均取得canonical pm7_B registry60/kind1/f64生成热，单位kcal/mol。按record/molecule/attempt/job/task五键、lane及原子数核对，未使用native energy替代；缺失原因计数为空，NULL收敛review记录0。

|分位百分数|分子内生成热范围（kcal/mol）|全部PM7—S′构象对RMSD（Å）|
|---:|---:|---:|
|0|0|0.0211090193|
|25|0|1.35455804|
|50|1.03836|2.16388706|
|75|5.975265|3.57498353|
|90|12.022095|5.54092905|
|95|18.8836475|7.1090026|
|99|49.620854|11.8568963|
|100|89.61673|18.7616745|

交叉RMSD按本试点全部构象对汇集，构象较多的分子贡献更多pair；不是按分子等权的分位数。生成热范围分位数则每分子贡献一个范围。三种顺序以原几何ID保存，能量／最低能起点多样性本试点HOF完整；最终训练排序仍等待全common覆盖。

## 原始N规则的历史来源

**未找到**原始PM7首次决定每个分子构象数的明确生成策略。检索仅覆盖配置指定的legacy、dataset_rebuild及历史服务器源码；导入器读取既有构象、WP0统计既有ID、S′复制既有PM7 N，都不能证明原始N公式。不从可旋转键相关性推测。各文件路径/SHA、命中行和截断记录见外部history_search.json。

## 证据和复现

以下路径相对外部run根；统计由prepare_profile.py和run_profile.py实际计算，本文件由render_report.py读取已闭合小型JSON生成，不重新处理科学正文。

- `artifacts/conformers/statistics_v1/prepared_v1/prepared.json`、`history_search.json`
- `artifacts/conformers/statistics_v1/profile_v1/receipt.json`、`profile_statistics.json`、`molecule_manifest.json`、`errors.json`
- `control/d7_profile_preparation_actual_closure_v1.json`、`control/d7_profile_actual_closure_v1.json`

统计JSON：2598B，SHA256 `517e0969088bdfb95a1b1f2cb5d95fab36739d01445876f9debe33e213fc4fae`。

复现渲染：`python -B workflows/data_v1_final/conformers/statistics_v1/render_report.py --run-root <外部run根> --output <新的报告路径>`。渲染拒绝覆盖；原科学数据只读。
