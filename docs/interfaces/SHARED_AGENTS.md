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

后续任务不使用 `--exclusive`，只申请任务实际需要的 CPU。开发集群 compute-0-20/21/22 使用可恢复的混合调度；本节覆盖较早“20–22一律直接SSH/不提交sbatch”的冲突条款。操作前读 [混合调度说明](MFM_p_recipe/docs/p_recipe/HYBRID_SCHEDULING.md)。

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
## 2026-11-13 P任务按9.3科学停止（当前状态）

新P任务D6(d)已发现323个TRAIN/下游重叠分子（16个完整InChIKey、307个仅既有WP5键）。按用户任务书9.3停止，等待用户决定TRAIN与受影响D4的处理。未启动新P训练，未完成评价队列已取消；不得依据此前新P自动推进授权擅自恢复或改数据。新明确用户答复可覆盖本状态。独立PR6、数据线及PubChem不受此停止影响。具体见MFM_p_recipe/docs/p_recipe/daily/2026-11-13.md与runs/p_recipe_20261113/D6_identity.json。
## 2026-11-13 新 P 任务授权（当前）

用户已明确要求完整执行根《模型线任务书 P：P 预训练配方研究（迁移前）.md》，这是终止旧模型任务后的新独立授权。工作树X:/MFM_p_recipe、分支p-recipe；仅P配方研究、任务书指定旧检查点评价/P0及最终P′对照。旧任务不重启；CPU瓶颈PR6由其他工作线独立负责，本线不取消或修改该线作业。以新任务书的科学规则、校验范围、日志文件和六条停止条件为准，禁止额外防御/诊断/试验臂。训练或排队每1800秒查询，阶段结论及时推送GitHub。真实磁盘字节/inode和跨窗口峰值保护继续。保留旧终止记录。数据线与PubChem不变。
## 2026-11-13 用户撤销模型线开发任务（当前最高优先级）

用户明确表示模型线开发任务已暂时不再有效，并要求结束那边任务。模型线旧任务书、开发日程和自动推进授权即日起停止执行；不得依据旧授权新提交、恢复、重试或继续推进模型线开发/训练/评价/诊断/性能任务。当前作业按本次指令取消，自动恢复停用；这是用户终止，不是科学任务验收完成。保留全部已有代码、日志、检查点、数据、结果和失败历史，不删除文件；数据线和PubChem扩充任务不在此次终止范围。只有用户重新明确布置/恢复后才继续。执行记录：runs/model_v31_20261105/MODEL_LINE_TERMINATION_20261113.json。
## 2026-11-06 用户要求：节点文件传输不得占满磁盘

适用于所有 Codex 窗口、子 agent、CPU/GPU 节点及下载、复制、rsync、缓存、解压和临时输出；执行任何节点大文件传输前必须遵守。

- 在实际目标节点解析目标路径及其文件系统，用 findmnt -T、df -B1 和 df -Pi 检查可用字节与 inode；/tmp、/var/tmp 可能与根分区及 SlurmdSpoolDir 共盘，不能当作独立大容量 scratch。共享盘 df 和账户 quota 不能替代节点本地磁盘检查。
- 估算新增物理占用的峰值，计入源文件、解压/数据库临时文件、旧新文件并存、partial 文件、失败残留及所有窗口已计划/正在进行的同盘写入。跨窗口在同一目标盘协调预留，不能各自拿同一份空闲空间重复预算。
- 根分区默认至少保留 max(10 GiB, 文件系统总容量的 10%) 给系统和 Slurm；站点更严格要求优先。其他文件系统须保留站点要求及覆盖并发增长的余量，既有账户 quota 余量规则继续执行。目标可用量不足覆盖峰值加余量，或无法查明容量时，不得开始复制；换经核实的专用 scratch/共享盘、减小缓存或分批处理。
- 长传输及缓存生成期间持续观察同盘余量，在触及预留空间前停止新增写入并保留可续传状态，不能等到 ENOSPC 才处理。新传输/缓存入口落实容量预检和运行期保护；仅打印 df 不算保护。未核实用途/所有权/依赖的文件不得自动删除，不改管理员目录或自行解除 drain。
- 已核实事故：compute-0-17 作业4526050于2026-11-05 16:33复制约29GB的d7.duckdb到/tmp，留下17,656,872,960字节部分文件并报ENOSPC，同刻节点因SlurmdSpoolDir is full进入drain。compute-0-20作业4526119取消后一个进程未退出并触发Kill task failed；这是不同故障，不误写为该节点磁盘满。

## 2026-11-05 Window two taskbook v2 (current)

The user explicitly requests completion of the root `数据线 v1 任务书 v2（窗口二）.md`. It supersedes conflicting historical data-line rules below. B1/B2 are first and parallel; B3/B4 proceed in background; B5 follows B1/B3/B4. Resume D6 and the missing first-two S-prime Pprime scope; do not recompute closed Pprime. PubChem is window three and out of scope. Producer-only single numeric/alignment/leakage checks; no new content hashes, receipts, per-job acceptance reports, independent QA, second rereads or throughput benchmarks. No artificial memory/wallclock/cost stopping gates. New logic gets unit tests; one full regression before a PR. Use TRAIN only and no downstream TEST results. Stop to ask only for deleting existing files, scientific changes, paid school server or formal pretraining. Do not delete anything under this task's authorization. Earlier v30 cleanup was already completed under historical user authorization; preserve its history and current v31 products. Keep the one daily summary to one page, push each completed task, append only to shared STATUS.md. Root coordinates submissions; parallel preparation of D3/D5 follows the existing agent assignment. Keep data out of Git and other windows' jobs untouched.
## PubChem current scientific quality and Alpha metadata continuation

For this expansion, preserve the taskbook strict new canonical-record mask fraction above1% stop-and-user-report condition. User removal of per-job Root approvals did not remove scientific quality. Exactly1% continues; source NA/component fractions/robust-z review are separate. Do not add Root approval receipts. Use complete external full-QA reference catalogs and original function-preserving native timing metadata. Alpha compute-local sacct is unusable; the tested native accounting prefix is ssh -n -o BatchMode=yes -o ConnectTimeout=5 218.192.171.238 sacct. Keep1885201 untouched and preserve immutable source/runtime history.
## 2026-11-04 PubChem concurrency follow-up

The user explicitly allows an appropriate increase in computation concurrency when needed. Recheck live free CPU allocations and actual RAM; prefer idle pure CPU nodes. When those are occupied, using idle CPU cores on a free Alpha host in partition all is within this CPU-only continuation, with no GPU request or GPU computation and no paid server. Root's current operational selection is compute-0-2/all 32 CPUs plus sonmi1/cpu 16 CPUs after the current filter, not a permanent user mandate for these counts/nodes. Use disjoint fingerprint search partitions and preserve identical full-reference exact math, source identity, R/N rules and max3 UFF/D recipe. Keep 1885201 running untouched; do not restart the active filter merely to raise its worker count. Update only unstarted downstream plans or deploy a new immutable source for continuation. Root remains the sole submission coordinator; real CPU/RSS/shared quota accounting and the one daily human summary remain.

## 2026-11-04 PubChem exact structure decontamination and direct execution

Current explicit user correction overrides all older composition/wildcard decontamination and per-job Root approval requirements for this expansion. Use only complete InChIKey and the original v1 wp5 key (first 14 InChIKey characters + ":" + final protonation character). Remove every elemental-composition exact/lower-bound and wildcard veto, including MoleculeNet case:18/PDBbind 1pts and case:00/ClinTox. Exclude all PDBbind from decontamination sources because it is outside the planned downstream evaluation. Any downstream record without a determined exact structure contributes no structural veto; exclude it from downstream evaluation and preserve a record-level exclusion list and original evidence.

Stop and archive further 1slg/1pts correspondence research. Rebuild source keys from original physical identity rows (filter PDBbind before insertion so shared keys from other datasets remain), then run one whole-pool filter, directly build R/N queues and the 2.5M first batch, followed by UFF (maximum 3 actual conformers, no filling/retry) and D labels. Keep the existing fixed 1M nearest-neighbor job running in the background; it must not block this expansion. There is no new per-job Root acceptance/receipt or approval schema: keep necessary producer checkpoints/manifests and actual resource/accounting facts, and write one daily summary. Preserve old reports as superseded history. Exact full reference NN math, v1 ranking rules, original UFF/D science and real shared quota/resource protection remain unchanged.

## 2026-11-03 PubChem扩充全任务续接（当前用户授权）

用户要求完成根《数据线工作流程：v1 定稿与数据扩充（Codex B）.md》第二部分2.1–2.9全部工作，并把代码、报告、清单和结果索引推送GitHub。第一批按原默认共250万分子、R/N各125万；固定队列累计1000万；只做UFF和D、不做QM或训练。用户随后覆盖2.6节：每分子最多3个UFF构象，固定种子和生成顺序，0.5Å去重；不足3个按实际数保留并标记，不补足、不重试；保留已有构象以便今后去重后追加第4个及以后。D20每分子一次、D3逐实际构象，P′本阶段不算。大数据按原要求留仓库外，Git保存清单与哈希。

本次扩充覆盖旧24/48小时人为任务上限、4小时诊断时限、连续两次失败STOP2和基于旧成本倍数的自动停审：可修复问题持续修复并从真实关闭检查点续接，不能因旧超时或次数门自行停止。集群真实MaxTime/调度限制如实查询；如有限，使用检查点正常收尾和续算，不假称已移除站点限制。原科学版本、筛选/去污染完整性、确定性UFF配方、质量标准和真实资源/配额保护不变；不扩大到付费服务器或其他任务。旧失败及UNKNOWN原样保留，不能借授权把未验收结果改成成功。

本次标准X重连错误85；已用本机127.0.0.1:22369的nativeSSH SFTP适配恢复Y，受信别名仍为descriptor-analysis-remote。Y和原服务器AGENTS.md的80738字节/SHA256 9d41b45666ad98397dd5721b9248d1737d5f55b3d831690b520127df9dae2114实核一致。按既有规则在局部PowerShell创建逻辑X指向Y并解析后编辑；不写OneDrive副本、不强拆旧挂载。适配器为C:/Users/mint/AppData/Local/Temp/pubchem_expansion_sftp_bridge_20261103.py，仅本机监听；其存活是瞬时事实，使用前重新核验。

## 2026-11-03 本轮D-3最新简化交付（用户六条，优先于下方旧门）

本轮固定已选的50,000 TRAIN＋5,000 ROUTINE VAL，按D-1 v3.0由一个Slurm导出作业完成LMDB。脚本末尾只校验一次：记录/分子/构象计数与清单一致，随机1,000条与parquet逐字段比较，并生成一份总清单SHA。取消旧Source3生产前套件、10,000条门、16-reader复核、F64全量二次读回和独立复核作业；已通过的旧检查保留历史，不重做。

吞吐只测一次、总计不超过5分钟。用rsync --checksum复制到GPU节点，一次完成，不追加复制后哈希复核。模型线加载器和逐预测头过拟合测试作为交付后的实际验收，只有在那里发现问题才回查数据。失败直接修复并重跑，不能再用本轮导出旧STOP2/4小时工具修复规则阻止续接；失败只在同一每日汇总记一行，不另写报告或加审批层。

D-3与D-5仍由已授权子agent并行准备，Root统一提交；D-5采用同样的一次1,000条（不足则全部）末尾校验，不重复吞吐。科学标签/掩码/过滤/角色、r73有序F64权威与单次F32、r674 LOSS_DISABLED保持。真实CPU/存储安全和100GB账户余量继续执行；不改变P′的独立科学规则或付费服务器授权。

## 2026-11-03 本轮MAD后直接交接、D-3/D-5并行

用户最新要求MAD算完后直接D3/D5，并调用子agent并行处理。本轮只做指南所需的首遍完整TRAIN统计，取消实现额外增加的第二遍全量统计；保留原Source6、统计定义/阈值、F64指纹和D3原Source3/一万条逐字段源读回/16-reader。真实新finalizer Source6及exit0后发布D4；元数据如实写单遍、full_second_statistics_pass_performed=false、independent_numeric_replay_equal=null，不伪造两份复算或C0。D3/D5各一子agent准备独立16CPU/24h/无mem父作业，Root统一提交；D5直接使用同一闭合D4几何，仅共享D3早期关闭配置，不等其整库/C0。r674 LOSS_DISABLED、无追加QM、100GB账户余量与56GiB D4上限保持。
## 2026-11-02 本轮D-4获准在主节点执行

用户明确要求D-4直接在主节点完成；本轮允许在Main的sonmi登录/主节点运行D-4，覆盖旧“登录节点不运行计算”的该项限制，不扩展到D-3/D-5、P′或付费服务器。本轮D-4由Root按实测空闲资源选择16并发，CPU亲和性0–15、BLAS/OpenMP各1线程、nice增加10，在20核主节点保留4核余量；该并发数是运行资源选择，用户未限定2核或8核。按真实PID和检查点复用已闭分组，保留科学规则和真实资源保护。

本地执行必须记录真实PID、UID、start_ticks、CPU亲和性和实际进程exit码；不得伪造SLURM_JOB_ID、Slurm分配或C0。原6项Source、原统计定义与本轮首遍完整TRAIN统计仍须通过；本轮真实本地exit0及完整统计验收可替代Slurm C0。读取 `runs/data_v1_20261025/control/current_work_state.json` 的D4_actual_headnode_current及其实际launch/proof/exit，先验证实际进程，勿按旧CPU等待状态重提。账户余量100GB临时政策、56GiB输出和其他授权边界保持。
## 2026-11-02 本轮D-4持续交付与临时账户余量

用户明确要求“保证D-4完成后再停止”。本轮D-4资源/工具修复与真实续接持续到暂定D-4交付，不再因旧60分钟窗口或例行失败计数自行转为停止；科学质量、真实资源保护、失败状态及可比试点2倍计算用量确认线保留。完成须有原6项Source、实际完整终态（本轮获准主节点真实exit0）、首遍完整TRAIN统计验收并发布归一化文件（最新单遍规则见上），不能以语法检查、已写字节或等待进程代替。

用户另明确把当前Main数据线账户预留空余临时由200 GB降至100 GB（100000000000字节，扣除全部未来预算后）；D-4单作业输出仍56 GiB。记录在 `runs/data_v1_20261025/repository/configs/data_v1/user_temporary_account_quota_floor_100GB_20261102_v1.json` 与 `runs/data_v1_20261025/control/current_account_quota_floor_policy.json`；保持真实quota读数与全部未来预算，不伪造可用空间。此条覆盖本轮旧200GB要求，其他任务/服务器不从中推断新授权。

P′的STOP2修复仍待单独批准；D-4授权不用于重开P′、修改科学规则或使用付费服务器。原始数据与完整检查点保留，可明确回收已关闭、未验收且能从完整检查点重建的派生部分文件，避免把多个失败部分文件累积进后续输出上限。
## 2026-10-29 模型线用户主线修订 v3（当前）

以用户最新明确授权 `runs/model_v3_20261026/MODEL_LINE_USER_AMENDMENT_V3_20261029.md` 为准，HPC skill 1.0.126已同步：C4以实际4524734 FP64 48/48判PASS，FP32仅非阻塞诊断；日志/W&B/SDK/记账/fixture/SHA不阻塞科学主线，W&B每日一次、记账每周一次；数值近零/解析恒零门可直接修订并写当日DAILY，诊断修复4小时或连续失败2次即停止、保守旧路径继续，不新开精度分支。当前先A采用/自动checkpoint、三卡同批C1-a全关checkpoint测量、首seed20阶段5配置。r674保留head但LOSS_DISABLED，不再追加处理。科学DECISION_RULES、TRAIN/noTEST及实际资源保护保持，付费服务器/正式预训练/科学规则变更/GPU用量超过估计3倍仍须用户确认。开发GPU也已获批自动内存，省略固定Slurm内存，软件预算/RSS/85%/UUID锁等原保护不变；下方相冲突门为历史。
## 2026-10-29 模型线CPU验证自动内存（当前用户授权）

用户已批准“模型线 CPU 也使用自动内存（建议）”及 runs/model_v3_20261026/MODEL_CPU_AUTO_MEMORY_PLAN_v1.md。模型CPU检查/回归继续按实际可用cpu节点2、8–19和至少16CPU提交，不声明Slurm固定内存或SBATCH内存环境覆盖，不使用exclusive；原CPU声明内存85%门由本条取代，RSS/实际MemAvailable/quota/private/output及全部科学门槛保留，默认0不代表获配16/32GiB。仅对核实仍PENDING未启动的自有checker按方案记录更新；已RUNNING或终态不变。完整回归采用独立自动内存资源版本，不能假用旧32GiB证明。GPU任务原资源/UUID/锁规则、学校预训练禁用、Root唯一提交及原Stage0–7全目标不变。HPC skill1.0.124两份同步；下方旧CPU内存条款为历史。

## 2026-10-25 模型 v3 独立开发（当前）

用户后续明确：CPU任务提交可用CPU节点，GPU节点只提交模型训练/微调等GPU任务。此条覆盖下段旧CPU默认compute-0-20限制；CPU回归、C2拟合、日志核验与准备按实测cpu分区compute-0-2、8–19统一Slurm调度，至少16CPU、全用户内存85%与实际可用内存/quota核验。不用20/21/22做纯CPU计算，不改他人或数据线作业。HPC skill最新1.0.119，旧地点仅为历史证据，不追写旧文件。

用户要求严格执行根《模型线工作流程：模型 v3、训练代码与训练配方（Codex A）.md》。主工作树 `X:\MFM_model_v3` / PROJECT/MFM_model_v3，分支model-v3；子agent用独立live X工作树和model-v3-sa*分支，Root唯一调度/整合。当前HPC skill1.0.119及该树docs/model_v3/EXECUTION.md优先。新指南授权开发服务器全部12GPU、单卡一个实验，实际Slurm/UUID/85%内存/公共GPU锁及不干预其他作业保持；不把CPU allocation声称为GPU隔离。仅正式训练前研发，不启动正式预训练、不用学校服务器、不访问下游最终结果、不改数据线负责目录或原LMDB、不覆盖历史证据/旧代码、不删除已有文件。直接SSH计算仍限有界compute-0-20，正式计算走实际Slurm分配。

模型固定6x512/H0维512；阶段0参数审计4520329及原2016测试4520330已实际C0，后续各阶段不能借用这些证据冒充验收。D-1至D-6未交付时先现有S/合成实现，不自造物理格式或真实标签。用户已明确允许SoM二分类满足开发面板分类覆盖。模型选择只用TRAIN内层；阶段6配方/B-star具体结果要用户确认后再冻结，阶段7后PR由用户合并。旧S修复及WP5已在2026-10-17闭合，不根据下面历史ACTIVE重启。

模型v3监督修正规则详HPC skill1.0.117：信号权限逐项绑定稳定内核进程生命周期，psutil墙钟created只作诊断；旧失败不改写。交互SSH内的嵌套SSH一律`ssh -n`，只凭实际sbatch回执登记任务。Git/SHA用机器值，不从PTY重绘输出手抄；PowerShell读中文UTF-8数据显式指定编码。CPU节点例外须有用户明确授权，未答复不视为授权。

## 2026-10-16 WP5 全人口闭合及最终验收续算（历史）

WP5严格catalog4515541实际CLOSED：1,220,466分子/11,231,854记录/134,782,248槽，missing0/issues0；fullverify498、pilot4的502、均匀200链499→500→501、六现场/共享清理/G0/最终交付仍须全部实际通过。最新交接 runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v9.md 优先于旧WP5点时状态；formal542与真实QA成本分列，原515 FAILED不伪装成功，不重做已闭合QM。仅数据生成验收，不训练、不写LMDB。

node14故障scratch经4515551全部52输出归档读回后已清空，22输入不存正文、1可重建cache；全部75file/48空目录清理及新forensic容器/receipt在final supplemental中交付，未知部分输出不升级科学状态。G0 shard0原5507 COMMIT锁失败，189837DONE保持；新同事务重试v3私有真锁测试通过，4515552在原STATE/node12继续，collector513依赖531/532/5552。不要用运行中inventory DB的全库GROUP BY监控造成共享读锁；只读取小日志/报告，关闭终态观察句柄后续算，DONE不重扫。其它S修复项目互不干预。Root唯一提交、既有节点12/13/14/17/18/19和85%资源规则、1h大批检查及原停止条件保持。

## 2026-10-16 S修复运行期v3（覆盖旧S修复活跃状态）

当前S修复源runs/s_denoise_repair_20261016/source_v3；99源码绑定configs/D3_source_binding_v4.json，核心85文件与前版相同，2016测试/逐位/真实worker/新GPU安全checkpoint已通过。仅优化subset本地块关闭生命周期，保持source-global噪声与全部Tensor输入不变；默认选项false，新配置true。旧Root160742退休、原型4515533/34实际CANCELLED并保留全部成本；新Root164635/control/d3_local_blocks_v1，A0新4515542/43。只有第3步五门槛全通过才直接全量B1双种子/B3双种子；当前仍D3，无全量结果。X原生阻塞/net use85时使用已经Sonmi新探针核实同一项目的Y，通过本地逻辑X→Y编辑器解析；不写OneDrive代替服务器，不强拆其它挂载。独立WP5不修改或取消。新root README与新控制状态优先。

## 2026-10-16 S去噪修复独立任务

用户已授权按新《S 去噪修复方案（Codex）》完成诊断、修复及门槛通过后的新B1两种子/B3两种子收敛测试。新root runs/s_denoise_repair_20261016；实际开发源source_v2/current/phychem_mfm，历史Stage59/旧S/source失败副本只读。GPU20/21/22、16CPU64GiB与85%全部用户声明内存；CPU8/9/10/11避开WP5。原LMDB只读、不建LMDB、不训练S′。2016全测试、v2逐位、真实spawn恢复已通过，D1/D2已完成；D3科学门槛尚未通过，查表重拟合与A0对照正在运行，不能称全量完成。五项门槛全通过可直接开始全量，失败按新指南停止；不复用旧0.141Å停止/raw-loss绝对相对差/epoch外推规则。源码冻结configs/D3_source_binding_v3.json，元数据Root身份control/d3_single_layer_v1/identity.json；不修改活跃源码或并行WP5。最新事实以新root README及实际状态为准。

## 2026-10-15 WP5 归档竞态恢复（优先于旧 WP5 点时记录）

WP5 phase15 的78作业已全部实际COMPLETED，所有六阶段463个正式作业已核终态；这不代表全人口完成。最新队列检查点为1,011,462分子／9,592,275记录（85.40%），剩余分子以实际R10恢复后队列为准，最终200条／2400任务验收仍未开始。

实际发现cleanup4515295提前finalize了仍活跃的cleanup4515292，删除其lane后24分子／214记录归档写失败并进入ATTENTION_REQUIRED。证据在 `reports/phase15_actual_foreign_finalizer_race_root_v1.json`；SCI worker完成数与永久前缀均61分子／581记录，不能凭错误receipt整JSON比较误报丢失科学结果。新runner14只将跨root repair移交Root终态保护工具，保留自身worker全部退出后的finalize及全部科学函数；实际16writer夹具、追加复现包4515309和G4 4515310均通过，contract7已冻结。普通正式cleanup不得触碰其它活动root，不能重开空lane掩盖已删文件。

R10只读99root完整核验4515312、24条同attempt恢复4515313、E8零待导出核验4515315、当前G3 4515314均已实际闭合，原STOP已归档解除。phase16已实际一次提交72主4515316–4515387＋6收尾4515388–4515393；当前runtime14/contract7，PROJECT cwd、24CPU32GiB48h及46+2不变。真实单Mol startup已核4515354/node18、10记录120任务全部SUCCESS，六trace字段及H2完整验证通过；不代表全人口验收。watch11 PID65713已启动，实际报告小时边界下一37、首次延迟3600秒，计账7阶段541唯一正式作业；actual541 map及receipt sidecar已生成。完成的本地镜像已清理16,390,533,120字节，永久清单与故障证据保留。先核同attempt完整SCI，确无完整SCI的本次精确24基础设施故障仅恢复PENDING并保留attempt、旧receipt/export/rank；不能用RETRY_PENDING额外增加科学尝试，也不把它们写成科学最终失败。恢复后按既有持续授权完成纯导出、当前容量与G0核验再续算，不重复索要相同权限；原六停止条件、原LMDB只读和最终200验收不变。copy只读源字节，SQL恢复仅本地镜像；完成后按实际依赖清理本轮临时副本，保留永久与故障证据。

## 2026-10-13 S′ 生成与 S 收敛检验（本轮独立任务）

用户明确要求严格执行 property_analysis/S′构象生成与S收敛测试指南_Codex.md。服务器账户和目录仍为 zixiao@202.38.247.57:22 的 descriptor_analysis；新独立输出根为 runs/sprime_s_convergence_20261013。A UFF 构象与 B S-only 收敛训练可与 WP5 并行，本轮明确授权 B1 两种子一轮、B3 一种子三轮，不套用旧 WP5 “不训练”限制。原 LMDB 与 WP5 清单只读、不创建新 LMDB。CPU 避开14–19并避开当前 WP5 使用的12/13，现场选择其他空闲 CPU 节点；GPU 限20/21/22。每项计算至少16核、有效并行、全部用户声明内存85%核验及唯一Root提交保持。

A 先按五文件组分层试跑10000Mol，外推核时严格小于5000且失败率严格小于1%才能自动全量；否则保留试跑并报告等待用户确认。N不足不可复制补齐，不替换UFF，原子顺序、SMILES指定立体及最低能PM7确定的未指定立体必须保留。B 固定三个S任务权重、禁动态balancer、TRAIN完整一遍才称epoch；NaN/发散、实际记录与清单不一致、超过0.1epoch去噪RMSE仍>=0.141Å按指南停止。停止条件不扩张到普通可修复软件故障。

本机标准 net use X 重连实际失败67；直接SSHFS在SFTP传输初始化时reset。已通过sonmi受信known_hosts与本地端口实测三种key摘要相等核验compute-0-8，且两端项目AGENTS.md物理inode/bytes/UID相等；恢复X为同一/share项目live view，经native SSH隧道到compute8及本机仅127.0.0.1的SFTP管道适配器，不改数据、不关闭主机验证。实际SSH别名继续用于Linux命令与Slurm提交。compute21旧SSH host key变更需独立核验；本轮自有Slurm4515020实际读出ED25519指纹SHA256:cB2kIJBHOR48KHedUYjICdLC+QzbSmR6A5kGyzE+jN0，属于受信调度路径的节点实测证据。现场GPU/内存/队列仅作点时信息，不写成永久容量。

## 最新执行状态：WP5 phase14 已有真实科学产出（2026-10-12；优先于下方历史点时条目）

用户最新要求持续到全部目标计算完成；可解决运行问题自主修复、恢复和续算，不重复询问相同权限。科学范围及原六条guide-stop不变，原LMDB/manifest只读，不创建LMDB或启动训练。只有全部11,231,854记录／1,220,466分子的12任务及最终200条／2400任务同环境验收真实闭合，才标记完成。

当前有效phase14仍使用冻结runner13/main13、contract6及同package：一次72主4514369–4514440＋6收尾4514441–4514446，资源24CPU/32GiB/48h，实际节点12/13/14/17/18/19。78实际WorkDir全为项目根 `/share/home/zixiao/descriptor_analysis`；所有后续helper调用cwd须明确为PROJECT，并读回实际WorkDir。回执 `runs/phase1_wp5_20261011/submission/recovery_attempt_v14/submitted_jobs.json` SHA4d2eed16ad56ebb8b1b933b6ec4748923d7819aa047f919f7a9004a69985e15b。

保存的首次实测startup-probe（epoch1791767801.0658562）已744claims、新完整192Mol／1895records，证明正常科学产出；不是全人口完成，不再重复该查询。证据 `runs/phase1_wp5_20261011/reports/continuation14_first_durable_science_actual_probe_v1.json`。watch7 PID3461479，identity在同root/reports/recovery_hourly_watch_v7_identity.json；observer6/watch7按5阶段385真实唯一作业计成本，人口仅一次。下一次批量检查1小时；内部checkpoint、截止保护、publisher和monitor频率保留，异常/用户输入及时处理。

旧R13全78 COMPLETED0但claims0／SCI0：77作业1848worker是cwd导致relative source_path初始化失败，1个task71范围空；它们不是成功科学计算，计账与旧partial handoff/原审计均保留。单wholeMol目录修复烟测4514366真实24worker/1Mol1record/12任务全SUCCESS、scratch清理通过。PENDING没有NodeList分配不是节点错误；按实际ReqNodeList/资源判断，点时23RUN55PD的修正v2审计PASS，不抹除v1误读历史。

6收尾后仍有可处理剩余时，按最新持续指示自主做最新全阶段真实终态、SCI恢复／纯导出、剩余存储/guide条件核验，再用同冻结科学代码与独立新phase回执续算，不复用已提交结果文件、不重置一次SCI retry、不再次申请相同权限。普通FAILED/锁错不扩展STOP；原六条件触发仍正常停止新Mol/checkpoint/退出，不scancel。Root唯一提交协调，旧冻结生产源码/plan/G0/package/数据/monitor和密钥不因文档同步修改。详细实际记录见 `runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v4.md`。

## 2026-10-12 WP5 修复版 R13 的实际交接

用户最新要求持续到全部计算完成，授权自主处理可解决的问题。R12 提交前发现收尾动态领取可能超出本地索引快照；独立 R13 将收尾领取限定于索引覆盖的任务集合，索引同时覆盖这些任务暂时 RUNNING 的分子。主任务领取、科学计算、解析、字段精度、重试次数、截止保护和600秒元数据等待沿原冻结逻辑。旧119份源文件及已有结果保留。

实际4514281的16个进程已通过跨任务关闭、同任务返待处理、空范围及后继收尾边界测试，零QM、零生产队列写入。runner13 SHA258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f；增量复现包4514282闭合，contract6 SHA dfbeb31ed87553a62f833d8aee22f7000dabffc973b4ed34366ce6edd1e65099；G4实际4514283以24个进程通过，manifest7。G4旧spec的同路径、同SHA/bytes重复引用可在独立适配器中原样保留，不能误当源码改变；报告的语义差异字段是binding_differences。

旧task2和最后收尾4142已正常完成。Root唯一提交协调器当前是wp5_first_submit_handoff_v3.py，PID3452926/UID1278/start_ticks8056177747；等待真实全229清单扫描4514280后继续apply、bootstrap13、实际剩余G3、G0和一次72＋6提交。批准记录878cc仍绑定原prepared12/contract5；修复版明确引用最新持续指示及真实metadata桥接证明，不伪造新的用户批准。当前原正常drain STOP的reason仍为USER_APPROVED_R12_SOFTWARE_RECOVERY_NORMAL_DRAIN；交接只归档该实际标记。所有计算与最终200条验收完成之前，单批作业终态不等于目标完成。新阶段监控消费实际R13第四份回执，首次累计307个科学作业；后续续算必须更新实际阶段全集和成本，不能漏记或重复计人口。


## 2026-10-12 R12 正常退出与新一次72＋6已获明确授权

用户实际回复“允许正常退出并一次性续算（建议）”（call_e92f4936799142f49105fe45329daf89），并明确要求现在提交新版并持续到全部计算完成，不因可解决问题随意停止。该具体授权已记录 submission/recovery_attempt_v12/user_approved_drain_and_one_phase_v1.json；Root已实际写STOP_NEW_MOLECULES进行正常drain，不scancel、不杀当前分子。不得重复询问这次新72＋6权限。旧229终态、全SCI修复/纯导出/production-bootstrap/G0须用真实输出闭合后提交同一批；当前压力/软件/参数测试已通过，不重测。后续在此次持续计算指示范围内自主处理可修复的运行与提交问题；原科学范围、六停止条件、200条最终验收及不写原LMDB保持。最新正在执行纯导出为4514279/V3，不将旧失败4514274当成功。
## 2026-10-12 WP5 R12 最新核验状态

R12真实生产大小元数据run6（4514266–72）PASS，5nodes/480writers/22parents/5765unique闭合，三场景各480报告无错误、全部正常退出。runner12冻结91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278，32原科学函数AST不变，metadata工程等待600s且继续min实际deadline；并未声称13节点R12写压力或新增QM冒烟。复现包4514275闭合，contract5/prepared12及G4实际4514278/24workers PASS。追加source使用绝对路径；既有混合路径核验在项目根执行，保留4514276/77路径错误历史。SCI子集4514265的178修复均已读回，7live/PD保护保持；19root纯导出4514274发生queue只读SELECT错误、0roots完成，修复中，不能当已闭合。新72+6阶段尚未获授权、未提交；原69+4许可已用，旧R11继续正常运行。正式软件恢复drain需具体用户授权后才写STOP，后续全229终态/reconcile/export/bootstrap/G0实际完成再提交。原科学配置、最终200及指南六停止条件继续适用。
## 2026-10-12 WP5 当前恢复点时状态

已授权69+4启动补交及两依赖调整确已实施，随后再次有共享queue锁错误。R12 candidate_v4只改元数据，AST32科学函数不变，隔离锁4514256 PASS，完整压力4514257–4514263尚在测；不将旧调度75项/warm144进程/五节点结果冒充生产或六节点科学通过。活动R11源保持；原SCI/provenance不改，不重复QM。下一正式阶段不在已用补交授权内，先准备具体测试/冻结/存储/恢复结果，再按指南3.5询问；未经明确例外不因锁错误暂停正式科学领取或scancel。当前watch_v4按原条件2/3/5/6判断，PID3439043/start8054882766；首5%仍由runner处理。当前读恢复审查只是queue锁中断，不得称SCI损坏或闭合。证据：runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v2.md。原完整流程和用户已批准的节点/归档规则继续适用。
## 2026-10-12 WP5 启动失败补交及依赖调整已获用户授权并完成

用户实际回复“允许本次补交与依赖调整（建议）”（call_1fyjGynKx3OVeadAmJPwxpcG）。仅补交此前量化开始前退出的69个主任务及4个收尾，并更新原4514142/4514143的own-node afterany；保留4514137/4514139/4514140的已有结果，不重新启动它们。Root已完成新主4514153–4514221、新收尾4514222–4514225及两个原收尾依赖调整；实际75项调度核验PASS（24CPU、32GiB、48h、原六节点和脚本），不改变冻结runner11/contract4/科学配置。新权威与实际回执在 runs/phase1_wp5_20261011/submission/startup_replacement_v1/，submitted_jobs.json SHA11e7fd66f653738e765b2308460ea33897899532189fc823d7ee075744ffdbe1（大小写等价）。旧4514140已完成且被控制器清除，afterany已满足，逻辑依赖仍保留在回执。六节点实际生产队列启动测试144进程均PASS；不冒称冷迁移原故障已无历史影响。累计成本保留原两阶段失败作业，人口只统计共享队列一次；当前授权不涵盖本次六收尾终态后再次追加正式波次，届时若仍有余项遵从指南3.5报告等待指示。最终200条及原停止条件保持。
## 2026-10-12 WP5 一次性续算已获用户明确授权

用户实际回复“允许按准备方案一次性提交续算（建议）”。仅本次新增的一阶段72主任务+6个own-node afterany收尾已获授权，不再次询问。权威记录在 runs/phase1_wp5_20261011/submission/recovery_attempt_v11/user_recovery_authority_20261012_v1.json，绑定原提交、冻结contract4、闭合reconciliation和prepared_plan_v11；新实际提交记录在同目录submitted_jobs.json。Root已一次性实际提交主4514069–4514140、收尾4514141–4514146，全部24CPU32GiB48h、六台已授权节点；原STOP按用户授权归档保留，原SCI/提交记录不覆盖。原六收尾终态后，3Mol30records已纯导出闭合，余1158499Mol/10618894records；G3剩余峰值只扣已计入quota的唯一永久输出，不重复收费。新旧两phase的coreh去重累计、SCI人口不相加；只读观察使用wp5_hourly_observe_v2.py。若本次六收尾后仍有余项，指南3.5仍要求报告等用户指示，不自动再开新phase。最终200条重算与其他原要求保持。
## 2026-10-11 新原始输出与复现性要求已获用户明确授权
用户六条原文及结构化权威：runs/phase1_wp5_20261011/configs/user_raw_retention_override_20261011_v1.json（USER_AUTHORIZED）；原文副本runs/phase1_wp5_20261011/reports/user_raw_retention_override_20261011_v1.md。取代原指南G3与第4步相关归档规定：所有输入不保存，成功非审计原始输出仅本地解析后删除；只归档全部失败计算及file_group×size_stratum按record分层随机约1%（选中record全部12任务完整输出）。不再强留最低构象。每record/task Parquet增加状态、软件ID、耗时、SCF次数、收敛标记、input SHA；冻结永久复现包。新增50记录同环境双算按字段精度比较，失败停报，不比较raw文本字节；G5必须验证registry_v2全部字段提取覆盖。重新按新策略G3含400GB训练格式预留/失败审计输出/临时峰值实测，200GB峰值余和300GB运行停止余量不变。最终200条原要求未取消。此前原策略3.19/3.59/5.80TB仅是旧策略估计，不继续作为新策略容量结论。原已运行的旧版本测试作为历史证据保留，不改正在运行源，不冒充新策略链路通过；正式新版本必须先完整验证和冻结。服务器/node整体替换授权仍有效；Root唯一Slurm提交。
## 2026-10-11 本次 WP5 节点替换已获用户明确批准
仅本次 WP5：测试和整轮正式计算采用 compute-0-12/13/14/17/18/19，15→12、16→13，槽位4/4/4/8/4/5。优先于下文该轮原14–19限制，不扩展到别的工作。权威用户批准：runs/phase1_wp5_20261011/gates/wp5_node_replacement_user_approved.json；实际72-task plan：packing/node_assignment_v3/tasks.json。G3空间要求没有豁免，新scope G4/G6与最终200条仍必须闭合。Root唯一提交Slurm；不得改用学校252账户。
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
## 2026-10-11 剩余筛查任务

用户新增根文件《Phase1 本轮筛查任务（Codex）.md》并明确要求完成剩余筛查。当前先执行所有列出的 A1–A4、B1–B6、C1–C5 共15个子项；标题“13项”不作为数据manifest计数。原LMDB只读，不建立lmdb_1；样本采用候选正式序列化统计字节，确实需要的临时库仅允许自有scratch并及时删除。

- 新文档授权B1失败ESP小样本重测及B3同100分子hess/ohess/MOPAC FORCE对照；ohess仅在独立测试scratch优化，原PM7坐标与LMDB保持不变。POLAR原生不对称确认后删除方案，不继续追查。
- 所有其他分析与小测试沿用用户已授权的任意空闲计算节点；C3必须compute-0-14至0-19，k24、每节点1–2h，实测总RSS/PSS、sacct MaxRSS和scratch I/O。依旧Slurm、每作业至少16核实际并行、唯一Root提交、全部用户声明内存85%核验。
- 复用已闭合几何与原生结果。新I01分析只比14位骨架及质子化末位，原严格规则保留对照；正式配置仍须在结果返回后由用户确定。没有test authority时如实报告，不编造train/val/test映射。
- 科学失败/字段缺失/参数不支持/计账MaxRSS缺失记录后继续，不能引入其他停审或确认点。只有要写原始数据或物理manifest计数不一致才停止；所有正式轮和字段格式讨论留在本轮报告之后。

## 2026-10-10 WP5 前节点范围已明确放开

用户明确：“在进入WP5之前你可以任意使用空余节点”。本轮WP0、WP1、WP4及其预处理/测试可在任意现场有空余资源的计算节点通过Slurm运行；优先空闲CPU节点，保持每作业至少16核与有效并行、85%声明内存核验、唯一Root提交、原LMDB只读和测试不写LMDB。该授权替代此前WP0/WP1默认compute-0-20限制，不再就相同节点范围询问。WP5仍仅compute-0-14至0-19，且须先完成WP4后的方案决策。

## 2026-10-10 数据重整与标签生成：当前任务范围

本轮以项目根《Phase1 数据集重整与标签生成：工作内容分析.md》为执行依据，只处理数据，不做训练。测试阶段完成 WP0、WP1 分析与 WP4，不创建或写入任何 LMDB；原 LMDB 在所有阶段只读。WP4 完成后汇总试跑结果，由用户决定正式轮的覆盖范围等待决事项；正式轮计算结果回写之前另行确定新增字段格式。不要将旧预训练协议/训练预算/训练监控当成本轮数据计算的前置审批。

- WP4 按新文档可使用任意现场空闲计算节点，使用 Slurm、每作业至少16核并实际并行；提交前查询 sinfo、scontrol 和全部用户的声明内存。WP5 仅 compute-0-14 至 compute-0-19，执行方案待 WP4 后确定。
- 用户本次明确大批量计算的对话级状态探测可以延长到每1小时（3600秒）；批量查询关联作业与必要进度，终态/异常/用户消息及时处理。作业内保护和持久日志保持，避免反复重审已完成结果。
- 用户允许子 agent 并行分析，主 agent 负责方向和唯一提交协调。测试结束清理本轮已结束、无继续用途的临时文件，保留结果与必要故障证据，不删除原数据或不确定的历史产物。
- 用户quota实测硬限4294967296 KiB（4TiB），2026-10-10初始已用2420196456 KiB；约2TB新产物预算仍须按实际剩余额度安排，不能以整盘df替代账户quota。

## 当前节点声明内存核验（2026-10-09，HPC skill v1.0.45）

节点AllocMem=0不代表已有任务没有内存承诺。提交前汇总目标节点全部用户作业的总声明内存及实际节点归属，按队列合计和AllocMem较大值加新作业核对RealMemory的85%上限。详见docs/skills/huagong_hpc_requirement/references/commands.md的“AllocMem 为零时的声明内存”。每任务至少16核、有效并行、600秒长任务探测及只读审计规则继续适用。
## 当前用户规则：资源并行与长任务探测（2026-10-09，HPC skill v1.0.44）

以下规则优先于本文较早的 max2/max4、最少核数或高频交互轮询记录：

- CPU 测试、扫描、预处理及 GPU 任务，每项计算作业至少分配 16 个 Slurm CPU 核，并通过适当 worker、线程或合法独立输入分片实际利用并行；不能只加资源请求仍单线程运行。GPU 数量按实际任务与设备核定，CPU/GPU 节点各司其职。
- 现场 CPU、内存、GPU、I/O、存储和预算允许时尽可能提高任务并发，不再使用旧 2/4 作业固定上限；仍由唯一协调者去重提交，遵守设备归属、每任务资源边界与原科学授权。使用 sinfo --Node 和 scontrol 核对节点，不把瞬时IDLE写成永久保证。
- 预计或实际运行至少半小时的 CPU/GPU 任务，对话级状态探测每 10 分钟一次（600 秒），批量查询相关作业；不每分钟返回模型或反复生成无变化的报告、重审闭合结果。用户查询、终态通知和实际异常及时处理；作业内资源保护、持久日志与自动告警保持。
- 用户暂停任务后停止自动审计、后续提交和轮询；已运行 Slurm 作业的暂停状态须单独核实，不能由目标 paused 推断作业已停。

> W&B归档更新（2026-10-07，HPC skill v1.0.37）：统一阅读入口为项目根普通文件 W&B_训练记录.html；实体目录 runs/phase1_full_corpus/wandb_archive，按模型/seed、SDK日期、jobID、真实PARTIAL/FAILED/FINAL及runID命名。实际已归档9个结束run、1个运行run待归档，45个原始文件与副本SHA再次核对相同，全部HTML链接可达，归档约140,614,924字节；原路径和冻结receipt/checkpoint/source未改。v2真实归档退出0/errors0，已部署最多24h、60秒周期的metadata监视服务，PID1425298身份与argv/start_ticks已核对；每次正式提交前须按技能检查服务剩余寿命覆盖段时限与收尾，或在登录节点确认终态后执行 scripts/archive_phase1_wandb_v2.py。记录仍offline，归档不等于W&B在线同步。首次v1摘要误录失败留档，当前以v2及 docs/phase1/evidence/stage60_wandb_archive_v1/actual_verification.json 为准；具体规范见 docs/skills/huagong_hpc_requirement/references/wandb_archive.md。

> 最新实际状态（Stage60，2026-10-07；下方均保留历史点时证据）：SDP已普通续交4512132，在compute-0-20以16CPU/64GiB/单自有GPU运行；从13,393updates/5,446,337base保存点恢复，真实W&B早期payload与源类型journal精确匹配，第一新更新13,394。科学source01b8/protocolf344未改，尚无三轮FINAL。P仍待显存保护容量修复；当时foreign=0，不能归因他人抢卡。每段2h、预留900s收尾，SDP正常partial后提交窗口未及时恢复造成空档，已续接健康条件。新段前累计P9276s、SDP21391s；估计完整三轮P约31h、SDP约50h，剩余P28–29h/SDP约44h，排队、修复及完整验证另计，P修复后需重估。W&B offline未同步，原failed及PT均保留；HPC skill v1.0.36两份已同步。新实际续交/首更新证据为stage60_successful_SDP69_ordinary_continuation_v1/{actual_submitted_jobs.json,first_running_observation_v1/summary.json}，此前报告队列为空仅为旧点时记录。

> 最新实际状态（Stage60，2026-10-07；下方保留历史点时记录）：本次重新核验队列为空。当前缩小版384维/4层/6头模型尚未完成完整TRAIN三轮；joint/SDP/seed0的4512069已成功partial结束，保存13,393updates、5,446,337base/16,339,011views，epoch0，约第一轮34.67%及三轮总曝光11.56%。最近完整routine验证在12,897updates/5,244,097base，固定16,000 VALID，criterion0.1601039；charge MAE0.0225134e、energy63.5460kcal/mol、全对geometry0.106932Å；Kappa1/2/3仍差于常量基线，不能以综合loss宣布成熟。P4512058保持FAILED，保存8000updates/3,257,537base，原显存cap失败和765update弃置尾部保留。候选4512071已完成6cases/8合成更新/32s容量验证，数值oracle仍未通过、未正式启用；native store4512072 FAILED189s、原partial数据保留。正式source01b8/protocolf344与24trained+3NONE/1674fits范围保持，尚无三轮FINAL、全矩阵或下游/统计完成。当前entropy0.05在no_grad内不提供正则梯度，报告明确披露。W&B仍offline未同步；未删除原PT。HPC skill v1.0.35同步。实际结果见stage60_training_report_20261007_v1/actual_status_and_metrics.json，当前配置与checkpoint已有CPU安全只读复核。

## 当前 Stage60：P已实际从checkpoint接续，SDP保存状态已审查（2026-10-02；优先于下方点时记录）

完整TRAIN训练3遍/科学协议f344/源码01b8不变；每trained共同47,129,667 base曝光。24trained+3NONE、五库下游与配对统计范围保持，尚无三轮条件完成。P4512053原FAILED1:0/2446s留档；保存2000updates/810689base/2432067views，真实2583持久行对2585ACK全部source-type seal精确，缺2payload类型/数值UNOBSERVED，582已持久尾部更新/237056base弃置但计算计账。Root review raw5fbab6ff授权一次从保存状态恢复，禁止fresh重启。

V11实际27个stdlib方法PASS/0.316s/exit0；P已通过Slurm提交4512054（compute20/16CPU64GiB），原V9首段仍FAILED。Root独立真实W&B早期快照确证新run mo9rvfpz实际optimizer2001，payload与journal按原source numeric catalog类型恢复后SHA精确相等，不仅凭ID/GPU占用。见 stage60_P_checkpoint_continuation_submission_v2/actual_submitted_jobs.json 与 first_running_observation_v1/summary.json；整段仍运行未闭合。提交helper v1在实际quota软限0处、sbatch之前停止，没有新任务；保留其失败证据，v2仅取正的有限soft/hard限额后实际提交54，未更改科学配置。

SDP4512052随后实际FAILED1:0/6326s，guard同为cgroup拒绝、异常PID/cgroup及原根因仍UNOBSERVED。Root compute20安全weights_only读回latest：4000updates/1626647base/4879941views、next_step4002/run zfqoihbh、validation_pending=false；真实4162持久行对4163ACK全部source-type SHA精确，缺1payload未观测。已持久尾部160updates/64170base与原计算6326s留档并计预算。单次恢复review已生成 stage60_failed_SDP_checkpoint_recovery_root_v1/review.json rawbca35628；SDP后继仍待新V12实际检查和提交，不称已恢复。旧矩阵协调器已停ROOT_ATTENTION；新多review V3尚待Root实际检查/迁移，不删除旧状态绕过保护。

协调器V2实际13个不同方法均PASS（首次9passed/4夹具缺key ERROR保留，修夹具后只补4项/0.005s，源码11dee不变）。全五库native binding外部包实际17 pytest cases PASS/3.50s/exit0，包括两tiny RDKit native projection与tensor解码；这不是完整150770-member store、Expansion7608几何或下游1674fits成功。实际384读出配置桥 raw896f95b8保持，旧512 hash只历史来源。完整geometry/mask/store/cost/runner/统计仍待实际执行。

HPC skill v1.0.28 canonical与项目镜像同步。16CPU64GiB、公共完整UUID一本项目任务、Slurm/W&B、已接受共享GPU风险、真实quota余量及2400训练GPUh/102每条件/104GiB输出硬限保持；不kill他人、不删failed或unsynced W&B，不从缺失日志臆造成功。

## 当前 Stage60：正式段状态与恢复审阅（2026-10-02；优先于下方点时记录）

用户确认完整TRAIN训练3遍，冻结f344/源码01b8保持；24trained+3NONE、完整五库下游/配对统计范围不缩减。SDP4512052仍在运行；P4512053实际FAILED1:0/2446s，原矩阵协调器发现失败后退出ROOT_ATTENTION，没有自动重试。原job/batch FAILED与extern COMPLETED、wrapper1及所有failed/W&B产物均保留。原guard具体异常PID/cgroup未记录，根因UNOBSERVED；不得把后续静态发现写成原根因已证实。

Root实际compute20 CPU安全读回P最新检查点：weights_only/type seal精确有效，partial，2000updates/810689base/2432067views、epoch0、tracking.next_step2001/run b5fpdblo。真实W&B2583持久行经原source numeric catalog恢复类型后全部原seal精确匹配；journal已ack2585行，末2行未持久、具体数值/类型UNOBSERVED。检查点之后582个已持久更新/237056base和另外2条ack尾部保留但不计入恢复后规范游标，不能称无损。原FAILED2446s继续计计算预算。见 `docs/phase1/evidence/stage60_failed_P_readback_v1/summary.json`、`stage60_failed_P_history_v2/summary.json`。Root单次checkpoint恢复review已真实生成：`stage60_failed_P_checkpoint_recovery_root_v2/review.json` raw5fbab6ff；尚未提交后继任务，不冒称P已恢复运行。

外部资源父V10仅修进程退出检查：proc/cgroup/proc双读UID/PGID/SID/start_ticks，确认消失/Z跳过，活跨cgroup/身份漂移仍拒，保存首失败诊断，逐PID有界收尾；实际chemprop Python缺pidfd，最终os.kill仍有非原子窗口，不声称完全原子PID保护。18个不同stdlib检查实际通过（首次Root遗漏base fixture导致17passed/1ERROR保留，补fixture后只执行该1项并通过）；见 `stage60_full_corpus_segment_parent_v10/actual_root_close_v1/summary.json`。V11单次failed checkpoint恢复与矩阵协调器V2仍在静态实现/核验，原52任务不重复提交。

下游仍保持五库、41main+21aux ×27=1674最多fits、239primary/269reported cells、fixed20/B32/FP32 native H0和预定统计。Root真实API配置核验确认全部32primary旧引用hash是512维；实际384配置仅input_dim不同，其余完整config一致。`stage60_actual_readout_config_bridge_v1/summary.json` raw896f95b8是按f344已冻结384派生的物理绑定桥，旧不可变协议不覆盖，不据成绩改方案。完整native packed store/Expansion7608几何/真实mask与readout sidecar/runner为本地待验草稿，尚无完整下游训练结果。AZ Cmpd36原字段`['none']`/`['1']`只按冻结missing-or-empty=preserve_unknown保留，专门来源绑定分支不推为化学全负；原strict parser失败保持。

HPC skill当前v1.0.27，canonical/项目镜像同步；16CPU64GiB、单完整UUID一本项目任务、Slurm/W&B、已接受共享风险与真实quota、2400训练GPUh/102每条件/104GiB输出硬限不变。完整Phase1目标继续active，尚无正式三轮条件完成。
## 当前 Stage59：用户确认三轮并要求启动正式训练（2026-10-02；优先于历史一次曝光方案）

> 当前状态（Stage59，2026-10-02；优先于下方历史记录）：用户已确认完整 TRAIN 训练3遍。三轮科学协议实际 FROZEN，content SHA `f344a049ecf9f17bfe437b5e4789b009d64d5bc1041dc2e93238d3f8cbdd0780`，完整TRAIN15,709,889，每trained condition共同base exposure47,129,667，三视图141,389,001；primary FINAL统一三轮端点，BEST仅诊断。实际源码 clean commit347e543/source01b8ad13，独立runtime `/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime` 与已测195文件一致；实际CPU组合83个不同检查通过（4512045初次缺fixture保留，4512046仅补该1项），无科学重跑。模型10,216,035参数、384维4层6头、AdamW3e-5、B512按原子预算动态收缩、动态梯度平衡与全TRAIN归一化均冻结。每任务16CPU/64GiB、Slurm、公共完整UUID一本项目任务、W&B offline保留与已接受共享风险保持。
>
> 首批4512050（joint/SDP/seed0）与4512051（joint/P/seed0）均实际FAILED1:0：启动时临时目录被持久结果的ordinary-only计量拒绝。源代码fresh-fit必须先完成并fsync初始validation journal才能进入优化；实际journal空、无resume/pt/summary，Root据此核验0更新/0 committed exposure；这不是仅由GPU0推断。原失败、partial W&B全部保留，原TMP对象已经自有finally移除，其具体类型UNOBSERVED。Root闭合 `stage59_three_epoch_protocol_v1/failed_startup_close_v2/summary.json`；只授权行政修复后一次fresh，不重放任何科学更新。
>
> 真实node20 W&B-only行政复现3.57秒完成init/一条合成int-float指标/finish、零模型与数据操作；邻近快照确实记录自有同设备单链接Unixsocket，原414计量在TMP报75次类型错。独立TMP计量V9已实际10项stdlib检查通过，仅FileNotFound最多3次完整重计，phase/W&B/cache的414规则不变。新的fresh pair4512052（joint/SDP/seed0）与4512053（joint/P/seed0）已实际RUNNING，compute-0-20、每项16CPU/64GiB，分别GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5与GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02。Root从各自真实W&B early-history不可变快照读取正optimizer_updates，并以原source numeric catalog重建类型后与fsync journal原payload SHA精确匹配；首次实际1次更新/512 base，不是仅凭job ID或GPU占用声称训练启动。见 stage59_three_epoch_protocol_v1/first_running_observation_v1/summary.json。采样418/410秒时owned GPU约46.889/40.129GiB、RSS11.813/13.330GiB、foreign_count0（点时，无独占保证）；两个offline runs均保存，整段尚未关闭。正式矩阵协调器实际7stdlib方法通过，PID778465已在sonmi启动，严格外层24h TERM/30秒收尾；原两失败仍FAILED并计账，只接管新pair，无重复提交/无自动retry失败/无自动删PT。后续成功段须actual三组件Slurm终态0+wrapper0+latest/rendezvous/source/exposure闭合后续训，24trained+3none仍0个完成。真实运行核验在 stage59_formal_matrix_coordinator_v1/actual_root_running_close_v1/summary.json。science frozen不等于正式训练完成：24trained+3none、完整下游与配对统计仍待执行；full-downstream成本前缀/239物理配置不是此次预训练启动门槛。GPUh2400训练/102每条件与104GiB全phase输出均为硬限，并非全任务必然容纳的保证；用户quota留32GiB。真实login quota轻量发布器已运行，严格检查≤90秒新鲜度。技能v1.0.26与镜像同步。

用户已明确确认完整TRAIN训练3遍(3 epochs)。每trained condition共同3N=47,129,667 base /141,389,001 views；训练人口仍15,709,889，验证与最终test不参与。24训练+3fresh NONE以及全部下游/统计范围保持。Root已实际创建隔离source `/share/home/zixiao/PhyChem_MFM_stage59_three_epoch`，初始09a/clean，旧AA与证据保留。现修epoch切换/3N cosine与positive策略/跨轮局部和累计恢复；不暗改在线扰动。冻结与真实提交正在推进，尚不宣称正式已开跑。

HPC skill已同步v1.0.25及references，junction保持已安装入口。Root在已授权范围内继续16CPU64GiB/Slurm/W&B/单UUID一本项目任务/已有共享风险接受；不重复请求启动许可。新累计计算预算按三轮更新，段长2h/900s收尾候选用于有限日志核验器与持续恢复；旧800h/一轮仅历史候选。新训练源码待针对性CPU和有界跨epoch恢复检查；已有数据QA/fit/model init通过字节兼容复用，避免重做全库。

行政CPU4512044已真实11方法通过，job/batch/extern COMPLETED0:0/1s，guard范围不等于新三轮科学路径通过。更正Stage58文字：几何0.113864Å及baseline0.112879Å是global geometry-pair MAE，旧root文字误标RMSE；producer验证原文件/数值/摘要未改。正式24训练+3none均仍0，完成齐备新协议后直接提交。
## 当前 Stage58 核验与共同训练预算（2026-10-02；优先于历史状态）

HPC skill 当前 v1.0.24（canonical/项目镜像及 references 同步）。P 成本4512041实际 COMPLETED0:0/115s，33真 optimizer updates/13824 base；24非probe稳态 .9097928382s，仅前缀投影，原缓存失败4512040保留。固定 partial83 TRAIN-CV4512042实际九读出全部闭合/COMPLETED0:0/219s，QM7主 MAE91.707722 对 NONE87.028689，linear87.662777 对87.340147，CYP hit@1 20/95 对24/95；均是小 TRAIN 面板描述性观察，端点没有换为后续643。

同一16k监控集五次原单位验证已完成，续训4512038累计643updates/261825base（完整训练集约1.67%）；root判定为“训练不足需延长”，并非训练充分。PM7、电荷学习明显，几何global geometry-pair MAE仍略差于带噪输入基线，28回归叶仅8项MAE优于自身基线，D中Kappa仍有大原单位误差。Warmup32768已结束而fullN cosine仍很早，不从动态总loss平台宣称成熟。科学代码仍09a/AA；在线扰动由CPUgetitem从有界clean cache生成，geom0.10Å Gaussian、无局部角/键缩放/删除，元素约9% eligible heavy候选且仅actual changed监督，seed+logical ordinal不含epoch；用户询问现状未授权改逐epoch随机。

九CV单元实际train/eval tensor序列、两mask、读出init与config摘要完全相同；独立真实源码审阅确认该native H0路由仅消费这些x/pos/partition/nativeIDs/targets/masks，故限定计算数据输入matched。唯一guanabenz:158完整source_proof SHA不同，历史完整payload未保存，来源literal/化学等价仍NOT_PROVEN，差异原因UNOBSERVED；不伪造全provenance fairness PASS或重训补日志。见stage58_matched_cv_review_v1、stage58_transfer_input_review_v1/root_close。

外部trained telemetry adapter实际CPU4512043的6stdlib methods+genuine AA CLI import/help+旧real WB layout计量已COMPLETED0:0/5s；root闭合见stage58_formal_telemetry_cpu_v1/root_close/summary.json。新V6仅行政路由/逐segment414计量/2h与900s收尾，11stdlib方法已提交4512044 CPU，真实结果尚待闭合，不称LIVE训练通过。

Root拟每trained condition共同一次完整N=15,709,889（24训练+3fresh NONE范围保持），actual sampler seed0/1/2为38651/38645/38644 batches；P/SDP实际前缀规划约635GPUh，训练矩阵累计800h/每condition34h为新预算候选。统一2h segments避免已知8h轻条件超过20000记录reader上界，恢复不重置累计预算，不加入不存在的max_batches字段、不截断日志。正式仍16CPU64GiB、RSS56GiB、1GiB GPU余量、单UUID本项目一任务；当前可验证容量先用node20两modified4090，所有seed同硬件/环境，startup minimum=真实SDP peak+1GiB=44,707,086,336B，至多2并发。当前共享风险用户已经授权，不再重复审批；未称隔离PASS。21/22仍在授权集合，当前B512/384模型32GB容量未验证，不凭旧5090路径成功推定。

完整下游1674 fixed20读出仍需单列GPU成本与全阶段输出上限；CPU试跑墙时不能直接称GPU实测。正在准备一次固定TRAIN-only、fresh H0、formal B32的真实GPU readout cost probe，不评分/不读最终targets/不换partial端点。待成本与新父验收闭合后生成齐备不可变科学/执行协议并直接运行。正式矩阵仍0/24训练+0/3正式NONE、NOT_FROZEN；完整下游/统计交付范围保持。Root具体判断与候选参数见stage58_learning_budget_decision_v1/decisions.json。本文所有旧预算/失败/点时状态保留，不升级。
# Remote server workflow

- This directory is `/share/home/zixiao/descriptor_analysis` on `zixiao@202.38.247.57:22`, exposed on Windows as the live SSHFS mount `X:\`.
- When the user says to implement, test, or run something "on the server", use this project and this account unless the user explicitly says otherwise.
- File edits under `X:\` apply directly to the server; this is not a local copy or a delayed synchronization folder.
- The current independent PhyChem_MFM refactor is `/share/home/zixiao/PhyChem_MFM_ICLR2027`; Phase 1 implementation reuses its H0 API. The archived `modern_ML_representation/support_scripts/MFM_descriptor` remains reference-only. Read the actual source repository's `AGENTS.md` as well.
- Run Linux commands and project scripts through `ssh descriptor-analysis-remote "cd /share/home/zixiao/descriptor_analysis && <command>"`, not through a local Windows interpreter.
- Before server work, verify the mount and key-based SSH connection. Never store the server password in the repository.

## Compute roles and submission policy

- This server is the default environment for code changes, audits, preprocessing, smoke tests, debugging, and the current Phase 1 formal work. On 2026-10-02 the user explicitly selected compute-0-20, compute-0-21 and compute-0-22 for Slurm formal tasks; verify the actual partition and GPU protection before training. Paid school-server authorization is not a prerequisite for this authorized sonmi scope.
- Direct SSH computation is permitted only for bounded short tests on `compute-0-20` or `compute-0-21`; verify node identity and available resources first. Formal work runs on nodes allocated by Slurm. Do not run compute jobs on the login node.
- A completed job may be purged from the controller and make `squeue -j` fail with Invalid job id specified. Check exact IDs in the current own-user queue together with retained actual sacct completion; do not replay science or infer failure from an expired queue ID.
- Submit all formal tasks through Slurm with `sbatch`; use `squeue` to inspect the queue and `sacct` to verify completion. Never launch formal work directly through SSH, nohup, tmux, or screen outside a Slurm allocation.
- The paid, GPU-rich pretraining server (the "school server") is `202264640132@202.38.252.202:22`. Use it only after the user explicitly approves starting formal pretraining.
- Formal pretraining on the school server must use `sbatch` and the cluster/partition/account settings already encoded in its existing sbatch scripts. Inspect the relevant shell history and those scripts before the first submission to follow the established workflow.
- Implementation, debugging, smoke tests, and exploratory runs remain on this default server even when they prepare a pretraining experiment. Never launch heavy work directly on either login node.
- Never store either server password in the repository, scripts, logs, shell history, or project configuration. Prefer key-based SSH and named aliases.

## Maintained HPC operating skill

- Before working on this server, read `docs/skills/huagong_hpc_requirement/SKILL.md` and the relevant sections of its `references/commands.md`. The Windows user-skill installation is `C:/Users/mint/.codex/skills/huagong_hpc_requirement/SKILL.md`.
- Never kill, cancel, suspend, preempt, or modify another user's tasks. Before stopping a task from the current work, verify its exact job ID/PID, owner, and authorization scope.
- By default, before formal GPU training verify GPU allocation, effective device/SSH isolation, non-preemptible scheduling, and sufficient memory headroom; the explicit 2026-10-02 current Phase1 shared-risk exception below overrides the unavailable isolation requirement only for its authorized scope. An idle GPU or CUDA_VISIBLE_DEVICES alone does not reserve a device. The maintained skill records currently unverified GPU protections; recheck the live configuration before submission.
- Every formal model-training run must use W&B or an equivalent functional experiment-management tool, including fine-tuning, ablations, and downstream training. Preserve metrics, configuration, run/job IDs, checkpoint references, and final status.
- When supplying an explicit W&B history step, commit the completed logical record explicitly (`commit=True`, or a declared accumulation-and-commit flow). Verify persisted history against scientific update/exposure cursors; a run ID or SDK in-memory cursor alone does not prove durable metrics. Fresh offline write verification does not establish backend resume or online sync.
- Respect the user's actual storage quota. Declared output budgets include temporary files, atomic-write overlap and failure records throughout the run. Clean verified obsolete self-owned test outputs and redundant formal artifacts while preserving unique results, necessary checkpoints, active-job dependencies, and unsynced tracking records.
- Apply the user's latest corrections during relevant work and update the skill, its Windows/project copies, and related AGENTS.md rules together. Maintain the version and verification date; do not rely only on conversational memory.

- When GPU hardware changes, verify actual CUDA operations in an owned bounded allocation and use a separately validated environment; include download/temp/cache peaks in storage budgets. The 2026-10-02 cu128 environment has passed four kernels and an actual full-model SDP update, durable W&B records and strict checkpoint restore on compute-0-21 (job 4511948). Compute-0-22 model compatibility and GPU reservation still require independent verification.

## Phase 1 scientific authority

- Follow `PhyChem_MFM_Phase1_Instructions.md` and `docs/phase1/DECISIONS.md`. The user's charge correction means existing MOPAC `NET ATOMIC CHARGES` (`y`, e), not a request to generate another population analysis.
- Preserve historical fusion results and use new shared H0 results separately. Formal conditions start from paired random initialization. Development probes use training-source molecular-group CV; final-test molecular identities may be read for decontamination, without using their targets or performance for development.

## 2026-10-02：已核验的单节点提交与运行绑定

- huagong_hpc_requirement当前1.0.13。单节点任务不能把20、21、22同时当作nodelist候选池；选择实际核实节点，遵守冻结协议允许集合和同种GPU/环境。
- 科学协议与独立预训练执行协议均已冻结；pretraining_only/PENDING只允许下游实际执行哈希后补，不改科学规则/resume协议。正式GPU任务仍须真实保护机制，gpu_num名称或冻结JSON不代替依据。
- hash/复杂参数从实际闭合文件自动派生，不从聊天手工转写；使用结构化argv，不拼接shell。最新证据在docs/phase1/evidence/stage45_pretraining_compilation。

## 2026-10-02：当前 Phase 1 已明确接受共享 GPU 风险

- 用户明确回复“是，接受风险并启动”。huagong_hpc_requirement已同步1.0.14：仅当前冻结Phase1/sonmi20、21、22允许自有Slurm CPU allocation中手选启动时实测空闲单GPU并绑定实际UUID；未注册GRES/未隔离不再是该任务启动阻碍。不推广其它范围，不声称独占或保护PASS。
- 科学协议不变；运行例外使用新不可变protocol版本/真实源码绑定。仍保持Slurm、W&B、UID/job/node/同GPU环境、8h/8GiB自身RSS/12GiB自身GPU/2GiB输出和quota；foreign运行占用记录风险，仅对本job自有进程执行异常停止，不杀他人、不自动重跑。
- 上述v1.0.13“保护仍为障碍”段落是接受风险前的点时事实。最新启动和授权证据见docs/phase1/evidence/stage46_shared_gpu_execution和stage46_shared_gpu_launch。

## 2026-10-02：当前 Phase 1 每任务资源改为16CPU/64GiB

用户最新明确要求每个正式训练任务16个CPU、64GB内存，单GPU只安排一个本项目任务；技能v1.0.15已同步。此前2CPU/12GiB、RSS8GiB/GPU12GiB仅为旧协议配置，不硬编码沿用。资源修改记录在新不可变协议；实际显存余量来自所选完整UUID，协作锁不声称阻止他人SSH。数据构建缓存/预取必须保持样本、标签、视图seed与顺序；如batch/更新次数改变，明确更新所有对照组同一科学配置及数据曝光量，不能在旧冻结协议下暗改。

## 2026-10-02：缩小模型并扩大预训练数据范围

用户最新明确要求适度缩小模型、利用完整LMDB更多样本、减少总批次数。58k/512维6层/batch2/49993更新及科学协议2d已成为旧方案历史依据，不能自动正式提交。当前仍每任务16CPU64GiB/单GPU一本项目任务/共享风险授权。先核实完整structure与parent molecule口径，再以实际profile冻结新模型、batch、数据覆盖、曝光和预算；使用有界缓存/预取，保留最终test目标隔离与MOPAC NET ATOMIC CHARGES。技能v1.0.16已同步。

## 2026-10-02：正式预训练前加入任务损失平衡

用户最新要求归一化损失与动态损失系数，避免某任务主导共享主干优化；技能当前v1.0.17。现有连续目标已有train-only标准化，须审阅实际task/family聚合，再以真实shared-gradient贡献（含组内差异）、权重约束、有效监督掩码及实际开销验证新方案。scale/controller只使用训练来源更新，缺失task不推进状态，验证状态冻结，最终测试target不参与；W&B记录raw/normalized各任务loss、动态系数和梯度占比，完整controller state纳入atomic checkpoint/resume。旧损失capacity pilot不等于新科学方案已冻结或正式训练，算法和新的数据/模型共同进入新协议。
## 2026-10-02：全量PyTorch预取与分段退出

当前技能v1.0.18。当前多worker预取路径在CPU4511978默认fork测试实际300s超时（根因尚未由stack证明），改用显式安全启动上下文、有限worker等待以及耗尽/异常/分段partial iterator关闭，并实际验证完整索引与仅已消费游标恢复。新脚本可在登录节点用标准库AST先检查语法，不运行模型或数据计算。FullQA4511981已Slurm运行；小测试通过不等于全库或正式模型训练通过。

## 2026-10-02 运行纠正（HPC skill v1.0.19）

已验证短节点TMPDIR避免PyTorch进程共享AF_UNIX路径过长；自有worker关闭须限时join并实测退出。同size/保mtime索引变更不得用旧元数据cache判为未改变。JSON直方图键在seal之前统一为字符串，未取得真实child0验收的chunk不凭手改receipt恢复。实际loader4511986 46 passed；QA v2 CPU4511984 9 passed、fresh full4511985运行中；Stage50 v2 collection导入失败保留；新v4实际CLI --help exit0、CPU4511988 38 passed/COMPLETED0:0，隔离候选已提交测试字节，production仍不改。完整QA/新fit及真实119类GPU容量和段恢复尚待闭合，正式optimizer仍0。

## 当前运行纠正（2026-10-02，HPC skill v1.0.20；优先于历史条款）

当前技能v1.0.20。新完整数据/较小模型/动态损失协议待全量fit与实际运行profile冻结；上方2d旧协议、8GiB/12GiB和接受风险前审批均为历史，不作为新配置。用户已接受当前Phase1及随后明确模型/数据修订的共享GPU风险；仍16CPU64GiB、单GPU一个本项目任务、Slurm/W&B及quota/自有资源监控。各启动器共用完整UUID.lock，按条件/seed单segment互斥，不以整项目锁串行不同GPU；累计GPU时/并发/条件跨segment存储另由root管理。局部扰动generator不消耗模型global RNG，seed/epoch规则显式冻结；weights_only metadata用builtin类型、Torch版本plain str，并实际readback。恢复numeric/semantic discrete/byteexact分别报告，controller自身seal与浮点差异区分；4511994原FAILED保留，新标准库闭合只证明既有数值/离散事实，不重跑容量或定因。共用曝光primary FINAL与未同步W&B、故障证据/活动checkpoint保留。实际source/测试范围见docs/phase1/evidence/stage52_positive_strategy_v2/actual_source_receipt_v3.json。
## 当前运行纠正（2026-10-02，HPC skill v1.0.21）

当前技能v1.0.21，两份及references同步。非交互srun同时--input=none及DEVNULL/</dev/null，不吞父PTY后续命令；每层立即保存真实退出码，旧缺失保持UNRECORDED，不为日志重跑科学。Python argv与runtime_environment使用已核实logical absolute venv入口，不用resolve/readlink-f binary目标替换；同一binary可选择不同包环境，metadata不证明GPU兼容。CLI仅此路径修正已由CPU4512003的4新入口cases+13原metadata/CLIhelp0实际验收，当前isolated clean3aea9a7/sourcec5a1dbe，见stage53_seed_runtime/actual_source_receipt_v2.json；77 prior scientific cases只对旧source33ee的原点时范围，科学代码字节未改。V4 launcher31检查4512001及node22helper16 CPU检查4512002已闭合，node22实际GPU仍待fullQA/fit/profile。Stage54 CPU4512004为15stdlib/实际新source DRAFT编译通过，不是科学冻结/授权提交；27entries/24training/3none保持。FullQA4511985在166子目录后finalizing，父summary尚未闭合。用户当前共享风险授权、16CPU64GiB/Slurm/W&B、common完整UUID.lock与全矩阵累计budget规则保持，正式optimizer0。

## 当前Stage55源码及验证接口（2026-10-02；优先于上方历史）

isolated当前clean09a02980/sourceaa582a2e，195files2488024B；见docs/phase1/evidence/stage55_original_metrics/actual_source_receipt_v3.json。原单位验证复用同一forward，计数/MAE/RMSE/classification及train-only控制累加器随partial验证atomic恢复；正式CLI要求raw绑定validation_controls。能量control118physical+intercept=119，training_application仍NONE；S实际corrupted/clean-positive来源mode未fit则typed unavailable，不以clean全人口代替。实际4512006 34新cases/CLIhelp0/COMPLETED0；4512005原父FAILED保留，其中30trainer/19compiler/33模拟guards仅原sourceimage范围，不重放。测试consumer为JSON接口时，经真正producer JSON序列化再读入来验证类型边界，不用放宽NumPy/weights_only规则来掩盖夹具错误。4512007仅5+5metadata checks，不是全库cost或实际scale提取。fullQA4511985父仍finalizing；production不改，活动SQLite不查询/重hash。prep新v3绑定09a/aa并WAIT，v1/v2未提交且保留。技能v1.0.21与用户已有共享风险授权/16CPU64GiB/UUID单任务/Slurm/W&B/累计budget不变；完整Phase1 goal继续含正式24训练+3none/下游/配对统计，正式optimizer仍0。
## 当前Stage56执行事实（2026-10-02；优先于上方点时状态）

完整QA4511985与全train-only preparation4512008均已实际COMPLETED0:0，train15,709,889/validation161,329，normalization/P-D controls/三seed119类384×4初始化已闭合，分别保留production QA producer和09a/aa consumer来源。source科学字节未改。详见docs/phase1/WORK_STATUS.md顶部及stage50_full_corpus_preparation/root_full_close_v3/summary.json。Stage56 CPU原4512010 FAILED保留48passed4failed；外部collate数量窄修正v3、4512014真实7passed/COMPLETED0，未声称整个52case在新helper重跑。node22profile4512012因启动时无空闲5090失败，未spawn模型child/optimizer0，不能升级容量或CUDA兼容PASS；无他人kill、无科学自动重放。S sidecar/真实TRAIN开发CV/34尺度/全sampler成本与新科学freeze仍待；正式0，完整24训练+3none/固定下游统计目标保持。技能v1.0.21、既有共享风险授权/16CPU64GiB/单完整UUID一本项目任务/Slurm/W&B/累计budget不变。在线扰动仍seed+logical ordinal固定复现，不含epoch，不静默改随机配方。

## 当前Stage57执行事实（2026-10-02）

TRAIN panel4512016实际闭合（QM7 192/CYP1A2 96，3折）；node20 profile4512017实际COMPLETED0:0/215s，36真实更新、712原子singleton/B512/8-worker33前缀全部请求shape通过，实际W&B三个run关闭/u33参考33条、34叶校准冻结。root_close_v1保存实际7列accounting，source仍09a/AA。额外u32全H0诊断114queries/46.85s单独计成本，未声称完整验证/恢复/成熟度通过。21纯metadata4512018实际完成，root-owned ED25519公钥与SSH呈现指纹匹配；未改known_hosts/关闭严格校验，也不是5090新模型CUDA测试。sampler4512023已实际RUNNING，精确3seed全TRAIN/512/65536/8M计数未闭合。34尺度metadata提取与resolved-pilot配置桥接、真实学习/恢复及TRAIN迁移CV仍待各自实际结果；正式0/NOT_FROZEN，24训练+3none/下游统计完整scope保持。详情见WORK_STATUS顶部与对应不可变证据目录；不升级旧FAILED或重放科学。用户关于在线扰动的询问仅说明现状：当前seed+logical ordinal固定复现，没有授权或实施逐epoch换扰动。

Stage57后续实际终态：4512023全3seed整数sampler COMPLETED0:0/484s，38,651/38,645/38,644 batches均覆盖15,709,889训练结构；GPU成本仍pending。4512024实际5metadata tests+34scales提取COMPLETED0:0/1s；4512025实际5metadata methods+12槽/37transitive绑定COMPLETED0:0。新v2只桥接原校准与resolved-pilot配置，原科学tail/driver保持。真实bounded learning4512026已compute20 RUNNING/16CPU64GiB（最近34s），262144前缀/2h上限、原单位验证及fresh continuation尚无闭合结论；缓存区别须实际监控。根闭合/提交证据见stage57_node20_learning_execution；正式0/NOT_FROZEN，完整24训练+3none/下游/统计scope继续。

## 当前运行纠正（Stage57，2026-10-02，HPC skill v1.0.22）

技能v1.0.22，两份SKILL/references同步，发现junction仍指向用户安装。自有W&B正常内部链接经实际布局/目标范围/UID/no-follow核验后可计量，目录和link文本计入、regular inode只一次，不沿目录链接递归或删除unsynced run修复guard。compute上的sacct可能无法访问localhost:6819，作业内测试退出码与login实际终态记账分开，不能重放已完成科学补日志或把组件通过升级原FAILED父。4512026学习FAILED1:0/63s无parent summary/child exit、updates UNPROVEN/partial8trzm保留；4512028五filesystemcases实际exit0而外围accounting失败，root sonmi另闭合。新4512029实际RUNNING20/16CPU64GiB（最近2:20）；e272训练CLI、sourceAA/扰动/损失/原学习预算未改。正式0/NOT_FROZEN、完整24训练+3none/固定下游统计scope保持，详情WORK_STATUS最新条。

## 当前Stage57学习与开发CV闭合（2026-10-02；优先于点时状态）

4512029实际FAILED1:0/415s，已保存真实33792base/83optimizer的checkpoint及0/32768两次16000监控验证；v3资源监督闭合、无resource stop。故障在关闭W&B后的payload hash类型边界。4512030误写81/32768 guard原FAILED保留；4512032实际COMPLETED0:0/6s，85/85原acknowledged scientific payload按源码int/float类型恢复后SHA精确相等、无数值容差，并safe读回83/33792。root sonmi实际accounting与小文件闭合在stage57_learning_closed_history_diagnostic/root_accounting_close_v1。后续仅从保存的83-update状态continuation，不重放first/升级原FAILED。4512031实际11 checks/COMPLETED；none CPU4512033 FAILED3s，child输出路径在package根被明确guard拒，未进入Torch/target/W&B；只改父argv为包外新目录，已测v2科学字节不动。开发pilot-CV端点在评分前固定33792/83 partial，不称正式FINAL。在线扰动seed+logical ordinal不含epoch，geometry只0.10Å Gaussian（局部角/键缩放关闭）、实际changed元素位点CE；没有授权改变扰动配方。HPC skill仍v1.0.22，正式矩阵0/NOT_FROZEN及完整24训练+3none/下游统计scope保持。
## 当前Stage58执行闭合与P成本缓存纠正（2026-10-02；优先于历史点时状态）

技能当前v1.0.23。续训4512038实际COMPLETED0:0/1057s，原83/33792状态精确恢复后累计643updates/261825base、新563条WB全部source-type exact，无first重放，旧FAILED保留。NONE4512037实际九fixed20 TRAIN开发CV闭合/COMPLETED0:0/219s；pilot-provider CPU4512039实际12passed+5subtests/COMPLETED0:0/7s，pilot83端点评分前固定不变。Root实际终态、source/raw产物闭合在stage57_goal_actual_close_v1，none小panel不等于正式none/full downstream。Pcost4512040 FAILED71s：W&B0.28.1对WANDB_CACHE_DIR再追加wandb，父设置cache/wandb导致实际cache/wandb/wandb/logs被合法布局guard拒；只修缓存根为cache，不删unsynced partial/放宽任意链接/改变科学loop。缺science journal不宣称optimizer0。训练/迁移/成熟度与成本预算须继续完整审核；正式0/24训练+0/3正式none、NOT_FROZEN，full下游/配对stats完整scope保持。科学source仍09a/AA，扰动seed+logical ordinal不含epoch，geom0.10Å Gaussian且局部角/键缩放明确关闭；用户问现状没有授权改配方。实际16CPU64GiB/单UUID一本项目任务/Slurm/W&B/共享风险已授权/quota不变。
## 2026-10-07 Stage61：Slurm 脚本换行核验

正式 sbatch 提交前读取脚本原始 bytes，要求 LF 且无 CR；bash -n 不能代替此检查。F5 materialization v2 的实际 CRLF 提交拒绝未创建 job，失败元数据保存在 stage61_data_input_audit_v1/scan_v2/checks/root_F5_materialization_v2_actual_CRLF_submission_rejection.json。旧冻结脚本/请求保留；仅 LF 修复采用独立 v2_unix.sbatch、新 ROOT READY 及任务 ID。原 F5 4512364、数据/manifest/协议/runs 未修改。HPC skill v1.0.40 两份同步。

## 2026-10-08 Stage61：版本与实际 CPU 记账

HPC skill v1.0.41两份同步。仅数字点分版本的前导零可规范化；RDKit2025.9.5与2025.09.5不应触发依赖升级。4512378启动门禁失败及旧源保留。预算使用实际AllocCPUS×ElapsedRaw，不重复计batch/extern；4512381请求1CPU但实际2CPU×1秒，C4续跑前累计292CPU秒。含atom-map的3D MolBlock回读可能增加立体注记，须核对封存身份、化学图和原明确CIP，不全局移除立体信息；审阅续跑保留原82固定seed、8真实MMFF失败与原signature lock，最多82新PM7。具体证据见docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/root_actual_C4_v4_reviewed_continuation_submission_20261008_v1.json；原数据/manifest/冻结协议/runs未修改，不据此宣称完整指南或历史复现成功。
## 2026-10-08 Stage61：确切 CPU 节点与已注册 prepared 元信息（HPC skill v1.0.42）

- 精确核验 CPU 节点时使用 `sinfo --Node --nodes=目标节点`，再结合 `scontrol show node 目标节点` 核对状态、空闲 CPU 和声明内存；默认 `sinfo` 可能压缩为 `compute-[17,19]`，不能误判为没有 IDLE 节点。4512488 的首次 preflight 在 READY/sbatch 前退出，只加逐节点输出后真实提交；点时状态不成为永久约束。
- Root 已注册 path/完整 SHA256 的 prepared 模板也保留原字节。后补 partial/count/cost 写新独立路径，不覆盖 active READY、源码或 RootReview。误改保留 mutation 说明及修改后副本；只有恢复候选实际字节数和完整原 SHA 同时精确一致才恢复，否则记录 owned prepared 差异，不据此触发原数据 HARD_STOP 或重跑科学。当前 v2 TEMPLATE 已按12589字节与原完整 SHA 精确恢复，新增成本另存 v3；actual4512488 READY/源码/RootReview 保持。

两份 SKILL.md 与 references/commands.md 同步；其他既有规则和历史点时状态保留。具体证据见 `docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/root_C1_current4_inventory_source_review_20261008_v2.json` 与 `pipeline_C1_current4_TEMPLATE_v2_exact_restoration_receipt_v1.json`。

## 2026-10-08 Stage61：PowerShell→ssh 引号/管道（HPC skill v1.0.43）
复杂远端元信息命令用自有Python脚本固定绝对路径启动，在脚本内subprocess参数列表、shell=False及DEVNULL；不要把嵌套引号或JSON字符串当跨shell转义。实际script|batch正则失去引号后新建自有at job1，已核本次创建输出、UID/owner/队列时间并仅atrm1/rc0/post不存在，未动Slurm或原数据，证明见scan_v2/checks/pipeline_PM7_own_unintended_at_job1_cleanup_v1.json。现有原始数据只读/唯一Slurm提交/停止规则不变，不增加审批门。

## 2026-10-16 WP5 v12：pilot 差异披露与最终验收

当前完整点时交接为 runs/phase1_wp5_20261011/reports/wp5_active_handoff_20261016_acceptance_v12.md；正式actual542人口已闭合，最终验收继续。指南当前200重现与旧pilot差异逐条披露分开验收，不能附加零DIFF停审或伪装数字PASS。真实577六次受控对照和582的43失败原因/13语义fixture已闭合；Root final disclosure review及delivery3保留全部原DIFF/状态、未归因项和冻结参数，index1用supplemental纳入实际证据。全量读回/原200/G0/存储/实际终态成本仍须完成，不因此重跑已闭合QM或写LMDB。活动G0 DB不做广泛观察查询；大目录真实终态未完成才续算、保留DONE。大型共享产物SHA在服务器元数据观测，live X只编辑小文件；不杀共享挂载或他人任务。技能镜像同步维护，不覆盖并发S修复内容。

## 2026-11-03 PubChem CPU-node preference and compute-0-21 approval

For the current PubChem expansion goal only, the user approved compute-0-21, initially 32 CPUs, Slurm partition all, CPU-only with no GPU request. Prefer available CPU nodes for later submissions; when none is available, compute-0-21 remains approved. This overrides compute-0-20-only for this goal and does not authorize changing other jobs or using the paid server.

## 2026-11-03 D-3 user override

For this D-3 export and its continuations, the user authorizes compute-0-21 / partition all / 16 CPUs / CPU-only. Submit to Slurm immediately, including while resources are occupied. Do not set a Slurm or program wall-time limit, memory request size, RSS limit or MemAvailable stop threshold. Keep resource telemetry; pause and resume for real storage availability while preserving the existing 100GB account headroom after all future budgets. Output forecasts are estimates, not arbitrary failure caps. Scientific rules and the single final data validation remain unchanged; leave other jobs untouched.


## 2026-11-03 D3优先安排的临时运行事实

Common4525659已在Main真实配额核对后恢复原64GiB未来预算并CONT；其后实际FAILED/1，不再是STOPPED。1957034旧暂停控制器已退休，2009468接续恢复控制器已完成。D3旧4525651为存储迁移实际CANCELLED，141闭合源组保留；新大文件使用Lustre，CPU路由仍按此前数据线授权（实际cpu分区节点含11–13，并有21例外），不以空闲CPU作提交门。compute-0-21目前DRAIN，不修改Slurm管理员节点状态。旧原始PubChem4525652仍为另行CANCELLED并保留部分结果。具体当前D3作业以control/current_work_state.json为准，不从本段恢复旧控制器或重复提交后台任务。

## 2026-11-03 PubChem return to recovered Alpha

For the current PubChem expansion goal, the user explicitly prefers recovered alpha@218.192.171.238:22 after inspecting reusable results. Use real Alpha UID1264 and /gfshome/alpha/codex_data_v1_20261026; do not pretend Main UID1278/source paths/proofs. Prefer available CPU nodes; current sonmi1/cpu16 is an observation, not permanent availability. Preserve existing results. Stop only duplicate owned expansion computation after verifying the replacement; Main Common may finish on its canonical source. New Alpha code is deployed from checked isolated source; X remains Main, never an Alpha mount. Run Python-I/clean code cwd to avoid home/string.py; do not modify that user file. Other tasks and paid pretraining are outside this authorization.
