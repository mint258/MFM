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