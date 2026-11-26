## 2026-11-06 用户要求：节点文件传输不得占满磁盘

适用于所有 Codex 窗口、子 agent、CPU/GPU 节点及下载、复制、rsync、缓存、解压和临时输出；执行任何节点大文件传输前必须遵守。

- 在实际目标节点解析目标路径及其文件系统，用 findmnt -T、df -B1 和 df -Pi 检查可用字节与 inode；/tmp、/var/tmp 可能与根分区及 SlurmdSpoolDir 共盘，不能当作独立大容量 scratch。共享盘 df 和账户 quota 不能替代节点本地磁盘检查。
- 估算新增物理占用的峰值，计入源文件、解压/数据库临时文件、旧新文件并存、partial 文件、失败残留及所有窗口已计划/正在进行的同盘写入。跨窗口在同一目标盘协调预留，不能各自拿同一份空闲空间重复预算。
- 根分区默认至少保留 max(10 GiB, 文件系统总容量的 10%) 给系统和 Slurm；站点更严格要求优先。其他文件系统须保留站点要求及覆盖并发增长的余量，既有账户 quota 余量规则继续执行。目标可用量不足覆盖峰值加余量，或无法查明容量时，不得开始复制；换经核实的专用 scratch/共享盘、减小缓存或分批处理。
- 长传输及缓存生成期间持续观察同盘余量，在触及预留空间前停止新增写入并保留可续传状态，不能等到 ENOSPC 才处理。新传输/缓存入口落实容量预检和运行期保护；仅打印 df 不算保护。未核实用途/所有权/依赖的文件不得自动删除，不改管理员目录或自行解除 drain。
- 已核实事故：compute-0-17 作业4526050于2026-11-05 16:33复制约29GB的d7.duckdb到/tmp，留下17,656,872,960字节部分文件并报ENOSPC，同刻节点因SlurmdSpoolDir is full进入drain。compute-0-20作业4526119取消后一个进程未退出并触发Kill task failed；这是不同故障，不误写为该节点磁盘满。

## 2026-11-04 PubChem concurrency follow-up

The user explicitly allows an appropriate increase in computation concurrency when needed. Recheck live free CPU allocations and actual RAM; prefer idle pure CPU nodes. When those are occupied, using idle CPU cores on a free Alpha host in partition all is within this CPU-only continuation, with no GPU request or GPU computation and no paid server. Root's current operational selection is compute-0-2/all 32 CPUs plus sonmi1/cpu 16 CPUs after the current filter, not a permanent user mandate for these counts/nodes. Use disjoint fingerprint search partitions and preserve identical full-reference exact math, source identity, R/N rules and max3 UFF/D recipe. Keep 1885201 running untouched; do not restart the active filter merely to raise its worker count. Update only unstarted downstream plans or deploy a new immutable source for continuation. Root remains the sole submission coordinator; real CPU/RSS/shared quota accounting and the one daily human summary remain.

## 2026-11-04 PubChem exact structure decontamination and direct execution

Current explicit user correction overrides all older composition/wildcard decontamination and per-job Root approval requirements for this expansion. Use only complete InChIKey and the original v1 wp5 key (first 14 InChIKey characters + ":" + final protonation character). Remove every elemental-composition exact/lower-bound and wildcard veto, including MoleculeNet case:18/PDBbind 1pts and case:00/ClinTox. Exclude all PDBbind from decontamination sources because it is outside the planned downstream evaluation. Any downstream record without a determined exact structure contributes no structural veto; exclude it from downstream evaluation and preserve a record-level exclusion list and original evidence.

Stop and archive further 1slg/1pts correspondence research. Rebuild source keys from original physical identity rows (filter PDBbind before insertion so shared keys from other datasets remain), then run one whole-pool filter, directly build R/N queues and the 2.5M first batch, followed by UFF (maximum 3 actual conformers, no filling/retry) and D labels. Keep the existing fixed 1M nearest-neighbor job running in the background; it must not block this expansion. There is no new per-job Root acceptance/receipt or approval schema: keep necessary producer checkpoints/manifests and actual resource/accounting facts, and write one daily summary. Preserve old reports as superseded history. Exact full reference NN math, v1 ranking rules, original UFF/D science and real shared quota/resource protection remain unchanged.

## 2026-11-03 PubChem全任务与3构象修订

扩充执行以configs/data_v1/expansion/user_completion_20261103.json的最新用户授权为准：2.1–2.9全交付，首批250万、R/N各125万；每分子最多3个UFF构象，不足不补不重试，固定种子/顺序支持保留原构象并续加；D20每分子一次、D3逐实际构象、无P′。旧任务超时/4h/STOP2/成本倍数自动停止不再阻塞本次扩充，真实科学/资源保护不变。实时挂载可经本机127.0.0.1:22369 nativeSSH-SFTP适配到Y，在局部PowerShell以逻辑X→Y解析后编辑，使用前验证连接。Git大数据在外部、仓库仅代码报告清单哈希。

## 2026-11-03 当前D-3导出按用户六条简化

单Slurm作业；导出末尾仅一次counts＋随机1000条parquet逐字段＋一份总清单SHA；吞吐仅一次且最多5分钟；rsync --checksum分发后不追加hash；真实验收交给Model loader/head overfit。旧Source3/10k/16reader/完整F64二次读回不再作本轮交付门。失败直接修复重跑，同一每日汇总一行。具体资源边界见SKILL.md顶部最新条款。

## 2026-11-02 D-4主节点特许执行

仅本次D-4已获直接在sonmi主节点完成的明确授权。当前入口与实际PID/UID/start_ticks/exit从 `runs/data_v1_20261025/control/D4_actual_headnode_20261102_v1/actual_local_launch.json` 和 `current_work_state.json` 读取，先核实真实进程，勿重开旧CPU等待或重复启动。2核亲和性、单线程库、原6项及两次TRAIN精确复算保留；本地exit0如实记本地终态，不伪造Slurm作业号/C0。D-3/D-5及P′不继承该主节点授权。
## 2026-11-02 当前D-4及临时账户余量

本轮D-4按用户要求持续到完整暂定交付；原6项检查和两次TRAIN精确重放保留。账户全future后余量临时采用100000000000字节，输出上限仍56GiB；机器政策见 `runs/data_v1_20261025/control/current_account_quota_floor_policy.json`。当前执行与交付事实只读 `runs/data_v1_20261025/control/current_work_state.json` 及当日单份汇总，不能沿用旧PID/旧200GB守卫或把Source待跑写成通过。P′修复授权仍单独等待。
## 2026-10-25 模型v3开发入口与记录

主树为PROJECT/MFM_model_v3，live X编辑；子树MFM_model_v3_sa1/sa2/sa3。GitHub来源、公开预注册与实际执行SHA映射见主树docs/model_v3/EXECUTION.md。新任务不恢复历史队列。原2016测试通过的实际16进程CPU入口为tools/model_v3/run_regression.py，执行模板/全部原始日志在PROJECT/runs/model_v3_20261025；SHA与job/batch/extern实际终态分别保留，父FAILED不能因某个组件PASS改写。compute节点缺git，code SHA由登录节点实际Git采集并与文件SHA共同绑定；默认仓库检查是标准库静态元数据，可在登录节点运行，不导入模型。

稳定密钥PTY优先复用，子SSH必须-n；复杂Python或包含管道/正则的命令写固定路径脚本后调用，不用嵌套ssh -c拼接。Windows读取/编辑UTF-8须显式指定编码。Git worktree的.git文件含Linux绝对路径，Windows原生Git不能据此解析，子树提交/合并走SSH；不要因此重克隆或改.git指针。模型线只读D1/D2等数据线正式交付，不修改其目录；尚未交付时依新指南开展S/合成开发，真实接口/三GPU/过拟合/评估门槛保留。

## 2026-10-13 S′ 与 S 收敛任务的实际连接和资源方法

当前独立输出根为 runs/sprime_s_convergence_20261013，用户指南原字节在 configs/user_guide.md。默认账户和项目不变；CPU 避开14–19及 WP5 当前12/13，已实际用2/8/9/10/11，GPU限20/21/22。Root scripts/submit.py 与 submit_after.py 留存每次全部用户声明内存、逐节点sinfo/scontrol、实际WorkDir和SHA，至少16核真实并行；afterany 仅绑定本轮已登记且核过UID和节点的前序任务。

本次标准net use实际错误67，直接SSHFS初始化SFTP时reset。已受信核验compute-0-8现有三种主机key和同一项目AGENTS.md物理inode/bytes/UID；本机nativeSSH端口22259转发到10.1.1.242:22，本机127.0.0.1:23259适配器把SSHFS原始SFTP流转至nativeSSH的受信compute8子连接，X仍是相同/share/home/zixiao/descriptor_analysis的live view。Windows临时helper为C:/Users/mint/AppData/Local/Temp/sprime_sftp_bridge.py（24h有界），不得把本次连接修复推广为关闭主机验证或编辑OneDrive副本。

compute21旧SSH key变化已在自有Slurm4515020由节点/etc/ssh/ssh_host_ed25519_key.pub核对，ED25519指纹SHA256:cB2kIJBHOR48KHedUYjICdLC+QzbSmR6A5kGyzE+jN0。5090正确逻辑解释器仍为docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python，cu128；不要从目录名chemprop_5090猜测其bin/python存在。本轮4515027因该猜测在任何CUDA计算前FAILED127:0/0s，真实历史保留；4515029已以原逻辑venv入口实际通过CUDA SDP前向/反向，只证明基础kernel，不证明模型路径或完整容量。真实报告在reports/cuda_probe_4515029.json。

当前各节点占用与GPU空闲只作点时事实。原LMDB/WP5人口只读，不创建新LMDB，不修改其他用户作业。RMSD科学定义及各版本生成/再验证源在本轮scripts/，不要将源代码版本、原型成功或Slurm退出0升级为全量数据或B三组训练完成。
## 2026-10-12 当前 WP5 phase14 已正常产出（skill v1.0.60）

以 `SKILL.md` 顶部与 `runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v4.md` 为当前事实，下方旧“等待批准／尚未提交／旧watch”均保留历史。实际phase14主4514369–4514440、收尾4514441–4514446全78 WorkDir为PROJECT，已保存首次744claims／192新完整Mol／1895records科学产出；不要重复查询该证明，也不要把退出0等同科学完成。

当前observer6/watch7（PID3461479）按实际5阶段385唯一正式IDs累计成本、同队列人口一次。下一次对话级批量检查间隔3600秒；内部持久checkpoint、截止保护和publisher/monitor频率保持。六收尾后仍有可处理剩余时，依最新持续指示和真实闭合证据自主续算，不重复相同权限；原6guide-stop、一次科学retry预算、最终200/2400及原数据/manifest只读不变。

提交helper的subprocess cwd必须为 `/share/home/zixiao/descriptor_analysis`；实际sbatch WorkDir须读回匹配。旧R13全78 COMPLETED0但claims0/SCI0是初始化cwd故障，不能写成成功计算。PENDING以ReqNodeList及声明资源判定，NodeList未分配不等于错节点。此次只同步说明，不启动/停止monitor、不提交/写STOP、不运行测试或重查数据。

## 2026-10-12 当前 R12 恢复状态（尚未新增正式阶段）

参阅 `runs/phase1_wp5_20261011/reports/startup_replacement_root_continuation_v2.md`。授权的69+4补交已实施后再现锁故障；调度/暖启动核验不能写成生产通过。当前candidate_v4/锁fixture4514256 PASS/fullshape4514257–4514263在测，冻结之前必须以真实完整报告为准。

当前自有小时watch PID3439043/start_ticks8054882766/source `wp5_recovery_hourly_watch_v4.py`；旧3429748仅在新watch实际identity核验后终止。Guide条件2/3/5/6才可写STOP，无新增普通FAILED暂停。恢复审查4514255只有只读queue锁冲突，不等于SCI损坏；仍需新有界读工具重审。正式新阶段或原六条件之外的科学checkpoint需未来具体用户指示，不能复用已用授权。
> 当前资源与探测规则（2026-10-09，HPC skill v1.0.44）：每个 CPU/GPU 计算任务至少分配 16 个 Slurm CPU 核，并通过 worker、线程或合法输入分片实际利用并行；现场资源允许时尽可能提高并发，旧 max2/max4 只作历史记录。CPU 用 CPU 节点，GPU 用 GPU 节点。具体约束见 [SKILL.md 的当前规则](../SKILL.md)。
>
> 预计或实际运行至少半小时的任务，对话级状态探测每 600 秒一次，批量查相关作业及小型进度产物；无变化时不生成重复报告或重做已完成检查。作业内原资源保护和自动告警频率保持，目标暂停与 Slurm 作业暂停分别核实。

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
# 连接、核验与提交参考

## 当前执行纠正（Stage57，2026-10-02，技能v1.0.23；优先于历史）

none4512033在科学初始化前因输出位于包根而FAILED3s；使用包外新自有目录。none4512034实际FAILED17s，W&B先创建debug-internal链接、目标文件尚未创建，父strict resolve和finally重复崩溃；partial0r12zmf1保留，不升级失败或为补日志重放科学。新统一计量器只允许四种精确W&B布局的内部暂缺目标，逐已存在祖先通过dirfd/O_NOFOLLOW+UID/type校验；目录/link文本及实际regular inode计入。普通文件在原子rename中消失只对ENOENT最多三次重计量，安全错误仍拒绝。新父finally独立捕获元数据失败以保留报告。

CPU4512036实际COMPLETED0:0/2s：12个标准库文件系统方法通过0.016s，真实W&B offline ew21psli初始化/关闭期间85次计量无异常，四链接实测（NONE core指向actual_cv/cache/wandb/logs），计量旧学习输出130522468B、旧none6807B。counter模块[owned_output_bytes.py](../../../phase1/evidence/stage57_owned_output_bytes_v1/owned_output_bytes.py)与[实际验收](../../../phase1/evidence/stage57_owned_output_bytes_v1/cpu_4512036/summary.json)绑定；不能将live采样视为原子快照、配额预约或GPU隔离。parent根/actual_cv根/actual_child根使用同API。

学习4512029原FAILED415s保留：已保存33792base/83optimizer；CPU4512032独立safe checkpoint+85条按源类型恢复SHA精确匹配，CPU4512035实际新decoder9checks/85条全部精确通过。后续仅continuation，不重放first；原/新共同7200sec与2GiB上限，等待metadata不计训练工作时间；W&B int/float源类型修复不使用数值容差或放宽未知字段。当前技能规则不变更在线扰动配方、正式科学范围或共享GPU风险授权。
## 当前执行纠正（Stage57，2026-10-02，技能v1.0.22）

4512026真实学习pilot为FAILED1:0/63s：资源监督器拒绝W&B正常内部链接，finally同一统计函数再次失败，未生成parent summary/child exit report。原partial offline run `8trzmqr1`保留，优化更新数没有闭合证据（UNPROVEN），不把此故障归为GPU OOM或模型失败。

只修改外部supervisor的output_bytes得到v3（a18557dd…），资源循环/main/finally和e272训练CLI保持原字节。核验actual_child/{first,continuation}/wandb下latest-run、debug.log、debug-internal.log，以及offline-run.../logs/debug-core.log指向同phase的cache/wandb/logs：目标必须同UID、同输出树内的普通目录/文件且不经过其它symlink，计数不沿目录链接递归、regular inode一次，另计目录及link文本。外部/未知/循环/跨phase链接和外部hardlink仍拒绝，不删除原W&B数据。

CPU4512027在运行测试前因batch无git而FAILED；4512028五项stdlib文件系统checks实际0/0.009s通过，随后sacct连接compute localhost:6819被拒，原父FAILED保留。Root在sonmi以actual195源码raw pins与实际7列sacct完成轻量闭合，未重放测试或科学计算。证据：[真实闭合](../../../phase1/evidence/stage57_node20_learning_supervisor_v3/root_close_v1/summary.json)和failed_4512026_closure.json。Git可选诊断不可阻断已绑定源码的模型计算；batch不得假定login PATH，记账必要时在login查询，立即记录各层退出码。

用户明确命名仍为huagong_hpc_requirement（underscore），优先于通用skill-creator的hyphen-case默认。保持已授权共享GPU风险、16CPU64GiB/完整UUID一本项目任务、Slurm/W&B/实际quota与科学矩阵范围。
## 当前执行事实（Stage53/54，2026-10-02）

技能v1.0.21仅补非交互 `srun` 的 stdin 隔离和Python逻辑venv入口规则，保留用户授权、underscore名称、16CPU/64GiB、共享GPU风险、W&B、预算与科学范围约束。以下是实际关闭的点时范围，不替代下次GPU现场检查或新完整训练协议。

- Stage53 CPU4512000实际77项真实CPU测试加13项标准库metadata检查、CLI --help退出0，COMPLETED0:0；当时隔离候选为commit `33eea874e8dc48a9bb5422bce8ef7837bb402b22`、source `9fda303f9a0444e5015338d651ca4c551ce6e232687d8bbbe06b9d92ae909f4d`，192个文件。证据为 `docs/phase1/evidence/stage53_seed_runtime/actual_source_receipt_v1.json`。这是历史点时来源，不预判后续CLI入口修正或新source已通过。
- Stage53 launcher V4的31项标准库guard由CPU4512001实际通过，source前后保持上述33ee/9fda；日志为 `docs/phase1/evidence/stage53_seed_runtime/cpu_4512001.log`。模拟Slurm/NVML/model观察不等于真实GPU PASS；实际自有子进程清理另按测试范围报告。
- node22新诊断helper的16项CPU测试由4512002实际通过，COMPLETED0:0，算法测试0.040s；范围为六项标准库metadata、六项CPU梯度手算和四项真实normalizer投影检查，source33ee/9fda前后不变。证据为 `docs/phase1/evidence/stage51_119_bucket_profile/node22_balance_diagnostics_v1/test_4512002` 及 `cpu_4512002.log`，不是node22 GPU兼容或119/full-fit梯度诊断PASS。
- FullQA4511985的166个计划chunk正在finalizing，尚无本条核验的完整closed summary、新全量fit/paired init及正式端点；不能把chunk目录数、部分成功或候选统计当作全库完成。正式训练optimizer仍0。此处不猜测新入口修正或未关闭作业结果。

## 历史执行事实（Stage49，2026-10-02）

当时技能主体为v1.0.19，已加入用户正式训练前的任务损失平衡要求。现有连续目标标准化保留，新控制器使用train-only前8次有效观察校准后冻结loss尺度、[0.25,4]有界任务/组乘子与每32 optimizer updates的共享梯度EMA探测，完整状态随checkpoint恢复。CPU4511972实际102 passed，修正浮点饱和边界后的CPU4511973实际58 passed，均COMPLETED0:0。

GPU4511974实际8更新/COMPLETED0:0。扩展4511975训练子进程实际完成40更新/160唯一train records/控制器恢复/40条W&B离线记录独立解码；外围旧8步guard导致该Slurm作业FAILED1:0。原失败和完成子进程证据都保留，不重复科学训练。CPU4511977已COMPLETED0:0独立验证上述闭合产物，见docs/phase1/evidence/stage49_balanced_loss/{actual_source_receipt_v2.json,DESIGN_AND_ACTUAL_CHECKS.md,closure_verification_4511977/verification.json}。同一模型状态u39 full-backbone D组norm share从固定91.14%到仅归一化78.42%，再到动态57.28%；这是小样本诊断，不保证长期全梯度恒等或消除方向冲突，不是原版GradNorm复现。

Production仍为下方实际Stage47资源接口源码；新的shared checkpoint/dynamic loss/compact loader在隔离候选目录验收。完整15,879,477结构的QA/whole-identity分组/target-opaque embargo/新train-only流式统计和119类模型大batch profile、成对init与segment resume尚待各自新证据；正式optimizer仍0，不提交旧58k配置。最新全量入口验收（Stage50，2026-10-02）：新的完整数据入口已实际使用balanced.total反传，固定validation指标不更新控制器，完整controller/AdamW/RNG/committed sampler恢复及分段W&B lineage已接入。CPU4511988 CLI --help exit0，30新案例+8旧normalization共38 passed/26.58s/COMPLETED0:0；自有spawn预取/未消费恢复、zero-label不优化、状态拒绝原子性及best/complete语义修正均实际验收。compact loader CPU4511986实际46 passed/25.12s/COMPLETED0:0。隔离候选测试字节已提交，实际source见[Stage50 receipt](evidence/stage50_full_corpus_training/actual_source_receipt_v4.json)，production未改；[实际验收与限制](evidence/stage50_full_corpus_training/ACTUAL_CHECKS.md)。FullQA4511981的直方图整数键seal失败/0accepted保留，修正v2 CPU4511984实际9 passed，fresh full4511985仍RUNNING：首13accepted覆盖1,214,673原始refs，不等同完整全库完成或新fit冻结。raw PM7能量按新train均值/std训练，composition baseline application=none，QA充分统计未solve。完整QA/新fit、119类较小模型真实大batch/bucket profile、新配对init/冻结协议与真实GPU段恢复仍待各自证据；正式optimizer0。HPC技能v1.0.19已同步。

## 历史执行事实（Stage48，2026-10-02）

当时技能主体为v1.0.16，production commit为`a2b6427ce3dad283ed23d37c70410dc555edc4c9`、source为`1a097b906bf0047f9c221085036e52ceabd25e9a005514a4a48abdeb9ac2547c`；实际部署见`docs/phase1/evidence/stage47_host_resources/root_commit_bridge_deployment_guard/deployment_result.json`。Stage46 CPU4511959为269 passed/COMPLETED0:0/16s，Stage47 CPU4511961为299 passed/COMPLETED0:0/16s。16CPU/Slurm64G（64GiB host RAM）请求已验证部署；15s驱动查询、实际GPU UUID协作单本项目任务及按该UUID总显存减安全余量的wrapper已通过聚焦测试。这些事实不证明硬件独占或他人无法占用GPU。

用户已明确“是，接受风险并启动”，共享GPU授权继续有效；不再为缺少GRES或设备隔离重复要求许可。唯一正式提交4511960因旧2s NVML启动查询超时FAILED1:0/2s，optimizer0/W&B0/无checkpoint，尚无正式训练端点。当前用户又要求缩小模型、尽可能使用完整报告语料及增大batch减少总批次，因此旧58k/hidden512×6层/batch2/49993步正式方案停止新的提交；原科学2d、执行v1/v2及既有trial保留点时，资源v3只静态草稿未执行。新模型、batch、有效train规模、epochs/updates、缓存和成本预算须依据新pilot重新绑定，不能冒称已冻结。

实际CPU库存4511962已COMPLETED0:0/1s（compute-0-20，16CPU/64GiB请求）：11个clean LMDB分片`__len__`声明合计15,879,477条结构，4个扰动分片另列，不计入clean总数。helper0.616s/RSS18.1MiB，只读stat/info/整数头，record与target解码为0；不证明unique parent、1.8M分子式、标签覆盖或train/validation/test划分。证据为`docs/phase1/evidence/stage48_full_dataset_inventory/run_4511962/{summary.json,shard_headers.jsonl}`；来源审阅为`docs/phase1/evidence/stage48_full_corpus/FULL_CORPUS_SOURCE_REVIEW.md`。完整标签/身份/新normalization/init/checkpoint resume仍需新范围证据。

下方旧阶段的现场占用、旧source及“GPU隔离未解决”文字保留历史点时范围；使用当前事实和SKILL.md中的已授权共享GPU例外，不把历史状态当作新的许可或冻结条件。

这里提供命令示例和必要的现场事实；约束以 `../SKILL.md` 和用户的新指令为准。执行前确认当前 shell：Windows 命令用于 PowerShell，Linux 命令在已连接的目标服务器执行。示例中的大写占位符必须替换为核实后的值，不能原样提交。

## Windows 端与登录节点

```powershell
Test-Path -LiteralPath 'X:\AGENTS.md'
ssh -n -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes descriptor-analysis-remote 'cd /share/home/zixiao/descriptor_analysis && pwd && id -un && hostname'
$login_check_ssh_rc = $LASTEXITCODE
```

需要交互式操作时：

```powershell
ssh -t -o StrictHostKeyChecking=yes descriptor-analysis-remote
```

在服务器登录节点交互登录一个允许的测试节点，然后核对身份与目录（此处保留 stdin，不加 `-n`）：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes compute-0-20
# 也可选择 compute-0-21，身份核验要求相同。
hostname
id -un
cd /share/home/zixiao/descriptor_analysis
pwd
```

非交互式单次节点检查可从 Windows 执行：

```powershell
ssh -n -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes descriptor-analysis-remote 'ssh -n -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes compute-0-20 hostname'
$node_check_ssh_rc = $LASTEXITCODE
```

在已有交互登录会话中连续发送命令时，非交互子 SSH 必须断开父 stdin。`-n` 等同于从 `/dev/null` 读取；正常交互登录或确需 stdin 的 `ssh HOST bash -s` 不加它，后者须单独提供脚本输入，不能共享待输入的父会话命令。以下轻量示例在计算节点记录 `hostname` 的退出码，在登录节点立即捕获子 SSH 的退出码；日志及退出码路径须先选为本次新证据，不能覆盖旧文件：

```bash
ssh -n -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes compute-0-20 'hostname; node_check_rc=$?; printf "remote_exitcode=%s\n" "$node_check_rc"; exit "$node_check_rc"' > /absolute/path/to/new_node_check.log 2>&1
node_check_ssh_rc=$?
printf '%s\n' "$node_check_ssh_rc" > /absolute/path/to/new_node_check.ssh.exitcode
```

每一层都在对应命令返回后立即保存 `$?`（PowerShell 保存 `$LASTEXITCODE`）；后续 `printf`、`cat`、Git 或队列查询的退出码不能代替被核验命令的退出码。SSH 返回码也应与日志中的远端命令码区分。若退出码文件或日志缺失，标为未验证，再用已关闭产物及实际进程／调度终态核实；不为补证据重跑耗时科学任务。

检查服务器中已选的 Python/conda 环境后再运行项目脚本。可在计算节点对一个准备好的小测试使用 `timeout 180s python path/to/prepared_smoke_test.py`；先确认该测试的数据量、设备、输出与步数已经受限，不能把整个正式脚本包装进 timeout 就当作短程测试。

学校服务器从 Windows 登录的地址为 `ssh -p 22 202264640132@202.38.252.202`，仍须启用主机验证并使用安全的现有认证。这里未验证其密钥登录、远端项目路径或调度隔离，不把示例当成可立即提交的证明。

## Slurm 的只读核验

在目标集群的登录节点执行：

```bash
sbatch --version
squeue -u "$USER"
sinfo
scontrol show partition PARTITION
scontrol show node NODE
scontrol show config
```

精确 CPU 节点审核使用逐节点输出，再与 `scontrol` 合并核对；默认 `sinfo` 的 `compute-[17,19]` 压缩行不是没有 IDLE 节点的证据（HPC skill v1.0.42，2026-10-08）：

```bash
sinfo --Node --noheader --partition=cpu --nodes=compute-0-19 --format='%P|%N|%t|%C|%m'
scontrol show node compute-0-19 --oneliner
```

该节点名只作实际接口示例，每次提交仍核对现场状态、空闲 CPU 和声明内存；不把点时结果写成永久占用状态。4512488 首次 preflight 在 READY/sbatch 前退出，随后只加 `--Node` 取得精确行并完成真实提交，见 `docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/root_C1_current4_inventory_source_review_20261008_v2.json`。
关注 partition/account/QoS、`Gres`、`CfgTRES`、`AllocTRES`、`OverSubscribe`、`PreemptMode`、`PreemptType`、`TaskPlugin`，以及可读的设备隔离/SSH 准入配置。`proctrack/cgroup` 仅说明进程追踪，不能单独证明 GPU 设备隔离。配置不可读时保留“不确定”的结论，以站点可信文档或管理员确认补足；不得修改集群配置。

实际 GPU 与进程检查在允许的计算节点或作业分配内执行：

```bash
nvidia-smi
nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu --format=csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv
```

需要归属核验时，以具体 PID 查询 `ps -o user,pid,ppid,args -p PID`；在对外报告中只保留必要的资源/用户归属信息，避免传播他人完整命令行。看不到他人进程不等于隔离已生效。

## 正式提交与追踪

先确认资源保护、训练跟踪和存储预算满足主技能，再提交已检查的脚本：

```bash
sbatch --parsable path/to/reviewed_job.sbatch
squeue -j JOB_ID
scontrol show job JOB_ID
sacct -j JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,AllocTRES,MaxRSS
```

记录返回的 job ID 和可能的集群后缀；对照实际配置检查分配。GPU 指令使用目标 Slurm 版本和站点支持的语法，例如 `#SBATCH --gres=gpu:1`；不要在没有 GPU GRES 的集群照搬。CPU 内存、GPU 显存与整节点独占分别核验。取消当前任务的自有作业时，先用 `scontrol show job JOB_ID` 确认 `UserId` 和归属，再在既有授权范围内对该精确 ID 执行 `scancel JOB_ID`。

交互 shell 能找到某命令，不代表 batch 节点也能找到。已核实的 Phase1 Python 是 `/share/home/zixiao/.conda/envs/chemprop/bin/python`；仅在该环境确实适用的任务中使用。必要依赖检查失败应明确退出；可选 Git 版本展示可按 `command -v git` 判断，缺失时写明并记录实际源码文件 SHA，不把版本展示失败当成科学审计失败。4511895已在CPU batch核实：现有源码追踪可从 `.git/HEAD` 和引用读取真实commit，并核对源码字节指纹；无Git时dirty状态为未知。后备路径仍须与实际冻结commit/源码hash一致，不接受任意环境变量代替绑定。

### 逻辑venv入口与binary诊断分开

启动 argv 和 `runtime_environment.python_executable` 使用同一个已核实的逻辑绝对入口，不先解引用symlink。在该入口启动的进程内可用：

```python
from pathlib import Path
import sys
python_executable = str(Path(sys.executable).absolute())
resolved_binary_diagnostic = str(Path(sys.executable).resolve())
```

前者用于环境绑定与子进程 argv；后者只单列诊断。不能将第二个值覆写第一个值，也不使用 `readlink -f` 结果替换执行器。实际5090逻辑入口为 `/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python`；原chemprop入口仍仅用于其对应的4090/cu126环境，不能因两个入口指向同一binary就互换。

实际标准库观察 `docs/phase1/evidence/stage53_seed_runtime/actual_interpreter_path_metadata_v1/actual_observation.json` 中，logical入口的absolute路径仍为venv，`sys.prefix`为该venv，`importlib.metadata`显示Torch2.10.0+cu128；其resolved binary为 `/share/home/zixiao/.conda/envs/chemprop/bin/python3.11`，从目标入口启动则prefix/base_prefix均为chemprop、Torch2.10.0+cu126。两个调用均未importTorch、未初始化CUDA、未运行模型：这是解释器入口/包选择证据，不是GPU kernel或node22模型兼容证明。canonical CLI的必要修正应另有实际source和测试记录；不把本条观察冒充修正已通过。

CPU准备作业的现场内存检查按站点实际字段解释。此集群22.05.7的4511898作业 `TRES=cpu=2,node=1,billing=2` 不含mem，但同一作业有 `MinMemoryNode=4G`。核对当前作业owner、RUNNING状态、node/CPU后，可将明确有限的 `MinMemoryNode`，或 `MinMemoryCPU` 与对应CPU数，作为调度器声明的请求预算；另记录证据来源，并以内部RSS与墙钟限制控制准备过程。内存请求、TRES记账和生效的OS/cgroup强制隔离是不同证据，不能相互冒充，也不能用CPU请求放行正式GPU训练。字段定义见 [Slurm 22.05.7官方手册](https://raw.githubusercontent.com/SchedMD/slurm/slurm-22-05-7-1/doc/man/man1/scontrol.1)；现场记录见 `docs/phase1/evidence/controls_fixture_4511898.scontrol`。

正在写入的共享文件可能在登录节点或SSHFS上显示旧长度。需要时，先确认 JOB_ID 属于本次任务且仍在运行，按站点许可在它自己的分配内做轻量、有时限的检查：

```bash
timeout 30s srun --input=none --jobid=JOB_ID --overlap --ntasks=1 --cpus-per-task=1 /usr/bin/stat -c '%s %y %n' /absolute/path/to/this_job_ledger </dev/null
owned_step_rc=$?
printf '%s\n' "$owned_step_rc" > /absolute/path/to/new_step.exitcode
```

该命令只在现有自有 allocation 内核验文件；不创建新正式工作，不检查或终止他人进程。`--overlap`须为站点和安装版本允许。若只读步骤无法准入，保留不确定性，等待日志/最终summary；不把缓存旧值解释为任务已卡死。`sstat`的空白或异常 CPU/RSS值不可作为有效资源统计。

### 非交互srun不得转发父PTY输入

上述不读输入的检查同时使用 `--input=none` 和调用方的 `</dev/null`。Python启动器使用参数列表和 `stdin=subprocess.DEVNULL`，例如：

```python
import subprocess
result = subprocess.run(
    ["srun", "--input=none", "--jobid=" + str(owned_job_id), "--overlap",
     "--ntasks=1", "--cpus-per-task=1", "/usr/bin/stat", "-c", "%s", owned_ledger_path],
    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, timeout=30,
)
owned_step_rc = result.returncode
```

这只适用于本步骤不需要stdin的非交互调用；交互 `srun` 或确需传入脚本的数据应单独提供输入，不与父PTY待执行命令共用。每层命令返回后立即保存该层真实returncode；超时或缺失returncode按实际状态报告，不能补写0或用随后日志/Git/squeue的退出码代替。

Stage48证据 `docs/phase1/evidence/stage48_full_corpus_qa/root_runtime_observation_v1` 有关闭的observation，但未记录退出码；其缺失保持UNRECORDED。新 `root_runtime_observation_v2/actual_execution.json` 记录实际 `srun --input=none` 与 `subprocess.DEVNULL`、actual_exitcode0，且两次范围均仅自有allocation内的进程/stat元数据，没有LMDB/SQL行或labels读取。v2是新的轻量观察，不是重跑QA科学任务，也不反向补齐v1退出码。

项目中 `modern_ML_representation/support_scripts/MFM_descriptor/pretrain/submit/` 已有 `g01n02_pretrain_ddp_formal.sbatch` 等示例，包含 `gpuA800` partition 和 GPU GRES 请求。它们不匹配默认 sonmi 集群当前 partition 清单；需在相应目标集群重新核实，不能在默认服务器原样提交。

## 实验管理与存储

W&B 使用已配置的账号/project/entity 与安全认证。若选择 offline 模式，应有实际 run 初始化、持久化指标和可检查的本地结果；例如 `WANDB_MODE=offline` 仅是模式设置，本身不能证明训练代码已接入管理工具。之后使用 `wandb sync` 同步指定的已完成 run；同步前确认账号与目的项目正确，并保留原始离线记录直到同步或可靠归档核验完成。

W&B 的 `run.log(metrics, step=history_step)` 默认不提交当前逻辑记录；应在该记录完成时用 `commit=True`，或按已声明的累积流程显式提交。提供 step 时的默认值见 [W&B Run.log 官方文档](https://docs.wandb.ai/ref/python/experiments/run/)。科学 optimizer-update cursor 和 W&B history cursor 分开管理，提交后验证实际游标；关闭后读回少量持久指标，确认更新数及曝光量对应。Phase 1 已有 `tools/export_wandb_history.py` 可解码指定的闭合 offline run 文件，不需要为检查上传原数据。

存储检查在实际写入的文件系统执行：

```bash
quota -s
df -h /share/home/zixiao/descriptor_analysis
df -i /share/home/zixiao/descriptor_analysis
du -sh /absolute/path/to/this_run
```

`quota` 不存在或结果不可用时，查站点提供的 quota 工具或已确认的账户额度；不能用 `df` 代替。检查只扫描相关输出目录，避免每次递归统计全部数据。清理没有通用 `rm -rf` 模板：逐项核验主技能要求的路径、归属、活动依赖和保留价值后实施。

## 已核验事实与待解决项

核验日期：**2026-10-01（Asia/Shanghai）**。以下是当次只读检查结果，不能代替下次提交前的现场核验。

- `X:\` 的 SSHFS 挂载目标是默认服务器项目；`descriptor-analysis-remote` 可用配置的 SSH 密钥登录，用户 `zixiao`，登录节点 `sonmi`。
- 默认服务器有 `sbatch`、`squeue`、`sinfo`、`scontrol`，Slurm 版本为 `22.05.7`；可见 partition 为 `all`、`gpu`、`cpu`。
- `scontrol show node compute-0-20` 与 `compute-0-21` 均返回 `Gres=(null)`，`CfgTRES` 未包含 GPU；`scontrol show config` 返回 `GresTypes=(null)`、`TaskPlugin=task/affinity`、`ProctrackType=proctrack/cgroup`。**尚未证明正式 GPU 训练所需的显卡调度与设备隔离。**
- 当次全局 `PreemptMode=OFF`、`PreemptType=preempt/none`；`all` 与 `gpu` partition 的 `OverSubscribe=NO`。这些值不能补足缺失的 GPU 分配与 SSH 隔离保障。
- `compute-0-20` 的 SSH 主机名检查成功。`compute-0-21` 连接曾出现主机密钥变更警告；尚未通过可信渠道核对新密钥。使用该节点前必须解决身份核验，不沿用宽松 SSH 配置。
- 同日保持交互 SSH 会话批量发送命令时，非交互子 SSH 曾读取父 PTY 的后续输入；`resources_before_memory_capacity.exitcode` 实际未生成，虽 stdout 完整，也不能据此断言追加的退出码／Git／队列命令已执行。后续非交互采集使用 `-n` 并在同层及时记录退出码，旧科学任务不为补日志重跑。
- Phase 1 当天清理已结束的自有两步测试checkpoint后最新核验 `quota -s`：账户使用3950G、硬上限4096G，余量约146G；七个明确文件的hash/归属/删除记录在`docs/phase1/evidence/correctness_cleanup_record.json`，未删除offline tracker、原数据或历史唯一结果。整盘剩余约5.6T不属于账户全部可用空间；此余量是现场值，写大文件前必须重查。
- Phase 1 同次节点检查可见 `compute-0-20` 两张RTX4090，每张49140 MiB，当时显存各占1 MiB；这不是显卡预约或隔离证明。
- 已在 `compute-0-20` 上执行有界 LMDB 审计、CPU测试、短GPU诊断及训练来源开发CV，全部限制数据/步数/时间、实际W&B offline记录；不是正式GPU矩阵。CPU完整身份审计通过 `sbatch` 提交作业4511885，运行于compute-0-13，最终FAILED/2:0是科学审计发现重叠及解析缺陷，不是调度失败。`sbatch --test-only` 曾预测无法分配，实际提交与`squeue`/`sacct`证据优先；不据预测虚称已提交或不可提交。
- CYP/AZ结构审计CPU作业4511886在compute-0-13的batch环境找不到Git，于读数据前FAILED/127:0；修订可选诊断后4511887实际完整执行，FAILED/2:0对应11条CYP结构身份冲突。源hash/日志/账本见`docs/phase1/evidence/full_som_structures_4511887*`；不能混淆环境退出和科学检查失败。
- QM CPU作业4511889在compute-0-13完整核验141050条结构及对应十fold成员，FAILED/2:0对应746条QM9源结构身份缺陷，程序wall471.62s；运行中登录/SSHFS缓存曾显示账本0字节，作业内stat已143MB。原始summary与sacct见`docs/phase1/evidence/full_qm_sources_4511889*`。完整覆盖与科学检查通过分别报告，不因完整覆盖就宣告全部有效。
- 学校服务器现有公钥登录返回认证失败；未获得资源保护与quota证据。未取消他人作业，未改写原LMDB、未清理历史结果；正式GPU矩阵尚未启动。
- 当前 PhyChem_MFM 独立重构位于 `/share/home/zixiao/PhyChem_MFM_ICLR2027`；Phase 1 权威指引仍在默认项目 `PhyChem_MFM_Phase1_Instructions.md`。旧 MFM_descriptor 为历史参考，工作时读取实际源码目录的 `AGENTS.md`。
- 阶段31在默认 compute-0-20 禁用CUDA的合成功能验证中，两个 fresh W&B offline run（冻结读出 i1uq78qq、微调 c8udr365）各完成4次更新，关闭后的实际 run 文件各读回4条 history，科学更新/样本/原子/有效标签曝光逐条吻合。实际退出0，整个输出目录49990B；记录仍未同步，不能删除。证据为 `docs/phase1/evidence/downstream_tracking_stage31/probe_summary.json`；这是持久写入接口的验证，不是正式训练、真实数据指标、GPU保护或后端恢复证明。

## 官方资料

命令细节以目标服务器安装版本及站点规则为准；新版资料中的选项可能不适用于当前 `22.05.7`。

- [Slurm sbatch](https://slurm.schedmd.com/sbatch.html)：批处理提交、资源与独占参数。
- [Slurm squeue](https://slurm.schedmd.com/squeue.html)：作业队列查询。
- [Slurm GRES](https://slurm.schedmd.com/gres.html)：GPU 资源登记、分配与设备映射。
- [Slurm cgroup.conf](https://slurm.schedmd.com/cgroup.conf.html)：设备隔离及 SSH 作业归属控制。
- [Slurm Preemption](https://slurm.schedmd.com/preempt.html)：调度抢占配置。
- [W&B experiment tracking](https://docs.wandb.ai/models/track)：实验与训练指标管理。
- [W&B distributed training](https://docs.wandb.ai/models/track/advanced/distributed-training)：分布式日志组织。

## 2026-10-02 指定节点复核

用户指定默认 sonmi 集群 compute-0-20、21、22为本轮正式任务目标，不再依赖学校付费服务器。实际登录节点只读结果在 `docs/phase1/evidence/stage42_gpu_inventory.txt`：三节点 Gres均null、CfgTRES均未列GPU，全局GresTypes null、TaskPlugin task/affinity；可读cgroup.conf仅声明ConstrainCores，没有设备约束；登录节点sshd PAM未显示pam_slurm_adopt。这些结果尚不提供GPU独占依据。Preempt OFF/none、partition OverSubscribe NO也不能补足该依据。节点实际硬件与配置另通过本次Slurm只读作业4511915核验；不修改管理员配置，不绕过compute-0-21的SSH主机密钥核验。
## 2026-10-02 实际试跑与兼容环境

- compute-0-20的4090使用原chemprop/Torch2.10.0+cu126。Slurm4511920完成256更新，4511926完成1024更新；仅改变后者预先声明的step horizon。4511925、4511930真实关闭后解码W&B，分别257/1025条history，与所有逐步指标/有效label计数/完整验证一致。allocator expandable_segments成功观察；仍是有界diagnostic，不代替正式训练成熟度或显卡预约。
- compute-0-21的5090在4511924真实FP32 zeros kernel失败（no kernel image），不能把4090成功推广给5090。独立venv在4511929通过CPU安装与依赖核验，原148项base METADATA及科学源码保持。路径`/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python`，Torch2.10.0+cu128/CUDA12.8。4511933在21的zeros/matmul/pointwise/SDP四项实际运算全部通过，COMPLETED0:0/7s。随后4511948在21完成完整模型的一次SDP更新、两条已关闭W&B持久记录、模型/optimizer/scheduler严格检查点恢复，COMPLETED0:0/15s；实际summary见`docs/phase1/evidence/stage43_5090_joint_4511948/summary.json`，raw SHA256 `a159832b7447e4ae22255508545557302ddacf854911bcdcbda2f6262e1b52e6`。该有界兼容性结果不证明GPU独占；22节点的实际模型路径仍待验证。
- 环境安装峰目录约6.75GB、关闭保留约4.29GB（十进制），包含TMPDIR/下载/缓存；预算12GiB。新环境从原chemprop继承可复用非Torch包，不能删除或移动原环境；依赖和新venv共同保留至正式选择稳定。
- compute节点的sacct可能因AccountingStorageHost=localhost而连接本机6819失败。闭合job状态从实际sonmi导出`JobIDRaw,User,NodeList,AllocCPUS,State,ExitCode`六列，立即捕获退出码；在计算作业使用这份原始文本及SHA绑定，不修改管理员配置，也不为补accounting重跑模型。
- 本机review checkout可能为CRLF，远端源码为LF。脚本/工具引用的raw SHA取实际服务器字节；只在实际远端校验一致时才解释为换行差异，不能把Windows副本raw SHA冒充服务器SHA。
- 2026-10-02用户提议以gpu_num申请独用。当前/usr/bin/sbatch帮助没有该参数；当次`sbatch --test-only --partition=all --nodelist=compute-0-20 --gres=gpu:1 ...`拒绝Invalid generic resource specification（exit1，没有提交任务）。这次结果仅说明当前已测试接口未生效，继续查站点实际gpu_num工具/旧成功命令；不据尚未核验的名称声明GPU已分配。证据`docs/phase1/evidence/stage43_gpu_request_test.stderr`。

### 2026-10-02：已退出作业的队列查询与合成测试临时文件清理

4511954已由实际sacct闭合COMPLETED/0:0，但后续`squeue -h -j 4511954`返回Invalid job id specified/exit1；初次清理检查因此停止，尚未删除文件。改为成功读取本账户`squeue -h -u zixiao -o '%i'`并核对精确ID缺席，再结合留存sacct与pytest/deployment退出0，按已解析的固定路径清理`docs/phase1/evidence/stage44_trial_source_bridge/test_4511954/tmp`。实际删除3530个自有可重建合成fixture文件、490目录、43个内部symlink（未沿链接扩展），表观6241346B；不据此声称确切quota释放量。源码快照、所有闭合日志、真实试跑/数据/模型/W&B及receipt保留。唯一清理记录`docs/phase1/evidence/stage44_trial_source_bridge/synthetic_tmp_cleanup_4511954.json`；失败与成功检查各自日志/exit保留，未重跑测试或科学计算。

### 2026-10-02：冻结运行协议与分节点 GPU 申请

独立预训练运行协议由 CPU Slurm4511958实际封存，COMPLETED/0:0/8s；当前生产8f37a04，120个科学核心保持，222项focused测试由4511957通过。协议在 docs/phase1/evidence/stage45_pretraining_compilation/sealed_pretraining_execution_4511958。pretraining_only/PENDING仅延后实际下游执行哈希，完整科学规则不变，冻结文件不证明 GPU 保护。

最新对 compute-0-20、21、22分别执行单节点 `sbatch --test-only ... --gres=gpu:1`，全exit1/Invalid generic resource (gres) specification，没有提交任务。实际配置、node export、帮助和逐节点退出码在同目录 root_scheduler_review_guard。首轮三节点逗号 nodelist 配合 nodes=1 仅报节点数冲突，不能当成 GPU 检查。正式单节点申请须选择核实节点，允许集合仍由协议/LIVE校验约束。

- hash由实际文件或闭合JSON自动派生，检查64位十六进制，不从聊天/摘要手工转写；复杂参数保存JSON argv，使用subprocess参数列表，不拼接shell。4511956启动和首轮metadata检查正确拒绝了65位转写hash，失败保留，后续仅更正参数，没有重跑科学计算。
- compute20既有source_provenance实测：无Git程序、有真实.git目录、无PHYCHEM覆盖时，HEAD/ref回退得到当前commit/hash；git_dirty为null未知，与sonmi的clean检查分开。无需安装Git、伪造环境变量或改科学代码。root_source_provenance_observation_guard记录允许的30秒短程SSH元数据观察，不是GPU LIVE PASS。
- 4511957已完成并部署后，仅清理已核归属/路径的合成pytest TMPDIR：4108文件、535目录、53内部symlink不沿链接，表观6647368B。保留真实数据、试跑、模型、源码快照、日志、receipt和未同步W&B，不声称精确quota释放。


### 2026-10-02：用户明确接受共享 GPU 风险并启动

用户明确回复：是，接受风险并启动。按SKILL当前Phase1窄例外执行，不再把先前Invalid GRES或缺隔离作为该任务的重复许可障碍；保留原证据且不声称独占。新例外授权和启动证据位于docs/phase1/evidence/stage46_shared_gpu_execution与stage46_shared_gpu_launch；旧冻结v1与科学协议不追改。启动仍经Slurm、显式实际GPU UUID、W&B及预算/自有进程监控。

### 2026-10-02：扰动与恢复修正（skill v1.0.20）

getitem生成clean/geom/topo；seed+logical ordinal在重复读取时固定，不等于逐epochfresh扰动。局部generator不应消耗global CPU RNG，Stage53六项CPU检查4511991已实际验证，集成source见stage52_positive_strategy_v2/actual_source_receipt_v3.json。4511997为120 passed/14 failed；仅修正dict-only hash的Mapping包装后4511998实际44 passed/COMPLETED0:0。两次测试保留各自bytes/scope，不合称同image164或134通过。

GPU4511990完成57容量更新后TorchVersion safe-load拒绝FAILED；仅补6更新的4511994安全读取成功但非bitexact，原FAILED1:0保留。verify_resume_numeric_metadata_v3.py实际标准库进程exit0；stage51_119_bucket_profile/resume_numeric_closure_v3证明两controller自身seal有效、离散状态及输入/RNG精确一致，1198 tensor/231 scalar在预声明atol1e-6/rtol1e-5内，最大abs8.186e-7；numeric/semantic true、byteexact false，未定因或重播容量。

启动器共用stage46_shared_gpu_launch/.own_gpu_uuid_locks/<完整GPU-UUID>.lock，条件/seed单segment互斥，允许不同GPU并行。launch V2的18 stdlib guards由4511995实测通过；Slurm/NVML/model receipts为SIMULATED，仅自有子进程清理为实际，不等于正式训练或GPU独占。

### 2026-10-02：W&B缓存根与双重wandb路径（skill v1.0.24）

真实P成本4512040在compute-0-20/16CPU64GiB运行71s后FAILED1:0。行政父设置`WANDB_CACHE_DIR=actual_child/first/cache/wandb`；实际0.28.1创建的run/logs/debug-core.log链接指向`actual_child/first/cache/wandb/wandb/logs/core-debug-20261002_162311.log`，已测414counter合法布局guard拒绝。保留parent summary/partial9mcdojj3，parent只停止own UID1278/PGID/SID；缺child science summary/journal，不能声称optimizer0。问题是本次环境路径，没有OOM/foreign占用证据。窄修正只把缓存根改`actual_child/first/cache`，child33科学loop与counter不变；W&B实际日志于是采用已核`cache/wandb/logs`。NONE4512037成功布局的WANDB_CACHE_DIR也为actual_cv/cache；其九fixed20 TRAIN开发readout由实际Slurm219s/0:0及Root stage57_goal_actual_close_v1/root_close/summary.json闭合。此记录不把修正后的P测量声明为通过，须看新job实际状态/报告；不重放已闭合83/643次科学更新或升级4512040原失败。

## 2026-10-02：用户确认完整训练集三遍（skill v1.0.25）

用户在“如果没有什么额外的问题，请开始正式轮训练，最大训练量初步定为所有样本训练3batch”后明确确认这是3 epochs。当前TRAIN N=15,709,889，目标每trained condition 3N=47,129,667 base /141,389,001 views；24条件合1,131,112,008 base /3,393,336,024 views。旧一次曝光候选预算不是最新正式预算，源科学代码必须支持epoch切换与累计恢复。

Root实际创建`/share/home/zixiao/PhyChem_MFM_stage59_three_epoch`隔离worktree，初始HEAD09a02980/clean，旧AA/source与试跑数据保持；见`docs/phase1/evidence/stage59_source_worktree_preparation/summary.json`。此条记录创建和用户要求，不声称改动已测试、协议已冻结或任务已启动。启动与最终状态以之后真实receipt/Slurm为准。

Stage58 CPU4512043实际6接口方法及真实AA import/help和旧real WB计量COMPLETED0:0/5s；CPU4512044实际11父行政guard方法(含两个自有session的边界终止)COMPLETED0:0/1s。二者只证明旧AA及V6对应行政接口，不冒用为新三轮科学路径或GPU LIVE通过。

### Stage59 实际 quota 与 W&B TMP 元数据（2026-10-02）

当前 live quota 实现为 `/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage59_live_quota_v1/publish_quota.py`，源 SHA `dbdb7a7469b074089235ed4b195ef74b35934367f233a0a74552d4a8e28a829d`；登录节点轻量执行 `quota -w -u zixiao`。`latest.json` 是不断刷新的真实测量，不能作为整段不变文件 SHA 绑定；逐次核验字段和新鲜度，保存每次实际引用的原始 quota 证据。compute 节点本地 quota 失败、SSH 不通及主机钥匙变动不构成改用 df 或关闭主机校验的理由。发布器到期后仅核验并维护本次自有 PID/lock；不得宽泛终止其他进程。

真实短程行政复现 `stage59_wandb_tmp_repro_v1/run_actual_wb_only/summary.json`：W&B0.28.1 成功初始化、记录一条合成 int/float 指标并关闭，3.57秒、无科学操作；原414 counter在TMP报75次类型错误，邻近 inode 快照确实包含 UID1278、单链接、同设备的 Unix socket。原4512050/4512051临时对象已在自有 finally 清理，因此具体原类型仍 UNOBSERVED，原 FAILED 保留。该检查仅验证监控工具和计量，不能当模型训练进展。持久结果仍使用原414规则，TMP使用独立受限计量。新的正式作业必须记录实际 optimizer/base exposure 与自己的 W&B journal；有 job ID 或 GPU 占用不代表训练更新已开始。
行政 V9 final `stage59_full_corpus_segment_parent_v9` 实际 compute-0-20 十项 stdlib 检查全通过；TMP FileNotFound 最多三次全树重计，其他拒绝不 retry。相同冻结科学协议 f344a049… 下新正式4512052/4512053实际进入优化，真实early W&B payload经原数值类型恢复与journal原SHA精确匹配；这是live early-prefix核验，不是整段关闭或checkpoint恢复证明。矩阵metadata协调器实际七项检查通过，bounded PID778465；原失败被单独保留计账，新pair先登记再考虑下一提交，缺任何终态闭合或未知sbatch响应则停止自动推进。当前自有单卡锁只保证本项目不重复，不承诺阻止他人SSH占卡。
## 2026-10-07 Stage61：Slurm 脚本换行核验

正式 sbatch 提交前读取脚本原始 bytes，要求 LF 且无 CR；bash -n 不能代替此检查。F5 materialization v2 的实际 CRLF 提交拒绝未创建 job，失败元数据保存在 stage61_data_input_audit_v1/scan_v2/checks/root_F5_materialization_v2_actual_CRLF_submission_rejection.json。旧冻结脚本/请求保留；仅 LF 修复采用独立 v2_unix.sbatch、新 ROOT READY 及任务 ID。原 F5 4512364、数据/manifest/协议/runs 未修改。HPC skill v1.0.40 两份同步。

## Stage61 C4 启动与版本比较修正（2026-10-08）

4512378 在 RDKit 版本字符串门禁处 FAILED 1:0/1CPU秒，科学 worker 尚未导入，未生成构象或运行 PM7。发行元数据2025.9.5与rdBase2025.09.5只差数字前导零；独立v3入口规范化纯数字点分比较，原包、旧源码、请求及失败均保留。实际依据：docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/root_actual_C4_4512378_startup_failure_metadata_v1.json。

4512380 完成固定槽位生成，但82个已收敛构象的身份被3D MolBlock回读增加的立体注记拦截，另8个MMFF未收敛。只读CPU诊断4512381确认原子化学、键型及原7个明确CIP一致；身份判断须绑定封存的mapped isomeric身份，保留实际和最终几何的严格比较，不能全局抹除立体信息。诊断实际请求1CPU、分配2CPU、1秒，计2CPU秒。原82坐标未保存，审阅后的独立v4续跑只重建原82固定seed槽，原8失败不重试，原signature lock保留，最多82次新PM7，累计预算含全部前置/失败。实际依据：scan_v2/checks/c4_identity_guard_4512381.json、root_C4_identity_guard_4512381_actual_accounting_v1.json和root_actual_C4_v4_reviewed_continuation_submission_20261008_v1.json；这些说明不构成历史PM7来源或完整实验成功的证明。
### 2026-10-08：注册后的 prepared 模板字节保留（skill v1.0.42）

Root 已登记 path/完整 SHA256 的 prepared 模板同样保留字节。partial 数量或成本更新采用唯一新路径，不覆盖 active READY、源码或 RootReview。误改须保留修改后副本与 mutation 说明；恢复候选先写独立文件，只在实际字节数和完整原 SHA 同时一致时恢复原路径，不能凭逻辑内容近似或手抄 hash 恢复，也不能把 owned prepared 后改当原 LMDB/manifest 漂移而发 HARD_STOP 或重跑科学。

Stage61 的 v2 TEMPLATE 后补成本曾改变已注册字节；新增内容已另存 v3，恢复候选与原12589字节/完整 SHA 精确一致后才恢复 v2。actual4512488 的 READY/源码/RootReview 未改。原 mutation 与恢复依据均保留：`scan_v2/checks/pipeline_C1_current4_TEMPLATE_v2_postregistration_change_note_v1.json`、`pipeline_C1_current4_TEMPLATE_v2_exact_restoration_receipt_v1.json`。本节是已发生的元信息修复，不改变原数据、manifest、冻结协议、runs 或科学算法。

### 2026-10-08 PowerShell→ssh 原生引号实证（HPC skill v1.0.43）
包含 `script|batch` 的双引号正则经PowerShell→ssh原生参数传递后失去引号，远端shell实际调用Unix batch并创建at job1。本次创建输出与队列job1/UID1278/ownerzixiao/创建时间吻合后只执行atrm1，返回0且post atq证明job1不存在；没有影响Slurm科学任务或原数据，没有输出spool环境/凭据。闭合证明：docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/pipeline_PM7_own_unintended_at_job1_cleanup_v1.json。
复杂SSH元信息查询改用固定自有Python脚本路径；脚本中subprocess argv、shell=False、stdin=DEVNULL，避免跨shell嵌套正则/管道拼接。简单SSH启动本身仍正常；不新增审批、暂停或未授权清理规则。

### AllocMem 为零时的声明内存（2026-10-09）

当 scontrol show node 返回 AllocMem=0，仍通过目标节点全部用户的队列和各作业元信息核对总声明内存及节点归属；squeue -w <node> 可用于列出任务。按现场声明的单位与计量范围核算，不能把本账户队列当作全部用户队列，也不能以零AllocMem忽略已有任务。已有内存承诺加新作业仍须满足技能的85%上限。

本次compute-0-19的实际观察中，AllocMem=0，两项32CPU作业各声明96GiB；实际CPUAlloc64与本账户在该节点64CPU合计相等。后续16CPU/16GiB私有聚合测试提交前再次读取全部节点队列，合计196608MiB，加新任务16384MiB后通过85%核验。此为点时证据，不保证节点以后空闲；见项目 docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/root_original_aggregate8_private_equivalence_static_resource_acceptance_20261009_v1.json。原16核、有效并行、唯一提交协调者和600秒长任务探测规则保持。


## 2026-10-10 数据计算任务与一小时探测

用户本轮依据项目根《Phase1 数据集重整与标签生成：工作内容分析.md》执行WP0/WP1/WP4测试，原LMDB只读、测试不写任何LMDB、无训练。WP4允许任意现场空闲计算节点；WP5仅compute-0-14至0-19，待试跑后用户决定正式方案。大批量计算的对话级探测间隔按用户要求改为3600秒，异常/终态/用户消息及时响应。本轮独立输出根为runs/phase1_dataset_rebuild_20261010；xTB6.7.1独立环境software/xtb/conda_env，MOPAC沿用已有mopac23.0.3环境，各调用独立LD_LIBRARY_PATH。SSH短时拒绝新连接可在恢复后保持单个交互SSH会话减少握手；非交互子ssh使用-n，srun使用--input=none。

### 2026-10-10 WP5前节点范围补充

用户于2026-10-10明确允许进入WP5前任意使用空余节点。WP0、WP1、WP4及其预处理/测试可通过Slurm分配任意有空余资源的计算节点，优先CPU节点；每作业至少16核且实际并行，沿用全部用户声明内存85%校验和Root统一提交。WP5仍限compute-0-14至compute-0-19，并先完成WP4后的用户决策。

## 2026-10-12 WP5 已批准续算

本次新phase的实际用户authority及submitted_jobs位于 runs/phase1_wp5_20261011/submission/recovery_attempt_v11/。冻结runner11/contract4保持原科学协议，仅队列并发元数据修复。主4514069–4514140、六收尾4514141–4514146已实际一次性提交；通过全部78资源/节点和六own-node afterany核验。小时级只读监控：ssh -n compute-0-20，chemprop Python运行 wp5_hourly_observe_v2.py --hour N --write-latest；union原/新实际IDs去重累计coreh，人口只读同一queue不相加。此授权只覆盖这一新增phase，不自动授权再续交；最终200条保持。原STOP已按批准归档，恢复action证据保存，原输出不删除。

## 启动失败补交实际回执（2026-10-12）

仅本次用户明确授权69主+4收尾+2依赖调整。实际回执：runs/phase1_wp5_20261011/submission/startup_replacement_v1/submitted_jobs.json；权威：user_authority_20261012_v1.json；75项调度核验：reports/startup_replacement_actual_scheduler_verification_v1.json（PASS）。不再次提问或重复提交；逻辑三健康主保留，新主4514153–4514221、收尾4514222–4514225。冻结科学文件不改，旧启动失败成本纳入去重累计。

## 2026-11-04 Alpha native accounting and scientific mask continuation

On compute nodes use: ssh -n -o BatchMode=yes -o ConnectTimeout=5 218.192.171.238 sacct -j ACTUAL_JOB --parsable2 --format=JobIDRaw,State,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList

Exact strict new-record mask guard is in uff3_alpha_runtime_v1/quality_gate.py. Full QA reference catalogs are in reference_catalog.py; native timing metadata is in uff3_candidate_v1/call_timing.py. No per-job Root approval receipt. Active source runtimes are immutable; deploy a new source and replace only pending dependents.
