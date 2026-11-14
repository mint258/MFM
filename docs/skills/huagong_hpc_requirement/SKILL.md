---
name: huagong_hpc_requirement
description: 在华工 HPC（sonmi、zixiao@202.38.247.57）或 PhyChem_MFM / descriptor_analysis 项目上连接服务器、编辑代码、短程测试、提交 Slurm 正式任务、监控模型训练、管理存储或纠正运行规范时使用；涉及既有学校服务器的正式预训练时也适用。
metadata:
  short-description: 华工服务器连接、Slurm 任务、GPU 隔离、训练监控与存储规范
  version: "1.0.158"
  updated: "2026-11-15"
---

# huagong_hpc_requirement

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



## 2026-11-14 P用户最新修订：废止旧首轮，先校准batch/lr/clip及筛选预算

用户已要求立即停止旧第2轮（含SSH与sbatch接管队列），原始输出保留；旧1.5M首轮采纳结论作废，不能作为后续配方选择依据。不得恢复旧第2轮。新校准覆盖本技能较早“固定B128/固定281.73111663818366/筛选1.5M/禁止新增测速”的冲突条款，仅限本次P研究。

- 在此前实际使用的每张GPU上，各测B32（关闭逐层重算）与B128各1000个优化器更新，记录卡型/UUID及实测样本秒；B128沿用现有逐层重算。先完成这批指定测速，不加额外batch或容量扫描。
- B0四组并行，各3M：B32/lr3e-4（关闭逐层重算）；B128/lr3e-4；B128/lr6e-4；B128/lr1.2e-3。在1.5M与3M各评一次既定R1/R3，不改评价协议。
- 每组前5%即150000样本，初始裁剪统一281.7；记录裁剪前梯度范数，在边界取该组p99并固定用于余下训练。阈值拟合状态随完整检查点续接。
- 取3M时R3主分最高组的batch/lr为新固定配置。筛选预算取该配置R3首次达到0.30的样本数，向上取整到0.5M，3M内不达则3M；如何利用额外0.5M检查点的观测按用户后续答复执行。新配置/预算下重跑B0+A1–A5，再按原计划做第2、3轮及放大确认。日报必须有校准表、新配置/预算与按卡型实测吞吐。
- 保留所有已生成输出。测速无需最终权重；四组校准保留0.5M检查点。后续重筛选保留最终/接管检查点及每0.5M原单位VAL记录；确认阶段保留原检查点安排。全局P峰值61GB（模型总峰值114569896448字节），按实际目标盘/账户quota预检和运行保护；未放宽真实磁盘规则、按需CPU/不exclusive、混合接管、其他用户进程保护或付费服务器边界。

## 2026-11-14 最新调度规则：按需CPU，SSH先跑、sbatch接管

后续任务不使用 `--exclusive`，只申请任务实际需要的 CPU。开发集群 compute-0-20/21/22 使用可恢复的混合调度；本节覆盖较早“20–22一律直接SSH/不提交sbatch”的冲突条款。操作前读 [混合调度说明](references/hybrid-scheduling.md)。

- 按实际目标节点/UUID检查Slurm剩余CPU和GPU显存。可分配CPU足够本任务且显存足够时直接sbatch；CPU已被分配、不足本任务时，不论GPU空闲或已有他人上下文，只要目标显存占用≤30%且剩余显存覆盖本任务，就SSH启动并同时提交同一任务的sbatch接管作业。GPU未知或余量不足不启动；不能把MIXED或有一个空闲CPU误当作足够本任务。
- 接管作业排到后请求原训练在下一次完整优化器更新结束处保存完整状态并退出；保存成功、原进程树/自有GPU锁释放后才恢复到真实新job ID下。模型、优化器、学习率进度、采样位置及全部相关随机数状态一并恢复，不从头训练、不双跑。SSH已完成时占位作业退出，不重跑。
- 保持其他用户进程不变；保留真实原生身份、job ID、退出状态及接管关系，GPU成本不重复计入两种句柄重叠时间。当前无GPU GRES时普通sbatch不提供显卡独占；始终按UUID核实实际占用。
- 新任务使用仓库 `configs/p_recipe/scheduling.json` 和 `tools/p_recipe/launch_plan.py`；旧运行未加载接管协议时，仅从已确认完整的既有检查点迁移，并如实记录回退量。磁盘预检/运行保护、5090>4090>3090、B128/OOM96再64及科学预算不变。本规则不扩大学校付费服务器或其他任务的授权。


## 2026-11-14 用户要求：A5/node22从原生运行转为sbatch

用户明确要求当前P研究A5在compute-0-22改为sbatch。按已保存检查点衔接，保留已有训练进度；Slurm分配与检查点就绪前可让已有原生进程继续，不能同时启动两份A5。该要求覆盖本次A5的node22直接SSH启动规则；其余现有任务和其他用户进程不改动。实际核实node22当前Gres=(null)，普通sbatch不构成GPU资源锁；Slurm节点独占需排队，仍无法阻止绕过Slurm的SSH进程。迁移模式和真实句柄以本研究handoff控制文件/执行台账为准，不能把排队提交写成已经完成迁移。

## 2026-11-14 用户最新OOM批量规则

用户明确允许OOM时适当缩小BS至96或64。P训练默认128；实际OOM后的后续尝试先用batch_size=microbatch_size=96，仍OOM再用64，不再受旧“始终固定128”限制；在既有4小时修复盒内执行该OOM降批顺序，其他失败沿用任务书规则。已经正常推进的尝试继续，降批后不自动放大。保留总样本预算、按样本计的学习率、种子、数据与归一化参数，并记录每次尝试实际BS、卡型、样本/秒、功耗及真实退出。已有逐层激活重计算可继续使用；评价探针仍32。空闲GPU优先级5090>4090>3090及显存<=30%直接SSH规则不变。

## 2026-11-14 空闲GPU选择优先级

用户明确：可用空闲显卡按5090 > 4090 > 3090分配。新任务先用可满足显存和现行准入条件的5090，再用4090，最后3090；继续固定B128。


## 2026-11-14 P研究最新决定：停止D4重算，固定11-07参数

用户明确撤回本次D4重算：只在TRAIN分子清单中剔除323个分子，整个P研究固定使用`/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/routes.json`，不中途切换。该决定覆盖此前“排除后重拟合基础D4”的授权；A1/A2/A5自身新增变换仍按任务书在TRAIN上拟合。用户同时授权移除本次D4重算产生的多余文件，范围仅为本研究的独立重算scratch/派生参数及专用代码，不删除数据线原参数、原始数据、323剔除清单、旧实验结果或运行日志。立即推进剩余P0、A1/A2拟合和第一轮筛选；按可用卡启动已就绪臂，其他既定臂随拟合就绪接入同一轮，A5仍由D2触发。首轮当日日报按卡型报告B128实际训练吞吐和GPU整卡实测功耗；B128、<=30%原生SSH与真实磁盘保护继续。

## 2026-11-06 用户要求：节点文件传输不得占满磁盘

适用于所有 Codex 窗口、子 agent、CPU/GPU 节点及下载、复制、rsync、缓存、解压和临时输出；执行任何节点大文件传输前必须遵守。

- 在实际目标节点解析目标路径及其文件系统，用 findmnt -T、df -B1 和 df -Pi 检查可用字节与 inode；/tmp、/var/tmp 可能与根分区及 SlurmdSpoolDir 共盘，不能当作独立大容量 scratch。共享盘 df 和账户 quota 不能替代节点本地磁盘检查。
- 估算新增物理占用的峰值，计入源文件、解压/数据库临时文件、旧新文件并存、partial 文件、失败残留及所有窗口已计划/正在进行的同盘写入。跨窗口在同一目标盘协调预留，不能各自拿同一份空闲空间重复预算。
- 根分区默认至少保留 max(10 GiB, 文件系统总容量的 10%) 给系统和 Slurm；站点更严格要求优先。其他文件系统须保留站点要求及覆盖并发增长的余量，既有账户 quota 余量规则继续执行。目标可用量不足覆盖峰值加余量，或无法查明容量时，不得开始复制；换经核实的专用 scratch/共享盘、减小缓存或分批处理。
- 长传输及缓存生成期间持续观察同盘余量，在触及预留空间前停止新增写入并保留可续传状态，不能等到 ENOSPC 才处理。新传输/缓存入口落实容量预检和运行期保护；仅打印 df 不算保护。未核实用途/所有权/依赖的文件不得自动删除，不改管理员目录或自行解除 drain。
- 已核实事故：compute-0-17 作业4526050于2026-11-05 16:33复制约29GB的d7.duckdb到/tmp，留下17,656,872,960字节部分文件并报ENOSPC，同刻节点因SlurmdSpoolDir is full进入drain。compute-0-20作业4526119取消后一个进程未退出并触发Kill task failed；这是不同故障，不误写为该节点磁盘满。


## 2026-11-13 用户最新决定：后续P训练固定B128

P配方研究本线全部后续筛选、放大确认、P′与分子数运行统一 batch_size=128、microbatch_size=128，无常规梯度累积。该明确决定覆盖此前按最大公共容量选B160的规则；即使4090/5090或其他卡显存更充裕也不自行增大。边界末批按样本预算/500k验证边界剩余数执行；探针按任务书第4节冻结batch32，历史结果和容量扫描保留原值，不改写已完成运行。任务书、配置和跨窗口STATUS共同采用B128；新启动前的实际显存、节点直接SSH规则及磁盘保护继续。

## 2026-11-13 用户新规则：20–22 小显存占用时直接 SSH 启动

适用于开发服务器 zixiao@202.38.247.57 的 compute-0-20、compute-0-21、compute-0-22。用户说明这些节点上当前是其他用户的小显存任务，并明确授权：节点已被占用时，登录目标节点，按实际 GPU UUID 检查 nvidia-smi 的 memory.used / memory.total；目标卡显存占用率 ≤30%（含30%）时，直接在该计算节点通过 SSH 启动本任务，不使用 sbatch，也不因节点 Slurm 已分配或存在其他用户 CUDA 上下文而拒绝启动。此规则覆盖旧的“必须等空节点/无外来上下文/所有大计算必须 sbatch/直接 SSH 只限 node20”在这三个节点上的冲突限制。

- 每次新启动前读取实际显存；用 CUDA_VISIBLE_DEVICES 指定实核的 GPU UUID，并把其他用户现有占用计入本任务可用显存与统一 batch 的余量。占用 >30% 或无法核实时，不依据本规则直接启动该卡上的新任务。
- 现有其他用户进程保持运行；不结束、暂停、重配置或修改其资源。本任务仍协调自己的同卡任务，避免重复启动或自有冲突；不把普通共存自动改为 MPS。
- 直接运行记录真实 PID、UID、内核 start_ticks、PGID、节点、GPU UUID 和 exit code；不用虚构 Slurm job ID/分配/C0。磁盘运行保护只作用于已绑定的自有进程树；实际目标盘字节/inode、根盘系统预留及共享账户 quota/并发峰值规则继续执行。
- 本规则不适用于登录节点或学校付费服务器。其他节点及其他授权边界沿用既有规则；P 任务的1800秒进度查询同时覆盖自有原生进程及仍在运行/排队的 Slurm 作业。

## 2026-11-05 PubChem window-three taskbook v2

2026-11-05 follow-up: the user explicitly authorized one fixed original1000000-query NN computation against the augmented reference, to obtain the before/after distributions for E4.3. This is the only exception to the no-new-NN rule for this task. Preserve all1196122 original reference ordinals as prefix plus all2500000 selected R/N graph fingerprints, original query membership/order, fingerprint recipe, exact integer/full-reference math and self-match semantics. Reuse closed inputs and the existing validated native kernel; no other NN/decontamination audit or new hashes/receipts/independent QA. UFF/D continues unchanged; window-two CPU priority remains.

The root `PubChem 扩充任务书 v2（窗口三）.md` is the latest explicit user authority for this goal. It supersedes conflicting older expansion rules below, including the >1% new-mask stop, hashes, receipts, independent QA, repeated readback and arbitrary memory/time/cost gates. E1 uses the already completed full-pool NN and R/N queues; no new NN/similarity or decontamination audit. First run10k, use measured timing/success to choose concurrency, then complete2.5M UFF/D family Parquet. Preserve the established S-prime numerical recipe, max3 delivered actual conformers, 0.5A dedup, fixed seeds/order, no-fill/no-retry, D20 once and D3/atomicSASA per actual conformer. Physical masks are report-only. Deliver one path/size/row-count manifest and one-page GitHub batch report; daily<=onepage; costs weekly. No QM/Pprime/training-format export or v1 data changes. CPU priority is below window-two v1 work. Only deletion of existing files, scientific rule/label change, paid-school-server use or formal pretraining requires asking. Own superseded job-chain cancellation at a verified zero-native-work boundary is an execution update, not deletion or scientific rollback. Keep branch data-v1-pubchem-completion-20261103 and draftPR1 unmerged; append E2/E4 notices to shared STATUS. Ownership is workflows/expansion and docs/expansion. User taskbook overrides inconsistent historical AGENTS/skill evidence rules.


## 2026-11-05 Window two taskbook v2 (current)

The user explicitly requests completion of the root `数据线 v1 任务书 v2（窗口二）.md`. It supersedes conflicting historical data-line rules below. B1/B2 are first and parallel; B3/B4 proceed in background; B5 follows B1/B3/B4. Resume D6 and the missing first-two S-prime Pprime scope; do not recompute closed Pprime. PubChem is window three and out of scope. Producer-only single numeric/alignment/leakage checks; no new content hashes, receipts, per-job acceptance reports, independent QA, second rereads or throughput benchmarks. No artificial memory/wallclock/cost stopping gates. New logic gets unit tests; one full regression before a PR. Use TRAIN only and no downstream TEST results. Stop to ask only for deleting existing files, scientific changes, paid school server or formal pretraining. Do not delete anything under this task's authorization. Earlier v30 cleanup was already completed under historical user authorization; preserve its history and current v31 products. Keep the one daily summary to one page, push each completed task, append only to shared STATUS.md. Root coordinates submissions; parallel preparation of D3/D5 follows the existing agent assignment. Keep data out of Git and other windows' jobs untouched.


## 2026-11-05 user-authorized D-3 v3.0 retirement

After v3.1 delivery, the user explicitly requested deletion of the old D-3 v3.0 export and its unused intermediate artifacts, followed by a remaining-storage report. This supersedes the earlier requirement to retain v3.0 and its GPU copies for this cleanup. Preserve original native LMDB and WP5 Parquet sources, current v3.1 shared/GPU products, D2/D4/D5 metadata/configuration and historical manifests. Exact old export LMDBs, derived F64 sidecars, obsolete projection/merge SQLite files, known old node-local copies and redundant closed v3.1 write scratch may be removed after path/ownership/dependency checks. Keep cleanup facts in the same daily summary; report per-account quota headroom separately from whole-filesystem space. Do not generalize this authorization to other datasets, active tasks, or original source data.

## 2026-11-05 D-3 v3.1 compact re-export (earlier export rule)

For the same frozen 50,000 TRAIN and 5,000 ROUTINE VAL, replace storage only using MFM4, one default LMDB per split, shared schema and external ID maps. Preserve science, fields, masks, orders and D5 holdouts. User approved r73's four ordered numeric arrays (shared pair row, integer channel codes, tristate onsite, F32/NaN values); dictionary belongs only in schema. WP5 F64 Parquet remains authority; do not add F64 copies or delete/overwrite v3.0 or its GPU copies. U records currently contain geometry only, not independent full P-prime data.

Exactly one export-end check suite: alignment/topology differences, 1,000 PM7 records against v3.0 with original masks and abs/rel 1e-6, and counts. Each split gets one mdb_copy -c. No new SHA, independent reread/QA job, throughput test or alternative compression. Existing SHA references are copied, not recomputed. Expected 10GB / 20KB per P is report-only. Distribute with rsync --sparse. With --protect-args, the rsync ssh transport MUST preserve stdin (no ssh -n); standalone ssh commands can use -n. Ordinary transport recovery resumes the already validated compact files without repeating export, compaction or numerical checks.

User says only stop to ask if scientific content must change or old files must be deleted; ordinary format/resource/tool fixes proceed and get one line in the daily summary. D6 and later remain paused until explicit resumption. Final report includes du, mean M/P/U bytes, full-population descriptive size extrapolation and export elapsed; Model loader and per-head overfit are the actual downstream acceptance. Latest user specification overrides the older D3 v3.0 SHA/throughput/checksum and STOP2 requirements below.

## 2026-11-04 expansion scientific quality and complete metadata correction

The root taskbook explicitly stops continuation and reports the user if any field has strictly more than1% anomalously NEW canonical record masks. Current user overrides removed time/cost/failure-count stops and per-job Root approval files, not this scientific condition. Earlier report-only expansion wording was an implementation error, not user approval. Check100*newly_masked_records>canonical_records before full continuation and final closure. Exactly1% continues automatically; source NA, component masks and robust-z review are separate. Keep all results and report concrete counts if the condition actually occurs. No Root approval receipt is added.

Full QA writes complete newline-closed family/batch reference catalogs with SHA, row counts, sameFD frames and EOF validation, rather than oversized inline arrays. Pilot/legacy small inline results remain compatible. New native timings annotate existing return events without extra native calls or journal fsync; original kernel arguments/results/core/native science stay unchanged. Legacy unmeasured timings remain unknown, not zero. Native metadata accounting on Alpha compute-0-2 and sonmi1 uses the tested prefix ssh -n -o BatchMode=yes -o ConnectTimeout=5 218.192.171.238 sacct because local localhost:6819 queries failed. Keep1885201 untouched; only pending UFF jobs were replaced.


## 2026-11-04 PubChem concurrency follow-up

The user explicitly allows an appropriate increase in computation concurrency when needed. Recheck live free CPU allocations and actual RAM; prefer idle pure CPU nodes. When those are occupied, using idle CPU cores on a free Alpha host in partition all is within this CPU-only continuation, with no GPU request or GPU computation and no paid server. Root's current operational selection is compute-0-2/all 32 CPUs plus sonmi1/cpu 16 CPUs after the current filter, not a permanent user mandate for these counts/nodes. Use disjoint fingerprint search partitions and preserve identical full-reference exact math, source identity, R/N rules and max3 UFF/D recipe. Keep 1885201 running untouched; do not restart the active filter merely to raise its worker count. Update only unstarted downstream plans or deploy a new immutable source for continuation. Root remains the sole submission coordinator; real CPU/RSS/shared quota accounting and the one daily human summary remain.


## 2026-11-04 PubChem exact structure decontamination and direct execution

Current explicit user correction overrides all older composition/wildcard decontamination and per-job Root approval requirements for this expansion. Use only complete InChIKey and the original v1 wp5 key (first 14 InChIKey characters + ":" + final protonation character). Remove every elemental-composition exact/lower-bound and wildcard veto, including MoleculeNet case:18/PDBbind 1pts and case:00/ClinTox. Exclude all PDBbind from decontamination sources because it is outside the planned downstream evaluation. Any downstream record without a determined exact structure contributes no structural veto; exclude it from downstream evaluation and preserve a record-level exclusion list and original evidence.

Stop and archive further 1slg/1pts correspondence research. Rebuild source keys from original physical identity rows (filter PDBbind before insertion so shared keys from other datasets remain), then run one whole-pool filter, directly build R/N queues and the 2.5M first batch, followed by UFF (maximum 3 actual conformers, no filling/retry) and D labels. Keep the existing fixed 1M nearest-neighbor job running in the background; it must not block this expansion. There is no new per-job Root acceptance/receipt or approval schema: keep necessary producer checkpoints/manifests and actual resource/accounting facts, and write one daily summary. Preserve old reports as superseded history. Exact full reference NN math, v1 ranking rules, original UFF/D science and real shared quota/resource protection remain unchanged.


## 2026-11-03 PubChem return to recovered Alpha

The user reports Alpha recovered and explicitly asks to inspect prior results and prefer Alpha for continuing this PubChem goal when usable. Alpha is alpha@218.192.171.238:22, UID1264, root /gfshome/alpha/codex_data_v1_20261026; Main remains UID1278. Both login hosts say sonmi, so authenticate by endpoint/UID/source roots, never hostname alone. The original124857440-row/502-Parquet source and COCONUT1885088/1885095 artifacts were freshly inventoried; old24h materialization timed out and is not a complete pool. Reuse verified closed scientific results and use new independently admitted Alpha runtime. Do not transplant Main UID/proofs or symlink fake Main paths. Root stopped only duplicate Main RAW4525652 after validation and preserves all outputs; Main Common4525659 may finish against its canonical inputs.

Prefer fresh idle CPU nodes; sonmi1/cpu was observed idle16 CPUs with about125GiB actual RAM, while Slurm RealMemory=1 is not trustworthy physical capacity. Resource availability is temporary. Gluster gv1 has directory quota/deem-statfs enabled; bind native volume configuration and /gfshome/alpha directory statfs to the effective2TiB limit, not the31TiB whole-volume banner. No admin/quota/security settings are changed. Alpha home contains string.py: use Python-I or the isolated absolute entry with exact clean code cwd; never run from home or delete its files. Root owns deployment and Slurm submission. The scientific recipe/max3/no-fill/no-retry/noQM and goal-specific removal of arbitrary wall/retry limits remain unchanged; other goals and paid training remain separate.

2026-11-04 operational follow-up: do not run external full-table progress counts against an active DELETE-mode SQLite writer. A 16.5-second read lock caused the own baseline writer to fail its commit; its committed prefix was preserved and completed by actual1885167C0. Prefer producer logs or OS/file metadata while running; inspect exact database counts after the writer is terminal, or on an independent closed backup. A producer's Slurm C0 alone does not accept a scientific reference: actual1885153 preserved119 graph HOLDs, so its1196003-row projection cannot be advertised as the full1196122 Common reference. Reuse the closed journals for an independent audit; preserve original HOLDs and receipts.



## 2026-11-03 D-3最新用户授权：compute-0-21、不设时间或内存停止门

本次D-3及其替代/续接作业已获用户明确授权使用compute-0-21、partition=all、16CPU，不使用GPU；直接sbatch排队，不以当前空闲CPU作为提交门。用户明确要求不再设置任务时限或任何内存限制：不设置SBATCH时间/内存大小，不保留程序总墙钟、有限配额服务寿命、RSS或MemAvailable阈值导致的停止。资源观察只作遥测；观测暂不可用或实际存储暂不足时等待恢复，不因这些人工资源门结束科学任务。300GB只作未来存储估计，不作任务输出硬停；实际账户quota扣除全部未来预算后保留100GB的既有要求继续执行。
科学标签、筛选/掩码、r73权威F64及单次F32、r674 LOSS_DISABLED保持；导出末尾一次计数与1000条原Parquet逐字段校验、一次总清单SHA、一次rsync --checksum及一次不超过5分钟的读取测量保持。这里取消的是D-3计算任务与程序资源时限，不改科学计算配方或其他任务的独立授权。不得修改/终止其他线程或模型作业；同账户并发的未来存储应合并核算。


## 2026-11-03 PubChem CPU-node preference and compute-0-21 approval

For this PubChem expansion goal, the user explicitly approved compute-0-21 for CPU-only statistics, screening and UFF, initially 32 CPUs through Slurm in partition all, with no GPU request. The user subsequently requested idle CPU nodes first and confirmed using 21 when none were available. Recheck CPU availability before future submissions; prefer an available CPU node, otherwise compute-0-21 remains authorized for this goal. This overrides the old compute-0-20-only rule only within this goal. Do not cancel or modify other jobs. CPU availability is a temporary observation, not a permanent cluster fact.



## 2026-11-03 PubChem扩充全任务续接（当前用户授权）

用户要求完成根《数据线工作流程：v1 定稿与数据扩充（Codex B）.md》第二部分2.1–2.9全部工作，并把代码、报告、清单和结果索引推送GitHub。第一批按原默认共250万分子、R/N各125万；固定队列累计1000万；只做UFF和D、不做QM或训练。用户随后覆盖2.6节：每分子最多3个UFF构象，固定种子和生成顺序，0.5Å去重；不足3个按实际数保留并标记，不补足、不重试；保留已有构象以便今后去重后追加第4个及以后。D20每分子一次、D3逐实际构象，P′本阶段不算。大数据按原要求留仓库外，Git保存清单与哈希。

本次扩充覆盖旧24/48小时人为任务上限、4小时诊断时限、连续两次失败STOP2和基于旧成本倍数的自动停审：可修复问题持续修复并从真实关闭检查点续接，不能因旧超时或次数门自行停止。集群真实MaxTime/调度限制如实查询；如有限，使用检查点正常收尾和续算，不假称已移除站点限制。原科学版本、筛选/去污染完整性、确定性UFF配方、质量标准和真实资源/配额保护不变；不扩大到付费服务器或其他任务。旧失败及UNKNOWN原样保留，不能借授权把未验收结果改成成功。

本次标准X重连错误85；已用本机127.0.0.1:22369的nativeSSH SFTP适配恢复Y，受信别名仍为descriptor-analysis-remote。Y和原服务器AGENTS.md的80738字节/SHA256 9d41b45666ad98397dd5721b9248d1737d5f55b3d831690b520127df9dae2114实核一致。按既有规则在局部PowerShell创建逻辑X指向Y并解析后编辑；不写OneDrive副本、不强拆旧挂载。适配器为C:/Users/mint/AppData/Local/Temp/pubchem_expansion_sftp_bridge_20261103.py，仅本机监听；其存活是瞬时事实，使用前重新核验。


## 2026-11-03 本轮D-3最新简化交付（用户六条，优先于下方旧门）

本轮固定已选的50,000 TRAIN＋5,000 ROUTINE VAL，按D-1 v3.0由一个Slurm导出作业完成LMDB。脚本末尾只校验一次：记录/分子/构象计数与清单一致，随机1,000条与parquet逐字段比较，并生成一份总清单SHA。取消旧Source3生产前套件、10,000条门、16-reader复核、F64全量二次读回和独立复核作业；已通过的旧检查保留历史，不重做。

吞吐只测一次、总计不超过5分钟。用rsync --checksum复制到GPU节点，一次完成，不追加复制后哈希复核。模型线加载器和逐预测头过拟合测试作为交付后的实际验收，只有在那里发现问题才回查数据。失败直接修复并重跑，不能再用本轮导出旧STOP2/4小时工具修复规则阻止续接；失败只在同一每日汇总记一行，不另写报告或加审批层。

D-3与D-5仍由已授权子agent并行准备，Root统一提交；D-5采用同样的一次1,000条（不足则全部）末尾校验，不重复吞吐。科学标签/掩码/过滤/角色、r73有序F64权威与单次F32、r674 LOSS_DISABLED保持。真实CPU/存储安全和100GB账户余量继续执行；不改变P′的独立科学规则或付费服务器授权。


## 2026-11-03 MAD完成即交接，D-3与D-5并行

用户要求“算完MAD以后就直接开始算剩下的D3D5吧，要尽量快”，并明确要求调用子agent并行处理D-3与D-5。本轮完成首遍完整TRAIN统计（含元素参考、精确缩尾分位数、均值/标准差、按元素统计、中位数/MAD）后即闭合D-4，不再执行实现额外增加的第二遍全量统计。指南要求可从parquet复现相同结果，并未要求生产验收时把所有统计完整计算两遍；保留原Source6、原统计定义/质量阈值、源与计数校验和D-3的一万条逐字段读回，不增加新的等待门。交付元数据必须如实写单遍、未作完整第二遍、independent_numeric_replay_equal=null，不能把首遍引用复制成两份充当独立复算。

D-3与D-5各交给一个子agent，复用同一冻结人群、已关闭几何和typed source；D-5不等待D-3全量载荷完成。Root统一实际提交和共享资源预算，先防止旧串行watcher重复提交，再在可用CPU节点并行运行两个日级父作业（每个至少16CPU、无SBATCH内存申请）。D-2尺寸相关性放在CPU导出路径内或并行处理，不阻塞已完成的D-4统计发布。r674保持LOSS_DISABLED，缺独立审计明确标待补，不追加QM、不编造完成状态。


## 2026-11-02 本轮D-4获准在主节点执行

用户明确要求D-4直接在主节点完成；本轮允许在Main的sonmi登录/主节点运行D-4，覆盖旧“登录节点不运行计算”的该项限制，不扩展到D-3/D-5、P′或付费服务器。Root在既有授权下按实测资源选择并发，用户没有限定为2核或8核。当前已由8并发自然收尾后续接至16并发，CPU亲和性0–15、BLAS/OpenMP各1线程、nice增加10；主节点20核，准入实测负载低于12、可用内存超过80GiB，保留至少4核余量。当前真实PID1415773、start_ticks8241327218，原Source6为6项全部通过，实测约15.9核；复用上一query的62个已关闭分组，不重做几何。此前2至8并发时复用的131组与原失败/停止历史保持。保留原3GiB每工作进程、56GiB输出、100GB账户余量、科学规则和本轮指南要求的首遍完整TRAIN统计。不得把Root运行资源选择误记为用户的固定核数要求，也不得把主节点权限扩展到其他任务。

后续分位数细化必须清除上一query的已完成分组缓存，只复用同一query的报告。当前私有实现对单值直方图和F64字节哈希作等价优化，原科学函数文件未改；原6项中的同一测试用例已包含与原实现逐位一致的字节/全部radix轮次对照，仍仅6个用例。保留原16位首轮及8位细化、中位数/MAD与全部质量规则。不要把实现优化描述成所有运行路径都直接使用原函数对象。

本地执行必须记录真实PID、UID、start_ticks、CPU亲和性和实际进程exit码；不得伪造SLURM_JOB_ID、Slurm分配或C0。原6项Source、原统计定义/阈值与本轮首遍完整TRAIN统计仍须通过；本轮真实本地exit0及完整统计验收可替代Slurm C0。读取 `runs/data_v1_20261025/control/current_work_state.json` 的D4_actual_headnode_current及其实际launch/proof/exit，先验证实际进程，勿按旧CPU等待状态重提。账户余量100GB临时政策、56GiB输出和其他授权边界保持。


## 2026-11-02 本轮D-4持续交付与临时账户余量

用户明确要求“保证D-4完成后再停止”。本轮D-4资源/工具修复与真实续接持续到暂定D-4交付，不再因旧60分钟窗口或例行失败计数自行转为停止；科学质量、真实资源保护、失败状态及可比试点2倍计算用量确认线保留。完成须有原6项Source、实际完整终态（Slurm C0或本轮获准主节点进程真实exit0）、首遍完整TRAIN统计及其真实验收并发布归一化文件（最新单遍规则见上），不能以语法检查、已写字节或等待进程代替。

用户另明确把当前Main数据线账户预留空余临时由200 GB降至100 GB（100000000000字节，扣除全部未来预算后）；D-4单作业输出仍56 GiB。记录在 `runs/data_v1_20261025/repository/configs/data_v1/user_temporary_account_quota_floor_100GB_20261102_v1.json` 与 `runs/data_v1_20261025/control/current_account_quota_floor_policy.json`；保持真实quota读数与全部未来预算，不伪造可用空间。此条覆盖本轮旧200GB要求，其他任务/服务器不从中推断新授权。

P′的STOP2修复仍待单独批准；D-4授权不用于重开P′、修改科学规则或使用付费服务器。原始数据与完整检查点保留，可明确回收已关闭、未验收且能从完整检查点重建的派生部分文件，避免把多个失败部分文件累积进后续输出上限。


## 2026-10-30 数据线双集群并发与 P′ 放行

用户已明确将 P′ 全12项成功率放行门设为99.45%；原2,000构象1989成功达到该门，允许开始正式数据生成。原版本、关键词、精度、输入、种子、900秒超时及其他科学阈值不变；保留11项失败及原试点结果，不重算。当前规范记录在 `configs/data_v1/pprime/user_release_9945_20261030.json`。

用户随后要求提高并发，使用 zixiao 和 alpha 两个免费集群当下可用CPU。依实际空闲CPU安排互不重叠的分子/物理构象分片，复用已完成结果；按每节点约一天的父作业打包并复用内部进程池，不以小批次创建短作业。沿用无SBATCH内存申请、CPU-only、不超占CPU、不动他人或模型作业、配额200GB余量和实际本地scratch/RSS观察。D-2至D-5优先交付不变；原计算用量超过可比试点估计2倍的确认线不变，不把增加并发等同科学规则或付费训练授权。


## 2026-10-29 数据线 v1-pilot-provisional 的最新用户规则

本节仅覆盖本轮数据线旧条款，保留无关模型线规则。以用户本次确认起48小时为期限，优先交付 D-2正式注册表、D-3固定50,000 TRAIN+5,000 VAL导出、D-4仅试点分子的暂定归一化、D-5嵌套清单与已见分子未见构象诊断集；统一版本 `v1-pilot-provisional`。共同人群、D-6/D-7、MoleculeNet/COCONUT/PubChem/P′均不得阻塞这四项。

- r674保持`LOSS_DISABLED`，不再追加QM诊断或现在做质心变换。平移变化在净电荷或偶极非零时是预期，不据此判数据错误；D-6后才考虑标准质心原点换算。
- P′原2,000构象试点已获直接运行授权：沿现有路径检查，将conda、xTB、MOPAC安装目录及其配置列为明确、只读白名单；修复后重跑原试点，不重做路径检查框架，不改变原版本、关键词、输入和科学阈值。
- 合法软件只读路径/权限误拦、换行/schema分类/SQLite或缓存资源上限、工具自身读写不一致，直接修复并继续，不逐次申请确认；每日汇总只记一行。
- 任一诊断或修复累计4小时或连续失败2次即停止该问题，记“未解决”，采用保守默认继续其他工作；后台去污染有问题且不影响交付时挂起。
- 每天一份进度汇总，每周一次记账；收据和SHA仅用于正式交付物，不另建逐失败报告或额外审核链。现有作业内持久检查点和正式交付所需来源绑定继续使用。
- 科学标签或筛选规则的修改、付费服务器、计算用量超过试点估计2倍仍须用户确认；本轮旧一般1.5倍报告继续条款以此新2倍确认线为准。CPU空闲节点、无SBATCH内存、日级打包和不修改他人/模型作业规则不变。


## 2026-10-29 模型线用户主线修订 v3（优先于下方旧操作门）

用户最新明确授权，完整记录为 `runs/model_v3_20261026/MODEL_LINE_USER_AMENDMENT_V3_20261029.md`，模型仓库为 `docs/model_v3/USER_MAINLINE_AMENDMENT_V3_20261029.md`。

- C4唯一硬门是FP64相对误差≤1e-9；实际4524734已48/48通过，C4立即PASS。FP32只报告逐分子/字段范数相对误差及p50/p99/max，标量分母加入实际字段TRAIN标准差，不判通过失败、不阻塞；旧v1/v2原样归档，不重跑。
- 零或近零参考使数值门失去意义、或门与已证明数学性质冲突时，直接改为范数/字段尺度规则，当日DAILY写旧门、问题、新门与理由，无需重复确认。科学DECISION_RULES、TRAIN-only和不看TEST保持硬性。
- 日志审计、W&B同步、SDK读回、记账、fixture、SHA校验均为非阻塞项，只记录真实状态，不能阻塞科学下一步。W&B每天集中一次，记账每周一次；不再逐作业堆叠审计/发布前置层。实际资源、所有权、GPU进程/公共锁、RSS、显存与配额保护仍执行。
- 任一诊断/修复累计超过4小时或连续失败2次，即在DAILY标“未解决”、保守保留旧路径并继续主线；除用户明确要求，不再新增数值精度候选分支。
- 当前优先为A类已通过项采用、按显存自动checkpoint、通过的HeadOff采用；三卡3090/4090/5090同真实批次、checkpoint全关各测C1-a一次；首seed20个阶段5配置静态就绪。D3实际到达后每配置50有效更新接线冒烟，24小时内真实阶段3及三卡SDP2000；D5到达启动阶段5，不伪造数据或前序胜者。
- r674保留预测头、LOSS_DISABLED、不再追加处理。改变科学DECISION_RULES、付费服务器、GPU用量超过估计3倍、正式预训练仍须用户确认。


## 2026-10-29 模型线开发 GPU 也采用自动内存（用户后续明确授权）

用户已明确回复“采用方案，GPU 也用自动内存”，批准 `runs/model_v3_20261026/MODEL_GPU_AUTO_MEMORY_PLAN_v1.md`；实际授权记录为 `runs/model_v3_20261026/MODEL_GPU_AUTO_MEMORY_USER_APPROVAL_20261029_v1.json`。此节覆盖下方“GPU规则不变”中开发服务器模型线 GPU 的固定声明内存条款，不适用于学校服务器或正式预训练。

- 新作业省略 SBATCH、sbatch argv 和继承环境中的显式内存大小声明，不用 `--mem=0`，不加 exclusive、overcommit 或 oversubscribe。真实默认 ReqMem/ReqTRES/AllocTRES照实记录，不把默认值写成有限物理内存保证。
- 原软件预算不增：普通 A 验证/性能作业64GiB、RSS56GiB；Native B32GiB、RSS28GiB。新软件预算加已登记自有并发 GPU 软件预算须低于节点 RealMemory 的85%，其他用户已声明的有限内存也纳入；自有自动声明不能计成零预算，不双计已有有限声明，未知声明不虚构有限保证。
- 每次提交与启动继续实际核验 MemAvailable，至少保留原软件预算加节点15%余量；保留16CPU、GPU实际UUID/进程/公共锁、显存85%、原墙钟、进程身份、双2GiB输出/私有目录及quota/全部未来存储预算保护。
- 先冻结并公开新资源版本和方法再提交；原模型、数据、种子、优化器、20批/500步、R1、W&B和科学误差门不变。原冻结源、结果、失败和正在运行的分段不改写；Native后续段须在安全边界用新操作版本续接，不能重复提交。旧PENDING作业不自动改写或取消，须逐项核验真实源资格与防重复条件。

## 2026-10-29 模型线 CPU 验证采用自动内存（覆盖旧 CPU 声明内存门）

用户已明确回复“模型线 CPU 也使用自动内存（建议）”，批准 runs/model_v3_20261026/MODEL_CPU_AUTO_MEMORY_PLAN_v1.md。此节只扩展到模型线 CPU 源码检查、完整回归和验证；GPU训练/微调及学校正式预训练的资源规则不变。

- CPU验证按现场cpu分区的可用节点提交，仍至少16CPU、Root统一调度，不超占已有CPU，不使用exclusive。当前节点范围为compute-0-2、8–19，运行前按sinfo/scontrol核验。
- 新CPU sbatch不声明--mem、--mem-per-cpu、--mem-per-gpu或等价固定内存，不通过SBATCH内存环境变量隐式申请。原CPU全用户声明内存85%门不再用于提交/启动准入；其他任务声明0或无上限不因此阻止提交。
- 真实默认内存及ReqMem/ReqTRES/AllocTRES如实记录；默认0不是有限物理内存保障，不能写成已申请或获配16/32GiB。软件工作预算、实际MemAvailable观察、RSS、private/output和quota保护继续保留；源码检查原RSS12GiB、完整回归原RSS24GiB及四个pytest子进程不变。
- 旧请求、脚本、失败和会计全部保留。仅对新鲜核验仍属本任务且PENDING、未开始、未获配的原checker，可按已批准方案以同jobID更新MinMemoryNode=0并记录前后真实回读；RUNNING/终态不修改、不终止。已C0的4626/4660按原16GiB执行事实验收，不伪称自动内存运行。
- 完整回归原32GiB硬绑定须独立资源版本后再用；新自动内存request/proof不冒用旧32GiB证明。只修改声明、准入与来源记录，不更改科学阈值、全量测试/源码范围、exec/JUnit证明、fixture重试和稳定内核身份规则。
- 本次授权不改变A梯度v2的另项已批准规则、原A5 FAILED、C-only bias删除、GPU UUID/公共锁、D1权威或正式预训练授权，原完整Stage0–7目标继续。下方模型段旧CPU声明内存85%表述为历史，本节优先。

## 2026-10-28 正式数据任务按一天打包（覆盖旧碎片提交方式）

用户明确纠正：正式数据任务应控制在一天左右；当前剩余 S′ 补齐可以合并成一个 sbatch，不再按每500个分子拆成大量短作业。

- 对数据扫描、构象生成、标签计算和批量导出，按实际资源及已测吞吐把一次正式 Slurm allocation 的预计工作量打包到约24小时；本轮剩余 S′ 使用一个24小时上限的 sbatch。若剩余工作不足一天，在同一作业内提前完成，不为凑时长增加数据或重复计算。超过一天的工作按日级续接；单作业原48小时硬上限仍有效。
- 分子、行组、源文件、500分子小批次可作为作业内的调度与持久检查点，不能因此各自创建 sbatch、作业数组元素、独立排队或反复执行相同前置核验。一个父作业内复用进程池和已验证只读输入，按实际获配CPU有效并行，控制BLAS/OpenMP线程不超占。
- 先用已关闭成果、真实终态和分子/配方/种子/几何来源核对剩余清单；复用已完成产物，明确保留失败和UNKNOWN。新父作业记录真实单一job ID及内部检查点，不伪造小批次的Slurm子作业或C0，不重算已经完成的样本。
- 保存逐分子结果、失败原因、原子提交的检查点与恢复游标；接近墙钟上限时停止领取新分子并让已开始计算自然收尾。接续从已持久游标和原始once记录恢复，不从头重跑。
- 短作业只用于确有必要的环境检查、有限诊断、源码测试或独立验收；不能把这些例外推广成正式生产的分钟级碎片。调度改造复用原科学函数、版本、配方、阈值和既有结果，完成一次必要验证后落实实际长作业，不循环增设前置审核层。
- 继续按现场空闲CPU选择已授权节点，至少16CPU，不申请SBATCH内存或exclusive；CPU-only、实际RSS/配额保护、至少200GB存储余量和不改动他人/模型作业的规则不变。资源发布器等辅助服务的真实剩余寿命须覆盖该长作业及收尾，使用独立有界实例，不伪造续期或修改运行中的科学任务。

## 2026-10-26 核时超过试点估算1.5倍：报告后继续

用户在看到本轮12个标签分片的实际核时超过外推估算1.5倍及证据后明确答复：“核时超标报告后继续，质量阈值不变”。这是本轮数据线的新授权，覆盖下方旧“任一批实际分配核时超试点估算1.5倍就停止”的规则。

- 对这项分配核时超标，保存实际父任务会计、试点外推依据、超标倍数与并发等限制，如实报告后继续。不得再仅因这项超标停止派发或要求用户重复批准。
- 由同一1.5倍成本规则派生的执行软停止也应在新的独立版本中改成超标观察/报告；保留历史请求、源码、结果与停止记录，不改正在跑的任务。不把新授权写回旧回执。
- 免费不等于实际核时为零；FAILED/TIMEOUT、启动等待、重试与核验都完整计入。费用授权不构成科学成功或接口验收。
- 数据质量阈值、UFF/QM配方与版本、图/立体/去重、坐标参考系/单位/标签精度、共同人群排除率、既有Se例外及试点成功率均不变。P′当前坐标协变矛盾仍须独立核清，不能用本条放行。
- CPU节点与无SBATCH内存申请、至少16CPU、不超占已分配CPU、单作业最长48小时、CPU-only、200GB存储余量、不强行终止运行作业及不动其他/模型作业的规则继续有效。

## 2026-10-26 当前集群免费及新增 alpha 集群授权

用户明确说明当前集群计算没有金钱费用，可直接使用；并授权尝试登录 `alpha@218.192.171.238:22`，成功后可在该集群提交部分新数据生成任务。认证信息只在交互式认证中使用，不保存密码到技能、项目、脚本、日志、命令历史或提交内容。

- 原数据线继续按空闲CPU及下节无内存申请规则执行，不因金钱预算停交任务。核时、每条记录耗时和成功率仍如实统计，用于指南的效率/科学验收，不解释为收费金额。
- 新端点已实际登录，UID为1264，hostname/ClusterName也叫sonmi，但它与原 `descriptor-analysis-remote` 是不同集群。必须用端点、用户、真实UID、实际job/node/source分别绑定，不把两边同名node、jobID或sonmi混用。
- 新集群CPU分区实际节点为compute-0-1、3–6及sonmi1；按每次现场空闲CPU提交、至少16CPU、无SBATCH内存或exclusive申请、CPU-only、单任务不超过48小时。不把原集群11–19节点白名单套到新集群。
- 新集群先提交真实CPU环境/存储检查，再隔离准备与原科学版本一致的环境、受控重放；原UFF配方、RDKit2025.09.5、WP5程序/关键字和数据质量阈值保持。已有环境和用户数据不覆盖，不因能登录就把环境检查当作新科学数据已生成。
- 新集群新run目录为 `/gfshome/alpha/codex_data_v1_20261026`。`/share`用户配额现场已超限，不往该位置存新数据；新挂载目录须独立实测可写、有效剩余容量及存储上限。环境检查1884759已在compute-0-1实际C0/34秒/16CPU完成；兼容环境构建1884760已实际提交。正式数据输入/输出须哈希校验、分片互斥、保持全局顺序与全部会计，避免两集群重复计算同一科学任务。
- 学校付费预训练服务器202.38.252.202仍禁止用于本轮数据工作；新增alpha集群授权不构成正式预训练授权。原X盘只映射原zixiao端点，不能把X盘编辑当作已同步到alpha集群。
## 2026-10-26 最新数据线 CPU 与自动内存规则（覆盖旧条款）

用户最新明确要求：“只要CPU节点现在有空余CPU，那就把任务先提交上，不一定非要满足内存要求，内存节点会智能调配，在sbatch任务里不要指定要用的内存大小”；随后补充：“实际上我认为11-13节点也可以作为可用cpu任务节点，请你在skill里更改一下这一点并将其落实”。

- 本轮数据线的一般 CPU 分析使用实际 cpu 分区节点（当前为 compute-0-2、8–19），明确包含 compute-0-11、12、13。原先 S′/UFF/QM 仅14–19的限制现扩展为11–19。节点是否空闲必须每次从 sinfo/scontrol 实测，不把此刻快照当永久状态。
- 按空闲 CPU 安排并提交，每任务仍至少16CPU；新 sbatch 不指定 --mem、--mem-per-cpu、--mem-per-gpu 或等价内存大小，也不通过 SBATCH_* 环境变量隐式申请内存。不用 exclusive/user 整节点隔离阻挡本可共享的空闲 CPU；不得 oversubscribe 已占 CPU。
- 取消本轮提交和启动时“必须申请64GiB”“全部用户声明内存≤85%”的准入门槛；其他作业内存为0/无明确上限不再因此阻止提交。实际默认内存/环境值如实记录，不伪造已申请或获配64GiB，也不把默认0说成物理内存保障。
- 保留真实 RSS/MemAvailable 运行观察；算法工作内存/软件软上限与 Slurm 申请区分记录。紧张时停止新派发、自然等待在跑工作结束，不强制终止运行任务。保留实际 quota 至少200GB余量、≤48h单任务、CPU-only、禁止学校付费服务器及不动他人/模型作业的约束。
- 本次只改变资源调度：原 UFF/QM 配方、程序版本、task/seed、Se单元素例外、ROUTINE整分子VAL和所有科学成功率/排除率/实际成本阈值不变。
- 已登记旧64GiB/85%请求、脚本和历史回执原样保留。只对核实仍PENDING的本任务旧作业做hold/取消替换；已运行任务不终止。用新名字、新资源权威和真实无内存申请的 request/proof 重提，不能仅删sbatch内存行却继续假用64GiB guard/proof。Root统一提交并记清新旧映射与全部成本。
- 此处用户明确要求同步技能，授权本机技能与服务器 docs/skills 对应副本的这次更新；数据生产代码仍只改指南允许的六个仓库目录。下方旧64GiB/85%与14–19记载仅为此前工作历史，本轮后续以本节为准。

## 2026-10-25 数据v1 CPU节点纠正

用户明确纠正：数据线当前标签扫描、只读诊断、输入准备是CPU任务，应从实际cpu分区的可用CPU节点选择，不应转去GPU节点21；这覆盖本轮一般计算默认node20的旧限制。站点当日cpu节点为compute-0-2、8–19，仍须每次查询实际分区/空闲CPU/内存，不把快照当永久可用性。正式S′/UFF/QM仍限定14–19，正式生成保留原16CPU64GiB及声明内存85%要求，学校付费服务器禁用，不动他人或模型作业。

用户此前允许小规模测试降低资源使用、正式生成保持原要求。本run有限分析试点的具体操作解释与监控策略仅以新run_decisions_v4.json及cpu_analysis_small_scopes_v1.json为准；Root对实测内存的小试点解释不构成其它任务或正式全量的普遍授权。原336单次批准、旧源码/配置/结果保持。项目指南只允许六个源码/文档目录，本次不修改范围外docs/skills副本；项目侧决策记录在允许的configs/data_v1与docs/data_v1。
## 2026-10-25 模型 v3：独立新任务，旧工作流不重启

用户最新资源分工明确覆盖此前CPU默认20的限制：纯CPU任务提交现场可用的CPU节点，GPU节点只用于模型训练、微调等GPU任务。本次实测站点cpu分区为compute-0-2及8–19；回归、C2查表拟合、日志核验和CPU准备均按实际CPU分配执行，不投20/21/22，不把先前未获准的21/22提议当授权。仍至少16CPU，Root统一调度，提交前核验全用户请求内存<节点85%及真实MemAvailable、quota；不动他人或数据线任务。新regression必须显式expected-node绑定CPU节点，旧20上的历史证据保留，不据新规改写原执行地点。

本轮新核验的监督/操作规则：进程授权用PID/UID、boot_id、内核start_ticks、PGID/SID、argv哈希、cgroup与Slurm job身份逐项绑定；psutil的墙钟created仅保留诊断，不据其NTP校时变化扩大或拒绝已绑定身份。4520410仅created漂移1秒而其余字段相同，旧版拒绝信号且Slurm清理，不能称数值失败；新固定源码6df0aa5经428真实私有child检查与433整树回归通过，旧证据不改。交互SSH内再调用SSH必须使用`ssh -n`，避免内层SSH消费后续调度文本；只按实际sbatch回执登记作业。PowerShell读取UTF-8中文JSON/源码须明确`-Encoding UTF8`，Git SHA由机器读取，禁止从PTY换行/重绘输出手抄。CPU节点授权仍按用户当前AGENTS，未答复的例外不是授权。

用户明确要求按项目根《模型线工作流程：模型 v3、训练代码与训练配方（Codex A）.md》执行正式训练前整理。当前主工作树为 `X:\MFM_model_v3`（远端 PROJECT/MFM_model_v3），分支 `model-v3`，基线 GitHub main `037546cd7f07b32dbb46bc21a69109dfd273f8da`；旧源码、配置、LMDB、S/WP5结果不覆盖或重跑。新模型固定6层/512维，H0 API和维度保持；本轮不做正式预训练，不使用学校付费服务器。指南明确授权使用开发服务器全部12张GPU、单卡一个实验，取代旧任务仅20/21/22的节点范围；仍由Root统一Slurm调度并现场核验CPU/内存、GPU UUID、实际进程与公共UUID锁，不声称未登记GRES的显卡已预约或隔离。直接SSH短测仍依用户AGENTS限定compute-0-20；新大计算只能在实际Slurm分配内执行。

指南明确要求SA-1/2/3并行、profiler后SA-4；平台最多主agent加三个同时工作者，分批安排。Git不允许`model-v3`与`model-v3/sa1-*`共存，实际子分支用`model-v3-sa1-performance`等连字符，独立live X工作树。Windows Git不能直接解析子worktree里的Linux绝对.git指针，相关Git操作经现有SSH执行。阶段0实际CPU4520329 C0/251s/16CPU：6x512+A4完整22,352,859参数、主干12,709,424、H0 shape512；旧4x384完整10,216,035。原61文件/2016测试4520330真实全部PASS/C0/316s，不当作后续真实数据或GPU验收。

阶段0本地b71729e与GitHub model-v3公开3441b280bc34431bf8e7596465af28be073644b6的Git tree精确同为d8950ec6503f39ddfc956cf97eb9e24308e9f47c；API发布提交号和实际执行code SHA分开记录。当前进度和各阶段证据以 `MFM_model_v3/docs/model_v3/EXECUTION.md`、`docs/interfaces/STATUS.md`、原实际Slurm/文件SHA为准。D-1至D-6尚未观察到时按指南先做现有S与合成实现，不编造数据线权威契约、统计或真实验收。2026-10-25用户明确允许SoM二分类满足面板分类覆盖；不把ExpansionRx连续回归阈值化。开发与决策只用下游TRAIN内层，禁止最终评价；recipe/B-star具体结果经用户确认后才能冻结。不得删除已有文件；新任务没有继承旧已完成S/WP5的待续ACTIVE。

## 2026-10-17 S去噪修复已完成指南STOP交付：禁止续跑旧ACTIVE

统一入口确切为项目根`W&B_训练记录.html`（archiver_v4第178行），本任务直达`runs/phase1_full_corpus/wandb_archive/s_denoise_repair_20261016_index.html`；v32只更正旧v31入口路径，不改科学或交付包。最新[最终交接v32](../../../runs/s_denoise_repair_20261016/reports/completed_handoff_20261017_srepair_v32.md)优先于下面v30及历史。代码/2016测试/旧v2逐位一致、D1/D2、初始12+消息补救4次4000步训练全部实际闭合。最佳A4 .052506/.051682 Å高于lookup .041299；消息1 .051982/.052549、消息2 .054122/.054992仍失败；原五门槛3PASS/2FAIL（去噪、成本），消息无匹配A5不借旧结果。用户指南要求1–2层仍未达则停止，GUIDE_STOP实际落盘，无新full/H0/LP/epoch建议，等用户另定下一轮科学方案。CPU675消息2profile actualC0，676/node17/15s最终五页PDF actualC0，全部5实际PDF raster已视觉通过；472文件/9,842,753B ZIP和每成员SHA/CRC已验证本地交付reports/s_denoise_repair_20261016_final_v1，中文结论/曲线/门槛/99科学源码/8filepatch/SourceManifest/完整成本齐全。最终71唯一本任务Slurm父全terminal/active[]，671.084444核h/34.360833 GPU节点作业分配h，含所有失败非利用率。23源SDK全部ARCHIVED/waiting0/errors[]，原SDK保留、未声称在线同步；仅自身quota184421及archive185884经精确UID/start/boot/argv/source核验后实际退出，final_own_metadata_retirement_v1有证据。没有04:00维护/24h续租/待续observer，不触WP5/Stage59/mount/model。Source3/Gate4/cost2冻结、Source4拒绝、原LMDB只读。本轮授权诊断与交付完成，科学验收未通过；不要据旧ACTIVE重启任何工作流。

## 2026-10-17 WP5 全部完成：禁止重启旧工作流

本轮科学计算、验收、G0、交付和最终成本已全部闭合。主入口[WP5最终完成交接](../../../runs/phase1_wp5_20261011/reports/wp5_completed_handoff_20261017_v1.md)，用户报告为同run的acceptance/final_20261016_v1/WP5_COMPLETION.md；最终index实际674 COMP0、3181永久文件/358metadata；最终accounting addendum完整590实际父（SCI542+QA48），26,751.293333核时，所有FAILED/TIMEOUT计入。1,220,466Mol/11,231,854记录/134,782,248明确槽，数据715.666GB；200重算50,800字段0diff；G0六路COMPLETE/pending0/errors0。原pilot差异、G5历史用户例外及原498/601 NOT_PASS留存，不改数值或容差。

原delivery672FAILED1的rawprobe已成功；报告本身因wrapper遗漏scan_v2/deps PYTHONPATH缺pyarrow而退出。新report-only wrapper使用既有已验证deps，冻结delivery3不变，673实际COMP0/2s；没有重跑科学或rawprobe。未来使用该依赖的metadata任务也需相同PYTHONPATH，不能只认为chemprop env自带pyarrow。最终账本含672失败/673修复/674索引，旧SHA文件不回写。自有publisher3212197经UID/start/fullargv（相对script结合/proc cwd解析）及sourceSHA核对后已结束；本轮exactqueue空、无用临时文件已清，所有科学与必要证据保留。未写LMDB/F32、未训练，后续字段/预算为新的阶段。不要根据下方历史ACTIVE记录重启WP5；并行S任务与共享挂载未动。


## 2026-10-17 S修复v30：第二层首seed实际C0未达，收尾路线已明确

最新[交接v30](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v30.md)接v29/v28/v25。M2_seed1_5670/node21 actualC0/8219s/4000/local.05499228875（lookup.04129859），noiseMSE.4375868/rps225.278/GPUpeak11.18GB，runtime.RUNNING是启动snapshot不重跑。只剩M2_seed0_5669/node20=3264@01:58、3000local.05858573，继续固定4000/C0，不提前写GUIDESTOP中断；之后必然双seed门槛失败、无A5，按v30明确步骤CPUprofile3→GUIDESTOP/最新dispatch3+summary3+driver3五页实际C0+全部PDF页视觉→final所有父成本/全部SDKclosed→精确退自己两metadata→packager4 ZIP/SHA安全本地交付。已备两个C temp helper复制5actualrasters和安全解包ZIP，仅py_compile未运行，详v30。Source99/Gate4/cost2/Source4拒绝不变，无新full/无S′训练。observer796 next02:08每600s；01:54actual服务auditPASS/21closed+2writing，原184421/185884今天10:32/10:36到期，04:00维护同v25；若已全terminal短交付则直接最终清理，不触WP5/Stage59/mount/model。最新69父v14=662.8622核h/33.85111GPU节点作业h、active669，含所有失败非final。lookup12fallback全纳无漏算/不加GPU审计同v29。继续完成真实最终交付，不只等待/启动即结束。

## 2026-10-17 S修复v29：消息2半程、查表回退定义已确认

最新[交接v29](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v29.md)接v28（最新5页STOP summary3/driver3/dispatch3/packer4）和v25（精确自身metadata维护）。00:48消息2_5669/20=1600、5670/21=2000，local.07531672@1500/.07214367@2000；Root391956 D3_RUNNING/GSTOP0，仍须双4000/C0及指南条件A5/五gate或严格STOP，不只启动结束。**lookup_used_pairs少12不代表遗漏**：已只读canonical refit_lookup.py/真实recipe，12对回退observed noisy distance且全纳1,319,881对误差和分母；最初“未覆盖”说法已向用户更正，无漏算/不新增GPU审计/不改baseline或gate。observer778自然停、新785 activephase消息2 next00:58，每600s，约01:54续。00:49实际服务auditPASS，原184421/185884身份/源/寿命正常，archive21closed+2writing/errors[]；04:00优先精确自身维护同v25，不触WP5/Stage59/mount/model。最新成本仍v13点时69父非final，未新Slurm自671。原科学99/Gate4/cost2/Source4拒绝不变，未新full/STOP。继续真正全部授权终点/实际5页视觉/全cost+closedSDK/精确退自己metadata/SHA本地ZIP交付；all五过则必须真正完整Root10正式，不能STOP模板冒充。

## 2026-10-16 WP5 v22：只读盘点实际活动与站点无效sstat

最新[WP5 v22交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v22.md)。科学验收已闭合，当前5600/node17和5641/node18继续G0，collector5513等二者。23:55–57只读同UID/实际SLURM_JOB_ID的两次/proc样本，核同PID/start_ticks的扫描进程CPU确有增长，采样时rpc_wait_bit_killable，主要共享文件系统I/O等待；不把日志不变当停滞、不打开活动SQLite、不由此补造完成百分比。证据F/g0_two_active_jobs_activity_check_v1.json。

本站本次两batch的sstat虽exit0，却返回AveCPU=213503982334-14:25:51、NTasks0/RSS空，是无效观察；保留原值，不当实际CPU/RSS/进度或成本。实际成本仍真实sacct父ElapsedRaw×AllocCPUS。fresh SSH曾瞬时UNKNOWN port-1拒绝，避免连续重开，等约5分钟后persistent key PTY25145成功；X按AGENTS net use重连后live正常。复用成功会话，不改共享挂载或并行S。完整交付顺序与下一小时检查见交接，目标仍ACTIVE。


## 2026-10-16 S修复v28：1层能力双fail，2层真并行与硬件明确报告

最新[交接v28](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v28.md)接v27/v26/v25。消息1双actualC0：5660/node20/8916s/local.0519818975、5661/node21/6973s/.0525492513，Rootcapfailed无A5。CPU5671/19 C0/整秒0 原profile3：eps共享47.9504/50.3053%不调权重，原cost18.0404/14.0649h（前者超15已向用户报告）。按指南真启动消息2 Root2 PID391956，5669/node20、5670/node21/16C64G/RUNNING，4000/LR3e-4/原权重/仅2messages，cfg全字段只读审计与原A4一致除condition/message层/授权metadata。Source3 science99/Gate4/cost2冻结，Source4拒绝；未新full/未GUIDESTOP。条件STOP最新summary3+driver3+dispatch3+packager4仍5页，增加GPU/rps/VRAM明确CSV、异构不算性能比且非ABBA、所有profile CPU父也必须actualC0、拒绝Source4decision纳交付；只AST未实际最终运行，精确CLI/schema/SHA见v28，别用旧版本。observer778 activephase消息2/next23:48每600s，65min约00:46要续；04:00自身metadata精确维护同v25，绝不碰WP5/Stage59/mount/model。最新69父v13=590.8622核h/29.35111GPU节点作业h，active669/670，所有失败计。继续真正全部2层/条件A5/原五gate/条件完整full或严格STOP实际5页视觉+全cost/closedSDK/源cfg/manifest/SHA本地ZIP，不只启动结束。

## 2026-10-16 S修复v27：消息1首seed实际C0，待另seed后层2

最新[交接v27](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v27.md)接v26（5页STOP模板/初始TRAIN实机）和v25（自身metadata精确续租/退役）。msg1_seed1_5661/node21 actualC0/6973s/4000/local.0525492513，未低lookup.04129859；rps271.9844、GPUpeak7.654GB、foreign最后0、runtime.RUNNING仅startup snapshot，绝不重跑。种子0_5660/node20仍3232@23:08（3000.06098786真实非单调），Root2 PID380763 D3_RUNNING/GSTOP0；待真实4000C0/Rootcapfailed后指南bootstrap2，同时CPU profile3 --phase d3_message1_v1 --conditions A4_msg1 --tag message1_v1。不能提前伪造前phase完成或A5，只有能力both过才A5/原Gate4全五过后真正full，原15.284预算fail不改。observer763自然停/新769运行，selectedphase/next23:18，04:00维护优先。22:58实际服务auditPASS/19closed+2writing（新终点尚待archivepass），原PID184421/185884不变；操作顺序见v25，不动WP5/Stage59/挂载/模型。最新66父v12=581.7644核h/28.7825GPU节点作业分配h、active仅660；新seed1 closure独立保存不是完整phasegate。全部源99/Gate4/cost2/Source4拒绝不变，未新full；继续所有真实授权实验与完整最终交付，不能只启动结束。

## 2026-10-16 S修复v26：TRAIN原始曲线实际闭合，条件STOP最新5页

最新[交接v26](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v26.md)接v25/v24/v23。22:08 msg1_5660/20=1568、5661/21=2016，local .064889@1500/.062346@2000，仍未终点；只按既有双4000能力1→2/A5/五项全过实际full条件走。新TRAIN renderer1读取真正每32步单batch共125点，与FULL2000九点验证分开；CPU665/19 actualC0/5s、六面板实际PDF已视觉PASS，11文件SHA本地stage3_initial_TRAIN_v1补充，原87包不覆盖。条件STOP最新改summary2（统一所有norm/fraction/cos/definedcount CSV）、driver2+dispatch2+packager3=**5页** summary/D1D2/TRAIN/FULL/gate，新的guard visual状态FIVE_PAGE，所有模板仅AST未实际STOP/最终运行，CLI/SHA详v26，别用旧4页v1/v2packer。原科学99/Gate4/cost2不变；全过仍真正Root10全部正式。自身metadata精确ret2/续quota2/续archive1及04:00维护同v25，未实际停/续，只21:54inspect两身份PASS。最新66父v11=550.0578核h/26.80083GPU节点分配h、active660/661，原失败全计。observer723约22:14续selected IIFE，next22:18；继续真正全部实验或完整STOP交付不只启动即停，不触WP5。

## 2026-10-16 S修复v25：消息1继续，精确自身metadata续租已备但未执行

最新[交接v25](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v25.md)接v24/v23。21:58 msg1_5660/20=1344、5661/21=1696，s1@1500 local.0688125；仍等待两4000，能力fail双C0才2层，能力pass才A5，全五过才full；原Gate3PASS/2FAIL/87文件initial已交付。新metadata ret2严格角色/UID/boot/argv/PID/startticks/source，只自身quota单PID SIGTERM或自身archive STOP_REQUEST，先落validatedrequest、最多20s/竞态/僵尸/实际closed确认；21:54仅inspect真实PASS，没停/续任何服务。新quota starter2只修僵尸误判、renewarchive1保持同源24h并正确续租理由，均仅AST未用、lease0002未建。04:00现有授权维护：相同dbdb源码新lease→精确退自身quota/真实exit→quota2→完整freshquote；再精确退自身archive/closed→renewarchive1→新healthy→audit→maintenance=minexpires−8h，详v25；不触WP5/Stage59/mount/model。最终全部Slurm及SDK闭合再只退自身两个metadata，写组合retirement供v24 packager2；所有STOP交付源模板未实际运行。observer723 selectedphase每600s、下一22:08、约22:14续IIFE；仍未新full/源99/Gate4/cost2冻结，继续到真实授权结局。

## 2026-10-16 S修复v24：msg1健康推进与条件STOP交付模板

最新[交接v24](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v24.md)接v23。Source3 Root2 PID380763、msg1_5660/20、5661/21/16C64G，21:38=768/992（500 local .107662/.111448），仍需两个4000终点；能力fail双actualC0才msg2，能力pass才A5；full仍五项全过。原12组全C0、gate3PASS/2FAIL（能力/成本）、87文件initial PDF真实视觉/SHA已本地交付不冒充final。等待期间仅AST准备STOP summary1/四页合并PDF+全部页raster driver1/CPU dispatcher1/小ZIP metadata packager2（旧1未用），都没运行无新Slurm，实际guard/CLI/闭合要求详v24。只有真正STOP/所有parentC0与terminal/4页实际PDF视觉/全部SDKARCHIVED/自身metadata退役后才final ZIP；全过则真正Root10全部正式科学。observer cell723/selected-phase每600s、下一21:48，65min约22:14须续；04:00自身服务精确续租不漏。Archive21:27pass65=19closed+2writing/errors[]，quota新样本正常；最新成本仍v10点时非final。不要只提交就结束，不改原科学99/Gate4/cost2或碰WP5。

## 2026-10-16 S修复v23：初始12actualC0，3PASS/2FAIL，真实msg1已启动

最新[交接v23](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v23.md)接v22。A5s0_5657 actualC0/7510s/local.05229928386，s1 .05233430610；完整A0–5双seed4000全部C0。CPU5662 profileA5 C0/1s；5663原Gate4 C0/1s：gradient53.466/54.499%、interference.393/1.262%、其他任务3PASS；capability .052506/.051682 >lookup.04129859、cost11.755/15.284两FAIL。依指南明确先试消息能力补救，Source3+Root2 PID380763，msg1两真实父5660/node20、5661/node21/16CPU64G，LR3e-4/4000/原固定权重；不是成本调参，不解除full五门槛。msg1能力fail双actualC0才layer2；能力pass才Root自动matchedA5。CPU5664 C0/16s D3renderer4+gate2+actualPDF raster已视觉PASS，87文件SHA复制本地stage3_initial_v1，INITIAL不是final，用户已有PDF链接。新selected_phase observer用于消息（旧observe只初始），当前cell723每600s，下一>=21:18:05；完整操作/refs详v23。Source3科学99/Gate4/原cost2冻结，Source4拒绝；正式候选Root10/freezer9仍待全部五过。最新65父v10=518.8889核h/24.85417GPU节点分配h，active660/661；原失败都计。04:00自身metadata续租按v20/v8，别触WP5。继续全部授权消息/条件实际full或完整STOP交付，不只启动结束。

## 2026-10-16 S修复v22：A5首终点与实际gate/图表就绪，尚待完整矩阵

最新[交接v22](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v22.md)接v21。A5s1_5658/node21 actualC0/5797s/local.0523343061、noiseMSE.4201858；A5s0_5657/node20在20:36=3136/4000、3000local.05473873。A5 inactive E/B分类低准确率仅raw监控，不作其它任务退化；Source3元数据/科学99/gate4/cost2均冻结，仍未新full/五门槛未全判。Repo source_v3/check_repository实际v26 PASS。新gate dispatcher只完整phase全actualC0才submit原Gate4；render_d3_report_v4、gate_render_v2、complete_diagnostics driver已AST未运行，N/A inactive分类/保rawCSV、精确验证同卡performance的selected checkpoint、实际PDF pdftoppm后仍需视觉，详v22。未来正式仍Root10/freezer9/34py。4个非执行消息DRAFT+README/manifest共6文件已SHA本地审阅复制，实际msg未开始；A5完整后依guide能力补救与独立成本/其它失败条款处理，cost15.284已选组不忽略、不改公式，权重>10%用户决定。最新60父v9=512.6533核时/24.46944GPU节点分配h，仅657active；04:00精确自身metadata续租event按v20/v8。未完成授权工作要继续至真正full或STOP完整交付，不只提交即停。

## 2026-10-16 S修复v21：A4正式选定、一个成本超15、A5真并行

最新[交接v21](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v21.md)接v20。A4s1_5652/node20 actualC0/7543s/local.05168208391，原A4s0 .05250560124；Root实际均值A2 .1008189/A3 .0688754/A4 .05209384选A4 LR3e-4，两个seed都未低于lookup .04129859。实际CPU5659/19/16C32G C0/1s完整A4 profile：eps共享fraction53.4655%/54.4993%，E/B准确率都超matchedA0；**选定组成本原公式11.754998/15.284324h，seed1超15已告知，不能再称未选组忽略/不能改公式或四舍五入强过**。A5_5657/node20、5658/node21真正RUNNING，4000各seed，LR3e-4、仅eps structural task、total_scale1/3匹配。原科学Source3/gate4不变，未新full；完整A5表后按guide条件处理能力补救及其它门槛，full仍5全过才自动实际全部完成。后续Source3 Root10/freezer9/34py和metadata精确续租见v19/v20；04:00维护event不漏。额外只读确认B1/B3 scheduler=len(index)*epochs所以horizon1/3正确；Native geometry_level.2→sigma.05+.25L=.1且angle/bondscale0，不误改。最新60父v8=463.4622核时/21.395GPU节点分配h，active657/658，所有失败留存；不能只启动即结束。

## 2026-10-16 S修复v20：18:14进度与自身metadata寿命实际核验

最新[交接v20](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v20.md)接v19，未五门槛/未新full。18:14 A4s1_5652/node20=2592/4000、2500 RMSE.05644681，待最终LR/A5；Source3/gate4/原cost不变，Source4已拒绝；未来正式仍Source3 Root10/freezer9/34py，完整流程见v19。一次性audit_own_services_v1 Sonmi实际/proc核UID/start_ticks/boot/argv/sourceSHA、quota90s、archive状态/receipt、剩余寿命覆盖5h+30min，184421/185884实际PASS、16ARCHIVED+1在写/errors[]，没动进程。两服务仍次日10:32/10:36到期，内存observer新增10-17 04:00优先维护event（1792180800000）自然结束，届时精确只续自身metadata，新lease后maintenance=最早expires−8h，别动WP5/Stage59/训练。当前observer650自然完结store可靠，下一>=18:24:33；实际新cell按tool ID继续wait。最终报告可按已验证CPU数据和既有render组装，不必强造大compiler，但全部实际实验、指南条件full或STOP完整报告/视觉/SHA交付要真正完成，不能只报已提交。

## 2026-10-16 S修复v19：正式候选Root10/freezer9，CPU池8–19实测

最新[交接v19](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v19.md)接v18，科学Source3/gate4/原成本不变，Source4已拒绝，仍未全量/五门槛未全过。A3双seed与A4s0结果/真实CPU profile/同卡A0A4详v18；17:04 A4s1_5652/node20=352/4000，是唯一active科学，A5待其LR均值。下一>=17:14。
后续正式候选改**full_coordinator_v10.py+freeze_formal_workflow_v9.py**（旧Root9/freezer8保留）。Root10只把自建CPU池8–11扩为实际cpu分区8–19；其余字节与Root9完全相同，LP17CPU64G、train16CPU64G、GPU20/21/22及21配对H0、85%全用户声明内存、全部科学/人口/种子/步数/模型/统计/配额保护不变。actual5656/CPU19/16CPU32G C0/1s，原16案例+2范围及字节相同共18tests全过，formal_cpu_pool_tests_closure_v1绑定。freezer9只指向Root10/自身及新增该actual测试closure，尚未CLI/未binding/未GPU24更新resumeproof/未full；目录34py最终定稿后整体freeze。五门槛全过才按v19实际完整正式；未过仍指南1→2msg或STOP完整交付。消息bootstrap Source3+Root2/科学gate4不变。精确服务续租/只动自身metadata及别任务隔离按v19/v13/v8。

## 2026-10-16 S修复v18：A3双seed/A4首终点、真实同卡表征

最新[交接v18](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v18.md)接v17。16:53 A3s1_5603/node20 actualC0/7567s/local.07063767，A4s0_5607/node21 actualC0/5815s/local.05250560；均仍高于新lookup.04129859。Root164635已自动A4s1_5652/node20真正RUNNING，须其最终LR均值才能A5，不预选。CPU5653/node19 C0/0s真实A3 profile：eps共享fraction44.9806%/50.2347%，准确率都超matchedA0；原成本11.815263/15.329391GPUh，seed1超15已告知、A3未最终选定，仍继续原A4/A5不提前整体停/不改公式。Source3科学99/gate4/analysisbinding3不变。
空闲21同5090预选择A0/A4 compute ABBA actual5655/16CPU32G C0/80s，4warm10timed/block、56zeroLR optimizercalls参数及buffers逐位不变、official0。A4/A0吞吐.8748287，peakallocated4487481856→3509852160B，foreign0；plan明确不选LR，完整成本仍原D3含loader，不能把短检乘进预算或冒充未来消息架构速度。Source4已拒绝不用。最新56父点时v7=427.3289核时/19.13722 GPU节点分配小时、仅5652active，所有失败保留。按v18完成原矩阵、指南1→2消息/五门槛及条件真正full或STOP完整交付；不是只启动即停。服务精确续租/隔离按v18/v13/v8。

## 2026-10-16 S修复v17：A5报表undefined处理实测，等待双seed终点

最新[交接v17](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v17.md)接v16；16:23 A3s1_5603=3104/4000/local.07265019@3000，A4s0_5607=2816/4000/.05613693@2500，下一>=16:33。原Root164635继续，未五门槛/未新全量；Source4实际拒绝不采用。A5冻结训练路径静态审查无需改；但旧profile1对有效权重0的E/B cosine=None会fsum失败，独立profile3改有定义均值并显式20批有效数/全undefined None，全部定义时旧数值精确不变、真实0仍有效。actual5651/node19 C0/0s16CPU5tests通过，profile_optional_cosines_tests_closure_v1。Source3科学99/旧分析4/gate4/cost公式不变。新dispatcher3在双seed真实4000+actualC0后才submit CPU16/32G，合法cpu节点2/8–19按实际准入；下一A3 profile命令及幂等见v17，尚未提交。未来消息bootstrap用Source3+已31测试Root2/原gate4，1→2条件严格同v16；全部授权实验/五门槛/条件full或指南STOP最终完整交付仍要真正完成，不能只启动即停。服务续租和别任务隔离按v17/v13/v8。

## 2026-10-16 S修复v16：Source3指南消息bootstrap实测完成，尚未执行

最新[交接v16](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v16.md)接v15，Source4因提速不足已拒绝不采用，科学/正式继续Source3。新的message_bootstrap_v1仅原phase完整12actualC0、A2–4全部组缺少双seed去噪能力才准1msg；2msg另需msg1真正能力fail和2actualC0，不允许成本/其他gate失败调架构。原LR/均值/lookup来源/99源码/guide全验证，新增msg各seed v3配置其余字段原样，Source3 normalization none、scalar√degree、4000steps不改。actual5643/node19 C0/0s16CPU，10guards测试及多子场景通过，message_bootstrap_tests_closure_v1冻结。**Root用已31测试的message_root_v2+Source3 binding4，科学gate仍4；gate5未用**，替代v15优先Root1建议。所有真正msg/bootstrap尚未开始，不能在原phase完整前--start；命令/幂等/后续见v16。
最近SMON16:13:19 A3s1_5603=2784/4000/2500RMSE.07589253，A4s0_5607=2400/4000/2000RMSE.06039538，下一>=16:23:19；后续每600秒。原Root164635正常，未新全量/五门槛未全过；继续至真实终点/条件全量或指南STOP完整报告，不只启动就结束。服务精确身份/续租及其他任务隔离按v15/v13/v8，别触WP5。GPU20/21/22，CPU其他合法cpu节点实际16核/85%准入；新CPU10guards无科学更新。

## 2026-10-16 S修复v15：可选优化实际拒绝，保持Source3

最新[交接v15](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v15.md)接v14，未全量/未全部五门槛。Source4候选CPU5627 actualC0/162s原2016+12及旧v2 310tensors bitexact全过；GPU5635/node21第二5090 actualC0/271s，0/1/2msg×first/largest ABBA 48行，6数值全过、12开发更新/6新模型及optimizer checkpoint恢复过、official0/foreign0。但提速1.0008–1.0675均<预登记1.10，execution_decision_v1已REJECTED，**不采用Source4**，不放宽要求/改原成本，不创建Source4科学binding。当前A0–A5与未来消息fallback继续Source3。source-aware Root2/gate5候选CPU5642/node19 actualC0/2s31tests，通过但未激活，科学gate仍4/analysis_binding3；Source4不采用故优先既有Source3 message_root1/gate4。真实消息bootstrap/配置/phase尚未建立，原组完成后若能力全组fail按指南1→2msg，其他门槛失败不借此调参。
CPU8–11全满而其他cpu分区节点合法可用，用户授权CPU其他节点并无8–11硬限制；CPU候选14、元数据测试19均实际16CPU准入，85%全用户声明内存；不抢占别人。后者dispatcher已只跑一次，不重跑造成跨节点重复。Source3长任务仍20/21，22按资源，训练64GiB不降。新51父点时accounting_v6=403.4178核时/17.6428 GPU节点分配小时，active5603/5607；actualCPU预检查无资源未创建job则不虚构计费。其余权限、archive/quota到期精确续租、600秒observer、真实所有后续/全量或指南STOP完整交付按v15/v13/v8。

## 2026-10-16 WP5 v20：只读盘点续算已迁移获批空闲节点

最新入口[WP5 v20交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v20.md)。科学/200/最终verifier/七storage已闭合，G0尚未。旧shard0/5552真实COMP0但257466 DONE+2 LARGE_PENDING，node12全96CPU被占，原helper在preflight拒绝、未提交/未动collector。Root已审阅窄入口后在已批准node18实际启动4515641（16:09:38，24CPU32G），同STATE/seed和冻结v3.scan_shard核心、46h预算；节点迁移只改变执行位置。窄入口显式核UID/actualSlurm/node18/原cfg/旧报告，保留原exclusive锁/DONE和真实前后receipt，不monkeypatch或改冻结NODES。不能把静态原manifest节点映射静默改写、伪称原入口直接支持迁移，亦不为同授权只读范围重复问用户。此入口pin旧5552，后续只能依据真实新终态作相应新续算。

当前只剩G0 actual5600/node17与5641/node18，collector5513真实afterany二者；QAmapv16=45，科学542另列，全部失败/超时成本保留。观察只小report/log，不开活动SQLite，终态0仍可能pending。按每小时主检查和已备有限delivery/index/最终记账继续，不提前goal完成；不动并行S工作。

## 2026-10-16 S修复v14：A3首终点、独立执行候选与D1/D2组件

最新[交接v14](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v14.md)接v13。A3s0_4515595 actualC0/5848s，local0.067113Å、masked/bond均超过matchedA0，但仍高于新基线0.04129859；15:54 A3s1_4515603=2176/4000、A4s0_4515607=1600/4000。Source3科学99/原分析4/gate_v4全冻结，Root164635继续原A0–A5，无新全量。
可选Source4执行优化事先plan_v1登记，默认False，逐边线性Wi*hi/Wj*hj改为逐原子投影，不改参数/科学配置/成本公式。Source4静态619文件PASS，CPU候选5627/14/16CPU64G已提交终态未知（8–11全满，cpu分区14现场IDLE合法；v1预提交无CPU拒绝未创建job）。必须2016+12/C6旧v2bitexact/真实GPU数值、吞吐及optimizer/checkpoint全过。复制的Source4 legacy脚本硬编码旧输出，不可直接运行；安全外部wrapper独立actualjob目录。采用仅限原组能力全失败后的指南消息fallback前瞻新phase，原A0–A5不换；成本单独失败不能绕STOP。采用需新sciencebinding/messageRoot/gate/formal路径，旧Root9/freezer8只Source3。GPU候选未实施/未采用，详v14。D1/D2完整组件actual5608 C0/4s，PDF实际视觉PASS，不能冒充D3门槛。服务精确身份和续租按v13/v8；每600s长任务批量观察，不触WP5。

## 2026-10-16 S修复v13：A2双seed闭合，A3继续（尚未最终五门槛）

最新[交接v13](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v13.md)覆盖v12进度。A2s1/4515586/node20真实COMPLETED0/7987s/16CPU，4000步local0.10055764Å/噪声MSE0.7698798；A2s0为0.10108014Å，两者均高于新基线0.0412985903。denoise末20批共享fraction35.0634%/40.8804%已过10%，不能以低梯度擅改权重；masked/bond均较A0退化。
通用profile_completed_d3_conditions_v1调用原cost_estimator_v2/gate_v4函数，CPU4515604真实COMPLETED0（ElapsedRaw0为整秒），六完整组CSV/JSON。A2成本14.930635/16.451951 GPUh，seed1超过15已告知；尚未选最优LR，必须继续A3/A4/A5后对选定双seed正式判定，不能借此提前整体停，也不能改原公式/阈值强行通过。A0s1真实geometry fraction0.0009964015325791555，旧摘要抄写差异以CPU数据为准。最新46唯一父点时361.6178核时/15.07694 GPU节点分配小时，所有失败保留。
A3s0_4515595在21推进、A3s1_4515603在20已自动启动。原lookup真正完成、gate_v4/analysis_binding_v3/22测试、源99/旧分析4、未来Root9/freezer8/31py不变；Root9正确16测试父4515581，开发proof新更新24而非旧文档32。未GPU恢复proof/未正式binding/未全量/H0/LP。按v13完成真实所有诊断、五门槛和条件全量/指南STOP完整交付。
Archive185884和Quota184421身份/到期及只续自身metadata按v8/v10/v12，勿动WP5或旧Stage59；原SDK保留。SSH PTY46543/Y可用，10分钟observer IIFE启动，已审lookup完成不循环返回。三版interim只中期，最新11文件PDF已实际视觉+SHA本地复制，不能冒称最终。

## 2026-10-16 WP5 v18：最终科学验收通过，G0仍执行

完整入口为 [WP5 v18交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v18.md)。科学542父人口闭合，200条50,800字段精确一致，六现场与shared存储PASS。原全量498已读3181文件、0文件异常，但957明确失败D20被无条件名称规则误报；定向601读回证明失败null/20null/20boolFalse，但漏识别已知JSON诊断而FAILED2。新602实际COMPLETED0，v2只处理601绑定元数据，957均合法失败、严重0，真实正例+13内存负例PASS。最终verifier为acceptance/final_20261016_v1/D20_failure_aware_v2_4515602/verification_report.json，Root采用证据为同F的D20_final_verification_root_adoption_v1.json。原498/601 NOT_PASS、QC、状态/空值及实际成本保留；不重写科学、不放宽SUCCESS或未知错误规则、不重扫715GB。

G0三实际5552/5592/5600仍运行、collector5513依赖三者；不能开活动SQLite观察、不能用quota inode数替完整盘点。v4候选实际599同4096项ABBA stat速度0.3701无收益，保持v3不启用。继续delivery3/index1与有限记账，不因科学完成提前宣称全部交付。当前QAmapv15为44实际父，科学542另列，最终成本包括所有失败/超时/交付/索引。SHA从机器引用程序取，PTY重绘可重复字符，手抄65位SHA不代表文件变更。每小时批量检查与事件及时处理照旧；不动并行S任务/服务。


## 2026-10-16 S修复v12：原lookup已真实闭合、A2首终点与gate_v4

最新[交接v12](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v12.md)覆盖v11。原lookup4515527真实COMPLETED0/22691s/16CPU，全TRAIN11104772，FULL RMSE0.0413792212Å、D3子集0.0412985903Å；lookup_refit_closure_v1绑定实际父/7原recipe源/输出。原pilotTIMEOUT保留，未提part不再启动。不要再因旧progress陈旧重复拟合。
A0/A1双seed闭合；A2s0/4515578真实COMPLETED0/7186s，4000步local0.10108014Å/噪声MSE0.7819743，共享梯度denoise35.0634%已过10%，masked/bond准确率比A0低。仍须A2s1_4515586与A3s0_4515595及后续扫描，不提前整体停止。单组成本原公式14.930635 GPUh，非正式最优/双seed门槛；当前分块8192未改。
最新gate改analysis/stage3_gate_v4.py，真实CPU4515594 COMPLETED0/5s/22测试，gate_analysis_binding_v3；添加lookup真实parent/hash校验，六科学判定函数AST和阈值不变，旧冻结分析全保留。gate前actual snapshot需包括completed_lookup_reference_v1及真实D3/C6。首新头中期曲线4515597真实COMPLETED0/4s、actual PDF已视觉，11文件SHA显式交付interim_v3，仍PARTIAL。所有失败计入44唯一父的点时实际成本，不按连续ID算WP5任务。
未来仍Root9/freezer8/31py，未正式冻结/未GPU恢复proof/未新全量。纠正旧交接开发proof总数：新更新8+8+4+4=24，payload累计[8,8,4,8]，不是32；代码原已正确，不改科学或旧bitexact标准。Archive185884/Quota184421到期和只续自身规则按v10/v8，不能触碰WP5。10分钟observer须async IIFE eval，已审lookup完成不反复返回；当前SSH PTY46543/Y可用。按v12继续全部实际诊断、条件全量及最终交付。

## 2026-10-16 S修复v11：完整判定14测试与实际全父成本（仍未全量）

最新[交接v11](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v11.md)接续完整v10；D3 Root164635、未来Root9/freezer8、科学99/旧分析4与新gate_v3不变。A1s1最近3552/3500评估0.12927662Å，A2s0最近1088/1000评估0.12272480Å，原lookup9437184仍执行，不能把短程改善当门槛通过。
新增repair_final_metrics_v2真实CPU4515585 COMPLETED0/7s，14测试+5子场景，final_metrics_binding_v1冻结。严格四训练/12端点/492单元/420任务行/32主项/88838176曝光，缺失保留，旧B3仅seed0。ExpansionRx真实任务为MAE回归，只有CYP/AZ hit@1；未测试v1草案保留不用。实际capture_repair_accounting_v1已按40个本ROOT唯一receipt/Sonmi真实parent计全部失败成本，点时259.7067核时/9.77861 GPU节点分配小时，3active，非最终成本；GPU节点分配时间不当利用率。完整报告主程序和真实科学结果仍待完成。
12:20新开SSH到57:22瞬时refused，但原key SSH PTY46543仍实测Sonmi可用、Y live正常；不关闭现有连接/强拆其它任务。对话科学批量观察约600秒，别再用55秒重复查询旧observer循环；作业内保护保持。按v11/v10继续至实际科学终点、五门槛与授权全量或指南STOP的完整交付；两metadata服务次日10:32/10:36到期须精确身份续租，不动WP5。

## 2026-10-16 WP5 v12：pilot 差异披露与最终验收

完整当前状态见 [WP5 v12交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v12.md)。正式人口和actual542科学结果已闭合；全量读回、原均匀200链、G0、六现场与shared、终态实际成本及交付尚需完成，不把计算覆盖率当最终验收。

- 指南第6步3要求当前200同环境重现；第6步4另要求逐条列出pilot差异。不能因实现附加的“pilot必须零DIFF”而自动停审，也不能把列出差异说成数值PASS。当前授权删POLAR后，官方MOPAC实现的隐式SCF精度分支会改变；只能在实际受控样本范围内解释，不泛化全人口或擅自采用新阈值。
- 实际577六次B-only对照已完成：当前配方科学字段精确重放；tight对旧除3条POLAR QC删除、3条已验证HB修复外全部物理及派生字段一致。实际582只读43条均为冻结Mulliken charge-QC主动拒绝，保留NULL/PROPERTY_FAILED，SCF收敛；没有POLAR/ESP残留。43条逐一SCF因果未控制，原全部DIFF和246526原始未归因计数不改。
- Root final review为 acceptance/final_20261016_v1/pilot_disclosure_review_root_final_v1.json，已服务器字节SHA及原始288字段计数读回；新delivery3可--pilot-review，状态明确“已披露差异”，不放宽其它闸门。13语义fixture真实PASS，不重复跑。旧index1通用supplemental已支持review/source/fixture/result，保持原入口，不为同一能力另造index2。
- 大文件checksum在服务器做轻量元数据观测，再经live X写小报告；不要为SHA通过SSHFS重复读取大Parquet。一次自有Windows只读helper按PID/owner/start/完整命令身份精确退休，未动挂载或科学进程；第二小元数据编辑及服务器readback均成功。原生X不稳继续既证liveY逻辑X，不拆共享挂载。
- 200计划只在全阶段末尾输出；首5索引后24进程从物理family rowgroups读取科学列、期间无heartbeat，短期无文件mtime变化不证明停滞。G0活动SQLite不做广泛readonly GROUPBY；大目录只在完成后提交，真实终态仍pending才按同STATE未完成项扩大预算续算，保留DONE与实际失败成本。
## 2026-10-16 S修复v10：正式Root9与门槛CLI入口已实测（仍未全量）

最新[完整交接v10](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v10.md)覆盖v9；v8原服务身份/续租仍有效。A0双seed及A1s0真实闭合，A1s1/A2s0继续，lookup4515527最近9437184但尚未完成，不重复全人口。源99/旧分析4保持冻结，五科学门槛尚未过。
未来候选是formal_workflows_v4/**full_coordinator_v9.py + freeze_formal_workflow_v8.py**。21真实两张同型号5090，资源准入/单UUID锁下允许64GiB训练+32GiB H0不同GPU同node，禁止两个64GiB训练；同伴须实际RUNNING，PENDING/未知不占第二slot。H0全21匹配旧硬件，训练同seed21/20配对。16项保护4515581真实COMPLETED0/4s，31py仅准备，真实GPU恢复proof/正式绑定/8epoch与12探针仍未跑。
预审发现旧gate_v2 argparse漏baseline_phase；先记录缺陷，独立新增analysis/stage3_gate_v3.py与gate_analysis_binding_v2.json。真实CPU4515584/17测试，源103完整SHA通过；六核心判定函数AST与原版相同，阈值不改，原4冻结分析文件不动。以后门槛用v3并真实Sonmi parent快照/lookup终态。性能probe4515583真实零更新/参数不变/数值通过，131072可缩短短批耗时但当前D3仍8192、不重启A2、不改冻结成本估算；候选不当正式结果。
新6文件中期PDF已实际视觉+SHA本地复制interim_v2，仍PARTIAL。Archive185884与Quota184421正常，到期仍10-17 10:36/10:32，精确身份只续自己metadata；原SDK/历史/失败成本/WP5保持。按v10继续实际科学终点和五门槛，全过自动全量收尾，不只启动就结束。

## 2026-10-16 S修复v9：后续Root8统一H0硬件（仍未全量）

最新[交接v9](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v9.md)及v8完整背景优先。D3仍Root164635，两A0闭合、A1两seed推进；lookup4515527已恢复937万，pilot5550实际TIMEOUT/0块，五门槛未过。Source99/分析4冻结不变，不动WP5。

未来formal候选改为formal_workflows_v4/**full_coordinator_v8.py + freeze_formal_workflow_v7.py**，不用v7Root/v6freezer。Root8将所有新H0固定21以匹配旧H0，训练同seed仍配对21/20；10个父状态/精确人口/12端点/H0硬件保护4515568实际COMPLETED0/3s。28份formal源仅准备，GPU恢复proof/binding/正式4条件8epoch/12探针均未执行。Archive185884与quota184421身份/到期及续租仍按v8；不能把旧169170或未启用草案当活服务。所有actual失败/成本/SDK继续保留。

## 2026-10-16 S修复v8：新实际metadata服务与正式流程准备（五门槛仍未过）

最新[交接v8](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v8.md)。D3 Root164635、两A0真实闭合、两A1继续；原lookup4515527按序734万暂未变，但自身allocation新probe为15R/1D，不能按停滞假设取消。分块pilot5550真实TIMEOUT/0块，不扩大未证实的I/O并发。科学99/分析4冻结不变，无新全量。

原W&B169170已精确身份STOP_REQUEST/closed退休，新watcher_v3 **185884** 真首轮HEALTHY：7ARCHIVED+2WAITING/errors0，到期北京时间10-17 10:36:11。archiver_v4支持带tag开发SDK并明确DEVELOPMENT+分支名称，单一入口/共用锁/原SDK/offline不变。未启用的v2/v3草案不作当前服务。新私有quota **184421** 是Stage59原publisher同字节复制，30s真实测量、90s新鲜度、24h到期10-17 10:32:02，control/live_quota_v1/current.json；不改原Stage59或WP5。真实source pin从原start.json机器读取核字节，不能人工照抄PTY重绘的65位错误hash。

formal_workflows_v4未来候选为full_coordinator_v7、segment_launcher_v5、live_quota_v2、freeze_formal_workflow_v6；13入口/6旧调度/12最新调度加真实CPU quota检查分别4515557/58/59实际COMPLETED0。新Root/launcher还没激活，GPU full8两次与4+4恢复证明没跑；旧v2逐位标准不放宽。五门槛全过才冻结dev→真实GPU证明→formal绑定/4配置/正式8epochs与12探针；配置仍version3。两metadata服务须核身份和余寿命覆盖墙钟+收尾并及时续租，不能把latest动态quote当不变SHA或用df代quota。所有原失败、原始SDK和成本保持，不动WP5。

## 2026-10-16 S修复v7：两A0闭合、分块pilot超时与入口保护实测

最新[交接v7](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v7.md)。A0s0/4515542与s1/4515543均4000updates实际COMPLETED0，终点localRMSE0.138843/0.140265Å；A1两seed4515553/4515554运行中。Root164635、科学99/分析4冻结源不变，五门槛未过，无新全量。

lookup原4515527仍执行，7340032记录；不能按曾停滞而取消。分块pilot4515550实际TIMEOUT（ExitCode0:0仍非成功）、2703s/16CPU=12.0133核时、0durable块，cache48数组bitexact不等于全拟合完成；新三part/reducer未提交，不扩大无证据收益的I/O并发。原进度和所有失败成本保留。

formal_workflows_v4是新增执行草案，保留v3历史。wrapper冻结源码/指南/门槛，checkpoint/resume新增workflow绑定；13CPU保护检查4515557实际COMPLETED0。4515555输出父目录缺失、4515556 compute缺git均保留FAILED，后者13测试组件OK不能升级父。源码checker是标准库静态元数据，现Sonmi repository_check_v18 PASS618/360py/571原来源；新GPU恢复证明/正式Root/launcher/12探针协调器仍未完成。

W&B169170原服务/到期规则不变。未启用archiver_v3+watcher_v2草案已补development_s_runner及带tag segment发现；首次GPU恢复证明前须验证并精确退休旧服务后升级，不能让旧v2漏归档或两版互覆索引。C本机避免SSHFS递归rglob；本轮仅结束精确核身份的自有陈旧只读helper14076，未动挂载/他人/科学进程。后续按v7完成，不重新训练旧S′/S、不动WP5。

## 2026-10-16 S修复v6：首个完整A0与查表恢复推进

最新[交接v6](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v6.md)。A0s1/4515543实际COMPLETED0/6140s，4k更新、RMSE0.140265Å、noiseMSE0.99259、最后20批distance共享份额0.10%；A1s0已4515553。Source99与分析4冻结不变，五门槛未过，无新全量。

原全TRAIN查表4515527/CPU9曾629万页等待35+min（16D但内存充足），现已恢复至727万，未取消。CPU8原配方48条4515549实过0；新耐久分块执行器pilot4515550运行中，缓存开启/重复与关闭的48条数组bitexact且48hits已验证，但16完整chunks尚待。**不要按旧停滞假设取消或重复跑全人口**；三part/reducer仅已准备，优先保留原恢复进度。新plan已pin运行engine/reducer，不改活跃文件，canonical新基线须Sonmi真实父终态验证后发布；原若完整则优先原结果。

消息层fallback协调器未启动，4保护测试4515548实过；能力失败先1再2层，双seed过lookup才A5。新最终reporter_v3支持失败phase/named键级recall与count，v2仍冻结。Windows SSH PTY长JSON会重绘重字，用短ASCII进度observer；functions.store srepair_observer_js可做5min/55s帧观察，cell运行时勿抢PTY。W&B169170及10-17 08:32到期、正式runner尚待等按v6；不动WP5。

## 2026-10-16 WP5 全人口已闭合，最终验收和 G0 续算继续（v9优先）

严格catalog4515541实际COMPLETED0：1,220,466分子、11,231,854记录、134,782,248槽，missing0/issues0；不是全验收完成。verify4515498和pilot4的4515502仍执行，499→500→501为原均匀200条重算链，六现场5518–5523仍待实际验收。正式actual542及515真实FAILED/539独立验证事实保持，不重做已闭合QM。永久SCI约715.7GB，另400GB训练格式仅预留，本轮不写LMDB。

节点14旧故障scratch已由真实4515551 COMPLETED0按策略闭合：原2成员备份加新50输出容器全部解压/SHA/逐字读回后，清理exact75files/48空目录、约101MB，exactroot absent。22输入正文不归档，1可重建cache；部分故障输出保持UNKNOWN_PARTIAL，SCI/队列/原receipt和历史scratch_clean不改。新证据、receipt、cleanup_report与supplemental必须纳入最终交付，不重放清理。

G0 shard0原4515507实际FAILED1，原因为COMMIT database is locked；已提交189837DONE保留。只读广泛查询曾与故障窗口重叠，不擅断唯一锁来源。运行中盘点不做全库GROUP BY观测，使用日志/小报告；终态或共享非阻塞锁观察结束后关闭句柄，避免观察器妨碍scanner。原只读观察器已自然exit0，无信号。新v3仅增加5处同事务COMMIT BUSY/LOCKED有界重试，保留原扫描/INFLIGHT恢复；真实私有共享读锁fixture已通过并清空/tmp。Root实际提交4515552，node12/24CPU32G48h/内部46h、同STATE、6h目录预算，DONE不重扫。3/4原续算531/532不动，collector513现afterany531:532:5552。仅未闭合目录续算；G0必须最终COMPLETE/pending0/errors0/all_shards_complete，不凭Slurm0升级。

最新28个实际QA父清单acceptance/final_20261016_v1/actual_acceptance_parent_jobmap_v3.json（SHA0f62760e2d36981134c9ee3ec1f7080fb5c28cffb4a0bc5214f00f9dcf839500c）；与formal542分开真实计成本，之后实际新增父另版追加。全量读回、200比较、pilot全部差异/分布、六节点+shared、G0、真实终态成本/配额和最终索引仍须完成。完整实际路径、源SHA和下一步以[WP5 v9交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v9.md)为准；大批量对话级检查仍1小时，异常/用户消息及时处理，不因此重置主检查截止。

## 2026-10-16 S修复v5：中期源码交付与真实W&B闭合归档

最新[交接v5](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v5.md)。D3 Root164635/99源码冻结及lookup4515527仍执行，门槛未过。8文件核心patch已对84校验原版实际apply验证；11个中期小产物SHA交付本地interim，不能当最终报告。正式新Root/launcher/probe协调器及GPU恢复证明尚待；performance crossover与gate page仅已准备。

本任务离线归档analysis/archive_s_repair_wandb_v2.py真实5闭合+2运行中、errors0，20源/副本文件与20链接通过；不解引用5个外部全局debug-core日志，仅保留指针文本。旧generic exporter真pin为64字符3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e8f975a，已核原服务收据，未改。共用既有archive lock/预算、独立S索引，保留单一W&B_训练记录.html原入口及新链接，不能用旧generic扫描覆掉任务链接。

24h metadata watcher169170，control/wandb_archive_service_v1/current.json，UID/start/argv已实核、首轮HEALTHY，600s；到期1792197167.5349即北京时间10-17 08:32。正式每段前须核余寿命超过墙钟+收尾，不足精确身份退休更新。所有本机文本显式UTF-8，检查元数据脚本成功后才调用依赖SSH操作；原生X挂起继续已证明Y的逻辑X resolver。

## 2026-10-16 S修复：分析v2与Sonmi实际记账快照

S修复仍在D3阶段，唯一Root164635/source_v3/binding_v4不变；4515542/43与全TRAIN查表4515527继续，不得把测试或部分图升级为门槛通过。当前交接 [v4](../../../runs/s_denoise_repair_20261016/reports/active_handoff_20261016_srepair_v4.md)。

实际发现compute节点sacct连localhost记账库失败，图表4515546 FAILED1/0秒，保留证据。改用analysis/capture_actual_parents_v1.py在Sonmi只读采集父sacct，生成不可变control/accounting_snapshots，CPU后处理验证原始行与dict一致；禁止在compute直接查sacct或凭产物推断COMPLETED。v2分析13测试及实际PDF渲染4515547 COMPLETED0/6秒，已视觉复核；configs/gate_analysis_binding_v1.json绑定该分析源。门槛CLI用stage3_gate_v2.py，须--parent-snapshot；成本v2预声明扣除全部checkpoint保存时间避免重复启动计费。

formal_workflows_v3只是未提交草案，配置保护6测试4515545 COMPLETED0，完整runner尚未GPU恢复验证；五科学门槛全过后才验证并启动新全量，不能越过门槛。原生X挂起时继续C临时metadata helper按逻辑X解析native Y；不强拆共享挂载，不把OneDrive当同步。

## 2026-10-16 S去噪修复运行期v3与实时挂载恢复（优先于旧S修复点时记录）

当前修复开发源为 runs/s_denoise_repair_20261016/source_v3/current/phychem_mfm；source/source_v2及旧Stage59/旧S证据全部保留。源码冻结configs/D3_source_binding_v4.json，共99份，85份核心科学代码与已验证v2逐字节相同。全测试4515537实际2016 passed/COMPLETED0、v2真实小批参数/H0/预测/loss逐位通过；新本地块选项下真实spawn/epoch/未消费预取恢复4515538通过，GPU真实A0/A1/A2与weights_only安全checkpoint存取4515540通过。

只读交叉对照4515536验证256记录三视图全部Tensor字节相同；使用subset-local索引关闭4096记录块，使关闭块切换498→32、累计worker加载秒22.87→6.36。新选项subset_map_close_uses_local_index默认false，仅新配置true；噪声仍用source-global索引，不能为提速改变噪声、样本次序或标签。工作流每500步安全保存/readback，分开记录compute/loader时间；中断SDK状态与指南NaN停止单独处理。

旧元数据Root160742已按UID/start_ticks/boot/source/cmdline核验退休。INT未停止其两个原型后，仅精确scancel自有4515533/4515534，实际CANCELLED by1278、1351秒/项；原部分日志、离线W&B及成本12.0089分配核时/0.7506GPUh保留，不将未保存尾段拼接到新对照，不以旧runtime的RUNNING快照否定真实sacct终态。
新唯一元数据Root164635/sonmi，control/d3_local_blocks_v1/identity.json，72h有界，source_v3/workflows/s_denoise/d3_root.py。新A0种子0/1已提交4515542/4515543，20/21；22仅现场准入，声明内存不足就等候。Root只协调D3，不启动全量。TRAIN全人口查表4515527仍执行，不重复拟合或把旧0.042当新人口结果。第3步门槛尚未通过，尚无新全量结果。

本机X原生访问再次阻塞；标准net use重连实际85，不强拆其它挂载、不提权或杀其它任务。Y已通过新写探针并由Sonmi读回核为同一项目：reports/client_live_mount_probe_v3.txt，inode21491884850/UID1278/38bytes，SHA1eea21375d48c591d948d5dd84830e419d927130d90143e4e129e9c5d0ceb3a5。当前客户端C:/Users/mint/AppData/Local/Temp/s_denoise_live_io_v3.py将X逻辑路径解析到Y实时视图，所有服务器编辑经此逻辑入口；不是OneDrive复制。C本地仅做元数据/源码搬运，科学仍SSH/Slurm。超长cmd命令会在启动前被拒，应把较长编辑批次放本地临时Python脚本，再通过逻辑X映射写入；冻结源或提交状态不明时先读真实文件/状态，不盲重试。

新指南允许五门槛全部通过后直接启动B1两种子各一轮、B3两种子各三轮；不重复询问同一授权。沿用16CPU64GiB、85%全部用户声明内存、20/21/22与共享GPU例外、CPU8/9/10/11、原LMDB只读/不建训练LMDB、不训练S′、不动WP5。D3/门槛/实际停止按新指南，不能带入旧0.141Å停止、旧raw-loss绝对差或epoch外推。D1/D2已完成且D2反驳0.1/N硬下限；最终主因仍须如实结合D3，不强行写成预期结论。当前README及新Root真实状态优先；旧记录为历史。

## 2026-10-16 S去噪修复：独立新任务，D3门槛尚未通过

用户明确要求执行《S 去噪修复方案（Codex）》；原文保存在 runs/s_denoise_repair_20261016/user_repair_guide.md，SHA240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3。沿用Stage59主干与原人口、原LMDB只读、不建LMDB、不训练S′、不影响WP5。GPU仅20/21/22、正式16CPU64GiB、全部用户声明内存85%、已接受共享GPU风险及单UUID一本项目任务保持；CPU诊断用8/9/10/11。新指南授权第3步五项门槛全通过后直接开始B1两种子各一轮、B3两种子各三轮，无需重复确认；不通过按指南停止报告。新单向指标/双组种子差异替代旧raw-loss绝对差规则，不带入旧0.141Å停止阈值，不外推epoch。

实际修复开发源为新root/source_v2/current/phychem_mfm，旧source开发副本及165项失败回归证据保留，不改历史Stage59/上一轮源码配置。Phase1LossPolicy新字段须keyword-only，保持旧两个位置参数；2016全部测试4515530实际COMPLETED/0（以submission/all_suite_v3.json实测ID为准），旧v2真实8记录参数/H0/预测/loss逐位通过；真实spawn及未消费预取恢复4515526通过，CPU/GPU源码/旧配置/新损失路径闭合。第二次整套回归仅缺PHASE1_JOINT_REFERENCE_PATH，原失败4515528保留；引用stage50_full_corpus_training/actual_api_reference/full_corpus_training.py并核原c1c011fc…摘要后完整通过，不能豁免或删除该测试。

D1 4515524真实200batch完成，距离逐batch共享梯度占比均值21.84%、全参数裁剪触发1%；D2 4515525真实1000Mol完成，原0.1/N自由对称权重可达0.008509Å，不能声称此形式存在约0.1Å硬下限或网络已达到神谕。新TRAIN查表重拟合4515527仍在运行。D3选定TRAIN10000Mol/91893records、FULL2000Mol/18486records，全部构象保留，分子无交集；A0–A4各双种子4000updates，A5后按预注册终点选LR。所有组验证共用source-global seed0/epoch0哈希噪声；原始查表0.05Å箱/至少32 TRAIN观测，完整FULL与D3子集分别评估，不用FULL拟合。

Root仅元数据，source_v2/workflows/s_denoise/d3_root.py，PID160742/sonmi，身份control/d3_single_layer_v1/identity.json，启动请求唯一且72h有界；只协调D3、不启动全量。已实际提交A0种子0/1为4515533/4515534，20/21，22按现场准入。冻结99份源码在configs/D3_source_binding_v3.json；不得修改活跃source_v2，后续修复另立版本。当前README、control实际状态及真实产物优先，不称门槛或全量通过。Windows PowerShell启动偶有阻塞时可用cmd.exe执行本地标准库元数据helper，Linux科学仍在SSH/Slurm内，服务器编辑只用X live视图；不得把本地Python当Linux科学解释器。

## 2026-10-16 WP5真实重试已采用，严格最终验收继续（以v8为准）

原catalog4515497正确拒绝两Mol的20记录/240槽：cleanup领取RETRY_PENDING消耗queue预算1后，compute_one误返同lane既有attempt0 completion。不能把预算归零、改写SCI/receipt编号或侧车豁免真实重试。Root已用冻结runner14/contract7/package14、原task69/node13补做实际4515515；科学链路WP5_JOB_CLOSED，2Mol/20记录/240槽闭合，237 SUCCESS与3 TIMEOUT均为actual attempt1，保留显式超时，不再QM。

4515515实际FAILED/1:0原因是随后v2纯元数据校验误要求COMMON家族含lane；不得将该父作业伪装为COMPLETED。COMMON原schema不含lane，须通过全12 canonical槽、QM行、durable receipt/raw context交叉证明。独立纯元数据v3校验4515539实际COMPLETED/0，完整240槽通过；Root已在compute20按新证明及两个真实终态原子adopt两row，预算1、原completion_rank、旧SCI与beforeimage保留。校验器失败与科学结果状态分别记账，已闭合SCI不得因元数据接口错误重跑。证据见[实际采用](../../../runs/phase1_wp5_20261011/acceptance/final_20261016_v1/exact_two_budget1_retry_v1/production_adoption_v3.json)及[240槽证明](../../../runs/phase1_wp5_20261011/acceptance/final_20261016_v1/exact_two_budget1_retry_v1/verified_240_slots_v3.json)。

固定actual542清单为 acceptance/final_20261016_v1/control_jobmap_actual542_v1.json，SHA9487a547e770170f40cd22f97b373cc4a5a3e242b37c1a877dc9f3209340a1e8、状态ACTUAL_542_FORMAL_PARENTS_TERMINAL_SCIENCE_VERIFIED；原541行不变，新增真实SCI父515保留FAILED原因，539为独立验收成本。原failed catalog四个元数据文件158,795,922B按SHA全字节rename保留，catalog仅建立指向catalog_closed_v2的相对逻辑链接。Root已实际提交严格catalog4515541，现有4515498 verify与4515502 pilot依赖改为afterok:4515541，499→500→501原链不重复提交。旧一次性resumer/helper159347已实际结束，不得复活或沿用COMPLETED515假设自动采用。证据与完整待办以[v8交接](../../../runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v8.md)及[catalog实际提交](../../../runs/phase1_wp5_20261011/acceptance/final_20261016_v1/catalog_v2_root_dispatch_v2)为准。

最终200条/2400槽重算比较、全文件SHA与字段核验、pilot差异披露、G0、六节点现场scratch与共享残留审查、实际成本/交付仍须实际闭合，不能把队列COMPLETE或成功提交当作验收完成。G0仅stat元数据，同STATE只续未闭合shard、DONE不重扫；scan/collect退出0还须status/pending/errors/all_shards_complete。六现场4515518–23已依赖200比较与pilot，不重复审计；残留只在永久副本证明后清自有冗余，不改历史scratch_clean=false。正式542包含515失败成本，QA/G0另列并汇总真实总成本。

连接补充：native X读写卡住时，先确认既有Y是相同账户/PROJECT的live树；在新的PowerShell局部脚本作用域使用 `New-PSDrive -Name X -PSProvider FileSystem -Root 'Y:\' -Scope Local`，同进程用 `SessionState.Path.GetUnresolvedProviderPathFromPSPath` 将X路径解析为native Y路径后读写。无需Remove-PSDrive，不用全局net use抢修或停止挂载进程，不编辑OneDrive副本；已有卡住句柄不反复重开。Linux项目计算仍经key SSH/Slurm，Windows标准库只可处理本机控制/静态源码元数据。此fallback的实际源码写入、server SHA与compute20执行证明保存在v8及catalog_metadata_preparation_v3/preparation_receipt.json。
## 2026-10-15 S′/S全量实验已最终验收（本任务无待续训练）
本S′/S任务已完成，reports/final_experiment_acceptance.json为FULL_EXPERIMENT_ACCEPTED。A10,782,661个S′/1,220,466分子全部状态、五组F64/SHA/随机100重现闭合。B1两种子各11,104,772记录一轮，B3准确33,314,316三轮；每轮1,206,608分子、missing/duplicates0。七个真实H0/287固定线性单元/245任务行已全部完成。最终报告4515415实际COMPLETED/0、实际七页渲染4515416 COMPLETED/0，已逐页视觉复核；首页恰好五项，曲线/耗时/35任务对照均可读。全部172个本任务注册Slurm父作业实际终态已封存，S正式成本793.8356核时含失败。
一轮不足：FULL距离差7.0992%/7.2257%，键级差246.9837%/232.4480%，元素差<2%；32主探针仅11满足种子差异标准。S边际增益条件外推约5轮，超出3轮LR horizon未验证，不代表下游联合收敛。epoch1三组RMSE0.124521/0.124586/0.122944均高于历史0.042；B3最终0.115046 Å。下一阶段去噪头/噪声修订与8条件/规模研究由用户另行决定，本任务不追加训练。原S科学v8、冻结配置/标签/人口未改，旧失败与成本保存。
训练4093402、探针4033124、报告46408均正常返回；发布器4014920在全终态封存后按UID/startticks/boot/source/cmdline核验退休，见own_metadata_services_closed_20261015.json。旧observer显示服务结束是正常完成，不得重启旧6/7或未完整epoch快照。当前README与active_handoff_20261015_final.md优先；并行WP5是独立工作，未取消/修改。
后期X原生全局映射孤立、net use85/2250且DefineDosDevice当前用户被拒，未提权或强杀。既有Y已核为同一PROJECT（AGENTS同inode64431312633/UID1278，最新67757bytes/SHA899490c3…与Sonmi一致，最终PDF及验收源码也SHA一致）。本次编辑采用当前用户PowerShell X盘指向Y并经GetUnresolvedProviderPathFromPSPath解析native路径后写入；不动Y或其他挂载/进程。Set-Content对此provider别名可能误判ADS，避免未经解析直接写。初始两次渲染提交因文件未写成在sbatch之前被拒，无新Slurm科学；失败日志保留，最终4515416实际完成。
22个报告/清单小文件已按源SHA精确下载到本地reports/sprime_s_convergence_20261013_final，delivery_manifest.json记录来源和SHA；这是明确交付副本，不是双向同步。S′大Parquet与checkpoint权威原件仍在服务器runs/sprime_s_convergence_20261013。技能两份同步，保留最新WP5归档竞态恢复等其他任务记录。
## 2026-10-15 WP5 归档竞态恢复（优先于旧 WP5 点时记录）

WP5 phase15 的78作业已全部实际COMPLETED，所有六阶段463个正式作业已核终态；这不代表全人口完成。最新队列检查点为1,011,462分子／9,592,275记录（85.40%），剩余分子以实际R10恢复后队列为准，最终200条／2400任务验收仍未开始。

实际发现cleanup4515295提前finalize了仍活跃的cleanup4515292，删除其lane后24分子／214记录归档写失败并进入ATTENTION_REQUIRED。证据在 `reports/phase15_actual_foreign_finalizer_race_root_v1.json`；SCI worker完成数与永久前缀均61分子／581记录，不能凭错误receipt整JSON比较误报丢失科学结果。新runner14只将跨root repair移交Root终态保护工具，保留自身worker全部退出后的finalize及全部科学函数；实际16writer夹具、追加复现包4515309和G4 4515310均通过，contract7已冻结。普通正式cleanup不得触碰其它活动root，不能重开空lane掩盖已删文件。

R10只读99root完整核验4515312、24条同attempt恢复4515313、E8零待导出核验4515315、当前G3 4515314均已实际闭合，原STOP已归档解除。phase16已实际一次提交72主4515316–4515387＋6收尾4515388–4515393；当前runtime14/contract7，PROJECT cwd、24CPU32GiB48h及46+2不变。真实单Mol startup已核4515354/node18、10记录120任务全部SUCCESS，六trace字段及H2完整验证通过；不代表全人口验收。watch11 PID65713已启动，实际报告小时边界下一37、首次延迟3600秒，计账7阶段541唯一正式作业；actual541 map及receipt sidecar已生成。完成的本地镜像已清理16,390,533,120字节，永久清单与故障证据保留。先核同attempt完整SCI，确无完整SCI的本次精确24基础设施故障仅恢复PENDING并保留attempt、旧receipt/export/rank；不能用RETRY_PENDING额外增加科学尝试，也不把它们写成科学最终失败。恢复后按既有持续授权完成纯导出、当前容量与G0核验再续算，不重复索要相同权限；原六停止条件、原LMDB只读和最终200验收不变。copy只读源字节，SQL恢复仅本地镜像；完成后按实际依赖清理本轮临时副本，保留永久与故障证据。

## 2026-10-15 最终报告v9 / Root v6与边际轮数估计
最新报告协调Root_v6/PID46408，identity/binding/status_v6；旧v5/PID42913只核验退休自有元数据，科学作业未停。report_current_v9、validator_v6、独立s_epoch_estimate_v1在实际CPU8作业4515296 COMPLETED/0，5项产物、故障尾段排除、7种边际估计边界通过，实际第一页视觉可读。新observer_v7，当前交接active_handoff_20261015_v2.md。训练4093402/v3、探针4033124/v2、记账4014920/v1保持，B1两种子整轮完成，B3约2.6轮，6/7真实探针，仍未全量完成。
报告后处理只在B3整数FULL三项曲线支持正底减速指数模型时给条件轮数，明确3轮LR horizon以外及下游充分性未验证；无正底/非单调/不可识别给下界3及需下一端点验证，不编造有限上界。实际观测2%变化和条件外推分开；原B1-vs-B3/32主项合取阈值不变，无额外训练。报告补全各epoch active/calendar耗时表、真实GPU类型/数目、epoch1查表对照和完成后的用户待决事项。并行WP5已有recovery15任务，勿触碰或取消；CPU收尾依旧实际资源准入并避开其当前工作节点。
## 2026-10-15 B1两种子整轮闭合、6/7探针及记账竞态修复
B1_seed0实际4515203、B1_seed1实际4515200均完成11,104,772记录/1,206,608分子整轮，missing/duplicates均0；B3实际4515214/GPU21约2.58轮，仍待准确33,314,316曝光。六真实H0/线性端点已闭合（210任务行），仅B3_e3待完成。三组epoch1 FULL局部RMSE约0.12452/0.12459/0.12294 Å均高于历史lookup0.042，应按指南单独呈现去噪头/噪声问题，不能归因于人口规模。科学runner_v8/配置未改，训练Root4093402/v3、探针4033124/v2、Sonmi发布4014920/v1保持。
报告4515189因新正式parent在Root预检查后注册、而快照未更新，完整性断言FAILED/1。新report_v8增加全报告共享1200秒有界等待真实Sonmi快照，保持publisher UID/host/sourceSHA、全parent覆盖及900秒新鲜度；5种元数据竞态/超时/伪造来源场景通过，实际报告4515216 COMPLETED/0且产物/故障尾段排除通过。新报告Root v5/PID42913、identity/binding/status_v5，validator_v5/template_v8，旧报告Root4080070核验后退休，仅自有元数据，不停科学。最新observer_v6，当前交接reports/active_handoff_20261015_v1.md。X断连已按AGENTS key/net use恢复，Test-Path和65484字节AGENTS SHA与Sonmi一致；新SSH工具会话3732，旧39201失效。尚未全量完成，不得提前验收。
## 2026-10-14 元数据排程提效，最新训练 Root v3
训练Root现v3/PID4093402，仍用formal_s/root_coordinator_v1_identity/status路径、binding_v3；旧v2/PID4078932核对自有UID/startticks/boot/cmdline后退休，运行中4515162/GPU20和4515168/GPU21未停。实际吞吐21更高，后续有空余21时优先给长B3，其他准入节点优先待运行B1；无相应任务立即使用其他PENDING条件，保持并发，ACTIVE/完成/repair/stop不提交。1000纯元数据状态×资源组合验证通过，原resource_ready/quota_ready/submit_segment等全部非main旧函数AST一致，runner_v8/launcher_v1/配置/run_plan SHA未变，见formal_s/metadata_scheduling_v3_validation.json。未新增科学更新或重跑，没改正式16CPU/64GiB、85%或冻结定义。报告Root4080070/v4、探针4033124/v2、记账4014920/v1不变；observer_v4/v5保持正确的共用训练身份路径。当前交接active_handoff_20261014_v10.md。两组真实探针已闭合，完整五epoch与余下五组未完成，不能称全量完成。
## 2026-10-14 第二真实探针闭合及 GPU20/21 正式并发
CUDA恢复4515159实际COMPLETED/0，B1_seed1安全累计6,440,960/15,812更新并保存segment_final；超越原故障曝光点且正常保存，原失败成本仍保留。B1_seed0续接4515168/GPU21，B3续接4515162/GPU20；20前一外国作业结束后全部用户声明资源检查通过，实际16CPU/64GiB及GPU UUID记录保持，未降配或触碰外国任务。资源情况为现场快照，不固定今后节点占用。
B3_seed0_e0p5准确5,552,386曝光/13,636更新，H0 4515169及LP4515171均实际COMPLETED/0，五套H0/41单元/35报告任务/32主项闭合，无缺失aggregate。正式探针2/7，剩余五终点和全部完整epoch未完成。报告4515172实际COMPLETED/0，NOT_YET_EVALUABLE。证据reports/second_formal_probe_and_cuda_recovery_closed_20261014_v1.json，当前交接active_handoff_20261014_v9.md。Root训练v2/报告v4/探针v2/记账v1不变，原science_v8和配置未改。
节点20的FULL验证曾耗时714.8秒，期间训练journal不增长但作业内validation_full_progress持续更新并最终127,082记录闭合；不能凭训练journal停顿重启。只读observer_v5可显示真实进度快照，但原快照IN_PROGRESS状态是历史写入原文，实际完成以validation_*_complete、summary和实际sacct为准。继续既有全量授权及全部停止规则，不称全量完成。
## 2026-10-14 CUDA 普通故障安全恢复及真实首个探针
4515155 B1_seed1 因 CUDA launch timeout FAILED/1，无NaN、manifest不一致或指南科学停止。4515158真实COMPLETED/0验证两张5090新上下文及安全checkpoint完整性；4515159同原runner_v8/正式配置从4,194,304记录、10,292更新恢复，已产生新增训练更新。失败未保存尾段至5,057,536/12,416只保留日志与成本，不累计或重复计入收敛曲线。cuda_recovery_v1/continuation_gate.json按实际失败summary/健康receipt/checkpoint SHA绑定，只适用此次失败，新CUDA故障须新审计；不得reset GPU或触碰外国任务。训练Root更新为v2/PID4078932，但仍使用formal_s/root_coordinator_v1_identity/status路径及原launcher绑定；普通故障不阻止其他已验证条件推进，指南科学停止仍全局生效。
报告v7/validator_v4实际4515160 COMPLETED/0，故障尾段排除和产物检查通过；报告Root现v4/PID4080070、binding_v4/identity_v4/status_v4。旧报告Root4050319及训练Root3993579仅核对自有UID/PID/startticks/boot/cmdline后退休，不停科学作业。观测使用s_experiment_observe_v4.py，探针Root4033124/v2和Sonmi记账发布4014920保持。第一正式端点B3_seed0_e0p25在H0 4515148、LP4515149均COMPLETED/0，41单元/35报告任务/32主任务闭合；其余六端点与完整五epoch尚未完成。保持原Stage59官方边界、287单元、20/21/22、16CPU/64GiB和85%声明规则；不得称全量完成。当前交接reports/active_handoff_20261014_v8.md。
## 2026-10-14 最新报告 v6 / Root v3（探针仍 v2）
最终合取判定已补充正确缺失处理：任一S损失或32主探针已知不合格即判一轮不足，不被另一个None探针掩盖；仅其余都合格而主探针缺失时判未能建立充分性。report_s_experiment_current_v6、validator_v3、四个规则边界场景由实际4515146 COMPLETED/0通过。4515145因新S作业未进入600秒sonmi记账发布快照FAILED/1保留，更新真实发布后同源retry1通过，未改变科学指标/阈值/模型。最新报告Root PID4050319，身份report_control/identity_v3.json，绑定binding_v3，状态status_v3；旧报告Root4033148核对身份和已结束报告作业后退休。观测改用s_experiment_observe_v3.py；探针Root4033124/v2、训练Root3993579/v1、记账发布4014920/v1不变。最新交接reports/active_handoff_20261014_v7.md。B1_seed0累计2659328、B1_seed1累计4064768，B3续接4515144开始，均尚未完整一轮，七正式探针尚未闭合；不可称全量完成。此前Stage59确认、官方5326/2282边界、35报告/32主指标、287单元、X续期、资源/停止条件保持。

## 2026-10-14 下游未执行草案已纠正，最新协调者 v2（优先于下面350单元旧快照）
用户明确沿用Stage59后再次核对原协议：四套数据保持十个原始scaffold轮换；ExpansionRx保留5326条log_train_data.csv TRAIN和2282条official_test.csv TEST，不把官方TEST移入训练，不新增inner split。指南scaffold回退条款不覆盖已明确指定的官方划分。全部35任务报告，QM9 A/B/C为辅助，32项主指标参与一轮判定。旧未执行LP v1曾误应用为五组scaffold/350单元，已在任何正式H0或线性任务启动前纠正；原几何和源数据未改，准备文件派生的Expansion fold注释不消费。新政策configs/s_probe_protocol_v2.json，新LP run_s_linear_probes_v2.py，每终点41单元，七终点共287；未观测正式探针分数后改口径。开发验证4515138实际COMPLETED/0，20个真实H0私有单元和全官方成员ID路由通过；仅原TRAIN标签作私有留出验证，改留出目标不改训练归一化、权重、顺序或预测，官方TEST目标未用于拟合或选择科学规则。旧记录保留，详见reports/downstream_partition_correction_20261014_v2.json。
旧纯元数据探针Root4011681和报告Root4016539按UID/PID/start ticks/boot身份核验后SIGTERM，未动训练和外国任务。最新探针Root PID4033124/finish_root_v2，身份probe_preparation_control/finish_root_v2_identity.json，绑定finish_binding_v2，状态finish_root_v2_status。最新报告Root PID4033148/s_report_finish_root_v2，身份report_control/identity_v2.json，绑定binding_v2，状态status_v2。当前联合report_current_v5及validator_v2由4515139实际COMPLETED/0，第一页五项渲染视觉通过。观测改用s_experiment_observe_v2.py，旧v1会把已退休服务看成失活。三个正式S运行均通过0.1轮FULL阈值；B1_seed0续接4515136实际累计游标恢复成立，未完成整轮。原训练Root3993579、记账发布4014920、runner_v8、*_v2配置、A接受结果、16CPU/64GiB及85%规则均不变。README和reports/active_handoff_20261014_v6.md为当前入口，尚未全量完成。

## 2026-10-14 B3 0.1轮检查通过及 X 实时挂载续期
B3_seed0正式4515133在GPU21，1110478条训练曝光后的FULL127082条读入闭合、missing/duplicate均0，local RMSE0.1376701602Å，低于0.141指南停止阈值；此前B1_seed1相同门槛0.1392035375Å也通过。该点时证据不代表完整epoch或最终收敛。五轮、七真实H0终点及350线性拟合单元由现有Root协调继续，最终仍按真实闭合与报告验收。
原本机raw-SFTP relay设24小时上限，会在后续长计算期间过期。已只更换自有X挂载：新relay PID39260/127.0.0.1:23260/有界168小时，新sshfs PID35724；原native SSH隧道PID36220/22259和严格可信compute8 known_hosts/key保持。切换前新relay实际SFTPv3握手通过，精确核对旧X挂载38952的PID/创建时间/程序/命令后停止，未碰其他挂载、用户任务或服务器科学进程。切换后X存在、原项目AGENTS inode64431312633/UID1278/bytes65484和SHA与sonmi一致，全部已绑定科学源码SHA复核通过；sonmi和计算节点不同st_dev为命名空间差异，不冒充另一项目或数据迁移。实际记录reports/client_mount_renewal_20261014_v1.json；本机新helper及挂载身份在Temp的sprime_sftp_bridge_v2_identity.json和sprime_sshfs_v2_identity.json。后台训练不依赖本机挂载存活。

## 2026-10-14 用户明确确认本轮沿用 Stage59 冻结配置
用户对原冻结引用澄清问题明确回答“沿用 stage59 已有冻结配置”。实际确认及两个文件实测SHA核对保存在 runs/sprime_s_convergence_20261013/formal_s/user_frozen_reference_confirmation_20261014_v2.json，已在sonmi再次读取原冻结文件和resolution_v3验证通过。此前确认元数据v1误抄resolution摘要，验证明确拒绝并保留，不是科学源或数据漂移；v2从实际文件取得摘要，原始科学配置和正在执行的正式训练未改。此明确答复与此前技术定位一致，不重跑已完成科学，不再询问相同配置选择；指南覆盖项及B1/B3全量授权继续。

## 2026-10-14 S′ 全量已验收、S 正式训练和真实探针收尾继续（优先于下方旧快照）
A 已由全人口闭合4515112、正式全人口随机100重现4515116、报告4515124实际 COMPLETED/0 验收。runs/sprime_s_convergence_20261013/dataset/acceptance.json 为 FULL_DATASET_ACCEPTED，reports/full_coordinator_v7_status.json 为 A_FULL_DATASET_AND_REPORT_ACCEPTED。1,220,466分子/11,231,854原S记录产生10,782,661 S′构象，98.8745%分子至少一个合格几何，99,224分子不足N；最近PM7重原子RMSD中位1.449Å，PM7覆盖9.8917%。原科学sprime_v6与源LMDB、WP5清单未改，不复制补齐。用户“请你完成全量实验”的授权保持。
B冻结引用已按下方v1.0.63的六份后续引用证据解决，无需重复询问技术定位。正式runner_v8、*_v2配置、16CPU/64GiB、85%全部用户声明内存、GPU20/21/22及唯一Root提交保持。4515089 B1_seed0正常分段471,552记录/0完整轮；4515109 B1_seed1首次0.1轮FULL验证127,082记录闭合，局部距离RMSE0.1392035375Å，低于0.141停止阈值。尚未完整B1/B3，不能判断收敛。20/22资源不足时等候，不能塞两项64GiB到21节点或杀他人。训练Root PID3993579，实际身份formal_s/root_coordinator_v1_identity.json。
五套冻结下游ETKDG+UFF输入生产4515119–4515123、全量验证4515125、仅报告重叠4515126均实际COMPLETED/0；probe_data_v3/acceptance.json接受150,770成员/148,076合格几何，失败和未知标注保留，未删除预训练重叠。H0/线性接口与无测试目标泄漏检查实际通过，仅为开发检查；七个真实终点共350个线性拟合单元仍待执行。探针Root PID4011681，身份probe_preparation_control/finish_root_v1_identity.json。
联合report_s_experiment_current_v4与产物检查4515131实际COMPLETED/0，第一页恰好指南五项、PNG视觉检查通过，当前报告明确NOT_YET_EVALUABLE。报告Root PID4016539、身份report_control/identity_v1.json，实际sonmi sacct发布PID4014920、身份formal_s/report_accounting_publisher_identity_v1.json；来源均绑定，不在计算节点伪造或忽略sacct失败。全五轮/七探针端点/245行任务表闭合后自动提交最终报告检查，仍需实际视觉复核。当前完整入口为任务README与reports/active_handoff_20261014_v5.md。所有服务仅Root元数据/Slurm提交，有界21天，不在登录节点计算；旧失败及成本保留，学校付费服务器未用。运行/分段完成/服务启动不等于全量实验完成。

## 2026-10-13 S 冻结引用已核对、正式训练已开始（优先于下方待定位历史）

本轮通用文件名 frozen_protocol.json 已按实际项目谱系解决：Stage59 `actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json` 原始 SHA cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4，与后续 Stage60 五份 segment-parent 和一份 full-statistics 引用共六份逐字一致，均为 frozen。实际新回执为 runs/sprime_s_convergence_20261013/formal_s/protocol_resolution_v3.json，SHA b4bc3fc8209c4470d84205ee7e5162f133cab6122e92c5e2224ec897c8109038a。这是 Root 基于新查明的主证据确定引用关系，不是虚称用户已答复或确认该具体文件名。

formal_s/run_plan_v2.json 已冻结 B1 seeds0/1 各1epoch、B3 seed0共3epoch，TRAIN11104772记录/1206608折叠分子；only S、固定每叶1/3、动态 balancer OFF，主模型/损失/数据视图/优化器沿原冻结配置，指南覆盖人口及 N/3N 学习率 horizon。s_convergence_runner_v8.py SHA ee8063cda7f33b80b136bfec436062abef9319cb40554bf9f1ba6616798f6b71。4515088 实际 COMPLETED/0，原生 LMDB 连续4步与3步+恢复1步（2006 records）模型与优化器差异0，CPU/CUDA RNG、coverage/sampler/scheduler严格相同；这仅是恢复预检，不是一轮训练或收敛。

4515087 因原60秒加载 guard连续三次重启仍无首记录，FAILED/1、0更新，失败保留。v8仅将明确声明的IPC等待上限改为600秒；恢复保留提交游标和父RNG，模型/数据/种子/学习规则不因此改变。formal_s/controller_binding_v1.json 绑定各源；Root S协调者实际PID3993579（身份元信息 formal_s/root_coordinator_v1_identity.json，按UID/start_ticks/boot_id核），已提交正式B1_seed0 **4515089** 到GPU21，16CPU/64GiB，每epoch须实际全记录闭合。正式下游探针采用原冻结五组数据（QM7、QM9、CYP isoforms、AZ exact SoM、ExpansionRx），按新指南覆写为H0线性、ETKDG+UFF、scaffold及只报告预训练重叠。

每项正式训练仍需64GiB；GPU21 RealMemory120000MiB无法在85%声明上限内容纳两项各64GiB。未提交的两slot/共享64GiB pool提案已在运行前拒绝，不能算正式并发或收据。GPU20/22仍按实时全部用户CPU/内存及UUID保护核验，资源合格后才增并发。普通有界开发测试可采用实际够用的32GiB并核85%，不把它标为正式训练。

A的原五个CPU作业保持；CPU12释放WP5后增加准入绑定的 admission-only v8作业4515083，96CPU/96GiB/95科学worker，原science v6和原v7队列逻辑AST不变。旧4515082因五节点准入限制 FAILED/1、无SCI，保留。新增节点一度等待NFS RPC，后已恢复实际产出；CPU分配384核不等于每时每刻384核有效。A/B仍需完成各自全部验收和联合报告，不能把当前运行、2006记录预检或单个checkpoint叫全量完成。学校付费服务器未用。

## 2026-10-13 S′ 全量已获明确授权

用户在收到 10000Mol 试跑及 A7 超门槛报告后明确说“请你完成全量实验”。该指令批准继续本轮 S′ 全量，不再次询问相同的 A7 权限；实际记录在 runs/sprime_s_convergence_20261013/reports/full_run_user_decision.json，绑定 pilot_summary SHA b8142dcca0dbab87ab3f853f5486c1c4c591a06d37118043446295b1a140fdc6。科学实现 sprime_v6.py 与试跑一致，原始 LMDB 和 WP5 清单只读、不建 LMDB。继续至全人口状态/计数闭合、SHA/float64读回、正式全人口随机100同种子坐标复现及报告完成；不能将提交或单批终态当作验收完成。保持唯一Root协调提交、至少16CPU、全部用户声明内存85%和避开当前WP5节点的要求。B1/B3的本轮既有授权仍有效；指名 frozen_protocol.json 尚未定位，不能把历史候选未经核对当成已获确认的本轮配置。学校付费服务器未获授权。

## 2026-10-13 S′ 生成与 S 收敛检验（本轮独立任务）

用户明确要求严格执行 property_analysis/S′构象生成与S收敛测试指南_Codex.md。服务器账户和目录仍为 zixiao@202.38.247.57:22 的 descriptor_analysis；新独立输出根为 runs/sprime_s_convergence_20261013。A UFF 构象与 B S-only 收敛训练可与 WP5 并行，本轮明确授权 B1 两种子一轮、B3 一种子三轮，不套用旧 WP5 “不训练”限制。原 LMDB 与 WP5 清单只读、不创建新 LMDB。CPU 避开14–19并避开当前 WP5 使用的12/13，现场选择其他空闲 CPU 节点；GPU 限20/21/22。每项计算至少16核、有效并行、全部用户声明内存85%核验及唯一Root提交保持。

A 先按五文件组分层试跑10000Mol，外推核时严格小于5000且失败率严格小于1%才能自动全量；否则保留试跑并报告等待用户确认。N不足不可复制补齐，不替换UFF，原子顺序、SMILES指定立体及最低能PM7确定的未指定立体必须保留。B 固定三个S任务权重、禁动态balancer、TRAIN完整一遍才称epoch；NaN/发散、实际记录与清单不一致、超过0.1epoch去噪RMSE仍>=0.141Å按指南停止。停止条件不扩张到普通可修复软件故障。

本机标准 net use X 重连实际失败67；直接SSHFS在SFTP传输初始化时reset。已通过sonmi受信known_hosts与本地端口实测三种key摘要相等核验compute-0-8，且两端项目AGENTS.md物理inode/bytes/UID相等；恢复X为同一/share项目live view，经native SSH隧道到compute8及本机仅127.0.0.1的SFTP管道适配器，不改数据、不关闭主机验证。实际SSH别名继续用于Linux命令与Slurm提交。compute21旧SSH host key变更需独立核验；本轮自有Slurm4515020实际读出ED25519指纹SHA256:cB2kIJBHOR48KHedUYjICdLC+QzbSmR6A5kGyzE+jN0，属于受信调度路径的节点实测证据。现场GPU/内存/队列仅作点时信息，不写成永久容量。

## 2026-10-12 WP5 phase14 正式续算已产生科学结果（v1.0.60，优先于下方历史）

用户最新明确持续到目标全部计算完成，没有无法解决的严重问题不随意停流程；这已覆盖可解决运行故障的自主修复与后续续算，不重复询问相同权限。科学范围、原六项运行停止条件、最终200条同环境验收，以及原LMDB/manifest只读保持。只有全部11,231,854记录／1,220,466分子及12任务闭合、最终200／2400验收通过后，才能称目标完成。

当前有效阶段是协调phase14，科学入口仍为冻结runner13/main13、contract6与原package。实际一次提交主4514369–4514440、收尾4514441–4514446；回执 `submission/recovery_attempt_v14/submitted_jobs.json` SHA4d2eed16ad56ebb8b1b933b6ec4748923d7819aa047f919f7a9004a69985e15b。78个作业的实际WorkDir均为项目根 `/share/home/zixiao/descriptor_analysis`，节点12/13/14/17/18/19、24CPU/32GiB/48h和6个own-node afterany保持。首次实际startup-probe（epoch1791767801.0658562）已有744次领取、192个新完整分子／1,895条新记录的持久科学结果，见 `reports/continuation14_first_durable_science_actual_probe_v1.json`；这是健康产出的点时证据，尚未完成全人口。

watch7实际PID3461479，身份记录 `reports/recovery_hourly_watch_v7_identity.json`；observer6/watch7按5份真实阶段回执累计385个唯一正式作业成本，同一队列人口只计一次。下一次对话级批量检查间隔为1小时（3600秒）；保留作业内截止/checkpoint、publisher与监控原频率，异常或用户输入及时处理，不重查已保存startup证明。待6个收尾结束仍有可处理剩余，按最新持续指示自主完成真实最新全阶段终态记账、SCI恢复／纯导出与剩余容量核验后，以同冻结科学配置和独立新回执续算；不重置一次科学重试预算，不额外申请相同权限。

必须保留旧R13故障事实：其全部78作业COMPLETED0，但全部sessions claims0、新SCI0；77作业的1,848个worker因错误cwd下relative source_path初始化失败，另1task71范围已空。不能把调度退出0写成科学成功。旧partial handoff、原失败源/回执和审计记录保留，不重启旧协调器重复提交。目录修复通过4514366真实单wholeMol链路：24worker、1分子1记录、12任务全部SUCCESS、inputtrace12、scratch清理；没有重做480压力或50×2科学验证。

后续sbatch/helper必须明确从PROJECT提交并读回实际WorkDir；不能从WP5ROOT提交后依赖相对source_path。PENDING的NodeList未分配不是节点错误，应按实际ReqNodeList、声明资源与后续真实allocation判定；本阶段点时23RUN／55PD与修正v2审计保留，v1误读仅为历史。普通FAILED或锁错误不新增STOP；原六条件真触发仍停止新Mol、落盘和正常退出，不scancel。详见 `runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v4.md`。

## 2026-10-12 WP5 修复版 R13 的实际交接

用户最新要求持续到全部计算完成，授权自主处理可解决的问题。R12 提交前发现收尾动态领取可能超出本地索引快照；独立 R13 将收尾领取限定于索引覆盖的任务集合，索引同时覆盖这些任务暂时 RUNNING 的分子。主任务领取、科学计算、解析、字段精度、重试次数、截止保护和600秒元数据等待沿原冻结逻辑。旧119份源文件及已有结果保留。

实际4514281的16个进程已通过跨任务关闭、同任务返待处理、空范围及后继收尾边界测试，零QM、零生产队列写入。runner13 SHA258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f；增量复现包4514282闭合，contract6 SHA dfbeb31ed87553a62f833d8aee22f7000dabffc973b4ed34366ce6edd1e65099；G4实际4514283以24个进程通过，manifest7。G4旧spec的同路径、同SHA/bytes重复引用可在独立适配器中原样保留，不能误当源码改变；报告的语义差异字段是binding_differences。

旧task2和最后收尾4142已正常完成。Root唯一提交协调器当前是wp5_first_submit_handoff_v3.py，PID3452926/UID1278/start_ticks8056177747；等待真实全229清单扫描4514280后继续apply、bootstrap13、实际剩余G3、G0和一次72＋6提交。批准记录878cc仍绑定原prepared12/contract5；修复版明确引用最新持续指示及真实metadata桥接证明，不伪造新的用户批准。当前原正常drain STOP的reason仍为USER_APPROVED_R12_SOFTWARE_RECOVERY_NORMAL_DRAIN；交接只归档该实际标记。所有计算与最终200条验收完成之前，单批作业终态不等于目标完成。新阶段监控消费实际R13第四份回执，首次累计307个科学作业；后续续算必须更新实际阶段全集和成本，不能漏记或重复计人口。


## 2026-10-12 R12 正常drain与一次72＋6明确获批

用户实际批准call_e92f4936799142f49105fe45329daf89：“允许正常退出并一次性续算（建议）”，随后明确要求立即推进新版提交并持续到全部计算完成，没有无法解决的严重问题不随意停流程。Root已写既有STOP_NEW_MOLECULES正常drain机制，授权记录在 submission/recovery_attempt_v12/user_approved_drain_and_one_phase_v1.json；不scancel、不杀当前wholeMol，不再询问这次同一批72＋6权限。待旧229真实终态、SCI修复/纯导出、生产bootstrap/G0闭合便按冻结方案提交。后续用户的持续计算指示覆盖可解决问题的自主修复，原科学配置、节点/资源、六项停止条件、最终200及原LMDB只读保持。最新纯导出4514279/V3仍在跑；此前压力、复现包、G4和存储已闭合，不重复科学验证。

## 2026-10-12 R12 元数据生命周期与冻结实测通过

run6（4514266–4514272）真实生产大小元数据压力测试PASS：五节点480 writers/22 parents，5765唯一领取及完成/回执/导出闭合，MAIN/NONE/RARE各480报告、无错误、15个stage done均正常退出。13节点不计为R12压力写节点；原六节点科学链路沿已闭合证据，不重复QM测试。runner12冻结SHA91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278；候选5相对候选4只将元数据等待120→600秒，仍min实际deadline，原32科学/解析/导出函数AST不变。

实际复现包4514275已闭合；contract5/prepared12已生成，G4实际4514278 PASS/24workers，gates/g4_frozen_manifest_v6.json。G4先前4514276/77相对引用定位失败均保留：以后追加source必须使用绝对路径，既有混合引用的核验应在项目根运行；不修改已冻结source/inventory掩盖错误。本轮六个测试clone终态后已清理约6.93GB，全部report/log/manifest仍保留。

SCI子集修复4514265实际178/178读回通过，163完整SCI补回metadata、2未完整释放、13terminal task恢复；保护原7个RUN/PD不变，未重QM。19root纯导出4514274在queue只读SELECT失败，尚未导出任何root，不能称闭合；修复仍限元数据库，原SCI/LMDB保持只读。G3新策略remaining测算212.46GB峰值余量为点时值，正式提交前更新真实quota。

新的72+6仍须单独用户授权，原69+4授权已经实际使用。旧R11仍正常运行，未经具体软件恢复授权不因普通锁错误写STOP。批准后先checkpoint正常退出、确认全部旧229终态、全范围SCI reconciliation与纯导出、生产schema bootstrap，再一次提交新72+6；最终200条与原六停止条件保持。当前尚未建立R12 G0、未写新phase用户授权、未提交新科学阶段。

## 2026-10-12 补交后仍有锁故障，R12 尚未冻结

69 主任务＋4 收尾补交和原两收尾依赖调整已按授权实际完成，但运行后再次出现 constructor/运行期锁错误；75 项调度核验 PASS、144 进程 warm 启动 PASS 都不能代替真实生命周期通过。该补交授权已经实施，不能复用于另一个正式阶段。活动 R11 冻结源、科学输出和历史失败证据均保持。

当前 R12 candidate_v4 只改元数据锁等待，SHA6752e2b05d05e17a5eabb14db34785b0bae82562449920f526a104b085d9ba9c；32 个原科学/解析/导出函数 AST 不变，16 worker 隔离锁测试4514256已PASS；五节点480 writers/22 parents真实大小全生命周期4514257–4514263仍在运行，尚未声称PASS/冻结。13节点只有只读元数据probe，不能写成六节点R12压力通过。前四轮私有fixture数据库已核终态/所有权后清理约4.48GB，保留所有证明；只结束了证明确已失败且无QM的自有元数据压力作业，没有取消正式科学任务。

小时监控v4 UID1278/PID3439043/start_ticks8054882766，sourceSHA43a055e5e51152f74dcb3f762a04cd4e75c09c20e82ae3af3c29446345fb3ca9。仅原指南2/3/5/6的新鲜实证可自动写STOP；普通FAILED、锁错误、缺账目或未知配额不新增停止条件，首5%仍由runner处理。只读SCI恢复审查4514255因queue读锁中断一root，未证明SCI损坏，也未闭合；需有界read重试，不重做QM、不混旧execution/contract/package。完整证据及后续状态见 runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v2.md；此条为点时记录，不当作最终完成。

按本技能执行服务器工作。用户在当前会话中的明确要求优先于旧记录；使用前读取项目的 `AGENTS.md`，发现过时或冲突的约束时一并修正。命令示例和核验记录见 [references/commands.md](references/commands.md)，在连接、提交、GPU 核验或存储检查时按需读取。

## 2026-10-12 WP5 启动失败补交已获用户授权并完成

用户实际选择“允许本次补交与依赖调整（建议）”，授权只补交量化开始前退出的69主任务和4收尾，并更新原4514142/4514143依赖。Root已提交主4514153–4514221、收尾4514222–4514225，原两个收尾更新own-node afterany后解除临时hold；4514137/4514139/4514140保留。权威与回执在 runs/phase1_wp5_20261011/submission/startup_replacement_v1/；submitted_jobs.json SHA11e7fd66f653738e765b2308460ea33897899532189fc823d7ee075744ffdbe1。实际75项调度核验PASS，原六节点、24CPU/32GiB/48h、冻结main11/contract4不变。已完成且控制器清除的4514140作为已满足afterany保留逻辑证明。此前冷启动锁故障仍保留历史；六节点实际warm queue启动144进程已PASS，不再重做相同测试。累计成本包含所有阶段真实失败启动作业，人口只统计同一队列一次。当前例外不授权本次六收尾后再开新波次；最终200条和原六停止条件仍适用。不得重复请求本次补交授权或重提已成功三主任务。
## 2026-10-12 WP5 一次性续算已获用户明确授权

用户实际回复“允许按准备方案一次性提交续算（建议）”。仅本次新增的一阶段72主任务+6个own-node afterany收尾已获授权，不再次询问。权威记录在 runs/phase1_wp5_20261011/submission/recovery_attempt_v11/user_recovery_authority_20261012_v1.json，绑定原提交、冻结contract4、闭合reconciliation和prepared_plan_v11；新实际提交记录在同目录submitted_jobs.json。Root已一次性实际提交主4514069–4514140、收尾4514141–4514146，全部24CPU32GiB48h、六台已授权节点；原STOP按用户授权归档保留，原SCI/提交记录不覆盖。原六收尾终态后，3Mol30records已纯导出闭合，余1158499Mol/10618894records；G3剩余峰值只扣已计入quota的唯一永久输出，不重复收费。新旧两phase的coreh去重累计、SCI人口不相加；只读观察使用wp5_hourly_observe_v2.py。若本次六收尾后仍有余项，指南3.5仍要求报告等用户指示，不自动再开新phase。最终200条重算与其他原要求保持。
## 2026-10-11 WP5 共享 SQLite 队列并发修复

正式72主任务/6收尾的原提交记录位于 runs/phase1_wp5_20261011/submission/submitted_jobs.json；原runner10和全部科学源码保留。首5%附近实际发生大量SQLITE_BUSY锁错误，不能标成SCF或量化方法失败。DELETE/FULL连接原已有BEGIN IMMEDIATE；放大因素为每parent重复12遍宽JSON统计、owner无索引的百万行写扫描以及超时退出后的收尾竞争。

独立runner11（e7828b4b78e42cd9a31c686ee30190cc9e788630d9c737980300606aa0236e7b）仅修队列：首5%跨进程单publisher+不可变绑定缓存、owner/cleanup索引、BUSY/LOCKED-only短事务回退、deadline与分块导出登记。实际隔离压力4514056–63全部完成，六节点144workers/29health、1,220,466合成行、10,080唯一领取/完成，415,389次fixture锁重试后闭合，科学attempt消耗0；它是metadata验证，不冒称新量化G6。证明在 gates/metadata_queue_fixture/queue_fix_v11_20261011_run1/report.json；实际首5%科学成功率另已PASS，最大下降0.115403个百分点。

完整SCI可以早于全局queue.finish持久化，不能凭RETRY_PENDING就重新QM。恢复先等原78作业终态，核完整整分子/12任务/execution/wireSHA，补回孤儿metadata并纯导出。旧attempt0回执/导出引用不能嫁接完整attempt1；新reconcile_v2保留beforeimage/历史并按真实execution定位。旧失效export claim只在其作业真实终态后恢复；显式处理当前export_roots。新正式提交仍受用户指南第3步第5条约束：原六收尾后仍余时报告等指示，不能自动新增正式波次。

Root20:19:54设置的SHARED_QUEUE_SQLITE_LOCK_RUNTIME_FAILURE标记是本次已实施的软件恢复控制事实，不扩展指南六项停止条件或形成新的通用审批要求。新source/contract/package与旧版本分别保存；不修改活动冻结源码、不把metadata retry计为科学retry、不删原SCI或历史数据。仅清本轮已结束且证明无依赖的临时fixture输入，保留全部验证证明。
## 2026-10-11 本次 WP5 节点替换与原始输出新策略

用户已明确授权本次 WP5 测试与正式任务整体采用 compute-0-12/13/14/17/18/19，15→12、16→13，仍为29槽4/4/4/8/4/5。该授权覆盖下文原14–19范围；真实hostname必须记录，不再次询问相同替换。对应权威与任务清单见 runs/phase1_wp5_20261011/gates/wp5_node_replacement_user_approved.json 和 packing/node_assignment_v3/tasks.json。

用户六条新要求明确取代原指南G3和第4步原始输出规定；原文及结构化权威位于 runs/phase1_wp5_20261011/reports/user_raw_retention_override_20261011_v1.md 和 configs/user_raw_retention_override_20261011_v1.json。普通成功非审计计算只在节点本地scratch解析后立即删除原始输出，共享归档中连metadata占位行也不保留。仅保留全部CALCULATION_FAILED、PROPERTY_FAILED、TIMEOUT，以及按file_group×size_stratum约1%分层随机选中的record全部12任务完整输出；输入文件在所有类别均不保存，仅在运行前计算逐输入文件SHA。取消最低构象强制保留。

每record/task的parquet保存status、software_version_id、elapsed_seconds、scf_iterations、converged、input_file_sha256；SCF无原生证据时保留NULL。永久复现包须保存软件二进制或精确环境、runner/parser/关键词/随机种子规则/登记表及全部SHA。新增exact50记录同环境双算，按原字段精度或严格位比较解析值，不比较raw文本字节；真正复现不通过则停报，禁止正式提交。G5验证registry_v2全部字段提取和序列化覆盖，不将缺代码或填零当完成。原历史归档例外有效，最终200条验收仍必做。

新G3须重新实测新格式parquet、失败与1%审计归档、400GB训练格式预留及临时峰值，峰值200GB余量与运行停止300GB余量不变。旧3.19/3.59/5.80TB是已被替代的策略估算，不能当新策略结论。旧已运行测试与源码保留作为历史，不能直接声称新归档链路通过。原LMDB及manifest仍只读；Root为唯一Slurm提交者，账户仍是zixiao@202.38.247.57。

## 2026-10-11 WP5 G5 历史归档例外与记账通路

用户已明确确认：“接受历史归档缺口为 G5 例外，结合六节点完整链路测试及最终200条重算继续（建议）”。这覆盖下方 G5 必须完整历史重解析的要求；不再重复询问该例外，不把原 NOT_PASS/DIFF 改成回归 PASS。G1/G2/G3/G4/G6 和最终200条仍需实测通过。缺的是旧试算生成的软件输出（MOPAC AUX、xTB 原 JSON/FOD/gradient/WBO 等），不是原 LMDB、输入结构或已解析标签。原始 SP JSON 保留量为零，不能把 AUX 的抽样保留推广为 JSON 抽样。

本轮实际 compute-0-14 的 sacct 连接 localhost:6819 拒绝；向 sonmi、10.1.1.1 和授权公网202.38.247.57 的 SSH:22 均实际拒绝。不能用未验证的内网 SSH 作为恢复通路。Root 登录 sonmi 发布真实 sacct/queue/quota 小型元信息；已实测 compute-0-14 从共享快照读回四个原作业的真实 FAILED 状态。工作 helper 为 wp5_accounting_v2.py，核对真实 UID1278/User zixiao、sonmi、注册job/receipt和查询退出码、发布来源与新鲜度，缺失/失败不伪造空成功。当前有界 publisher 每60秒发布、最多240小时；对话级大批量检查仍按用户1小时间隔。只读元信息发布可在登录节点，科学计算仍走指定计算节点的Slurm。本轮 helper/runner6/harness6 只改记账通路，原科学协议与已完成结果不变。

## 2026-10-11 WP5 正式数据计算指南已获授权
本轮执行项目根《WP5 正式计算行动指南（Codex）.md》，SHA256 cd227614ee0a9133b45ea96e3993dbbb0a72ff1b1ead51302a7c55e01a62df3e。用户再次明确账户必须是 zixiao@202.38.247.57:22；“华工HPC”是技能名称，不能据此切换学校252服务器。只进行数据计算，无训练。新指南覆盖之前尚待配置选择的门：I01放宽，隔离4900条/490分子不算，TRAIN–FULL连通分量泄漏移FULL，五组maxheavy22/26/30/36，PM7 B/离子/水/辛醇+xTB7类全构象，不做POLAR/ESP/Hess/OHess。P能量使用本轮重算PM7 Hf，原值另外保留。
- 第0步六道闸门 G1–G6 均须实际通过；未通过时按指南给实证、原因与备选方案并等待用户确认。不得把缺失历史raw字段当回归通过。
- 测试与正式数据计算都仅 compute-0-14..19。正式每槽24CPU/32GiB/48h，29槽4/4/4/8/4/5；全部主任务和6个afterany收尾在一个提交阶段预先提交，不能轮次续交。
- 只在节点本地scratch生成逐计算文件。共享仅永久float64 family parquet、dictionary zstd SQLite或blobparquet容器及checkpoint/清单；本轮不建任何LMDB。原LMDB和原manifest只读。
- 不删除任何本轮之前已存在的文件；只允许清理本轮产生且确认无继续用途的临时文件。前轮清理授权不能扩展为这轮历史目录清理。
- 指南列出的六项运行停止条件触发时写全局停止标记，停止领取新Mol、落盘checkpoint、正常退出，不能scancel。配额余300GB、G3策略峰值余200GB；普通40h与>75heavy20h打包、预测任务>46h拆分；小时级批量探测。
- 完成后按指南200条同环境重算、allstatus人口闭合、SHA/读回、pilot对比、分布/QC及scratch清空验收，用户决定lmdb_1字段之后才写回。
- 新根 runs/phase1_wp5_20261011。2026-10-11本机旧全局X盘阻塞，标准net use删除后出现全局残留/85；未杀旧SYSTEM sshfs、未删除服务器文件。临时用户SSHFS底层Y指向同一远端项目，经native SSH loopback tunnel到已核sonmi内网10.1.1.1:22、HostKeyAlias=202.38.247.57、StrictHostKeyChecking=yes/原key；若native X卡住而既有Y已核为同一live树，在新PowerShell局部作用域使用New-PSDrive -Name X -PSProvider FileSystem -Root Y:\ -Scope Local，并在同进程经SessionState.Path.GetUnresolvedProviderPathFromPSPath解析X为native Y路径后编辑；无需Remove-PSDrive，不以全局net use或停止挂载进程抢修。所有编辑仍经X逻辑入口解析为实际live Y路径，绝不写OneDrive项目复制。此为连接修复，不能改变服务器账户或科学范围。

## 2026-10-11 C3 两节点替代已获用户确认

本轮 Phase1 剩余筛查中，原 C3 的 compute-0-15/16 无法取得24个空闲CPU，用户明确选择“允许改用空闲的12、13节点补测，并明确标注替代”。仅本轮 C3 允许原设计15→实际12、原设计16→实际13；保持原15/16的分子hash桶、k24、90min、32GiB和只读原数据，在报告中同时写原设计与真实hostname，不把15/16声称实测。Root核实并取消尚未启动的自有原两作业后统一补交。已运行14/17/18/19不重跑。WP5原14–19范围及最终配置/字段格式决策门不因此放开。
## 当前资源与探测规则（2026-10-09，用户明确修订）

- CPU 测试、扫描、预处理和 GPU 任务，每项计算作业均至少申请 16 个 Slurm CPU 核；单进程通常使用 `--cpus-per-task=16`，多进程分配的总 CPU 核数至少为 16。GPU 任务也须至少配备 16 个主机 CPU 核；GPU 数量按实际任务和设备资源核定。
- 加核须落实到有效并行：根据任务设置 worker、线程或互不重叠的输入分片，并验证实际吞吐。不能只申请 16 核却继续单线程扫描；worker 与 BLAS/OpenMP 线程合计须控制在实际分配内。串行瓶颈先调整实现或任务拆分；不能用不稳定的目录顺序跳过未闭合数据。
- 在现场 CPU、内存、GPU、I/O 和存储预算允许时，尽可能提高 CPU 与 GPU 任务并发；旧“最多 2 个”或 Stage61“最多 4 个”项目作业数不再是当前固定上限。保持唯一提交协调者、作业去重、每个任务资源边界及设备归属。CPU 任务优先 CPU 分区的 IDLE 节点；GPU 任务在 GPU 节点执行；资源暂不足 16 核时等待或换节点，不自动降为单核。
- 提交前使用 `sinfo --Node`、`scontrol show node/partition` 与本账户队列核对可用资源，按实际分配记账；MIXED 节点仍须有足够空闲核数，声明内存合计加新任务不超过 RealMemory 的 85%。并发增加不改变原科学范围、冻结数据或尚未取得的实验授权。
- 核对节点内存时同时汇总该节点全部用户作业的总声明内存；AllocMem=0不能视为零占用。结合节点队列与各作业实际节点、内存声明，按队列合计和AllocMem中较大值加新作业核对85%上限；方法与本次证据见 [references/commands.md](references/commands.md) 的“AllocMem 为零时的声明内存”。
- 对预计或实际运行至少半小时的 CPU/GPU 长任务，对话级状态探测改为每 10 分钟一次（600 秒）；一次批量查询所有相关作业及必要的小型进度产物。避免每分钟返回模型、重复读 skill、生成无变化的报告快照或重审已闭合结果。用户查询、实际终态通知或异常事件到达时及时处理。
- 10 分钟间隔针对消耗 token 的交互探测；作业内已有的资源保护、日志持久化及自动告警继续按原要求运行。用户暂停任务后停止自动审计、后续提交与轮询；已运行作业单独核对暂停能力，不能把目标 paused 冒称 Slurm 作业已暂停。

## 登录与目录

| 用途 | 连接与路径 |
| --- | --- |
| 默认工作服务器 | `zixiao@202.38.247.57:22`，登录节点主机名 `sonmi` |
| Windows SSH 别名 | `descriptor-analysis-remote` |
| 已配置的私钥文件 | `C:/Users/mint/.ssh/id_ed25519_descriptor_analysis`；仅使用密钥，不读取或输出私钥内容 |
| 默认项目目录 | `/share/home/zixiao/descriptor_analysis` |
| Windows 实时挂载 | `X:\`，对应上述项目目录；文件修改立即发生在服务器上 |
| PhyChem_MFM 当前独立重构 | `/share/home/zixiao/PhyChem_MFM_ICLR2027`；Phase 1 优先复用其共享 H0 接口 |
| PhyChem_MFM 历史实现 | 项目内 `modern_ML_representation/support_scripts/MFM_descriptor`；作为参考保留，不将旧 fusion 数值混入新 H0 实验 |
| 本轮 Phase 1 正式任务目标 | 默认 sonmi 集群 `compute-0-20`、`compute-0-21`、`compute-0-22`；用户已于2026-10-02指定，GPU 型号、准入和隔离仍以现场核验为准 |
| 短程测试节点 | `compute-0-20`、`compute-0-21`，从默认服务器登录节点经 SSH 进入 |
| 既有学校预训练服务器 | `202264640132@202.38.252.202:22`；付费环境，正式预训练仍须用户明确授权启动 |

- 开始工作先验证实时挂载与密钥登录，核对远端用户、主机和工作目录。执行 Linux 命令使用 SSH；服务器脚本使用服务器上的环境与解释器。
- 从 Windows 使用 `ssh descriptor-analysis-remote` 登录；从登录节点执行 `ssh compute-0-20` 或 `ssh compute-0-21`，然后进入项目目录。实际连接须启用 `StrictHostKeyChecking=yes`；核对 `hostname` 后再执行计算。
- Windows PowerShell 到原生 `ssh` 的嵌套引号不保证按字面送到远端 shell；复杂查询或含管道、正则和嵌套引号的调用，写到自有远端 Python 元信息脚本，再用固定绝对路径启动，脚本内以 `subprocess` 参数列表及 `shell=False` 执行。2026-10-08 的 `script|batch` 正则因引号被去掉而意外创建 Unix at job 1；已按本次创建输出、UID/owner/队列时间核定，只清理该自有 job，before/after/退出码证明保留。不要把命令字符串或 JSON 序列化当 shell 转义，也不新增审批或停审条件。
- 在保持交互 SSH 会话并批量发送命令时，非交互子 SSH 使用 `-n`（或 `</dev/null`），防止它消耗父会话的 stdin、吞掉后续命令。正常交互登录及确需从 stdin 接收脚本的 SSH 不加 `-n`；脚本输入应与父会话后续命令分开提供。
- 在父交互 shell/PTY 中运行不需要输入的 `srun` 时，使用 `--input=none`，并将调用进程 stdin 设为 `subprocess.DEVNULL` 或 shell 的 `</dev/null`。不能只处理子 SSH 而让 `srun` 继续转发待执行的父命令。确需交互输入的步骤单独提供输入，不套用此非交互规则。Stage48 v1 的退出码未记录；v2 隔离 stdin 后实际退出0，旧观察及缺失状态保留，不为补退出码重跑科学任务，见命令参考。
- 各层命令的退出码在执行该命令的同一层 shell 立即捕获，随后再执行日志、查询等操作。缺失退出码或日志不构成成功证据；核对已关闭产物、实际进程或 Slurm 终态，不为补日志重跑耗时科学任务。2026-10-01 曾因子 SSH 读取父 PTY 输入而未生成预定退出码文件，详见命令参考。
- 只读检查、文件编辑、调度查询可在登录节点进行；模型计算、数据密集处理及重型测试进入计算节点或调度分配的节点。
- GPU 型号或 CUDA 环境变化时，先在本次自有有界作业中验证基础 CUDA kernel及实际模型路径；不只凭版本号、arch list或另一型号成功推定兼容。新增依赖优先放入独立环境，保留原环境与科学源码，计入下载临时文件和缓存峰值。2026-10-02 的5090/cu126基础运算失败；独立cu128环境在21节点已通过基础运算和完整模型的一次SDP更新、W&B持久记录及检查点恢复。22节点的实际模型路径仍待核验，兼容性通过不证明资源独占。
- 密码和 W&B API key 使用既有安全认证或环境变量；不得写入技能、仓库、脚本、日志、shell 历史或训练配置，也不得在诊断输出中打印。
- 主机密钥变更时，先通过管理员或可信记录核对新指纹。不得关闭主机验证、盲目接受新密钥或自动删除 `known_hosts` 条目。学校服务器的认证、项目路径和调度参数独立核实，不沿用默认服务器的路径或密钥假设。

## 当前 PhyChem_MFM Phase 1 监督约束

- 用户在2026-10-01明确：本阶段电荷指已有 MOPAC 输出的 `NET ATOMIC CHARGES`，单位 `e`；复用已有 LMDB 标签，不将旧指引中的 Mulliken 名称当成另一个计算任务，不补做 QM。PM7 能量仍为 `FINAL HEAT OF FORMATION`，单位 `kcal/mol`。
- 报告、任务清单、配置与指标统一采用已确认的名称和单位。标签来源、结构单位、身份或原子编号对应须以实际源记录/生成脚本核验；发现矛盾时留证并修正，不能仅凭字段名或旧 PASS 推定有效。
- 阶段状态以 `docs/phase1/WORK_STATUS.md` 及原始证据为准。有界正确性测试和开发训练不等于正式矩阵完成；未确认的划分修复及未冻结的协议不静默投入正式训练。

## 短程测试

- 用户允许在 `compute-0-20` 或 `compute-0-21` 上经 SSH 执行小规模、可终止的短程测试。运行前确认节点身份、当前占用与可用资源；站点的实际准入规则仍须遵守。
- 为测试明确小数据子集、步数/批次数和墙钟时间上限；CPU 核数遵守上方当前规则，每任务至少 16 核，并落实有效并行。GPU 数量、内存与输出按验证目的及现场资源核定；样例时限不代表统一阈值。
- GPU 测试须同时核对队列与实际显卡进程；不能把 `squeue` 没有作业、节点显示 `IDLE` 或显存暂时空闲当作显卡预约。发现其他用户占用或资源归属不清时换节点、使用 CPU、申请调度资源或等待，不抢占显卡。
- 直接 SSH 测试应保持有界并在完成后结束；不得把它延长为正式训练、长程预处理或无人管理的后台计算。正式工作转入下一节的调度流程。

## 正式任务与作业边界

- 当前 Phase 1 正式任务已获用户授权在默认 sonmi 集群的 `compute-0-20`、`compute-0-21`、`compute-0-22` 上提交；不再将学校付费服务器授权作为该范围的前置条件。按现场可用 partition 约束目标节点，仍须满足后续 GPU 保护、监控和存储要求。该选择不扩展直接 SSH 短测节点范围，也不授权更改集群配置。
- 所有正式任务通过 **Slurm** 提交：`sbatch` 提交批处理脚本，`squeue` 查询队列。用户所说的“用 squeue 系统提交”按此流程执行，不能编造 `squeue` 的提交参数。
- 使用适合目标集群的已有脚本或按其规则编写脚本，核验 partition、account、QoS、CPU、内存、GPU、时限、工作目录、环境和输出目录；不得猜测或跨集群复制调度参数。学校服务器首次提交前核对既有 sbatch 脚本及与提交相关的历史记录，不输出无关历史或秘密。
- 从 Windows 写入 Slurm 脚本后，提交前按原始 bytes 检查无 CR、换行为 LF；bash -n 通过不证明 sbatch 接受换行。2026-10-07 Stage61 v2 验证脚本被实际 DOS CRLF 检查拒绝，未创建 job 或执行科学步骤；保留该拒绝与冻结源，另写仅换行归一化的独立脚本、新请求及任务绑定，不能改已注册源或把提交拒绝写成科学失败。
- 批处理环境不默认继承交互登录节点的 PATH/conda 状态；使用已核实的解释器绝对路径或明确的环境初始化。必需依赖在作业中核验；展示 Git 版本等可选诊断不得阻断实际任务，Git 不可用时明确记录并保留实际源码 hash。2026-10-01 的CPU作业4511886曾因此在读数据前退出，修订后4511887已实际执行。
- Python 启动和运行环境绑定保留已核实的逻辑绝对入口，例如 `venv/bin/python` 或 `Path(sys.executable).absolute()`；不得用 `Path.resolve()`、`realpath` 或 `readlink -f` 的目标路径替换该入口。解析出的 binary target 只作额外诊断，不作为启动 argv 或解释器环境相等的替代。Stage53 同一 binary 的逻辑venv入口与目标入口实际选择cu128/cu126不同包环境；该标准库元数据观察不证明GPU兼容，见命令参考。
- 包版本比较须区分发行元数据与库的显示格式。Stage61 的 RDKit 发行版本 `2025.9.5` 与 rdBase `2025.09.5` 是同一数字点分版本；只可规范化纯数字分量的前导零，不同版本、额外分量或预发布后缀仍拒绝。4512378 在此启动门禁退出、未进入构象或 PM7；原失败留存，仅修复独立入口后继续，不能为字符串差异升级或替换依赖。
- CPU 预算按实际 `sacct` 主作业的 `AllocCPUS × ElapsedRaw` 计量，不按请求核数猜测，也不重复相加 batch/extern。4512381 请求1CPU但CPU17实际分配2CPU，1秒诊断计2CPU秒；真实失败、前置检查和后续执行均计入同一有界实验预算。
- 禁止在 Slurm 分配之外，通过登录节点或直接 SSH 的 `python`、`torchrun`、`nohup`、`tmux`、`screen` 等方式启动正式计算。作业获得资源后，可按站点规范在作业内用 `srun` 或既有启动器运行。
- 已结束作业可能已从Slurm控制器清除，`squeue -j <旧ID>` 会以非零退出并报 `Invalid job id specified`；不能据此重跑、取消任务或否定已闭合结果。核对本账户当前 `squeue -u zixiao` 返回的精确ID，并结合已留存的实际 `sacct` 终态及退出码确认原作业已结束。2026-10-02清理4511954的合成测试临时文件时已遇到此情况，第一次检查未删除文件，修正查询后按精确路径完成。
- 当前项目作业并发遵守上方2026-10-09资源规则，不再沿用旧两作业固定上限。包含PENDING和Root额外提交，使用已核验协调者识别的命名并统一去重、记账。暂停提交协调者时核对精确PID/UID/start_ticks；恢复前绑定新输出根至全phase存储计量。
- 提交前检查本账户是否已有相同任务，避免重复提交。记录作业 ID、脚本、配置和日志路径；获得作业 ID 仅表示已提交，不表示训练已启动或完成。用 `squeue`、日志和 `sacct` 核验排队、运行和最终退出状态。
- 精确核验 CPU 节点时，用 `sinfo --Node --nodes=目标节点` 取得逐节点行，再结合 `scontrol show node 目标节点` 核对实际状态、空闲 CPU 与声明内存。默认 `sinfo` 可能把多个节点压缩为 `compute-[17,19]`；不能因没有单独的完整节点名行就误判没有 IDLE 节点。2026-10-08 的首次 preflight 因压缩行未匹配精确节点而在 READY/sbatch 前退出，加 `--Node` 后才提交4512488；该事实不固定任何节点的当前占用。
- 所有已被 Root 注册具体路径和完整 SHA256 的 prepared 模板也保留原字节；后续 partial 计数或成本补充写入独立新路径，不覆盖 active READY、源码或 RootReview。误改时保留 mutation 说明与修改后副本，只有恢复候选的实际字节数和完整原 SHA256 均精确匹配已注册引用才恢复原路径；否则如实保留 owned prepared 差异，不把它当原数据/manifest 漂移触发 HARD_STOP 或重跑科学任务。4512488 的运行 READY/六份源码保持不变；prepared v2 模板已在12589字节与完整原 SHA 同时匹配后精确恢复，新增成本另存 v3。
- 共享文件系统、登录节点和 SSHFS 的文件长度/mtime 可能滞后于正在写入的计算节点。怀疑任务无进展时，在本次自有 Slurm 分配内进行有界只读核验，结合程序日志及最终 summary/退出状态判断；不能仅因缓存的零长度、空日志或异常 accounting 字段而重启、取消或重复提交。记录最终关闭文件后的大小/hash。4511889运行时登录端显示账本0字节，作业内核验已写143MB，随后完整完成范围。
- **不得 kill、scancel、挂起、抢占或修改其他用户的任务。** 不使用宽泛的 `pkill`、`killall` 或批量取消来清理环境。
- 若需要结束本次工作创建的作业，先核对精确 job ID/PID、用户身份及任务归属，在已有任务授权范围内处理；停止自己测试的超时进程可以自动完成。与当前工作无关的既有作业不得因“腾出资源”而取消。

- Slurm 记账在当前计算节点可能指向不可达的 `localhost:6819`。作业内测试退出码与终态记账分开保存；需要时由登录节点查询 `sacct`，按原真实 parent/component 状态闭合，不为查询失败重跑已完成测试或科学计算，也不将组件通过升级为原 FAILED 父作业成功。Stage57 4512028 的五项文件系统测试实际退出0，外围查询失败保持 FAILED；root 登录节点另行闭合，见命令参考。
- 分段墙钟上限不等于完整三轮预算；正常 partial 段以实际保存游标、accounting、wrapper、receipt 和 W&B 核验后继续。为修复某条件关闭提交窗口时，明确记录恢复步骤；不能让不受该故障影响且已验证的条件无限等待，也不能将单段 COMPLETED 写成全部训练完成。2026-10-07：SDP 正常分段后因窗口未恢复出现空档，Root 已普通续交4512132，并实测第一新更新13,394，源码01b8/协议f344未改；P显存保护失败仍须独立修复。

## 正式模型训练的 GPU 保护

除下述明确授权的当前 Phase 1 例外外，正式 GPU 训练启动前必须有可核验的独占或隔离依据，防止其他作业共享显卡、挤占显存或使吞吐暴跌。分别核验以下问题：

1. **资源分配**：确认目标节点已在 Slurm 中登记正确 GPU GRES/TRES；按集群支持的方式申请明确的 GPU 数量与型号，例如 `--gres=gpu:数量`。使用作业分配的设备，保留调度器设置的 `CUDA_VISIBLE_DEVICES`，不扩大到未分配显卡。
2. **资源隔离**：确认调度器不会把同一物理 GPU 再分配给他人，并核验站点设备隔离及 SSH 准入约束，例如生效的 `task/cgroup`、`ConstrainDevices=yes` 与适当的 SSH 作业归属控制，或管理员明确确认的等效保护。`CUDA_VISIBLE_DEVICES`、文件锁和“当前无人使用”都不能单独防止其他用户访问显卡。
3. **共享与调度抢占**：核对 partition/QoS 的共享及 Preempt 配置，选用符合本任务稳定性要求的非抢占资源。不要启用 `--oversubscribe`，也不要以 `--exclusive=user` 代替完整独占。需要整节点独占时，使用站点允许的 `--exclusive`，并仍核实显卡与 SSH 隔离；此参数本身不能阻止绕过调度器的进程。
4. **容量与实际进程**：在同类 GPU 上用代表性输入做有界的前向、反向和 optimizer-step 测试，测量显存峰值与 CPU RAM，给 batch size、数据加载、DDP 和保存操作预留合理余量。CPU 的 `--mem` 不等于显存配额。作业启动时核对分配、设备和显卡进程归属，不能因资源申请成功便跳过此检查。
5. **持续监控**：记录吞吐、step 时间、显存峰值、GPU 利用率和失败原因。出现异常共享、性能骤降或 OOM 时，保存诊断并处理本次作业，不能通过杀他人进程、额外占满显存或修改系统 GPU 模式来“保护”训练。

无法核实保护机制，或目标节点没有登记 GPU 资源时，先继续代码准备与必要的有界测试，明确报告缺失的保障，解决隔离或选择已获授权且受保护的资源后再启动正式 GPU 训练。不得虚称已保证不会抢占或 OOM；模型自身的显存需求还须单独验证。最新现场核验情况见命令参考中的“已核验事实”，每次正式提交前重新核实。

- `gpu_num` 须核对实际工具、字段及 GPU 申请映射，不能把变量名当成已生效的调度隔离。单节点任务不要将多个节点同时写入 `--nodelist` 当作候选池；列表要求全部节点，与 `--nodes=1` 冲突。2026-10-02 对20、21、22的分节点原生 GPU 申请检查均因 Invalid GRES 失败，未获得原生 GPU 预约或隔离证明；当前 Phase 1 按下条用户明确授权的例外执行，详见命令参考。

### 当前 Phase 1 的明确共享 GPU 例外（2026-10-02）

本会话用户在得知三节点未验证 GPU 隔离、可能共享降速或 OOM 后明确回答：“是，接受风险并启动”。此最新授权优先于先前独占要求，仅对当前 Phase 1及用户随后明确授权的模型/数据修订、sonmi compute-0-20/21/22生效：允许真实自有 Slurm CPU allocation 内选择启动时实测空闲的一张 GPU，显式绑定并记录实际 CUDA UUID/硬件环境。native GPU GRES 未登记、device/SSH 隔离未建立本身不阻止本次已授权任务；记录为 USER_ACCEPTED_SHARED_GPU_RISK，不能声称预约、独占或防抢占 PASS。

这不推广到其它任务、服务器或会话，不扩大科学范围或冻结预算。仍须 Slurm、W&B 持久记录、实际 UID/job/node、同种 GPU/环境配对、quota、8h、用户最新要求的每任务16CPU/64GiB主机内存、明确记录的运行期RSS及实测UUID显存余量上限、2GiB run输出；保留启动时 foreign-process 检查和运行期共享/性能监控。单纯运行期 foreign 出现记录风险；异常或资源阈值只处理本作业自有进程，不杀他人，不自动重采或重跑。旧严格隔离政策仍为其它情况的默认规则。

### 当前 Phase 1 的资源修正（2026-10-02）

用户随后明确要求每个正式训练任务16个CPU、64GB主机内存，以及每张GPU仅一个本项目任务。Slurm使用`--cpus-per-task=16 --mem=64G`，主机内存与显存分别核对；此前2CPU/12GiB申请、8GiB RSS/12GiB显存上限仅为旧协议点时配置，不得作为当前硬编码继续执行。实际RSS停止阈值须给64GiB申请保留系统/缓存开销；GPU上限按所选完整UUID的实测总显存扣除明确安全余量派生并记录，不能按常规型号规格猜测容量。

提交和实际执行都核对自有任务与GPU UUID，单卡仅安排一个本项目任务，协作锁不等于防止其它用户SSH占用。提高GPU有效利用率优先解决数据构建、缓存、预取及实际计算batch瓶颈，不分配无用张量伪称“吃满”。缓存须有界、不改变标签/视图seed/样本顺序，不缓存最终测试标签；batch/更新步数/曝光量变化须一致更新全部对照条件的科学配置和新不可变协议，保留旧结果来源。

### 当前 Phase 1 的模型与数据规模修正（2026-10-02）

用户最新要求适度缩小模型、利用完整dataset中更多结构（用户报告约16M结构/1.8M分子式），并增大有效batch以减少总批次。旧58k选池、512维/6层共享主干、batch2与49993更新只作为历史配置，不再自动提交为当前正式方案；16CPU/64GiB及已接受共享GPU风险的范围保持。

首先核对原始LMDB的真实structure/parent molecule/化学身份/分子式口径；已有扰动副本不重复作为新样本计数，formula不能替代分子身份。大规模数据采用有界缓存、流式读取和预取，不将16M preparedgraphs全部塞入64GiB或复制至有限quota。模型尺寸/batch/实际数据范围/曝光量/学习率调度/验证频率与新预算需基于当前实际有界profile记录并冻结为新协议；重新生成新模型的成对初始化及适用于新训练集的归一化，不冒用旧58k fit/init或120文件字节兼容证明。保留MOPAC NET ATOMIC CHARGES及用户确认的QM9 fold处理，不以扩大数据为由访问最终测试目标。

有PyTorch线程/运行时和多worker预取的当前路径，显式选择安全的spawn或经实际验证的等效上下文，并给worker等待设置有限超时；正常耗尽、异常和分段提前退出都须关闭本作业worker。动态加载的transport只序列化已绑定的源路径/hash，在worker中重建函数和只读LMDB句柄，不能把父进程打开的环境或运行时当作可安全继承。必须实测多worker及未消费预取的恢复，不能以0-worker通过代替。CPU4511978的超时保留为点时失败；之后4511982实际stack确认长TMPDIR触发AF_UNIX path too long，因此不得将早先超时直接归因于fork。Python启动前使用短的节点临时目录，例如按实际Slurm job ID唯一命名的/tmp目录；先验证路径、UID和不存在，再以0700创建，正常/异常闭合后只清理该自有范围，日志及W&B/checkpoint留在持久证据目录。worker关闭后必须实际join并确认退出，不能把私有shutdown调用返回当作闭合证明。新脚本在正式提交前可在登录节点进行轻量标准库AST语法检查，这不属于模型或数据计算。带自校验seal的JSON产物必须在保存与读取往返后得到一致摘要；对象键须在seal之前采用统一字符串形式。失败或缺少真实child退出0验收的chunk不得凭手工改seal升级为可恢复产物。

### 当前 Phase 1 的损失平衡修正（2026-10-02）

用户要求在正式训练前加入损失归一化与动态系数，主要目标是避免某个任务主导共享表示的优化。先核对既有 train-only 连续目标标准化、有效标签掩码及组内/组间聚合，不将已有 normalizer 误报为缺失；固定等权平均不能作为梯度平衡证明。

按真实共享主干梯度贡献验证方案，同时考虑 S/D/P 组间和组内任务的差异。动态尺度与权重只能用训练来源更新，缺失监督任务不更新状态；权重须保持正值并有明确约束，避免任务被静默压到零或动态总尺度变相改变全局学习率。测量权重更新的实际开销与修改前后梯度占比、稳定性，不能只使 loss 数值接近或宣称完全消除梯度冲突。保留每任务原始/标准化损失、有效计数、系数及共享梯度诊断，并将控制器完整状态纳入检查点恢复。

新的平衡算法及其校准、更新间隔、掩码、固定验证指标和恢复规则纳入新科学协议；阶段48旧损失容量试跑仅提供该试跑范围的容量参考，不代表新正式方案通过。最终测试目标不用于尺度拟合、动态权重、校准或方案选择，验证集不更新动态状态。以实际代码/试跑为准；若借鉴 GradNorm 而实现 EMA 等变体，明确其具体算法，不冒称原论文复现。

### 在线扰动、安全检查点与恢复证据（2026-10-02）

- 在线生成扰动与每轮换扰动是不同配方；记录视图、强度、种子与样本/epoch绑定。当前seed+logical ordinal在重复读取时生成同一扰动，缓存只存clean数据；不误报为每次重新随机，不在冻结后静默加入epoch变化。显式局部generator独立于模型global RNG，不能先消耗global随机数再用局部结果覆盖；保存原子数/order、原target及真正元素改变mask。
- weights_only检查点metadata使用真正builtin标量和声明的CPU tensors；torch.__version__转plain str。JSON可序列化不等于torch.save后weights_only可读。实际safe-save/readback在真实环境验收，不因TorchVersion对象改unsafe加载或放宽safe globals。
- 分别报告恢复后的输入、已消费游标、配置、CPU/CUDA RNG、控制器离散状态、模型/AdamW数值容差和字节一致性。控制器selfseal分别重算有效，再与浮点内容区分；不同内容产生不同seal不能被误作额外离散漂移。容差预先声明并保留两端实际payload与独立比较；数值通过不升级原bitexact失败，无证据不定因为CUDA非确定性或恢复bug，不为补日志重跑容量阶梯。
- 所有启动器使用共同目录及完整UUID.lock；条件/seed单活动segment、单GPU一个本项目任务，不以整项目锁把不同GPU串行。协作锁不能阻止他人占GPU。根调度器另管全矩阵并发、累计GPU时及跨segment条件存储，单segment上限不冒充累计上限。保留共用曝光端点的primary FINAL，best仅诊断，不因其较小而删除唯一FINAL。

### 当前 Phase 1 的三轮正式训练要求（2026-10-02）

用户最新明确要求启动正式训练，并确认“所有样本训练3batch”指完整训练集训练3遍（3 epochs）。此要求替代先前新完整数据一次曝光的候选方案；当前已核实训练集15,709,889结构，每trained condition共同总base曝光47,129,667、三视图共141,389,001。验证集与最终测试数据不计入训练；NONE保持fresh paired initialization和0 optimizer updates。科学任务、划分、原单位标签、模型和在线扰动配方不因增加epoch而暗改。

正式入口、learning-rate cosine和策略时钟必须按3N统一配置；跨轮切换关闭并join已结束worker，再推进真实sampler epoch，保持条件间seed/epoch数据顺序配对。恢复分别核对累计base/batch计数与当前epoch局部游标，不将prefetched样本当已消费；明确保存各已完成轮次的实际batch会计。primary FINAL采用共同三轮端点，diagnostic BEST不代替；任何提前停止或超预算须记录实际曝光，不能称三轮完成。

用新不可变源码/协议绑定此次改动并做必要的跨轮恢复验证；原单轮试跑、FAILED和关闭W&B证据保留。模型/数据fit/init字节未改且已有完整有效证据时，做来源兼容检查并复用，不为更新source hash重做全库QA或训练。共享GPU风险授权与16CPU/64GiB、Slurm、W&B、单完整UUID一本项目任务、quota及自有进程边界继续生效；8h为段时长上限，具体安全分段及累计计算/存储预算由新协议按真实profile确定。

### 进程退出检查与失败段恢复（2026-10-02）

- `/proc` 的组成员快照、状态与 cgroup 可能在进程退出时变化。围绕 cgroup 读取两次核对 PID、UID、PGID、SID 和 start_ticks；确认消失或真实 zombie 的进程不作为活动资源或信号目标。活跃进程跨 cgroup、身份改变、仍存在但无法读取的 PID 继续拒绝。不能仅凭一次退出附近的 cgroup 异常声称有外来任务；保留最先失败的真实身份诊断，避免 finally 重查覆盖首个原因。Stage60 V10 的18个不同标准库检查已实际通过；原 P4512053 与 SDP4512052 的具体异常 PID/cgroup 未记录，根因仍未证实。
- 当前 compute20 的 chemprop Python 实测缺少 os.pidfd_open。逐 PID 发信号前重新核对上述身份及本作业 cgroup，采用有界 TERM/KILL 收尾；不得猜 syscall 编号，也不得声称最后一次检查与 os.kill 之间已获得原子 PID 复用保护。信号只能针对本次作业核验过的活动进程，不用未核验的组信号或宽泛杀进程。
- Linux 退出进程可能仍显示 R，却已带 PF_EXITING 并在传统 freezer cgroup 中显示根目录。读取同一 `/proc/<pid>/stat` 帧的 field9 flags，同时核对完整身份；只在双读确认退出标志时排除该退出进程，0→退出标志的转变需再进行一次有界身份/标志确认。RSS=0 本身不授权排除；活跃跨 cgroup、PID 复用、标志回落和存在但不可读仍拒绝。现场探针4512056的两个自建子进程均自然退出并回收，实际匹配内核header确认PF_EXITING=4并捕获双读R/退出标志/根cgroup；V13新10项检查通过。此证据不补造旧54未记录的flags，旧失败保持。
- CUDA OOM 分开记录实际所需分配、活跃 tensor、reserved 未使用、设备余量与其它进程。大额未使用 reserved 提示碎片参与，但不证明唯一根因；当前attention的8M padded上限可产生约11.44GiB单个FP32中间张量，旧常见batch通过不覆盖所有尺寸。可在既有授权内验证并显式记录原生allocator的expandable_segments运行设置，先做有界、仅分配小空buffer的兼容检查；它只证明兼容，不证明真实失败批次或完整训练通过。allocator设置不改模型、有效批次、精度、样本顺序或曝光端点；若需改变这些科学参数，重新统一冻结对照协议。55真实CLI OOM、5155提交状态及354更新尾部留档；恢复不得伪称已越过失败批次。
- 资源监督器触发显存上限并TERM自有child，与CLI真实CUDA OOM分别报告；核对停止前owned/free/foreign/RSS及原始cap，不为了恢复而上调安全上限或反复运行原失败批次。padded-pair数量上限不等于实际显存上限，检查单层高维中间张量及反传即时峰，已有整层activation checkpoint也不保证这些峰消失。若分块或其它实现修复改变实际源码，保存新不可变源码/协议及真实数值、梯度、RNG和恢复验证；不得谎称原source hash仍匹配、静默monkeypatch或改写原checkpoint的seal。原保存状态与未提交尾部独立留档。
- 正式段 FAILED 后协调器停止自动重试并保存原始状态；不删除 status 绕过保护，不把原失败改成成功或零更新。若存在原子保存并通过 weights_only CPU 读取、完整类型摘要和真实持久历史前缀验证的检查点，可在已有任务授权范围内，由 Root 明确绑定原 FAILED accounting、wrapper、源码/协议、配置、游标、跟踪 lineage 和物理 checkpoint，审阅后一次从该提交状态恢复。成功段仍按原闭合规则续训，未审阅失败不自动恢复。
- SDK log 返回并写入 fsync journal 不证明每条记录已进入 W&B 文件。区分已确认、实际持久、已保存 checkpoint 与丢失尾部；失败日志和未同步 offline run 全部保留。恢复后的规范曝光量从保存游标累计，弃置尾部与原失败计算时间另行记账；不能宣称无损恢复、把未持久记录的数值补造出来，或把失败段已产生的额外计算从累计预算中漏掉。
- 实际 quota 行的 soft 或 hard 为0时，该字段表示未设置该类限额，不能与正值直接取min当作零可用额度。严格解析used/soft/hard后仅对正的有限限额取min，两个限额均为0则额度未知并拒绝大规模输出；保留原始输出、真实退出码及计算单位。Stage60 P恢复提交v1因此在sbatch前停止，未产生新任务；v2按现有真实publisher相同规则修正，随后实际提交4512054。
- 真实 `squeue` 空结果可以是0字节文件，其SHA为标准空内容摘要；它不等于缺失或未关闭证据。仅对明确命名的队列引用允许空内容，同时核对UID、物理inode、路径、长度、摘要和原查询退出0；首次读取及模型启动前复核采用相同规则。源码、配置、检查点和其它必需输入仍要求非空。59接续在该旧校验处、真实CLI调用之前FAILED0s，Root已复现实际空引用错误并核验原恢复标记未消费；V15两项新检查通过后按原55提交状态恢复，不将59失败当新训练结果，也不修改运行中的P58父进程文件。

2026-10-03 的独立实时观察已核验 P4512058/SDP4512063 使用不同 GPU UUID，每项16CPU/64GiB；SDP 真实持久 W&B 中第5510次更新的 source-type payload 与 ACK 摘要精确匹配，随后已到6027更新，越过旧55的失败批次。该点时证据不证明全部未来批次容量或三轮已完成。V6协调器已迁移九条真实作业记录并持续轮询；原59零更新启动失败及全部历史FAILED/弃置尾部计算成本仍保留。证据见 `docs/phase1/evidence/stage60_actual_live_training_progress_v1/summary.json`。

## 所有正式模型训练的监控

- 每一次正式模型训练，包括预训练、微调、消融和下游模型训练，都必须使用 W&B 或既有的同等训练管理工具。普通 stdout 日志不能代替实验管理；不得以 `disabled`、空实现或静默跳过记录应付要求。
- 默认沿用项目已选的管理工具、账号与实验组织方式。正式训练前验证 run 初始化和指标写入；缺少认证或可用记录工具时先完成接入，不启动无跟踪的长程训练。
- 至少记录：唯一 run ID、Slurm job ID、配置与随机种子、源码版本或源码 hash、数据/划分标识、环境及 GPU 资源、step/epoch、训练与验证指标、各主要 loss、学习率、吞吐/耗时、内存/显存，以及 best/final checkpoint 的路径和最终结果。
- 需要诊断的问题记录梯度范数、异常值、错误堆栈和终止原因；指标按稳定 step 写入并定期刷新。DDP 明确 rank 0 等日志责任，避免重复实验与重复大文件上传；恢复训练关联原 run 和 checkpoint，保留恢复记录。
- W&B 显式指定 `step` 时默认 `commit=False`；在该逻辑记录应提交时明确设置 `commit=True`，或完成预先声明的累积后再提交。核对实际持久记录中的 step 与科学更新/曝光量，不能只看 run ID 或 SDK 内存游标。2026-10-01 已用两个 fresh offline 合成 run 验证；这不证明真实后端续接或在线同步，恢复仍须独立核验 lineage 和记录游标。
- 在线服务不可达时，使用持久化的 W&B offline run 或可实际查看的本地管理工具，并明确离线状态及同步方法。不能把未同步记录当成已在线可见；离线文件同步或可靠归档前不得删除。
- 默认记录指标与模型文件引用，不上传整份数据集，也不对每个 checkpoint 重复上传。保持管理工具在运行时可检查，训练结束后核验最终指标、run 状态和 Slurm 退出状态一致。

### W&B 统一归档与阅读入口（2026-10-07）

用户明确要求以后每次训练结束，把 W&B 集中到固定目录并标明名字。当前 Phase1 的实体归档目录为 `/share/home/zixiao/descriptor_analysis/runs/phase1_full_corpus/wandb_archive`；项目根的普通文件 `W&B_训练记录.html` 是统一阅读入口。按模型/seed分目录，以SDK日期、作业ID、真实结束状态及run ID命名；同时保留原始SDK文件、完整指标CSV、可读指标/曲线HTML及来源SHA清单。具体脚本、服务检查和收尾方法见 [references/wandb_archive.md](references/wandb_archive.md)。

- 作业结束后核对本账户队列、Slurm终态及receipt，确认源清单前后一致再发布归档；正在写入的run原地保留，只在索引中标为待归档。FAILED也归档故障历史，正常partial和三轮FINAL严格分开，不能仅凭Slurm COMPLETED命名FINAL。
- 已冻结的receipt、checkpoint恢复及W&B核验引用原物理路径，当前以经过SHA核对的归档副本集中呈现，保留原件；不用移动原件、任意符号链接或硬链接破坏既有校验。已核W&B日志链接仅物化为普通归档文件，目标须仍在该自有phase内。归档、临时副本和CSV/HTML峰值均计入用户quota及全phase预算，不复制checkpoint或整份cache。
- 每次正式提交前，核验归档metadata服务的PID、UID、start_ticks、脚本SHA及剩余寿命覆盖该作业墙钟上限和收尾；不足时按参考方法更新服务，或在登录节点协调器确认终态后调用归档脚本。当前有界服务每60秒检查、最多24小时，不能将其写成永久服务。归档故障单独标ARCHIVE_PENDING并保留原科学终态；训练结束不等于归档或在线同步成功。
- 归档页面标明刷新时间、服务到期时间及offline状态。可靠归档不自动等于在线W&B可见，也不授权删除原未同步run；后续报告直接给统一阅读入口和有名字的目录。

## 存储预算与清理
- 当前 sonmi 集群的 compute-0-20 内 `quota -v -u zixiao` 实际失败；不得把它当作零使用量或改用整盘 `df`。使用登录节点轻量发布的真实用户 quota，经 UID、发布脚本 pin、原始输出 SHA、额度行一致性及新鲜度核验后计入训练监督；发布器过期或数据无效时保留可恢复状态并停止，不拿陈旧额度继续。当前发布器有 24 小时时限、30 秒刷新、90 秒最大可接受年龄；实现与实测见 references/commands.md。
- 训练临时目录与持久结果分开计量。真实 W&B0.28.1 在自有 TMP 创建 Unix socket；仅 exact `/tmp/p1fc_<实际jobID>` 私有根内、相同 UID/设备的目录、单链接普通文件及 Unix socket 可按 lstat 大小计入，socket 不打开、不跟随。持久 segment/W&B/cache 的原规则不因此放宽；symlink、FIFO、设备、外部 hardlink 或未知 UID 仍拒绝。仅正常删除产生的 FileNotFound 可有限次完整重计，其余失败立即记录实际路径/类型并停止。原失败记录保留，未观察到原对象时不得把后来的复现写成原根因已证实。
- 当前W&B0.28.1会在`WANDB_CACHE_DIR`指定的缓存根下追加`wandb/logs`；按实际SDK与链接目标核对缓存根，已核本项目布局使用`phase/cache`，不要重复写成`phase/cache/wandb`并得到双重wandb目录。启动失败先修自己的环境路径，保留partial与原FAILED，不放宽任意链接或删除unsynced run；具体4512040实际失败及NONE成功对照见commands。
- 仅已枚举的自有W&B布局允许初始化时链接目标暂未创建：先验证链接文本归一化后仍在自有输出根内、精确目标形式及每个已存在祖先的UID/普通目录/O_NOFOLLOW；计入link文本和实际存在inode，后续监控再计入新文件。不用resolve(strict=True)把正常初始化悬空链接当作训练失败，也不任意允许外链或链链。
- 原子保存检查点时pending文件可能在枚举和stat之间被rename；对这种ENOENT最多三次完整重计量，其它权限/类型/所有权错误仍拒绝。finally应保存真实失败原因，避免重复同一统计异常吞掉parent summary。已由CPU4512036验证12个文件系统方法与真实W&B初始化85次计量；示例和边界见commands。

- W&B 在自有 run 目录内生成 `latest-run`、debug 日志链接属正常布局。存储监督器应只读核对实际链接位置、目标范围与 UID，允许已验证且目标仍在该自有输出范围内的布局；不沿目录链接递归，regular inode 只计一次，并计入目录和链接本身大小。外部目标、链接链或未知布局先保留证据并拒绝该路径，不能通过删除未同步 W&B 来修复统计。具体已验证布局及五项文件系统检查见命令参考 Stage57。
- 测试、正式训练与批量结果导出前，检查用户实际 quota、目标文件系统容量与 inode、已有结果大小，并估算峰值输出。`df` 的整盘剩余空间不等于账户可用额度；额度未知时不得按整盘空闲容量安排大规模输出。
- 每个 run 使用独立目录，区分可丢弃测试输出、正式结果、checkpoint、缓存与管理工具数据。限制保存频率与保留数量，避免重复数据集、重复 embedding、重复 checkpoint 和无界调试日志。
- 声明输出上限时计入整个 run 的实际峰值：正常产物、原子写入时并存的新旧文件、pending/incomplete 和失败记录。异常处理也遵守同一空间上限；空间不足时保留必要故障证据、如实非零退出，不用更大的默认日志上限绕过预算。
- 测试结束及后续工作开始时及时清理已确认过时的本账户测试结果。正式结果保留 best checkpoint、必要的 latest/resume checkpoint、最终指标、配置、源码/数据标识与关键日志；只有经核验重复、可重建且无继续使用需求的中间文件才能清理。
- 清理前列出目标绝对路径及大小，核实所有权、活动作业/恢复依赖、备份或重复证据。删除必须局限于已核实的具体输出路径，不沿符号链接扩展范围；Windows 侧按解析后的路径核对范围并使用 `Remove-Item -LiteralPath`，不跨 shell 拼接删除命令。
- 可在既有授权范围内清理本次任务的已结束临时产物和已证明冗余的自有输出；保留简短清理记录。对归属、保留价值或冗余性不确定的历史结果，先报告并澄清，不能按文件年龄直接删除。
- 不删除原始数据、唯一正式成果、活动 checkpoint、未同步 offline run、重要故障证据或他人的文件。存储不足时降低输出、清理已核实冗余或调整资源计划，不继续无界写盘；移动到同一 quota 内的“垃圾箱”不算释放配额。

当前Stage60的四份旧SoM来源账本只含path/rows/SHA；与新接口衔接时仅允许为这四份账本核对原路径与原SHA后观测bytes，并继续严格核对原行数，保存原描述与投影的独立sidecar。通用物理引用验证器与原来源账本不改。全phase存储须显式枚举互不重叠的正式训练、冻结产物、下游准备/拟合/统计和失败证据根；历史安装环境属于quota中的已有输入，不能把不适合该目录层级的W&B计量失败当科学任务失败。成功分段按实际accounting、wrapper、rendezvous、保存点与原epoch检查接续；失败段和未通过的实现候选仍保留各自原状态。2026-10-03已实际核验SDP63成功保存9258updates后普通续接69，第一新更新9259真实持久payload精确；native-store68元数据修复后70实际FAILED1:0/374s，并有110,048,762字节partial records，不能称未接触目标。旧SoM几何名称与新接口basis不同时，只接受READY+ORIGINAL_SOURCE_3D、READY+SAVED_GENERATED_CANDIDATE、NOT_READY+SAVED_GENERATED_CANDIDATE三种严格映射，全部坐标、状态、来源和encoder tensor hashes仍须原样核对；实际新1项CPU oracle和全部2,112成员核验通过。完整15,709,889 TRAIN整数索引核验完成，maxN712、原子总数821,431,906、intrinsic超预算singleton0；原sampler仍保留最大分子及末尾partial，整数观察不升级GPU容量。新chunk候选source已有真实独立git commit，正式01b8/f344未改；Slurm4512071仅为16CPU64GiB/20分钟/8次合成更新显存与数值验证，结果待闭合。细节与当前状态见[命令参考](references/commands.md)，该点时记录不声称三轮或下游矩阵完成。
2026-10-07重新核验：SDP4512069已PARTIAL_SEGMENT_EXIT_ZERO，保存13,393updates/5,446,337base/16,339,011views、epoch0，尚无完整epoch或三轮FINAL；最近验证在12,897updates/5,244,097base，用固定16,000 VALID。不能把Slurm分段COMPLETED写成模型三轮训练完成，也不能将较早validation冒充最后496updates后的实测。报告每目标原单位MAE/RMSE或accuracy/macro-F1，比较匹配基线并明确有效评价人口；综合固定标准化指标不保证Kappa等每任务充分。当前entropy配置0.05在no_grad中计算，只改变loss值，不提供logits正则梯度，修正时须统一新协议并保留既有结果。GPU候选4512071已真实8次合成更新/32s完成资源测试，但旧新数值oracle仍未通过；native store4512072原FAILED189s/AttributeError及partial records保留，后续修复尚未正式执行。当前实测队列为空；W&B offline保存、未同步，完整矩阵和下游未完成。报告原始证据见docs/phase1/evidence/stage60_training_report_20261007_v1/actual_status_and_metrics.json。

## 持续维护

- 主维护文件：Windows 用户技能目录 `C:/Users/mint/.codex/skills/huagong_hpc_requirement/SKILL.md`。项目副本：`/share/home/zixiao/descriptor_analysis/docs/skills/huagong_hpc_requirement/SKILL.md`，通过 `X:\docs\skills\huagong_hpc_requirement\SKILL.md` 访问。
- 标准用户发现入口 `C:/Users/mint/.agents/skills/huagong_hpc_requirement` 是指向上述本机技能目录的 junction；修改同一份文件即可，维护时保持入口指向正确。
- 在实际使用中遇到用户纠正、连接/调度变化、资源冲突、训练跟踪遗漏或清理失误时，当次工作中修正规则及必要命令；验证后同步两份技能、参考文件和项目 `AGENTS.md` 的相关条款。不要只在聊天中记住修正。
- 更新 `metadata.version` 与 `metadata.updated`，日期按用户的 Asia/Shanghai 日期；在相关规则附近简记必要的原因或核验依据，不保留已经误导执行的旧建议。
- 用户要求与已核验站点事实分别记录。瞬时节点占用、可用空间及当前队列只作现场信息，不写成永久结论；不能把一次临时处理推广成绕过调度、关闭跟踪或删除未知结果的许可。
- 维护在相关工作中由新证据触发，不自动创建定时任务，也不为“验证技能”启动训练、取消作业或清理历史成果。

2026-10-07 最新续接：SDP4512132 已在 compute-0-20、16CPU/64GiB/单自有GPU运行；真实W&B早期payload与源类型journal精确匹配，第一新optimizer更新13,394，从此前13,393/5,446,337base保存状态恢复。此前队列为空的报告保留为旧点时证据；本条不声称该新段或三轮结束，P仍未恢复。

### Stage61 审计适用当前并发规则

2026-10-09 用户的新规则取代旧 Stage61 四 allocation 上限及单核扫描建议：每个 CPU/GPU 计算作业至少 16 个 CPU 核，落实有效并行，资源允许时提高并发。主 agent 负责进度与代码审阅，已授权的子 agent 可并行查验；唯一提交协调者防止重复提交。CPU/GPU 节点分工、实际资源/预算与只读边界继续遵守；C4 PM7 和 G7 推理沿用本次会话已有授权，不重复索取确认，也不将授权扩大到其他实验。

## 2026-10-10 数据重整与标签生成：当前任务范围

本轮以项目根《Phase1 数据集重整与标签生成：工作内容分析.md》为执行依据，只处理数据，不做训练。测试阶段完成 WP0、WP1 分析与 WP4，不创建或写入任何 LMDB；原 LMDB 在所有阶段只读。WP4 完成后汇总试跑结果，由用户决定正式轮的覆盖范围等待决事项；正式轮计算结果回写之前另行确定新增字段格式。不要将旧预训练协议/训练预算/训练监控当成本轮数据计算的前置审批。

- WP4 按新文档可使用任意现场空闲计算节点，使用 Slurm、每作业至少16核并实际并行；提交前查询 sinfo、scontrol 和全部用户的声明内存。WP5 仅 compute-0-14 至 compute-0-19，执行方案待 WP4 后确定。
- 用户本次明确大批量计算的对话级状态探测可以延长到每1小时（3600秒）；批量查询关联作业与必要进度，终态/异常/用户消息及时处理。作业内保护和持久日志保持，避免反复重审已完成结果。
- 用户允许子 agent 并行分析，主 agent 负责方向和唯一提交协调。测试结束清理本轮已结束、无继续用途的临时文件，保留结果与必要故障证据，不删除原数据或不确定的历史产物。
- 用户quota实测硬限4294967296 KiB（4TiB），2026-10-10初始已用2420196456 KiB；约2TB新产物预算仍须按实际剩余额度安排，不能以整盘df替代账户quota。

## 2026-10-10 WP5 前节点范围已明确放开

用户明确：“在进入WP5之前你可以任意使用空余节点”。本轮WP0、WP1、WP4及其预处理/测试可在任意现场有空余资源的计算节点通过Slurm运行；优先空闲CPU节点，保持每作业至少16核与有效并行、85%声明内存核验、唯一Root提交、原LMDB只读和测试不写LMDB。该授权替代此前WP0/WP1默认compute-0-20限制，不再就相同节点范围询问。WP5仍仅compute-0-14至0-19，且须先完成WP4后的方案决策。

## 2026-10-11 剩余筛查任务

用户新增根文件《Phase1 本轮筛查任务（Codex）.md》并明确要求完成剩余筛查。当前先执行所有列出的 A1–A4、B1–B6、C1–C5 共15个子项；标题“13项”不作为数据manifest计数。原LMDB只读，不建立lmdb_1；样本采用候选正式序列化统计字节，确实需要的临时库仅允许自有scratch并及时删除。

- 新文档授权B1失败ESP小样本重测及B3同100分子hess/ohess/MOPAC FORCE对照；ohess仅在独立测试scratch优化，原PM7坐标与LMDB保持不变。POLAR原生不对称确认后删除方案，不继续追查。
- 所有其他分析与小测试沿用用户已授权的任意空闲计算节点；C3必须compute-0-14至0-19，k24、每节点1–2h，实测总RSS/PSS、sacct MaxRSS和scratch I/O。依旧Slurm、每作业至少16核实际并行、唯一Root提交、全部用户声明内存85%核验。
- 复用已闭合几何与原生结果。新I01分析只比14位骨架及质子化末位，原严格规则保留对照；正式配置仍须在结果返回后由用户确定。没有test authority时如实报告，不编造train/val/test映射。
- 科学失败/字段缺失/参数不支持/计账MaxRSS缺失记录后继续，不能引入其他停审或确认点。只有要写原始数据或物理manifest计数不一致才停止；所有正式轮和字段格式讨论留在本轮报告之后。
