# QM7b 官方图身份与 MAT 行映射检索

2026-10-27，SB4；仅官方网页/论文/维护者源码与现有小元数据核对，未运行科学程序，未读取或解析本地科学 DATA，未提交作业。没有修改任何原 UNKNOWN、组成策略、阈值或 full decontamination HOLD。

结论：找到两条有直接原作者出处、正常 HTTPS HEAD200 的2,671,083B ZIP 候选，但尚未证明其内容包含原 SMILES/SDF/键表或显式 MAT 行映射。优先让 Root 对原作者2013论文链接的 ZIP 做有限下载和 CPU archive/README 清点。不能把“未在本轮网页找到图”写成“官方图不存在”，也不能把这两个候选提前当成已验收图来源。

## 当前资产实际类型

1. 现有792小报告 `moleculenet792_metadata_v1/qm7b_mat.json` 只通过 MAT 变量元数据观察到 `X(7211,23,23)`、`T(7211,14)`、`names(14)`；没有直接 Z/R/SMILES/键表字段，未 materialize 数值数组。`names` 是14个性质名称，不是7211个分子ID。此物理观察与 [Quantum-Machine 官方说明](https://quantum-machine.org/datasets/)相符。
2. `qm7b_native_composition_main_v1/{contract,projection}.py` 绑定实际4521897格式 C0：作者2019 v3 `qm7b_coords.xyz` 为7,837,328B extended XYZ，完整7211帧，原 species 是 H/C/N/O/S/Cl，原身份头字段0。这里的 Z 只由明确原元素符号查固定原子序数表得到；坐标 token 不转浮点，不构键。输出 source ID 是原文件物理帧 locator，`native_author_ID=None`，不是 MAT 行号或作者分子ID。
3. 当前组成入口仅调用冻结 `native_composition` / `identity`，空 full keys/WP5 keys、原图 UNKNOWN 和每一帧都保留。本次未查询2093终态，不声称它已经完成。
4. [2019作者仓储 README](https://archive.materialscloud.org/records/rmp9p-1k216/preview/README.txt?include_deleted=0)声明全7211分子按 FPS 重排。[作者2019论文](https://www.nature.com/articles/s41597-019-0157-8)还说明向核电荷中心平移并重新编号 molecule0001…molecule7211。因此这套命名/顺序不能自动当2013 MAT row。对应[仓储发布页](https://archive.materialscloud.org/records/rmp9p-1k216)列出 XYZ 和量化程序输出包，页面未给可验证的2013 MAT→FPS对应表。

## 两条新的原作者精确候选

| 优先 | 精确 URL | 直接出处 | 实际网络小观察 | 尚未证明 |
|---|---|---|---|---|
| 1 | [2013dsgdb7njp.zip](https://www.mrupp.info/Data/2013dsgdb7njp.zip) | [Matthias Rupp 论文页](https://www.mrupp.info/publications.html)的2013 Montavon论文条目，实际 HTML 相对 href=`Data/2013dsgdb7njp.zip` | HEAD200，application/zip，Content-Length2671083 | archive成员/README/图/SMILES/原ID/MAT映射均UNKNOWN |
| 2 | [gdb7-13.zip](https://qmml.org/Datasets/gdb7-13.zip) | [QM/ML数据目录](https://qmml.org/datasets.html)的 GDB7-13/QM7b 条目；[站点主页](https://qmml.org/)明确维护者为原作者 Matthias Rupp | HEAD200，application/zip，Content-Length2671083 | 与候选1是否同字节也UNKNOWN，不能凭长度相同合并来源 |

本机普通 HTTPS HEAD 的机器观察保存在同目录 `qm7b_official_candidate_http_metadata_20261027_v1.json`。只访问响应头，没有打开 ZIP body；未计算 SHA/MD5/CRC、未解析成员或图。两个 ETag 不同；ETag/Last-Modified/长度都不是内容 SHA。没有调整代理/网络环境、VPN、认证绕过、镜像替换或联系作者。

原论文 DOI 的 SI 入口为 [stacks.iop.org/NJP/15/095003/mmedia](https://stacks.iop.org/NJP/15/095003/mmedia)，但本轮 web工具访问受限；没有绕过，也没有猜造 CDN suppdata 文件名。[作者2013论文的 arXiv版本](https://arxiv.org/html/1305.7074)明示补充材料提供全部原几何/性质；原作者个人页的 ZIP 是更直接、已实际 HEAD 可达的候选。其内部到底是否发布原 SMILES/图及顺序说明，需要后继真实 CPU 观察。

## 维护者“graph”接口不等于原化学键

[DeepChem已冻结commit源码](https://raw.githubusercontent.com/deepchem/deepchem/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm7_datasets.py)的 `QM7B_MAT_URL` 指向原 MAT；同文件 `gdb7_v2.sdf`、Z/R数组及 sanitize说明属于 QM7，而不是 QM7b。不能用这些字段或 QM7 的原SDF补成7211 QM7b的身份。

[DeepChem2.1.0维护者原QM7b函数](https://raw.githubusercontent.com/deepchem/deepchem/2.1.0/deepchem/molnet/load_function/qm7_datasets.py)使用 X/T，`ids=None`，未加载原键表/SMILES或给XYZ映射。[PyG维护者QM7b源码](https://pytorch-geometric.readthedocs.io/en/latest/_modules/torch_geometric/datasets/qm7.html)则将每个 Coulomb matrix 的非零位置直接作为 edge_index，edge_attr 为对应 Coulomb 数值。这些边不是作者发布的化学键/键级/电荷/立体证据，不能据此生成冻结的full key。

[MoleculeNet作者论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868307/)也分别列 QM7 的 SMILES/3D 与 QM7b 的3D；这一表述不是原图或 MAT 行关联表。

另一个作者仓储 [2020 dipole README](https://archive.materialscloud.org/records/44zme-4tq16/preview/README.md?include_deleted=0)明确其 QM7b 被随机重排，`fps_order` 对应 FPS 序。它最多给本仓储随机序与 FPS 序的联系；网页没有把 `fps_order` 定义为2013 MAT row。不能因其字段名看起来是 index 就作跨资产 join。

## 官方原始生成流程及未知边界

Montavon等[原作者方法段](https://arxiv.org/html/1305.7074)的明确流程是 **原 GDB SMILES → OpenBabel 的 UFF 初始几何 → FHI-aims PBE几何优化**。论文指出原几何在补充材料；没有在已核页面规定从XYZ用某个距离/价态/DetermineBonds算法逆向重建原键、原SMILES或立体的流程。正向生成事实不能授权反向推键，也不能证明原 SMILES 随某个已下载资产发布。

本轮没有找到可直接闭合“每条原MAT row → 原SMILES/键表/SDF/authorID”的显式文件/维护者映射源码。所有相同N、数字文件名、物理顺序、FPS index、QM7近似子集关系和 Coulomb/几何可比性都不能替代这样的证据。现有原XYZ组成只证明元素多重集；同组成异构体、图、电荷、同位素与立体依然不明，不自动升级成精确去污染。

## 最窄后继建议，尚未执行或代签

Root可先对候选1普通下载为新 opaque 文件，保留真实传输终态/长度；首次内容SHA不得预造。新的有限 CPU bootstrap在纯边界后校 wholeSHA/稳定FD/ZIP centraldir/完整CRC、有限列成员名与小README/格式字段。不要执行任何archive内脚本或pickle，不自动全图解析。优先找作者显式 SMILES/键表/SDF、原条目ID，以及其与2013性质/MAT顺序的明文或维护者源码定义。若只有XYZ/性质而没有映射，仍记录UNKNOWN，不能重解释现有MAT rows。

只有实际小inventory/README证据出来后，才决定是否存在可复用原图 reader 或需要单独请求新科学seam。若有明确原图，后继应保存全部原变体/未知并审计身份 union，不能因为已经有组成 fallback 就绕开原图。当前不下载科学body、不实现图构造、不改任何科学接受规则或生产配方。
