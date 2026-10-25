# SB-5 扩充准备：阶段 1

## 目的

为 PubChem 新分子扩充建立可审阅的来源、化学范围、去重、去污染和 R/N
排序接口。D-1–D-5 优先；本阶段不占科学计算资源，不下载全量数据。

## 输入与来源

Root 于 2026-10-25 在 compute-0-20 对官方 CID–SMILES URL 实测 HEAD 返回
200，长度 1,488,715,010 bytes，Last-Modified 为 2026-10-24 18:17:31 GMT。
证据是外部 `control/pubchem_network_probe_v1.json`；该证据不是数据文件 SHA。
下载后必须重新验证版本并计算实际 SHA256。

代码规则沿用 `workflows/dataset_rebuild/scripts/wp0_inventory.py`、
`wp1_geometry.py` 与 `workflows/wp5/scripts/wp5_population.py` 的已核实语义。
本次新增文件另行版本化，不回改这些历史来源。当前输入配置、参数与待闭合
项在 `configs/data_v1/expansion/`；物理来源清单在
`configs/data_v1/decontamination_sources.json`。

官方元数据入口：

- [PubChem 官方下载说明](https://pubchem.ncbi.nlm.nih.gov/pcfe/docs/markdown/downloads.md)：官方 FTP 区域支持 HTTPS。
- [TDC 官方 ADMET Group](https://tdcommons.ai/benchmark/admet_group/overview/)：22 个端点；官方包 metadata 指向 Harvard Dataverse file 4426004。
- [DeepChem 官方 MoleculeNet 文档](https://deepchem.readthedocs.io/en/latest/api_reference/moleculenet.html)：具体子集尚需冻结，清单暂列保守候选并保持 PENDING。
- [MARCEL 官方数据入口](https://github.com/SXKDZ/MARCEL)：Drugs-75K 和 Kraken 各有官方归档链接，尚未取得归档字节及其 SHA256。
- [COCONUT 官方下载页](https://coconut.naturalproducts.net/download)：当前页面版本 October 2026，CSV 官方链接已写清单；active/inactive 完整覆盖尚未证明。

这些只是来源定位；它们不证明已下载、已提取全部身份或已去污染。

## 规则和参数

保持原 X01–X05、RDKit 2025.09.5、同位素及源立体信息，不设新的重原子上限。
在 PubChem 内按完整 InChIKey 去重，保留 CID 别名与来源行号。与所有下游划分
比对完整 InChIKey、WP5 的 connectivity14＋质子化末位键，以及原有未解析
身份的保守非氢组成隔离规则。下游标签和特征不得参与新颖性评分。

默认首批 250 万分子，R/N 各 125 万；总排序保留各 500 万的固定前缀，种子
20261025。扩充不算量化及 P′。构象/D 科学实现与 1 万分子试点尚未执行。

## 当前结果与异常

没有筛选数量、去污染数量、成功率或核时的科学结果。新增代码包含有界
spawn 并行筛选、来源版本与续传检查、严格全来源验证、身份过滤及 R/N
排序参考实现。代码测试与仓库检查由 Root 在 compute-0-20 执行并保留证据；
本报告不预写 PASS。

关键未闭合项：MoleculeNet 子集范围、全部下游物理 SHA/划分覆盖、完整 v1
原始输入回归、v1 共同人群结构/指纹来源、精确近邻成本、全池外部排序成本、
与 S′ 一致的 UFF 输入适配器及 UFF/D 试点。任何 PENDING 都不升级为已去污染。

## 已知限制

当前仅为阶段准备。构象、D 标签、完整报告和 250 万候选交付均未完成。
后续必须逐阶段用实际数据和脚本生成统计，先试点再提交正式批次，并保留
失败证据、每步真实成本和配额至少 200 GB 的余量。
