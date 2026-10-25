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
