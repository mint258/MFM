# D-family weekly native allocation costs

Snapshot: 2026-11-22T21:48:57.507456+00:00; Slurm query since 2026-11-19T00:00:00 CST. This is the current cumulative week, not a completed-week claim.

| Scope | Parent allocations | Allocated CPU h | One-target GPU-host wall h |
|---|---:|---:|---:|
| Terminal (including failed/cancelled) | 86 | 387.068888889 | 45.749166667 |
| Running prefix at snapshot | 2 | 1.918055556 | 0.000000000 |

Original parent allocations only. Allocated CPU hours are ElapsedRaw × AllocCPUS; parent TotalCPU is unreported and remains unavailable. GPU-host wall is the registered single-target allocation proxy, not GPU busy time, device energy, or monetary cost. Embedded training/readout time is counted once. Batch, extern, observation steps and queue time are excluded.

Scope uses original D work/submission paths plus explicitly registered own D CURRENT job fields. Cancelled-before-start entries retain zero elapsed costs. Failed jobs retain real consumed allocation time. The two live A1 jobs are partial prefixes and will continue accruing cost. No telemetry or scientific arrays were reread.

[Per-job original accounting](../../results/d_recipe/costs_weekly_20261123.json) includes status, source provenance and original unreported TotalCPU values. The short accounting producer 4539190 begins after this input snapshot and is listed separately after closure. No monetary rate has been assumed.

Accounting producer completed normally: job4539190, CPU11, 12s × 1 allocated CPU, C0. Its original supervisor reaped root4190726 and reported children=[]. [Separate post-snapshot parent cost](../../results/d_recipe/weekly_costs_producer_20261123.json); excluded from the table above to preserve the snapshot.

## G1 seed0 single-run cost, outside the fixed weekly snapshot

The original G1 parent4539204 completed0:0 in37702s with5 allocated CPUs: 10.472777777777777 target-one-GPU job-wall hours and 52.36388888888889 allocated CPU hours. The original loop including fixed VAL took37215.715877037495s and processed80.61110553165612 samples/s.

Original RTX3090 telemetry gives a whole-card point-sample mean228.29927302100162W, 1238 samples and0 missing. The original sampler records only0<samples<training_budget, excluding final GPU readout; this is neither integrated energy nor a device-only attributed measurement. Parent job wall time includes readout. TotalCPU remains site-unreported, not measured zero; no money rate is assumed.

[Exact native result](../../results/d_recipe/D-G1_seed0_complete_GPU_job_costs_20261123.json) was produced once by4539289 onCPU13, COMPLETED0:0,8s×1CPU. Its root1757127 was reaped, resident children=[], and actual/proc root absent. This producer reads only current G1 telemetry and copies the original cost algorithm. [Separate producer record](../../results/d_recipe/G1_costs_producer_20261123.json). Main CPU statistics4539205/54s×1 and comparison4539206/15s×1 are separate parent costs. The weekly table above is unchanged; endpoint diagnostic parents4539284–4539288 are still open and will be recorded after closure.

## 2026-11-24 · L1正式训练原前1000更新

GPU5/4539360、RTX3090/UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377、5CPU/3workers、B32，原正式3M的TRAIN_1000_updates行记录32000样本/1000更新、669.8406839910895循环秒，资源算术为47.77255363071628样本/秒。原atom_sasa/graph_2d/molecule_3d三行均保留，[原转录](../../results/d_recipe/D-L1_seed0_first1000_native_timing_20261124.json)。统计窗只覆盖原循环首1000更新；以此作普通排程外推约17.443767812267957循环小时，后续固定VAL变化、外层初始化、GPU最终读出及排队另计，不作采纳或停止门。原48h、900秒安全收尾保持；原GPU正式训练继续，无新增测速、前向或配方改动。

整卡功耗由该原正式作业持续采样；闭合时原一次成本生产汇总整段与首1000采样窗，本条没有重新读取遥测或旧周账。字段/输出头参数与MAC引用[冻结源码解析](HEAD_COSTS.md)，实际吞吐不单归因于输出头。前1000的原clipped_fraction=0.0是梯度裁剪窗记录，字段±6截断比例继续引用原fullTRAIN fit.fields。

## 2026-11-24 · L2 A1未解决原成本

原父4539164 FAILED1:0/46秒×1CPU，4539169 FAILED1:0/81858秒×1CPU；保留全部失败成本，不把未启动D-L2神经臂记作已运行。源[原失败记录](../../results/d_recipe/L2_A1_unresolved_20261124.json)。周快照里该A1曾有在跑prefix，后续最终账只按原父完整分配计一次，不将旧prefix叠加；无旧遥测/周账重算，TotalCPU/单价未提供。

## 2026-11-24 03:56 CST · 退役L2未用模型预留，原L1守卫自然恢复

L1原日志实际出现DISK_TRANSPORT_PAUSED，PID1491773，available313209810944B/required313356249146B；样本停在71488。保留原live配置和guard源码，不手动信号或重启。L2已按TASKBOOK3.5未解决且从未启动神经臂，原12槽×250000000B的Stage2池中其三个1M/2M/3M槽位不再有未来writer。只撤回这750000000B未使用本线future：模型槽12→9、模型字节3000000000→2250000000，221225472B日志/读出/序列化缓冲及三个额外槽均保留；旧所有实际checkpoint/partial数组保留，无删除。

Data plan的Stage2池3221225472→2471225472B、full峰值35118709120→34368709120B、全D NFS联合峰值声明42074762973→41324762973B。原在跑L1配置仍保留42074762973B更保守的配置声明，所有其它owner预留、100GB/fresh5秒、原quota额外缓冲和各根盘系统底线不变；这不是降低需要的安全余量。原h_peer_storage每次读取本线live plan，原guard自行通过准入并记录DISK_TRANSPORT_RESUMED、同PID1491773；随后原losses.csv已75456样本/2624.544632997364循环秒。没有新job、没有L1重新初始化/检查点重载，也没有重试L2。原分配与暂停时间全部留在成本中，不从计时剔除。[预算/原事件](../../results/d_recipe/unused_L2_slots_retired_and_L1_native_resume_20261124.json)。

## 2026-11-24 09:02 CST · L1原1M断点、固定VAL与原守卫恢复

原1M完整断点samples_1000000.pt已于00:48:53 UTC发布，205549589B；只接收文件元信息与原configuration科学绑定，不加载张量。原1000000样本/31250更新固定2000 VAL有198字段原单位误差，三块loss原值atom_sasa=0.01316781784594059、graph_2d=0.045788690209388735、molecule_3d=0.04451841747760773，累计梯度裁剪fraction=0.006656（不是目标±6截断率）。[原1M记录](../../results/d_recipe/D-L1_seed0_original_1M_milestone_20261124.json)、[原CSV](../../results/d_recipe/D-L1_seed0_VAL_original_units_1000000_20261124.csv)；无另一次验证、重采样或拟合，不用VAL选配方。

原quota守卫随后在1007360样本暂停，PID1491773，available312291291136B/required312397987623B。只退役已闭合Stage1 seed1两个未使用额外checkpoint槽464000000B：原GPU4538566/67、CPU4538568/69/70已原C0并reap、无未来writer；原六个1M/2M/3M文件及全部缓冲保留，Stage2九槽/原221225472B缓冲也不变。Stage1池2147483648→1683483648B，全D full峰值34368709120→33904709120B、live联合41324762973→40860762973B。所有实际文件、其它owner future、100GB/fresh5秒、原quota额外8GiB/根盘底线及活跃L1配置42074762973B上界保持。

同一原guard自行通过新计划准入后DISK_TRANSPORT_RESUMED，仍PID1491773；原losses.csv随后1010912样本/20969.7940208707循环秒。无人工信号/新job/重启/重新初始化或checkpoint重载，原分配及暂停全部计成本。[本线未用future与原事件](../../results/d_recipe/closed_stage1_unused_slots_and_L1_resume_20261124.json)。若后续L1 seed0 WIN才另登记该臂seed1，不复用此已闭合Stage1控制池启动新工作。L2仍UR不重试，最终配方未冻结，全部后续关卡/冷9M/最终A-B-C与基准/成本/一次全回归及两PR范围保持。

## 2026-11-24 · L1原监督器/proc竞态，准备原1M完整状态续接

原GPU4539360在1501088样本/46909更新/30202.13498191908循环秒后FAILED1:0，实际父30323秒×5CPU。原1.5M固定2000 VAL已生成198字段与三块损失，保留[原失败前窗口](../../results/d_recipe/D-L1_seed0_original_fixed_VAL_1500000_failed_prefix_20261124.json)；这不是3M/R3结果。原冻结resident traceback为ProcessLookupError `/proc/1511343/task`，位于supervise→descendants→children；原root1491752已reap(-15)、worker1491773及瞬时PID1511343均实际/proc缺失，actual remaining own job scope=[]，节点5仍MIXED。没有OOM/磁盘满/节点故障结论，不对其它用户进程发信号。

仅给后续监督器补上进程/线程刚退出时的ESRCH处理，权限等无关错误继续抛出；旧冻结resident/配置/产物保留。CPU12/4539397已通过13项相关测试、0跳过、原测试0.300秒，原Slurm C0/ElapsedRaw0×1CPU；root1812247 reap0、resident children=[]、实际/proc缺失。完整默认回归仍留PR前一次。

按TASKBOOK3.4，准备从原205549589B、1M完整checkpoint恢复同一D-L1/seed0，原模型、优化器、clock、采样器/torch/CUDA随机状态和已冻结p99随原载荷恢复，逻辑预算仍3M。原未保存的501088样本需重放，全部实际失败成本保留，不从头训练或加新臂/seed。拟用GPU4/RTX3090/5CPU/3workers及CPU12单核统计→原R1 seed0配对；节点实际盘/inode/GPU/Slurm健康已核实，原900秒退出窗口、48h/8h/4h时限、NFS/根盘/UID/其它owner future保持。原1M不复制，后续仅2M/3M两个断点仍在原Stage2九槽池内。[具体原记录和续接绑定](../../results/d_recipe/L1_exit_proc_race_and_1M_continuation_prelaunch_20261124.json)。此刻只完成准备，尚未提交新训练。

## 2026-11-24 · 续接前原配额准入与已闭合物理资源结算

没有在准入不足时提交续跑。对原已闭合R1 seed0、Stage1 seed1、G1的12个checkpoint只读stat.st_blocks×512资源元信息，撤回806413184B未使用预测；全部12文件保留，活动L1两次剩余断点/三个通用备用槽及原checkpoint上界250MB、读出/序列化缓冲均保持。[闭合checkpoint结算](../../results/d_recipe/closed_checkpoint_pool_physical_settlement_20261124.json)。另以原h_resources.allocated同一物理方法按整个已闭合structures目录、native A1 reference目录、原R0四层cache目录保守结算，撤回2729007854B原未用预测；所有数组/统计/缓存原封保留，role索引预测、原200MB metadata/360138915B序列化、Stage1的291483648B及Stage2的221225472B缓冲都不减。[闭合源目录结算](../../results/d_recipe/closed_source_components_physical_settlement_20261124.json)。

现full峰值30369288082B、live联合NFS37325341935B；活跃前续接配置仍保留原42074762973B更保守声明。物理释放0B、不改其它owner future/100GB/fresh5秒/原native额外8GiB或根盘底线；只是剔除已无writer的本线未用future。原native完整准入已重新通过，所需308397102081B。新训练仍待实际sbatch；科学条件与原1M完整状态/501088样本重放记录不变。[续接记录](../../results/d_recipe/L1_exit_proc_race_and_1M_continuation_prelaunch_20261124.json)。

## 2026-11-24 · 原1M续接改用获准的GPU20备用组

4号GPU在复核时已有其它CUDA上下文，我未据此挡住4539399提交；该父FAILED1:0/11秒×5CPU，launcher在训练前退出，未创建训练目录、loss或telemetry。原reap roots3609151/3609183/3609148、returncodes0/1/1，resident children=[]且实际/proc均缺失；原新旧配置与所有成本保留，没有操作其它任务。此项属于启动资源准入拒绝，退出监督器竞态修复已由原13项CPU测试通过，没有重复该代码故障或追加同类修复。

实际小组各卡均已有CUDA上下文，按原授权转另一组：compute-0-20的RTX4090/UUID GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02，实际423/49140MiB、公共自有锁可用，符合20/22既有≤30%共存规则；原其它上下文保留。该节点104CPU/已分配80，5CPU普通sbatch足够，不启动原生SSH模型。实际root余924034408448B、inode465749662，按实际954159071232B的10%系统底线再留本线17314086912B；原联合NFS37325341935B/UID与其它预算不变。

新入口仍恢复原1M完整状态至同一seed0/3M，501088样本未保存重放及全部失败成本保留，已冻结p99不重拟合、原R1控制复用。[具体准备记录](../../results/d_recipe/L1_GPU20_same_1M_continuation_prelaunch_20261124.json)。此刻GPU20尚未提交；原4号脚本冻结保留，后续只用新文件。
