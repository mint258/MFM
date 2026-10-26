# S′ 全量 CPU v3：有限架构审查与接口提案

2026-10-26，SB-1；仅静态源码与小 JSON 元数据。下述 v3 尚未实现、测试、登记或提交，不构成全量授权、试点质量通过或 common 冻结。Root 所述 Main 4521321 C0/69s 为闭合父作业；本审查没有查询 Slurm。原 4520364 与恢复 4521110 都是 TIMEOUT，不能把 14 个完整控制包称为 14 个 Slurm C0。

## 1. 指南是否阻止继续规划

权威为项目根《数据线工作流程：v1 定稿与数据扩充（Codex B）.md》：

- :48–53 要求真实小试点、记录耗时/成功率、科学配方不变及单作业 ≤48h；没有规定 S′ 试点必须有 336 个包、父 COMPLETED/0:0 或数值成功率门槛。
- :119 要求超过 500 核时的计算由 Root 确认试点后提交；不允许子 agent 凭本提案直接放行。
- :132–139 要求同 UFF/0.5Å，10N/≤300、技术/partial 一次 retry、严格图/立体检查、unsupported 不换力场且排除。
- :141–146 定义完整 PM7 与充足 S′ 的共同人群及组成/分布报告。
- :336 的最终共同人群总排除 >2% 或单元素 >20% 仍必须停报；只有已授权 Se 例外。:344 的“试点达标后”没有给 S′ 另一个可据此伪称达标的数字。
- :338 的 99.5% 是 P′ 2000 试点门槛，不能套成 S′ 336 的门槛，也不能因本提案放行 P′。

结论：可为“真实包 + 诚实执行未决、耗时右删失”的证据编写新的有限规划器；旧的全 336 包/父 C0 不是指南的 S′ 硬条件。但接受这份证据用于规划，需要新的 Root 明确意见；当前 closure 自身仍是 pilot_accepted_for_planning=false、formal_generation_authorized=false。高科学失败比例与未知全量耗时必须披露，不能把“可规划”写成“科学达标”。

资源新权威 user_cpu_auto_memory_20261026_v1.json 已覆盖旧 64GiB/85%/14–19：Main conformer 11–19、analysis 2/8–19、16CPU、cpu 分区、无 memory/exclusive/GPU 申请、无 requeue、≤48h、真实 RSS/MemAvailable 与自然 drain、200GB 配额余量。成本新权威 user_allocation_overrun_report_continue_20261026_v1.json 覆盖 1.5 倍停止：保留实际超标证据，报告后继续；不覆盖科学质量。

## 2. 实际闭合证据与导入边界

joint_timeout_audit_report.json 的 schema=SPRIME336_PACKAGE_OR_TIMEOUT_OUTCOME_AUDIT_V2，status=CLOSED_WITH_TWO_EXECUTION_UNRESOLVED_REQUIRES_ROOT_REVIEW：334 原始包、14 同 seed 精确复现控制、929 个原始包几何 float64 SHA 回读通过；2 个原任务无包、scientific_status 未赋值，不能称化学失败。未可靠保存两任务各自的 worker/PID/阶段/耗时；两父 elapsed 不能分摊成任一分子的耗时。

334 包的状态为 SUCCESS 102、EMBED_FAILED 41、INSUFFICIENT_CONVERGED_CANDIDATES 42、PM7_STEREO_UNRESOLVED 25、SOURCE_CONFORMER_GRAPH_OR_ATOM_ORDER_MISMATCH 33、SOURCE_SMILES_ATOM_MAPPING_FAILED 41、SOURCE_SMILES_GRAPH_MISMATCH 50。即 232 个有观测的科学失败包，不是 334 个成功。

从 terminal_outcomes336 的小元数据分组直接读得：retry_once=246 包+2 未决，fill_10N=72 包，enough_control=16 包。正式缺口消费导入应为 **320 项（318 包+2 未决）**；16 个原 enough_control 不进入缺口 once 任务，额外 14 个同 seed 控制也不新增人口/尝试。当前名义 90,069 非 unsupported 缺口减去 320 得 89,749 待首次派发；这只是待 CPU 对原缺口/角色表逐项 join 核对的预期，不能跳过实际全集守恒。原 320/16 配额亦见 configs/data_v1/conformers/pilot_v1.json。

closed_package_only_statistics.json 的 scope 是 334 原包描述统计、其有效比较子集 molecules=118；不是 336 完整成功率、全量总体分布或可靠耗时预测。分层偏采的失败试点不能直接外推全体排除率。

## 3. 旧源码中真正受影响的位置（原字节不动）

| 现有位置（相对 repository） | v3 必须替换的假设 |
| --- | --- |
| conformers/formal_v1/full_common.py:28–41,137–146；父 common.py:113–145 | 旧配置/节点/64GiB/85%/旧 preflight/runtime 不能继续被 v3 调用。IO 与科学纯函数可 pin 后复用，不能复用其资源守卫。 |
| formal_v1/full_common.py:106–121；:87–88 | review 要求 336 完整 receipt 且指定父 C0；不能消费现有 timeout closure。实际 accounting 仍需原始 sacct 对照与去重，科学接纳应与父终态分开。 |
| formal_v1/plan_batches.py:49–65,76–119 | 要求 336 gzip；只导入有包任务；用完结样本最长耗时作外推并写 memory_gib=64。会遗漏两项已消费未决任务。 |
| formal_v1/plan_batches.py:125–155,159–188 | 旧 import schema 必有 source 包；旧预算必须有有限 forecast；continuation 仅旧 C0 receipt，无法恢复 TIMEOUT 后确实未开始的任务。 |
| formal_v1/materialize_batch.py:14–20,30–32,54–64 | 资源/plan schema 要新适配；保留一次账本拒绝、原指针数与旧严格可用数相等、来源身份校验。 |
| formal_v1/run_batch.py:24–29,56–79 | 结果返回父进程后才持久化；父 TIMEOUT 时可能没有最终 receipt。需先落 durable 任务/包证据，再确认完成；保持原 process_task 科学函数。 |
| formal_v1/run_batch.py:59–62,89–105 | 1.5 倍触发停止应改观测/报告；明确墙钟/内存/空间停止派发与自然 drain，不重算已启动任务。 |
| formal_v2/finalize_common_v2.py:22,130–145,154–202 | 继承旧 config/runtime、C0/无 unknown/1.5 与旧 forecast-budget 契约；必须新接口。 |
| formal_v2/finalize_common_v2.py:203–223,281–300 | 用 set(packages)==全部缺口要求每项有包；v3 应是 packages 与 execution_unresolved 互斥并集等于全部缺口。 |
| formal_v2/finalize_common_v2.py:84–110,224–275,284–310；identity_v2.py | 保留旧物理 ID/int64/gaps、失败 ID 空间、旧坐标/锚/seed 守恒、append 规则、原母数和 2%/20%/Se 闸门；只为新 import schema 增适配，不退回 v1 dense 物理 ID。 |

上表 conformers 前缀为 workflows/data_v1_final/conformers/。旧 test_formal.py 的 once/阈值用例及 test_identity_v2.py 的物理身份用例有复用价值；64GiB、旧 C0/全包、1.5 阻断的断言不代表新政策。

## 4. 最小新 namespace 与阶段接口

建议仅新增 workflows/data_v1_final/conformers/formal_cpu_auto_v3/ 的 contract.py、plan.py、prepare_batch.py、run_batch.py、finalize.py 和 README，以及 configs/data_v1/conformers/formal_cpu_auto_v3.json。close-batch 可作为 finalize.py 子命令。不复制任何 queue；统一调用已登记 execution/cpu_auto_memory_queue_v2.runtime.require_startup，精确 expected_scope_key/parameters/full argv/actual primary/source/required refs。planning/import/prepare/closure/finalize 使用 kind=analysis，只有 science run 使用 kind=conformer；pilot=false。

建议新 schema/交接：

1. **Root evidence review** SPRIME_CENSORED_PILOT_ROOT_REVIEW_V3：status=ACCEPTED_FOR_BOUNDED_PLANNING，绑定 closure+terminal336+package references+两 timeout 原始会计+closure C0 实际会计+原 task/recipe/source/roles+新资源及费用权威三元组；accept_scientific_failure_disclosure=true、accept_execution_unknown_as_consumed=true、full_forecast_status=RIGHT_CENSORED_NO_VALIDATED_FULL_FORECAST、formal_generation_authorized=false。不改原 report/receipt。
2. **CPU draft/import** SPRIME_FORMAL_CPU_DRAFT_V3：重新 SHA/来源/缺口 join，写 original_deficits、unsupported、pilot_consumed_imports、unstarted shards；记录 expected 99,351/9,282/90,069，实际核对 320/16/14，三类互斥守恒。estimated_full_core_hours=null；已完结样本耗时只描述，下界/敏感性须明确不是可靠 forecast。
3. **Root freeze review** SPRIME_FORMAL_CPU_ROOT_REVIEW_V3：pin 具体 draft、资源/费用权威和本 wave 全 job 清单/CPU/wall/output；对 >500 核时或无法可靠估计但允许的配置分配上限可能 >500，显式 approved_over_500_core_hours=true。每 job 整分钟 wall≤172800。配置的 ΣCPU×wall 是有限的请求上限口径，不是 full runtime forecast 或严格实际核时保证；调度收尾/超时清理费用仍按实际计。冻 plan 只授权所列有限 wave，不授权未知后续任务。
4. **once import / batch prepare**：沿用旧 task_key 算法与唯一 canonical ledger root；318 缺口包与 2 未决写独占、可逐字段等值重读的历史 import 记录，保持原 task SHA/cohort/seed/recipe/证据 parent IDs。未决 package_reference=null、science_result_observed=false、scientific_status=null、execution_resolution=UNRESOLVED_AFTER_PARENT_TIMEOUT；不伪造 formal_start/PID/新 seed。若已有键且语义不同即拒绝，不删除旧 claim。冻结与 import 未全部结束前禁止任何科学派发。
5. **science batch** SPRIME_FORMAL_CPU_BATCH_V3：只消费已冻结未启集合；16 workers、每 worker 单科学线程、最多16 active，不堆未启 future。任务真实开始前独占 claim+fsync，记录 job/UID/boot/PID/startticks/完整任务 pin；完整包必须原子落盘+fsync 才汇总完成，避免把仅内存 future 当 durable evidence。并发写前空间核算要串行/有锁，包含临时文件、所有失败包/1%审计与收尾。仅墙钟/真实内存/空间/实现错误停止新派发并自然 drain；1.5 超标只记录报告。
6. **CPU close/finalize** SPRIME_FORMAL_CPU_COMPLETION_INDEX_V3：每真实父 terminal account/raw/source/claim/package 的明确归属；有效包独立严格验收，不因父 TIMEOUT 丢弃已验包。不见包且已有 consumed claim 为 EXECUTION_UNRESOLVED（科学状态 UNKNOWN）；无 claim、无提交证据且确实未启的任务才能进入新 continuation。冲突/无法证明的提交状态保守按 consumed unknown，绝不自动重投。

保持 science.py、selection.py、原 sprime_v6/prepare 及配方相关原科学依赖的准确 SHA 与原语义；seed_for 仍按原 molecule/cohort，10N/300/0.5Å/UFF tol/graph/stereo/atom order 不变。不得为控制或 TIMEOUT 重调种子、tol、候选数，也不调用 QM。元数据 authority/脚本 pin 在登录侧；大源 SHA、gzip/Parquet/LMDB 读取只能在真实 CPU allocation。

## 5. 最终共同人群与不能越过的风险

最终 CPU 必须证明全部 90,069 非 unsupported 原缺口各有一次已消费终态，且 valid packages 与 execution-unresolved 清单互斥、无缺项/额外项。包的科学失败类别与执行未知独立保存；UNKNOWN 不造空包，不捏造化学失败阶段。旧严格可用几何保留；未知补齐不得增加 merged count，仍不足原 N 则 common=false，附 EXECUTION_UNRESOLVED 与 INSUFFICIENT_ACCEPTED_SPRIME 原因。

原 TRAIN+ROUTINE 整分子 VAL 母数 1,214,218 不变，其他 FULL 保留审计但不进该分母。unsupported、科学失败导致不足、执行未知导致不足、PM7 不完整均留在对应排除分母中；总率严格 >2%、任一非 Se 元素严格 >20% 时写证据并停，不发布 frozen manifest。不能先移除 unknown/失败再缩分母。所有原始终态类别、元素/大小/骨架分布变化仍报告。

主要风险有三项：232 科学失败包提示最终质量闸门可能失败，现有偏采试点不能排除此风险；右删失没有可靠有限 full forecast，有限 wave 也不能保证在48h内完成任何特定长尾分子；旧父进程集中持久化存在超时丢回执风险，v3 需 durable 子任务/包及真实终态闭合，不能用“父 C0”替代逐项证据。新全量未产出前，D1/D3/D5、common/order/P′ 仍未因此完成。

## 6. 本审查实际读取的关键小权威

路径缩写 RUN=X:/runs/data_v1_20261025；REPO=RUN/repository。以下为静态读取时字节 SHA，不是未来生产结果。

| 路径 | bytes | SHA256 |
| --- | ---: | --- |
| X:/数据线工作流程：v1 定稿与数据扩充（Codex B）.md | 23196 | 1905868ca4f9b9515f7bdfc3c05de48cf2be7692fa4ed9e9300b324e8996b05b |
| RUN/artifacts/conformers/recovery_timeout_closure_v2/v1/joint_timeout_audit_report.json | 35297 | b61a9562c85fe46922ae1d6d9c77454bb1e4766979575ca82251617de4f383a4 |
| 同目录 closed_package_only_statistics.json | 2845 | 990cb724be541d68f732f9459e2767d99e41be3324f64214181d1b9197a5dc6d |
| 同目录 terminal_outcomes336.json | 351339 | 1f683ea1172ea91c9f36153e9bd2f66f4dfb342cc62f7373ea87dff482116741 |
| REPO/configs/data_v1/user_cpu_auto_memory_20261026_v1.json | 3196 | 25c1b2f301ce2b07aa8eb57db9b406e003bf97f76aa5d50e2186b75317713fdc |
| REPO/configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json | 1331 | aa333f4eb26f69abae9600d11be47384919d8031af99dadf0e843feb1f25a7fd |

另只读同 closure 目录的小 unresolved_after_timeout2.json / stratified_descriptive_and_censored_bounds.json 与上列源码。未打开复现 gzip、Parquet、LMDB、科学母表；没有执行 Python/tests/AST/SSH/Slurm/Git，没有改 Root 或任何已登记源码。
