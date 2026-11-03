# D27 1885189：独立小元数据与应用域审阅记录

记录日期：2026-11-04。本文是给 Root 的独立来源、字段与域说明，**不是 Root acceptance，不新增审批层，也不宣称新 UFF 250 万分子或全部生产质量已验收**。Parent 报告实际 Alpha 作业 1885189 C0、1807 秒、16 CPU；本次未另查终态账本，终态采用由 Root 另行绑定实际 accounting/raw sacct。

## 本次实际读取与校验范围

Alpha 根：`/gfshome/alpha/pubchem_expansion_20261103/exact/d27_fullCommon_train_v2_job_1885189`。参考子目录：`reference_17cea5fda35c451fad4eaed91a616692`。本次仅远程读取/复制小 JSON 和小源码至本机临时元数据目录，用 stdlib 核 SHA/字段/守恒；没有重新读取 10.55 GB typed bodies、canonical SQLite 或几何文件，也没有拟合、生成构象、提交作业或写验收。

实际读取的四份参考 JSON、coverage、eligibility 的本次 SHA：

| 文件 | 字节 | SHA256 |
|---|---:|---|
| receipt.json | 3031 | `798d72e4c2cae27184bebde8741987876d9d7730390edca51fbdce23edd76e8b` |
| calibration.json | 10668 | `589677c7adf7d627c8587cf07eaf9ffd43b290926959908a698d374dbd1ddb19` |
| domain.json | 4917 | `d293968d77aafcc24b8be7a3f66f4a262ba3e4ec376fca7c3a249c9ec4e91504` |
| review.proposed.json | 1882 | `80ee7fa5933a08a88cdf81ef340bcde130672b3b3ab670599fb0467399cfedd9` |
| coverage.json | 50248 | `53f6ae7ba18d3fbc46fe8e93d8489f7798fc2d4bbfb19eaa5038d0a89287a6ce` |
| eligibility.json | 14904 | `d18721c46d0bdf730348553a58761a85fcb923b05fecf6ff7d90b04c6a1744e1` |

另逐文件核了以下 27 份实际 field manifest：共 **100151 字节**，IDs 0..26 恰一次，记录 **16 个不同 worker PID**。每份 median/MAD/TRAIN_n/MAD_n 均逐值匹配 calibration，scope fingerprint 同为 `f036ac1284ec4f0f3aee4d18bcca8ee165eafcb902b39ef99ae23c3c810118c9`；每字段 **7 次 median + 7 次 MAD**，14 次输入 F64 SHA 完全相同，input_leaves 恒等于 TRAIN_n。它们声明使用原 RadixCounts/advance；该声明与已审 producer 的直接函数对象绑定和 Root 的 actual Source4/C0 证据结合使用，不把本次小元数据核检冒充重新跑全数据。

| ID | 原字段 | 冻结单位 | TRAIN_n = MAD_n | median | MAD | 实际 field manifest SHA256 |
|---:|---|---|---:|---:|---:|---|
| 0 | D20.BertzCT | dimensionless | 10953084 | 841.15234375 | 250.38043212890625 | `95517a74675ff4ff8a4b289de03fecf1afd47041277b31e743805ea8c62a1464` |
| 1 | D20.ExactMolWt | Da | 10953084 | 381.2335205078125 | 67.19015502929688 | `f22bc9965be47c60a23023a56dae2118992856bdebbbf91cf144b840ab55b843` |
| 2 | D20.FractionCSP3 | dimensionless | 10953084 | 0.375 | 0.1634615659713745 | `8201ed23f95f8b686ec284c118baba6648ed4b5f51e679a883fbf2764ea0617d` |
| 3 | D20.HallKierAlpha | dimensionless | 10953084 | -2.309999942779541 | 0.7799999713897705 | `39fda4ff28b6933c7747c31ace11051e1e2d777ddf31763f548032e1574b93cf` |
| 4 | D20.HeavyAtomCount | count | 10953084 | 26.0 | 5.0 | `8c67aac23a56e5d787b88c1b97caa17a891c690223f459f8fdc6a6e318dde545` |
| 5 | D20.LabuteASA | A^2 | 10953084 | 158.54335021972656 | 27.875640869140625 | `77571cc7628036aba7317c075fccc8a92be5850031b75f004dfaac47360668a5` |
| 6 | D20.MolLogP | dimensionless | 10953084 | 3.7596399784088135 | 1.261080026626587 | `da8696345dd72ed79d9c1a235e0c318a154564684f0c87f8fda30258b11e16a6` |
| 7 | D20.MolMR | 旧 schema 未宣告物理单位 | 10953084 | 104.16110229492188 | 19.00859832763672 | `26560c1e7d1e964d687d47b8b78f6e6a80f2566b25148eca29bd00360e521472` |
| 8 | D20.NumAliphaticRings | count | 10953084 | 1.0 | 1.0 | `249e6eb212f38d2382099096670ad3b6ccd14670b4ee7434f8fbd2c2221b1472` |
| 9 | D20.NumAromaticRings | count | 10953084 | 2.0 | 1.0 | `8584b8dd30cc72812216d7b3da1af85d26e64d2eced45eb7b309f7836ff94225` |
| 10 | D20.NumBridgeheadAtoms | count | 10953084 | 0.0 | 0.0 | `5cac7a9659bb771ec43d567a700e9a2520f2eeb30338cd850943cb4efaac9130` |
| 11 | D20.NumHAcceptors | count | 10953084 | 4.0 | 1.0 | `889b051c6ffbf0651fef7ab76c8b71a99366a7af9ef31300e19ce7d76cd97ab9` |
| 12 | D20.NumHDonors | count | 10953084 | 1.0 | 1.0 | `e3cbd84918e5470fe553bf9f165f9e352b9c683bc821eb034336d69363e3ad15` |
| 13 | D20.NumHeteroatoms | count | 10953084 | 7.0 | 2.0 | `a525a738d6cc0ba0b6718c004890f9c0b31d9bc35ddef7745192abc18943b8c8` |
| 14 | D20.NumHeterocycles | count | 10953084 | 1.0 | 1.0 | `d3f2afe212092367f3c545da8befa0051014b8a0942ff9e0b03fc6f475599a46` |
| 15 | D20.NumSaturatedRings | count | 10953084 | 0.0 | 0.0 | `e515a52e02b764669b9d7fae397bc96234b32426ef92a9b448feb309db4da4a9` |
| 16 | D20.NumSpiroAtoms | count | 10953084 | 0.0 | 0.0 | `0fe8e9dee0f953062ad63fafb787b2a582beec81ff3820d37c1ae320d3e844bd` |
| 17 | D20.NumValenceElectrons | count | 10953084 | 140.0 | 24.0 | `9f5a465782120f45fc78030609f4742469581241b20773ebdd51248d167b183b` |
| 18 | D20.RingCount | count | 10953084 | 3.0 | 1.0 | `dffaea704d54abca114436ea2529e3293133cbba0d4dcb6d0b8c54c5d9eed116` |
| 19 | D20.TPSA | A^2 | 10953084 | 66.4000015258789 | 20.220001220703125 | `3cf6248cf238153acb4d641b10df9028f4cd4e2798a884eea09efd9172bd216b` |
| 20 | D3.PBF_A | A | 10953084 | 1.022226870266027 | 0.1854396949234569 | `9f71071b2c24fd8607e53646030a62fcd0a7f95ed1356ef2b02b09d2a056f013` |
| 21 | D3.PMI1 | Da A^2 | 10953084 | 1548.446853235289 | 729.199503539716 | `9a7661870b36ecea7cb0a7bfe962ae521ced646ed8ce380028142955b2a787d2` |
| 22 | D3.PMI2 | Da A^2 | 10953084 | 5812.365373115654 | 2454.925844274676 | `57a0d9c3c27d97582d4f92bd46c7bb20c43cee6e19a756ee5ec36bae1dd7a682` |
| 23 | D3.PMI3 | Da A^2 | 10953084 | 6717.867966908524 | 2718.9216140293884 | `0302422f1fc99d440256f7abc2454ad5807559b755d2d05a46bade0acafb7fd7` |
| 24 | D3.SASA_atom_A2 | A^2 | 580397586 | 11.11837462840625 | 7.501901856809434 | `73f053b00ee3644ddc5da521a563334b88dd233f9ee0ca96a123c67e489ccb00` |
| 25 | D3.SASA_total_A2 | A^2 | 10953084 | 634.2397705265416 | 81.79547106802607 | `b0c9091b4b4a752655b360d27ee0c94f58b4fd8e9bc4937fa0e4565dfad633fa` |
| 26 | D3.volume_A3 | A^3 | 10953084 | 345.1120000000001 | 60.06400000000002 | `01a56ae9f6ee4a28e3c1c2097af307bcdef3fbd34efc680ecafee28bbca3b66f` |

字段文件的实际原路径、字节与 SHA 均由 calibration.field_statistics_references 固定；所有下载文件均按该引用逐 SHA 对照。

## 全体来源、TRAIN 与诊断排除

coverage 记录 171 个完整原逻辑组、11,231,854 条 canonical 记录、22,463,708 条 D20/D3 task rows；声明每族每 canonical key 恰一次，原 typed part 全 SHA/stream/row signature 已重开，旧 55k authority 没有作为全体释放。该计数是全体 source coverage，不是只覆盖所拟合的 TRAIN。

eligibility 中 `FIT=10,953,084`、`D5_HELD_BASE=20,000`，合为 Common TRAIN 原 native records **10,973,084**。其余 `ROLE_FULL=54,557`、`ROLE_VAL=72,525`、`OUTSIDE_COMMON=131,688` 与前两者合为 11,231,854；OUTSIDE_COMMON 对应原 TRAIN 11,104,772 减 Common TRAIN 10,973,084。Common role molecule census 是 TRAIN 1,188,592、VAL 7,530。

D5 采用真实旧组件的 20,000 分子 / 40,000 PM7+UFF diagnostic bases / 280,000 targets，独立恢复并精确排除 20,000 PM7 native keys；不是删掉 20,000 个分子，也没有重选诊断集。D27 是原 base task 标签，没有凭空增加 perturbed-child D 标签。旧 D5 provisional delivery / 原 Main 4525184 真实 C0 provenance 保留；没有把它重标为新 full-Common D5 release，也未重开 3.278 GB historical binding SQLite。

## 函数、字段映射和权重

冻结 field_map SHA `92bab06f489396483e3a0a3a215369cc59635cfdad8852aa47b7235e37ea9141`。ID 0..19 按字段名排，不是 raw D20 vector 的位置：例如 ID0 是 BertzCT，而 vector 首项是 MolLogP。原 `labels/common.py:task_components` 通过 source_path/name 查 D20_NAMES 索引；新质量路径复用它，不能按 field_id 与 vector 直接 zip。集合恰为原 D20（不含 Kappa1/2/3），D3 恰为 PBF_A、PMI1/2/3、atom/total SASA、volume，未添加 NPR/回转半径等其他指标。

D20 通过原 GRAPH_DESCRIPTOR_SPECS 的对应 2D 函数对象计算；HBA 是 Lipinski.NumHAcceptors，匹配原 corrected_base 的修正语义。新 Graph D20 每新分子只算一次是生成规则；本参考仍保持原统计的 **canonical PM7 record-frequency weighting**，不把旧 TRAIN 去重成一分子一票。26 个 molecular scalar 各有 10,953,084 个有效训练值，atom SASA 则汇总 **580,397,586 个有效原子叶子**，恰等于 eligibility.fit_atom_upper_bound。包括显式氢的原子顺序与 total_atoms 由原 codec/owner 约束；不存在把 atom SASA 当一个分子标量的平均权重。

原 wire：`/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/scripts/c_engineering_wire.py`，本次 Main 小源码实际 SHA：`ce9bbdf15459e647fc21592941c99664141b7d7a4442619f433c88a3536d99a1`。原 generator 当前源码 SHA：`86a3c5b8181d25c6b892bedb3ac599fbd3e643d3aede19b0b38edb03ed0469d9`。对照当前 `uff3_candidate_v1/native.py:d3/compare_original_wire` 与 `portable_sources_v1/kernel.py`：

- PMI1/2/3、PBF 调用相同 RDKit Descriptors3D API；原 wire 元数据明确 principal moments 使用原子质量、PM7 原 S 坐标，PBF 单位 Å。输出 PBF→PBF_A 仅按字段名对接。
- volume 同为 ComputeMolVolume(gridSpacing=0.2, boxMargin=2.0)，单位 Å³。
- SASA 同为 LeeRichards / Protor、RDKit periodic-table VDW radii、1.4 Å solvent probe，保留显式 H；total 和 atom 均 Å²。旧 wire 的 atom/edge 对齐检查与新实际坐标 seam 比较不能由“元素序列相同”代替。
- 独立 actual-coordinate wire seam 的机制及既有小分子 native smoke 支持实现一致性，但不能表述为已验证全部新 250 万分子/全部未来 UFF 坐标。

**MolMR 特例必须保留说明**：原 fmap 的精确 unit 字符串为 `molar refractivity; frozen schema does not declare a unit`。本次能确认同一 Crippen.MolMR 函数和原数值约定，不能自行补写一个已确认的物理单位或施加换算。D20.LabuteASA 是原图描述符的面积估计，与 D3.SASA_total 即使同为 Å² 也不是同一字段。

## 掩码、零 MAD 与原始精度

每字段全体 denominator 均 11,231,854、fit_records 均 10,953,084；全体 source_ineligible_records 均 **957**，newly_masked_records=0、final false-mask records=0、review_records=0。D20 source reason 为 SOURCE_VALID_MASK_FALSE，D3 为 SOURCE_D3_FAILURE_ISSUE。空叶 source NA 不混算为新增物理掩码；957 不能被写成“新增掩码 957”。结合每记录 scalar 最大一叶、atom 最大 total_atoms 的 producer 约束及全部 TRAIN_n，拟合集合没有这类缺失叶质量。

原 masks.source_value_mask / 原 cross-field / sparse mask parity 保留；D27 的原 cross-field helper 不会凭空套用 PM7 charged-state IP/EA 或 charge-sum 条件。coverage 的旧 review 计数为零，不代表已用这次新 median/MAD 对全体原 TRAIN 或新 UFF 完成 robust-outlier review。

零 MAD 是真实结果：ID10 NumBridgeheadAtoms、ID15 NumSaturatedRings、ID16 NumSpiroAtoms 的 median=MAD=0。原 scan_v2.add_reference_reviews 对非零偏离给 ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY，不换成 scale1。正常 MAD 用 0.6744897501960817*|x-median|/MAD；原子字段以该记录内最大有效叶偏差给 record-level review，>20 仅加 ROBUST_Z_GT20_REVIEW_ONLY；不由此自动改 value_mask。此次扩充的 1% 是 canonical-record fraction 的报告触发，保留 source NA / 新掩码 / final mask 分离，不删记录、不自动停全部候选发布。

历史 D20 值可见 F32 后提升的精度（如 HallKierAlpha median=-2.309999942779541、TPSA median=66.4000015258789）；F64 存储/精确 radix 统计不会恢复丢失的小数。新 D20 用原函数输出的 F64，与该历史基准存在精度差异，domain 已如实披露，不能宣称旧源重新变成原生 F64。

## 可支持的应用范围与尚未完成事项

这是真正 full Common TRAIN、精确 D5 排除后得到的原 PM7 S 来源 27 字段 median/MAD；不是原 50k provisional 的放大或重标。S 是原 PM7 geometry；新 S-prime 是 UFF geometry。即使 D3 函数/参数/单位相同，坐标分布和新 PubChem R/N 化学分布仍不同。Root 的应用说明应明确该域差异、记录/原子权重及历史精度，并保持固定 TRAIN 参考，仅用于原规则的 robust review；**禁止用新 R/N 重新拟合或自动把域外 z-score 当错误标签删除/掩码**。

仍需 Root 以实际189 terminal accounting/raw 绑定现有 APP-reference 状态并作域说明；本笔记不是它。真实新 UFF 10k pilot、实际最多3构象/不足保留、全 250 万输出、物理/跨字段/robust review 分布、1%逐记录报告及其实际 C0/QA 仍分别以未来真实结果判断。这里既没有这些数据，也不以 tiny seam smoke 代替它们。

本产物不是全146字段 D4 normalization、winsor/mean/std/元素条件归一化或 P-prime/training release。atom SASA 当前是与原 outlier helper 相同的 pooled-atom field reference，不能冒充已完成按元素的全 D4 归一化。参考/coverage/domain 的 pending-Root 字段是 producer 时状态，不能修改原 JSON 冒充事后 C0；Root 用独立真实记录引用原哈希即可。
