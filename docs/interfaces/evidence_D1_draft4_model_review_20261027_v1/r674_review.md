# D1 draft4：r674 模型侧源代码审阅（DRAFT v1）

结论：draft4 的“保留完整六分量、作为一个对称张量消费”方向可继续共同设计，但当前模型尚不支持这一路径，不能宣布可训练或共同冻结。draft4 自身为 **PROPOSAL_NOT_ADOPTED**，不替代 draft3。本次 DRAFT 指审阅稿；未修改 registry、原值、source mask、数据契约或模型代码，未读取科学 payload，也未运行测试或作业。逐文件当前字节/SHA、行号与精确 registry 投影见同名 JSON。

## 1. 精确身份和现状

唯一机器身份为 `registry_id=674 / task=xtb_singlepoint / source_path=values.molecular_quadrupole_traceless_au`。六个启用成员严格按 `xx,xy,yy,xz,yz,zz`，字段键为 `P.xtb_singlepoint.r674.{component}`；`r67_4` 仅人类简称。registry 声明 GFN2-xTB、charge0、gas、ground_state、`native_original_PM7`、单位 `e bohr^2`。这些声明并不构成原生输出轴/原点的独立验收：`reference_frame.verification=PENDING_CONTROLLED_READBACK`，family_final 为空，size/D4 仍 `PENDING_FROZEN_TRAIN`。registry 同列 pm7/uff_sprime geometry_sources，也不能据此把 PM7 的同一张量静默挂到另一构象。

源码边界如下；这是源代码审查，不是本轮实际测试结果。

| 层 | 当前确切行为 | r674 缺口 |
|---|---|---|
| parser，`wp4_parsers.py:247–250` | 匹配 native `molecular quadrupole (traceless)` 的 `full:` 六个数字，按捕获顺序保存 | 不证明轴、原点、定义系数、真实 trace 或打印精度 |
| codec，`mapping.py:6–7,79–115` | 顺序固定，支持 symmetric6 与按位置镜像的 3×3；声明 all_components | 镜像不增独立观测；codec 往返不验模型物理或 partial-mask 共同政策 |
| FieldSpec，`v3_contract.py:20–21,43–84` | level graph/atom/pair；representation scalar/vector/magnitude；宽度为 1 或 3 | 无 rank-2 类型、六分量 shape/metric 或显式观测算子 |
| provider，`v3_wire_provider.py:121–148,257–290` | 仅显式 synthetic candidate；P/D regression 只接 scalar/vector；保留 component reason audit，另求 row-valid | 无真实 r674 路径；不能通过改名、拆六标量或改 source mask 绕过拒绝 |
| head，`model/v3_heads.py:97–119` | vector 分支及 scalar graph/atom/pair 分支 | 无 rank-2 协变 head；普通 invariant H0→六列 MLP 不会因此变成张量 head |
| loss/D4，`v3_losses.py:76–94`、`v3_contract.py:129–179` | vector radial Huber；其余 component Huber；vector 零中心/等轴尺度；FieldTarget 为逐行 bool | 无 tensor Frobenius/radial loss、tensor D4 或 partial observation-domain 定义 |
| tests | vector_loss 的旋转/梯度与 component-Huber 反例；wire scalar/vector fixture 与未知字段拒绝 | 不证明 r674 可训练或 native frame；wire 名为 tensor 的负例只是 model_field 不匹配，并非 rank-2 正例 |

## 2. 必须统一同一个旋转约定

现有模型诊断实际使用行坐标 `X' = X R + t`（`v3_composed_equivariance.py:283–289,315`；vector_loss 测试同样右乘 R）。若 Q 是关于同一随坐标共同移动的原点 O 的二阶空间张量，`O'=OR+t`，则：

\[
Q'=R^\top Q R.
\]

因为行位移 u 变为 uR，而 `uᵀu` 变为 `Rᵀ(uᵀu)R`。提案的 `Q→RQRᵀ` 可在另一约定下成立：必须明确其 `R_data=R_modelᵀ`，对应坐标 `X'=X R_dataᵀ+t`。不能把两个文档里的同名字母 R 直接当成同一个数值矩阵。

一个以后可实现的解析符号反例是 `Q=diag(1,2,-3)`、`R=[[c,-s,0],[s,c,0],[0,0,1]]`、`c=s=1/√2`：模型行约定给 `Q'xy=+1/2`，`RQRᵀ` 给 `-1/2`；trace 与 Frobenius norm 均相同，单验这两项抓不到约定反转。本次只给解析推导，未执行该测试。

平移律还依赖原生原点。charge0 不足以证明 quadrupole 对固定原点的平移不变，非零 dipole 仍可产生平移项。须由数据线给出原程序定义、实际输入/输出轴、原点及其随坐标移动规则；模型不能自行选 COM/charge-center、改几何中心或强行修正标签。下面的统计性 `cI` shift 也不等于改变物理原点。

## 3. 六个成员是一个物理目标；metric 与 Huber 必须共同冻结

令 `q=(xx,xy,yy,xz,yz,zz)`，则

\[
Q(q)=\begin{pmatrix}q_0&q_1&q_3\\q_1&q_2&q_4\\q_3&q_4&q_5\end{pmatrix},\qquad
\|E\|_F^2=e_0^2+2e_1^2+e_2^2+2e_3^2+2e_4^2+e_5^2.
\]

所以源顺序的平方误差权重为 **(1,2,1,2,2,1)**，不能六列等权冒充矩阵 Frobenius。可选正交六坐标 `(q0,√2q1,q2,√2q3,√2q4,q5)` 只是表示/metric 约定；不是新增标签。3×3 镜像也不是九份独立观测。即使以后证实物理上严格 traceless，原六值仍全部保留，不能先删 zz、投影 trace 或将名称当成该证据。保留六条 source leaf 的覆盖计数与“一份 tensor loss”是两个不同层次。

逐分量 Huber 一般不旋转不变，**加 offdiag 权 2 也不够**。以 δ=1、`E=diag(2,-2,0)` 为例，加权 component Huber 和为 3；按上述行约定旋转 π/8 后是 `4√2−2`，但 Frobenius 平方仍为 8。这与已有 vector component-Huber 反例同一问题，并非当前代码已支持 tensor。

可供共同决定的候选是每个 eligible 物理张量只计一次：

\[
L_Q=\operatorname{mean}_{\text{eligible tensors}}
\rho_\delta\!\left(\frac{\|\hat Q-Q\|_F}{s\sqrt d}\right).
\]

例如 d=6 表示六维正交 tensor 坐标的均方规范；d=9 的矩阵-entry 均方规范也可保持旋转不变，但会改变尺度、Huber 转折与组内相对权重，不能当成九个独立标签。**d、δ、mask 分母、field/group 计数必须共同冻结，本审阅不采用其中一个。** 当前 loss 是 observed-field→group 的平均，若把 r674 拆六个 scalar field，还会改变目标权重，不能用它代替这项设计。

## 4. TRAIN-only 的协变归一化与候选 head

在本次要求的单一尺度方案下，可共同定义 `Q_tilde=(Q−cI)/s`，s>0 且 c、s 只由冻结 TRAIN、精确 condition、eligibility/分母政策计算并绑定 D4/版本/SHA。可讨论 `c=mean_TRAIN(trace(Q))/3`、`s²=mean_TRAIN(||Q−cI||F²)/d`；实际统计、有限值/退化尺度政策均未给出，也未计算。若 trace 物理被证实且共同采用 traceless 目标，可选 c=0。固定逐轴/逐成员中心和尺度一般不与旋转交换；固定均值矩阵在所有旋转下不变须为 cI。此处是最小单尺度候选，不是声称数学上不存在更一般的 irrep-wise 方案。不能借 PM7 的统计替代不同 condition/几何的 P′ 或 UFF 统计。

只有原点/几何/单位与 head 输入已共同确认后，下面才是可讨论的协变构造示例。令 `u_i=(x_i−O)/ℓ` 为行向量，a_i、b 为 invariant 特征的标量函数：

\[
\hat{\widetilde Q}=\sum_i a_i\left(u_i^\top u_i-\tfrac{\|u_i\|^2}{3}I\right)+bI,
\qquad \hat Q=cI+s\hat{\widetilde Q}.
\]

它说明需要显式几何 rank-2 基与 invariant 系数，不等于选定架构、充分表达性或当前 C4 已过。是否约束 b=0 必须等 trace 证据/共同政策，不能反过来修改原 y。ℓ、坐标单位与输出 `e bohr^2` 的映射须明示，不能把 Å² 与 bohr² 隐式混用。当前模型没有这条实现。

## 5. partial component mask 不能靠旋转六个 bool 解决

必须保留原六成员的 validity、reason/codebook、顺序及 source mask，不补零、不删有效 leaf、不把镜像当额外观测。当前 FieldTarget 的每行 bool 只能表达整行是否用于该 loss，不能表达一般的 partial tensor 观测算子。

可共同选择的两类政策是：

1. 只对完整 tensor 使用 full-tensor loss，但另存 `loss_eligible=all(valid6)` 及完整/部分覆盖计数，所有有效 source leaf 与原因审计仍保留。是否允许此损失资格政策须共同签定，当前 codec 的 all_components 不是模型单边弃用部分有效 leaf 的授权。
2. 明确定义 `y=A_M(Q)` 的观测算子、frame、误差 metric/权重、分母、精度与版本。若 `T_R(Q)=RᵀQR`，同一观测在变换坐标中应写 `A'_M=A_M∘T_R^{-1}`，其中 `T_R^{-1}(Q')=R Q'Rᵀ`；不能只旋转预测并照搬六个 bool，也不能由缺项捏造旋转后的分量标签。候选残差可写 `W_M^(1/2)(A_M(Q_hat)−y)`，但 W_M/对角与非对角计数、source error/covariance 及 loss 还须共同规定。

无论采用哪类，都不能单方把 D4 eligibility、partial loss mask 或 synthetic augmentation 变成新的 source mask。

## 6. 待补证据与后续边界

共同冻结前至少须补齐：原程序/版本与 quadrupole 定义系数；原生轴/原点/主动被动变换及平移律；真实 trace/打印舍入与精度证据；单位和实际 geometry/atom order/H0 view 对齐；PM7 与 UFF/P′ condition 映射；完整六成员及 partial observation/loss 资格政策；逐 condition TRAIN-only D4；最终 physical/family/common/order 等映射、reason codebook、release/source/schema/代码 SHA 与真实 provider/VAL/D3/D5 验收。F64 容器、字段名、codec 往返、合成旋转公式或现有 vector 测试均不能替代这些证据。

在这些问题解决前，r674 模型消费保持 **UNSUPPORTED/PENDING**，原 enabled source leaf 不变，不产生 MODEL_DATA_JOINT_CONTRACT_FROZEN。以后才实施 FieldSpec/shape、provider、rank-2 head、tensor loss/D4/partial-domain 与有意义的旋转/梯度、mask/类型/来源拒绝测试，并保留旧 scalar/vector 路径。本审阅没有执行或声称通过这些工作。
