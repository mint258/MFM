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
