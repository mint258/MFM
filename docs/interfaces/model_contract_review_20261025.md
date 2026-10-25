# 模型—数据接口交叉审阅（2026-10-25）

状态：数据线根据两份工作指南与当前草案所做的文档交叉检查。本文不是模型线实际反馈，不表示双方已确认冲突或共同签字；契约仍为DRAFT，未定为v3.0。本文保留全部启用标签，仅列出共同定稿前需要明确的接口事项。

## 目的与输入

对照模型线指南的接口依赖、阶段3加载器/预测头/损失及等变性验收，检查D1 draft.2、登记表draft.1和已冻结来源角色能否被同一加载器无歧义解释。本次只读取文档及小型JSON元数据，没有运行模型、量化计算、标签扫描或Slurm。

下列路径以Root工作仓库为相对根；模型线指南在X盘项目根。读取快照的bytes/SHA256为：

|输入|bytes|SHA256|
|---|---:|---|
|模型线工作流程：模型 v3、训练代码与训练配方（Codex A）.md|26121|e618165501d22556c4c421d93f1c01928fab3f50202ce6d0fec3249c79921239|
|docs/interfaces/training_format_v3.md，v3.0-draft.2|13050|8fb8913527e67ec997e7c3d536f349de4ec50b08541438a7e047d3ff63b002dd|
|configs/data_v1/label_registry_v3.json，draft.1|585411|b6a230b74b5bebfa0108e67572ed2ccc699718c2958fb69e99c58b8323c6ce45|
|configs/data_v1/export/roles_authority_v1.json|1314|a6d47c06efd40ad19ef9aad1efbb18c888f172d1e9c79bd36550448274778f6c|

下述计数来自该登记表或角色JSON，不是新数据扫描。文件后续修订须按新哈希重新确认本审阅的适用范围。

## 1. 146统计分量不能直接作为146个预测头或损失等权单位

登记表enabled行的层级分布为：

|登记level|enabled行数|接口含义|
|---|---:|---|
|molecule|69|43P＋26D分子标量|
|atom|39|含逐原子SASA；每行仍须解析其具体component|
|sparse_atom_pair|11|原子对值及本字段自己的稀疏索引|
|molecule_vector|18|六个偶极矩任务各xyz三行|
|atom_vector|3|三项整体原子矢量目标，单行可含[n_atom,3]|
|molecule_tensor|6|r674四极矩的六个存储分量|
|合计|146|统计component行数|

模型线3.2要求物理层级相应的预测头，3.3要求逐字段平均。当前登记表将偶极矩xyz拆为统计行，却把原子梯度整体放在单行；若直接“一行一个头/一个等权loss”，会把偶极矩分成三个不变标量头，并使不同物理字段的权重依赖统计拆分方式。

定稿前需共同增加或明确：物理目标ID、统计component ID、head target分组、component轴映射、有效mask的聚合及loss计数单位。例如P.pm7_B.r52.{x,y,z}应能无歧义组合为一个[3]矢量目标；该建议不等于已冻结最终预测头数量。S结构任务也不属于这146行，不能由登记表行数推导S/D/P总权重。

## 2. 二阶张量目标是当前文档的覆盖缺口

登记表保留六个enabled字段P.xtb_singlepoint.r674.{xx,xy,yy,xz,yz,zz}，源路径为values.molecular_quadrupole_traceless_au，单位e bohr^2，源顺序写明xx,xy,yy,xz,yz,zz。模型线3.2列出了标量、原子、原子对和矢量头，没有明确二阶张量头；D1的类型/形状表也尚未明确该目标。

不能把这些旋转时会混合的分量直接交给不变分子标量头。建议共同约定一个对称二阶张量目标：导出[3,3]，或保留六个存储位置并按明确顺序重建；同时登记对称性、坐标原点、单位、shape、各分量mask与缺项处理。保留全部六个实测分量，不自行删列或改为模长。

字段名包含traceless，需通过实际源定义和读回检查trace约束；若确实无迹，其物理自由度为5，但这不改变当前保存六个分量的事实。定稿验收应包括Q_rot=R Q R^T，并与原子序/坐标轴检查一起完成。若使用六分量残差表示，还需明确对角与非对角的计量权重；完整矩阵Frobenius平方包含非对角项两次，不能默认六列等权就等同它。具体头结构由模型线确认，本审阅不修改其实现。

## 3. 共参考系、梯度符号与实际输入几何仍需真实验收

登记表矢量/张量reference_frame.verification均为PENDING_CONTROLLED_READBACK；“输入没有主动旋转”及元素顺序相同，只是实现证据，不能升级为所有程序输出轴已证实相同。模型线的1e-5等变性测试检验模型实现，也不能替代数据源参考系验收。

需逐物理目标绑定实际geometry/view ID、原子序、坐标轴/原点、单位和转换来源：

- 偶极矩为[3]、Debye；不能以模长替代xyz。
- PM7 AUX梯度允许源[3N]，导出[n_atom,3]的reshape顺序必须明确。
- xTB r625为dE/dR、Eh/bohr；r624为force、eV/Å，含负号和单位换算，不能仅因shape相同合并。
- 扰动梯度对应实际扰动坐标，而不是只对应parent PM7/UFF坐标。D1虽要求保存实际扰动几何，但顶层schema尚需给出可执行的view连接方式，加载器不能凭geometry_source=pm7猜测目标作用点。
- 对坐标施加刚体旋转时，同步变换矢量及二阶张量；随机几何扰动与刚体旋转的标签规则需要区别，不能把后者的变换规则当作前者的量化重算。

这些是待实际验证的边界，不是已观察到数据旋转错误。

## 4. 矢量/张量的归一化必须与输出对称性同时定义

模型线3.3要求用TRAIN统计后计算Huber，3.5要求矢量输出等变；D1要求逐字段缩尾计算统计、保留原标签。登记表本身尚没有最终D4统计。这几项可以兼容，但需要共同决定“字段”是物理矢量/张量还是各个统计component。

若把矢量逐轴写成T(v)=D^-1(v-mu)，一般非零固定mu及不同轴尺度D不能满足T(Rv)=R T(v)。因此，模型若输出归一化矢量后再逐轴反归一化，必须验证最终物理输出仍满足等变性。若模型始终输出原单位等变矢量，只把各轴尺度用在loss，输出结构仍可等变，但该loss权重一般不随任意旋转保持不变；不能混为同一项保证。

可供双方确认的方案是：保留逐component审计统计，同时为物理矢量/张量提供共同标量尺度、明确是否中心化及其依据，且在原单位输出上验收。Huber按component还是按矢量/张量残差范数计算也须明确；即使共同尺度，逐component的非二次Huber也不自动等于旋转不变的范数损失。本审阅不自行选择或更改算法。

缩尾只用于统计拟合，不能剪裁真实训练标签或旋转后的标签。Pprime独立拟合；不同方法、单位、任务/电荷/溶剂的能量元素参考也需分别绑定，加载器不得自行混用或换单位。拟合人口、record/分子权重、元素顺序/系数、percentile算法与标准差规则必须进入统计文件。

## 5. 当前登记JSON与候选wire之间需要显式编译/映射

D1是候选字段规范，登记表保留了源布局。以下是实际命名/形状差异，不表示现有加载器已经错误：

|D1候选概念|当前登记表示|定稿所需|
|---|---|---|
|field_id|field_key|明确稳定ID与版本映射，不按列位置猜测|
|molecule/atom/pair + value_type|含molecule_vector、atom_vector、molecule_tensor、sparse_atom_pair；value_type有scalar_component、tensor_component|冻结目标level/type枚举及source枚举的映射|
|逐导出字段shape|r39.s仍写源[n_atom] of {s,p,d,f,unknown}；r52.x仍写源[3]|分别保存source_shape和明确export_shape，不能把一个xyz分量再次展开成3个值|
|family/pooling|family_v1_final全146项为null；部分pooling_guidance为architecture_decision_required|D2仍为草案；按TRAIN rho/物理定义及模型线约定冻结，禁止加载器临时推断|
|unit|D20.MolMR保留“原冻结schema未声明单位”的事实|补权威单位依据或显式限制，不能填猜测单位后称最终D1完整|
|pair索引|source level=sparse_atom_pair|每字段连接其自身pair索引，明确方向性、排序和零基，不能沿用所有bond_pairs|

D1候选MFM3+JSON header+raw arrays尚无真实试点往返/多worker读取证据；模型线可以据草案开发，但双方未确认前不能将其视为已交付的生产加载格式。

## 6. Pprime、暴露掩码和分子均匀采样

模型线总loss只有S/D/P三组；登记表已写pprime.inherits_group=P，但D1字段表允许group=Pprime。定稿需统一：Pprime是P在UFF几何上的条件/标签来源，是否与P同时出现及其组内平均规则由共同配方说明，不能无意增加第四个等权组。

geometry_sources=[pm7,uff_sprime]应解释为字段可适用来源，不是两种实测标签均已可用；登记表明确computed_labels_available=false。Pprime出值前，不得将原PM7标签附到UFF坐标冒充Pprime；生成后必须更新实际geometry_context/source target及独立统计。

模型线3.1还要求逐分子的label-group exposure mask和family exposure mask。D1当前较详细的是逐字段有效mask及common_population，仍需单独登记暴露掩码。没有启用某家族与标签无效是不同原因，不能合并；组内平均只统计本批按配方启用且至少一个有效标签的物理字段。

按分子均匀采样需要molecule→geometry来源→允许conformer ID列表的可读取索引、固定顺序及明确缺项规则。现有record级条数不能直接作为采样概率；构象多的分子不能因此自动被过采样。P、D拓扑字段可按molecule复用时，需明确复用粒度及几何相关D3的限制。

## 7. 已冻结来源角色与尚未冻结的训练人群

最新roles_authority_v1.json为来源角色FROZEN：TRAIN 1,206,608分子／11,104,772 records；VAL 7,610／72,525；FULL 6,248／54,557。原ROUTINE legacy record为11,322，不能当作完整VAL几何数。它们由job4520334闭合来源支持；本审阅没有重跑该任务。

加载器应连接effective_role，保留source_role=FULL及legacy_routine_member；所有PM7/S′几何按同一molecule_id角色。D1 draft.2仍写角色清单待物化，是待随下一次草案修订更新的状态文字，不影响已闭合角色结果。

该authority同时明确common_population_frozen=false、diagnostic_geometries_frozen=false、final_normalization_authorized_by_this_manifest=false。因此D4及D5仍不能仅凭来源角色FROZEN就宣称完成。还须绑定共同人群、诊断heldout几何和最终训练清单；诊断几何在所有训练条件及拟合来源中排除，VAL/FULL/embargo不参与TRAIN统计。

模型线的两个验证集应分别记录：ROUTINE分子VAL与TRAIN分子的heldout构象诊断集，不能把legacy_routine_member当作第三种有效训练角色，也不能把同一分子的其他构象放回TRAIN。

## 8. 当前可判定的结论

没有收到模型线正式审阅意见，尚无双方已确认冲突。当前分子标量/原子/原子对/矢量方向总体兼容，但二阶张量覆盖、物理目标分组及其归一化、实际参考系、source→export schema、Pprime分组/来源和暴露掩码，需要双方明确后才能共同定为v3.0。既有float32训练导出、float64永久数据、原子序、TRAIN-only拟合、分子级角色和新建外部LMDB的要求一致。

下一步宜由Root在共享STATUS提供本审阅路径，模型线在D1“模型线意见”中确认或提出需求；本文件不代填其意见、不修改模型代码、不升级契约状态。

### 元数据计数复现

以下仅解析已绑定登记JSON，不读取科学数据：

~~~python
import collections
import json
from pathlib import Path
registry = json.loads(Path("configs/data_v1/label_registry_v3.json").read_text())
enabled = [f for f in registry["fields"] if f["status"] == "enabled"]
print(len(enabled), collections.Counter(f["level"] for f in enabled))
print([f["field_key"] for f in enabled if f["level"] == "molecule_tensor"])
dipoles = [f for f in enabled if f["level"] == "molecule_vector"]
print(len(dipoles), len({(f["task"], f["registry_id"]) for f in dipoles}))
print(sum(f["family_v1_final"] is None for f in enabled))
~~~
