from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("data/openadmet_leaderboard")


COLUMN_ZH = {
    "rank": "排名",
    "final rank": "最终排名",
    "initial rank": "初始排名",
    "user": "用户/队伍",
    "CLD": "CLD",
    "MA-RAE": "MA-RAE",
    "MAE_display": "MAE_显示值",
    "RAE_display": "RAE_显示值",
    "R2": "R2",
    "R2_display": "R2_显示值",
    "Spearman R": "Spearman R",
    "Spearman R_display": "Spearman R_显示值",
    "Kendall's Tau": "Kendall's Tau",
    "Kendall's Tau_display": "Kendall's Tau_显示值",
    "submission time": "提交时间",
    "model details": "模型说明链接",
    "official_top20_model_type": "官方Top20_模型类型",
    "official_from_pretrained": "官方Top20_是否使用预训练",
    "official_external_public_data": "官方Top20_是否使用外部公开数据",
    "official_proprietary_data": "官方Top20_是否使用私有数据",
    "official_descriptors": "官方Top20_描述符/指纹",
    "official_multitasking": "官方Top20_是否多任务",
    "official_data_augmentation": "官方Top20_数据增强",
    "official_split_strategy": "官方Top20_划分策略",
    "official_hpo": "官方Top20_超参数优化",
    "method_review_scope": "方法审阅范围",
    "q1_external_data_pretraining_transfer": "问题1_外部数据_预训练_迁移方式",
    "q2_molecular_representation": "问题2_分子表示方式",
    "q3_training_model_architecture": "问题3_训练模型架构",
    "q4_task_training_strategy": "问题4_九任务训练策略",
    "q5_final_averaging_ensemble": "问题5_最终平均或集成方式",
    "method_source_notes": "方法来源备注",
}


VALUE_ZH = {
    "not reviewed": "未审阅",
    "NM": "未说明",
    "No": "否",
    "No?": "可能否",
    "Yes": "是",
    "likely": "可能是",
    "lightly": "轻量级",
    "small gain": "小幅收益",
    "Chemprop+ML": "Chemprop + 机器学习",
    "Chemprop, KERMT": "Chemprop、KERMT",
    "Chemprop/KERMT": "Chemprop / KERMT",
    "Chemprop/TabPFN": "Chemprop / TabPFN",
    "Chempropv2 + ML": "Chemprop v2 + 机器学习",
    "Chempropv2+TabPFN+ML": "Chemprop v2 + TabPFN + 机器学习",
    "GNN Ensemble": "GNN 集成",
    "GNN/Transformer/Chemprop": "GNN / Transformer / Chemprop",
    "Hybrid MPNN+ML": "混合 MPNN + 机器学习",
    "Uni-Mol2 + GNN": "Uni-Mol2 + GNN",
    "Yes (CheMeleon)": "是（CheMeleon）",
    "Yes (CheMeleon, CLAMP)": "是（CheMeleon、CLAMP）",
    "Yes (CheMeleon, own)": "是（CheMeleon、自研预训练）",
    "Yes (Uni-Mol2)": "是（Uni-Mol2）",
    "Yes (arxiv pre-trained Chemprop)": "是（arXiv 预训练 Chemprop）",
    "Yes (Fingerprints)": "是（分子指纹）",
    "Yes (MACCS/ErG)": "是（MACCS / ErG）",
    "Yes (MPNN-learned)": "是（MPNN 学习表示）",
    "Yes (MolGraph)": "是（MolGraph）",
    "Yes (MolGraph,Maplight)": "是（MolGraph、MapLight）",
    "Yes (Mordred,ECFP,Jazzy)": "是（Mordred、ECFP、Jazzy）",
    "Yes (RDKit)": "是（RDKit）",
    "Yes (RDKit, MiniMol)": "是（RDKit、MiniMol）",
    "Yes (RDKit, Mordred, ADMET-AI)": "是（RDKit、Mordred、ADMET-AI）",
    "Yes (RDKit,Jazzy)": "是（RDKit、Jazzy）",
    "Yes (RDKit,Jazzy,MOE,QM)": "是（RDKit、Jazzy、MOE、QM）",
    "Yes (RDKit,Morgan,Boltz-2,kNN)": "是（RDKit、Morgan、Boltz-2、kNN）",
    "Yes (TPSA, ESOL, MD)": "是（TPSA、ESOL、MD）",
    "Yes (RIGR)": "是（RIGR）",
    "Yes (SMILES)": "是（SMILES）",
    "Yes (de novo gen)": "是（从头生成）",
    "Yes (kNN)": "是（kNN）",
    "Difficulty-biased": "难度偏置划分",
    "Random": "随机划分",
    "Random CV": "随机交叉验证",
    "Scaffold": "骨架划分",
    "Similarity-based": "相似性划分",
    "Temporal": "时间划分",
    "Temporal/Cluster": "时间 / 聚类划分",
    "Temporal/Random": "时间 / 随机划分",
    "reviewed_top20_github": "已审阅：Top20 GitHub 文档",
    "reviewed_top20_github_shared_repo": "已审阅：Top20 共享 GitHub 仓库",
    "reviewed_top20_google_doc": "已审阅：Top20 Google 文档",
    "reviewed_top20_google_doc_or_summary": "已审阅：Top20 Google 文档或官方摘要",
    "reviewed_top20_published_doc": "已审阅：Top20 发布版文档",
    "top20_official_summary_only": "仅依据官方 Top20 摘要",
    "Not specified.": "未说明。",
    "Official top20 summary only.": "仅依据官方 Top20 摘要。",
    "Official top20 summary; linked doc partially reviewed.": "依据官方 Top20 摘要；链接文档仅部分可审阅。",
}


METHOD_ZH = {
    "pebble": {
        "q1_external_data_pretraining_transfer": "同时使用仅基于比赛数据的模型，以及基于整理后的公开数据和私有 ADMET 数据训练的模型。额外 ADMET 数据用于相近任务组；迁移方式是按任务组进行监督训练，并在相关组中加入辅助性质。",
        "q2_molecular_representation": "使用图神经网络学习到的分子表示；官方报告中未提到额外描述符。",
        "q3_training_model_architecture": "多个 GNN 架构组成的集成模型，按任务组监督训练，并使用 Optuna 进行优化。",
        "q4_task_training_strategy": "按任务分组训练：{LogD}、{KSOL}、{MLM,HLM}、{Caco Papp,Caco ER}、{MPPB,MGMB,MBPB}；部分组加入 LogD、pKa 等辅助性质。",
        "q5_final_averaging_ensemble": "是。基于交叉验证 out-of-fold 预测构建 Caruana ensemble。",
        "method_source_notes": "Inductive Bio/Pebble 模型报告及官方 Top20 摘要。",
    },
    "overfit": {
        "q1_external_data_pretraining_transfer": "在可用时使用私有数据集，并微调文献中已有的预训练 Chemprop 模型。迁移方式是对 Chemprop 多任务和单任务模型进行训练/微调。",
        "q2_molecular_representation": "直接从分子图/SMILES 输入 Chemprop message passing；未加入额外描述符或特征。",
        "q3_training_model_architecture": "Chemprop v2 多任务和单任务模型；官方摘要也列出 KERMT。",
        "q4_task_training_strategy": "同时使用多任务和单任务 Chemprop；具体 endpoint 分组未说明。",
        "q5_final_averaging_ensemble": "由多个模型组成的 ensemble，但具体平均方式未说明。",
        "method_source_notes": "Overfit Google 文档及官方 Top20 摘要。",
    },
    "moka": {
        "q1_external_data_pretraining_transfer": "使用 Large 和 ADME 预训练数据集，其中包含公开数据和内部数据；CheMeleon 作为已有描述符预训练 Chemprop 使用。迁移方式是按 endpoint 分组微调。",
        "q2_molecular_representation": "组合多种图表示与描述符：GatedGCN、GraphGPS、GIN、拼接 RDKit 描述符的 Chemprop、CheMeleon、Jazzy、显著 MOE 描述符等。",
        "q3_training_model_architecture": "GatedGCN 加 virtual node、GraphGPS transformer、带位置编码的 GIN、拼接 RDKit 描述符的 Chemprop；使用 AdamW/MAE 多任务训练。",
        "q4_task_training_strategy": "四个 endpoint 组分别独立训练：MPPB/MBPB/MGMB；HLM/MLM；LogD/KSOL；Caco Papp/Efflux。",
        "q5_final_averaging_ensemble": "是。每种架构通过 CV/数据切片训练 10 个模型，最终对模型预测做简单平均。",
        "method_source_notes": "moka GitHub README 及官方 Top20 摘要。",
    },
    "campfire-capillary": {
        "q1_external_data_pretraining_transfer": "使用筛选后的外部数据，并对部分 endpoint 加入内部私有数据，同时设置任务特异的权重。迁移方式是对扩充后的 endpoint 数据进行监督训练/再训练。",
        "q2_molecular_representation": "组合图模型表示与由 scikit-fingerprints 生成的传统描述符/指纹。",
        "q3_training_model_architecture": "多任务 MPNN、图 transformer，以及 AutoGluon 经典机器学习模型套件；深度学习部分使用 Ray Tune/HyperBand 做超参数搜索。",
        "q4_task_training_strategy": "使用多任务 MPNN；部分 endpoint 有额外处理；九个任务的精确分组未说明。",
        "q5_final_averaging_ensemble": "是。将表现最好的传统机器学习模型与深度学习模型聚合成异构 ensemble。",
        "method_source_notes": "campfire GitHub README 及官方 Top20 摘要。",
    },
    "shin-chan": {
        "q1_external_data_pretraining_transfer": "仅使用公开数据，在 108 个公开 ADME 任务、约 45 万数据点上预训练，并过滤化合物重叠；加入 TPSA、ESOL、MD 派生性质等计算型辅助任务。迁移方式是 Chemprop 多任务微调。",
        "q2_molecular_representation": "Chemprop D-MPNN 分子图表示，并加入计算型辅助任务/性质（TPSA、ESOL、MD 派生性质）。",
        "q3_training_model_architecture": "Chemprop v2.2.1 多任务 D-MPNN，使用自定义 L1 不确定性损失和贝叶斯超参数优化。",
        "q4_task_training_strategy": "根据 Spearman 相关性进行任务亲和分组；例如 LogD/LogS/蛋白结合组、LogD/HLM/MLM 组，以及单任务 Caco endpoints。",
        "q5_final_averaging_ensemble": "是。最终提交平均了 5 个不同随机种子的模型。",
        "method_source_notes": "shin-chan Google 文档及官方 Top20 摘要。",
    },
    "HybridADMET": {
        "q1_external_data_pretraining_transfer": "没有使用外部/私有性质数据。使用公开 Uni-Mol2 checkpoint，其预训练来自分子结构信息；随后在本比赛任务上端到端微调全部参数。",
        "q2_molecular_representation": "Uni-Mol2 transformer、PAMNet GNN，以及 MACCS/ErG/PubChem 指纹的混合表示。",
        "q3_training_model_architecture": "端到端混合神经网络，包含 Uni-Mol2 encoder、PAMNet 分支和 fingerprint 分支。",
        "q4_task_training_strategy": "针对不同目标使用不同输入目标组进行建模；不是一个统一的全任务模型。",
        "q5_final_averaging_ensemble": "根据 leaderboard 做模型选择；是否显式进行多模型平均未说明。",
        "method_source_notes": "HybridADMET Google 文档及官方 Top20 摘要。",
    },
    "rced_nvx": {
        "q1_external_data_pretraining_transfer": "仅使用公开数据。使用公开学习型 embedding/基础模型表示，例如 CheMeleon、MiniMol、CLAMP；无私有数据。迁移方式是把这些表示作为特征，与比赛标签训练下游模型。",
        "q2_molecular_representation": "组合 ECFP4/FCFP4/Avalon 指纹、RDKit2D/Mordred/ADMET-AI 描述符，以及 CheMeleon/MiniMol/CLAMP 学习型 embedding。",
        "q3_training_model_architecture": "Chemprop 2.2 MPNN、TabPFN v2、Random Forest、LightGBM、XGBoost 的加权平均 ensemble。",
        "q4_task_training_strategy": "官方摘要显示使用多任务；具体 endpoint 分组未说明。",
        "q5_final_averaging_ensemble": "是。多个模型加权平均，且未进行 HPO。",
        "method_source_notes": "rced_nvx GitHub README 及官方 Top20 摘要。",
    },
    "tibo": {
        "q1_external_data_pretraining_transfer": "使用比赛数据和整理后的公开数据；无私有数据。重构公开 TDC 方案；尝试 C-MixUp 和 RIGR 数据增强。迁移方式是特征化后训练多个下游模型。",
        "q2_molecular_representation": "ECFP4/FCFP4/Avalon 指纹、RDKit2D/Mordred/ADMET-AI 描述符、CheMeleon/MiniMol/CLAMP embedding。",
        "q3_training_model_architecture": "经典机器学习 RF/XGB/LightGBM、Chemprop v2 MPNN、TabPFN v2，以及重构的 MapLight-TDC 和 CaliciBoost 方法。",
        "q4_task_training_strategy": "提到多任务和任务特异特征工程；九个任务的精确分组未说明。",
        "q5_final_averaging_ensemble": "是。对中间提交结果进行加权平均。",
        "method_source_notes": "tibo GitHub README 及官方 Top20 摘要。",
    },
    "beetroot": {
        "q1_external_data_pretraining_transfer": "使用比赛数据和整理后的公开数据，无私有数据。使用 CheMeleon/已发表模型/内部公开 ADMET 多任务权重，并在 1000 万个比赛化学空间附近的从头生成分子上进行自研预训练。迁移方式是 Chemprop 分组微调。",
        "q2_molecular_representation": "Chemprop 图表示，并用 CheMeleon/自研预训练初始化；Mordred、ECFP、Jazzy 和计算型辅助性质作为任务或特征。",
        "q3_training_model_architecture": "Chemprop v2 ensemble，包含 Bounded-MSE/MVE 估计器、冻结 MPNN warm-up 后解冻、逐任务损失加权。",
        "q4_task_training_strategy": "基于任务亲和性的多任务分组训练，并进行 endpoint 级优化；辅助任务降权。",
        "q5_final_averaging_ensemble": "是。多个 Chemprop 方案集成；部分 endpoint 使用加权平均。",
        "method_source_notes": "beetroot 发布版 Google 文档及官方 Top20 摘要。",
    },
    "temal": {
        "q1_external_data_pretraining_transfer": "官方摘要显示使用了外部公开数据；是否预训练未说明。",
        "q2_molecular_representation": "可访问摘要中未说明。",
        "q3_training_model_architecture": "Chemprop。",
        "q4_task_training_strategy": "官方摘要显示使用多任务；具体分组未说明。",
        "q5_final_averaging_ensemble": "未说明。",
        "method_source_notes": "仅依据官方 Top20 摘要。",
    },
    "yanyn": {
        "q1_external_data_pretraining_transfer": "LogD 单任务模型使用公开数据；使用 CheMeleon 基础模型。迁移方式是在比赛任务上训练 Chemprop/CheMeleon 和 KERMT 多任务模型。",
        "q2_molecular_representation": "Chemprop 分子图/CheMeleon 基础表示和 KERMT 图表示；官方摘要中也提到 RDKit。",
        "q3_training_model_architecture": "多个不同超参数的 Chemprop/CheMeleon 多任务模型，加上四个 KERMT 多任务模型。",
        "q4_task_training_strategy": "除 LogD 使用带公开数据的单任务训练外，其余任务使用多任务训练。",
        "q5_final_averaging_ensemble": "是。10-fold CV 评估后，只集成测试 MAE 低于阈值的模型。",
        "method_source_notes": "yanyn GitHub README 及官方 Top20 摘要。",
    },
    "crh201": {
        "q1_external_data_pretraining_transfer": "使用私有/内部数据，公开 HLM/MLM 数据校正，CheMeleon/AZ 权重，以及自研 Chemprop foundation model 到 Mordred 指纹的从头预训练。迁移方式是按任务亲和组进行 Chemprop 微调。",
        "q2_molecular_representation": "Chemprop 图表示，并按任务亲和组选择 Mordred/Jazzy/ECFP 特征。",
        "q3_training_model_architecture": "Chemprop v2，使用 bounded-MSE loss；CheMeleon 式描述符预训练；从冻结到解冻 MPNN 的适配流程。",
        "q4_task_training_strategy": "使用 endpoint 级和多任务优化，并按任务亲和性分组；精确分组未说明。",
        "q5_final_averaging_ensemble": "暗示集成了预训练/模型变体；具体平均方式未说明。",
        "method_source_notes": "crh201 Google 文档及官方 Top20 摘要。",
    },
    "arabica": {
        "q1_external_data_pretraining_transfer": "使用公开 Galapagos Polaris、Novartis 数据集，以及计算得到的 CDD LogD/pKa 辅助值；无私有数据。迁移方式是在比赛任务和辅助 endpoint 上进行 Chemprop 多任务训练。",
        "q2_molecular_representation": "MolGraph Chemprop 表示，并可加入 MapLight 特征：Morgan、Avalon、ErG、MACCS。",
        "q3_training_model_architecture": "Chemprop GNN，使用手动选择的超参数；也探索了 Ray Tune HPO。",
        "q4_task_training_strategy": "在 ExpansionRx 和辅助 endpoint 上进行多任务学习。",
        "q5_final_averaging_ensemble": "是。提交结果平均了 5 个随机划分训练得到的 checkpoint 预测。",
        "method_source_notes": "Ngoson2004 GitHub README 及官方 Top20 摘要。",
    },
    "Gashaw": {
        "q1_external_data_pretraining_transfer": "没有使用外部公开/私有数据，也没有外部预训练；仅在提供的数据上从头训练。",
        "q2_molecular_representation": "Morgan/ECFP4、FCFP4、MACCS、Avalon 指纹；RDKit 描述符；Chemprop MPNN embedding；ChemBERTa embedding；并按目标拼接不同描述符。",
        "q3_training_model_architecture": "Chemprop 2.2.1 单任务/子多任务/多任务 MPNN；在有用时使用 XGBoost、LightGBM、CatBoost、RF、ExtraTrees、Ridge、Huber 等经典机器学习 stacking。",
        "q4_task_training_strategy": "主要是单任务；子多任务包括 LogD+LogS 和 PPB+BPB+MPB；Caco ER 使用经典机器学习 stack。",
        "q5_final_averaging_ensemble": "是。跨 5 个 CV fold 平均预测；部分 endpoint 做残差修正/stacking。",
        "method_source_notes": "Gashaw Google 文档及官方 Top20 摘要。",
    },
    "c-test": {
        "q1_external_data_pretraining_transfer": "官方摘要显示使用了预训练模型；未提到外部公开数据；无私有数据。",
        "q2_molecular_representation": "官方摘要显示未使用描述符；很可能直接使用图表示/基础模型表示。",
        "q3_training_model_architecture": "Chemprop / KERMT。",
        "q4_task_training_strategy": "使用多任务；具体分组未说明。",
        "q5_final_averaging_ensemble": "未说明。",
        "method_source_notes": "仅依据官方 Top20 摘要。",
    },
    "Universal15": {
        "q1_external_data_pretraining_transfer": "官方摘要显示使用预训练 KERMT 和外部公开数据；无私有数据。",
        "q2_molecular_representation": "KERMT 图表示加 RDKit 描述符。",
        "q3_training_model_architecture": "KERMT。",
        "q4_task_training_strategy": "使用多任务；具体分组未说明。",
        "q5_final_averaging_ensemble": "未说明。",
        "method_source_notes": "依据官方 Top20 摘要；链接文档仅部分可审阅。",
    },
    "echo": {
        "q1_external_data_pretraining_transfer": "官方摘要显示使用 CheMeleon 预训练模型和外部公开数据；无私有数据。",
        "q2_molecular_representation": "除 Chemprop/KERMT 风格学习表示外，官方摘要未说明更多细节。",
        "q3_training_model_architecture": "Chemprop / KERMT。",
        "q4_task_training_strategy": "使用多任务；具体分组未说明。",
        "q5_final_averaging_ensemble": "未说明。",
        "method_source_notes": "仅依据官方 Top20 摘要。",
    },
    "Artichoke": {
        "q1_external_data_pretraining_transfer": "先进行大规模公开 ADMET 多任务预训练，再做 endpoint 特异微调；官方摘要显示无私有数据。迁移方式包括用 CheMeleon 初始化 Chemprop MPNN，并将公开模型/描述符预测作为下游 stack 特征。",
        "q2_molecular_representation": "Chemprop 学习 embedding、RDKit 理化描述符、Morgan/MACCS/atom-pair/torsion 指纹、Boltz-2 binding affinity 预测、kNN/local 特征，以及相关任务预测。",
        "q3_training_model_architecture": "CheMeleon 初始化的 Chemprop MPNN，加 LightGBM、CatBoost、XGBoost、ExtraTrees、ridge/elastic-net、TabPFN、kNN/local ridge 修正、stacked meta-learner 等。",
        "q4_task_training_strategy": "先多任务预训练和跨 endpoint 迁移；下游使用 endpoint 特异 stack，并把相关任务预测作为特征。",
        "q5_final_averaging_ensemble": "是。使用 stacked meta-learner、学习型 gating network、局部相似性修正，以及基于不确定性/分歧/可靠性特征的自适应 blending。",
        "method_source_notes": "Artichoke Google 文档及官方 Top20 摘要。",
    },
    "UncertainTea": {
        "q1_external_data_pretraining_transfer": "官方摘要显示未使用外部数据；但使用外部预训练/已发表预测器作为特征，例如 CheMeleon、MiniMol、AZ-pred、ChemAxon/Jazzy 特征。迁移方式是将这些表示或预测作为比赛任务特征。",
        "q2_molecular_representation": "RDKit2D/3D、ECFP4、Avalon、ErG、ChemAxon、Jazzy、CheMeleon embedding、MiniMol embedding、AZ-pred 预测。",
        "q3_training_model_architecture": "三个 Chemprop 多任务网络，加 TabPFN v2.5 的共享特征模型和 endpoint 特异特征模型。",
        "q4_task_training_strategy": "Chemprop 跨所有 endpoint 多任务训练；TabPFN 使用共享特征集和 endpoint 特异特征集。",
        "q5_final_averaging_ensemble": "是。最终提交为多个建模策略预测的 winsorized mean。",
        "method_source_notes": "UncertainTea GitHub README 及官方 Top20 摘要。",
    },
    "liberica": {
        "q1_external_data_pretraining_transfer": "使用公开 Galapagos Polaris 和 Novartis 数据集，以及 CDD 计算 LogD/pKa 辅助值；无私有数据。迁移方式是结合整理后的辅助 endpoint 进行 Chemprop 多任务训练。",
        "q2_molecular_representation": "MolGraph Chemprop 表示；官方摘要强调 MolGraph。",
        "q3_training_model_architecture": "Chemprop GNN。",
        "q4_task_training_strategy": "在 ExpansionRx 和辅助 endpoint 上进行多任务学习。",
        "q5_final_averaging_ensemble": "可能使用共享仓库流程中的 checkpoint 平均；官方摘要称无 HPO、随机划分，liberica 的具体 ensemble 未单独说明。",
        "method_source_notes": "Ngoson2004 GitHub README 及官方 Top20 摘要。",
    },
}


METHOD_COLS = [
    "q1_external_data_pretraining_transfer",
    "q2_molecular_representation",
    "q3_training_model_architecture",
    "q4_task_training_strategy",
    "q5_final_averaging_ensemble",
    "method_source_notes",
]


def translate_cell(value: object) -> object:
    if pd.isna(value):
        return value
    text = str(value)
    return VALUE_ZH.get(text, text)


def translate_file(src: Path, dst: Path) -> None:
    df = pd.read_csv(src)

    for col in df.columns:
        if col in METHOD_COLS:
            continue
        if df[col].dtype == object:
            df[col] = df[col].map(translate_cell)

    for idx, row in df.iterrows():
        user = row.get("user")
        method = METHOD_ZH.get(user)
        if method is not None:
            for col in METHOD_COLS:
                if col in df.columns:
                    df.at[idx, col] = method[col]
        else:
            for col in METHOD_COLS:
                if col in df.columns and isinstance(df.at[idx, col], str):
                    df.at[idx, col] = translate_cell(df.at[idx, col])

    df = df.rename(columns={col: COLUMN_ZH.get(col, col) for col in df.columns})
    df.to_csv(dst, index=False, encoding="utf-8-sig")


def main() -> None:
    outputs = [
        (ROOT / "current_leaderboard.csv", ROOT / "current_leaderboard_zh.csv"),
        (ROOT / "leaderboard_cld_results.csv", ROOT / "leaderboard_cld_results_zh.csv"),
    ]
    for src, dst in outputs:
        translate_file(src, dst)
        print(f"wrote {dst}")


if __name__ == "__main__":
    main()
