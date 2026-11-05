# D1 draft5/addendum：模型线条件式反馈（DRAFT v1）

状态：`MODEL_CONDITIONAL_SOURCE_REVIEW_NOT_JOINT_FREEZE`。本页只读比较模型线已公开的 draft4 意见、数据线 draft5/addendum、其明确引用的小元数据和必要源代码；不修改合同、登记、数据、模型或标签。Root 的 `training_format_v3.md` 仍为 `v3.0-draft.3`。此页不签认 draft5、joint v3.0 或真实训练可用性。

精确输入和本页 raw SHA 见同名 `training_format_v3_draft5_model_feedback_refs_DRAFT_v1.json`。旧模型意见是 `training_format_v3_draft4_model_review_20261027_v1.md`（14563 B，SHA256 `48303f8dcdd50c1a36d9ab5e1131de6954e3c4fdaf671c0d1f3dc85ad211cc12`），未被本页覆盖。

## 已吸收的意见与仍需确认的边界

addendum 已明确收到模型的条件式审阅；不能继续写成“模型尚未审阅”，也不能把“已审阅”改写为“已共同采用”。原 draft5 的未公开工作树比较，已有 exact public commit `1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7` 的增量来源核对。本轮读取并绑定该数据线静态证据，不重新调用 GitHub 或宣称重新验证其整树。

| 事项 | 已吸收，模型线可确认的设计原则 | 尚未共同冻结或实际验收 |
| --- | --- | --- |
| r73 原生身份 | 有序的两个 atom 端点及两个独立 channel、onsite、重复项和原解析列表 ordinal；独立于普通 pair | 新域名称/版本、可逆 codebook、target/head/loss/count/恢复实现及实际 retained-entry 对照 |
| r73 精度 | 区分原值、原 token/程序精度和 F64 容器；不再把现有 f4 wire 当作永久 F64 保存 | 权威 F64 sidecar＋一次 F32，或新 f8 codec/family schema，二者尚未选择 |
| r674 目标 | 保留 `xx,xy,yy,xz,yz,zz` 一个对称二阶物理目标及六项原始有效性 | 实际 origin/unit/sign/frame、tensor consumer、loss 和 D4 的共同版本 |
| 旋转约定 | 行坐标 `X'=XR+t` 与同变换原点对应 `Q'=RᵀQR`；列约定必须明确 `R_data=R_modelᵀ` | 不得在相同字面 R 下同时采用旧 `RQRᵀ` 和行约定；尚无新域实际旋转验收 |
| tensor loss/尺度 | Frobenius 非对角权重、各向同性尺度/中心、partial-mask 与训练 eligibility 分开讨论 | radial 定义、d6/d9 分母、Huber delta、组权重、拟合人口及 partial 策略未选定 |
| gradient child | 标签必须绑定实际 child geometry、原子序、parent、条件、扰动协议；不能借 S 噪声或 base H0 | 数据 child 证据与模型 view/H0 路由、batch/trainer/恢复验收未闭合 |
| release/authority | 五层映射、真实 TRAIN/ROUTINE VAL、来源分离、D4/D5 父链不可省略 | Common/质量/mask/角色/最终人口与 D3–D6 交件仍不能由源码或 fixture 替代 |

## r73：可接受的无损表示，不等于已有消费者

本轮重新读到原 `wp4_native_pilot_v4.py:171–195,383–385`：`sparse_sigma_pi` 以 `(打印 atom 号−1, 原 channel 字符串)` 识别端点，保留 onsite 和选定近邻，输出有序的 `atom_i,basis_i,atom_j,basis_j,value` 列表。它没有保存独立 AO ordinal；有选择和解析跳过分支。因此“无损”只能针对**已保留的解析列表及其来源**，不能宣称恢复完整 AO/原打印矩阵或所有被跳过项。本轮没有另外重验 WP5 完整调用链。

官方 MOPAC v23.0.3 `denrot.F90` 的已绑定静态源码说明：打印通道从 `(s,px,py,pz)` 改为 sigma/pi 等，使用原子对方向调用旋转、对部分通道累积平方项，最后另设打印对角 valency。它支持 pair-dependent 通道和特殊对角语境；仍不证明本冻结生产程序、具体 retained entry 或任意通道在分子旋转下的实际性质。`DEL/DELL/DELTA` 不凭名字自动等价；未知字符串、缺失映射和原原因保留，不能并码或补有效零。

可继续共同审阅的最小 wire 项为：完整 owner/task/field/condition/geometry/atom-order 身份；零基 `src_atom,dst_atom`；原样 UTF-8 `src_channel,dst_channel`（或可逆版本化 codebook 及 SHA）；record/task/field 内的 `entry_ordinal`；已解析值及可得的原 token/来源精度引用；逐 entry/component 的原 validity、reason 和独立 review/exposure。保留重复及方向，不排序成无序 pair，不镜像、去重、求和或平均。ordinal 用于对齐/审计/恢复，不作为任意 learned ID 捷径。

实际模型仍须新增独立 entry 的类型和路径：

1. FieldSpec/FieldTarget、DecodedSample 与 batch 需要承载双端 channel 和 ordinal；collate 只对 atom index 作原子偏移，保持每记录 entry 顺序、重复及恢复映射。
2. predictor 输入必须区分两端的 atom 表示与两端 channel；输出逐 entry 对齐。当前 `_PairHead` 的 `h_i+h_j,|h_i−h_j|,distance` 交换对称，且没有 channel 输入，不能靠放行 self 项表达该域。具体物理对称性和共享/head 形式未在本页选择。
3. mask/loss/count 必须按已声明的 entry/component 人口计算，保留来源无效、review 和组/家族 exposure 的分离；未共同冻结前不能由 unique atom-pair 数取代 entry 数。优化器提交/恢复还需绑定 entry 投影、codebook、registry 和消费游标。

因此只改 `allow_self`、删除 duplicate 检查或镜像 ordinary pair 都不够，也会破坏旧 S bond/Wiberg 的边界。当前 wire `mapping.validate_pairs` 仍要求 atom-pair 唯一，模型 collate 仍拒 self，provider 仍拒 basis；这些拒绝不应通过改 authority 字符串绕过。

## r674：源程序定义、物理绑定和训练定义分别闭合

官方 xTB v6.7.1 `aespot.f90:669–740` 的 `molmom` 接收 Cartesian `xyz,q,dipm,qp`，六项顺序与打印头一致；q/dip 平移项各自做 `1.5*T−0.5*trace(T)*I`，再加入 atomic qp。此处不是主轴本征值输出。不得对已经打印的 full 再乘 1.5、减 trace 或删 zz。实际调用链的 `xyz` 单位/原点、q/CAMM 符号、实际运行版本、parser 选取/转换和最终 geometry 的关系仍须证明；打印标题或 registry 的单位声明不能独立关闭这些事项。

行坐标的数学约定已经讲清，但物理坐标绑定仍待实际证据。原模型旋转诊断引用是独立 `MFM_model_v3_composed_equivariance` 工作树里的已绑定源码；不能把 exact public commit 下该短路径的 404 替换成默认分支文件，也不能把诊断源码当已部署 tensor consumer。源 Cartesian frame、整体旋转约定和 actual native frame 分别记录。

训练定义仍需双方在同一版本决定：

- 单个对称 tensor 的完整六成员及索引；原各分量 mask 保留，trace 打印舍入只报告，不修改标签。
- Frobenius 对六项的权重为 `(1,2,1,2,2,1)`。逐 component Huber 即使加此权重也一般不旋转不变；若选 radial loss，须同时固定 radius、d6/d9 归一分母、delta、有效人口计数和字段/组平均方式。
- 归一化候选 `(Q−cI)/s` 或 `c=0`＋单一尺度尚未选择；D4 须按实际 TRAIN 和 condition 拟合，并处理退化尺度。统计中心 `cI` 不是物理原点平移，也不能代替正确的 tensor 平移定律。
- partial validity 不自动等于完整 tensor loss eligibility。选择完整六项 eligibility 时必须保留原 component masks/reasons 并报告 excluded/retained coverage；如选 frame-aware 部分观测，则需要显式观测算子及其随旋转的变换，不能旋转 prediction 后重用固定六项 bool，也不能补齐缺失值。本页不替双方选择。

当前 `FieldSpec` 只接受 scalar/vector/magnitude，宽度为 1/3；`FieldTarget.valid` 是每观测一项 bool。现有 vector radial Huber 不是 tensor6/partial tensor 实现。需要 representation/provider/collate、保持所选对称性与坐标绑定的 tensor head、loss/count 和 D4/CP schema 的完整新路径；不能拆六个普通不变标量头来声明完成。

## unit / sign / property axes 还缺什么

需要继续按**精确 registry/target/component/condition/source** 单列，不设“所有物理轴已验证”的总开关：

- r73：保留原程序/解析值定义、方向相关通道、特殊 onsite 与 codebook；actual raw→parser→retained list 对照尚不能由官方不同版本源码代替。
- r674：完整六成员和打印定义已有静态依据；实际 origin、坐标/物理单位、符号及 tensor frame 的运行父链仍待共同验收。
- dipole/gradient/force 和 child：完整分量布局、源单位与转换、符号及实际几何/原子序须分别核验；不以 tensor 的静态结论外推。特别不能把程序的整体打印标题当每个 component 已完成单位转换的证明。
- draft5 没有关闭 MolMR、Fukui、Dn/De 等旧 convention pending。本页不猜测它们的物理命名或新单位；须由各自精确源定义、程序调用链和已有受控证据闭合。

可复用已有 source/provenance 和有界 native/summary 结果，不要求仅为身份证明重跑 QM。B32 读取成功只覆盖该固定窗口；原提案/addendum 当时尚缺 summary actual C0。本轮没有读取其后新 summary 证书，既不补写通过，也不据此断言后续未发生。已有或新增实际证据由 Root 另作增量绑定，不修改原 source-only/失败记录。

## D3–D6 与下一次共同冻结

| 交付 | 本轮明确未替代的事项 |
| --- | --- |
| D3 | 真实候选 export/release 及模型实际加载、源值/索引/mask 对照；合成 provider PASS、B32 和公开源字节一致不是 D3 真实验收 |
| D4 | 最终 TRAIN-only、逐 condition 的拟合人口/目标投影/尺度/offset/版本 SHA；拟合源码、局部 cache 或部分统计不等于最终 D4 |
| D5 | 最终 Common/质量与 TRAIN/VAL/诊断 anti-join、来源独立的构象顺序/retained rank、N=1/N=2/k 不足策略和实际 index/人口 release；候选 sampler 或 legacy Native S 不等于该交付 |
| D6 | 本轮没有收到或验证最终 D6 交付及其实际消费验收；按原交付清单另行交件，不用本次源审阅、旧合成测试或 Native S 结果代填，也不在本页重定义 D6 范围 |

Root 已通知 D1–D7 仍未 final；上表是本轮证据边界，不是重新判断数据线全部实时状态。四项分别保留待交付/待实际验收，且 P′ 条件不能借 PM7 的 D4。真实 TRAIN/ROUTINE VAL 的来源角色已有证据，与最终 release 人口和新真实 authority adapter 是不同事项。

下一次共同审阅可直接追加：实际 summary 的 prepare/result/parent C0 与 retained source 引用；各新域最终 schema/codebook/selector/precision 选择；逐 target 的 unit/sign/geometry/frame 证据；统一 release 下的五层映射（registry→component、component→物理目标、selector→stored entry/value/mask、actual geometry→sampling、provider→FieldSpec/view/D4，含 D5）；共同选择的 head/loss/mask/count/normalization 规则及实际消费者验收计划。未有的父件保持 pending/null，不填未来 SHA。本页不要求新 controller、重复已过 fixture 或无关的新 QA 父任务。

模型线结论是：**draft5/addendum 已实质吸收先前条件式意见，可作为下一轮共同冻结的设计输入；当前尚不能宣告新域可训练、真实 consumer 已实现/QA 已过或 joint v3.0。** 本轮未运行 Python、AST、Git、测试、模型、Slurm、SSH、网络请求，未读取/转换科学 payload、LMDB、数组、标签或权重；只新增本页与来源元数据，所有原件保留。
