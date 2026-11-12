# v3 开发方法

本工作属于研究主线E0。Lite是待检验的稠密模型模块，不能代替主线E4按标签家族组织的MoE主张。E1压缩网格及预算、E2正式种子数仍按主线D4/D6在相应实验前由用户确定；当前不启动这些实验或访问TEST。第0层短训练数按用户2026-11-11确认，为T0-3/T0-4各S/P共4组。

## 固定成员与表示

开发任务为v1的9个任务，成员、TRAIN优化/内层验证、原子顺序及分子组划分全部保持；无目标的H0按检查点/几何/既定成员只编码缓存一次，各读出共用。只消费train与train_inner_validation。每个数据集的N_ref为其实际优化子集内几何可用分子的平均原子数，作为固定缩放常数；不使用验证标签拟合。历史R0/R1及18格结果直接引用，不重新训练旧读出。

随机参考保持v1的同架构规则：seed20261025的C1-0/a/b参考各计算一次R2/R3，由S/P共用。将三个参考放在一个参考生产作业内，因此总计6个候选评价作业和1个参考作业组；不将一个C1的参考替代另一C1。编码器始终冻结，H0无梯度。

## R2、R3

R2分子输入为[mean(H)||sum(H)/N_ref]，原子输入为h_i。R3分子读出先逐原子用MLP映射至256维，再拼接mean和sum/N_ref后用第二个MLP预测；SoM直接复用对应R2预测，不重复训练。每个MLP为两个仿射层，隐层宽256、ReLU、无dropout；原子变换的输出维度为256。优化子集逐维总体均值/标准差用于特征标准化：R2在其输入特征上拟合，R3在原子H0输入上拟合。回归目标使用优化集均值与总体标准差，损失为标准化MSE；SoM仅在原有候选/监督掩码交集上计算BCE。未观测NaN在运算前排除。

AdamW学习率1e-3、betas(.9,.999)、weight_decay.01，批大小32个分子，30轮、seed0，取最后一轮，无早停或超参扫描。读出优化与预训练样本时钟分别记录，不将读出曝光计入6M/64M预训练预算。离线W&B保留全部逐更新损失、1000更新均值和30秒系统观测；真实SDK关闭后交付完整文件。R3唯一新增读出单测检查原子置换及padding不变性，容差逐元素为max(1e-6,1e-5×|参考值|)。

## 单种子比较与不确定性

每任务使用同读出、同架构匹配随机参考的误差归一化改善(r−e)/r；任务内误差仍为原单位MAE或原SoM的1−Hit@1。R3九任务等权为主指标，跨条件先各条件内九任务等权，再条件等权。R1、R2及历史18格仅次要报告。

沿用compare_panel的分子组配对bootstrap，1000次、seed20261025、百分位95%区间。新路径保留按抽样序号排列的每次主指标及明确分子组顺序。候选、条件、任务共享相同抽样；直接对同一次抽样的候选主指标做差，再对差值取区间，不相减两个单独区间。未定义的抽样明确计数，不能重排抽样序号；缺少完整任务/条件不能选型。

Δ下界严格大于0且Δ≥max(.01,.05×max(score_A,score_B))才认为A胜出；反向按同一规则。否则平局。多候选先按主分排序，仅比较前二，平局仅在这二者中按预先简单性顺序选。C1顺序为0/a/b，视图两/三，预测头H1/2/3，模块原架构优先；不同型号GPU的原始耗时不作直接比较。R3与历史排名不同只在结果文件记录，不追加探索分析。

## 全量平台

固定64M学习率调度，在实际1/2/4/8/16/32/64M检查点评价；分段恢复原优化器、RNG与累计样本时钟。首次翻倍增益小于max(.01,.05×翻倍前后较高主分)，或配对Δ区间包含0，取翻倍前样本数；S/P分别求预算，再取较大值。64M上限没有满足平台定义时仍记未定，不用上限代替平台。

## 待实现模块及实验

Lite/PMA/重建/同参数MLP、指定FP64数学验收及三层实验完全使用TASKBOOK_V3.md的固定取值和采用规则。第0层只报告；第1层分别比较A3R2z对A0R3和A4R3，并检查SoM保护条件，按预注册顺序分解；只有采用后才做规定λ/k及从头确认。不补S条件未规定的目标。机制分析只用开发面板TRAIN及数据线已有28类SMARTS，微调仅规定3任务，均不参与采用决策。各组完成时补入实际统计与方法实现，不能以本段计划代替完成证据。

## Lite 核心实现与指定数学验收

新增模块只在第5/6层原有FFN之后读写；PMA仅在最终H0上读一次。所有潜变量MHA投影宽256、8头、无投影偏置，FFN为256→512→256、GELU；原骨干SiLU保持原实现。写回逐通道门γ初值严格为0。z为按固定潜变量顺序拼接的8×64投影、64维sigmoid门控未归一化原子和除以N_ref及log(N)，默认维度577。N_ref=53.64145，来自原240000个TRAIN分子各一次的total_atoms，不按构象重复加权，不重拟合D4。

解码器输入仅有Z的64维投影、元素嵌入及到质心距离的32个Gaussian径向基，不接触X；径向范围0–8Å、宽8/31。教师X停止梯度。重建误差对512个分量求平方和，再对有效原子平均，除以教师逐维总体方差的均值；不额外除512，零方差仅按浮点epsilon保护。dense_addon两层原子残差MLP的宽度由新增参数数目代数求解并取最近8倍数，不按性能扫描；真实条件模型构建时记录完整参数数目以落实5%限制。

2026-11-11在compute-0-20运行test_v3_latent_math.py：指定3项全部通过，耗时1.60秒。使用原C1-0/S/6M真实检查点：完整原路径下γ=0的有效原子X逐元素满足max(1e-7绝对,1e-6相对)；新插入映射在真实第5/6层状态上以FP64检查同一性质。FP64新增潜变量映射在原子置换和随机刚体变换下，z相对范数误差7.35897005741585e-16≤1e-9；padding也满足上述X/z逐元素容差。FP32对应相对误差3.917589026514179e-7，仅报告、不作通过门槛。既有骨干坐标/RBF内部固定FP32，未为本测试改变其精度路径；FP64结果针对新增数学映射，不声称重新验收完整旧骨干的FP64坐标计算。

配置见configs/model_v3/latent_lite_v1.json。核心数学通过不代表训练接线或模块采用；预测头、续训及三层真实实验另行完成。用户2026-11-11已确认：分子标量接z，物理矢量保留原等变路径；字段和D4保持原定义。
## 原生S潜变量训练接线

T0/T1所有S组继续使用原GroupedSIndex/native LMDB传输和原240k分子—构象两级均匀抽样。每组从相同6M S检查点恢复原数据抽样状态、CPU/CUDA RNG及结构增强累计样本序号；新模块以seed0初始化且不改变公共参数初始化/RNG消耗。T0只更新新增模块参数，干净视图上的L_rec为唯一S目标，不添加结构或分子监督。T1保留原三项S损失与原结构视图，只有A3另加0.1L_rec；A1/A2不补新目标。A0/A4没有z或重建损失。

每组重置AdamW，betas(.9,.95)、原weight_decay.01、B32、clip1，2%阶段样本warmup及余弦到0；T0为0.5M、lr3e-4，T1为1.5M、lr1e-4。阶段预算时钟与原6M累计样本分别记录。整批B32计算教师逐维总体方差，避免将微批方差的平均误当原公式。所有结构视图经潜变量模块；重建仅取同次干净图的Z及干净H0，其他图不进入教师/解码器。原头形状、原512维H0和S原目标均保留。

真实第一轮训练作为接线验收，不另加模型冒烟。逐更新CSV及真实离线W&B保留损失、1000更新均值、preclip梯度、学习率、阶段/累计样本、显存峰值及SDK原生30秒系统指标；每100000阶段样本保存报告快照，SDK真实关闭后归档。
## P分子预测头路由与T0-2

按用户2026-11-11确认，只有注册表graph/scalar预测头接入z；分子矢量和原子矢量继续使用原等变X/坐标路径，字段、三分量物理矢量合并、掩码及D4残差单位均不变。mean标量由独立MLP(z)预测；sum标量由逐原子独立MLP(X)求和加无偏置线性w_z·z预测，w_z初值为0。字段函数严格继承当前H1/H2/H3结构：H1为单仿射，H2为按标签组共享的宽64/SiLU投影和独立输出层，H3为独立宽64/SiLU两仿射层。C1续训保持H1；后来比较头形式只改变字段函数结构，z/X输入路由不变。H2的mean(z)与sum(X)输入维数不同，分别建立组内共享投影；旧标量头和旧H2投影不作为无用参数保留。先载入所有原检查点权重，再安装新头；原子、原子对和矢量头原权重全部保留。

P继续使用原MFM4/D4/训练视图/240k成员及原分子—构象两级均匀抽样，不改P扰动标签的真实pos_perturbed路由。每步保存干净编码的X、z和投影潜变量局部引用；随后真实扰动几何编码不覆盖重建所用干净引用。T0的P只启用分子级P字段，只更新新潜变量及新标量头；T0-3不加重建，T0-4加0.1L_rec。T1启用原全P字段，A3加0.1L_rec，其他组不加。A4按照完整P条件模型（包括A3新增/替换的标量头）的参数数目代数求宽，并记录完整参数数目及≤5%差异；派生宽度随检查点配置保存，不作性能扫描。

T0-2直接读取已闭合的C1-0/S/P及匹配随机参考H0缓存，不调用编码器。每分子拼接mean、sum/N_ref、max及逐维总体标准差（ddof0）；R1沿用原五折按分子分组ridge，R2沿用固定v2优化参数。原子SoM不受池化改变，直接引用旧R1结果及已有R2预测，不重复拟合；R1九任务均值由7个新分子结果加2个原子旧格子组成，其新bootstrap区间只描述7个分子任务。R2完整9任务使用对应匹配参考及原分子组bootstrap。该层只报告，不作为采用门槛。
## 潜变量冻结评价与配对比较

每个新检查点在原TRAIN优化/内层验证成员上只编码缓存一次，X和z来自同一干净图、同一前向。R1/R2/R3照常读取X，R1z/R2z直接读取z；SoM两格只读取X，并把对应R1/R2预测作为R1z/R2z的原子格子别名，R3的SoM也直接复用R2。R1仍是原五折分子分组ridge，R2z继承R2全部固定优化和标准化参数。缓存只含输入身份、无目标表示和固定N_ref；预测/权重保留在仓库外。

匹配随机参考seed20261025、S/P共享：原子X的参考与已闭合C1-0参考函数相同（新增写回/dense门初值为0，PMA无写回，新增模块初始化不消耗公共RNG），直接复用已有R2/R3预测。z按PMA或两层读写、k、写回开关登记参考并只生产一次；解码器和重建权重不参与z，lite/lite_rec对应同一初始化z路径，故复用相同参考。参考生产加互斥锁，避免并发重复编码/拟合。

原v1只保存了R1汇总而未保存逐记录预测。为完成本文新要求的R1z对A0R3配对区间，在新评价路径中将匹配随机参考的R1逐记录预测用原H0缓存和原ridge配方生产一次；不替换或重算六个C1已交付的R1分数。新增检查点的R1则是本轮首次评价。所有新读出的完整9格均保留相同分子组顺序、1000次抽样序号和逐任务抽样值；不同读出/条件/模型直接对同次抽样求差。

T1严格报告全部预注册比较。SoM保护使用两格的归一化改善（非原始误差），条件内两任务等权再S/P等权；容许下降为max(.02,.1×abs(A0的SoM平均改善))。其区间从原完整9格同次抽样中提取两格，保持跨模型/读出/条件配对。A3须同时胜A0、A4并满足SoM保护；不满足才按同样三条判断A1。T1通过只是暂定选择，仍须规定的λ/k分支及从头6M确认，不提前宣布模块或全线冻结。

## T0复用边界

T0-3/T0-4的原骨干完全冻结、潜变量没有写回，因此X与C1-0原检查点相同。该层直接引用已闭合的R1/R2/R3分数和已有R2/R3逐记录预测，不重新拟合这些旧X探针，也不重编码SoM。只为新增z计算必要的分子表示和R1z/R2z探针。R2z的两格SoM引用对应原R2预测，仍可给出完整9任务配对区间；R1z的SoM引用原R1点分数，九任务只给点均值，新区间明确只覆盖7个分子任务，不把7格区间误标为9格区间。T0只报告、不作采用门槛；T1的新检查点则首次完整生产R1/R2/R3/R1z/R2z及9格配对抽样。


逐检查点的配对bootstrap汇总作为该冻结GPU评价作业的最后一步，在其已分配的16个CPU核上完成，随后释放作业；不在登录节点运行统计或模型计算，也不额外派发CPU计算到未授权节点。compute-0-20当前104核均已占用，独立的四统计量CPU作业继续排队。此安排使各训练组的分数随评价产物闭合，预算和统计方法不变。

## 条件性全新6M确认的初始化

仅当第1层按预注册规则实际采用A1/PMA或A3/lite_rec后，才允许stage=T2。T2读取原C1-0的configuration.json作为科学配方元数据，不加载其模型、优化器或RNG张量；拒绝initialize_from或resume。骨干和相应新模块按seed0重新初始化，数据抽样发生器为新的default_rng(0)，样本和更新时钟均从0开始，结构视图序号也从0开始。继续沿用原240k成员、三视图、B32、6M预算、lr3e-4、2%warmup与cosine、clip1及AdamW(.9,.95)。S保留原S目标，P继承原字段、D4、数据视图和头形式；仅lite_rec添加选定lambda的重建项。只允许默认(lambda=.1,k=8)及任务书规定的(.3,8)/(.1,16)。这些入口尚未代表模块被采用或确认训练已完成。

SoM评价中的R1/R2预测别名只用于文件映射，独立于历史X结果目录；T1/T2不会误引用T0冻结X的旧结果。

## 仅报告的完整微调

条件性第2层完成后，两个P/6M检查点各在exp.LogD、exp.Log_HLM_CLint和qm9.homo上微调一次，共六组。原检查点用R3、新检查点用R2z，编码器与新建监督读出共同更新；编码器lr1e-4、读出lr1e-3，AdamW(.9,.999)、weight_decay=.01、B32、30轮、seed0，固定最后一轮，无早停。没有增加重建或预训练目标，不以微调结果作任何采用决策。

沿用固定TRAIN优化/内层验证成员、原几何与掩码。初始特征标准化直接复用该检查点已经生成的X/z缓存：R3为TRAIN原子特征逐维均值/总体标准差，R2z为TRAIN分子z统计量，微调中固定这些常数；N_ref沿用该数据集优化集常数。回归目标只按TRAIN观测标签均值/总体标准差做MSE，最终在原单位报告内层验证MAE。初始缓存不额外编码，最终读出随实时编码器梯度更新。保留最终权重、预测、真实离线W&B逐更新损失、1000步均值和原生系统指标，selection_use=false，不访问TEST。这是待真实下游运行验收的实现，不代表六组微调已完成。

## 选定架构的后续联合训练入口

后续C3/预测头/M4/全量分段由显式配置接入选定的none、pma或lite_rec，尚未生成或启动依赖采用结果的运行。旧v31训练入口保持原样。MFM4联合入口保留原采样、D4、字段及按完整有效批观察数计算的字段/组等权平均；标量z路由与当前头形式组合，矢量仍走原等变路径。含潜变量时用完整有效批一次计算干净X、z及重建教师方差，避免微批方差改变目标；读取干净潜变量局部引用后才执行真实扰动几何分支。重建只在lite_rec添加一次，lambda不因S/P/D/SDP条件改变。none保留原字段计数加权累积。

全量分段沿用原SampleClock与固定预算调度：checkpoint保留模型/优化器、已消费抽样RNG、CPU/CUDA RNG、样本/更新时钟、全部TRAIN裁剪前范数及累计耗时。恢复只允许输出、执行微批、worker数和本段终点不同，科学配置一致；分段结束不重启warmup。每段SDK另记真实进程、已有累计时钟及新损失；10万样本快照从恢复后的下一边界开始，不伪造恢复前历史。各段实际第一次下游训练为接线验收。

## 原生S代理输入与后续判定

240k的S视图/配方比较继续使用原GroupedSIndex和native LMDB传输；成员相同不将MFM4 S引擎当作同一科学运行复用。native_selected入口支持选定架构、原三项S损失、原增强及原子序号、B32/B64和规定调度，保留样本/优化器/RNG/全部preclip范数的真实恢复。none保留已有逐字段观察数加权微批，潜变量路径按完整有效批计算注册的教师方差。完整D6人口的S/P另走正式全量配置。SDK初始化在独立RNG上下文中进行，以保留训练初始化和续跑的随机状态。

后续判定统一消费已闭合的v2配对面板，不重新拟合探针或重采样分子。lambda/k两档各与默认档配对比较，未胜出或平局保留默认；若两档均胜默认，再直接配对比较，平局仍保留默认。全新6M确认比较S/P等权的新R2z与原R3，只有新模型按原规则胜出才采用，否则保留none并要求日报首行记录。C3/头/池化及配方候选使用各自预注册的简单性顺序和前二比较。全量B*逐条件按首次满足平台的翻倍前端点计算，取S/P较大值；未观察平台的64M上限继续记未定。全量曲线按1/2/4/8/16/32/64M顺序消费连续端点，按原入口观察到平台即可停止；否则继续倍增，调度预算始终64M。已观察平台与已到64M但未观察平台分别记录，后者仍记B*未定。

原生S的一批预取复用既有ordered_sample_batches，并以GroupedSIndex.draw作为抽样回调：先向量化抽取整批分子，再逐分子抽取构象，保留原随机序列，而非改为交替逐分子抽样。规划时钟/RNG独立，优化器更新后才提交已消费的状态；只预取下一批，无磁盘缓存。2026-11-11此改动用于尚未启动的原生S运行，当前已启动的A0/S与A1/S原进程继续。实际后续运行首次使用验收，不加额外冒烟或速度对照。选定潜变量配置须显式绑定，未提供时拒绝回落到隐含默认值。

## 后续比较的输入完整性

后续决策清单的candidate_set类须显式给出comparison：views要求S/SDP，heads要求P/D/SDP，pooling要求P，learning_rate/batch/schedule要求S/P。每个声明候选都必须提供所有规定条件的已闭合九任务主面板；缺候选或缺条件时不选型。views/heads/pooling的简单性顺序分别固定为two/three、H1/H2/H3、registry/learned；配方候选沿用各自实验前声明的既定顺序。所有比较仍调用原配对1000次bootstrap及原效果阈值，不重算探针或重采样。该输入约束落实任务书的完整比较矩阵，未增加新的科学指标或测试。


## T1 report-only functional-group logistic probes

The canonical data-line set of 28 SMARTS is applied with RDKit to bonded TRAIN
structures, with native member and full-molecule identity preserved. Original
panel optimization and inner-validation populations are retained separately by
dataset. Mean(H) is probed for A0/P and A3/P; z is additionally probed for A3/P.
A0 has no z. Five-fold molecule-group CV uses the same folds, seed and positive
regularization strengths as R1. Fold-local feature standardization and final
optimization-only normalization prevent inner-validation leakage. L2 logistic
regression selects minimum mean 1-AUROC, with smaller alpha for exact ties.
All five fold metrics must be available. The liblinear implementation uses
C=1/alpha, seed0, tol1e-4 and max_iter1000, without class weighting. Failed or
single-class fits are explicitly unavailable, with no omitted folds. Final
held-out AUROC is stratified at <=20, 21-35 and >35 heavy atoms, without new
significance tests or size-specific fitting. Existing T1 X/z caches are reused.
Full input/solver and continuation conventions are in MECHANISM_ANALYSIS.md.
This producer is implemented but awaits canonical SMARTS/structure delivery and
closed T1 P evaluations; it has not produced scientific results.


## Training progress reports across stages

The report producer `tools/model_v3/v3_prepare_training_reports.py` reads actual submitted run plans and the original producer configuration, snapshots and histories. Effective batch size and scientific sample budget come from the run configuration. The original sample offset is the recorded cumulative clock minus the recorded stage clock, or zero when samples already use the absolute clock. Fresh6M confirmations therefore do not inherit the paired-continuation6M offset, and B64 reports retain the actual64 batch. Numeric stage labels are displayed as strings. The1000-update loss means are copied from existing history records, not refitted or reaveraged. Published point IDs remain unchanged and are skipped. Multiple actual plans can be supplied with repeated `--plan`; no job is queried, submitted or recovered by this tool. Native per-step SDK histories,30-second system statistics and actual training recipes are unaffected.

## C3 and view-independent head baseline execution (2026-11-13)

The complete ten-arm T1 producer comparison retains the original C1-0 architecture (latent=none). Its required module-adoption conditions fail, so the conditional lambda/k, fresh-module6M and associated fine-tuning branch is not invoked. All original T1 scores,paired differences,1000 common-draw intervals and SoM safeguards are retained in results/model_v3_t1.json.

C3 compares two/three structural views equally across S and SDP with the v2 nine-task R3 primary readout and the registered paired decision rule. The original C1-0 three-view native-S seed0 full6M checkpoint and its existing R3_summary.json are reused unchanged; the T1 A0 7.5M continuation is not substituted for this6M budget. The other three cells are fresh random-initialized6M seed0 runs on the original240k sources. S retains GroupedSIndex/native LMDB transport through native_selected; SDP retains the original MFM4 field,mask,D4 and full-effective-batch observation weighting through selected. All use B32,AdamW lr3e-4,betas(.9,.95),the original2% warmup/cosine and clip1. Execution microbatches initially were32 for S and16 for SDP; the SDP runs subsequently continued at32 as recorded below. H0/X caches use unique checkpoint keys in the existing readout cache and reuse its frozen random reference; no original probe is refit for reuse.

The prescribed H1/D baseline is independent of the C3 view choice: pure D,like pure P,does not call the structural-view builder. It is started on the fourth free card with the original inactive three-view metadata,H1,registry pooling and the same240k/seed0/6M/B32 recipe. No view winner is assigned early. This is the queue rule permitting the next stage's independent work; the remaining SDP head cells still require the actual C3 winner.

Every actual job has16 allocated CPU cores and one pinned3090 UUID. Fresh target-node filesystem bytes/inodes,root reserve,native quota,combined growth and empty GPU contexts were checked; runtime guards continue every5seconds. Both new parent roots debit the same global100GB model forecast,not a per-node copy. The existing recovery service now registers67 actual execution entries. Each training's original evaluation and complete SDK archive are afterok-linked; archives request1CPU on node20 with nice10000 and retain the source SDK files.

An optional MODEL_V3_FOLLOWON_PLAN environment value in the existing dispatcher calls the C3 summary-only consumer after an actual evaluation. Only the last completed C3 evaluation consumes all four complete primary panels and computes the registered comparison inside its existing allocation. Default command/recovery identity is unchanged. Actual first training use is wiring acceptance; no new model smoke run,source-data audit,probe recomputation or repeated regression was added.


## Execution continuation and independent head queue (2026-11-13)

C3 SDP microbatches changed from16 to32 while effective batch32 and the complete6M scientific recipe remained unchanged. Both runs restore complete32000-sample/1000-update checkpoints including model,AdamW,RNG,sample clock and the preclip history. Original jobs4530283/4530286 consumed40640/38976 samples; their continuations4530292/4530293 replay8640/6976 unsaved samples. The original files are retained. This is an execution continuation,not another scientific candidate or another6M run. Scientific field observation weighting is unchanged.

The INT signal also interrupted the original SDK processes before a normal finish marker. Their ordinary raw SDK files are retained unchanged as INTERRUPTED_PARTIAL_RAW_SDK,with original terminal-controller evidence; no normal SDK completion or parsed-system-report claim is made for them. The final logical bundle combines the actual closed continuation and evaluation SDKs with the retained interrupted raw files,explicitly recording two closed sources and one interrupted source. Existing closed-only archives retain their previous interpretation.

Four own zero-work follow-ons became JobHeldAdmin after dependency rebinding. They were replaced by fresh immutable own submissions4530294/4530295 and4530296/4530297; the former jobs and configuration files are preserved. H2/P,D and H3/P,D are queued on the existing head/native-S lanes after their actual predecessor evaluations. Pure P/D never invoke the structural-view builder,and retain scientifically inactive three-view metadata. H2/H3 SDP still await the actual C3 result; no view choice is inferred early.


The original H1 registry/learned pooling comparison remains required because latent=none. Its registry-P cell exactly reuses the original C1-0 H1/P seed0 full6M checkpoint and existing v2 R3 panel. Only the learned-pooling H1/P cell is a new6M seed0/B32 training,with original240k sampling,D4,fields,AdamW3e-4,2% warmup/cosine and clip1. Pure P views remain inactive,and H1 is fixed by the original pooling experiment rather than selected from the head comparison. This cell is queued after the existing H2/D evaluation on node6; the comparison still uses paired bootstrap and the registered registry-before-learned simplicity rule. No baseline score is recomputed.


## C3-to-SDP-head execution handoff (2026-11-13)

After the last actual C3 evaluation has produced its complete panel,the existing C3 completion hook scores the registered comparison once. It then invokes the required H2/SDP and H3/SDP queue preparer on compute-0-20. Only the actual status=CANDIDATE_GROUP_SELECTED,comparison=views result can supply the view count; no fallback view is used. The two runs are fresh6M seed0/B32 trainings on nodes5/7 with their prescribed head forms and the selected views. H1/P exactly reuses the original C1-0 P6M panel,and H1/SDP exactly reuses the winning C3 SDP6M panel. All P/D/SDP cells are recorded in the head comparison manifest before head selection.

The new jobs depend on the still-live last C3 evaluation job,not purged historical job IDs. Actual target capacity/inodes/native quota are checked before queueing and by the original startup guard. Queued jobs are held until their actual identities,SDK follow-ons and recovery entries are recorded; all outputs stay within the existing common100GB forecast. An incomplete submission journal requires coordinator recovery and never triggers blind resubmission. Failure to queue does not reclassify or rerun the completed native evaluation; it is retained separately in heads_sdp_queue_attempts.jsonl. Actual first training use remains the wiring acceptance.


## M4 initial learning-rate configuration binding (2026-11-13)

The first recipe grid has exactly five rates(1e-4,3e-4,6e-4,1e-3,2e-3) x S/P,seed0,original240k,6M,B32,2%warmup/cosine,clip1 and original AdamW(.9,.95). The preparer consumes the actual closed C1,latent,view,head and pooling selections,and supplies no implicit winner. The current completed latent choice is none. Native S retains the original GroupedSIndex/LMDB engine; P retains original MFM4 fields,D4 and two-level sampling. New executions use micro32 while effective batch stays32. Readouts use the same v2 R3 panel and frozen random reference.

Only an identical effective3e-4 baseline is reused. S reuses the selected-view original C3/native6M cell,because P/D heads and graph pooling are inactive for pure S. P with registry pooling reuses the selected H1/H2/H3 P6M cell; H1 learned pooling reuses its original pooling comparison cell. A learned-pooling H2/H3 combination has no identical earlier baseline and therefore receives a new3e-4 run. Reused cells retain their source run/stage and zero new exposure; they are never new training rows. All ten logical panels remain required for the registered equal-S/P learning-rate comparison.

CLI: tools/model_v3/v3_prepare_m4_lr_20261113.py --output /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M4_V3_LR_20261113,run on compute-0-20 only after the actual model_v3_c3_views.json,model_v3_heads.json and model_v3_pooling.json exist. It prepares concrete configurations and a comparison manifest only; it submits no job,reserves no GPU and freezes no model or recipe. Output registration and actual-node capacity/UUID admission remain at submission. Actual scan execution waits for all required model decisions.


## M4 top-two effective-batch continuation

The B64 preparer requires the actual complete five-rate B32 decision and takes exactly its score-ranked top two rates. Each rate is retrained for S and P,6M,seed0,B64,with execution micro32 and the same selected model,clip1 and2%warmup/cosine. The original B32 cells remain unchanged. For each measured rate,the original single-seed paired rule compares B32/B64 across S/P,ties retaining B32. The retained measurements then populate the complete five-rate matrix for the same registered learning-rate selection. This implements the original joint LR/batch sequence with the v3 paired rule; it does not introduce another LR,condition,seed or metric. Outputs retain every per-rate batch comparison and the final common rate/batch choice.

CLI tools/model_v3/v3_prepare_m4_batch_20261113.py prepare consumes --initial-plan and --initial-selection and writes fresh --output configurations only. Its select command additionally consumes --batch-plan and writes --results only after the actual B64 panels exist. Preparation submits no GPU job; selection fits no new probe. All recipe results remain unfrozen until schedule,TRAIN clipping,SDP confirmation and full-data B* work are complete.


## M4 schedule configuration continuation

The schedule preparer consumes the actual M4_LR_BATCH_SELECTED result,retaining its common LR,batch,model and original240k inputs. The cosine cells are the identical already measured selected S/P6M cells,whether obtained from a new LR/B64 trial or exact M3 reuse. Only two fresh WSD S/P trainings are generated. WSD keeps2%warmup and starts linear decay at80% of the6M budget,ending at zero; clip stays1 during schedule comparison. The v2 paired schedule comparison uses cosine-before-WSD simplicity and the original common random references. No cosine probe or training is duplicated.

CLI tools/model_v3/v3_prepare_m4_schedule_20261113.py --joint-selection <actual_joint_result.json> --output <fresh_control_directory> prepares configurations only. It does not set the TRAIN p99,submit SDP/full-data jobs or freeze the recipe. Those steps still require their real preceding results and original source definition.


## Full-D6 sequential configuration and B-star inputs

The full first-segment preparer consumes the actual completed6M SDP confirmation configuration and its original v2 evaluation. It retains the selected architecture,head,pooling,LR,batch,schedule,clip and data view/D4. Each S/P model starts fresh at seed0 on all1,194,551 formal D6 TRAIN molecules; the240k subset is removed. Full S uses the original MFM4 full-population engine rather than substituting the native240k proxy. The schedule budget is64M at every segment,with1/2/4/8/16/32/64M endpoints. Thus2%warmup lasts1.28M samples; neither warmup nor a WSD decay is shortened to an execution segment. Only the first1M configurations are initially prepared.

A subsequent configuration copies the actual previous full producer configuration. Only output,resume checkpoint and run_until_samples change; model,AdamW,sampling/CPU/CUDA RNG,sample/update clocks,TRAIN preclip history and elapsed time are restored by the existing selected trainer. Stable candidate and code_tag fields are retained across segments. The next endpoint is always the next registered doubling,not a reset run. A condition whose actual curve has an observed plateau gets no next segment. At64M without a plateau it remains undetermined; the ceiling is never substituted for B*.

The full-curve collector consumes only original completed v2 endpoint readouts and calls the existing registered convergence consumer. Each actual observed prefix gets a fresh manifest/result/page; unchanged prefixes are not recomputed. Unfinished conditions have empty or shorter prefixes,so S and P may continue independently. Future planned paths are kept separate from actual curve points. Each next-segment request binds its actual endpoint panel to that curve decision. The shared B* remains the maximum of the two observed per-condition budgets,and stays undetermined if either has no observed budget. No probe is refit and no final configuration is frozen by these preparation tools.

CLI tools/model_v3/v3_prepare_full_segments_20261113.py first requires --sdp-configuration,--sdp-evaluation and fresh --output. Its next command requires --previous-configuration,--previous-evaluation,--budget-decision and fresh --output. tools/model_v3/v3_collect_full_curves_20261113.py consumes repeated --plan plus fresh --output,--results and --page. All execute on compute-0-20,generate metadata/configurations only,and require actual output registration and target-node admission before any later GPU submission. Current full-data configurations/jobs have not been generated or submitted.
