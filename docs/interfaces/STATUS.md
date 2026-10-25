# 数据线与模型线接口状态

更新时间：2026-10-25，数据线分支 `data-v1`。

**当前：Se例外已批准，用户明确指定既有ROUTINE作为VAL；正在冻结身份清单和准备试点。**

- D-1草案已发布：[training_format_v3.md](training_format_v3.md)。尚未双方定为v3.0，原家族留出文字正在按用户纠正更新。
- VAL以ROUTINE的分子ID决定，预期7610分子、原ROUTINE11322条记录；同分子的全部几何保留同一VAL角色，原记录成员标记另留。实际ID/化学身份交叉检查和manifest待Slurm核验。
- 不再从TRAIN抽取家族。原TRAIN/FULL的分布比较仍有效：[分布核验](../data_v1/validation_population_review.md)。
- S′补齐与注册表/掩码流程正在独立分支实现。D-2至D-7、P′及扩充真实数据尚未交付。
- 仅对Se单元素排除率>20%作例外，仍排除UFF_UNSUPPORTED，其它阈值不变。

当前决定以configs/data_v1/run_decisions_v2.json为准；旧启动报告和v1决定作为历史保留。模型线可审阅D1草案，真实新数据加载仍待试点导出。
