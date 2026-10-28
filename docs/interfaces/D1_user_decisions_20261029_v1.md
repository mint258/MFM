# D1：请一次决定以下五项

状态：`USER_DECISION_REQUIRED_NOT_JOINT_ACK`。下表把设计选项收敛为可直接批准的决议，不再新增一轮证据或草案。可以回复“全部A”，或“1A、2A、3A、4B、5A”等逐项选择。用户决定授权政策；Root与模型线仍须把同一选择签入合同/映射，并完成尚未实现的consumer及真实数据验收。当前模型线**已经条件式审阅**，尚无joint ACK。

以下事实不作为可选项：r73保留的是原解析器选定的ordered-entry列表，不是完整AO矩阵；双端channel、onsite、方向、重复项和列表ordinal必须保留。r674是一个full symmetric6目标，顺序为`xx,xy,yy,xz,yz,zz`，不是六个不变标量或特征值；原值/原component masks/reasons全部保留，不再乘1.5、不投影trace、不删除zz。192项缺少独立输出坐标观测是UNKNOWN，不是物理失败，不自动新增异常mask。

| 决议 | A：推荐 | B：明确的替代选择 | 选择后的实现边界 |
| --- | --- | --- | --- |
| **1．r73表示与精度** | **原F64值为权威sidecar，训练wire从它恰一次转F32；独立ordered-entry域。** 两端atom/channel独立，保留onsite/重复/方向/retained-list ordinal；不把ordinal作为学习ID，不套普通pair唯一性或交换对称假设。 | 新建F64训练codec/family版本，权威值与训练wire都保持F64。 | A仍须真正增加sidecar、双端channel类型/provider/collate及逐entry head/loss/count/恢复绑定；B还须新codec/版本及模型精度路径。现有f4文件不能宣称永久F64，现有PairHead不能冒充该域。 |
| **2．r674 partial与人口** | **完整六项均有效、且绑定同一actual geometry时，才进入完整tensor loss。** 六项各自原validity仍导出；partial值继续审计，另报eligible/excluded数，不补零、不把loss exclusion改成新数据异常。 | 允许frame-aware partial tensor loss；必须显式定义观测算子及其随旋转的变换。 | 推荐A可避免把固定六项bool误用在旋转后的预测上。B是新的consumer/算子实现，不是放宽mask或把部分缺失补成有效值。full6原始目标两项选择都不变。 |
| **3．r674归一化** | **`Qnorm=Q/s`，不减中心，六项共用一个正标量。** `s`取现有D4 `frobenius_norm`序列的TRAIN-only 0.1%/99.9% winsorized `std_ddof0`；逐登记target/condition单独拟合。 | 本版暂不启用r674模型exposure，保留full6数据、component统计及原因；不自选另一个未实现尺度算法。 | A选择的是已有Source定义的序列和统计器，不是声称最终数值已到。必须绑定实际D4数值/人口/series key/SHA；不能拿RMS、单个分量std或临时人口替代。常量/退化沿原D4规则，不悄填epsilon；若没有合法正尺度则暂不解锁该loss。 |
| **4．r674旋转不变loss** | **一个tensor算一个target：Frobenius-radial Huber，d9，delta=1。** 半径/平均方式见下式；新目标在既有target加权框架中权重为1，不按六个任务重复加权。 | 同样Frobenius-radial Huber，但改用d6、delta=1；其余人口/平均方式不变。 | 两者都旋转不变，差别是明确的损失尺度。不能使用“六分量分别Huber再加权”来声称旋转不变。模型现有vector radial实现不等于tensor6已实现。若3B关闭该目标，本项仅登记后续约定，不启用loss。 |
| **5．192项坐标UNKNOWN如何进入物理政策** | **接受注明假设的源程序frame provenance作为本版逐target物理审阅依据。** 明确记录“无独立输出坐标观测”；允许Root据已闭Source/调用/输入绑定及可信目录连续性推断签认对应frame政策，再交模型联合验收，不要求仅为此重复QM。 | 对缺独立坐标观测的相关frame/origin敏感目标，本版先关闭模型exposure；原数值/统计保留。已有独立证据的目标和无此frame依赖的标量继续推进，不把整批/整分子判无效。 | A的假设是正常可信FS与时钟、同目录/路径未被替换或恢复、无特权时间戳操纵。它不把192个UNKNOWN改成独立观测PASS，也不豁免unit/sign/atom-order或输入hash问题。B不自动触发新QM、不新增数值mask。 |

## 3A使用的现成统计定义

对完整有效六元组，原`normalization_v1.series.views`已定义：

```text
F(Q) = sqrt(xx^2 + yy^2 + zz^2 + 2*(xy^2 + xz^2 + yz^2))
qlo,qhi = 原D4对该F序列的TRAIN-only 0.1%/99.9%精确分位点
u_i = clip(F(Q_i), qlo, qhi)
s = sqrt(sum_i (u_i - mean(u))^2 / n)     # 原WinsorMoments.std_ddof0
Qnorm = Q / s                            # 不减mean(u)，不作tensor原点平移
```

这里clip只用于拟合统计量，原Q和训练标签不被裁剪/改写。已有Source的series key形式为`physical/<registry_id>/<task>/frobenius_norm`；r674须以实际inventory的原task及key绑定。完整六项资格与该现成F序列的进入条件一致。正式参数只能来自最终发布人口的Common∩effectiveTRAIN，并反连接D5 heldout base及全部真实直接children；VAL/FULL/embargo不得拟合。若先做有明确边界的临时试点，其参数必须另有pilot人口/版本，不能称正式v1参数。

这是对现成算法的明确选择；本页没有计算D4，也没有构造未来数值或SHA。若实际发布器尚不能绑定这个已有series，补的是执行/绑定实现，不再由本文伪造一份统计值。

## 4A/4B的完整数学约定

行坐标约定固定为`X'=XR+t`，同一对应原点的tensor旋转为`Q'=R^T Q R`；此式不代替带电体系的原点平移定律。令`E=(Qhat-Q)/s`，按上面的六项顺序取`w=(1,2,1,2,2,1)`：

```text
r_d = sqrt(sum_j w_j * E_j^2 / d)         # A: d=9；B: d=6
h_1(r) = 0.5*r^2       if r <= 1
         r - 0.5       if r > 1
L_target,condition = mean_i h_1(r_d(i))   # i仅限完整有效、geometry一致的tensor
```

同一target/condition先按eligible geometry平均，再按已签认的target权重合并；零eligible计为无该loss观测，不当有效零，不把六分量计为六个任务。原component审计分母和原始mask仍完整保留。delta是归一化训练loss参数，不是物理QA容差，不能用于放宽原逐值对照或1%质量门。预测输出必须是符合所签旋转律的对称tensor；原标签打印trace残差完整保留，不以头或归一化悄修标签。

## 决议后还要完成什么（实现/签认，不是再次索要证据）

Root和模型线按选择写入同一合同版本：registry/component→物理target→stored value/mask→actual geometry/D5→provider/head/D4五层映射；r73可逆channel/codebook和精度位置；tensor6类型、mask/count/loss/尺度；真实gradient child/H0路由；源unit/sign/origin/frame逐target审阅。随后由模型真实加载/对照/恢复验收。用户选A并不等于consumer已经实现或joint ACK。

现有实际物理report已经到达：407引用链的有界核验及已完成的MOPAC/gradient/tensor关系检查按原scope保留。192项仍是六种xTB single-point的独立坐标UNKNOWN，与已取得独立坐标的160项MOPAC及32项gradient分开。第5项只决定证据接受政策，不自动外推所有unit/sign、charged dipole原点或新精度协议都已接受。原SCF诊断与正式生产协议分开，full/2000不从本决议自动获得授权。Se仅有既有排除率例外；1%质量门没有豁免。

依据：Model `model-v3` commit `a45495e0398bc38ffda88f8384aee5d6011fc04d` 的条件反馈；既有D1 Source链/参数目录连续性补充及实际物理facts；原`normalization_v1/series.py:35–45,95–108`、`streaming_v1/calibration.py:152–173`，与当前D4 direct-object bindings。精确机器refs在本目录receipt中。无Root/Model/旧draft修改，无Python/AST/tests/SCI/SSH/Slurm执行。