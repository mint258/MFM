# D1 draft5 补充：公开精确 commit 的字节核对与模型条件反馈

状态：`STATIC_PUBLIC_COMMIT_VERIFIED_CONDITIONAL_REVIEW_RECEIVED_NOT_JOINT_FREEZE`，2026-10-27。

本页只补充旧 draft5，不修改其原文或 30 项冻结 refs，不修改 Root draft3、Model 代码/文档或任何科学值与 mask。核对对象固定为 `mint258/MFM` 的 `1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7`，没有使用浮动分支或把不同 commit/工作树视为同一版本。没有运行 Python、AST、测试、Git CLI、SSH、Slurm 或读取科学 DATA。

## 1. 字节核对结论及范围

通过 GitHub 插件逐文件请求精确 commit、完整 base64 内容，无行截断。对解码后的原字节计算 SHA256，并按 `SHA1("blob " + byte_length + NUL + bytes)` 逐件核对 GitHub 返回的 blob SHA1；没有转换换行、重排 JSON 或重新编码后冒称字节相同。

| 原 draft5 的引用范围 | 结果 |
| --- | --- |
| 30 项 refs 中属于 MFM 的 22 项 | 全部成功取得并完成完整 SHA256/Git blob SHA1 校验；20 项与冻结/当前工作树字节一致，2 项不同 |
| 其中 11 件关键 consumer 源码 | 11/11 与冻结 refs 及当前工作树同字节，详见下表；draft5 已实现消费缺口可用于此公开 commit |
| 另 11 件 Model 文档/已有证明 | 9 项同字节；差异为 `docs/interfaces/STATUS.md` 和 `docs/model_v3/results/D1_draft3_review_source_recheck.json` |
| 原 refs 的其余 8 项 | 数据线合同/提案、官方程序源及其取得证明、B32/成本/summary-source 元数据，位于 MFM 仓库之外；不应向 MFM 请求或称为“公开 MFM 同字节” |
| 当前工作树对原冻结 Model refs | 22/22 仍同字节。branch ref `3d9b1cc…` 与公开 commit 不同的事实保留；未证明全树一致或工作树干净 |

11 件关键源码相对 `current/phychem_mfm/` 为：

| 源码 | 公开 commit 的消费边界仍成立 |
| --- | --- |
| `phase1/v3_contract.py` | scalar/vector/magnitude、宽 1/3；无 entry-channel/tensor target 类型；TRAIN-only affine 校验不替代真实 D4 release |
| `phase1/v3_data.py` | 普通 pair 的 collate 拒绝 diagonal；target/device/offset 路径没有独立 channel/ordinal 域 |
| `phase1/v3_wire_provider.py` | 只接显式 synthetic fixture、base scalar/vector；拒绝 r73/tensor/off-equilibrium/真实 authority/VAL |
| `phase1/v3_wire_audit.py` | 既有来源/原因审计保留；审计携带不是新物理域的预测消费实现 |
| `phase1/v3_sampling.py` | 既有来源、角色与采样类型边界保留；没有凭枚举存在验收真实人口 |
| `phase1/v3_sampling_bridge.py` | 候选 synthetic TRAIN、来源独立、anti-join 和 retained training rank 规则保留，非最终 D5 release |
| `phase1/v3_architecture_views.py` | 现有结构视图不自动成为 WP5 实际 perturbation child |
| `phase1/v3_trainer.py` | 仍绑定当前 clean-view/choice 结构；未接真实新域、child H0 与最终 D4/D5 |
| `model/v3_heads.py` | 普通 pair 用交换对称特征且无 channel 输入，并拒 self；未实现 r73 有序通道头或 r674 rank-2 头 |
| `model/v3_multiview.py` | P/D 仍从当前 clean rows 取 H0；未实现 target→实际 child-view 路由 |
| `phase1/v3_losses.py` | 既有 scalar/vector 路径与计数保留；未实现 r73 entry/tensor/partial-observation 新契约 |

逐文件 bytes/SHA256/blob SHA1/原 frozen reference/当前 reference/比较结果均在 `byte_comparison.json`；原始精确公开 SOURCE 响应在 `source_transport.json`。这是静态实现等价证明，不是重新运行旧测试、真实 D3 加载或科学验收。原 synthetic provider 的 pre/post PASS 继续保持原时间点和范围。

第二项文档差异 `D1_draft3_review_source_recheck.json` 经完整解码及 JSON 解析后，与本地冻结版本内容完全相同：31 checks、31 unchanged、0 changed、264 registry rows，tests/science/contract_finalized 均为 false。它只有字节差异，不应当作新增运行、当前 source census 或共同冻结。

## 2. 已收到的真实新增模型审阅

前轮依据本地 11325-byte STATUS 静态审查，未覆盖公开版新增的后文。现在确认公开 [`STATUS.md:202–206`](https://github.com/mint258/MFM/blob/1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7/docs/interfaces/STATUS.md#L202) 已有模型线 draft4 增量意见。不能再把当前公开模型状态表述为“尚无新审阅”。它仍没有联合签认，因此旧 draft5 的“未共同冻结”结论保持。

实际意见在同一精确 commit 的 [`training_format_v3_draft4_model_review_20261027_v1.md:65–112`](https://github.com/mint258/MFM/blob/1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7/docs/interfaces/training_format_v3_draft4_model_review_20261027_v1.md#L65)，状态为 `MODEL_REVIEW_RECEIVED_CONDITIONAL_DOMAIN_DESIGN`。`MODEL_SOURCE_BINDINGS.json` 状态为 `ROOT_SOURCE_REVIEW_BOUND_NOT_JOINT_FREEZE_OR_RUNTIME_ACCEPTANCE`，明确 train-ready=false、joint=false、未运行测试或读取 native payload。四份新增审阅 SOURCE 的完整字节及哈希分别保存在 `incremental_review_transport.json`、`review_provenance.json`。

| 精确条款 | 已收到的模型意见 | 数据侧承接与仍待共同决定 |
| --- | --- | --- |
| 67–73：r73 entry | 支持原解析列表的有序双端 atom/channel、onsite、重复和 ordinal；需要独立消费/计数/恢复链 | 同意该保留方向；无损范围仅是已解析列表，不宣称原 AO 矩阵完整。ordinal 用于 provenance/alignment，不能作为可学序号替代物理身份；监督人口按原 ordinal，不按 unique atom pair |
| 75–77：F64 | 现 codec 不含 f8、family value 强制 f4；不能只加 entry 数组就称永久 F64 已支持 | 同意必须补明确版本与来源：永久 F64 留既有权威源/sidecar并绑定训练一次 F32，或新 codec+family schema 同时支持 f8。两种方案尚未选择。原 token 未保存就保留 UNKNOWN，不从 F64 容器反推程序精度 |
| 79–87：r674 | 六成员作为一个 tensor；统一数值 R 的行坐标约定；Frobenius/radial、TRAIN 单尺度为共同候选 | 同意按一个物理目标共同设计，保留全部六值和原 mask；下文列出公式/参数待定项，不把候选或 source-only 文档当实现/接受 |
| 89–96：partial mask | source leaf 有效性与全 tensor loss eligibility 分离，或定义 frame-aware 观测算子 | 同意必须先冻结政策、分母和覆盖报告。现 codec 的 all_components 不授予单方丢弃有效 leaf 的权力；本页不选两方案之一 |
| 98–108：真实证据与验收 | 原 raw/input/owner/version/atom-order、native 定义与精度、五层 map/release/D4/D5；再实现新 consumer 和真实模型验收 | 使用既有 B32→summary 和官方精确程序源推进，不重跑 QM 补身份、不重复已有镜像 fixture。真实 TRAIN/ROUTINE VAL、gradient child、1000 分子逐头过拟合和三 GPU SDP 冒烟仍各守原门 |

r73 的原字符串 DEL/DELL/DELTA 等不能靠人类别名归并。未知 channel 在新 consumer 应拒绝消费并保留原记录/原因，而不是静默改 mask、补镜像、合并或改成有效零。原普通 S bond/Wiberg/default pair 路径不改。

## 3. 对 r674 数学条件的数据侧回应（尚未采用）

同意模型条款 83 要求在契约里区分同一个数值矩阵的约定：模型线报告的行坐标变换是 `X'=XR+t`，若原点也随之变为 `O'=OR+t`，相应二阶 tensor 写作 `Q'=RᵀQR`。原 draft3/draft4 的 `RQRᵀ` 只有在明确 `R_data=R_modelᵀ` 的列坐标约定中才能对照，不能让两份合同共用相同 R 字面值而方向相反。这是待冻结的接口约定；不在原标签上旋转、换原点或拟合变换。

来源边界单独保留：模型 `MODEL_SOURCE_BINDINGS.json` 将行旋转诊断模块绑定到**另一个** `MFM_model_v3_composed_equivariance` 工作树的 30285-byte 源文件，SHA256 `0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8`。本轮按短模块名尝试公开 commit 的 `current/phychem_mfm/phase1/v3_composed_equivariance.py` 实际返回 404（原响应见 `supplemental_lookup_failure.json`），没有换默认分支或拿其他文件代替。故本页接受“需要统一此约定”的审阅条件，不把该实验工作树源文件称作已在本公开 consumer 目录实施的 tensor 支持。原生 quadrupole 的实际坐标传递、原点/平移律/单位/符号仍待 Root 官方调用链及 actual summary 证据，数学变换公式不替代这些门。

同意围绕 Frobenius/radial 的方向继续设计：按源顺序 `xx,xy,yy,xz,yz,zz` 的 Frobenius 平方权重是 `(1,2,1,2,2,1)`；逐分量 Huber 即使给 off-diagonal 加 2 也一般不旋转不变。模型条款 85 的 radial 候选、`d=6` 正交六坐标规范或 `d=9` 矩阵-entry 规范，仍须共同决定 `d`、Huber delta、归一化分母、每 tensor 计一次的权重和 field/group 聚合。镜像矩阵不是九份独立标签；本文未选择或实施某种 loss。

同意最小 TRAIN 单尺度候选应与共同变换律相容，可讨论 `(Q-cI)/s`（或 `c=0`），而不是独立逐轴中心/尺度。`c/s` 的稳健统计、条件、eligibility、退化尺度、原点和 Å/bohr 输出映射均须由最终 D4/科学定义及共同决定绑定。本文没有计算、选择统计公式，没有把统计 cI shift 当作移动物理原点，也没有把源程序 q/dip 的 1.5 定义系数再次施加到已打印 full 值。

同意 partial-mask 的两个候选必须显式版本化并保持 source mask：其一，仅完整 tensor 进入该 loss，另保存 eligibility 与完整/部分覆盖；其二，保留真实观测算子 `y=A(Q)`、frame/metric/分母，并随 `T_R` 使用 `A'=A∘T_R⁻¹`。不能只旋转预测后照搬六个 bool，或从缺失分量制造旋转标签。实际全人口 component 覆盖未知前不选政策；有限 B32 的覆盖不能替代该决定。

## 4. 对旧 draft5 待办的精确更新

1. **已闭合：** 本公开精确 commit 的 11 件关键 consumer 与已审工作树实现逐字节相同。r73/tensor/child view/真实 authority 的实现缺口无需因不同 commit 名称重新猜测；不是全仓库等价或部署验收。
2. **已收到，未联合采用：** 模型线已提出有条件的域/精度/旋转/loss/D4/partial 设计反馈。数据侧同意上述保留原则与共同设计条件，不能继续写“模型尚无意见”，也不能写“双方已选定/冻结算法”。
3. **仍待实际证据：** summary prepare/summary C0 的完整父链及 retained 逐 entry/六 token/trace/实际几何比对；官方调用链 units/sign/origin/frame；有限窗口与全20k/最终覆盖分开。Root 当前 source/pure 或提交/排队不冒充 summary 实测。结果到达后另追加真实引用，不改历史文件。
4. **仍待实现与真实交付：** 新域 codec/family/FieldSpec/provider/collate/head/loss/recovery、最终角色/Common/quality/masks/五层 map/D4/D5/release、真实 TRAIN/ROUTINE VAL 与 child H0 接入，再做规定的真实模型验收。已有合成 provider PASS、原 C4 HOLD、独立 P′ 精度诊断边界均不改变。

Root 可使用的短状态通知：

> 已对公开 model-v3 精确 commit 1f7f255 的 22 项 Model 源/证明逐件核对；11 件关键 consumer 全与 draft5 冻结及当前工作树同字节，实现缺口仍在。公开 STATUS 后文及独立 draft4 审阅已有真实条件反馈：数据侧承接 r73 entry/F64 版本、r674 行旋转/Frobenius-radial/TRAIN 单尺度/partial-mask 共同设计条件；参数/政策、原生物理证据和新 consumer 均未冻结或接受。原 draft5/refs、Root draft3 与 Model 代码不变，无 joint v3.0 签认。
