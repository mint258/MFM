# M3/M4 续接入口（2026-11-10）

状态：D6正式READY；M3 P三候选已实际启动。此页只说明执行接口，未选定主干、头、配方或B*。科学规则以DECISION_RULES_TASKBOOK_V2.md为准；原S结果、M2诊断和预注册保留。

统一入口 `tools/model_v3/v2_run_development.sbatch MODE CONFIG GPU_UUID PYTHON`，通过sbatch指定实际空闲节点。MODE为native_s、v31或dev，分别调用原v2_train_s.py、v2_train_v31.py、v2_evaluate_s.py；不替换训练算法或开发面板。新输出在 `/lfshome/zixiao/model_v31_20261105/`，先将其训练根追加到仓库外 `runs/model_v31_20261105/model_output_budget.json` 的roots；dev子目录共享该根。总预测仍全节点合计100GB，已分配物理块去重扣除。启动与运行保护沿用现有真实节点字节/inode、native quota及UUID锁；未注册根不运行。

native_s配置只含原CLI参数：index_path、output、distance_bias、views、seed、samples、batch_size、microbatch_size、lr、schedule、clip、workers，以及恢复时的resume。C1补seed1时继续读原S240k/records.parquet，6000000样本、B32、lr3e-4/cosine/clip1，执行微批按下述真实峰值指定，原index与其他科学参数不变。旧configuration.json中的model/betas是生产器报告，不能作为未知CLI字段透传。v31配置直接使用原实验JSON。dev配置只含checkpoint、output及可选validation_index，固定原18格TRAIN内层面板。

待P的6381/6382/6383实际开发评价闭合后，与保留的S_C1_0_seed0_v2、S_C1_a_seed0、S_C1_b_seed0_v2的真实18格分数按每个seed内S/P等权汇总。仅初始前两候选各补S/P seed1；先完成它们的开发评价，再按同配置真实种子SD和既定简单性顺序确定C1。条件不能冒充种子，Bootstrap不能替代预训练种子SD。保持原失败记录及实际完整检查点的区别。

后继顺序及既定网格：C3两/三视图×S/SDP使用胜出C1；H1/H2/H3×P/D/SDP使用选定主干/视图；H1下注册表/可学习池化×P。每项初始seed0，前两配置各条件补seed1。完全相同科学配置与预算的已完成运行复用，不重训；未选择前不填默认胜者，也不释放原Held两视图旧任务。

M4依次为五个lr×S/P/B32、前两lr×S/P/B64、最佳lr下cosine/WSD（末20%线性衰减），再用实际TRAIN preclip范数p99确认SDP。全量S/P按D6正式TRAIN，保持完整64M调度预算，以run_until_samples分段取得1/2/4/8/16/32/64M开发读数；每段恢复原优化器/RNG/样本时钟。实际达到平台才决定B*；64M仅观测上限。最后冻结模型/配方两份配置、代码标签，并补全现有PREREG/HANDOFF。无下游TEST、性能网格、正式预训练或付费服务器运行。

本入口新增10项分派测试及2项共享输出注册测试，只验证既有CLI参数保留与同一预算登记；不增加实际模型冒烟或独立数据复核。实际测试结果记本日DAILY。

机器可读配置位于 configs/model_v3/followon_templates.json：44个条件模板覆盖C1各候选潜在补种子、C3/头/池化、M4扫描与全量首段。它们不是44个获选或已提交任务：C1只运行实际前两候选补种子，其他比较同样仅给实际前两名补种子；相同已完成配置复用。全量S/P分别含seed0/1模板，给既定预算判据提供同条件、同最终配方和人口、同检查点的真实预训练种子标准差（ddof=1）；不混合S/P或用proxy/readout/bootstrap波动代替。实际种子读数不足时B*待定；每次运行仍保留64M调度上限并从1M分段开始。所有未决选择保持null，正式数据根/D4/原240k索引已绑定；不能将模板文件直接作为执行JSON。

C1补种子准备作业4529082已afterok:4526381:4526382:4526383入队。v2_prepare_c1_repeats.py只读取六个完整原6M开发汇总及原配置，调用既有S/P等权规则排名，输出实际前两名的四份seed1配置和selection.json至 runs/model_v31_20261105/M3_C1_TOP2_20261110。P保留原完整科学配置；S继续原native索引/CLI配方；只在新运行的seed/output及执行微批上设置新值。它不读标签/权重、不新增数值QA，不提交GPU任务或计算seed SD/最终C1胜者。实际补种子启动时仍须现场选择空闲GPU并登记输出。

C1补种子执行微批：P在64k样本检查点记录的GPU峰值为C1-0 4,023,376,896B、C1-a 3,448,503,808B、C1-b 3,461,263,872B；S-a/b完整6M的峰值分别6,111,961,088B、6,118,976,000B。后续P补种子微批设16，按原micro4峰值四倍再加25%余量估算，最大20,116,884,480B；S-a/b设8，按两倍峰值加25%余量；S-0缺完整峰值保持4。实际启动时按所分配GPU重新核实容量。有效批32、原逐字段观测数加权、样本/优化器/clip/调度均不变；实际吞吐仍由后续真实运行报告，不据该估算宣称已提速。此处只调整尚未启动的补seed1配置，当前三组及其待商量的micro8续跑方案不变。

分段训练计数：MFM4生产器的execution.json记录本段起始累计samples/updates/seconds，summary保留累计科学时钟并另列actual_samples/actual_updates/actual_seconds。结果CSV中的曝光/更新/耗时按本作业新增工作记录；开发分数与dev.consumed_samples累计检查点对齐。M4倍增平台判定仍用累计检查点样本数，不用分段CSV新增曝光代替。seed1生成时移除seed0的resume指针并取消执行分段终点，保持6M从随机初始化开始。

当前三组P切换微批8的可审阅方案和三份PROPOSED配置位于仓库外runs/model_v31_20261105/M3_P_micro8_continuation.PROPOSAL.json及其列出的配置路径。切换会从最近完整检查点重放尚未持久化的后缀，按任务书工作原则5先与用户商量。原三组与原评价链继续，尚未执行切换或提交新GPU任务。获准后先核实实际自有任务/目标容量，冻结检查点为同盘硬链接后续跑，仅替换自有未启动评价/依赖并登记同一个100GB预算；原检查点/日志保留。

已有运行复用：v31_experiments.py仅在S启用时调用视图builder/structural前向；P/D由V31PDModel直接调用相同encoder。s_model在选择V3TwoViewModel/V3MultiViewModel包装前已构造同一encoder；两视图类不覆盖构造函数，只覆盖此处P/D不调用的结构前向/损失。因此纯P/D的views二/三元数据不构成不同有效训练条件。保留原配置与结果原样，在阶段结果表记录引用关系，不另添一行虚构的新训练。

条件相同才复用：核对实际完整6M检查点/开发结果、种子、C1、数据/原子与构象采样、D4/字段/掩码/家族、头形式、池化、有效批、LR/betas/clip/调度及精度。C3三视图S可用选定C1已有S；H1/P可用相同选定C1已有P（P的S视图数未启用）；H1/SDP可用选定C3已有SDP；H1注册表池化P可用同一H1/P。M4的3e-4/B32/cosine点只在最终所有有效模型/输入/配方参数也完全相同的条件下引用M3实测，其他LR/B/调度及头/池化组合按原网格执行。S/SDP视图变化是实际输入变化，不作这种复用；native S与MFM4 S输入引擎也不据成员相同就互相替代。

训练CSV维持每个实际训练一行；阶段表引用被复用run_id及原阶段，不能将一次运行记为两个新作业或新增曝光。M4新native S运行的stage需从其实际阶段6队列记录填写：v2_collect_runs.py调用时使用`--stage 6`，或collect_run传stage=6；原producer配置缺stage时才补充，若显式stage冲突则报错。旧native S配置未包含stage，不能盲用汇总器默认stage5；被复用的M3原行仍保留阶段5。此处完善执行引用，不新增数据检查、模型测试或科学判定规则。

后续MFM4输入预取：v31_prefetch.py通过原14个CPU reader预取下一有效批，与当前GPU计算重叠；最多一批在前，不缓存到磁盘、不改微批或有效批。使用独立规划RNG/clock，执行完optimizer.step后才将本批RNG状态提交给原检查点；中断时未消费的预取只被重新读取，不跳过样本或计训练曝光。保留原逐分子/构象抽样顺序、里程碑边界、loss/优化器/torch RNG。原正在运行的三组已加载旧循环，继续原实现。实际一次GPU利用率采样21–26%只说明该时刻状态，不证明瓶颈或提速幅度。新预取7项单测及原相关9项共16PASS/0.33秒；无新增真实模型测试。
