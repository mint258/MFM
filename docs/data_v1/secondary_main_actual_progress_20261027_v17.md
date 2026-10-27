# 数据线实际进度 v17（2026-10-27）

本页记录 v16 之后的实际闭合、错误与有限授权；D1–D7、共同人群及扩充仍未整体完成，尚无最终交付 PR。

## 已完成的独立核验

| 工作 | 实际结果 | 可采用的范围 |
| --- | --- | --- |
| 全源身份与逻辑顺序 | 4524431 C0/87s/16CPU14，16 个真实进程完成全部 11231854 记录、1220466 分子及 171 来源组；184 base、2024 label、14 task slots | 新 full logical owner plan 的来源身份与原文件顺序权威，已独立 Root freeze；没有读取 label 数值，不能替代全数值覆盖或最终 Common D4 |
| 原生精度与控制证据 | 4524414 C0/61s/16CPU15，384 完成、0 held，复用原 1152 input/evidence/raw 文件；独立 technical close 成功 | 原输出的精确打印/计算与保留控制证据；单位、符号、origin/axes 和模型共同验收仍未放行 |
| D5 materializer 源码 | 4524182 C0/31s/16CPU15，3 项边界检查通过 | 实际 D5 数据物化仍等待真实 Common、几何、顺序和全部真实 child 输入 |
| no-PM7 UFF+D 入口源码 | 4524328 C0/35s/16CPU15，两组共 6 项检查通过 | 完整 R/N 上游及实际 10k pilot 尚未具备，不用部分候选替代 |
| 标签恢复 seed | 4523763 C0/3225s/16CPU13，448 原闭合区间只读采用，1951233 行新 sidecar 重新打开校验 | 旧 1904 仍 TIMEOUT；两个 RESERVED 窗口、旧账、未知消耗及全部文件保留 |
| Drugs 全原生结构 | 4523818 C0/1579s/16CPU14，558002 全部闭合 | 126 条涉及 31 名称的 native/source key 差异保留并集，未放行全池去污染 |

全源角色实际守恒：TRAIN 为 11104772 记录/1206608 分子；ROUTINE VAL 为 72525/7610；FULL 为 54557/6248。新权威不改写旧 full plan 的 null，也不追认旧 TIMEOUT 或旧账本。

## 本轮新获批准的 QA

用户明确回复“批准仅此轮最多1200次QA”。新决定独立保存于 `configs/data_v1/user_pprime_new20_all12_strict_qa_20261027_v1.json`，绑定原具体提案与已准备的 20 唯一 MID。原未获授权模板保持原样。

仅本轮 20×12×5、最多 1200 调用，三个精度例外为 pm7_B 的 `SCFCRT=1.D-9`、xTB singlepoint 与 perturbed_gradient 的 `--acc 0.01`。原版本、种子、坐标、900 秒单调用超时和全部质量阈值不变；最多 16 CPU/24h，共享准备 1GiB、执行 31GiB；scratch/RSS 软观察，有限 quota provider 不自动续期。失败或资源压力停止派发、自然收尾，不重试、不替换未知调用。实际任务 **4524436** 已提交到 CPU13，未申请 Slurm 内存；本页尚未记录其终态或科学通过。

原 15 次已获准诊断的 4523473 C0/15 调用、25 原向量比较及 5 同几何检查通过仍保留，原 15FAIL 与 UNKNOWN 原因也保留。新本轮没有自动更大 QA、2000 构象试点或全量授权。

## 实际错误与恢复边界

紧凑标签投影 v1 的 4524257 实际 FAILED/37s/592 核秒，资源时钟读取了不存在的 `observed_unix_seconds` 顶层字段。新 v2 采用实际 ISO/Slurm/monotonic 时钟，经 4524377 C0 的源码逆证明及 3 项边界核验；实际 v2 投影 4524395 仍 FAILED/35s/560 核秒，原 compact mask 中 bytes 不能直接 JSON 序列化。10 个小窗口与 3 个 UNKNOWN_UNPUBLISHED tickets、69947985B 逻辑消耗均保留，不按失败父件采用为正式 C0。新 v3 仅修复可逆二进制 mask IO 与读回校验接合，须实际 CPU 写闭读回及新 512 对照通过；原 worker、掩码语义、TSQR256、原序 left fold 和所有 QC 不变。

原 native precision 4524373 FAILED/60s/960 核秒，原因是新 reader 的一处 Python 关键字调用语法错误，在 DATA 读取前失败。Root 将全部 8 件修复前源码归档并只修复该语法；原 SourceFinal 包保留，当前 reader 明确为独立 R2 字节版本。4524392 C0/30s/480 核秒已实际 AST/import 全部 7 个 Python 文件及 3 项检查，随后才运行并闭合 4524414。没有把旧 8 件 SourceFinal 摘要冒充当前字节。

S′ 旧有限 controller 2962541 已实际退出，其最后状态为 `HOLD_ROOT_REVIEW_REQUIRED_NO_NEW_DISPATCH`：batch-00132 prepare 4524181 FAILED/31s/496 核秒，错误为 `CURRENT_SHARED_ACCOUNT_QUOTA_REQUIRED`；原异常未保存 budget.report，因此具体根因仍 UNKNOWN，不能直接写为配额不足。失败前未开始 formal pointer/baseline/UFF 读取。冻结 controller state 有 107 批实际 close C0；108/109 的 run 4524128、4524172 随后也已自然 C0，但尚不能据此写为 close 完成。后续 11–19 节点资源适配需真实新节点核验、旧阶段实际采用和 Root 有限 cutover；不终止或重复在跑科学任务。

旧 TRAIN512 路由到 r7 后停止，原因是旧元数据 helper 读取数值 query/report。全部旧结果与源码保留，后续 numeric/calibration/query/model 只作为 CPU DATA；未继续提交旧 r8。原小样本人群是总计 4251 记录/512MID/16组（TRAIN4211、VAL20、FULL20），不是 4251 TRAIN。median/MAD 是源诊断，不是指南 1.6 的最终 Common、TRAIN-only、0.1/99.9 分位缩尾 mean/std normalizer。

## 资源、源码与账本

当前已公开并核验的源码为 v23/Source29：execution `fdc3395804744726ba37f6bfe06971bf87051802`，public data-v1 `8fc441222f0a0c4ce873ff5f2499b1bf3becc73b`，tree `17a4ca5b1bf7cd84ab2d3d043c8ca66281d32502`。原 checker 27 项及自身 3 项、完整 3441 源文件实际 CPU 检查通过；此页及新修复尚未包含其中，下一提交仍须整体实际 CPU 检查、Root 当前字节复核。

Main46 为 599 唯一父任务/569.2533333333333 已观察分配核时；Alpha44 为 231 唯一父任务/1734.5022222222221 已观察分配核时。两者是各自点时账本，之后的 QA 等继续计入，不能把历史快照相加。全部 FAILED/TIMEOUT/启动费用保留；免费不等于核时为零。

Main 全未来 writer caps 加 200GB reserve 现按 1900737418240B 核算；只退休实际闭合的 Drugs 与 legacy512 的未来 writer 预算，用于新 numeric8GiB、native1GiB、full identity1GiB；全部 182 S′ caps、旧 32GiB 逻辑与 UNKNOWN 费用、独立 labels14GiB、新 QA32GiB 和历史文件保留。没有物理删除或未知退款。Alpha 继续原 PubChem 有限控制器和 COCONUT 实际任务，有限 epoch 不自动续期；不读 active SQLite/journal。

外部证据均位于 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`（即 X 盘）：

- `control/full_logical_owner_plan_v2_actual_frozen_authority_v1.json`、`control/root_actual_full_logical_owner_plan_v2_freeze_review_v1.json`；
- `control/native_precision384_r2_actual_C0_technical_closure_v1.json`、`control/source_revisions/native_precision384_root_reader_syntax_r2_v1/revision_receipt.json`；
- `control/pprime_new20_all12_qa_cpu13_actual_submission_v1.json`、`control/pprime_new20_actual_authorized_execution_stage_v1/`；
- `control/root_full_logical_plan_v2_fresh_storage_review_v1.json`、`control/root_pprime_new20_actual_authorized_fresh_resource_review_v1.json`；
- `control/accounting/` 保存上述实际 Slurm 终态与原始 sacct；大 DATA、全部失败原件和完整引用留在仓库外。

后续仍需完成实际标签全域覆盖/512精确对照、Common/N1/三顺序/全部子视图、D1 联合冻结、D3/D5 真入口及 D4 最终统计、P′ 独立 QA 与正式试点原质量门槛、全 PubChem 去重去污染/准确 NN/RN1000万/10k UFF+D 与首 250 万交付。本轮不运行扩充 QM。
## 本页之后的限定 QA 实际闭合

4524436 已实际 COMPLETED/0:0/154s/16CPU13，分配 2464 核秒（约 0.684444 核时）。1200 dispatch intents、1200 返回 terminal、1200 已校验 closed25M roles，原调用前 attempt flags 与返回标记均为 1200；不是独立 Popen/PID 次数审计。全部声明的 1200 项 own/pair 诊断及 500 项原向量比较完成；错误、未知角色、未派发项均为空，16 worker 自然退出0，没有资源 STOP/强制信号/重试。递归 RSS 实测峰值 16161538048B，最小 MemAvailable 388402327552B，均是观察值而非 Slurm 内存申请。

Root 已独立核对实际用户决定、原提案/冻结20、完整 argv/scope、当前源码及小件字节、实际 Slurm parent/原始会计和有限范围，证据为 `control/root_actual_new20_all12_1200_limited_diagnostic_review_v1.json`。物理语义、SCF 具体因果仍 UNKNOWN，`scientific_PASS=false`、2000/full HOLD、原15FAIL保留；没有自动新QM权限。全部终态 DATA 与原始输出保留在独立 once 域，不改旧生产 once。

Alpha44 的两件已闭合小会计逐字节传回 Main 并验证，见 `control/alpha44_closed_small_accounting_transfer_verified_v1.json`。这不是科学 DATA 转移，也未将历史账本相加。
## 2026-10-28 零点后的源码核验与资源补充

三包均已精确安装，实际 AST/import 全部各包 Python、原源码逆证明及各 3 项边界检查通过：compact v3 为 4524449，D5 输入 builder 为 4524450，S′ 多节点资源层为 4524451；各 C0/31s/16CPU，分别使用 CPU14、15、18。compact 的合成检查实际写出并关闭 Arrow/TypedPart、重新打开并验证 bit/None/index/mask/owner/digest 与逆序字段局部 mask；没有接管旧失败输出。源码包不是科学 DATA 或新节点 32 分子兼容验收。

Main47 已更新为 600 个唯一父任务、570.0133333333333 已观察分配核时，包含本轮 1200 QA，之后上述 3 个父任务另继续计入。实际闭合的 QA 无未来执行 writer，Root 在其 parent/batch/extern 和 observer 全终态后，仅退休 31GiB 的未来执行预算；准备 1GiB、全部已写数据、角色 reservation bound、旧账与 UNKNOWN、全部 182 S′ caps 等保留。新总未来 caps+200GB 为 1867451421696B；这不是物理回收或逻辑退款，见 `control/root_post_new20_closed_future_capacity_review_v2.json`。其中 509786778B 明确是原 Roles.bound（含固定 parent reserve），不冒充独立全物理/charged 字节测量。

首个 Source3 提交曾因 Root 外部 helper 的 scope_key 含大写 AST 被原中央严格命名校验拒绝，发生在 sbatch 前、没有分配；旧准备和拒绝记录保留，仅新 Root helper/spec 改为合法小写键后上述实际 3 个 C0 成立。原中央 guard、三包与科学源均未因此改变。
紧凑标签新投影 **4524453** 已实际 C0/89s/16CPU14（1424核秒），原 Arrow 二进制 mask 写出问题已在真实原数据读写中通过。manifest 报 errors/quality_hold_fields/unpublished_tickets 皆空、resource_soft_stop=false，charged_output_bytes341603100B；下一步仍须独立全4251选中记录×14任务覆盖与原512精确统计对照。没有采用旧失败的10片段/3UNKNOWN，也未凭本投影释放全源数值或最终Common D4。