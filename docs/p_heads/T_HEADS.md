# 原子级新预测头与 PMA 消融

2026-11-18；状态：T1/T2/T3/T5 seed0原评价与配对判定已发布，均按规则待条件seed1；T4正式运行继续。

## 用户补充指令与当前执行范围

以用户新增 `docs/p_heads/USER_DIRECTIVE_20261117.md` 为冲突条款的权威来源。本线T0–T5与配方线9M确认臂不同，后者明确写作“配方线9M-Tk”。下列覆盖原T1逐头验收造成的缺失决策；原报告/逐头数值保留为历史，不再阻止用户授权的从头训练。

| 臂 | 当前基底与唯一改动 | 对照与条件seed1 |
| --- | --- | --- |
| T1 | 当前明确M2（A1+B3+B4），全部45个atom/pair字段走零残差初始化decoder，从头3M，无64样本gate | 复用配方线M2 seed0；若触发seed1，只补本臂并复用配方线M2 seed1 |
| T2 | 现有B3基底九约束头运行继续 | 原B3对照；若胜出，在发布的CURRENT_BEST上额外从头3M seed0确认，对照复用该配方 |
| T3 | 现有B3基底query注意力均匀化继续 | 原B3对照，不换基底 |
| T4 | B3；仅将sum支路sigmoid门固定为1 | B3及本线共享一次B3 seed1 |
| T5 | B3；无PMA，分子标量线性读取[mean(H0),sum(H0)/N_ref,logN] | B3及本线共享一次B3 seed1 |

之后新启动按配方线发布的CURRENT_BEST绑定；T1正式启动前协调窗口已核新发布CURRENT_BEST仍为M2，与已准备基底一致，无需更改配置。T4/T5明确固定B3。所有正式运行均从头、3M、不载入验收权重；不停止或迁移T2/T3。GPU顺序为提速线（GPU部分完成前）优先，其后配方线，再本线与解耦线；T1/T4/T5互不等待科学结果。M2源JSON的checkpoint_samples仅1M/2M/3M、无显式step_overhead，新T1逐项保留这些执行键与训练器默认，没有加首32或改worker/lr/clip。恢复、旧尝试和祖先检查点元数据已从新配置移除。

T4新增默认关闭 `p_recipe.pma_sum_gate_one`：实际门是Linear(512,1)加sigmoid后广播到64维sum_project输出；恒1时只跳过这个门，保留sum_norm、sum_project及除以固定N_ref=53.64145。query/self-attention/FFN/logN及所有既有参数不改。

T5新增默认关闭 `p_recipe.simple_molecular_readout`：不构造PMA，严格排除padding后生成512维均值、512维sum/N_ref及1维logN，共1025维，送入各P分子标量字段的线性层；原子、pair、向量和下游H0保持B3路径。T4/T5仅新增三项单元测试：T4门恒1与padding，T5维度/线性及padding排除，关闭开关后的原finish逐位一致。实际Slurm4535715/compute16/1CPU已COMPLETED/0:0，20秒，三项全部PASS（测试0.629秒）；未重复旧测试或做逐头验收。

配置入口 `t_prepare_configuration.py` 必须指定实际基底JSON（CURRENT_BEST若是发布清单，先由协调窗口解析到实际配置），外部M2 seed1只绑定已发布路径，不猜运行或结果。`t_decide.py`按显式p_heads_reference绑定主对照；T1种子1只请求本臂，对外部M2 seed1缺失记录等待，不新建本线M2/B3对照。T2/T3/T4/T5原B3对照的条件seed1共享同一B3_seed1.json。T2胜出只发CURRENT_BEST seed0确认需求，确认不自动衍生额外seed1。统计阈值仍按原规则，新增机制组合解释由预注册补充冻结。
本线T侧薄接管入口已准备：`t_native.py`记录真实worker PID/UID/start_ticks/PGID/退出码，并将原生worker及其后代亲和性限制在实际allowed集合中的15核；这只是native亲和性，不声明Slurm分配。共享UUID锁仅由t_train持有，原生薄runner持续使用本线24GiB H/T guard；其磁盘暂停/恢复信号仅可作用经身份核实的本worker新进程组。原生主worker及已记录子树退出后才发布终态。`t_hybrid.py`只把原scheduled_run协议绑定到冻结T源、CONTROL/hybrid独立台账、15CPU和T入口，不改p_recipe的完整保存/回执/真实job/旧GPU上下文与锁释放等待流程；接管后使用真实Slurm mask。源端HANDOFF_SAVED即退出，最后评价仍只在t_train执行一次，已完成全部评价时不再接管训练。

新薄入口仅3项fixture/mock CPU单测由Slurm4535726/compute16/1CPU完成（COMPLETED/0:0，5秒，测试0.003秒，全部PASS）：独立账本与15CPU、保留原协议并将入口单次路由至T训练、native身份/亲和性/清除伪Slurm环境与无外层GPU锁。该测试不代表已发生真实接管。原0d04c40三个冻结源保留；新增T1/T4/T5_hybrid_source供后续按真实资源启动，准备/原生启动/真实sbatch/register由协调窗口执行；实际T1原生运行事实见下节，尚未据此声称完成真实接管。
配方线现已发布外部共享参考清单 `/share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/M2_SEED1_REFERENCE.json`，其reference configuration为 `/share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/fixed_20261115/noise_seed1/M2_seed1.json`（清单内相对路径以MFM_p_recipe为前缀）。已发布run为fixed_20261115_M2_seed1_noise_20261117_attempt2，真实job4535736／node7，当前发布状态RUNNING_NOT_YET_REUSABLE。必须等3M检查点、完整R1/R3及成功终态均确认后才可复用，不能把当前参考当已完成或据此作质量判定。本次仅文档绑定，不修改live T1 canonical配置；最终若本线T1触发seed1，使用已有参数 `--reference-seed1-configuration /share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/fixed_20261115/noise_seed1/M2_seed1.json` 显式绑定外部对照，并由协调窗口在调用前确认其就绪；不新跑本线M2 seed1。

旧T4队列4535734已由协调窗口hold并确认PENDING／0秒后取消，没有启动或重跑训练。当前真实T4作业为4535771：node4／15CPU／nice10000，afterany独立H层6任务4535770，只是同卡资源接续，不依赖H科学结果。原T4_source@0d04c40、B3基底和配置不变，日志CONTROL/T4_seed0_4535771.log，目标GPU UUID前缀6965a7c7；此前PENDING未记为启动；现已实际RUNNING并发布首32，唯一事实观察见下。T5原队列4535735的旧依赖提速线4535718失败后，协调窗口确认T5仍PENDING／0秒再hold并更新；release被Slurm拒绝，遂取消该未开始句柄，以相同冻结源／配置／B3基底干净重提真实4535747：node5／15CPU／nice10000，afterok当前提速线4535744。此处只替换零进度等待队列，T5没有训练进度重启；旧0秒记录保留，T1/T2/T3未改动。
用户新增明确授权T4/T5在node4低显存条件下与原有4个gmx上下文共用，现已由协调窗口记入resources.json的对应scope；原gmx进程保持不动，只使用真实Slurm分配，不扩展为node4原生SSH混合启动许可。本次T3最终点H层6任务4535770实际已在node4／4CPU运行，T4等待其同卡物理资源释放后再接续。T5仍为同一4535747／node5，原提速线4535744再次失败后，仅在已确认PENDING／0秒／DependencyNeverSatisfied状态将依赖直接改为afterok提速恢复4535772（正priority、未再次hold/release或取消），不将T4/T5挤在同一卡。T4已在真正RUNNING并发布首32后完成一次实际主进程/后代Slurm mask与完整GPU UUID观察，不把初始化视作更新，也未增加硬gate。T1/T2/T3既有运行未改动；T3原作业继续自动评价，完整scores.json发布后仅由根窗口运行一次既定t_decide。
T4唯一实际资源观察由协调窗口relay原工具并写入 `results/p_heads/T/T4_resources_4535771.json`：4535771实际RUNNING／compute-0-4，主Python PID3504910、UID1278、start_ticks5881235217、PGID3504910；Slurm CPU_IDs和真实主mask均为0–14共15核，实际2个按需spawn reader及所有所观测后代均受其约束。配置workers14不变；CUDA_VISIBLE和nvidia-smi真实主上下文均匹配GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6。工具确认losses首条samples=32且完整首32检查点 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T4_seed0/samples_32.pt` 已发布，CP内容未读；这是实际首个训练更新证据，不只是W&B初始化。该观察不再重复，不影响原gmx上下文或其他在跑任务。
T4普通日志唯一500更新窗口由协调窗口实际compute4读取并计算：731更新／23,392样本至1,231更新／39,392样本，共16,000样本／470.3855091333389秒，34.01465327764704样本/秒；对应3M训练更新ETA为2026-11-19 05:18:42.495993 CST，未来固定VAL及最终读出另计，估计可变。此时GPU仍与原有4个gmx上下文共用，不能将该速率用于架构速度比较；这里只报告时间／成本并继续原训练，不停训、调参或换卡。本报告直接转录该一次窗口，没有重新测速或读取同窗口。
T5现已由原4535747实际RUNNING／compute-0-5。唯一资源观察保存在 `results/p_heads/T/T5_resources_4535747.json`：主Python PID1312779、UID1278、start_ticks1128299236、PGID1312779；Slurm CPU_IDs及真实主mask均为0–14共15核，实际4个按需spawn reader及所有观测后代同受该mask约束，workers14不变。CUDA_VISIBLE与nvidia-smi真实主上下文均匹配GPU-dac07d74-6269-c7db-8832-340dd3c0b377。工具确认losses首条samples=32及完整 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T5_seed0/samples_32.pt` 已发布，未读取CP内容；不重复T4/T1资源观察、不追加测试或硬gate。先前PENDING／0秒和依赖更新均为队列历史，不代表此时仍在等待。
T5唯一普通500更新估计已由协调窗口relay写入 `results/p_heads/T/T5_runtime_estimate.json`：4,156更新／132,992样本至4,656更新／148,992样本，共16,000样本／237.69553899990767秒，67.31304296672371样本/秒；3M训练更新ETA为2026-11-18 17:14:16.492789 CST，未来固定VAL及最终读出另计，估计可变。只直接消费该已有producer窗口结果，没有重读losses、重新测速或复观T5身份；T4及T1既有速率均未重算。
T5自身p99已由原生产者发布并唯一读取：实际run=p_heads_T5_seed0，来源 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T5_seed0/clip_calibration.json`；initial_clip=281.7，window_start_samples=60,000，calibration_samples=150,000，sample_axis=optimizer_step_start，observed_updates=2,813，quantile=0.99，threshold=**90.51889801025392**，fitted=true，effective_freeze_samples=150,016。此后按原规则固定至3M，不以该值调参或改变训练。本次只读取已自然发布的真实阈值，不重算p99、不再读取速率窗口、资源身份或CP内容。
T4自身p99已自然冻结。约06:02后从canonical配置实际输出唯一次读取 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T4_seed0/clip_calibration.json`，actual_run=p_heads_T4_seed0：initial_clip=281.7，window_start_samples=60,000，calibration_samples=150,000，sample_axis=optimizer_step_start，observed_updates=2,813，quantile=0.99，threshold=**42.98546188354493**，fitted=true，effective_freeze_samples=150,016。此后按原协议固定至3M。本次报告写入前已在实际compute-0-20执行共享h_resources.guard(force=True)通过（根盘字节/inode、NFS与UID配额及全部并发预留）；未重算p99、读取CP体、复观资源身份或重新测速，也未重复T5阈值。
T5首个既定1M检查点已实际发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T5_seed0/samples_1000000.pt`，220,568,041字节，mtime=2026-11-18 08:56:02.851418 CST（原epoch1794963362.8514183）。协调窗口约09:00唯一观察时，T5自然日志已达1,007,104样本／31,472更新；本报告只转录该新元数据，不重读CP体、阈值或速率，不改变旧ETA，不作中间几何或额外评价。同期实际compute20的guard(force=True)已返回MILESTONE_WRITE_GUARD_OK／EXIT0，原磁盘、inode、UID配额及全部并发预留保护继续。

同期资源安排只记录事实：原D及CPU后处理已退出，node20有89个Slurm可分配CPU；ec788ed1候选卡由更高优先配方线C3 owner先评估，followup STATUS已确认UUID锁FREE、既有gmx约400MiB共用规则适用，但尚未出现C3迁移新job。本线不据空闲数字抢先提交或占卡。T3 seed1的4535777当时P0 hold，为较早Dprime保留一次可恢复槽位（现已完成让行并release，见下段）；B3 seed1仍暂排T2结束后20a，四条已在跑训练保持，不加入科学依赖或操作live任务。
T5首次2M训练检查点也已自然发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T5_seed0/samples_2000000.pt`，220,570,345字节，mtime=2026-11-18 13:10:24.857142 CST（原epoch1794978624.8571422）。根约13:10首次记录该元数据，本报告只转录、不重读CP、阈值或速率，不改变旧ETA或科学配置。该次转录时T4首1M尚未发布；后续真实首1M现已记录如下，不补中间几何。共享B3 seed1仍hold等待C3下一快卡优先；此前readiness未答时默认保留优先；现用户已明确C3会立即使用、继续保留快卡，不阻塞原评价或CPU后处理。
T4首个既定1M训练检查点现已实际发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T4_seed0/samples_1000000.pt`，232,047,619字节，mtime=2026-11-18 13:20:11.286347 CST（原epoch1794979211.286347）。本报告仅引用根首次提供的元数据；13:29实际compute20 T4_1M_WRITE_GUARD_OK／EXIT0已在写前通过，不再查CP、身份、阈值或数值。依据这次实际首1M进度，T4后续3M训练更新运行规划调整为11月19日约06:30，固定验证/最终读出另计、估计可变；原唯一34.01465327764704/s窗口和05:18:42.495993初估留为历史，未重测速或改参数。

T5仅依据已记录1M 08:56→2M 13:10的自然CP节奏，运行规划更新为11月18日约17:30；原唯一67.31304296672371/s窗口及17:14:16.492789初估保留历史，不重算测速。T1约16时规划不变；原T2正式结果亦不改。用户现已明确答复“C3会立即使用，继续保留快卡”，readiness不再pending，四处STATUS已发布；B3 seed1 4535778继续hold。根/Hagent同次已提供20a在13:28.610938为843/49140MiB、仅2gmx、UUID锁FREE，13:31 Slurm有20CPU可分配，H仅CPU4不占卡；这里只转录已发布资源事实，不重新观察。C3仍先使用，本线不因空闲数抢占、解除hold或启动新训练，T2 seed1 source/提交仍由根协调，暂无新训练。
唯一共享B3 seed1已正式启动。16:59 node7外部gmx释放，根17:00实际核GPU-9db54192-dd3f-3177-e56f-dcd161ff932c为5/24576MiB、利用率0%、无任何CUDA计算上下文，34CPU free，瞬时UUID锁FREE；实际root53,655,703,552字节、NFS6,948,995,989,504字节、UID449,439,285,248字节对175,707,924,480字节需求及inode／24GiB合并峰值guard通过。根先核旧4535778仍held/PENDING／0秒／未Start／Restarts0，再仅取消该未启动队列；旧CANCELLED／0:00历史保留。相同B3_seed1_source@d8dce41和相同canonical fresh配置已改排为新4536238／node7／正式15CPU／nice10000，cu118兼容3090、启动wrap再核实际CUDA上下文为空后exec。此为共享B3 seed1首次从头3M，不是重复新baseline、不借尚待答的3090共用授权，也未占用用户保留给C3的20a。

首32后的唯一真实资源观察已由根完成，产物为 `results/p_heads/T/B3_resources_4536238.json`，observed_time=1794992695.3195026（17:04:55 CST）。实际trainer PID2615732、UID1278、PPID2615728、PGID2615732、start_ticks1979361618；真实Slurm15CPU／CPU_IDs0–14，父与所有所见后代mask均0–14；实际4个按需lazy reader、配置最大14。CUDA_VISIBLE与真实父CUDA上下文均匹配node7完整UUID9db54192-dd3f-3177-e56f-dcd161ff932c；first32loss及samples_32.pt已由原helper确认，CP内容未读。本窗口仅转录根提供的全部事实，没有重采或重读该JSON验证。B3 config/run/output与d8dce41源不变；当时T3仍held等待3090共用scope及C3原运行资源释放，后续已在无context的node5启动4536267；T2仍perf后，T1 seed1已冻未排，当时没有第二张空卡。

T5根16:53:44自然日志已到2,809,600样本／87,800更新、seconds43322.857407443225；根据该真实进度把训练3M更新规划修正至11月18日约17:45，原固定VAL/R1/R3另计、速率波动下估计可变。旧17:30自然CP规划及初始67.31304296672371/s窗口／17:14初估均为历史，不重新测速或读取旧行。T4同次自然进度1,436,800样本／44,900更新仅作进度记录，不改科学参数；本窗口继续只监测T5原4535747及post4535836，完整父+post成功后才一次消费正式产物。
## 成本1.5倍提示：仅报告并继续

沿用T4/T5原唯一普通500更新窗口34.0146533／67.313043样本每秒作资源粗估，补充指令原估T1/T4/T5三臂约30 GPU-h。当前仅T1已闭合Slurm段10:39:20，加T4约24.5小时训练更新、T5约12.4小时训练更新，已有约47.5 GPU任务墙钟小时的计划粗估，超过45小时＝1.5×30；尚未包括T1旧native段以及T4/T5固定VAL／最终读出。这是现有吞吐下的计划估计，不是实际已结算成本、GPU利用率或独立进程能耗。本次只转录已知事实，没有新测速、重读旧窗口或复算原始数值。实际收尾按真实native／Slurm无重叠区间汇总，保留原lineage并扣除接管分配等待的重叠，不能重复算T1旧段。依任务书总规则6仅报告并继续，原预算和科学参数不改，不因此停训、调参或追加臂；成本按周/收尾汇总，不编造价格。此次两MD写前actualcompute20 COST_REPORT_WRITE_GUARD_OK已通过。
共享B3 seed1自身校准已自然完成。根17:46:07在自然日志153,600样本／4,800更新后，唯一次读取 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_B3_seed1/clip_calibration.json`：calibration_samples=150,000，quantile=0.99，initial_clip=281.7，threshold=**35.74676895141602**，observed_updates=2,813，fitted=true，window_start_samples=60,000，sample_axis=optimizer_step_start，effective_freeze_samples=150,016。此记录严格属于本线唯一共享B3 seed1／p_heads_B3_seed1，不替换T0/B3 seed0；后续该原训练固定阈值，不调参或改变预算。本窗口仅引用根提供的真实生产者字段，没有重读JSON、旧梯度CSV、资源截图或身份产物，也未复算、独立验证或追加评价。
T5实际最终3M训练检查点首次元数据已由本窗口17:55读取：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T5_seed0/samples_3000000.pt`，220,572,585字节，mtime=2026-11-18 17:47:47.567798693 +0800。只读取最终文件元数据，未读CP体或生成hash。同次sacct原4535747仍RUNNING／13:04:31／15CPU／compute-0-5，post4535836仍PENDING／0秒／CPU1；不能从训练3M发布推断parent或post已C0，也未消费任何T5正式分数、描述性产物或提前判定。根约17:57通过稳定会话在actualcompute20唯一relay写前guard，返回T5_FINAL_CP_WRITE_GUARD_OK；本次仅里程碑阶段推送，之后继续原句柄约10分钟终态观察，父与post均真实成功后才一次消费原产物，不重跑评价／MAE或读取旧阈值与窗口。独立最终几何由原H4536219负责，本窗口不增加中间或最终重复几何。
T3 seed1已在合法首空闲卡实际启动。18:35:51根确认node5 Slurm IDLE／48CPU可分配；18:36:50实核GPU-dac07d74-6269-c7db-8832-340dd3c0b377／3090为5/24576MiB、util0且无CUDA计算上下文，MemAvailable380388320kB；actualguard已通过root56,162,119,680B、NFS6,930,220,187,648B、inode、UID448,682,192,896B对174,951,254,016B需求，own6,275,514,368B／remaining19,494,289,408B，瞬时UUID锁FREE。根再次核旧4535777为held／PENDING／0:00／Restarts0／StartUnknown后，仅取消该未启动队列，CANCELLED／0:0／0秒历史保留，没有动C3或任何已有训练。相同T3_seed1_source@d8dce41及canonical fresh T3_seed1配置/run/output改排新4536267／node5／gpu／15CPU／nice10000／cu118及完整dacUUID，无C3依赖；启动wrap在exec前再要求零CUDA上下文，不借待答共用授权、不占20a。此新阶段覆盖旧5777 held的历史，不是seed1训练重启或额外科学臂。

根唯一资源观察已于1794998507.0093772（18:41:47 CST）写入 `results/p_heads/T/T3_resources_4536267.json`。实际4536267在18:41:16 RUNNING／2:54／15CPU／node5，trainer PID1325065、UID1278、PPID1325061、PGID1325065、start_ticks1133264168；Slurm CPU_IDs与父/全部所见后代mask均0–14，4个lazy读者/max14；visible GPU与actual parent CUDA context匹配完整dacUUID。first32loss及完整CP32present已由原helper确认，CP内容未读。本窗口只转录根提供的事实，没有重采、读该JSON验证或读旧窗口。T3 seed1完成时间暂按旧T3 seed0完整13:33:29墙钟作旧运行参考，粗估11月19日约08:15，估计可变且不是新测速。

根已预排纯CPU1／空CUDA／nice10000／node20：字段copy4536268 afterok4536267，仅原t_collect_descriptions对T3_seed1.json复制现成CYP/VAL，采用独立T3_seed1文件名，不重算、不等其他臂科学结果；最终两seed判定4536269 afterok4536267 AND afterok唯一B3 seed1 4536238。两job当前均真实PENDING／0秒／Dependency。后者届时使用当前t_decide与canonical T3_seed0.json（实际seed0仍attempt2输出），复用已发布seed0点/CI，仅首次新seed1 paired；现在不运行，不另建基线。B3已有字段copy4536240不重复。T4/B3 seed1仍R，T5 seed1 4536260仍node4 P0/afterany原T4按既有授权，T2仍perf后，T1 seed1已冻未排，20a继续留C3；其他新共享范围仍待答，科学配置/预算/源均未改。
T1 seed1已从已冻结等待变为真实资源队列4536272：node0／gpu／请求15CPU／nice10000／cu118，目标GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332，afterany外部48CPU gmx4536203，仅等同卡资源、不设科学成功前提。源仍T1_seed1_source@617e78f（原CPU冻结4536217 C0／8秒／16,671,422B），canonical fresh M2+全45decoder／seed1／3M／B32／workers14及checkpoint[1M,2M,3M]原样，无32CP例外不变。真正RUNNING后首32loss及实际proc/Slurm/GPU可作身份观察，不能套要求CP32的generic helper；当前根实核PENDING／0秒／15CPU／Dependency，不把队列记为启动。

根19:01:27实核node0 CPU48/48由外部4536203 xueying gmx占用；GPU0／3090总24576MiB用558MiB，两个gmx3502830(266MiB)/3511479(284MiB)；MemAvailable350765356kB。actualguard通过root38,876,553,216B／NFS6,862,688,747,520B／inode、UID448,435,134,464B对174,704,322,560B需求及24GiB/跨线预留，瞬时ownUUID锁FREE。新wrap在exec前严格要求实际无CUDA上下文，否则打印T1_RESOURCE_NOT_EMPTY_NO_TRAINING并exit77，这是资源前置拒绝且不启动训练，不借未答共用scope、不改停gmx、不self-undrain。4536272只是暂定资源队列，其他首个合规空卡先到可只改P0，不因同型卡或别臂科学结果等待。perf/recipe优先、20aC3保留，T4/B3/T3 seed1既有R不变，T5 seed1仍node4 P0既有授权，T2仍perf后；本窗口没有重新观察资源或操作任务。
外部M2 seed1 readiness本线已仅按生产者完成元数据确认：实际output为`/share/home/zixiao/descriptor_analysis/runs/p_recipe_noise_training/fixed_20261115_M2_seed1_noise_20261117_attempt2`，实际summary为COMPLETE、samples及actual_samples均3,000,000、updates93,750，结合已知外部4535736 C0／12:53:40以及原完整R1/R3生产流程证明可以复用。最终`samples_3000000.pt`为232,058,173B、mtime 2026-11-18 13:58:40 CST；`readout/scores.json`为742,648B、mtime14:10:03，仅文件元数据，未读分数、数组或CP体。公开`M2_SEED1_REFERENCE.json`仍写RUNNING_NOT_YET_REUSABLE及1M，是未回写的旧状态，不代表实际尚未完成。准确外部配置仍为`/share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/fixed_20261115/noise_seed1/M2_seed1.json`；不修改配方线reference，不更改T1 seed0生产者的external_pending标志，不提前比较，也不新建M2训练。

根已注册T1 seed1原字段copy4536280及正式两seed收尾4536281，均node20／CPU1／空CUDA／nice10000，真实PENDING／0秒／Dependency，均afterok:4536272。copy使用canonical `T1_seed1.json`，只转录原CYP/VAL、独立seed1文件名；正式收尾使用`--configuration configs/p_heads/T/T1_seed0.json --reference-configuration configs/p_recipe/fixed_20261115/round3/M2.json --reference-seed1-configuration /share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/fixed_20261115/noise_seed1/M2_seed1.json`。外部已经完整成功，故不挂可能被controller清除的旧4535736依赖；等待本臂6272完整成功后才运行，直接复用已发布seed0点/CI，仅首次新seed1 paired，不在此准备阶段执行真实计算。6272当前仍PENDING未启动；M2不加CP32的执行键例外保持。
T3 seed1自身p99已自然冻结：根19:23:33在原普通日志163,200样本／5,100更新后，唯一读取`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T3_seed1/clip_calibration.json`。生产者给出calibration_samples=150000、quantile=0.99、initial_clip=281.7、threshold=34.8736344909668、observed_updates=2813、fitted=true、window_start_samples=60000、sample_axis=optimizer_step_start、effective_freeze_samples=150016。此为T3 seed1独立阈值，不替换T3 seed0原35.027…记录；此后固定到尾，不调参。本次仅转录根的生产者事实，未读取该JSON、旧窗口或梯度，未重算p99、测试或benchmark。T4、共享B3 seed1及T3 seed1仍R，T1 4536272与post4536280/81仍P0，T5 seed1仍node4 P0且沿用既有授权，T2 seed1仍perf后；20a留C3、新全3090共用scope待答，源码与运行任务均未改变。
T2/T5 seed1后处理准备已登记，根先确认没有重复队列；以下均node20／gpu／仅CPU1／空CUDA／nice10000，真实PENDING／0秒／Dependency，仅在相应数据生产成功后自动接续，当前不执行计算，也不是新模型。

| 臂 | 字段post | 字段依赖 | 两seed post | 两seed依赖 |
| --- | --- | --- | --- | --- |
| T2 | 4536289 | afterok:4536170 | 4536290 | afterok:4536170且afterok:4536238 |
| T5 | 4536291 | afterok:4536260 | 4536292 | afterok:4536260且afterok:4536238 |

字段整理分别使用canonical `T2_seed1.json`、`T5_seed1.json`，只copy原CYP/VAL至独立seed1 stem。两seed判定分别使用当前`t_decide --configuration configs/p_heads/T/T2_seed0.json`或`T5_seed0.json`，显式`--reference-configuration configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json`；直接复用已发布seed0统计，仅首次新seed1 paired，唯一共享B3 seed1仍4536238。T2是否补胜出确认只能按真实最终flag决定，目前不预建或预跑确认。原B3字段4536240、T3字段／判定4536268／69、T1字段／判定4536280／81不重复；其它训练与资源队列、C3保留及待答共用范围不变。以后若资源改排尚未启动的训练父job，取消旧父前须把仍P0的post依赖绑定到真实新ID；若post已被Slurm自动取消，仅重建零进度post，此为资源维护，不改变科学依赖或当前父job。
## 固定协议与对照

T0直接复用主线 B3 seed0 的完整 3M 状态和已有 R1/R3，不重训。实际来源为 `configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json`；旧 `round2/B3.json` 中 B128/1.5M 不是本轮基底。原配置中的迁移恢复来源、attempt、旧GPU限定已从新臂移除；全量 TRAIN、B32、3M、A1、PMA、优化器、clip、step_overhead 和首32/1M/2M/3M保存策略保持。新输出及日志位于本研究NFS目录，不向主线结果表写入。

## T0 复用的描述性基线

已有B3的CYP行直接来自 `results/p_recipe/scores.csv` 中该resumed运行的3M条目；原单位VAL来自 `results/p_recipe/training/fixed_20261115_provisional_B_20261116_round2_B3_5090_resumed_20261117/VAL_original_units_3000000.csv`。109个字段的MAE、观察数和单位以及以下4条CYP记录已原样整理为 `results/p_heads/T/T0_B3_descriptions.json`；没有重评、重算或增加bootstrap。

| 读出 | CYP任务 | 原误差 | 相对随机参考的score（只报告） |
| --- | --- | ---: | ---: |
| R1 | 3A4 | 0.4 | 0.41666666666666663 |
| R1 | 2D6 | 0.5769230769230769 | 0.06250000000000014 |
| R3 | 3A4 | 0.4285714285714286 | 0.28571428571428564 |
| R3 | 2D6 | 0.5769230769230769 | 0.06250000000000014 |

新训练完成后，逐字段VAL直接取本线已有生产者 `CONTROL/runtime/results/p_recipe/training/<run>/VAL_original_units_3000000.csv`；CYP取 `CONTROL/scores.csv`，不重新读出或拟合。CYP始终排除在七任务主分之外。完整逐字段数表随上述小JSON及新臂对应描述表交付，不另写评价协议。

## T3 PMA 均匀权重

新增 `p_recipe.pma_uniform_weights`，默认关闭。仅将 PMA 从原子读取信息的 cross-attention 权重改为每个有效原子 1/N；padding为0。PMA 后续 query self-attention、残差、FFN、sum分支和所有参数保持原结构；不删除q/k投影。因此参数量与 B3 完全一致。下游仍读编码器H0。既有577维z由8×64维query块、64维sigmoid门控求和及1维logN组成；T3仅均匀query→atom softmax，64维门控求和与logN完整保留，门控分支仍可依据原子特征加权。

生产者新逻辑单元测试在 compute-0-20 通过2项：有效原子均匀参考（atol1e-6、rtol1e-5）；padding替换为1e8后结果逐位一致；参数数量一致；默认关闭/显式False与原softmax公式逐位一致；相同state dict严格加载。实际 B3 完整 ModuleDict(structural,pd) 也已在CPU strict加载通过，clock为3M样本、93,750更新，见 `results/p_heads/T/B3_checkpoint_loading.json`。这证明对照可复用，不构成新臂科学结果。

T3首次启动4535405在0样本、0更新时因冻结源缺Git身份元数据退出，原输出保留。身份元数据已修复，冻结可执行源码T3_source未改。当前正式attempt2真实作业4535476已在node0/3090运行，常规生产者已提交32、64样本及首32完整检查点；没有重读CP内容。此前未运行的资源等待队列已取消，无训练样本重跑。当前3M训练检查点已发布，原流程下游评价待完成（见下段最终里程碑）。

一次运行资源事实观察保存在 `results/p_heads/T/T3_resources_4535476.json`：真实主Python PID3481447、GPU UUID `GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332`，CUDA_VISIBLE与nvidia-smi实际GPU上下文均匹配。Slurm分配15CPU，CPU_IDs与主进程实际mask均为 `16-23,39-45`，所观测后代的mask均受其约束。配置workers=14未改；现场实际4个reader属于现有4批prefetch和spawn池按需创建，未强行增建worker，也未增加训练门或benchmark。早期最近500更新普通日志窗口曾一次估计46.5823样本/秒，后续未重复测速。

T3自身的既定裁剪阈值现已由训练生产者冻结：初始clip=281.7，按optimizer_step_start使用60,000–150,000样本窗口的2,813次裁剪前梯度范数，quantile=0.99，得到p99 **35.02704330444336**。完整B32批次使实际冻结点为150,016样本；fitted=true，此后按原协议固定至3M结束。

以上数值唯一读取生产者已有 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T3_seed0_attempt2/clip_calibration.json` 后直接记入本报告，未重新计算p99、未加检查点、未调参或改变正在运行的训练。
T3第一个常规1M里程碑已由生产者发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T3_seed0_attempt2/samples_1000000.pt`，230,472,905字节，文件mtime为2026-11-17 19:56:56.545488 CST。本线在约20:51的常规状态检查中首次观察到该产物；原publish_checkpoint使用临时文件完整保存/fsync后发布最终.pt名称，本次仅记录最终文件存在、大小及mtime，没有读取CP内容、作中间几何或额外评价。现场squeue确认4535476仍RUNNING/compute-0-0，4535630仍RUNNING/compute-0-20；两臂3M检查点及既有readout/scores.json尚未发布。该1M保存是原配置既定里程碑，没有新增训练或保存点。

T3既定2M里程碑已发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T3_seed0_attempt2/samples_2000000.pt`，230,475,145字节，LastWriteTime为2026-11-18 00:22:28 CST（协调窗口通过live X:/观察，Windows显示为秒精度）。本次直接引用该唯一生产者元数据，不重复读取同CP或解析其内容，不做中间几何、额外评价或测速。同期既有普通日志已达T3 2,044,800样本／63,900更新，T2 848,000样本／26,500更新；T3最终3M及readout、T2首1M当时尚未发布。原SSH会话失效且新连接暂被拒绝，尚未核实终态；文件日志仍live可读，连接失败不作为训练失败或重启依据，两条既有任务均不作操作。
T3最终3M检查点现已由原生产者发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T3_seed0_attempt2/samples_3000000.pt`，230,477,385字节，mtime=2026-11-18 04:31:25 CST（秒精度）。协调窗口04:33通过live X:/唯一观察最终元数据，本报告仅引用，不重复读取该文件或解析CP体。训练已达到3M，原4535476继续既定末尾流程与自动R1/R3，完整评价尚待完成；这不提前等同于全部任务完成或质量判定。根窗口已通知H并协调仅最终点的第6层几何，不补中间点。

后续仅在原 `readout/scores.json` 完整产出后，协调窗口运行既有t_decide，以实际T3 canonical配置和原B3配置作1000条既有配对bootstrap差值判定；没有新增bootstrap、评价或更换CURRENT_BEST基底。只有R3原门槛实际触发时才生成T3_seed1及共享B3_seed1配置。CYP直接取CONTROL/scores.csv，原单位VAL直接取CONTROL/runtime/results/p_recipe/training/p_heads_T3_seed0_attempt2/VAL_original_units_3000000.csv，不重评或重算。
## T3 seed0完成与条件补跑

T3原4535476已真实COMPLETED／0:0，Elapsed13:33:29、15CPU，原R1/R3及readout/scores.json完整发布。协调窗口唯一提交既有判定入口4535773；以下直接引用其生产者 `results/p_heads/T/T3_deltas.json`，未再运行判定或重算配对区间，对照始终为原B3。

| 读出 | T3 score | B3 score | 配对Δ | 原95%CI | seed0规则结果 |
| --- | ---: | ---: | ---: | --- | --- |
| R1 | 0.3174702599368024 | 0.3142474985239394 | 0.0032227614128629845 | [-0.008731332850063315, 0.014110362564626137] | 未达单种子门槛，单独报告 |
| R3 | 0.4524899548750453 | 0.47450343188220573 | -0.022013477007160442 | [-0.032053393575519645, -0.012058970924839008] | SEED1_REQUIRED |

R3区间虽全负，|Δ|仍小于预注册0.06，不能据此提前判负；当前也不能把T3视为最终“≈B3”。实际R3规则已触发T3 seed1及本线共享一次B3 seed1，4535773已生成 `configs/p_heads/T/T3_seed1.json` 和 `configs/p_heads/T/B3_seed1.json`，由根窗口统一冻结/调度，本窗口未独立补算或提交。当前对照不换CURRENT_BEST，也不触发T2确认。R1不触发额外补跑。最终胜/负/平等待两种子按原规则判定；CYP与原单位VAL仅整理现成生产者记录，另附完整JSON/Markdown字段表。
原R3条件补跑现已实际提交两条独立PENDING／0秒队列：T3 seed1为4535777／node6／15CPU／nice10000，afterok高优配方线C3作业4535189，采用同3090类型；共享一次B3 seed1为4535778／node20／15CPU／nice10000，afterok原T2作业4535630，暂排其4090_20a（UUID前缀8bfd2ba3）。两独立源由4535776／compute16／1CPU冻结完成（COMPLETED／0:0，20秒），绑定d8dce41；旧resume、attempt、UUID等迁移键均已清理，两条都是seed1从头3M，不复用旧优化器或采样状态。

根窗口已在实际node6/node20目标完成根盘字节／inode、NFS与UID配额guard；此处只转录已提交句柄，不将PENDING当启动。node0虽释放T3卡，但仍DRAIN／Kill task failed，不自行undrain或伪造Slurm分配。更高优先GPU需求仍优先，两条未开始候选槽可由协调窗口让出或调整；B3 seed1的20a只是暂排，T2接近结束前须再核配方线C3快卡需求，不能抢占更高线。已在跑的任务不迁移、不停止，本窗口没有提交或操作任何队列。
此前T3 seed1队列4535777由根确认PENDING／0秒后hold为JobHeldUser，作为一次可恢复的资源让行：配方线C3 ready迁往快卡后，node6实际槽位优先留给较早已启动并等待续训的Dprime，避免本线占满全部后续卡。四仓共享STATUS已记录；若Dprime已在其他卡获得资源或这次让行完成，根应release或改排T3 seed1到首个合规槽位。不添加科学结果依赖，不改配置、种子或3M预算。共享B3 seed1的4535778仍暂排T2结束后的20a，T2临终前再核更高优先配方需求；四条已在跑T1/T2/T4/T5保持不变。本窗口未再查询身份、CP、p99或速率，也未操作队列。
约09:55，一次资源让行已结束：followup共享STATUS发布Dprime已在node20b从5,760样本完整状态原生续训，并有真实standby4535831等待16CPU；这里只引用已发布事实，不重新观察其身份或状态。根再次确认本线T3 seed1 4535777仍PENDING／0秒后，scontrol release成功。当前为PENDING／Dependency（原afterok4535189），不再人工hold；node6／15CPU／nice10000、配置和seed1均未改动，C3优先保留，没有新增科学依赖。实际compute20 guard已返回T3_QUEUE_RELEASE_NOTICE_GUARD_OK／EXIT0，四处STATUS已通知。本线四条live及共享B3 seed1暂排T2后20a均不变，T2临结束前仍须复核更高线快卡需求。本次仅文档恢复队列事实，无源码/科学变化或额外观察。
约12:00，共享B3 seed1的4535778由根确认仍PENDING／0:00后scontrol hold成功，当前JobHeldUser。原因仅为用户资源顺序和最新owner更正：Dprime接管后无即时完整SAVE_AND_EXIT钩子，20b不能当作随时可让给C3的卡，因此T2完整结束释放20a时不能被本线B3候选自动抢占。四处STATUS已通知C3 owner，其原运行不由本线改动；C3实际取卡或明确不准备用该slot后，根恢复或改排B3 seed1，保持已触发补跑必做，不以其他臂的科学结果设置门槛。T3 seed1的4535777已解除此前hold，仍原afterok4535189依赖等待；四条live继续，CPU后处理4535833及HCPU4536097不占GPU照常。实际compute20的C3_PRIORITY_NOTICE_GUARD_OK／EXIT0已通过，容量保护合法；本次只更新资源文档，无源码、配置、CP、阈值、身份或测速访问。
T3的既有CYP四条与109个原单位VAL字段已由CPU整理任务4535774直接转录为 `results/p_heads/T/T3_descriptions.json` 和 [T3_FIELDS.md](T3_FIELDS.md)。CYP的R1 3A4／2D6 score分别0.4583333333333333／0.18750000000000006，R3分别0.19047619047619035／0.25；四行全部excluded_from_mean=true，不进入七任务主分。完整原误差、随机参考误差及109字段MAE／观察数／单位保留在附表，未重新评价、拟合、bootstrap或计算MAE，没有新增CSV入Git。既有判定任务4535773已确认COMPLETED／0:0、7秒；最终点几何4535770也已COMPLETED／0:0、13:21，具体H数值由独立H报告交付。当前T3仍待条件seed1最终判定，未由几何或CYP改判。
## 全部新开关关闭的整模型对照

任务开始前的9d66cf3原模块与当前实现由独立进程加载，PYTHONPATH分别指向隔离的old/new源码；相同seed19、相同输入，以512维轻量合成编码器调用完整V31PDModel.predict。B3既有PMA与grouped_fields原执行路径开启，全部本任务新开关关闭/为空。molecule标量、atom标量、pair、atom vector、dipole x/y/z、下游H0及577维PMA z全部逐位torch.equal。此项是任务书明确要求的整模型off路径测试，不代替此前真实B3 state strict加载；没有重新读取真实B3 checkpoint，没有训练或benchmark。

工具 `tools/p_heads/t_test_model_off.py` 和一次生产者结果 `results/p_heads/T/model_off_path.json` 保留，原始golden/current源码及张量在本线NFS控制目录。该项由协调窗口在compute-0-20唯一执行并PASS，未重复此前单元测试。

## T1 原子注意力解码器

新增默认关闭 `p_recipe.atom_attention_decoder`。分子内8头注意力，q/k/v为512→256且无偏置，输出256→512；两个LayerNorm、512→512→512 SiLU FFN，两残差输出层零初始化。仅原子标量和pair头读解码结果，分子标量仍从原始H0经PMA、向量头保持原路径。既有grouped_fields执行开关保留，仅为对应桶传入解码原子特征。

新增逻辑在 compute-0-20 共3项测试通过：零初始化逐位identity和分子隔离；原grouped pair路径与逐头参考（atol1e-6、rtol1e-5）；失败头回退原H0路由。后者使用可选 `atom_decoder_fields` 列表，在grouped桶中区分是否读取解码表示，避免未通过验收的头继续收到新表示。单元测试不代替真实头部验收。

旧64 TRAIN／冻结B3的2000步验收45头均未通过，该事实与逐头表保留。用户已明确该验收不适用于T1并授权取消gate：当前T1改为M2基底、全部45字段、从头3M，不再按此历史结果记当前臂缺失。

## T1当前正式训练：M2基底原生启动与完整Slurm接管

用户直接训练授权现已实际执行。新T1_hybrid_source绑定18e4043，由CPU冻结4535729完成（COMPLETED/0:0，10秒）；旧0d04c40三个源保留。协调窗口完成prepare、native、真实held sbatch、register和release，原生node22 wrapper PID18807、真实worker PID18810；standby为真实4535733，根初始观测PENDING／0秒／ReqNodeNotAvail。该standby句柄不是原生worker的Slurm分配，两者不混写。基底为启动前已核CURRENT_BEST中的M2，全量TRAIN／B32／全部45字段／seed0／从头3M，未重复逐头验收。

本线唯一实际资源观察见 `results/p_heads/T/T1_resources_native_18810.json`。worker UID1278、start_ticks5372205、PGID18810、PPID18807与原生记录一致，实际亲和性为0–14共15核；现场实际2个按需spawn reader及全部所观测后代均受此mask约束，workers14上限未改。native_affinity_only=true，环境中实际没有SLURM_JOB_ID；这不是Slurm CPU分配声明。CUDA_VISIBLE与nvidia-smi的真实worker上下文均匹配node22／5090 UUID GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef。

既有生产者losses首条记录为32样本、1更新、total=7.489604473114014、preclip_norm=96.15419006347656、lr=1.6e-7、seconds=14.942423879998387。这表明原生训练已完成首个优化器更新，不是仅初始化。T1按原M2配置没有首32保存要求，本次未要求或读取首32CP，也未增加硬gate、benchmark或训练操作。

T1首个普通日志稳态估计由协调窗口唯一计算：actual_run=p_heads_T1_seed0，窗口从332更新／10,624样本到832更新／26,624样本，500次更新共16,000样本、337.9894569340031秒，速率47.33875472075513样本/秒。按此早期窗口和已有日志时间，3M训练更新ETA为2026-11-18 18:48:46 CST，不含未来固定VAL及最终R1/R3读出额外耗时；估计可变，不代表全程平均速度。此前569更新时仅记录窗口不足，未估算速率；本次未新增测速或读取CP，不因较早估计慢而调参、诊断扫描或停训。该窗口记录时尚未到自身150,016样本处p99冻结；其后实际冻结结果见下段，不重读其他臂阈值或反复估计该速率窗口。
T1自身p99现已由原训练生产者冻结。02:22后沿task的真实configuration读取canonical配置，actual_run仍为p_heads_T1_seed0，actual_output仍为 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T1_seed0`，当次尚无handoff_state文件。仅从该实际输出下已发布的 `clip_calibration.json` 唯一读取：initial_clip=281.7，window_start_samples=60,000，calibration_samples=150,000，sample_axis=optimizer_step_start，observed_updates=2,813，quantile=0.99，threshold=**36.04056640625**，fitted=true，effective_freeze_samples=150,016。此后按原协议固定至3M；未重算p99、另行测速、复观资源、读取CP或要求首32保存。
05:14出现T1 standby基础设施失败：4535733 FAILED／1:0、2秒、15CPU，原scheduled_run.handoff经execution_ledger.write创建 `CONTROL/control/p_heads_T1_seed0_request.json.tmp.23335` 时因control父目录不存在报FileNotFoundError。唯一请求尚未发布、无handoff_state，原native18810仍在运行，训练不停止、不重启。协调窗口已在实际node22 guard后mkdir自有control目录，并以cp -n保留首次失败日志T1_takeover_4535733_attempt1_failed.log。requeue同4535733返回Invalid job id，因该旧job已从controller清除；sacct原FAILED／1:0／2秒证据保留。这仍只有一次实际standby失败，不是第二次训练运行，原native18810继续、无SAVE_AND_EXIT或handoff_state。本窗口未操作live路径/句柄或旧冻结源。当前仓库为未来prepare补充owned request/ack路径验证与guard后父目录创建；同时提供显式--replace-terminal-job OLD，在实核旧绑定终态或明确缺失、新held job同节点真实ID、原生身份仍匹配且未请求接管后才替换，并在账本保留旧ID与终态观察。新缺目录与新替换逻辑两个必要case已由实际CPU1任务4535780完成（COMPLETED／0:0，6秒，2tests／0.029秒），旧3项mock未重复；本线累计28项新逻辑/兼容测试通过。根已提交e91675e修复并held提交新4535781，由当前repo显式替换4535733绑定成功后release，takeover仍使用旧冻结18e源码。
T1现已完成真实完整交接，事实保存在 `results/p_heads/T/T1_handoff_4535781.json`。原native18810及原已知后代、原18810进程组均已无活worker，原生记录COMPLETED／exit_code0／worker_tree_exited=true；唯一request/ACK的request_id和真实job4535781一致，ACK clock与handoff_state均为809,696样本，来源为原native输出的samples_809696.pt。原18810 CUDA上下文已消失，来源18e可执行代码未改，不从0重启，不回退已提交样本。

新真实4535781 RUNNING／compute-0-22／15CPU，worker PID24035、UID1278、start_ticks6883839、PGID24035、PPID24023，Slurm CPU_IDs及实际主mask均0–14；实际4个lazy reader及所有观测后代同受该mask约束，workers14不变。环境真实SLURM_JOB_ID=4535781，CUDA_VISIBLE与真实GPU上下文均匹配GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef。/proc/24035/fdinfo/3明确记录同UUID文件的FLOCK ADVISORY WRITE 24035，证明旧源释放后新worker持有唯一UUID锁，没有叠加外层锁。

新输出的生产者configuration明确resume=原samples_809696.pt、resume_samples=809696；首条恢复日志为809,728样本／25,304更新、total=0.043533697724342346、preclip_norm=3.9273345470428467、lr=0.0002543836964988362，seconds=15109.038924951994，确认接续而非重置。canonical配置仍为configs/p_heads/T/T1_seed0.json，actual_run/output现为p_heads_T1_seed0_sbatch及CONTROL/training/p_heads_T1_seed0_sbatch，最终判定据该配置实际output取结果。此次只收集原子交接元数据及首条自然日志，不读取CP体、重算p99/500更新速率或再次训练；原失败4535733保留为一次基础设施失败，不能把修复requeue无效计作训练重启。
T1首个既定1M检查点已在接管后的实际输出发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T1_seed0_sbatch/samples_1000000.pt`，244,689,549字节，mtime=2026-11-18 06:23:28.655838 CST（原epoch1794954208.6558381）。协调窗口约06:33唯一读取生产者进度/元数据，actual_run=p_heads_T1_seed0_sbatch，普通日志已达1,031,520样本／32,235更新；本报告只转录已提供事实，没有重读产物或CP体。此为原配置的1M里程碑，尚未最终3M，没有新增评价或中间几何；原先唯一ETA和已冻结阈值保持，不另计算。写入前由协调窗口83200在实际compute20 relay共享guard成功（T1_1M_WRITE_GUARD_OK／EXIT0），磁盘、inode、UID配额及并发保护继续。
T1首次2M里程碑已在实际canonical输出发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T1_seed0_sbatch/samples_2000000.pt`，244,691,853字节，mtime=2026-11-18 11:05:12.262865 CST（原epoch1794971112.2628648）。根11:27唯一观察时，actual_run=p_heads_T1_seed0_sbatch，自然日志2,077,472样本／64,921更新，actualcompute20 guard返回PROGRESS_GUARD_OK／EXIT0；本报告只转录已提供元数据，不重读CP、阈值、身份或旧窗口。依据已记录1M 06:23:28→2M 11:05:12的真实检查点节奏，3M训练更新运行规划现调整为11月18日约16时，固定VAL/最终读出另计、估计可变；原启动500更新窗口47.33875472075513/s及旧18:48:46估计保留为历史，不重新测速，不改科学参数。T2接近3M，仍按原约13–14时规划，另计验证与读出，不增加测速。

当前资源约束按owner发布更正：Dprime已正式由Slurm4535831运行，接管后没有即时SAVE_AND_EXIT钩子，不能把node20b当作随时可迁出让卡。配方线C3仍获下一合规快卡优先；共享B3 seed1虽暂排T2结束后20a，T2临终前必须再与更高线核实实际卡需求，不能把暂排解释成卡承诺或假设可即时迁移Dprime。四条live训练保持，未操作任何作业。
T1实际最终3M训练检查点已发布：canonical run=p_heads_T1_seed0_sbatch，`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T1_seed0_sbatch/samples_3000000.pt`，244,694,093字节，mtime=2026-11-18 15:46:45.768024 CST（原epoch1794988005.768024）。根15:53首次读取该元数据，当时原4535781仍RUNNING／10:28:53，原VAL/R1/R3尚未成功终态；训练3M发布不等同于整体C0、原评价或最终判定完成。post4535834及HCPU4536173仍依赖parent成功，本窗口不读取分数或描述性产物，不重评、测速、读取CP体或旧数字；等待根确认真实post成功后才一次消费T1_deltas/descriptions。写前actualcompute20 T1_FINAL_CP_GUARD_OK／EXIT0已通过，采用训练里程碑与完整后处理两阶段推送。

当前新增3090低显存共用统一口径仍待用户答复：node7/node6存在gmx上下文；node0由外部恢复IDLE后实测仍有gmx约266MiB，后来又被gmx分配48CPU，不能因历史IDLE或低显存视作合规空卡。当时共享B3 4535778与T3 seed1 4535777两条PENDING／0秒均hold（之后B3已改排实际RUNNING4536238，见下段）；该最新状态覆盖此前T3已解除一次让行hold的历史。20a继续按用户已明确“C3会立即使用”保留，与本次3090共用提问不同，不动其他任务；T2 seed1仍暂排perf后。本窗口只引用根给出的资源事实，没有重新查询身份或资源。
后续接管由原协议将实际run/output写回task的configuration路径；最终t_decide读取这份canonical配置，再从其实际output/readout/scores.json取candidate。不会猜测旧native输出目录；M2对照与外部seed1绑定随原配置保留。最终3M产出时才向H交付准确CP路径补第6层几何，中间保存不补几何。
## T2 物理约束头

冻结42,961条面板的唯一一次检查已完成，结果见 `results/p_heads/T/label_constraints.json`。读取原缓存的TRAIN 39,220条和VAL 3,741条，使用原单位raw标签，仅在原mask及全部原子有效的记录上逐记录检验；未更改mask或补齐缺失。阈值为 `max(N×5e-5, 1e-3×Σ|y|)`，通过率门槛99.9%。不把模型训练归一化后的数值用于电荷守恒检查。

| 字段 | 有效记录 | 通过率 | 处理 |
| --- | ---: | ---: | --- |
| r68、r279、r346、r413、r668 电荷 | 各42,961 | 各100% | 启用约束头，复用原验收通过 |
| r210 anion 电荷 | 42,960（缺1） | 100% | 启用约束头，复用原验收通过 |
| r44、r45、r46 PM7 Fukui | 各42,960（各缺1） | 各100% | 原MLP后求和投影，补验收通过 |
| r64 Mulliken | 42,961 | 99.2528107% | 保持原MLP |
| r712 f_minus | 42,932（缺29） | 77.7462033% | 保持原MLP |
| r712 f_plus | 42,932（缺29） | 77.8044349% | 保持原MLP |
| r712 f_radical | 42,932（缺29） | 78.1771173% | 保持原MLP |

面板电荷和的实测整数与预注册一致：anion −1、cation +1，其余0。没有根据结果修改阈值；四个不满足字段按预注册保留MLP，继续其余工作。此检查在T2模型代码实现前完成。

已为上述9个通过字段实现默认关闭的 `p_recipe.physical_constraint_heads`。每个电荷头为512→64→2 SiLU MLP，输出χ和u；J=14.3996+softplus(u)，以14.3996/√(r²+1)构造软化库仑矩阵，逐分子解带Σq=Q约束的(N+1)阶KKT系统。FP64组装、求解，输出转FP32。Fukui头直接包装bank已有512→64→1 SiLU MLP，保留模块、参数对象及原初始化/权重，再按原单位做 `f=s+(1−Σs)/N`，保留负值。

约束只作用于原单位输出；`V31PDModel.output_parameterization`沿用B3的raw，之后由未修改的原 `pd.loss`/`grouped_v31_loss` 应用该字段既有D4/A1变换进入原loss。没有把归一化残差的和强制设成原单位Q。

3项新逻辑CPU测试已通过：Q=−1/0/+1的电荷解与独立NumPy FP64参考比较（atol1e-6、rtol1e-5）且电荷和误差≤1e-6+N×1e-6、反向梯度有限；Fukui投影求和误差≤1e-6且允许负值、梯度有限；自定义约束头在grouped_fields下正确跳过原MLP桶并执行。原64样本验收4535407已完成；其中6个未改电荷头的通过记录继续复用。随后发现Fukui实现未复用原MLP本体，已按任务书修正；原3个Fukui通过记录被替代；新实现已用相同64 TRAIN、冻结B3和固定优化器补验收通过，正式3M待资源协调启动。

## 逐头真实验收方法

`tools/p_heads/t_accept_heads.py`使用实际B3 loader在同一全量TRAIN清单中固定取64个分子及其第一个允许构象。加载真实B3完整状态，冻结编码器，缓存两个32样本批次的H0；只为当前臂的新头及对应atom/pair MLP开放梯度，其余参数固定。T1的初始loss来自B3已有atom/pair MLP与新增零初始化decoder；这些MLP可随新decoder一起更新，没有为验收另行重置。T2六个电荷头的初始loss来自新初始化物理头；修正后的三项Fukui补验收保留B3原MLP初始权重，追加原单位投影。采用固定AdamW lr0.003、weight_decay0，不做超参数搜索。每个头以实际原loss为初值，首次降至初值1%以下即通过；最多2000次更新，同时受单项4小时限制。未观察到有效标签的头记录为未验收，不视作通过。

T1按通过头列表选择解码器路由，失败头读原H0；T2只保留通过真实验收的物理约束头，失败字段恢复原MLP。验收只更新本任务配置，不修改主线、标签或mask。运行入口先取得共享UUID锁，再核实实际显存准入，写入受NFS磁盘guard/watchdog保护。T1真实验收已完成且按规则记录缺失；T2六个电荷头原真实验收已通过；三项Fukui在修正原MLP复用后由4535600完成独立补验收，按首次达标锁存规则3/3通过。若固定初始化与预算下不达标，则按预注册保守记为UNRESOLVED/回退；这不证明架构本身必然无效。不会依据中途结果重置、调参或重复验收。全无通过的臂记为缺失，不启动与T0等同的重复3M；部分通过则明确报告实际作用的头列表。

## T1正式seed0完成与M2对照结果

T1实际canonical run=p_heads_T1_seed0_sbatch，原4535781已COMPLETED／0:0，Elapsed10:39:20、15CPU；这是Slurm接管段，先前native段独立lineage已保留，本次不叠加或重复核算GPU重叠。post4535834在node20／CPU1／CUDA空完成COMPLETED／0:0／9秒，一次执行原判定及描述转录。本报告只消费该新正式producer T1_deltas/T1_descriptions及现成score摘要，未独立bootstrap、复算MAE、读取CP或重跑旧验收。

| 读出 | T1 score | M2 score | 配对Δ | 原95%CI | seed0规则结果 |
| --- | ---: | ---: | ---: | --- | --- |
| R1 | 0.29856994797497977 | 0.2974547347686018 | 0.001115213206377974 | [-0.010517873819686894, 0.013809469597857244] | 未达单种子门槛，单独报告 |
| R3 | 0.47225381237562564 | 0.4680026331456454 | 0.004251179229980251 | [-0.007078817581392126, 0.014793625130516982] | SEED1_REQUIRED |

R3效应未达|Δ|≥0.06且区间跨0，正式触发本臂seed1；不提前判胜负、两seed或机制结论。producer requested_configurations仅T1_seed1.json，没有创建本线M2或B3对照。该新canonical配置已生成：M2（A1+B3+B4，原gamma0.1597693323500406）加全部45 decoder字段，seed=1、3M/B32/micro32/workers14，run=p_heads_T1_seed1、fresh CONTROL/training/p_heads_T1_seed1、独立request/ack；无resume／resume_samples／resume_from_output／attempt／旧GPU限定。保留原M2 checkpoint_samples=[1M,2M,3M]且不显式新增step_overhead，不加首32CP。后续首32实际loss后资源事实应使用真实proc/native或Slurm方法，不能硬套要求首32CP的观察入口。

外部配方M2 seed1 4535736已由根确认完整成功C0；本轮没有读取其分数或提前比较。T1_deltas中reference_seed1_configuration=null及external_reference_pending=true仅说明本次post未显式绑定外部配置，不能解读为外部训练未完成，也不为清除此flag重跑seed0。待本臂seed1真实完整3M、R1/R3及成功终态后，由根传入已发布绝对M2 seed1配置路径一次组合；不新跑自有M2 seed1，不在当前阶段组合。

T1的现成描述性输出为 `results/p_heads/T/T1_descriptions.json` 及 [T1_FIELDS.md](T1_FIELDS.md)，CYP4条、原单位VAL109字段；CYP R1 3A4／2D6 score=0.41666666666666663／0.12500000000000008，R3=0.42857142857142855／-0.06249999999999996，四行全excluded_from_mean=true。原误差、参考误差及109字段MAE／观察数／单位均来自原生产者，无重新计算。HCPU4536173已RUNNING／4CPU，未读取其未完成统计。本轮只更新文档/字段附表引用，seed1冻结、候选资源与提交均由根协调，C3保留及3090共用待答安排不变。
## T1历史验收：UNRESOLVED／缺失（已被用户直接训练授权覆盖）

真实作业4535406在compute-0-0 COMPLETED/0:0，耗时00:20:51；完整执行2000次更新，64个实际TRAIN分子，45个头均有有效标签，无未见字段。没有头达到相对于本次固定初始loss的1%门槛。当时所有头按原MLP/H0回退并记缺失；这些仅为旧决策。当前配置已按用户新指示启用全部45字段，并以M2为基底从头3M；需要时复用外部M2 seed1对照。

T1初值来自B3已有MLP与零初始化decoder，本次没有重置旧MLP；只有新头与对应MLP参与更新，编码器冻结。末loss相对初值确有变化（不是因0通过便判定路径恒定），但固定初始化、优化器和2000步预算下均未达到门槛。该结果只支持“当前验收设置下未通过”，不能推论注意力解码器架构必然无效；未调参或重跑。

以下逐头初末loss及ratio直接抄录生产者T1_acceptance.json，均为实际训练使用的原loss，不重新计算。旧验收通过名单为空；当前45字段路由由用户直接训练授权确定。

| 头 | 初始loss | 最终loss | 最终/初始 | 通过 |
| --- | ---: | ---: | ---: | --- |
| P.pm7_anion.r190.p | 0.0001700751382 | 0.0004372421245 | 2.570876197 | 否 |
| P.pm7_anion.r190.s | 0.0006593272265 | 0.001400020032 | 2.123406975 | 否 |
| P.pm7_anion.r210.value | 0.00452218065 | 0.002884426969 | 0.637839837 | 否 |
| P.pm7_B.r39.p | 4.591402467E-05 | 0.0001396447042 | 3.041438976 | 否 |
| P.pm7_B.r39.s | 0.0001881725257 | 0.0008174880932 | 4.344354152 | 否 |
| P.pm7_B.r40.value | 0.0001152633668 | 0.001186786569 | 10.29630317 | 否 |
| P.pm7_B.r44.value | 0.07126883231 | 0.03791300766 | 0.5319717811 | 否 |
| P.pm7_B.r45.value | 0.07166172564 | 0.0460325107 | 0.6423583899 | 否 |
| P.pm7_B.r46.value | 0.06880665012 | 0.04430373944 | 0.6438874639 | 否 |
| P.pm7_B.r55.electron_electron | 0.0001626400772 | 0.0003416696854 | 2.100771786 | 否 |
| P.pm7_B.r55.electron_nuclear | 0.0002804663818 | 0.0003845540487 | 1.371123506 | 否 |
| P.pm7_B.r55.total | 0.0002244468051 | 0.0002995394025 | 1.33456746 | 否 |
| P.pm7_B.r56.C | 0.0003616753675 | 0.004097381374 | 11.32889254 | 否 |
| P.pm7_B.r56.EE | 0.0002246708464 | 0.0006620849308 | 2.946910743 | 否 |
| P.pm7_B.r56.EN | 0.0006920986925 | 0.00213892106 | 3.090485624 | 否 |
| P.pm7_B.r56.J | 4.66582751E-05 | 0.001126786345 | 24.14976427 | 否 |
| P.pm7_B.r56.K | 6.393914555E-05 | 0.001068231126 | 16.7069972 | 否 |
| P.pm7_B.r56.NN | 0.0005192274111 | 0.001906480116 | 3.67176323 | 否 |
| P.pm7_B.r56.total | 0.0001059506722 | 0.002503774944 | 23.63151543 | 否 |
| P.pm7_B.r64.value | 0.001851714042 | 0.001060257724 | 0.5725817811 | 否 |
| P.pm7_B.r65.value | 0.001101626316 | 0.001633685722 | 1.482976304 | 否 |
| P.pm7_B.r68.value | 0.001078156143 | 0.001339838665 | 1.24271301 | 否 |
| P.pm7_B.r73.value.pi | 0.03111409955 | 0.02344064275 | 0.7533768642 | 否 |
| P.pm7_B.r73.value.sigma | 0.042073505 | 0.03593398631 | 0.8540763672 | 否 |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.09881448373 | 0.02282437496 | 0.2309820797 | 否 |
| P.pm7_B.r82.De | 0.09685233608 | 0.03420894593 | 0.353207236 | 否 |
| P.pm7_B.r82.Dn | 0.05662492476 | 0.01642059721 | 0.289988857 | 否 |
| P.pm7_B.r84.value | 4.455448106E-05 | 0.0005520522536 | 12.39049901 | 否 |
| P.pm7_cation.r259.p | 0.0002221342293 | 0.0003398661211 | 1.530003378 | 否 |
| P.pm7_cation.r259.s | 0.0006431043439 | 0.001657564251 | 2.577442163 | 否 |
| P.pm7_cation.r279.value | 0.007008286892 | 0.003820560407 | 0.5451489738 | 否 |
| P.pm7_octanol.r326.p | 4.519825961E-05 | 0.0002384700565 | 5.276089357 | 否 |
| P.pm7_octanol.r326.s | 0.000178987153 | 0.0007013895956 | 3.918658874 | 否 |
| P.pm7_octanol.r346.value | 0.0009852779331 | 0.001233060146 | 1.251484586 | 否 |
| P.pm7_water.r393.p | 4.700234967E-05 | 0.000139249576 | 2.962608827 | 否 |
| P.pm7_water.r393.s | 0.0001679458001 | 0.0008224724734 | 4.897249429 | 否 |
| P.pm7_water.r413.value | 0.0009713245672 | 0.001092219492 | 1.124463984 | 否 |
| P.xtb_fod.r537.value | 0.0119889765 | 0.01336311642 | 1.11461695 | 否 |
| P.xtb_singlepoint.r666.value | 0.0002334866076 | 0.000705418759 | 3.021238632 | 否 |
| P.xtb_singlepoint.r667.value | 0.0001272950649 | 0.000582381268 | 4.575049854 | 否 |
| P.xtb_singlepoint.r668.value | 0.001113562495 | 0.001644470845 | 1.476765653 | 否 |
| P.xtb_singlepoint.r677.value | 0.0003337349335 | 0.001879144285 | 5.630649047 | 否 |
| P.xtb_vfukui.r712.f_minus | 0.01345691318 | 0.0147783556 | 1.098198035 | 否 |
| P.xtb_vfukui.r712.f_plus | 0.01636770833 | 0.01597713446 | 0.9761375348 | 否 |
| P.xtb_vfukui.r712.f_radical | 0.009039754514 | 0.009552853648 | 1.056760295 | 否 |

## T2验收记录与Fukui实现修正

原作业4535407在compute-0-0 COMPLETED/0:0，耗时00:18:59；64个实际TRAIN分子、冻结B3，共1046更新，原实现9/9达到门槛，无未见字段。该原始报告和下表保留。16:34核对任务书“原MLP输出s后投影”发现：旧Fukui头重新创建了另一MLP，并未保留bank原MLP本体及初始化。旧3个Fukui验收记录因此被替代，不能再作为当前实现的验收通过依据；未改变的6个电荷头（r68/r210/r279/r346/r413/r668）原验收继续有效且不重跑。

修复后的FukuiHead直接持有原field_heads模块，只追加既有投影；唯一针对性CPU回归在Slurm4535578/node16/1CPU实际完成（COMPLETED/0:0，8秒，Ran1test OK）：模块/参数对象复用、权重未变，输出逐位等于原MLP后投影。本线新逻辑累计17项通过，未重复旧单测。补验收只选r44/r45/r46，使用原64实际TRAIN、冻结B3、FP32、固定AdamW lr0.003/wd0和≤2000更新，无调参或强求通过；CPU执行不需要GPU准入。实际4535600/node16/2CPU（torch1及guard/IO）COMPLETED/0:0，耗时00:01:49，762次更新、无未见字段，按原首次达标锁存规则3/3通过。新报告单独保存results/p_heads/T/T2_fukui_reuse_acceptance.json，作为当前原MLP包装定义的验收依据；配置只按新补验收处理这3头，完整保留6个未测电荷头。未复跑六电荷或旧projection/KKT测试，未延长、重置或重试补验收。r64及r712三个分量继续保持原MLP。

正式配置configs/p_heads/T/T2_seed0.json现固定启用6电荷与3Fukui，共9头：六电荷复用原验收，三Fukui依据新补验收。正式训练从seed0新建模型/优化器和采样状态，Fukui包装新建bank的原MLP，不加载B3或补验收拟合权重；保持全量TRAIN、B32、3M及B3所有执行键。旧4535453由协调窗口核实held/PENDING、0秒后取消，未产生训练样本；旧T2_source保留不改。修复提交1a23d66的独立T2_source_fukui_fix已由4535599/node16冻结成功（COMPLETED/0:0，8秒，源码16,615,295字节）；资源等待作业4535619由协调窗口确认held/PENDING、0秒后取消，未启动或产生训练样本。当前正式3M真实作业4535630已在node20/15CPU/nice10000运行，无资源依赖；实际4090_20a UUID为GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5。该卡准入现场829/49140MiB（含其他两个gmx上下文，低于30%），节点空余21CPU且实际磁盘/配额guard通过，沿现行混合规则共享；5090高占用不准入。原run/output/config、B32/3M/seed0及冻结源T2_source_fukui_fix/1a23d66均不变，不加载验收权重。启动日志已记录1194228 TRAIN/B32及offline W&B；首32完整检查点及losses首条32样本已由生产者发布；本线唯一资源事实观察已完成，未重读CP内容。T3在跑源及任务完全不动。
T2唯一运行资源事实记录在 `results/p_heads/T/T2_resources_4535630.json`：compute-0-20真实主Python PID54234，Slurm分配及主进程实际mask均为0–14共15核；现场实际3个按需spawn的reader及其余所观测后代均受此mask约束。workers最大14配置保持原样，未强行启动额外reader。CUDA_VISIBLE与nvidia-smi真实GPU上下文均匹配GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5。首32完整CP只确认存在，没有读取内容、benchmark或新增训练门。
T2自身裁剪阈值已由训练生产者冻结：初始clip=281.7，按optimizer_step_start轴取60,000–150,000样本窗口的2,813次裁剪前梯度范数，quantile=0.99，p99为 **33.84247207641602**。实际完整B32冻结点150,016样本，fitted=true，此后按原协议固定至3M。数值只从生产者 `/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T2_seed0/clip_calibration.json` 唯一读取并原样记录；现场4535630仍RUNNING/compute-0-20，未重算p99、另行测速、重复资源身份观察或读取中间CP内容。

T2首个既定1M检查点已由生产者发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T2_seed0/samples_1000000.pt`，232,059,773字节，mtime=2026-11-18 01:24:40.230788355 CST。协调窗口于01:35:41经真实服务器会话唯一stat，本报告仅转录该元数据，没有重查同文件、读取CP内容、测速或补中间几何。当时4535630 RUNNING／6:24:58，普通日志1,030,400样本／32,200更新；T3仍RUNNING／10:29:58，普通日志2,294,400样本／71,700更新，两臂最终3M和readout尚未发布。协调窗口基于实际启动至1M发布的墙钟进度，将T2 3M保存粗略预计为11月18日约13:55，替代早期14:54窗口估计；未来VAL与最终读出另计，估计可变，此处未重算窗口或速率。
T2既定2M检查点已发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T2_seed0/samples_2000000.pt`，232,062,077字节，mtime=2026-11-18 07:04:07.400380 CST（原epoch1794956647.4003797）。协调窗口07:18唯一观察时，T2普通日志已达2,042,496样本／63,828更新；本报告只转录该新元数据，不重读CP或重新验证，不改已有唯一ETA，不作中间几何或评价。同期实际compute20共享guard通过：UID可用452,344,942,592字节，对本次全部预留需求178,103,429,120字节；根盘可用346,131,120,128字节、inode检查通过，其他并发预留及根盘下限保护继续。
T2最终3M训练检查点已由原生产者发布：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/training/p_heads_T2_seed0/samples_3000000.pt`，232,064,317字节，mtime=2026-11-18 13:17:22.831864 CST（原epoch1794979042.8318639）。此刻原4535630仍在既定末尾VAL／R1/R3流程，不能把训练检查点发布当作整体COMPLETED／0:0或提前判定。CPU后处理4535833、HCPU4536097仍等parent成功；本窗口不读CP体、不增加评价或复算任何数值，等待根提供真实终态后才一次消费原T2_deltas及描述性生产者产物。写入前实际compute20 FINAL_CP_WRITE_GUARD_OK已于13:15通过。
下表直接抄录原T2_acceptance.json。通过步是原生产者记录；r44/r45/r46三行仅为被替代的历史记录，六项电荷头继续复用。

| 头 | 初始loss | 最终loss | 最终/初始 | 首次通过更新 |
| --- | ---: | ---: | ---: | ---: |
| P.pm7_anion.r210.value | 0.430469811 | 0.001181915693 | 0.002745641305 | 298 |
| P.pm7_B.r44.value | 0.4986832589 | 0.003650469356 | 0.007320216372 | 905 |
| P.pm7_B.r45.value | 0.5732448995 | 0.004083457636 | 0.00712340858 | 843 |
| P.pm7_B.r46.value | 0.5473314524 | 0.005463474896 | 0.009982022543 | 1046 |
| P.pm7_B.r68.value | 0.430039838 | 0.0004010919511 | 0.0009326855692 | 85 |
| P.pm7_cation.r279.value | 0.4281749725 | 0.001522488368 | 0.003555762167 | 390 |
| P.pm7_octanol.r346.value | 0.4210058004 | 0.0004102118692 | 0.0009743615618 | 80 |
| P.pm7_water.r413.value | 0.4259786308 | 0.000411648216 | 0.0009663588411 | 84 |
| P.xtb_singlepoint.r668.value | 0.3814159185 | 0.0004171170003 | 0.001093601447 | 80 |

## 修正后Fukui补验收终态

以下新值直接引用4535600的生产者T2_fukui_reuse_acceptance.json，替代上表r44/r45/r46三项历史证据。实际冻结源为T2_source_fukui_fix，输入、原单位投影、既有D4/A1与原loss路径保持。首次达标是验收规则；通过后不停止该头，仍随未通过头共同更新，到全部曾通过时结束。

| 原MLP包装头 | 初始loss | 最终loss | 最终/初始 | 首次通过更新 | 按固定规则 |
| --- | ---: | ---: | ---: | ---: | --- |
| P.pm7_B.r44.value | 0.07140423730015755 | 0.0006924213084857911 | 0.009697201940202831 | 762 | 通过 |
| P.pm7_B.r45.value | 0.07157871872186661 | 0.0016877036541700363 | 0.02357828813236998 | 702 | 通过 |
| P.pm7_B.r46.value | 0.06874412153929472 | 0.001373119419440627 | 0.01997519845396141 | 721 | 通过 |

r45/r46的终点ratio分别约2.36%和2.00%，已回升到1%以上；只能表述为三头均曾按规则达标，不能表述为终点三头均低于1%。没有按终点回升延长、重置或重试，也没有改动首次达标锁存规则。头部小样本拟合验收只证明这一固定设置下达到过门槛，不构成正式3M的泛化或质量结论。
## T2 seed0完成与条件补跑

原T2 4535630已真实COMPLETED／0:0，Elapsed18:14:22、15CPU；原自动R1/R3完整结束。后处理4535833先前因16CPU资源不足而PENDING／0秒，仅同job改排gpu分区／node20／1CPU、无CUDA后完成COMPLETED／0:0／6秒，一次顺序执行现有t_decide与描述转录；没有重评、重新bootstrap或重复计算MAE。下表直接抄录生产者 `results/p_heads/T/T2_deltas.json`，现成score摘要给出相同点值，本窗口未再次运行判定或验证数学。

| 读出 | T2 score | B3 score | 配对Δ | 原95%CI | seed0规则结果 |
| --- | ---: | ---: | ---: | --- | --- |
| R1 | 0.3108263615978493 | 0.3142474985239394 | -0.003421136926090085 | [-0.015207643623784359, 0.008744198142949395] | 未达单种子门槛，单独报告 |
| R3 | 0.4669179815594994 | 0.47450343188220573 | -0.007585450322706355 | [-0.016785810164422956, 0.0020004774800213097] | SEED1_REQUIRED |

R3未达|Δ|≥0.06且区间不跨0的单种子直接判定条件，原规则正式触发T2 seed1；当前不判胜／负／平或提前做两种子结论，current_best_confirmation_required=false，不启动CURRENT_BEST确认。已生成canonical `configs/p_heads/T/T2_seed1.json`：arm=T2、seed=1，run=p_heads_T2_seed1，output=CONTROL/training/p_heads_T2_seed1，独立request/ack路径，B3基底与6电荷+3Fukui、3M/B32/workers14均保持；不存在resume／resume_samples／resume_from_output／attempt／required_gpu_uuid迁移键。它是从头新种子配置，本窗口只核对来源与路径，不提交任务或改冻结源。

T2 seed1独立源已实际准备并提交等待：4536169在gpu分区／node20仅CPU1、CUDA空执行冻结，COMPLETED／0:0／15秒；T2_seed1_source绑定4f1a80f，源码16,671,422字节，不是新GPU训练。正式真实队列4536170为gpu分区／node22／15CPU／nice10000，afterok提速任务4535799，使用既有stage43 SM120 Python（/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python），目标GPU前缀9b6008d0；当前PENDING／0秒／Dependency，未记为已启动。perf4535799实际等待T1及外部gmx88任务，依赖仅为物理资源接续，不等科学结果；若其他首个合规空闲卡先到，根只移动尚未启动的队列。5090必须使用兼容SM120环境，不使用旧cu118入口，也不抢用户为C3保留的20a。

T2最终两种子组合判定必须等本臂seed1和唯一共享B3 seed1均真实完成3M、完整R1/R3且成功终态后，才由根一次运行既有组合入口；不提前重跑已完成T2 seed0判定或把PENDING当补跑完成。该次记录时共享B3 4535778仍hold、T3 seed1仍原afterok C3、HCPU4536097仍R／4CPU；后续B3已实际RUNNING4536238，HCPU已完成，见最新阶段及H1报告；四处STATUS已发布，既有live保持。本文只引用根提供的新source／handle元数据，没有读取任何旧产物、数值或身份，源码/科学配置不变。
共享对照直接复用已存在的 `configs/p_heads/T/B3_seed1.json`，run仍p_heads_B3_seed1、seed=1、fresh CONTROL/training/p_heads_B3_seed1，不另建第二条B3。该对照尚未跑完，不能据此提前完成两seed判定；4535778仍为C3优先/readiness安排而hold，此前问题未答不构成数据科学门；现用户已明确C3立即使用，优先保留快卡。HCPU4536097正在运行／4CPU，尚未读取或引用其未完统计。

T2现成描述性产物为 `results/p_heads/T/T2_descriptions.json` 及 [T2_FIELDS.md](T2_FIELDS.md)：4条CYP、109个原单位VAL字段。CYP的R1 3A4／2D6 score为0.37499999999999994／0.31249999999999994，R3为0.238095238095238／0.18750000000000006，四条全部excluded_from_mean=true，不进入七任务主分；原误差、参考误差与完整109字段MAE/观察数/单位由后处理直接转录。本窗口只读已发布JSON/score摘要及核对附表存在，没有读取原CSV、CP或H未完统计。
## T5 seed0完成与条件补跑

根18:00:59权威sacct已确认原T5 4535747 COMPLETED／0:0／13:08:45／15CPU，post4535836 COMPLETED／0:0／7秒／CPU1。本窗口在父和post真实成功后只消费一次新正式T5_deltas、T5_descriptions及现成score摘要，没有独立bootstrap、验证数学、复算MAE、读取旧CP或重跑评价。以下为原判定生产者结果，对照仍为原B3：

| 读出 | T5 score | B3 score | 配对Δ | 原95%CI | seed0规则结果 |
| --- | ---: | ---: | ---: | --- | --- |
| R1 | 0.2648272314420518 | 0.3142474985239394 | -0.049420267081887626 | [-0.06304156716061819, -0.03728776003429126] | 独立报告，不额外触发计算 |
| R3 | 0.45884990727591485 | 0.47450343188220573 | -0.01565352460629088 | [-0.02558674306005184, -0.005034994896060215] | SEED1_REQUIRED |

R3区间虽全负，|Δ|仍未达0.06单种子直接判负门槛，依原R3规则正式触发seed1；R1独立报告，不驱动额外补跑。当前不直接判负、不提前认定“T5≈B3”或“两种子结论”，也不据此采纳简单读出机制解释。最终须本臂seed1与唯一共享B3 seed1都完成3M、完整R1/R3及成功终态后才一次组合。

post已生成 `configs/p_heads/T/T5_seed1.json`：arm=T5／seed=1，fresh run=p_heads_T5_seed1，output=CONTROL/training/p_heads_T5_seed1，B3基底加simple_molecular_readout、3M/B32/micro32/workers14，checkpoint_samples=[32,1M,2M,3M]，独立request/ack路径，没有resume／resume_samples／resume_from_output／attempt／旧GPU迁移键。仍复用已存在且正在4536238运行的唯一B3_seed1配置，不另跑第二baseline。源冻结及候选资源提交由根协调，本窗口未启动训练、分配GPU、改冻结源或重复判定。

原描述性复制已完成，现成 `results/p_heads/T/T5_descriptions.json` 及 [T5_FIELDS.md](T5_FIELDS.md)含CYP4条和VAL109字段。CYP R1 3A4／2D6 score=0.37499999999999994／-0.06249999999999996，R3=0.1428571428571429／0.12500000000000008，四行均excluded_from_mean=true，不进入七任务主分；完整原误差／参考误差／原单位MAE及观察数保留附表。本窗口没有再读原CSV或重新计算这些数值。T5最终几何及既有CPU4方法由Hagent单独交付H1.md，原H4536219负责，本窗口不重复方法、读取或计算其统计；具体终态与成本以H专题记录为准。原预算、训练基底与科学规则保持。
T5 seed1后续资源准备由根在本轮正式结果commit后执行：计划CPU1冻结T5_seed1_source，并暂排node4／15CPU／nice10000／afterany原T4 4535771，只等待同卡资源释放，不依赖T4科学成功。用户此前对T4/T5在node4低显存共用的明确授权持续覆盖本臂seed1，原gmx保持；实际启动仍需真实分配、UUID锁和≤30%显存准入。其他首个合规槽位更早到，根只改未启动候选，不为同型卡等待。新的统一3090共用问题仅影响尚未获覆盖的卡/臂；node5现gmx278MiB，根没有启动新的共用，20a继续保留C3。本次只有配置生成与候选计划事实，没有冻结或提交新训练。
T5 seed1已实际冻结并入真实等待队列：冻结4536258在node20仅CPU1／空CUDA执行，COMPLETED／0:0／9秒；T5_seed1_source@0ababf4，源码16,671,422字节，复制已完成且不受后续源码编辑影响。正式4536260已提交node4／gpu／15CPU／nice10000／cu118，实际UUID为GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6，afterany4535771只等原T4同卡资源、不依其科学成功；根实核PENDING／0秒／15CPU／Dependency，不把等待写成启动。node4的T4/T5低显存共用是持续明确授权，不需等待新的全3090共用提问；实际启动仍须原guard、UUID锁、≤30%准入，gmx保持。其他首个合规槽位先到，根可只改P0。此处仅转录源/队列事实，没有冻结、提交、测试或操作任何训练。
最终组合入口的I/O现复用已发布seed0点值／CI，不重开旧seed0 scores或重新paired；首次无该产物仍按原路径计算一次，只对尚未保存的新seed1调用paired，已保存seed1亦复用，噪声从已存参考点取得。canonical实际seed1路径、T1外部M2绑定以及原公式／阈值／1000条配对draws均未改。唯一新增synthetic行为测试4536261在node20／CPU1／空CUDA／1线程／srun1核与actualguard下COMPLETED／0:0／3秒，1case／0.023秒／OK，证明缓存seed0 CI保留、旧scores不可访问且只计算新seed1；旧2项边界和此前闭合28项没有重跑。现独立新逻辑／兼容测试共29项（原28＋本次1），日志CONTROL/T_decision_reuse_unit_4536261.log。该case仅在独立synthetic临时数据中两次收尾，其COMPLETE_TWO_SEEDS不是真实T5或其他臂结论；所有真实seed1最终结果仍待完整成功后组合。
## 显著性与最终判定（已应用seed0；最终两seed待完成）

所有科学规则以冻结 `configs/p_heads/preregistration.json` 原文为准。T2–T5相对B3，T1相对其绑定的当前最优配方（现M2），以原1000次配对bootstrap求95%CI；R3差≥0.06且下界>0判胜，差≤−0.06且上界<0判负。其他情况触发该臂seed1；T2–T5共享一次B3 seed1，T1复用配方线M2 seed1；最终按两种子CI及预注册平均增益门槛判定。R1独立报告但不触发补跑；CYP及逐字段VAL原单位MAE仅作描述。判定辅助程序已仅用于真实T1/T2/T3/T5 seed0产物，未重复运行；其单种子门槛及两种子效果/方向边界2项CPU测试通过。T1/T2/T3/T5 seed0的新分数及差值均已由原生产者发布并触发条件seed1，当前尚无最终两种子或机制结论，不能据单元测试或单种子结果采纳新头。

## 限制

机制解释范围限于query→atom softmax的选择性；H6观察和T3消融均未移除64维sigmoid门控求和，logN大小信息也仍存在。最终胜/负/平严格沿用冻结预注册，结果不能扩展成所有PMA加权均已被均匀化或排除。

新代码默认关闭；不接入主线或p-followup在跑任务。标签、mask、归一化及字段集合不改。T1旧固定验收未通过的历史仍保留，当前由用户授权在M2上直接训练，T2六个电荷头复用已通过的实际拟合验收、三项Fukui修正后补验收按首次达标规则通过；T1/T2/T3/T5现有seed0质量结果均尚待条件seed1形成最终判定；其他未完成运行及资源等待不视为科学完成。

T2 最终后处理已注册为真实 Slurm 4535833（cpu/node16、1CPU、nice10000、afterok:4535630；当前仅依赖等待）。只有原 T2 训练及原 R1/R3 成功结束后，顺序运行既有 t_decide 与 t_collect_descriptions：前者按预注册读取原1000配对bootstrap、只生成实际触发的seed1配置，后者只转录既有CYP/原单位VAL行；不重新训练/评价/计算MAE。整理器785fd62仅将实际seed1输出加_seed1后缀，避免覆盖seed0描述性附表，seed0路径保持原样；未运行额外整理或数值检查。

其余已实际在跑的seed0臂也已注册相同的正式后处理，均cpu/node16/1CPU/nice10000、无CUDA设备、仅afterok等待各自原训练与评价成功：T1=4535834→4535781，T4=4535835→4535771，T5=4535836→4535747。T1读取交接协议维护的canonical实际run，并显式复用本仓库M2 infra_recovery_20261117_sbatch的seed0参考；T4/T5仍显式B3，不切换基底。T1 seed1外部对照此阶段不提前绑定或使用；若触发，最终两种子判定在配方M2 seed1完整3M/R1/R3/成功终态后再显式传入发布的配置。上述队列仅使必做判定/描述转录在各自真实输入就绪后立即运行，不提前执行，不增加评价或新训练臂。

13:44资源队列修正：T3 seed1真实4535777经确认仍PENDING/0:00，依赖更新为afterany:4535189（原node6/15CPU/nice10000/正优先级不变）。该依赖仅等待C3释放GPU，合法迁移的旧handle即使CANCELLED也不应阻断本线；不要求其它臂先取得科学成功。实际启动仍由原GPU占用/UUID锁/CPU分配/磁盘守卫检查。用户已明确20a立即给C3，B3共享seed1仍hold；未修改或停止任何在跑任务。

最终后处理资源修正：根逐一确认T1/T4/T5的4535834/4535835/4535836仍PENDING/0:00后，仅将原CPU16位置改为gpu分区的node20、仍各1CPU/空CUDA；真实Slurm核实原afterok依赖分别4535781/4535771/4535747完整保留。它们只读各自已完成的原3M分数/描述记录，不增加评价、不占GPU，也不以H结果为前置科学条件。H1 T2 CPU4536097已C0/29:03；下一唯一H1 writer为T1 CPU4536173/4CPU、afterok4535781，保持几何整写串行。

3090新共用范围待确认：M2 seed1实际4535736 C0/12:53:40后，node7有16个可分配CPU、显存290/24576MiB且原gmx上下文282MiB/GPU利用率点值约71%；实际磁盘/inode/quota已通过。B3参考seed1可据既有冻结源改排该卡，但尚未启动，等待用户统一3090共用范围答复。新node6也有gmx276MiB，根确认T3 seed1 4535777仍PENDING0后临时hold，其afterany:C3资源依赖保留，以免C3迁出后发生未经确认的共用；非科学条件。原node4 T4/T5已获授权及其在跑训练不受影响，20a仍留给C3。

T1 seed1准备：正式node20/1CPU/空CUDA作业4536217已COMPLETED 0:0、8秒，生成T1_seed1_source@617e78f（16671422B）。源冻结内先按实际节点通过合并24GiB峰值、root/NFS字节和inode、UID quota及其它窗口增长守卫，再复制小型源码；配置仍为已发布fresh M2/全45decoder/seed1/3M，未启动训练或重训外部M2。当前等首个合规资源；node20a按用户答复继续保留C3，新增3090共用的统一口径仍待答。
