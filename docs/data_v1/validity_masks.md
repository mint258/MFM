# v1 有效性掩码：v1-pilot-provisional

## 2026-11-05 当前交付边界

D-2至D-5的 `v1-pilot-provisional` 已交付：[正式D-4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D-3导出](../../configs/data_v1/v1-pilot-provisional/D3_export.json)及[同父D-5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload_D3_job4525880_bound.json)保留同一试点人口、原值与掩码。D-3实际父4525880已完成原唯一计数及1,000条原Parquet逐字段比较；这不替代全人群逐字段异常数量、原因分布、最严重样例或最终Common的独立交付。r674仍为 `LOSS_DISABLED`，不新增QM或改变科学掩码规则。当前数据交付事实见[接口状态](../interfaces/STATUS.md)与[训练导出报告](training_export_v1_pilot_provisional.md)。

以下2026-10-30及更早内容按原时间点保留；其中“待发布”“正在运行”等叙述不作为当前运行状态。

## 2026-10-30 暂定试点口径（历史）

当前试点固定为已有完整普通 S′ 的50,000个 TRAIN 与5,000个 ROUTINE VAL 分子，采用 D-1 v3.0 联合冻结政策。D-4作业4525252已完成所选标签缓存覆盖阶段，正在核验已有几何与实际程序输入的绑定；这不代表整个 D-4 已结束或数值报告已交付。

所选缓存保留全部146个有效字段的原始 F64 值、原始掩码、新增掩码、原因码、None及非有限值身份和原子/有序条目索引。每条 canonical base 与原14项任务的覆盖和重复检查已在本次 CPU 作业内完成。统计拟合资格与标签的科学有效性分别保存：VAL及已留出的诊断构象不进入 TRAIN 拟合，不把“禁止拟合”改写成标签异常。

正式数值状态以 `configs/data_v1/v1-pilot-provisional/D4_normalization.json` 及其实际 C0 引用链为准；该入口目前尚未发布。后续 D-3 使用同一人群、同一掩码和同一实际统计，原标签不会被缩尾值覆盖。r674维持 `LOSS_DISABLED`，原值、部分值和掩码仍保留；不追加 QM 或质心变换。原 MolMR 单位与历史独立坐标证据中的 UNKNOWN 不补默认值。

本次所选缓存的完整覆盖不等于全人群异常扫描验收。逐字段掩盖数量、原因分布、TRAIN median/MAD、z>20复核及各类严重度最高20例，仍须分别由实际数值报告证明。全人群报告继续作为后台定稿工作，不冒充已经完成，也不阻塞用户指定的四项暂定试点交付。既有科学规则和质量阈值不因本文档更新而放宽。

当前试点说明和交付入口见 [DATASET_V1_CARD.md](DATASET_V1_CARD.md)。下方为早期实现及当时的待执行记录，不能用作当前作业状态。

## 历史试点实现记录

# v1 有效性掩码：实现与待执行验收

目的：只掩盖无效标签，保留全部 canonical records。当前交付是可运行的有界试点代码和规则，尚未执行新科学数据扫描。

## 输入及来源

字段和规则分别位于 `configs/data_v1/label_registry_v3.json`、`configs/data_v1/labels/mask_rules_v1.json`。WP5 catalog 的 SHA256 为 `b5aed096ae0dc4c479a64b9b05e8709205911a0f9a474b71ae1490992ce28765`，采用的最终读回报告 SHA256 为 `ce9b58e988f66f8a402dc93eeb050a8f7b55317cfe37db3c3b1f08dd7b2045e5`。

`prepare_pilot_plan.py --check-catalog-only` 已在 compute-0-20 实际退出0，逐个交叉核验 catalog/readback 中 path、bytes、SHA、job 和 group，得到2024个 label family parquet 引用。收据在 `runs/data_v1_20261025/control/sb3_catalog_projection_v1/projection_receipt.json`。该操作只读小型 JSON，没有重新读取这些科学文件正文。

试点还需要 Root 提供带完整 owner identity 的新 record manifest 与新鲜 quota 收据；生成的 plan 对它们重新记录 path/bytes/SHA。字段字典和历史统计输入 pins 见注册表报告；新试点结果尚无 SHA，不填写未来数值。

## 已实现的规则

`canonical_reader.py` 只接受完整 record/molecule/attempt/job/task 身份匹配，P 家族另核 lane；同一 record/task 跨文件重复或逐字段覆盖数不符均失败。原子/原子对/basis 索引不进入物性数值。

`pilot_masks.py` 在默认 compute-0-20 的16核 Slurm 中 spawn 16个 worker，限制5,000条以内。此任务是CPU标签分析，不是量化或构象生成。分别保存原 source mask 与新增 mask，逐叶保留 float64 原值。NULL、ABSENT、EMPTY、非有限值、源失败状态、字段形状、numeric_issues 分开报告。

物理界仅来自定义：例如非负面积/体积/PMI、0–1的FractionCSP3、中性体系正IP。未确认的单位或物理界不猜测。电子 `converged=False` 会产生新增 mask；`NULL` 仅计数并复核，不能称为已证不收敛。

电荷和检验仅限中性对应任务，容差来自源舍入位数；精度未知则只复核。同一 PM7 上下文检查 IP−EA 与 LUMO−HOMO 符号；不把 GFN1 IP/EA 与 GFN2 轨道混作同一方法。z>20 只进入复核清单，不能自动掩盖。

## 数量、停止条件与输出

当前只有来源映射和登记元数据已运行；新 mask 数量、成功率、核时与字段最严重样例尚待 Root 提交试点。输出的 `newly_masked_records` 只计算原本 source-eligible 的叶被新增规则掩盖的 record；分母为全部 canonical in-scope record。既有缺失、63个N/A和5个ESP不混入新增异常。

任一 enabled 字段新增 mask record 比例超过1%，程序保存报告并退出2。已保存输出不删除，也不会自动提交全量。受控参考系、全分子跨构象跳变、TRAIN median/MAD 和每类最严重20例仍需后续实际扫描。当前试点仅给最先遇到的20例并明确标注非严重度排名，不冒充最终报告要求。

## 已知问题

EA 8791.0184 eV 已由历史审计在正式值中定位；三条补读记录为 SUCCESS、numeric_issues为空、converged和iterations为NULL，根因未知。样本7条异常不能外推全人群数量。新流程保留原值并按明示规则检查，不补造原始 SCF 文本或擅改任务状态。

完整试点输入协议、资源预算、CLI和模板见 `workflows/data_v1_final/labels/README.md`。Root 统一提交；当前模板不是全量运行许可或试点验收结果。
