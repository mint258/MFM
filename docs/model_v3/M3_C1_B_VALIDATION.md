# P/C1-b seed0：既有独立验证结果

原作业4529709在compute-0-6已COMPLETED 0:0，耗时00:34:38。本页于2026-11-12补发布该已关闭生产结果，没有重新运行验证，也不参与C1或任何模型/配方选择。

原6M检查点：`/lfshome/zixiao/model_v31_20261105/P_C1_b_seed0_micro32_continuation_20261110/samples_6000000.pt`。

| 人口 | 分子 | 实际构象 | 内容 |
| --- | ---: | ---: | --- |
| D6 FULL | 13815 | 126764 | 独立留出分子 |
| TRAIN_UNSEEN_CONFORMATION | 4292 | 4292 | 原240k已见分子的留出构象交集 |

逐字段训练损失和原始列原单位R²、MAE、观察数完整保留于[原生产结果](../../results/model_v3_c1_b_validation_seed0.json)。沿用现有`v2_validate_v31.py`及`validate_v31`的原字段、掩码、D4和原单位反变换；本次仅拷贝已关闭JSON并建立索引，没有重新计算数值、增加聚合或补入分子。全局20k诊断ID集合在原240k内的实际交集是4292，不将它记作20k。

这是预训练数据D6的FULL与TRAIN留出构象诊断，不是下游TEST评价。原结果中所有`selection_use=false`保持不变；模型选择继续使用预注册v2开发面板。
