## 2026-11-05 PubChem扩充：队列与250万来源完成，UFF/D试跑进行中

扩充当前入口为[每日汇总](../expansion/daily_20261105.md)和[任务2.1完整分布报告](../expansion/v1_distribution.md)。原固定100万查询已自然完成，使用全部1,196,122个Common参考；统计、覆盖不足区间和图表已发布。官方全量获取、同v1规则回归/筛选及修正后的全池精确去污染已完成，109,875,599个去重结构留下105,670,833个候选，11类来源均已闭合。下文早期PubChem TIMEOUT、9/11 READY和组成规则仅保留为对应时间点历史。

截至13:30，全池精确近邻已完整完成：105,670,833个候选、88,756,722个不同指纹、555个闭合投影分片。215排序与217来源父作业及全部步骤均C0：已落盘R/N各500万的互斥嵌套队列，以及首批各125万的完整来源结构和250万图参考投影，详见每日汇总中的生产者清单及原生状态。真实1万UFF/D试跑272使用32个CPU核，与参考打包222并行；旧248仅元数据索引阶段取消，科学调用为零，原索引和成本保留。缓存修复只新增两条SQLite连接PRAGMA，科学逻辑及完整核对不变；全批274在273正常QA后自动启动，未设置人工挂起。实际全批UFF/D、增广覆盖及最终批次报告尚未完成，不能作为训练就绪或接口ACK；草稿PR1保持未合并。

本次去污染只用完整InChIKey及原v1 wp5，不使用组成下界或通配符；PDBbind移出去污染来源，结构未确定的下游行剔出评估并保留逐条审计。扩充分子最多3个实际UFF构象，保留原固定候选、种子、生成顺序及0.5Å去重；不足时不补足、不科学重试，缓存支持以后续接第4个及之后。D20每分子一次，D3及原子SASA逐实际构象；本阶段不计算QM/P′或训练。严格>1%异常NEW/canonical新增掩码停止条件及全部未来预算后的200GB配额余量继续有效；不增加逐作业Root审批。

## 2026-11-03 当前：D5载荷交付，D3单作业运行

D-2、D-4已正式暂定发布。D-5诊断载荷4525593实际C0/1607秒：试点已见893分子、12502几何、43757标签记录、53子库，一次1000条原Parquet比较通过，见[正式入口](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)。全局嵌套/20k母清单保持；本载荷不把试点外分子冒称已见。

D-3新独立producer pilot_family_D3_single_job_v1由实际4525598在compute-0-13/16CPU运行，固定50k TRAIN＋5k ROUTINE VAL；复用D4闭合几何、内部无损压缩。按用户最新规则，同一作业只一次counts＋1000条原Parquet逐字段＋总清单SHA、一次rsync --checksum分发、一次不超过5分钟吞吐。无生产Source3、10k、独立16-reader、F64全量二扫或复制后哈希。交付后请Model运行真实loader与逐预测头过拟合验收，当前不代填ACK。r73完整F64及ordered、一转F32；r674 LOSS_DISABLED。详见[今日唯一汇总](../data_v1/progress_20261103_v1_pilot_provisional.md)；以下旧时间点作为历史。

Model接线补充（2026-11-03观察点）：D3实际4525598复用旧4525596已关闭的63/113源组并处理剩余组，payload仍在运行；DataCodec读取接口已就绪不代表D3载荷已交付。现有 `CandidateWireFactory` 和 `synthetic_head_overfit.py` 仅支持合成fixture，不能作为本轮真实验收。模型线接好本次 `v1-pilot-provisional` 解释器、TRAIN/VAL/TRAIN_UNSEEN_CONFORMATION三个role indexes和readonly reader factory后，复用 `MFM_model_v3_clean_integration_v1/current/phychem_mfm/phase1/v3_data_adapter.py` 的 `RealDataProvider.prepare`（或 `make_proxy_inputs`）以及原 `V3StepTrainer.step/validate`，执行真实loader和逐head overfit；不把暂定试点改称Common或正式全量。

正式handoff最少使用：待实际发布的 `configs/data_v1/v1-pilot-provisional/D3_export.json` 中 `manifest_reference`、`store_references`、`actual_configuration_references`、`distribution.node/directory`、`actual_parent_accounting`及`D5_diagnostic_payload_reference`；另取已发布的[D2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)中registry/mapping/target_policy引用和[D4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)中statistics/population引用。[D5载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)提供 `selected_diagnostic_geometry_ids_reference`、`actual_seen_diagnostic_molecule_ids_reference`及其stores，角色保持 `TRAIN_UNSEEN_CONFORMATION`、`training_excluded=true`，仅893个试点已见分子，不将20k母名单全部算作试点已见，也不重拟合D4。

数据端统一读取入口为 `workflows.data_v1_final.export.pilot_family_D3_single_job_v1.payload_io.Reader`：以实际store目录构造，`get(gid)`返回训练metadata与数组（连续值为F32），`get_f64(gid, sidecar_reference)`恢复完整权威F64及原metadata，兼容D5未压缩旁车。节点本地路径按 `distribution.directory` 与源store相对路径映射，sidecar引用的path同步定位到真实本地文件，bytes/SHA不改。训练header仅保留 `source_trace_authority` 时，完整 `df_SOURCE_trace` 和原native控制证据从F64恢复，不要求重复放入训练header。r73保留ordered和单次F32，r674仍LOSS_DISABLED。当前 `Model_payload_ACK=false`；DataCodec就绪与D5交付均不代填实际模型验收。

## 2026-11-01 当前交付状态：v1-pilot-provisional

D-1 已按同一 v3.0 双方冻结，见[冻结记录](D1_v3_0_joint_interface_freeze_20261029_v1.md)。r73 权威 F64 与有序条目保留、训练仅转一次 F32；r674 维持 LOSS_DISABLED，不追加 QM。

D-2当前（2026-11-03）已发布[正式暂定注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)，包含146字段、全部76项实际TRAIN尺寸相关性及实际归一化/目标政策绑定。四份配置、header和rho已在CPU上独立核对完整哈希；这是组件交付，不等于D-3父作业C0或55k训练载荷就绪。D-5已交付[嵌套与留出清单](../../configs/data_v1/D5_v1_pilot_provisional_delivery.json)，包含120k⊂240k⊂600k⊂1,108,366 TRAIN、50k/5k试点和20k诊断母名单；实际D-3已见分子交集的诊断标签载荷尚未导出。

D-4当前（2026-11-03）：已正式发布[v1-pilot-provisional暂定归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)。全部首遍统计与MAD已闭合，最终实际进程1443031退出0、Source6 PASS/6/0/0，TRAIN-only 50k、VAL不参与；单遍、第二遍未执行、independent_numeric_replay_equal=null。D-3 4525587仍在compute-0-13 RUNNING/16CPU，76项rho和配置完成、复用已有几何建立导出索引。D-5全部113源组已安全关闭合并，4525591实际FAILED/3停在首批writer格式不一致；私有writer已按target分离granularity与完整F64原生注释。新writer-only父4525592已提交16CPU，仅复用闭合domain导出并执行原验收，不重投影源组。当前D-3载荷因已知一致性问题不自动发布，待真实关闭和新D-5发布后由已审查接续器复用几何/rho/四配置一次续接；活跃共享源码未改。原指南本地磁盘CPU读取验收另有独立草稿，不占GPU、不冒称Model ACK或D-6。整库及诊断载荷尚未交付，r674保持LOSS_DISABLED，无新增QM/UFF。见[当日汇总](../data_v1/progress_20261103_v1_pilot_provisional.md)。
P′完成下限仍1,060,508/2,119,502（50.04%），其中1,060,287全12项成功，尚无全量训练数据库。用户要求续跑后，实际4525495已C0，仅核对后清理116,708个已发布重复临时文件、释放8,890,447,289字节；新元数据接续连续两次失败，最后拦截为FRESH_QUOTA_CARVEOUT_AND_FINITE_PROVIDER_NO_RENEWAL，未产生新Native提交意图或QM作业，按用户STOP2要求记未解决并停止该修复；已申请仅一次30分钟已定位资源核算修复，尚未获批。Alpha PubChem保留TIMEOUT部分数据、NO_RELEASE，MoleculeNet/COCONUT保留9/11 READY。日汇总只维护[当日汇总](../data_v1/progress_20261102_v1_pilot_provisional.md)，以下旧时间点快照不作当前运行事实。
## 2026-10-30 D-5 v1-pilot-provisional 已交付

实际作业4525184已 COMPLETED / 0:0，Root 已接受并发布[正式D-5清单](../../configs/data_v1/D5_v1_pilot_provisional_delivery.json)与[交付说明](../data_v1/D5_v1_pilot_provisional_20261030.md)。已有完整S′的暂定母人群中，TRAIN嵌套清单为120,000 ⊂ 240,000 ⊂ 600,000 ⊂ 1,108,366；另含50,000 TRAIN与5,000 ROUTINE VAL试点。

20,000个TRAIN诊断分子各留出一个PM7和一个普通S′构象。全部训练清单在取前k之前，已排除留出基底、已登记子几何及实际输入视图；诊断仅用于预训练损失诊断，不用于模型选择。元素、重原子数、骨架分布对照及数据文件SHA由正式清单引用。

本项是暂定完整S′母人群的D-5交付，最终共同人群、D-6、D-7后续更新。D-3/D-4实际产物和模型加载验收仍待完成，当前D-5交付不等于训练数据已全部就绪。P′全量流程已按用户指令重新启动，首批8个输入准备任务128核运行；尚无新增QM产出。

## 2026-10-30 D-2 正式暂定定义字典已交付

版本 `v1-pilot-provisional` 的146字段定义字典已由Root实际生成并读回：[正式发布入口](../../configs/data_v1/d2_v1_pilot_provisional_registry/published.json)、[注册表](../../configs/data_v1/d2_v1_pilot_provisional_registry/source_dictionary_20261030_r1/label_registry_v3.json)、[模型线交接说明](../../configs/data_v1/d2_v1_pilot_provisional_registry/source_dictionary_20261030_r1/model_handoff.json)。字段ID、原mask schema、原生形状/单位与来源保持，r73永久F64及有序条目保留，r674维持LOSS_DISABLED，MolMR原单位UNKNOWN且相关物理损失关闭。

本项交付可用于字段与接口开发。`family_v1_final`、实际TRAIN尺寸相关性、HoF元素参考、归一化绑定、数值mask和55k payload仍待D-3/D-4实际闭合；不以默认尺度或虚构读回补齐，不充当D-3可执行配置或模型实际payload ACK。后续统计注册表另出不可变revision。D-3、D-4、D-5仍是当前优先任务；双集群并发背景生成不阻塞它们。

2026-10-29 当前：D1 v3.0 同版本政策与接口设计已由双方签署冻结，见 [双方冻结记录](D1_v3_0_joint_interface_freeze_20261029_v1.md)。D2–D6 的真实数据交付与验收仍分别待完成；下方旧 pending/draft 为历史记录。

## 2026-10-29：5A一次测试已结束，r674物理资格暂关闭，其他目标继续

[实际30次测试结果](xtb_native_frame30_actual_results_20261029_v1.md)：4524754 C0/84秒/16CPU，三项预检和全部30调用闭合；偶极与四极旋转10/10、偶极平移10/10；四极平移中性4/5、带电1/5。按原容差保留失败，不追加QM、不挑通过样本。用户1–4正式设计保持；未核实charged-origin目标按5A回退，r674暂 `LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND`、原值/6mask/F64及F/scale/偏差统计保留，其他ready目标继续。[实际物理暴露政策](../../configs/data_v1/interfaces/physical_exposure_after_native_frame30_20261029_v1.json)是本轮Root决定，待Model同版本签认；历史192坐标仍UNKNOWN，实际QM电荷与SMILES形式电荷分开。

## 2026-10-29：D1 v3.0 用户设计定稿，待同版本签认与限定物理测试

用户已选择 1A、2A、3A、4A，5A附一次半小时xTB坐标变换测试。正式设计、机器政策和五层映射选择已精确安装；不再重开算法草案选择。请模型线按以下同一 v3.0 设计及其实际 SHA 签认和实现：

- [正式设计合同](training_format_v3_0_user_frozen_design_20261029_v1.md)
- [机器政策](../../configs/data_v1/interfaces/D1_v3_0_user_frozen_design_policy_20261029_v1.json)
- [五层映射选择](../../configs/data_v1/interfaces/D1_v3_0_five_layer_mapping_selections_20261029_v1.json)
- [接合与实际证据边界](D1_v3_0_user_frozen_design_handoff_20261029_v1.md)

r73保留F64权威旁车，训练只转一次F32，独立有序双端channel域；r674保留全6分量，仅完整同几何进入tensor loss，c=0，实际TRAIN的winsorized Frobenius范数std为单尺度，d=9、delta=1的径向Huber。现有vector loss确为/3。尺度缺失/退化只禁本target loss，其他已就绪目标继续；源值与mask保留，不能造s=1。报告完整6资格排除率与元素/可靠结构分布，以及逐条原始F的mean(F)/s；现有winsor mean及均值张量的范数均不可替代原始E[F]。

5A限定试验正在准备（最多5分子×电荷0/+1×原始/旋转/平移=30次原版单点；16CPU、1800秒、无自动重试），尚无PASS声明。历史192项独立输出坐标仍UNKNOWN。Model的已有conditional反馈保留；本次同版本非conditional ACK、真实consumer、r73旁车恢复、r674张量loss与真实数据验收尚待，用户设计冻结不代表JOINTLY_FROZEN或release已可训练。

后台：S′4524666、原标签coverage4524729、PM7优先缓存4524738继续。Alpha COCONUT strict5任务1885088已实际RUNNING（16CPU/24h）且Source3及完整源码逆变通过；MoleculeNet闭合后去污染清单保守覆盖10/11，尚未全库放行。

## 2026-10-29：D1一次决议与已有完整S′试点优先

D1已收敛为[五项用户决议](D1_user_decisions_20261029_v1.md)，等待一次选择；Model已有conditional review，尚无joint v3.0。决议后直接接合同/五层映射与消费者，停止草案往返。192项独立坐标UNKNOWN和全部原值/mask继续保留。

[实际进度v6](../data_v1/actual_progress_20261029_pilot_priority_v6.md)：S′4524666与标签覆盖4524729正在日级作业内继续；PM7 4524738同父20预检PASS，优先旧完整S′的55k试点，再原全人口；P′4524740在软件asset路径检查处FAILED/168秒，3pure通过、0初始化/0新QM；限定软件reader修复继续。MoleculeNet4524733实际C0/35秒，21项保守排除覆盖完整、原图UNKNOWN21不改，现为10/11部分排除就绪，尚非全池放行。COCONUT1884790已C0/2939137物理行/46分块，strict5投影继续；Alpha两PubChem日父仍运行。

D2–D5尚未全部交付。试点独立使用已有完整S′，允许明确版本的暂定D4；全Common/D6补齐后更新。全部原质量门、原计数、失败/UNKNOWN和会计保留，D1–D7与250万扩充完整目标继续。
## 2026-10-28 D1 静态链与共同冻结候选

已补齐[原生token→解析→存储→调用控制链](D1_native_token_parser_storage_control_chain_review_20261028_v1.md)与[参数目录及共同冻结候选](D1_parameter_inventory_and_joint_freeze_candidates_addendum_20261028_v1.md)。r73候选保留权威F64 sidecar、双channel/原端点/重复项/原保留序号，consumer仅一次F32转换；r674确认是xTB原生traceless quadrupole的full6，完整分量资格、c=0及每condition单一TRAIN尺度需双方具体签定。radial loss、计数、尺度系列和真实head实现尚未共同冻结，不能据本候选声称consumer已支持。

唯一非空XTBPATH目录当前无.xtbrc，目录mtime/ctime早于调用期，原verification与冻结spec匹配。Root接受注明可信文件系统连续性假设的有限rc缺失推断；六参数表本身仍不等于完整目录枚举，192项独立坐标UNKNOWN保持。Model已有conditional review，尚无joint ACK；原科学QA矛盾未据此放行。

## 2026-10-28 日级任务实际更新 v5

S′4524666（compute-0-14/16CPU/24h）和标签4524665（compute-0-18/16CPU/24h）正在运行；内部批次不单独提交。HPC skill1.0.123已同步两份。Alpha两个32CPU/24h PubChem父及原48h Coconut父继续运行。

MoleculeNet4524659实际C0但HOLD21；4524667实际C0仅整理全部21项原证据，未改变UNKNOWN。D1已有Model conditional review，尚无joint ACK。失败父4524658/4524664及费用保留，窄IO修复已用于新父。[实际进度与限制](../data_v1/actual_progress_20261028_daypack_v5.md)。D1–D7和250万扩充仍继续，未声明整体完成。

## 2026-10-28 日级作业实际更新 v4

S′剩余续接已实际提交并RUNNING：4524658，compute-0-18/16CPU/24h，同父9项preflight PASS。Alpha两个32CPU/24h父1885075、1885076继续RUNNING，Coconut1884790沿用原48h父。规则已同步HPC skill1.0.123。

标签4524608是实际C0但业务资源STOP，仅完整哈希阶段可经下一CPU验证复用，未完成D4。MoleculeNet两次Source启动FAILED的Q/hashlib已修复，第三份暂未提交；正在核对全部实际API。失败费用及原产物全保留。[完整实际进度](../data_v1/actual_progress_20261028_daypack_v4.md)。D1–D7/250万扩充未整体完成，接口科学冻结仍按真实验收。

## 2026-10-28：四个日级父任务实际运行

最新状态见[单日打包实际进度v3](../data_v1/actual_progress_20261028_daypack_v3.md)。Main S′4524556/64CPU13 与标签恢复4524608/64CPU18 均为真实24h父任务；Alpha PubChem1885075/1885076各32CPU/24h，真实互斥接管247个未领取索引，旧253个消耗索引保留。标签新父9项预检与原whole3843检查实际PASS，正在CPU只读校验旧471171617813字节闭合缓存；不伪旧FAILED为C0、不重扫已读Parquet，也不称D4已放行。七来源实际C0并独立接纳，加Drugs/Kraken为9/11部分READY；MolNet全17与COCONUT尚未释放。skill1.0.123两份内容一致，后续按日级父任务和内部检查点执行。D1未jointfreeze、D1–D7及扩充完整交付尚未完成。

## 2026-10-28 08:54：七来源闭合与标签恢复

最新见[单日打包实际进度v2](../data_v1/actual_progress_20261028_daypack_v2.md)。七来源4524598实际C0/638秒，严格身份11469344条已独立接纳，结合Drugs/Kraken为9/11部分READY；MolNet全17及COCONUT未闭，不放行全数据池。407份P′留存物理事实已到，仍待Root科学审阅/Model最终policy，192项xTB无独立native坐标仍UNKNOWN。标签4524575实际FAILED于收尾缺失bindings导入，64worker已返回、471171617813字节旧缓存保留，正做同日级Parent只读恢复并续未读游标，不伪旧C0或重扫已读输入。S′单一64CPU24h任务4524556继续；Alpha两份32CPU日级任务等真实旧协调器/锁终止后互斥接续。D1未jointfreeze、D1–D7与扩充完整交付未完成，goal继续。

## 2026-10-28 单日打包与全量继续

最新实际状态见[单日打包进度](../data_v1/actual_progress_20261028_daypack_v1.md)。S′已改为真实64CPU/24h单一作业4524556，内部500仅作检查点；Drugs严格去污染身份投影4524566实际C0并独立接受，Kraken既有READY复用；标签数值余量正在改为单日父作业。1200次P′限定诊断已经完成，500项原向量比较实际通过，旧“待授权”段落保留原时间点历史；物理参考系/张量证据及正式2000/full仍待完整验收。全指南goal继续执行，D1仍未jointfreeze，D1–D7与扩充最终交付尚未完成。

## 2026-10-27 最新实际进度 v16

见[实际进度v16](../data_v1/secondary_main_actual_progress_20261027_v16.md)。Drugs全部558002 native图实际4523818 C0，技术unknown0，126 key差异/31名称完整并集保留。native384输入及原parser逐条复核3953 C0，r73/N/A与r674六值/打印trace/坐标证据如实分开，unit/sign/propertyaxes尚未接受。NEW20输入3779 C0，1200输入/0QM；执行器源码检查3855 C0，新1200限定授权待用户明确决定，原15FAIL与2000/fullHOLD保留。S′wave2观察101批闭合，原有限链继续；标签新book seed3763已实际C0但两处旧HOLD及TIMEOUT/逻辑费用保留。TRAIN512五轮C0、r5已提交，仍只是provisional诊断，不是D4。Alpha手动epoch source3实际1884950 C0，旧控制器deadline不变、新epoch未启动；PubChem所存点3200万原行/3282技术未决。模型公开HEAD已有draft4条件审阅，已纳入[draft5及公开补充](training_format_v3_draft5_public_head_addendum_v1/ADDENDUM.md)，不是jointfreeze或consumer实现。当前权威仍draft3。D1–D7及扩充交付继续，未开最终PR；以下历史段落按原时间点保留。

## 2026-10-27 最新实际进度 v15

见[实际进度v15](../data_v1/secondary_main_actual_progress_20261027_v15.md)与[P′15次独立精度诊断](../data_v1/pprime_strict15_precision_diagnostic_20261027_v1.md)。15调用/25向量比较/5同几何检查通过原容差，原15FAIL保留，2000/full仍HOLD；下一NEW20分子全12项QA待明确提案与授权。S′95和96已各500包实际闭合，后续97–179恢复有限CPU13资源链。Main新inventory/book/Common接口9测试实际PASS；native384元数据键全有，但basis/tensor/单位/轴仍待原生读取。Drugs原生1000图成功且无未知/来源差异，未代替剩余557002 SDF。Alpha Source27的3340文件、27+3测试及全SHA通过；PubChem所存点106片/2650万原行、2188技术未决保留。D1当前权威仍draft3，draft4待共同审阅；D1–D7及扩充最终交付未完成、未开最终PR。以下历史段落按原时点保留。
## 2026-10-27 最新实际进度 v14

见[实际进度v14](../data_v1/secondary_main_actual_progress_20261027_v14.md)。用户已批准限定15次P′独立精度诊断；Main实际源码门改在CPU15的4523054（原未启动2930取消、0核时），S′CPU17 source3的4522931仍待CPU，尚无新QM或新96科学执行。Alpha源码1884880实际C0，3249源与Main全集/字节一致、原checker/12portable pure通过；不能冒Main物理engine检查、环境或科学QC。PubChem所存观察点64分片/1600万原行闭合，技术未决1410保留，续跑仍受原绝对deadline约束。全原生39633结果清单C0，27原索引提取1884885亦C0，缺上下文与key UNKNOWN分轴保留；标签1904仍TIMEOUT，2748/2858待CPU。D1权威仍draft3，draft4待共同审阅；D1–D7及扩充最终交付未完成、未开最终PR。

## 2026-10-27 历史实际进度 v13

见[实际进度v13](../data_v1/secondary_main_actual_progress_20261027_v13.md)。标签首批1904实际TIMEOUT，独立只读核验2748排队，旧book/cache保留。Alpha六新分片均C0，实际已处理1450万物理行，872技术未决保留；metadata控制器HOLD修复不重算已完成分片。MoleculeNet39633物理SDF清单1884866已运行，TDC2证据1884865实际C0。新源快照校验将Alpha执行，不能替Main17实测、P′未批准诊断或任何科学QC。

[D1 draft4提案](training_format_v3_draft4_native_domains_proposal.md)仍待共同审阅，当前权威draft3；已有provider/采样桥接实际PASS不降级。最终D1–D7和扩充未交付，原P′质量HOLD保持。
## 2026-10-27 最新实际进度 v12 与 D1 共同审阅请求

[实际进度v12](../data_v1/secondary_main_actual_progress_20261027_v12.md)：S′94批闭合、95科学C0待索引、96全部未启动的技术恢复待新资源链；标签首批1904仍运行。Alpha修复51 C0，共52片/1300万物理行闭合，732历史技术未决保留，未全池放行。MoleculeNet原生3195试点C0，未知原因待0parse诊断。P′原质量HOLD保持，15次精度提案尚待用户批准。

请模型线共同审阅[draft4原生domain提案](training_format_v3_draft4_native_domains_proposal.md)与[D1剩余冻结项](../data_v1/d1_joint_freeze_remaining_20261027_v1.md)，重点为r73基函数通道/同原子/多条目线格式与r674张量消费及坐标证据。当前权威仍draft3；已有provider/采样桥接的实际PASS保持，未声称原生frame、真实全样本或最终契约已验收。
## 2026-10-27 最新实际进度 v10

见[实际进度v10](../data_v1/secondary_main_actual_progress_20261027_v10.md)。S′93批/46,500包；标签首32GiB全源续算1904运行。缓存TRAIN接入1915实际发现metadata浮点投影缺陷，v2待验证。Kraken全1552+21287来源键C0且差异全保留；QM7b7211帧C0、原图未知转冻结composition策略适配；Alpha45片/1125万原始行闭合。原P′科学HOLD保持，新精度提案未批准未执行。代码已同树发布v17，D1–D7及扩充最终交付继续。

## 2026-10-27 最新实际进度 v9

见[实际进度v9](../data_v1/secondary_main_actual_progress_20261027_v9.md)。S′当前83批/41,500包闭合；PM7首5000分子/39511记录C0；标签有界缓存10455比对一致。P′实际输入几何/JSON选择已核验，一般旋转科学检查仍FAIL，质量HOLD保持。TDC全44身份扫描C0、2未决保留；Drugs全量已提交、Kraken身份试点C0。Alpha六CSV全量C0、PubChem31片/775万原行闭合。D1–D7及扩充最终交付继续执行。

## 2026-10-27 最新实际进度：全部标签目录闭合

见[实际进度v8](../data_v1/secondary_main_actual_progress_20261027_v8.md)。2,208个源footer全部完成，待处理/错误均0；标签值、掩码、D4仍未放行。S′当前58批/29,000验证包闭合。Drugs原名称全对应，290多SMILES组完整保留；Kraken安全opcode探针C0；TDC全44身份任务已提交。Alpha点时20片/500万原始行完成，尚未去重去污染。原P′质量HOLD保持，D1–D7与扩充交付继续执行，未开最终PR。

## 2026-10-27 最新实际进度：S′恢复与官方MARCEL档案核验

见[实际进度v7](../data_v1/secondary_main_actual_progress_20261027_v7.md)。S′wave2当前40批/20,000验证包闭合；33仅修复metadata并保留失败成本，有限队列已恢复。PM7 HoF32的203记录及16golden位比对通过；标签512无损缓存通过。MARCEL两官方ZIP已CPU19 wholeSHA/全CRC C0，TDC44头/结构修正后C0；均尚未完成身份去污染。Alpha已闭合9片/2,250,000原始行。P′原15FAIL/2000与full HOLD不变，限定诊断0QM准备规格待CPU。全部D1–D7与扩充交付仍进行，原质量阈值保持。

## 2026-10-27 最新实际进度：N1真实第二几何与标签汇总

详见[实际进度v6](../data_v1/secondary_main_actual_progress_20261027_v6.md)。N1准备4521417 C0验证4631原baseline，真实UFF试点4521418 C0得到32/32真实第二几何，308优化完成，2个合法below0.5Å补齐；旧once账本保留。Alpha标签扫描1884788和原核汇总1884791均C0，6测试与227/65正文SHA实际通过；不是最终mask或D4。COCONUT全物理身份归一化1884790仍运行；P′15FAIL与2000/full HOLD保持。原Main两个只读重复排队任务仅在PENDING时hold并取消，绝不冒充Main C0。所有核时含失败/启动如实记录，质量阈值不变。

## 2026-10-26 最新实际进度：SQL全表与十一源载荷闭合

详见[实际进度v5](../data_v1/secondary_main_actual_progress_20261026_v5.md)。COCONUT全15表清点1884772 C0、十一源载荷1884784 C0、20000身份标准化试点1884785 C0；均不冒充去污染或最终数据完成。Main原空间成本4521316与S′历史产物闭合4521321 C0。N1 4521326实际母群5105与旧5040硬值不符，保留全母群作新版本核清；P′原15FAIL与2000/full HOLD不变。Native不变量首次1884786在启动storage-schema比较时退出，未读科学body，新版本修正中。标签Alpha原6测试后校验227正文并扫描，尚待实际结果。

核时超标报告后继续，质量门槛保持；下列历史快照按其时间保留。

## 2026-10-26 最新进度：完整SQL与独立16例读回完成

当前事实见[第四次实际进度](../data_v1/secondary_main_actual_progress_20261026_v4.md)。Alpha完整COCONUT SQL1884765已C0/5778秒，37,876,914,074字节与完整SHA闭合；结构检查1884767 C0，尚未证明全表身份覆盖。16例UFF独立读回1884768 C0/6秒，当前源码、配方和环境版本的有限软件兼容性由Root另行验收，人口新增0；未冒称Main执行或全量质量通过。

Main当前实际排队4521293/4521316/4521321/4521326/4521327，分别推进P′诊断、原空间成本试点、S′诚实闭合、N1真实第二UFF的输入准备及标签payload试点。旧4521315只在核PENDING/Elapsed0后取消替换，运行作业未被强制终止。核时超标报告后继续，所有质量阈值及P′2000/full QM HOLD保持。PubChem副本与P′原72例正在Alpha接入实际只读校验。D1–D7、共同人群、全量生成、去污染及首2.5M仍未全部完成；下列旧快照保留其原时间点事实。

## 2026-10-26 最新快照：核时超标报告后继续，科学质量不变

最新状态以[实际进度报告](../data_v1/secondary_main_actual_progress_20261026_v3.md)为准；以下旧段落保留其原时间点事实。用户已明确“核时超标报告后继续，质量阈值不变”，新权威为configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json，技能1.0.122已同步。标签余12片最终109.0933分配核时、约初估3.769倍，完整报告后继续。

16个标签源状态分片及汇总4521201均C0，覆盖1,220,466分子/11,231,854记录/2,024文件/14任务，尚待实际数组和JSON结构、单位/原生精度、物理/跨字段/分子内异常检查；未形成最终mask或D4。全本地身份已有404单元的11,398,552唯一身份，原4521152失败保留，只读闭合4521192 C0，仍未完成外部去污染或候选池释放。

Alpha软件对照1884766 C0/40秒，16个科学结果均精确匹配Main原包（仅排除elapsed），新增人口0；Main独立CPU读回入口已准备。官方COCONUT完整CSV ZIP1884764 C0/47秒，738,794行；完整SQL1884765仍在下载，未声称inactive全覆盖。Main当前4521293原生精度诊断、4521315构象334包+2未决诚实闭合、4521316全原始空间均匀10000成本试点已提交并排队，未占用其他作业CPU。

P′原15项协变矛盾及2000/full QM HOLD保持，2个S′超时任务不伪造包/科学阶段。PM7N1的第二真实UFF几何试点仍在接入，不能克隆几何。模型已有候选provider和四项合成串联实际4521005；[最新接口消费核对](../data_v1/interface_consumption_remaining_20261026_v1.md)区分已实现与真实authority/tensor/basis/perturbed/50kTRAIN+5kVAL尚待验收。D1draft3尚未共同冻结，D1–D7、ordered10M及首2.5M未全部完成；不开放最终PR。

## 2026-10-26 双集群实际进度：原资源限制已替换，科学门槛仍保留

当前进度以[脚本生成报告](../data_v1/secondary_main_actual_progress_20261026_v1.md)及其机器证据为准。主集群已实际使用CPU 12、13等节点且SBATCH无内存/exclusive申请；alpha@218.192.171.238已实际登录，独立gfshome环境1884762完成，状态只为READY_FOR_GOLDEN16_COMPATIBILITY_TEST。凭据未进入项目。

PubChem原始124,857,440行全EOF/CRC清点4521093完成；本地全源身份profile4521092、30项官方HEAD4521094完成，均不等于完整去污染或候选池。标签prepare4521101与首分片4521118完成，后续分片4521130–4521132已实际运行。P′ 72项frame4521124全部执行留存，但原15项协变准则失败保持，2000/full QM继续HOLD；新只读打印精度/真实输入诊断准备中；15项增量检查首次4521134因自身临时目录枚举竞争失败（已完成的3项子测试保留，整个父任务不称PASS），新入口修复后以独立输出技术重提。retention原4521125技术失败保留，新输出4521129已C0完成，未新增UFF/QM。

S′恢复4521110仍按原2 missing +14 controls执行；不根据已完成14个对照声明整个恢复完成。原334包复用，不改原task/seed。Alpha将先做固定16个已有SUCCESS小样本的软件QA，不加入共同人群；仍须实际完全匹配及Main独立验收，环境就绪不等于正式新数据完成。全指南/D1–D7/第一批2.5M仍未完成。

# 数据线与模型线接口状态

更新：2026-10-26。用户最新资源授权及实际落实优先见 [CPU节点与自动内存记录](../data_v1/cpu_nodes_auto_memory_actual_20261026_v1.md)：技能已更新1.0.120，科学CPU节点11–19；新sbatch不指定内存，按实际空闲CPU提交。4521065已在CPU12完成30项边界检查（C0/28s/16CPU）；旧9项严格内存任务已核PENDING并hold，正在用新资源入口替换。新队列4521077尚held，解析修复与8项新检查待闭合。S′旧6900秒成本估算漏计4520335准备费用，后续以完整实际费用及较短新时限为准。v1全部交付与扩充第一批仍未完成。

以下为该授权之前的阶段快照，旧64GiB/85%、仅14–19及八任务PENDING不再作为当前调度规则。科学事实和旧证据保持。
更新：2026-10-26。data-v1 仍在进行，最终真实数据未交付。最新可复算结果与全部父任务成本见 [CPU 实际报告](../data_v1/cpu_actual_sb5_sources_queue_20261026_v1.md)；报告生成入口为 workflows/data_v1_final/execution/cpu_analysis_v1/write_actual_report_v3.py。此前 [CPU 转移记录](../data_v1/cpu_transition_actual_v1.md) 保留原时间点结论。

- CPU任务使用实际cpu分区2、8–19；截至最新报告，8个严格规格任务在17和8排队。正式 S′/UFF/QM 仍限14–19、16CPU/64GiB、全部用户申报内存合计85%。零/缺失内存声明不作豁免；exclusive=user交给Slurm等待资源，启动仍须新鲜严格声明/live memory/quota证明。学校付费服务器与GPU禁用，其他用户和模型作业未改动。
- [八项实际阶段与三监控](../data_v1/registered_phases_actual_all_eight_20261026_v1.md)：原4520959–962保留；4521022为14队列+8来源边界检查，4521023为afterok1022的全人口磁盘索引准备；4521036身份导出试点与4521037原字节盘点也依赖1022。当前八项PENDING，尚无新增测试或科学PASS。实际readback均16CPU64GiB/exclusive=user/Requeue=0。三个监控已核对UID、boot/start_ticks、完整argv、PGID/SID、cgroup、源码及新鲜心跳，registry互不重叠；每20秒观察，24小时租期后须续接同一作业，不能重提。
- Se 单元素例外及 ROUTINE VAL 7610分子/72525 PM7记录保持；其余科学阈值不变。
- D-1仍为[draft.3](training_format_v3.md)，未共同签为v3.0。核对确认数据侧tensor六分量、按来源D5顺序/诊断anti-join及稀疏leaf原因已存在，详见[接口边界核对](../data_v1/model_adapter_alignment_v1.md)。新增按来源采样桥接已由4520608实际C0/1s/16CPU4GiB验证6项边界：PM7/UFF独立ID与顺序、诊断排除后energy training_rank=0最低能ID、碰撞/诊断回流拒绝。[实际验证记录](../data_v1/model_adapter_sampling_actual_v1.md)保留来源与成本。模型tensor消费、原因sidecar/provider及真实加载验收仍待模型线对齐；没有正式签署或契约意见冲突。
- 标签512分子4251记录、16源组、146分量的精确median/MAD/mask已实际闭合（最终reducer4520564）；各字段新增mask均0。拟合TRAIN4211，应用VAL20/FULL20。它仍是原source人口小试点，最终共同人群、geometry/order/diagnostic冻结后才计算D4。
- 全人口标签来源审计已有新源码和输入计划：1220466分子、11231854记录、14任务槽、2024物理文件；157245956个规范槽与8694个历史非规范行分别核验。新8项边界尚未实际执行；先准备磁盘索引，再仅首扫描分片实测，Root验收后决定余15片；560分配核时是申请上限而非实测预测。60GiB全阶段输出与200GB配额保留不变。[静态审查](../data_v1/source_status_static_review_20261026_v1.md)列明安全失败边界；尚未完成1.5数值扫描、掩码或D4。
- 尺寸相关性4520541实际完成：129物理目标/146分量，TRAIN元素参考与逐目标rho已保存。sigma/pi的物理不变性、部分单位/原生精度仍待证据，未据此冻结最终注册表。
- S′原336试点4520364为TIMEOUT/14425s/64.111111分配核时；只读审计4520527确认334完整可复用包、2缺包、0损坏；完整包中SUCCESS102，其余科学失败保留。新的独立恢复计划已提交4520960：保留334包，仅2原task/seed重放与14独立复现控制；16CPU64GiB/6900s的追加申请预算与旧成本合计94.777778核时，低于原96门槛；最终实际会计仍须包含调度清理时间。这是申请预算，无运行时预测或成本豁免，尚待实际测试、执行与新联合闭合。
- P′原1000分子/2000UFF与4520552的72组输入准备保留。4520961已排队执行原72次QM帧控制和原evaluator；4520962已排队做严格CPU64GiB的retention manifest准备，不进行UFF/QM。两者和S′恢复均依赖4520959的22项新增边界检查实际C0。2000构象12任务QM试点仍须等待frame实际PASS与retention实际闭合后冻结提交，之后按99.5%/11.7分配核秒门槛决定全量。
- [EA七例原生诊断](../data_v1/ea_known_seven_cpu_v1.md)已由4520570实际C0/20秒完成：7例、14上下文、16worker。复用同文件Parquet句柄并关闭旧句柄后，最高worker RSS为385368064B；96次打开/关闭、5560次复用，预算保持1280MiB/worker和全局32GiB/75%。14份canonical原始输出均未保留或不存在，根因仍UNKNOWN，未从NULL/缺失或跨方法能量推断SCF失败，未改标签或新增mask；约390条全人口计数仍待重建。
- PubChem官方raw SHA/CRC已通过；全X15879477记录回放一致率100%、未解释0，共同人群范围待最终绑定。首轮完整前缀4520593实际FAILED：753错误恢复，但320条原成功记录仅generic_ring_systems漂移，STOP保留。兼容版4520597实际C0/8s/16CPU4GiB，4项新边界PASS；10000行中8198旧成功全字段保持、8197历史存储行逐条核验、753错误全部恢复、1049化学排除不变，实际16worker。原raw与旧DB完整SHA保持；[兼容回放报告](../expansion/paired_prefix_compat_actual_v1.md)记录来源和组合证明。候选仅评估，未改pool、未放行全量筛选或去污染。
- 76个来源current pin已由4520547实际完成；这不等于全部身份导出或全划分去污染。新4521036只做65536 formal记录、全部4900 embargo及本地全来源集合的身份试点，保留SOURCE_*原逐记录成员布尔，不冒称新整分子VAL。4521037重验原gzip SHA/EOF/CRC并测真实行数，原字节TSV+有界JSONL在10GiB范围内；不化学筛选、不释放池。两项各在真实正文前运行4项新边界。全identity须实际profile及预算审查，TDC/MoleculeNet/MARCEL/COCONUT全来源证据仍待完成。
- D3/D4/D5/D6/D7最终交付、正式S′/P′与扩充第一批尚未完成，未开最终PR。最新实际总账为82个父任务：74个历史终态、8个PENDING；已观测累计76.55555555555556分配核时，包含所有失败和超时。0整秒值不解释为真实零成本；实际状态与来源见最新报告。

## 2026-11-05 窗口三 v2 执行说明

E1已完成，固定R/N各500万队列、首批各125万来源复用既有完整全池分数。根《PubChem 扩充任务书 v2（窗口三）.md》覆盖上方旧掩码停止、哈希/收据、独立QA和人工资源门：物理范围掩码只报告，不做新NN/相似度或去污染审计。E2/E3正在真实1万试跑1885278，未声明250万完成或训练格式就绪；后续Root自动提交剩余249万，最终仍需一页批次报告和GitHub交付。参见[每日汇总](../expansion/daily_20261105.md)。E2/E4实际完成后再追加完成通知。

## 2026-11-05 15:47 窗口三试跑完成、全批运行

1万分子试跑1885278已真实C0：R/N各5000、13,906构象，45.10%得到三个构象；源缺失和失败保留。剩余249万已提交1885281/1885282/1885283/1885284，Alpha 160CPU正在运行，采用试跑结果、不重算。E2/E3整体及E4尚未完成，不能声明全批就绪或训练格式ACK。见[每日汇总](../expansion/daily_20261105.md)，后续完成时再追加通知。

## 2026-11-05 窗口三 E4.3 科学口径待确认

原生状态确认增广参考NN作业未启动；现有结果只有到v1的分布。任务书同时要求加入后NN分布、又禁止追加NN/相似度，已向用户异步询问口径；不能把新增结构的自身覆盖替代该项或声明E4.3完成。全批1885281–1885284继续运行，不等待该问题；用户决定前不新增NN计算。

## 2026-11-05 16:40 窗口三 E4.3 单次增广NN授权

用户已明确授权“既定随机100万样本到增广参考的NN，完成前后分布对比”，取代上方待确认状态。范围仅原固定100万查询对完整3696122参考（原1196122顺序前缀+首批250万来源图指纹），保持指纹/成员/顺序/self-match语义，复用原生整数内核；不新增其他相似度或去污染作业。输入正在搬运，准备Main空闲compute-0-16、96CPU低优先级运行，让窗口二优先。1885281–1885284的UFF/D生产不变；E4最终报告必须包含真实前后分布及跨服务器实际核时，尚未声明完成。见[每日汇总](../expansion/daily_20261105.md)。
2026-11-05 16:41补充：授权NN真实作业4526054已RUNNING，Main compute-0-12/96CPU/Nice1000；因窗口二开始使用16，提交后在尚未启动时移至空闲12。全部输入搬运完毕，新增4项单测及14变更文件检查通过；已开始完整增广参考准备，未宣称NN已完成。

## 2026-11-05 18:49 窗口三授权NN完成、全批继续

单次固定100万增广NN作业4526054已真实COMPLETED/0:0：原1196122参考顺序前缀加首批250万，完整参考3696122；原查询成员/顺序、指纹和self-match语义保持。均值0.519917→0.631870，低于0.4比例18.66%→2.93%，730565条查询提高；100万行/100个Parquet已完整回传Alpha `/gfshome/alpha/pubchem_window3_v2_20261105/nn_after`。本作业已释放Main compute-0-12的96CPU分配。1885281–1885284仍在生产，最新累计364304来源、359500构象（含试跑）；E2/E3全批和E4最终批次报告仍待完成，之后再追加完成通知。见[每日汇总](../expansion/daily_20261105.md)。
## 2026-11-06 给窗口一/窗口二/窗口三及所有子agent的用户通知：节点磁盘保护

用户明确要求：以后往各节点传输文件时必须保证不要将磁盘占满，并让其他正在工作的Codex知悉。各窗口在下一次节点传输/缓存/解压/生成临时文件之前，重新读取项目根AGENTS.md及huagong_hpc_requirement技能顶部2026-11-06条款并在本状态文件追加简短已读确认；本通知写入不代表已经取得其他会话的已读确认。

必须检查实际目标节点的目标文件系统、可用字节和inode，计入复制/解压/数据库临时峰值、残留与跨窗口同盘并发写入；根分区至少保留max(10GiB,10%总容量)，站点更严格规则优先。空间不足或容量不明时不传，改经核实的scratch/共享盘或减小批次；传输中在触及预留空间前停止新增写入。/tmp可能占用根盘及Slurm共用空间。新传输/缓存入口必须落实检查与运行期保护。原始数据、其他窗口作业、管理员目录和drain状态不因这条通知获得修改/删除授权。

事故依据：节点17作业4526050于11月5日16:33向/tmp复制约29GB数据库，部分文件17,656,872,960字节，ENOSPC与SlurmdSpoolDir is full drain同刻；节点20作业4526119于11月6日01:35取消清理时一个进程未退出，触发Kill task failed，不能混同为磁盘满。

## 2026-11-06 05:07 窗口三已读并落实节点磁盘保护

本窗口已读取HPC skill 1.0.148及11月6日节点磁盘规则。已在Alpha compute-0-1/2/8、sonmi1实核挂载、可用字节和inode；/tmp与50GiB根分区共盘，根盘剩余约32.4–41.5GiB，系统/Slurm预留至少10GiB。UFF/D缓存、gzip、Parquet及临时导出均写共享/gfshome，不追加节点本地大缓存。

Alpha账户共享盘当前约1.288TB可用、约13.98亿空闲inode；四分片已有109670126080字节。按剩余人口、最多320个256分子分块及4倍观测尺寸估算后续约52.6GiB。本窗口在该盘合计预留256GiB后续增长和500000inode，另保留100GiB/10000inode；不是每节点独占一份。其他窗口在相同Alpha账户盘计划写入时应扣除此预算，不能重复使用同一空闲量。新传输/缓存仍须目标节点预检和运行期保护。

磁盘观察的5项新逻辑单测通过；1885281已自然COMPLETED/0:0，无活动写进程。1885282/1885283/1885284已分别在实际节点启用观察，容量未知或不足时只SIGSTOP匹配本UID/作业ID且start_ticks未变的进程，保留内存和检查点，不取消或科学重试。sonmi1后台观察未保持存活，已改为经实际PID/新鲜状态确认的持久SSH前台观察。其余生产代码、标签/掩码和其他窗口作业未改。当前E2/E3全量和E4最终报告仍待完成；见[11月6日日报](https://github.com/mint258/MFM/blob/data-v1-pubchem-completion-20261103/docs/expansion/daily_20261106.md)。


## 2026-11-06 15:53 窗口三 E2 完成：首批250万 UFF/D 已闭合

Alpha四个全量作业1885281/1885282/1885283/1885284均真实COMPLETED/0:0；末个1885283的batch/extern亦0:0。生产者累计2,500,000分子（R/N各1,250,000），3,485,968个实际构象；原1万试跑直接复用。原S′/UFF参数、固定30内部候选/种子/顺序、0.5Å去重及最多3个实际构象保持，不补足、不重试；D20每分子一次，D3/逐原子SASA逐实际构象。v1家族Parquet及v2_candidate/R/N/CID/版本字段已写出，失败与物理掩码保留。报告合并步骤已通过生产者家族行数对齐条件，未启动独立QA或二次Parquet读回。

数据根 `/gfshome/alpha/pubchem_window3_v2_20261105`；唯一最终路径/大小/行数清单 `delivery/manifest.json` 已生成（11,356,157字节，含本次授权的100万NN逐查询文件引用）。协调进程11778正在由原du子进程24256统计实际占用，最终batch_summary和一页GitHub报告尚待写完，E4此刻未宣布完成。草稿PR1继续未合并；不做QM/P′或训练格式导出，不动v1。

磁盘观察1885283已记录NO_JOB_PROCESSES，匹配活动进程0，四作业均已结束；原256GiB/500000inode的后续生产增长预留现在释放，仅保留64MiB/256inode用于Alpha报告收尾。账户100GiB/10000inode底线不变，既有文件仍按实际占用计入，未删除任何数据。其他窗口再使用该盘前仍须实际目标预检与同盘并发预算，不能把这次释放视为容量保证。

窗口三补充：E2已完成；E4以报告推送后的正式追加通知为准。


## 2026-11-06 16:04 窗口三 E4 完成：首批250万已完整交付

E2/E3全部生产及原生会计已关闭，协调进程11778正常结束；一页批次报告已实际推送并读回确认：[PubChem v2首批报告](https://github.com/mint258/MFM/blob/data-v1-pubchem-completion-20261103/docs/expansion/pubchem_v2_batch_report_20261106.md)。[PR1](https://github.com/mint258/MFM/pull/1)保持草稿、open、未合并。R/N各1,250,000来源，3,485,968实际构象；恰3构象1,131,093（45.24%），不足3和失败按原状态保留。

唯一清单 `/gfshome/alpha/pubchem_window3_v2_20261105/delivery/manifest.json`：11,356,157字节，70,394个Parquet引用、59,405,222,512字节，仅path/size/rows；D20/source_status各2,500,000行，D3/geometry各3,485,968行，含授权100万NN逐查询结果。完整失败/掩码/会计在同目录batch_summary.json；物理新增掩码仅PMI1两条，D20源缺失595另计。固定100万查询NN均值0.519917→0.631870，全部来源图（含UFF失败）及自匹配口径保持；CDF仅绘制已关闭分箱，无新NN或科学数据读回。

本轮试跑/生产/统计/授权NN分配2,917.91核时（含失败/续接），分子内CPU 2,243.95核时。Alpha本批目录实际120,345,793,536字节，Main NN目录4,753,616,896字节；这些是已发生占用，不能当作未来预留重复相加。早期筛选/排序/全池NN成本按周汇总。无QM/P′或训练格式导出，v1未改，无新增hash/收据/独立QA。

四个生产作业及所有本窗口磁盘观察均已随完成退出；原256GiB/500000inode生产增长和64MiB/256inode报告收尾预留均释放，实际数据/候选缓存全部保留。Alpha账户100GiB/10000inode底线继续有效；其他窗口的新写入仍须目标节点实核容量、quota和全部并发预算。本窗口任务书E1–E4完成，后续v3.1训练格式导出由窗口二统一处理。

2026-11-06 窗口三立体补跑进行中：按用户已批准的新规则，仅首批1,285,342个原STEREO_REFERENCE_UNAVAILABLE_NO_PM7分子补跑，已成功几何和原D20不重算；MID独立公平立体随机流，全部嵌入/UFF候选失败才最多4次立体重抽。旧250万全来源图固定100万NN已完成并复用，不重复。Alpha共享盘本次预留512GiB新增峰值/1,000,000inode（含准备、缓存、临时及残留），另留账户100GiB/10000inode底线与16GiB运行期写入突发余量；这是本次全节点合并预算，不能各节点重复预留。旧parent_a/b的Oct28历史预算不活跃，当前Alpha用户squeue为空，旧窗口三生产256GiB预算已在E4完成时释放。四个目标节点已实核findmnt/df字节/inode，共享账户有效2TiB、可用1,279,141,961,728B，各根分区可用34.8–44.6GB；数据/临时写共享盘，根保留max(10GiB,10%)。新任务执行前与执行中继续真实磁盘保护；当前只测新逻辑，无冒烟、数值二次读回、新hash或收据。尚未宣布补跑完成。
2026-11-06 窗口三立体补跑续接：新逻辑13项单测已通过（仅合成结构、模拟native失败、元数据/成员筛选/协调脚本；不含NN或分子冒烟）。旧名单准备1885295只读元数据、零科学调用，因共享盘SQLite小写入而在该边界取消，所有中间文件保留；1885297用内存SQLite和8路有界元数据预取/4CPU，已流读全2,500,000状态并选出恰1,285,342目标，索引一次写回共享盘中，无/tmp缓存。生产采用新冻结runtime window3_stereo_v3_20261106，四互斥余数分片仍64/32/48/16CPU；原已指定未来输入保持原键/邻接顺序和原UFF路径，未改变普通失败分类。根协调器只在真实C0和准备闭合后提交，不做试跑。旧全来源图固定100万NN直接复用；仅含3D的补充参考保留全v1顺序前缀及原chirality=False指纹。为该后续Main覆盖行另预留16GiB新增峰值（含成员文件、参考打包、临时和残留）；最新Main原生quota可用340,390,498,304B，须同时扣窗口二160,993,980,283B、账户100GB、既有模型/控制6GB与8GiB突发余量；实际启动/传输前仍须目标节点实核和运行期quota/字节/inode保护。Alpha原512GiB/百万inode全节点共用预算继续有效，补跑尚未完成。
2026-11-06 窗口三立体补跑已正式启动：准备1885297真实COMPLETED/0:0，elapsed768秒/4CPU；元数据输入确认旧含3D分子1,188,667、旧实际构象3,485,968，选出恰1,285,342条旧立体参照缺失记录。1885300(compute-0-1/64CPU)、1885301(compute-0-2/32CPU)、1885302(compute-0-8/48CPU)、1885303(sonmi1/16CPU)均实际RUNNING，共160CPU，互斥mod10余数分片、batch128，无冒烟。四个精确作业磁盘观察均WATCHING；共享账户可用约1.272TB，各根盘可用34.8–44.6GB，根max(10GiB,10%)及共享100GiB/10000inode底线正常。Alpha512GiB/百万inode合并峰值和Main后续3D覆盖16GiB预算继续预留；全来源图旧NN不重算。代码/13项新逻辑单测/5399源码检查已推GitHub f5c6433，草稿PR1未合并；本地AGENTS.md用户修改保持未暂存。协调器22331只在四作业真C0后接状态扩展/仅含3D成员生成；最终覆盖、报告和完成通知尚待，不能把已启动写成补跑完成。
2026-11-06 窗口三目标节点实核补充（供所有窗口）：Main compute-0-17 虽sinfo显示CPU可用，但实际根盘 `/dev/mapper/sonmihpc_compute--0--17-root` 总75,125,227,520B、仅余36,577,280B（100%），inode余188,494，/tmp同根盘。已排除该节点的新传输/缓存/临时写入与后续覆盖作业，不以共享盘5.7TB余量或CPU空闲替代根盘保护；本次仅只读检查，无新增节点文件、不删除未知文件、不改管理员/drain。后续Main考虑已获准compute-0-21并另行实核；本通知不表示21已经准入。Alpha四个立体补跑继续，均有根盘/共享盘精确作业保护。
2026-11-06 窗口三Main准入保护：compute-0-21已只读实核，根盘总954,159,071,232B、余830,653,652,992B/inode465,702,216，满足max(10GiB,10%)系统余量；共享NFS仍按原生用户quota而非整盘df准入。Main4526176/compute-0-21/1CPU真实C0，3项新增合成quota保护单测通过（总新增16项；未查询真实quota/未发信号/未调用NN）。新增可选quota_guard仅供后续Main写入，联合UID/原生quota可用量/20秒新鲜度与既有未来预算，未知或不足时暂停自己写入；未改动Alpha冻结runtime或已运行科学核。此刻只做了源码/单测，尚未向Main传输3D成员或启动新覆盖NN；仍须启动前实核当前quota与跨窗口预算。Alpha四个立体补跑继续原160CPU，完成以最终真实产物和追加报告为准。
2026-11-06 窗口三未来R/N失败路径补齐：Main4526177/compute-0-21/1CPU真实C0，两项新增模拟单测通过（总新增18项）。未来新批次先对原来源图计算一次D20，即使随后立体规范化失败也保留该已算D20；无效来源清空当前D20，不继承上一分子。原来源图缓存只在原键校验成功后绑定当前source，立体重抽不重复图校验或D20。首批补跑仍复用旧D20，当前Alpha冻结runtime/四作业未修改、未重启、未重算任何已有构象。没有新增科学核冒烟或数值QA；后续仅3D覆盖与最终追加报告仍待这四作业真实闭合。
2026-11-06 窗口三立体准备边界已修复：初始闭合分块暴露N–H亚胺无显式双键参考及桥头元素后显露的问题，均发生在嵌入/UFF之前。显式H/规范化闭包7项相关单测在Main4526178真实C0（RDKit2025.09.5），新增修复选择/合并两项及受影响元数据/脚本5项在4526179真实C0；effective计数/顺序的2项受影响fixture在4526180真实C0。唯一新增逻辑共22项通过，无UFF/NN冒烟、无数值二次读回。冻结runtime window3_stereo_v5_20261106已用于准备修复/收尾，协调器30620（coordinator_v4_config.json）仅替换旧的元数据等待进程；1885300/301/302/303及其保护进程全部未改动/未重启，原160CPU继续。

每个初始分片真实C0后，协调器只选择actual_conformers=0且明确在任何嵌入/UFF调用前返回的旧STEREO_REFERENCE_UNAVAILABLE_NO_PM7或POTENTIAL_DOUBLE_WITHOUT_STEREO_REFERENCES；只为这些零原生调用记录接一次正确准备路径。普通原生失败/其他完整性错误/已有正构象数均排除，不扩充4次立体组合预算、不补构象、不重算D20。原始及阶段中间文件都保留，最终canonical source_status保留所有原列并添加effective状态/实际数/顺序等消费接口和stereo_preparation_repaired标记；R/S、E/Z计数替换旧准备失败部分，避免重复MID。全图NN旧结果继续复用，最终仅3D覆盖及报告尚待真实生产闭合。Alpha全节点512GiB/百万inode峰值与Main后续16GiB预算/账户底线继续有效；Main17根盘不合格仍排除。
2026-11-06 窗口三仅3D覆盖准备：Main冻结代码及配置模板已写 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/window3_nn_3D_stereo_20261106`，只复用旧inputs与已验证原生.so，未启动NN/打包参考/传输3D成员，模板added_reference_molecules为null，等待最终闭合名单。Main21实核根盘余830,653,849,600B/inode465,702,216，NFS inode2,966,296,735，原生用户quota可用340,380,676,096B；当前联合底线/其他窗口预算/本16GiB及8GiB突发合需292,763,784,059B，准备代码小复制在预算内。正式启动仍须刷新窗口二剩余预算和目标容量，再启原生quota发布器/作业保护；Main17继续排除。Alpha1885300–303仍实际RUNNING/合160CPU，协调器30620实际存活，四观察WATCHING；补充未完成，不发布完成通知。
2026-11-06 窗口三收尾入口准备：Main仅3D NN的run.sbatch已写并通过bash及内嵌Python语法检查，未提交；要求闭合3D名单/摘要、真实目标及新鲜原生quota后才可运行。新增stereo_report.py只从闭合摘要/清单/资源会计追加原报告和3D覆盖引用，不读回D20/D3/坐标、不重算旧全图NN；尚未实际生成补充报告。Alpha四作业及协调器30620已再次核实存活，原160CPU与磁盘保护继续，目标仍进行中。
2026-11-16 · 窗口三未指定立体补充完成：原1,285,342独立分子及58,296零原生调用准备修复已闭合，最终2,352,284含3D分子/6,893,024实际构象；原D20、SMILES/CID/state及历史文件保留，消费effective_*。后续单分子UFF全部候选/抽取累计3600秒硬截止持续生效，CID172104056已终止，最终18条UFF_TIMEOUT/unknown单列；旧1885300 FAILED及成本保留。最终有效重抽189,314（零构象116,503/未知13），历史处理事件191,380另列。仅3D NN1885927真实COMPLETED/0:0，100万查询/3,548,406参考，NN均值0.519917→0.629899；全图原结果0.631870复用。完整补充26个Slurm作业30,014.82分配核时，Alpha新增目录观测133.066GB；唯一最终清单/gfshome/alpha/pubchem_window3_stereo_20261106/delivery/manifest.json含113,207条Parquet引用/119,703,753,472B，batch_summary.json链接NN与资源。最终报告/完成日报/源码已推GitHub 6a5bc853ec838c38481b329fef5371c2c51a01c0并逐文件核实，PR1保持open/draft/unmerged；限时相关29项、汇总修正3项测试及最终仓库检查5415文件通过。确认本窗原生NN进程已清空，本次2小时监测随计算完成结束；本窗Alpha保守512GiB与Main最后2MiB的未来新增增长预留在本条收尾后结清为0，现存文件仍保留并计df/quota，其他窗口预算不变。完成通知。

[跨线 用户指示 2026-11-22 15:40 CST] 新增 docs/interfaces/STORAGE_GUARD_20261122.md 与 tools/shared_guard.py：存储/内存预留改为共享登记目录 runs/shared_storage_reservations/，每条线只写自己的 <线名>.json，每次轮询续期，写完释放；新作业用 check_with_timeout()（60 秒超时即拒绝）。不再抄写或公告他线存储数字。在跑作业不动，下一次轮询起迁移。
