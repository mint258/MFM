# D1 draft5 补充提案：原生域与模型实际消费的共同审阅

状态：`PROPOSAL_NOT_ADOPTED_NOT_JOINTLY_SIGNED`，2026-10-27。

本文是独立共同审阅材料，不替代 Root 的 `training_format_v3.md`（仍为 `v3.0-draft.3`），也不宣布 draft4/draft5 已生效。没有修改模型代码、原合同、物理标签、掩码、head、loss 或尺度。本文仅静态读取源码和已有小型运行元数据；没有运行 Python、AST、测试、Git、SSH、Slurm，也没有读取科学 DATA body。

精确文件路径、字节数、SHA256 及已有结果的机器摘录见同目录 `training_format_v3_draft5_native_consumption_source_refs_20261027_v1.json`。路径中的 Main 根为 `/share/home/zixiao/descriptor_analysis`，Windows 的 `X:/` 是同一挂载。

## 1. 版本与证据边界

- Root 当前合同为 19059 bytes、SHA256 `399ee0cebf8497c4e73accc52f84fd7d42b9753f9779433c80d12641df5a5ea2`，内含模型线 draft3 原意见；没有共同冻结签字。此前 `training_format_v3_draft4_native_domains_proposal.md` 仍为未采用提案。
- 本次检查对象是实际 `MFM_model_v3` 工作树的逐文件字节。静态读取的 `.git/HEAD` 指向 `model-v3`，其 loose branch ref 为 `3d9b1cc0c580dacc9398a5570b0c2fff3e257618`。这不证明工作树干净或文件等于该 commit。Root 提供的 GitHub `mint258/MFM` 公开 HEAD 为 `1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7`；本次没有读取该 commit 的全部文件，不能宣称公开版与工作树同字节。
- 已有候选 provider 实际结果继续有效：premerge `b4c59be9fe03718fe719560b166b4cddd11fa79e` 的 2414 PASS/2 skip、103 files；postmerge `3789c19865f70f80191986675cb13b606ebd210b` 的 2473 PASS/2 skip、104 files。它们验证合成 fixture 工程路径，不是本次重跑，也不是下列真实域的科学验收。原失败的 4520977 及后续仅调整负例 fixture 放置的记录保留。
- 实际 Main `4523708` C0 的 B32 manifest：32 固定记录 ×12 条件，共 384 observed、0 held；状态仍为 `FINITE_NATIVE_BODY_OBSERVED_PHYSICAL_CONVENTIONS_PENDING`，`native_physical_axes_verified=false`、`D1_jointly_frozen=false`。成功读取不表示所有字段均有值；registry N/A、UNKNOWN 和未输出的坐标仍是原状态。这不是完整 20k 诊断或最终全人口覆盖。
- 新 `native_frame_summary32_v1` 八件 SOURCEFINAL 仅提供可执行汇总路径。本提案尚未得到其实际 prepare/summary C0 结果，未将计划输出、token 比对、trace 或几何残差统计写成已观察事实。后续只追加真实结果引用，不回写旧接受历史。

## 2. 当前模型消费缺口重新核对

下表相对 `MFM_model_v3/`。行号绑定本次 companion JSON 中的工作树 SHA，不能移用于其他 commit。

| 位置 | 当前实际限制 | 共同冻结前必须补齐 |
| --- | --- | --- |
| `current/phychem_mfm/phase1/v3_wire_provider.py:119–148` | 只接 `synthetic_fixture`；只接 scalar/vector regression、base、PM7/Sprime_UFF；拒绝 tensor、basis、off-equilibrium | 新版本真实 authority adapter 及域专用投影；保留当前候选拒绝边界 |
| 同文件 `258–261` | 对 `basis_i/basis_j` 或 `sigma_pi_entries` 明确拒绝 | r73 无损双端通道 entry 域；不能只改 manifest 通过 |
| `phase1/v3_data.py:199–205` | 普通 pair 要求两个 atom index 不相等 | r73 onsite 与多通道 entry 的新类型、collate 和 batch 语义；不能删除普通 pair guard |
| `phase1/v3_contract.py:20–21,43–80,161–166` | level 仅 graph/atom/pair，representation 仅 scalar/vector/magnitude；target 宽仅 1/3；FieldTarget 没有原通道和 entry ordinal | r73 entry 身份与 r674 symmetric6 的显式模型契约，不以 CPU audit 对象代替实际 target 身份 |
| `model/v3_multiview.py:46–65`、`phase1/v3_trainer.py:168,251–255` | P/D 从当前 clean rows 读 H0；检查每个 choice 的 clean graph/atom 数 | gradient 要路由到真实 child 坐标视图，并审核 view 计数、H0 选择和 trainer 绑定 |
| `phase1/v3_wire_provider.py:234–244,318–319` | 读取断言 effective_role=TRAIN、显式 fixture atom-order receipt；prepare 只接 TRAIN | ROUTINE VAL、TRAIN/unseen-conformation 实际 authority、原子序和坐标收据；不能把 fixture receipt 升格 |
| `phase1/v3_sampling_bridge.py:123–136,298–307,347–359` | CandidateSamplingIndex 为 synthetic TRAIN、非 release；保留 anti-join、来源分离和 retained energy rank=0 | 实际最终 D5/共同人群 release 接口；既有桥接逻辑可保留，不能改 authority 字面值冒接入 |
| `phase1/v3_contract.py:124–153` | TrainNormalization 只验证已供应 affine transform；vector 要零中心/各向同性尺度 | 真正 D4 TRAIN 拟合/角色/版本/目标投影父链；tensor 规则仍需双方选择 |

`model/v3_heads.py`、`phase1/v3_losses.py` 仍只覆盖现有 scalar/vector/magnitude 及既定损失模式。没有从字段名存在、registry 行数或 synthetic PASS 推断新 head/loss 已实现。

## 3. r73：保留 pair-dependent 的原生双端通道 entry

精确来源仍为 `registry_id=73`、`task_code=pm7_B`、`source_path=values.sigma_pi_entries`。解析器字段 `basis_i/basis_j` 是原打印通道字符串，不是全局 AO 或笛卡尔 px/py/pz 编号。

Root 已取得并核对官方 MOPAC v23.0.3 tag `490725eac356e0e75037f37bdd2db343d6bc9e09` 的 `src/output/denrot.F90`：53–58 行声明 S-SIGMA/P-SIGMA/P-PI 等打印通道；98–137 行对每个原子对用 `coord(:,j)-coord(:,i)` 调 `coe`；142–172 行按 `isp` 合并通道并累积旋转后的 `sum**2`；187–198 行将打印矩阵对角项替换为逐行 bond-order 总和。这支持“通道与原子对方向相关、存在特殊 onsite/diagonal 语义”的源定义，不支持将其解释为全局 AO 矩阵。官方来源：[精确 tag 的 denrot.F90](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/denrot.F90)。

候选新域（名称及版本仍待双方确认）至少保留下表。它与普通无 self 的 atom-pair 域独立；不改 S bond/Wiberg 的既有语义。

| 字段 | 无损语义与边界 |
| --- | --- |
| native record/task/field identity、geometry_id、source atom-order digest | 同一条原生列表的父身份；不同条件不能借同一分子 ID 混用 |
| `src_atom`, `dst_atom` | 原解析器 atom 索引按已声明基数转为 wire 基数，保留方向；允许相等，不按无序 pair 排序 |
| `src_channel`, `dst_channel` | 两端原通道字符串原样保存；如采用 codebook，必须另有精确可逆、带 SHA 的版本。禁止单个合并 channel 或猜测 AO_ATOMINDEX |
| `entry_ordinal` | 该 record/task/field 原解析列表的次序；不是原 AO 编号或自行构造的 printed row/column。即使 atom 对和双端通道都重复，也保留每项 |
| original value、component validity、reason scopes | 永久 F64/原 token 证据保留；训练只按最终 codec 作一次 F32。源缺失、registry N/A、审阅和 exposure 独立，不加和、不去重、不补有效零 |
| retained raw/parser evidence references | 可审计原行、通道、值和列表投影；原 token/坐标/原 ID 只在受控 scientific DATA 中，不进入小 summary |

`onsite` 可由两端 atom 相等得到审计标记，不能使这些行自动无效或自动成为普通 bond 标签。官方打印对角的源定义和具体 retained entry 的对应仍需实际 summary 的逐项证据。native printed row/column slot 如果被诊断导出，只是额外 provenance；不得混为 AO 编号。

模型侧待共同确认：新 entry target/batch 如何保留双端通道与 ordinal；何种输出/损失可表达该域；与普通 pair 的类型隔离及 mask 单位。本文不选择 head、共享方式、去重策略或 loss。现有候选 provider 的拒绝保持到新版本实际验收。

## 4. r674：六分量存储与源定义分开验收

精确机器身份仍为 `registry_id=674`、`task_code=xtb_singlepoint`、`source_path=values.molecular_quadrupole_traceless_au`。`r67_4` 只是人类别名，不改程序字段。存储顺序固定为 `xx,xy,yy,xz,yz,zz`；对称矩阵无损重建为 `[[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]]`。六个原分量及各自有效性保留，不能因理论无迹而删 zz、强制消 trace，或拆成六个旋转不变标量头。

Root 的官方 xTB v6.7.1 tag `26b28010e805f7d1aeeef39813feb473e69cc4be`、`aespot.f90:669–740` 中，`molmom` 接收 Cartesian `xyz`、原子 partial charge、dipm 和 traceless atomic qp。分量顺序由该 routine 的注释及打印头直接给出。q 与 dip 平移项各自采用 `1.5*T - 0.5*trace(T)*I`，再与 atomic qp 相加；不能把整个已打印 full 再乘 1.5 或去 trace。该 routine 没有把值变成主轴本征值；本地源定义使用传入的 Cartesian frame。官方来源：[精确 tag 的 aespot.f90](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/aespot.f90)。

这些源定义尚不闭合 `mol%xyz` 的单位/原点沿调用链、q/CAMM 的符号、实际 raw→stored parser→geometry 的帧绑定。registry 的 `e bohr^2` 是待以原调用链和实际证据共同核验的声明；不在本文自签 units/sign/axes PASS。原打印 `f12.3` 精度、原容差和原值全部保持，printed trace 舍入差只报告，不修正。

模型需新增 symmetric6/对称 tensor 的 representation/shape、mask 投影、provider、head、loss 和 D4 适配。tensor 旋转测试、零中心/尺度约束和 Huber 聚合方式由双方共同确定；保留逐 component 统计，但不将它们直接当训练变换。源 Cartesian 定义已查清的部分与尚未验证的实际坐标传递分别记录。

## 5. gradient child 坐标与条件

`r623/r624/r625` 等扰动标签必须引用其实际 child geometry：明确 target 条件、parent geometry、view ID、原 perturbation seed/协议、原子序、实际输入坐标摘要和 parser/raw 引用。坐标和 token 保留受控 DATA；小元数据只存绑定、计数、差异/缺失原因和引用。

当前模型所谓 clean view 是从本次 choice 构造的模型视图，不自动等于 WP5 child。S denoising 的本地随机噪声也不是 WP5 的实际扰动。可讨论的消费方案是“child 作为有明确 parent 的实际 geometry choice”或“显式 target→actual-view 路由”；两者都须审核实际 reader、H0 路由、trainer choice/view 数、诊断 base/child anti-join 和独立条件 D4，本文不替模型作选择。PM7/UFF 来源 ID 继续独立，mixed 只明确选择一个来源，不假造跨来源构象对齐。

B32 的直接几何/输入绑定证据只说明其固定窗口；新 summary 会分别报告 native direct frame、rendered input、未输出、残差和未选择的单位假设。缺失 native coordinates 或无法闭合 frame 时保留 UNKNOWN，不能凭文件头存在或最佳拟合旋转通过。

## 6. TRAIN/VAL 与五层映射的真实父链

ROUTINE 用作 VAL 的用户决定和已闭合来源角色保持：原 11322 routine records 对应 7610 分子；VAL 按这些分子覆盖全部原 PM7/S′ 几何，不能只留那 11322 条记录。Root draft3 所列实际来源人口是 TRAIN 1206608 分子/11104772 PM7 records、VAL 7610/72525、剩余 FULL 6248/54557。它们不是经过共同人群/质量/诊断剔除后的最终训练人口，不能直接作为 D3/D4/D5 release。

当前 synthetic index/provider 不能直接更名为 data_line。新真实适配必须从 Root 最终 release 父链接入五层映射，并保留各层版本和完整 SHA：

| 映射层 | 必须显式绑定 |
| --- | --- |
| 1. registry → source component | registry ID、task、原 source path/component、status/unit/原字段形状，区分 N/A、未知和 invalid |
| 2. component → physical target | 实际 members、条件、level/representation、family/group、tensor6/r73 entry 域，不按 146 统计行自动造 head |
| 3. selector → stored entry/value/mask | field/leaf/entry identity、动态维度、双端通道、ordinal、reason book、完整 raw/source/new/review 证据，field-set 不静默丢项 |
| 4. actual geometry → sampling | 来源/parent/view、原 atom order、坐标摘要、有效构象与 retained training ranks、诊断排除、TRAIN/ROUTINE VAL/heldout 身份 |
| 5. provider → model field/view/normalization | schema/shard/codec/code SHA、Z−1/shape/offset、上述新域 target 类型、实际 H0 view、条件独立 D4、element reference 的明确 offset 与实际 role |

真实 release 还需最终 Common/质量与 masks、owner/registry、完整 TRAIN coverage、D4 和 D5 的实际父件及 Root 审核。D4 的 typed-cache 适配 SOURCE 或部分 profile 不能代替全部 TRAIN 拟合；已采用的旧 TIMEOUT committed 窗口应保留其独立 inventory/seed actual C0 与 Root adoption 链，而不是伪造旧父 batch C0。当前不存在的父件不填未来 SHA。

每层的“数据保留格式可读”“模型支持/实际消费”“物理单位/符号/frame 通过”分别记录。全 TRAIN 常量/异常/元素参考统计、VAL 排除、诊断 heldout 和 P′ 独立条件规则不因新接口降低。Se 仅保留用户已批准的排除率例外，仍排 UFF 不支持分子；本提案不扩大例外或放行独立 strict15 为生产 P′。

## 7. 下一次共同审阅的最小闭合表

| 顺序 | 数据侧须交真实证据/接口 | 模型侧须明确确认 | 当前状态 |
| --- | --- | --- | --- |
| 1 | summary prepare/summary actual C0、源 pin、每条件计数/原因、原 parser 精确比对、retained DATA 引用；不外推为全20k | 按同一工作树/commit SHA 对照；保留已有 synthetic PASS | 新 summary 仅 SOURCEFINAL，实际结果待 Root |
| 2 | r73 双端字符串、onsite、重复与 list ordinal 原样 roundtrip | 新 entry representation/target/collate/provider；普通 pair guard 保留；输出/loss 另共同决定 | 必需契约升级，未实现/未签 |
| 3 | r674 顺序/原 token/trace 审计；官方调用链单位/符号/实际 frame 闭合 | symmetric tensor representation/provider/head/loss/normalization 与旋转验收 | 仅源定义部分清楚，消费与物理签认未闭 |
| 4 | gradient actual child→parent/坐标/原子序/条件定位与诊断排除 | 选定实际 view/H0 路由并更新相应 batch/trainer 验收 | 原 provider 明确拒绝；不能借 S 噪声替代 |
| 5 | 最终 registry/Common/masks/role/D4/D5/schema/shard 父链及真实 D3 | production authority + ROUTINE VAL + condition D4 的 fail-closed adapter 和实际加载验收 | 来源角色已有真实证据；最终 release 未交 |
| 6 | 共同版本、精确源码/实际结果清单和未决项处理 | 模型线书面确认，双方共同签认同一版 | 没有 joint sign；Root 当前 draft3 不变 |

不因本提案追加新 controller、重复三 fixture 或开始全量 QM。已有 source-level seam、CPU 汇总和最终数据 release 各守原门；能静态核清的字段定义不塞进新的科学重算。

可供 Root 在真实状态中使用的短通知（非签认）：

> 新增 D1 draft5 原生域/模型消费共同审阅补充提案。静态复核当前 Model 工作树仍缺 r73 双端通道+onsite+ordinal、r674 tensor6、实际 gradient child H0 路由及真实 TRAIN/ROUTINE VAL/D4 authority 消费；原候选合成 PASS 保留。B32 实际 C0 仅闭合有界原生读取，summary 实际证据待补，单位/符号/实际 frame 及新 head/loss/scales 仍未共同确认。工作树文件 SHA 与公开 commit 分列；当前 D1 仍 draft3，未 joint freeze。
