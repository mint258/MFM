# 标签注册表 v3：D2 元数据草案

目的：在保持 WP5、原 LMDB 和历史审计字节不变的前提下，提供逐字段可追溯的标签适配登记。此版本可以供接口开发审阅；不是最终科学冻结。

## 输入与复现

全部输入 pins 在 `configs/data_v1/labels/registry_sources_v1.json`；生成器为 `workflows/data_v1_final/labels/build_registry.py`。

| 输入 | 字节数 | SHA256 |
|---|---:|---|
| 既有字段字典 `wp5_registry_and_descriptor_fields_v1.json` |707031|`b4ca83de65f5702177a88ec4566f8ff7a708c44625178cc6151b6c6912e3c976`|
| 已闭合 TRAIN 分量统计 `all_field_statistics.csv` |138838|`eea97cd80c4103944c80cd3aeba6269937407f8358b8a0f99e45ed087e60b008`|

两份文件都来自 `runs/pretraining_readonly_audit_20261023_v1/`；实际生成在 compute-0-20 使用 `/share/home/zixiao/.conda/envs/chemprop/bin/python -B`，退出0。收据为 `runs/data_v1_20261025/control/sb3_registry_generation_v1.json`。生成 JSON 为585411字节，SHA256 `b6a230b74b5bebfa0108e67572ed2ccc699718c2958fb69e99c58b8323c6ce45`。

## 已生成内容

| 类别 | 分量数 | 说明 |
|---|---:|---|
| enabled |146|历史 TRAIN 中有值且非常数；不代表新 mask 或最终归一化已通过|
| N/A |103|对应63个原 registry 字段；非任务 required scope，不补算|
| deleted |10|五种 PM7 任务的 f、unknown 壳层恒零分量|
| legacy_inactive |5|旧 ESP 占位，独立保留原因，不混入 N/A 或新异常|
| 合计 |264|237个 P 分量（含ESP）＋20个D20＋7个D3|

生成器实际核验分子级标量为 **43个P＋26个D**。D 共27个字段，其中 `SASA_atom_A2` 为原子级；不能按指南中的42/27将它变成分子标量。146是当前统计分量数量，不等于146个独立预测头；xyz、复合字段分量与原源 registry 字段的关系均保留。

每项含：原 registry ID（D 不伪造数值ID）、source path/component、组别、启用状态和原因、源 family、任务、层级、形状、单位、方法/电荷、几何上下文、源表示、mask 通道、物理定义约束、广延性及池化建议。P′ 沿用 P 字段ID，但采用 `uff_sprime` 几何来源和独立统计量，未声称已有计算结果。S 的坐标/元素属于生成式监督配方，单列元数据，不虚增 WP5 标签数。

## 矢量及原子顺序

偶极矩保存为 `[3]` 的 xyz 分量，单位 Debye，不是模长。PM7 梯度可为 `[3N]`，单位 kcal·mol⁻¹·Å⁻¹；xTB 扰动梯度为 `[N,3]` 的 dE/dR，单位 Eh/bohr；力为 `[N,3]`，单位 eV/Å，符号为 `force=-gradient×EH_TO_EV/BOHR_TO_A`。新适配器保留原子索引、shape、源 CELL kind 与参考单位。

源引擎按原始 native 原子顺序渲染坐标，没有主动旋转。输出矢量轴与所存坐标的等价性仍标 `PENDING_CONTROLLED_READBACK`：代码中的元素序检查不能替代坐标和参考系实测。模长只有在源中独立存在时才能作为独立一致性检查，不能用同一向量新算模长后自证。

## 尺寸家族与归一化状态

`family_v1_provisional` 只按物理语义预分类，COSMO面积/体积归 size。`family_v1_final`、Spearman ρ、pairN 明确待新的冻结 TRAIN 计算；生成热必须扣除 TRAIN 元素参考后再判定。原始未校正相关不得冒充这一结果。非标量相关还需明确旋转一致、按分子计算的聚合定义。

VAL 采用用户已指定的既有 ROUTINE；不重新切分 TRAIN。最终 TRAIN、common population、diagnostic geometry 排除清单尚未同时冻结时，不能发布最终归一化。历史 TRAIN 数字只用于元数据启用状态映射，不作为新的尺度、异常阈值或模型选择依据。

## 异常与限制

生成首轮曾在未明确分类 `core_core_repulsion_eV` 时拒绝；已将 core-core 与 ENPART 明确归入 energy 后，生成器实际退出0，未读科学 parquet 正文或改原值。

目前还需完成新角色/共同人群冻结、全人群 mask、物理/参考系受控校验、TRAIN size ρ、元素参考、P′统计及模型线意见对齐。所有这些缺口保留在 JSON 的 freeze dependencies 中。登记草案不能作为全量数据或模型已经可训练的声明。
