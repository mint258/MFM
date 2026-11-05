# training format v3：draft.4 native domains 独立提案

状态：PROPOSAL_NOT_ADOPTED，2026-10-27。本文是对draft.3及模型线七条意见的候选扩展；**不替代draft.3，不签署v3.0，不改变任何已登记schema、源码、原值、mask或frame状态**。仅新增文档，未实现新wire/provider、执行测试或读取科学正文。Root与模型线共同审阅后才可决定后继契约版本。

目的：使原native中不能用普通atom pair表示的r73域、r674完整tensor及其消费责任有明确边界，防止为了接现provider而丢失科学身份。出处与当前字节绑定见`../data_v1/d1_joint_freeze_remaining_20261027_v1.md`，其Root契约SHA为399ee0cebf8497c4e73accc52f84fd7d42b9753f9779433c80d12641df5a5ea2。

## 1. r73：有序双端通道entry域

精确源：`P.pm7_B.r73.value / registry_id=73 / task=pm7_B / values.sigma_pi_entries`，条件为中性气相native_original_PM7。不能与相同path但不同task/registry的源合并。

冻结`wp4_native_pilot_v4.py:171–196,383–385`实际hook逐端形成`(打印atom号−1, 原basis标签)`；basis来自S/P/D/F-SIGMA/PI/DEL…字符串。原字段每条保存`atom_i,basis_i,atom_j,basis_j,value`，允许onsite，保留选定近邻中的原顺序。这是原orbital-group标签，不能用独立AO_ATOMINDEX替换，不能把它声称为已恢复的程序AO ordinal。可用三元语义键`(src_atom,dst_atom,(src_channel,dst_channel))`描述；channel是有序的**两端标签对**，不是单一shell类别。

候选存储按一个entry轴逐项对齐，长度均为n_entries；以下是待双方确认的字段语义表，不是当前MFM3已接受的新schema：

| 字段 | 原值映射 / 约束 |
|---|---|
| native_identity / geometry_ref / source_ref | 原record/molecule/完整owner、method/charge/context及source pin；最终opaque geometry未冻时不造ID |
| src_atom:int32[n] | 原atom_i，零基，同所存全原子序，范围[0,n_atoms) |
| dst_atom:int32[n] | 原atom_j，同上；允许src=dst，方向原样保留 |
| src_channel / dst_channel | 原basis_i / basis_j逐条UTF-8字符串，不交换、排序、合并或物理重命名；若将来字典编码，须明确可逆字典/版本/hash |
| entry_ordinal:int64[n] | 原已解析列表位置，0至n−1；保留原顺序与重复，明确不是原打印列号或AO ordinal |
| values:float64[n] | 永久源value及精度provenance；训练仅按冻结规则一次float32转换，不加和/平均/去重 |
| valid:bool[n] | 原逐entry/leaf validity；未提供可确定映射时拒绝，不用有效0填缺项 |
| reason_refs / codebook_ref | source/new/review字段原因、原稀疏leaf例外及65535含义原样保留；review/exposure不得更改source validity |

同atom对不同通道必须并存；即使上述三元键重复，也以entry_ordinal保留实际原记录并单列review，不能静默删除或改mask。原parser本身仅以(atom,basis_label)登记keys，未保存独立原打印列/轨道组ordinal；该缺失写入provenance，不伪补。源只包含当时保留的onsite/所选近邻项，不能补出远距条目或把缺项当真0。

**现格式冲突与变更责任：** 当前wire/source_v2处理每字段[p,2]，`validate_pairs`要求原子对唯一；模型collate还拒self，provider显式拒basis。只设allow_self、增n_pairs或传basis元数据均不足。须在后继契约共同定义独立entry域、entry身份与模型通道输入/输出、mask/loss计数、方向/重复政策，并由模型线增加对应消费路径；普通S bond/Wiberg pair不得借此改变。本文不决定r73的物理旋转律、invariance、pooling或归一化。

## 2. r674：保留六值的codec与尚缺的模型消费

唯一机器身份：`registry_id=674 / task=xtb_singlepoint / values.molecular_quadrupole_traceless_au`；成员顺序固定`xx,xy,yy,xz,yz,zz`。人类别名r67_4不进入匹配，不改程序名或源字段。原registry单位声明e bohr²、native_original_PM7；实际原点、输出轴、trace及native打印精度仍待证，不由名称、F64容器或合成旋转推定。

| 接点 | 当前已有 / 后继版本必须明确 |
|---|---|
| registry→physical target | 六个原component已存在；共同映射为一个symmetric_tensor目标，成员、顺序、task/context和mask全绑定，不拆六个不变标量、不删zz、不强制修正trace |
| 数据codec | 现wire/mapping已支持symmetric6及对称3×3；重建仅按原六位置镜像对称项。须冻结实际选用storage、schema/hash及component-mask审计；矩阵镜像不增加独立观测计数 |
| provider/FieldSpec | 现模型仅scalar/vector/magnitude，候选provider拒tensor；须新增显式tensor表示、shape/对称性及真实source-frame绑定，保持旧路径拒绝未知类型 |
| head/loss/D4 | 模型线实现与双方确认rank-2消费、物理计量/Huber与尺度、是否中心化及对称性。六列等权不自动等于矩阵Frobenius；不得单边套逐轴中心/尺度或借PM7统计填P′ |
| 实际验收 | 必须区分数据native轴/原点证据与模型Q→RQRᵀ测试；两者都不由codec往返代替。未完成时保留UNSUPPORTED/PENDING，不能升成可训练 |

## 3. 五层map与版本闸门

| map | 至少绑定的身份与待确认内容 |
|---|---|
| raw registry→component | 原registry_id/task/source_path/component、启用状态及源shape/单位证据；不按列位置或近似名称猜测 |
| component→physical target | 稳定target_id、完整成员、level/kind、family、condition、geometry、shape、单位、mask与loss计数；r73新entry域及r674 tensor明确版本化 |
| source selector→entry/value | 完整canonical owner、每字段原索引、entry ordinal、双端通道、native atom order、原值/理由粒度与source precision；保留原方向、重复及稀疏缺项语义 |
| native geometry/order→sampling | opaque geometry与native physical key对应；PM7/UFF独立entry、诊断base/child排除、保留集三种training_rank；最低能取保留energy training_rank=0。N=1/N=2/k不足仍待冻结 |
| provider→FieldSpec/D4 | target→模型字段/shape/通道/索引转置和batch offset、S原生transport、actual view/H0路由、condition→normalizer及审计sidecar/codebook/hash；真实TRAIN/VAL入口另验收 |

每层必须指向同一个release所绑定的原子序、角色/common、D4/D5、source、schema/shard与代码SHA；同SHA的别处路径不代替实际部署引用。新增domain/字段、mask、order或映射语义须新版本，旧请求/结果/checkpoint provenance保持。MFM3低层数值codec可复用不等于旧family schema/provider已兼容新域。

双方待确认：r73完整domain及模型算法；r674物理定义/原点/尺度/loss/模型实现；原native单位与frame；实际perturbed target→child/parent/坐标hash/H0路由；mask粒度；最终common/orders/N-k政策；逐condition D4；最终五层maps及真实provider/VAL和D3验收。无共同确认记录不产生MODEL_DATA_JOINT_CONTRACT_FROZEN；不自动减少启用标签以通过现loader。

## 可直接写入STATUS的短通知（待Root整合发布）

数据线新增独立`training_format_v3_draft4_native_domains_proposal.md`，仅提议r73有序双端通道/onsite/entry_ordinal域、r674完整六分量的provider变更及五层map绑定。draft.3仍是当前草案，本文未被共同采纳；没有新frame/单位/物理算法验证或D3–D5交付。现模型provider对basis/tensor/off-equilibrium的拒绝继续有效。请模型线在后继共同审阅中确认domain、模型消费与物理定义，未共同冻结前保持DRAFT。
---

## 模型线意见

### 2026-10-27 Codex A：draft4 增量共同审阅（尚未共同冻结）

本文件前文保留数据线 draft4 提案原文，以下为模型线意见。它是独立版本的审阅副本，不修改当前被任务 pin 的 draft3 或数据线原提案，不产生 v3.0 / MODEL_DATA_JOINT_CONTRACT_FROZEN。接受无损保留科学身份的设计方向；现 provider 对 basis、tensor 及未经批准的真实来源的拒绝继续有效。这些意见没有执行新模型、原生输出读回、测试或作业。

#### 1. r73：支持独立的有序双端 entry 域

支持保留原已解析列表中的 src/dst atom、两端原 basis 字符串、entry_ordinal、value、valid 和 reason/codebook，以及原 owner、atom order、geometry/source 身份。允许 onsite，保留方向、顺序与重复；entry_ordinal 是已解析列表位置，不是程序 AO ordinal。未知 channel 拒绝，不能无声合并 DEL/DELL/DELTA、去重、平均、补镜像或把缺项填成有效0。

当前普通 pair 路径不足以实现该提案：wire拒重复 atom pair，collate/head拒 self，原 PairHead 只有交换对称特征且没有 channel 输入。后继版本须有独立的 entry identity/channel→collate/offset→有序预测→target/mask/loss-count→恢复指纹链；普通 S bond/Wiberg 默认路径不变。有效监督按原 ordinal 观测计数，不按 unique atom pair 计数，不据词典类别数静默重设字段或组权重。

原 parser 没有完整打印列或 AO ordinal，部分解析边界也会跳过条目。因此“无损”只相对已有解析列表；不能宣称重建全部 AO 矩阵或修复了未保存的原输出。entry_ordinal 仅用于 provenance/alignment，不能通过可学序号替代未知物理身份来获得过拟合。若相同物理身份的源值冲突，应单列原始对照。

#### 2. 精度与 codec 也需要明确版本

当前 codec 不含 f8，family mapping 强制 target values 为小端 f4。后继契约应明确永久源 F64 位于既有权威源/sidecar，还是要新增支持 f8 的 codec/family schema；两种方案都必须绑定永久值、一次训练 F32 转换、source/schema/hash。不能仅增加 entry 数组就声称现格式支持永久 F64。F64 容器、原 parser 已解析浮点数均不证明原程序或打印精度；缺失原 token 时记未知，不补造精度。

#### 3. r674：同意完整六成员对应一个对称物理张量

精确身份是 registry_id=674、task=xtb_singlepoint、values.molecular_quadrupole_traceless_au，六成员顺序固定为 xx,xy,yy,xz,yz,zz。保留全部原值及逐成员有效性/原因，不拆成六个不变标量，不删 zz，不根据名称强制修正 trace。矩阵镜像不是九份独立标签。

模型当前实际坐标约定是行向量 X'=XR+t。在原点也按 O'=OR+t 共同移动的条件下，同一数值 R 对应 Q'=R^T Q R。提案 RQR^T 若使用列向量旋转须明示 R_data=R_model^T；不能共用同名 R 却采用相反方向。原点、主动/被动约定和平移律仍须原生证据，不能由 charge0 或张量名称推断。

六值 Frobenius 平方度量的权重按原顺序为 (1,2,1,2,2,1)。逐分量 Huber 即使加权一般也不旋转不变。可共同讨论 radial Huber：rho(||Q_hat-Q||F/(s sqrt(d)))；d=6 的正交六坐标规范或 d=9 的矩阵-entry规范均需明确冻结，本文不单方采用。计数、delta、分母、物理 target 与组权重须一致。

TRAIN-only 归一化应与该变换律相容；本轮最小单尺度候选为 (Q-cI)/s，或 c=0。稳健参数及退化尺度政策由最终 D4/condition 给出，不能把说明性均值示例当作已采用统计。禁止固定逐轴中心/缩放代替共同方案，也不能把统计 cI shift 当作改变物理原点。模型需要显式 rank-2 几何基与 invariant 系数；普通 H0→六列 MLP 不具备该协变保证。是否约束 trace、坐标尺度及 Å/bohr 输出映射都待共同确定，不修改原 y。

#### 4. partial component mask 不能机械变成六个旋转 bool

全部 source-valid leaf 和 reason/codebook 原样保留。需共同选择并版本化以下政策之一：

- 全张量 loss 的 eligibility 与 source validity 分开，报告完整/部分覆盖；是否采用 all(valid6) 必须双方明确，不是模型单方弃用有效 leaf。
- 定义 frame-aware 观测算子 y=A(Q)、metric、分母及变换后的 A'=A∘T_R^{-1}，保留真实观测，不从缺项生成旋转后的标签。

以上只是候选政策；当前 all_components codec 声明、现有 vector fixture 或字段 enabled 均不能授权其一，也不能升级成 r674 可训练。

#### 5. 数据线需提供的最小真实证据

请沿既有有界 witness/source locator 连接原 task/owner、程序版本/keywords、原输入输出及 SHA，不需重新跑 QM 或重做已通过的镜像 fixture。r73 需原通道相对原子对/坐标的定义、onsite/换端语义、分页/重复与真实逐 entry 对照；r674 需 quadrupole 定义系数、原点/轴/平移律、六成员顺序、实际 trace 与原生打印精度。raw 不存在时明确 UNKNOWN；官方手册、字段名、F64 容器和 codec 往返各自不能代替这些证据。

必须同时绑定实际 PM7/UFF/扰动几何、atom order、坐标哈希与 H0 view。不得把 base 标签挂到另一几何，或借 PM7 的 D4 统计填 P′。本审阅没有放行 P′ 的精度提案或其既有科学 HOLD。

#### 6. 共同冻结与模型验收的后继步骤

请把 raw registry→component、component→physical target、source selector→entry/value、native geometry/order→sampling、provider→FieldSpec/D4 五层映射与同一 release 的 source/common/role/schema/shard/codebook/D4/D5/代码 SHA 绑定。N=1/N=2、k不足、三种构象顺序与最终共同人群政策仍须明确；不克隆几何来补 k。

双方定义明确后，模型线实施新域的 FieldSpec/provider/collate/head/loss/审计与恢复路径，保留旧 scalar/vector/pair 默认行为。真实 D3/D4/D5 到位后再做真实加载/VAL、源值对照、逐头1000分子 R²≥0.95，以及三种 GPU 的 SDP 2000步冒烟与吞吐/显存测量。模型 FP32 协变测试与原生标签 frame 证据是两个独立门，不能互相替代。现有 C4 21PASS/27FAIL HOLD 没有因本审阅改变。

#### 审阅来源和当前状态

完整源代码接点、公式反例、当前测试边界和 rawrefs 见本目录 evidence_D1_draft4_model_review_20261027_v1 下的 r73/r674 两份审阅及 JSON。MODEL_SOURCE_BINDINGS.json 记录 Root 对小型来源字节的复核；它不是项目测试、原生读回或部署验收。当前结论为 MODEL_REVIEW_RECEIVED_CONDITIONAL_DOMAIN_DESIGN；r73/r674 仍 UNSUPPORTED/PENDING，draft3 仍是当前草案，未共同冻结、未改变标签或现有运行。
