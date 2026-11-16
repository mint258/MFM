# PhyChem-MFM 文献清单

初版：2026-11-15。收录在主线讨论中检索、阅读或判断过与本工作关系的文章，按它们在论文中的
角色分组。主线定义见 [`docs/RESEARCH_MAINLINE.md`](../RESEARCH_MAINLINE.md)。

**核对状态**
- ✅：讨论时读过正文或摘要，表中描述有依据；
- ◐：只读过摘要或二手介绍，细节待核；
- ○：只凭领域常识列出，作者、年份、发表处投稿前必须核对。

写论文前统一生成 BibTeX；这里只记录"为什么引用"和"和我们差在哪里"。新增文章直接追加行，
不删除旧行；判断改变时在"关系"一栏追加日期说明。

## A. 最接近的工作（审稿人一定会拿来比，必须正面回应）

| 文章 | 年份/发表处 | 核对 | 和我们的重叠 | 和我们的区别 / 应对 | 主线位置 |
| --- | --- | --- | --- | --- | --- |
| [OmniMol: Unified and explainable molecular representation learning for imperfectly annotated data from the hypergraph view](https://www.nature.com/articles/s41467-025-63730-6) | 2025 Nat Commun | ◐ | 按任务路由的 MoE（t-MoE），输出随任务变化的表示，并用来解释性质间关系；有 SE(3) 编码器 | 在实验性质上做有监督多任务训练，标注稀疏是核心问题；我们是计算标签预训练、标签齐全、迁移到未见任务。全文未读：需核对是否有预训练阶段、是否测试新任务 | H3、E4、E6 基线 |
| [qcGEM: a graph-based molecular representation with quantum chemistry awareness](https://www.biorxiv.org/content/10.1101/2025.11.02.686183.full.pdf)（Wang, Gong） | 2025 bioRxiv | ✅ | 量化信息注入预训练表示；全连接 3D Transformer；几何去噪和遮盖重建；xTB 几何加 DFT 单点 | 量化描述符既是输入也是目标，推理时要做量化计算（Hybrid 版 100 原子约 28 分钟/核）；无受控标签比较、无 MoE。放入"推理需量化计算"一档单独比较；它已证明量化信息有用，所以我们不以此为卖点 | E5 基线 4a、E6 |
| [Pretraining graph transformers with atom-in-a-molecule quantum properties for improved ADMET modeling](https://jcheminf.biomedcentral.com/articles/10.1186/s13321-025-00970-0)（Fallani 等；[arXiv](https://arxiv.org/pdf/2410.08024)） | 2025 J Cheminform | ✅ | 同一批分子（约 13.6 万）上比较 DFT 原子级量化性质预训练和遮盖式预训练，22 个 TDC ADMET 任务 | 只有一种量化层级，无描述符、无几何层级、无组合。是我们"受控比较"最直接的前人工作 | H1、E2 |
| [Deep Learning Foundation Models from Classical Molecular Descriptors（CheMeleon）](https://arxiv.org/html/2506.15792v2)（Burns 等） | 2025 arXiv | ✅ | 用描述符作预训练目标（D 只当目标） | 输入只有分子图；目标为 1,613 个 Mordred 描述符，损失中随机遮掉 85%。未和"Chemprop + 描述符输入"比较；用户消融发现其训练描述符直接当输入更好，这是读出 C 的动机 | D 条件、E5 读出 B/C、E6 |
| [KPGT: Knowledge-Guided Pre-training of Graph Transformer](https://www.nature.com/articles/s41467-023-43214-1.pdf)（Li 等；[arXiv](https://arxiv.org/pdf/2206.03364)） | 2023 Nat Commun | ✅ | 描述符和指纹参与预训练 | 知识节点用 200 个 RDKit 描述符和 512 位指纹初始化，遮 50% 后重建：D 既是输入也是目标。代表"D 当输入+目标"范式 | E6 基线 |
| [UMA: A Family of Universal Models for Atoms](https://arxiv.org/pdf/2506.23971v2) | 2025 arXiv | ✅ | 用线性专家混合（MoLE）把不同 DFT 精度的数据集合进一个模型；报告小模型不用 MoLE 时多任务总比单任务差 | 力场模型，目标是能量和力；不同精度来自不同分子。和我们"用 MoE 整合异质计算标签"思路最接近 | H3、E4、E6 |
| [Scaling Molecular Representation Learning with Hierarchical Mixture-of-Experts（H-MoE）](https://www.biorxiv.org/content/10.1101/2025.08.09.669511.full.pdf) | 2025 bioRxiv | ◐ | 分子预训练中的共享专家加专用专家 | 按骨架和原子路由，不按标签 | E4 |
| [Suiren-1.0 Technical Report: A Family of Molecular Foundation Models](https://arxiv.org/html/2603.21942) | 2026 arXiv | ◐ | 在约 7,000 万个 DFT 构象上预训练的 MoE | MoE 只用于扩容 | E4、E6 |
| [Q-GEM: Quantum Chemistry Knowledge Fusion Geometry-Enhanced Molecular Representation for Property Prediction](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12412488/) | 2025 | ○ | 名称显示把量化知识融入 GEM | 未读，待判断 | 待定 |

## B. 预训练是否有用、对哪些任务有用

| 文章 | 年份/发表处 | 核对 | 要点 | 用法 |
| --- | --- | --- | --- | --- |
| [Does GNN Pretraining Help Molecular Representation?](https://arxiv.org/abs/2207.06010)（Sun 等） | 2022 NeurIPS | ✅ | 分子图预训练的提升常常很小甚至没有 | 引出"预训练效果因任务而异"的问题 |
| [Strategies for Pre-training Graph Neural Networks](https://arxiv.org/pdf/1905.12265)（Hu 等） | 2020 ICLR | ✅ | 只做图级有监督预训练会造成负迁移；原子输入为原子类型加手性标签 | H2 负迁移的早期证据 |
| [How Well Do Large-Scale Chemical Language Models Transfer to Downstream Tasks?](https://www.ijcai.org/proceedings/2026/0531.pdf)（Sagawa, Kojima；[arXiv](https://www.arxiv.org/pdf/2602.11618)） | 2026 IJCAI | ✅ | 预训练损失降低不一定带来下游提升；损失、Hessian 迹等事先指标都不能可靠预测 | 说明"预训练价值难以事先预测" |
| [RoFt-Mol: Benchmarking Robust Fine-Tuning with Molecular Graph Foundation Models](https://arxiv.org/pdf/2509.00614v3) | 2025 arXiv | ✅ | 有监督多任务预训练在任务对齐时有益，不对齐时在 HIV、MUV 上出现负迁移 | H2 |
| [Fast and effective molecular property prediction with transferability map](https://www.nature.com/articles/s42004-024-01169-4) | 2024 Commun Chem | ✅ | 用梯度距离预测哪个源数据集能迁移到目标 | 数据集间迁移，不涉及预训练标签 |
| [Learning to Group Auxiliary Datasets for Molecule（MolGroup）](https://ar5iv.labs.arxiv.org/html/2307.04052) | 2023 | ✅ | 学习为目标数据集挑选辅助数据集；FreeSolv 总拖累其他数据集 | 同上；发表处待核 |
| [Task-specific pre-training for molecular property prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC12853129/) | 2026 Brief Bioinform | ◐ | 按任务选择预训练 | 相关工作 |
| [Enhancing molecular property prediction with auxiliary learning and task-specific adaptation](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11270959/) | 2024 J Cheminform | ◐ | 辅助任务的梯度式适配 | 相关工作 |
| [Multitask finetuning and acceleration of chemical pretrained models for small molecule drug property prediction](https://arxiv.org/pdf/2510.12719) | 2025 arXiv | ◐ | 多任务微调 | 相关工作 |
| A systematic study of key elements underlying molecular property prediction（Deng 等） | 2023 Nat Commun | ○ | 系统研究分子性质预测的关键因素 | 系统研究类先例 |

## C. 计算标签、量化信息与多保真度

| 文章 | 年份/发表处 | 核对 | 要点 | 用法 |
| --- | --- | --- | --- | --- |
| [Transfer learning with graph neural networks for improved molecular property prediction in the multi-fidelity setting](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11258334/)（Buterez 等） | 2024 Nat Commun | ✅ | 用低保真数据帮助预测同一性质的高保真值 | 多保真度先例；针对单一目标性质，不是表示预训练 |
| [Quantum-Informed Molecular Representation Learning Enhancing ADMET Property Prediction](https://pubs.acs.org/doi/10.1021/acs.jcim.4c00772) | 2024 JCIM | ◐ | 量化信息增强 ADMET 表示 | 相关工作 |
| [Supervised Pretraining for Molecular Force Fields and Properties Prediction](https://arxiv.org/pdf/2211.14429) | 2022 arXiv | ◐ | 用力场和性质做有监督预训练 | 物理监督先例 |
| [Self-Conditioned Denoising for Atomistic Representation Learning](https://arxiv.org/pdf/2603.17196) | 2026 arXiv | ◐ | 去噪式原子表示学习 | S 的去噪目标相关 |
| [Reducing the Cost of Quantum Chemical Data By Backpropagating Through DFT](https://arxiv.org/pdf/2402.04030)（Mathiasen 等） | 2024 arXiv | ✅ | 降低单次量化计算成本 | 成本角度的相关工作 |
| [Learning the Neighborhood: Contrast-Free Multimodal Self-Supervised Molecular Graph Pretraining](https://arxiv.org/pdf/2509.22468) | 2025 arXiv | ◐ | 自监督预训练 | S 相关 |

## D. 多任务学习、任务亲和度与混合专家

| 文章 | 年份/发表处 | 核对 | 要点 | 用法 |
| --- | --- | --- | --- | --- |
| Taskonomy: Disentangling Task Transfer Learning（Zamir 等） | 2018 CVPR | ○ | 视觉任务两两迁移图谱 | "通用对专用"问题的经典参照 |
| Which Tasks Should Be Learned Together in Multi-task Learning?（Standley 等） | 2020 ICML | ○ | 任务分组 | 任务亲和度 |
| Efficiently Identifying Task Groupings for Multi-Task Learning（TAG，Fifty 等） | 2021 NeurIPS | ○ | 用梯度前瞻估计任务亲和度 | 门控解释的对照方法 |
| Boosting Multitask Learning on Graphs through Higher-Order Task Affinities（Li 等） | 2023 KDD | ○ | 高阶任务亲和度、代理模型 | 同上 |
| Modeling Task Relationships in Multi-task Learning with Multi-gate Mixture-of-Experts（MMoE，Ma 等） | 2018 KDD | ○ | 多门控 MoE 处理任务关系 | E4 结构先例：共享加专用并非新点 |
| Progressive Layered Extraction（PLE，Tang 等） | 2020 RecSys | ○ | 共享专家加任务专用专家，专门解决负迁移 | 同上；审稿人最可能拿来比的结构 |
| DeepSeekMoE（Dai 等） | 2024 ACL | ○ | 大模型中的共享专家加路由专家 | 同上 |
| Sparse Upcycling: Training Mixture-of-Experts from Dense Checkpoints（Komatsuzaki 等） | 2023 ICLR | ○ | 从稠密检查点复制出专家继续训练 | E4 初始化方法 |
| [A Comprehensive Survey of Mixture-of-Experts](https://arxiv.org/pdf/2503.07137) | 2025 arXiv | ◐ | MoE 综述 | 背景 |
| [Enhancing Molecular Property Prediction via Mixture of Collaborative Experts（MoCE）](https://arxiv.org/pdf/2312.03292) | 2023 arXiv | ✅ | 任务描述引导路由，24 个分子数据集、35 个任务的有监督多任务 | 下游数据集多任务，无预训练 |
| [Omni-Mol: Multitask Molecular Model for Any-to-any Modalities](https://arxiv.org/html/2502.01074v3) | 2025 NeurIPS | ✅ | 大语言模型多任务；始终激活的锚定专家加路由专家；统一训练会拖累部分回归任务 | 说明共享加专用已是常见思路 |
| [Multi-View Mixture-of-Experts for Predicting Molecular Properties Using SMILES, SELFIES, and Graph-Based Representations](https://neurips.cc/virtual/2024/103777) | 2024 NeurIPS workshop | ◐ | 多视图 MoE | 相关工作 |
| [Topology-Aware Multiscale Mixture of Experts for Molecular Property Prediction](https://www.arxiv.org/pdf/2601.12637) | 2026 arXiv | ◐ | 按拓扑尺度分专家 | 相关工作 |
| [MolGraph-xLSTM](https://arxiv.org/pdf/2501.18439) | 2025 arXiv | ◐ | 多头 MoE 用于分子表示 | 相关工作 |
| [Adaptive Substructure-Aware Expert Model for Molecular Property Prediction](https://arxiv.org/html/2504.05844v1) | 2025 arXiv | ◐ | 按子结构分专家 | 相关工作 |
| [Task-customized Masked AutoEncoder via Mixture of Cluster-conditional Experts](https://arxiv.org/pdf/2402.05382) | 2024 | ◐ | 按聚类条件分专家的预训练 | 视觉领域的"按数据分专家"预训练 |
| [Modeling Task Relationships in Multi-variate Soft Sensor with Balanced Mixture-of-Experts](https://arxiv.org/pdf/2305.16360) | 2023 arXiv | ◐ | 平衡 MoE 处理任务关系 | 相关工作 |

## E. 用小规模实验预测大规模结果（家族析因的方法依据）

| 文章 | 年份/发表处 | 核对 | 要点 | 用法 |
| --- | --- | --- | --- | --- |
| RegMix: Data Mixture as Regression for Language Model Pre-training | 2025 ICLR | ○ | 小模型回归选择数据配比 | 家族析因可信度检查的依据 |
| Datamodels: Predicting Predictions from Training Data（Ilyas 等） | 2022 ICML | ○ | 用训练子集回归预测模型行为 | 同上 |
| Staged Factorial Screening | 2026 预印本 | ○ | 分阶段析因筛选 | 标题、作者均需核对 |

## F. 规模与算力

| 文章 | 年份/发表处 | 核对 | 要点 | 用法 |
| --- | --- | --- | --- | --- |
| [ChemFM as a scaling law guided foundation model pre-trained on informative chemicals](https://www.nature.com/articles/s42004-025-01793-8) | 2025 Commun Chem | ◐ | 缩放律指导的化学基础模型 | 规模分析相关；E6 基线 |
| [Unveiling Scaling Behaviors in Molecular Language Models](https://arxiv.org/html/2601.22757v1) | 2026 arXiv | ◐ | 模型大小、数据、表示对缩放的影响 | 规模分析相关 |
| [Bridging Compute- and Data-Optimal Pretraining](https://arxiv.org/pdf/2607.25271) | 2026 arXiv | ◐ | 算力最优与数据最优预训练 | H4 的算力讨论 |
| Training Compute-Optimal Large Language Models（Chinchilla，Hoffmann 等） | 2022 NeurIPS | ○ | 算力最优的模型与数据配比 | 背景 |
| [Foundation Models for Discovery and Exploration in Chemical Space](https://arxiv.org/html/2510.18900) | 2025 arXiv | ◐ | 化学基础模型综述 | 背景 |

## G. 基线模型（E6）

只列模型名和主要出处，核对状态均为 ○，投稿前逐一核对版本和 checkpoint 来源。

| 模型 | 主要出处 | 范式 |
| --- | --- | --- |
| Uni-Mol | Zhou 等，ICLR 2023 | 3D，原子类型加距离；对镜像不变 |
| GROVER | Rong 等，NeurIPS 2020 | 2D 图 Transformer 自监督 |
| Mole-BERT | Xia 等，ICLR 2023 | 2D 遮盖式自监督 |
| MolCLR | Wang 等，Nat Mach Intell 2022 | 2D 对比学习；同时在 v1 上重训 |
| MoLFormer | Ross 等，Nat Mach Intell 2022 | SMILES 语言模型 |
| MiniMol | Kläser 等，2024 arXiv | 多任务有监督预训练 |
| MACE / UMA | Batatia 等，NeurIPS 2022；UMA 见 A 组 | 等变力场 |
| CheMeleon、KPGT、ChemFM、OmniMol、qcGEM | 见 A、F 组 | — |
| Chemprop | Heid 等，JCIM 2024 | 非预训练 D-MPNN，可加描述符输入 |

## H. 范围之外，写进局限

| 文章 | 年份/发表处 | 核对 | 要点 |
| --- | --- | --- | --- |
| [Learning 3D representations of molecular chirality with invariance to bond rotations（ChIRo）](https://www.arxiv.org/pdf/2110.04383)（Adams, Pattanaik, Coley） | 2022 ICLR | ✅ | 手性感知 3D 表示和对映体基准 |
| [Learning Molecular Chirality via Chiral Determinant Kernels（ChiDeK）](https://arxiv.org/html/2602.07415) | 2026 ICLR | ✅ | 指出 SchNet、DimeNet 一类模型原理上无法区分对映体 |
| [Rem3Di: Learning smooth, chiral 3D molecular descriptors from atomistic foundation models](https://arxiv.org/pdf/2607.19977) | 2026 arXiv | ✅ | 手性在 TDC/MoleculeNet 中不是核心因素；仅靠 CIP 标签在骨架划分下效果大幅下降 |
| [Chi-Geometry: A Library for Benchmarking Chirality Prediction of GNNs](https://www.arxiv.org/pdf/2508.09097) | 2025 arXiv | ✅ | 手性预测基准库 |

## I. 数据与构象

| 文章 | 年份/发表处 | 核对 | 用法 |
| --- | --- | --- | --- |
| GEOM: Energy-annotated molecular conformations（Axelrod, Gómez-Bombarelli） | 2022 Sci Data | ○ | 每分子构象数不同的先例；构象去重与采样的讨论 |
