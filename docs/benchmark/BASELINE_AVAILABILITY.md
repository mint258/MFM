# B2 基线可用性 · 本次授权范围结论

2026-11-20：14 个模型均已记录本次可用性结论，**7 个可用、4 个 UNRESOLVED、1 个权重未公开、2 个需申请权限**。可用以固定 100 分子推断步骤成功为准，未成功项不作为已验收模型。固定样本为 `benchmark_B1_20261119/smoke100/job_4536859/fixed100.json`，seed 20261025。3D 模型读取同一 B0 首个已接受 UFF 构象和原子顺序，没有自行生成构象；本次不提取全量表示。

| 模型 | 结论 | 固定 100 分子接口、版本和原生作业 | 权重来源与许可 |
|---|---|---|---|
| TabPFN | 可用，V2 回归接口 | 包 10.2.0；100 个预测；4536865；独立环境 | [PriorLabs V2](https://huggingface.co/Prior-Labs/TabPFN-v2-reg) 公开回归权重；Apache 2.0 加模型署名条款。新默认权重的门控不影响本次 V2 结论。 |
| Chemprop v2 | 可用，架构接口 | 2.2.2；100×300；4536875；独立环境 | 从头训练参考使用 seed 20261025 随机初始化，预训练权重不适用；[代码 MIT](https://github.com/chemprop/chemprop)。 |
| CheMeleon | 可用 | Chemprop 2.2.2 官方适配器；100×2048；4536871；独立环境 | [Zenodo 15460715](https://zenodo.org/records/15460715) 的 `chemeleon_mp.pt`，严格加载；代码 MIT，Zenodo API 的 `metadata.license.id=mit-license`。许可元数据保存于 4536975 的源记录目录。 |
| MiniMol | UNRESOLVED，两次接口失败 | 1.3.4 / Graphium 2.4.7；4536874、4536897；独立环境 | [官方包与仓库](https://github.com/graphcore-research/minimol) 的公开打包权重，MIT。首次 SciPy Float16 稀疏构造失败；第二次为 Graphium strBatch/featurization 接口错误。不是权重未公开。 |
| Monroe | 可用 | commit `de075eabe98e4adbbedbc86ca9e877f4bfd9b629`；100×720；4536890；独立环境 | [官方仓库 LFS](https://github.com/blazejba/monroe)，MIT；CPU 显式加载和严格编码器加载。 |
| Uni-Mol | UNRESOLVED，两次尝试后结束诊断 | unimol_tools 0.1.5；4536882、4536890；独立环境 | [官方 all-H 权重](https://huggingface.co/dptech/Uni-Mol-Models) 已下载并加载，模型卡 MIT。分子表示得到，但原子输出长度与原始输入原子数不匹配，验收步骤报错；不作第三次尝试。 |
| MACE-OFF | 可用 | mace-torch 0.3.15 / MACE-OFF23 small；100 个分子的原子标量宽度 192；4536880；独立环境 | [官方权重](https://github.com/ACEsuit/mace-foundations)，权重 ASL；代码 MIT。共享 F64 坐标未优化。 |
| UMA-S | 需申请权限 | 4536914；未找到既有 HF 凭据；环境安装与 100 分子推断未完成 | [官方模型仓库](https://huggingface.co/facebook/UMA) 为门控访问，FAIR Chemistry License v1。权限由用户本人申请；两次节点直连均为网络错误，不能写成 401/403 或申请被拒。未注册账号或接受条款。 |
| KPGT | UNRESOLVED，两次权重传输失败 | commit `47dc1646c70b2138a157de481d24a1ac35d174cd`；4536923、4536928；独立环境 | [官方 Figshare 权重](https://figshare.com/s/d488f30c23946cf6898f) 首次返回非 ZIP，第二次 HTTP 403；代码 Apache 2.0，权重记录 MIT。不是权重未公开，不作第三次尝试。 |
| Frad | 可用 | commit `d4af0a60727b8d4fabb9f51f5332cba87468afe7`；100 个分子原子标量宽度 256、向量形状 3×256；4536947；独立环境 | [官方 Zenodo QM9 权重](https://zenodo.org/records/12697467)，86,717,861 字节；代码 MIT，权重 **CC-BY-4.0**（原生 API 的 `metadata.license.id`）。沿作者 CLI 的旧检查点兼容默认值，严格加载编码器。旧表“未明确单列许可”为字段读取错误，本表更正。 |
| QuADMET-Former | 可用 | 官方源码 commit `b5789c52a2701009005b98930fae24f8c136142f`；100×128 均值池化，原子标量宽度 128；4536967；独立环境 | [作者源码](https://github.com/arunraja-hub/quadmetformer) 与 [公开 HF 权重](https://huggingface.co/arunraja007/quadmetformer)，MIT；固定 single_conf 全目标检查点，严格加载 shared_backbone/out_norm。仅为未使用的多构象模块提供空导入垫片，不修改源文件。 |
| PaiNN / SchNetPack | UNRESOLVED，两次模型尝试失败 | SchNetPack 2.1.1；4536952、4536964；保留两个独立环境 | 从头训练参考，无预训练权重要求；[代码 MIT](https://github.com/atomistic-machine-learning/schnetpack)。首次 torch 动态库 libnvJitLink.so.12 缺失；第二次 CPU torch 2.4.1 加载后，接口访问不存在的 `properties.scalar_representation` 报错；不作第三次尝试。 |
| Fallani 2025 / GraphQPT | 权重未公开，按规则不用 | commit `72c0cb5bc3f8209bf673cc662c0e8b4ec0041788`；4536914；已建独立源码环境，未推断 | 作者官方代码树没有检查点，releases 为空；论文链接的 [Zenodo 13374020](https://zenodo.org/records/13374020) 仅发布 gap/qm137 数据。代码 MIT；没有用论文数字代替模型结果。 |
| Rem3Di | 需申请权限，另有作者已知兼容问题 | commit `4a0d6da147aa8080f84a80e3ee153cb194dbf9a7`；4536914；源码/venv 已准备，发布包要求 Python ≥3.12，安装与推断未完成 | [作者 HF 仓库](https://huggingface.co/Felixb7/rem3di-polar) 已有门控权重，不能记为未公开；代码 Apache 2.0，权重 rem3di-weights，MACE 底座另有 ASL。作者注明 remedi 0.1.1 不兼容现有检查点，兼容分支的原子预处理仍未完成，POLAR 另缺未发布的 graph_longrange。未申请权限或接受条款。 |

独立环境、继承的基础环境、有效依赖清单、原始 stdout、失败记录与权重元数据位于共享 `benchmark_B1_20261119/environments/`；推荐模型源码与访问记录位于 `B2_remaining_sources/job_4536914/`。Frad 和 QuADMET 的接口记录分别位于 `environments/frad_smoke100_job_4536947/interface_metadata.json`、`environments/quadmetformer_job_4536967/interface_metadata.json`。

UNRESOLVED 项保留原始产物并采用保守默认，不作为通过的模型；权限项在本次授权下延期，不能声称功能环境已验收。compute-0-18 的 4536933 在 Python 导入前取消，仅为基础设施续接，不计 PaiNN 模型失败次数。本次没有独立数值复核、B2 全量表示提取、B3/B4 或正式预训练。最终本表的 SHA-256 单列交付。
