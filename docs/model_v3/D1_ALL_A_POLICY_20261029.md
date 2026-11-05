# D1：用户已确认全部A的模型消费政策

2026-10-29。用户本次明确答复“全部采用推荐项A”（Root本轮任务传入的聊天确认）。这是五项政策选择的授权；**不是Model/Data joint ACK，不是D3/D4/D5/D6交付或真实标签验收。** 原Model651a的median(Frobenius)/sqrt6与d6是已被本次选择取代的历史候选，不覆盖旧文档或历史结果。

选项原文是Data只读文件：

`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/docs/interfaces/D1_user_decisions_20261029_v1.md`

7871 B，SHA256 `94a3c8eb98e381b46d88217986ae601b26c8246de56e596a479deaf4e588e415`。该原件保留当时的待选状态；本页记录后继用户确认，不改Data原件/STATUS，不代Data签名。

## 已选五项

1. **r73原F64 sidecar为权威，训练值恰一次F32。** 对象是原解析器保留的ordered-entry列表，不是完整AO矩阵。两端atom与literal channel独立；保留onsite、重复、方向、列表ordinal及原valid/reasons。可逆codebook不折叠DEL/DELL/DELTA等字符串；ordinal只作对齐/恢复，不进学习输入。不套普通交换对称PairHead，也不从opaque channel推断旋转律。
2. **r674仅full-valid且同一actual geometry进入完整tensor loss。** 原六序固定`xx,xy,yy,xz,yz,zz`，native traceless full6原值完整保留；不乘1.5、不再投影trace、不删zz、不补缺值。原component masks/reasons、有效leaf数、partial/retained/excluded审计与原质量分母、>1%规则保留。loss eligibility不写成新source-invalid。
3. **center0、单一正尺度，逐target/condition拟合。** 对实际Common∩effectiveTRAIN的物理观测去重，反连接D5 heldout base及全部真实直接children；VAL/FULL/embargo不参与拟合。采用原Frobenius序列TRAIN-only0.1%/99.9%精确分位winsorized `std_ddof0`：

   `F(Q)^2 = xx^2+yy^2+zz^2+2(xy^2+xz^2+yz^2)`；仅拟合统计时clip F，`s=std_ddof0(clip(F,q.001,q.999))`，训练`Qnorm=Q/s`，不减F的均值、不clip标签。实际series为`physical/674/<实际task>/frobenius_norm`，不得把task猜成另一个condition。空/zero/nonfinite或一次F32后不再正且有限的s均HOLD，无epsilon/floor。实际统计、人口、Source和数值rawref未交付时不启用。
4. **一个tensor一个target，Frobenius-radial Huber d9、delta1、target weight1。** `r=sqrt((Exx²+Eyy²+Ezz²+2(Exy²+Exz²+Eyz²))/9)`，`E=(Qhat-Q)/s`；每eligible geometry计一次，再沿既有字段/组权重合并。不是六个component Huber，不按六/九个任务重复加权。零eligible是无loss观察，不是有效零标签。普通scalar/vector既有政策不改。
5. **有明确假设的源程序frame provenance可供逐target签认。** 正常可信FS/时钟、同目录/路径未替换或恢复、无特权时间戳操纵等假设须保留；192项无独立输出坐标观测继续UNKNOWN，不能改成独立PASS，不新mask或重复QM。unit/sign/atom-order/input hash与真实gradient-child链仍各自需要签认和验收。

行坐标`X'=XR+t`对应tensor `Q'=R.T Q R`。rank2 head的source-origin是独立几何输入`O`，变换为`O'=OR+t`；不从标签反推，不默认centroid/COM。固定零原点下带电体系的平移需要另有实际dipole/charge律，用户ALLA未豁免该物理边界。

## 本次代码接点与实际边界

`phase1/v3_label_domains.py`提供：

- `OrderedEntryInputs/Target`：head只拿atom/channel/entry_graph、codebook、source geometry/frame；ordinal、label values、原mask/reasons只在target。运输/audit可保留`frame_origin=None,frame_basis=None`；给head时必须显式提供detached finite F32 `[G,3]`原点与`[G,3,3]`正交基，且两者来自已签`source_frame_metadata`实际rawref。类型层不生成0/I/centroid。basis仅作F32 metadata检查（atol1e-6/rtol0，禁autocast），不改变科学误差门。`ordered_entries_from_f64`拒F32作为权威输入，记录源与数组SHA及一次转换，不拟合统计。
- `Tensor6Inputs`：显式`origin[graphs,3]`及origin/source-geometry来源；`Tensor6Target`分别保存raw F32 full6、component_valid与由六个实际geometry ID推导的geometry_valid，`valid`仅为loss资格与独立recipe exposure。
- `collate_ordered_entries`只做atom offset与graph映射，不排序/去重/改ordinal；`collate_tensor6`保留全部六值/masks/reasons；`collate_domain_inputs`不含label或ordinal。

`phase1/v3_data_adapter.py`提供实际可接的`RealDataProvider.prepare -> PreparedV3Batch`与`make_proxy_inputs -> ProxyInputs`，复用原collate、structural/PairedCorpusBatch、sampler/trainer/验证入口，不另造runner。

实际Data发行格式尚未共同冻结，因此由**单独审核、实际rawSHA绑定的Data release解释器**把真实joint/release/registry/mapping/Common/effective TRAIN/heldout/D4/geometry/codebook解释成Model消费投影。该投影不是Data权威格式；解释器必须核原件真实含义，不能用“return True”、自造状态或改authority字符串代替发布。必须提供`verify_model_v3_release_authority(request, documents)`；全部metadata与解释器原件前后重绑，未知schema/缺件拒绝。真正的sidecar/shard解码与内容SHA验证由该已绑定readonly reader在CPU/GPU allocation内完成，Root login不读科学payload。

- 正式proxy/full/grid：仅`Common_intersection_effective_TRAIN`与实际final release；既有Root admission、240k proxy、三GPU SDP、D6、本地容量/配额和存储门不变。
- `authoritative_pilot`：只能消费真实已发布、单独版本的provisional pilot TRAIN/D4/heldout；返回`authority_kind=data_line_pilot`，不是Common/final。原Stage5 `bind_inputs`仍要求`data_line_final`，不能借此给D5资格；旧CLI未被悄改。
- 新typed字段必须有独立`domain_inputs`及`geometry_context`，当前`DecodedSample.geometry_ref`绑定原pos来源；ordered几何ref须逐项相等，tensor origin来源独立，绝不把label值喂给encoder/head。

ordered head使用`(pos-O)@B.T`的source-frame坐标，被动重表达`X′=XR+t,O′=OR+t,B′=BR`时保持同一source域身份；这不是retained AO/ordered列表的active旋转律验收。collate拒audit-only/数值frame混合，也拒不同frame绑定策略；to/pin保留原数值。真实r73 reader缺数值frame或独立source-frame metadata绑定即拒绝，不能由joint_policy或pos的geometry_ref自动推出该资格。

解释器投影须明确同一ALL_A_POLICY、三个真实role index SHA和两完整validation人口绑定；解释器还须绑定全部模型normalizations的canonical SHA（不只tensor），不能让调用者另填统计。每target的unit/sign/frame/origin/condition声明、r73可逆codebook、r674实际D4 series/task/分位政策/Source/人口和heldout rawrefs不可省略。provider身份不包含最终request SHA，避免request→provider→request循环；request自身仍被独立闭合。改变目标域实现、release、解释器或reader会改变provider绑定。

## 验证状态

本次只写源码与synthetic schema/transport tests；没有本机Python/AST/模型/数组/真实标签读取、测试或Slurm执行。计划47项（domain24+adapter23；实际收集/结果以Root CPU为准），覆盖ordered方向/onsite/重复/ordinal/双转换拒绝、full6 partial/geometry/count、显式origin、真实返回类型的provider/collate/role句柄、joint缺失、D4空/zero/错误人口/错误算法、pilot不可冒final与前后来源绑定。

这些fixtures不等于真实D3验收。Root/SA2负责公共FieldSpec/collate/PreparedV3Batch的类型保持和head/loss接线；SA4的pooling改动不在本模块复制。真实sidecar/codebook、共同合同、D4数值/人口与发布、源值比对、16worker、1000分子逐字段过拟合、恢复/H0与三卡SDP仍须实际完成。未带入任何已停止的FP32补偿模块或旧tensor98ec补偿reducer；最终配方、数据与模型验收不由本页冻结。

## 后继窄实现：target-local尺度状态与真实发布口（本节待CPU验证）

此前Root报告本模块v3的47项及整组144项通过；该旧QA不覆盖本节新增改动。新增专用`test_model_v3_loss_readiness.py`，原有测试文件不改写。当前只完成源码工作，未运行新测试/AST/模型或作业。

`DisabledNormalization`是显式typed disposition，无scale/center/transform，携目标、原因、真实统计rawref/pointer、数据版本与TRAIN身份。只有实际null、空人口、zero或nonfinite（含F32后不可用）的统计事实，在新target-local路径返回该状态；旧`tensor6_normalization`默认仍strict。缺authority、hash错误、错误condition/人口、unknown schema、坏pointer、负std、坏bounds或改标签一律整体拒绝，不捕获成“该target disabled”。缺整个真实D4/release也不能借此开始训练。

原raw values、component mask/reasons与source/geometry counts完整保留；`counts`仍表示原观察人口，独立`loss_counts`才判实际loss/optimizer update。disabled target不进字段loss分母、公开loss为None、其独立head.grad为None；其它就绪目标继续真实更新。原enabled-group分母不自动调整。验证raw MAE/R2仍用真实有效源人口，但loss采用独立分母；pre-scale与实际loss资格分列。全批无有效loss沿原no-label clock路径消耗已抽样样本、optimizer_updated=false，不做伪更新。CP沿原normalization projection/hash保存和恢复，改变状态/原因/来源会拒绝错误复用。

`V3LossResult`原构造/dataclass字段与默认asdict保持；新readiness为opt-in属性/metadata，旧默认指标不增加键。未改变模型head/参数、数据、掩码或科学阈值。

真实Data发行器使用`ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1/JOINTLY_FROZEN`与`ROOT_FINAL_LABEL_RELEASE_V1`，本adapter按其原Source逐项闭合Root/model ACK/contract、directive、registry/mapping/normalization、五个configuration wrapper及candidate→startup/accounting/raw C0。`FULL_V1_FROZEN`还要求实际Model runtime acceptance；`BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1`仅接pilot，不授full/proxy资格。用户冻结设计包不是joint。旧`MODEL_DATA_JOINT_CONTRACT_FROZEN`仅为显式engineering fixture协议，release_accepted=false，不能获得真实Data权威。

实际producer normalizer的`lower/upper/std_ddof0`及`original_training_labels_modified`按原字段读取，不伪造为另一种原始JSON schema。现Data冻结final_release_v1的`exact_series_recipe`仍会对缺/zero整候选raise，模型本补丁未改Data发行器；Data必须实际交付允许target-local状态的新版输出与签认，否则HOLD。真实reader/sidecar及其内容对照仍待交付/验收，schema机械测试不等于实际D3。

`tensor6_raw_mean_report`只读真实同series/condition/TRAIN及heldout人口的、明确为`raw_mean_F`的Data元数据。无该值准确返回`RAW_MEAN_F_REPORT_PENDING`，不拿winsor mean/audit_series_mean或norm(mean Q)代替，不从标签在login补算。raw mean未就绪不妨碍已有合法scale；scale disabled时不除零、不造ratio。新增Data报告绑定须带actual rawref、record pointer、人口/heldout SHA及计数；>10的ratio只提示下一版centering评估，当前c=0不变。

**头容量范围：** 原指南196的H1/H2/H3仅用于分子级标量。r73与tensor6是固定独立新域头，三forms下同构同容量；九个trial不作为它们的容量选择。512/hidden64/channel16例子中，r73为`68097+32*K`、tensor6为`32962`参数，仅说明该局部结构，不是实际完整模型总参数count或新的选择结果。
