# P 数据信息研究：计划来源核查报告

2026-11-15（America/New_York）

状态：SOURCE_REVIEW_COMPLETE。本文完成的是仓库来源与实验范围核查；不是阶段 0–5 的新数值实验报告。没有读取服务器上的真实标签载荷，没有启动训练或单点计算。

## 本次完成了什么

针对用户要求，核对了已有计划书格式、可复用的旧数据线子集、过去数据分析的实际覆盖范围，并据此形成 TASKBOOK_V1.md。新计划以数据本身为对象，不把表征低秩、梯度或下游模型表现当作标签信息量的直接证据。

本次固定来源版本：

| 来源 | 提交 |
| --- | --- |
| 数据线 data-v1 | bc47699c709f57bb00108473f17bf4652333d2ec |
| 当前 P 研究 p-recipe | 5b42908d364e84e39bf384b19a5c6ab08d13ab63 |
| 历史 descriptor 分支，仅用于排除混淆 | 6cb8d8474ba8a78cced3bbb46ae4285a55530ef8 |

## 1. 计划书格式

已完整阅读仓库中可核实的 docs/model_v3/TASKBOOK_V3.md。新计划沿用其“本版范围与当前起点—已完成工作—总规则—固定实验规格—资源日程—日报与提交”的形式。

AGENTS.md 引用的根目录中文 P 任务书未收入本次 Git tree，不能宣称逐字读取了该外部文件；因此格式明确依据已读取的 TASKBOOK_V3.md。没有把旧模型任务书的训练网格、GPU 预算或已取消任务带入新计划。

## 2. 已核实的可复用子集

本次选择已交付的 v1-pilot-provisional / v3.1 pilot 作为母集：

- 50,000 TRAIN 和 5,000 ROUTINE VAL 分子。
- 两角色合计 509,194 条 P records；另有同数 U records。
- 共享根为 /lfshome/zixiao/data_v1_20261025/D3_v31_pilot_20261105_v1。
- 原成员表、schema、manifest 和 id_map 均有已提交交付引用。
- P 记录包含真实多构象；这个 U 导出只含 UFF 几何，不含 P′ 标签。
- 原 WP5 标签及原 native 数据保留；不使用已经退休的旧 v3.0 F64 sidecar。

母集成员及已发表 hash 已在 TASKBOOK_V1.md 写明。其成员排序 seed 20261025 与构象排序种子用途不同；执行时直接消费冻结成员表。

这一子集与两个其他集合不混用：

1. descriptor 分支是 2026 年 4 月的旧代码。其约 8k 的 principal_valid_test 索引切片没有证明是用户本次所指的数据线子集。
2. 最终 D5 的 120k/240k/600k 在改变后的完整 S′ 候选池上重新选择，不能用旧 pilot 的成员 hash 替代。

这里“本次选择”是本计划的具体实施选择，不声称已经找到另一份未提交 D 线计划书并确认其所指。

## 3. 数据身份连接可以怎样实现

pilot 紧凑导出的 ID map 实现记录 molecule_id、native_record_id、局部 molecule_index/conformer_index、holdout 以及 source_to_M 原子映射。schema 声明原 WP5 FP64 为权威值，并保留输入 Parquet 引用。

因此，新研究可以使用旧 pilot 的分子成员，通过稳定物理 ID 定点连接到原标签和当前 D6。不能直接把两个导出的局部整数索引对齐。

本次仅核实了这些字段和来源契约，尚未实测所选面板的 join 成功率、当前文件可访问性或标签共同有效率。这些是新计划阶段 0 的实际输出。

## 4. 之前已经研究过什么

| 证据 | 已有结果 | 尚未回答的部分 |
| --- | --- | --- |
| D7 构象统计 | 11,229,900 个可对齐 PM7 records，0.5 Å 固定映射规则下代表数 7,483,854 | 不是标签重复率，也不是本面板重复率 |
| 256 分子 FP64 生成热试点 | 分子内 max−min 中位数 1.03836、P75 5.975265 kcal/mol | 包含单构象/重复构象和来源选择偏差；未连接数值噪声与训练端保留 |
| 512 分子标签试点 | 146 字段，发现 8 个同分子数量级跳变组供复核 | 异常跳变筛查不等于细微构象信号辨识 |
| 全量 D4 | 分布、元素参考、尺度、median/MAD 已交付 | 没有系统完成同式异构和同分子构象差异判断 |
| P/P′ 比较 | 121 字段相关、850 分布系列 | 实现比较分子内有效叶子均值，不是同构象配对证据 |
| P0 D3 | 20,000 个 TRAIN 分子，每分子一个构象的总体/状态相关性 | 五状态不是五构象，未控制组成/身份 |
| 物理参考系检查 | 有实际通过、未通过及未知项 | 不可概括为所有 P 字段的物理语义全部通过 |
| FP32 导出检查 | 已有一次性数值检查 | 尚未测真实结构对的差值归零、方向翻转或相对幅度变化 |

还核实了两处容易误引的证据：

- P0 D1 加载旧 P checkpoint 计算预测误差，不是元素计数基线。
- 当前 A4 为 family_equal，均值标签路径是 C3；未将 A4 当作构象均值消融。

## 5. 本计划如何把缺口变成有界实验

阶段 0–5 依次覆盖定义/条件、结构覆盖、数值分辨率、条件区分度、联合信息/缺失以及处理链保留。

母集只读元数据；数值面板最多 5,000 TRAIN + 500 VAL 分子，每分子至多 10 个已有允许构象。因此最多读取 55,000 条 P 记录，构象标签主配对不超过 33,000 对，连接异构分子对不超过 3,300 对。

核心与同式富集分别报告，TRAIN 与 VAL 分开，组内重复配对不当独立样本。任何标签区分结论都同时报告实际覆盖、有效分母和精度证据；不以总体方差或相关秩作判决。

新训练为 0。新 QM 默认 0；仅当关键能量家族没有适用精度证据时，计划内阶段 2B 允许至多 32 次原方法单点数值校准。校准只用面板内 4 个分子的 8 个已有构象，给案例稳定性证据，不扩展到高等级真值研究。

每阶段完成即提交对应报告、聚合 JSON 与图并推送工作分支，不等待所有阶段结束。原数据和大缓存保持外部存储。

## 6. 当前完成状态

| 交付 | 状态 |
| --- | --- |
| 旧格式、子集来源和已有证据核查 | COMPLETE |
| 新任务书 | 已形成，可交由执行窗口逐阶段实施 |
| 子集 join、几何、标签差值和处理链数值 | NOT_RUN |
| 新模型训练 | 不在计划内 |
| 条件单点校准 | 尚未评估触发条件，未执行 |

## 7. 文档检查与 GitHub 交付

首次提交 9c08e7834c6736fa5e11257f572fdbfff02bd888 已发布到 docs/p-data-information-20261115，只新增本报告与 TASKBOOK_V1.md。本地文档候选集通过原 tools/check_repository.py，未声称在本地重跑完整仓库。

GitHub 的完整 Source checks 未通过。已读取并逐项比较本次首次提交与其原始基线的检查输出：

| 检查对象 | 错误数 | 本次新增文档的错误 |
| --- | ---: | ---: |
| 基线 p-recipe@5b42908d364e84e39bf384b19a5c6ab08d13ab63 | 202 | 不适用 |
| 本次首次文档提交 9c08e7834c6736fa5e11257f572fdbfff02bd888 | 202 | 0 |

错误集合逐项相同：111 项为已有文件格式与仓库数据/资产规则冲突，91 项超过已有 2 MiB 文件大小限制。本次新增错误为 0。这些是已有仓库内容的检查问题，不能写成“整仓检查通过”，也没有因此扩大本任务去删除历史产物或改检查规则。

- [本次完整检查](https://github.com/mint258/MFM/actions/runs/43788164925)
- [基线完整检查](https://github.com/mint258/MFM/actions/runs/43784255900)
- [首次文档提交](https://github.com/mint258/MFM/commit/9c08e7834c6736fa5e11257f572fdbfff02bd888)

## 来源索引

- [TASKBOOK_V3.md](https://github.com/mint258/MFM/blob/5b42908d364e84e39bf384b19a5c6ab08d13ab63/docs/model_v3/TASKBOOK_V3.md)
- [AGENTS.md](https://github.com/mint258/MFM/blob/5b42908d364e84e39bf384b19a5c6ab08d13ab63/AGENTS.md)
- [pilot 成员交付](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/configs/data_v1/D5_v1_pilot_provisional_delivery.json)
- [v3.1 pilot 导出交付](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/configs/data_v1/v1-pilot-provisional-v31/D3_export.json)
- [ID map 实现](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/workflows/data_v1_final/export/pilot_v31_compact_v1/run.py)
- [最终 Common/D5/D7](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/configs/data_v1/final_Common_D5_D7_v1_DELIVERY.json)
- [生成热构象试点](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/docs/data_v1/conformer_statistics_pilot_actual_v1.md)
- [512 分子标签试点](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/docs/data_v1/compact_label_profile_actual_v1.md)
- [D4 最终交付](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/configs/data_v1/window2_D4_final_DELIVERY.json)
- [P/P′ 比较实现](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/workflows/data_v1_final/labels/window2_pprime_statistics_v1/compare.py)
- [P0 实现](https://github.com/mint258/MFM/blob/5b42908d364e84e39bf384b19a5c6ab08d13ab63/tools/p_recipe/diagnose.py)
- [P 实验臂定义](https://github.com/mint258/MFM/blob/5b42908d364e84e39bf384b19a5c6ab08d13ab63/current/phychem_mfm/phase1/p_recipe_plan.py)
- [存储精度规范](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/docs/interfaces/training_format_v3_1_storage_revision_20261105.md)
- [已有 xTB 参考系检验](https://github.com/mint258/MFM/blob/bc47699c709f57bb00108473f17bf4652333d2ec/docs/interfaces/xtb_native_frame30_actual_results_20261029_v1.md)
