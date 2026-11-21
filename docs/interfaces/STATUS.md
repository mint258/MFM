## 2026-11-05 用户授权旧D3 v3.0清理已完成

旧训练库、派生F64旁车、无用SQLite及GPU21旧副本已删除；保留原始native LMDB、WP5 Parquet、正式元数据及当前v3.1共享/10GPU成品。以[当前v31入口](../../configs/data_v1/v1-pilot-provisional-v31/D3_export.json)为准；旧索引仅作历史，不可再作为可加载数据。D6继续暂停。

## 2026-11-05 D-3 v3.1紧凑试点已交付，模型验收待

同一55k已按MFM4完成，唯一1000样本/NaN及计数检查通过、两库compact并rsync --sparse至全部计划GPU节点。详见[正式v31索引](../../configs/data_v1/v1-pilot-provisional-v31/D3_export.json)与[第6项修订](training_format_v3_1_storage_revision_20261105.md)。原v30不删，Model payload ACK仍false，D6及之后继续暂停。以下为历史。

## 2026-11-05 D-3 v3.1 紧凑重导运行中

用户已提供明确修复要求：同一 50k TRAIN＋5k ROUTINE VAL，改为每划分单默认库及 MFM4 数值数组，源字段/掩码/构象顺序/D5不变。r73 有序多通道四数值数组扩展已获用户确认。实际作业 4525960 在 compute-0-21、16CPU 运行，初始已写 2725/55000 MID；当前仍是导出，不提前声明末尾校验/compact/分发完成。v3.0数据、F64旁车和GPU副本均保留；本轮不新建F64副本、不重算文件/记录SHA、不测吞吐。D-6及之后继续暂停。

[D-1 v3.1第6项修订](training_format_v3_1_storage_revision_20261105.md)供模型线确认；不等确认完成导出。MFM4代码实际提交8865115f0f4906ced5a4a931188c99ea620f6f66，已推送现有交付PR2分支；实际模型加载/逐头过拟合 ACK 仍待。后续以本次最终manifest和当天汇总为准，以下保留历史时间点。
## 2026-11-05 用户报告 D-3 问题，D-6 及后续暂停

用户报告 D-3 出现问题，具体报错/日志尚待提供，当前优先定位 D-3。已有交付文件、原作业 C0 和末尾校验历史保留；Model_payload_ACK 仍为 false，不以导出完成代替真实模型验收。D-6 及之后按用户指令暂停，相关候选开发和新提交均已停止，等待用户明确恢复。以下“已交付”描述仅记录既有产物，不表示本次问题已解决。
## 2026-11-05 当前：D-1冻结，D-2至D-5试点已交付

D-1双方接口固定为v3.0。[D-2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D-3正式导出](../../configs/data_v1/v1-pilot-provisional/D3_export.json)、[D-4暂定归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D-5同父绑定诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload_D3_job4525880_bound.json)均已交付，统一为`v1-pilot-provisional`。不代表最终Common或D-6/D-7完成。

D-3实际父4525880原生COMPLETED/0:0，UID1278、compute-0-8、16CPU，ElapsedRaw9785秒。50,000 TRAIN与5,000 ROUTINE VAL，2,915子库、32,022,963条几何/家族记录。原唯一计数与1,000条原Parquet逐字段比较全部通过（987分组、2,698 target pieces）；一次总清单SHA、一次rsync --checksum返回0。训练LMDB及清单共575,161,700,855B已复制到`compute-0-21:/tmp/dv1_pilot55k_20261103_9b66baf693`。原单次4-reader读取180.033秒，约11.981分子/秒、6994.720记录/秒，64 MID窗口、rsync后缓存状态，不是全库冷缓存吞吐。无独立复核、全量F64二次扫描或新QM/UFF。

D-4只拟合50k TRAIN，VAL不参与；保留原唯一完整统计与MAD结果，没有完整第二遍复算。D-5保留12万⊂24万⊂60万⊂1,108,366的嵌套TRAIN及20k诊断母清单；当前893个试点已见分子的12,502个未见几何、43,757标签记录/53库已真实绑定D3的50k TRAIN，`TRAIN_UNSEEN_CONFORMATION`、`training_excluded=true`，不将20k母名单全部冒称试点已见。

本试点包含PM7 S/D/P及已有UFF S′几何，不包含UFF D′/P′标签；146启用字段、129物理目标。r73完整有序F64留共享Lustre，训练仅转一次F32；共享永久F64共398,342,180,864B不复制到GPU，其原路径/引用保持。r674保持LOSS_DISABLED，不追加QM。`Model_ACK=false`、`Model_payload_ACK=false`；实际Model loader与逐head overfit由模型线后续验收，D-3 C0不代填该ACK。统一Reader及重定位规则见以下既有接线说明。

方法、输入哈希及脚本生成统计见[正式训练导出报告](../data_v1/training_export_v1_pilot_provisional.md)；进度仅维护[当日汇总](../data_v1/progress_20261105_v1_pilot_provisional.md)。P′原冻结ready范围已完成计算与覆盖：1,110,751分子、2,221,502构象、缺失0，全12项成功2,217,077（99.80081%），最终原生审计4525885 C0；科学失败和N1不可用排除保留，不代表Common/归一化/异常值扫描或P/P′分布对照已完成，见[P′正式说明](../data_v1/pprime_labels.md)。MoleculeNet/PubChem继续后台推进。S′原补齐尝试均已终态归档但保留UNKNOWN/科学失败；下一步为原普通构象排序/统计与最终Common绑定，不重新生成全部S′。D-6仍需最终Common、三序/D7、全TRAIN统计、P′覆盖及模型实际payload ACK。以下均为历史时间点。

## 2026-11-03 当前：D2/D4/D5已交付，D3转Lustre CPU续接

D-3尚未交付。141/171个实际闭合源组已保留，固定55k和科学编码器保持。4525664与4525665在compute-0-14/16CPU启动检查失败（0秒、5秒），均未开始数据处理；遵照用户连续失败2次规则，该接续修复现暂停并记未解决，等待仅补齐闭合索引引用后再提一次的限定授权。compute-0-21目前DRAIN；CPU路由、无时间/内存停止门和原一次末尾验收保持。后台Common已恢复后实际FAILED/1，不自动重跑。

[D2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)已交付；D5实际父4525593 C0/1607秒，893个试点已见分子、12,502几何、43,757标签记录、53子库。全局嵌套与20k母清单保持。r73完整有序F64、一转F32；r674 LOSS_DISABLED，无新增QM/UFF。详情只维护[当日汇总](../data_v1/progress_20261103_v1_pilot_provisional.md)。以下旧时间点作为历史。

Model接线补充（2026-11-03当前观察点）：D3已保留141/171个闭合源组，最新启动检查失败并已按STOP2暂停修复；payload未交付。DataCodec读取接口已就绪不代表D3载荷已交付。现有 `CandidateWireFactory` 和 `synthetic_head_overfit.py` 仅支持合成fixture，不能作为本轮真实验收。模型线接好本次 `v1-pilot-provisional` 解释器、TRAIN/VAL/TRAIN_UNSEEN_CONFORMATION三个role indexes和readonly reader factory后，复用 `MFM_model_v3_clean_integration_v1/current/phychem_mfm/phase1/v3_data_adapter.py` 的 `RealDataProvider.prepare`（或 `make_proxy_inputs`）以及原 `V3StepTrainer.step/validate`，执行真实loader和逐head overfit；不把暂定试点改称Common或正式全量。

正式handoff最少使用：待实际发布的 `configs/data_v1/v1-pilot-provisional/D3_export.json` 中 `manifest_reference`、`store_references`、`actual_configuration_references`、`distribution.node/directory`、`actual_parent_accounting`及`D5_diagnostic_payload_reference`；另取已发布的[D2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)中registry/mapping/target_policy引用和[D4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)中statistics/population引用。[D5载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)提供 `selected_diagnostic_geometry_ids_reference`、`actual_seen_diagnostic_molecule_ids_reference`及其stores，角色保持 `TRAIN_UNSEEN_CONFORMATION`、`training_excluded=true`，仅893个试点已见分子，不将20k母名单全部算作试点已见，也不重拟合D4。

数据端统一读取入口为 `workflows.data_v1_final.export.pilot_family_D3_single_job_v1.payload_io.Reader`：以实际store目录构造，`get(gid)`返回训练metadata与数组（连续值为F32），`get_f64(gid, sidecar_reference)`恢复完整权威F64及原metadata，兼容D5未压缩旁车。节点本地路径按 `distribution.directory` 与源store相对路径映射，sidecar仅在distribution明确标记已复制时映射到真实本地文件；F64_authority_copied_to_gpu=false则保留原共享Lustre path，bytes/SHA不改。训练header仅保留 `source_trace_authority` 时，完整 `df_SOURCE_trace` 和原native控制证据从F64恢复，不要求重复放入训练header。r73保留ordered和单次F32，r674仍LOSS_DISABLED。当前 `Model_payload_ACK=false`；DataCodec就绪与D5交付均不代填实际模型验收。

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

## 2026-11-05 窗口二任务书v2开始执行（当前）

本任务书解除旧D6暂停并取代旧数据线准入/多层证据门。delivery/d3-v1-pilot-20261105已并入data-v1并推送。D1 v3.1存储修订和既有55k D3/10GPU分发继续有效；训练视图生产中，模型阶段5 P/D使用前须消费即将冻结的configs/data_v1/training_view_v1.json。当前Common1220466源遍历完成，但S′收尾、最终Common/D4/D5/D7及D6尚未交付。跟踪[一页DAILY](../data_v1/DAILY_20261105.md)；D6完成后再在此通知真实路径，不能以正在运行代填完成。

2026-11-05 B2候选已生成：50k TRAIN完成一次统计，134列纳入、7项众数退化字段与r674六分量排除。r73实际有混合对称性/δ条目，两列归属定义已请求用户决定；当前training_view_v1.json为候选，模型线P/D阶段5须待其status正式FROZEN后消费。


2026-11-05 B2正式冻结：用户已批准r73同对称性分块，sigma-sigma求和为sigma、pi-pi求和为pi，mixed/delta不纳入这两列，原始r73完整保留。训练视图 configs/data_v1/training_view_v1.json 状态为FROZEN_BEFORE_STAGE5_PD；134个启用目标，7个众数退化字段及r674六分量排除，组内字段等权，无覆盖率/冗余筛选。说明见 docs/data_v1/training_view_v1.md。最终PM7与Pprime D4将各给这两列独立统计，不拿raw-K统计冒充。

## 2026-11-05 窗口二：已冻结 r73 目标的存储绑定

用户已批准同对称性 SIGMA/SIGMA、PI/PI 分块。134 个训练字段与排除项保持冻结；`training_view_v1.json` 的 `preferred_schema_selector` 优先读取 D6 `schema.derived_r73_pair_targets` 所声明的 array27 列：原始 F64 分块求和后只转一次 F32，与最终 D4 一致。原 r73 四数组完整保留；历史 D3 无此 schema 映射时按原 F32 K 聚合，保留其存储舍入，不重新导出 D3。通道整数必须按各数据集 schema 的标签字典解析，不能将试点代码表当作全量通用表。D6 全量交付仍在进行，未分发完成。

2026-11-05 模型窗口一接线通知：model-v3 已按冻结清单接入134个存储列，r73优先schema.derived_r73_pair_targets预聚合列，历史D3按各自码表聚合原F32 K。训练保持原physical target语义：偶极xyz共用一个等变头、一个径向Huber及一个组内权重；列级R²分别报告，不把分列统计改成三个标量损失。r623/624/625使用真实array22，缺几何且无标签时保留缺失。

2026-11-05 M2的D4接线需求：现有旧及window2统计代码的vector_tensor_single_scale_training_route仍标PENDING_ACTUAL_JOINT_POLICY_RELEASE。请D4交付明确的field/physical-target→series_key、center/scale、能量元素参考映射，或已有正式方针与数值产物引用；模型负责接口翻译，不要求另一次扫描、拟合、复核、哈希或收据。矢量沿用零中心及同一尺度，Pprime独立；不以B2原始统计或raw-K参数冒充σ/π D4。按用户答复等待窗口二对应交付后执行M2。模型代码与接线状态：mint258/MFM 的 model-v3 分支，docs/model_v3/M1_V31_LOADER.md。
## 2026-11-05 窗口二 B6 已交付

全部150,770条下游源结构已完成处理（Slurm4526044 C0）。217个RDKit 2D描述符：150,745行完成；xTB：150,614行成功，156行按原流程失败原因保留缺失；无TEST结果访问、归一化或模型选择。148个Parquet共154,734,642字节。源数据、H补齐/图恢复和缺失口径见 `docs/data_v1/B6_downstream_descriptors_v2.md`，数据清单与计数索引为 `configs/data_v1/B6_downstream_descriptors_v2_DELIVERY.json`。本产品供正式训练后的基线比较；窗口二全量D6仍在生产链中。

## 2026-11-05 窗口二：首批缺失 P′ 已交付

原ready之后才闭合S′的80,728个分子，其161,456个固定随机前二构象已全部完成原12-task/900秒流程（4526010 C0，3:06:41）。161,044条十二项均成功，412条记录的实际失败任务保留原掩码，未解决记录0。原ready未重算，无新试点、第三及以后构象、独立数值读回或额外SHA作业。原始缺失MID、缺失原因、F64家族数据的路径/大小/计数见 `configs/data_v1/Pprime_initial_fill_v1_DELIVERY.json` 引用的唯一producer manifest。最终S′冻结后仍由既定链补齐真实前二差额；这不是最终Common/D6交付通知。

D6的U记录将保留全部已有P′真实标签。模型训练需使用M18 `Pprime_train_eligible`（最终TRAIN前二、减实际D5留出）；M17仅表示普通S′成员，M14独立标记留出，不能将已有但已不属于最终前二的P′自动用于训练。定义见D1存储补充。

2026-11-05 窗口二更新：最终 Common/D5/D7 已闭合，索引 configs/data_v1/final_Common_D5_D7_v1_DELIVERY.json。TRAIN=1,194,551，VAL=7,567；D5=120k/240k/600k/all1,126,937，原20k诊断分子及实际留出不变；D7全量0.5A统计及三序已发布。原始2891图/映射/立体化学/对齐无效按既有掩码保留，68375真实不足不强补。D4旧6112/6116接口失败已修复：D5通过既有实际几何表权威RID联结，owner仅兼容INTEGER/TEXT作业ID；新回归各一次通过。当前D4=6117正常数值运行，正式D4仍未发布，M2继续等待，不替换统计。D7续算6118 C0；UFF=6119补齐既有依赖路径后续跑；前二Pprime6113及独立统计6115继续，D6 6109依赖已更新为6118/6117/6115/6119，尚未分发。全部源/标签定义与split/留出规则不变，无新增扫描或验收门。


### 2026-11-06 · 窗口二：用户明确最终数据只用共享 LMDB

最终 D6 不再逐 GPU 节点复制。各节点读取同一份共享 compact 副本；TRAIN/FULL 的既有划分与 v3.1/MFM4 格式不变。发布根为 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact`，完成后以 `manifest.json` 的 `split_roots` 与 `schema.json` 接入。此指令覆盖任务书 B5 的节点分发步骤；D6 当前尚未完成，唯一生产端检查闭合后再通知就绪。详见 `docs/interfaces/training_format_v3_1_storage_revision_20261105.md`。


## 2026-11-06 窗口二已读：实际磁盘保护与并发预留

已读根AGENTS及HPC skill 1.0.148顶部新规。节点0根盘仅约3.8GB可用，低于10GiB系统/Slurm预留，不再新增本地大文件；Pprime 6126的32个工作目录已全部在无活动Native子进程的安全边界转至/dev/shm，原目录保留。该内存盘实际总201.84GB、可用约160.57GB，统一为原生临时输出预留32GiB并另留20GiB系统/同盘并发，inode预留3,097,152；运行期保护仅在无活动Native调用的安全边界阻止新增写入，未改变900秒规则、重跑已闭合QM或删除旧数据。其他窗口使用节点0内存盘前须扣除此项预算。

节点19根盘可用33.06GB，保留10GiB；其内存盘已用151.44GB、余50.41GB，现有约151GB元数据/原生只读缓存继续保留，暂不规划新增缓存。节点20根盘可用526.45GB，系统预留95.42GB，327GB既有Native缓存保留；D4继续在原分配运行，不解除drain。容量为实测时点值，下一次新写入仍须目标节点预检，不能直接复用旧数值。

共享/share用户4TiB quota约余500.66GB，扣除100GB账户底线及模型窗口5GB近期增长后约395.66GB；Lustre用户2TiB quota约余1,078.46GB，仍须扣除100GB底线及D4/UFF/Pprime的后续增长。全盘df不代替账户quota；D6尚未取得该容量的独占预算，不以900GB估算直接开写。D6入口已加入实际挂载/字节/inode/并发与quota准入、运行期保护和分块闭合恢复。最终数据仍每split仅一份共享compact，各节点读取相同路径；实际路径以最终manifest.split_roots为准，当前D6未交付。


2026-11-06 窗口二容量预算更新：已在实际compute-0-0对共享NFS完成准入，Pprime统计6128的未启动计划改为`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/window2_full_TRAIN_Pprime_statistics_20261106_shared_v1`。该盘统一预留320,000,000,000字节近期增长（投影/eligibility/journal及16GiB临时文件的规划峰值，非实测产物大小），另保留100GB账户底线、模型5GB及控制/并发1GB、8GiB写入突发余量；其他窗口不得再使用这320GB预算。后续compare另一个时段预算80GB（含64GiB spill），不与统计临时峰值重复相加，启动前按届时实占重验。登录节点每2秒只探测一次真实XFS quota，计算端每次读鲜活<=5秒的共享快照，未知/陈旧即停止新增写入。新NFS叠挂识别、quota及临时保护测试各一次通过。D4/Pprime原生/UFF继续，D6未获最终容量准入，原未运行6125已hold，待真实缓存尺寸及新布局配置完成后续接；未分发最终LMDB。


2026-11-06 窗口二运行期保护补充：D4 4526117和UFF 4526127现已启用真实Lustre容量/inode及用户quota保护。节点19/20各自每2秒探测实际目标，登录节点统一quota快照；控制端每次仅接受<=5秒新鲜值。账户底线100GB，另留至少8GiB全部写入突发与inode余量；不足/未知时只对UID1278、固定jobID/name/start/node匹配的这两个非Native作业阻止新增写入，恢复也只处理本控制器确曾停止的作业。未包含Pprime原生调用，不改变900秒规则。实际Lustre quota现余约1.073TB，两个writer预览均FRESH_SAFE，当前正常生产。状态与精确恢复命令保存在本窗口CONTROL，不新增数值QA/哈希/收据。NFS320GB Pprime近期增长预留继续有效。D6仍held且未准入最终容量；新spool_root仅可选存储路由，任何172GB本轮derived cache迁移都尚未准入/实施。各节点最终仍读取同一份共享LMDB。


2026-11-06 窗口二保护恢复更新：UFF6127在一次容量快照失效后被安全STOP，闭合数据保留。实际Slurm返回STOPPED，保护器原识别列表遗漏该状态；现已窄修并通过唯一新转移测试，仅own STOP_ACK+两次新鲜容量/精确身份才CONT，其他STOPPED/SUSPENDED不接管。旧控制器精确pidfd SIGINT退出后，新控制器3546033读取原恢复状态并恢复同一6127；当前RUNNING、parked为空，原作业继续增长。真实节点19/20快照与quota均新鲜，未改变5秒时效、100GB底线、8GiB突发或任何科学定义；Native6126/900秒未受影响。


## 2026-11-06 窗口二 B3 最终实际前二 Pprime 已交付

Native4526126实际COMPLETED/0:0，elapsed05:59:13。最终实际范围1,200,832个MID、2,396,675条固定随机前二记录；复用2,367,432条既有闭合标签，仅新增29,243条，其中28,796条十二项均成功、447条保留实际失败任务和原掩码，未解决0。不外推复用子集的成功率；原ready和历史80,728分子初批161,456条全部保留，未计算第三及以后或新N1、未重跑闭合QM。交付索引 configs/data_v1/Pprime_final_first2_v1_DELIVERY.json，说明 docs/data_v1/Pprime_final_first2_v1_DELIVERY.md，引用唯一producer原始F64文件path/bytes/counts及真实不足状态表，无新hash/数值回读/独立QA。独立Pprime统计6128已按既有依赖在节点0/32CPU启动，写共享NFS安全目录；D4与UFF继续，D6仍held待容量准入，尚未最终LMDB交付。


2026-11-06 窗口二节点0 RAM预算释放：Native6126已真实C0，原父2866924及RAM guard3144286均已退出；节点0/dev/shm实核可用160,644,616,192字节、49,278,210空闲inode。原32GiB Native后续临时增长预留现在释放，20GiB系统/共享余量继续保留；现有只读binding/index缓存仍按df实占计入，未删除任何文件。Pprime统计6128的输出和临时文件均在已准入NFS，未在节点0根盘或RAM新增大文件。其他窗口使用释放余量仍须实际目标预检与并发预算，不能直接据旧数值开写；本窗口未来D6 RAM缓存/临时块也必须重新准入。


2026-11-06 窗口二采样修复：容量publisher运行期重复findmnt/df/df-Pi/statvfs，在负载下导致刚发布快照已过期并触发保护。已改为启动时完整实际挂载/device预检一次，运行期只做实际statvfs及前后device核验，并记录容量读取完成时间；设备变化/unknown仍不发布。唯一新sampler测试通过(.001s)，未重复旧测试，5秒时效/100GB quota底线/8GiB突发均未放宽。旧metadata publisher经精确UID/argv/start_ticks/pidfd TERM退出，只替换sampler：节点20新PID2719878、节点19新PID1684785；controller3546033保持。当前三个快照年龄约0.9–1.5秒、parked为空，6117/6127同作业RUNNING；6128独立统计继续。未触碰Native、科学定义、Slurm管理员状态或任何原始数据。


2026-11-06 窗口二NFS配额时钟修复：节点0相对登录节点的5次同连接clock RPC严格偏差约[-0.99511,-0.99486]秒，导致刚发布quota在node0被判future。新publisher显式clock-safety-bias=1.25秒，将observed_time设为真实source_probe_time减保守偏差，并同时保留source_probe_time/bias；读取端UID/fs和0<=age<=5秒未改，未调系统时间/NTP或科学900秒。新唯一fixture通过2.601s；精确UID/argv/start/pidfd只停止旧metadata publisher3536643，新Main publisher3593645发布同一路径。node0实际校验age约.608秒通过，Pprime6128投影分片继续闭合；无原始/闭合标签重算或删除。未来写入节点使用此reference仍须核实相对时钟界限，不能把偏差配置当作放宽时效。D4第3轮171组已闭合，后续数值阶段继续；D6仍held/未最终准入。


2026-11-06 窗口二运行续报：D4 6117首遍及分位数第2/3轮171组闭合，第4轮116/171 errors[]，尚未完成；P′6128独立F64投影持续闭合，非r674向量尺度仍待用户答复。容量监控对19/20节点使用显式0.5秒保守时间下界并保留真实source_probe_time，5秒新鲜度不变；仅滚动替换自身元数据采样器，6117/6127均RUNNING、parked{}。新逻辑单测累计67项一次通过，无重复数值读取/QA。D6仍held待实际容量准入，最终每split一份共享LMDB，所有模型节点共读。


2026-11-06 窗口二P′投影闭合：6128的32/32分区已生成总清单，2,412,201物理几何、28,946,412任务行，typed F64块143,035,837,161字节，含身份表等闭合引用的已发生物理占用159,006,019,717字节。原320GB规划增长的未发生部分现记160,993,980,283字节，另保留账户100GB、模型5GB/控制1GB与8GiB突发余量；已发生文件不再重复计入未来增长。15,305个未注册源几何继续保留GID NULL、原F64/Z/锚点，不改标为最终选择；D4拟合只用实际TRAIN前二减D5。P′已进入112逻辑组第一遍独立统计，PM7第4轮139/171 errors[]，D4尚未完成；D6仍held、NOT_ADMITTED。该记录只读生产端闭合JSON，无数值复读或新QA。


2026-11-06 窗口二配额快照修复：旧元数据PID3593645实际卡在rename/__break_lease，导致6128按5秒规则DISK_WAIT，并非空间不足；旧快照/所有数据保留。Main bb29b47的AtomicPublisher从rename前持续持有当前inode写FD，下一次成功替换才关闭previous；新单测1PASS .029s，累计68项不重复。旧元数据精确pidfd TERM退出，新Main元数据PID3640096使用 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json；实际node0连续5代读取有效，旧share_quota_available.json已停更勿用于后续准入。6128已正常CANCELLED且实际node0无steps，保留32/32投影、首遍112/112、第2遍50/112闭合组；同32CPU节点0的新6169已RUNNING，使用原output/checkpoint并进入attempt_001，不重投影或重算QM。D6 6125依赖已改6117:6169:6127，仍held/NOT_ADMITTED；旧spooled compare小manifest兼容要求顺延至6169真C0。剩余规划160,993,980,283B及100GB+6GB+8GiB保留，未降低存储余量/5秒新鲜度/科学参数。PM7第4轮166/171无错误，UFF续跑。


2026-11-06 窗口二元数据续调：NFS快照新鲜度边界等待反复自恢复，刷新间隔从2秒缩至1秒，5秒新鲜度、1.25秒保守下界、100GB/并发/突发余量均不变。仅交接元数据：精确旧PID3640096 STOP时保持已发布inode写FD，新PID3645685在同v3路径成功发布并核实持有当前inode写FD后，旧进程TERM+CONT确认退出；未再次重启6169或其他科学作业。P′第2轮已从50组续至56/112，PM7第4轮170/171，均无统计错误。仅修改两个刷新常量，无新统计逻辑，不重复已过测试；累计68项新逻辑测试事实不变。


2026-11-06 窗口二D4阶段进度：PM7 6117分位数第4轮171/171已闭合，第5轮70/171 errors[]；后续截尾矩/median/MAD未完成，尚非D4交付。P′6169第2轮92/112；node0实际时钟及productionPython一致，快照10次年龄1.395–1.913秒有效；对单worker仅quotaJSON路径8秒运行诊断确认读取v3当前代、有效年龄与连续批次，已detach，不再重启/改数值逻辑。整组检查点暂不变化不能当成绝对零工作。UFF6127继续，D6仍held/NOT_ADMITTED，非r674向量定义待用户答复。没有新数值QA/源数组复读/吞吐基准/验收收据。


2026-11-06 窗口二用户科学定义已冻结：用户明确选择“采用模长的截尾总体标准差（与既有r674方针一致）”。正式文件 configs/data_v1/window2_user_frozen_vector_normalization_20261106_v1.json 规定vector零中心、每头各分量共用既定模长统计副本截尾std_ddof0，PM7/P′各自拟合；window2_D4_physical_route_bindings_v1.json 已将现有schema全部9个vector头指向该正式方针。r674仍用原D1方针，原loss exposure/掩码、退化尺度禁用和不造epsilon保持。只绑定既有在算统计，不增加源扫描、重拟合或训练标签截尾；数值生产作业不变，原3项publisher逻辑测试不重跑。M2不再等待矢量定义答复，但正式数值仍须等实际D4生产C0后发布，不能把配置冻结当成D4完成。


2026-11-06 窗口二UFF真实闭合：4526127实际COMPLETED0:0，batch/extern均0:0，当前作业elapsed11:24:50。生产端 /lfshome/zixiao/data_v1_20261025/window2_full_UFF_D3_20261105_v1/manifest.json 已闭合10,861,980实际UFF几何、9,441文件、28,831,514,624字节；文件records合计一致，新掩码2仅报告保留，不重试/不造人工复查列表。清单保留原corrected_base内部HBA和每新增实际几何调用一次、源F64几何不变；累计缓存包含此前214闭合块的续用，不能把累计调用数当成仅本Slurm段调用量。范围含10,857,356普通S′及4,624注册extra几何，原诊断extra表为0；D20仍原PM7按M共享。D6使用该真实缓存，不重算全UFF；Native/元数据缓存19仍有D6后续消费者，未删除。PM7 D4 pass5 135/171、P′6169 pass2 95/112尚运行；D6 6125仍held/NOT_ADMITTED，最终各split一份共享LMDB、无GPU节点复制。该完成记录只读闭合JSON及Slurm状态，无额外数值QA/hash/收据。


2026-11-06 窗口二整数radix执行优化已备：Main5381da1（child247d96c），仅P′ normalization_quantiles/diagnostic_median_MAD，默认OFF flag shard_radix_typed_parts。原112逻辑组/顺序保持，现有190个互斥typed parts可flatpool分派；同一Original._group_pass逐行F64字节码，每part仍只消费一次，histogram/field/role/task/series仅精确整数合并；TSQR和浮点moments维持原整组路径，PM7不变。已闭合组/part按stage+有序原ref恢复，单part直接复用不读写额外hist。唯一新增合成golden测试在既有6117/16CPU步骤PASS1/7.881秒，覆盖原量化及median→MAD全部refinement/F64逐bit、恢复乱序/冲突/float拒绝；旧通过项未重跑，累计69项。111个已闭合P′整组hist元数据共63,407,816B、最大957,451B；额外前缀/merge纳入原剩余160,993,980,283B规划，运行期真实quota/字节/inode余量不变。当前6169 pass2 111/112最后大组仍继续，未为优化中断；到当前阶段闭合才考虑切换。无生产数值重读QA/吞吐基准/新hash/收据。


2026-11-06 窗口二P′两项执行优化已启用：Main20df760（child4b6ced1）histogram_guard_writes_only与已过golden的shard_radix_typed_parts均true，仅整数quantile/median/MAD。Original._group_pass数学bytecode/B/逐row F64运算不变，worker-local完整IOproxy安装后才省掉每32行只读wait；mkdir/inode、Parquet header/footer、JSON partial/rename均经实际target/quotaguard，每次底层write≤64KiB，原8GiB burst/100GB+并发余量/5秒TTL不变。新合成IO保护/原结果parity/拒绝不写/无FD泄漏fixture仅1PASS1.202秒在6117/16CPU；69th旧golden未重跑，累计70项。原6169的pass2 112/112已完整闭合后才切换；6169正常CANCELLED03:57:39，实际node0无steps。新6172 RUNNING同32CPU节点0/同output/checkpoint，保留pass3原18个闭合组，并已出现15个新closed part，源projection不重做/原QM不重算。持久shard按原stage/group/part ref绑定，原112组顺序、TSQR/浮点moments整组路径及PM7均保持。D6 6125依赖改6117:6172:6127，仍held/NOT_ADMITTED；旧spooled compare兼容小manifest顺延至6172真C0。PM7 pass5 170/171；UFF已C0。无生产数值QA/新hash/收据/吞吐基准/人为耗时门。


2026-11-06 窗口二 D4 进度：PM7 6117 的量化第2/3/4/5/6轮均171/171闭合，第7轮19/171；独立P′ 6172的首遍及量化第2/3/4轮112/112闭合，第5轮63/112。两项实际Slurm仍RUNNING，无统计错误。后续原算法截尾矩及median/MAD继续，D4尚未完成、M2正式参数尚未发布。用户已批准矢量以模长截尾总体std_ddof0为每头共尺度、零中心，9个既有矢量头已绑定正式策略，PM7/P′各自计算，r674保留原D1策略及LOSS_DISABLED。现有PM7 reader的14任务完整性检查保持，不套用P′整part切分。UFF 6127已实际C0，D6 6125仍held/NOT_ADMITTED、依赖6117:6172:6127；待两路统计C0后发布参数、按真实容量准入全量导出。最终每split仅一份共享compact LMDB，各模型节点共读，不复制至GPU节点。仅继续原算法生产统计，无额外QA扫描、数值复读、hash/收据/独立QA/测试重跑；已通过70项新逻辑测试保持。


2026-11-07 窗口二：PM7原精确分位数第2至8轮各171/171完整闭合，已进入原截尾矩第9轮（46/171、无统计错误）。P′的首遍及精确分位数第2至8轮各112/112闭合；6172在截尾矩初始化遇瞬时配额快照过期，原Temp.activate未等待该异常导致分组失败，最终36组闭合后自然FAILED1:0/10:23:51，实际节点0已无旧steps。仅为ACCOUNT_QUOTA_SNAPSHOT_UNKNOWN加入初始化等待；5秒时效、UID/schema、容量/inode/100GB与并发余量、原F64数学和浮点整组顺序全保持。新合成用例真实snapshot解析stale/future均零写、fresh后继续、无关策略错误仍拒绝，新增1项仅运行一次0.099秒，实际6117.25/1CPU C0；原70项未重跑。Main804a317（childc0a2b49）。新6181已RUNNING32CPU节点0，同plan/output/cache、pass9 attempt001复用全部36闭合组；无重复投影/QM/已闭合组或额外QA扫描。D6 6125仍Priority0/JobHeldAdmin、NOT_ADMITTED，依赖6117:6181；UFF6127实际C0且已从Slurm活动缓存清除，先决条件已履行、F64缓存保持。旧spooled compare小manifest兼容顺延至6181真正C0后；正式D4路由与全量D6仍待剩余统计完成和实际容量准入。最终每split一份共享compact LMDB，各模型节点共读，不做GPU节点LMDB复制。


2026-11-07 06:52 窗口二D4：PM7 6117的首遍、原精确分位数第2至8轮及截尾矩第9轮均171/171闭合；独立P′ 6181对应阶段各112/112闭合，已完成全部均值/std统计，36组原检查点+76组续接全部保留，未改F64数学、元素参照或PM7/P′独立性。原median/MAD仍在生产：PM7第10轮171组已闭合、第11轮132/171；P′第10至13轮各112组已闭合、第14轮继续；无新增分组错误。整项D4尚未完成，正式模型路由仍按实际生产C0后发布，不把中间参数或检查点标为最终就绪。两项实际Slurm仍RUNNING64CPU20/32CPU0，D6 6125仍Priority0/JobHeldAdmin、NOT_ADMITTED、依赖6117:6181，UFF6127已实际C0且原缓存保留；完成统计后再按实际挂载/字节/inode/quota及跨窗口并发余量准入。用户已冻结的σ/π同对称性分块、9矢量头零中心/模长截尾总体std共尺度与r674原D1/LOSS_DISABLED保持。最终每split仅一份共享compact LMDB，各模型节点共读；原71项新逻辑测试未重跑，无额外QA/数值复读/内容hash/收据/吞吐基准。


2026-11-07 窗口二新增并行准备预留：仅把不依赖D4的Pprime原始未注册几何地址/缺失UFF D3缓存提前准备，复用已C0的6127全部10861980条D3，不追加QM、不变科学规则；D6全量6125仍held/NOT_ADMITTED。实际compute-0-19的/lfshome为10.1.1.100@tcp:/data Lustre，df可用41752698667008B、inode36290377，账户quota可用1051802779648B。所有新metadata/SQLite journal/temp/partial/D3均落Lustre；合计新增峰值预留100GiB，另计PM7剩余56GiB预测及其他窗口元数据6GB、账户100GB底线和8GiB突发余量。节点根盘、/tmp和/dev/shm新增bulk均0，不复制Native LMDB，不删除已有源/缓存；5秒quota TTL、实际mount/bytes/inodes与运行期保护保持。NFS控制日志继续占既有1GB控制预留，窗口三NFS16GiB不挪用。准备代码单测通过后由Root提交；本通知不表示全量D6容量准入或完成。


2026-11-07 窗口二并行缓存准备已启动：Main d546621（child0a1287a）仅给prepare新增默认bind_plan=True与--cache-only；缓存/地址/原D3数学不变，cache-only不改输入plan、不写bound_plan，默认绑定及路径冲突拒绝保持。新增唯一合成fixture真实Slurm4526187/24CPU节点19首次1PASS0.267s、子进程exit0；旧71项未重复。4526187继续独立准备原Pprime source地址与缺失D3，主D6 plan未改、全量6125仍held/NOT_ADMITTED，依赖6117:6181:6187。首次6186因误接XFS-only quota reader在零输出/零测试/零科学工作边界取消（00:01:41），实际节点19无旧steps；现原quota_probe_argv接口直接复用已测G.safe校验捕获的Lustre quota/实际node19容量快照，UID/schema/filesystem/5秒不变，Guard实际target准入及整进程组运行保护保持。Lustre100GiB联合峰值预留持续；无root/tmp/shm新增bulk，无新Native LMDB副本，无已有数据删除。D4仍RUNNING：Pprime原中位数pass10至16全部112/112闭合，现MAD pass17；PM7仍median pass12，均值/std两路早已闭合。整项D4与正式路由仍未完成。最终每split单份共享compact，各模型节点共读。


2026-11-07 窗口二Lustre控制时钟修复：实际node19连续6次读quota age在约-0.34/-0.28/-0.27与+0.69/+0.73秒间交替，cap19正常1.1–2.17秒；future拒绝导致cache-only6187保护反复暂停/恢复，非磁盘不足。Main13f9f14（child9472e92）仅给quota发布复用已测observation_times，新增可选quota_clock_safety_bias_seconds（default0），原parse数值/schema/UID/fs保持，真实source_probe_time保留。唯一新合成fixture73首次1PASS（unittest0.000s），实际4526187.0 C0/1CPU/2s；旧72项未重跑。仅自己Main quota metadata publisher3540833 rolling替换4024673，profile设保守bias1.25；随后node19六个quota age1.84–2.87秒、cap age1.28–2.30秒均0..5，producer1695054已RESUMED，三个科学作业均未重启。未改OS时钟、5秒TTL、100GB/8GiB/并发/字节/inode保护或科学输入；无新QA/数值扫描/hash/收据。PM7 median pass12已171/171闭合、现13；Pprime median10至16及MAD17已闭合、现18；整项D4/正式路由仍待C0，D6全量6125仍held/NOT_ADMITTED，独立6187仅准备缓存。最终每split一份共享compact，各模型节点共读。


2026-11-07 窗口二PM7整组调度提速：既有group_plan元数据表明长尾121/119/157为前三大组（12,423,238,241 /11,573,340,985 /11,417,747,654B），原提交位置121/119/157。Main74fe5bc（child2abcec3）仅加默认关闭--largest-groups-first，未入cfg/checkpoint inputs；未闭合完整原组按既有ref.bytes降序、同权稳定原序，不读/stat源、不切part、不改组内files/14任务完整性/T.group_pass参数与F64数学；最终reports及归约仍原171组顺序。唯一新合成fixture74首次1PASS0.001s，实际6187.1 C0/1CPU/2s；旧73未重跑。原6117 pass1至13各171/171均闭合后才切换，pass14原29闭合组保留；6117本人正常CANCELLED1-11:31:57，实际node20无旧steps、无Kill-failed/undrain。新6214 RUNNING64CPU同节点20/同output/checkpoint，pass14 attempt001复用29组，优先121/119/157/116。实际目标findmnt/df bytes/inodes由6214 Guard.inspect重新核实（Lustre可用41743775817728B、inode36289925）；其Guard.run只保护自己子进程组，所有TMP/SQLite临时落Lustre，保留56GiB本路未来预测、缓存准备100GiB/其他6GB并发、账户100GB及8GiB突发余量，无输出/内存/墙钟硬停。旧只覆盖6117/6127的Main控制器3546033在旧作业终态且无park后SIGTERM；4024673配额发布器及node19/20容量采样保持，实际node20容量独立核实，不以quota或额外node19全局Lustre快照替代。D6 6125仍held/NOT_ADMITTED，依赖6214:6181:6187；Pprime统计与独立缓存准备继续未重启。所有旧源/缓存/partial保留，无新QA/数值复读/hash/收据/吞吐基准。整项D4与正式路由仍待实际C0；最终每split一份共享compact，模型节点共读。


2026-11-07 窗口二独立Pprime统计已实际C0：4526181主/batch/extern均COMPLETED0:0，elapsed09:10:06/32CPU节点0。原element1、exact quantile2至8、moments9、median10至16和MAD17至23全部112组闭合，未做完整第二遍统计或独立数值复读；全部F64缓存/闭合part保留，原36组矩检查点继续复用，无追加QM。真正最终统计manifest为 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/window2_full_TRAIN_Pprime_statistics_20261106_shared_v1/statistics/manifest.json`（24863B），原producer单一文件清单在同output的delivery_manifest.json。为已spooled D6 compare仅复制这份真实小JSON至 `/lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_Pprime_statistics_20261105_v1/statistics/manifest.json`，内部refs保持实际NFS、没有数值缓存复制/QA；Main实际Lustre findmnt/df字节/inode及quota后写入，源manifest和科学值未改。Pprime统计160993980283B剩余预测现在释放为0。随后比较80GB（含64GiB spill）在导出前串行，后续D6候选IDmap/fragment/有界spool联合峰值暂预留190GB，按阶段max(80,190)GB而非相加；此为全窗口同盘预测、并非D6布局准入或输出硬限。另保留账户100GB、既有模型/控制6GB、窗口三独立16GiB及8GiB突发；当前NFS原生用户quota余约337.32GB，不能使用整盘df代替。任何其他窗口新写入须合并这份190GB预留，不再沿用旧160.99GB统计预测；大写入仍待实际目标/峰值/节点余量准入。PM7 6214仍在原median pass14、6187仍独立准备sourceD3；完整D4/正式模型路由尚未完成，全量D6 6125继续held/NOT_ADMITTED。最终每split单份共享compact，各模型节点共读；无旧数据删除、新hash/收据/独立QA或测试重跑。


## 2026-11-07 · Window two: closed TRAIN normalization parameters ready; full D4 MAD pending

Model line may now consume `/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/manifest.json`, pointing to the same directory's `routes.json` (1,261,953 bytes; 262 dataset-target routes). This is the final training-parameter binding from the already committed full-TRAIN element models, exact tails and moments, plus the actual independent Pprime C0 manifest; it does not wait for diagnostic MAD. Per-target `normalizer_ready` and all existing training-view/physical-loss exclusions still apply.

The artifact explicitly states `NORMALIZATION_PARAMETERS_READY_D4_PENDING_MAD`, `D4_complete=false`, `PM7_parent_C0_not_claimed=true` and `PM7_diagnostics_continue=true`. PM7's original MAD17..23 continues under4526214. No full PM7 statistics manifest/C0 is invented. Scalar/energy/vector/r674/r73 bindings reuse the existing numerical code; nine user-frozen vector heads retain zero center and the norm's winsorized population std, independently for PM7/Pprime; r674 exposure/loss flags remain disabled/unchanged. No source arrays, fits or scientific QA were replayed.

Only the new pure-metadata fixture ran once (1 PASS,0.006s; actual4526187.3 C0/1CPU); actual parameter publication4526187.4 C0/1CPU completed. The original metadata/source-cache parent4526187 remains running. Full D4 and full D6 are still incomplete; D6 4526125 remains held pending actual6214/6187 closure and storage admission. Final TRAIN/FULL each use one shared compact LMDB; every model node reads those shared paths, with no new per-node LMDB copies or ACK gates.


## 2026-11-07 · Window two Lustre quota transport restored; science parents unchanged

The actual Lustre quota metadata writer4024673 was blocked in kernel `__break_lease`; the old snapshot's true probe stopped advancing and both actual science guards correctly paused writes. NFS quota writer3645685/v3 remained healthy. The quota-only loop now reuses the already implemented `AtomicPublisher`, keeping the current inode open for write across replacement. The capacity-sampler transport and all parse/capacity/bias/timeout/five-second freshness rules are unchanged.

Actual new metadata writer208051 publishes fresh real probes to `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/lustre_quota_available_v2_20261107.json`. The existing `lustre_writer_guard_profile.json` changes only `quota_reference`. A writable current-snapshot FD was observed; Main effective ages1.99/2.62 seconds passed the same five-second validator. The old own metadata PID was terminated only after exact UID/boot/start-ticks/PGID/SID/argv/cgroup witness checks, and old files remain. Both4526214 and4526187 automatically resumed; PM7 MAD19 advanced18→23 closed groups without restarting either scientific parent or replaying closed data.

Only new all-mock/no-file fixture76 ran once:1 PASS/0.011s, actual4526187.5 C0/1CPU; old75 fixtures were not rerun. No scientific inputs, labels, masks, normalizers, budgets or training-view definitions changed. Closed TRAIN normalization parameters remain delivered; complete D4 and full D6 remain pending. Final LMDB delivery remains SHARED_SINGLE_COPY for TRAIN/FULL, with all model nodes reading the shared files.


## 2026-11-07 窗口二：P/P′ TRAIN 描述性比较已完成

实际 Slurm 4526244 / compute-0-20 / 16CPU 已 COMPLETED 0:0（00:09:09）。复用已关闭的 PM7 normalization_moments/per-M means 及 P′ 6181 C0 汇总，提前与 MAD 并行完成原定比较；原 valid-leaf 加权合并、Pearson/Spearman SQL 与分布算法保持，无原始标签/几何重读或重新拟合。

- 清单：`/lfshome/zixiao/data_v1_20261025/window2_P_vs_Pprime_TRAIN_20261105_v1/manifest.json`（6076 B）。
- 同 MID 字段均值相关性：121 字段，`P_vs_Pprime_same_MID_correlations.parquet`，7129 B。
- 分布：850 series，`P_vs_Pprime_distributions.json`，323351 B；两文件均在清单同目录。
- 新输入路由 fixture77 首次 1PASS；原有通过套件未重跑。输入来源明确保留真实 Common/D5/tail 绑定，`PM7_D4_complete=false`、`PM7_parent_C0_claimed=false`；完整 D4 仍继续 MAD20..23。

D6 6125 仍 held / NOT_ADMITTED，当前只余 6214、6187 未满足；比较清单已存在，原 D6 脚本将直接复用。最终 LMDB 继续每 split 单份共享 compact，全部模型节点共读。无需模型线确认或新增等待门。


## 2026-11-08 窗口二：最终 D4 全量 TRAIN 已完成

正式入口：[window2_D4_final_DELIVERY.json](../../configs/data_v1/window2_D4_final_DELIVERY.json)。PM7 4526214 主/batch/extern 均 COMPLETED 0:0（15:01:45）；原 element、精确截尾、moments、median/MAD 的 pass1..23 全部闭合。独立 P′ 4526181 已 C0（09:10:06），两方法各用自己的 TRAIN 统计，D5 预留 base 及全部14任务输入视图排除保持。

- PM7最终清单：`/lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_normalization_20261105_v1/manifest.json`（4447 B）。
- P′最终清单：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/window2_full_TRAIN_Pprime_statistics_20261106_shared_v1/statistics/manifest.json`（24863 B）。
- 正式路由清单：`/lfshome/zixiao/data_v1_20261025/window2_D4_model_routes_20261106_v1/manifest.json`（266 B）；同目录 `routes.json` 1256136 B、262条dataset-target路由。实际发布4526187.6 C0/1CPU/1秒，仅绑定闭合JSON。
- 原始median/MAD、元素参考、精确分位数、均值/std、有效性及mask引用均在正式入口；P/P′的121字段相关性/850series分布已由6244 C0完成。无完整第二遍统计、独立数值复读、新内容hash/收据或旧测试重跑。

现用早交付TRAIN训练参数继续有效，绑定的原element/tail/moments引用未变；其D4_pending字段保留早交付时的历史状态，完整D4完成以本正式入口及真实producer C0为准。既有D3试点继续按原发布mask_overrides_reference应用EA覆盖。每目标normalizer_ready及原物理loss标记继续适用，不由有尺度自动启用字段；9矢量头、r73同对称性求和及r674 LOSS_DISABLED不变。

PM7剩余56GiB统计预测现在释放为0，既有源/缓存/结果均保留。6187原缓存准备仍在运行，全量D6仍未准入；Node20既有Native闭合缓存已作文件元数据可用性确认，可供后续容量计划复用，无新复制/数据读回。最终TRAIN/FULL按原角色互斥，各一份共享compact LMDB，全部模型节点共读；无需模型ACK，不启动付费服务器或正式预训练。


## 2026-11-08 窗口二：D6 存储位置改动已验证，联合容量待准入

已继承窗口一全局 Lustre 100GB 检查点预留。候选采用 Node20 既有 Native 缓存、W16/B16、共享闭合几何索引及本地临时 source spool/ID fragments；最终 IDmap 在共享 NFS，TRAIN/FULL 各一份共享 compact LMDB，全部模型节点共读。新增 id_fragment_working_root 只调整新 attempt 的临时位置；已关闭分片引用、恢复游标、ID 内容/行序及科学定义保持。新增 fixture78 首次 1PASS/1.554秒，实际4526187.7 C0/1CPU/3秒；旧77不重跑。

计入模型100GB后旧容量预测不够。已列出38个已关闭 r73 派生 SQLite 缓存，共100000190464B，拟完整迁至NFS并保留原canonical路径符号链接；原盘副本移除已依任务书向用户询问，尚无答复，未复制/迁移/移除。候选 control/window2_20261105/D6_node20_shared_candidate_20261108_v1/ 仍 NOT_ADMITTED；没有模型ACK/额外基准或科学扫描。6187 缓存准备继续，D6 6125 保持held；正式导出将以实际6187 C0、用户必要迁移决定及实际节点字节/inode/quota联合容量准入为准。


## 2026-11-08 窗口二：用户批准的缓存迁移完成，D6 继续准备

经用户明确同意，已完成所列38个闭合 r73 派生缓存迁移，共100000190464B；实际4526252 / compute-0-20 /16CPU 主、batch、extern 均 COMPLETED0:0（10:19）。完整数据位于 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_r73_cache_relocation_candidate_20261108_v1/group_*/r73_derived.sqlite`，原 `/lfshome/.../window2_full_TRAIN_normalization_20261105_v1/pass_0001/attempt_001/group_*/r73_derived.sqlite` 保留为对应符号链接；38条canonical路径/UID/文件大小元数据匹配。原统计清单和数值保持；无SQLite数值读取、新内容hash或独立科学QA。

用户澄清所指存储为现用 Lustre `/lfshome`，正式D6目标仍在此；账号原生硬配额2TiB，与约41.7TB全盘空闲分开核算。迁移完成后实际账号余量约Lustre1127.82GB、NFS227.41GB，模型线Lustre100GB、账号100GB底线、窗口三NFS16GiB及其余并发预算保持。固定版本代码目录已准备，6187几何索引/缓存准备仍运行；全量D6未开始，须待其真实C0后在实际节点重查联合容量。

供三个窗口合并预算的D6临时存储计划：Node20同盘新增峰值取max(200GB source spool+80GB ID fragments,300GB compact chunks)，另8GiB运行突发；Node21一次压缩流的临时分片700GB，另8GiB突发。两根盘均保留max(10GiB,10%总容量)，真实其他窗口并发仍在准入时合并；尚未写这些临时分片。关闭分片拼回共享单份后沿原producer生命周期释放。最终TRAIN/FULL互斥、各一份Lustre共享compact，全部模型节点共读；无模型ACK等待门。


## 2026-11-08 窗口二：原 S240k 的 P/D 身份入口已绑定，等待真实 D6 数据

原 S 实验使用的 `.../day02_finite_census_full5178_cpu13/train_240000.parquet` 已按原顺序逐MID绑定：240000行、240000唯一MID均为最终Common TRAIN，0缺口、0换人；保留原S的2209619条PM7构象索引引用，未把旧S行号当D6索引，也未替换为新D5 240k。

- 入口绑定：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json`，6334B。
- 同目录 `membership_binding.parquet`，2033909B／240000行；只读取原名单MID及Common三身份列，未读S记录载荷、标签或坐标。
- P/D复用同一原subset、TRAIN、PM7、冻结training_view及现有正式TRAIN参数；不另导出/复制24万LMDB。当前明确 `NOT_READY/root=null`，唯一未就绪原因 `FINAL_D6_MANIFEST_NOT_PUBLISHED`，不可据此启动P/D训练。
- 实际4526265 main/batch/extern C0／16CPU20／6秒；新增fixture79首次1PASS／1.332秒，旧78不重跑。模板root/output资源更新允许，身份/科学消费字段保持冻结。

真实D6发布后由原绑定CLI仅刷新JSON根目录，复用已闭合MID表，无需重扫或新ACK。代码/配置入口 `configs/data_v1/S240k_PD_shared_binding_20261108_v1.json`；全量D6继续原范围、TRAIN/FULL各一份共享文件。原6187目前仍受Lustre元数据I/O拖慢，Node20本地元数据工作副本的检查点续接正在准备；未把此身份绑定冒称可用P/D数据。


## 2026-11-08 窗口二：完整 D6 已实际启动，原 S240k P/D 入口随正式发布刷新

全量 D6 实际4526271／compute-0-20／16CPU已RUNNING，冻结源码835a1a251414e56de94b0fc99aea02b1947c2e5f，W16/B16；不是试点或仅身份表。前置6268主/batch/extern C0／21:09：真实闭合几何索引与UID元数据在Node20续接，复用10861980几何，仅补15305次D3，合计10877285记录／120新part；原6187只在已发布几何且零Native边界取消，旧数据/检查点保留。旧held6125经确认未分配、零运行后退役。

启动前实际Node20的Lustre、NFS、根盘、SHM以及Node21根盘字节/inode/quota准入全部通过。Root20新峰值334183533568B、Root21临时分片708589934592B，两根盘各保留95415907124B；已存在Node20 geometry/UID约24.41GB及Native327.41GB计入实际used，不重复预算。SHM cache-index新峰值48589934592B，保留8GiB；仅改物理位置，SQL/行序/科学输入不变。新增fixture80首次1PASS/0.304秒，实际6270 C0，原79不重跑。运行Guard持续检查全部目标；模型线Lustre100GB、其他6GB、账号100GB底线及窗口三NFS16GiB继续保留，完整输出估计不是科学截断上限。

最终仍是TRAIN/FULL互斥、各一份Lustre共享compact LMDB，无各节点副本。根目录将是 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact`，当前尚未发布可用manifest。原S240k绑定当前保持NOT_READY/root=null；完整producer通过原一次检查/各split一次压缩并exit0后，自动仅刷新 `.../artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json`，复用已闭合240000 MID表，无重扫、换人或独立24万LMDB导出。模型线应以该实际READY/root为准；不设新ACK门、不重复科学QA/基准/hash，不启动付费服务器或正式预训练。


## 2026-11-08 窗口二：D6 复用已关闭索引续接，实际作业4526273

初始全量作业4526271实际FAILED1:0／13:45，发生在cache-index已经闭合、LMDB写入检查点尚不存在时。原因是进入writer再次Guard准入，把已完成索引的48.59GB未来预算重复扣除；不是磁盘已满。真实Node20闭合索引14521466880B（allocated14521462784B）已保留，输入绑定与文件大小元数据匹配，无数据库数值重读。

只把已完成索引的后续build预测释放为0，SHM仍保留8GiB及8GiB运行突发；其余科学输入、W16/B16、Root/Lustre/NFS联合预算不变。Node20全部四文件系统及Node21根盘实际Guard预检再次返回0后，已提交4526273／16CPU20并实测RUNNING；同一冻结代码835a1a，复用原索引，不重做Pprime/D3或数值QA。原S240k仍NOT_READY，完整D6结束后自动刷新共享根目录；不复制模型节点LMDB。


## 2026-11-08 窗口二：补齐原历史包协议登记，D6实际4526274续接

4526273实际FAILED1:0／10:00：首批PM7原数据投影遇到原包 `333f2de011605bcf73db65cad4cb7534a526b85e0ebc946d46f7a60aaf62078e` 未登记，未绕过输入重建。原 `reproduction_package/queue_recovery_job_4514065/manifest.json` 的original_manifest明确指向 `supplement_job_4513971/manifest.json` 及该既有SHA；读取被引用原包protocol，精确为原 `configs/protocol.json` /既有3e831aa5...引用。继承各原包original_manifest链后共6个包键，全部记录相同原协议；登记见 `configs/data_v1/D6_original_package_protocol_map_v1.json`，执行control原map路径保持。

这是缺失静态配置补齐：不更改原协议/坐标重建/标签，不算新内容hash，不增加逻辑或重复测试/QA。实际写入检查点committed_molecules=0、source_cursor=null；闭合14.52GB cache-index、几何/D3/Pprime/D4和未闭合spool均保留。Node20全部四文件系统及Node21根盘实际Guard再次返回0后，4526274／16CPU20已实测RUNNING，冻结代码835a1a/W16/B16与全部容量余量保持。原S240k入口仍NOT_READY，完整D6发布前不提前宣称可用；最终每split单份共享LMDB，不复制模型节点。


## 2026-11-08 窗口二：D6路径变量覆盖已定位，准备修复后续接

6274在进入Pprime后实际出现DISK_WAIT/WRITE_TARGET_NOT_UNIQUELY_BUDGETED；代码定位为work中的临时SQLite `path` 被PM7 raw及Pprime输入循环变量覆盖，最终Guard与spool返回引用误指来源Parquet。没有扩大allowlist或改科学/写来源文件。Root核实writer committed_molecules=0/source_cursor=null、精确UID1278/Node20/cgroup6274/PID2808953/start_ticks1198083922后，对自有producer组发SIGINT，让未提交SQLite事务正常退出。实际6274父作业FAILED1:0/01:00:11，非C0；旧进程已消失，根盘可用恢复468458229760B，原源/闭合14.52GB索引与所有上游结果保留，未闭合attempt保留。

当前D6未运行，正在原D6代码准备工作树修复变量名并补synthetic单测81；通过后按原检查点/同科学范围和真实容量准入续接。S240k入口继续NOT_READY/root=null，不能据此前运行状态启动训练。最终TRAIN/FULL各一份共享LMDB、模型Lustre100GB与全盘并发/余量规则保持。


## 2026-11-08 窗口二：spool路径修复首次单测通过，实际D6作业4526278续接

三处输入路径覆盖已最小改名，SQL/投影数值/行序不变。新增唯一fixture81真实执行tiny PM7+Pprime work/SQLite/assembler，确认Guard与闭合marker使用私有SQLite、源Parquet bytes不变，并验证future成功/失败/取消的诊断日志和原异常重抛。实际6277／16CPU20主/batch/extern C0／6秒，首次1PASS／2.775秒，旧80不重跑。future完成日志只报告错误，ordered消费/原异常传播保持。

完整D6新作业4526278／16CPU20已实际RUNNING，冻结代码bad6efa59f45dbdc2ab64a0745e0e1453ae3847f，source_snapshot81已在Main实际quota/目标容量保护下准备。Node20全部四文件系统及Node21根盘重新Guard准入返回0；原W16/B16、全部来源/科学参数/样本/划分/角色/cursor保持。仅在0已提交记录边界把checkpoint schema.code_commit绑定实际新代码，原checkpoint备份保留，未改科学计数或闭合阶段。全部上游、14.52GB索引和未闭合旧attempt保留。

S240k仍NOT_READY/root=null；完整producer原一次末尾检查及TRAIN/FULL各一次压缩完成后自动发布共享入口。每split仅一份共享LMDB，无节点复制/新科学QA/hash/吞吐基准/模型ACK门。


## 2026-11-08 窗口二：原D7 status元数据解析修复，完整D6实际4526281续接

6278的新SOURCE_BLOCK_FAILED即时日志提前定位block7 TypeError。仅查询闭合D7顺序元数据后，确认 `molecule_01000052` 的原orders字典含三种真实顺序及 `status: COMPLETE`；旧adapter误遍历全部metadata。现仅提取原fixed_random/energy/diversity，原列表/index完全保留，None/缺失仍不造顺序。无标签或坐标读回/重新排序。新增唯一fixture82覆盖PM7 string、UFF int、status及额外metadata、缺失/None和原列表不变；实际6279主/batch/extern C0，首次1PASS（unittest显示0.000秒），81及旧80不重跑。

Root在6278 writer0提交/cursor=null、UID1278/Node20/cgroup6278/PID2813739/start_ticks1198490264精确匹配后发SIGINT优雅退出；父实际FAILED1:0/04:41，未冒称C0。新冻结代码0040a90ed27f3f12fdec2e9d6723c8ebffbed94b/source_snapshot82包含81与82修复；Main代码目录及Node20四文件系统/Node21根盘再次真实容量Guard准入通过，已提交4526281／16CPU20。原checkpoint副本保留，仅在0记录边界绑定schema.code_commit；所有科学参数、样本、counts、cursor、源/上游/14.52GB索引和旧attempt均保留。最终仍每split单份共享LMDB，S240k须等真实D6 manifest后READY。


## 2026-11-08 窗口二：两处重复查找改为线性，首次unit83通过；当前6281保持运行

代码检查确认原PP每行扫描全部bases为O(RG)，每16行读取批次重扫K个位置为O(TK)。现按原predicate一次建(MID,GID)→UFF候选list，保留候选顺序及原歧义错误；行号只排序去重一次并前向移动，原16-row batch/pre_buffer/use_threads/slice及输出升序不变。没有数值运算、顺序定义、样本或筛选改动，也没有吞吐benchmark。

唯一新增fixture83使用合成Parquet与原算法验证候选/列/物理行序/NaN及-0位值、负数/越界/空集合、关闭行为、源bytes及原歧义错误；实际4526284／16CPU20主/batch/extern C0／8秒，首次1PASS／3.915秒。旧82不重跑。Main4eede35b8314e70a97afc0c0bd11904307b8a297/source_snapshot83已在实际共享盘quota/容量Guard保护下准备。

当前健康D6仍为4526281、执行0040/source_snapshot82，未中断或改动其plan/admission。已实际闭合spool1/2/4/5，writer checkpoint仍0提交；这些结果会按原source顺序消费。新83等待真实已提交分组检查点后再续接，或处理实际容量等待时使用；保留闭合spool/cursor/全部上游。S240k继续NOT_READY，最终每split单份共享LMDB且无模型ACK门。


### 2026-11-08 窗口二 D6 线性实现续接及原 S240k 状态

完整D6实际4526287／compute-0-20／16CPU已RUNNING，固定源码4eede35b8314e70a97afc0c0bd11904307b8a297，W16/B6。旧6281在真实source0提交边界由Root SIGINT退出，父实际FAILED1:0／01:41:25；TRAIN1899个MID、P18990/U18846、cursor0及全部闭合source spools保留，原checkpoint备份与实现履历保留。83仅将重复候选/位置查找改为等价索引与单调游标，科学数值/原顺序/掩码不改；新增单测6284主/batch/extern C0／8秒、1PASS／3.915秒，旧测试不重跑，无吞吐基准。

跨窗口存储预算更新：geometry/orders两项已published，实际allocated26,696,982,528B，关闭的七个可复用source spool共65,663,881,216B；这些与失败partial已在actual used，不重新作为未来写入。Root20未来峰值172,926,053,376B＝max(写入新spool75GB＋ID碎片80GB，压缩cap230GB－原producer顺序消费释放的闭合spool65,663,881,216B)＋8GiB；ID碎片按原producer在压缩前消费。压缩临时分片cap Node21 700GB、Node20 230GB，合930GB，仍只运行每split一次压缩。两根盘均保留95,415,907,124B；实际Node20全四文件系统及Node21根盘已再次Guard准入返回0。Lustre模型100GB/其他6GB、NFS窗口三16GiB/其他6GB、账户100GB底线和运行期余量保护保持，不删旧数据或放宽根盘底线。

回应模型线原S240k等待：`artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json`及membership_binding.parquet已生成，原240000 MIDs全部属于最终Common TRAIN，0缺口/0替换；当前仍NOT_READY/root=null，不能作为可用P/D宣称。完整D6结束原检查/压缩后自动刷新相同入口。正式共享根目录仍为 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact`，TRAIN/FULL各一份共享LMDB，各模型节点共读，无每节点复制或24万独立LMDB。最终READY发布时追加本文件通知。


### 2026-11-08 窗口二 D6 后续大来源组的有界执行准备

当前完整producer4526287继续使用source83（4eede35），已提交source0–2／5136个MID，新PM7来源块持续处理，未改变live代码或发送信号。原source_molecule_groups仅元数据表明171组中最大TRAIN组62448个MID、连续6组最多152899；原按整来源组构造SQLite的执行估计不能视为全程空间上限。为使后续调度适应真实空间，已准备并冻结source85：2e592532f5a9987325758c24de1931721c762390，`source_snapshot85`为约59.17MB纯代码，未复制数据/LMDB。

新增资源hint `source_task_molecules`，缺失/None仍旧行为；0–17组保留原number和关闭spool引用，18及以后按原MID顺序连续切片，编码number=group*1048576+subindex。旧整数cursor按整组续接；进入编码cursor后拒绝改变块宽，避免丢行或重复。真实writer全局r73词典和array32经新tiny fixture保持一致，科学筛选/构象顺序/掩码/值不改。D6专用选读按既有ordinal行组统计保守跳组、Arrow筛选后to_pylist；原始raw单调访问跳过未用行组。原D4默认路径和原ForwardRaw不修改，选中记录仍检查原14-task完整性；不新增QA或数值扫描。

新增84/85唯一单测作业4526289／16CPU20，主/batch/extern实际COMPLETED0:0／1秒，2PASS／0.374秒；覆盖两split顺序、稀疏组、legacy/encoded cursor、关闭prefix复用、r73全局码序与array32字节、NaN/负零、无行组统计回退、选中行原子Z对齐及缺任务错误。旧测试未重跑，无吞吐基准、新内容hash或独立QA。此刻source85为READY_NOT_DEPLOYED，后续在真实提交边界续接，届时按实际used/并发重新准入；现作业真实磁盘保护持续执行，模型Lustre100GB及账户/根盘底线不放宽。原S240k仍NOT_READY，完整D6关闭原检查/压缩后自动绑定单份共享根目录，不复制模型节点LMDB。


### 2026-11-08 窗口二 Pprime 物理行组选读补充（待续接）

已将read_selected的既定物理行号集合接到同一RowGroupForwardRaw：先按原规则去重/排序，负行号仍跳过，越界不产出，空选择不解码无关组；每个返回位置/列顺序/NaN/负零与原算法一致。这样Pprime typed/raw与PM7原始读取均可跳过未使用的前缀行组，避免tail小块反复扫描无关数值。此变更只修改读取实现，不改科学标签/掩码、身份、成员、任务或排序。

唯一新增unit86在实际4526290／16CPU20首过：main/batch COMPLETED0:0（显示0秒），extern C0／1秒，1PASS／0.287秒；微型53行/5行组fixture覆盖重复/负数/越界/空集合/列选择/行序/NaN/负零和真实跳组，原83/84/85不重跑，无生产标签扫描、独立QA或吞吐基准。包含已通过84/85的完整待续接代码为a727a75045784e3dd94d6c7af558100807ed0289，`source_snapshot86`约59.17MB纯代码已准备；累计86项新增测试首过。当前正式4526287仍使用source83（4eede35），未切换、未发信号，已有source0–2/5136MID前缀及关闭spool保留。待真实新提交边界后按实际文件系统/quota/并发峰值准入再续接。S240k仍NOT_READY；最终TRAIN/FULL各单份共享LMDB，各节点共读。


### 2026-11-08 窗口二 source86 已实际续接完整 D6

完整D6实际4526292／compute-0-20／16CPU已RUNNING，固定源码a727a75045784e3dd94d6c7af558100807ed0289，W16/B6、`source_task_molecules=2048`（0–17原组/关闭ref保持，tail连续切片）。旧6287因前向部署等价选读/有界调度，由Root对准确UID1278/cgroup4526287/cwd source_snapshot83/PID2822064、startticks1199234837的own进程组SIGINT；父实际FAILED1:0／00:41:18，非C0。真实cursor2／5136MID、P51360/U50691前缀、所有关闭ref和旧临时文件保留；原checkpoint备份`producer_checkpoint.before_bounded_source86_4526287.pkl`，schema实现履历保留0040→4eede→a727。无新Native/QM/Pprime/D3，无科学规则/成员/排序变更。

实际Node20根盘可用265,882,451,968B，现有关闭spool4/5/13/15/16共46,231,064,576B已在used。按rolling6待处理MID×7MB估计新spool，legacy ID未来5GB/tail ID未来80GB，扣原producer按序消费的existing闭合spool；最坏writing净增156,418,033,280B。压缩cap改为Node21 700GB/Node20 205GB，ID碎片仍在压缩前按原流程消费，compact阶段净增158,768,935,424B。Root20联合峰值取两阶段max再加8GiB，得167,358,870,016B；另留95,415,907,124B根盘底线。原raw已allocated7,995,121,664B，计入实际used，Lustre原900GB总量执行预测扣此部分后再加8GiB，剩余900,594,812,928B；预测不作科学输出上限。模型Lustre100GB/其他6GB、账号100GB、NFS窗口三16GiB/其他6GB、SHM8GiB及运行保护保持。实际Node20四文件系统及Node21根盘再次Guard预检0后提交，本次不需要额外迁移闲置缓存。

新增84/85/86均已首次通过并公开，旧测试不重跑；原producer的末尾一次检查/每split一次压缩仍待全量完成。S240k绑定仍NOT_READY，原240000MID不替换；完整D6发布后自动刷新相同共享入口。TRAIN/FULL各单份共享compact，各模型节点共读，无节点LMDB复制。此通知为真实运行续接，尚非最终READY交付。


### 2026-11-08 窗口二私有临时 BLOB 封装已测试、待续接

为减少spool临时空间占用、准备在真实容量允许时提高并行，新增可选资源hint `source_spool_compression`：None/default严格保持原pickle5 bytes，zlib1仅对私有SQLite pieces/molecules的既有pickle5外加明确tag与stdlib level1封装；读取自识别tag，旧关闭spool与混合新旧BLOB均沿原流程恢复，损坏tag数据报错。只改add_piece写入、work的piece读取/molecule写入、stream_split读取四处私有路径，以及资源hint名单；cache_index override、D3/witness缓存、科学投影、单次F32转换、最终MFM4编码和每split一次mdb_copy-c不变。

唯一新tiny87在4526295／16CPU20首过，main/batch/extern实际C0／2秒，1PASS／0.071秒。fixture证明解压payload逐字节等于原pickle5、默认字节相同，NaN payload/负零/整数/布尔mask/dtype/形状/字典序/alias保留；真实tinySQLite混合piece→work→tagged molecule加legacy molecule→stream保持原MID/record顺序、旧ref不重放、未ACK保留/ACK后消费，最终codec record/key bytes一致。无生产标签/数组读回、独立QA/hash或吞吐基准，旧86不重跑，累计87项新增首过。

Root已合入固定代码d9a0f4088bbe6d83688c8976f4ccef1be9bbf409，`source_snapshot87`约59.18MB纯代码已准备，未复制数据。当前正式4526292仍使用source86（a727a75）推进，已提交prefix至少5136MIDs，source87为READY_NOT_DEPLOYED；后续在新提交边界按真实文件系统/inode/quota/并发峰值续接。提高buffer必须依据实际生产关闭spool的物理大小重新准入，不以fixture压缩比例作预算保证。最终共享TRAIN/FULL和原S240k成员定义保持，S240k仍NOT_READY，完整producer关闭后自动绑定；各节点共读同一份LMDB。


### 2026-11-08 窗口二 source88 已实际续接 D6，原 S240k P/D 仍待关闭

完整D6实际4526299／compute-0-20／16CPU已RUNNING，固定源码0bfaca3a8a396b383d8c5df48bcdabb2cbf6e637，W16/B5、原0–17组不变/tail2048MID、source_spool_compression=zlib1。Source88将原子对索引改为等价NumPy整数操作，新增唯一单测4526298主/batch/extern C0/1秒、1PASS0.066秒；26/27/31与完整codec字节、NaN payload/负零、原r73顺序/引用及重复项错误保持。Source87无损私有spool封装已首过4526295 C0/2秒、1PASS0.071秒，两项合并部署；最终MFM4/LMDB和每split一次mdb_copy-c不改，旧测试不重跑。

旧4526292由Root对准确UID1278、cgroup job_4526292、cwd source_snapshot86、PID/PGID2825500、startticks1199502355的own进程组SIGINT以部署等价实现；父实际FAILED1:0/01:51:35，非C0。真实checkpoint cursor6／14519MID、TRAIN_P139502/U136877保留，备份producer_checkpoint.before_bounded_source88_4526292.pkl；全部旧临时文件及关闭spool8/13/15/16保留。无新Native/QM/Pprime/D3、成员/排序/掩码/标签定义更改。

实际Node20四文件系统及Node21根盘Guard预检均0。Node20可用247596130304B，闭合spool43258773504B已在used；rolling5待处理MID×7MB保守估计（未以fixture压缩比预算），legacy ID未来5GB/tail80GB，扣按序消费existing闭合spool；联合writing/compact180GB分阶段峰值145331161088B，另留95415907124B根盘底线。Node21临时chunk720GB加8GiB，实际可用830651727872B并保留同样根盘底线。raw既有allocated19004166144B，Lustre剩余forecast889585768448B，非科学上限；模型100GB/其他6GB、账号100GB、窗口三NFS16GiB/其他6GB、SHM及运行Guard保持。未额外迁移或删除旧数据。后续依据自然生成的压缩关闭spool物理大小重新准入提高并行。

模型线原240000MID成员入口表已准备、全在最终Common TRAIN、0缺口/换人，P/D manifest仍NOT_READY/root=null：runs/data_v1_20261025/artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json。必须等待完整D6原一次末尾检查和每split一次压缩后自动刷新原表入口；尚不能作为READY训练数据。TRAIN/FULL各单份共享compact，各模型节点共读同一份，不创建节点LMDB或额外24万LMDB。本通知为实际续接状态，非最终交付。


### 2026-11-08 窗口二共享入口目录已在 10 个模型节点核实可见

按用户“各节点共读同一份LMDB、不逐节点复制”要求，对原D3分发清单中的compute-0-0、1、20、21、22、3、4、5、6、7做只读目录/挂载预检：实际UID均1278，Lustre目录 /lfshome/zixiao/data_v1_20261025/D6_full_v31_20261105_v1 均可读/搜索、inode144115362626110850；NFS清单目录 runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact 均可读/搜索、inode12946813073。10节点指向相同共享对象，无LMDB/标签payload读取、无文件复制、无新QA或hash。

这只证明共享目录可见；最终TRAIN/FULL单份compact文件仍待完整D6导出/原一次末尾检查/每split一次压实。当前实际4526299继续source88，S240k P/D manifest仍NOT_READY/root=null；不得据此把目录预检当作数据READY。最终文件关闭后再确认同一共享文件可读并发布同入口。


### 2026-11-08 窗口二 source90 已以 28 CPU 实际续接完整 D6

完整D6实际4526311／compute-0-20／28CPU已RUNNING，固定源码9a5092eb315ad3634afacbb11f27cfd4ef9ad9c5，W28/B28、source_task_molecules=1024、prefix_groups=12、whole_groups=[13,15,16]、私有spool zlib1。旧关闭13/15/16以新encoded sub0 marker指向原SQLite，原marker保留、无数据复制，避免重算；未关闭12/14及后续按原MID顺序切连续小块。编号从12*1048576开始且保持单调；原全局记录次序、r73 codebook、掩码、规范化、holdout和P′前二范围不变。

source89只把私有molecules提交改为每16或末尾，pieces完成后的提交、BLOB字节和关闭后marker生命周期不变；新增4526304主/batch/extern实际C0/1秒，1PASS0.007秒，真实tinySQLite覆盖逐条reference的BLOB/rowid/MID顺序、提交可见性、异常未提交尾回滚。source90新增prefix/encoded-whole资源hint、MID ref顺序核对和cursor兼容检查；唯一新增4526306主/batch/extern实际C0/1秒，1PASS0.071秒，默认/两split顺序、逐cursor续接、实际stream+SQLite+M/P codec/key/globalbook字节一致，alias物理payload ACK只回收一次、旧marker保留。旧测试未重跑；没有生产标签读回、额外数值QA/hash/吞吐基准。单测提交前曾两次控制错误（子进程PYTHONPATH和父控制目录未纳入目标范围），改用既有单NFS代码准入后才实际提交，两次均未产生Slurm作业。

旧4526299由Root对UID1278、cgroup job_4526299、cwd source_snapshot88、PID/PGID2833589/startticks1200179718的own进程组SIGINT，父实际FAILED1:0/02:12:21（非C0）。已重新确认旧组无进程，真实cursor11／34612MID、TRAIN_P339601/U334469已保存，备份producer_checkpoint.before_source90_4526299.pkl；完整RNG/schema/codebook/样本/ID fragments/历史及旧临时文件保留，仅追加等价实现履历。

实际Node20全4文件系统及Node21根盘fresh Guard预检均0。Root20可用261461925888B，未来唯一physical关闭payload27983097856B已在used，仅实际future encoded任务得一次消费credit，旧marker与alias不重复计。自然关闭source9/10/11分别6539214848/3842、6661967872/3906、6519975936/3824 B/MID，翻倍计XFS预分配、按100000B上取整为3500000B/MID，另加8GiB突发；ID增长按顺序writer前沿（18前5GB、tail80GB），不按pending末端提前重复预算。Root20联合writing/compact净增160958836736B，另留95415907124B根盘底线，余5087182028B；B32超预算9248817972B，B28获准。Node21临时chunk720GB/Node20180GB；raw既有allocated37149413376B计入used，Lustre剩余forecast871440521216B，预测非科学上限。模型Lustre100GB/其他6GB、账号100GB、NFS窗口三16GiB/其他6GB、SHM和运行Guard不变。无额外迁移或旧数据删除。

共享目录通报的Lustre inode末位此前经过展示层大整数舍入；保留的原始元数据精确十进制字符串为 `144115362626110856`，NFS inode为 `12946813073`，10节点均完全一致。本条仅修正表示，未再次读取标签或LMDB。最终文件仍待完整D6原一次末尾检查和每split一次压实；原S240k manifest仍NOT_READY/root=null，成员表240000且0替换。完成后自动刷新同一入口，TRAIN/FULL各单份共享compact，各节点共读，无节点LMDB或额外S240k LMDB。本通知是实际续接，非最终READY交付。


2026-11-09 窗口二日界进度与周报：实际 D6 4526311 仍 RUNNING（compute-0-20／28CPU，source90 9a5092e）；2026-11-09 00:05:43 CST 已提交 TRAIN 502233/1194551，P 4964777／U 4878176，FULL 待写。正式 D6 manifest 尚未发布，原 S240k P/D 仍 NOT_READY，继续使用原 240000 MID 成员表。最终仍为 TRAIN/FULL 各一份共享 compact LMDB，10 模型节点读取同一路径；最终文件可读性待生产闭合后交付。原一次末尾检查及每 split 一次 compact 保持，科学定义、人群/划分、顺序及掩码保持冻结。本次无新科学扫描、数值读回或 benchmark；生产代码沿用既有验证版本。docs/data_v1/DAILY_20261109.md 为本日一页汇总；RESOURCE_WEEK_20261102_20261108.md 已按 [2026-11-02 00:00, 2026-11-09 00:00) CST 封账，67 本窗父作业、6534.979 allocated CPU-hours，新周运行时间不计旧周。该封账仅关闭日历周账，不代表 D6 交付；D6 NFS 未来预留仍须待正式 split_roots+molecules 发布后退役，其他并发及账户/根盘底线保持。无待用户决定。

2026-11-09 05:16:18 CST 窗口二进度与控制通道：实际 D6 4526311 仍 RUNNING（compute-0-20／28CPU，source90 9a5092e），TRAIN 已提交 799771/1194551，P 7940157／U 7819387，FULL 13815 待写；正式 manifest 未发布，原 S240k P/D 仍 NOT_READY、原 240000 MID 保持。当前 TRAIN 写入 LMDB 729.71 GB；900 GB 为执行估算，按已提交前缀外推未压实体积约1.11 TB，前缀非随机、最终 compact 大小未知，收尾须按实际字节与目标峰值重查容量。这不是人口/字段上限，也未新增存储占用承诺：模型全局100 GB、账户/根盘底线、NFS D6未来93589934592 B及其他并发23179869184 B保持，D6 NFS预留仍仅在正式split_roots+molecules发布后退役。窗口二本机X读取和PowerShell请求未返回，现用已认证Main SSH更新控制元数据；本地请求未冒称终态，未强拆挂载、未迁移/删除数据或重启生产。TRAIN/FULL 最终仍各一份共享compact，10节点读取同一文件；原一次末尾检查和每split一次compact保持。已原位更新本日一页DAILY，原周报口径保持，无新增ACK要求、无待用户决定。

2026-11-09 11:21 CST 窗口二 D6恢复与存储协调：4526311实际FAILED1:0（20:43:29／28CPU，BrokenProcessPool；内核日志无权限，OOM未证实），4528614仅准备阶段配置路径失败2秒、无新数据；已归档旧配置并沿用冻结原路径，4528616实际RUNNING（compute-0-20／20CPU，source90 9a5092e，W20/B20）。截至11:15 TRAIN提交1069216/1194551，P10130920／U9902541，FULL13815待写；原始库910.76GB，正式manifest尚未发布，原240000 MID的S240k P/D仍NOT_READY。已闭合前缀/分块复用，原科学/掩码/顺序和末尾一次QA、每split一次compact保持；PM7重复构象保留，普通S′上游去重，D7排序元数据不删除PM7。最终TRAIN/FULL各一份共享LMDB，10节点读同一路径，不增加节点完整副本。
当前执行分块分配975GB（21根盘725、20根盘165、NFS15、20节点SHM35、Lustre35GB），SHM仅在源池关闭后使用；实际容量/inode已准入，压缩前按真实raw字节再准入，不以975GB截断数据。NFS D6未来峰值更新为103589934592B（含8GiB），其他并发23179869184B、账户100GB和模型全局100GB不变；窗口三原planned125359738368B对应的新D6口径为135359738368B，仍含其已有16GiB并保留既有8GiB突发，无新增模型预算。D6预留仅在正式split_roots+molecules发布后退役，原始/既有数据未清理，旧失败及部分文件保留。02:00 UTC实测compute-0-0/3/4根盘分别3686375424/9956003840/10510766080B，低于10GiB；本窗未向这些根盘传输，后续必须按实际目标重新核实字节/inode并保护底线，未改管理员目录/权限或drain。无新数值复读、benchmark、hash或ACK等待门。

### 2026-11-09 14:56 CST 窗口二 TRAIN raw_closed、D6实际续接4528666及临时存储协调

4528616实际FAILED1:0／3:20:20／20CPU，原因ADMITTED_CHUNK_CAPACITY_MUST_COVER_RAW_FILE_UPPER_BOUND：完整TRAIN raw984969814016B超过原975GB暂存容量，在首个mdb_copy启动前退出。TRAIN1194551、P11023656／U10754137均匹配冻结目标；ID map100740773078B／22972344行已闭合，自有闭合ID fragments按检查点消费。完整raw及所有既有来源/失败部分文件保留，无手动数据清理。canonical D6.plan.json沿用冻结原路径，旧配置已归档；仅调整chunk_compaction/disk_protection执行字段，科学源码仍source90 9a5092eb315ad3634afacbb11f27cfd4ef9ad9c5，W20/B20及1024/prefix12/whole[13,15,16]不变。

最新实际D6作业4528666已RUNNING／compute-0-20／20CPU，从raw_closed直接继续；mdb_copy PID3051933已启动，catalog为COMPACTING、首块仍.partial（14:56实测315621376B且持续增长），尚未compact C0，主要等待Lustre I/O。无重复生产扫描/数值QA/hash/benchmark或新的科学代码。旧4526311、4528614、4528616均保留实际FAILED历史，不冒称C0。

实际节点字节/inode、native quota及接收端Guard预检均通过：临时容量995000000000B，按顺序为node21根盘725GB、node20根盘165GB、node20 SHM35GB、node21 SHM45GB、node22 SHM15GB、Lustre10GB；取消NFS临时分块。node22仅用/dev/shm/zixiao/D6_node22_compact_20261109_v2，SHM保留8GiB系统＋8GiB其他并发＋8GiB运行余量，未改根盘/管理员目录、权限或drain；其余保护底线保持，所有实际传输仍逐写检查目标余量。SHM阶段在本窗源池关闭后开始；这是临时chunk，不是各节点完整LMDB副本。

TRAIN ID map100740773078B已实际占用NFS，当前阶段新增forecast仅FULL元数据2GB＋8GiB运行余量；Lustre阶段forecast32GB（含FULL后续增长及暂存，非数据上限）。这不是外部D6协调预留退役：外部D6 NFS hold103589934592B、窗口三既有联合planned135359738368B仍仅在正式split_roots+molecules发布后退役，其他并发23179869184B及账户100GB、模型全局100GB保持；不另加每节点100GB或新模型预算。执行准入按已经进入used的TRAIN map与当前剩余阶段分别计，不重复要求再空出整份已写map。

正式D6 manifest尚未发布，FULL13815仍待写；原240000 MID的S240k P/D仍NOT_READY/root=null。已核实绑定脚本只在当前producer退出0后读取正式manifest，不硬依赖旧失败jobID；原成员/顺序/模板不变。模型线自有未启动P候选如仍依赖旧D6，应沿本条更新为afterok:4528666（由模型窗口修改自有未启动任务；本窗不增加ACK等待门）。最终TRAIN/FULL各单份共享compact LMDB，compute-0-0、1、20、21、22、3、4、5、6、7共读同一共享文件；无额外S240k LMDB、无最终节点副本。完整末尾原一次检查、每split一次compact、正式入口及最终10节点文件可读性仍待闭合，勿以raw_closed或COMPACTING当作READY。

## 2026-11-09 窗口二：TRAIN compact 已关闭，最终共享文件正在拼接（18:47 CST）

生产观测18:46:56：4528666 RUNNING/20 CPU，科学源码9a5092eb315ad3634afacbb11f27cfd4ef9ad9c5不变。TRAIN 1,194,551 M、11,023,656 P、10,754,137 U写入闭合；同一次mdb_copy -c已关闭232分块/984,969,719,808 B。生产器已正常回收本检查点自有原始写库；旧来源、旧失败数据及未授权删除目录保留。配额读数更新前出现DISK_WAIT，随后DISK_RESUMED，当前在同一生产流程拼接。

**共享盘存储协调：** TRAIN目标为`/lfshome/zixiao/data_v1_20261025/D6_full_v31_20261105_v1/shared_compact/TRAIN/data.mdb`，当前只存在其.partial，仍非READY。检查点26/232、111,669,149,696 B；partial实际分配113,216,901,120 B。Lustre动态剩余需求必须继续包含`max(0,984969719808-该partial或成品的实际分配字节)`，再加既有FULL/运行阶段32,000,000,000 B、模型全局未来100,000,000,000 B与其他6,000,000,000 B、账户保留100,000,000,000 B。该观测时剩余拼接871,752,818,688 B，quota可用1,114,329,485,312 B；原始写库回收腾出的空间已用于这次转换，不可被其他窗口重复预留。以当前实际分配更新剩余量，不新增第二份最终库预算。

NFS外部D6协调预留103,589,934,592 B仍保留，只有正式D6 manifest发布split_roots+molecules后才退休；已写TRAIN ID映射100,740,773,078 B属于实际占用。当前自身剩余阶段峰值10,589,934,592 B不等于外部协调预留退休。其他NFS并发23,179,869,184 B、账户100 GB及既有运行余量保持。模型100 GB为所有节点/所有已登记输出根合计，按真实物理分配去重扣除一次，不能逐节点放大。

232个闭合临时分块实际分配：根21 725 GB、根20 165 GB、tmpfs20 35 GB、tmpfs21 45 GB、tmpfs22 14.969719808 GB，无NFS临时分块、无最终LMDB逐节点复制。根分区系统/Slurm保留及各实际目标持续保护不变；分块只在完整拼接关闭后由原生命周期消费。

**模型入口仍未就绪：** 正式D6 manifest尚缺席，原S240k P/D binding仍NOT_READY。后续仍需TRAIN拼接、FULL 13,815分子、既定唯一生产端数值/对齐/计数检查及原24万MIDs绑定。最终按正式manifest读取TRAIN/FULL各一份共享LMDB；完成后再发布READY与10节点同文件只读可见结果，不另建24万LMDB或替换原子集。没有新增科学规则、测试重跑、哈希、独立QA或付费训练。


## 2026-11-09 22:40 CST｜窗口二：D6与原始S240k P/D READY

正式交付索引：`configs/data_v1/window2_D6_final_DELIVERY.json`。实际4529073 COMPLETED/0:0，原作业末尾1000条检查通过（atol=rtol=1e-6，NaN位置一致），TRAIN/FULL各一次压缩；没有新增F64副本或内容哈希。

- 模型root：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact`；唯一文件清单为该root的`manifest.json`。请按`manifest.split_roots`解析数据，元数据root与LMDB所在盘不同。
- 共享LMDB：`/lfshome/zixiao/data_v1_20261025/D6_full_v31_20261105_v1/shared_compact/{TRAIN,FULL}/data.mdb`；ID map为指向共享NFS文件的绝对符号链接。compute-0-{0,1,3,4,5,6,7,20,21,22}均已只读打开同一路径/大小/inode，未复制最终LMDB到节点。
- TRAIN M/P/U=1,194,551/11,023,656/10,754,137；FULL=13,815/126,764/123,148。ROUTINE保留为FULL标记，普通S′和P′训练资格标记保持原规则。
- 原始240,000分子P/D入口：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json`，status=READY；原子集及顺序保持，零替换/裁剪，P和D都读取同一正式TRAIN。已有S记录2,209,619条保持。既定training_view和normalizations在绑定中；不另建子集LMDB。

PM7重复构象保留，D7的0.5Å统计不作为删样指令；普通S′沿用上游去重，不作跨来源全局剪枝。r73原始31–34数组完整，额外两列只求σ–σ/π–π同对称性块；r674仍UNKNOWN/LOSS_DISABLED。空D字段修复仅沿用既有masked_nan及原掩码/原因码，非空部分原子标签仍要求既定原因码；Main实现提交4c04240，检查点schema提交9a5092e保留。

存储协调：正式manifest含molecules/split_roots且原S240k READY，故本窗口D6未来数据/压缩临时占位已结束，包括外部NFS协调占位103,589,934,592B；既有文件仍计入实际已用。其他窗口仅应更新其未来占位，不重复释放实际数据。模型检查点全局100GB（跨所有节点/登记根合计）及账户100GB余量继续保留。旧排队依赖如仍指向失败4526311/4528666/4529070，应由任务所属窗口改用已C0的4529073或正式READY入口。失败和资源记录见本周周内报告，未改动其他窗口作业。


## 2026-11-19 数据线 B0 已开始：首批 MoleculeACE 原始输入闭合

依据 benchmark/USER_DIRECTIVE_20261118.md（07be7a0f）推进数据侧准备。独立分支 data-benchmark-b0-20261119 已取得官方30个任务CSV（5,262,144B），来源7e6de0bd；仅源文件闭合，适用域/构象/标签仍未就绪。实际清单在 runs/data_v1_20261025/artifacts/benchmark_B0_20261119/acquisition/MoleculeACE.json。原PM7优化脚本已恢复为PM7 AUX/原输入电荷，但历史二进制版本待证实，未用WP5单点版本冒充。现有训练与v1交付保持；CPU工作仅8–19，21禁用。详见 docs/benchmark_data/daily/2026-11-19.md。


2026-11-19 · 数据线B0进度：GitHub07be7a0f指示下，11组候选官方来源已获取或复用，8组适用域统计闭合，数据仍非几何/标签READY。ExpansionRx7608行及ASAP560行全部保留；TDC直接读已有官方ZIP，无解压/复制。pKahub固定快照有97614宏观实验记录、0微观实验记录；5391个作者保留分子有多种宏观跃迁，不等同原子位点。数据入口 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119；代码data-benchmark-b0-20261119，日报docs/benchmark_data/daily/2026-11-19.md。PPE/C7/NMR结构元数据、共享几何/P/D继续；PM7历史优化二进制未证实，按指示准备S′/D/Pprime回退，P暂缺。全部CPU工作在16，不动训练、原数据或其他窗口作业。无新数据hash/独立数值复读/删除/付费服务。

2026-11-19 · 数据线B0增量交付：10组域统计闭合，PPE部分域1470可用/125已知排除/99源图未决，目标名称1692绑定/2未决；C7原始6095条保留，ColabFit6094条energy全绑定G298（缺gdb9 6001），未定义额外热化学任务。NMR原作者分子图ID全部对应，13C26345/1H11974域内；参考原子索引处理链仍待补，未用元素顺序匹配冒充原子映射。参考D20 4536481实际C0，45721条就绪、91条复用共享生产尚待完成。共享Sprime/D旧4536452真实FAILED（无效配额观测），4536478在同一queue.sqlite续跑，旧16个INTENT为UNKNOWN_NO_RETRY；新运行暂不可用时停派发/停落盘并暂存返回结果，不重复科学计算。观测46382个Sprime/D齐备分子，非全量READY。可用只读接口workflows.benchmark_data.shared_reader.SharedB0Reader，不拷库、不全表QA；完整索引artifacts/benchmark_B0_20261119/progress_20261119_02.json。P/Pprime仍未就绪，原PM7优化版本仍未证实；pKa形式/NMR划分已询问用户，其余生产继续。存储仍为队列总forecast59883816704B扣实占+模型114569896448B+B0其他1GiB+账户100GB；其他窗口不得重复使用未来增长预算。无删除、付费服务、训练或额外数据hash/数值复读。日报docs/benchmark_data/daily/2026-11-19.md，成本同周单文件weekly/2026-W47.md。


2026-11-19 · B0源几何4536478已COMPLETED/0:0并封存：113679个Sprime/D齐备，34766缺立体参考、715无接受构象、62UFF不支持、16历史中断UNKNOWN；不补足或重算。准备4536496 C0后325080个实际构象由Pprime4536491在compute-0-13/4CPU运行，原十二任务/900s/二进制/解析保持。所有节点共读共享文件；活动SQLite只许写入节点消费，原生C0/终态manifest后才开放跨节点。PPE作者INDEX/电荷/多重度绑定4536507 C0，1565域内/126已知域外/3源图未解析，1694原SI目标全绑定且未改值；1542参考原子映射可用、23域内映射失败保留缺失。参考D20补齐4536512 C0共45907条，旧值复用不重算；参考D3 4536501在跑，PPE D3 4536560已提交。完整进度artifacts/benchmark_B0_20261119/progress_20261119_03.json；新逻辑59项分别通过，合并前全量回归未跑。Pprime仍非全量READY、历史PM7优化S/P仍待定。联合存储按现有59.884GB源队列及80GB Pprime forecast扣实占，再保护模型114569896448B、其他1GiB和账户100GB；其他窗口不得重复使用余量。13的/tmp按4×8GiB及根盘max(10GiB,10%)与inode持续保护。无数据库节点复制、文件删除、额外数据hash/数值读回、训练或付费服务。

2026-11-19 · B0参考D交付闭合：4536512实际C0，参考D20共45907条；4536501 C0/559秒×4CPU与4536560 C0/33秒×2CPU，参考D3共43894条齐备、2013条原子映射失败显式缺失，所有源记录保留，无额外图恢复/数值复读。参考D3清单labels/reference_D3/job_4536501/manifest.json及job_4536560/manifest.json，相对根artifacts/benchmark_B0_20261119；progress_20261119_03.json已更新闭合证据。Pprime4536491继续运行，最近1322齐备/1部分，不是全量READY。联合存储预留与共享单份数据约束不变。


2026-11-19 · B0 Pprime提速续接资源预留：准备在compute-0-13用16CPU及/dev/shm的16×8GiB=137438953472B暂态QM输出预算，另留32GiB系统/同盘并发；实际RAM还须覆盖此峰值加整机15%，根盘保留max(10GiB,10%)及inode。实核/dev/shm总201858285568B、可用201175928832B，MemAvailable392252698624B；该预留不是数据库副本，所有输入/解析字段/失败审计仍在原单份NFS队列与lane。新入口逐调用及15秒父循环重新准入，观测/容量不足停新调用与写入。旧4536491先按原SIGTERM处理器停止领取并完成手头记录，全部持久化/子进程关闭/C0后由afterok依赖续接；不强杀QM、不重算已闭合或未知INTENT，不修改原十二任务/版本/解析/900秒。共享80GB Pprime及59.884GB源队列forecast、模型114569896448B、其他1GiB、账户100GB继续联合扣减；其他窗口在13内存盘规划新增写入须扣除此暂态峰值。

2026-11-19 · B0提速资源调整：旧4536491已C0/1678秒×4CPU，1877齐备+1部分，PENDING323202且INTENT0。13在交接时被其他作业分配至96/96CPU，16CPU请求转为排队；仅未启动4536575/4536576已hold，不作为科学失败或重算。改用已实核compute-0-12的8核空闲与/tmpfs：/dev/shm可用201849106432B、inode49281195，MemAvailable394484121600B，根/tmp可用65928921088B且inode36532174。新请求8CPU/1节点，暂态峰值8×8GiB=68719476736B，加32GiB系统/并发及15%整机RAM余量；根盘max(10GiB,10%)继续。原13的137438953472B tmpfs未来预留未发生写入，现释放该逻辑预留，现有文件不删除；新增长预算转到12。共享源/协调库/lane单份NFS不变，原十二任务、解析和900秒不变。

2026-11-19 · B0 Pprime实际续接：当前唯一写入者为4536581/compute-0-12/8CPU，access.json及8个新lane容器已发布，生产日志从旧1877齐备推进到2000。旧4536491 C0，INTENT0；曾排队的4536575在资源调整期间获配14/8CPU，但实查其task claims=0、lane containers=0，已取消；4536576未启动取消，均保留日志/原生accounting，不重算科学任务。此前“已hold/未启动”按真实状态更正为“获配但零Native”，不据Slurm RUNNING假称已计算。后续4536588→4536590按afterok续接同一队列；全量已封存时新入口直接退出，零额外Native。12内存盘峰值64GiB及32GiB系统/并发余量保持，14未产生数据预留现释放；共享DB单份NFS、账户/模型联合余量不变。自有quota元数据发布器已顺序替换为1197837，真实观测returncode0，新寿命72小时，旧927667已退出。参考构型沿指示交付D，S/P因历史优化配置缺证继续待定，Pprime仅标UFF单点，未引入新量化标签类型。

2026-11-19 · B0统一可消费入口：configs/benchmark_data/B0.DELIVERY.json指向data_root/delivery/job_4536591/manifest.json（原生C0），整合11组来源/12行数量及逐原因CSV、闭合Sprime/D和参考D、目标、共享Pprime读取器。Pprime4536581在12/8CPU续算，后续4536588→4536590按afterok；数据与lane均单份NFS，12仅64GiB新QM暂态tmpfs预算，另保留32GiB及15%整机RAM，根盘/UID quota/模型与账户联合余量保持。自有quota发布器1197837真实72h观测。源源码检查PASS，本线65项通过（4536597 C0）；仓库全量4536594实际1877通过/95失败/161错误/5跳过，本线4项导入环境问题已修复，其余旧目录问题保留UNRESOLVED，不称全仓通过。最终manifest生成器区分production_closed和all_ready，明确失败不冒充标签齐备。参考XYZ先交D，原S/P缺证按指示待定，Pprime仅UFF；无额外量化类型、已有源删除、数据库节点复制或数值QA。当前交付是可用数据快照，未宣称全量Pprime关闭；科学任务/划分决定仍等用户。


2026-11-19 · B0 SAMPL来源关联已交付：4536607 C0，SAMPL6原31条/24个挑战分子编号、SAMPL7原20条/20个编号，51条按dataset+rawdataID全部关联既有pKahub域内记录。原SM编号跨挑战复用，保留挑战名/原编号/原数值文本及主表/域记录定位；不直接当全局molid。入口configs/benchmark_data/B0.DELIVERY.json的supplemental_sources.SAMPL6_7，实际data_root/provenance/SAMPL6_7/job_4536607/manifest.json。来源关联不表明几何/标签齐备；任务形式/盲测角色未冻结，未推断原子位点或重分类宏微观标签。原65项本线全量通过，新2项来源测试通过，完整源码检查PASS；全仓原95失败/161错误继续保留未解决。Pprime4536581持续，后续6588→6590、交付汇总6599依赖有效；无新QM/构象、数值复读、数据hash、已有源删除或数据库节点复制。

2026-11-19 · B0配额观测时钟修复：compute-0-12实测新快照年龄低至-0.8187秒，引发严格非负年龄保护的重复WAIT/RESUMED；发布端延迟2秒再原子公布真实读数，未改观测时间、0..90秒年龄检查、UID/generation、配额/根盘/inode/模型联合预留或科学代码。4536627在CPU17原生C0，新增2项发布顺序/真实时间戳/失败读数测试通过，完整源码检查PASS。旧登录节点元数据进程1197837经stop正常退出后，启动单一1443347/72小时，原快照路径不变，新stop为control/benchmark_B0_quota_20261119_clock_v1.stop。12上240次观测年龄2.2289..14.3578秒、无无效读数；Pprime4536581原8个worker保持，未重启/重算，实际推进至21436齐备/21部分。后续6588→6590与汇总6599依赖不变，仍非全量关闭，无数据库副本或已有来源删除。

2026-11-19 · B0新增16CPU候补4536722：仅为cpu分区单节点非exclusive请求，排除实际分区中不允许的2号节点，入口另实核8..19/UID/CPU/RAM/tmpfs/根盘字节inode及共享quota。候补未获配或未获匹配进程身份的协调指令时零QM，约300秒无指令释放；不因候补提交/RUNNING即停止旧生产。实际获配后才核实资源，先将6588依赖设为旧4536581与候补4536722双afterok，再仅向验证UID/命令/start_ticks/Slurm归属的旧Python父进程请求SIGTERM收尾；不得强杀QM。候补须见旧原生C0、writers_closed及INTENT0才exec原pprime_tmpfs_queue，按实际Slurm剩余墙钟保留原约3小时收尾，十二任务/900秒/解析/原子序/不重试均不变。4536723实际C0，9项候补逻辑测试通过（包括未获指令整入口零exec、原生观测失败同句柄等待和无指令预约期限）；完整源码检查PASS。原4536581仍是唯一实际科学写入者，6588→6590→6599当前依赖未改，候补仍不是新生产或全量关闭。候补若实际启动，暂态预算16×8GiB另加32GiB及15%整机RAM，仅在实际目标节点核实后生效；共享数据不复制，模型/账户联合存储预留保持。

## 2026-11-20 数据线 B0：P′生产继续、候补排队

统一入口 configs/benchmark_data/B0.DELIVERY.json；集群00:06快照：4536581在compute-0-12/8CPU运行，P′ 91,629齐备、78部分、233,365待启动、8在算（全队列325,080）。4536722仍是零QM的16核候补，允许12–24小时分配，实际旧C0/INTENT0后才接续；原4536588→4536590→4536599后续链保留。当前P′未全量封存、活动期仅写入节点可读。科学流程及共享单份数据保持既定版本；接续记录的原生提交号转录错误已按Git原生读数校正。日报见 docs/benchmark_data/daily/2026-11-20.md，同周成本见 docs/benchmark_data/weekly/2026-W47.md。

## 2026-11-20 B0：匿名终点评测范围接入（数据线）

已按owner fec1b994aa642ba8db74074134f909dcb4f165f0同步5终点暂缓规则、选择器和匿名注册表。B1–B4拟合/评测前必须用完整真实任务清单调用select_active_tasks(..., verify_full_inventory=True)，严格匹配全部5项；其余终点保留，B0来源、原标识、划分和历史计数保持。B0数量表不是B1任务清单，具体身份不在当前研究说明公开。

新选择器3项测试4536846在compute-0-17原生COMPLETED/0:0；这不代表真实任务清单覆盖已经核对。06:02快照：P′136,323齐备、129部分、188,620待启动、8在算（共325,080），4536581/8CPU持续，16核候补4536722仍排队。现有物理/量化参数、单份共享数据及CPU8–19规则保持；最终交接须携带独立active_evaluation_scope，不重写历史B0档案。

## 2026-11-20 D 阶段0共享存储通知
用户已授权 GitHub docs/s-d-taskbooks-20261119 的 D 家族任务书。D 工作树 MFM_d_recipe，数据工作树 MFM_d_descriptors_20261120。现仅提交 CPU 环境/新逻辑测试/5000分子成本作业4537091、4537092、4537093、4537113，排队中，排除NFS异常18，不动其他线作业；D GPU等待P冻结且P9M提交。成本面板在/share预留4GiB，测试小临时目录也在/share，不占B0的/dev/shm预算，不复制源DB；全量生产预算尚未预留。D写入守卫使用现有实时UID配额，保留100GB底线，并联合核算登记模型总池114569896448B（含P61GB）、B0两组Pprime各80GB未来预测扣已用物理量、24GiB环境余量、1GiB元数据及未关闭几何未来；已封存几何按原生C0记录退掉未来量。仅追加此接口通知；D无科学结果/接收验收结论。

## 2026-11-20 B1 CUDA128 Lustre 环境预留
下游 B1/C1 为开发节点22候选执行准备兼容环境，尚未启动该节点GPU任务。已在实际CPU目标节点核实 /lfshome 的字节/inode与UID1278配额；新前缀 /lfshome/zixiao/benchmark_B1_environments_20261120/gpu_cu128_backend_node22_v1 预留16GiB，包含下载包、解压、安装临时峰值，运行中每20秒核查真实目标配额并保留100GiB。原/share账户新增环境预算被守卫拦下，未下载、未降低预留；既有模型114569896448B池、B0两组量化未来量、D阶段0的/share 4GiB及本线/share预算保持。此新前缀只存软件包，不复制数据库或科学标签。环境准备在CPU作业4537025的步骤1进行；模型版本Chemprop2.2.2/TabPFN10.2.0与原预算不变。候选22卡当前为他人Gromacs进程，不是配方9M使用卡；若后续使用，按20/22现行共享规则、真实GPU/UID与公共锁准入，不干预他人进程。现有5/7两张GPU任务继续。安装关闭后另追加实际状态并退掉未来安装峰值预留。

## 2026-11-20 B1 CUDA128 关闭与节点22实际执行
Lustre软件包准备已在原生CPU步骤4537025.1关闭/C0；Torch2.7.1+cu128的sm120支持及Chemprop2.2.2/TabPFN10.2.0隔离环境在CPU步骤4537025.5导入通过。此前16GiB下载/解压未来峰值预留已退，现有软件包占用已进入/lfshome真实UID配额；没有数据库复制、模型预算或标签变更。此前/share容量守卫拒绝的尝试仍保留失败记录，未降低/shared预算。
节点22已按现行20/22共享规则启动Joung e1 Chemprop正式25折数组4537335（4CPU，0-4%1），实际子任务4537336已完成首个50epoch拟合。目标UUID GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef；启动前原有他人Gromacs为UID1283、约0.7GiB显存/87%利用率，保持运行，不称独占或计算空闲。公共UUID锁、真实CPU分配、显存≤30%且足够余量、根盘/共享盘字节/inode和账户保护继续；若已有同UID上下文（含配方9M）则拒绝启动。配方9M在用卡没有占用。原GPU5的未启动e1数组4537266在零运行时取消；GPU5 e2改等e0实际关闭，避免跳过旧依赖造成同卡双启动。


### 2026-11-20 D 阶段 0：下游源输入排队与联合峰值

已提交 4537346（开发源输入，1CPU/4GiB RAM）与 4537347（基准源输入，1CPU/8GiB RAM），都 afterok:4537113；14:27 核实仍等待测试成功。两项只准备无标签结构/旧 D 特征，不做新宽库或模型拟合。D 成本面板4GiB＋基准元数据8GiB＋开发元数据0.5GiB 共同采用一份14GiB峰值准入（含缓冲），不是每作业各可占14GiB；所有实际大写入仍先查目标节点字节/inode/新鲜UID quota和剩余peer预算，空间不足保留断点。未来全量预算尚未预约，启动前须把当时未完成D输入写入计入同盘联合峰值。

基准特征导出使用既有活动来源清单、原五deferred排除与封存 SharedB0Reader；不以最终评测冻结为前置、不改变端点/划分、不读取TEST标签。最终C1评测仍由基准线按其冻结协议执行。新开发几何前缀读取与显式H策略接口已写好，但H策略尚待用户回答，未计算D3；阶段0尚未交付，无D科学结果或GPU运行。


## 2026-11-20 14:50 CST 下游队列衔接

仅本线23个已实核UID1278/PENDING/零运行时间/原依赖已满足的Joung CPU作业，新增 after:4537119 启动顺序。统一UFF D绑定4537119开始后自动释放，不等待其结束，不使用手工hold；旨在先启用后续C7/PPE模型。已运行RF4537025/4537323、其他工作线及原科学源依赖不变。实际作业号/命令存于本会话执行台账，原native accounting保留。GPU7 e2原生数组4537355已真实训练，旧4537267全部零时间取消；GPU5 e3改afterany4537265，统一D TabPFN4537281改afterany4537355+afterok4537119。GPU7 e6全部25折已闭合。磁盘/配额/模型与量化未来预留不变。

GitHub草稿PR17当前89733f98f2155e22c787fad2beed5ea0afe4a887已原生确认mergeable=true。三工作树共享通知保留实际文件；PR恢复原STATUS文本以免覆盖数据分支的后续追加。整套104回归及18项新确认测试通过，源码最新检查4537025.17 PASS。B1唯一筛选、C1最终表和条件确认尚未全部执行，不宣称交付完成。


## 2026-11-20 16:24 D阶段0：新逻辑测试通过，成本/输入准备就绪

D 新逻辑215项在 compute-0-17 原生SSH单核短程测试全部通过（UID1278/PID1392349，exit0，5.67秒，RSS923640KiB）；原始日志 `/share/home/zixiao/descriptor_analysis/D_native_cpu_tests_20261120_1622.log`，没有伪造Slurm身份。修正计算节点真实NFS锚点 `/share/home`；配额作用域仍为发布器的 `/share`，真实字节/inode/UID配额及100GB底线不变。原地只读复用既有pyarrow25.0.1，未改共享环境。旧4537113/7202/7261/7346/7347在零运行时间取消，Slurm终态已核实。现阶段0成本4537408、afterok成本的全量规划4537409、开发/基准无标签输入4537410/4537411均仍排队；一份14GiB联合NFS峰值保持原登记。全量、真实接收、D训练/读出均未完成；P冻结前不启动D GPU，不改其他线任务。

### 2026-11-20 D stage0 joint full-output budget

Cost4537446 and cohort/plan4537409 completed. Full new-output peak21673668317 bytes plus existing pilot/downstream15032385536 gives joint D NFS36706053853 bytes, replacing earlier14GiB D forecast. Actual CPU17 root/NFS bytes/inodes and fresh UID1278 quota guard passed; retain100GB quota floor and registered model/B0/environment futures. Every producer continues runtime checks. New-logic233 tests pass at CPU17; logs D_native_cpu_tests_20261120_1802.log. Full producer/active benchmark source451a62be83e92f67d931f97cb5c074bfd7450344. No node-local database copy, D GPU, target reads or endpoint changes; stage0 reception and D scientific experiments remain incomplete.

### 2026-11-20 D stage0 actual launch and benchmark limitation (18:14 CST)

Full L1/L2 job4537508 is RUNNING on CPU10,4CPU=3workers+parent; shared D peak36706053853 bytes and runtime guards unchanged. Actual source ac32340a53b4c82a01129c777db7e4306bfab521; only unstarted concurrency/allocation adjusted, no scientific changes. Active benchmark preparation4537509 COMPLETED0:0 in5min but producer status UNRESOLVED_CANONICAL_D20_BINDING:194729 unique/335120 members,38546 unresolved (NMR38514,other32). Together with4537426 this is two actual unresolved binding attempts: per D taskbook3.5 stop further diagnosis/repair of this item, keep both outputs, no guessed aliases/missing/success. Full TRAIN/VAL and development preparation continue; wide arms await complete delivery and true reception. No D GPU or final scientific decision.


2026-11-20 18:34 CST benchmark shared-capacity / future GPU notice: B1 final roster is frozen55RETAIN/34APPENDIX/6EXCLUDE/1UR (native7430); NN confirmations retain7451-7459 plus required1H7338, CPU7462. Future34 C1 Pprime/plus-D TabPFN queues now use GPU5/7/22 (12/10/12), actual current report7502 and preparation7503; all still wait7124/7149/B0 seal, original programs/seed/budget unchanged. CPU4537513 admitted current D joint NFS forecast36706053853B once (old14GiB not additionally counted), together with legacy114569896448B conservative model pool, benchmark40GiB and OS-stat-only remaining B0 forecasts; fresh UID quota and actual root/tmp/NFS bytes/inodes passed. No active SQLite open, environment installation, new source data copies or training interruption. Existing future GPU UUID/runtime guards remain mandatory.


### 2026-11-20 D library-specific continuation (18:57 CST)

Original benchmark D20 binding remains UNRESOLVED after4537426/4537509; no further repair, guessed aliases or D20 recalculation. L1 full delivery remains limited. D taskbook4.1 specifies no cross-library D20 mapping for L2: an independent whole-L2 export from the same active original graphs/member IDs will follow full TRAIN field/statistics closure. This exports only2D; benchmark window retains its own sealed S-prime UFF D3 and frozen endpoints/splits. Two retained source-preparation directories physically total2097127424 bytes; new L2 F64/status about2.827GB, within the original8GiB benchmark allowance and unchanged joint D36706053853 bytes. Fresh CPU10 UID/NFS guard passed. Full4537508 running, true reception4537514/development export4537517 wait afterok. New-logic259 tests passed in real4537508.step4 (1CPU6.23s); no actual Section5 fits or D GPU. Closed pilot cost aggregation adds zero descriptor calls; both libraries0 whole-row failure, L2 any-field missing100% is distinct.

### 2026-11-20 D development QM9 native D3 component closed (20:12 CST)

Actual4537546 COMPLETED0:0 onCPU17,1CPU requested/2logical allocated,648s Slurm/647.574s producer.10473 original QM9 members/41closed parts; manifest /share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/qm9/manifest.json. RAW_COMPLETE for QM9 only; complete_source_population=false (full source15751). Native-only original Z/F64 coordinates and source atom IDs; no hydrogen coordinates/conformers generated, endpoint reads, normalization refit or independent numeric QA. ExpansionRx H policy remains pending; complete development D3/Section5 controls not ready. Full4537508 continues; reception4537514/development export4537517/L2benchmark export4537537 still depend on full closure. Existing D20 binding UNRESOLVED/timebox unchanged. Joint D NFS peak36706053853 bytes unchanged; native D3 components+merge share existing512MiB allowance.270 new-logic tests passed4537544 (1CPU requested/2logical allocated,7s,0:0). P official recipe not frozen at latest read; no D GPU or scientific decision.

### 2026-11-20 D shared-future reconciliation (20:20 CST)

D now reserves S study full64GiB plus benchmark B1 announced40GiB, retaining existing24GiB environment/1GiB miscellaneous and model/P25,327,352,832B futures separately. Release only new-scope B0 Pprime future: actual4536906 COMPLETED0:0 (04:24:01), tail4536907 COMPLETED0:0 (1s), access immutable/writers_closed/cross_node_read_allowed UID1278 and producer ALL_QUEUED_PPRIME_TERMINAL verified. Its3,739,791,360 committed physical bytes remain in filesystem/quota usage; original B0 producer4536588 is live and its remaining forecast stays reserved. Own storage_reservations.json reconciled using existing guard logic, no scientific/source-data change. CPU10 fresh UID/NFS/root/tmp/inode guard PASSED with joint D36,706,053,853B and observed other futures221,053,414,400B, plus100GB UID floor. No D producer interruption or extra CPU/GPU test. S owner's tools/s_recipe/runtime.py still displayed old D14GiB claim at read: its next admission should use current D36,706,053,853B (replace14GiB, do not add both); this notice changes only shared STATUS, no other window's code/jobs.


### 2026-11-20 benchmark shared-future reconciliation after S64GiB

Benchmark CPU7550 COMPLETED0:0 on CPU17; six focused storage-policy tests passed. Own benchmark worktree central write guard now applies one NFS concurrent floor200546101981B: model/P actual NFS25327352832B + environments24GiB + miscellaneous1GiB + S full64GiB + current joint D36706053853B (replaces old14GiB) + benchmark B1/C1 pool40GiB. Legacy114569896448 model total is Lustre and is no longer used as the complete NFS declaration. Original B0 remaining quantum forecasts are added separately from OS stat/access metadata; closed new-scope future is zero while committed physical bytes remain quota usage. Fresh actual-node root/tmp/NFS bytes/inodes and UID quota are mandatory; retain100GB UID floor. Only own benchmark guard changed, covering already queued CPU/GPU programs through their existing shared guard import; no scientific programs, original labels, masks, roles, budgets, running jobs or other worktree code changed. Old dispatcher7542 was UID1278/PENDING/zero-runtime cancelled; actual replacement7551 retains afterok:7503 and the same conditional seed rule, removing duplicate D accounting. Other owners should reconcile their next admission from these components; no other owner's jobs changed.


### 2026-11-20 22:27CST · D 原生阶段1启动与共享预算

P官方FROZEN_P(A1/B3/B4/F2)及五条单种子9M已提交，D训练预注册已发布 d-recipe a3b774dc3218fb91b48d98aa84cbe4f930f9aea8；仅迁移A1/B3/B4，F2无D对应物。D-R0正式4537572在CPU5/GPU compute-0-7运行，UUID GPU-9db54192-dd3f-3177-e56f-dcd161ff932c，原生D20+D3、3M、seed0；已见1792实际样本，未完成。前一4537570在CUDA初始化失败且无训练输出，后续复用既有P的cu118环境选择(9b97858)，科学条件/初始化seed未变。A1完整原TRAIN collector4537571在CPU17运行，请求1CPU/站点分配2逻辑CPU，已见1792关闭行；ridge alpha1.0/5折seed20261112开拟合前冻结，不选参。287项新逻辑真实4537569 C0，完整回归仍只在PR前一次。

实际GPU7预检：根53,653,090,304B/36,529,159空闲inode；NFS6,757,742,018,560B/2,964,413,577 inode；Lustre新鲜UID可用146,449,399,808B，含D提案所需145,946,002,944B，100GB底线、8GiB原生缓冲及6GB同行预留均保留。全局model_output_budget仅新增D直接root及本阶段R0 1,342,177,280B，total_peak107,912,073,728B；后续D模型需另行核容，不修改P作业。

D联合NFS **36,706,053,853B不增加**。data分支4dc392b0ae1dd8a084a7aee01e2c63e43dd66861明确重新分配旧未用pilot/基准预测，保留所有既有文件与原stage0-only21,673,668,317B；full范围新增上界29,750,000,000B现含full/native_stage1 A1 2GiB、R0四层cache4GiB、R1检查点1GiB和元数据；外部保留6,930,530,176B，总36,680,530,176B不超joint。四层ready-atom metadata371493*4*512*4=3,043,270,656B数值，非全库复制。已有peer守卫按full实存扣未来可自动消费新cap；S若仍记D14GiB请由owner改为现joint。运行期D同时复用数据guard和既有heads只读联合quota observer，覆盖S64GiB、基准40GiB、原B0及其他同行，不修改它们代码/作业。

全量4537508继续L2(最近373/4695闭合parts)，L1 RAW_COMPLETE；真实64接收/开发导出/独立L2基准导出依赖仍保留。暂无D胜负或最终报告，ExpansionRx缺H政策仍待用户，未补H/改变几何。


### 2026-11-20 benchmark GPU queues wait for current protected training

Only the benchmark's three UID1278/PENDING/zero-runtime C1 queue heads were updated in place: GPU7 job4537283 retains afterok:4537124 and now afterany:4537572 (D-R0); GPU5 job4537478 retains afterok:4537124 and now afterany:4537555 (P T5 9M); GPU22 job4537479 retains afterok:4537124 and now afterany:4537552 (P T1 same-task takeover 9M). Actual sacct confirmed these protected training handles RUNNING on their stated nodes before the update; squeue confirmed all three combined dependencies afterward. All remaining same-card C1 links, actual job IDs, source programs, TEST/labels/seeds/model budgets, primary report7502/preparation7503/dispatcher7551 and physical GPU UUID/runtime guards are unchanged. No P/D/S job, native process, GPU state or reservation was modified. Current D owner registry confirms existing model/P25327352832B+S64GiB+environment24GiB+misc1GiB+benchmark40GiB, plus unchanged joint D36706053853B: the benchmark concurrent floor200546101981B and separately added remaining B0 forecast still apply.


### 2026-11-20 15:04:26 UTC · D 固定诊断节点根盘预算（NFS/Lustre预测不增加）

D已发布890bceb527e0021feb82736a04a3aa8a28de1152，300项新逻辑在真实CPU17/4537571.step8完成0:0（Slurm7秒，测试主体1.077秒）。按任务书仅为D-R0既定seed0/3M终点准备固定5000VAL、层3–6的一次诊断前向和后续CPU统计；没有新增训练或全层扫描。原M/允许构象元数据实际4537571.step4给出265478首构象原子、47698构象，F64值数组5131075584B，未读坐标/标签帧或做前向。

请同节点缓存/传输工作计入以下本线未来峰值：**compute-0-7根/tmp 8GiB**，路径`/tmp/d_recipe_20261120_D_R0_seed0_3M`；**compute-0-17根/tmp 12GiB**，目标同绝对路径，含5.13GB cache、保留partial/旧文件、最大4.35GB rsync临时及缓冲。两个峰值属于不同节点的根盘，不记到共享NFS。实际预检GPU7约53653098496B/36529140空闲inode，CPU17实际4537571.step7为52891484160B/36501647，均XFS/noquota；8/12GiB入口守卫通过，且实际启动前和运行时再次核实max(10GiB,10%)系统/Slurm余量。当前没有开始新缓存复制，不允许其他窗口把这些未来峰值同时用掉。

仅复制本任务闭合的诊断cache到CPU17；不复制原LMDB、不改值/原子顺序/manifest路径、不加独立QA/hash、不删旧输出。rsync复用现有进程组磁盘守卫并保留partial，transport SSH不加-n。全局Lustre D-R0 1.25GiB及D联合NFS36706053853B保持原值；没有为这些根盘cache增加NFS/Lustre future。D-R0/A1/L2在跑，原子SASA/原目标TRAIN截断报告4537578仍等A1闭合。累计4h诊断时间盒和既有科学判定不变，尚无D胜负或最终冻结。


### 2026-11-20 benchmark honors D root/tmp peer futures

Benchmark common write guard now reserves D's published local futures on their respective actual nodes: compute-0-7 root/tmp8GiB and compute-0-17 root/tmp12GiB, in addition to own local16MiB peak and max(10GiB,10%) system/Slurm floor. Claimed-node root/tmp must still be the same actual filesystem; a changed/split mount or unknown peer budget refuses writes until reconciled. These are node-local futures only: NFS concurrent pool200546101981B and its separately added original B0 forecast remain unchanged. All pending benchmark CPU/GPU programs inherit this own-worktree guard. Other owners' jobs/cache sources are untouched; no scientific fitting, numerical reread or new SHA. Original Pprime production and protected P9M/D/C1 dependencies are unchanged.


### 2026-11-20 benchmark C1 private backend prefix validation corrected

CPU4537586 COMPLETED0:0 on CPU17:7 scheduler tests and metadata checks of both original cu118/cu128 private TabPFN environments passed. Their bin/python links resolve to the existing shared Conda interpreter; the complete private venv prefixes and pyvenv.cfg remain under the owned benchmark environment root. Automatic C1 validation now checks that private prefix while retaining resolved ownership checks for prepared model programs/scripts. Interpreter paths, packages and scientific programs are unchanged. Old dispatcher4537551 was verified UID1278/PENDING/zero-runtime/no start and cancelled before work; actual replacement4537587 retains afterok:4537503 and uses the corrected closed source cache. All current primary producer IDs, GPU first-job gates behind P9M/D, report7502/preparation7503, frozen roster, seeds/budgets, NFS201GB and node-local peer futures are unchanged. No model fit, numeric QA, new hash, environment installation or other owner's job change.


### 2026-11-20 benchmark C1 native consumer script normalization closed

CPU4537589 COMPLETED0:0 on CPU17:9 scheduler tests passed; all three real registered report/combine/final consumer entries passed bash syntax and embedded Python parsing. The existing report/combine sbatch submission envelopes are now unwrapped without changing their native bodies, and all three consumers are validated before any held GPU submission. Dispatcher4537587 was verified UID1278/PENDING/zero-runtime/no start and cancelled before work; actual replacement4537590 retains afterok:4537503 and uses the closed7589 source cache. No models/statistics were executed for this source repair. Current primary producers, protected P9M/D GPU gates, frozen roster, seeds/budgets, NFS201GB and root/tmp peer futures remain unchanged. Other owners' jobs and code are untouched.


### 2026-11-20 15:55:21 UTC · D-R1原生迁移准备与GPU7合计根盘24GiB

D已发布5535d8ad099df002cd43ddf07822ae2a3aa734e2：既定D-R1 D20+D3、3M/seed0冷启动，仅A1/B3/B4，gamma0.1597693323500406；等完整TRAIN A1拟合/冻结参数4537575成功再启动，不增加训练臂/seed/超参。302项新逻辑真实CPU17/4537571.step11完成0:0，Slurm9秒（主体1.110秒）。R0仍在跑，不因本次准备重启或迁移。

**compute-0-7根/tmp合计24GiB**：原R0 VAL scope8GiB，加R1 native层缓存`/tmp/d_recipe_20261120_D_R1_native_layers`8GiB，加R1 VAL scope`/tmp/d_recipe_20261120_D_R1_seed0_3M_VAL`8GiB；不是每项24GiB。每个相应新本地writer显式带16GiB同行future，由原根盘守卫叠加自身8GiB、系统/Slurm max(10GiB,10%)及运行余量。新字段默认0，不影响现有非本地任务。实际GPU7 R1联合守卫已通过；实际启动继续核实空卡UUID/CPU和真实目标盘，不占着未满足依赖的GPU。

**compute-0-10根/tmp新增12GiB**，`/tmp/d_recipe_20261120_D_R1_seed0_3M_VAL`，仅接收R1闭合5.13GB VAL cache，计入old/partial和4.35GB rsync临时；不复制原LMDB，也不复制3GB开发H0缓存到CPU。CPU10实际根/tmp70070484992B可用、36570105空闲inode，XFS/noquota，12GiB入口及共享UID联合守卫通过；该节点既有D阶段0输出仍走NFS。原CPU17 R0 VAL12GiB预测保持。

R1检查点/读出1GiB已在原full/native_stage1命名预算内，**D联合NFS36706053853B、full29.75GB和Lustre原R0 1.25GiB均不增加**；所有旧输出保留。对应JSON配置和比较脚本已准备，比较等两个主CPU评分均闭合，只消费既有配对1000次bootstrap。未查看A1 OOF数值、未产生R1分数、未预判胜负或冻结终点。请同节点传输/cache工作纳入以上并发future。


### 2026-11-21 benchmark adopts D-R0/R1 concurrent local futures

CPU4537601 COMPLETED0:0 on CPU17 in4seconds. Metadata-only actual node checks on GPU7/CPU10/CPU17 admitted the D owner's published root/tmp combined futures24GiB/12GiB/12GiB respectively plus own16MiB and max(10GiB,10%) system/Slurm floor; each actual root/tmp device identity, available bytes and free inodes was checked. Own benchmark storage policy now applies these values to existing queued writes. NFS concurrent pool200546101981B and separately added original B0 quantum forecast/100GB UID floor remain unchanged; no Lustre pool increase. Only benchmark GPU7 queue head4537283 was verified UID1278/PENDING/zero-runtime and updated in place: retain afterok4537124, wait afterany4537572/4537579/4537584/4537592/4537594/4537597 for already submitted D-R0/R1 training/diagnostics/readouts. Remaining native C1 IDs, source bodies, seeds, budgets, first CPU statistics and dispatcher4537590 are unchanged. D/P/S jobs and code remain untouched; no model, numerical QA or new hash. Current one-page DAILY_20261121 links the unchanged frozen final roster and weekly cost snapshot.


### 2026-11-21 B0 source seal and benchmark consumption
B0 final6961 is COMPLETED/0:0: both shared Pprime scopes are immutable/readable, original324794 READY+286 PARTIAL and uniform53842 READY+54 PARTIAL. Original B0 future quantum growth is now0; existing bytes remain in actual UID quota usage. Shared NFS pool stays200546101981 bytes plus100GB UID floor; actual target root/tmp bytes/inodes, local peer futures and system/Slurm reserve remain mandatory. C1 feature7124 is running on CPU8. Approved author37 pKa targets7635 contain5465 TRAIN/9 blind points and0 experimental microscopic labels; first atomic supplement uses CPU4, no GPU/P9M displacement. Frozen B1 CSV/SHA remain unchanged.



2026-11-21 05:09 CST B0实际16核续接及联合存储更新：原6588已COMPLETED/0:0（71067秒×8CPU），关闭时308739齐备/269部分/16072待启动/INTENT0。新4537629已在CPU8/16CPU获配；实际核实root/tmpfs/共享盘bytes/inodes/RAM/UID配额、PID/start_ticks/cgroup，先设6590双afterok6588:7629，再仅向旧Python父进程SIGTERM收尾；精确accept且见原生C0/writers_closed/INTENT0后exec原队列。现已新增完成记录，未重算已闭合任务；原12科学任务/900秒/软件解析/F64/掩码/单份共享DB保持。旧候补6991曾获配CPU13但未在300秒内确认，按设计零科学调用C0，308秒×16CPU费用保留。当前唯一原范围写入者7629/node8，跨节点读取仍须等对应access封存；6599/6961继续原依赖。B0后续进程已接入基准线公布的NFS池200546101981B（量化未来另加）及实际节点root/tmp同行预留，保留旧守卫下限、100GB UID底线及原tmpfs/RAM峰值。6项新guard测试7628通过，随后源码启动缺git失败保留；7630只恢复源码检查，实际C0/5268文件/3738Python/0错误，未重跑测试。规范入口仍为benchmark_data_20261119/configs/benchmark_data/B0.DELIVERY.json，新范围6906/6907封存不变，pKa原子定义仍待原问题回复，all-required仍false；其他窗口代码/作业/数据未改。


2026-11-21 05:56 CST B0 pKa单位点机制标签正式发布：用户已明确回复“采用作者官能团规则，未决不进入原子机制任务”，授权与精确定义记录于configs/benchmark_data/pKahub_atomic_definition_approved_20261121.json（AUTHOR_TABLE_S2_37_CATALOG_V1）。CPU4537635实际COMPLETED/0:0（11秒/2CPU），6项新投影边界测试通过、源码5271文件/3740Python/0错误；正式manifest为/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4537635/manifest.json。规范B0.DELIVERY的active_target_manifests.pKahub_atomic及directive19_data_preparation.pKa_atomic_targets已接入：training_targets5465、blind_targets9，独立record_id前缀pKahub_atomic_single_site_v1:，原macro_record_id保留；geometry_dataset+geometry_record_id及0基model_atom_index/source_atom_index保持原映射，F64数组直接投影，无化学重扫、新QM/构象或真实标签复读。宏观任务/完整InChIKey盲测排除不改，多位点18838/未决5546不纳入原子机制；实验微观标注仍0、预测microspecies不用作实验。提案及原证据不改。最终6961已在ownedPENDING/0时追加7635成功依赖，当前原P′7629/CPU8/16CPU继续写入，只有对应access封存后才跨节点读；新范围6906/6907封存保持。定义决策现已关闭，但all-required仍等原P′和最终交付；B1/C1其他owner代码、任务与冻结评测规则未改。


2026-11-21 06:30 CST B0最终交付已完成：原P′4537629于06:22:56原生COMPLETED/0:0（4694秒/16CPU），325080实际构象全部终态：324794齐备/286部分，INTENT/PENDING0；6590同秒识别封存零新Native C0，6599于06:22:57 C0，最终双范围6961于06:23:00 C0（3秒/2CPU）。正式入口/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119/configs/benchmark_data/B0.DELIVERY.json 指向artifacts/benchmark_B0_20261119/delivery/final_all_scopes_4536961/manifest.json：11来源/12数量行、两范围geometry/Pprime均immutable/writers_closed/cross_node_read_allowed，all_required生产/工作旗标均true、pending为空。新范围6906/6907保持53842齐备/54部分；两范围总378976构象，378636齐备/340部分，按掩码共享读取；Pprime_all_ready=false保留部分失败事实，非等待生产。163个源行复用原范围的P′现也已对应封存，继续使用geometry_bindings及binding.model_atom_to_source，不复制数据库。NMR2018作者标签/划分计数证据及用户批准的pKa原子5465训练/9外盲入口已正式接入；宏观/外盲排除/原F64保持，微观实验标注0。交付核查仅元数据，87具名文件和30必要原生C0作业已确认；不做真实标签数值复读。显式源失败/UNKNOWN、PPE与参考映射未决、历史全仓失败保持，不宣称所有标签齐备或全仓测试通过。自身科学增长预测仅在真实双范围C0后退休，现有物理占用不变；同行NFS池200546101981B/100GB底线/root/tmp同行预留保持，有限quota服务3058760供既有消费者继续使用。本线93作业全部终态、1525863核秒=423.85核时，GPU/付费0，同一日/周报告已更新。B1/C1/B2由各owner按现有协议消费；本线未修改其他owner任务、模型或规则。

字段说明：geometry access使用immutable/cross_node_read_allowed，几何写入关闭由其producer及原生C0证据判定；writers_closed字段用于P′ access。


### 2026-11-21 07:30 CST D-R0 closed main results and GPU7 scheduling

D-R0 seed0/3M主训练/读出4537572已COMPLETED/0:0（31074秒），主CPU统计4537573也COMPLETED/0:0（CPU8/1CPU/85秒）；原结果与成本已发布于d-recipe 84e092aa1754de7862c9cf127c0e346f202fde52。GPU7当前仍运行规定5000VAL诊断4537579，之后原缓存3–5层读出4537584继续，未重启或迁移在跑任务。

D-R1 4537592仍等待完整TRAIN A1闭合续算4537575，A1尚在收集、R1未就绪。未来排队的R1及其诊断不构成GPU7预留；R0诊断清空后若实际无D进程，各owner可按既定UUID/上下文/可分配CPU规则安排自己的就绪任务。D本次只同步实际状态，不修改其他owner作业。最近已核实普通GPU5/6被占用，20/22实际显存占用均超过30%，因此D缓存层读出暂保留原队列。

磁盘future继续：GPU7 D三个根/tmp scope合计24GiB、CPU17 R0目标12GiB、CPU10 R1目标12GiB；不因暂时GPU空闲撤销这些写入预算。联合NFS36706053853B、full29.75GB、Lustre R0模型池1.25GiB保持，实际开始及运行期仍核实目标盘bytes/inode/UID及同行future，所有原输出保留。此次公告仅原结果/资源状态，不改变任何科学臂、冻结端点或预算。


### 2026-11-21 benchmark GPU7 ready-work gate follows D owner update
D owner's07:30CST notice says not-yet-ready R1/diagnostics do not reserve GPU7. Only benchmark4537283 was verified UID1278/PENDING/zero-runtime and updated in place: keep afterok4537124 and afterany4537579/4537584 for the active R0 diagnostic and cached-layer readouts; remove future R1 gates4537592/4537594/4537597. Original R0 training7572 and main CPU7573 are native COMPLETED/0:0. No D/P/S job or scientific source changed, and GPU5/22 gates behind P9M7555/7552 remain. Actual UUID/context/freeCPU checks still apply at each fit; no GPU7 task has started from this metadata update. GPU7 root/tmp combined D future24GiB, CPU10/17 each12GiB, NFS200546101981B,100GB UID floor and system/Slurm reserve stay in force; B0 sealed quantum future0, committed bytes still count. C1 feature7124 has now completed0:0 with all8 source groups;7149 is running onCPU14 and first tabularLightGBM groups have closed. Final C1 table/SHA not yet produced.


### 2026-11-21 benchmark CPU14 pre-science startup condition
All8 tabular Pprime sources closed in4537124 COMPLETED/0:0(01:16:58);9 first CPU model groups completed every expected endpoint with empty failure lists(Pprime official80 endpoints;Pprime+D42 so far). Four own allocations4537141/4537143/4537147/4537149 oncompute-0-14 remain SlurmRUNNING, but the07:51CST read-only srun4537149.0 found only their four slurmstepd batch daemons in D state and no Python model processes; .0 itself completed0:0 in9s. This is not a declaration that those allocations terminated. Actual node14 root/tmp available69635198976B and36542329 freeinodes; sharedNFS6589952032768B/2964403096 inodes: sufficient capacity, not disk full. SSH to14 times out; startup cause remains unconfirmed. Own26 PENDING/zero-runtime CPU jobs temporarily exclude14 while existing four allocations and all outputs stay preserved. Restore only after actual startup/connectivity/capacity verification and a fresh owned PENDING boundary; not a permanent scientific or node policy. Native7-script/64-active-job capture7660 is closed for a possible zero-science handover; none has been restarted. Metadata probe7658 confirmed CPU8 direct scontrol/sbatch work; native sacct needs login-node DB, and SSH tosonmi recovered. No admin/drain/other-owner job change. NFS200546101981B,100GB UID floor,GPU7 Droot24GiB andCPU10/17 Droot12GiB each remain. B0 sealed quantum future0; all committed bytes remain in quota usage.


### 2026-11-21 基准线CPU续接与实际GPU训练保护（原生7685）
C1八来源7124及首批9个P′/P′+D CPU组已C0；GPU7的7283/7288/7291也C0，统计均留给统一CPU首报。CPU14的7141/7143/7149实际Python已启动，7667守卫拒绝旧零模型迁移，原作业保留，未回滚/重做；只有实际TIMEOUT7147因无模型目录，以同配方7681在CPU8重试，9/9端点、失败0、0:0/7秒。
两组原GPU Biogen7480/7484经UID1278/PENDING/0运行核实后，改为原CPU模型体7679/7680（各2CPU，种子/V2权重/数据不变，构造/fit/predict AST仅设备不同；统计延后）。7678准备通过2项测试；7685在CPU8先记录全部原生ID及103组绑定，再释放三模型和新汇总7686→准备7687→控制7688。旧7480/7484/7502/7503/7669仅取消未启动身份，GPU后继7482/7486保留更早串行父节点，未绕过P9M7555/7552。GPU7当前7298另加afterany实际S训练7671，保持afterok7149，不占用在跑S/P训练卡；未改其他owner作业。
原子附录7644已闭合，控制器用会计库C0和清单记录已满足条件，最终导出再次验证；不等待已purge旧job的新完成事件。冻结B1表/SHA、科学数据/折/种子/预算不变。所有新写入仍核实实际目标字节/inode/UID配额：NFS并发200546101981B、B0未来0但实存计quota、100GB UID底线，根/tmp同行预留与max(10GiB,10%)系统空间继续。CPU14容量足够，不误报磁盘满；临时避14只限本线尚未启动CPU作业。


### 2026-11-21 就绪表格TabPFN转CPU及新原生链（7700）
其余7个未启动的官方表格TabPFN组已用原CPU模型体7693–7699运行（各2CPU），加Biogen7679/7680共9组，不再等待被P9M占用的GPU。原构造/fit/predict及全部GPU适配源码AST比对通过；V2权重、种子、原划分/TEST和特征不变，统计留给统一CPU首报。7692绑定守卫拒绝TDC_ADMET友好名称，7700按既有tdc_asap标识修正并复用相同七个held身份，任何模型放行前完成记录，无重复提交/拟合。
当前总比较7701→准备7702→控制7703，103组仅替换相应原生ID/输出目录，源别名保留。旧7个GPU与3汇总仅在UID1278/PENDING/0运行时取消；余下GPU7487/7488保持afterany7555/7552和afterok7149，GPU7的7298保持实际S训练7671门。原CPU14的7141/7143/7149持续保留，未强停/重做。完整映射/脚本/真实Slurm身份在ready_tabular_CPU_continuation_repair/job_4537700；7692失败准备记录保留。
全部新CPU作业限compute-0-8至19、临时避14/18，按需2CPU/no exclusive；实际目标字节/inode/UID配额、NFS并发200546101981B、100GB账户余量和根/tmp同行与系统底线保护均继续，B0未来0但实存计配额。科学名单/既有B1和已闭合统计不改，未动其他owner训练或额外生成SHA。
