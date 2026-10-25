# D7只读构象统计：有界profile v1

本阶段只读已有PM7及已验收S′，不嵌入、不优化、不量化、不创建LMDB。独立新目录不改变已登记的336分子试点及32G执行源。当前为256个完整分子的成本/正确性profile，不能称D7全人群完成；最终TRAIN+ROUTINE VAL共同人群统计等待冻结角色和补齐人口。

## 输入与权威

配置为 configs/data_v1/conformers/statistics_profile_v1.json。正式人口通过实际job4520356的3485B小receipt绑定，含1.24GB索引真实SHA和设备/inode/mtime/UID，compute20核物理身份；Root登录guard不哈希该大表。latest owner通过job4520341的9941B owner_receipt绑定其本轮observed 30,233,309B SHA c6ea21ab66b62415011fb71f475a803c895418d5a8b69a31302d7ac3805c1d80；这不是冒称旧catalog内嵌SHA。闭合catalog、D20-aware最终verification和pm7文件projection通过SB3的1189B projection_receipt绑定。

Root source_references只列新代码、配置、冻结的父common/selection、两份旧science源和上述小receipt/manifest；不直接列formal大parquet、pm7 family或LMDB。配置内metadata_data_pins只由compute20验证。现有S′全文件SHA由闭合manifest继承，实际检索前后核size/identity，所选坐标在运行阶段逐条核geometry/atom-order/stereo。

## 准备与统计

prepare_profile.py 从PM7完整、S′ SUCCESS且严格可用数=N的原TRAIN/FULL分子中选256个。先贪心选择至多16个owner jobs覆盖原角色/重原子数/N分层，按可覆盖的新层数、分子数和job ID稳定破同分，再在这些jobs中按层固定hash选样；若16个job仍未覆盖所有层，报告未覆盖清单。这个job上限是显式I/O界限，存在选择偏差；本profile不是均匀全人口调查。

HOF仅取canonical pm7_B的registry60/kind1/f64，单位kcal/mol。按record_id、molecule_id、attempt_id、job_id、task_id五键精确匹配latest owner，并核lane和原子数。只投影values的registry_id/kind/f64叶，拒绝读取数组和text大列；缺字段不退回读取整个values。SUCCESS或PROPERTY_FAILED只要HOF自身有限且无numeric issue即保留；converged=False无效，NULL保留并标人工review。这个最小可读性QC不替代SB3最终全人群mask。

run_profile.py 用16个spawn workers只读源LMDB，逐payload SHA校验；使用S′原source_record_id锚定来源图，核全部PM7的z序列/有序图，不重新编号原子。S′核原atom-order SHA、source anchor、原立体签名及实际几何立体；图继承自闭合来源及同原子映射，不用另一个3D bond猜测器改变图。

RMSD完全复用固定旧sprime_v6函数：源重原子固定索引、proper Kabsch，无反射或对称原子重排。唯一构象数统一按固定随机顺序贪心0.5Å去重；PM7和S′采用同一个顺序规则。该选择顺序被明确记录，不能与未说明顺序的聚类数混用。输出唯一数直方图、≥2/5/10比例、PM7重复构象和有重复分子比例、PM7–S′全交叉RMSD分位数、与heavy atoms/rotatable bonds/rings的Spearman，以及canonical HOF范围。常数相关向量输出null和原因，不伪造0。

三种顺序直接复用冻结selection：random seed20261025的stable_key，与P′前k规则一致；energy升序按ID稳定破同分；diversity从最低能量开始贪心maxmin，距离同分按能量/ID。PM7有缺失HOF时仍保留全部几何和随机顺序，只将能量/最低能起点多样性顺序标为不可用，不拿native energy顶替；HOF范围同时报告有效数和是否完整。S′使用原UFF能量。

## 运行接口与预算

两阶段均由Root使用原analysis提交守卫统一提交到compute-0-20，不申请GPU。建议每阶段16CPU/32GiB/2h（各最多32分配核时，非实测预测），每阶段新增输出cap=1GiB，真实账户剩余保持≥200GB。旧336分子32G内存例外不适用本分析任务；沿用正常全部用户声明内存85%准入。

先准备：

    /share/home/zixiao/.conda/envs/chemprop/bin/python /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/statistics_v1/prepare_profile.py --config /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/statistics_profile_v1.json --root-preflight /absolute/dv1_d7_prepare.intent.json --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/statistics_v1/prepared_v1

再运行：

    /share/home/zixiao/.conda/envs/chemprop/bin/python /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/statistics_v1/run_profile.py --config /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/statistics_profile_v1.json --prepared /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/statistics_v1/prepared_v1 --root-preflight /absolute/dv1_d7_profile.intent.json --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/statistics_v1/profile_v1

实际解释器为已有chemprop Python；Root渲染SBATCH时设置PYTHONDONTWRITEBYTECODE=1、OMP/BLAS=1、CUDA_VISIBLE_DEVICES为空。config、prepared及输出均有SHA绑定；所有新路径拒绝覆盖。实际AllocCPUS×ElapsedRaw、MaxRSS和I/O由Root在终态闭合后附入，不把提出的墙钟上限称为实测成本。

prepared.json schema状态为D7_PROFILE_PREPARED_NO_GEOMETRY_COMPUTED，含config/root_intent、所选分子/原record owners、HOF source投影列、before/after身份、历史N来源检索和tasks.jsonl SHA。每个task携带完整PM7指针、原可用S′坐标和canonical HOF状态，不含pickle。

run输出逐分子压缩JSON（源角色、原始与唯一数、canonical HOF逐record状态、交叉RMSD矩阵/两侧ID、三种顺序、代表构象ID、原子/图/几何SHA）、profile_statistics.json、errors.json、molecule_manifest.json、receipt.json。partial失败完整列出，不能升级为全人口完成；图/身份不一致不做自动修复或重试。

## 历史N策略

prepare在配置列出的legacy、dataset_rebuild及明确历史路径作有界源码检索，保存每文件绝对路径、SHA、命中行号/文本和截断计数。已知build_lmdb是已有优化XYZ的导入器，wp0_inventory统计已有conformer_id；S′ full_dataset复制已有PM7 N，不是原PM7首次N生成策略。当前检索范围未建立原始N规则；未找到就报告“未找到”，不能由rotatable相关性推断公式，也不能声称搜遍服务器。

## meaningful tests

    python workflows/data_v1_final/conformers/statistics_v1/test_profile.py -v

15个合成tests验证proper旋转/平移、拒反射和原子置换、0.5Å边界、与P′一致的固定随机顺序、缺HOF不删几何/不造能量、多样性最低能起点、HOF字段级失败与NULL收敛语义、Arrow叶投影确实不读array/text、完整owner过滤历史、错lane和重复canonical记录拒绝。只读冻结源码和合成临时parquet，不读实际LMDB、不调用UFF/QM。实际profile仍须Root提交并验收。
