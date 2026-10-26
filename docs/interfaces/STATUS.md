## 2026-10-26 Native S 长程准入实测闭合

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

执行前公开版本99788277501ceff4a8adf37f7d9ee01498b9dbf1对应的AV诊断4521641实际C0/75秒：192次原H0逐位门、1152项原AV重放全部通过。中心化对Rnorm的聚合RMS约改善11.3%，第0层192/192局部项RMS变差，Rraw参照下总体也更差；不选层采用，未得到新的物理通过。统一六层FP32候选已SOURCE+CPU冻结，并在独立[实验分支](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)公开f8417157dc23326d1beca8e19e4725755d9f13c6（本地cf8ce66d97cd518ebf279b40ee20294919bb95e1）。完整CPU父1707实际C0/132秒，2712采集=2709PASS/3既有SKIP，73新测试及47原numeric全部PASS/0skip；最终执行metadata已实际绑定并通过仅元数据audit；[正式GPU协议](../model_v3/C4_centered_attention_e2e_prereg_20261027_v1.md)与运行器待Root公开读回后唯一提交，GPU48矩阵尚未运行，无adoption。证据与完整负结果见[AV诊断进展](../model_v3/reports/attention_av_diagnostic_20261027_v1/PROGRESS.md)、[分析](../model_v3/reports/attention_av_diagnostic_20261027_v1/ANALYSIS.md)和[标量汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/SCALAR_SUMMARY.json)。

S slot8/4521644实际C0，安全7000更新/2851328基础记录消费；slot9/4521686已续7000→8000。slot7/8待与9批量SDK审计，无新增online；四成员各20k的首成员仍未完成，7000不表示D5或B验收。58完整run已在线Root闭合，原7不完整保留；七项本地归档1639及slot5/6本地归档1649均实际C0、Root闭合和审阅后接入统一入口，旧索引不变。新增两段2004条history与每页1000个默认训练曲线点分母不同，见[本地归档证明](../model_v3/reports/attention_av_diagnostic_20261027_v1/SLOTS005_006_ARCHIVE_ROOT_CLOSURE.json)。

v17成本快照为2026-10-26 22:17:38 UTC（北京时间10月27日06:17:38）的443父/1076112 CPU核秒/46983 GPU分配秒，活动1338/1644；不含1649等后续成本，非最终账单。A01/1338仍PENDING，最近节点20为104/104 CPU占用。v11收据的payload摘要抄录问题已另有机器补正，原收据和预注册树保留。数据线v7已有实际处理进度，D1–D7与扩充交付仍进行中；D3–D6最终未交、D1 draft.3未共同冻结；完整指南、B*、最终recipe/tag/HANDOFF/PR均尚未完成。此前各段保持原时间点记录。


候选的实际[完整CPU闭合](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_ROOT_CLOSURE.json)、[原汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_FULL_SUMMARY.json)和[独立分支公开读回](../model_v3/reports/attention_av_diagnostic_20261027_v1/CANDIDATE_PUBLICATION.json)已随报告固化；SOURCE/CPU冻结与待运行的科学GPU验收、最终配方冻结分别记录。
