2026-10-29 最新模型实现已公开af11eaae：C4 v3 PASS；完整137模块3235PASS/3原skip；首seed20设计+20接线模板静态通过，50有效更新实现通过合成/UNIT。实际4090 A采用5173 C0，BackboneOff及原输入一致；C1-a checkpointOff的4090已测，3090/5090待资源。真实D2–D6仍待，D3后24h真实阶段3/三卡2000、D5后阶段5科学顺序按用户v3执行。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 用户主线修订v3：C4已凭实际4524734 FP64 48/48判PASS，FP32仅非阻塞诊断，旧v1/v2不重跑。立即推进A采用/按显存checkpoint、三GPU同批C1-a全关checkpoint各测一次、首seed20配置及真实D3后50更新接线；D3到达24h内阶段3真实验收和三卡SDP2000，D5到达启动阶段5。D2–D6实际仍待，日志/SDK/同步/fixture/SHA不再阻塞科学主线；r674保留head但LOSS_DISABLED。详[本日唯一汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 v5已真实公开并通过同父16项资源元数据检查与仓库检查；Root已实际启动，等明确占用任务5142真实终态后只首次显式续新32/u9000→10000。31原失败保留，未新增模型有效更新；完整B与D2–D6仍待。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 最新：Native031/4525157在模型启动前被原GPU占用门拒绝，FAILED保留、无新增有效更新；有效bf16seed0仍9k。v4已停止。已冻结v5，仅等待明确占用任务5142真实终态，之后Root首次显式从030有效CP续接新32，任何新失败仍停止；公开/元数据验收后才启动。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 Native原S/FP32seed0=20k、bf16seed0=9k，最新030段完整SDK/官方同步/云回读已闭合，020–029原证据保留；新v4协调器已实际启动，等待原5090 UUID空闲后续接10k。完整B四曲线与D2–D6真实数据仍未完成。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 阶段2耗时已超过早期预估；原因是用户修订梯度门后的全量重验、原失败保留与CPU/GPU资源排队。当前科学门不变，原3090与Native原5090都在等待资源。真实D2–D6仍独立待交，详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 最新模型状态：当前生产源已通过完整135模块，3186PASS/3原CUDA skip；当前A-v2全20批+500更新复核8/9。七组ABBA共28真实run的完整原生SDK、官方选择同步和云端元数据回读已闭合，详[阶段2当前报告](../model_v3/02_speedup_AB.md)与[当日汇总](../model_v3/DAILY_20261029.md)。D1同版本policy/config已双方签署冻结；D2–D6真实数据/归一化/子集/fullrelease仍未交付验收。Native原四20k计划继续：fp32seed0=20k、bf16seed0=9k，原5090被其他用户占用，10k段等待，seed1两支未启动；B/最终recipe及整份Stage0–7尚未完成。下方pending/draft与旧计数按日期保留为历史。

2026-10-29 canonical模型生产源已通过后验133模块：3122PASS/3原CUDA skip；新物理消费门保持原值/mask/合法scale，跳过无用head。Native4904已实际自动内存续接，最大原生712输入4906 C0。Model最终policy/config ACK待该canonical源实际公开后签署，D3–D6/真实release仍待，详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 开发GPU自动内存已明确获批，原预算/RSS/85%和科学门保持；Native026安全停界待新源采用。132完整回归及两组R1/SDK已闭合，物理政策133回归与实际D1 joint/D3–D6继续；见[唯一当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 用户D1五项全部A已确认：[政策与边界](MODEL_LINE_D1_ALL_A_20261029.md)。[当日模型汇总](../model_v3/DAILY_20261029.md)：A-v2完整复核3/9及三组原生日志同步已闭合；原完整Stage0–7继续。joint ACK、真实D3/D4/D5/D6与最终冻结未完成，四极标签独立物理政策正在对齐。

2026-10-29 最新模型优先事项：[每日汇总](../model_v3/DAILY_20261029.md)。等变性采用v2；全部FP32补偿不采用且停止；C1-a工程性能在已有S直接测，不等待D-5。旧段中的原1e-5门槛和继续诊断不再是当前任务。

## 2026-10-26 Native S 长程准入实测闭合


2026-10-29 后续：[A00-v2/Native/FP32与数据依赖](../model_v3/STATUS_20261029_A00_V2_CP19000_SCALAR_REVIEW.md)。D1仍候选，真实D3–D6模型侧验收待办；来源角色FROZEN不替代Common人口或归一化授权。


2026-10-29 更新：[CPU 自动内存、A5-v2、残差 FP32 与 Native 续接阶段报告](../model_v3/STATUS_20261029_CPU_AUTO_A5_V2_FP32_NATIVE.md)。四套完整 CPU 回归通过；A5 和残差 FP32 仍未通过科学门。旧 A 类 PASS 按新规则逐项复核，D1 joint 与模型侧真实 D3–D6 验收继续待办。


CPU4521405实际C0/595秒完成全部9阶段：29项SDK元数据测试及4项checkpoint测试全PASS/0skip；两原短测SDK完整读回，两个safe checkpoint的保守未来上界约392.094MB，均小于384MiB cap；512roots/32768JSON/512MiB压力真实三组×八pass完成。Root据真实同一CPU父与两GPU原sup/raw sacct组装证据，原NativeV2完整准入已PASS；新长程phase仍未预留或训练。精确ops源码和有限工程配置见[方法与执行补充](../model_v3/reports/native_s_execution_20261026_v1/EXECUTION_UPDATE.md)，不是最终recipe/B*。

完整CPU归因4521404实际384次forward及全部观察器重放控制闭合，原等变性case仍0/48通过。GPU4521406的固定输入op显示原policy下10/11自然变化；独立strict诊断11/11稳定，但不能当生产物理门槛通过。原1e-5不改，数值候选在单独隔离分支实现。数据最终接口、架构/配方实验、用户确认后的冻结与最终交接继续待完成。
## 2026-10-26 启动有效期与实际重放诊断更新

四项CPU作业1334–1337在排队4小时有效期后才获分配，实际0–1秒FAILED，日志均为 `Queue lease expired before original work`，无worker admission、未执行原测试。原publisher按有限租期退出，未取消或改写这些作业。现场CPU13出现16空核后，Root复用原单任务提交器与资源核验直接重交：QA55实际4521398 C0/5s、55PASS/0skip，ABBA QA76实际4521399 C0/6s、76PASS/0skip；源码前后相同。SDK/检查点/全规模元数据压力验收仍未完成。

C4首例4521397实际FAILED1/9s，但三轮unhooked1→unhooked2→hooked及全部12次encoder前向已完成、JSON和52成员数组均持久保存，随后严格新重放控制判定不相等。旧1333档案及新三轮的数组数值比较也已保存。它仅为REPLAY_DIAGNOSTIC_ONLY，不是full48或科学验收；不改1e-5阈值或生产模型。W&B只读API再次确认账号mint_leaf/default entity mint_leaf258；线上同步未完成。

最新独立时间点账本为378个本模型父任务、772912 allocated CPU秒、29986 GPU作业秒；捕获时4521338仍PENDING，包含失败及启动成本，不能当最终成本或GPU利用率。见[实际会计](../model_v3/results/job_ledger_model_v3_active_v13.json)、[QA55实际核证](../model_v3/results/native_S_QA55_actual1398_v1.json)、[C4实际终态](../model_v3/results/C4_firstcase_GPU_1397_actual_closure_v1.json)。长程4×20k启动包仅完成静态审查，readiness与实际长曲线仍待完成。整份指南尚未完成。
## 2026-10-26 Native S 实测与完整回归补充

本条是当前进度快照，下面各段保留其原时间点事实。整份指南尚未完成。

- Root 3d9b1cc0c580dacc9398a5570b0c2fff3e257618 完整整合回归已由八个实际CPU父闭合：2592 collected、2589 PASS、3 skip、0 failure/error、112文件；旧失败没有改写。Native storage修订82项另由4521200实际C0闭合。
- 现有原生S短测已实际完成：FP32 4521331 C0/252s、bf16 4521332 C0/90s，均20更新、7680原始记录（23040视图图）；固定验证另外1024记录（3072视图图）。输入消费链相同。两个安全检查点及持久化离线SDK已生成，完整SDK独立读回和未来状态上界仍待CPU验收。冷启动VAL计时不同，不能当作稳定十倍精度提速。
- 现有S的四条20k更新精度曲线不依赖D5；科学计划和数值规则保持3d9/ce7，真实曲线尚未运行。它们不能替代D5代理架构/配方实验、两个预训练种子噪声或新标签验收。四成员将从各自seed的u0开始，短测u20检查点不作为科学曲线前缀。
- 4521328/4521329原生S启动失败、4521330/4521333 C4诊断失败均保留；C4组合等变性尚未通过。原严格1e-5阈值和未完成的诊断状态不变。A01独立ABBA测量4521338已提交，仍等待节点20分配，不记作测试或性能已通过。
- 原四项CPU验证在60分钟启动有效期内始终PENDING；Root仅按PENDING/UID/源精确条件取消，实际sacct确认未启动，旧回执/成本/账本保留。新1334–1337使用明确的4小时排队有效期、仍16CPU及原内层资源和源码，待实际执行。没有修改其他或数据线作业。
- W&B认证已确认entity mint_leaf258；这不等于任何历史SDK已在线同步。历史57份离线记录的完整性分类、选择性同步及两新profile的独立核验继续进行。
- 数据线最新STATUS仍为D1 draft.3未共同冻结、D1–D7最终交付未完成；继续现有S和合成工作，不生成最终recipe/B*、tag或HANDOFF。

# Model/data interface status

2026-10-26最新：整份模型指南仍未完成。A采样桥接+B候选wire/provider已完成独立与整合回归；最新Root3789c19865f70f80191986675cb13b606ebd210b为2473PASS/2CUDA skip、104文件，实际4项A→B→原trainer贯通全PASS。新独立C4组合检查则为48FAIL/9控制PASS，误差归因继续，不将原单独测试当组合接受。见[候选接口与完整限制](../model_v3/03_candidate_interfaces_20261026.md)及[289条原时间点审计](../model_v3/COMPLETION_AUDIT_20261026_v1.md)。D1draft.3可读而未最终冻结，最终D3–D7未交；没有最终recipe/B*、main更新、tag或正式预训练授权。


All dates use Asia/Shanghai. Model-line checkout:
`/share/home/zixiao/descriptor_analysis/MFM_model_v3`, branch `model-v3`.
This file records observations in this checkout; it does not declare external
data-line work absent or override another checkout's delivery state.

| Date | Item | Status | Path / evidence |
| --- | --- | --- | --- |
| 2026-10-25 | Model stage 0 | ACCEPTED: actual audit 4520329 and existing 2,016 tests 4520330 passed; 6x512+A4 total 22,352,859, backbone 12,709,424 | Report published on model-v3 at `3441b280bc34431bf8e7596465af28be073644b6`; `docs/model_v3/00_baseline_review.md` |
| 2026-10-25 | Model decision rules | Initial rules published with stage 0; user SoM coverage decision and bounded panel details recorded before scientific comparisons | `docs/model_v3/DECISION_RULES.md`; publication/execution mapping in `docs/model_v3/EXECUTION.md` |
| 2026-10-25 | D-1 | USER_CONFIRMED_NOT_DELIVERED; real integration awaits data-line contract | Expected `docs/interfaces/training_format_v3.md` |
| 2026-10-25 | D-2 | USER_CONFIRMED_NOT_DELIVERED: registry v3 with levels, families, groups, pooling, vector storage and physical masks | Data-line delivery path pending |
| 2026-10-25 | D-3 | USER_CONFIRMED_NOT_DELIVERED: pilot training export | Data-line delivery path pending |
| 2026-10-25 | D-4 | USER_CONFIRMED_NOT_DELIVERED: TRAIN normalization and elemental references | Data-line delivery path pending |
| 2026-10-25 | D-5 | USER_CONFIRMED_NOT_DELIVERED: nested molecule subsets and held-out-conformation validation | Data-line delivery path pending |
| 2026-10-25 | D-6 | USER_CONFIRMED_NOT_DELIVERED: full v1 export and node-local copies | Data-line delivery path pending |
| 2026-10-25 | D-7 | NOT_OBSERVED: descriptive conformation report | Data-line delivery path pending |
| 2026-10-25 | Model stages 1-2 | Original native jobs352/353/354 completed 20 updates each but failed profiler RSS/output budgets. Bounded representative capture tested9/9 in362, committed dc22d3f before retries365/366/367. A tools26/26 passed360; A/B scientific acceptance pending, B proxy awaits D-5 | `docs/model_v3/EXECUTION.md`; profiler-v2 and A tools use separate worktrees |
| 2026-10-25 | Model stage 1 | ACCEPTED: native365/366/367, nine-trace analysis369 and report378 all COMPLETED/0:0. Root reviewed numerical denominators and all three PNGs. Distance MLP dominates sampled GPU time; causal peak-memory dominance remains unproven | `docs/model_v3/01_profiling_baseline.md`; `docs/model_v3/results/baseline_*` |
| 2026-10-25 | Model stage 4 existing TRAIN | Metadata-only preparation379 COMPLETED/0:0; zero target records decoded. Selected-member semantic access audited; real materialization385 submitted under the frozen request. No D-1-D-6 substitute or new label generation | SA-3 `SELECTED_TRAIN_STORE.md`, `TRAIN_TARGET_ACCESS_AUDIT.md`; external request raw SHA ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1 |
| 2026-10-25 | Model stage 3 | Code integrated; post-merge 4520355: 2,067 passed / 1 CUDA skip. Ten trainer integration tests passed; nine synthetic head cases exceed R²0.95, repeated with isolated W&B 351. Real D-3 acceptance pending | `docs/model_v3/03_labels_losses.md`; merge `76bceb59d5372515fb10f8916b89ec2bb42fd4ed`; 336/338/342 history retained |
| 2026-10-25 | Model stage 4 | SoM binary coverage user-approved. SA-3 full363: 2,076 passed. Actual B3 safe load/SHA and target-free H0 candidate/random[5,384] passed360. Locating existing COMPLETE downstream store for TRAIN-only projection; this does not depend on new D-1–D-6 | `MFM_model_v3_sa3/configs/dev_panel_v1.json`; snapshot `464b96eff38a7b73b2dab5b7fd68bfd7b1146e58`; original358 spawn timeout retained |

The user explicitly confirmed on 2026-10-25 that D-1 through D-6 are not yet
delivered and instructed the model line to continue S and synthetic work.
The model line proceeds with existing S inputs and clearly marked synthetic
fixtures while these interfaces are pending. Existing WP5 family Parquet and
the historical target-fidelity registry are not replacements for D-1/D-2.

Stage gates: 0 baseline report; 1 profiler evidence on three GPU types; 2
numeric/trajectory and bf16 evidence; 3 real-data head/loss acceptance; 4
TRAIN-only evaluator and integration; 5 architecture decisions; 6 recipe/B-star
plus user confirmation; 7 freeze/tag/real smoke/PR. No stage is accepted by
preparing its implementation alone. No formal pretraining is authorized here.

Latest model-line observations: source public at
`61658a4c1f472de035601dbedc17809315774784`; post-merge406 passed 2,196 tests
with one CUDA skip. Native A00 controls405/410/411 passed their actual
20-batch gates; paired500 trajectories remain pending. Architecture branch412
and post-merge415 passed complete regression; scientific decisions await data/evidence.
Existing downstream metadata was resealed in413 with zero target decoding and
exactly the379 members/groups/roles/contracts. Real store421 completed17,602
selected TRAIN records with exact cohort replay and zero outer-target decoding,
after all2,096 SA-3 tests passed420. Full panel execution remains pending.
No new D-1–D-6 delivery is inferred from this model-owned existing-data projection.

2026-10-25 update: actual B3 nine-task/two-readout evaluation437 completed
18 cells, Slurm C0/543s, inclusive guard wall541.230s. It is a historical384
sanity check; independent native SDK verification/archive is pending. Do not
use its result for v3 architecture selection or claim512 timing acceptance.
C2 user-confirmed local-geometry bins to3D denoising vectors; branch441 passed
2,187 tests/one CUDA skip. Root392 passed2,255/one skip in443. Integration
and public preregistration remain required before real C2 fitting. CPU node20
is fully occupied by another user's104-CPU job; a temporary21/22 CPU exception
has been requested under the user's AGENTS rule, not assumed. Existing jobs
and the data line are untouched. D-1 throughD-6 remain user-confirmed pending.

Subsequent user instruction resolves CPU placement: submit CPU work to
available CPU nodes; GPU nodes are reserved for model training/fine-tuning
and other GPU jobs. Therefore the proposed21/22 CPU exception is not used.
Current site CPU partition is compute-0-2 and8–19; Root checks live allocations,
all-user requested memory and actual available memory before each admission.
C2 method is now publicly preregistered at1a8c124571ddf37f87ae06ef9971efa85e417f95,
with tree exactly equal to local dd6cbaf. Integration regression precedes fitting.

Latest verified integrations: export478–481 PASS2,285/one skip; precision498–501
PASS2,294/one skip; plan506–509 PASS2,306/one skip. All are complete disjoint
CPU regression partitions with actual C0 closures. Decision39 unit cases and
premerge502–505 PASS2,319/one skip precede a separate postmerge regression.
B3 independent487 SDK verification is complete (170,299 native records /
56,738 history, exact metrics/clean EOF/exit0); historical384 limitations remain.
A06 fused457 failed the original500-step trajectory gate; it is not adopted.
Fresh A00 export486 completed C0 and awaits explicit outer-terminal admission
before the primary512 panel. C2 fit482 failed during TRAIN solving, before any
validation geometry read; v1 remains failed pending a separately registered
TRAIN-only solver diagnosis. D-1–D-6 remain pending, with no delivery inferred.

Current toolchain evidence: primary512 run544 completed C0/512s, full9 tasks /
18 readout cells /1000 molecular-bootstrap draws, matched random512, cold cache.
Actual guard including cleanup509.330s and1.609GB output satisfy this run's1h/
2GiB budgets. Independent566 verified170,295 native SDK records /56,738 history,
every scalar and global step, clean EOF/exit0. It is an A00 short500 checkpoint,
not sufficiently trained-model or architecture acceptance; single-seed SD is
unavailable. Full reports/typed run CSV preserve all cells and negative results.
Root postmerge533–536 passed2,368/one CUDA skip. Stage4 overall still awaits
D-3 all-label SDP2000-update smoke on all three GPU types. C2 diagnostic559
is TRAIN-only and preregistered publiclycd0c434, original482 staysFAILED.
Archive562 completed with41 unique offline runs, including failed evidence and
independently verified synthetic resume513/514; no online sync is claimed.

2026-10-25 latest model-line evidence: C2 corrected artifact loader40 tests599 C0;
real TRAIN-only artifact preflight602 C0/6s (no native reader imported). New method
published as0f26274 with exact local916697e tree87d533a before first VAL. Actual
603 CPU8/16CPU/32GiB C0/127s evaluated all1024 existing-S PRETRAIN_VAL records
(55,650 atoms), current TRAIN geometry reads0, no new fitting. Independent606
C0/4s verifies31 SDK packets/two history steps/all public config+summary/clean EOF
exit0; report-source44 tests601 C0/67s. Component RMSE0.0654994134 Angstrom,
vector RMSE0.113448312, local-pair RMSE0.0575438344; analysis only, no model choice.
Report/PNG/source pins: docs/model_v3/05_C2_coordinate_baseline.md. Failed482/595
remain failed; no inferred original stop. A TF32 numeric failure589 and GPU-cap
abort590 archived by605 C0/1s after40 tests604 C0/3s, offline index55/no online sync.
D-1 throughD-6 remain user-confirmed not delivered. No final model/recipe freeze,
no main update or school-server job; overall guide acceptance remains pending.

2026-10-25 new observation: D-1 draft.3 and draft registry are now readable in
runs/data_v1_20261025/repository. Model review covers31 SHA-bound source files
and264 registry metadata rows, no scientific data or tests run for this review.
Opinions were appended under the actual contract's model-line section, preserving
its entire original15581-byte prefix; before/afterSHA receipt is published with
docs/model_v3/03_D1_draft3_review.md. Data wire tensor6/source-specific D5/sparse
reasons andr82 scatter already exist; remaining model consumption and scientific
contracts are distinguished explicitly. No v3.0 signature or D3–D6 final delivery
is inferred. An independent old-native S bond transport gap is being repaired
in isolated model-v3-s-bond-transport; no new wire codebook/physical-label decision.

2026-10-25 S native bond loader fix VERIFIED: optional typed old rdkit_bond facts retained through decoded collation. Targeted64349PASS/2CUDA skips; complete pre648–651/post656–659 each2388PASS/2skips,102 files. Actual production code 91f0c40a78478447a14ef2e8e91f05c07e0f5019. No new wire codebook/physical semantics or D3 acceptance. Report docs/model_v3/03_s_bond_transport.md.

## 2026-10-27 模型线实际更新

固定50条完整W&B日志已全部真实同步/读回核验（37finished/13failed），7条不完整原件保留未上传；统一训练记录入口已追加在线核验链接。新增S profiles和长段另行核验，活动日志不上传。数值候选完整CPU回归4521421实际2636PASS/3既有skip/0FAIL、113文件；原48项GPU矩阵4521435为10PASS38FAIL，候选不采用。S首长段4521411因quota freshness失败，无safeCP；原ledger失败计数只复用不重写。独立v4修正保留原校验并存拒绝feed、在原host封存；同science重试4521438已实际运行，8项启动metadata通过但父尚未终态。411父点时成本包含所有失败，非最终成本。D-1仍draft.3，D-3～D-6正式交付和全部指南验收仍未完成，无main/最终freeze/tag/PR。

证据、预注册、完整负结果和方法源：[训练前整理实际更新](../model_v3/reports/training_preparation_20261027_v1/PROGRESS.md)。

2026-10-27 模型最新实际：S安全累计2000更新/818176base，1459及独立完整SDK审计1487实际C0，下一段1485续跑。55份完整W&B已同步、回读和Root闭合，旧7份不完整保留。固定H0捕获1492实际C0/48组合192forward，但物理仍10PASS38FAIL；CPU影子v3仅预注册未执行。费用范围修正及全部限制见docs/model_v3/reports/training_preparation_20261027_v2/PROGRESS.md。最终D3–D6仍待交付，完整指南/模型/配方尚未完成冻结。

2026-10-27 后续：CPU1503实际C0/13秒，48/432精度分解与212来源独立闭合；FP64头仍31/48组合超限，原C4仍10PASS38FAIL。新encoder参考已267source/AST/bash静态及独立review完成，仅预注册待GPU。S1505实际C0至安全4000/1629317base，SDK待核；下一1548续4000→5000。56完整日志已在线Root闭合，原7不完整保留；显式7项集中CSV/曲线归档准备中。详见docs/model_v3/reports/fixed_h0_shadow_20261027_v1/PROGRESS.md，未完成整体指南或冻结。

2026-10-27 encoder参考1561实际C0/131秒，全192原H0位等、192F64与268来源独立闭合，三PD F64全部0/432超1e-5；原FP32仍10PASS38FAIL，尚未采用。AV局部数值诊断已静态复核并预注册待执行。S安全5000/2034688base、1616续6000；1635正常队列等待CPU核验4k/5k日志。56完整在线，显式7项本地归档准备中。完整限制及报告见docs/model_v3/reports/encoder_precision_reference_20261027_v1/PROGRESS.md；整指南未完成/未冻结。


## 2026-10-27 AV局部诊断与S长段归档更新

执行前公开版本99788277501ceff4a8adf37f7d9ee01498b9dbf1对应的AV诊断4521641实际C0/75秒：192次原H0逐位门、1152项原AV重放全部通过。中心化对Rnorm的聚合RMS约改善11.3%，第0层192/192局部项RMS变差，Rraw参照下总体也更差；不选层采用，未得到新的物理通过。统一六层FP32候选已SOURCE+CPU冻结，并在独立[实验分支](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)公开f8417157dc23326d1beca8e19e4725755d9f13c6（本地cf8ce66d97cd518ebf279b40ee20294919bb95e1）。完整CPU父1707实际C0/132秒，2712采集=2709PASS/3既有SKIP，73新测试及47原numeric全部PASS/0skip；[正式GPU协议](../model_v3/C4_centered_attention_e2e_prereg_20261027_v1.md)及运行器已执行前公开63ae209b27acabaadafa15cf4ebd8f64f8a98e06；GPU4521776实际FAILED1/42秒，48项21PASS/27FAIL、0error/skip，C4仍HOLD/noadoption，1e-5/rtol0未改。tiny CUDA及48个domain控制通过，来源前后相同，记录71/1872项字段观察超门；Root元数据已闭合、NPZ仅stat，[证明](../model_v3/reports/attention_centered_e2e_20261027_v1/ROOT_METADATA_CLOSURE.json)及原失败保留，[V2完整分析](../model_v3/reports/attention_centered_e2e_20261027_v1/ANALYSIS.md)保留15旧FAIL转PASS及4旧PASS退化，非单调改善；H0标量max/32-atom模式不足以定位机制。当前fixed-H0分解仅在准备，未执行/未预注册，须先按同分量H/G/I辨别再选干预。证据与完整负结果见[AV诊断进展](../model_v3/reports/attention_av_diagnostic_20261027_v1/PROGRESS.md)、[分析](../model_v3/reports/attention_av_diagnostic_20261027_v1/ANALYSIS.md)和[标量汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/SCALAR_SUMMARY.json)。

S首成员已安全闭合8000更新/3258368基础记录消费，4521773在快照时正续8000→9000；四成员各20k首成员仍未完成。slot7/8/9 SDK审计4521777实际C0/15秒、28QA、3006history全部typed匹配，同步1778实际C0/32秒并Root闭合三条；online现61，原7不完整保留。新增本地归档1780实际C0/3秒、3006history/原4QA，三页Root视觉检查和入口追加已完成，[证明](../model_v3/reports/attention_centered_e2e_20261027_v1/SLOTS007_009_ARCHIVE_ENTRY_APPEND.json)保留旧索引/前缀。8000不表示D5或B验收。61完整run已在线Root闭合，原7不完整保留；七项本地归档1639及slot5/6本地归档1649均实际C0、Root闭合和审阅后接入统一入口，旧索引不变。新增两段2004条history与每页1000个默认训练曲线点分母不同，见[本地归档证明](../model_v3/reports/attention_av_diagnostic_20261027_v1/SLOTS005_006_ARCHIVE_ROOT_CLOSURE.json)。

[v18点时成本](../model_v3/reports/attention_centered_e2e_20261027_v1/ACTUAL_COST_SNAPSHOT_v18.json)为2026-10-27 00:06:41 UTC（北京时间08:06:41）的454父/1171344 CPU核秒/52741 GPU作业分配秒，捕获时1338 PENDING/1773运行；非最终成本、利用率或费用金额，活动后续时间不在快照内。v11收据的payload摘要抄录问题已另有机器补正，原收据和预注册树保留。数据线持续有实际处理进度，最终D1–D7与扩充交付仍进行中；D3–D6最终未交、D1 draft.3未共同冻结；完整指南、B*、最终recipe/tag/HANDOFF/PR均尚未完成。此前各段保持原时间点记录。


候选的实际[完整CPU闭合](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_ROOT_CLOSURE.json)、[原汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_FULL_SUMMARY.json)和[独立分支公开读回](../model_v3/reports/attention_av_diagnostic_20261027_v1/CANDIDATE_PUBLICATION.json)已随报告固化；SOURCE/CPU冻结、完整GPU失败与C4 HOLD、最终配方冻结分别记录。

## 2026-10-27 当前centered固定H0诊断预注册准备

C4完整1776的21PASS/27FAIL与全部退化保持HOLD/noadoption。新的[执行前协议](../model_v3/C4_centered_fixed_H0_diagnostic_prereg_20261027_v1.md)只安排当前cf8/f841候选的fresh同forward H0/pos/state捕获：原48/192 FP32/0 F64 encoder、全52外部1776终端逐位重放及逐case passmatrix一致后，才以冻结1503纯CPU方法做432项同分量H/G/I分解。没有1776隐藏H0或旧1492/1503代替当前H0的声明；F64残差不自动归因encoder。Root静态5AST/2bash及metadata source audit实际通过，新GPU/CPU诊断均未执行；候选/model不变，无需新增整套回归。本协议及源待Root检查、公开读回后唯一提交；未更新v13的S/日志/成本快照或任何科学结果。

## 2026-10-27 当前centered固定H0诊断实测

预注册7b290606b776ba74d38a6976c0730360cc7a718e后，GPU1838实际C0/66秒完成48fresh case/192 FP32/0 F64 encoder，全部2496外部1776终端逐位重放；物理结果仍21PASS/27FAIL，C4 HOLD/noadoption。CPU1842实际C0/32秒，48case共432项观察；F64头D仍50项/30case超1e-5，max约3.08038e-5。原GPU失败同分量H为最大源项52、head arithmetic19；F64使42原坏降阈下又暴露21原好，不能称解决C4。Root两阶段均闭合1290当前raw refs/来源前后/监督，NPZ未由Root独立读取；[新报告](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/PROGRESS.md)及最终V2分析记录限制。下一历史H64接口量化CPU反事实仅待审提案，未执行/未预注册，不选新encoder算子或改512D API。

1776已公开V2 scalar仅派生分组字段有误，原48pairs/测量/MD的15改善4退化6共同PASS23共同FAIL正确；[V3 scalar](../model_v3/reports/attention_centered_e2e_20261027_v1/SCALAR_SUMMARY_CORRECTED_v3.json)与[更正链](../model_v3/reports/attention_centered_e2e_20261027_v1/GROUPING_CORRECTION_v3.json)新增保留旧文件，不视为科学重跑。 [Root独立分组核对](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/ROOT_DERIVED_GROUP_VERIFICATION.json)重算144份原case和闭合结果，确认四种配对分组与全部11个cohort分组；其余1776 scalar不变。

S1773实际C0/2507秒，安全9000更新/3665920基础记录消费；1830在v19捕获时正向10000运行，首个20k成员尚未完成。slot10 SDK待下一3段批次，online61不是62；非D5/B验收。[v19账本](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/ACTUAL_COST_SNAPSHOT_v19.json)固定2026-10-27 00:47:12 UTC（北京时间08:47:12），459父/1210864 CPU核秒/55161 GPU作业分配秒，活动1338/1830；非最终成本、利用率或费用金额。最终数据交付/全指南/recipe/B*/tag/HANDOFF/PR仍未闭合，main未变。

## 2026-10-27 历史H64接口量化CPU协议准备

新的[执行前协议](../model_v3/C4_H0_interface_quantization_CPU_prereg_20261027_v1.md)只对保存的1561历史H64做A/B/C纯CPU反事实：每arm192次head调用、432项观察，0 encoder/GPU；不冒作当前1838 H0。A先以1e-10核全部432×3个原标量控制，数值失败全48保留后HOLD；B只一次F32量化再无损提升，BC含实现/dtype/backend，不能推出通用FP32下界、必要API变更或CUDA结论。物理1e-5/rtol0与C4 21PASS/27FAIL HOLD不变。

Root的3AST/1bash/SA4审阅和最终metadata装配已完成；combined selected stat为125739933B，低于固定134217728B，未读NPZ payload/执行模型/提交。10份源及3份Root证明已逐字节快照；原README DRAFT字节保留，最终inputs/pins明确另绑定。资源固定CPU16/16GiB、120秒/RSS12GiB、3分钟、whole/private各2GiB；须本协议与精确源公开读回后Root唯一执行。目前没有该诊断CPU结果、PASS或采用；此前S/成本/报告继续保持其原时间快照。

## 2026-10-27 历史H64接口量化1917实测

CPU4521917在公开协议后实际C0/11秒/16CPU/node15；A/B/C各48case、192head调用、432项观察均0超1e-5，最大D分别1.223000971e-6/2.031757251e-6/7.897615433e-6。A全部1296标量控制max9.237e-14，原tiny controls、源前后/155current raw refs与125739933B<128MiB输入闭合，0 encoder/GPU。[完整报告](../model_v3/reports/H0_interface_quantization_20261027_v1/PROGRESS.md)保留所有字段/分组/同分量和tie限制；C的零D不是新terminal nonzero证明。

范围仅历史1561 H64及此CPU backend，非当前centered H0、通用FP32下界或一般head/CUDA接受；原1776/1838仍21PASS/27FAIL HOLD，无API/生产/候选采用。下一local-module F32 replay与同输入独立F64参考仅准备，未执行/公开预注册；旧F64参考不同数值算法，须明示precision+algorithm contrast。

S首成员安全10000更新/4076032基础记录消费，v20时1906续11000；四成员各20k仍未完成，slot10/11 SDK待下一3段批次，online61，非D5/B验收。v20固定01:56:54.187994UTC的463父/1274464 CPU核秒/59116 GPU作业分配秒，活动1338/1906，非最终成本/利用率/金额。最终D交付、B*/recipe/tag/HANDOFF/PR及全部剩余指南要求仍未闭合，未缩减范围。

## 2026-10-27 当前编码器局部算子精度预注册

本提交同时记录已闭合1917结果及下一项[局部算子GPU诊断协议](../model_v3/C4_encoder_local_op_precision_prereg_20261027_v1.md)。原1917报告、实验规则和所有历史证据保留；新诊断尚未执行。13份冻结源、4份Root/SA4证明、原始最终协议和点时成本已逐字节快照。计划192次完整FP32/0次完整FP64 encoder、5312次局部FP32重放及5312次独立FP64参考、4368项观察；必须保留原48 case和全部1838 H0/终端逐位控制，不选择层/seed或修改absolute1e-5/rtol0。候选仍cf8/f841，物理21PASS/27FAIL HOLD，无采用或API修改。正常仓库检查、公开精确tree读回和现场资源准入各以实际证明为准，源码审阅不替代运行。

[v23点时账本](../model_v3/reports/encoder_local_op_precision_prereg_20261027_v1/ACTUAL_COST_SNAPSHOT_v23.json)为470个已登记父任务，CPU分配核秒1385344、GPU节点作业分配秒66046；它含仍在运行/排队的任务，非最终成本、利用率或金额。原最终协议中的v21点时原件亦保留，未刷新历史快照。真实D交付、C4通过、阶段5/6实际对比与全量收敛、最终recipe/B*/tag/HANDOFF/PR仍待完成。

## 2026-10-27 D-1 draft4：模型线增量共同审阅

状态：MODEL_REVIEW_RECEIVED_CONDITIONAL_DOMAIN_DESIGN，未共同冻结。模型线已在[独立审阅副本的“模型线意见”一节](training_format_v3_draft4_model_review_20261027_v1.md)形成对数据线v12/draft4的反馈，并保留原提案、两项源码审阅与Root字节绑定。当前被运行任务pin的draft3原件未修改，未签v3.0，模型/原值/source mask/现有运行均不变。

r73接受无损保留已解析有序双端entry的方向，但须独立channel/onsite/重复身份及消费链；原对称pair头不可替代，当前codec的F64缺口需版本化解决。r674需完整六值作为一个对称张量，统一行坐标R约定、Frobenius/radial损失、TRAIN单尺度与partial-mask共同政策。真实原点/轴/单位/精度、原生对照、五层map/D4/D5/release及新consumer仍待完成，basis/tensor保持UNSUPPORTED/PENDING。该审阅未运行新测试或读取科学payload，不能代替D3真实加载、1000分子过拟合或三GPU SDP冒烟；C4的21PASS/27FAIL HOLD未变。源码审阅证据见[evidence目录](evidence_D1_draft4_model_review_20261027_v1/)。

### 2026-10-27 模型线阶段2/3/5/6：候选CPU核验与局部误差分析

- 模型实现：Native桥接74项、配方工具120项、A1/A5执行99项相关测试均实际C0且已发布独立分支；完整统一运行树回归与GPU验收待完成。
- C4：实际48案例/192前向/5312对局部调用完成；4368观测/546组统计和两图已核验，原21通过/27未通过、FP32容差保持。
- 记录：新增8段W&B日志实际同步、Root核验并追加统一入口，原SDK和失败历史保留。
- D-1～D-7：最终交付未齐，真实新标签及D-5/D-6验收待数据权威；既有S首成员17000步不替代科学验收。
- 报告：[训练前准备实际进度](../model_v3/reports/PRETRAINING_PREPARATION_20261027_v1.md)。最终冻结、B*、交接与PR尚未完成。

## 模型线增量 v19（2026-10-27）

三候选组合full4376已实际C0：116模块2734通过/3原CPU可选skip/零失败；组合源码已精确树发布到model-v3-runtime-integration-20261027-v1(public57d95b5c79fbd33e916330a455a7c3d4178c2284)。manual R2实际20批/500步与CPU consumer已Root闭合，不外推auto/R1/速度；Native10k full9面板CPU准备4415通过，GPU待现场准入。Core64完整48诊断和Native面板v2方法在本次预注册，尚无相应GPU结果。draft5条件式模型意见已归档，23明确输入当前核验，仍非joint freeze。参见docs/model_v3/reports/PRETRAINING_PREPARATION_20261027_v2.md及docs/interfaces/training_format_v3_draft5_model_feedback_DRAFT_v1.md。真实训练接线、FP32物理21/48、D1–D7最终交付和完整指南后续验收仍未完成。


## 2026-10-28 模型线实际进度 v20

[最新实际报告](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v1.md)与[精确证据](../model_v3/reports/pretraining_preparation_compact_evidence_20261028_v1.json)：训练/恢复/六层512 H0 CLI链实际CPU4524523完整121模块2905PASS+3原有skip，runtime快进同一tested commit并核2149受管源及9外部源，公开0cfc5c40。新FP32投影候选完整115模块2753PASS+3skip，候选b2c4c677与完整48GPU科学方法4bfb4263已公开，最终metadata和实际GPU仍待。

Native S10000完整9×2实际4476 C0/518秒，H0/来源/资源已Root闭合；候选/随机参考同可用几何人口，原SoM3/ExpansionRx48缺几何排除明确保留；SDK独立核验/同步待办。原全FP3221/48未升级，混合Core64实际14/48未采用。D1当前权威仍draft3，draft5未jointfreeze，D1–D7最终交付、真实A/B/架构/19配方/D6/120k-k2-1M E2E及最终冻结/交接/PR继续。没有开始正式预训练。


## 2026-10-28 模型线实际进度 v21

[最新报告](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v2.md)及[精确证据](../model_v3/reports/pretraining_preparation_compact_evidence_20261028_v2.json)：auto R2实际4551 C0/2274秒，20+500全通过且前向/梯度/轨迹最大相对差全0，源/资源闭合、hold释放；不扩大到R1/A5/ABBA/三卡或新runtime训练。新投影4550是12P36F/完整48，未采用，原正式21P27F不变；终端CPU4554全部1872重放一致且无本批不可表示分量，继续被动geometry/H0诊断。Native S10000 SDK4552与精确单run sync4555均实际C0并Root闭合，远端vcxcfx54 finished/56738历史行，原SDK/4553失败保留。4090新独立manual源包已备、还无提交；原1338不动。最终D1–D7/科学/配方/真实E2E与冻结/交接/PR继续，正式预训练未开始。

## model-v3: passive trace v3 / paired logs v2 (2026-10-27T20:25:39Z)

原指南阶段0–7仍未完成，FP32正式物理门槛仍为21/48；投影候选4550为12/48，未采用。归档的passive trace v3只补齐观测引用生命周期，固定原48例/192前向、52终端逐位对照、512MiB采集与原2GiB监督限制；源码审阅和Root AST4/bash1已完成，实际GPU采集结果尚未产生。

paired日志v2仅修复嵌套descriptor路径，原四ID/每role 500行/完整config及summary/原v3传输预算不变。实际核验4524559已在CPU节点提交，结果与在线同步尚待Root实际终态确认。既有S10000面板日志已同步；新日志不得据源码检查声称成功。4090作业4524558仍在compute-0-20排队，D1–D7最终交付和原完整剩余验收不变。

## model-v3 v23：实际离线统计和R1方法

报告PRETRAINING_PREPARATION_20261028_v3.md记录四日志核验/同步、全48被动采集和CPU4564完整9120条统计。模型及阈值未变，原formal21/27、候选12/36均未通过；完整0–7仍待。新R1 ABBA单员提交入口和原始脚本已归档，尚无R1实际提交或速度结论；D1–D7及最终冻结未完成。


## 2026-10-28 模型准备进度 v24

见[实际进度v24](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v4.md)：A00四次校准与日志同步闭合，速度比0.993无提速；新geometry候选116模块2816通过/3原跳过，GPU48待验。完整GPU与head-off方法同批归档，D1–D7及阶段0–7剩余科学矩阵继续；未最终冻结。


## 2026-10-28 模型准备进度 v25

见[实际进度v25](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v5.md)：新geometry GPU4579完整15通过/33失败，1198源与资源闭合，未采纳；98份JSON独立确认双向翻转，headOff4580固定20批通过/500轨迹待终态。日志方法及负结果同批归档，完整阶段0–7未完成矩阵保留。

## 2026-10-29 模型线当前状态

原Stage0–7继续。[单日记录](../model_v3/DAILY_20261029.md)记录canonical8adb、实际133模块3122PASS/3原CUDA skip、Model同版本policy/config签署、R1两组实测与最大712单例SDK闭合。剩余A-v2两项实际GPU验收运行中；Native bf16/seed0已到6000，下一段等待CPU资源。D3–D6真实交付、架构/配方科学矩阵、B*确认、最终冻结、12万/k2/百万样本端到端和PR仍未完成；未启动学校正式预训练。


## 2026-10-30 模型线非数据依赖工作复核

第二种子实际配置/UNADMITTED请求接线已补齐，预算改为用户v3三倍确认线、
记账非阻塞；实际CPU4525191为138模块3263PASS/3原skip，首轮UNIT失败保留。
D1双方设计冻结仍有效；数据方当前STATUS明确D2–D6实际交付/验收未完成。
首seed20项静态准备完成，不能冒充D3的20×50更新或D5科学比较。
C4按用户v3为PASS；r674保持LOSS_DISABLED。3090/5090 C1-a、原438复核及
Native四条20k曲线仍受实际GPU资源阻塞；等待进程存活不代表已执行或科学完成。
详见[当日唯一汇总](../model_v3/DAILY_20261030.md)。正式预训练未启动。

| 2026-11-05 | 模型线 v2 M1 | MFM4/NaN/D5 排除/分子均匀采样的 UNIT 已通过；M2 真实验收尚未完成 | model-v3: docs/model_v3/M1_V31_LOADER.md |
| 2026-11-05 | 模型线 v2 M3 S | D5 240k 已连接到现有 S：240,000 分子、2,209,619 个训练 PM7 构象；按新判定规则开始 6M 开发实验 | docs/model_v3/DECISION_RULES_TASKBOOK_V2.md |
| 2026-11-05 | 训练视图依赖 | 等待窗口二 training_view_v1.json 后完成字段排除、r73 σ/π 与 D4 接线；用户已要求等待该交付，不自定字段 | configs/data_v1/training_view_v1.json（数据线） |

| 2026-11-05 | 模型线接收正式训练视图 | 已收到 FROZEN_BEFORE_STAGE5_PD，按原 pair 行汇总双轴同对称性的 σ/π，保留自环/方向/重复与缺失；正在接入134字段 | 数据线 configs/data_v1/training_view_v1.json |
| 2026-11-05 | M2 所需 D4 参数 | 现有 numeric_repetition_0 的向量路线仍为 PENDING_ACTUAL_JOINT_POLICY_RELEASE；请数据线在正式 D4 中交付字段到归一化参数的映射，包括新 σ/π、能量元素参考、矢量零中心单尺度及原子字段策略。模型端不以 B2 原始均值/标准差替代 D4，不用 raw-K 统计归一化 σ/π；等参数交付后直接进行 M2 | docs/model_v3/M1_V31_LOADER.md |

| 2026-11-05 | D6 r73 存储绑定已接线 | 优先消费 schema.derived_r73_pair_targets 的 array27 预聚合列；历史D3保留F32 K聚合，按各自schema标签字典解析通道。原子对仅在有标签的行执行预测，按原行号还原掩码/方向/自环；扰动标签使用真实array22，缺几何且无标签时保持缺失 | current/phychem_mfm/phase1/v31_loader.py；v31_training.py |
| 2026-11-05 | 阶段5代理人口保持 | 当前S对比使用已交付D5的240,000 TRAIN分子，训练索引为 runs/model_v31_20261105/S240k/records.parquet。后续P/D/SDP将消费同一代理分子列表；若最终D6缺其中ID，实际加载时报告缺口，不把另一份240k列表静默当作同一比较 | 数据线 configs/data_v1/D5_v1_pilot_provisional_delivery.json |

2026-11-05 模型窗口一已接D6 M17/M18：普通UFF按M17且排除M14，Pprime训练按M18且排除M14；先资格过滤再取k，保留的其他真实Pprime标签不自动扩张训练集合。D5诊断按实际holdout数组访问全部留出，包括普通排列之外的addressable几何；FULL不套用TRAIN-only的M18。若M18合格几何缺少发布的source order，模型会明确报接口缺口，不按存储序号猜次序。新增5项逻辑单测通过，M2仍等正式D4参数。

2026-11-05 最终人口消费约定（模型窗口一）：已收到最终Common TRAIN=1,194,551与D5完整池=1,126,937，新D5标明nested_selection_recomputed_for_final_complete_pool。M3及M4的24万代理仍绑定当前S实验实际使用的原D5 240k名单，后续P/D/SDP用相同MID，不静默换成新的240k前缀；D6交付后在实际消费者中定位。M5的120万格子人口不足已请用户作科学决定，答复前不改M或预注册。当前M2仍等待正式D4，三条S保持6M预算。

2026-11-06 用户已批准模型M5最大M由原120万调整为最终D5完整嵌套TRAIN全池1,126,937；同步修订PREREG、网格启动入口及HANDOFF，其余k/条件/种子/判据不变。M3/M4仍用当前S实际240k名单，不更换代理人口。正式D4/M2及实际M3/M4选型仍待完成，未启动性能实验。

## 2026-11-06 给窗口一/窗口二/窗口三及所有子agent的用户通知：节点磁盘保护

用户明确要求：以后往各节点传输文件时必须保证不要将磁盘占满，并让其他正在工作的Codex知悉。各窗口在下一次节点传输/缓存/解压/生成临时文件之前，重新读取项目根AGENTS.md及huagong_hpc_requirement技能顶部2026-11-06条款并在本状态文件追加简短已读确认；本通知写入不代表已经取得其他会话的已读确认。

必须检查实际目标节点的目标文件系统、可用字节和inode，计入复制/解压/数据库临时峰值、残留与跨窗口同盘并发写入；根分区至少保留max(10GiB,10%总容量)，站点更严格规则优先。空间不足或容量不明时不传，改经核实的scratch/共享盘或减小批次；传输中在触及预留空间前停止新增写入。/tmp可能占用根盘及Slurm共用空间。新传输/缓存入口必须落实检查与运行期保护。原始数据、其他窗口作业、管理员目录和drain状态不因这条通知获得修改/删除授权。

事故依据：节点17作业4526050于11月5日16:33向/tmp复制约29GB数据库，部分文件17,656,872,960字节，ENOSPC与SlurmdSpoolDir is full drain同刻；节点20作业4526119于11月6日01:35取消清理时一个进程未退出，触发Kill task failed，不能混同为磁盘满。

2026-11-06 模型窗口一已读根AGENTS及HPC技能顶部磁盘新规。实际节点21/20的根盘分别约831/526GB可用，均高于95.4GB系统预留线，inode充足；/tmp与根盘共盘。当前无新增节点本地大文件传输，模型已有CP约199MB/份并写共享盘；活跃S及下一M2近期新增预留5GB（后续大批提交前更新并与数据线并发合并预算）。共享盘整体约5.69TB可用，账户quota当前3630GiB/4096GiB，另保留既有100GB账户底线；不把共享盘余量当作节点根盘余量。后续checkpoint增加预检/写入期保护；不删旧文件、不动他人任务或drain。最终D6按数据线新接口读取共享compact，不复制到各GPU节点。

2026-11-06 模型活跃作业磁盘保护已部署：compute-0-21的观察进程3062529绑定本窗口4526020/4526023，compute-0-20的2706796绑定4526041；直接在实际节点每5秒检查根盘和共享输出字节/inode，当前均OBSERVING且状态持续更新。容量不足/未知只用scancel --signal=STOP --full并限定本UID、实际节点和这三个作业ID，保留训练内存/优化器/时钟，不重启、不取消或重算；主观察器会提示暂停/心跳失联。新4项逻辑测试通过；5GB是模型两节点合计近期预算，不重复预留为10GB。其他窗口320GB共享NFS及节点0 RAM/节点19既有缓存预留已读，不占用这些预算。

2026-11-06 模型M2正式D4接入说明请求：已读EA既有规则命中3,333条、其中222条新增掩码的生产端报告。M2会直接消费既有v3.1 D3试点及正式D4；请在D4交付中注明该遮罩版本与既有D3试点的兼容性。若修正适用于其中记录，请提供已有的NaN覆盖/正式mask引用及MID、RID、字段绑定；若无需覆盖，请直接说明。只需现有producer的版本/绑定说明，不新增扫描、数值回读或独立QA；模型不自行执行EA阈值筛选，也不把归一化参数当作标签遮罩。当前尚未观察到试点实际遮罩不一致，不据此判定数据错误；S实验继续。

2026-11-06 模型已接收用户冻结的向量尺度方针 window2_user_frozen_vector_normalization_20261106_v1.json：center=0，按已有physical_key的norm序列精确type7 0.001/0.999统计副本截尾后总体std(ddof0)作为每头唯一尺度；训练标签原值/NaN和原物理矢量损失保持，空/未定义/零尺度不发明epsilon或替代值。M2仍等实际参数与字段绑定。为加快接入，若所需截尾均值/std、元素参考及上述norm.std在median/MAD报告之前已由既有生产步骤独立闭合，可先发布明确状态的训练绑定供M2真实消费，其余D4报告照常继续；仅翻译已有参数，不新增扫描/拟合/回读，也不将部分绑定冒充D4全部完成。尚未闭合的参数继续等待。此前EA遮罩与既有D3的兼容说明请求仍有效。

2026-11-07 模型M2参数接续（PM7截尾矩已闭合后的跟进）：已读窗口二04:30生产汇总，PM7 pass9均值/std已171/171闭合，正在median/MAD；S三候选首种子6M及全部终点评价已完成。M2的1000分子过拟合/2000步SDP只消费既有PM7 D3和PM7训练归一化，不依赖P′参数、D6或median/MAD诊断报告。若既有pass9 winsorized_statistics、元素参考及字段绑定已独立闭合，请按此前请求先发布明确标注“训练参数已闭合、完整D4诊断未完成”的PM7正式路由供M2消费；P′和median/MAD照常继续，不把部分交付冒充整体D4完成。仅从现有closed JSON翻译/绑定，不扫描/重拟合/数值回读，不放宽尺度或改变标签。沿用用户冻结零中心/截尾norm.std_ddof0单尺度及既有target-local退化状态；D3试点EA遮罩兼容说明/已有覆盖引用仍需随绑定交付。模型不会自行生成统计或套阈值掩码。近期模型合并5GB预算继续为后续M2预留，结束的20/21模型观察已精确退出；新启动前重新核实目标容量并绑定自身任务保护。

2026-11-07 模型M2实际接入反馈：正式TRAIN routes已收到，新增按已发布mask_overrides_reference/native_record_id+MID应用EA标量leaf0 NaN覆盖，归一化前同步raw/valid；3项新合成单测4526232实际C0/0.11s，代码已推GitHub5a39f01。实际M2 overfit4526233在MFM4Dataset初始化、任何训练更新前失败：`D4 preserves disabled source loss for D20.MolMR`。冻结training_view_v1.json中D20.MolMR enabled=true、exclusion_reasons=[]；正式P_D路由native_d3ce435b9e185a70bb13ec72054c0f4a3ecd12ca418a850685fd3519425e843f虽normalizer_ready=true，但original_loss_enabled=false/source_loss_policy=DISABLED_UNIT_UNSPECIFIED。请窗口二按既有D1/物理损失策略对齐冻结视图与路由，明确该字段参与损失/仅保留统计的正式消费方式；模型不自行绕过禁用、不删字段、不造单位或参数。此为真实下游使用报出的接口冲突，不另起数值QA/源标签扫描。节点21已实核root约830.65GB、NFS quota337.32GB及各并发预算，M2近期5GB全节点合并预算继续预留；4526233零训练更新，原失败产物保留。

2026-11-07 模型M2反馈更正：已定位为模型适配器把字段选择与物理损失启用混为一谈，不再要求窗口二修改冻结视图。正式routes中original_loss_enabled=false现继承为字段loss_enabled=false：保留MolMR原始读取/已有归一化及统计，仅从优化头/损失/启用头R²门槛排除；r674和其他既有排除不变，不造单位、不改科学规则。Pprime同样继承D字段禁用标志但不消费D归一化，完整字段顺序保留。只运行修正旧fixture及一项新Pprime fixture，4526236实际2PASS/0.07s，旧其余项不重跑。原6233失败及零更新记录保留；模型马上用实际M2续接，参数交付已满足依赖，不再等待MAD或额外ACK。


2026-11-07 模型加载确认（M1/M2实际运行）：v3.1+D4正式训练参数及已发布EA逐记录NaN覆盖已实际读取。6238/1000分子过拟合和6239/2000步SDP均Slurm主/batch/extern C0；134读取列、133启用列、121物理头，MolMR原损失禁用仍保留。逐字段R²阈值保持0.95，实际40/133通过、93未达标；不宣称全部过拟合通过，不删这些字段。SDP前100→末100步S=1.266039→0.667048、D=2.187473→0.389692、P=144.239207→8.927668，三组均下降。全部失败字段如下（精确R²/MAE/有效数见 /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_failed_fields_20261107.csv；原完整逐字段表及两个summary/检查点见模型仓库docs/model_v3/M2_V31_DELIVERY.json）：

D20.BertzCT, D20.FractionCSP3, D20.HallKierAlpha, D20.MolLogP, D20.NumAliphaticRings, D20.NumAromaticRings, D20.NumHAcceptors, D20.NumHDonors, D20.NumHeterocycles, D20.NumSaturatedRings, D20.RingCount, D20.TPSA, D3.PBF_A, D3.PMI1, D3.PMI2, D3.PMI3, D3.SASA_atom_A2, D3.SASA_total_A2, P.pm7_B.r42.value, P.pm7_B.r44.value, P.pm7_B.r45.value, P.pm7_B.r46.value, P.pm7_B.r47.value, P.pm7_B.r48.value, P.pm7_B.r49.value, P.pm7_B.r50.value, P.pm7_B.r52.x, P.pm7_B.r52.y, P.pm7_B.r52.z, P.pm7_B.r53.value, P.pm7_B.r55.electron_electron, P.pm7_B.r55.electron_nuclear, P.pm7_B.r55.total, P.pm7_B.r56.EE, P.pm7_B.r56.EN, P.pm7_B.r56.NN, P.pm7_B.r58.value, P.pm7_B.r61.value, P.pm7_B.r62.value, P.pm7_B.r63.value, P.pm7_B.r64.value, P.pm7_B.r65.value, P.pm7_B.r68.value, P.pm7_B.r73.value.pi, P.pm7_B.r73.value.sigma, P.pm7_B.r82.De, P.pm7_B.r82.Dn, P.pm7_B.r82.charge_density_q_minus_Z, P.pm7_anion.r193.value, P.pm7_anion.r196.x, P.pm7_anion.r196.y, P.pm7_anion.r196.z, P.pm7_anion.r210.value, P.pm7_cation.r262.value, P.pm7_cation.r265.x, P.pm7_cation.r265.y, P.pm7_cation.r265.z, P.pm7_cation.r279.value, P.pm7_octanol.r329.value, P.pm7_octanol.r331.value, P.pm7_octanol.r332.x, P.pm7_octanol.r332.y, P.pm7_octanol.r332.z, P.pm7_octanol.r341.value, P.pm7_octanol.r343.value, P.pm7_octanol.r346.value, P.pm7_water.r396.value, P.pm7_water.r398.value, P.pm7_water.r399.x, P.pm7_water.r399.y, P.pm7_water.r399.z, P.pm7_water.r408.value, P.pm7_water.r410.value, P.pm7_water.r413.value, P.xtb_ALPB_octanol.r459.value, P.xtb_ALPB_water.r498.value, P.xtb_fod.r537.value, P.xtb_fod.r538.value, P.xtb_perturbed_gradient.r624.value, P.xtb_perturbed_gradient.r625.value, P.xtb_singlepoint.r666.value, P.xtb_singlepoint.r667.value, P.xtb_singlepoint.r668.value, P.xtb_singlepoint.r669.x, P.xtb_singlepoint.r669.y, P.xtb_singlepoint.r669.z, P.xtb_singlepoint.r671.value, P.xtb_singlepoint.r672.value, P.xtb_vfukui.r712.f_minus, P.xtb_vfukui.r712.f_plus, P.xtb_vfukui.r712.f_radical, P.xtb_vipea.r751.value, P.xtb_vipea.r752.value

仅实际训练与producer报告，无标签二次扫描/拟合/独立QA或额外冒烟。原6233/6237零更新失败保留；适配器已继承既有物理损失标志并复用S入口精度初始化，不要求窗口二改视图/科学。M3 P/D/SDP待实际D6，仍须同现有S实际24万MID；不自行替换新前缀。两节点近期模型增长仍按全局5GB联合预算，不按节点重复；完成的M2保护观察按精确own PID退休。
