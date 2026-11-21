## 2026-11-18 用户新规则：GPU 按规模分配，不让显卡空着

适用于所有使用 GPU 的工作线、Codex 窗口和子 agent。本条覆盖以前"空闲卡按 5090 > 4090 > 3090 选择"的全局优先级，以及混合调度只看 compute-0-20/22 的做法。

- **gpu 分区包括 compute-0-0 ~ compute-0-7（主要是 3090）和 compute-0-20 ~ compute-0-22。** 两组都要用。
- **小规模任务优先用 compute-0-0 ~ 7。** 小规模指训练预算不超过 3M 样本的运行，包括：
  - ablation 和筛选臂，以及它们的 seed 1；
  - 过拟合测试和其他短测试；
  - 读出评估；
  - 基线推断。
- **大规模任务优先用 compute-0-20 ~ 22**，组内仍按 5090 > 4090 > 3090。大规模指训练预算超过 3M 样本的运行，如 9M 确认和正式预训练。
- **不让显卡空着。** 优先组没有空卡时，直接用另一组的空卡，不排队干等：
  - 小任务可以上 20~22；
  - 大任务可以上 0~7。
  - 有已就绪的 GPU 任务而某张卡空着，就是要处理的问题。按既有的 1800 秒轮询，发现空卡就补上。
- **0~7 号节点的提交方式：** 普通 sbatch（gpu 分区）。提交前按目标 GPU 的 UUID 核实没有被占用，再按任务实际需要申请 CPU。显存不超过 30% 时直接 SSH 启动的规则，仍只适用于 compute-0-20/21/22。
- 相应更新 `configs/p_recipe/scheduling.json` 和 `tools/p_recipe/launch_plan.py` 的节点列表，并同步全局技能 huagong_hpc_requirement。
- 已经在跑的任务不因本条迁移或重启，本条只对新提交生效。
- 磁盘保护、不使用 exclusive、OOM 降批、不动他人进程等既有规则不变。

## 2026-11-18 用户新规则：CPU 任务只在 CPU 节点提交

适用于所有工作线、Codex 窗口和子 agent，覆盖以前把 CPU 工作放在 GPU 节点或 compute-0-2 空闲核上的做法。

- **不用 GPU 的任务一律提交到 CPU 节点 compute-0-8 ~ compute-0-19**（共 12 个）。包括：标签计算（PM7、xTB、UFF、RDKit）、数据预处理和打包、参数拟合、统计分析和 bootstrap、传统 ML 基线、环境搭建、下载和安装。
- 用 sbatch 时用 `--nodelist` 或 `--exclude` 限定到这 12 个节点。提交前按实际节点查看空闲 CPU 和内存，只申请实际需要的量。
- **不占 GPU 节点的 CPU。** GPU 节点包括 compute-0-20、21、22 和其他带 GPU 的节点，它们的 CPU 只留给 GPU 任务。GPU 训练在 GPU 节点上也只申请自身数据加载等实际需要的 CPU。
- Alpha 集群同理，只用没有 GPU 的主机。
- CPU 节点占满时，排队等待，不退到 GPU 节点上。排队不是停止条件，日报记一行即可。
- GPU 节点上已经在跑的 CPU 任务不中途停止。能从检查点或分批边界续接的，在下一个边界迁到 CPU 节点；不能续接的跑完为止。以后不再往 GPU 节点新提交 CPU 任务。
- 同步更新全局技能 huagong_hpc_requirement。
- 节点磁盘保护、按需申请 CPU、不使用 exclusive 等既有规则不变。

## 2026-11-15 当前最高优先级：在跑训练连续性与P补充规则
用户再次明确：没有特别停止指令，不得因规则更新或微小配方改动主动停止正在运行的训练，也不以此要求从头训练。保留已有进度，必要更新从后续运行生效或从已有完整检查点续接，并记录生效点；既有真实磁盘保护和用户已授权的同任务SSH→sbatch完整状态接管保持。当前G1按用户要求沿原配方完成3M及既定R1/R3，原p99=8426.777509765629不在中途改动；G2–G4保持用户要求的停止状态，不重启对照。

用户后续明确回复：现有G1完成后直接复用为新首轮B0，不另跑同配方B0，并如实报告其旧裁剪窗口例外。C1/C2仅限制谁可把学习率作为筛选变量；胜出学习率可随M3采纳，两者都胜出则按较大Δ留一个。T2/T4/T5/T6/T7使用M3学习率；T1与T3（M2、不含第3轮改动）保持3e-4，无学习率臂胜出则全部3e-4。
当前执行配置：三轮筛选3M、确认9M；每500k固定VAL不变。确认阶段恢复检查点每1M及最终9M保存，另保留用户已授权的完整状态接管点；这是实际配额下的存储安排，保留所有已有输出，不改变训练/评分预算。

2026-11-14任务书补充规则覆盖较早冲突条款；用户随后明确固定筛选预算3M、放大确认9M：
- 后续P运行batch_size=microbatch_size=32，单次前向32、无梯度累积、关闭逐层重算。AdamW lr3e-4、betas(0.9,0.95)、wd0.01，cosine按每条自己的预算完整退火到0、warmup2%；只允许第3轮C1=6e-4、C2=1.5e-4改lr。保持均匀分子→允许10构象均匀采一个。
- 每臂前150000样本clip281.7，使用60000–150000样本窗口每步的裁剪前梯度范数p99，之后固定至结束；窗口不随预算变化。每臂阈值写training/<运行>/，只报告不调参。
- 整个P研究始终使用window2_TRAIN_normalization_parameters_20261107_v1全TRAIN归一化；清单剔除/子集不触发重算或切换。发现TRAIN/下游重叠就直接剔除清单、日志记一行并继续，不能作为停训条件。
- 三轮筛选全部3M；T1–T7放大确认均9M（3×筛选预算）。B128旧首轮仅存档、不参与决策。D5支持第2轮B1共享投影器优先启动。
- 未列入任务书的CPU/GPU计算若预计>2小时，不执行，列日报“待用户决定”；基础设施故障后的续跑除外。
- 每轮完成后日报按卡型各报告一行实测样本/秒和整卡平均功耗。按需CPU、不exclusive、5090>4090>3090及既有混合调度不变。

## 2026-11-14 P最新用户修订：旧首轮作废，先做batch/lr/clip校准

旧第2轮已按用户要求停止，SSH与sbatch接管队列均取消，输出保留。旧1.5M首轮结论作废，不得用于选择或恢复旧第2轮。先在此前实际使用的6张卡上分别测B32（关闭逐层重算）和B128各1000步。B0四组并行3M：B32/3e-4（无逐层重算），B128/3e-4、6e-4、1.2e-3；在1.5M和3M评R1/R3。每组前150000样本用281.7初始裁剪并收集裁剪前范数，随后冻结其p99。以最高3M R3选择新固定batch/lr，再按首次R3≥0.30（向上取整0.5M，最高3M）确定新筛选预算；额外0.5M读出观测按用户待答复执行。新配置/预算下重跑B0+A1–A5，第2/3轮及后续确认仍按原计划。现行HPC技能1.0.156为准；旧B128、固定clip和1.5M限制在此范围被覆盖。所有既有输出保留；不放宽磁盘字节/inode/quota、按需CPU、不exclusive及混合接管规则。

## 2026-11-14 最新调度规则：按需CPU，SSH先跑、sbatch接管

后续任务不使用 `--exclusive`，只申请任务实际需要的 CPU。开发集群 compute-0-20/21/22 使用可恢复的混合调度；本节覆盖较早“20–22一律直接SSH/不提交sbatch”的冲突条款。操作前读 [混合调度说明](docs/p_recipe/HYBRID_SCHEDULING.md)。

- 按实际目标节点/UUID检查Slurm剩余CPU和GPU显存。可分配CPU足够本任务且显存足够时直接sbatch；CPU已被分配、不足本任务时，不论GPU空闲或已有他人上下文，只要目标显存占用≤30%且剩余显存覆盖本任务，就SSH启动并同时提交同一任务的sbatch接管作业。GPU未知或余量不足不启动；不能把MIXED或有一个空闲CPU误当作足够本任务。
- 接管作业排到后请求原训练在下一次完整优化器更新结束处保存完整状态并退出；保存成功、原进程树/自有GPU锁释放后才恢复到真实新job ID下。模型、优化器、学习率进度、采样位置及全部相关随机数状态一并恢复，不从头训练、不双跑。SSH已完成时占位作业退出，不重跑。
- 保持其他用户进程不变；保留真实原生身份、job ID、退出状态及接管关系，GPU成本不重复计入两种句柄重叠时间。当前无GPU GRES时普通sbatch不提供显卡独占；始终按UUID核实实际占用。
- 新任务使用仓库 `configs/p_recipe/scheduling.json` 和 `tools/p_recipe/launch_plan.py`；旧运行未加载接管协议时，仅从已确认完整的既有检查点迁移，并如实记录回退量。磁盘预检/运行保护、5090>4090>3090、B128/OOM96再64及科学预算不变。本规则不扩大学校付费服务器或其他任务的授权。

## 2026-11-14 用户要求：A5/node22从原生运行转为sbatch

用户明确要求当前P研究A5在compute-0-22改为sbatch。按已保存检查点衔接，保留已有训练进度；Slurm分配与检查点就绪前可让已有原生进程继续，不能同时启动两份A5。该要求覆盖本次A5的node22直接SSH启动规则；其余现有任务和其他用户进程不改动。实际核实node22当前Gres=(null)，普通sbatch不构成GPU资源锁；Slurm节点独占需排队，仍无法阻止绕过Slurm的SSH进程。迁移模式和真实句柄以本研究handoff控制文件/执行台账为准，不能把排队提交写成已经完成迁移。
## 2026-11-14 用户最新OOM批量规则

用户明确允许OOM时适当缩小BS至96或64。P训练默认128；实际OOM后的后续尝试先用batch_size=microbatch_size=96，仍OOM再用64，不再受旧“始终固定128”限制；在既有4小时修复盒内执行该OOM降批顺序，其他失败沿用任务书规则。已经正常推进的尝试继续，降批后不自动放大。保留总样本预算、按样本计的学习率、种子、数据与归一化参数，并记录每次尝试实际BS、卡型、样本/秒、功耗及真实退出。已有逐层激活重计算可继续使用；评价探针仍32。空闲GPU优先级5090>4090>3090及显存<=30%直接SSH规则不变。
## 2026-11-14 P B128实际OOM后的执行修复

首轮B0/3090和A3/共用5090的首次实际运行均在50944样本后、下一批距离偏置矩阵分配时发生CUDA OOM；此前有限批量容量测量不构成完整TRAIN上界。全部后续P训练继续实际B128/micro128，并启用已有骨干逐层activation_checkpointing=true（非重入重计算，保留参数、采样顺序、精度、损失和优化器步数）。这是内存执行修复，不增设科学臂。首个失败尝试的配置、输出、日志和真实句柄保留；重试使用独立attempt2运行/输出，后续计划生成保留该重试引用。现有未失败的运行继续原尝试；有实际失败再按同一执行修复处理，不更改其他用户进程。
## 2026-11-14 空闲GPU选择优先级

用户明确：可用空闲显卡按5090 > 4090 > 3090分配。新任务先用可满足显存和现行准入条件的5090，再用4090，最后3090；继续固定B128。

## 2026-11-14 P研究最新决定：停止D4重算，固定11-07参数

用户明确撤回本次D4重算：只在TRAIN分子清单中剔除323个分子，整个P研究固定使用`/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/routes.json`，不中途切换。该决定覆盖此前“排除后重拟合基础D4”的授权；A1/A2/A5自身新增变换仍按任务书在TRAIN上拟合。用户同时授权移除本次D4重算产生的多余文件，范围仅为本研究的独立重算scratch/派生参数及专用代码，不删除数据线原参数、原始数据、323剔除清单、旧实验结果或运行日志。立即推进剩余P0、A1/A2拟合和第一轮筛选；按可用卡启动已就绪臂，其他既定臂随拟合就绪接入同一轮，A5仍由D2触发。首轮当日日报按卡型报告B128实际训练吞吐和GPU整卡实测功耗；B128、<=30%原生SSH与真实磁盘保护继续。
## 2026-11-13 P线用户最新决定：所有后续训练B128

用户在完成不同batch测量后明确选择128，以尽量快并保留OOM余量；本线全部后续P筛选/确认/P′/分子数运行固定batch_size=microbatch_size=128，不再自动放大到160或其他值。任务书、base/protocol与全局HPC技能1.0.150已同步；历史测量保留，评价探针保持任务书冻结的32。尚无新P预训练运行需要迁移；D4原生修正继续，其他工作线任务不改。

### 2026-11-13 用户新规则：20–22 显存≤30%时直接 SSH 启动

用户明确授权：compute-0-20/21/22 被其他用户的小显存任务占用时，登录实际节点按目标 GPU UUID 核实 memory.used/memory.total；≤30%（含30%）则直接 SSH 启动自有任务，无需 sbatch，不再因 Slurm 节点已分配或外来 CUDA 上下文而阻止。>30% 或未知不据此启动。不操作其他用户进程；记录真实原生 PID/start_ticks/PGID/exit，不伪造 Slurm 身份；实际磁盘、inode、账户 quota 和并发峰值保护继续。全局技能 huagong_hpc_requirement 已更新至1.0.149，旧冲突规则在上述范围被覆盖。

P 任务 goal 同时更新：统一增大 P 训练的实际整批 batch，按全部12卡显存和实际 P 前反向峰值确定公共取值并修改任务书/配置；323个重叠分子排除及受影响TRAIN/D4修订继续。旧模型开发任务保持终止。
## 2026-11-13 用户已批准排除重叠并修正TRAIN/D4后继续（最新）

用户对P任务D6(d)明确选择“排除重叠分子，修正受影响的 TRAIN/D4 后继续（建议）”。本授权解除此前9.3等待：排除已识别的全部323个分子（16个完整键+307个既有WP5键），新TRAIN为1194228分子；修订受影响的TRAIN清单及P/Pprime所用D4统计，随后继续完整P任务书。这覆盖原不改TRAIN/不重拟合基础D4条款，其他科学规则保持。采用P研究专用派生清单/归一化，保留原始数据、旧D4和历史结果；不复制或改写大数据、不删除文件。不得恢复旧模型任务或干预独立PR6。此前科学停止记录保留为历史，STOP_D6_OVERLAP.json的resolved=true表示本次授权已收到。
## 2026-11-13 新 P 任务授权（当前）

用户已明确要求完整执行根《模型线任务书 P：P 预训练配方研究（迁移前）.md》，这是终止旧模型任务后的新独立授权。工作树X:/MFM_p_recipe、分支p-recipe；仅P配方研究、任务书指定旧检查点评价/P0及最终P′对照。旧任务不重启；CPU瓶颈PR6由其他工作线独立负责，本线不取消或修改该线作业。以新任务书的科学规则、校验范围、日志文件和六条停止条件为准，禁止额外防御/诊断/试验臂。训练或排队每1800秒查询，阶段结论及时推送GitHub。真实磁盘字节/inode和跨窗口峰值保护继续。保留旧终止记录。数据线与PubChem不变。
## 2026-11-06 用户要求：节点文件传输不得占满磁盘

适用于所有 Codex 窗口、子 agent、CPU/GPU 节点及下载、复制、rsync、缓存、解压和临时输出；执行任何节点大文件传输前必须遵守。

- 在实际目标节点解析目标路径及其文件系统，用 findmnt -T、df -B1 和 df -Pi 检查可用字节与 inode；/tmp、/var/tmp 可能与根分区及 SlurmdSpoolDir 共盘，不能当作独立大容量 scratch。共享盘 df 和账户 quota 不能替代节点本地磁盘检查。
- 估算新增物理占用的峰值，计入源文件、解压/数据库临时文件、旧新文件并存、partial 文件、失败残留及所有窗口已计划/正在进行的同盘写入。跨窗口在同一目标盘协调预留，不能各自拿同一份空闲空间重复预算。
- 根分区默认至少保留 max(10 GiB, 文件系统总容量的 10%) 给系统和 Slurm；站点更严格要求优先。其他文件系统须保留站点要求及覆盖并发增长的余量，既有账户 quota 余量规则继续执行。目标可用量不足覆盖峰值加余量，或无法查明容量时，不得开始复制；换经核实的专用 scratch/共享盘、减小缓存或分批处理。
- 长传输及缓存生成期间持续观察同盘余量，在触及预留空间前停止新增写入并保留可续传状态，不能等到 ENOSPC 才处理。新传输/缓存入口落实容量预检和运行期保护；仅打印 df 不算保护。未核实用途/所有权/依赖的文件不得自动删除，不改管理员目录或自行解除 drain。
- 已核实事故：compute-0-17 作业4526050于2026-11-05 16:33复制约29GB的d7.duckdb到/tmp，留下17,656,872,960字节部分文件并报ENOSPC，同刻节点因SlurmdSpoolDir is full进入drain。compute-0-20作业4526119取消后一个进程未退出并触发Kill task failed；这是不同故障，不误写为该节点磁盘满。

## PubChem current scientific quality and Alpha metadata continuation

For this expansion, preserve the taskbook strict new canonical-record mask fraction above1% stop-and-user-report condition. User removal of per-job Root approvals did not remove scientific quality. Exactly1% continues; source NA/component fractions/robust-z review are separate. Do not add Root approval receipts. Use complete external full-QA reference catalogs and original function-preserving native timing metadata. Alpha compute-local sacct is unusable; the tested native accounting prefix is ssh -n -o BatchMode=yes -o ConnectTimeout=5 218.192.171.238 sacct. Keep1885201 untouched and preserve immutable source/runtime history.
## 2026-11-04 PubChem concurrency follow-up

The user explicitly allows an appropriate increase in computation concurrency when needed. Recheck live free CPU allocations and actual RAM; prefer idle pure CPU nodes. When those are occupied, using idle CPU cores on a free Alpha host in partition all is within this CPU-only continuation, with no GPU request or GPU computation and no paid server. Root's current operational selection is compute-0-2/all 32 CPUs plus sonmi1/cpu 16 CPUs after the current filter, not a permanent user mandate for these counts/nodes. Use disjoint fingerprint search partitions and preserve identical full-reference exact math, source identity, R/N rules and max3 UFF/D recipe. Keep 1885201 running untouched; do not restart the active filter merely to raise its worker count. Update only unstarted downstream plans or deploy a new immutable source for continuation. Root remains the sole submission coordinator; real CPU/RSS/shared quota accounting and the one daily human summary remain.

## 2026-11-04 PubChem exact structure decontamination and direct execution

Current explicit user correction overrides all older composition/wildcard decontamination and per-job Root approval requirements for this expansion. Use only complete InChIKey and the original v1 wp5 key (first 14 InChIKey characters + ":" + final protonation character). Remove every elemental-composition exact/lower-bound and wildcard veto, including MoleculeNet case:18/PDBbind 1pts and case:00/ClinTox. Exclude all PDBbind from decontamination sources because it is outside the planned downstream evaluation. Any downstream record without a determined exact structure contributes no structural veto; exclude it from downstream evaluation and preserve a record-level exclusion list and original evidence.

Stop and archive further 1slg/1pts correspondence research. Rebuild source keys from original physical identity rows (filter PDBbind before insertion so shared keys from other datasets remain), then run one whole-pool filter, directly build R/N queues and the 2.5M first batch, followed by UFF (maximum 3 actual conformers, no filling/retry) and D labels. Keep the existing fixed 1M nearest-neighbor job running in the background; it must not block this expansion. There is no new per-job Root acceptance/receipt or approval schema: keep necessary producer checkpoints/manifests and actual resource/accounting facts, and write one daily summary. Preserve old reports as superseded history. Exact full reference NN math, v1 ranking rules, original UFF/D science and real shared quota/resource protection remain unchanged.

# MFM development workflow

- Read `docs/DEVELOPMENT_HANDOFF.md` and `docs/DATA_PIPELINE.md` first. Develop under `current/phychem_mfm`; root MoE code and `legacy/descriptor` are historical implementations.
- Canonical downstream representation: `SharedBackboneMFM.encode_atoms(batch)` (H0). Preserve source atom order and explicit labels/masks. Do not add task fusion or gates to H0.
- `docs/SOURCE_MANIFEST.json` records exact server exports. Record new source revisions separately; do not silently rewrite historical hashes or checkpoint provenance. Preserve frozen configurations and evidence.
- Keep real data, weights, checkpoints, computed labels, caches, databases and credentials outside Git. Run `python tools/check_repository.py` before committing. Credentials use existing keys or environment variables.
- Server means `zixiao@202.38.247.57:22`; project means `/share/home/zixiao/descriptor_analysis`. `X:\` is its live SSHFS view. Server edits use `X:\`, not the local OneDrive copy. Verify `Test-Path X:\` and key-based `ssh descriptor-analysis-remote` first.
- Linux commands run by SSH after entering `compute-0-20`. Never run server scripts using a local Windows interpreter. Formal computation uses the established Slurm workflow. This source snapshot does not authorize launching experiments or restoring old queues.
- Paid school server `202264640132@202.38.252.202:22` is only for explicitly approved formal pretraining. Recover its existing sbatch workflow before submitting; never use it for development/tests.
- Use the installed `huagong_hpc_requirement` skill for actual server operations. Do not modify/cancel others' tasks or unrelated active WP5 work.
- Normalization and model selection use TRAIN only. Preserve official ExpansionRx membership and source atom IDs. PM7 energy is FINAL HEAT OF FORMATION (kcal/mol); charge is NET ATOMIC CHARGES (e).

### 2026-11-13 P任务D6(d)科学停止，等待用户决定

新P任务已经开始，旧任务仍不恢复。P任务D6(d)一次实际身份比较发现323个TRAIN/下游重叠分子，其中16个完整InChIKey精确重叠、307个仅既有WP5结构键重叠；按任务书9.3停止。新P训练未启动；六个未完成P任务评价作业已取消，结果保留。不得自行恢复P任务或调整TRAIN/D4，等待用户明确处理决定。结果见X:/MFM_p_recipe/docs/p_recipe/daily/2026-11-13.md及runs/p_recipe_20261113/D6_identity.json。独立PR6、数据线和PubChem未取消。


## 2026-11-17 用户长期授权：可使用其他合适的开发计算节点

用户明确回复“允许在其他节点计算，之后的也保持这一规则”。默认开发服务器仍是 zixiao@202.38.247.57；开发、调试、短测、CPU回归及其他已授权计算可按现场空余资源选择其他合适计算节点，不再局限 compute-0-20，后续同类节点选择无需重复询问。compute-0-21 禁用、登录节点禁算、按需CPU/非exclusive、实际GPU UUID与现有任务保护、真实磁盘字节/inode/UID配额和跨窗口预留均继续；不扩大学校付费服务器或完整训练的授权。本次CPU回归可使用compute-0-16/CPU分区/16CPU。

## 2026-11-20 用户授权：A800单卡一小时最终测速

用户取消本线5090新旧测速，明确改为学校202264640132@202.38.252.202上的一个A800单卡、9 CPU、1小时sbatch作业，比较PR8后M2基线与本轮S1–S8实现及不同BS，结束推GitHub作为最终速度结果。此授权覆盖旧学校端禁止测试的冲突条款，仅限本次测速及其必要CPU准备；不授权额外GPU作业或正式长训。学校环境/代码准备使用cpuXeon6458按需CPU作业，不在登录节点计算。沿用a_xk/gpuA800、9核:1卡、现有压缩LMDB原地只读、全部既有FP64数据处理；实际目标盘字节/inode/配额及跨窗口预留保护继续。未运行自有5090作业4535799已取消，不动其他工作线。详见MFM本线docs/perf_sync/USER_DIRECTIVE_20261120_A800.md。

### 2026-11-20 A800选分区补充

用户指出学校A800不止gpuA800一个分区。新A800任务先查sinfo -a、各A800分区的实际节点/资源、当前用户关联账户和分区AllowAccounts；不要只查gpuA800就等待。用sbatch --test-only验证实际账户/分区组合，不产生额外分配；在账户有权使用且资源合适的分区迁移同一个未启动任务。不能把全局空闲节点当作本账户已可分配，也不擅用其他课题组的计费账户。单卡9核、一小时上限、本次仅一个实际GPU分配及实际节点磁盘/配额保护继续。瞬时节点占用与当前账户查询结果写任务记录，不当作永久权限结论。