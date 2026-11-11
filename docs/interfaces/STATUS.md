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

详见[实际进度v6](../data_v1/secondary_main_actual_progress_20261027_v6.md)。N1准备4521417 C0验证4631原baseline，真实UFF试点4521418 C0得到32/32真实第二几何，308优化完成，2个合法below0.5Å补齐；旧once账本保留。Alpha标签扫描1884788和原核汇总1884791均C0，6测试与227/65正文SHA实际通过；不是最终mask或D4。COCONUT全物理身份归一化1884790仍运行；P足已请用户作科学决定，答复前不改M或预注册。当前M2仍等待正式D4，三条S保持6M预算。

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

原三组P seed0均已6M；0的开发因同卡外部进程未启动，替代4529708在node6等a验证9706后运行，完整C1准备4529710随后读取六组原结果。数学上必在前二的C1-a提前运行S/P seed1：4529691/node5/3090与4529704/node22/5090，已有真实优化更新，原科学配方/有效B32/6M保持。node6推进原FULL与TRAIN未见构象独立诊断（a9706→dev0 9708→b9709），不用于选择。新节点实际磁盘字节/inode/native quota已核实，根盘保留max(10GiB,10%)，全部窗口共用原峰值预测，无数据复制/旧文件删除；用户要求根巡桏dd护持续。


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
