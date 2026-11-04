# D-5 暂定交付：v1-pilot-provisional

[正式交付清单](../../configs/data_v1/D5_v1_pilot_provisional_delivery.json)已绑定实际 C0 作业、数据文件、字节数和 SHA，以及 Root 验收。适用范围为已有完整 S′ 的冻结暂定母人群；最终共同人群、D-6、D-7 后续另行发布。

| 清单 | 分子数 |
| --- | ---: |
| train_120000 | 120,000 |
| train_240000 | 240,000 |
| train_600000 | 600,000 |
| train_all | 1,108,366 |
| pilot_train | 50,000 |
| pilot_val | 5,000 |
| val_all | 7,016 |

TRAIN 子集为 120,000 ⊂ 240,000 ⊂ 600,000 ⊂ 1,108,366。试点为其中 50,000 个 TRAIN 分子和 5,000 个 ROUTINE VAL 分子。VAL 全清单的 7,016 个分子属于本次完整 S′ 母人群。

诊断集含 20,000 个 TRAIN 分子，留出 20,000 个 PM7 构象与 20,000 个普通 S′ 构象。留出目标及其全部已登记子几何和实际程序输入视图，已在取前 k 个构象之前从训练索引排除；诊断分子仍保留其他训练构象。该集合仅用于预训练损失诊断，不用于模型选择。

元素出现、重原子数和骨架分布的子集与全集对照，见正式清单中的 `distributions_manifest_reference`。实际几何、输入视图、字段绑定和训练索引也由同一清单引用。当前构象索引使用固定随机顺序；D-7 的能量和多样性顺序后续发布。

此报告由 `workflows/data_v1_final/reports/d5_pilot_provisional_v1.py` 从已接受的正式清单生成。清单与诊断集的计算、排除和回读实现为 `workflows/data_v1_final/export/bounded_old_complete_d5_resume_v2/`；实际生产作业为 4525184，终态 COMPLETED / 0:0。
