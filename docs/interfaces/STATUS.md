## 2026-11-05 PubChem扩充：全池近邻完成，R/N排序进行中

扩充当前入口为[每日汇总](../expansion/daily_20261105.md)和[任务2.1完整分布报告](../expansion/v1_distribution.md)。原固定100万查询已自然完成，使用全部1,196,122个Common参考；统计、覆盖不足区间和图表已发布。官方全量获取、同v1规则回归/筛选及修正后的全池精确去污染已完成，109,875,599个去重结构留下105,670,833个候选，11类来源均已闭合。下文早期PubChem TIMEOUT、9/11 READY和组成规则仅保留为对应时间点历史。

截至11:55，全池精确近邻已完整完成：105,670,833个候选、88,756,722个不同指纹、555个闭合投影分片；low11/high5父作业及全部步骤均C0。R/N排序215已在Alpha使用32个CPU核运行，详见每日汇总和完整生产者清单。跨集群返回及全部关闭缓存历史保留。1000万嵌套R/N队列、各125万的首批、实际UFF/D、增广覆盖及最终批次报告尚未交付，不能作为训练就绪或接口ACK；草稿PR1保持未合并。

本次去污染只用完整InChIKey及原v1 wp5，不使用组成下界或通配符；PDBbind移出去污染来源，结构未确定的下游行剔出评估并保留逐条审计。扩充分子最多3个实际UFF构象，保留原固定候选、种子、生成顺序及0.5Å去重；不足时不补足、不科学重试，缓存支持以后续接第4个及之后。D20每分子一次，D3及原子SASA逐实际构象；本阶段不计算QM/P′或训练。严格>1%异常NEW/canonical新增掩码停止条件及全部未来预算后的200GB配额余量继续有效；不增加逐作业Root审批。

# Integrated model and data status

Data-line delivery updates are listed first. The model-line history follows in a separate section; its older data-readiness observations retain their original dates and do not supersede later delivery records.

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

---

# Preserved model-line history (model-v3)

2026-10-29 最新模型实现已公开af11eaae：C4 v3 PASS；完整137模块3235PASS/3原skip；首seed20设计+20接线模板静态通过，50有效更新实现通过合成/UNIT。实际4090 A采用5173 C0，BackboneOff及原输入一致；C1-a checkpointOff的4090已测，3090/5090待资源。真实D2–D6仍待，D3后24h真实阶段3/三卡2000、D5后阶段5科学顺序按用户v3执行。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 用户主线修订v3：C4已凭实际4524734 FP64 48/48判PASS，FP32仅非阻塞诊断，旧v1/v2不重跑。立即推进A采用/按显存checkpoint、三GPU同批C1-a全关checkpoint各测一次、首seed20配置及真实D3后50更新接线；D3到达24h内阶段3真实验收和三卡SDP2000，D5到达启动阶段5。D2–D6实际仍待，日志/SDK/同步/fixture/SHA不再阻塞科学主线；r674保留head但LOSS_DISABLED。详[本日唯一汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 v5已真实公开并通过同父16项资源元数据检查与仓库检查；Root已实际启动，等明确占用任务5142真实终态后只首次显式续新32/u9000→10000。31原失败保留，未新增模型有效更新；完整B与D2–D6仍待。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 最新：Native031/4525157在模型启动前被原GPU占用门拒绝，FAILED保留、无新增有效更新；有效bf16seed0仍9k。v4已停止。已冻结v5，仅等待明确占用任务5142真实终态，之后Root首次显式从030有效CP续接新32，任何新失败仍停止；公开/元数据验收后才启动。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 Native原S/FP32seed0=20k、bf16seed0=9k，最新030段完整SDK/官方同步/云回读已闭合，020–029原证据保留；新v4协调器已实际启动，等待原5090 UUID空闲后续接10k。完整B四曲线与D2–D6真实数据仍未完成。详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 阶段2耗时已超过早期预估；原因是用户修订梯度门后的全量重验、原失败保留与CPU/GPU资源排队。当前科学门不变，原3090与Native原5090都在等待资源。真实D2–D6仍独立待交，详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 最新模型状态：当前生产源已通过完整135模块，3186PASS/3原CUDA skip；当前A-v2全20批+500更新复核8/9。七组ABBA共28真实run的完整原生SDK、官方选择同步和云端元数据回读已闭合，详[阶段2当前报告](../model_v3/02_speedup_AB.md)与[当日汇总](../model_v3/DAILY_20261029.md)。D1同版本policy/config已双方签署冻结；D2–D6真实数据/归一化/子集/fullrelease仍未交付验收。Native原四20k计划继续：fp32seed0=20k、bf16seed0=9k，原5090被其他用户占用，10k段等待，seed1两支未启动；B/最终recipe及整份Stage0–7尚未完成。下方pending/draft与旧计数按日期保留为历史。

2026-10-29 canonical模型生产源已通过后验133模块：3122PASS/3原CUDA skip；新物理消费门保持原值/mask/合法scale，跳过无用head。Native4904已实际自动内存续接，最大原生712输入4906 C0。Model最终policy/config ACK待该canonical源实际公开后签署，D3–D6/真实release仍待，详[当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 开发GPU自动内存已明确获批，原预算/RSS/85%和科学门保持；Native026安全停界待新源采用。132完整回归及两组R1/SDK已闭合，物理政策133回归与实际D1 joint/D3–D6继续；见[唯一当日汇总](../model_v3/DAILY_20261029.md)。

2026-10-29 用户D1五项全部A已确认：[政策与边界](MODEL_LINE_D1_ALL_A_20261029.md)。[当日模型汇总](../model_v3/DAILY_20261029.md)：A-v2完整复核3/9及三组原生日志同步已闭合；原完整Stage0–7继续。joint ACK、真实D3/D4/D5/D6与最终冻结未完成，四极标签独立物理政策正在对齐。

2026-10-29 最新模型优先事项：[每日汇总](../model_v3/DAILY_20261029.md)。等变性采用v2；全部FP32补偿不采用且停止；C1-a工程性能在已有S直接测，不等待D-5。旧段中的原1e-5门槛和继续诊断不再是当前任务。

## 2026-10-26 Native S 长程准入实测闭合


2026-10-29 后续：[A00-v2/Native/FP32与数据依赖](../model_v3/STATUS_20261029_A00_V2_CP19000_SCALAR_REVIEW.md)。D1仍候选，真实D3–D6模型侧验收待办；来源角色FROZEN不替代Common人口或归一化授权。


2026-10-29 更新：[CPU 自动内存、A5-v2、残差 FP32 与 Native 续接阶段报告](../model_v3/STATUS_20261029_CPU_AUTO_A5_V2_FP32_NATIVE.md)。四套完整 CPU 回归通过；A5 和残差 FP32 仍未通过科学门。旧 A 类 PASS 按新规则逐项复核，D1 joint 与模型侧真实 D3–D6 验收继续待办。


CPU4521405实际C0/595秒完成全部9阶段：29项SDK元数据测试及4项checkpoint测试全PASS/0skip；两原短测SDK完整读回，两个safe checkpoint的保守未来上界约392.094MB，均小于384MiB cap；512roots/32768JSON/512MiB压力真实三组×八pass完成。Root据真实同一CPU父与两GPU原sup/raw sacct组装证据，原NativeV2完整准入已PASS；新长程phase仍未预留或训练。精确ops源码和有限工程配置见[方法与执行补充](../model_v3/reports/native_s_execution_20261026_v1/EXECUTION_UPDATE.md)，不是最终recipe/B*。

完整CPU归因4521404实际384次forward及全部观察器重放控制闭合，原等变性case仍0/48通过。GPU4521406的固定输入op显示原policy下10/11自然变化；独立strict诊断11/11稳定，但不能当生产物理门槛通过。原1e-5不改，数值候选在单独隔离分支实现。数据最终接口、架构/配方实验、用户确认后的冻结与最终交接继续待完成。
## 2026-10-26 启动有效期与实际重放诊断更新

四项CPU作业1334–1337在排队4小时有效期后才获分配，实际0–1秒FAILED，日志均为 `Queue lease expired before original work`，无worker admission、未执行原测试。原publisher按有限租期退出，未取消或改写这些作业。现场CPU13出现16空核后，Root复用原单任务提交器与资源核验直接重交：QA55实际4521398 C0/5s、55PASS/0skip，ABBA QA76实际4521399 C0/6s、76PASS/0skip；源码前后相同。SDK/检查点/全规模元数据压力验收仍未完成。

C4首例4521397实际FAILED1/9s，但三轮unhooked1→unhooked2→hooked及全部12次encoder前向已完成、JSON和52成员数组均持久保存，随后严格新重放控制判定不相等。旧1333档案及新三轮的数组数值比较也已保存。它仅为REPLAY_DIAGNOSTIC_ONLY，不是full48或科学验收；不改1e-5阈值或生产模型。W&B只读API再次确认账号mint_leaf/default entity mint_leaf258；线上同步未完成。

最新独立时间点账本为378个本模型父任务、772912 allocated CPU秒、29986 GPU作业秒；捕获时4521338仍PENDING，包含失败及启动成本，不能当最终成本或GPU利用率。见[实际会计](../model_v3/results/job_ledger_model_v3_active_v13.json)、[QA55实际核证](../model_v3/results/native_S_QA55_actual1398_v1.json)、[C4实际终态](../model_v3/results/C4_firstcase_GPU_1397_actual_closure_v1.json)。长程4×20k启动包仅完成静态审查，readiness与实际长曲线仍待完成。整份指南尚未完成。
## 2026-10-26 Native S 实测与完整回归补充

本条是当前进度快照，下面各段保留其原时间点事实。整份指南尚未完成。

- Root 3d9b1cc0c580dacc9398a5570b0c2fff3e257618 完整整合回归已由八个实际CPU父闭合：2592 collected、2589 PASS、3 skip、0 failure/error、112文件；旧失败没有改写。Native storage修订82项另由4521200实际C0闭合。
- 现有原生S短测已实际完成：FP32 4521331 C0/252s、bf16 4521332 C0/90s，均20更新、7680原始记录（23040视图图）；固定验证另外1024记录（3072视图图）。输入消费链相同。两个安全检查点及持久化离线SDK已生成，完整SDK独立读回和未来状态上界仍待CPU验收。冷启动VAL计时不同，不能当作稳定十倍精度提速。
- 现有S的四条20k更新精度曲线不依赖D5；科学计划和数值规则保持3d9/ce7，真实曲线尚未运行。它们不能替代D5代理架构/配方实验、两个预训练种子噪声或新标签验收。四成员将从各自seed的u0开始，短测u20检查点不作为科学曲线前缀。
- 4521328/4521329原生S启动失败、4521330/4521333 C4诊断失败均保留；C4组合等变性尚未通过。原严格1e-5阈值和未完成的诊断状态不变。A01独立ABBA测量4521338已提交，仍等待节点20分配，不记作测试或性能已通过。
- 原四项CPU验证在60分钟启动有效期内始终PENDING；Root仅按PENDING/UID/源精确条件取消，实际sacct确认未启动，旧回执/成本/账本保留。新1334–1337使用明确的4小时排队有效期、仍16CPU及原内层资源和源码，待实际执行。没有修改其他或数据线作业。
- W&B认证已确认entity mint_leaf258；这不等于任何历史SDK已在线同步。历史57份离线记录的完整性分类、选择性同步及两新profile的独立核验继续进行。
- 数据线最新STATUS仍为D1 draft.3未共同冻结、D1–D7最终交付未完成；继续现有S和合成工作，不生成最终recipe/B*、tag或HANDOFF。

# Model/data interface status

2026-10-26最新：整份模型指南仍未完成。A采样桥接+B候选wire/provider已完成独立与整合回归；最新Root3789c19865f70f80191986675cb13b606ebd210b为2473PASS/2CUDA skip、104文件，实际4项A→B→原trainer贯通全PASS。新独立C4组合检查则为48FAIL/9控制PASS，误差归因继续，不将原单独测试当组合接受。见[候选接口与完整限制](../model_v3/03_candidate_interfaces_20261026.md)及[289条原时间点审计](../model_v3/COMPLETION_AUDIT_20261026_v1.md)。D1draft.3可读而未最终冻结，最终D3–D7未交；没有最终recipe/B*、main更新、tag或正式预训练授权。


All dates use Asia/Shanghai. Model-line checkout:
`/share/home/zixiao/descriptor_analysis/MFM_model_v3`, branch `model-v3`.
This file records observations in this checkout; it does not declare external
data-line work absent or override another checkout's delivery state.

| Date | Item | Status | Path / evidence |
| --- | --- | --- | --- |
| 2026-10-25 | Model stage 0 | ACCEPTED: actual audit 4520329 and existing 2,016 tests 4520330 passed; 6x512+A4 total 22,352,859, backbone 12,709,424 | Report published on model-v3 at `3441b280bc34431bf8e7596465af28be073644b6`; `docs/model_v3/00_baseline_review.md` |
| 2026-10-25 | Model decision rules | Initial rules published with stage 0; user SoM coverage decision and bounded panel details recorded before scientific comparisons | `docs/model_v3/DECISION_RULES.md`; publication/execution mapping in `docs/model_v3/EXECUTION.md` |
| 2026-10-25 | D-1 | USER_CONFIRMED_NOT_DELIVERED; real integration awaits data-line contract | Expected `docs/interfaces/training_format_v3.md` |
| 2026-10-25 | D-2 | USER_CONFIRMED_NOT_DELIVERED: registry v3 with levels, families, groups, pooling, vector storage and physical masks | Data-line delivery path pending |
| 2026-10-25 | D-3 | USER_CONFIRMED_NOT_DELIVERED: pilot training export | Data-line delivery path pending |
| 2026-10-25 | D-4 | USER_CONFIRMED_NOT_DELIVERED: TRAIN normalization and elemental references | Data-line delivery path pending |
| 2026-10-25 | D-5 | USER_CONFIRMED_NOT_DELIVERED: nested molecule subsets and held-out-conformation validation | Data-line delivery path pending |
| 2026-10-25 | D-6 | USER_CONFIRMED_NOT_DELIVERED: full v1 export and node-local copies | Data-line delivery path pending |
| 2026-10-25 | D-7 | NOT_OBSERVED: descriptive conformation report | Data-line delivery path pending |
| 2026-10-25 | Model stages 1-2 | Original native jobs352/353/354 completed 20 updates each but failed profiler RSS/output budgets. Bounded representative capture tested9/9 in362, committed dc22d3f before retries365/366/367. A tools26/26 passed360; A/B scientific acceptance pending, B proxy awaits D-5 | `docs/model_v3/EXECUTION.md`; profiler-v2 and A tools use separate worktrees |
| 2026-10-25 | Model stage 1 | ACCEPTED: native365/366/367, nine-trace analysis369 and report378 all COMPLETED/0:0. Root reviewed numerical denominators and all three PNGs. Distance MLP dominates sampled GPU time; causal peak-memory dominance remains unproven | `docs/model_v3/01_profiling_baseline.md`; `docs/model_v3/results/baseline_*` |
| 2026-10-25 | Model stage 4 existing TRAIN | Metadata-only preparation379 COMPLETED/0:0; zero target records decoded. Selected-member semantic access audited; real materialization385 submitted under the frozen request. No D-1-D-6 substitute or new label generation | SA-3 `SELECTED_TRAIN_STORE.md`, `TRAIN_TARGET_ACCESS_AUDIT.md`; external request raw SHA ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1 |
| 2026-10-25 | Model stage 3 | Code integrated; post-merge 4520355: 2,067 passed / 1 CUDA skip. Ten trainer integration tests passed; nine synthetic head cases exceed R²0.95, repeated with isolated W&B 351. Real D-3 acceptance pending | `docs/model_v3/03_labels_losses.md`; merge `76bceb59d5372515fb10f8916b89ec2bb42fd4ed`; 336/338/342 history retained |
| 2026-10-25 | Model stage 4 | SoM binary coverage user-approved. SA-3 full363: 2,076 passed. Actual B3 safe load/SHA and target-free H0 candidate/random[5,384] passed360. Locating existing COMPLETE downstream store for TRAIN-only projection; this does not depend on new D-1–D-6 | `MFM_model_v3_sa3/configs/dev_panel_v1.json`; snapshot `464b96eff38a7b73b2dab5b7fd68bfd7b1146e58`; original358 spawn timeout retained |

The user explicitly confirmed on 2026-10-25 that D-1 through D-6 are not yet
delivered and instructed the model line to continue S and synthetic work.
The model line proceeds with existing S inputs and clearly marked synthetic
fixtures while these interfaces are pending. Existing WP5 family Parquet and
the historical target-fidelity registry are not replacements for D-1/D-2.

Stage gates: 0 baseline report; 1 profiler evidence on three GPU types; 2
numeric/trajectory and bf16 evidence; 3 real-data head/loss acceptance; 4
TRAIN-only evaluator and integration; 5 architecture decisions; 6 recipe/B-star
plus user confirmation; 7 freeze/tag/real smoke/PR. No stage is accepted by
preparing its implementation alone. No formal pretraining is authorized here.

Latest model-line observations: source public at
`61658a4c1f472de035601dbedc17809315774784`; post-merge406 passed 2,196 tests
with one CUDA skip. Native A00 controls405/410/411 passed their actual
20-batch gates; paired500 trajectories remain pending. Architecture branch412
and post-merge415 passed complete regression; scientific decisions await data/evidence.
Existing downstream metadata was resealed in413 with zero target decoding and
exactly the379 members/groups/roles/contracts. Real store421 completed17,602
selected TRAIN records with exact cohort replay and zero outer-target decoding,
after all2,096 SA-3 tests passed420. Full panel execution remains pending.
No new D-1–D-6 delivery is inferred from this model-owned existing-data projection.

2026-10-25 update: actual B3 nine-task/two-readout evaluation437 completed
18 cells, Slurm C0/543s, inclusive guard wall541.230s. It is a historical384
sanity check; independent native SDK verification/archive is pending. Do not
use its result for v3 architecture selection or claim512 timing acceptance.
C2 user-confirmed local-geometry bins to3D denoising vectors; branch441 passed
2,187 tests/one CUDA skip. Root392 passed2,255/one skip in443. Integration
and public preregistration remain required before real C2 fitting. CPU node20
is fully occupied by another user's104-CPU job; a temporary21/22 CPU exception
has been requested under the user's AGENTS rule, not assumed. Existing jobs
and the data line are untouched. D-1 throughD-6 remain user-confirmed pending.

Subsequent user instruction resolves CPU placement: submit CPU work to
available CPU nodes; GPU nodes are reserved for model training/fine-tuning
and other GPU jobs. Therefore the proposed21/22 CPU exception is not used.
Current site CPU partition is compute-0-2 and8–19; Root checks live allocations,
all-user requested memory and actual available memory before each admission.
C2 method is now publicly preregistered at1a8c124571ddf37f87ae06ef9971efa85e417f95,
with tree exactly equal to local dd6cbaf. Integration regression precedes fitting.

Latest verified integrations: export478–481 PASS2,285/one skip; precision498–501
PASS2,294/one skip; plan506–509 PASS2,306/one skip. All are complete disjoint
CPU regression partitions with actual C0 closures. Decision39 unit cases and
premerge502–505 PASS2,319/one skip precede a separate postmerge regression.
B3 independent487 SDK verification is complete (170,299 native records /
56,738 history, exact metrics/clean EOF/exit0); historical384 limitations remain.
A06 fused457 failed the original500-step trajectory gate; it is not adopted.
Fresh A00 export486 completed C0 and awaits explicit outer-terminal admission
before the primary512 panel. C2 fit482 failed during TRAIN solving, before any
validation geometry read; v1 remains failed pending a separately registered
TRAIN-only solver diagnosis. D-1–D-6 remain pending, with no delivery inferred.

Current toolchain evidence: primary512 run544 completed C0/512s, full9 tasks /
18 readout cells /1000 molecular-bootstrap draws, matched random512, cold cache.
Actual guard including cleanup509.330s and1.609GB output satisfy this run's1h/
2GiB budgets. Independent566 verified170,295 native SDK records /56,738 history,
every scalar and global step, clean EOF/exit0. It is an A00 short500 checkpoint,
not sufficiently trained-model or architecture acceptance; single-seed SD is
unavailable. Full reports/typed run CSV preserve all cells and negative results.
Root postmerge533–536 passed2,368/one CUDA skip. Stage4 overall still awaits
D-3 all-label SDP2000-update smoke on all three GPU types. C2 diagnostic559
is TRAIN-only and preregistered publiclycd0c434, original482 staysFAILED.
Archive562 completed with41 unique offline runs, including failed evidence and
independently verified synthetic resume513/514; no online sync is claimed.

2026-10-25 latest model-line evidence: C2 corrected artifact loader40 tests599 C0;
real TRAIN-only artifact preflight602 C0/6s (no native reader imported). New method
published as0f26274 with exact local916697e tree87d533a before first VAL. Actual
603 CPU8/16CPU/32GiB C0/127s evaluated all1024 existing-S PRETRAIN_VAL records
(55,650 atoms), current TRAIN geometry reads0, no new fitting. Independent606
C0/4s verifies31 SDK packets/two history steps/all public config+summary/clean EOF
exit0; report-source44 tests601 C0/67s. Component RMSE0.0654994134 Angstrom,
vector RMSE0.113448312, local-pair RMSE0.0575438344; analysis only, no model choice.
Report/PNG/source pins: docs/model_v3/05_C2_coordinate_baseline.md. Failed482/595
remain failed; no inferred original stop. A TF32 numeric failure589 and GPU-cap
abort590 archived by605 C0/1s after40 tests604 C0/3s, offline index55/no online sync.
D-1 throughD-6 remain user-confirmed not delivered. No final model/recipe freeze,
no main update or school-server job; overall guide acceptance remains pending.

2026-10-25 new observation: D-1 draft.3 and draft registry are now readable in
runs/data_v1_20261025/repository. Model review covers31 SHA-bound source files
and264 registry metadata rows, no scientific data or tests run for this review.
Opinions were appended under the actual contract's model-line section, preserving
its entire original15581-byte prefix; before/afterSHA receipt is published with
docs/model_v3/03_D1_draft3_review.md. Data wire tensor6/source-specific D5/sparse
reasons andr82 scatter already exist; remaining model consumption and scientific
contracts are distinguished explicitly. No v3.0 signature or D3–D6 final delivery
is inferred. An independent old-native S bond transport gap is being repaired
in isolated model-v3-s-bond-transport; no new wire codebook/physical-label decision.

2026-10-25 S native bond loader fix VERIFIED: optional typed old rdkit_bond facts retained through decoded collation. Targeted64349PASS/2CUDA skips; complete pre648–651/post656–659 each2388PASS/2skips,102 files. Actual production code 91f0c40a78478447a14ef2e8e91f05c07e0f5019. No new wire codebook/physical semantics or D3 acceptance. Report docs/model_v3/03_s_bond_transport.md.

## 2026-10-27 模型线实际更新

固定50条完整W&B日志已全部真实同步/读回核验（37finished/13failed），7条不完整原件保留未上传；统一训练记录入口已追加在线核验链接。新增S profiles和长段另行核验，活动日志不上传。数值候选完整CPU回归4521421实际2636PASS/3既有skip/0FAIL、113文件；原48项GPU矩阵4521435为10PASS38FAIL，候选不采用。S首长段4521411因quota freshness失败，无safeCP；原ledger失败计数只复用不重写。独立v4修正保留原校验并存拒绝feed、在原host封存；同science重试4521438已实际运行，8项启动metadata通过但父尚未终态。411父点时成本包含所有失败，非最终成本。D-1仍draft.3，D-3～D-6正式交付和全部指南验收仍未完成，无main/最终freeze/tag/PR。

证据、预注册、完整负结果和方法源：[训练前整理实际更新](../model_v3/reports/training_preparation_20261027_v1/PROGRESS.md)。

2026-10-27 模型最新实际：S安全累计2000更新/818176base，1459及独立完整SDK审计1487实际C0，下一段1485续跑。55份完整W&B已同步、回读和Root闭合，旧7份不完整保留。固定H0捕获1492实际C0/48组合192forward，但物理仍10PASS38FAIL；CPU影子v3仅预注册未执行。费用范围修正及全部限制见docs/model_v3/reports/training_preparation_20261027_v2/PROGRESS.md。最终D3–D6仍待交付，完整指南/模型/配方尚未完成冻结。

2026-10-27 后续：CPU1503实际C0/13秒，48/432精度分解与212来源独立闭合；FP64头仍31/48组合超限，原C4仍10PASS38FAIL。新encoder参考已267source/AST/bash静态及独立review完成，仅预注册待GPU。S1505实际C0至安全4000/1629317base，SDK待核；下一1548续4000→5000。56完整日志已在线Root闭合，原7不完整保留；显式7项集中CSV/曲线归档准备中。详见docs/model_v3/reports/fixed_h0_shadow_20261027_v1/PROGRESS.md，未完成整体指南或冻结。

2026-10-27 encoder参考1561实际C0/131秒，全192原H0位等、192F64与268来源独立闭合，三PD F64全部0/432超1e-5；原FP32仍10PASS38FAIL，尚未采用。AV局部数值诊断已静态复核并预注册待执行。S安全5000/2034688base、1616续6000；1635正常队列等待CPU核验4k/5k日志。56完整在线，显式7项本地归档准备中。完整限制及报告见docs/model_v3/reports/encoder_precision_reference_20261027_v1/PROGRESS.md；整指南未完成/未冻结。


## 2026-10-27 AV局部诊断与S长段归档更新

执行前公开版本99788277501ceff4a8adf37f7d9ee01498b9dbf1对应的AV诊断4521641实际C0/75秒：192次原H0逐位门、1152项原AV重放全部通过。中心化对Rnorm的聚合RMS约改善11.3%，第0层192/192局部项RMS变差，Rraw参照下总体也更差；不选层采用，未得到新的物理通过。统一六层FP32候选已SOURCE+CPU冻结，并在独立[实验分支](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)公开f8417157dc23326d1beca8e19e4725755d9f13c6（本地cf8ce66d97cd518ebf279b40ee20294919bb95e1）。完整CPU父1707实际C0/132秒，2712采集=2709PASS/3既有SKIP，73新测试及47原numeric全部PASS/0skip；[正式GPU协议](../model_v3/C4_centered_attention_e2e_prereg_20261027_v1.md)及运行器已执行前公开63ae209b27acabaadafa15cf4ebd8f64f8a98e06；GPU4521776实际FAILED1/42秒，48项21PASS/27FAIL、0error/skip，C4仍HOLD/noadoption，1e-5/rtol0未改。tiny CUDA及48个domain控制通过，来源前后相同，记录71/1872项字段观察超门；Root元数据已闭合、NPZ仅stat，[证明](../model_v3/reports/attention_centered_e2e_20261027_v1/ROOT_METADATA_CLOSURE.json)及原失败保留，[V2完整分析](../model_v3/reports/attention_centered_e2e_20261027_v1/ANALYSIS.md)保留15旧FAIL转PASS及4旧PASS退化，非单调改善；H0标量max/32-atom模式不足以定位机制。当前fixed-H0分解仅在准备，未执行/未预注册，须先按同分量H/G/I辨别再选干预。证据与完整负结果见[AV诊断进展](../model_v3/reports/attention_av_diagnostic_20261027_v1/PROGRESS.md)、[分析](../model_v3/reports/attention_av_diagnostic_20261027_v1/ANALYSIS.md)和[标量汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/SCALAR_SUMMARY.json)。

S首成员已安全闭合8000更新/3258368基础记录消费，4521773在快照时正续8000→9000；四成员各20k首成员仍未完成。slot7/8/9 SDK审计4521777实际C0/15秒、28QA、3006history全部typed匹配，同步1778实际C0/32秒并Root闭合三条；online现61，原7不完整保留。新增本地归档1780实际C0/3秒、3006history/原4QA，三页Root视觉检查和入口追加已完成，[证明](../model_v3/reports/attention_centered_e2e_20261027_v1/SLOTS007_009_ARCHIVE_ENTRY_APPEND.json)保留旧索引/前缀。8000不表示D5或B验收。61完整run已在线Root闭合，原7不完整保留；七项本地归档1639及slot5/6本地归档1649均实际C0、Root闭合和审阅后接入统一入口，旧索引不变。新增两段2004条history与每页1000个默认训练曲线点分母不同，见[本地归档证明](../model_v3/reports/attention_av_diagnostic_20261027_v1/SLOTS005_006_ARCHIVE_ROOT_CLOSURE.json)。

[v18点时成本](../model_v3/reports/attention_centered_e2e_20261027_v1/ACTUAL_COST_SNAPSHOT_v18.json)为2026-10-27 00:06:41 UTC（北京时间08:06:41）的454父/1171344 CPU核秒/52741 GPU作业分配秒，捕获时1338 PENDING/1773运行；非最终成本、利用率或费用金额，活动后续时间不在快照内。v11收据的payload摘要抄录问题已另有机器补正，原收据和预注册树保留。数据线持续有实际处理进度，最终D1–D7与扩充交付仍进行中；D3–D6最终未交、D1 draft.3未共同冻结；完整指南、B*、最终recipe/tag/HANDOFF/PR均尚未完成。此前各段保持原时间点记录。


候选的实际[完整CPU闭合](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_ROOT_CLOSURE.json)、[原汇总](../model_v3/reports/attention_av_diagnostic_20261027_v1/CPU_FULL_SUMMARY.json)和[独立分支公开读回](../model_v3/reports/attention_av_diagnostic_20261027_v1/CANDIDATE_PUBLICATION.json)已随报告固化；SOURCE/CPU冻结、完整GPU失败与C4 HOLD、最终配方冻结分别记录。

## 2026-10-27 当前centered固定H0诊断预注册准备

C4完整1776的21PASS/27FAIL与全部退化保持HOLD/noadoption。新的[执行前协议](../model_v3/C4_centered_fixed_H0_diagnostic_prereg_20261027_v1.md)只安排当前cf8/f841候选的fresh同forward H0/pos/state捕获：原48/192 FP32/0 F64 encoder、全52外部1776终端逐位重放及逐case passmatrix一致后，才以冻结1503纯CPU方法做432项同分量H/G/I分解。没有1776隐藏H0或旧1492/1503代替当前H0的声明；F64残差不自动归因encoder。Root静态5AST/2bash及metadata source audit实际通过，新GPU/CPU诊断均未执行；候选/model不变，无需新增整套回归。本协议及源待Root检查、公开读回后唯一提交；未更新v13的S/日志/成本快照或任何科学结果。

## 2026-10-27 当前centered固定H0诊断实测

预注册7b290606b776ba74d38a6976c0730360cc7a718e后，GPU1838实际C0/66秒完成48fresh case/192 FP32/0 F64 encoder，全部2496外部1776终端逐位重放；物理结果仍21PASS/27FAIL，C4 HOLD/noadoption。CPU1842实际C0/32秒，48case共432项观察；F64头D仍50项/30case超1e-5，max约3.08038e-5。原GPU失败同分量H为最大源项52、head arithmetic19；F64使42原坏降阈下又暴露21原好，不能称解决C4。Root两阶段均闭合1290当前raw refs/来源前后/监督，NPZ未由Root独立读取；[新报告](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/PROGRESS.md)及最终V2分析记录限制。下一历史H64接口量化CPU反事实仅待审提案，未执行/未预注册，不选新encoder算子或改512D API。

1776已公开V2 scalar仅派生分组字段有误，原48pairs/测量/MD的15改善4退化6共同PASS23共同FAIL正确；[V3 scalar](../model_v3/reports/attention_centered_e2e_20261027_v1/SCALAR_SUMMARY_CORRECTED_v3.json)与[更正链](../model_v3/reports/attention_centered_e2e_20261027_v1/GROUPING_CORRECTION_v3.json)新增保留旧文件，不视为科学重跑。 [Root独立分组核对](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/ROOT_DERIVED_GROUP_VERIFICATION.json)重算144份原case和闭合结果，确认四种配对分组与全部11个cohort分组；其余1776 scalar不变。

S1773实际C0/2507秒，安全9000更新/3665920基础记录消费；1830在v19捕获时正向10000运行，首个20k成员尚未完成。slot10 SDK待下一3段批次，online61不是62；非D5/B验收。[v19账本](../model_v3/reports/centered_fixed_H0_diagnostic_20261027_v1/ACTUAL_COST_SNAPSHOT_v19.json)固定2026-10-27 00:47:12 UTC（北京时间08:47:12），459父/1210864 CPU核秒/55161 GPU作业分配秒，活动1338/1830；非最终成本、利用率或费用金额。最终数据交付/全指南/recipe/B*/tag/HANDOFF/PR仍未闭合，main未变。

## 2026-10-27 历史H64接口量化CPU协议准备

新的[执行前协议](../model_v3/C4_H0_interface_quantization_CPU_prereg_20261027_v1.md)只对保存的1561历史H64做A/B/C纯CPU反事实：每arm192次head调用、432项观察，0 encoder/GPU；不冒作当前1838 H0。A先以1e-10核全部432×3个原标量控制，数值失败全48保留后HOLD；B只一次F32量化再无损提升，BC含实现/dtype/backend，不能推出通用FP32下界、必要API变更或CUDA结论。物理1e-5/rtol0与C4 21PASS/27FAIL HOLD不变。

Root的3AST/1bash/SA4审阅和最终metadata装配已完成；combined selected stat为125739933B，低于固定134217728B，未读NPZ payload/执行模型/提交。10份源及3份Root证明已逐字节快照；原README DRAFT字节保留，最终inputs/pins明确另绑定。资源固定CPU16/16GiB、120秒/RSS12GiB、3分钟、whole/private各2GiB；须本协议与精确源公开读回后Root唯一执行。目前没有该诊断CPU结果、PASS或采用；此前S/成本/报告继续保持其原时间快照。

## 2026-10-27 历史H64接口量化1917实测

CPU4521917在公开协议后实际C0/11秒/16CPU/node15；A/B/C各48case、192head调用、432项观察均0超1e-5，最大D分别1.223000971e-6/2.031757251e-6/7.897615433e-6。A全部1296标量控制max9.237e-14，原tiny controls、源前后/155current raw refs与125739933B<128MiB输入闭合，0 encoder/GPU。[完整报告](../model_v3/reports/H0_interface_quantization_20261027_v1/PROGRESS.md)保留所有字段/分组/同分量和tie限制；C的零D不是新terminal nonzero证明。

范围仅历史1561 H64及此CPU backend，非当前centered H0、通用FP32下界或一般head/CUDA接受；原1776/1838仍21PASS/27FAIL HOLD，无API/生产/候选采用。下一local-module F32 replay与同输入独立F64参考仅准备，未执行/公开预注册；旧F64参考不同数值算法，须明示precision+algorithm contrast。

S首成员安全10000更新/4076032基础记录消费，v20时1906续11000；四成员各20k仍未完成，slot10/11 SDK待下一3段批次，online61，非D5/B验收。v20固定01:56:54.187994UTC的463父/1274464 CPU核秒/59116 GPU作业分配秒，活动1338/1906，非最终成本/利用率/金额。最终D交付、B*/recipe/tag/HANDOFF/PR及全部剩余指南要求仍未闭合，未缩减范围。

## 2026-10-27 当前编码器局部算子精度预注册

本提交同时记录已闭合1917结果及下一项[局部算子GPU诊断协议](../model_v3/C4_encoder_local_op_precision_prereg_20261027_v1.md)。原1917报告、实验规则和所有历史证据保留；新诊断尚未执行。13份冻结源、4份Root/SA4证明、原始最终协议和点时成本已逐字节快照。计划192次完整FP32/0次完整FP64 encoder、5312次局部FP32重放及5312次独立FP64参考、4368项观察；必须保留原48 case和全部1838 H0/终端逐位控制，不选择层/seed或修改absolute1e-5/rtol0。候选仍cf8/f841，物理21PASS/27FAIL HOLD，无采用或API修改。正常仓库检查、公开精确tree读回和现场资源准入各以实际证明为准，源码审阅不替代运行。

[v23点时账本](../model_v3/reports/encoder_local_op_precision_prereg_20261027_v1/ACTUAL_COST_SNAPSHOT_v23.json)为470个已登记父任务，CPU分配核秒1385344、GPU节点作业分配秒66046；它含仍在运行/排队的任务，非最终成本、利用率或金额。原最终协议中的v21点时原件亦保留，未刷新历史快照。真实D交付、C4通过、阶段5/6实际对比与全量收敛、最终recipe/B*/tag/HANDOFF/PR仍待完成。

## 2026-10-27 D-1 draft4：模型线增量共同审阅

状态：MODEL_REVIEW_RECEIVED_CONDITIONAL_DOMAIN_DESIGN，未共同冻结。模型线已在[独立审阅副本的“模型线意见”一节](training_format_v3_draft4_model_review_20261027_v1.md)形成对数据线v12/draft4的反馈，并保留原提案、两项源码审阅与Root字节绑定。当前被运行任务pin的draft3原件未修改，未签v3.0，模型/原值/source mask/现有运行均不变。

r73接受无损保留已解析有序双端entry的方向，但须独立channel/onsite/重复身份及消费链；原对称pair头不可替代，当前codec的F64缺口需版本化解决。r674需完整六值作为一个对称张量，统一行坐标R约定、Frobenius/radial损失、TRAIN单尺度与partial-mask共同政策。真实原点/轴/单位/精度、原生对照、五层map/D4/D5/release及新consumer仍待完成，basis/tensor保持UNSUPPORTED/PENDING。该审阅未运行新测试或读取科学payload，不能代替D3真实加载、1000分子过拟合或三GPU SDP冒烟；C4的21PASS/27FAIL HOLD未变。源码审阅证据见[evidence目录](evidence_D1_draft4_model_review_20261027_v1/)。

### 2026-10-27 模型线阶段2/3/5/6：候选CPU核验与局部误差分析

- 模型实现：Native桥接74项、配方工具120项、A1/A5执行99项相关测试均实际C0且已发布独立分支；完整统一运行树回归与GPU验收待完成。
- C4：实际48案例/192前向/5312对局部调用完成；4368观测/546组统计和两图已核验，原21通过/27未通过、FP32容差保持。
- 记录：新增8段W&B日志实际同步、Root核验并追加统一入口，原SDK和失败历史保留。
- D-1～D-7：最终交付未齐，真实新标签及D-5/D-6验收待数据权威；既有S首成员17000步不替代科学验收。
- 报告：[训练前准备实际进度](../model_v3/reports/PRETRAINING_PREPARATION_20261027_v1.md)。最终冻结、B*、交接与PR尚未完成。

## 模型线增量 v19（2026-10-27）

三候选组合full4376已实际C0：116模块2734通过/3原CPU可选skip/零失败；组合源码已精确树发布到model-v3-runtime-integration-20261027-v1(public57d95b5c79fbd33e916330a455a7c3d4178c2284)。manual R2实际20批/500步与CPU consumer已Root闭合，不外推auto/R1/速度；Native10k full9面板CPU准备4415通过，GPU待现场准入。Core64完整48诊断和Native面板v2方法在本次预注册，尚无相应GPU结果。draft5条件式模型意见已归档，23明确输入当前核验，仍非joint freeze。参见docs/model_v3/reports/PRETRAINING_PREPARATION_20261027_v2.md及docs/interfaces/training_format_v3_draft5_model_feedback_DRAFT_v1.md。真实训练接线、FP32物理21/48、D1–D7最终交付和完整指南后续验收仍未完成。


## 2026-10-28 模型线实际进度 v20

[最新实际报告](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v1.md)与[精确证据](../model_v3/reports/pretraining_preparation_compact_evidence_20261028_v1.json)：训练/恢复/六层512 H0 CLI链实际CPU4524523完整121模块2905PASS+3原有skip，runtime快进同一tested commit并核2149受管源及9外部源，公开0cfc5c40。新FP32投影候选完整115模块2753PASS+3skip，候选b2c4c677与完整48GPU科学方法4bfb4263已公开，最终metadata和实际GPU仍待。

Native S10000完整9×2实际4476 C0/518秒，H0/来源/资源已Root闭合；候选/随机参考同可用几何人口，原SoM3/ExpansionRx48缺几何排除明确保留；SDK独立核验/同步待办。原全FP3221/48未升级，混合Core64实际14/48未采用。D1当前权威仍draft3，draft5未jointfreeze，D1–D7最终交付、真实A/B/架构/19配方/D6/120k-k2-1M E2E及最终冻结/交接/PR继续。没有开始正式预训练。


## 2026-10-28 模型线实际进度 v21

[最新报告](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v2.md)及[精确证据](../model_v3/reports/pretraining_preparation_compact_evidence_20261028_v2.json)：auto R2实际4551 C0/2274秒，20+500全通过且前向/梯度/轨迹最大相对差全0，源/资源闭合、hold释放；不扩大到R1/A5/ABBA/三卡或新runtime训练。新投影4550是12P36F/完整48，未采用，原正式21P27F不变；终端CPU4554全部1872重放一致且无本批不可表示分量，继续被动geometry/H0诊断。Native S10000 SDK4552与精确单run sync4555均实际C0并Root闭合，远端vcxcfx54 finished/56738历史行，原SDK/4553失败保留。4090新独立manual源包已备、还无提交；原1338不动。最终D1–D7/科学/配方/真实E2E与冻结/交接/PR继续，正式预训练未开始。

## model-v3: passive trace v3 / paired logs v2 (2026-10-27T20:25:39Z)

原指南阶段0–7仍未完成，FP32正式物理门槛仍为21/48；投影候选4550为12/48，未采用。归档的passive trace v3只补齐观测引用生命周期，固定原48例/192前向、52终端逐位对照、512MiB采集与原2GiB监督限制；源码审阅和Root AST4/bash1已完成，实际GPU采集结果尚未产生。

paired日志v2仅修复嵌套descriptor路径，原四ID/每role 500行/完整config及summary/原v3传输预算不变。实际核验4524559已在CPU节点提交，结果与在线同步尚待Root实际终态确认。既有S10000面板日志已同步；新日志不得据源码检查声称成功。4090作业4524558仍在compute-0-20排队，D1–D7最终交付和原完整剩余验收不变。

## model-v3 v23：实际离线统计和R1方法

报告PRETRAINING_PREPARATION_20261028_v3.md记录四日志核验/同步、全48被动采集和CPU4564完整9120条统计。模型及阈值未变，原formal21/27、候选12/36均未通过；完整0–7仍待。新R1 ABBA单员提交入口和原始脚本已归档，尚无R1实际提交或速度结论；D1–D7及最终冻结未完成。


## 2026-10-28 模型准备进度 v24

见[实际进度v24](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v4.md)：A00四次校准与日志同步闭合，速度比0.993无提速；新geometry候选116模块2816通过/3原跳过，GPU48待验。完整GPU与head-off方法同批归档，D1–D7及阶段0–7剩余科学矩阵继续；未最终冻结。


## 2026-10-28 模型准备进度 v25

见[实际进度v25](../model_v3/reports/PRETRAINING_PREPARATION_20261028_v5.md)：新geometry GPU4579完整15通过/33失败，1198源与资源闭合，未采纳；98份JSON独立确认双向翻转，headOff4580固定20批通过/500轨迹待终态。日志方法及负结果同批归档，完整阶段0–7未完成矩阵保留。

## 2026-10-29 模型线当前状态

原Stage0–7继续。[单日记录](../model_v3/DAILY_20261029.md)记录canonical8adb、实际133模块3122PASS/3原CUDA skip、Model同版本policy/config签署、R1两组实测与最大712单例SDK闭合。剩余A-v2两项实际GPU验收运行中；Native bf16/seed0已到6000，下一段等待CPU资源。D3–D6真实交付、架构/配方科学矩阵、B*确认、最终冻结、12万/k2/百万样本端到端和PR仍未完成；未启动学校正式预训练。


## 2026-10-30 模型线非数据依赖工作复核

第二种子实际配置/UNADMITTED请求接线已补齐，预算改为用户v3三倍确认线、
记账非阻塞；实际CPU4525191为138模块3263PASS/3原skip，首轮UNIT失败保留。
D1双方设计冻结仍有效；数据方当前STATUS明确D2–D6实际交付/验收未完成。
首seed20项静态准备完成，不能冒充D3的20×50更新或D5科学比较。
C4按用户v3为PASS；r674保持LOSS_DISABLED。3090/5090 C1-a、原438复核及
Native四条20k曲线仍受实际GPU资源阻塞；等待进程存活不代表已执行或科学完成。
详见[当日唯一汇总](../model_v3/DAILY_20261030.md)。正式预训练未启动。

| 2026-11-05 | 模型线 v2 M1 | MFM4/NaN/D5 排除/分子均匀采样的 UNIT 已通过；M2 真实验收尚未完成 | model-v3: docs/model_v3/M1_V31_LOADER.md |
| 2026-11-05 | 模型线 v2 M3 S | D5 240k 已连接到现有 S：240,000 分子、2,209,619 个训练 PM7 构象；按新判定规则开始 6M 开发实验 | docs/model_v3/DECISION_RULES_TASKBOOK_V2.md |
| 2026-11-05 | 训练视图依赖 | 等待窗口二 training_view_v1.json 后完成字段排除、r73 σ/π 与 D4 接线；用户已要求等待该交付，不自定字段 | configs/data_v1/training_view_v1.json（数据线） |

| 2026-11-05 | 模型线接收正式训练视图 | 已收到 FROZEN_BEFORE_STAGE5_PD，按原 pair 行汇总双轴同对称性的 σ/π，保留自环/方向/重复与缺失；正在接入134字段 | 数据线 configs/data_v1/training_view_v1.json |
| 2026-11-05 | M2 所需 D4 参数 | 现有 numeric_repetition_0 的向量路线仍为 PENDING_ACTUAL_JOINT_POLICY_RELEASE；请数据线在正式 D4 中交付字段到归一化参数的映射，包括新 σ/π、能量元素参考、矢量零中心单尺度及原子字段策略。模型端不以 B2 原始均值/标准差替代 D4，不用 raw-K 统计归一化 σ/π；等参数交付后直接进行 M2 | docs/model_v3/M1_V31_LOADER.md |

| 2026-11-05 | D6 r73 存储绑定已接线 | 优先消费 schema.derived_r73_pair_targets 的 array27 预聚合列；历史D3保留F32 K聚合，按各自schema标签字典解析通道。原子对仅在有标签的行执行预测，按原行号还原掩码/方向/自环；扰动标签使用真实array22，缺几何且无标签时保持缺失 | current/phychem_mfm/phase1/v31_loader.py；v31_training.py |
| 2026-11-05 | 阶段5代理人口保持 | 当前S对比使用已交付D5的240,000 TRAIN分子，训练索引为 runs/model_v31_20261105/S240k/records.parquet。后续P/D/SDP将消费同一代理分子列表；若最终D6缺其中ID，实际加载时报告缺口，不把另一份240k列表静默当作同一比较 | 数据线 configs/data_v1/D5_v1_pilot_provisional_delivery.json |

2026-11-05 模型窗口一已接D6 M17/M18：普通UFF按M17且排除M14，Pprime训练按M18且排除M14；先资格过滤再取k，保留的其他真实Pprime标签不自动扩张训练集合。D5诊断按实际holdout数组访问全部留出，包括普通排列之外的addressable几何；FULL不套用TRAIN-only的M18。若M18合格几何缺少发布的source order，模型会明确报接口缺口，不按存储序号猜次序。新增5项逻辑单测通过，M2仍等正式D4参数。

2026-11-05 最终人口消费约定（模型窗口一）：已收到最终Common TRAIN=1,194,551与D5完整池=1,126,937，新D5标明nested_selection_recomputed_for_final_complete_pool。M3及M4的24万代理仍绑定当前S实验实际使用的原D5 240k名单，后续P/D/SDP用相同MID，不静默换成新的240k前缀；D6交付后在实际消费者中定位。M5的120万格子人口不足已请用户作科学决定，答复前不改M或预注册。当前M2仍等待正式D4，三条S保持6M预算。

2026-11-06 用户已批准模型M5最大M由原120万调整为最终D5完整嵌套TRAIN全池1,126,937；同步修订PREREG、网格启动入口及HANDOFF，其余k/条件/种子/判据不变。M3/M4仍用当前S实际240k名单，不更换代理人口。正式D4/M2及实际M3/M4选型仍待完成，未启动性能实验。

## 2026-11-06 给窗口一/窗口二/窗口三及所有子agent的用户通知：节点磁盘保护

用户明确要求：以后往各节点传输文件时必须保证不要将磁盘占满，并让其他正在工作的Codex知悉。各窗口在下一次节点传输/缓存/解压/生成临时文件之前，重新读取项目根AGENTS.md及huagong_hpc_requirement技能顶部2026-11-06条款并在本状态文件追加简短已读确认；本通知写入不代表已经取得其他会话的已读确认。

必须检查实际目标节点的目标文件系统、可用字节和inode，计入复制/解压/数据库临时峰值、残留与跨窗口同盘并发写入；根分区至少保留max(10GiB,10%总容量)，站点更严格规则优先。空间不足或容量不明时不传，改经核实的scratch/共享盘或减小批次；传输中在触及预留空间前停止新增写入。/tmp可能占用根盘及Slurm共用空间。新传输/缓存入口必须落实检查与运行期保护。原始数据、其他窗口作业、管理员目录和drain状态不因这条通知获得修改/删除授权。

事故依据：节点17作业4526050于11月5日16:33向/tmp复制约29GB数据库，部分文件17,656,872,960字节，ENOSPC与SlurmdSpoolDir is full drain同刻；节点20作业4526119于11月6日01:35取消清理时一个进程未退出，触发Kill task failed，不能混同为磁盘满。

2026-11-06 模型窗口一已读根AGENTS及HPC技能顶部磁盘新规。实际节点21/20的根盘分别约831/526GB可用，均高于95.4GB系统预留线，inode充足；/tmp与根盘共盘。当前无新增节点本地大文件传输，模型已有CP约199MB/份并写共享盘；活跃S及下一M2近期新增预留5GB（后续大批提交前更新并与数据线并发合并预算）。共享盘整体约5.69TB可用，账户quota当前3630GiB/4096GiB，另保留既有100GB账户底线；不把共享盘余量当作节点根盘余量。后续checkpoint增加预检/写入期保护；不删旧文件、不动他人任务或drain。最终D6按数据线新接口读取共享compact，不复制到各GPU节点。

2026-11-06 模型活跃作业磁盘保护已部署：compute-0-21的观察进程3062529绑定本窗口4526020/4526023，compute-0-20的2706796绑定4526041；直接在实际节点每5秒检查根盘和共享输出字节/inode，当前均OBSERVING且状态持续更新。容量不足/未知只用scancel --signal=STOP --full并限定本UID、实际节点和这三个作业ID，保留训练内存/优化器/时钟，不重启、不取消或重算；主观察器会提示暂停/心跳失联。新4项逻辑测试通过；5GB是模型两节点合计近期预算，不重复预留为10GB。其他窗口320GB共享NFS及节点0 RAM/节点19既有缓存预留已读，不占用这些预算。

2026-11-06 模型M2正式D4接入说明请求：已读EA既有规则命中3,333条、其中222条新增掩码的生产端报告。M2会直接消费既有v3.1 D3试点及正式D4；请在D4交付中注明该遮罩版本与既有D3试点的兼容性。若修正适用于其中记录，请提供已有的NaN覆盖/正式mask引用及MID、RID、字段绑定；若无需覆盖，请直接说明。只需现有producer的版本/绑定说明，不新增扫描、数值回读或独立QA；模型不自行执行EA阈值筛选，也不把归一化参数当作标签遮罩。当前尚未观察到试点实际遮罩不一致，不据此判定数据错误；S实验继续。

2026-11-06 模型已接收用户冻结的向量尺度方针 window2_user_frozen_vector_normalization_20261106_v1.json：center=0，按已有physical_key的norm序列精确type7 0.001/0.999统计副本截尾后总体std(ddof0)作为每头唯一尺度；训练标签原值/NaN和原物理矢量损失保持，空/未定义/零尺度不发明epsilon或替代值。M2仍等实际参数与字段绑定。为加快接入，若所需截尾均值/std、元素参考及上述norm.std在median/MAD报告之前已由既有生产步骤独立闭合，可先发布明确状态的训练绑定供M2真实消费，其余D4报告照常继续；仅翻译已有参数，不新增扫描/拟合/回读，也不将部分绑定冒充D4全部完成。尚未闭合的参数继续等待。此前EA遮罩与既有D3的兼容说明请求仍有效。

2026-11-07 模型M2参数接续（PM7截尾矩已闭合后的跟进）：已读窗口二04:30生产汇总，PM7 pass9均值/std已171/171闭合，正在median/MAD；S三候选首种子6M及全部终点评价已完成。M2的1000分子过拟合/2000步SDP只消费既有PM7 D3和PM7训练归一化，不依赖P′参数、D6或median/MAD诊断报告。若既有pass9 winsorized_statistics、元素参考及字段绑定已独立闭合，请按此前请求先发布明确标注“训练参数已闭合、完整D4诊断未完成”的PM7正式路由供M2消费；P′和median/MAD照常继续，不把部分交付冒充整体D4完成。仅从现有closed JSON翻译/绑定，不扫描/重拟合/数值回读，不放宽尺度或改变标签。沿用用户冻结零中心/截尾norm.std_ddof0单尺度及既有target-local退化状态；D3试点EA遮罩兼容说明/已有覆盖引用仍需随绑定交付。模型不会自行生成统计或套阈值掩码。近期模型合并5GB预算继续为后续M2预留，结束的20/21模型观察已精确退出；新启动前重新核实目标容量并绑定自身任务保护。

2026-11-07 模型M2实际接入反馈：正式TRAIN routes已收到，新增按已发布mask_overrides_reference/native_record_id+MID应用EA标量leaf0 NaN覆盖，归一化前同步raw/valid；3项新合成单测4526232实际C0/0.11s，代码已推GitHub5a39f01。实际M2 overfit4526233在MFM4Dataset初始化、任何训练更新前失败：`D4 preserves disabled source loss for D20.MolMR`。冻结training_view_v1.json中D20.MolMR enabled=true、exclusion_reasons=[]；正式P_D路由native_d3ce435b9e185a70bb13ec72054c0f4a3ecd12ca418a850685fd3519425e843f虽normalizer_ready=true，但original_loss_enabled=false/source_loss_policy=DISABLED_UNIT_UNSPECIFIED。请窗口二按既有D1/物理损失策略对齐冻结视图与路由，明确该字段参与损失/仅保留统计的正式消费方式；模型不自行绕过禁用、不删字段、不造单位或参数。此为真实下游使用报出的接口冲突，不另起数值QA/源标签扫描。节点21已实核root约830.65GB、NFS quota337.32GB及各并发预算，M2近期5GB全节点合并预算继续预留；4526233零训练更新，原失败产物保留。

2026-11-07 模型M2反馈更正：已定位为模型适配器把字段选择与物理损失启用混为一谈，不再要求窗口二修改冻结视图。正式routes中original_loss_enabled=false现继承为字段loss_enabled=false：保留MolMR原始读取/已有归一化及统计，仅从优化头/损失/启用头R²门槛排除；r674和其他既有排除不变，不造单位、不改科学规则。Pprime同样继承D字段禁用标志但不消费D归一化，完整字段顺序保留。只运行修正旧fixture及一项新Pprime fixture，4526236实际2PASS/0.07s，旧其余项不重跑。原6233失败及零更新记录保留；模型马上用实际M2续接，参数交付已满足依赖，不再等待MAD或额外ACK。


2026-11-07 模型加载确认（M1/M2实际运行）：v3.1+D4正式训练参数及已发布EA逐记录NaN覆盖已实际读取。6238/1000分子过拟合和6239/2000步SDP均Slurm主/batch/extern C0；134读取列、133启用列、121物理头，MolMR原损失禁用仍保留。逐字段R²阈值保持0.95，实际40/133通过、93未达标；不宣称全部过拟合通过，不删这些字段。SDP前100→末100步S=1.266039→0.667048、D=2.187473→0.389692、P=144.239207→8.927668，三组均下降。全部失败字段如下（精确R²/MAE/有效数见 /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_failed_fields_20261107.csv；原完整逐字段表及两个summary/检查点见模型仓库docs/model_v3/M2_V31_DELIVERY.json）：

D20.BertzCT, D20.FractionCSP3, D20.HallKierAlpha, D20.MolLogP, D20.NumAliphaticRings, D20.NumAromaticRings, D20.NumHAcceptors, D20.NumHDonors, D20.NumHeterocycles, D20.NumSaturatedRings, D20.RingCount, D20.TPSA, D3.PBF_A, D3.PMI1, D3.PMI2, D3.PMI3, D3.SASA_atom_A2, D3.SASA_total_A2, P.pm7_B.r42.value, P.pm7_B.r44.value, P.pm7_B.r45.value, P.pm7_B.r46.value, P.pm7_B.r47.value, P.pm7_B.r48.value, P.pm7_B.r49.value, P.pm7_B.r50.value, P.pm7_B.r52.x, P.pm7_B.r52.y, P.pm7_B.r52.z, P.pm7_B.r53.value, P.pm7_B.r55.electron_electron, P.pm7_B.r55.electron_nuclear, P.pm7_B.r55.total, P.pm7_B.r56.EE, P.pm7_B.r56.EN, P.pm7_B.r56.NN, P.pm7_B.r58.value, P.pm7_B.r61.value, P.pm7_B.r62.value, P.pm7_B.r63.value, P.pm7_B.r64.value, P.pm7_B.r65.value, P.pm7_B.r68.value, P.pm7_B.r73.value.pi, P.pm7_B.r73.value.sigma, P.pm7_B.r82.De, P.pm7_B.r82.Dn, P.pm7_B.r82.charge_density_q_minus_Z, P.pm7_anion.r193.value, P.pm7_anion.r196.x, P.pm7_anion.r196.y, P.pm7_anion.r196.z, P.pm7_anion.r210.value, P.pm7_cation.r262.value, P.pm7_cation.r265.x, P.pm7_cation.r265.y, P.pm7_cation.r265.z, P.pm7_cation.r279.value, P.pm7_octanol.r329.value, P.pm7_octanol.r331.value, P.pm7_octanol.r332.x, P.pm7_octanol.r332.y, P.pm7_octanol.r332.z, P.pm7_octanol.r341.value, P.pm7_octanol.r343.value, P.pm7_octanol.r346.value, P.pm7_water.r396.value, P.pm7_water.r398.value, P.pm7_water.r399.x, P.pm7_water.r399.y, P.pm7_water.r399.z, P.pm7_water.r408.value, P.pm7_water.r410.value, P.pm7_water.r413.value, P.xtb_ALPB_octanol.r459.value, P.xtb_ALPB_water.r498.value, P.xtb_fod.r537.value, P.xtb_fod.r538.value, P.xtb_perturbed_gradient.r624.value, P.xtb_perturbed_gradient.r625.value, P.xtb_singlepoint.r666.value, P.xtb_singlepoint.r667.value, P.xtb_singlepoint.r668.value, P.xtb_singlepoint.r669.x, P.xtb_singlepoint.r669.y, P.xtb_singlepoint.r669.z, P.xtb_singlepoint.r671.value, P.xtb_singlepoint.r672.value, P.xtb_vfukui.r712.f_minus, P.xtb_vfukui.r712.f_plus, P.xtb_vfukui.r712.f_radical, P.xtb_vipea.r751.value, P.xtb_vipea.r752.value

仅实际训练与producer报告，无标签二次扫描/拟合/独立QA或额外冒烟。原6233/6237零更新失败保留；适配器已继承既有物理损失标志并复用S入口精度初始化，不要求窗口二改视图/科学。M3 P/D/SDP待实际D6，仍须同现有S实际24万MID；不自行替换新前缀。两节点近期模型增长仍按全局5GB联合预算，不按节点重复；完成的M2保护观察按精确own PID退休。


2026-11-07 模型M1/M2阶段PR已提交：https://github.com/mint258/MFM/pull/5 。实际完整CPU回归4526242主/batch/extern C0，3368 PASS/3旧条件跳过/5警告，1765.37秒；随后仓库检查PASS/errors=[]。真实M2结果仍为40/133字段R²达标、93未达标已通知，一次SDP三组下降，不提升过拟合结论。PR与main仅共享文档冲突，保留双方全部新增记录完成合并；实际模型代码未因合并改变。联合架构、M4配方/B*和最终冻结仍待原定实验；D6由窗口二继续，无性能网格/付费服务器/正式预训练。


2026-11-07 模型窗口一后续M3/M4检查点存储预留：正式D6仍每split单份共享compact，模型各节点共读，不复制数据。后续新增模型检查点/恢复partial/旧新共存/曲线拟写 `/lfshome/zixiao/model_v31_20261105`，全节点合计新增峰值预估100,000,000,000B（不是每节点，也不是输出/时间硬限）；近期原NFS模型5GB改作该共享Lustre预测，NFS仅模型配置/控制日志约1GB，其他窗口尚未调减其既有6GB合并预留时继续保守扣除。实际compute-0-21 findmnt为10.1.1.100@tcp:/data Lustre，df可用41,729,069,383,680B、inode36,288,634；真实UID1278 quota余1,032,528,035,840B。联合扣PM7未来56GiB、窗口二缓存100GiB、其余6GB、参数temporary1GiB、本模型100GB、账户100GB及8GiB突发仍有余量；根盘830,651,338,752B可用，高于95,415,907,124B保留，root/tmp无新增bulk。三项P模板仍root=null，未启动任何训练/未写Lustre检查点；每次真正启动仍在实际目标节点重查字节/inode/真实quota、计入并发并落实运行保护，无新ACK等待门。旧模型产物保留，不迁移/删除，不改变科学配置。


2026-11-07 模型磁盘观察器已补真实账户quota：新增5项逻辑单测4526245实际主/batch/extern C0，5PASS/0.84秒、旧4项未重跑；仓库检查PASS/errors=[]，累计110项新增逻辑测试。读取已有原生quota快照，校验UID/文件系统及有效时间0..5秒；扣账户100GB、全节点未来增长/同盘并发和8GiB突发，整盘df充足不能绕过用户quota。未知/不足只对本窗口绑定UID/节点/Slurm作业STOP；原字节/inode及根盘规则保留。后续实际训练绑定相应原生快照及实际预测，未新增科学QA/哈希/收据/内存或墙钟限制，未改变模型/数据/科学规则；仍待D6。


2026-11-08 模型窗口一：已接收最终D4，现用早交付TRAIN参数仍有效，原M2历史结论不变。加载器已按实际D6 producer合同从schema根manifest.split_roots读取TRAIN/FULL共享LMDB并消费根molecules计数；外部ID map沿发布符号链接供MID/EA覆盖共同使用，无复制。6249/16CPU节点20实际新增7PASS/0.75秒，主/batch/extern C0。两个原生S索引生成入口另补峰值/inode预检与写入期CheckedWriter，已有文件不覆盖，空间不足保留partial；6250首次4PASS/1失败为新fixture未跨8MiB检查边界，修正后仅失败项6251首次PASS/0.07秒/C0，其余不重跑，仓库检查PASS/errors=[]。新增逻辑累计122项，既有完整回归3368PASS/3旧条件skip保留。窗口二缓存6187继续，D6未交付；P模板仍待其实际根路径，沿用原S24万MID/6M，不提前训练、不新增ACK或数据QA/hash/收据，不动其他窗口作业。


2026-11-08 窗口一共享存储预算更新：M2诊断输出仍在 `/lfshome/zixiao/model_v31_20261105` 的全节点100,000,000,000B总峰值预测内，并非各节点另加100GB。两项E2关闭后，6332实际节点20准入已统计模型占用447,689,216B（已进入quota used），剩余模型未来预测99,552,310,784B；后续新观察器继续按同一共享目录实际物理块数扣已占用，避免重复预留。其他窗口可据这一总峰值/已占用口径更新自身并发未来预算，原账户100GB、8GiB突发及根盘max(10GiB,10%)不变，无旧产物删除/迁移或新数据副本。本条仅磁盘协调，不是诊断字段/标签侧通知，无模型ACK等待门。

2026-11-08 窗口一预算修正：模型全局100GB总峰值继续不变；实际物理占用现递归统计M2_DIAG_*子目录，并按(st_dev,st_ino)去重，纳入唯一完整回归的Lustre临时文件。16:13已分配2,338,340,864B、模型剩余未来97,661,659,136B；这些物理块已在quota used，不应再重复预留。原一层统计遗漏嵌套文件曾触发自有作业保护暂停，实际节点重新准入后只替换自有观察器并CONT原进程，未重跑训练、未删除文件、未降低账户100GB/8GiB突发或根盘底线。本条仅资源协调，不是标签通知。


2026-11-08 窗口一共享峰值最新点：唯一完整回归和fixture恢复已关闭；当前自有观察器记录Lustre模型实际已占用 12082143232 B、剩余未来预测 87917856768 B，两者合计仍为全节点100GB总峰值。这些检查点/回归临时文件已在quota used，其他窗口并发预算可按同一递归物理块去重口径扣除已占用部分（tools/model_v3/v2_diagnosis_disk.py:model_growth_forecast；实时值见runs/model_v31_20261105/M2_controlled_4526360.state.json），不另加每节点100GB，也不重复预留全部100GB。原账户/根盘底线保持，无清理/迁移、无标签待查通知。


### 2026-11-08 窗口一 M2诊断完成：仅交接6个标签侧待查字段

固定原4526238的1000MID/同一构象、D3v3.1、原D4/掩码；E2两组30k、E3六家族10k及E4六家族30k全部关闭，最终133行归因已生成。只有下列6项在完整E4后仍R²<.95且修正提案亦未达标；此结论只针对有限探针配方，不判定标签错误。62项未解决（含11项E4已可学）及1项多任务干扰不交给数据线作标签归因。

完整交接文件：`/lfshome/zixiao/model_v31_20261105/M2_DIAG_FINAL_20261108/label_side_residual_top20.json`，6字段×20分子=120条；每条含原MID/构象、原始标签、预测、原掩码及需要时的pair索引，缺失用null并保留掩码。原始数值数组留服务器，不进入Git。下表均为该文件对应`fields[字段][0]`的第一条真实残差样例；其余19条在同一字段数组中，无需复制数据。

| 字段 | E4 R² | 第一条残差MID | 原构象索引 | 分子RMSE |
| --- | ---: | --- | ---: | ---: |
| P.pm7_B.r73.value.pi | 0.846165 | principal_00116939 | 4 | 0.340480149 |
| D20.BertzCT | 0.736512 | principal_00863628 | 3 | 2079.478516 |
| P.pm7_anion.r196.z | 0.747962 | principal_00573159 | 8 | 18.940844 |
| P.pm7_B.r58.value | 0.000035942 | molecule_02607283 | 3 | 3.238187 |
| D3.PMI3 | 0.910939 | principal_00863628 | 3 | 76474.671875 |
| D3.PMI2 | 0.899493 | principal_00863628 | 3 | 76501.046875 |

最终归因CSV：`/lfshome/zixiao/model_v31_20261105/M2_DIAG_FINAL_20261108/attribution.csv`（133行）；一页报告和唯一交付清单在模型仓库`docs/model_v3/M2_OVERFIT_DIAGNOSIS.md`及`M2_OVERFIT_DIAGNOSIS_DELIVERY.json`。所有字段照常参与M3，修正判据未获批准/未用于正式验收；原S结果和M3模板不变。D6作业4526311此时RUNNING，正式原S240k P/D入口17:09仍NOT_READY/root=null；待窗口二原末尾检查/压实和自动发布，不增加复核或模型ACK等待门。



### 2026-11-08 窗口一 M3 P候选已依赖正式D6入队

M2诊断14个受控运行及最终133字段归因已闭合并推送。P条件C1-0/C1-a/C1-b的实际作业4526376/4526377/4526378均依赖afterok:4526311，当前PENDING/0更新，分别用Node21两张5090和Node20的GPU-ec788...4090；未占用yu的GPU-8bfd...。仅在窗口二正式原S240k绑定READY后，在启动时给原模板绑定root；原24万MID、D4/视图、6M样本及所有科学参数不变，无新扫描/数值QA、数据副本或模型ACK门。若窗口二将D6替换为新jobID，请沿用共享STATUS公布实际续接；模型线仅更新自有未启动任务的依赖。

模型全局100GB总峰值不变，登记未来P输出的物理占用与M2输出一起去重扣除；D6正式split_roots+molecules发布后，其NFS93,589,934,592B才视为已进入used、从未来预算退役，其余并发23,179,869,184B及账户/根盘底线保持。7项M3启动新单测6373 C0/0.44秒，仓库检查PASS，正式输入未发布时不会训练。执行计划见模型仓库configs/model_v3/published_pd_queue.json。


## 2026-11-10 窗口一：消费正式D6并续接M3 P候选

已消费窗口二22:40的D6正式交付4529073 C0及原S240k READY绑定。原240000分子/顺序、D4/训练视图、6M样本及科学配方保持。三个自有未启动候选4526376/4526377/4526378原依赖失败4526311，本次仅清除失效依赖，原作业均已RUNNING；分别C1-0/C1-a/node21两张5090、C1-b/node20的GPU-ec788...4090。原开发评价6381/6382/6383继续afterok绑定相应训练，使用原18格TRAIN内层面板，不读下游TEST。M2及诊断不重做，未提前选择联合胜者。

直接读取manifest.split_roots的共享TRAIN/FULL，不复制LMDB或另建24万库、不做新数值QA/hash/ACK门。实际目标节点字节/inode及新鲜native quota启动检查通过，持续磁盘保护已运行；正式D6未来占位退役，既有used不释放，模型全局100GB及其他并发/账户/根盘底线保持。后续按既定C1补种子→视图/头/池化→配方/B*→冻结推进，无待用户决定。

## 2026-11-10 窗口一：用户批准的P微批8续跑已接入

原P三候选4526376/6377/6378已各从483264实际样本切换至480000完整检查点，每组实际重放3264；原日志/检查点及同盘硬链接均保留。新训练4529096/9097/9098均RUNNING，使用原node21两GPU及node20的GPU-ec788...；新18格TRAIN评价4529099/9100/9101分别afterok绑定。准备任务4529103再依赖三项评价，原未启动4529082因更改依赖后JobHeldAdmin无法release，已仅取消该自有未启动任务并用相同脚本/输入/资源替换。原Held4526030未动。

有效B32、模型/优化器/RNG、D6原240k人口/顺序、D4/字段/掩码/构象规则及累计6M预算保持，尚无P最终分数或联合C1选择。CSV旧行保留实际工作，新行仅记恢复点后新增工作。新增输出纳入原全局100GB预测并按inode去重，不另留第二份100GB；启动时实际节点字节/inode、新鲜native quota、GPU上下文及UUID锁均通过。数据线结果、其他窗口预算和其他用户GPU均未改动。

## 2026-11-10 窗口一：micro32/B32与每10万样本W&B

用户批准当前三组P从最新完整544000/544000/608000继续micro32、B32；新训练4529108/9109/9110、新开发9111/9112/9113，准备9103依赖已先原地更新，随后取消旧自有未启动评价。旧micro8实际574624/550656/611232，重放30624/6656/3232计成本；所有文件/历史冻结保留，数据/科学目标保持。真实W&B CPU侧记录4529106已接入，历史导入标记、每实际执行独立run，每100000样本轻量快照推GitHub。原凭据API AuthenticationError，当前OFFLINE_UNSYNCED，已请求终端安全重登；不将本地SDK当云端已同步。原始SDK/数据/权重不进Git，全模型100GB一次预算含新增根，真实节点磁盘保护保留。

## 2026-11-10 窗口一：node21保护暂停恢复及实时状态修正

09:16模型训练4529108/9109因NFS账号配额快照future/stale被原保护STOP；sacct延迟仍显示RUNNING，scontrol确认STOPPED。两目标的实际根盘/输出盘字节与inode、并发预算及native quota重新核验通过后CONT原进程，样本已恢复增长。捕获原完整原因：runs/model_v31_20261105/M3_micro32_disk_pause_1794273383.json。模型观察器改优先控制器并核对UID1278，联读磁盘保护状态；5项定向回归通过。原容量/新鲜度底线与全模型100GB一次预测持续执行；模型/AdamW/RNG、数据/字段/掩码、B32/6M科学目标保持。其他窗口任务与数据未调整。

## 2026-11-10 模型线：训练系统指标与1000更新平均损失已接入

新增独立CPU记录4529240（compute-0-20，4CPU），原4529106逐步损失记录继续。实际训练4529108/4529109/4529110均已在真实W&B SDK中保存GPU功率、利用率、显存、温度/时钟、主进程CPU/RSS/I/O、节点余量与区间吞吐，以及连续1000优化器更新的总/分项均值和有效条数；配对run与原训练job/group/UUID明确关联。约30秒采样，新10万样本GitHub点附独立观测时间/样本数，整卡功率明确标注。定向18PASS/0.09秒，原生记录已核实；见模型仓库docs/model_v3/WANDB_TRAINING_DIAGNOSTICS.md。目录仍在既有WANDB_20261110根，计入原全模型单次100GB预测和实际字节/inode/native quota保护。用户重登后API仍HTTP403/HTML，当前离线；已请求CLI --verify安全验证。训练科学配方保持。中午node21两组文件页I/O等待后原进程吞吐恢复，未重启/回退。

## 2026-11-10 模型线：按用户决定改为GitHub报告交付

用户明确选择继续离线W&B、停止云端认证排查，训练完成后上传完整W&B离线运行文件。当前新增results/model_v3_wandb/report/LATEST.md及training_curves.svg，随每10万累计样本点更新中文进度/1000步总与分项均值及有效数，并绘制平均损失、GPU利用率、显存、整卡功率四面板。图表读取已产生的诊断JSONL，保留独立执行和时间/样本时钟，缺测与长间隔断线。相关定向21PASS/0.11秒；实际首图已渲染检查。记录仍为4529106与4529240，训练科学规则保持；完整SDK待实际执行和SDK结束后归档上传，原文件保留。图表/cache/预览写入前在实际node20复核字节/inode/native quota，沿用原全模型单次100GB预测与NFS元数据余量。


## 2026-11-11 模型线：C1-b完整6M已闭合，node21原进程恢复

P/C1-b训练4529110及18格TRAIN开发评价4529113均实际COMPLETED/0:0，累计6000000样本，开发汇总0.20315388182067007；只用train/train_inner_validation，尚不选择联合C1。其逐步W&B与配对诊断run均正常finished，完整离线归档待上传。node21的4529108/9109因NFS quota快照future/stale保护STOP，本日实际节点字节/inode、并发预测及native quota准入通过后CONT原进程，Restarts=0且样本已增长。新增持久元数据恢复协调器仅监控这两组：原guard须DISK_PAUSED，UID/节点/完整命令/Restarts匹配，并在实际节点通过原完整容量检查、再复查STOPPED后才CONT；10项控制单测PASS/0.07秒。全局模型100GB一次预测、原容量底线与全部科学输入/配方保持，其他窗口作业和数据未改动。客户端断连期间积累的10万样本报告正在补推，原始SDK继续保留。

### 2026-11-11 模型线：P/C1-b 完整离线 W&B 已交付

P/C1-b seed0 的4526378→4529098→4529110三个实际训练执行及配对诊断共六个SDK run均已关闭，完整110个原始普通文件已上传 https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111 ，压缩30,209,948字节，附文件清单与合并解压命令。原文件保留；其余两组训练及原容量保护继续，无标签/划分/科学配方修改。

### 2026-11-11 模型线：P/C1-a 6M与TRAIN开发评价完成

训练4529109、开发4529112均COMPLETED/0:0；累计6M/187500更新、原18格TRAIN汇总0.25992266173725326，只使用train/train_inner_validation。该micro32执行新增5456000样本/170500更新。三个实际训练分段及配对诊断共六个SDK run完整110文件已追加至 https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/P_C1_a_seed0 （压缩30929928字节），原文件保留。C1-0仍训练，尚未联合排名/冻结；此前未执行的C1-a迁移现已无需执行。根巡检按用户要求为30分钟，原记录/磁盘保护继续，无标签/科学配方修改。


### 2026-11-11 模型线：空闲GPU推进原必需任务

原三组P seed0均已6M；0的开发因同卡外部进程未启动，替代4529708在node6等a验证9706后运行，完整C1准备4529710随后读取六组原结果。数学上必在前二的C1-a提前运行S/P seed1：4529691/node5/3090与4529704/node22/5090，已有真实优化更新，原科学配方/有效B32/6M保持。node6推进原FULL与TRAIN未见构象独立诊断（a9706→dev0 9708→b9709），不用于选择。新节点实际磁盘字节/inode/native quota已核实，根盘保留max(10GiB,10%)，全部窗口共用原峰值预测，无数据复制/旧文件删除；用户要求根巡检每30分钟，训练及保护持续。


### 2026-11-11 模型线：初始C1完整结果与首组双人口验证

P0替代开发4529708真实C0，三组P seed0训练/18格TRAIN开发均完成。S/P等权初始前二为a(0.2601907066)/0(0.2421121645)，b为0.2255957873；最终C1/SD待实际seed1。a的S/P9691/9704在node5/22真实训练；0的S/P9711/9713及开发9712/9714已在node6当前b验证后接好，有其他空闲卡则改派未启动任务；原科学配方保持。P/a验证9706 C0：FULL13815分子/126764构象、TRAIN留出4292/4292，原始97损失头/109源列指标已交付，selection_use=false。仅六个关闭JSON的汇总准备9710因node20不可调度而PENDING零运行取消，相同短元数据命令已在指定compute20完成，不作Slurm C0声明。全部输出仍共用原100GB峰值预测与实际磁盘/配额保护，无数据复制/旧文件删除。模型源/results与M3_C1_RESULTS.md已更新，最后冻结仍等待M3/M4。


### 2026-11-11 12:40 模型线：用户暂停补种子，等待通知

用户明确要求“先不要做补种子任务了，等待通知”。已核实并暂停3个运行中自有补种子作业9691/9704/9711，控制器均STOPPED；5个尚未开始的补种子/开发9693/9705/9712/9713/9714均PENDING JobHeldUser。Slurm suspend权限拒绝后以精确UID/节点/作业的STOP信号暂停原进程，未取消/重启/回退。已将补种子从自动磁盘恢复登记移出，已有状态/检查点/结果保留，等待新明确通知后继续。


### 2026-11-11 模型线：任务书v3接续，取消选型补种子

根《模型线任务书v3：C1收尾、读出扩展与分子潜变量模块》现取代v2未执行部分。已scancel全部8个9691/9693/9704/9705/9711/9712/9713/9714，实际均CANCELLED by1278；日志/检查点原样保留。P/b验证9709已COMPLETED/0:0。后续仅seed0，先在任何新分数产生前提交新判据和dev_panel_v2.json，再用R2/R3重评6个现有C1检查点，Lite模块及指定数学验收与评价并行。成员/标签/D4/原划分不变，原18格不重算，v2种子SD判据退役。固定3倍GPU估计才停问用户，1.5倍只报告；原真实磁盘/并发/native quota保护继续，新缓存仍纳入同一全模型峰值，不复制数据/删除旧文件。完整日程见DEVELOPMENT_SCHEDULE.md；缺失研究主线文件及T0计数歧义已向用户询问，独立工作继续。


## 2026-11-11 模型线v3进展

已按v3取消8个补种子作业，原文件全部保留。dev_panel_v2及新单种子判据在首分前提交；7个R2/R3评价正常闭合。C1选定0（S/P等权R3=0.34630315；对第二名b的Δ=0.29821048，95%CI[0.23203856,0.36017167]），不追加排名差异分析。结果为results/model_v3_c1_final.json及docs/model_v3/M3_C1_RESULTS.md。原标签、D4、240k成员与TRAIN内层不变，无TEST。

Lite核心3项指定数学性质已通过；用户确认T0共4组、标量头接z且矢量保留原等变路径。T0四组/T1十组均已提交（S4529723–29，P4529730–36）；当前先运行S的两组T0，5/6各一张3090，余组按依赖交错推进。22由其他用户GPU作业占用，不改其作业。真实SDK离线记录、原磁盘/配额保护、同一全模型100GB峰值预测继续；根监控1800秒，不改变SDK30秒系统采样。仅完成C1/模块核心和接线，未作模块采用或全线冻结结论。

### 2026-11-11 17:33 模型线：T0四组闭合，进入T1

T0-3/T0-4各S/P四组均已完成0.5M训练和v2冻结评价，全部COMPLETED/0:0；分数见results/model_v3_t0.json及M3_T0_RESULTS.md，仅报告不作采用门槛。T0-2四统计量仍在CPU20排队，不冒称整个第0层全部完成。T1已在5/6各一3090开始A0/S与A1/S，其余按原配对依赖推进；仍从相同原6M检查点续训1.5M、seed0/B32及原标签/D4/抽样RNG。分子标量接z、矢量保留原等变路径。

真实离线SDK和1000步均值/30秒系统指标继续，10万边界累计207点。新闭合SDK归档等待CPU20（实际104/104核占用）；原P的330文件已在归档分支交付。新代码已准备条件性从0的6M确认、六组只报告微调、后续联合及原生S配方入口和配对判定，未提前选择或启动依赖结果的运行。根检查1800秒、同一全模型峰值预测和实际节点磁盘/inode/native quota保护不变；无数据复制、删除、TEST或付费/正式预训练。

### 2026-11-11 磁盘通知：compute-0-0 暂不准入（模型线实测）

MODEL_NODE0_ROOT_RESERVE_20261111T1017：空闲3090所在compute-0-0根文件系统共75,125,227,520B，可用仅3,684,593,664B（96%已用），低于max(10GiB,10%)=10,737,418,240B底线。共享Lustre/NFS可用不替代根盘余量。本次在只读预检处拒绝，未提交该节点模型任务、未复制/缓存数据、未删除任何文件或改管理员配置。请各窗口继续遵守现有磁盘规则；该节点只有真实根盘余量恢复且重新通过实际目标文件系统/并发/native quota准入后才可新增任务输出。原5/6训练继续，科学配方不变。


### 2026-11-12 模型线：T1进度与机制输入接口

MODEL_V3_MECHANISM_INPUTS_20261112：C1已选0，T0四组训练/评价及T1 A0/S、A1/S续训/评价均已闭合；T0-2仍在node20排队。03:34 CST两组P在node5/6各268736/264320阶段样本（预算1.5M，原6M偏移），同为seed0/B32、原标签/D4/抽样。100k报告本次累计241点；本日新闭合SDK包25会话、321普通文件、54分段，原P三包330文件保留。

T1机制分析入口已实现但尚缺任务书所指“数据线已有的28类固定SMARTS”的原始定义及开发面板TRAIN成员到带键分子/SMILES的对应。消费接口见模型仓库docs/model_v3/MECHANISM_ANALYSIS.md：定义保持原28个id/SMARTS和顺序、来源；结构映射保留dataset_id/member_index/member_uid/full_inchikey、原TRAIN角色与SMILES。原始定义和对应路径尚未交付到本模型窗口，不用通用RDKit描述符替换，不从坐标推断键。此项selection_use=false，不阻塞T1采用及后续主线；不要求重算已交付标签、D4、去污染或数值QA。

node0旧试点本地副本34.94GB的删除提案已交用户，尚无批准、未删除；共享试点原件和正式D6保持。node0根盘仍低于保护线，当前只用5/6；实际磁盘/inode/native quota、原全局峰值保护与1800秒根巡检继续。


### 2026-11-12 node0 根盘恢复与第三张模型开发卡接入

MODEL_NODE0_ROOT_RESERVE_RECOVERED_20261112：用户明确批准仅清理compute-0-0的`/tmp/D3_v31_pilot_20261105_v1`。重新核对实际节点、UID1278、精确7个普通文件、无打开句柄及独立共享原件后，已删除该本地副本7文件/3目录，释放34,937,044,992B；根盘可用由3,684,085,760B升至38,621,130,752B，超过10,737,418,240B底线。共享试点原件、正式D6及模型日志/检查点保留；此前node0不准入通知现由本条实际恢复记录补充。

已在实际node0重新核实根盘/共享目标字节与inode、native quota、全部并发与模型全局峰值、MemAvailable、GPU UUID及公共锁；未复制数据。A2/S→评价→A2/P→评价新链为4530010→4530011→4530012→4530013，仍用原1.5M、seed0、有效B32、原6M检查点与既定科学配置。旧4529727/4529743/4529734/4529750核实零运行后取消，实际均CANCELLED/00:00:00；node5的A4/S改接既有A0/P评价4529748，node6原链继续。

00:03 UTC（08:03 CST）首次真实A2/S已8704样本/272更新，loss0.311022、rec0，守护OBSERVING；0/5/6各一张3090分别运行A2/S、A0/P、A1/P。恢复协调器已登记41项；根巡检1800秒和原磁盘/配额保护继续。该清理授权仅覆盖上述node0旧副本，其他节点副本保持原权限与审批范围。

### 2026-11-13 P任务D6(d)科学停止，等待用户决定

新P任务已经开始，旧任务仍不恢复。P任务D6(d)一次实际身份比较发现323个TRAIN/下游重叠分子，其中16个完整InChIKey精确重叠、307个仅既有WP5结构键重叠；按任务书9.3停止。新P训练未启动；六个未完成P任务评价作业已取消，结果保留。不得自行恢复P任务或调整TRAIN/D4，等待用户明确处理决定。结果见X:/MFM_p_recipe/docs/p_recipe/daily/2026-11-13.md及runs/p_recipe_20261113/D6_identity.json。独立PR6、数据线和PubChem未取消。
### 2026-11-13 P任务：用户批准排除重叠后继续

用户已明确批准排除323个重叠分子并修正受影响TRAIN/D4；此前P任务9.3等待已解除。P专用派生TRAIN为1194228分子，原D6/标签/旧D4均保留。D4修订4530455在node20排队，F64缓存及原统计数值方法保持，最终参数使用独立路径；历史C1读出重算和P0表示谱已恢复/提交。未启动新P预训练，旧模型开发任务不恢复，独立PR6及其他数据任务不改动。详情MFM_p_recipe/docs/p_recipe/daily/2026-11-13.md。
### 2026-11-13 用户新规则：20–22 显存≤30%时直接 SSH 启动

用户明确授权：compute-0-20/21/22 被其他用户的小显存任务占用时，登录实际节点按目标 GPU UUID 核实 memory.used/memory.total；≤30%（含30%）则直接 SSH 启动自有任务，无需 sbatch，不再因 Slurm 节点已分配或外来 CUDA 上下文而阻止。>30% 或未知不据此启动。不操作其他用户进程；记录真实原生 PID/start_ticks/PGID/exit，不伪造 Slurm 身份；实际磁盘、inode、账户 quota 和并发峰值保护继续。全局技能 huagong_hpc_requirement 已更新至1.0.149，旧冲突规则在上述范围被覆盖。

P 任务 goal 同时更新：统一增大 P 训练的实际整批 batch，按全部12卡显存和实际 P 前反向峰值确定公共取值并修改任务书/配置；323个重叠分子排除及受影响TRAIN/D4修订继续。旧模型开发任务保持终止。

## 2026-11-13 P线用户最新决定：所有后续训练B128

用户在完成不同batch测量后明确选择128，以尽量快并保留OOM余量；本线全部后续P筛选/确认/P′/分子数运行固定batch_size=microbatch_size=128，不再自动放大到160或其他值。任务书、base/protocol与全局HPC技能1.0.150已同步；历史测量保留，评价探针保持任务书冻结的32。尚无新P预训练运行需要迁移；D4原生修正继续，其他工作线任务不改。
## 2026-11-13 P研究D4并行节点临时盘预留

P′独立D4将用compute-0-20的/tmp/zixiao_p_recipe_D4_Pprime_20261113（4workers、nice10），本窗预留未来120000000000字节、根盘系统保留95415907123字节；实际根盘可用275950137344字节、inode464398629，内存可用约116GB，目标GPU仅441/49140MiB且CPU-only不占CUDA。原PM7 D4继续node21、同窗未来120GB；两者是不同节点本地文件系统，统计源共享只读，最终小参数才写入P专用D4_REPAIRED目录。其他窗口不得重复拿这两份本地空间作未来预算；原始数据/旧D4/已有scratch不删除。发布后同数据集入口复用已闭合参数，避免原串行父任务重复计算P′；加独立数据集锁，科学算法/顺序/掩码不改。
## 2026-11-13 P研究检查点固定留存/共享写入预算

新P训练每500k样本保存独立samples_<n>.pt，保留全部已有点，不使用滚动恢复点覆盖；最多16条筛选×3点+7条确认×9点=111份，以每份300MB及6份并发临时文件估算新增约35.1GB。P阶段共享输出总预测改为45GB（包含已写P缓存），全模型峰值98569896448字节，独立PR6的8GB预留保持。compute-0-20实际预检：模型已分配50900611072B，全局剩余47669285376B；Lustre quota可用179904507904B/需要162259219968B，NFS可用143451877376B/需要131836912640B。100GB账户安全余量及全部节点磁盘/inode保护保持。根盘两个D4节点各120GB是独立本地文件系统预算，不加入共享输出重复计数。所有后续训练仍固定B128。
2026-11-13 08:03UTC P-recipe resource update: node21 P_D D4 resumes its original logical-group checkpoints with 16 CPU workers (was8), nice10. Actual104 CPUs/51%idle/65.6GB MemAvailable; root702.42GB free, system reserve95.42GB, total scratch peak forecast raised120->160GB including retained attempts. node20 Pprime4 workers/scratch120GB unchanged. No other users' processes changed; P training remains fixed B128.

2026-11-13 09:05UTC P-recipe CPU continuation: node20 Pprime D4 increases4->16 workers/nice10 using the same group checkpoints and scratch. Measured104 logical CPUs/28%idle/74.03GB MemAvailable; current four-worker maxRSS2.78GB, estimated incremental RSS~38GB leaves>20GB system RAM margin. Target GPU6345/49140MiB<=30%, CPU-only/noCUDA. Actual root275930087424B free, inode464398339; existing local peak forecast120GB/system reserve95.42GB unchanged. node21 PM7 remains16 workers/scratch forecast160GB. Other users' processes untouched; all new P training B128.

2026-11-13 13:14UTC P-recipe readiness: reuse the existing publisher's separation of closed element-reference/exact-tail/moment parameters from pending MAD diagnostics. The study adds guarded one-shot TRAINING_READY exports and training_routes.json (training_normalizations_complete=true, D4_complete=false while MAD pending). P0/label fits can start after these parameter stages close; MAD continues on existing16-worker producers. Metadata waiters replaced at a verified no-launch boundary:3792435/3792436; D4 producers3628047/3336857 unchanged. Existing local160/120GB scratch forecasts,45GB P shared output peak and fixed B128 remain. No new P model training started.

## 2026-11-14 P研究最新执行规则与D4预算解除

用户已明确停止本次D4重算；323个分子仅从P专用TRAIN分子清单剔除（1194228分子）。整个P研究固定使用数据线window2_TRAIN_normalization_parameters_20261107_v1/routes.json，中途不切换；A1/A2自身变换仍在TRAIN拟合。旧D4生产者及等待器已按真实绑定身份停止，真实exit -15保留；经所有权与依赖核实，已清除本窗node21/node20独立D4 scratch共11249文件、178381381632已分配字节。原node21 160GB/node20 120GB本地D4峰值预留解除，共享P检查点45GB及系统/Slurm余量规则继续。

空闲且满足当前准入条件的GPU优先顺序固定5090 > 4090 > 3090；新任务按此分配。20–22仍按实际UUID显存占用<=30%直接SSH，不使用sbatch、不操作其他用户进程；后续P训练固定B128/micro128。全局HPC技能已更新1.0.152。

P0 D1、D3已真实exit0，D2与A1/A2拟合已启动；第一轮B0/3090作业4532406、A3/5090 PID3633440、A4/4090 PID3346967均已进入实际训练。B0早于最新优先级启动，继续原运行；后续臂按新优先级分配。第一轮按卡型的实测B128吞吐及整卡功耗见P日报2026-11-14与results/p_recipe/training/round1_B128_initial_throughput_power.csv。旧模型开发线仍终止，其他窗口任务不改动。

2026-11-13 20:10UTC（11-14 04:10CST） P研究A1/A2各128000 TRAIN分子拟合已真实exit0，A1为11字段/A2为30字段；自动按5090>4090>3090将A1加入node21 GPU-c35f2434/PID3634326，将A2加入node20 GPU-8bfd2ba3/PID3348062，准入15.20%/2.63%，原生运行/B128/固定11-07基础参数。两卡已有自有UUID锁；其他用户任务不改。首轮B0/A1/A2/A3/A4均已启动，A5仍依D2；20:23UTC统一定期查询。

2026-11-13 20:28UTC P研究真实OOM与修复：首轮B0/3090作业4532406、A3/5090 PID3633440均在50944样本后发生距离偏置CUDA OOM，真实失败配置/输出/日志保留。继续实际B128/micro128，后续启用已有逐层非重入激活重计算；A4/A1/A2尚未失败继续原尝试。B0_attempt2已在node21 GPU-22e21021/PID3635058启动，A3_attempt2为node5 GPU-dac07d74/Slurm4532408 RUNNING，符合空闲5090>4090>3090顺序；其他用户进程不改。04:23累计训练GPU墙钟1.7614h（含失败0.7390h）、D1/D2诊断0.8095h；D2为37/50，A5仍等待真实判定。下一次统一20:53UTC。

## 2026-11-14 用户最新OOM批量规则

用户明确允许OOM时适当缩小BS至96或64。P训练默认128；实际OOM后的后续尝试先用batch_size=microbatch_size=96，仍OOM再用64，不再受旧“始终固定128”限制；在既有4小时修复盒内执行该OOM降批顺序，其他失败沿用任务书规则。已经正常推进的尝试继续，降批后不自动放大。保留总样本预算、按样本计的学习率、种子、数据与归一化参数，并记录每次尝试实际BS、卡型、样本/秒、功耗及真实退出。已有逐层激活重计算可继续使用；评价探针仍32。空闲GPU优先级5090>4090>3090及显存<=30%直接SSH规则不变。

2026-11-13 20:36UTC P0已闭合：D2真实exit0（6400分子，3物理头53.964%梯度能量、前1%分子51.830%），触发A5，node22 CPU拟合PID80229已90112/128000，GPU不占用；P0_SUMMARY一次交付。A1原运行也实际OOM/exit1，旧输出保留；第二次运行已启动node21 GPU-c35f2434/PID3635649，已有B128更新。用户最新允许OOM后96→64，规则已同步；当前正常尝试继续。下一次统一查询20:53UTC。

2026-11-13 20:39UTC P研究A5拟合真实exit0（128000 TRAIN分子/5变换字段/CPU164.06秒），A1/A2/A5三份参数原样导出configs/p_recipe/label_parameters共58956字节。A5已启动node22/5090 GPU-9b6008d0，PID80467/UID1278/start_ticks23970538/PGID80467，已有6016样本B128更新；首轮六臂均已启动。新OOM规则允许96→64，现有正常尝试继续。P0全部闭合；下一次模型统一查询20:53UTC。

2026-11-13 20:53UTC P研究定期查询：首轮六臂真实RUNNING，B0/A3重试已越过原OOM批次；全部实际B128，后续OOM授权96→64。当前UUID自有锁保持（node21两5090、node20两4090、node22一5090、node5一3090），不能仅因小显存就重复自有任务。训练GPU墙钟4.4052h（含失败1.1094h），D1/D2诊断0.9774h；不新增磁盘预算，45GB P/98.57GB模型峰值及真实磁盘保护继续。A4首1000步裁剪99.9%仅报告、固定阈值不改；暂无组件采纳。下次21:23UTC。

2026-11-13 21:01UTC 用户继续P研究后实际复核：首轮六臂原句柄均RUNNING，原生PID/start_ticks/PGID及Slurm句柄保持；A1重试也已通过原OOM批次，三条重试未再OOM，当前全部B128，无需降批或重启正常进程。A2首1000步裁剪100%、A4此前99.9%，只报告不改固定阈值。训练GPU墙钟5.1950h（含失败1.1094h）、D1/D2诊断0.9774h；资源预算不新增，下一次统一21:23UTC。

2026-11-13 21:24UTC P研究定期查询：首轮六臂均真实RUNNING，样本B0/A1/A2/A3/A4/A5=117376/98944/195584/131840/213632/200576，当前全部B128，未新增OOM；原句柄与UUID自有锁保持。训练GPU墙钟7.4200h（含失败1.1094h），D1/D2诊断0.9774h。已有累计裁剪记录A2/A3/A4/A5为100%/87.2%/99.9%/92%，仅报告不改阈值。P共享45GB/全模型98.57GB峰值不变，不新增数据/检查点外副本。下次21:54UTC。

2026-11-14 P线A5/node22改sbatch：已提交4532409节点独占申请，真实PENDING(Resources)，GPU GRES当前未配置，普通sbatch不能锁GPU；独占/普通模式正在等用户选择。原生A5 PID80467继续，未停止或更改其他CPU/GPU作业；到分配和完整检查点就绪才交接，不重复训练。user-only共享GPU锁与node20/21现有SSH规则继续。05:48只读采样证实node21两个gmx均有约53% SM利用率，显存小不等于计算负载小；node22卡只见本A5。06:08六臂仍RUNNING，下一次06:38。

## 2026-11-14 06:54CST · P线混合调度规则/旧A5迁移失败已如实修复

用户最新要求：后续禁止exclusive，只申请所需CPU；compute-0-20/21/22剩余CPU足够且显存准入时走普通sbatch，CPU不足但GPU空闲/占用≤30%且显存足够时SSH先跑，同时提交同任务sbatch接管。排到后由原训练在完整更新后保存状态并主动退出，新job从该点恢复，不能双跑。配置MFM_p_recipe/configs/p_recipe/scheduling.json，协议docs/p_recipe/HYBRID_SCHEDULING.md；技能1.0.155及共享AGENTS已更新。新保存使用临时文件+原子发布+回执，完整恢复模型/优化器/采样游标/RNG；7项定向测试通过（包括真实CPU子进程退出交接及精确续训），未重跑全量回归/基准。全局P磁盘预测57GB覆盖额外断点，不按节点重复预留；已在node20核实bytes/inode/quota，其他线预算不动。

原A5迁移发生协调失误：旧代码直接写最终文件，500k检查点写完前被结束，仅76156928字节且不可读，损失约2.045GPUh。原件/日志保留；旧原生PID80467真实-15，4532409/4532410已取消且均未运行训练。A5以相同配方/B128在node22普通16CPU作业4532411从初始化重试，实际已训练，未标为成功断点接续。其余五条训练与其他用户任务保持运行。PR7持续草稿，当前仍首轮六臂，尚无R3筛选结论。

## 2026-11-14 07:23CST · P首轮定期查询

2026-11-13 23:23UTC实际句柄查询：六臂均RUNNING，无观测错误及新OOM；B0 369024；A1 341504；A2 499456；A3 416256；A4 497920；A5 169856，各目标1.5M。当前全部B128。A3真实Slurm4532408，A5为node22普通16CPU作业4532411（同配方从初始化重试）；其他四臂原生进程继续。统计窗口吞吐/整卡功耗和累计裁剪率已更新同日日报及小CSV；训练GPU墙钟19.3422h，含失败3.1543h；D1/D2诊断0.9774h单列。无新筛选结论，不改配方或裁剪阈值；下一次2026-11-13 23:53:39 UTC。全P目标继续，旧模型任务及其他工作线不改动。



## 2026-11-14 07:53CST · P首轮定期查询

23:53UTC实查六个当前训练句柄均RUNNING，无观测错误或新OOM。B0/A1/A2/A3/A4/A5样本438400/407552/574240/486528/568352/297216，各预算1.5M，全部实际B128。A2/A4已通过500k验证/保存边界并继续推进；A5重试真实Slurm4532411继续。当前训练GPU墙钟22.3521h，含失败3.1543h；D1/D2诊断0.9774h另列。累计裁剪率按任务书报告，固定阈值不变。日报及实测吞吐/整卡功耗CSV已更新，无筛选结论；下一次2026-11-14 00:23:45 UTC。完整P目标继续，其他用户及工作线不变。



## 2026-11-14 08:23CST · P首轮定期查询

00:23UTC真实句柄/会计查询六臂均RUNNING，无新OOM或观测错误；B0/A1/A2/A3/A4/A5样本518816/482816/647968/557344/635296/428288，均实际B128。B0/A3已通过首500k验证及检查点边界，A2/A4继续第二段，A1接近首500k。A3真实Slurm4532408、A5重试4532411，其余四个已绑定原生进程继续。训练GPU墙钟25.3634h，含失败3.1543h；D1/D2诊断另计0.9774h。A2累计5000步裁剪100%仍仅报告，固定阈值不变；其他裁剪/吞吐/整卡功耗在日报CSV。无筛选结论；下一次2026-11-14 00:53:51 UTC，完整P目标继续。



## 2026-11-14 08:53CST · P首轮全部通过500k边界

00:53UTC实查六臂均RUNNING，无新OOM及观测错误。B0/A1/A2/A3/A4/A5样本607776/558112/724512/627232/707232/502560，各预算1.5M、实际B128；A1及Slurm4532411中的A5重试均已通过首500k固定VAL/保存边界并继续更新，六臂现在均超过500k。A3仍为4532408，其余四臂自有原生句柄继续。训练GPU墙钟28.3743h（含失败3.1543h），D1/D2诊断0.9774h另计。裁剪比例仅报告、阈值不变；当前不按中途VAL做选择。新增A1/A5原单位VAL CSV、日报及吞吐/功耗实测表已更新，尚无完整1.5M R3结论；下一次2026-11-14 01:23:58 UTC，完整P研究继续。



## 2026-11-14 09:24–09:26CST · P首轮查询/实际GPU共享变化

01:24UTC实查六臂仍RUNNING、无OOM及观测错误。B0/A1/A2/A3/A4/A5样本696096/632352/794912/698784/778528/579232，全部B128。训练GPU墙钟31.3852h，含失败3.1543h；D1/D2诊断0.9774h另计。A5阶段吞吐下降后作一次5秒只读资源检查：node22出现其他用户yu的gmx PID86271，仅672MiB显存，但pmon SM样本42/38/23/79/45%，平均45.4%；本任务PID83400为54/50/70/12/49%，平均47.0%。当前无GPU GRES，普通16CPU sbatch无法提供GPU排他；继续不exclusive、按需CPU，不修改其他用户进程，不重启健康训练。日报及实测表更新，仍无筛选结论；下一次2026-11-14 01:54:04 UTC。



## 2026-11-14 09:54CST · P首轮过半

01:54UTC实际进程/Slurm会计查询：六臂均RUNNING，无新OOM、无观测错误；B0/A1/A2/A3/A4/A5样本773152/708640/857888/770080/847776/653600，合计4611136，占本轮9M预算51.23%，全部实际B128。A3 Slurm4532408和A5 Slurm4532411继续，另外四臂原生句柄正常推进。训练GPU墙钟34.3940h（含失败3.1543h），D1/D2诊断0.9774h另计。保留09:26 node22共享GPU的只读采样备注，不修改他人任务。日报/家族损失/裁剪比例及卡型吞吐功耗CSV更新；固定裁剪阈值与科学配置不变，仍不以中途VAL选择配方。下一次2026-11-14 02:24:10 UTC，完整P目标继续。



## 2026-11-14 10:24CST · P首轮56%

02:24UTC实查六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本853152/783776/927136/840992/917792/729504，合计5052352/9M（56.14%），全部实际B128；A2/A4接近1M边界。A3 Slurm4532408、A5 Slurm4532411及其余四个自有原生句柄正常推进。训练GPU墙钟37.4054h，含失败3.1543h；D1/D2诊断0.9774h单列。日报及家族损失/裁剪/卡型吞吐功耗CSV更新，固定阈值与科学设置不变，不用中途VAL选配方。下一次2026-11-14 02:54:16 UTC；完整P研究继续。



## 2026-11-14 10:54CST · P首轮61%

02:54UTC实际句柄/Slurm会计查询六臂均RUNNING，无新OOM或观测错误。B0/A1/A2/A3/A4/A5样本935584/854432/991904/912032/989216/803360，合计5486528/9M（60.96%），全部B128。A2/A4接近1M验证及保存边界，其他臂继续本轮完整1.5M预算。A3 Slurm4532408、A5 Slurm4532411与四个自有原生进程正常推进。训练GPU墙钟40.4153h（含失败3.1543h），D1/D2诊断0.9774h另列。日报/家族损失/裁剪及吞吐功耗CSV更新，不改变配置或裁剪阈值、不按中途VAL选择。下一次2026-11-14 03:24:22 UTC；完整P目标继续。



## 2026-11-14 11:24CST · P首轮66%/三臂通过1M

03:24UTC实际句柄/Slurm会计查询六臂均RUNNING，无新OOM、无观测错误；B0/A1/A2/A3/A4/A5样本1014208/928160/1056192/984096/1056192/874784，合计5913632/9M（65.71%），全部实际B128。B0/A2/A4已通过1M固定VAL及保存边界并继续推进，A3接近1M；仍按各自完整1.5M预算及末次R1/R3判定。训练GPU墙钟43.4230h（含失败3.1543h），D1/D2诊断0.9774h另计。新增B0/A2/A4原单位1M VAL CSV、家族损失、裁剪及实测吞吐功耗更新；不改变阈值/科学设置，不用中途VAL选配方。下一次2026-11-14 03:54:27 UTC，完整P目标继续。



## 2026-11-14 11:54CST · P首轮70%/五臂通过1M

03:54UTC实查六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本1091136/1002944/1118656/1053888/1125184/933920，合计6325728/9M（70.29%），均为实际B128。A1/A3已通过1M固定VAL及保存边界并继续更新；五臂超过1M，A5继续本轮完整1.5M预算。训练GPU墙钟46.4303h，含失败3.1543h；D1/D2诊断0.9774h另列。新增A1/A3原单位1M VAL CSV、日报/家族损失/裁剪/卡型实测表更新；固定阈值和科学设置不变，不以中途VAL选配方。下一次2026-11-14 04:24:32 UTC，完整P目标继续。



## 2026-11-14 12:24CST · P首轮75%

04:24UTC实查六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本1170880/1075264/1193920/1124672/1194816/996384，合计6755936/9M（75.07%），全部实际B128；五臂在最后500k段，A5尚未越过1M，继续既定1.5M预算。A3 Slurm4532408、A5 Slurm4532411及四个自有原生进程正常推进。训练GPU墙钟49.4428h，含失败3.1543h；D1/D2诊断0.9774h另计。日报、家族损失、裁剪、实测吞吐功耗更新，固定阈值与科学设置不变；本轮评价及选择仍待完整训练。下一次2026-11-14 04:54:40 UTC，完整P目标继续。



## 2026-11-14 12:54CST · P首轮80%/全部通过1M

04:54UTC实际进程/Slurm会计查询六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本1248960/1148736/1260864/1196864/1263424/1066304，合计7185152/9M（79.84%），均为实际B128。A5已通过1M固定VAL及原子保存边界并继续推进，六臂现在均在末段500k训练；仍以完整1.5M及R1/R3做本轮判定。训练GPU墙钟52.4545h（含失败3.1543h），D1/D2诊断0.9774h单列。新增A5原单位1M VAL CSV、日报/家族损失/裁剪/实测表更新，科学配置及阈值不变。下一次2026-11-14 05:24:47 UTC；完整P研究继续。



## 2026-11-14 13:24CST · P首轮85%

05:24UTC实际进程/Slurm会计查询六臂均RUNNING，无新OOM或观测错误。B0/A1/A2/A3/A4/A5样本1326656/1223744/1339840/1266496/1332032/1138624，合计7627392/9M（84.75%），全部B128，均在末段500k。B0/A2/A4接近完整1.5M；完成训练后由各自现有入口自动进行R1/R3评价，尚未产生本轮选择结论。训练GPU墙钟55.4638h（含失败3.1543h），D1/D2诊断0.9774h另计。日报、家族损失/裁剪和实际吞吐/整卡功耗更新，科学配置与阈值不变；下一次2026-11-14 05:54:52 UTC，完整P研究继续。



## 2026-11-14 13:54CST · P首轮90%

05:54UTC实际进程/Slurm会计查询六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本1406144/1296448/1411776/1337152/1404736/1215680，合计8071936/9M（89.69%），全部B128。B0/A2/A4接近1.5M；各自完整训练后仍须完成自动R1/R3评价才算该臂结束，当前不做本轮配方判定。训练GPU墙钟58.4724h（含失败3.1543h），D1/D2诊断0.9774h单列。日报、家族损失/裁剪及实测吞吐/整卡功耗更新，科学配置与固定阈值不变；下一次2026-11-14 06:24:57 UTC，完整P研究继续。



## 2026-11-14 14:25CST · P首轮94.5%

06:25UTC实查六臂均RUNNING，无新OOM、无观测错误。B0/A1/A2/A3/A4/A5样本1482048/1370688/1479104/1409984/1471424/1288000，合计8501248/9M（94.46%），均实际B128。B0/A2/A4尚余17952/20896/28576样本，完成后接续现有自动R1/R3评价；当前尚未结束完整评价，不做配方判定。训练GPU墙钟61.4808h，含失败3.1543h；D1/D2诊断0.9774h单列。日报/家族损失/裁剪/实测吞吐功耗更新，科学配置与固定阈值不变；下一次2026-11-14 06:55:02 UTC，完整P研究继续。



## 2026-11-14 14:55CST · P首轮首批评价完成

06:55UTC实查：B0与A2真实exit0、summary COMPLETE且R1/R3 scores均已产出；A4达到1500000样本、仍在评价，A1/A3/A5正常训练，无新OOM。B0/A1/A2/A3/A4/A5样本1500000/1445824/1500000/1479104/1500000/1348800，合计8773728/9M（97.49%），当前实际B128。已完成B0的R3/R1为0.055749/-0.025767，A2为0.035642/-0.106595；尚不闭合本轮或变更采纳配方，等待六臂齐全后按预注册配对规则判定。发布本批评分及B0/A2/A4的1.5M原单位VAL CSV，日报/损失/裁剪/实测吞吐功耗同步。累计训练64.1975GPUh含失败3.1543h，D1/D2诊断0.9774h另列。下一次2026-11-14 07:25:04 UTC；完整P研究持续。



## 2026-11-14 15:25CST · P首轮四臂评价完成

07:25UTC真实查询：B0/A2/A3/A4均COMPLETED且真实exit0、完整R1/R3评分已产出；A1达到1500000样本、正在评价；A5正常训练1411648/1500000。六臂当前实际B128，无新OOM或观测错误，合计8911648/9M（99.02%）。已完成R3/R1：B0 0.055749/-0.025767，A2 0.035642/-0.106595，A3 -0.015744/-0.088752，A4 0.028028/-0.077040。等待六臂完整终态后统一按预注册配对规则决策，采纳配方暂B0。发布新增评分和A1/A3最终1.5M原单位VAL CSV，更新同日日报/损失/裁剪/功耗吞吐；累计训练65.5379GPUh含失败3.1543h，D1/D2诊断0.9774h另列。A5近期34.27样本/秒、剩约43分钟训练后接评价；下一次2026-11-14 07:55:05 UTC。完整P目标继续，不恢复旧模型任务。



## 2026-11-14 15:55CST · P首轮五臂评价完成

07:55UTC实查：B0/A1/A2/A3/A4均真实exit0且完整R1/R3评分已产出；A5作业4532411仍RUNNING，1471168/1500000样本，近期34.00样本/秒，剩约14分钟训练后自动评价，无新OOM或观测错误。六臂当前实际B128，首轮累计8971168/9M（99.68%）。新增A1主分R3=0.057498、副分R1=-0.100969，已发布；其余已完成分数沿用生产结果。整轮尚待A5真实终态与评分，当前采纳配方B0，不提前作筛选结论。累计训练66.5048GPUh含失败3.1543h，D1/D2诊断0.9774h另列；同日日报/家族损失/裁剪/实测功耗吞吐同步更新。下一次2026-11-14 08:25:05 UTC，届时按完整结果推进首轮闭合及第二轮；完整P目标继续。



## 2026-11-14 16:29CST · P首轮闭合，第二轮真实启动

首轮六臂均完成1.5M、完整R1/R3评价及真实exit0；A5作业4532411 COMPLETED0:0。按预注册配对1000次分子bootstrap：A1 Δ0.001748 CI[-0.009986,0.013247] tie；A2 Δ-0.020107 CI[-0.031222,-0.008987] loss；A3 Δ-0.071493 CI[-0.087415,-0.057126] loss；A4 Δ-0.027721 CI[-0.039525,-0.016948] loss；A5 Δ-0.025361 CI[-0.037209,-0.013795] loss。无组件采纳，M1=B0；连续空轮1，按任务书进入第2轮。首轮实际67.0223GPUh（含失败3.1543h），D1/D2诊断0.9774h另列。deltas.csv、首轮最终评分/全部1.5M原单位VAL及日报已更新。

第二轮M1/B1–B4均已真实RUNNING、每条1.5M、B128、固定11-07归一化，无新拟合依赖。M1=node22普通16CPU sbatch4532491；B1/B2=node21原生PID3648907/3648908+接管sbatch4532492/4532493；B3/B4=node20原生PID3367321/3367322+接管sbatch4532494/4532495，4接管作业当前PENDING。新调度只申请所需CPU、不exclusive，按实际显存准入启动；其他用户进程不改。下一次2026-11-14 08:59:06 UTC。完整P研究继续，PR7保持draft，尚无放大确认或最终配方结论。



## 2026-11-14 17:23CST · P用户改案：旧首轮作废、旧第2轮已停，进入校准

用户已明确废止旧1.5M首轮采纳结论（B0 R3=0.05575、旧6M约0.408），不得再作为配方选择依据。旧第2轮M1/B1–B4及接管队列4532491–4532495全部已取消，4原生训练退出-15，输出/日志/旧分数/旧日报完整保留。round1_decision.json已标selection_valid=false，旧结论不进入新轮次。

新B0校准四组并行3M：B32/lr3e-4（关闭逐层重算），B128/lr3e-4，B128/lr6e-4，B128/lr1.2e-3；1.5M与3M各评R1/R3。每组前150000样本统一281.7初始裁剪并收集裁剪前梯度范数，随后冻结自身p99，完整保存拟合状态供接管恢复。以最高3M R3选择新固定batch/lr，预算按胜者首次R3≥0.30向上取整0.5M、3M内不达用3M；额外0.5M R3回填问题待答复。基础归一化仍固定11-07、TRAIN1194228。校准后重跑B0+A1–A5，第2/3轮及确认/最终REPORT继续原范围。

此前实际6卡（3×5090、2×4090、1×3090）各B32/B128测1000更新，绑定同一UUID。已启动B32：node22 sbatch4532499、node21两原生+接管4532500/4532501、node20两原生+接管4532502/4532503、node5 sbatch4532504。当前3卡B32已完整1000更新：5090_21b 46.2692、4090_20b 44.4370、3090_05 48.9168样本/秒（含初始数据准备），稳态另列CSV；对应B128已启动（node5 job4532505，node21/node20原生+接管4532506/4532507）。其余同卡B32结束后接B128，不与自身测速抢卡。四组3M尚未启动，等本批测速完成后同批并行。

全局HPC技能更新1.0.156，根/模型AGENTS及任务书顶部同步。所有既有输出保留；新测速只产日志/计时及必要接管点，校准保留0.5M检查点，新重筛选仅最终/接管权重并保留全部0.5M VAL，确认检查点安排不变。P峰值从57改61GB（+4GB），模型全局114569896448字节，独立PR6仍8GB；在实际node20核实盘/inode和账户额度后登记，原磁盘保护/不exclusive/按需CPU/混合接管不变。6项针对性测试PASS，仓库检查PASS，旧全量回归不重复。下一次2026-11-14 09:32:12 UTC。PR7仍draft，完整P目标包含本次校准及重跑，未完成。



## 2026-11-14 17:32CST · 新校准测速：6卡B32全部完成，B128全部真实RUNNING

09:32UTC真实查询：B32六卡均COMPLETED、1000优化器更新/32000样本，均无逐层重算。实际1000步样本秒（含该次初始数据准备）为5090_22 28.8193、5090_21a 36.3558、5090_21b 46.2692、4090_20a 30.2313、4090_20b 44.4370、3090_05 48.9168；稳态窗口另列throughput.csv。不同共享占用下不作纯硬件性能排序。

对应同UUID的六个B128测速均真实RUNNING，node22/21a/21b/20a/20b/05已完成40/45/177/41/137/188更新，未满1000步，不提前填最终吞吐。node22为sbatch4532508、node5为4532505，node21/20原生源及接管4532506/4532507/4532509/4532510继续现有句柄。没有新失败或观测错误，不重跑已完成B32。

本批测速累计2.1132GPUh，四组3M尚未启动；测速全部结束后按最新四组表同批启动。旧筛选/取消69.4139GPUh单列存档，旧1.5M首轮结论仍无效。日报/原始家族记录及校准CSV同步，最新规则1.0.156不变；下一次2026-11-14 10:02:17 UTC。完整目标仍含3M校准、新配置/预算重筛选、后续确认和REPORT。



## 2026-11-14 校准后重筛选规划已具备独立命名/预算/结果与成本范围

当前仍进行用户指定的B128测速；四组3M尚待测速完成后同批启动，新固定batch/lr及筛选样本预算未选择。工程接口已支持--base-configuration和--study-directory；未来base/计划在configs/p_recipe/recalibrated_20261114，运行前缀recalibrated_20261114_，结果在results/p_recipe/recalibrated_20261114，控制状态在runs/p_recipe_20261113/recalibrated_20261114。实际所选budget会传给所有筛选臂；确认预算仍4.5M。旧round1/round2计划显式selection_valid=false，已有输出、原deltas与原始评分不删。

生成/比较逻辑拒绝作废结论和跨修订基线混用。执行台账/接管新记录包含study_revision；completed_screening_gpu_hours_by_revision按修订独立累计，未来新200GPUh筛选统计不能混入旧67GPUh、已取消旧第2轮或新校准/测速。兼容保留旧按round统计用于历史账目。新筛选最终/接管权重与全部0.5M VAL、确认0.5M检查点符合已登记61GB总预测。7项针对性规划/保留档案/预算隔离检查PASS，仓库PASS4849文件1965Python，未新增GPU试验/未重跑全量回归。完整P目标继续，下一次实际查询2026-11-14 10:02:17 UTC。



## 2026-11-14 18:02CST · B128接管返回值故障已修复并从完整停止点继续

4个B128原生源在完整CP原子发布、ACK写完后，因返回值dict重复run字段TypeError退出1；Slurm接管4532506/4532507/4532509/4532510按非零源退出保护FAILED。这是真实实现故障，失败记录/原日志/完整CP保留，没有把原失败改写成成功。现在用finish_handoff统一返回状态；实际CPU worker保存/ACK/延迟wrapper/正常退出的回归1PASS，仓库PASS4849文件1965Python，没有全回归/额外GPU实验。

明确从原ACK点恢复4组：5090_21a样本25984/203步→当前28672/224步；5090_21b41856/327步→44544/348步；4090_20a22656/177步→26624/208步；4090_20b33280/260步→37504/293步。4个新run均后缀_recovery2且真实RUNNING，沿用完整模型/优化器/采样/RNG/学习率时钟，同卡B128不重置总1000更新预算。node21源PID3653675/3653674和接管4532515/4532516；node20普通16CPU job4532517/4532518。node22原job4532508仍RUNNING579步，node5原4532505仍RUNNING749步。所有B32完整1000步结果保持。

测速主值合并同一1000步的有效训练时钟，含各段数据准备，故障/排队间隔另记而不当训练秒；成本仍包含失败源真实GPU占用。本批累计3.7804GPUh，旧筛选/取消69.4139GPUh单列。四组3M还未启动，待全部测速结束同批进行；旧首轮结论仍作废，新配置/预算尚未选。日报/CSV明确本次接管故障；下一次2026-11-14 10:32:17 UTC。P61GB全局预测及其他窗口作业不变。



## 2026-11-14 18:58 CST · P测速闭合并启动四组校准

用户指定6张实际卡的B32无逐层重算/B128测速全部完成，每项严格1000更新；B128实测5090为38.73/49.57/44.86、4090为34.82/43.75、3090为39.77样本/秒。4次完整保存后返回异常的真实失败保留并已续接，无额外1000步重跑。按空闲卡5090>4090>3090及实测速率分配，四组3M已启动：G1 B32/3e-4→node21 GPU-c35f，G2 B128/3e-4→node21 GPU-22e2，G3 B128/6e-4→node22 GPU-9b60（Slurm4532552），G4 B128/1.2e-3→node20 GPU-ec78。G1/G2/G4为SSH+sbatch接管4532550/4532551/4532553；每组16CPU，不exclusive。各组前150k统一clip281.7后冻结自身前裁剪范数p99；1.5M/3M读出后才选新固定配置/预算。旧结论无效、旧输出保留；新旧归一化均固定11-07原全TRAIN参数。P全峰值61GB及现有真实盘/quota/guard规则保持，其他工作线作业不动。



## 2026-11-14 20:04 CST · P实际接管成功，四组自身p99已冻结

G1/G2原生源均在完整保存后正常exit0，从106272/139520样本由真实Slurm4532550/4532551接管，20:04已推进245648/207216样本；同GPU、完整模型/优化器/采样/RNG与前5%梯度统计续接，未从头重跑。G3为4532552/157808样本，G4仍node20原生PID3374702/153200样本、接管4532553待分配。四组均RUNNING，已完成前150000样本统计：初始统一281.7后分别冻结p99=8426.777509765629/8497.284765625/8428.734101562497/8369.670146484368；G1为4688更新，B128三组各1172更新。1.5M/3M R1/R3仍待产出，不提前选择新配置或预算。接管前后家族窗口CSV均保留并发布；仍16CPU/不exclusive，P峰值61GB及原磁盘保护不变，其他工作线不动。



## 2026-11-14 21:04 CST · P四组现均在sbatch下运行

G4已从264816样本/2069更新的完整停止点由4532553接管，原生PID3374702正常exit0，21:04继续到274416样本。连同G1/G2的4532550/4532551和G3的4532552，四组当前均为Slurm RUNNING，各16CPU、不exclusive；原生源/ACK/检查点均保留。G1达570464样本并产出首个500k固定2000 VAL家族损失及原单位MAE；G2/G3为371440/311280。四组p99沿用各自已冻结值。P峰值61GB和磁盘/配额保护保持，其他工作线不改。



2026-11-15 01:29 CST · P校准G4调度迁移：500000样本完整检查点/已提交游标一致，源4532553因计算节点→sonmi SSH拒连导致接管控制失败，清理后实际FAILED 113:0，所有输出及原始失败记录保留。经现有登录会话正式sbatch提交4532593，node20/4090_20a UUID GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5，16CPU、不exclusive；实际RUNNING/PID3381321、UID1278/start_ticks1257119225/PGID3381321，已推进501152样本。完整模型/优化器/RNG/样本时钟及冻结p99=8369.670146484368续接；B128/lr1.2e-3/3M预算/原11-07归一化不变。旧G1/G2/G3继续，未增加科学实验或重测吞吐。实际node20磁盘/share可用7.22TB、/lfshome可用40.56TB，根可用275.95GB>95.42GB保留、inode充足，后续写入仍受现有磁盘守卫约束。


2026-11-15 02:43 CST · P校准G1故障续接：原4532550实际FAILED/1:0（02:13:36），训练日志CUDA kernel launch timeout，最后提交2198080样本；源PID3656685已缺失。最近完整检查点2M（220321833B），从该点重做198080未保存样本，旧输出/失败状态/全部占用成本保留。原5090/node21b UUID GPU-c35f2434-9137-9723-1af5-dc69b6295243可响应、15MiB/32607MiB，正式sbatch4532594请求16CPU、不exclusive；实际RUNNING，新PID3660590/UID1278/start_ticks738579913/PGID3660590，已推进2000032样本，B32无逐层重算/lr3e-4/p99=8426.777509765629/原11-07归一化保持。最终1.5M评估沿resume祖先使用精确同样本检查点，新增2项CPU测试PASS，无GPU重测或额外科学实验。node21实际根可用830.68GB>95.42GB保留、/share可用7.22TB、/lfshome可用40.56TB、inode充足；node20 CPU验证的根可用275.95GB>95.42GB保留，临时文件不足1MB。G2/G3/G4继续，旧G4源4532553失败及新4532593续接关系保持。


2026-11-15 04:10 CST · 用户立即停止校准G2-G4：正式scancel4532551/4532552/4532593后，实际sacct均CANCELLED、批处理0:15；原G2 PID3656690/node21、G3 PID94064/node22、G4 PID3381321/node20均已缺失，squeue仅余G1 4532594 RUNNING/node21，其PID3660590仍在。所有已有输出/检查点保留。账本标记user_requested_stop_G2_G4及do_not_resume，训练计划记录user_stopped_arms/auto_restart_stopped_runs=false；未获新指令不重启三组。G1按原B32/lr3e-4/冻结p99继续3M及既定读出。四组对照尚未完成，当前不据此宣称选定新配置/新预算。node20实际/share可用7199982092288B、空闲2965690464inode，本次仅写入少量状态元数据。


2026-11-15 05:05 CST · P用户补充规则已执行：固定B32/单次完整32/无梯度累积/无逐层重算，AdamW3e-4 betas.9/.95 wd.01，自身cosine2%warmup至0；新臂裁剪前150k用281.7、按步起点60k–150k范数p99，完整32批于150016冻结，只报告。用户明确筛选3M×三轮、确认9M；C1/C2胜出lr并入M3，T2/T4/T5/T6/T7继承，T1/T3(M2)3e-4；B1第2轮优先。全研究原11-07全TRAIN归一化不变，重叠剔清单记日志继续。HPC技能1.0.158及根/本仓AGENTS、共享规则、根P任务书已更新：无特别停令不得因规则/小配方更新停在跑训练或要求从头重训。
此前代理误停G14532594（CANCELLED），已按用户纠正从2.5M完整点续接，仅重做3392样本，保留原p99=8426.777509765629；用户明确原G1完成后直接复用B0。当前G1/native node21b PID3662666 UID1278 start_ticks739170260 PGID3662666，sbatch接管4532595排队，05:05已2663232样本。G2/G3/G4保持CANCELLED，未重启。新首轮A1/node22 sbatch4532596、A2/node21a native PID3663754+standby4532597、A3/node20a sbatch4532598、A4/node20b sbatch4532599、A5/node05 sbatch4532600均实际RUNNING且有32整批训练记录，预算各3M。无新B0训练；原A1/A2/A5标签参数复用，未重算D4/身份审计/新增GPU测速。
确认恢复权重每1M/最终9M及接管点保存，VAL仍每500k；全P既有61GB峰值/模型总114569896448B按实际node20和账户quota重新预检ADMITTED（Lustre可用171580461056B、需求169941542400B；NFS可用143438168064B、需求131836912640B），保留全部已有文件，不改其他工作线预留。已通过24项针对性CPU测试及全仓检查；仅新检查点间隔的定向测试补验中。日报新首轮固定设置和卡型吞吐/整卡采样均值真实记录；B0前段未采功耗不补造。

本次新检查点间隔补验已完成：10项针对性CPU测试PASS（0.11s）；24项主体针对性测试PASS（0.23s）。

2026-11-15 · 新独立任务：用户要求迁移前生成训练精简 LMDB，并以 sbatch、多CPU、zstd完成。源 D6 v3.1/原ID表/原始r73/已有缓存与所有训练作业保持；新副本排除r73原始数组31–34（保留σ/π训练目标）、训练禁用列、100GB原ID表及历史缓存，迁出前烘焙稀疏掩码并保存轻量train/VAL索引，保持原全TRAIN归一化。控制目录 runs/training_lmdb_slim_20261115。小样本4532601在node18启动受阻已取消，4532602缺Python zstandard真实失败，4532603改用现有libzstd、node20/16CPU已完成测量。压缩仍预计数百GB；/share及/lfshome账户余量不足，禁止写入全量副本。拟由node20的20CPU sbatch负责所有投影/压缩，node21仅经SSH接收字节并写新LMDB，路径/tmp/zixiao/training_lmdb_slim_20261115；node21本次实核可用830674976768B、根保留95415907124B，峰值新增上限600000000000B，另计其他窗口并发100000000000B和4GB保护余量。所有窗口须共同计入此600GB预留；容量不满足不开始写入，运行期接收器逐事务检查，触及预留退出并保留可续传状态。未授权启动正式预训练或外部转移，尚未发布完整训练集。
2026-11-15 · LMDB训练精简实际启动：4532604在投影schema检查时因r73特殊selector未跳过而失败（未写数据），4532605在解析稀疏掩码前因chemprop缺pyarrow失败（仅少量新metadata）；已修正并复用既有模型venv+deps。当前sbatch4532606，node20/20CPU、无GPU，node21仅字节接收/LMDB写盘；磁盘准入free830671888384B、根保留95415907123B、并发预留100GB、输出cap600GB。767条分散样本的保留数组/有效训练raw、mask、normalized结果PASS，保留133个训练字段；FULL20/TRAIN3176个稀疏掩码地址已解析，新副本烘焙原mask。FULL全量导出中，TRAIN随后，当前未完成/未转移/未启动正式预训练。控制与使用说明：runs/training_lmdb_slim_20261115/README.md。旧源数据/原ID表/历史缓存/其他窗口作业均保留。全量完成只以completed.json及新数据manifest.json为准。
2026-11-15 · 4532606实际推进：FULL已通过最终源计数与接收LMDB小样本字节核对并关闭，TRAIN已处理1282048记录（含1194551个M及已开始P），尚未完成。node21输出实测allocated6448300032B、根可用824226656256B；600GB总预留保持。全量任务会自行完成精简→逐记录zstd→事务写入→计数与写入验证→发布manifest/completed，失败或空间阈值保留提交游标，可用同一sbatch恢复。此时不得把“sbatch已启动”记为整个数据集完成。
2026-11-15 · 训练精简LMDB已完整完成并验收：导出4532606 COMPLETED0:0，node20/20CPU，耗时02:20:07；读取集成4532607 COMPLETED0:0，node20/2CPU，14秒。输出node21:/tmp/zixiao/training_lmdb_slim_20261115，TRAIN393457491968B、FULL4319641600B；含metadata实际总占用397789855744B，根可用432882802688B。新副本无原始r73数组31–34/100GB ID表/历史缓存/禁用训练列，保留原σ/π目标及133个有效字段、几何和掩码、原11-07归一化。767条生产等价PASS，真实闭合LMDB entries=TRAIN22972345/FULL263728（各含1个提交游标键），数据记录总23236071；TRAIN/FULL×PM7/Pprime共12个实际字节读取样例PASS；默认索引1194228 TRAIN（保留323排除）/2000 routineVAL PASS。原始文件、原ID表、旧缓存和其他工作线任务保留；未启动正式预训练或外部迁移。600GB“未来新增峰值”预留现已结清，未来新增=0，现有397.8GB已在df中，不得再当作600GB未来增量重复扣减；文件继续保留，后续任何跨节点/外部复制仍须针对目标盘新预检。完成报告及持续监控历史：runs/training_lmdb_slim_20261115/final_report.json、monitor_history.jsonl；输出自带README/files.json/两份验证摘要/轻量索引及SlimDataset读取器。
2026-11-15 · 用户已明确授权将当前训练精简LMDB和模型文件复制至202264640132@202.38.252.202学校集群；授权仅限文件迁移、目标路径/配额/磁盘元数据检查，不启动正式预训练，不在学校集群做开发/调试/科学计算。源LMDB node21:/tmp/zixiao/training_lmdb_slim_20261115实际397789855744B；当前模型代码约68.95MB、B0/G1已关闭3M完整检查点220324713B及A1/A2/A5参数，计划总398079189848B；当前A1–A5仍在跑且尚无已发布完整检查点，不为迁移停训或强制保存。准备清单runs/school_migration_20261115/transfer_plan.json，源代码HEAD3ab4a9b4060c9a57e66663e481e921272c619b10（保留工作区修改，未改Git状态）。已重试Windows默认key/既有descriptor key和开发服务器密钥，学校账户均拒绝publickey；已核Xshell窗口当前连login01、会话Host252.202/Port22/User正确，但本轮无可复用命令行认证，正待用户在已登录Xshell为本机既有公钥开通访问或提供可用OpenSSH密钥路径。没有读取/导出Xshell密码，未写目标文件，容量/账户quota尚未知，因此禁止先传输。后续认证成功后实核目标findmnt/df字节+inode/账户quota及并发峰值，采用续传及运行期磁盘保护；保留所有源文件。
2026-11-15 · 学校迁移认证/磁盘准入已落实：用户已在学校账户加入本机既有公钥，Windows与源node21经临时SSH agent转发的直达学校SSH均验证成功；私钥不复制到任何服务器。目标login01 /share为GPFS dssgdev/root fileset，UID/GID67109；GPFS配额须用实际UID67109查询（全数字用户名被按其他UID解释，此前拒绝）；实时用户硬限2393423872KiB，用量约24033280KiB，扣blockInDoubt后可用约2.425TB；组及root fileset无额外有限限额，整盘字节/inode充足。目标预留新增峰值450GB，账户/FS余量各100GB、其他并发100GB、运行突发16GB；已部署接收端逐秒磁盘/实时quota保护，只暂停/终止绑定的自有rsync进程组。目标staging /share/home/202264640132/descriptor_analysis_migration_20261115.partial，全部成功后同盘原子发布为descriptor_analysis_migration_20261115。源node21另做已保存模型文件独立快照，新增峰值<=1GB，根默认95.42GB保留另计其他并发100GB（当前可用432GB），主LMDB397.8GB保持。源21→学校直接rsync --inplace --partial，避免400GB本地中转缓存和目标临时双份；先模型后数据，不删除源，不启动正式预训练/学校科学计算。当前模型只复制已关闭B0/G1 3M CP；A1–A5继续在源集群跑，不强制新检查点。控制目录runs/school_migration_20261115。
2026-11-15 每步CPU提速独立线：X:/MFM_step_overhead_20261114，NFS新增输出峰值预留4,000,000,000字节（已核实quota并计入其他预测），不复制LMDB/检查点；node7空闲3090仅作8重批显存验证。P在用GPU/作业/输出目录均不触碰，PR仅就绪不合并。



2026-11-15 · 学校文件迁移实际完成：目标 202264640132@202.38.252.202:/share/home/202264640132/descriptor_analysis_migration_20261115，源node21直传，MODELS/DATA发送端及接收端均exit0；原生rsync文件传输校验成功，4858个清单文件大小/归属核对通过，含清单自身和完成标记共4860文件，逻辑398079801353B、实际占用398356945408B。训练精简LMDB记录23236071，TRAIN393457491968B/FULL4319641600B；模型含当前源码/配置、A1/A2/A5参数及已关闭B0/G1 3M完整检查点220324713B。staging已原子发布，完成标记及最终目录已复查；完成时实际quota可用2026001137664B、FS可用7194385632460800B，inode充足。源文件全部保留，源在跑训练未中断，未启动学校正式预训练/科学计算；旧配置绝对路径保留并附path_map，目标训练环境尚未验证。源模型快照1GB及目标450GB的未来新增峰值预留均结清为0，现存文件已在df/quota中，不得重复扣未来峰值；已有源快照/LMDB继续保留。报告 runs/school_migration_20261115/final_report.json，持续监控历史 destination_monitor_history.jsonl。

2026-11-15 每步CPU提速独立线补充：node7本线全量回归将另预留根盘/tmp新增8,000,000,000字节；根盘实测可用约26.9GB、另留至少10GiB系统空间，独立监控自有job。NFS仍共用本线4GB总输出预测，不与P训练共享GPU。


2026-11-15 CPU提速回归磁盘续跑：node7自有4532629已在保护触发后停写并取消，/tmp/step_reg_4532629约8.16GB保留，不清理；续跑4532639拟用node12，实际根盘69.4GB可用、inode36.5M，新增临时峰值24GB并保留至少10GiB系统空间，按自有job持续监控。复用已完成模块，仅补未完成/受影响项；NFS总输出预测仍4GB。


2026-11-15 CPU提速线最终梯度原始记录：同名results目录NFS总新增峰值预算由4GB提高至16,000,000,000字节，覆盖两组权重×20批×旧1/旧2/新全部FP32完整梯度。4532640在同张node7/3090上接在4532627结束后执行，启动前实际磁盘/inode/quota重新预检并持续保护；LMDB/G1/P卡不改动，原试次保留。


2026-11-15 每步CPU提速完成：PR https://github.com/mint258/MFM/pull/8 已就绪、未合并。node7同卡3090为52.25→71.60样本/秒（1.370×），数值和1000批输入精确对照通过；全部自有测试作业已结束，GPU释放。完整梯度120份共11,882,731,320字节已计入NFS实际占用，后续本线仅文档/Git写入、剩余未来增长<200MB，原16GB未来预算不重复计；node7约8.16GB测试临时目录与node12测试临时目录保留。P在用卡/作业/LMDB/检查点未改动，合并由用户在两轮之间决定。


2026-11-15 精度独立线已启动，工作树X:/MFM_precision_20261115，分支perf/precision-20261115，基于GitHub最新p-recipe。仅该线新增FP32/TF32 islands/BF16 islands；不占P运行卡。node7现已被P4532642占用，精度测试改选node0/3090 GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332，实际预检根盘38.6GB余量、NFS7.41TB、账户458.76GB可用，新增18GB总预算（代码/短测/双3M及读出），另扣其他未来23.18GB并保留100GB+8GiB。测试/结果只写NFS、TMPDIR短NFS路径，不复制数据，不删旧临时目录；自有job持续磁盘保护。用户最新明确授权A800精度及B32/B128测试：gpuA800单卡9CPU、申请比例9:1、全在计算节点、用storage并核实实际quota，尽量合并申请节省费用。硬件最大5090/4090/3090/A800=3/2/6/4，预期约一半；P卡不改动。

2026-11-15 16:45 精度线：数值4532643已C0，固定20B×seed0/G1-3M×FP32重复/TF32/BF16均有限；唯一新增岛测试CPU/GPU通过，原有相关测试25通过。质量TF32/BF16在node21两张目前无P进程的5090上从头并行3M，native主PID3690581/3691013，GPU分别22e21021/c35f2434，own UUID锁及NFS18GB全局余量保护；同任务standby4532644/4532645，不使用P ledger，现有P不改。3090速度网格4532646 node0执行中，同卡B32/B128各三精度100+1000步。学校准备CPU2092055因计算节点无外网取消（未申请GPU），改在开发compute20仅下载Linux轮子，经受控文件传输送学校离线安装；学校新增20GB预算覆盖代码/轮子/环境/测速，实际GPFS quota2.027TB可用，另留100GB系统/账户+100GB其他并发+16GB边际。用户明确直接用学校已迁移压缩LMDB，不整库解压不复制数据；r73及全部既有FP64数据协议必须原样。

2026-11-15 用户明确禁止使用compute-0-21，所有窗口后续不得再在该节点启动本线计算。精度线原两条在12032样本因原Lustre LMDB kernel folio_wait_bit_common停滞，已仅关闭本线绑定PID，原始输出保留，4532644/4532645取消。短暂本地压缩恢复TF32已响应用户禁用要求，完整保存samples_2304.pt、72updates后正常exit0，4532683取消；BF16本地恢复未启动。本线启动器已硬拒绝node21。TF32正式续接改node6/3090（实测整卡5MiB/0%，48CPU闲置，根57.5GB可用、共享quota持续保护），Slurm4532684；BF16改node0/3090，4532685依赖本线速度4532646成功完成后启动，仍并行覆盖各自完整3M，P现有卡不动。学校离线轮子已服务器直传完成，只使用CPU节点接收/安装、尚未申请A800；直接读取已迁移压缩LMDB、不整库解压。校端仍20GB峰值，开发端18GB峰值，原始失败/断点/成本全部保留。

2026-11-15 精度线最新口径：用户确认node21禁用后当前有效最大5090/4090/3090/A800=1/2/6/4，平均0.5/1/3/2；原3张5090仅另列规划情景，不参与当前推荐。草稿PR10 https://github.com/mint258/MFM/pull/10，未合并、不切换P。3090 B32实测FP32/TF32/BF16=52.40/46.36/47.43样本秒，B128网格4532646继续；TF32质量4532684 node6已超过14万样本，BF16 4532685依赖同卡测速结束后在node0启动。学校环境CPU检查2092224已C0，A8002092234排队，实际TRES=9CPU/1GPU/64GiB，未占GPU计费时间。后台监控compute20 PID1602836每1800秒写本线CURRENT.json（计算节点sacct不可用，自动读squeue及本线原生状态）；不自动重启任务。本线总25项CPU测试=新增1+既有24，新增岛测试另在GPU通过，前文'25个既有'口径更正；仅新增一个测试。开发NFS18GB、学校20GB预算保持，原始失败/恢复输出保留，后续不再用node21。

2026-11-15 10:49UTC 精度线：node21继续禁用。当前有效5090/4090/3090/A800上限1/2/6/4、平均0.5/1/3/2；原3/2/6/4规划仅另列情景。3090网格4532646、TF32 3M作业4532684继续；BF16 4532685依赖测速完成。4090 node20卡0测试4532716已排队，节点COMPLETING尚未分配，未占卡，不动GPU1的P任务；A800 2092234仍待Priority，1卡9核64GiB。唯一岛测试加强版开发/学校CPU均通过，GPU检查在测速入口执行。

2026-11-15 10:42UTC 精度线时间更正：上一条标作10:49UTC的记录实际核实时间截至10:42UTC；作业、资源和测试状态不变。

2026-11-15 10:48UTC 精度线追加：node22/5090测速4532717已提交，afterany:4532596（P A1），当前PENDING(Dependency)，不占用在跑P卡。使用现成Torch2.10.0+cu128/PyG2.7.0环境（compute20 CPU导入核实，无安装）；16核32GiB、启动前仍检查P进程/显存/自有锁及磁盘。监控计划已纳入4532717。

2026-11-15 11:21UTC 精度线：3090同卡网格已闭合5/6格；新TF32/B128为39.0987样本秒、CPU100.032%、280.983W、分配峰值8925813760字节，1100更新/100预热+1000计时。4532646已自动进入最后BF16/B128，4532685质量任务仍等待其成功结束；TF32质量4532684继续。A8002092234仍PENDING，预估11-16 14:24仅为预测；4090/5090队列不变。CPU PR8仍未合并，不触发重测。

2026-11-15 21:09UTC（11-16 05:09CST）精度线：用户2小时时间盒G1/BF16排查已完成，固定最坏batch0/12/13/19的实际前反向dtype观测54183次未发现规定FP32岛泄漏；偏差主要来自允许BF16的独立H1标量头点积相消。生产精度/标签/掩码/归一化/既有FP64未改，BF16质量4532685继续、未重启，TF32 4532684继续。完整11760行逐字段CSV及诊断报告/100行消融CSV/audit JSON已推至PR10分支。4090短程诊断已退出0并释放GPU与自有锁，4532716已解除本线临时hold，仍待Slurm；5090 4532717在P自然结束后执行，唯一加强版岛测试GPU通过；3090六格闭合。A800旧2092234在g02n03因根盘仅28.095GB<42.946GB保留量于2秒退出，无科学计算；新2094953排除该节点，仍1卡9核64GiB。监控计划已更新。

2026-11-15 21:30UTC（11-16 05:30CST）精度线4090推进：node20持续IDLE+COMPLETING，实际Slurm无法分配；目标GPU-8bfd2ba3卡无P进程、870/49140MiB、0%利用率，根盘/共享盘/UID配额预检通过后已SSH启动受保护独立测速格流程。真实guard PID1614634、worker PID1614643，job_id=null；唯一岛测试GPU通过，首格FP32/B32完整1100更新、计时1000更新，76.7872样本秒/CPU99.354%/225.199W/分配峰值5832558592字节，现TF32/B32继续。新接管作业4534809已排队16CPU32GiB；旧4532716从未分配，已取消。仅在完整独立格结束后交接，不跨计时窗口、不重跑已闭合格；实际Slurm接管尚未发生。首次启动参数错误退出2（未开始测试）记录已保留。模型/数据/在跑质量与P任务均未更改。

2026-11-15 21:59UTC（11-16 05:59CST）精度线：node22/5090测速4532717已COMPLETED0（2:02:08），同UUID六格均1100更新/100预热+1000计时完成，本线已结束该卡测试；新P任务仍按实际占用准入。B32 FP32/TF32/BF16=92.6878/90.0689/86.1984，B128=74.4020/74.6456/68.4781样本秒。4090 B32三格=76.7872/73.3311/67.3994，B128在原生受保护流程继续、4534809接管仍排队。学校CPU准备2095229 COMPLETED0（2CPU58秒，零GPU），直接压缩LMDB读TRAIN/VAL、完整G1模型构建通过：1194228/2000、133字段、24755300参数；A8002094953仍PENDING。未改在跑质量/P任务，node21继续禁用。

2026-11-15 22:26UTC（11-16 06:26CST）精度线A800：2094953在g02n02启动设备识别时FAILED6、Elapsed0秒（No devices were found），无测速输出；原root失败2092234保留。已将绑定从Slurm/global数值当NVML索引，改为在磁盘准入后保留Slurm CUDA可见性、由CUDA设备属性取UUID，再统一模型/功耗查询。代码已在CPU作业2095439部署并通过Torch2.8.0+cu128 UUID接口/脚本检查，COMPLETED0、2CPU12秒，实际GPU绑定仍待分配验证。新2095456按1卡9核64GiB/4h排队，排除g02n02/g02n03，继续直接使用已有压缩LMDB；监控已换新jobid。主模型/数据协议及质量训练未变。

2026-11-15 22:46UTC（11-16 06:46CST）精度线A800已实际启动：2095456 RUNNING于g04n05，根盘可用35682783232字节/总75125227520字节、inode36571256，UID67109配额可用约2.016TB，准入通过。Slurm GPU编号2映射CUDA可见0，现通过CUDA实际UUID GPU-41d7530a-6ffa-0295-a09e-234661b33ad6绑定到模型及NVML，实际绑定验证成功；唯一GPU岛测试1passed，首格FP32/B32已完整100预热+1000计时，69.6327样本秒/CPU98.197%/183.740W/分配峰值5831537152字节，后续同卡继续。1卡9CPU64GiB及直接压缩LMDB不变；未改模型数学或数据协议。4090已闭合4/6格，FP32/B128为50.8566样本秒，TF32/B128继续；两条3M质量原作业继续。

[precision 2026-11-16 08:19 CST] CPU PR8已合并，精度线使用独立MFM_precision_rebased_20261116做集成；原MFM_precision_20261115的两条3M质量作业4532684/4532685继续原代码，不热改/不重启。额外工作树及复核峰值预算0.5GB已在实际compute20根盘/NFS字节+inode+quota核验。4090六格原生退出0；单步变基复核1652612退出0，GPU20现已释放，4534809及4534815均零分配取消。学校2095456仅剩A800 BF16/B128。新基线已发布的provisional_B deltas.csv触发旧仓库检查器白名单遗漏，本线只补该确切汇总路径。

[precision 2026-11-16 08:54 CST] 四卡24格速度已完成并通过原始功耗/步数/UUID核验；3090和5090已释放，4090原生六格C0且无Slurm分配，A8002095456为COMPLETED/0（9CPU+1GPU，8690秒）已释放。精度PR10已接到CPU PR8合并后的p-recipe并完成唯一固定首批单步复核；现仍以旧启动工作树继续TF32质量4532684/node6和BF16质量4532685/node0，不迁移/不热改/不占用P在跑卡。当前约1.70M/1.00M样本；最终R3/R1质量判定尚待两臂3M及既定评价结束，尚不切换P精度。

[P data information 2026-11-16 CST] User authorized TASKBOOK_V1 stages0–5 only,CPU-only/GPU0; independent docs/p-data-information-20261115 checkout X:/MFM_p_data_information. External /share/home/zixiao/descriptor_analysis/runs/p_data_information_20261115_v1 reserves at most16GiB NFS growth (no Lustre or root cache growth), plus <=1GiB source checkout/fetch. Current compute20 actual NFS/root bytes+inodes checked; each producer checks quota/concurrent headroom before writes. No existing jobs or production data changes. Stage0 identity metadata:55000 linked,8 current TRAIN exclusions,49992 TRAIN+5000 VAL eligible; no numeric conclusions yet.


[P data information 2026-11-16 14:39 CST CLOSED] TASKBOOK_V1 stages0–5 completed with explicit UNRESOLVED evidence; final study pushed 54b0cb8f6de8052005fcf7e2d55267985220a962 on docs/p-data-information-20261115. 4665 molecules/42961 records; 43 original-F64 graph +35 local scalar fields,109 pilot/current-CPU targets. Source vector frame integration stopped after2 implementation failures per taskbook; not evidence of undefined data. New training0/GPU0; only8 PM7 SCF-tight cases, no xTB calls or production/job changes. All own numerical processes exited. compute20 measured retained cache6822977536 bytes, source checkout43053056 bytes before final Git/docs; shared UID1278 headroom446284775424 bytes. No further numerical growth planned: prior16GiB analysis+1GiB source future-growth reservation closes; retained files remain quota-used, are NOT deleted or freed. Other projects' reserves/real disk/inode/root floor protection remain unchanged. Final report: MFM_p_data_information/docs/p_data_information/FINAL_REPORT.md.

[P follow-up 2026-11-17 CST] User taskbook filename v1 has v2 body A/B/C/D. Independent branch p-followup-20261116, checkout MFM_p_followup_20261117 at p-recipe e1926db; prereg5314afe and B0 ca639d0 pushed. A forward-only job4535148 uses compute20 GPU-ec788ed1,4CPU; holds shared UUID lock, no training. C/D only seed0,3M each; source/ledger separate, mainline runs untouched. Storage: new logical /lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/p_followup_20261116 links to /share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/training (NFS); no old file moved/deleted. Reserve10GiB NFS growth including A<=3GiB,C/D checkpoints/evaluation<=4GiB,mean table<=1GiB,source/control. Original-F64 sidecar physically on /lfshome/zixiao/data_v1_20261025/p_followup_f64_20261116,forecast~1.00GB from22027705 conformer rows,1.1GiB growth reserve,2GiB cap. Existing mainline61GB/global114569896448 and other-window reserves unchanged. Real target-node root/shared bytes,inodes,UID quota checked and guarded; compute21 remains banned. Sidecar switch stays off in C/D/mainline; C/D recommendations require user confirmation before integration.

## 2026-11-17 精度研究：TF32质量闭合，BF16继续

精度线TF32作业4532684已COMPLETED/0，完整3M/93,751更新及150万、300万原协议R1/R3全部完成，node6的本线Slurm资源已释放。相对G1：R3差−0.058471（95%配对CI −0.072070至−0.044797），FP32胜出，TF32不合格；R1差−0.023836（CI −0.042608至−0.005397）。完整训练记录连续且有限，最终VAL 109字段/10家族齐全。GitHub精度分支报告和质量JSON已更新，PR10继续草稿。BF16作业4532685在node0继续原G1配置至3M和既定评估；保留原运行工作树，不重启、不调整P精度、不触碰其他作业。监控计划仅保留BF16活动作业，TF32原始证据与终态完整保留。

[P follow-up 2026-11-17 CST storage update] The one full CPU regression's terminal first attempt used7.1GiB of owned NFS scratch; its logs/XML/summary are retained and only that terminal owned scratch was removed. For the repaired full run4535192, reserve8GiB temporary regression growth IN ADDITION TO the original10GiB follow-up NFS budget: total18GiB peak, not18GiB plus10GiB. Actual compute20 preflight: UID1278 NFS headroom478461227008B vs total forecast167204395008B; root free349007233024B of954159071232B, inode margin sufficient. The follow-up guard charges the18GiB peak before/during new CPU-regression writes. Existing C/B1/D1 continue; no live training restart. Sidecar1.1GiB Lustre and its2GiB cap, C/D4GiB cap, means1GiB cap, mainline61GB/global114569896448B and all other-window reserves remain unchanged. New regression stays pending until compute20 CPUs are allocated; no paid server or other node used.

[P follow-up 2026-11-17 CST regression/runtime update] C automatically handed off its complete1472416-sample state to real Slurm4535150, trainerPID29495/UID1278/start_ticks5860252 on compute20 GPU-8bfd2ba3, continuing the unchanged frozen C_source. CPU full suite4535192 is terminalFAILED:3538 reported tests across200 modules; failed modules include tests requiring real16CPU allocation, node-local private storage and the established native Python reference exports. Repair reruns only its18 failed modules, retaining completed passes and all original logs. New repair requests real16 CPUs; no fake Slurm context. Reuses existing PrivateStorage and native reference paths. New test scratch roots /tmp/mpTests_<job> and /tmp/mv3n_<job> share a combined10GiB local-root peak forecast, guarded before/during writes. Actualcompute20 root available349006774272B of954159071232B,465753833 freeinodes; system floor max10GiB/10% and all other-window forecasts remain. NFS18GiB follow-up reserve remains, including retained prior terminal regression scratch; C/D4GiB, means1GiB, sidecar1.1GiB Lustre/2GiB cap and mainline/global reserves unchanged. No old D4 refit is restored, no live training is restarted, no paid server is used.

[P follow-up 2026-11-17 CST regression closure] Full200-module CPU suite and failed/changed-module repairs now PASS: effective3659 tests,24 skipped,0 failures/errors. Original4535192 and4535238 failures retained; final4535240 COMPLETED0:0, real1CPU37-test targeted repair. Together with interim4535184, actual allocatedCPU cost1.487CPU-h. All own test jobs terminal; the temporary10GiB root future-write reservation closes, while retained /tmp test files remain actual used bytes. NFS18GiB forecast remains for retained prior NFS scratch and pending research outputs. No cleanup/move or release of another window's reserve occurred. C4535150/PID29495 continues on frozen C_source; D14535185 and B14535157 continue; D2 remains dependency-bound. Full scientific goal is still active, with real B3/C/D/D2 acceptance pending.

## 2026-11-17 精度研究最终交付：统一FP32

两条原G1完整3M质量作业均已COMPLETED/0：TF32 4532684/node6、BF16 4532685/node0，均93,751更新，150万和300万原协议R1/R3及每500k固定VAL齐全且有限；本线Slurm资源已释放，自有元数据监控9314已在身份核实后停止。R3：G1 0.347503、TF32 0.289032、BF16 0.327593；按预注册配对规则FP32胜过两候选，均不合格，统一推荐FP32。有效平均B32合计419.60样本/s，上限839.19；原规划仅作情景512.28/1024.57。P运行设置未改，后续时机由用户在轮间决定。

一页PDF、Markdown、完整逐字段CSV、24格速度CSV、最终质量和10家族VAL精确CSV已推送GitHub精度分支；PR10已可审阅、未合并：https://github.com/mint258/MFM/pull/10 。分支源码检查PASS（5016文件/1992 Python/1308冻结来源）；合并态GitHub CI仍有主分支既有201项数据/体积策略错误，基线202项，本PR新增0项，已在PR明确说明。所有原始结果、恢复状态与失败记录均保留；数据FP64协议未改，未触碰其他作业。

[P follow-up 2026-11-17 CST B1 recovery] OriginalB14535157 completed all22027705 D6 handles/offsets, then failed because non-CELL QC metadata was included as a numeric family. Selected families are onlypm7_neutral/xtb_alpb/xtb_singlepoint; actual representative source projections now pass through original common.task_components. Preserve existing sidecar staging. Recovery chain4535375(four-column F32 comparison cache) ->4535376(source-only F64 continuation) ->4535377(B3); old never-run B34535158 canceled. F32 cache grows~0.353GB on own NFS within existing18GiB peak, no new Lustre cache/copy and no full source index. Source locators stay compact/in memory, coalescing existing row/slot pointers so selected row groups read once. Actualcompute20 preflight UID headroomLustre161136656384B vs forecast160686345318B (~450MB spare), NFS469426810880B vs158428411904B; root349GB and inodes sufficient. Preserve mainline61GB/global114569896448B and every other-window reserve. Real disk/quota guards continue; cache failures terminate only owned pool workers. C/D1 continue unchanged; source recovery initially queues for5CPUs.

[P follow-up B1 scheduling correction 2026-11-17 CST] Actualcompute20 has4 allocatable CPU slots (CPUAlloc100/104). The old5CPU recovery chain4535375/4535376/4535377 was confirmedPENDING; its root job was held, then all three were canceled before native work. Replacement4535380(F32 reference recovery)->4535381(source F64)->4535382(B3) uses4CPU for each production stage,3 readers+parent; B3 remains2CPU. No training, data/labels/masks/thresholds or disk forecasts changed. NFS reference cache~0.353GB stays within18GiB; Lustre1.1GiB sidecar reserve and mainline/other-window forecasts remain intact.

[P follow-up B1 handle repair 2026-11-17 CST] Recovery4535380 stopped at its first scalar S7 handle comparison: NumPy drops trailing NUL bytes when extracting a fixed-width binary scalar. Preserve/pad all7 bytes for comparison; P/U and MI/CI mismatch checks remain. Existing F64 module now4 tests PASS on actualcompute20 CPU, sourcec2984b6; base full gate preserved separately. Never-run dependent381/382 canceled. Replacement4535384 is RUNNING with actual F32 cache read progress, source4535385 and B34535386 are dependency-bound;3 readers+parent=4CPU. Existing D6 staging/offsets retained, reference cache~0.353GB within own18GiB NFS; no new source index or Lustre cache, no data/mask/scientific threshold changes. D14535185 continues (330240 TRAIN MID at latest check), D24535191 depends afterok; C4535150 continues~1.946M/3M. No changes to mainline jobs or other-window reserves.

[P heads 2026-11-17 CST] User explicitly started independent p-heads-20261117. Worktree MFM_p_heads_20261117; H/T agents operate concurrently under TASKBOOK.md v1.1. Preregistration freezes before scientific computation. Reserve TOTAL18GiB NFS new peak: H10GiB + T7GiB + source/control1GiB, shared across this line, not per job. No bulk writes/copies to Lustre or node-local root/tmp; any actual temporary output remains subject to node bytes/inodes/quota and runtime guards, root floor max10GiB/10%. Preserve mainline global114569896448B, follow-up18GiB, sidecar1.1GiB Lustre and all other-window forecasts. No mainline/follow-up job changes, no node21 or paid server. Baseline B3 seed0 reused; mandatory T1/T2/T3 seed0 each3M, conditional seed1 up to4 more only. Mainline new-GPU demand has priority. Coordination owner: p-heads root; runtime handles will be recorded in docs/p_heads/DAILY_20261117.md.

[P heads runtime 2026-11-17 CST] H5 job4535403 COMPLETED0:0 (5000VAL,147s); H1 job4535404 RUNNING compute0/4CPU on shared-lock UUID GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332; T3 job4535405 PENDING16CPU on same node, afterany4535404 only for shared GPU release. T3 uses own frozen16.6MB executable source. Mainline new-card demand remains priority; coordinate with p-heads root before claiming this pending same-GPU slot, never stop a running job. Existing mainline/follow-up processes unchanged. This line's18GiB NFS total reservation remains (not18GiB per job), no new Lustre bulk output. T1/T2 await real64-sample head acceptance; no extra training authorized.

[P heads CPU resource update 2026-11-17 CST] Pending T3 job4535405 now requests15 CPUs (NumCPUs,CPUsPerTask,MinCPUsNode all15); same job/source/GPU/dependency afterany4535407, no training started/restarted. Code review: direct entry has14 single-thread readers+1 main compute process; auxiliary threads share its actual Slurm mask. Reader pool exits before unchanged16-thread evaluation. Actual cluster uses task/affinity; owned T2 one-CPU Python is confined to its assigned Linux CPU16. Verify T3 parent/readers remain confined to its actual15 allocated CPUs on startup. No workers/step_overhead/batch/lr/clip/seed/sample-budget/eval or mainline scheduling changes. Existing T2 acceptance and every other live job continue. Mainline new-card priority, shared UUID locks and18GiB NFS total remain.

[perf_sync 2026-11-17] Independent taskbook line MFM_perf_sync_20261117 / perf/sync-free-20261117. TOTAL new NFS peak23GiB: source/Git/report3GiB plus one combined scratch cap20GiB across results/perf_sync/scratch and sibling .perf_sync_scratch_20261117. No LMDB/checkpoint copies or Lustre/root bulk writes; actual target bytes/inodes/UID quota checked and guarded. Mainline114569896448B Lustre and all other-window forecasts remain separate; this line conservatively debits other NFS70GiB before admission. All GPU types unavailable at S0, skipped without waiting; mainline/follow-up/heads jobs unchanged; node21 banned; no paid server. Only own CPU-only final regression4535450 queued compute-0-20/16CPU (legacy real CLI fixtures require16); native infrastructure attempt retained, passing modules reused. All new switches default off, none qualified or enabled.

[P heads queues 2026-11-17 CST] T2 acceptance4535407 COMPLETED0:0:1046updates,all9headsPASS; mandatory whole-PD-model new-switches-off comparison is bitwisePASS. T1 remains missing by its fixed2000-update producer gate. InitialT34535405 failed at Git metadata initialization (0updates/noCP); fixed only frozen real revision metadata, preserving original outputs. Pending/unstarted449/451 confirmed0s then canceled because node0 CPUs now48/48. Current registered jobs: T34535452 waits afterokC4535150 on4090_20a/8bfd2ba3; T24535453 waits afterokC14535187 on4090_20b/ec788ed1. Bothnode20/15CPU/nice10000, mainlinepriority, no active job changes. Source T3_source/T2_source frozen;18GiB NFS shared peak remains. Node4 low-VRAM CUDA coexistence is awaiting user clarification; no task computation started there.

[2026-11-17 USER COMPUTE NODE POLICY] User explicitly allows other suitable development compute nodes for this and future tasks; compute-0-20 is no longer mandatory. HPC skill1.0.160 and root AGENTS updated. No login computation, node21 still banned, no paid-server expansion, mainline/other tasks and actual disk/inode/UID quota guards remain. Own pending CPU-only regression4535450 may be replaced by compute-0-16/16CPU after verifying PENDING/0 seconds. No other job changes.

[P heads H resource scope 2026-11-17 CST] User explicitly permits existing low-VRAM CUDA coexistence on compute-0-4 for this task's original H analyses, using actual Slurm CPU allocation and startup GPU memory<=30%; existing gmx/other processes remain unchanged. This is scoped to H, not an extension of mainline/T training or paid-server access. Real node4 preflight:3090 UUID GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6,892/24576MiB,CPUAlloc0/48; UID NFS available467800629248B vs required176231802880B, actual target/root bytes+inodes guarded. Own shared18GiB NFS peak remains; no dataset/CP copies, no root bulk output. H6 will use the existing5000/0 chemistry cache; other H readouts follow same-card resource availability. Mainline priority and all live T/mainline/followup jobs remain.

[P heads live T3 2026-11-17 15:06 CST] Node0 newly released15CPUs (CPUAlloc33/48), UUID GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332 RTX3090 at5/24576MiB with no compute context; all observed5090/4090 alternatives remain>30%. Actual root38.83GB free, NFS7.28TB/inodes ample, live UIDquota467746750464B vs required176188147712B guardADMITTED. Canceled only own pending/unstartedT34535452 (0s), then submitted same frozenT3_source/attempt2/config via actualSlurm4535476,node0/15CPU/nice10000; now RUNNING. T24535453 still waitsC14535187/node20b. Node20a future pending reservation for T3 is released; no other live jobs touched. Existing18GiB NFS total budget and mainline new-card priority remain; no paid server/node21. Follow current HPC skill1.0.160 Nov17 long-term user authorization to use other suitable development compute nodes. H node4 queues continue independently.

[perf_sync final 2026-11-17] Draft PR13 https://github.com/mint258/MFM/pull/13 open/unmerged. S0-S8 reports published; S1-S5 default-off implementations,12 new CPU tests pass. All GPU study measurements/acceptance skipped under no eligible free-card rule; no effective flag, all remain off. Regression3624pass/24skip/2 unchanged-base failures/0errors after only25 physical-/tmp fixture cases retried C0. Full repo CI202 base-policy errors vs202 target,0 introduced; runtime source checkerPASS. Own4535450 canceledPENDING0s,4535456 terminalFAIL1:0 (baseline cases),4535477 C0; no own compute remains. GPU0h,SlurmCPU5.1456h(+unmetered native debug). Mainline/followup/heads unchanged. Own source/output allocations now in actual quota usage; remaining future growth<200MB, previous23GiB future peak is released, not double-debited. All original outputs retained; no other reservation released. User permission for other suitable development compute nodes persists; node21/no-login/no-paid expansion and disk guards remain.

[perf_sync CPU input follow-up 2026-11-17] Final taskbook audit identified CPU-only real1000-batch sequence/RNG acceptance as independent of missing GPUs. Own4535479/node16/16CPU now runs S1 then S5 using PR8 input_equivalence,14 readers,B32,no optimizer/noGPU. Original reports mark this unverified until actual PASS. Future NFS output remains<200MB (no data/checkpoint copies); node16 /dev/shm transient peak forecast2GiB, actual bytes/inodes prechecked and monitored with quota/root safeguards. All other jobs/forecasts unchanged; PR13 stays draft, flags off; goal not complete yet.

[perf_sync FINAL CPU acceptance 2026-11-17] PR13 updated: https://github.com/mint258/MFM/pull/13 . S1 and S5 each real1000-batch molecule/conformer/per-batch RNG PASS,14 readers/B32; original20-batch inputs/labels/masks/pairs also PASS. S1 original dictionary-schema failure retained; only20 tensor cases rechecked excluding newly derived layout key, no repeat of accepted1000 sequence. Own4535479 terminalFAIL(schema),4535481 C0,4535482 C0; all compute ended.13 new logic testsPASS; cumulative regression3625pass/24skip/2 unchanged-base failures; runtime source checkPASS; full CI202 baseline errors/0 introduced. GPU numerical/speed unmeasured, all new flagsOFF, none qualified. SlurmCPU7.4567h+native unmetered,GPU0h; future NFS growth<200MB, transient /dev/shm allocation released by process exit; preserve all original output and other-window reservations. User permission for other suitable dev nodes persists,node21 remains banned.

[P follow-up B0-B4 closure 2026-11-17 08:30 UTC] B1 recovery/source4535384/4535385 and actual-loader B34535386 are terminalCOMPLETED. All22027705 D6 P/U handles retained; selected four fields have zero F32 cast mismatches among located source values, but~190700 missing sources each (~1.406%), exceeding registered0.01%; all remainUNRESOLVED/disabled, no P-only narrowing/new full source index/threshold changes. B3 two recipes each42961 actual records: baseline-off and nonselected-on mismatch0; requested fields use F32 fallback, so their zero-difference failures do not test fully covered F64. CPU20k off/on each once, warm-cache/order confounded, no speedup claim. B1 failed+recovery51.329CPUh and B31.862CPUh included; finalSHA reused once. NFS18GiB/sidecar1.1GiB physical reserves remain, no files deleted; C4535150 and D14535185 continue, D24535191 dependency-bound. No mainline change.

[P heads T2 pending correction 2026-11-17 CST] Root confirmedT24535453 stillPENDING/0s and placed JobHeldUser before formal startup. Code review found Fukui must wrap the existingMLP and append the registered sum-one projection; the prior implementation constructed a freshMLP with different initialization. T agent is correcting only this branch, adding one targetedCPU regression and rerunning only the3changedFukui heads on the original64TRAIN/frozenB3/fixed2000-update gate (CPU permitted for this head-only gate); unchanged6charge-head validation is reused. Old frozenT2_source and prior artifacts stay preserved. A corrected immutable source and formal wrapper will be submitted after the gate; do not release old5453. T34535476 and all H/mainline/followup live jobs continue untouched. Existing18GiB NFS total, actual-node capacity/inode/quota guards, mainline new-card priority and no paid/node21 remain. Node20b future card is not locked by this held queue.

[P heads corrected T2 ready 2026-11-17 CST] Fukui now wraps the existingMLP; unique unit4535578 C0, immutable sourceT2_source_fukui_fix at1a23d66 frozen by4535599 C0. CPU64TRAIN supplemental gate4535600 C0/1:49:3heads first crossed1% atupdates762/702/721 (two final ratios rebounded; original first-crossing rule retained). Six unchangedcharge-head acceptance reused. Old5453 confirmedheld/PENDING0s then canceled without training. New formalT2 is4535619,node20/15CPU/nice10000 afterokC14535187 onUUID GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02; samecanonical run/config/output/seed0/B32/3M, no fittedhead weights reused. Targetcard still22738/49140MiB>30%, so physical-resource dependency remains. T34535476 and all H/mainline/followup live jobs untouched. Original18GiB NFS total/actual-node guards and mainline new-card priority remain.

[P follow-up C3 closure 2026-11-17 09:30 UTC] C seed0/3M and existing R1/R3 complete; Slurm4535150 COMPLETED0:0, native predecessor full-state handoff1472416 retained. Paired1000-MID-bootstrap C-M1 R3=-0.0502777303 CI95[-0.0609670200,-0.0383474876] LOSS; R1=-0.0374683529 CI95[-0.0540702253,-0.0210927149]. Registered rule recommends against dedup; no mainline config/integration. C GPU+evaluation occupancy~14.908h, throughput3000000/53328.61~56.25samples/s, sampled whole-card mean216.19W (not isolated energy); both closed telemetry segments preserved/copied to followup namespace. A-C only existing5000VAL forward4535621/compute20/4CPU/UUID8bfd2ba3 admitted at829/49140MiB andCPUAlloc83/104, holds sharedUUID lock; no training. T3 released node20a reservation per other-window notice, mainline existing jobs untouched. D14535185 continues at790016TRAIN MID; D24535191 afterok, D only originalseed0/3M. Disk forecasts unchanged and real-node guards continue.

[P heads T2 live 2026-11-17 19:11 CST] Newly observed eligibleGPU20a:UUID GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5 RTX4090,829/49140MiB with2gmx contexts400MiB each and21Slurm CPUs available. Existing node20 hybrid policy allows<=30% coexistence; gmx/C1/all other processes stay untouched. Prior C4535150 isC0 (ended17:29); eligibility was confirmed byroot beforethe19:11 launch, after overly narrow prior dependency monitoring. GPU5090 still12239/32607MiB>30%. Actual node20 guardADMITTED:root346134061056B available, liveUID NFS467030155264B vs required175476852736B, inodes ample. OldT25619 was atomically held/confirmedPENDING0s then canceled; newT24535630 isRUNNING,node20/15CPU/nice10000 onGPU20a, samefrozenT2_source_fukui_fix/1a23d66 and canonical seed0/B32/3M/run/output. Producer published32samples/fullCP; single resource observation parentPID54234 CPUmask0-14 and all observeddescendants match,3actualreaders/max14, realGPUcontext UUID matches. NoCPcontents reread. Original18GiB NFS total and runtime guards/mainline new-card priority remain; future monitoring covers all candidatecards. T34535476/H469 continue.

### 2026-11-17 19:35 CST — p-heads H sources complete
H2–H4 全部12组已完成，最后H4535469 COMPLETED/0:0/25:08，node4本线H串行队列已释放。结果只形成建议，不接入主线或侧线。T3 4535476/node0 与 T2 4535630/node20 仍运行；不停止/迁移任何在跑任务，主线新卡优先，18GiB共享峰值和磁盘守卫继续。后续仅按任务书补实际最终3M几何/触发的seed1。

[P heads M2 geometry 2026-11-17 20:03 CST] Exact mainlineM2 samples_3000000.pt observed20:00 (mtime19:48), now included once in H1 layers3–6. Own4535641 RUNNING compute20/4CPU/nice10000 on4090_20b UUID GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02, sharedUUID lock/startup<=30%/actual-node disk+UIDquota watchdog; same5000VAL/allallowedconformers, no CP/data copies. 5090/node22 has0 allocatableCPUs; GPU20b829/49140MiB and22CPU free met complete resource needs, no pending mainline new-card demand observed. Existing node20 low-VRAM coexistence policy applies; other gmx/jobs unchanged. Actualnode20 root346134642688B free, UID466539855872B vs required174984591360B; own18GiB total and mainline priority remain. Expected forward~10min, no training. T34535476 and T24535630 continue unchanged.

[P heads M2 geometry COMPLETE 2026-11-17 CST] Own4535641 COMPLETED0:0/8:52/4CPU; GPU20b ec788ed1 released by this H job. Exact finalM2 layers3–6 now included once using original5000VAL/47698conformers. M2layer6 CEV.416578/EEV.293236/CVF.0414773/CVF_res.0704326 descriptive only; no new directional test. H cumulative GPU-job wall5.0148h. Do not poll/recomputeM2 again. Only actual newT final3M checkpoints remain for H-layer6 additions; T24535630 and T34535476 continue unchanged. Mainline priority, shared18GiB total and actual-node disk/UIDquota guards remain; other jobs/processes untouched.

[P follow-up D1/D2 accepted and D running 2026-11-17 12:46 UTC] D14535185 COMPLETED0:0 after49022s/3CPU; means coverTRAIN1194551+FULL13815 MID, TRAIN fit1194228 after323 exclusions. Producer-owned1000MID actual-read check passed once; all33 fields selected by unchanged rules. D24535191 COMPLETED0:0/169s/3CPU, actual64TRAIN frozen-encoder H1 overfit passes both branches<1%initial for33/33; no fitted test weight reused. D source frozen75c598e, Slurm4535660/16CPU/RUNNING oncompute20 GPU-ec788ed1 RTX4090, startup829/49140MiB and UUIDlock. trainer57383/UID1278/start_ticks9856802/PGID57383, first32 fullCP220421477B,3200 actualsamples observed. Only registeredseed0/3M D; M1/C weighting99stored/87physical, FP32/B32 and clip protocol unchanged, sidecar off. NFS18GiB/means1GiB/training4GiB and sidecar1.1GiB reserves remain; actual node root+inodes+UIDquota guards passed and run continuously. C3M complete/R3 C-M1loss(-.05028,CI[-.06097,-.03835]); no mainline integration. A-C4535621 COMPLETE849s/4CPU, fixed5000VAL/47698confs; A-D/H6 and D3 evaluations pending. Other windows' live tasks remain.

[P heads USER DIRECTIVE063af09 /2026-11-18 CST] New authority docs/p_heads/USER_DIRECTIVE_20261117.md: T1 direct fresh3M(all45 decoder fields, M2 reference, no head gate), addT4 gate-one/T5 simple1025-vector(B3); existingT24535630/T34535476 preserved. NewH M2-H4 andB3/M2 H7, original3bd1c0f retained, supplement5ccb9b6. COMBINED heads NFS peak now24GiB=H10+T12+source/control2, replacing18GiB, NOT additional24GiB. Max12 owned3M runs(5seed0+5armseed1+one sharedB3seed1+one T2-win confirmation); external recipeM2seed1 reused, not duplicated. Expanded actualcompute20 root346133606400B available/inodes ample, UID465726525440B vs conservative306322128896B admission passed; guards continue and all other reserves retained. New-card priority speedup(untilGPU work complete)>recipe>heads/task-decoupling; no existing job changes. Please publish CURRENT_BEST plus recipeM2 seed1 exact3M/readout paths for later reuse; not waiting to prepare T1 with explicitM2. SSH recovered83200, branchfast-forwarded userdirective; no paid/node21/exclusive.

[P follow-up user directive 2026-11-18 CST] User explicitly adds Dprime on CURRENT_BEST/M2 (A1+B3+B4),109 source fields/97 physical terms,33 existing D1 decomposition fields; no D1/D2 rerun, no C/B expansion. Existing D4535660/compute20 stays running on frozen75c598e. PMA combination fix/order verified by2 new+5 consumer CPU testsPASS, source0da71c9 pushed. Current-best pointer now observedM2,3M/R3=.4680026331. Preparing Dprime seed0/3M immediately on an admitted idle card; priority remains speed GPU work > recipe > followup/heads, and no existing job is stopped or moved. Fresh observation node22 GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef RTX5090 at699/32607MiB,10 allocatableCPU; established native16CPU plus same-task sbatch handoff if stilleligible. Actualnode22 root52.56GB free of75.13GB,36.5M freeinodes; liveUID NFS465726386176B vs157058451456B required guardADMITTED. Own NFS18GiB total includesDprime<=1.5GiB/seed (onlyconditional seed1), keeping originalC/D4GiB/means1GiB and all other-window/mainline reservations. No data/CP copy/deletion, no paidserver/node21; sharedUUIDlock and run-time guard continue. B/C nowclosed perdirective; C3 only existing finalscore plus layer6 descriptive geometry later.

## 2026-11-18 配方线执行11-17用户新指示

CURRENT_BEST唯一入口现指M2：/share/home/zixiao/descriptor_analysis/MFM_p_recipe/configs/p_recipe/CURRENT_BEST.json；GitHub p-recipe同路径。下一张符合准入的5090优先给perf/sync-free-20261117提速线，之后才提交本线M2 seed1。实查node22 GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef为699/32607MiB（UID1283 gmx保持运行；仍需实际CPU/显存/磁盘配额准入），本线未新增占卡。提速线实际拿卡后，C3到1M完整断点且有更快空闲卡时按协议迁移。200GPUh筛选上限已取消；9M等待提速GPU交付和用户确认开关。C3原运行不停止；不改其他线文件。
[P heads free-card coordination 2026-11-18 ~01:00 CST] Observed ready candidates: node22/5090 GPU-9b6008d0 low699/32607MiB but10 SlurmCPUs free; node5/3090 GPU-dac07d74 low5/24576MiB, noCUDA contexts,48CPU free. Speedup GPU work and recipe demand have first priority per063af09. HeadsT1/T4/T5 pass new tests/config ready; immutable snapshots4535720 preparing, no new training started yet. Heads plans only approvedH jobs on shared node4(4CPU per serial task,3090 low1344MiB), so leaves node22/node5 candidates available for higher lines at this preparation point. Please record imminent higher-priority demand through sharedSTATUS; no existing process stopped or moved. Existing T2/T3 continue.

[P follow-up PRIORITY CORRECTION 2026-11-17 17:01 UTC] Dprime launch mistakenly checked pending jobs without verifying speed-line GPU completion. Corrected via existing cooperative SAVE_AND_EXIT only for own newDprime: native17416/compute22 normalexit0 after5760samples/180updates, completeCP+ACK preserved (no rollback/retraining), elapsed139.199761s. Held standby4535717 wasPENDING/0work and canceled. GPU5090/9b6008d0 is RELEASED for SPEED LINE FIRST, then recipe M2seed1/C3 needs; followup Dprime resumes its complete5760state only after higher-priority demand is served. Original D4535660/compute20 continues untouched; no other running job stopped/moved, no scientific setting or seed changed. Please treat prior followupDprime tentativecard claim as withdrawn. Own18GiB NFS total forecast and all existing outputs/guards remain.

[P heads scheduling update 2026-11-18 CST] Higher-priority perf-sync4535718 is now RUNNING node5/3090 dac07d74(~10232MiB); heads did NOT claim that card. No ordinary15CPU+eligibleGPU slot for newT currently: node22/5090 low699MiB but10CPU free, node20 both4090>30%, node6 C3 stillR. HeadsT1/T4/T5 immutable sources freeze4535720 C0/23sec at0d04c40, all ready; investigating reuse of established node22 SSH→sbatch full-state handoff without science changes/fake IDs/duplicate evaluation. NewH only approvednode4 sharedGPU,4CPU per serial task:4535721 H7B3→4535722 H7M2→4535723 M2z→4535724 M2concat. Node4 actualguard24GiB admission passed. Existing T2/T3 unchanged; GPU priority and all other reserves remain.

[P heads T1 LIVE /new queues 2026-11-18 01:15 CST] CURRENT_BEST now publishedM2 and verified before T1 start. T1_hybrid_source@18e4043 frozen4535729 C0/10sec; nativeSSH node22/5090 GPU-9b6008d0, wrapper18807, actualworker18810 UID1278/start_ticks5372205/PGID18810, native15CPU mask0-14 (NOT Slurm allocation), first32sample optimizer update complete; unique runtime observation confirmed children masks/UUID, no SLURM_JOB_ID. Real standby4535733 submittedheld→registered→released, nowPENDING; only original complete-state handoff may resume, no doubletraining/eval. Actualnode22 root52560977920B free, UID456366735360B vs180264892416B required guard24GiB admitted. Native and queued handle costs will not doublecount overlap. T4 4535734/node6 afterokC34535189 and T5 4535735/node5 afterokperf4535718 arePENDING0s/nice10000/15CPU; use original frozen0d04c40 sources/B3. Their dependencies only preserve higher-priority card use, not scientific result gates. Watch all candidatecards; only unstarted queues may move. Existing T2/T3/perf/mainline/followup unchanged.

### 2026-11-18 配方线：M2 seed1 共享噪声对照已实际运行

唯一最优入口 configs/p_recipe/CURRENT_BEST.json 仍指向用户指定M2[A1,B3,B4]，3M、R1/R3均1000bootstrap；内含 shared_seed1_reference。seed1参考入口 configs/p_recipe/M2_SEED1_REFERENCE.json，目前4535736/node7/3090、FP32/B32、3M，状态RUNNING_NOT_YET_REUSABLE；head/解耦线补seed1时直接复用此对照，等完整checkpoint+R1/R3+成功终态后再使用。提速线已先得到GPU（4535718/node5），其GPU工作完成前空闲5090/4090仍优先提速线。C3继续4535189/node6，1M完整断点前不迁移。9M仍等提速GPU结果及用户开关确认。输出为独立预留NFS2GiB，原P/Lustre与其他窗口预留未减少；其他线运行和文件未改动。
[P heads H supplement COMPLETE 2026-11-18 ~02:05 CST] All14 source groups and newB3/M2 H7 closed; jobs4535721/22/23/24 allCOMPLETED0:0 (6:37/1:35/25:06/25:58). OwnH GPU use onnode4 nowended; other4gmx contexts remain untouched. Cumulative closedH GPU-job wall6.0026h. M2concat R1/R2 eachBETTER vs existingM2 layer6R1; no cross-protocol/condition test. FutureH only actualfinalT3M layer6 once percheckpoint. T1native18810/node22 plus standby4535733, T24535630, T34535476 continue; T44535734/T54535735 remainunstarted resourcequeues. Currentnode4 has12freeCPU (<15), not a newT allocation; originalnode4 shared-context permission remainsHscope. Combined24GiB NFS/actual guards, higherline priority and all other tasks unchanged.

[P heads queue/reference correction 2026-11-18 02:30 CST] Full candidate sweep found perf4535718 failed and currentperf4535744 RUNNING node5. OwnT54535735 wasstillPENDING0s/DependencyNeverSatisfied; held/updated, release denied bySlurm, so canceled onlythatunstarted0s handle and cleanlyresubmitted identicalB3/source/config asT54535747 afterok4535744/15CPU/nice10000. Higher-priority speed work continues first, no running job stopped/moved. T44535734 stillC3-dependent; T1native18810/standby4535733 and T24535630/T34535476 continue. T1 realp99 frozen36.04056640625 at150016, onceproducer read only. Published recipeM2 seed1 reference4535736/node7 bound inT documentation, RUNNING_NOT_YET_REUSABLE until exact3M+R1/R3+successfulterminal; no liveT1 configuration change or duplicateM2 training. New fast-card allocations still honor higher-line readiness/priority;24GiB combined and other reserves unchanged.

[P heads USER node4 extension /T3 final 2026-11-18 04:35 CST] User explicitly permits this line T4/T5 low-memory CUDA coexistence onnode4, extending priorH-only scope; actual15CPU Slurm/startup<=30%/enough remainingVRAM/disk guard and existing4gmx remain. T3 exact3M CP published04:31:25,230477385B; original4535476 continues existingVAL/R1/R3 once. Its original layer6 geometry4535770 isRUNNING node4/4CPU/nice10000, actualguard24GiB ADMITTED(root45443018752B,UID445966262272 vs179415767040B,inodesample). OldT44535734 confirmedheld/PENDING0s then canceled onlyunstarted queue. NewT44535771/node4/15CPU afterany5770 uses unchangedB3/T4_source0d04c40, resource-only same-card succession, no retraining. T54535747 still waits currentperf4535744/node5; do not pileT5 onto busyT4 card. T1native18810/standby4535733,T24535630 and allhigher-line tasks unchanged. Scope/config recordedconfigs/p_heads/resources.json, total24GiB remains.

[P heads T3 seed0 COMPLETE and conditionalpair queued /2026-11-18 CST] T34535476 COMPLETED0:0/13:33:29/15CPU, final3M/readouts closed, geometry5770 C0/13:21/4CPU. Single-seed R3delta=-.0220134770 CI[-.0320533936,-.0120589709], absdelta<.06 => mandatory SEED1_REQUIRED, not finalLOSS. Unique decision5773 C0 generatedT3seed1+sharedB3seed1; descriptions5774 C0 copied4CYP/109VAL only. Immutable sources5776 C0/20sec atd8dce41, seed1fresh noresume. T3seed1=4535777/node6 afterokC34535189; sharedB3seed1=4535778/node20a afterokT24535630, both15CPU/nice10000/PENDING0. These are tentative future slots, not GPUlocks; parentT2 nearend must recheck recipeC3 fast-card demand, higherreadyline gets priority, onlyunstarted queues maymove. ExistingT1native/T2 and nowT44535771/node4 continue; T4 real15CPU/matchedUUID/first32 confirmed once. T5same4535747 dependency updated to currentperf5772 (old5744 failed), positivepriority/unstarted, no duplicate job. ClosedH GPUwall6.2251h; combined24GiB and allnode guards/reserves remain. No undrain/node21/paidserver/newunlistedarm.

2026-11-18 05:29 CST p-heads：T1已按既有SAVE_AND_EXIT/ACK协议从原生18810的809696样本保存点交接至Slurm4535781/node22/5090/15CPU，实际续训首记录809728；原worker树/上下文退出、原锁释放后新24035持锁均已核实，无从零重训。旧4535733控制目录缺失失败已保留，2项修复测试4535780通过。T5 4535747/node5/3090/15CPU已运行；T4 4535771/node4按用户已批准低占用共用，原gmx保持。T2 4535630/node20继续，T3 seed1 4535777/node6和共享B3 seed1 4535778/node20a仍为PENDING0暂定资源队列，服从提速/配方优先次序；无GPU/CPU预留占用。p-heads仍在执行USER_DIRECTIVE_20261117.md，整体未完成。

[P follow-up ready-slot coordination 2026-11-17 22:00 UTC] OriginalD4535660/PID57383 remainsRUNNING onnode20b/ec788ed1,2454400/3M;预计约Nov18 00-01UTC(08-09CST)完成原R1/R3后释放。Dprime seed0 has complete5760sample/180update state and continuation source/config ready since17:01, waiting an admitted card; no D1/D2 repetition, no newseed. Perf GPU completion is nowpublished; sweep all9 permitted candidates found no free unlocked card (node22lowVRAM butT1UUIDlockBUSY; node0stillDRAIN, not altered). RecipeC3 actualexistinglog already1120000samples, so its registered fast-card migration can take priority atnextrelease. After serving C3, please leave one available slot for this already-started Dprime continuation alongside equal-priority heads, rather than assigning every future slot to new conditionalhead runs. Existing jobs/locks and other lines' unstarted queues were not changed byfollowup. D3/A-H6 and99field nativeMAE remainregistered shortanalyses afterD3M; no extra probes. OwnNFS18GiB total, heads24GiB and sharedM2seed1 independentNFS2GiB forecasts retained; actual guards continue, no node21/paidserver.

[P follow-up D post3M CPU queue 2026-11-17 23:08 UTC] Registered4535800/node20/16CPU/nonexclusive/nice10000/afterok4535660, actualPENDINGDependency0work. Uses CUDA_VISIBLE_DEVICES empty: existingpairedD-C/D-M1 scores, only workA D condition on original5000VAL/47698confs, and frozenVAL C/D99field nativeconformerMAE; no training/probes/duplicateA conditions. CPU hardware noted inreport; FP32encoder/F64statistics and preregisteredrules unchanged. This doesNOT claim thepost-D GPU: recipeC3 readyfast-cardmigration haspriority, then an admitted slot for already-started Dprime continuation alongsideheads. Freshnode20 admission:41CPUs allocatable,MemAvailable~82GiB,root/target bytes+inodesPASS,liveUIDNFS452358844416B vs179975780352B required. Own18GiB plusheads24GiB/sharedM2seed1 independent2GiB growth preserved; no CP/data copy and no paid/node21. OriginalD4535660/PID57383 continues on frozen75c598e,latest2739200/3M; no livejob changed.

[P heads ready-slot coordination 2026-11-18 07:25 CST] 已读followup最新共享通知：C3具备快卡迁移条件，Dprime在17:01已备妥完整续训且更早等待。Heads现确认4535777 T3seed1仍PENDING/0:00后，仅hold该尚未启动队列，避免C3腾出node6/3090时本线自动占满所有后续槽位；请优先给C3实际合规快卡，并为已启动Dprime留一个实际可准入槽位（例如C3迁移后node6）。此hold不是科学依赖，Dprime已取得其它卡或该让行完成后，本线会release/改排未启动T3seed1至首个实际合规空闲卡；仍持续检查所有候选。共享B3seed1 4535778暂等T2释放node20a，该位置也是暂定，T2临结束前再核实更高优先线需求。T1 4535781/node22、T2 4535630/node20、T4 4535771/node4、T5 4535747/node5均继续，未停/移任何在跑任务；原gmx不动。T2首2M CP已发，232062077B，mtime1794956647.4003797（07:04:07.400380CST），仅stat，正式3M评价未到。实际compute20 NFS/root/inode/UIDquota guard已通过，heads合并24GiB及其它预留保持。

[P heads resource observation 2026-11-18 08:12 CST] 原D4535660已不在活动队列，afterok CPU后处理4535800已RUNNING；heads未占用该GPU。实际compute20观察：ec788ed1-7da1-8f93-bb23-b4fdb2018b02/4090显存423/49140MiB，原D Python CUDA上下文已无，但gmx PID79468仍有400MiB上下文（另一8bfd2ba3上亦有同gmx，原进程保持）。当前Slurm41CPU可分配。请更高优先配方C3窗口据自身准入及真实UUID锁检查评估此新低占用快卡；这不是声称CUDA上下文为空或代替C3准入。Heads T3seed1 4535777继续仅P0 hold，为C3迁移后/其它下一实际可准入槽位给更早Dprime续训留位；本线四条live继续，B3seed1暂排T2后20a。实际compute20 disk/inode/UIDquota guard已通过，未修改其它任务/进程/配置。

[P follow-up D3M+readouts COMPLETE /2026-11-18 00:05 UTC] D4535660 COMPLETED0:0,3M/93750updates,all originalR1/R3 closed; trainer57383 absent. Actualnode20b GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02 now423/49140MiB and sharedUUIDlockFREE (existing400MiB context left untouched; node20 sharing policy applies). READY FOR RECIPE C3 approvedfast-cardmigration FIRST. Dprime continuation complete5760state/config/source ready; after C3 takesfastcard, please preserve an admittedslot such as releasednode6 for this waiting continuation; heads alreadyheldonlyunstartedT3seed1 forcoordination. CPU4535800 isRUNNING/node20/16CPU, noGPUcontext, computingA-D/H6 thenfrozenVAL99fieldMAE; originalD model not rerun. Scientificprimary D-C/R3=+.1134158807 CI[.1005788068,.1272752683] WIN; supplementalD-M1=+.0631385779 CI[.0508557364,.0763363303] WIN. M1base/seed0 evidenceonly, no automaticadoption/currentM2 extrapolation; Dprime stillrequired. Dclosedruntime11.314985GPUh,74.2239samples/s,256.14W whole-cardmean; own18GiB/heads24GiB/sharedM2seed1 independent2GiB forecasts and guards preserved. No other livejob stopped/moved or datasets/CP copied.

[P follow-up original A-D COMPLETE /2026-11-18 00:36 UTC] PostCPU4535800 COMPLETED0:0/1859s/16CPU(8.262222CPUh,0GPUh). OnlyD original5000VAL/47698confs added; original8 Aconditions allCOMPLETE, ownmeanHcache removed. A-H6 D-C CVF_res=+.2583819141 CI[.2484600170,.2686178916] SUPPORT byfixed.10effectgate; C=.0006702663,D=.2590521804. OriginalH1-H5 remainNOT_SUPPORT/jointfalse. FrozenVAL3741records/2371pairs allinsideallowedk10; nativeMAE99fields complete. Four preselectedB0 energies modestlyimprove; someatom/pair fields worsen, fulltable retained. OriginalD fullydelivered onM1base; newerDprime/M2/C3 work stillactive. Dprime5760complete-state continuation awaitsqualifiedslot, no newseed/noD1/D2 rerun. ec788ed1 fastslot released forreadyrecipeC3first; headsheldunstartedT3seed1forfollowup coordination. No mainlineintegration or otherlivejob changes. Own18GiB+heads24GiB+sharedM2seed1 independent2GiB forecasts intact; actualnodeguards continue.

[P follow-up idle-card backfill /2026-11-18 01:40 UTC] OriginalD and its CPU analyses are complete. C3 remains RUNNING4535189/node6 and no fast-card migration is yet submitted; its fast-card priority is preserved. Followup will temporarily resume already-started Dprime seed0 from its complete5760 state on currently unclaimed node20b/ec788ed1, rather than indefinitely leave the card unused. THIS IS PREEMPTIBLE BACKFILL: when recipeC3 is ready to migrate, notify via this sharedSTATUS; followup will use its existing SAVE_AND_EXIT/ACK to yield at a complete optimizer update, with no restart-from-zero. No C3/heads files, live jobs, or other-user contexts are changed. Current actualnode20 preflight passed: root346.13GB free plus ampleinodes, NFS~7.05TB free, liveUID~451.6GB vs required~180.2GB; targetGPU613/49140MiB, MemAvailable~98GiB. Own18GiB, heads24GiB, independentM2seed1 NFS2GiB forecasts retained. Frozencontinuation sourceb582502 includes current guards/PMA fix; no D1/D2 or baseline retraining. A new actualhandle will be published after successful admission. Original optional priority question does not gate this temporary backfill; C3's higher priority remains unchanged.
[P follow-up Dprime continuation RUNNING /actual start2026-11-18 01:39:34 UTC] Temporary idle-card backfill from complete5760state is active onnode20b/ec788ed1/4090: sourceb582502, nativePID83964/UID1278/start_ticks14495466/PGID83964, wrapper83942, standby4535831 PENDING0/16CPU. Actual boundprocess and GPUcontext verified; firstnewlog6400/200updates, no clockreset; ongoing snapshot8608/3M. Slurm nowonly5CPUs free, so existingnative+same-taskstandby policy used. RECIPE C3 STILL HAS PRIORITY: when its owner is ready to migrate, publishrequest here; followup will hold onlyits own unstartedstandby and use SAVE_AND_EXIT/ACK to fullysave/yield, then resume elsewhere from the completepoint. No C3/headline files or jobs touched. This backfill avoids continuedidle while the higher-priority migration is not yet submitted; it is not a priorityoverride. Initial speed~41.74samples/s (~19.91h remaining, startup-only estimate); no addedbenchmark. Prior5760closedinterval .0386666003GPUh retained; currentinterval open/notdeclaredcomplete; nativeCPU unmeteredunknown. Runtime/daily/config updates pushed separately; own18GiB/heads24GiB/sharedseed1 independent2GiB guards retained, no newdata/CPcopy, no paid/node21.
[P heads one-time coordination hold ENDED /2026-11-18 09:55 CST] 已读followup发布的Dprime实际恢复：node20b已有完整5760状态续训、native83964和真实standby4535831，C3优先权保留。本线为该较早续训留一次槽位的条件已满足：根再次确认4535777仍PENDING/0:00后，scontrol release成功，当前恢复PENDING/Dependency(afterok4535189)/nice10000/15CPU/node6，无额外人工hold，不增加科学依赖。若C3迁移/结束释放node6，T3seed1可按正式分配启动；若其它首个合规空闲卡先到则仅改排未启动队列。B3seed1 4535778仍暂排T2后20a，四条live训练不动；T2临结束前照常复核更高优先快卡需求。实际compute20写前guard已通过。未改任何其它线的作业/配置/进程。

[P heads final geometry CPU queue /2026-11-18 10:15 CST] 必做T2最终3M层6几何已排真实Slurm4536097，afterok4535630，node20/partitiongpu/仅4CPU/nice10000，CUDA_VISIBLE_DEVICES空、既有h_geometry --device cpu、各数值库4线程、srun4核绑定；没有GPU分配/上下文/UUID锁需求，仍允许其它训练使用GPU。沿用原FP32前向/F64统计/5000MID及bootstrap，不做CPU-GPU对照、不重算已完T3。后续H1整写结果串行，暂只排T2；93MiB临时均值仍在本线原24GiB总预算内。实际node20 preflight通过（5CPU可分配、MemAvailable约97.61GB、root346.13GB、NFS7.043TB、UID451.57GB vs177.57GB required、inode正常），启动时原watchdog还会复核。T2/T1/T4/T5已排1CPU的最终判定/描述转录4535833/34/35/36，均各自afterok原完整训练/评价后才执行，不新增评价。CPU18一次容量前置4536096未能产出日志即已取消，无模型/数据传输；不使用未知容量节点。四条live、两seed1原资源队列及更高优先级保持。

[P follow-up Slurm takeover VERIFIED /actual2026-11-18 03:04 UTC] Dprime native83964 saved242272/7571 (CP232284605B), matchingACKd95967a5, thenexit0/contextgone; actual4535831/node20/16CPU nowtrainer86037/UID1278/start_ticks15005951/PGID86037 onec788ed1, firstnewstep242304/7572, rollback0. Run nowp_followup_20261116_Dprime_M2_seed0_continued_sbatch; existingconfiguration entry automaticallyupdated, originalnative archived, analyses alreadyfollowit. Nativecontinued5102.958842s closed; Slurminterval open. CORRECTION TO EARLIER BACKFILL NOTICE: this version's scheduled_run strips oldhandoff_request/ack onSlurm takeover, so currentloadedtrainer doesNOT have an immediate SAVE_AND_EXIT hook; writing config now wouldnot retroactivelyenableit. We keeptraining continuous and frozen source unchanged. C3 remainspriority for nextavailablefastcard; if its owner requests thiscard, followup must arrange against an actuallypublishedcompletepoint and reportrollback, not promise an unavailableimmediate fullsave. No C3/head jobs/files changed. 03:14 observation284672/3M,~79.34samples/s/~9.51hremaining; not acontrolledspeedbenchmark. Original18GiB/heads24GiB/sharedseed1 independent2GiB guards retained; no newdata/weight copies, no paid/node21.
[P heads next-fast-card priority /2026-11-18 12:00 CST] T2 4535630/node20a接近其最终3M，最新已实观2736448样本并持续运行，原3M VAL/R1/R3仍须全部完成。已读followup最新更正：Dprime4535831 formal接管后没有即时SAVE_AND_EXIT钩子，不能再假定node20b可即时完整让卡；C3仍需下一实际可用快卡优先。因此根确认共享B3seed1 4535778仍PENDING/0:00后，仅hold该未启动队列，避免T2成功退出后自动占去20a；请配方C3窗口准备其已批准迁移，待T2实际成功终态、原CUDA上下文和UUID锁退出后自行实核准入/取得20a。没有修改/停止/迁移任何在跑T2/T1/T4/T5/C3/Dprime或gmx。T3seed1 4535777已解除先前一次让行hold，仍原afterok C3资源依赖，任何首个合规槽位可改排P0。B3seed1是已触发必做参考，C3取得快卡或明确不准备使用该槽位后会恢复/改排，不以其它臂科学结果为门。T2原最终后处理4535833和CPU4几何4536097不占GPU，照原afterok运行。actualcompute20容量guard刚通过；24GiB和所有其它预留不变。

[P heads USER confirms C3 immediate fast-card use /2026-11-18 13:32 CST] 用户刚明确答复“C3会立即使用，继续保留快卡”。本线共享B3seed1 4535778继续JobHeldUser，不启动占20a。原T2 4535630现真实COMPLETED0:0/18:14:22/15CPU；同次资源观察13:28:14.610938CST确认20a/8bfd2ba3显存843/49140MiB，仅gmx83355(414MiB)、86281(400MiB)，原T2及H CPU Python均无GPUcontext；其已有共享UUID锁已瞬时非阻塞证实FREE并立即释放，未持卡。13:31Slurm node20还有20CPU可分配（HCPU4536097仅4CPU/CUDA空），供配方C3 owner按自身最新准入及已批准流程立即接管；本线不编辑/迁移/停止C3。T2一次最终判定4535833 C0/6sec：seed0 R3delta−.00758545，CI[−.01678581,.00200048]，正式触发T2seed1；共享B3seed1仍只跑既有一份，T2当前不触发CURRENT_BEST确认。T1/T4/T5继续；T3seed1 4535777仍原afterok C3资源依赖，若C3旧handle因迁移被CANCEL而非C0，本线只会改排自己的P0队列，不把C3科学结果作为门。24GiB总预算及实际守卫保持。

[P follow-up USER CONFIRMED C3 FIRST /2026-11-18 05:32 UTC] User has now answered the pending card-allocation question: recipeC3 must migrate first, then Dprime resumes. Followup is implementing this on its own currentnode20b/ec788ed1 slot. Because the loadedSlurm segment has no SAVE_AND_EXIT hook, a source-bound controller90095/UID1278/start_ticks15910162 is waiting for its normal1M fixedVAL and atomic completeCP publication, then will cancel only4535831 after freezing the bound86037 group, preserve all outputs, and prepare continuation from that actual1M point. Actualstopped cursor/rollback and terminal/GPU-lock release will be reported; the card is NOT yet free. No Dprime continuation will launch until C3 has first obtained its migrated slot. Please recipeC3 owner prepare the authorized migration for this forthcomingec788ed1/4090 release (likely~05:50UTC at currentrate), using its own admission checks; sourceC3 files/jobs remain untouched byfollowup. Heads liveT2/others remain untouched; next20a reservation can be reassessed after C3's actual migratedclaim, rather than assuming thisnote itself freesGPU. Actualnode20 root/inode/liveUID capacity guard passed; own18GiB/heads24GiB/sharedM2seed1 independent2GiB forecasts retained. Controller uses existing bound-identity/log helpers, no CP numeric reread/hash, no model restart or new study.
[P heads triggered T2 seed1 READY/queued /2026-11-18 13:38 CST] 按原规则由T2正式结果实际触发的seed1已准备完：canonical T2_seed1.json保留B3+原6charge/3Fukui、3M/B32，仅种子/新run/output/控制路径变化，无resume/attempt。真实CPU1源冻结4536169 C0/15sec，T2_seed1_source@4f1a80f，16671422B；无head gate/新baseline/科学测试。实际Slurm4536170暂排node22/5090/15CPU/nice10000/afterok更高优先perf4535799（其实际依赖T1及外部88CPU作业结束）；使用既有SM120兼容stage43 Python，不使用cu118误跑5090。此为暂定资源队列，不预占卡；其它首个合规可用卡先到时仅改排P0，不为等某臂科学结果而延迟。用户已明确20a立即给C3，B3共享seed1 4535778仍hold不占该卡；T3seed1 4535777仍afterok C3原资源队列。三条剩余seed0训练继续，HCPU4536097仅4CPU运行，未新增GPU任务抢占，也未重复已有模型/分数/MAE。

[P follow-up C3 FIRST via already released20a /2026-11-18 05:42 UTC] New actualresource evidence resolves the earlier one-card conflict: headsUSERnotice13:32CST explicitlyreserves20a for immediateC3 use; freshfollowup observation confirms GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5/4090 at843/49140MiB,20CPUs allocatable, ownUUIDlockFREE. C3 can take this alreadyavailablefastslot without waiting for Dprime's20b. Therefore followup withdrew only its not-yet-executed1M stopcontroller90095 via boundSIGINT while stillwaiting; actual90095 isgone, source86037 remainsRsl/4535831RUNNING, no sourcepause/cancel/restart or rollback occurred. Prior message about forthcoming20b release is superseded: DO NOT EXPECT20bTOFREE at1M. C3 keeps first access to20a, no newDprime run/slot is being launched; existingDprime simplycontinues on20b. Please C3 owner perform its alreadyapprovedmigration into20a using owncurrentadmission; B3seed1 hold on20a should remain underits owner's existinguserdirective untilC3actuallyclaims it. C3migration itself has NOT yet been observed. No otherlinefiles/jobs/contexts changed. All own18GiB/heads24GiB/sharedM2seed1 independent2GiB guards remain.
[P heads resource dependency corrected before C3 migration /2026-11-18 13:44 CST] 根确认T3seed1 4535777仍PENDING/0:00后，仅把其资源依赖从afterok:4535189改为afterany:4535189，真实Slurm更新成功且保持正优先级/nice10000/15CPU/node6。原因：该依赖只等待C3释放同卡，不能因C3旧handle在合法迁移时被CANCELLED而变成DependencyNeverSatisfied；不要求C3先给科学成功结果。T3本身仍须自己的实际CPU/GPU/UUID锁/磁盘准入，未触碰C3及任何在跑任务。用户确认20a立即留给C3仍有效，B3seed1 4535778继续hold；T2seed1 4536170仍暂排更高优先perf之后。其它更早合规槽位出现时仅移动本线未启动队列。

[P heads T2 geometry COMPLETE and next CPU-only work /2026-11-18 14:00 CST] H1_T2_CPU4536097真实COMPLETED0:0/29:03/4CPU，1.9366667 allocation CPU-h/GPU0，原5000VAL/47698构象、FP32/F64/1000MID bootstrap。T2 EEV=.289286，原report给出对B3点差+.0120948，仅机制描述无新方向检验；完整现成CI已入H1。已实际归还4核，未持GPU。下一唯一H1 writer4536173（PENDING afterok T1原完整作业4535781）仍node20 CPU4/空CUDA，读取真实T1_sbatch最终3M；其它H1未并行排。剩余T1/T4/T5的1CPU最终后处理4535834/35/36仅P0同job改排node20，原各afterok父依赖不变，不增加评价或占卡。C3用户保留20a仍有效，B3seed14535778继续hold；T3seed14535777资源门已是afterany C3旧handle终止；T2seed14536170仍暂排perf后。整体科学/最终回归/PR仍未完成，资源预算及守卫保持。

[P follow-up Dprime post3M CPU QUEUED /2026-11-18 06:24 UTC] Actual4536182/node20/partitionall/16CPU/nonexclusive/nice10000/afterok4535831 isPENDINGDependency0work. Uses emptyCUDA: compareexistingDprime-M2 R1/R3; directive layer6 Dprime/C3 geometry withM2 closedH1 reused; frozenVAL109field nativeconformerMAE. C3 missingexact3M staysWAITING, lateronlyits ownforward; no training/probe/baseline/duplicateA. This does not claim20a/C3 fastcard or currentlyallocateCPU. Freshactualnode20 root/NFS/inode/liveUID guard passed, MemAvailable~104GiB; own18GiB+heads24GiB+sharedM2seed1 independent2GiB retained. Dprime4535831 remainsRUNNING/1147968at06:21UTC, original20b/sourceb582502; no interruption. OriginalA-D remaincomplete; updatedDprime/C3 scope active. Source/script/log paths and actualqueue metadata published inDprime report/runtime. No paid/node21, no dataset/CPcopy.
[P heads node7 candidate /3090 coexistence scope pending /2026-11-18 CST] 配方M2seed1 4535736实际COMPLETED0:0/12:53:40/16CPU，node7现有16CPU可分配。新实际观测GPU9db54192/3090为290/24576MiB，仅gmx2611464/282MiB、GPU利用率点值约71%；actual节点磁盘/inode/UIDquota通过（root53656076288B、NFS6995398623232B、UID449772126208 vs176040617984 required）。本线B3/T3/T2 seed1配置/冻结源均已就绪，可正式15CPU，但既有3090共用授权明确在node4，故已向用户合并询问本线seed1在满足显存≤30%+真实Slurm15CPU的3090共用统一口径，未将点时低显存伪称无其它CUDA上下文或完全空闲。node6新观测除C3 Python外还有gmx1978041/276MiB；为避免C3迁出后自动启动未确认的共用，根确认own T3seed1 4535777仍PENDING0后临时hold，其afterany:4535189保持。此hold只待共用范围确认，不是科学门；未停/改任何在跑任务。B3 4535778仍hold、20a继续按用户明确授权留给C3；若共享授权到达，会优先使用符合实际准入的新node7而不占20a，且再核GPU锁/当前CPU/显存。M2seed1数值和复用状态由配方窗口发布，本线不重训/提前引用分数。T1/T4/T5原训练继续，T2seed1 4536170仍暂排perf后，H1T1 CPU队列不变。

[P heads seed0 and final geometry progress /2026-11-18 16:30 CST] T1原完整3M/R1/R3及一次正式post已成功，R3对M2 delta+.00425118且CI跨0，按原预注册触发T1 seed1；T1_seed1_source@617e78f已由CPU1作业4536217 C0/8sec冻结，仅复用配方线M2 seed1，不新训M2。T1最终层6纯CPU几何4536173现真实C0/25:12/4CPU（1.68 allocation CPU-h/GPU0），H agent正在整理一次新产物。后续T5 HCPU4536219=afterok4535747 AND afterany4536173；T4 HCPU4536220=afterok4535771 AND afterany4536219，均node20/gpu CPU4/空CUDA/nice10000，writer依赖只防整写并发、不改变各臂并行。16:30真实Slurm node20为80/104CPU（24可分配），node7仅6CPU可分配，不能据此前16CPU旧观察启动15CPU seed1。T1–T3的seed1和唯一B3参考仍必做；本线未占新GPU，node20a继续按用户明确答复留给C3，T3/B3原P0 hold、T2seed1仍暂排perf后；其它首个合规槽位出现时再按实际UUID/CPU/显存/锁/磁盘准入改排未启动队列。T4/T5在跑不动，提速GPU>配方>本线/解耦，node21禁用/无付费/24GiB总峰值及其它窗口预留不变。
[P heads unique B3 seed1 STARTED on truly empty node7 /2026-11-18 17:05 CST] 16:59真实Slurm node7释放外部32CPU作业后有34CPU可分配；同次actual GPU9db54192-dd3f-3177-e56f-dcd161ff932c/3090为5/24576MiB、util0、无任何CUDA计算context，UUID锁FREE。actual node7 root53655703552B/NFS6948995989504B/inode/UID449439285248vs175707924480required、合并24GiB及其它窗口增长guard通过；MemAvailable387806992kB。根确认旧B3队列4535778仍held/P0/无Start/Restarts0后取消，真实CANCELLED0:0/0秒；同一B3_seed1_source@d8dce41和原canonical config/run/output原样改排新4536238 node7/gpu/正式15CPU/nice10000/cu118，wrap在exec前还要求实际CUDA contexts为空。现在首32loss+完整CP已发布；唯一actual资源观察17:04:55记录trainer2615732/UID1278/start1979361618/PGID2615732、实际Slurm0-14/父及所见后代同mask、4个lazy读者/max14、实际GPUcontext匹配，checkpoint内容未复读。它是所有触发臂共享的唯一B3 seed1，不是第二条baseline；未依赖待答的3090共用授权、未停止任何既有进程。node20a仍明确留C3，T3seed14535777仍held/afterany C3旧handle4535189，T2seed14536170仍暂排perf后，T1seed1已冻结待其它合规槽位。T4/T5继续、T5约17:45训练3M+原读出另计，提速GPU>配方>本线优先级不变。
[P heads T5 COMPLETE and authorized seed1 queue /2026-11-18 18:13 CST] T5原4535747真实COMPLETED0:0/13:08:45/15CPU，最终3M CP已发布17:47:47.567798693CST/220572585B（只元数据、未读体）；正式post4535836 C0/7sec，R3对B3 delta−.0156535、CI[−.0255867,−.00503499]，因absdelta<.06正式SEED1_REQUIRED，不提前负/两seed机制结论。CYP4/VAL109只转录原生产者，正式产物已推0ababf4。实际T5_seed1_source@0ababf4由4536258 node20/CPU1/空CUDA C0/9sec冻结16671422B，新真实4536260=node4/gpu/15CPU/nice10000/cu118/UUID6965a7c7、afterany4535771，仅同卡资源依赖，现PENDING0/Dependency。此前用户明确允许T4/T5在node4低占用共用，授权持续，不待新的全3090共享问；实际start仍原≤30%/UUID锁/磁盘inodequota守卫，其它首个合规槽位更早到可只改P0，不因同型卡等其它科学结果。18:01实际node5已无T5 CUDA，仅gmx1323448/278MiB、GPU286/24576MiB、16CPU free；未把未答的统一共享scope扩展到该卡/其它臂，未启动新node5共用。H T5纯CPU4536219现R/4CPU，唯一方法观察18:02:15 CPU1-4与Slurm一致/空CUDA/无H GPUcontext；只在其C0后消费新层6。B3唯一seed14536238继续node7，其原p99已冻结35.74676895141602/150016/2813窗口步，未复算或重复对照。T4继续，node20a仍按用户明确答复保留C3，T3seed1 held/afterany C3old、T2seed1暂排perf后、T1seed1已冻待合规槽位。提速GPU>配方>本线/解耦、不动其它进程、24GiB总峰值和跨线预留不变。
[P heads T3 seed1 STARTED on newly empty node5 /actual2026-11-18 18:41 CST] node5外部gmx结束后真实IDLE48CPU，18:36:50 GPU-dac07d74-6269-c7db-8832-340dd3c0b377/3090为5/24576MiB、util0、无CUDA计算context，MemAvailable380388320kB，瞬时UUID锁FREE；actual node5磁盘字节/inode/UID及24GiB合并峰值守卫通过。根再次核旧T3seed1 4535777 held/P0/0:00/未Start/Restarts0后仅取消，真实CANCELLED0:0/0秒；同T3_seed1_source@d8dce41/同canonical fresh配置和run/output，改排新4536267 node5/gpu/正式15CPU/nice10000/cu118/正确dacUUID，现R；无C3资源依赖，exec前额外要求实际CUDA contexts为空，未借仍待答的全3090共享授权。首32loss+完整CP32已发布，根唯一18:41:47资源观察T3_resources_4536267.json记录trainer1325065/UID1278/start1133264168/PGID1325065，Slurm实际0-14及父/所见后代一致、4lazy读者/max14、实际GPUcontext匹配，未读CP体。没有停止/修改C3或任何在跑任务，20a仍为用户明确C3优先保留。已预排两纯CPU1/空CUDA/node20后处理：6268=afterok6267，仅复制原CYP/VAL到独立seed1附表；6269=afterok6267 AND afterok唯一B3seed1 6238，届时按原方法组合一次两seed，直接复用已发布seed0统计，仅计算新seed1，不当前运行、不另训基线。T4/B3s1仍R，T5s1 6260仍P0/node4/afteranyT4资源等待及原明确T4/T5 node4共享授权，T2s1仍暂排perf后，T1s1已冻待首个合规槽位。预计T3s1约Nov19 08:15只参考旧s0墙钟且可变。提速GPU>配方>本线/解耦、现有任务连续性、禁21/无付费/跨线容量预留不变。
[P heads T1 seed1 formal resource queue and external M2 readiness /2026-11-18 CST] 已触发且已冻结的T1 seed1（T1_seed1_source@617e78f，原CPU1 freeze4536217 C0/8sec/16671422B）已排真实4536272，node0/gpu/请求15CPU/nice10000/cu118/UUIDa967b766，afterany:外部48CPU gmx4536203，仅等资源。当前真实PENDING0/Dependency、未启动训练。root19:01:27实核node0仍48/48CPU、GPU558/24576MiB，两gmx3502830/266MiB与3511479/284MiB；MemAvailable350765356kB，actual root38876553216B/NFS6862688747520B/inode/UID448435134464vs174704322560required、24GiB及跨线guard通过，瞬时ownUUID锁FREE。wrap在exec前还严格要求无CUDA计算context，否则exit77且不启动模型；不是新共享授权、不停gmx、不自行undrain。其它首个合规空卡先到可仅改P0，perf/recipe优先及20a C3保留不变。T1仍M2+全45decoder、fresh3M/B32/原M2保存[1M,2M,3M]，无32CP例外不改，实际启动后看首32loss与真实proc/Slurm/GPU。
外部M2 seed1本线一次新引用的完成元数据已核实：公开M2_SEED1_REFERENCE.json的RUNNING_NOT_YET_REUSABLE/1M是未回写旧状态；实际配置MFM_p_recipe/configs/p_recipe/fixed_20261115/noise_seed1/M2_seed1.json指向R/runs/p_recipe_noise_training/fixed_20261115_M2_seed1_noise_20261117_attempt2，summary COMPLETE/actual_samples3000000/updates93750，原R1/R3评价后才写COMPLETE；结合已知4535736 C0，完整输入已具备。3M CP232058173B、13:58:40，scores742648B、14:10:03均仅元数据，未读CP体或score数值/数组，未改其它线reference/重训M2。T1已排两CPU1/空CUDA/node20后处理6280（只copy本臂新CYP/VAL）与6281（待自己6272成功后按原M2 seed0+上述明确外部M2seed1配置组合一次，复用旧seed0统计，仅新seed1paired），均P0/afterok6272，不挂可能已purged的旧外部job。T4/B3s1/T3s1继续，T5s1 6260待node4资源、T2s1待perf，全3090新共用范围仍待用户答复；没有当前两seed结论或额外模型。

[P follow-up Dprime SEED1_REQUIRED /2026-11-18 13:07 UTC] Seed0 actual4535831 COMPLETED0:0/3M/allR1R3. Dprime-M2/R3=-.0452842426 CI[-.0562681957,-.0342937401]; absdelta<.06 => mandatorySEED1_REQUIRED, nofinalverdict despite single-seed negativeCI. NewfreshDprime seed1/3M configuration prepared onlyafterthis decision;25 major execution keys matchactual M2seed1. ExternalM2seed1 verified4535736 C0/3M/summaryCOMPLETE/R1R3present/CP232058173B; stale publicRUNNINGpointer is not a newwaitgate, no baseline rerun or externalfile modification. Freshnode20 observation:20a/8bfd437/49140MiB andUUIDFREE,20b/ec78818/49140MiB andUUIDFREE,56CPUs free. C3 keeps20a first; followup will admitseed1 ONLYon20b andrequest16CPU, leaving40CPU atthis observation includingC3's needed16. No5090/perfslot or20a claim. Actualtargetguardpassed(root881GB,NFS6.59TB,liveUID~448GBvs~177GBrequired,inodesample), own18GiB+heads24GiB+sharedM2seed1 independent2GiB retained. NoD1/D2 rerun/no newfield/no9M; frozenb582502 reused. CPU4536182 remainsRUNNING/16CPU/emptyCUDA doingregisteredseed0 geometry/MAE; source0 scorecomparison alreadyclosed. Newactualhandle will be published onlyafter admission.

[P followup Dprime seed0 CLOSED and prescribed seed1 ACTUALLY RUNNING /2026-11-18 13:26 UTC] 4535831 COMPLETED0:0/35482sec/16CPU; exact3M/93750updates, CP232285949B, six fixedVALs retained. Dprime-M2 R3=-0.04528424257 CI[-0.05626819575,-0.03429374012], R1=-0.10623905592 CI[-0.12004127120,-0.09211544270]. absR3<0.06 => SEED1_REQUIRED, NOT final loss. Registered CPU4536182 C0/1540sec/16CPU:109field frozenVAL2371pairs nativeMAE and layer6 5000MID/47698confs complete; M2 CVF/CVF_res=.04147733/.07043261, Dprime=.06074518/.09626978; four preselected energy MAEs worse, descriptive only. C3 exact3M still pending; no C3 job/file changed. Actual both4090 free and56CPU available before seed1 admission; ONLY20b/ec788/16CPU used, leaves20a and40CPU for higherpriorityC3. New actual seed1 4536314 RUNNING, trainer97394/UID1278/start18633541/PGID97394 in actualSlurm process tree and ec788 context, first32samples/1update then10400/325; fresh3M/B32 same frozenb582502/33fields/immutableD1, own seed1p99 window. Actual M2seed1 4535736 C0/COMPLETE3M/CP232058173B/readouts complete reused via exact config snapshot; stale publicpointer not an artificial gate, no baseline training. PureCPU1 4536315 afterok4536314 queued for final comparison, matching closedseed0 statistics reused and only seed1 new pairing; no extra probes/fields/9M/D1/D2. Perf mandatory5090 remains higherpriority,20a explicitly C3reserved, no paidserver/node21; existing disk/inode/UID/concurrency guards retained. Reports prepared on p-followup-20261116.

[P heads USER unified3090 seed1 coexistence /2026-11-18 23:05 CST] 用户刚同时回复node7及统一问题，明确允许本线已按预注册触发的seed1（含唯一共享B3 seed1）在3090显存占用≤30%、剩余显存足够且正式Slurm15CPU下与既有gmx共用；不扩大H或新增训练权限，原进程保持，20a仍明确留C3。23:05实际GPU节点CPU/任务未出现新合规槽位：0/1/3满48CPU，4/5/7本线模型在跑，6仍C3高显存，20b为followup Dprime seed1，22提速GPU优先。已将可变资源policy记录新授权，既有冻结源、模型/标签/超参数均不改。
T1旧4536272经P0/StartUnknown/Restarts0确认后hold；新4536334同T1_seed1_source@617e78f、同canonical配置/UUIDa967b766/cu118/node0/15CPU/nice10000/afterany4536203仅资源等待，取消旧额外零CUDA上下文要求，保留原≤30%/UUID锁/磁盘守卫，并在exec前要求memory.free≥11527MiB（正式T1资源峰值11012555776B加1024MiB余量）。两项原CPU1后处理6280/6281已先绑定afterok6334，再仅取消旧6272，真实CANCELLED0:0/0秒；新6334已release为正常PENDING/Dependency/0秒，不是新模型重复训练。T1仍M2保存[1M,2M,3M]且无CP32；外部M2 seed1原件复用不重训。actualnode0 root38876471296B/NFS6567995899904B/inode/liveUID447611609088vs173913217024required及24GiB/跨线守卫通过；GPU558/24576MiB、free23701MiB仅两gmx，但目前CPU48/48，故不启动。T4/B3s1/T3s1继续，T2s1/T5s1原暂定资源队列及提速>配方>本线/解耦优先级不变，其它首合规卡出现时只改P0。

[P heads T3 seed1 infrastructure recovery /2026-11-18 23:45 CST] 原T3 seed1 4536267实际FAILED75:0/04:29:30/End23:07:52，P_HEADS_DISK_STOP JSON解析失败：根原地写本线共享resources.json时，该source/configs下live symlink被watchdog读到半写内容。当前policy完整合法，T4/B3在跑未停止。所有窗口后续更新此类运行中共享JSON必须同文件系统临时文件写完后用Linux os.replace原子替换，不得直接truncate正式文件；不为本次故障改科学规则或冻结源。原T3只有完整CP32（230445257B/18:39:43.182482898），未有1M，原日志/阈值/文件保留，失败墙钟4:29:30单列，不能声称保留约930k进度。
恢复配置已由根在actualcompute5原子替换canonical T3_seed1.json，仅run/output/resume/request/ack路径5键变化，同d8dce41冻结源完整恢复model/optimizer/clock/RNG/clip状态。新4536341=node5/gpu/正式15CPU/nice10000/cu118/dacUUID，p_heads_T3_seed1_attempt2，从祖先32恢复的首loss64/up2已确认。23:44:23唯一身份观察trainer1328479/UID1278/PPID1328475/PGID1328479/start1135082565、实际Slurm0–14及父/所见后代一致、2lazy读者/max14、真实CUDAcontext匹配；新目录不应再有CP32，祖先CP未复读。旧post6268已改afterok6341，6269改afterok6341且6238，未重复计算。node5启动前actual GPU286/24576MiB/free23981，仅原gmx1328206/278MiB，16CPU可分配，ownUUID锁FREE；root56162091008B/NFS6562847391744B/inode/liveUID447596236800vs173902084096required/24GiB跨线guard通过，使用用户23:05统一3090共用授权，gmx不动。旧T3 seed1 p99仅失败attempt历史，新CP32未拟合，必要重放训练自然校准，不复制阈值/独立复算。T4/B3继续，T1新6334/T2/T5原P0，提速/配方优先及20a C3保留不变；H1只实际最终3M/C0，当前不分析中间CP。

[P followup C3 read-only reference and registered CPU description /2026-11-19 01:46 CST] Recipe line has actually resumed C3 from2121056 on reserved20a/8bfd UUID: new4536352 RUNNING/node20/16CPU, canonical round3/C3.json points to fixed_20261115_round3_C3_node20_gpu0_resumed_20261119. Old4535189 C0 is handoff completion before3M, not scientific endpoint. Followup did not operate C3 training/migration; it only references owner metadata and registers its required description. New own4536353=PENDING/Dependency/0sec, afterok4536352, node20/all/request16CPU/nice10000/nonexclusive/emptyCUDA; immutable O/C3_geometry_cpu_20261119.sbatch, only directive_geometry.py --conditions C3 --device cpu. Reuse closed M2/Dprime geometry; no repeat forward or model. Completion requires actual C3 exact3M, final R1/R3 and layer6 payload, not dependency/jobexit alone. Actual target disk/inode/liveUID guardPASS447055151104available vs174705440768required; own18GiB/heads24GiB/sharedM2seed1 independent2GiB retained. Dprime seed1 stays20b/4536314,17:44UTC1287040/3M; original execution/clip/budget unchanged. Perf priority and existing contexts untouched.

[P heads T2 seed1 STARTED on node6 released by recipe C3 owner /2026-11-19 02:02 CST] 已读配方/跟进共享通知及实际Slurm：C3由配方线从2121056完整状态迁入用户预留20a，新4536352/node20/16CPU RUNNING；旧4535189 C0是handoff非最终3M。Heads没有提交、停止或迁移C3。node6实际IDLE48CPU后，本线按最早已就绪的必做T2 seed1使用首个合规空卡，未占C3/5090提速卡。actual GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef/3090为5/24576MiB、free24262、无CUDAcontext，MemAvailable371743808kB，瞬时ownUUID锁FREE；实际root57474326528B/NFS6537919594496B/inode/liveUID447045128192vs173347231744required/合并24GiB和跨线预留guard通过。
根实核旧T2 seed1 4536170 P0/StartUnknown/Restarts0后hold，新4536355=node6/gpu/正式15CPU/nice10000/cu118（3090环境，不误用5090的stage43 Python），同T2_seed1_source@4f1a80f、同canonical T2_seed1.json/run/output/fresh3M/B32/无resume。先把原字段post6289改afterok6355、组合post6290改afterok6355且6238并验证，再仅取消旧6170，实际CANCELLED0:0/0秒；新6355已R，原node22 perf队列不动。新wrap保留≤30%/UUID锁/磁盘watchdog并要求memory.free≥10655MiB（已闭合T2资源峰值10098291200B加1024MiB余量）。首32loss及完整CP32已就绪；唯一02:02:25资源观察T2_resources_4536355.json记录trainer1988017/UID1278/PPID1988013/PGID1988017/start1982582634、实际Slurm0–14及父/所见后代同mask、2lazy读者/max14、实际bdb GPUcontext匹配，CP内容未回读，非新benchmark。T4/node4、共享B3s1/node7、恢复T3s1/node5继续；T1新6334/node0和T5s1 6260/node4仍原P0资源等待，既有统一3090共用授权持续。原科学基底/参数/裁剪协议和唯一B3 seed1不变，H1仅最终3M checkpoint按既有方法，writer串行；提速>配方>heads/解耦优先级及既有所有进程保持。

## 2026-11-19 P recipe round4 storage reconciliation

The P line reconciled its registered round4 into the existing shared model output forecast at /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/model_output_budget.json (p_recipe_remaining_plan_20261119). Existing P output physical allocation26,165,161,984B is retained. Remaining105 checkpoint slots at<=300MB cover C3 final, five round4 arms, one F1 acceptance, conditional M3 merge, up to seven9M confirmations,15 further handoffs and7 concurrent temporary checkpoints;3GB covers future logs/readouts/metadata. Projected P peak60,665,161,984B fits its existing61GB reservation. Global114,569,896,448B and every other window's reservation/roots are unchanged; no per-node duplicate reservation. Actual compute-0-20 root/Lustre/NFS bytes/inodes and fresh UID quotas passed at the unchanged global forecast. Recheck selected nodes at launch. No new training, deletion, stopped process or migration resulted from this reconciliation.

[P heads unique B3 seed1 COMPLETE / T1 seed1 STARTED on released node7 /2026-11-19 06:02 CST] 唯一共享B3 seed1 4536238真实COMPLETED0:0/12:42:27，原3M/93750updates及R1/R3完成；字段post4536240 C0/6sec，CYP4/VAL109只copy。最终CP232057661B/05:36:26.257382406仅stat。原GPU已释放后actualnode7 IDLE48CPU，9db54192/3090为5/24576MiB、free24262、无CUDAcontext，MemAvailable387899316kB，ownUUID锁FREE；实际root53655605248B/NFS6493239771136B/inode/liveUID445976883200vs172281903104required及heads24GiB/跨线预留守卫通过。根将更早已触发T1 seed1从旧6334 P0/未Start/Restarts0安全改排新4536378=node7/gpu/正式15CPU/nice10000/cu118/9dbUUID；同617e78f冻结源、同canonical fresh3M，无科学变化。先hold旧队列，新held提交后先绑定post6280/6281 afterok6378并核，再取消旧6334=CANCEL0:0/0秒、release新6378，现实际R。首loss32/up1；唯一资源观察PID2625282/UID1278/start1984020492/PGID2625282、Slurm实际0–14及父/所见后代一致、4lazy/max14、真实GPU一致；M2保存[1M,2M,3M]无CP32保持，未读CP体。
新H1 B3_seed1 CPU4536379=node20/gpu/4CPU/nice10000/emptyCUDA，明确最终3M、仅layer6，现R；唯一PID110908/UID1278/start21812172/PGID110908、实际48–51与Slurm4核一致/无该PID GPUcontext。先hold未来T4 H4536220，仅增加afterany6379串行门（原afterok5771保留）再release两者，避免wholeJSON并写。没有占新GPU或新增评价/额外臂。T4/node4、T3s1/node5、T2s1/node6继续，T5s1等原node4；其它线C3 6352、Dprime6314及perf5799不动，提速GPU完成前>配方>本线/解耦优先级不变。此次没有两seed最终判定、9M或旧数值/测试重跑。

[P heads all seed0 CLOSED / T4 seed1 READY and queued /2026-11-19 07:04 CST] T4 seed0 4535771真实COMPLETED0:0/25:55:36，原最终3M CP232052163B/06:18:36.396520555仅stat，原R1/R3完成；finalpost4535835 C0/8sec，R3 delta−.02299068455、95%CI[−.03329311921,−.01238114201]，虽CI为负但absdelta<.06，正式SEED1_REQUIRED，尚非最终负结论。原post已生成fresh canonical T4_seed1.json，仅seed/run/output/request/ack与s0不同，不加新科学臂。源冻结4536389=node20/gpu/CPU1/空CUDA C0/10sec，T4_seed1_source@9fdc6ed约16.7MB，原实际磁盘/inode/liveUID/24GiB合并及跨线守卫保持。
新T4 seed1真实4536390=node5/gpu/15CPU/nice10000/cu118/dac07d74，正常PENDING0/Dependency afterany4536341，仅等当前本线T3s1释放同卡，不要求其科学成功；任何更早实际合规槽位出现可只改P0。未预占GPU、不抢提速/配方优先卡，原已有任务不动；启动须原显存≤30%、ownUUID锁、实际容量watchdog，额外memory.free≥10660MiB（唯一已闭合T4s0资源峰值10103364096B加1024MiB余量，非benchmark）。新CPU1/空CUDA/node20字段post4536392及两seedpost4536393均afterok6390，显式复用已完成唯一B3 seed1，不依赖将purged旧6238，不重训基线；seed0点/CI复用缓存，仅新seed1 paired一次。
原已就绪T5 seed1 4536260自06:43:45在node4/正式15CPU运行，唯一资源观察PID3516059/UID1278/start5890570682/PGID3516059、实际0–14与Slurm一致、4lazy/max14、6965UUID实际context匹配、首32loss/CP32有而未读体。T4最终H1 4536220同刻在node20仅4CPU/空CUDA运行，唯一PID112716/UID1278/start22081970/PGID112716、实际68–71与Slurm一致/无其GPUcontext；B3s1 H6379先C0，writer保持串行。T1/T2/T3 seed1继续，新T1自身自然p99=35.45996673583984/2813步/150016冻结固定，不复算。至此T1–T5全部seed0已正式触发seed1，最终两seed结论尚待各自完整产出。其它线C3/Dprime/perf及gmx保持，禁21/付费/独占，提速GPU>配方>本线/解耦优先不变。

## 2026-11-19 07:56 CST — user scheduling rules synchronized

New submissions: <=3M GPU work prefers compute-0-0..7; >3M prefers20/22 (5090>4090>3090 within that group); use the other group when the preferred one has no admissible slot. Low-group jobs require the actual gpu partition, idle GPU UUID and enough Slurm CPUs, and use ordinary sbatch. SSH+standby remains20/22 only;21 remains disabled. CPU computation/testing/statistics now goes only toCPU nodes8..19; queue there if full. Running jobs are preserved. Authority: MFM/p-recipe AGENTS.md commits3fa1eb75/3b1d69de; installed huagong_hpc_requirement1.0.161 and repository mirror updated. The launch policy scans both groups and checks actual partition membership; compute-0-2 is currently cpu-only in sinfo and is not used for gpu submissions. No side-line job or code was changed by this notification.

## P-followup 2026-11-19 08:05 CST：D′ 两种子最终 LOSS / GPU 释放

D′ seed1 4536314 COMPLETED/0:0、精确3M；比较4536315 COMPLETED/0:0（1CPU×6秒），直接复用seed0闭合统计。D′−M2 R3：seed0 −0.04528424，95%CI[−0.05626820,−0.03429374]；seed1 −0.03157315，95%CI[−0.04243676,−0.02110343]；均值−0.03842870，两CI上界均<0，按现行规则最终LOSS。本线没有可交接配方线的两种子胜出项，D′不采纳；原D的M1+C单种子结果不替代M2两种子结论。配方配置/分支未改。

20b/ec788ed1的本线训练已终止；07:53CST实查PID97394不存在、自有锁FREE、该UUID无CUDA上下文，释放供高优先级工作线使用。本线后续无GPU工作。C3训练4536352仍由配方线负责；本线仅等其精确3M分数/第6层CPU描述。依据最新CPU节点规则，尚未启动的描述4536353已原位改为compute-0-16/cpu/16CPU，afterok4536352保持，无取消/重训或C3迁移。最终完整回归和仓库检查也将只在CPU节点执行，之后开未合并PR。

[P heads new CPU/GPU policy applied / five seed1 arms ACTUALLY RUNNING /2026-11-19 08:06 CST] 已完整读取installed huagong_hpc_requirement1.0.161顶部及p-recipe AGENTS 3fa1eb75/3b1d69de。后续纯CPU work只8–19；本线10个尚P0/0秒的CPU1字段/两seedpost（6268/69、6280/81、6289/90、6291/92、6392/93）已先hold后同ID改Partition=cpu、ReqNodeList=compute-0-16再release，CPU/原命令/科学不变，所有依赖保持正常。actualnode16当时96CPU可用、MemAvailable383683836kB、root69766787072B，NFS/inode/UID及24GiB+跨线守卫PASS；未来源码冻结/统计/测试/最终H亦只CPU8–19。已完node20 CPU源/几何是更新前历史，未重跑。
07:56实际Dprime seed1 4536314 C0/10:39:05、post6315 C0/6秒；20b/ec788ed1-7da1-8f93-bb23-b4fdb2018b02已18/49140MiB、free48521MiB、无CUDAcontext，ownUUID锁FREE。低组0/1/3 CPU48/48、4/5/6/7本线在跑，无合规槽；2实际非gpu分区。按新“优先组无合规立即fallback”使用20b；未见对该4090的新更高优先ready claim，20a配方C3继续、22 perf Resources优先不动。actualnode20有56CPU free、MemAvailable112013904kB，root881251127296B/NFS6473114451968B/inodes2964683762/liveUID445220552704vs171528173568required，合并24GiB/跨线预留PASS。
根确认原T4 seed1 4536390 P0/StartUnknown/Restarts0后hold；新held4536400=node20/gpu/正式15CPU/nice10000/cu118/ec788UUID、同T4_seed1_source@9fdc6ed及canonical fresh3M、无科学变化。先把CPU16 posts6392/6393改afterok6400并核，再仅取消旧6390（真实CANCEL0:0/0秒）、release新6400，现R。首32loss/完整CP32已就绪；唯一08:03:27资源观察T4_resources_4536400.json记PID115195/UID1278/PPID115191/PGID115195/start22548522、实际Slurm52–66/15及父/所见后代一致、4lazy/max14、env与实际GPU匹配，未读CP体。原≤30%/UUID锁/磁盘watchdog与free≥10660MiB保持。此为P0资源改排，不停止/迁移任何在跑训练。
T1/T2/T3/T5 seed1继续原节点，至此T1–T5五臂seed1均实际运行，唯一B3 seed1早已完整成功，不新增基线。T5于08:06 ordinary150400/up4700后唯一读取新producer自然p99=66.44803680419925（2813窗口步、150016冻结），固定到尾；不比较/替换旧seed0或复算。全部seed0与B3s1最终H已完成，未来每条本臂seed1 H仍待实际终态串行，最终两seed结论未出；无额外臂/第三seed/9M/付费/21。现有其他进程保持。

[P heads T3 seed1 COMPLETE / node5 available observation /2026-11-19 13:26 CST] 本线T3 seed1亲4536341正式C0/13:14:08，最终3M CP230477513B/12:47:29.999911850仅首次元数据；COMPLETE累计samples3M/updates93750，恢复成功段actual_samples2999968+祖先32=3M，不追加预算。字段6268/两seed判定6269在原CPU16全满后仅P0同ID改CPU14/cpu/各1CPU，解除hold后13:20:15起实际R；科学/命令不变，尚未发布两seed结论。唯一H1 T3_seed1 4536609 CPU18/cpu/4CPU/空CUDA实际R，step0 Python13:14:16开始；guard/身份发布通过前不加载模型，暂未观测PASS marker，不把SSH超时当作失败或重启。CPU14/18原各8CPU可用，MemAvailable47042/68693MiB，其余CPU后处理仍16，未来纯CPU只8–19。
13:26实核node5 UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377仅5/24576MiB/util0且无CUDA计算context，Slurm CPUAlloc10/48（38可分配）。本线没有待启GPU模型，可供提速>配方>本线/解耦按最新实际CPU/UUID/锁/容量准入接用；这是点时读数，不预占或替其它线启动。C3属配方线，p-heads未提交/停止/迁移C3。T1/T2/T4/T5自身seed1继续原处，不迁移，24GiB及跨线预留/根盘floor/inode/UID守卫保持。

[P heads CPU14/18 NFS wait observed /2026-11-19 13:32 CST] 只读元数据已在各自既有Slurm分配内用短srun --overlap --exact/1CPU/ps确认，不新增分配、不发进程信号：CPU18 H6609实际python933104处于D/nfs_wait_bit_killable（约1078秒），CPU14原fields6268/decision6269实际python2505838和2505839均D/nfs_wait_bit_killable（约621秒），Slurm仍R。这解释空日志，当前不是bootstrap/几何完成证据，也不是已失败；保留原作业等待文件系统恢复，不重复提交/重启、不操作其它进程或管理员挂载。CPU18 SSH也在公钥认证响应处超时。后续未启纯CPU任务仍限定8–19并按实际资源/可达性选节点，勿据本次情况把CPU科学计算退到GPU节点。本线四条GPU训练持续正进度。

## 2026-11-19 13:35 CST — P recipe CPU reporting resource observation

配方线CPU10统计作业4536612已C0/1CPU/1秒（13:23观测），同机4536595此前也C0。启动守卫实际核实root约70.07GB可用、NFS约7.40TB及inode/新UID配额、MemAvailable约398GB；13:23 scontrol为CPU62/64、FreeMem120648MiB。12:28配方线仅CPU元数据作业4536593在CPU14未发布ADMITTED、日志为空，284秒后取消并保留成本/原日志；C3 GPU4536352未受影响。heads日报13:32记录其CPU14/18 post在D/nfs_wait_bit_killable，统计/几何尚未进入执行；本条仅共享已验证的CPU10可用性事实，具体新提交前仍须按现场CPU/内存/实际FS检查。未操作任何他线作业或代码。CPU工作仍限8–19，不转GPU节点。

[P heads T3 TWO-SEED DECISION / CPU-post NFS recovery /2026-11-19 13:43 CST] T3正式R3=LOSS、R1=TIE。新seed1 R3 candidate .4311420004438634 /B3 .4406415201948996，Δ=-.00949951975103619、95%CI[-.018908726064840085,-.000056519258680874253]；既有seed0 Δ=-.022013477007160442、CI[-.032053393575519645,-.012058970924839008]复用缓存。按原预注册两seed CI上界均<0判负，不加入其它幅度门槛；R1新Δ+.011893479671824803、CI[-.0019266658452948156,.025638475820842884]，独立TIE。唯一B3 seed1已用，原3M B3两seed R3训练噪声=.03386191168730612首次正式报告。T3只去query→atom选择性、保留门控求和/logN，限制解释范围；无胜出配置供配方采纳，无换基底确认/第三seed。
CPU10实测完整root/NFS/inode/UID/24GiB+跨线守卫PASS、2freeCPU及Mem388633084kB，故仅恢复受CPU14真实D/NFS阻塞的单核post：导出原body，新held6613/6614各afterany原6268/69；确认旧主/批/extern全终态后release，actual6613 C0/15秒与6614 C0/14秒/cpu10/各CPU1/空CUDA/nice10000。旧各CANCEL0/19:52等待成本保留，未产科学结果；不重读旧分数/重bootstrap/MAE/独立噪声，CYP4/VAL109只转录。H6609CPU18仍实际NFS等待，未冒称H完成；未来纯CPU只8–19。T1/T2/T4/T5 seed1继续原处；C3配方所有权/其它进程/高优先GPU/禁21及磁盘保护不变。

[P heads H1 T3 seed1 CPU recovery ACTUALLY STARTED /2026-11-19 13:51 CST] CPU18旧H6609 Python933104再次实核D/nfs_wait_bit_killable且无PASS/科学输出，已13:49:47主CANCEL0/39:02、batch FAILED15:0/39:04、step0 CANCEL0:15/35:33、externC0；实际等待2.602222 allocation CPU-h单列。不是训练停止/科学失败，不接触其它进程。actualCPU17 SSH/完整guard健康、MemAvailable383523996kB（sinfo低FreeMem不等于MemAvailable）、8逻辑CPU free/2threadspercore。旧全终态后才放行新唯一H1 writer4536620 cpu17/cpu/1node/4CPU/nice10000/空CUDA，13:50:28开始，13:51:11 R0:43且H_PREFLIGHT_PASS已出并exec原几何。
实际新guard root69514584064B/NFS7400969994240B/inodes2964686335/liveUID439979986944vs169932806144required/24GiB+跨线通过。唯一PID3523579/UID1278/PPID3523574/PGID3523579/start2168188290；Linux affinity6,7,102,103与srun真实Linux绑定mask一致，Slurm实际AllocCPUS4/CPUsTask4（2物理核4逻辑线程）。HT节点不把抽象CPU_IDs直接伪作Linux核号。原h_geometry condition T3_seed1/最终attempt2 CP/torch4/5000VAL/47698构象/1000MID方法不改，实际模型加载在guard通过之后；新资源JSON已原子发布，H科学结果等C0后消费。此前6619始终held/P0/Restarts0、取消0秒（hint导致请求显示2节点，改普通4CPU显式1节点6620），不是科学失败/新臂。T3两seedR3 LOSS/R1TIE已推2882e0e8；其余四GPU训练持续原处，C3仍配方所有权，无GPU抢占/迁移。

[P heads T3 seed1 FINAL GEOMETRY COMPLETE /2026-11-19 14:34 CST] 唯一H writer4536620 CPU17真实COMPLETED0:0/43:20/AllocCPUS4，Start13:50:28、End14:33:48；释放本作业4逻辑CPU，无H GPU占用。producer2550.594521秒，原exact3M/5000VAL/47698构象及4项各1000有效MID bootstrap完成。H agent唯一消费新T3_seed1层6：CEV .402764 [.391562,.411555]；EEV .359731 [.358296,.361363]；CVF .0424250 [.0408217,.0440203]；CVF_res .0703346 [.0675437,.0731970]。仅既有CI表列描述，不新增方向/paired检验、旧条件重读/重算或CP复核。既有H1_GEOMETRY.md方法脚注/CPU17实际身份及HT绑定已恢复，无新文档。
本次成功geometry allocation CPU2.8888889h，累计11.7777778h（仅成功几何，来源探针等另列）；旧6609真实D/NFS等待2.6022222CPUh另列、不与batch/steps重复相加，metadata18 .0555556h另列，H GPU仍6.2251h。T3两seedR3 LOSS/R1TIE及最终H均已闭合，无额外确认/新臂。T1/T2/T4/T5 seed1和其最终H/两seed判定仍必做，14:31四训练实际继续推进；最终报告/一次完整默认回归+仓库检查/未合并PR尚未开始，全线未结项。纯CPU8–19、训练连续性、其它用户/高优先线和磁盘保护不变。

[P heads T4 TWO-SEED DECISION / T1 final3M /2026-11-19 19:19 CST] T4 seed1亲4536400真实C0/11:11:30（19:13:00结束），最终CP232052163B/19:06:27.716511880；CPU17字段6392/两seed6393均C0/各3秒。正式R3 TIE：新S1 Δ+.008936110520611162、95%CI[−.0004768960235272762,.018201008294255163]，旧S0缓存复用；R1独立LOSS：新Δ−.03718610119099747、CI[−.05178440010141949,−.02374540391812444]。B3两seedR3噪声.03386191168730612直接引用正式producer，CYP4/VAL109只copy；无胜出配置交接或额外确认。T3原R3 LOSS/R1 TIE保持。
T4最终H4536744在CPU10/cpu/4CPU/空CUDA运行，19:11:17实际开始，guard及身份/真实srun绑定PASS后exec原H；原CP完整临时文件close/fsync后原子hardlink发布，依11-17 H补充3可与parent原R1/R3短暂并行，不加科学门槛/重算。T1 seed1最终3M244694029B/19:16:16.049485835已首次metadata匹配canonical；19:18原parent6378仍R评估，H4536745仅CPU10/4CPU afterany6744串行。CPU16满后四P0 posts6280/81/6392/93同ID安全改CPU17再release，原body/CPU1/Nice/依赖不变，无held遗留；实际CPU17容量/UID/内存guard健康。T2/T5原训练继续，未来纯CPU仅8–19。
本线T4已释放自身20b GPUcontext；19:18实测ec788ed1/4090=423/49140MiB、另有PID129986/400MiB，Slurm20 CPU64/104，不能据本通知认定空卡；各线仍须按最新actual UUID/上下文/CPU/容量准入。C3由配方线负责，heads未提交/停止/迁移C3；高优先线与其它进程保持。所有剩余mandatory seed1/H、最终报告/一次默认fullreg+checker/未合并PR仍必做，未结项。

[P heads T1 seed1 TRAINING/EVALUATION COMPLETE /2026-11-19 19:28 CST] T1亲4536378真实COMPLETED0:0/13:25:59/15CPU/node7，Start05:58:10 End19:24:09，原3M及R1/R3完成；finalCP244694029B/19:16:16.049485835首metadata已记录、不复读。字段6280/两seed6281仍P0/正常Priority/依赖满足/CPU17，正式T1判定尚未产出；该节点已192/192满（其它线作业保持），CPU18只读capacity probe19:26超时124且无PASS，未迁入写入。T1最终H6745仍CPU10/4CPU/空CUDA afterany当前T4 H6744，wholeJSON writer串行；19:26 T4H仍R15:21。T2/T5训练继续，纯CPU满则排队，不退GPU节点；未新增科学计算/臂/第三seed，不提前结项。C3归配方线，heads无操作。

[P heads T1 TWO-SEED DECISION / T4 finalH C0 /2026-11-19 19:44 CST] T1正式R3 TIE、R1独立TIE。新S1 R3 candidate .46778791130674247 /外部M2 seed1 .470049811395258，Δ−.0022619000885155116、95%CI[−.012367245104910263,.007547898029821682]；R1新Δ−.06252541000781825、CI[−.07430686597279726,−.04962435563598987]，旧S0 R1 CI跨0，故不单用S1负值替代原两seed规则。M2参考R3训练噪声.002047178249612591直接引用producer，不能混作B3噪声.03386191168730612。外部M2 seed1实际复用/不再pending，旧S0缓存复用；CYP4/VAL109只copy，无胜出交接或额外确认。T3 R3 LOSS/R1 TIE、T4 R3 TIE/R1 LOSS保持；TIE不是等价证明。
CPU17已满且18容量探测无PASS，root在19:30仅将T1两个P0 posts6280/81同ID改到经actual容量/UID/内存guard健康的CPU10；未改body/CPU1/Nice/科学/原依赖，未加H科学门槛，全部hold释放。T4H6744真实C0/27:52/4CPU，Start19:11:17 End19:39:09；随后T1fields6280 C0/10秒及two-seeds6281 C0/8秒（CPU10，19:39:17起）。T4新几何由H agent仅一次整理现成新row/CI，旧值不重算。成功几何CPU新增1.8577778h、累计13.6355556h，GPU仍6.2251h，原NFS等待另列。
T1最终H6745已19:40:17在CPU10/cpu/4CPU启动，H agent唯一读取新resource PASS（root不复读）：PID2415330/UID1278/start1988957179/PGID2415330，Linux31,36,37,63与srun mask一致、空CUDA；root可用70071783424B、NFS7284946108416B/inodes2964680631、UID434040098816B>168342530048B、MemAvailable388192336kB。原方法/5000VAL/47698构象/F64/1000MID保持。19:31 T2 seed1=2243200样本、T5=1475200，均R；剩余训练/判定/H与最终报告/default fullreg/checker/未合并PR仍必做。C3属于配方线，本线不操作它，未结项。

[P heads T4 seed1 FINAL GEOMETRY COMPLETE /2026-11-19 19:46 CST] H4536744 CPU10/cpu真实C0/27:52/AllocCPUS4（19:11:17–19:39:09），producer1632.890185秒，新增成功geometry CPU1.8577778h、累计13.6355556h，H GPU仍6.2251h。H agent仅一次消费新T4_seed1层6：CEV .342479 [.330087,.352662]；EEV .303662 [.302366,.305120]；CVF .0496946 [.0475323,.0517017]；CVF_res .0749682 [.0715590,.0783670]。exact3M/5000VAL/47698构象/4项各1000原MID bootstrap保持，仅现成CI表列描述，不加新方向/差值/paired检验或重读旧科学行。H1方法与全部CPU/旧NFS等待成本脚注已恢复；H2–H4 persist_features=False/原始H-z仅内存事实补入方法，H1正常producer均值临时文件unlink事实记录，非当前库存核实/active不动。全部H结束后才核对本线精确临时残留，预测/统计/参数结果保留。
T1最终H6745仍为当前唯一H1 writer，资源PASS已由H agent唯一消费并报告，root未复读；其科学行与成本尚未结算。正式T1 R3/R1双TIE已推412b6877；T3 R3 LOSS、T4 R3 TIE保持，T2/T5自身训练及最终判定/H、全线最终收尾仍必做。纯CPU8–19、训练连续性/其它进程保护/禁21/磁盘UID并发预留继续，C3归配方线，本线未结项。


2026-11-19 20:03 CST — P recipe resource status: C3 seed0 job4536352 completed0:0 with full3M/R1/R3. The original pairedCPU producer found |R3delta|=.0117058186881 >= half-tau .0117000658286, so the registered C3 seed1 alone is now ready and waiting for the first admissible GPU; M2 seed1 is reused. PP4536748/node5, F24536749/node7, X14536750/node20a, X24536751/node20b are running under sbatch16CPU each. F1 real-loader/per-head acceptance remains next after the registered C3 seed1 when a further slot is available. The existing perf-line5090 reservation remains. P Lustre forecast still61GB/global114569896448B; C3 seed1 uses3 of the18 conditional checkpoint slots,15 remain. Pure CPU jobs stay8..19; accounting queries use the head (compute10 sacct reachedlocalhost6819 and failed). Multi-node --nodelist lists request all listed nodes: our CPU-pool submissions now request --nodes=1 and exclude other nodes, with1 requestedCPU; CPU17 allocates2 logicalCPUs as its minimum whole core. All old outputs and failed/zero-progress handles are retained. Main milestone: https://github.com/mint258/MFM/commit/72621d316ed48cf968c5a837f79c1a0ce1c1976d .

[P heads T1 seed1 FINAL GEOMETRY COMPLETE /2026-11-19 20:08 CST] H4536745 CPU10/cpu真实C0/21:36/AllocCPUS4，Start19:40:17 End20:01:53，producer1275.432742秒。H agent仅一次消费新增T1_seed1层6：CEV .441975 [.431219,.450860]；EEV .299165 [.298068,.300403]；CVF .0386044 [.0371551,.0400261]；CVF_res .0685241 [.0659303,.0711430]。exact3M/5000VAL/47698构象/四项各1000原MID bootstrap保持，仅现成CI表列描述，无新方向/差值/paired检验；M2 seed1没有H参照，不编差值。既有CPU方法/身份/真实srun绑定及正常均值临时文件生命周期脚注已恢复，资源不复读。
成功几何新增1.44 allocation CPU-h、累计15.0755556h，H GPU仍6.2251h；旧H NFS等待2.6022222CPU-h、CPU18 metadata .0555556及其它管理/读出CPU各另列。当前无active H writer；全部seed0/唯一B3 seed1/T1-T3-T4 seed1最终H已完成，T2/T5各自seed1最终H仍必做。20:01实际T2 seed1 R/2313600样本、T5 R/1532800，继续原训练；T1正式R3/R1 TIE、T3 R3 LOSS/R1 TIE、T4 R3 TIE/R1 LOSS保持。已完成H方法与T统计写作交接已汇总，最终报告仍待全部实际判定，不提前结项、不启动最终回归/仓库检查/PR。纯CPU8–19、现有任务/其它用户保护、磁盘UID并发预留继续；C3归配方线，heads无操作。

[P heads Nov20 progress / T5 seed1 2M recovery point /2026-11-20 00:05 CST] 00:01:38实际T2 parent4536355=node6 RUNNING22:02:16、2867200样本/89600更新；T5 parent4536260=node4 RUNNING17:17:53、2006400/62700。T5新完整samples_2000000.pt=220570345B，mtime2026-11-19 23:57:20.169101939 +0800，root仅首次metadata、未读体/hash，保存后继续；中间恢复点不补H/评分。现有训练不停止/迁移，全部原3M、原R1/R3和已触发两seed判定照常完成。
正式闭合R3仍为T1 TIE、T3 LOSS、T4 TIE（R1 TIE/TIE/LOSS）；T2/T5实际判定和各自最终H仍待完成，当前无active H writer。新S1 paired只做一次、旧S0缓存复用；唯一B3 seed1与外部M2 seed1不重复训练。Nov20一页DAILY已建立；已完成方法/测试证据写作交接已整理，最终报告/default fullreg/check_repository/未合并PR仍留全部科学完成之后。
00:03 CPU10 actualguard PASS：root70072967168B、NFS7199421104128B/inodes2964621679、liveUID430137827328B>168127891456B；heads24GiB及跨线预算、rootfloor/inodes/watchdog/原子共享JSON保护继续。新纯CPU只8–19；C3归配方线，heads无操作/新GPU任务，不加臂/第三seed/9M/付费/21，未结项。

[P heads T2 pending CPU posts retarget /2026-11-20 00:11 CST] 为避免已近最终3M的T2后处理继续绑定满CPU16，root00:11:16核实字段4536289/两seed4536290均P0、RunTime0、Restarts0后hold/update/release，同ID改到compute-0-17/cpu/各CPU1。原body/Nice10000/afterok4536355及科学保持，所有hold已释放、正priority/正常Dependency，未启动统计或改在跑训练。T5未来post6291/92仍原CPU16，临近其parent时再按实际资源处理。
CPU17先实际184/192CPU（8free），freshguard00:10:32 PASS：root69544357888B、NFS7196666494976B/inodes2964621612、liveUID430001864704B>168126363648B、MemAvailable383542908kB；不是把sinfo低FreeMem当作MemAvailable。新纯CPU只8–19、按需/非exclusive、根盘/UID/跨线预留保持。T2/T5本身继续原3M与原R1/R3，正式两seed判定和最终H仍待各自真实产物；没有新臂或独立重算，C3归配方线，本线未结项。

[P heads H6 optional SMARTS evidence boundary /2026-11-20 00:31 CST] 本线H6实际使用元素×杂化、芳香/成环与BaseFeatures六类；原报告记录“未定位到现成28类SMARTS交付，不等待”，所以未纳入该附加组。本次仅定向查询既有上游文档：11/12 STATUS及11/13 docs/model_v3/MECHANISM_ANALYSIS.md仍记录canonical28定义待输入，未取得证明H6运行前已可用的正式交付日期/定义实例/manifest。报告已补清此边界，不宣称28类已追加，也不把未搜到当上游绝未交付证明；H6仍从D6坐标/电荷重建键，不增TRAIN结构映射门槛、不造替代SMARTS。未读raw/sidecar/源码，未重做编码器、统计/bootstrap或新检验；已有科学结果/判定保持。
00:31:38实际两GPU训练仍R：T2 seed1 2934400样本/91700更新，T5 seed1 2067200/64600。T2已近final3M，root后续按原子最终文件就绪交H；原R1/R3与两seed判定照常，尚不提前结论。T5自身最终3M/H与全部最终收尾仍待完成，既有CPU8–19、训练连续性及真实容量/UID并发保护继续。

## P-followup 2026-11-20 00:35 CST：科学部分全部闭合，余工程检查

A–D、D′两seed及C3规定的分数/第6层描述均已完成。D′对M2最终两seed LOSS，无可交接的两seed胜出项；原D的M1+C单seed WIN仍限于该基底。配方线可直接读取这些最终科学判定，本线剩余为完整CPU回归、默认仓库检查和未合并PR，不含新的候选试验，后续无本线GPU工作。

C3源4536352及本线描述4536353均COMPLETED/0:0；C3精确3M R1=0.25509339、R3=0.45629681。描述仅原5000 VAL/47698构象、第6层：CVF=0.01465560、CVF_res=0.02346760；M2/D′直接复用。CPU8×1632秒、0 GPU-h，临时mean(H)已移除；未追加配对检验或训练，未改配方配置。

科学报告已推送：https://github.com/mint258/MFM/blob/p-followup-20261116/docs/p_followup/FINAL_REPORT.md （科学闭合494eb4cf，00:01日报90bf9bf8）。最后完整检查4536755请求单机16CPU，限定CPU分区8–19、Nice0、非exclusive、空CUDA；00:32CST仍PENDING、分配0秒，无单机16核空位。按现行规则继续排队，不使用GPU节点替代。科学部分完成不等于本线工程结项，最终检查及PR仍待办。

## 2026-11-20 01:14 CST · P 配方线运行更新
- C3 seed1 已实际启动：普通 sbatch 4536799，compute-0-6 / RTX 3090，GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef；16 CPU，非 exclusive。已核实 UID1278 / PID=PGID2003482 / start_ticks1990923379、实际 CUDA 上下文及正向 CSV 进度；B32/FP32、3M、11-07 归一化不变。只补 C3，对照复用已就绪 M2 seed1，不重复训练对照。
- PP/F2/X1/X2 原任务持续运行；四臂 1M 完整断点均保留，X1 新 2M 完整断点已在 node20 核实（230892519 B）。不停止或迁移健康训练。
- F1 已按实际 2 CPU 的串行加载器/逐头过拟合需求重新扫描卡位，当前无合规普通 sbatch 空卡；继续等待，尚未执行验收。开发已用600秒、剩余13800秒，资源等待不计。
- CPU 统计/报告只在8–19；GPU任务按规模分组，compute-0-21禁用。真实磁盘/inode/UID和跨线预算保护保持，当前 C3 seed1 已在既有 P61GB/全局114569896448B 预留内；无新增预算、无删除/大文件迁移。不操作其他工作线作业。

[P heads T2 TWO-SEED DECISION / finalH STARTED /2026-11-20 01:09 CST] T2正式R3 TIE、R1独立TIE；新S1 R3 candidate .44194477249539066/B3 .4406415201948996，Δ+.0013032523004910535、95%CI[−.009372422341078549,.011136945517705965]；R1新Δ+.009722118146321235、CI[−.0024079925355455635,.02278484642280607]。旧S0点/CI缓存复用、只新S1 paired；直接producer B3/reference R3训练噪声.03386191168730612，CYP4/VAL109只copy。current_best_confirmation_required=false，因此不触发CURRENT_BEST 3M确认；无新胜出配置交接，不提前给尚在跑T5结论。
原T2亲4536355真实C0/23:08:39，Start11-19 01:59:22 End11-20 01:08:01；CPU17字段6289 C0/4秒、判定6290 C0/2秒。最终3M CP232064317B/00:59:51.676574727的首次metadata及canonical arm/seed/run/output已匹配；未读体/hash。root据原子发布合同启动唯一H4536798 CPU17/cpu/4CPU/nice10000/空CUDA，曾与原评估并行。H agent唯一读取resource PASS：PID3529087/UID1278/PPID3529082/PGID3529087/start2172231180，Linux6,7,102,103与真实srun mask一致；Slurm抽象CPU_IDs12–15不硬当Linux号。actual root61218676736B/NFS7177165078528B/inodes2964619736/liveUID429170077696B>167897339904B/MemAvailable381620952kB，模型前guard后exec保持身份；原L6/5000VAL/47698构象/F64/1000MID方法不变，新H科学行与成本待C0。
本线T2自身GPU已释放；随后node6实际GPU12530/24576MiB，PID2003482对应新job4536799（只读ps/cgroup确认），CPU40/48已分配，不能据本通知当空卡；heads未操作该进程/作业。当前剩余本线GPU训练为T5，01:01样本2128000/u66500，其最终判定/H与T2最终H、最终报告/default fullreg/checker/未合并PR仍必做。纯CPU8–19、现有训练/其它用户保护、真实容量/UID跨线预留继续，C3属于配方线，本线未结项。

[P heads T2 seed1 FINAL GEOMETRY COMPLETE /2026-11-20 01:58 CST] H4536798 CPU17/cpu真实COMPLETED0:0，Start01:04:17 End01:51:22，Elapsed47:05/AllocCPUS4，producer2802.024062秒。H owner仅唯一消费新增T2_seed1层6：CEV .493523 [.480698,.503226]；EEV .320708 [.319169,.322410]；CVF .0316983 [.0303328,.0329266]；CVF_res .0621256 [.0595298,.0648603]。exact3M/5000VAL/47698构象/F64/四项各1000原MID bootstrap保持，仅现成CI描述，无新方向/paired/delta检验；旧rows/CP/资源不复读。H1方法、实际Linux6,7,102,103与srun绑定、容量PASS及正常mean.npy生命周期脚注恢复，最终残留库存仍留所有H后核对。
新增3.1388889 allocation CPU-h，成功几何按原Elapsed秒数累计18.2144444h，H GPU仍6.2251h；旧NFS等待2.6022222CPU-h、CPU18 metadata .0555556及其它管理/读出CPU另列。当前无active H writer；T1/T2/T3/T4两seed正式判定与最终H闭合，剩余本线科学工作为T5 seed1原3M/原R1R3/两seed判定/最终H。T5最近01:31:38实际R/2192000样本/u68500，不提前判定。
最终回归入口修正2e94ce05已推送：不再把Slurm抽象CPU_IDs当Linux号，沿用已成功H worker的srun threads实际mask核对/进程身份记录，测试模块范围不变；最终默认完整回归、独立仓库检查和PR仍留全部科学完成后。现有训练不迁移/停止，新纯CPU只8–19，按需/非exclusive与真实容量/UID跨线预留继续；C3归配方线，heads不操作，未结项。

[P heads T5 pending CPU posts retarget /2026-11-20 05:43 CST] root实核原字段4536291/两seed4536292均PENDING、RunTime0、Restarts0、UID1278/本线WorkDir、CPU1/cpu/nice10000及afterok4536260(unfulfilled)后，hold/update/release同ID，ReqNodeList从满CPU16改compute-0-17。原body/工作目录/CPU数/原训练完成依赖保持；两job均已释放全部hold、正priority4294607412/4294607411、正常Dependency，仍未执行统计或复制。训练4536260保持原node4/原3M/R1R3；最近05:31:38实际R/2688000样本/u84000，不提前判T5。
CPU17现场CPUAlloc184/192（8free）；05:41:50实际guard PASS：root61218848768B/total75125227520/inodes36522200、NFS7084508708864B/inodes2964614665、liveUID426173317120B>167867721728B、quota age1.535s，MemAvailable380995732kB。own_allocated12300034048B/remaining13469769728B、followup剩余4628148224B，合并24GiB/跨线预留/rootfloor保护保持；未把sinfo FreeMem当MemAvailable。此为资源变更，无新训练/新检验/重读旧统计，CPU只8–19、按需/非exclusive，所有在跑任务及C3保持不动。
T1/T2/T3/T4正式判定与最终H已闭合，只余T5原训练/评价/两seed判定/最终H；最终报告/default fullreg/checker/未合并PR仍在全部科学完成之后。11/18过长日报已压缩并推送9b7964b5，实际实验/JSON产物未改，详情仍在专题与Git历史。本线未结项。

[P heads USER STOP DIRECTIVE /2026-11-20 06:20 CST] GitHub e7aeea0d新增docs/p_heads/USER_DIRECTIVE_20261119.md，立即生效并明确取消T5 seed1及专用后处理。root实核UID1278/本线WorkDir/job身份后取消4536260、4536291、4536292；实际sacct均CANCELLED by1278，End06:20:53。训练Start11/19 06:43:45、Elapsed23:37:08/AllocCPUS15，两后处理运行0。已有断点、日志、输出和成本保留，无文件删除；node4之后仅4个gmx GPU上下文，均未操作。
T5依seed0最终无显著改善，不计算seed1 H；T1–T4两种子判定原样保留、不重判，无胜出项交接。以上旧T5继续训练/评价/seed1 H安排自此取代。余项为最终报告、一次默认完整回归、独立仓库检查、开PR不合并，本线尚未结项。

[P heads final validation recovery /2026-11-20] Science complete under USER_DIRECTIVE_20261119; T5 S1/its posts canceled and no S1 H needed, T1-T4 judgments retained. Initial full-suite4536860 enumerated192modules but8CPU violated real-provider fixtures>=16; core recorded3638tests/14failures/50errors/24skips and metadata Path exportfailed. Root acknowledged resource choice, restored actual16CPU requirement (no spoofed Slurm vars or weakened assertions), fixed Path-only metadata conversion; valid retry4536884 is PENDING, not counted passed. Initial checker6866 lackedGit and was incomplete; corrected6885 ran default checker and produced202errors, all outside this branch changed-path set (9633files/5002Python). Full scanner output retained in results/p_heads/REPOSITORY_CHECK.json. Original logs and all scientific outputs retained; no model/statistical reruns. Remain real16CPU fullreg result, finalreport/evidence and PR unmerged; notclosed. CPU8-19 only/nonexclusive, otherjobs/C3 untouched.

[P heads final regression CPU pool /2026-11-20] Same pending job4536884 now waits on the admitted CPU-only pool8/9/10/11/12/13/15/16/17/19 instead of fixed17. Actual-node root/tmp bytes+inodes, live UID quota+concurrent headroom passed the existing guard with10GiB tmp future budget; MemAvailable read on each node. Nodes14/18 timed out and are excluded, as is GPU node2 in cpu partition. Runtime exact-host gate and existing actual-node capacity guards apply before scientific output and during work. Still one job/one node/real16CPUs/nice10000/4h; same full192modules/two workers, no duplicate run or new reservation budget. It remains pending, not passed; science complete, other jobs/C3 untouched.

- 2026-11-20 11:08 CST · p-heads：回归4536884实际仍PENDING/0秒/Restarts0，核实priority/basic下原Nice10000造成额外让位后恢复普通Nice0，同步本线sbatch默认值；同一job、真实16CPU、容量已核实CPU池及4h时限保持，无抢占或重提。科学结果不变，无胜出项交接；C3仍归配方线。完整回归未完成，本线尚未结项。

## 2026-11-20 D 阶段0共享存储通知
用户已授权 GitHub docs/s-d-taskbooks-20261119 的 D 家族任务书。D 工作树 MFM_d_recipe，数据工作树 MFM_d_descriptors_20261120。现仅提交 CPU 环境/新逻辑测试/5000分子成本作业4537091、4537092、4537093、4537113，排队中，排除NFS异常18，不动其他线作业；D GPU等待P冻结且P9M提交。成本面板在/share预留4GiB，测试小临时目录也在/share，不占B0的/dev/shm预算，不复制源DB；全量生产预算尚未预留。D写入守卫使用现有实时UID配额，保留100GB底线，并联合核算登记模型总池114569896448B（含P61GB）、B0两组Pprime各80GB未来预测扣已用物理量、24GiB环境余量、1GiB元数据及未关闭几何未来；已封存几何按原生C0记录退掉未来量。仅追加此接口通知；D无科学结果/接收验收结论。

[S recipe authorized preparation / 2026-11-20 12:15 CST] User explicitly selected current p-recipe as the s-recipe base. Published base49f1c6bc9d699085474fa86b7d5638a3c5231246; independent target MFM_s_recipe. CPU setup4537087 and afterok new-logic tests4537088 remain PENDING (Priority/Dependency) at12:11:43; monitor every1800s and retain existing handles. Source/staging/control: runs/s_recipe_20261120; source+common-population preparation forecast2GiB on NFS, with existing100GB account floor, concurrent forecast and liveUID guard. No S GPU training or GPU reservation; S GPU starts only after P recipe freeze and P9M submission per TASKBOOK. S work does not change other lines' arms, budgets or active jobs. New code and tests are prepared, not passed; population/rotor index and baseline acceptance remain pending.

## 2026-11-20 B1 CUDA128 Lustre 环境预留
下游 B1/C1 为开发节点22候选执行准备兼容环境，尚未启动该节点GPU任务。已在实际CPU目标节点核实 /lfshome 的字节/inode与UID1278配额；新前缀 /lfshome/zixiao/benchmark_B1_environments_20261120/gpu_cu128_backend_node22_v1 预留16GiB，包含下载包、解压、安装临时峰值，运行中每20秒核查真实目标配额并保留100GiB。原/share账户新增环境预算被守卫拦下，未下载、未降低预留；既有模型114569896448B池、B0两组量化未来量、D阶段0的/share 4GiB及本线/share预算保持。此新前缀只存软件包，不复制数据库或科学标签。环境准备在CPU作业4537025的步骤1进行；模型版本Chemprop2.2.2/TabPFN10.2.0与原预算不变。候选22卡当前为他人Gromacs进程，不是配方9M使用卡；若后续使用，按20/22现行共享规则、真实GPU/UID与公共锁准入，不干预他人进程。现有5/7两张GPU任务继续。安装关闭后另追加实际状态并退掉未来安装峰值预留。

## 2026-11-20 B1 CUDA128 关闭与节点22实际执行
Lustre软件包准备已在原生CPU步骤4537025.1关闭/C0；Torch2.7.1+cu128的sm120支持及Chemprop2.2.2/TabPFN10.2.0隔离环境在CPU步骤4537025.5导入通过。此前16GiB下载/解压未来峰值预留已退，现有软件包占用已进入/lfshome真实UID配额；没有数据库复制、模型预算或标签变更。此前/share容量守卫拒绝的尝试仍保留失败记录，未降低/shared预算。
节点22已按现行20/22共享规则启动Joung e1 Chemprop正式25折数组4537335（4CPU，0-4%1），实际子任务4537336已完成首个50epoch拟合。目标UUID GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef；启动前原有他人Gromacs为UID1283、约0.7GiB显存/87%利用率，保持运行，不称独占或计算空闲。公共UUID锁、真实CPU分配、显存≤30%且足够余量、根盘/共享盘字节/inode和账户保护继续；若已有同UID上下文（含配方9M）则拒绝启动。配方9M在用卡没有占用。原GPU5的未启动e1数组4537266在零运行时取消；GPU5 e2改等e0实际关闭，避免跳过旧依赖造成同卡双启动。


## 2026-11-20 P storage forecast reconciliation (14:07 CST)

P retired 8,000,000,000 bytes of unused future reservation after the Nov19 cancellations and single-seed9M directive. Active P reserve is 53,000,000,000 bytes; the global model peak is 106,569,896,448 bytes, with all other model reservations unchanged (53,569,896,448 bytes). The authoritative live registry is `/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/model_output_budget.json`, active key `p_recipe_remaining_plan_20261120`.

Actual P physical allocation on compute-0-6 was 30,357,630,976 bytes. Remaining forecast retains 63 checkpoints at <=300MB (F1 two milestones, conditional F1seed1 three, five9M runs45, six cooperative handoffs, seven concurrent temporary saves), plus3GB logs/readouts: projected52,257,630,976 bytes, rounded to53GB. Future additional migrations/recovery saves require a refreshed forecast. All existing files/checkpoints are retained; no quota/root/inode guard or the100GB account floor/8GiB buffer was reduced. F1's own quota controller automatically continued the same PID2012066 from its retained state after admission passed; progress1587136->1593792, no rollback or sample replay. No other-window job was operated and no new GPU run was launched.

### 2026-11-20 D 阶段 0：下游源输入排队与联合峰值

已提交 4537346（开发源输入，1CPU/4GiB RAM）与 4537347（基准源输入，1CPU/8GiB RAM），都 afterok:4537113；14:27 核实仍等待测试成功。两项只准备无标签结构/旧 D 特征，不做新宽库或模型拟合。D 成本面板4GiB＋基准元数据8GiB＋开发元数据0.5GiB 共同采用一份14GiB峰值准入（含缓冲），不是每作业各可占14GiB；所有实际大写入仍先查目标节点字节/inode/新鲜UID quota和剩余peer预算，空间不足保留断点。未来全量预算尚未预约，启动前须把当时未完成D输入写入计入同盘联合峰值。

基准特征导出使用既有活动来源清单、原五deferred排除与封存 SharedB0Reader；不以最终评测冻结为前置、不改变端点/划分、不读取TEST标签。最终C1评测仍由基准线按其冻结协议执行。新开发几何前缀读取与显式H策略接口已写好，但H策略尚待用户回答，未计算D3；阶段0尚未交付，无D科学结果或GPU运行。


2026-11-20 S线新增NFS总峰值预留64GiB（替代先前2GiB，非叠加）：原生转键SQLite约19.63GB含索引/事务预估，六臂与条件seed1/merge每3M最多2GiB，9M每条最多4GiB，另含源码/初始化/诊断/日志并发。所有输出仅runs/s_recipe_20261120与MFM_s_recipe，复用v31原数据不复制，CPU8–19；启动/运行均核实际字节/inode及UID1278配额，未知/不足暂停新增写入。未启动S GPU，仍等P冻结和P9M提交。


## 2026-11-20 P 线：撤销已取消测速任务的5090预留

2026-11-20 08:16UTC · 5090过期预留撤销 · 实际sacct确认提速线旧待跑4535799已于11:48:24 CST取消（CANCELLED by1278、ElapsedRaw=0、从未分配节点）。依HPC技能1.0.163中11-20用户取消5090测速的授权，P启动配置gpu_priority_active改为false；不再据此排除全部5090，仍按预算分组、5090>4090>3090及实际GPU UUID/CPU/显存/磁盘配额准入。9M全部新开关关闭、不使用付费服务器；当前F1和其他线作业不停止、不迁移。



## 2026-11-20 16:24 D阶段0：新逻辑测试通过，成本/输入准备就绪

D 新逻辑215项在 compute-0-17 原生SSH单核短程测试全部通过（UID1278/PID1392349，exit0，5.67秒，RSS923640KiB）；原始日志 `/share/home/zixiao/descriptor_analysis/D_native_cpu_tests_20261120_1622.log`，没有伪造Slurm身份。修正计算节点真实NFS锚点 `/share/home`；配额作用域仍为发布器的 `/share`，真实字节/inode/UID配额及100GB底线不变。原地只读复用既有pyarrow25.0.1，未改共享环境。旧4537113/7202/7261/7346/7347在零运行时间取消，Slurm终态已核实。现阶段0成本4537408、afterok成本的全量规划4537409、开发/基准无标签输入4537410/4537411均仍排队；一份14GiB联合NFS峰值保持原登记。全量、真实接收、D训练/读出均未完成；P冻结前不启动D GPU，不改其他线任务。


### 2026-11-20 D stage0 full-production admission (18:10 CST)

D only: cost pilot4537446 COMPLETED0:0 on CPU10 (L1/L2 each5000 TRAIN); source count4537409 COMPLETED0:0 gives1201795 unique rows (TRAIN1194228, commonVAL7567). Forecast new full-output peak21673668317 bytes. Joint D NFS peak36706053853 bytes includes earlier15032385536 pilot/downstream budget; actual CPU17 root/NFS bytes/inodes and fresh UID1278 quota guard PASSED before submission, retaining100GB quota floor and existing model/B0/environment futures. This joint peak replaces the earlier14GiB D forecast; not additive to it. Full producer and active benchmark preparation will check the same joint peak at runtime. No node-local database copy. Native single-core CPU17 new-logic tests233 PASS, log D_native_cpu_tests_20261120_1802.log; no fictitious Slurm identity. Development source inputs4537410 completed; earlier benchmark metadata retained, active preparation now uses the author-approved NMR2018/pKa source manifests and original geometry namespaces. No D GPU launch, final reception, model fits, endpoint changes, or scientific success claimed; P is still pending freeze.


### 2026-11-20 D stage0 actual launch and benchmark limitation (18:14 CST)

Full L1/L2 job4537508 is RUNNING on CPU10,4CPU=3workers+parent; shared D peak36706053853 bytes and runtime guards unchanged. Actual source ac32340a53b4c82a01129c777db7e4306bfab521; only unstarted concurrency/allocation adjusted, no scientific changes. Active benchmark preparation4537509 COMPLETED0:0 in5min but producer status UNRESOLVED_CANONICAL_D20_BINDING:194729 unique/335120 members,38546 unresolved (NMR38514,other32). Together with4537426 this is two actual unresolved binding attempts: per D taskbook3.5 stop further diagnosis/repair of this item, keep both outputs, no guessed aliases/missing/success. Full TRAIN/VAL and development preparation continue; wide arms await complete delivery and true reception. No D GPU or final scientific decision.


### 2026-11-20 D library-specific continuation (18:57 CST)

Original benchmark D20 binding remains UNRESOLVED after4537426/4537509; no further repair, guessed aliases or D20 recalculation. L1 full delivery remains limited. D taskbook4.1 specifies no cross-library D20 mapping for L2: an independent whole-L2 export from the same active original graphs/member IDs will follow full TRAIN field/statistics closure. This exports only2D; benchmark window retains its own sealed S-prime UFF D3 and frozen endpoints/splits. Two retained source-preparation directories physically total2097127424 bytes; new L2 F64/status about2.827GB, within the original8GiB benchmark allowance and unchanged joint D36706053853 bytes. Fresh CPU10 UID/NFS guard passed. Full4537508 running, true reception4537514/development export4537517 wait afterok. New-logic259 tests passed in real4537508.step4 (1CPU6.23s); no actual Section5 fits or D GPU. Closed pilot cost aggregation adds zero descriptor calls; both libraries0 whole-row failure, L2 any-field missing100% is distinct.


### 2026-11-20 D development QM9 native D3 component closed (20:12 CST)

Actual4537546 COMPLETED0:0 onCPU17,1CPU requested/2logical allocated,648s Slurm/647.574s producer.10473 original QM9 members/41closed parts; manifest /share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/qm9/manifest.json. RAW_COMPLETE for QM9 only; complete_source_population=false (full source15751). Native-only original Z/F64 coordinates and source atom IDs; no hydrogen coordinates/conformers generated, endpoint reads, normalization refit or independent numeric QA. ExpansionRx H policy remains pending; complete development D3/Section5 controls not ready. Full4537508 continues; reception4537514/development export4537517/L2benchmark export4537537 still depend on full closure. Existing D20 binding UNRESOLVED/timebox unchanged. Joint D NFS peak36706053853 bytes unchanged; native D3 components+merge share existing512MiB allowance.270 new-logic tests passed4537544 (1CPU requested/2logical allocated,7s,0:0). P official recipe not frozen at latest read; no D GPU or scientific decision.


### 2026-11-20 D shared-future reconciliation (20:20 CST)

D now reserves S study full64GiB plus benchmark B1 announced40GiB, retaining existing24GiB environment/1GiB miscellaneous and model/P25,327,352,832B futures separately. Release only new-scope B0 Pprime future: actual4536906 COMPLETED0:0 (04:24:01), tail4536907 COMPLETED0:0 (1s), access immutable/writers_closed/cross_node_read_allowed UID1278 and producer ALL_QUEUED_PPRIME_TERMINAL verified. Its3,739,791,360 committed physical bytes remain in filesystem/quota usage; original B0 producer4536588 is live and its remaining forecast stays reserved. Own storage_reservations.json reconciled using existing guard logic, no scientific/source-data change. CPU10 fresh UID/NFS/root/tmp/inode guard PASSED with joint D36,706,053,853B and observed other futures221,053,414,400B, plus100GB UID floor. No D producer interruption or extra CPU/GPU test. S owner's tools/s_recipe/runtime.py still displayed old D14GiB claim at read: its next admission should use current D36,706,053,853B (replace14GiB, do not add both); this notice changes only shared STATUS, no other window's code/jobs.


## 2026-11-20 20:32 CST P final recipe freeze and five9M launch

P final registered screening is closed using the original cached paired results. F1 is TIE (R3 delta -0.002391554478365754, CI[-0.013084806316985923,0.008434799573100492]); no adoption/seed1. F2 removal TIE crosses zero and is adopted under Nov19. Final frozen components A1+B3+B4+F2; both side-line recipe decisions complete with no adoptions. Runnable configs/p_recipe/fixed_20261115/FROZEN_P.json and round4_decision.json are present; freeze CPU4537549 COMPLETED0:0 (10s,2allocatedCPU17), no extra merge training or statistical replay.

All five seed0 B32/FP329M runs started with ALL_OFF/16CPU/14readers: T1 node22 RTX5090 native PID82513 + same-task sbatch takeover4537552; T2 node20 RTX4090 sbatch4537553; T4 node20 other RTX4090 native PID156429 + same-task takeover4537554; T5 node5 RTX3090 sbatch4537555; T6 node6 RTX3090 sbatch4537556. Actual20:32 node observations match all five UID1278/PID/start_ticks/PGID identities and positive optimizer/sample progress. T1/T4 source continuations retain full-state takeover; no exclusive allocation. T3/T7 remain cancelled, no9M seed1. No school-server P job.

Actual target nodes20/22/5/6/7 passed root/NFS/Lustre bytes+inodes and fresh UID quotas. P53GB/global106569896448B pool unchanged; NFS joint admission reads the current D/B0/benchmark registry (already includes S64GiB), adds D joint36706053853B once, and respects closed benchmark Lustre environment preparation (no future16GiB claim). NFS quota required about366.31GB vs387.99GB available; Lustre144.89GB vs146.73GB, unchanged100GB floor+8GiBbuffer. All old outputs/cost preserved. S/D gating may now use this actual P freeze+P9M submission milestone, but their owner schedules/launches their own jobs. P remains active through all five9M, final comparisons/scaling/cost/parameters and one finalREPORT/PR7 closure.


### 2026-11-20 22:27CST · D 原生阶段1启动与共享预算

P官方FROZEN_P(A1/B3/B4/F2)及五条单种子9M已提交，D训练预注册已发布 d-recipe a3b774dc3218fb91b48d98aa84cbe4f930f9aea8；仅迁移A1/B3/B4，F2无D对应物。D-R0正式4537572在CPU5/GPU compute-0-7运行，UUID GPU-9db54192-dd3f-3177-e56f-dcd161ff932c，原生D20+D3、3M、seed0；已见1792实际样本，未完成。前一4537570在CUDA初始化失败且无训练输出，后续复用既有P的cu118环境选择(9b97858)，科学条件/初始化seed未变。A1完整原TRAIN collector4537571在CPU17运行，请求1CPU/站点分配2逻辑CPU，已见1792关闭行；ridge alpha1.0/5折seed20261112开拟合前冻结，不选参。287项新逻辑真实4537569 C0，完整回归仍只在PR前一次。

实际GPU7预检：根53,653,090,304B/36,529,159空闲inode；NFS6,757,742,018,560B/2,964,413,577 inode；Lustre新鲜UID可用146,449,399,808B，含D提案所需145,946,002,944B，100GB底线、8GiB原生缓冲及6GB同行预留均保留。全局model_output_budget仅新增D直接root及本阶段R0 1,342,177,280B，total_peak107,912,073,728B；后续D模型需另行核容，不修改P作业。

D联合NFS **36,706,053,853B不增加**。data分支4dc392b0ae1dd8a084a7aee01e2c63e43dd66861明确重新分配旧未用pilot/基准预测，保留所有既有文件与原stage0-only21,673,668,317B；full范围新增上界29,750,000,000B现含full/native_stage1 A1 2GiB、R0四层cache4GiB、R1检查点1GiB和元数据；外部保留6,930,530,176B，总36,680,530,176B不超joint。四层ready-atom metadata371493*4*512*4=3,043,270,656B数值，非全库复制。已有peer守卫按full实存扣未来可自动消费新cap；S若仍记D14GiB请由owner改为现joint。运行期D同时复用数据guard和既有heads只读联合quota observer，覆盖S64GiB、基准40GiB、原B0及其他同行，不修改它们代码/作业。

全量4537508继续L2(最近373/4695闭合parts)，L1 RAW_COMPLETE；真实64接收/开发导出/独立L2基准导出依赖仍保留。暂无D胜负或最终报告，ExpansionRx缺H政策仍待用户，未补H/改变几何。


## P storage forecast active five9M / 4537577

ClosedF1TIE requires no seed1. Actual retained P physical bytes=31181479936; remaining milestone checkpoints=45, five further full-state handoff/recovery slots and five concurrent temporaries, each<=300MB, plus3GB logs/readouts. Projected P peak=50681479936B; reserve 53000000000 -> 51000000000B. Global model peak 107912073728 -> 105912073728B; all other model reservations unchanged at 54912073728B. No old output/checkpoint removed. Root/inode protection and100GB UID floor+8GiB buffer retained. Active registry /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/model_output_budget.json key p_recipe_remaining_plan_20261120_confirming. Extra recovery/migration beyond this forecast needs re-admission.


### 2026-11-20 15:04:26 UTC · D 固定诊断节点根盘预算（NFS/Lustre预测不增加）

D已发布890bceb527e0021feb82736a04a3aa8a28de1152，300项新逻辑在真实CPU17/4537571.step8完成0:0（Slurm7秒，测试主体1.077秒）。按任务书仅为D-R0既定seed0/3M终点准备固定5000VAL、层3–6的一次诊断前向和后续CPU统计；没有新增训练或全层扫描。原M/允许构象元数据实际4537571.step4给出265478首构象原子、47698构象，F64值数组5131075584B，未读坐标/标签帧或做前向。

请同节点缓存/传输工作计入以下本线未来峰值：**compute-0-7根/tmp 8GiB**，路径`/tmp/d_recipe_20261120_D_R0_seed0_3M`；**compute-0-17根/tmp 12GiB**，目标同绝对路径，含5.13GB cache、保留partial/旧文件、最大4.35GB rsync临时及缓冲。两个峰值属于不同节点的根盘，不记到共享NFS。实际预检GPU7约53653098496B/36529140空闲inode，CPU17实际4537571.step7为52891484160B/36501647，均XFS/noquota；8/12GiB入口守卫通过，且实际启动前和运行时再次核实max(10GiB,10%)系统/Slurm余量。当前没有开始新缓存复制，不允许其他窗口把这些未来峰值同时用掉。

仅复制本任务闭合的诊断cache到CPU17；不复制原LMDB、不改值/原子顺序/manifest路径、不加独立QA/hash、不删旧输出。rsync复用现有进程组磁盘守卫并保留partial，transport SSH不加-n。全局Lustre D-R0 1.25GiB及D联合NFS36706053853B保持原值；没有为这些根盘cache增加NFS/Lustre future。D-R0/A1/L2在跑，原子SASA/原目标TRAIN截断报告4537578仍等A1闭合。累计4h诊断时间盒和既有科学判定不变，尚无D胜负或最终冻结。


### 2026-11-20 15:55:21 UTC · D-R1原生迁移准备与GPU7合计根盘24GiB

D已发布5535d8ad099df002cd43ddf07822ae2a3aa734e2：既定D-R1 D20+D3、3M/seed0冷启动，仅A1/B3/B4，gamma0.1597693323500406；等完整TRAIN A1拟合/冻结参数4537575成功再启动，不增加训练臂/seed/超参。302项新逻辑真实CPU17/4537571.step11完成0:0，Slurm9秒（主体1.110秒）。R0仍在跑，不因本次准备重启或迁移。

**compute-0-7根/tmp合计24GiB**：原R0 VAL scope8GiB，加R1 native层缓存`/tmp/d_recipe_20261120_D_R1_native_layers`8GiB，加R1 VAL scope`/tmp/d_recipe_20261120_D_R1_seed0_3M_VAL`8GiB；不是每项24GiB。每个相应新本地writer显式带16GiB同行future，由原根盘守卫叠加自身8GiB、系统/Slurm max(10GiB,10%)及运行余量。新字段默认0，不影响现有非本地任务。实际GPU7 R1联合守卫已通过；实际启动继续核实空卡UUID/CPU和真实目标盘，不占着未满足依赖的GPU。

**compute-0-10根/tmp新增12GiB**，`/tmp/d_recipe_20261120_D_R1_seed0_3M_VAL`，仅接收R1闭合5.13GB VAL cache，计入old/partial和4.35GB rsync临时；不复制原LMDB，也不复制3GB开发H0缓存到CPU。CPU10实际根/tmp70070484992B可用、36570105空闲inode，XFS/noquota，12GiB入口及共享UID联合守卫通过；该节点既有D阶段0输出仍走NFS。原CPU17 R0 VAL12GiB预测保持。

R1检查点/读出1GiB已在原full/native_stage1命名预算内，**D联合NFS36706053853B、full29.75GB和Lustre原R0 1.25GiB均不增加**；所有旧输出保留。对应JSON配置和比较脚本已准备，比较等两个主CPU评分均闭合，只消费既有配对1000次bootstrap。未查看A1 OOF数值、未产生R1分数、未预判胜负或冻结终点。请同节点传输/cache工作纳入以上并发future。


## 2026-11-21 09:28:33 CST · D Root：R0规定诊断全部闭合，撤销其已结束本地写入future

R0表示统计4537581已实际COMPLETED/0:0（CPU17/2分配CPU/4446秒）；原前向4537579、cache传输4537580、缓存层读出4537584/4537585及主训练/统计4537572/4537573均已C0。固定5000VAL/47698构象的层3–6 F64 PR/CEV/CVF/CVF_res与逐层读出均闭合；结果仅描述，主R3仍第6层0.3047600714630222，CURRENT_BEST未冻结。原完整谱与bootstrap已保存共享盘原运行目录representation_statistics；所有物理cache及旧结果保留，没有额外前向或重算。

本次依据实际写入者闭合（非GPU暂时空闲）撤销GPU7 R0 VAL 8GiB、CPU17 R0 12GiB未来写入：**GPU7 D future由24降为16GiB，仅R1 native8+R1 VAL8；CPU17 R0 future降为0；CPU10 R1 future仍12GiB。** GPU7/CPU17原R0 cache物理占用5133008896B/5133246464B保留、继续由实际df扣除；不可把撤销future误作删除或释放这些实存。实查两节点根盘总量各75125227520B，可用48517754880B/47753945088B，空闲inode36529111/36501585；实际开始/运行仍叠加同行future、max(10GiB,10%)系统/Slurm空间和UID限制。未启动R1配置同步并发scope预算8GiB，已结束R0配置保留原历史口径。

D联合NFS36706053853B、full29.75GB、Lustre模型池1.25GiB保持。A1/L2原生产继续，R1仍等A1，未持有GPU7或修改其他owner作业；请同行仅更新上述同节点未来写入预算。R1可选F64 PR分块256仅执行参数，默认32保留、公式及1000次配对抽样不变，7项相关CPU新逻辑测试已通过；没有实测提速主张。


## 2026-11-21 12:18:56 CST · D Root：两库原始计算闭合，L1按时间盒未解决，L2独立统计继续

原4537508已闭合1201795行L1/L2原始F64+状态，各4695批、217/1613字段；原数组与生产者对齐标记保留。L1唯一TRAIN统计中的7个raw非恒定稀有计数在既定缩尾后std0，原最终化4537508 FAILED1:0/64639秒，复用原产物的4537574同错FAILED1:0/43秒。依TASKBOOK第3节连续两次实际失败，**L1=UNRESOLVED，D-L1不跑、保留对照**；不是TIE/LOSS，也不改预注册过滤、补epsilon或删字段。原raw manifest及L1统计完整保存Data结果目录，Root报告results/d_recipe/stage0_full_status_20261121.json。

**L2首次全TRAIN统计4537771已实际RUNNING于compute-0-10，请求1CPU**；旧4CPU全阶段已终止，只有该统计继续。新增明确未解决库的默认关闭执行入口，3项相关测试在CPU17/4537571.step27通过，无重算L1统计或原始描述符。L2真实64样本接收4537772、原开发导出4537517及独立基准L2导出4537537均afterok4537771。旧双库接收4537514经UID1278/PENDING/0秒核实后取消，仅自身未启动句柄；未动其他owner任务。L2仍需原统计、接收及导出闭合，当前不是阶段0交付完成。

原生A1 4537571继续收集，R1 4537592仍等4537575，原比较与诊断链保持。D联合NFS36706053853B/full29.75GB/Lustre模型1.25GiB不增加；GPU7未来16GiB、CPU17 R0未来0、CPU10 R1目标未来12GiB保持，所有物理cache保留。CPU10实际目标NFS/root bytes/inode已核实，运行期真实UID/同行future/系统底线守卫继续。请下游以最终清单中的逐库状态为准，不消费L1为已交付库。


## 2026-11-21 12:30:12 CST · D Root：L2亦两次零尺度失败，两宽库未解决，原生主线继续

更新上一条L2在跑状态：唯一L2 TRAIN统计已闭合，65项在既定缩尾后std0；4537771 FAILED1:0/358秒/1CPU，复用原闭合统计的4537773仍同错FAILED1:0/13秒/1CPU。依TASKBOOK第3节两次实际失败，**L1/L2均UNRESOLVED，D-L1/L2不跑，当前无已采纳宽库而K1未触发**；不是TIE/LOSS或“宽库无显著改善”。L1先前7项问题和两次失败记录保持，未改过滤定义、D4、补epsilon、删字段或重拟合。

仅元数据闭合作业4537774已COMPLETED0:0、CPU10/1CPU/12秒，final_manifest.json明确全局及两库UNRESOLVED，没有有效库交付。新4项相关测试在CPU17/4537571.step30通过。原始两库F64数组/状态、完整字段清单、唯一L1/L2统计全部保留；结果转录在Data results/data_d_descriptors和Root results/d_recipe/stage0_full_status_20261121.json。

自身未启动L2接收4537772、开发导出4537517与独立基准L2导出4537537已按zixiao/PENDING/0秒核实后取消，会计均CANCELLED by1278/0秒；没有执行无效接收或导出。原双库接收4537514亦为已取消0秒。原生A1/R1及其比较/诊断依赖保持，D-L2统计已结束，CPU10不再有本线阶段0数值工作；GPU任务仍等A1就绪，不占卡。既有D联合NFS36706053853B/full29.75GB/Lustre1.25GiB及节点future16/0/12GiB仍保守保持，物理实存均保留，实际开始/运行继续真实磁盘/UID/同行守卫。

如需恢复宽库，须用户批准仅对新库补充零尺度字段过滤（7/65项）；当前仅形成可审阅方案，未执行科学修订。请下游按逐库未解决状态处理，不将原始计算闭合或元数据C0当作科学接收完成；其他owner作业与冻结端点不改。


## 2026-11-21 14:26:10 CST · P Root：原 B0 已封存，核销未用未来写入

原 B0 生产4536588和尾作业4537629均实际COMPLETED/0:0；尾作业在CPU8/16CPU以4694秒闭合。原共享目录access已声明UID1278、immutable/writers_closed/cross_node_read_allowed；producer_4537629为ALL_QUEUED_PPRIME_TERMINAL，324794 READY及286 PARTIAL原样保留，P_ready仍false，没有重算或数值复读。

共享configs/data_d_descriptors/storage_reservations.json仅把原80GB B0预测项从B0_labels移到closed_B0_labels、future_write_bytes=0；原注册预测和旧JSON已留存。核销的是49707794432B未用future，所有SQLite/几何实存继续计实际UID配额，没有删除数据。非D同行future由213547842560降为163840048128B；加D联合36706053853B后为200546101981B，与基准线宣布的封存后口径一致。

四个P实际运行节点20/22/5/6用原守卫复核全部ADMITTED，NFS要求358910939869→309203145437B；100GB UID底线/8GiB缓冲、P51GB/其他模型、S64GiB、环境24GiB、基准41GiB、D联合/full29.75GB/Lustre1.25GiB及各节点future16/0/12GiB均保持。没有改训练配方、守卫代码或他人作业。原生D继续，宽库UNRESOLVED不因本次资源核销改成成功。

原配置备份和原生会计在runs/p_recipe_20261113/fixed_20261115；可审阅闭合记录追加到MFM_p_recipe/configs/p_recipe/fixed_20261115/storage_confirmation_20261120.json的original_B0_closed_future_20261121。DataD工作树此项共享元数据已原子更新，请后续提交保留这一原B0闭合记录；其他字段逐项相等，旧“原B0在跑”的basis作为历史快照保留。


## 2026-11-21 22:24:15 CST · D Root

原生A1全1194228 TRAIN/23分子字段唯一拟合已FROZEN_FIT：12残差/11原目标、无未解决，旧D20/D3/D4不改。4537571/4537575均COMPLETED0:0（85805/32秒）；[冻结分档与参数](https://github.com/mint258/MFM/blob/d-recipe/docs/d_recipe/A1_FULL_TRAIN.md)。R1 4537592于22:12:23 CST在compute-0-7、原RTX3090 UUID GPU-9db54192-dd3f-3177-e56f-dcd161ff932c冷启动3M/seed0，5CPU，尚无终点评分。原截断报告以4538106/CPU17/请求1CPU同配置同输出关闭游标续接；真实日志/训练状态保留。后续D离线SDK日志只路由至已预算共享控制scope，避免full-store中的SDK快捷链接；9项相关测试4538106.step0通过。现行NFS36706053853B、Lustre1.25GiB、GPU7未来R1原生8GiB+VAL8GiB、CPU10未来VAL12GiB及全部实存/同行预算不变；CPU17无新本地缓存预算。两宽库仍按原预注册UNRESOLVED，未批准/执行零尺度过滤修订；配方未冻结，R1/G1/条件种子/最终对照/9M继续原规则，不占用或修改同行任务。

[配方线 用户指示 2026-11-22 06:10 CST] 新增 docs/p_recipe/USER_DIRECTIVE_20261121.md：9M 的 1M–9M 断点全部保留；9M 跑完后补跑 T1/T2 的 1M–8M、T4/T5/T6 的 3M/6M 第 6 层 R1/R3，只作预算曲线描述；读出用 compute-0-0~7 的 24GiB 卡，不占 S 线需要的 ≥36GiB 卡；最终 P 报告等这些读出完成后再生成。其他线无需动作。


## 2026-11-22 05:59:49 CST · D Root

用户已明确批准仅补充过滤新库原7/65个缩尾后标准差为0字段；事先记录追加预注册，不改原TRAIN统计、原数组或D20/D3/D4。独立清单`/runs/d_recipe_20261120/full/stores/final_manifest_zero_scale_amendment_20261122.json`启用L1 191项、L2 1314项。真实64 loader接收4538200在CPU10/1CPU完成0:0，162秒，197/197与1320/1320头通过、两库ACCEPTED；[原接收与执行记录](https://github.com/mint258/MFM/blob/d-recipe/docs/d_recipe/ZERO_SCALE_AMENDMENT_20261122.md)。开发双库导出4538204（3CPU）和基准独立L2导出4538205（4CPU）于05:55:23 CST在CPU10恢复RUNNING。现行联合NFS36706053853B、其中已保留开发512MiB/基准L2 3.75GiB预算内续跑，无新增节点本地cache或原库复制。原R1 4537592/GPU7与截断4538112/CPU8继续；宽库GPU训练仍等阶段1配方选择。原D20基准绑定失败及ExpansionRx H政策待定保持，未获H修改授权；配方未冻结，原条件种子/G1/K1/最终对照/9M规则保持，不占用或修改同行任务。


## 2026-11-22 07:22 CST · P：指定22个9M中间断点读出新增NFS预留

按USER_DIRECTIVE_20261121，仅在每条原9M完成后补指定L6/H0 R1/R3，GPU严格0–7/24GiB，CPU8–19（排除14/18），不占≥36GiB，不停止/迁移在跑训练。新增本线NFS峰值3221225472B（22×128MiB+256MiB），仅为readout输出和控制/临时量，不复制断点、不持久化H0。共享MFM_d_descriptors_20261120/configs/data_d_descriptors/storage_reservations.json的registered_model_share_components.P_confirmation_budget_curve已登记该量，registered_model_share_future_bytes由94046829568B变为97268055040B；旧模型/P25327352832B、S68719476736B、D36706053853B、B0与基准预留均保持。CPU8实际联合准入ADMITTED，鲜活NFS UID可用356165890048B>含底线/缓冲需求312424370909B，目标字节/inode及根盘系统空间通过。新入口10项及预算表/最终门8项定向测试均C0；新增GPU读出尚未提交。生产配置和守卫以后读取该最新联合项，勿重复加算，也勿把它计入D/S自身预算。全部旧输出和1M–9M完整断点保留；P固定11-07归一化不变。


## 2026-11-22 08:06:31 CST · D Root

原计划基准独立L2导出4538205/CPU10/4CPU实际COMPLETED0:0，7842秒，194729唯一分子、761批关闭，启用1314/1613字段；开发双库4538204/3CPU也已COMPLETED0:0，612秒、15518唯一分子。原TRAIN统计/参数、原成员划分与原始值不改，不读取任务标签或重拟合。两训练库已由原64 loader接收4538200实际ACCEPTED；本次下游原清单仍保留reception_acceptance=pending、current_C1_complete=false，不代替基准接收/冻结或完整D3对照。基准L2清单为`/runs/d_recipe_20261120/benchmark/L2_descriptors/manifest.json`；[原清单转录与交付状态](https://github.com/mint258/MFM/blob/d-recipe/docs/d_recipe/DOWNSTREAM_INTERFACE.md)。旧D20基准绑定未解决、ExpansionRx H政策待定均保持，未获H修改授权。联合NFS36706053853B及原开发512MiB/基准L2 3.75GiB保留预算不增，无新节点cache或原库复制。R1 4537592/GPU7和截断4538112/CPU8继续，宽库训练仍等阶段1配方选择；配方未冻结，不修改同行任务。


## 2026-11-22 12:32:10 CST · D Root

R1原3M/GPU主读出已闭合，主CPU统计4537593与配对4537599继续原链。F64几何诊断4537594/4538515因容量快照新鲜度准入两次实际失败（3715秒/1秒），按任务书记UNRESOLVED并停止修复；原部分文件保留，可选未生效修复已撤回。原缓存3–5层GPU读出4537597已COMPLETED0:0/1217秒，CPU逐层读出4537598等待主统计。原传输4537595和表示统计4537596均未开始即取消0秒。GPU7的D-R1原8+8GiB与CPU10原12GiB未来写入归零；全部D-R0/D-R1原缓存及部分文件保留，物理占用继续以实际df计入，不删除、不复制原库。联合NFS峰值36706053853B不变；配方未冻结，诊断未解决不作主比较WIN/TIE/LOSS。


## 2026-11-22 14:21:47 CST · D Root

D-R1 seed0 paired R3 is WIN: delta=0.09770468747584315, 95% CI=[0.08195311354654226,0.11189074805862387], tau=0.02012323794694327. The original comparison JSON and identical log closed before job4537599 timed out; do not resample or rerun it. Held successor4538541 was cancelled before starting. Transfer adoption still requires the registered individual seed1 WIN.

The triggered pair is one fresh3M D-R0 seed1 control plus one fresh3M D-R1 seed1. Configuration/storage preparation4538547 onCPU17 was cancelled after RPC wait before configuration generation; dependent replacement4538549 is onCPU8. Neither seed1 training has started. Proposed extra NFS future is2GiB (joint36706053853 ->38853537501B); it is NOT admitted or registered until the live Data plan/configurations close and actual target bytes/inodes/fresh UID quota pass. No seed1 local feature/geometry cache, no additional Lustre growth, no original data copy. Existing clipping4538532 and cached-layer CPU4537598 remain active with original outputs retained. Shared-filesystem RPC waits currently delay progress; do not infer scientific failure or a final recipe decision from them.


## 2026-11-22 14:32:10 CST · D Root

R1 seed0 remains the original paired WIN; no comparison was repeated. Only its two registered fresh3M seed1 runs are now conditionally queued: D-R0 shared control GPU4538551 oncompute-0-4/UUID GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6, D-R1 GPU4538552 oncompute-0-5/UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377. Both require afterok4538549, which must first seal their exact configs/registry and the live Data joint NFS forecast (+2GiB to38853537501B). CPU4538553/4538554 follow their respective GPU; original paired comparison4538555 follows both CPU. Actual squeue shows all five PENDING/Dependency; neither model has started or occupied a GPU.

These are scheduler dependencies, not storage/GPU admission. Unchanged launcher/guards must inspect the assigned real UUID/context/free memory/5CPUs and actual node root/NFS bytes/inodes/fresh5s UID quota plus all peer futures before model execution or large writes. GPU4's completed readonly observation found5.7TB NFS,2.964B free inodes and353221890048B UID quota (effective age1.43558s when read). GPU5 readonly observation returned root/tmp only before the shared10-minute probe4538550 timed out; do not treat that partial observation as shared-filesystem admission. No seed1 diagnostic caches, original-data copies, new Lustre future, transfer adoption, stage2 or9M. Configuration preparation4538549 and original CPU clipping/layer jobs retain their original outputs through current RPC waits. R1 layer CPU4537598 limit is now03:39:00; with original GPU1217s its total allowance is14357s (<4h), deadline16:19:13CST. Node-side STATUS/report mirroring waits for real shared-storage admission; GitHub records current closed science and queued dependency state.


## 2026-11-22 14:39:00 CST · D Root

D Root goal is blocked by the same external shared NFS startup/page-I/O fault confirmed in three consecutive goal turns. Preparation4538549 remains live onCPU8, its process2827663 is D state with zero CPU time before batch entry; both seed1 configs, registry and log are still absent. Original layer/clip workers remain in NFS/page wait with unchanged CPU times. This is no new scientific loss, result invalidation or cancellation. R1 seed0 original paired WIN remains closed.

Retain original clip4538532, layer4537598 (16:19:13CST cumulative diagnostic deadline), preparation4538549, GPU4538551/4538552, CPU4538553/4538554 and comparison4538555. All five seed1 jobs remain PENDING/Dependency. Do not submit duplicates or release cancelled comparison4538541. Existing afterok and actual node GPU/root/NFS/inode/fresh5s UID-quota/peer guards remain in force; the proposed extra2GiB is not live until original preparation seals the Data forecast. No model has started, no transfer adopted, no stage2/9M. All outputs retained; no admin/NFS settings changed. Shared I/O must recover before further substantive work; resume the goal from exact current jobs/artifacts after recovery. Node-side report/STATUS mirroring also waits for actual write admission; GitHub CURRENT_BEST records the blocker without pretending execution is complete.

[配方线 用户指示 2026-11-22 15:15 CST] 新增 docs/p_recipe/USER_DIRECTIVE_20261122.md：转录 9M 预算曲线各读出点的逐任务 R1/R3；对 T2、T1 的 1M/3M/6M/9M 做第 6 层组成信息诊断（预注册 H-comp）；最终 P 报告在其完成后生成。其他线无需动作。

[跨线 用户指示 2026-11-22 15:40 CST] 新增 docs/interfaces/STORAGE_GUARD_20261122.md 与 tools/shared_guard.py：存储/内存预留改为共享登记目录 runs/shared_storage_reservations/，每条线只写自己的 <线名>.json，每次轮询续期，写完释放；新作业用 check_with_timeout()（60 秒超时即拒绝）。不再抄写或公告他线存储数字。在跑作业不动，下一次轮询起迁移。


## 2026-11-22 15:35:44 CST · D Root

Read user11-22 exit/drain prevention and skill1.0.164. All not-yet-started seed1 jobs4538551–4538555 are verified PENDING0s then held (JobHeldUser); do not release until future entry cleanup protection and actual target health are ready. No existing training was interrupted or frozen scientific source changed. This notice does NOT claim new entries already implement exit protection.

Original R1 layer3 score is closed: R3=0.40784337449791125, CI[0.39454694681264635,0.42062377850793353]; R1=0.22251130365828092, CI[0.20889490422663376,0.2364367774943568]. Original1000/20261025 draws retained; layers4/5 remain missing; fixed layer6 main and seed0 paired WIN unchanged. CPU7598 was safely stopped from its closed layer3 prefix: exact UID/PID/start_ticks/job-cgroup rechecked, worker2819839 got oneTERM thenZ; parent2819751 got oneTERM only after no live children remained. Both/proc PIDs are confirmed absent. NativeFAILED0:15/9837s, notTIMEOUT; noKILL. With GPU1217s total11054s, remaining3346s for the same diagnostic after health verification. Original fullTRAIN clip4538532 remains live with its prior closed prefix.

Preparation4538549 remains blocked before script entry. Its PID2827663 is slurmstepd with UIDs[0,1278,0,1278], start_ticks2244925324, not an ordinary owned userworker; no direct signal to it. Observed NFS/page waits do not establish the underlying cause, OOM or full disk. Admin kernel/slurmd/slurmctld/filesystem review is needed; no repeated diagnosis/resubmission on fault nodes, no drain bypass or service/spool changes. Node17 drain attribution is UNCONFIRMED. Existing root/system/inode/UID-quota/peer protections and proposed+2GiB activation gate remain; shared/node report mirroring waits for real write admission.

[配方线 用户指示 2026-11-22 16:30 CST] 新增 docs/p_recipe/USER_DIRECTIVE_20261122B.md：F 微调评测（frozen/top2/full/scratch，T2 1M–9M、T1、T5、T6 9M，四任务三种子）、A1 读出噪声、A2 B4 组成信息、A3 B4 惩罚项大小、A5 P 对 P′ 同一 UFF 几何、A6 QM9 3 万标签、B 去 B4（I1）；最终 P 报告在其后生成。模型容量研究另开 p-capacity-20261122，配方线不执行。


## 2026-11-22 16:40 CST · D Root

D science unchanged: user-approved7/65 new zero-scale exclusions and original unique statistics remain; bothwide libraries accepted and exports closed; original R1 seed0 paired WIN and fixed layer6 main remain. No actual seed1 training or adoption. Five old jobs4538551–4538555 remain held/PENDING0; they embed the OLD copied sbatch scripts, so source publication cannot authorize simply releasing them.

New inactive Root exit-supervision code and wrappers are staged. Original16 source-policy/lifecycle tests +3 shell syntax checks passed onCPU10/4538557 (COMPLETED0:0/23s/1CPU, test0.309s, actual children=[]). Full repository regression remains reserved for prePR. Extended attempts4538558/CPU10 (389s) and4538559/CPU15 (119s) were interrupted before tests closed: existing memory supervisor performed controlled TERM/reap and returned75 with actual children=[] before real deadlines; neither is accepted as18 or2 passing tests. After two infrastructure interruptions, additional clipping-entry integration is UNRESOLVED; no further tests/repairs on those fault channels. The two actual cleanup outcomes are preserved, not disguised as successful tests.

Production activation is still NOT ready. A source-independent outer supervisor must already reside in Slurm-copied/local memory BEFORE reading shared modules. Four staged sbatch templates now default toexit64 unless D_EXIT_OUTER_SUPERVISION is provided by a real supervised launch; setting a flag alone is not proof. Do not submit them directly or release old held jobs. Close outer supervision, canonical configurations/live Data forecast and actual healthy-node admission first, then verify old five still never started, replace with the SAME registered science and rebind dependencies. No duplicate control/seed, no frozen P/D scientific worker changes, no extra GPU/forward. Managed local log forecast must include at least32MiB/log and ALL actual-node peer/D future before activation, retaining max(10GiB,10%) root reserve and inode/fresh5s UID-quota guards. NFS remains36706053853B; proposed+2GiB is not activated by source publication.

Original clip4538532 worker2822119/start_ticks2244363539/UIDsall1278 had exact original job-step cgroup and no children before ONE TERM; afterward it still existed inD, freezer row1:freezer:/, exit UNPROVEN. No repeated signal/KILL/scancel or replacement producer; preserve1020928/1194228 closed cursor, original config/coefficients/conformer choices and arrays. Layer7598 original parent/worker absence remains proven; original layers3/6 closed and4/5 allowance3346s unchanged.

Preparation4538549 still waits at slurmstepd2827663/start_ticks2244925324/UIDs[0,1278,0,1278]; no ordinary user-worker entry, no direct signal. Its actual hard deadline is2026-11-22 18:18:03CST: administrator kernel/slurmd/slurmctld/filesystem review is needed BEFORE then. Underlying root cause and node17 attribution remain UNCONFIRMED. Avoid fresh tasks on observed failing8/10/15 channels and known14/16/17/18;21 prohibited. No service/spool/drain bypass, no existing training interrupted. Root goal was resumed and remains active with the external blocker; do not infer completion or carry old blocked-turn counts into this resumed run.

Root original layer3 JSON and latest docs/CURRENT were mirrored under actual head-target admission including all peer future, proposed2GiB and1MiB metadata; no scientific arrays were reread or duplicated. This notice records Root's actions only and does not claim other sessions have read or deployed it.


## 2026-11-22 16:50 CST · D Root

D Root resumed-goal audit now reached3 consecutive turns with the SAME external preparation/source-I/O blocker. Goal is BLOCKED, NOT complete; full TASKBOOK objective is preserved. Latest lightweight head checks at2026-11-22T08:49:15Z: preparation4538549 RUNNING/02:31:13 onCPU8, original clip4538532 stillRUNNING, old seed1 jobs4538551–4538555 allPENDING/JobHeldUser/0s. Bothseed1 configs and conditional registry remain absent; preparation log exists but0B (mtime16:25:09CST). Historical mixed-rootUID slurmstepd identity is not presented as a fresh fault-node PID observation. No new probe, repair or computation was launched.

Administrator kernel/slurmd/slurmctld/shared-filesystem recovery is required, particularly BEFORE preparation4538549 actual hard deadline18:18:03CST today. No direct signal to management/root processes, repeated kill/scancel, service/spool/drain changes or duplicate producer. Old clipping PID exit remains unproven; original closed1020928/1194228 cursor and all outputs retained. New entry extension remains UNRESOLVED after two safely reaped75 exits; core16 passing tests retained; staged templates remain default64/inactive pending source-independent outer supervision and actual health/config/forecast admission. Do not directly release the five old copied scripts.

After recovery, read actual latest jobs/configs/registry/budgets/artifacts first and preserve any newer progress; NEVER overwrite subsequentREADY or completed state with this blocked snapshot. Original R1 seed0 WIN, approved7/65 filtering and unchanged unique statistics remain. No scientific fallback/adoption/freeze/9M was invented from this infrastructure fault. Still required: actual stage1 seed1 confirmation; selected-recipeL1/L2/G1 and conditionalK1/seeds; allowed diagnostics; finalfreeze/registered cold9M; finalA/B/C, benchmark handoff, reports/costs and two unmergedPRs. All guards and existing other-line training are preserved. No claim that peers have read this notice.


## 2026-11-22 17:38 CST · D Root

User explicitly requested changing nodes and resumed the full D goal. Old preparation4538549 now had an actual owned batch worker2828496/start_ticks2245694583/UIDsall1278 in exactjob4538549/step_batch, no children. OneTERM was sent only after that binding; actualPID ABSENT verified, nativeFAILED0:15/10708s/1CPU, before18:18 deadline. No root/manager signal, KILL or timeout. The old preparation writer cannot race the new canonical files.

CPU19 local OS/RAM is usable; shared statvfs admission4538562 did not close and was safely reaped75/99s. Do not interpret that as shared-disk admission. Actual4538564/C0/1s/1CPU used local OS/RAM and captured exact original planner/fresh-seed/prepare_runtime source, with no shared-source/array/output access. Three new resident rendering tests passed0.001s plus an actual nested resident-child test with children=[]; existing16 lifecycle/policy passes retained. This is not a retry of closed clipping geometry or scientific statistics.

Root canonical D-R0/D-R1 fresh3M seed1 configs and the ONE shared registry are now sealed under actual head-target Guard.wait, fresh5s UID quota and all peer forecasts. Actual Data/live NFS forecast is38853537501B (+2GiB), full31897483648B: original8 slots at232MB plus128MiB NFSlogs/readouts, no Lustre change or seed1 diagnostic cache. Every actual target additionally declares128MiB joint Root local-log future (all planned D logs); original peer forecasts and max(10GiB,10percent) root/inode guards remain. This registration is not actual GPU admission.

New resident_bootstrap renders a Slurm-copied system-Python-ISB supervisor BEFORE shared module or shell startup. It embeds the reviewed original lifecycle, uses real finiteTimeLimit/EndTime,900s cleanup, original cooperativeSAVE_AND_EXIT, exact identity TERM/join/reap, noKILL. The scientific P/D workers remain unchanged, including original card-specific Python, preserved environment,3M schedule/fresh clip/seed/shared sampling. Four old standalone staged templates remain default64 unless truly wrapped. Five old jobs4538551–4538555 are verifiedzixiao/PENDING0s and will be replaced with resident launches, not released. GPU targets4/5, file-dependentCPU9/11/13; original UUID/empty-context/free-GPU/CPU and real-node shared/root/quota/peer admission still run before models.

At this publication no seed1 model has started or recipe been adopted. Original seed0 WIN, accepted7/65 filtering/unique statistics, geometryUR and layer4/5 allowance3346s preserved. Old clip2822119 stillD/freezer root and actualexit unproven; no repeated signal or same-output replacement producer. That residual process still needs admin recovery, independently of new mainline work. Full TASKBOOK stages, conditional seeds/K1, freeze/9M/finalA/B/C/benchmark and twoPR scope remain. Other sessions' receipt/deployment is not claimed.


## 2026-11-22 18:30 CST · D Root

用户要求更换节点后，D 两个全新 seed1 正式 3M 作业4538566/4538567已分别在 compute-0-4/5 的 RTX3090 运行；18:13 CST 原生产日志均已确认153600 samples/4800 updates，独立60000–150000窗口 p99 分别11.076789627075199与25.356171264648438（150016冻结）。原科学配置、成员、随机状态和训练预算不变。后续原统计4538568/4538569及逐seed比较4538570仅按afterok依赖运行；原5个未启动held作业4538551–4538555已核实0秒取消。尚无seed1胜负，不提前采纳转移。

R1原缓存层诊断由CPU13作业4538572补齐缺失层4/5，C0/81秒，原层3/6复用；总成本11135秒<14400。4层原F64/1000分子bootstrap已闭合，主终点仍为层6，不按诊断层择优。旧裁剪4538532最终原生FAILED0:15，实际旧PID已核实退出；原完整TRAIN裁剪由4538573在CPU13沿同一原配置/游标续接，18:16 CST已从1020928推进到1049600/1194228。原准备作业4538549实际自有进程也已退出；这两项旧阻塞已解除。

新作业使用Slurm复制的自包含resident退出监督入口，真实EndTime前预留收尾，TERM/join/reap自有子进程，不用TIMEOUT正常收尾，无KILL、无故障节点重试、无管理员操作。Data联合NFS峰值38853537501字节包含seed1额外2GiB；保留实际目标盘字节/inode/配额与跨窗口余量检查。未改其他工作线/在跑训练。完整D目标仍active；后续宽库、K1、冷启动9M、A/B/C、交付与PR尚待原任务书关卡。


## 2026-11-22 19:46 CST · D Root：完整TRAIN截断报告

原完整TRAIN目标±6报告已闭合：CPU13/4538573原生COMPLETED0:0/6260秒/1CPU，2026-11-22 19:43:28 CST结束。原atomic_cursor1194228/1194228；原report.json statusCOMPLETE，完整转录results/d_recipe/native_TRAIN_clipping_20261122.json。报告含原24启用字段两配方valid/clipped/fraction；SASA原子valid63001422、clipped62681、原fraction0.000994914051305064。原native_D20完整配置、cohort、choices、RNG、系数和同一输出保留，原D4/存储值未改，没有重拟合、重复闭合统计或独立数组QA。

在原CPU13 StateMIXED核查后，一次有界只读SSH实际确认监督器3582785/start_ticks2758861604及worker3582788/start_ticks2758861610均ABSENT。没有新信号/KILL，不由batch终态替代进程退出证明。旧4538532及准备4538549此前已核实退出，不再是主线阻塞；14/16/17既有管理边界不变。

19:44 CST两个fresh3M seed1原日志均620800样本/19400更新，GPU4/4538566与GPU5/4538567继续运行，原clip冻结值未变；CPU4538568/4538569及配对4538570仍按afterok依赖。尚无seed1胜负，不提前采纳或冻结。全目标active，剩余宽库/G1/K1/条件种子、规定诊断、冷9M、最终A/B/C/基准接口/成本/两个未合并PR保持；ExpansionRx H政策待明确。联合NFS38853537501B及所有实际字节/inode/配额/同行future与退出保护不放宽，无新模型或其他线文件改动。


## 2026-11-23 03:18 CST · D Root：批准H生产已实际推进

用户已明确批准ExpansionRx沿既有B6固定全部原坐标、仅补氢坐标、不生成新构象。定义见Root docs/d_recipe/H_POLICY_20261123.md；Data源及配置已发布9af334f，Root源/22项通过测试已发布bfa47cb。测试4539054实际CPU11/1CPU/8秒、22tests/0.280秒、0:0，原目标盘/NFS/fresh5秒UID守卫与OWNED_TREE_REAPED/remaining_children=[]已核实，不替代科学生产。

原生产4539057在CPU11实际RUNNING，03:13:14开始、TimeLimit8h/截止11:13:14，03:15:48原cursor已闭合256/5278成员。实际原监督器4169297/start_ticks2249574973与原worker4169300/start_ticks2249574979，UIDs全1278、精确job4539057/step_batch已核。原完整QM9 component保留；新唯一合并4539061为同一原merge/config、afterok4539057，完整15751成员清单尚未闭合，C1/A/B/C未完成。旧未启动合并4539058因复制的stdout/devnull缺少终态日志，在owner/PENDING0秒核查后仅一次取消，CANCELLED by1278/0:0/0秒；科学合并没有双跑。

原共同开发D3/合并512MiB和全局NFS38853537501B不增。生产/devnull不写Root日志；测试已闭合并作为实存保留，3个拟CPU统计/比较日志+1个新合并终态日志仍共用原每节点Root128MiB future，无第五个同时增长日志；根/tmp系统底线、同行future、inode和fresh5秒UID保护保持。新入口在Slurm复制的内存resident中先驻留，再读共享代码，真实TimeLimit前900秒收尾、TERM/join/reap，无KILL/管理员操作。原坐标/D20/D4/成员/划分未改；明确化学失败保留逐成员缺失和原错误码，坐标约束及未知错误仍拒绝继续。

两个seed1训练4538566/4538567原03:15:48日志均2707200样本/84600更新，原clip未变，原CPU8568/8569及比较8570afterok保持。目标active，后续全部TASKBOOK关卡、条件臂/种子、冷9M、最终A/B/C/基准、成本、一次完整默认回归和两个PR范围保持。

[配方线 用户指示 2026-11-23 03:30 CST] 新增 docs/p_recipe/USER_DIRECTIVE_20261122C.md：组成信息诊断中"原子 H 的 CEV/CVF/CVF_res"作废；原子级只报 EEV，mean(H) 按现有定义；H-comp 与 H-B4 只用 mean(H) CEV 判定。


## 2026-11-23 04:00 CST · D Root：完整开发D3已交付

用户批准的B6固定原坐标补H已按原程序完成：CPU11/4539057原ExpansionRx5278成员COMPLETED0:0/1568秒/1CPU，03:39:22 CST结束；原merge4539061 COMPLETED0:0/3秒/1CPU，03:39:25 CST结束，复用原QM9后完整15751成员、原顺序/划分/原数组引用，statusRAW_COMPLETE且complete_source_population=true。原component仍正确声明仅ExpansionRx/complete_source_population=false。原两个JSON转录到Data results/data_d_descriptors/development_D3_ExpansionRx_B6_20261123.json及development_D3_full_20261123.json；完整实际清单/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/merged/manifest.json。

CPU11实际StateMIXED，一次有界只读核实原supervisor4169297/start_ticks2249574973及worker4169300/start_ticks2249574979均ABSENT，无新信号/KILL。合并原resident日志明确Rootworker4171120已reap0、RESIDENT_TERMINAL0/remaining_children=[]，不以batch状态替代实际退出。原坐标/D20/D4/成员和source标签保持，原六分子D3及逐原子映射按原mask保留；原子SASA不进入分子特征。原共同峰值203909476B<512MiB，NFS38853537501B、Root128MiB联合future及所有物理实存保留。原22项测试C0/8秒及旧未启动合并9058取消0秒记录保留，没有重复科学生产/数值数组QA/新拟合。

源同步的一次性head容量检查原先把D已落盘产物及已消耗followup仍全额计入未来；现在复用既有h_peer_storage.concurrent/h_resources.allocated及原模型future算法，只从各自预算中扣其已提交物理块，原Data.guard以实际目标/UID准入通过。未改任何运行中守卫、已登记预算/同行future、100GB底线或5秒TTL。此校正只涉及源/报告元数据，当前训练未停或修改。

两个seed1 GPU4538566/4538567原03:48:59日志均2867200样本/89600更新，原clip未变；原CPU8568/8569和比较8570afterok保持。输入H依赖已闭合，但最终A/B/C和C1仍未执行；原接收pending/C1false保留。目标active，所有后续原TASKBOOK关卡/条件臂和种子/诊断/冻结/冷9M/基准/成本/一次完整默认回归/两个未合并PR保持。


## 2026-11-23 04:20 CST · D Root：两个seed1原3M训练闭合

D-R0/4538566 GPU4、D-R1/4538567 GPU5原训练汇总均3000000样本/93750更新，fresh init/B32；1M/2M/3M原完整状态断点均已发布，仅读元信息、无张量复核。GPU当前仍执行原规定读出，CPU4538568/4538569及配对4538570依赖原链，未提前采用迁移/冻结。原训练秒数/clip/峰值及断点路径转录见 d-recipe/results/d_recipe/stage1_seed1_training_20261123.json。已有完整15751开发D3、宽库191/1314接收、原D4及全部同行任务保持。可选A1计数复用优化两次小测试失败后UR停用，宽库继续原通用拟合入口；无第三次修复。不停止/迁移在跑任务，不扩大科学臂。


## 2026-11-23 04:40 CST · D Root：阶段1确认与阶段2容量

原seed0/seed1各自配对WIN，ΔR3分别0.09770468747584315（CI0.08195311354654226–0.11189074805862387）和0.1244890629833722（CI0.10891211543183203–0.13955854300080836），后续采用A1+B3+B4整包；新seed1五作业全部C0且实际resident children=[]，没有第三种子/合并CI。报告d-recipe/docs/d_recipe/STAGE1_TRANSFER_RESULTS.md。

阶段2仅原L1/L2/G1，复用同seed R1控制。原通用完整TRAIN A1拟合将用CPU11本地L1 4GiB/L2 16GiB；本节点共同Root future38788923392B（新20GiB+既有16GiB+128MiB共同日志），系统max10GiB10%另留。实际CPU11 Root可用69943164928B/inode36569937；新预算head fresh5秒UID准入通过，生产入口仍重查实际节点。普通新增模型NFS池3GiB（12槽×250MB及221225472B读出/日志/缓冲），D联合NFS42074762973B，登记于Data full_20261120/plan.json；原同行future/100GB底线/5秒TTL不变，保留全部旧输出，无数据库副本。当前参考生产尚未启动。

现查0–7具备5CPU的节点4/5/6/7均有CUDA上下文，0/1/3 CPU不足；20两卡约26/49GiB、22为14428/32607MiB均超过30%，G1待合规卡。1800秒复查，不碰现有上下文，不绕过drain，21禁用。最终配置未冻结，原后续条件臂/seed0诊断/冷9M/最终A-B-C/交付/成本/回归/两PR继续；其他线在跑任务不变。


## 2026-11-23 04:55 CST · D Root：宽库原A1生产已开始

阶段1两种子各WIN、已采用A1+B3+B4整包；最终配置仍未冻结。CPU11现运行原通用完整TRAIN A1：L1/4539166原闭合2048/1194228行（197分子标量），L2/4539169闭合512/1194228行（1320标量）；各1CPU，48h，真实EndTime11-25 04:50:12/04:52:37 CST、预留900秒收尾。最初两入口在任何数组创建前退出，原子树已reap/children=[]；现入口只先经原guard准入后建独立自有根，两个原收集器均已有正游标，无算法/字段/D4更改。

已登记联合NFS42074762973B及CPU11 Root共同future38788923392B、系统max10GiB/10%另留、同行future/100GB/fresh5秒保护不变；原log/旧产物保留，不复制原数据库。04:55实际Root余量69906649088B/inode36569906。G1就绪待合规GPU，下一次完整资源复查21:06 UTC；不碰当前CUDA上下文、不停止/迁移在跑任务。进度与原生身份见d-recipe/configs/d_recipe/CURRENT_BEST.json和docs/d_recipe/daily/2026-11-23.md。完整后续任务继续，无新用户审批项。


## 2026-11-23 06:55 CST · D Root：G1原3M已启动

新空卡compute-0-7已按原≤3M优先组规则接入D-G1：原Slurm4539204、RTX3090 UUID GPU-9db54192-dd3f-3177-e56f-dcd161ff932c、5CPU/3workers、fresh seed0/B32各3M；原日志已4736样本、75.868646658957训练秒，完整TRAIN1194228。沿已确认A1+B3+B4及D20，仅关闭全部D3损失，二维块不放大，不改其他线/在跑作业。原CPU统计4539205(afterok4539204)及同seed R1比较4539206(afterok4539205)已提交CPU11/各1CPU、8h/4h，当前PENDING Dependency；不重训控制、不提前作胜负/冻结。

本卡原实际StateIDLE、48可分配CPU、零CUDA上下文、显存5/24576MiB；Root/tmp同盘可用45430296576B/inode36529024，MemAvailable388872864kB。resident实际准入Root45429927936B/inode36529018、真实TimeLimit48h/EndTime11-25 06:53:49 CST，提前900秒完整状态安全收尾，TERM/join/reap自有子树，不靠TIMEOUT/KILL。GPU7共同Root未来17314086912B（原8GiB自己+8GiB同行+128MiB日志），D联合NFS42074762973B与CPU11未来38788923392B均不增；fresh5秒UID、100GB及系统max10GiB/10%保护保留。

CPU11原L1/4539166、L2/4539169仍RUNNING；06:40 CST原游标84992/1194228和57344/1194228。仅原采集粗估24日06:20/17:50 CST，之后拟合另计，预算/阈值不改。宽库逐字段R²与截断计数直接用原fit.fields，不新增数组扫描；SASA旧报告复用。完整任务仍active：后续全部条件种子/K1/规定seed0诊断、冻结、冷9M、最终A/B/C及基准、成本、一次完整默认回归/仓库检查、Root与数据两个未合并PR保持。其他会话是否读到/部署不作声称。


## 2026-11-23 · D Root：G1原3M闭合与终点诊断

原D-G1 seed0/3M、主统计及同seed R1配对4539204/4539205/4539206均C0，实际resident children=[]、原root PID均ABSENT。原R3=0.41941109959286943，Δ=0.016946340654004077、95%CI[0.0038709507854383872,0.029767100949210194]、τ=0.020970554979643473，TIE、无seed1。CI未跨0，依任务书删项条件保留D3；最终配方未冻结，不增加臂/重采样。原训练/1M2M3M元信息/VAL与判定见d-recipe/docs/d_recipe/STAGE2_G1_RESULTS.md。

规定的G1固定5000VAL/F64/层3–6终点诊断已绑定原执行器与source-independent resident，尚未提交：几何GPU6/RTX3090 UUID GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef/2CPU→CPU13各1CPU；层读出原GPU7/UUID GPU-9db54192-dd3f-3177-e56f-dcd161ff932c/5CPU→CPU13。GPU6实际Root57462898688B/inode36540116，GPU7 Root42347425792B/inode36529045，CPU13 Root69513863168B/inode36542451；两GPU均IDLE/零CUDA上下文/5MiB，CPU13 MIXED/64freeCPU，/tmp实际findmnt均同root xfs。新GPU6未来8GiB私有+8GiB同行+128MiB日志=17314086912B；GPU7相同既有预算不增、仅消费闭合开发层缓存；CPU13未来12GiB私有+16GiB同行+8GiB余量+128MiB日志=38788923392B，系统max10GiB/10%另留。原固定队列5,131,075,584B几何值及4,349,591,552B rsync临时均在私有12GiB内，不复制数据库/原开发层缓存，不新增前向QA。

联合NFS42074762973B与原CPU11未来38788923392B保持。新node声明在d-recipe/configs/d_recipe/diagnostics/G1_node_storage_20261123.json；入口和运行中沿原fresh5秒UID/同行future/100GB/实际字节inode保护，几何及层诊断各累计4h、两失败UR，真实TimeLimit前预留300/900秒TERM/join/reap，不靠TIMEOUT/KILL，不碰他人或R1已UR几何。原L1/4539166、L2/4539169各1CPU仍CPU11 RUNNING；完整条件臂/冷9M/A-B-C/基准/成本/一次回归和两个PR目标保持。共享此容量声明，不声称其它会话已读/部署。


## 2026-11-23 · D Root：G1终点诊断实际启动与原成本闭合

原D-G1主3M、主统计及配对已全部C0并实际reap/children=[]；配对TIE且CI不跨0，按删项规则保留D3，无seed1。原R3/判定及一次成本见[Root报告](https://github.com/mint258/MFM/blob/d-recipe/docs/d_recipe/STAGE2_G1_RESULTS.md)。G1 RTX3090原一次成本4539289/CPU13 C0/8秒×1CPU，原root1757127已reap/ABSENT：80.61110553165612样本/秒、整卡点采样均功耗228.29927302100162W/1238条、GPU父分配10.472777777777777卡时；训练活跃采样窗不含最终读出、父分配墙时含读出，不是积分能耗。原周快照和旧遥测未重做。

已按已发布7fab219的五份原执行器配置/复制resident提交终点描述诊断：GPU6/4539284几何前向(2CPU、真实1h/EndTime18:45:16CST、提前300秒)，原cursor在17:46已608；GPU7/4539285缓存层3–5读出(5CPU、45m/EndTime18:30:26、提前300秒)，两者09:56UTC仍RUNNING。CPU13传输4539286(afterok4539284、30m/300秒)→几何统计4539287(afterok4539286、2h30m/900秒)；CPU13层统计4539288(afterok4539285、3h15m/900秒)，各1CPU，当前PENDING Dependency。主层6已闭合直接复用，不重复编码器前向；首个预检OWNED_TREE_REAPED不代表完整新诊断退出。

实际新入口已通过目标Root/健康/UUID和fresh联合准入：GPU6 Root57462800384B/inode36540110、GPU7 Root42347175936B/inode36529039。此前声明的GPU6/7各17314086912B、CPU13 Root38788923392B、CPU11原38788923392B、D联合NFS42074762973B保持；真实系统max10GiB/10%、同行future/UID100GB/fresh5秒及所有旧实存保留。几何和层诊断各分配时限合计4h，两失败UR，不绕drain、不KILL、不改其它线运行。所有配置及登记见[Root诊断口径](https://github.com/mint258/MFM/blob/d-recipe/docs/d_recipe/G1_DIAGNOSTIC_EXECUTION.md)。

L1/4539166与L2/4539169原CPU11各1CPU仍RUNNING，17:48原闭合670976/1194228及411904/1194228；完整原A1、条件臂/种子、冷9M、最终A-B-C/基准/全部成本/一次回归及两个未合并PR目标继续，最终配方未冻结。共享实际节点占用和容量，不声称其它会话已读/部署。


## 2026-11-23 · D Root：G1缓存层闭合与同游标续接准备

D-G1原缓存层3–6诊断已COMPLETE：GPU7/4539285 C0/1174秒×5CPU、CPU13/4539288 C0/78秒×1CPU；两个resident均实际reap/children=[]，原root在实际节点/proc均ABSENT。原F64/1000分子bootstrap/seed20261025，层6直接复用、主层固定6，不选诊断高层。源结果见d-recipe/results/d_recipe/G1_layers_3M_20261123.json及docs/d_recipe/STAGE2_G1_RESULTS.md；G1主判TIE/CI不跨0→D3保留、无seed1保持。

GPU7本线两个writer4539204/4539285已全部关闭，释放本线原8GiB未来写入为0；原约3GiB开发层cache仍为实存保留、不删除、不对quota重复抵扣。原同行8GiB和共同128MiB日志仍保留，GPU7剩余共同future8724152320B；该更新不冒称其它会话已读/更改预算。GPU6几何17314086912B、CPU13/CPU11各38788923392B、D联合NFS42074762973B和系统max10GiB/10%、inode、fresh5秒UID100GB保护保持。

原GPU6/4539284几何仍RUNNING，18:15原cursor26272/同一固定5000VAL队列；CPU13原传输4539286→统计4539287仍PENDING依赖。直接引用既有固定周父记录：同队列R0前向3388秒、传输29秒、统计4446秒；未重测旧遥测/数组/统计。当前前向1h/300秒收尾实际3300秒工作窗偏短，已发布仅在原安全终结、子树实证退出且cursor未完时的原cursor续接准备，尚未提交，不改/停当前任务。条件分支时限为初始1h+续15m(180秒收尾)+传输30m(300秒)+统计2h15m(900秒)=4h，原科学配置/同scope/已关闭前缀/随机状态不变。若原FORWARD_COMPLETE/C0，沿现有依赖，不使用备用；只有真实未成功且owner/PENDING0核实后才一次退役未开始的旧依赖。见configs/d_recipe/diagnostics/G1_conditional_cursor_20261123.json，最多两失败，不把75/TIMEOUT当完成。

L1/4539166、L2/4539169仍原CPU11各1CPU，18:19原闭合700928/1194228及428544/1194228；完整TASKBOOK后续条件臂/冷9M/最终A-B-C/基准/成本/一次完整回归和两个PR继续，最终配方未冻结。其它线/在跑任务不改。


## 2026-11-23 · D Root：G1原前向闭合与CPU13统计接续

已依1206f731预先发布的同cursor方案完成原前向收尾：4539284在预留窗口返回75:0/3288秒×2CPU，原cursor47456，resident已reap/children=[]且原root2117304/2117307/2117339全部ABSENT，不是科学完成、未到Slurm TIMEOUT。GPU6健康IDLE/零CUDA上下文、Root52357775360B/inode36540107且实际/tmp同xfs root核实后，原4539290 C0/50秒×2CPU从47456续到47698并发布同一5000VAL/F64/layers3–6的FORWARD_COMPLETE。原4539291 CPU13闭合cache转运C0/32秒×1CPU；两者各自原resident也reap0/children=[]、原root均ABSENT。没有重算已关闭前缀/复制原数据库/新科学条件。

旧4539286/4539287在zixiao/PENDING/0秒核查后仅一次取消，实际CANCELLED by1278/0秒，无科学执行。新CPU13/4539292是相同原diagnostic_statistics，1CPU/2h15、真实EndTime21:01:01CST、提前900秒，实际resident Root64381878272B/inode36542435准入，当前RUNNING。原前向manifest statistics_complete=false仍正确保留；最终几何统计未完成。整项初始1h+续15m+转运30m+统计2h15m=4h、两失败规则保持，原P函数/F64/1000分子bootstrap/seed20261025不变，源见d-recipe/results/d_recipe/G1_forward_and_transfer_20261123.json与诊断执行口径。

GPU6本线所有writer已关闭，现与GPU7一样仅释放本线8GiB未来写入，原几何/开发层cache均为实存保留、不删除或重复抵扣；同行各8GiB+联合日志各128MiB仍保留，各节点剩余future8724152320B。CPU13/CPU11原共同future各38788923392B、D联合NFS42074762973B、系统max10GiB/10%、inode/fresh5秒UID100GB保护保持；CPU13统计尚在运行，自己的几何/统计预留不释放。所有自有进程UID/PID/cgroup收尾由原复制resident管理，无KILL/管理员操作。共享实际容量事件，不声称其它会话已读/部署。

G1主实验TIE、CI不跨0→保留D3、无seed1保持；缓存层诊断已COMPLETE。原L1/4539166及L2/4539169仍CPU11各1CPU，完整TASKBOOK的宽库/条件臂/冷9M/最终A-B-C/基准/成本/一次回归与两个未合并PR继续，最终配方未冻结，不动其它线/在跑训练。


## 2026-11-23 · P：真实 Lustre UID 硬配额与后续输出改盘

19:15 CST 实测 Main UID1278：`lfs quota -u 1278 /lfshome` 的 hard=2TiB，仅余1067335680B（约0.994GiB）；整卷约39.7TB不能代替UID额度。NFS `/share` 沿既有五秒新鲜发布源，hard=4TiB、当时余量338684014592B。P已停止新增Lustre写入，原3M训练/九个GPU R3及全部旧输出、失败成本保留；组成前向SIGBUS的根因未确证，保存游标24576/47698，拟从该点改到已核实NFS续接。P的必选真实UID配额与实际autofs目录修正已通过CPU4539306的19项检查，既有科学配置不改。详见[实际额度、已计入的并发预留与处理边界](LUSTRE_UID_QUOTA_20261123.md)。各窗口由自身owner核验后续/安全续接与自身实际写入；不据此停止他人训练、删旧输出或改管理员配额，不声称其他窗口已读或部署。


## 2026-11-23 · P：I1原3M及配对闭合、原22C组成与注册full12接续

I1原4539186已完整3M/93750更新；原GPU9项R3/4539296、CPU9项R1和原配对统计4539310、只消费既有1000draws的判定4539325均C0。R3候选0.4692604924343602、原F2自身预算3M基线0.474057641022044，Δ−0.004797148587683819，CI[−0.015324382193372076,0.0062871009040671565]：TIE跨0，原删项规则建议DROP B4，不触发seed1。是否采纳待用户；冻结A1+B3+B4+F2保持，未增加9M/容量研究。主结果见p-recipe/docs/p_recipe/I1_RESULTS_20261123.md。

Lustre实余0.994GiB后，原九个R3预测与原manifest转至/share，H0原缓存只读复用；CPU原R1没有重编码。组成原游标24576通过4539309稀疏校验转运，原4539324在node5续至47698、C0/40秒，原F2基线4539200前向只复用。mean统计4539327、22C补充4539331、导出4539332全部C0，A2从8增至12行：I1−F2 meanCEV+0.01867111575450242，原配对CI[0.01629128117645299,0.02084145132357948]；原子只EEV，H-comp/H-B4原判定不改。原SIGBUS根因未确证、失败及所有旧实存保留；单任务描述输出声明按原峰值428867584B修至512MiB，并未增加整体32GiB NFS预留或改科学代码。

注册full12已按原四任务/三微调种子提交普通sbatch4539312–4539323，node6与7各一条afterok顺序队列、同卡同时一项，16CPU/64GiB，不exclusive；CPU原汇总4539329等全部完成。GPU实际UUID分别GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef、GPU-9db54192-dd3f-3177-e56f-dcd161ff932c，启动前均IDLE/48freeCPU、零CUDA/5MiB；Root实际余量52.33GB/42.35GB，系统和已发布同行future保留。新入口真实35分钟TimeLimit内提前900秒、原完整断点续接和TERM/join/reap；不靠TIMEOUT/强杀收尾。所有后续I1新输出/share固定32GiB未来预留，原Lustre清单未来为0，既有物理输出不删/不重复释放。CPU11三种原统计峰值合计不超过本线24GiB RAM声明，真实UID/fresh5秒及同行预留沿9aedfe处理。

原半小时Slurm/claim观察器PID354632/start8413032111仍在；第126轮全部本地控制查询returncode0、实际reap，未重启，不自动提交或操作其它线进程。全部26项仍active；D第5节A4继续等待外部闭合交付，PR7保持draft，最终REPORT/权重SHA未生成。共享实际占用和容量，不声称其它窗口已读或部署。


## 2026-11-23 · D Root：G1全部规定诊断已闭合

原CPU13/4539292 F64统计COMPLETED0:0/4027秒×1CPU，固定5000VAL/47698构象/层3–6/1000配对分子bootstrap seed20261025，原summary COMPLETE。实际resident原root1757811/1757777均reap0、/proc ABSENT、children=[]，早于900秒收尾窗口，无TIMEOUT/KILL。末层原CEV=0.4075617657426487、CVF=0.00489512801748446、CVF_res=0.008215964289908527；原均值/95%CI与PR见d-recipe/results/d_recipe/G1_geometry_native_summary_20261123.json，执行闭合及原阶段成本见G1_geometry_3M_20261123.json。未重算/重复bootstrap或独立QA；原eigenvalues/抽样数组留在实际原文件。

原3288秒75失败前缀、50秒同cursor续接、32秒转运及4027秒统计累计7397秒，4h声明与两失败规则保持。缓存层3–6早已COMPLETE，现G1全部规定诊断闭合；原主TIE、CI不跨0、保留D3/无seed1不变，R1 F64 UR两失败不重试。前向manifest statistics_complete=false仍为其前向producer原事实，独立统计summary声明最终COMPLETE。

CPU11 L1/4539166、L2/4539169各1CPU仍原完整TRAIN A1，不停止/迁移；NFS42074762973B、CPU11/13原共同future38788923392B暂保守保留，GPU6/7实存cache不删除、同行future不动。CPU13本线writer已闭合，但本次不下调其原future，后续实际新任务仍核对健康、目标盘/inode/UID/同行与系统底线。最终配方未冻结，宽库/条件臂/冷9M/最终A-B-C/基准/成本/一次完整回归/两个未合并PR继续；无新增科学审批项。不声称其它窗口已读/部署。


## 2026-11-23 · P：I1全部原科学后续闭合，等待外部A4

I1原自身3M训练、原9R3/9R1、判定、两源22C组成及注册full12全部闭合。原fullCPU统计4539329 C0/10秒、导出4539337 C0/5秒，F表由108增至116行，原108行原字节保留。只复用原冻结读出，不重新拟合/重采样；F三种子分数点均值与均预测CI分开。实际原报告完成门仅缺D第5节A4直接描述符/组成交付，P不自行重拟合或用D G1诊断替代。I1 R3为TIE且CI跨0，原规则建议DROP B4；是否采纳待用户，冻结A1+B3+B4+F2保持，无seed1/新9M/容量研究。

末尾原4539322/4539323先核zixiao/PENDING0/无分配，再仅取消这两个未开始槽，借已空出的GPU5改为4539335/4539336（465/462秒）。同12个任务、同代码/输出/超参，原CPU329依赖对应更新；没有停止在跑训练。node6/7各五项、node5两项均实际OWNED_TREE_REAPED0/children=[]且原root ABSENT。最后一项正常运行中完整state曾286308867B并持续更新，不重载权重/不算最终SHA。全部原输出和尝试成本保留。

原I1/RTX3090/B32最终67.4555472642样本/秒，整卡原梯形积分时间加权均功耗307.1383300768W（1471次、44426.366秒观察窗，含原训练内VAL/断点，不含后续读出/FT）。原3M单位VAL和完整family-loss直接交付。原native成本生产者4539338 C0/6秒：全P物理GPU时间仍为历史下界710.6584790494h，无活动GPU句柄；I1训练/读出与失败尝试12.4658333333h，full12 1.1902777778h。原历史两段缺失终止时钟下界不伪造，CPU分配秒不冒充实耗；见p-recipe/docs/p_recipe/I1_RESULTS_20261123.md、COST.md与原结果JSON/CSV。

本线所有科学GPU writer已关闭；GPU5/6/7本线未来RAM/tmp均0，未使用I1 NFS未来32GiB也释放为0，旧实际checkpoint/cache/结果全部保留并继续计入真实UID quota。仅保留CPU11未来8GiB RAM/64MiB日志及既有约265.8MB控制/最终交付预算，原守卫/fresh5秒/同行/系统底线继续，不触碰其它线或当前其它用户上下文。这里只释放本线未使用未来，不声称当前全局卡空闲或其它窗口已读/部署。

第127轮原半小时观察四项控制查询均returncode0且实际reap；PID354632/start8413032111仍在、interval1800、下次12:58UTC，仅Slurm/ownclaim，无自动科学提交或停止。全部26要求继续；外部A4未到，最终REPORT/权重SHA未生成，PR7保持draft。


## 2026-11-24 · D Root：L1原A1闭合后的三百万已在GPU5启动

CPU11原L1 A1/4539166 COMPLETED0:0、79720秒×1CPU，完整1194228 TRAIN/197字段原FROZEN_FIT、unresolved=[]、original_D4_modified=false。原参数reference/L1/label_parameters.json与逐字段R²/有效数/±6截断原报告均已闭合；actual resident root4176565 reap0、/proc ABSENT、children=[]。不重拟合旧D4、不重试已UR可选适配器，不读取旧raw数组做独立QA。

实际GPU5 SlurmIDLE/48空CPU、UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377 RTX3090，24576MiB仅5MiB、零CUDA计算上下文，UID1278、Root57211424768B/total75125227520/inode36540394，/tmp同xfs root。登记D L1自身8GiB+保守同行8GiB+128MiB日志=17314086912B，系统max10GiB/10%另留；已有cache全保留。新L1 fresh seed0/3M/A1+B3+B4/B32/5CPU/3workers入口复制原source-independent resident，48h提前900秒，D3/原子SASA块与原绝对权重/旧D4/±6/新p99窗口不变。源5ded3205已先发布，原GPU5/4539360现RUNNING（5CPU/3workers），原日志1194228 TRAIN/B32/micro32/PM7；真实End26日03:10:57CST、900秒收尾。CPU11统计4539361 afterok4539360→比较4539362 afterok4539361，均PENDING/Dependency、0秒科学执行，未为等待GPU预占CPU；实际入口继续核验健康/UUID/owner和root/NFS/fresh5秒UID/同行future后才执行，不把准入当运行结果。

原CPU主统计/同seed R1配对各1CPU绑定健康CPU11，8h/4h/900秒，依赖新GPU/新统计，原R1控制复用。CPU11/13原future38788923392B仍保守保留，D联合NFS42074762973B不增（已含本seed0模型池）；L2/4539169仍原CPU11全TRAIN，不停或迁移。当前S已公告两9M在20/22、P尾部无活动5声明，实际5无上下文；不动其他owner或视PENDING未来任务为活动预留。G1全部规定结果闭合/TIE保留D3无seed1；最终配方仍未冻结，剩余全TASKBOOK范围不缩减。源见d-recipe/results/d_recipe/L1_A1_closure_and_GPU_admission_20261124.json与L1_original_A1_fit_20261124.json。不声称其它窗口已读或部署。


## 2026-11-24 · D Root：L2 A1两次原生失败后按任务书未解决

原CPU11 L2 A1/4539169实际FAILED1:0/81858秒×1CPU，原peer quota守卫在checkpoint发布前拒绝：available313207726080B、required313356249146B（冻结future/底线口径），差148523066B。不是物理ENOSPC/OOM/节点drain或Slurm超时证据，不更改配额算法、同行future或100GB底线。原closed cursor729600/1194228、参数未发布；actual resident root4176838已reap1，remaining_children=[]，实际/proc ABSENT。原rootFS仍57269452800B/inode36569833。失败记录与原traceback见d-recipe/results/d_recipe/L2_A1_unresolved_20261124.json。

连同首次4539164 FAILED1:0/46秒/0收集行，同一L2 A1项已有两次实际失败。依TASKBOOK3.5/failure_policy记UNRESOLVED，对应D-L2及条件seed1不跑，无第三次诊断/修复；不以部分TRAIN替代、不改A1/旧D4/字段统计/目标或阈值。未运行不构成R3 TIE/LOSS或更大库无效结论。原阶段0 L2字段/唯一统计/64头接收及已闭合开发/基准二维源保持，所有局部数组/旧输出保留。

原L1 GPU5/4539360继续（03:44原71488样本/1412.4644965790212循环秒），CPU11统计4539361→比较4539362仍原afterok/PENDING0科学工作，未停止/迁移或修改活跃训练/guard源码。G1原TIE、D3保留/无seed1和全规定诊断闭合不变。虽两A1 writer均已退出，本次仍保守保留CPU11/13各38788923392B Root future、D联合NFS42074762973B及GPU5自身/同行/日志17314086912B；原实存cache不删，实际新任务继续节点/UUID/字节/inode/fresh5秒UID/同行与系统max10GiB10%准入。最终配方未冻结，剩余L1条件种子/K1/冻结后冷9M/最终七任务A-B-C/基准接口/成本报告/一次默认回归与两个未合并PR全范围继续。不声称其它窗口已读/部署。


## 2026-11-24 · D Root：退役L2未用三个模型槽，原L1配额守卫自动恢复

L2 A1两次实际失败后已依TASKBOOK3.5未解决，D-L2从未启动且不再补跑。仅退役本线为它预留的1M/2M/3M三个从未写入checkpoint槽：3×250000000=750000000B。Data full_20261120/plan.json的Stage2模型池3221225472→2471225472B、checkpoint_slots12→9、model_checkpoint_bytes3000000000→2250000000；221225472B日志/读出/序列化缓冲和三个额外备用槽全部保留，所有已有实际checkpoint/partial数组/cache不删除。各阶段0库的字段、统计、成员、验收及科学参数不改。

同一本线full峰值35118709120→34368709120B、D live联合NFS峰值42074762973→41324762973B。活跃L1配置保留原42074762973B更保守声明；没有修改运行源码、模型、3M样本预算/随机状态/原D4或其它owner任何预留，100GB/fresh5秒、原quota额外缓冲和根盘max10GiB10%全部不变。只撤回已经确定不会再有writer的本线future，不把物理占用当释放空间。

原L1 Guardian确曾DISK_TRANSPORT_PAUSED：PID1491773，available313209810944B/required313356249146B、样本71488。它在自行读取新live计划并完整通过原准入后自动记录DISK_TRANSPORT_RESUMED，同PID1491773；后续原losses.csv已75456样本/2624.544632997364循环秒，未发人工信号、未重启/重新初始化或加载checkpoint，也未重试L2。原暂停与分配时长全留成本，不伪造正常TIMEOUT。源见d-recipe/results/d_recipe/unused_L2_slots_retired_and_L1_native_resume_20261124.json；真实L1 GPU4539360/原CPU依赖4539361→4539362继续，CPU11/13原root future仍保守保留。最终配方未冻结，所有后续既定关卡/冷9M/最终A-B-C/基准/成本/一次完整回归及两个未合并PR全范围保持。不声称其它窗口已读/部署。

[配方线 用户指示 2026-11-24 04:10 CST] 新增 docs/p_recipe/USER_DIRECTIVE_20261123.md：E1 构象数 k* —— 全量分子、k∈{1,2,5,10}、冻结配方 3M seed0（k=10 复用 round4 F2），frozen R3 与全量微调都不判 LOSS 的最小 k 为本线 k*。S 线同步执行同一设计。


## 2026-11-24 · D Root：1M原断点与阶段1已闭合空槽退役，原L1守卫恢复

L1原GPU5/4539360在1M正常保存samples_1000000.pt（205549589B，00:48:53 UTC），原固定2000 VAL/198字段已生成。随后在1007360样本因原quota守卫暂停，同PID1491773；available312291291136B/required312397987623B，不把它写作磁盘满或节点故障。只撤回本线已闭合Stage1 seed1注册中的两个从未使用额外模型槽：2×232000000=464000000B。GPU4538566/67、CPU4538568/69及配对4538570早已正常闭合且原实际自有树reap/children=[]；两条各1M/2M/3M的六个现存断点（无partial）全保留，不重复训练共享控制。

Data live plan的stage1池2147483648→1683483648B、槽8→6；134217728B读出/日志和157265920B其余原缓冲均不变，Stage2九槽/2471225472B及221225472B缓冲不变。全D full峰值34368709120→33904709120B、联合NFS live峰值41324762973→40860762973B。活跃L1配置保留原42074762973B保守声明，原guard源码/额外8GiB/100GB/fresh5秒/系统底线及其它owner任何future均不改，所有已存文件不删除。若未来L1 seed0胜出才另登记该臂seed1资源，不借已闭合Stage1控制池启动新臂。

同一原守卫自行读取新计划、通过原准入后已DISK_TRANSPORT_RESUMED，仍PID1491773；无人工信号、无重启/重新初始化/加载checkpoint。暂停和分配时长保留成本。原1M报告与预算证据见d-recipe/results/d_recipe/D-L1_seed0_original_1M_milestone_20261124.json及closed_stage1_unused_slots_and_L1_resume_20261124.json。L2 A1仍按两次失败UNRESOLVED、不重试。完整任务继续、配方尚未冻结；不声称其它窗口已读/部署。
