# B2 基线可用性 · 执行中

本表尚未完成 B2 全部模型验收，暂不附最终 SHA。验收范围仅为固定 100 个下游分子的推断；没有授权或执行全量表示提取。固定样本：`benchmark_B1_20261119/smoke100/job_4536859/fixed100.json`，seed 20261025。3D 输入来自同一 B0 已接受 UFF 构象，保持原子顺序，不自行生成构象。

| 模型 | 当前状态 | 版本、权重和原生证据 |
|---|---|---|
| TabPFN | 可用，V2 回归接口 | 包 10.2.0，公开 V2 regressor，100 个预测；4536865。当前默认新权重的门控不等于 V2 权重未公开。Prior Labs V2 Apache 2.0 加署名条款；原始许可随模型缓存保存。 |
| Chemprop v2 | 可用，架构接口 | 2.2.2，100×300；4536875。从头训练对照使用 seed 20261025 随机权重，预训练权重不适用。MIT。 |
| CheMeleon | 可用 | Chemprop 2.2.2 官方适配器，100×2048；4536871。权重 [Zenodo 15460715](https://zenodo.org/records/15460715)，严格加载；代码 MIT，所查权重记录未明确单列许可。 |
| MiniMol | UNRESOLVED，两次接口失败 | 1.3.4 / Graphium 2.4.7；4536874、4536897。权重随包公开；先为 SciPy Float16 稀疏构造错误，修复后为 featurization/strBatch 接口错误。不能记为“权重未公开”。 |
| Monroe | 可用 | commit `de075eabe98e4adbbedbc86ca9e877f4bfd9b629`，公开仓库 LFS 权重，100×720；4536890。CPU 显式加载、严格编码器权重、直接共享坐标建图；代码 MIT。 |
| Uni-Mol | UNRESOLVED，两次尝试后停止诊断 | unimol_tools 0.1.5；4536882、4536890。公开 all-H 权重已下载并加载，100 分子表示已得到，但原子输出与输入原子接口不匹配，验收步骤报错；没有第三次复核。代码 MIT，权重许可未核实。 |
| MACE-OFF | 可用 | mace-torch 0.3.15，MACE-OFF23 small，100 分子原子标量特征 192 维；4536880。原始 F64 坐标，未优化结构；代码 MIT，权重 ASL。 |
| UMA-S | 访问未解决；权限申请由用户处理 | [官方模型仓库](https://huggingface.co/facebook/UMA)。节点未找到既有 HF 凭据；两次直接访问均为网络错误，不能据此声称收到 401/403。未申请权限、注册账号或接受许可；4536914。 |
| KPGT | UNRESOLVED，两次权重传输失败 | commit `47dc1646c70b2138a157de481d24a1ac35d174cd`；独立环境已准备。官方 [Figshare 权重](https://figshare.com/s/d488f30c23946cf6898f) 首次返回非 ZIP 内容，第二次下载 HTTP 403；4536923、4536928。代码 Apache 2.0，权重记录 MIT；不等同于权重未公开。 |
| Frad | 可用 | commit `d4af0a60727b8d4fabb9f51f5332cba87468afe7`，公开 [Zenodo QM9 预训练权重](https://zenodo.org/records/12697467)；4536947。补齐作者 CLI 的旧检查点兼容默认值后严格加载编码器，完成同一 100 分子原子表示推断。代码 MIT；记录未明确单列权重许可。 |
| QuADMET-Former | 进行中 | [公开 HF 权重](https://huggingface.co/arunraja007/quadmetformer/tree/main)；模型卡代码地址为占位链接，需恢复可复现的原始接口，尚未验收。 |
| PaiNN / SchNetPack | 进行中 | 独立环境与同一 100 分子原子表示接口准备中；从头训练基线无预训练权重要求。 |
| Fallani 2025 / GraphQPT | 进行中 | commit `72c0cb5bc3f8209bf673cc662c0e8b4ec0041788`，代码 MIT，已建独立环境；作者所链 Zenodo 13374020 发布的是数据集，仍在核实权重发布情况，未用论文数字冒充模型。 |
| Rem3Di | 进行中 | commit `4a0d6da147aa8080f84a80e3ee153cb194dbf9a7`，代码 Apache 2.0，已建独立环境；PyPI 版本要求 Python ≥3.12，权重与接口尚未关闭。 |

各模型独立环境、有效依赖清单、权重来源与原生 stdout 留在共享 `benchmark_B1_20261119/environments/`；源码与推荐模型访问元数据在 `B2_remaining_sources/job_4536914/`。依赖继承的基础环境和各个 venv 均明确记录。UNRESOLVED 项保留原始失败产物并继续其他模型。
