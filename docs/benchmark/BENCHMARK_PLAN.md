# 下游评测与基线对比计划（Benchmark Plan v1）

- 状态：**B0、B1、C1、B2 环境准备与下游构象预生成已于 2026-11-18 授权**，见 [USER_DIRECTIVE_20261118.md](USER_DIRECTIVE_20261118.md)；全量表示提取、B3 及以后仍未授权。
- 日期：2026-11-17
- 适用范围：PhyChem-MFM 文章的下游评测（任务名单、适用域规则、基线模型、评测协议）。
- 与家族析因的关系：本文定义"在哪些任务上、和谁比、怎么比"。我们自己的模型（3D / 2D / 2D+3D × S / P / D / SPD）进入第 B4 阶段时才评测，checkpoint 来自析因线。

---

## 1. 任务名单

依据：2026-11-17 的文献核查（见 §9 来源）。剔除标准为"已有工作中主流方法间差距很小，或常用划分下已接近精度上限"。

### 1.1 正文主任务

| 任务 | 数据 | 层级 | 划分 / 协议 | 选择理由 |
|---|---|---|---|---|
| ExpansionRx 官方 test | OpenADMET ExpansionRx（HF） | 分子级，多终点稀疏 | 官方 train/test；榜单式 MA-RAE + 各终点 MAE | 盲测，最终榜单 MA-RAE 分布宽（约 0.51 至 >1.0），区分度高 |
| pKa | pKahub（JCIM 2026）+ SAMPL6/7 盲测 | 原子级（电离位点）/ 分子级 | 见 §6 待用户决定 | QupKake 显示半经验量化特征关键；可比方法多，差距明显 |
| NMR 化学位移 | NMRShiftDB2（¹³C / ¹H；可用 NMRShiftDB2-DFT 构型） | 原子级 | 文献标准划分（执行时按所对比文献确定一种并固定） | HOSE 3.52/0.29 ppm → GNN 1.355/0.224 → GT-NMR 1.189/0.158 → CSTShift 0.944/0.185，差距明显；直接检验原子级表示 |
| 光学性质 | Joung 2020 实验光学数据库 | 分子级（发色团 + 溶剂） | **只用 scaffold / 发色团外推划分**；随机划分已饱和（MAE <7 nm），不使用 | 外推划分下仍有区分度；检验电子结构信息 |

### 1.2 正文次要 / 机制任务

| 任务 | 数据 | 用途 |
|---|---|---|
| MoleculeACE | 30 个 ChEMBL 靶点 | 活性悬崖，探索性；已知 ECFP 类方法占优，预期我们不占优 |
| ASAP-Polaris antiviral ADMET 2025 | Polaris unblinded | 第二个真实项目盲测；注意官方 CLint 下限修订 |
| C7H10O2 异构体 | 6095 个异构体，G4MP2 | 组成固定下的结构信息；目标为 G4MP2 绝对值 + Δ(G4MP2 − B3LYP) |
| PPE1694 | 实验生成焓 1694 个化合物 | **以残差任务为主**（ΔHf − 基团加和，ΔHf − 半经验）；必须报告基团加和基线 |

### 1.3 待基线筛选

| 任务 | 说明 |
|---|---|
| PharmaBench | 未找到可靠的模型间差距证据；按 §2.2 规则决定去留 |

### 1.4 附录

| 任务 | 说明 |
|---|---|
| Biogen ADME（Polaris adme-fang） | 区分度低（多数两两比较不显著，PPB 子集过小）；作质量对照 |
| TDC ADMET group | 数据质量争议、榜单无显著性信息；作附录对照 |

### 1.5 不做

Buchwald–Hartwig HTE 产率（随机划分饱和、多组分任务）、Hait & Head-Gordon 极化率/偶极矩、QUEST、GW100（过滤后几乎只剩极小分子、无表示学习可比对象）。MPCONF196 移到构象解耦线，不作为评测任务。

---

## 2. 适用域规则与任务筛选（预注册的科学决策）

### 2.1 适用域规则（所有数据集、所有模型统一使用）

在看到任何模型结果之前固定，文章中写明：

1. 闭壳层：自旋多重度为 1，RDKit 自由基电子数为 0。
2. 净电荷：与预训练集一致；ADME 数据先去盐、保留最大片段，质子化状态按预训练规则统一。
3. 元素：预训练集元素的子集。
4. 大小：重原子数 ≥ 3 且 ≤ 200。
5. 几何：数据集自带参考构型的用参考构型；否则用预训练时的同一构象流程。

每个数据集报告过滤前后数量（按原因分列）。过滤后少于 30 个点的数据集不进正文。

**盲测榜单（ExpansionRx、ASAP）不得过滤**：域外分子用事先指定的备用预测（训练集均值），在文章中写明。

**筛选影响检查**：对能处理全集的基线（RF-ECFP、LightGBM-RDKit、Chemprop v2），报告其在全集 / 保留子集 / 被剔除部分上的表现。

### 2.2 任务去留规则（只用基线，不看我们的模型）

在 B1 阶段，用 RF-ECFP、LightGBM-RDKit、Chemprop v2 三个基线判断：

- **信号不足**：三者中最好的 RAE（相对训练集均值预测器）≥ 0.90，且其 paired-bootstrap 95% CI 上界 ≥ 0.85 → 剔除。
- **区分度不足**：三者 RAE 的极差 < max(0.02, 2 × 配对差的 bootstrap SE) → 降为附录。
- 其余保留。

该规则只在 B1 执行一次，结果写入 `results/benchmark/B1_task_screen.csv`，之后不再修改。

---

## 3. 基线模型

### 3.1 必做

| # | 基线 | 类别 / 预训练信号 | 输入 | 评测方式 | 来源 |
|---|---|---|---|---|---|
| 1 | LightGBM | 传统 ML | RDKit 2D 描述符；另跑 ECFP4 | 原生训练 | lightgbm |
| 2 | RF | 传统 ML | ECFP4（2048 bit, r=2） | 原生训练 | scikit-learn |
| 3 | TabPFN | 表格基础模型 | RDKit 2D 描述符 | 原生推断（记录版本号） | PriorLabs/TabPFN |
| 4 | 我们的架构从头训练 | 无预训练对照 | 与对应主干相同 | 端到端微调 | 本仓库 |
| 5 | Chemprop v2 | 端到端 D-MPNN | 2D 图（另跑加 RDKit 特征版） | 端到端训练 | chemprop/chemprop |
| 6 | CheMeleon | 描述符监督预训练（对应 D） | 2D 图 | 冻结 + 微调 | 经 Chemprop v2 加载（执行时核实） |
| 7 | MiniMol | 多任务监督（量化 + 生物） | 2D 图 | 冻结嵌入 | graphcore-research/minimol |
| 8 | Monroe | PM6 + PCBA 多任务监督（对应 P + 生物） | 2D 图 + 3D 辅助 | 冻结 + TabPFN（原论文协议） | blazejba/monroe（权重是否公开需核实） |
| 9 | Uni-Mol | 3D 自监督（对应 S） | 3D | 冻结 + 微调 | deepmodeling/Uni-Mol |
| 10 | MACE-OFF | MLIP（能量 / 力） | 3D | 冻结原子特征 → 我们的 readout | ACEsuit/mace |
| 11 | UMA-S | MLIP（OMol25 等） | 3D | 冻结原子特征 → 我们的 readout | facebookresearch/fairchem（HF 需申请权限） |
**规则：权重未公开的预训练模型直接不用**（不引用论文数字代替）。在 B2 记一行并继续。

### 3.1a 三个核心对照（必做，用户 2026-11-17 指定）

| # | 对照 | 内容 | 要回答的问题 |
|---|---|---|---|
| C1 | **标签当特征** | 对下游分子用与预训练**完全相同**的流程直接计算 P 标签（PM7/xTB 性质，同字段、同单位）和 D 标签（RDKit 描述符），作为特征喂给 LightGBM 和 TabPFN。三组：P 特征、D 特征、P+D 特征。原子级任务用原子级 P 字段（电荷等）+ RDKit 原子特征接 LightGBM | 预训练表示是否优于"直接把预训练标签当特征"。这是审稿人最可能质疑的点，必须在每个任务上报告 |
| C2 | **随机权重编码器 + 相同读出头** | 我们每种主干（3D / 2D / 2D+3D）的随机初始化编码器（固定种子 20261025，不训练），接与预训练模型完全相同的 R1/R3/R4 | 把"架构归纳偏置"和"预训练学到的东西"分开。几乎零成本。外部预训练基线若有同架构随机初始化版本可得（Uni-Mol、D-MPNN、MACE），也按同样方式补一份 |
| C3 | **同架构、同数据、不同标签** | S / P / D / S′ / P′ / SPD / S′P′D / MoE，在 3D / 2D / 2D+3D 三种主干上（来自家族析因线的 checkpoint） | **论文主结论**。所有外部基线都是为这组对比做铺垫 |

C1 的计算：P 标签对下游分子的计算必须使用预训练时同一程序版本、同一构象流程与同一字段定义；计算失败的分子记一行，该分子在 C1 中缺失而不填补（不影响其他模型的评测集）。

C3 在 B4 阶段评测，其统计比较是全文的核心比较：同一主干内用归一化分数和配对检验；跨主干用原始 MAE / RAE。

### 3.1b 任务级经典基线（随任务定义，不单列为对照）

- PPE1694：Benson 基团加和（残差任务的定义本身需要它）。
- NMR：HOSE 码（引用文献数字即可）。

### 3.2 推荐

| 基线 | 类别 | 输入 | 评测方式 | 来源 |
|---|---|---|---|---|
| KPGT | 知识引导的图 Transformer 预训练 | 2D | 冻结 + 微调 | lihan97/KPGT（执行时核实） |
| SliDe（或 Frad） | 3D 去噪预训练（物理启发） | 3D | 冻结 + 微调 | 二者选其一，优先权重可用、文档齐全者 |
| QuADMET-Former | QM 性质预训练的 EGNN（与 P 最接近的已发表工作） | 3D | 冻结 + 微调 | HF arunraja007/quadmetformer（MIT） |
| 3D 等变模型从头训练 | 无预训练 3D 对照 | 3D | 端到端 | PaiNN（schnetpack 实现） |
| Fallani et al. 2025 | 原子级量化性质预训练的 Graphormer | 2D | 冻结 + 微调 | J Cheminform 2025 附带代码/Zenodo（执行时核实） |
| Rem3Di | MACE 原子特征的注意力聚合 | 3D | 冻结 + 微调（原论文协议） | PyPI `remedi` |

Fallani 2025 与"原子级 QM 标签是否有用"直接相关（Monroe 结论相反）；Rem3Di 避免因只用原始 MACE-OFF 特征而低估 MLIP 路线。

### 3.3 可选（算力允许再做）

Uni-Mol2（中等规模版本）、KERMT、MoLFormer、AIMNet2、Boltz（Boltz-2 配体表示）、QM 增强 Chemprop（Li et al. QM 描述符）。

---

## 4. 评测协议

### 4.1 统一 readout（冻结表示）

所有能导出表示的模型（我们的模型、CheMeleon、MiniMol、Monroe、Uni-Mol、MLIP 等）都接同一组 readout：

- R1：岭回归（分子级用 mean(H)；原子级用原子 H）
- R3：原子级深层 readout（现有实现）
- R4：TabPFN，作用在分子级表示上（Monroe 显示 TabPFN readout 会大幅改变排名，必须纳入）

TabPFN 支持的样本数 / 特征数有上限。超限时按其官方推荐的子采样集成方式运行，并在结果中标注；仍无法运行的任务只报 R1/R3。

只有分子级指纹的模型（CheMeleon 指纹、MiniMol、Monroe）不参与原子级任务；原子级任务另行引用任务专属 SOTA 的文献数字。

### 4.2 微调

每个预训练基线再跑一遍其官方推荐的微调方式（用官方默认超参，不做额外搜索）。我们的模型在关键格子上采用 LP-FT（先训 readout，再整体微调），学习率 3 档，编码器学习率为 head 的 0.1 倍，在内部验证集上选择。

### 4.3 划分、种子与统计

- 盲测 / 官方划分：使用官方划分；按分子分组做 1000 次 paired bootstrap。
- 无官方划分的数据集：5×5 重复交叉验证（scaffold 划分），按 Ash et al. 2025 的方法比较协议，用 Tukey HSD 判断显著性。
- 每个配置 2 个种子（传统 ML 1 个种子即可，其随机性由 CV 覆盖）。
- **跨主干比较用原始 MAE 或 RAE（相对训练集均值预测器）**；我们的归一化分数（相对同架构随机初始化编码器）只用于同一主干内的比较。

### 4.4 构象

所有 3D 模型（我们的、Uni-Mol、MLIP、QuADMET-Former、SliDe/Frad、PaiNN）使用同一套构象，来源为数据集参考构型或预训练构象流程。不允许各模型使用自带的构象生成。

### 4.5 预训练数据泄漏检查

对每个预训练基线，若其预训练分子清单可得，按完整 InChIKey 检查与各下游测试集的重叠；重叠分子从该模型的测试中剔除，并记一行。清单不可得的模型，在结果表中标注"未检查"。

---

## 5. 执行阶段

| 阶段 | 内容 | 资源 |
|---|---|---|
| B0 | 下载数据集；按 §2.1 过滤；输出过滤前后数量表；对下游分子按预训练流程计算 C1 所需的 P 标签（PM7/xTB）与 D 标签（RDKit） | CPU |
| B1 | 三个传统基线在全部候选任务上运行；按 §2.2 确定最终任务名单 | CPU 为主，Chemprop 少量 GPU |
| B2 | 搭建必做基线环境；提取冻结表示 | GPU，短 |
| B3 | 必做基线的 R1/R3/R4 与官方微调；推荐基线随后 | GPU |
| B4 | C2（各主干随机权重编码器）与 C3（析因线 checkpoint：S/P/D/S′/P′/SPD/S′P′D/MoE × 3D/2D/2D+3D）按同一协议评测 | GPU |

阶段间无需等待用户确认，除非出现 §7 的停止条件。B1 完成后在日报中汇报最终任务名单。

---

## 6. 待用户决定的科学问题（启动前或 B0 后确定）

1. pKa 任务形式：宏观 pKa（分子级）、微观 pKa（位点级），或两者都做；多电离位点如何处理。B0 统计 pKahub 的标注情况后由用户决定。
2. NMR 采用的标准划分（对应要比较的文献）。

---

## 7. 停止条件（仅以下情况停止并报告）

- 需要删除任何文件；
- 需要改变适用域规则、任务去留规则或标签定义；
- 需要使用学校付费服务器；
- 需要进行正式预训练（本计划不包含任何我们自己模型的预训练）。

其余所有情况：记一行日志并继续。基础设施故障直接修复并重跑，不单独报告。任何诊断或修复超过 4 小时，或连续失败 2 次，标记为 UNRESOLVED，采用保守默认（该基线在该任务上记为"未完成"）并继续。成本超过估计的 1.5 倍不是停止条件。

## 8. 不要做

- 不要根据我们模型的结果修改任务名单、适用域规则或划分。
- 不要为基线做超出官方默认的超参搜索（TabPFN、传统 ML 也用默认或文献配置）。
- 不要让各 3D 模型使用自带构象生成。
- 不要在随机划分上报告光学性质结果作为主结果。
- 不要对任何结果做二次读回或独立复核，除非产出该结果的步骤本身报错。
- 不要为本计划启动任何预训练，也不要占用析因线正在使用的显卡。
- 单元测试只覆盖新写的逻辑（数据加载、适用域过滤、readout 接口）；合并前跑一次全量回归。

报告：每日一页以内的日报；每周一次成本统计；只有最终交付物（任务筛选表、最终结果表）附 SHA。

---

## 9. 来源

- ExpansionRx 榜单：https://benchmarklist.com/benchmarks/openadmet_expansionrx/
- ASAP ADMET：https://polaris-hub.vercel.app/datasets/asap-discovery/antiviral-admet-2025-unblinded
- Biogen ADME：https://polaris-hub.vercel.app/datasets/biogen/adme-fang-v1 ；复现分析 https://www.blopig.com/blog/?p=15109
- pKahub 基准：https://real.mtak.hu/247419/1/ci6c00107.pdf ；QupKake（Abarbanel & Hutchison, JCTC 2024）：https://biomed.reviewer.ly/app/publication/a39708eb-29b4-44ed-a3e4-2516f3494da5
- NMR：GT-NMR https://doi.org/10.1186/s13321-024-00927-9 ；CSTShift https://pmc.ncbi.nlm.nih.gov/articles/PMC11209944/
- Joung 光学数据库：https://www.nature.com/articles/s41597-020-00634-8
- MoleculeACE：https://pmc.ncbi.nlm.nih.gov/articles/PMC9749029
- C7H10O2（G4MP2）：https://www.colabfit.org/id/DS_olmzgsz9hmxy_0
- PPE1694：https://moldis-group.github.io/prunedhof
- PharmaBench：https://pubmed.ncbi.nlm.nih.gov/39256394/
- Monroe：https://arxiv.org/abs/2608.18982
- CheMeleon：https://arxiv.org/abs/2506.15792
- MiniMol：https://github.com/graphcore-research/minimol
- QuADMET-Former：https://huggingface.co/arunraja007/quadmetformer
- Fallani et al. 2025：https://doi.org/10.1186/s13321-025-00970-0
- MapLight / TabPFN 对照：https://arxiv.org/abs/2310.00174 ；https://arxiv.org/abs/2506.06443
- QM 描述符（ASKCOS）：https://arxiv.org/abs/2501.01835
- UMA：https://fair-chem.github.io/molecules/models.html
- Rem3Di：https://arxiv.org/abs/2607.19977
- 方法比较协议：Ash et al., JCIM 2025, 65(18):9398
