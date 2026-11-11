# M3/M4 续接入口（2026-11-10）

状态：D6正式READY；M3 P三候选已实际启动。此页只说明执行接口，未选定主干、头、配方或B*。科学规则以DECISION_RULES_TASKBOOK_V2.md为准；原S结果、M2诊断和预注册保留。

统一入口 `tools/model_v3/v2_run_development.sbatch MODE CONFIG GPU_UUID PYTHON`，通过sbatch指定实际空闲节点。MODE为native_s、v31或dev，分别调用原v2_train_s.py、v2_train_v31.py、v2_evaluate_s.py；不替换训练算法或开发面板。新输出在 `/lfshome/zixiao/model_v31_20261105/`，先将其训练根追加到仓库外 `runs/model_v31_20261105/model_output_budget.json` 的roots；dev子目录共享该根。总预测仍全节点合计100GB，已分配物理块去重扣除。启动与运行保护沿用现有真实节点字节/inode、native quota及UUID锁；未注册根不运行。

native_s配置只含原CLI参数：index_path、output、distance_bias、views、seed、samples、batch_size、microbatch_size、lr、schedule、clip、workers，以及恢复时的resume。C1补seed1时继续读原S240k/records.parquet，6000000样本、B32、lr3e-4/cosine/clip1，执行微批按下述真实峰值指定，原index与其他科学参数不变。旧configuration.json中的model/betas是生产器报告，不能作为未知CLI字段透传。v31配置直接使用原实验JSON。dev配置只含checkpoint、output及可选validation_index，固定原18格TRAIN内层面板。

待P的4529111/4529112/4529113实际开发评价闭合后，与保留的S_C1_0_seed0_v2、S_C1_a_seed0、S_C1_b_seed0_v2的真实18格分数按每个seed内S/P等权汇总。它们依赖用户批准的micro32/B32续跑4529108/4529109/4529110，从544000/544000/608000完整检查点继续至累计6M。仅初始前两候选各补S/P seed1；先完成它们的开发评价，再按同配置真实种子SD和既定简单性顺序确定C1。条件不能冒充种子，Bootstrap不能替代预训练种子SD。保持原失败记录及实际完整检查点的区别。

后继顺序及既定网格：C3两/三视图×S/SDP使用胜出C1；H1/H2/H3×P/D/SDP使用选定主干/视图；H1下注册表/可学习池化×P。每项初始seed0，前两配置各条件补seed1。完全相同科学配置与预算的已完成运行复用，不重训；未选择前不填默认胜者，也不释放原Held两视图旧任务。

M4依次为五个lr×S/P/B32、前两lr×S/P/B64、最佳lr下cosine/WSD（末20%线性衰减），再用实际TRAIN preclip范数p99确认SDP。全量S/P按D6正式TRAIN，保持完整64M调度预算，以run_until_samples分段取得1/2/4/8/16/32/64M开发读数；每段恢复原优化器/RNG/样本时钟。实际达到平台才决定B*；64M仅观测上限。最后冻结模型/配方两份配置、代码标签，并补全现有PREREG/HANDOFF。无下游TEST、性能网格、正式预训练或付费服务器运行。

本入口新增10项分派测试及2项共享输出注册测试，只验证既有CLI参数保留与同一预算登记；不增加实际模型冒烟或独立数据复核。实际测试结果记本日DAILY。

机器可读配置位于 configs/model_v3/followon_templates.json：44个条件模板覆盖C1各候选潜在补种子、C3/头/池化、M4扫描与全量首段。它们不是44个获选或已提交任务：C1只运行实际前两候选补种子，其他比较同样仅给实际前两名补种子；相同已完成配置复用。全量S/P分别含seed0/1模板，给既定预算判据提供同条件、同最终配方和人口、同检查点的真实预训练种子标准差（ddof=1）；不混合S/P或用proxy/readout/bootstrap波动代替。实际种子读数不足时B*待定；每次运行仍保留64M调度上限并从1M分段开始。所有未决选择保持null，正式数据根/D4/原240k索引已绑定；不能将模板文件直接作为执行JSON。

C1补种子准备作业4529103已afterok:4529111:4529112:4529113入队；原未启动4529082修改依赖后成为JobHeldAdmin，Slurm拒绝release，因此仅取消该自有未启动任务，以相同脚本/输入/节点/16CPU重新排队。v2_prepare_c1_repeats.py只读取六个完整6M开发汇总及原配置，调用既有S/P等权规则排名，输出实际前两名的四份seed1配置和selection.json至 runs/model_v31_20261105/M3_C1_TOP2_20261110。P输入已指向实际续跑目录，补seed1时移除其seed0 resume指针；S继续原native索引/CLI配方。它不读标签/权重、不新增数值QA，不提交GPU任务或计算seed SD/最终C1胜者。实际补种子启动时仍须现场选择空闲GPU并登记输出。

C1补种子执行微批：本次冻结的480k样本micro4检查点GPU峰值为C1-0 4,108,229,632B、C1-a 4,113,306,624B、C1-b 4,129,276,928B；S-a/b完整6M的峰值分别6,111,961,088B、6,118,976,000B。后续P补种子微批设16，按原micro4峰值四倍再加25%余量估算，最大20,646,384,640B；S-a/b设8，按两倍峰值加25%余量；S-0缺完整峰值保持4。实际启动时按所分配GPU重新核实容量。有效批32、原逐字段观测数加权、样本/优化器/clip/调度均不变；实际吞吐仍由真实运行报告。补seed1微批16与本次用户批准的seed0续跑微批8分别记录。

分段训练计数：MFM4生产器的execution.json记录本段起始累计samples/updates/seconds，summary保留累计科学时钟并另列actual_samples/actual_updates/actual_seconds。结果CSV中的曝光/更新/耗时按本作业新增工作记录；开发分数与dev.consumed_samples累计检查点对齐。M4倍增平台判定仍用累计检查点样本数，不用分段CSV新增曝光代替。seed1生成时移除seed0的resume指针并取消执行分段终点，保持6M从随机初始化开始。

用户已明确同意当前三组P从最新完整检查点续跑微批8。原4526376/6377/6378分别记录483264实际样本、15102更新后被用户授权取消；最新完整检查点均为480000样本、15000更新，已用原Lustre目录内micro8_resume_20261110.pt硬链接保留，每组实际重放3264样本。原日志/检查点全部保留；恢复模型、AdamW、RNG及累计6M时钟。新作业4529096/9097/9098运行于原节点/UUID，新评价4529099/9100/9101 afterok绑定新训练。配置与实际冻结映射位于仓库外runs/model_v31_20261105/M3_micro8_checkpoint_bindings_20261110.json及三份.APPROVED.json；原PROPOSAL文件保留批准及实际作业状态。新增输出登记在同一个全局100GB预算，硬链接按inode去重，不增加第二份预测；原Held4526030未动。CSV旧行保留实际完整工作，新行仅记录480000恢复点之后的新增工作；科学开发读数仍对应累计6M。

已有运行复用：v31_experiments.py仅在S启用时调用视图builder/structural前向；P/D由V31PDModel直接调用相同encoder。s_model在选择V3TwoViewModel/V3MultiViewModel包装前已构造同一encoder；两视图类不覆盖构造函数，只覆盖此处P/D不调用的结构前向/损失。因此纯P/D的views二/三元数据不构成不同有效训练条件。保留原配置与结果原样，在阶段结果表记录引用关系，不另添一行虚构的新训练。

条件相同才复用：核对实际完整6M检查点/开发结果、种子、C1、数据/原子与构象采样、D4/字段/掩码/家族、头形式、池化、有效批、LR/betas/clip/调度及精度。C3三视图S可用选定C1已有S；H1/P可用相同选定C1已有P（P的S视图数未启用）；H1/SDP可用选定C3已有SDP；H1注册表池化P可用同一H1/P。M4的3e-4/B32/cosine点只在最终所有有效模型/输入/配方参数也完全相同的条件下引用M3实测，其他LR/B/调度及头/池化组合按原网格执行。S/SDP视图变化是实际输入变化，不作这种复用；native S与MFM4 S输入引擎也不据成员相同就互相替代。

训练CSV维持每个实际训练一行；阶段表引用被复用run_id及原阶段，不能将一次运行记为两个新作业或新增曝光。M4新native S运行的stage需从其实际阶段6队列记录填写：v2_collect_runs.py调用时使用`--stage 6`，或collect_run传stage=6；原producer配置缺stage时才补充，若显式stage冲突则报错。旧native S配置未包含stage，不能盲用汇总器默认stage5；被复用的M3原行仍保留阶段5。此处完善执行引用，不新增数据检查、模型测试或科学判定规则。

MFM4输入预取：v31_prefetch.py通过原14个CPU reader预取下一有效批，与当前GPU计算重叠；最多一批在前，不缓存到磁盘，不改变有效批。使用独立规划RNG/clock，执行完optimizer.step后才将本批RNG状态提交给原检查点；中断时未消费的预取只被重新读取，不跳过样本或计训练曝光。保留原逐分子/构象抽样顺序、里程碑边界、loss/优化器/torch RNG。原三组旧循环的日志保留，新续跑4529096/9097/9098已采用该预取和微批8。原一次GPU利用率采样21–26%只说明该时刻状态，不证明唯一瓶颈；续跑速度按实际日志记录，不归因于单一优化。新预取7项单测及原相关9项共16PASS/0.33秒；本次不新增模型冒烟。

当前micro32执行：4529096/9097/9098实际574624/550656/611232后取消，本次v2冻结544000/544000/608000，重放30624/6656/3232。新训练4529108/9109/9110、开发9111/9112/9113；B32及全部科学配方保持。此前micro8与第一次micro32冻结映射保留为历史；只从v2绑定启动。配置准备9103先改新依赖，再取消旧未启动开发任务，无hold。

W&B由独立CPU任务4529106读取真实CSV，原始SDK留在共享Lustre的WANDB_20261110。每次Slurm执行单独run，导入历史明确标注；重复计算不冒充规范曲线新曝光。每100000累计样本保存快照，根协调器将每个新边界的轻量快照推至results/model_v3_wandb/points/<Slurm作业>/<样本数>.json，同时更新results/model_v3_wandb/report/LATEST.md及四面板图；最初19点的汇总文件保留。独立CPU诊断4529240约30秒记录实际系统指标，并按连续1000次优化器更新汇总总/分项损失。新dispatcher训练自动登记到同一个manifest。按用户最新决定保持OFFLINE_UNSYNCED，停止云端认证排查；对应训练和SDK真实结束后，将完整离线W&B文件上传GitHub并提供下载/重组说明，原文件保留。运行中的SDK不作为最终归档；数据、权重、检查点和密钥不进Git。

实时作业状态优先读取scontrol控制器并核对UID1278，sacct只作显式历史回退；同步读取原磁盘保护状态，控制器/保护观察异常交回Root核查。09:16两组node21训练被NFS配额快照future/stale保护STOP，sacct仍延迟显示RUNNING；实际容量复查通过后CONT原进程、样本已恢复增长。原原因保存在仓库外runs/model_v31_20261105/M3_micro32_disk_pause_1794273383.json，5项定向状态回归通过。原模型/AdamW/RNG、B32、6M预算和保护规则保持。

2026-11-11：P/C1-b训练4529110及开发4529113均真实C0，科学累计6M/187500更新，18格TRAIN汇总0.20315388182067007，原检查点samples_6000000.pt。当前执行新增5392000样本；该段CSV按新增工作计账，分数仍对应累计6M。其逐步与配对诊断SDK均已正常关闭，三个实际执行分段及配对诊断的[完整离线归档已上传](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111)，包含110个原始普通文件、压缩30,209,948字节，原文件保留。C1-0/a仍继续；此处不是联合C1选择。

持久恢复入口为tools/model_v3/v2_recover_quota_pause.py，使用仓库外runs/model_v31_20261105/M3_guard_recovery_20261111.json及同名前缀.state.json。它只协调登记的自有现存作业：UID1278、节点、完整启动命令和Restarts必须匹配；原guard须DISK_PAUSED；随后通过SSH在实际目标节点执行原v2_diagnosis_disk.py --once的全部容量/并发/native quota检查，再复查控制器STOPPED后CONT。实际容量未知时不发信号，不重启模型或回退检查点。10项控制单测PASS/0.07秒。当前协调器作为Main轻量元数据进程持续运行，服务配置enabled=false可退出，两组实际终态后自动退出；新运行需显式登记实际job/配置/UUID/解释器。11月10日晚同类快照暂停已按原容量规则重新准入，原进程/优化器/RNG/样本时钟恢复并实际推进。

2026-11-11 08:35后续状态：P/C1-a训练4529109及开发4529112均C0，累计6M/187500更新，18格TRAIN汇总0.25992266173725326；该micro32执行新增5456000样本/170500更新、86684.38754783012秒，CSV按新增工作计账。其三个实际执行与配对诊断共六个SDK run已关闭，完整110文件归档已追加至同一GitHub归档分支（压缩30929928字节），原文件保留。C1-0仍训练，初始联合排名及前两名seed1仍等待其完整dev；未执行的C1-a迁移提案现已无需执行。用户要求根进度巡检每30分钟一次，训练日志/系统采样与原实际磁盘保护继续，所有10万样本边界在巡检时集中补推。


2026-11-11 空闲卡并行推进：C1-a完整S/P seed0均分0.2601907066129589>b的0.22559578728623164，三候选仅剩一个未知，故a对所有剩余有效结果均必在前二；仅提前执行原必需S/P seed1，不提前公布全排名、C1胜者或种子SD。实际S4529691/node5/3090/micro8、P4529704/node22/5090/micro32，均B32/6M、从seed1随机初始化开始；P使用已实测a完整micro32峰值29204564480B选卡。预生成配置与完整准备器使用同一路径，prepare按内容相同复用；完整准备器selection.gpu_jobs_submitted=false只表示CPU准备器未提交，不能据此重复提交已运行a。以c1_initial_results.json.early_submitted_repeats和真实作业为准。原P首次9692被外部GPU上下文保护挡住、0样本，保留历史。

0的P训练4529108已C0/6M；旧开发4529111在保护处被同卡外部进程挡住、0评价工作，替代4529708在node6 afterok4529706。完整准备作业替换为4529710 afterok4529708，仍读取全部六个完整18格TRAIN结果再按原规则排名。未启动旧准备9103、旧b验证9707以PENDING/零运行时间取消并保留，b验证替代9709等待9708。node6的a验证9706在运行，依次接关键dev0和b验证；validation模式只分派既有v2_validate_v31.py，FULL/ROUTINE与TRAIN未见构象分开原始诊断，selection_use=false，禁止TEST/新归一化。16项分派测试PASS/0.07秒，共同100GB预算/原容量保护继续，无数据复制。


2026-11-11 12:09后：P0替代开发9708 C0，六组初始结果完整，联合均分C1-a=0.2601907066129589、C1-0=0.24211216453990045、C1-b=0.22559578728623164；原rank_initial选前二a/0，最终C1与种子SD仍null。原16CPU汇总9710在compute20不可调度（预计Nov18），PENDING/零运行取消，原脚本仅读取六个关闭JSON，现按短元数据方式在指定compute20经容量检查后exit0，未进行模型/数据计算或宣称Slurm完成。a运行复用，新增0的S9711→dev9712→P9713→dev9714在node6 afterok9709之后同卡串接，有其他卡释放则优先改派尚未开始的任务。S0保持micro4；P0依据完整6M/micro32实测峰值7947732480B，在首次启动前由micro16提高为32；有效B32/6M/原240k/全部配方不变。新根已登记同一全局100GB预测，详见M3_C1_RESULTS.md与results/model_v3_c1_initial.json。

P/a独立验证9706真实C0：FULL13815分子/126764构象、TRAIN留出4292/4292，各97损失头和109源列原单位R²/MAE/计数，完整结果results/model_v3_c1_a_validation_seed0.json，selection_use=false，不参与C1选择；P/b验证9709继续。原20k为全局诊断MID范围，此处4292是原240k已见人口的实际交集，不伪称20k或补入其他分子。监控器不再轮询已结束的CPU准备作业；已确认C0的验证允许显式历史记账回退，控制器不可见本身不当作训练失败。


用户2026-11-10批准的新任务书v3取代本文所有尚未执行的选型：取消全部seed1，后续单seed0；面板v2以九任务R3为主指标，采用配对bootstrap/绝对及相对效果阈值，B*取首次平台的翻倍前端点。旧规则及已完成记录保留为历史。先重评6个原C1 checkpoint，再做Lite模块及三层实验、原后续阶段和冻结。本文未冲突的分派/共享输出登记/真实物理磁盘保护/W&B归档接口沿用；后续详情以根任务书v3、修订后的DECISION_RULES_TASKBOOK_V2.md、dev_panel_v2.json及DEVELOPMENT_SCHEDULE.md为准。


2026-11-12 publication: original P/C1-b independent validation4529709 completed0:0 in00:34:38, FULL13815 molecules/126764 conformers and TRAIN held-out4292/4292. The closed producer JSON is published unchanged as results/model_v3_c1_b_validation_seed0.json; see M3_C1_B_VALIDATION.md. selection_use=false; no recomputation or C1-selection use. This closes the previous historical pending-validation notice.
