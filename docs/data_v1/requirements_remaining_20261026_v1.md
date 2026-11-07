# 全指南剩余证据矩阵（2026-10-26）

目的：逐项核验根目录《数据线工作流程：v1 定稿与数据扩充（Codex B）.md》的完整终点，不能把排队、源码或合成fixture视为真实数据交付。此次仅只读指南、Root STATUS、小型收据与源码文档；未运行Python、SSH、Git、Slurm或读取科学数据正文。下面科学数字均引用既有producer/收据，不是本次重新计算。

观测基准：Root源码5d761fd36a32db7aa214d683bf3ec5b4e3a5fc10；`docs/interfaces/STATUS.md`、`control/active_checkpoint_v13.json`、`control/queued_actual_20261026_v1.json`。后者03:28快照为4520959等待Resources，4520960/961/962等待Dependency；22项新检查尚无实际PASS，观察进程2054694已核身份。排队需持续跟进，但不等于四步已执行，更不等于全部指南完成。

路径约定：`R`为本run根`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`；下表仓库路径相对`R/repository`，`control/`与`artifacts/`相对R。等级分别是“源码/协议已存在”“fixture实际通过”“真实小试点/局部完成”“最终人口完成”。它们不可相互替代。旧README中compute20、尚未下载/尚未试点等文字是历史快照；当前CPU资源与实际完成度以新决策、intent和实际收据为准。

## 第一部分及D-1到D-7

|指南/交付|已具备的最高证据及权威|仍缺的下一份实际证据|
|---|---|---|
|1.1 / D-1 契约|`docs/interfaces/training_format_v3.md`覆盖七项，状态draft.3。wire合成8项、16worker/32记录实际读回见`control/sb1_wire_candidate_tests_v2.log`；采样桥接6项实际PASS见`docs/data_v1/model_adapter_sampling_actual_v1.md`、job4520608。|模型线正式审阅写入共同契约、双方v3.0签署及版本/哈希；真实provider解码和加载验收。不能代填模型签署。tensor参考系、tensor消费、原因sidecar边界见下文。|
|1.2 S′与共同人群|`docs/data_v1/sprime_fill_and_common_population.md`及`conformers/formal_v1/`、`formal_v2/`有生产规划/执行/最终化源码和已有fixture。原336试点4520364 TIMEOUT；`artifacts/conformers/partial_pilot_audit_v1/audit_v1/audit_report.json`确认334完整包、2缺包，完整包中SUCCESS仅102。恢复4520960已排队。|恢复2原task/seed+14独立控制的实际结果、334旧包不变及新联合闭合/试点预算；再冻结完整缺口批次、执行一次账本、全量补齐、失败清单、共同人群/geometry/order三权威及哈希。最终TRAIN+VAL总排除/逐元素排除、元素/大小/骨架分布变化由脚本生成。|
|1.3 / D-7 构象统计与顺序|`docs/data_v1/conformer_statistics.md`、`conformer_statistics_pilot_actual_v1.md`记录256完整分子的canonical HOF/几何小试点；固定映射proper Kabsch 0.5Å与随机/能量/多样性源码存在。|在最终共同人群分别重算PM7/UFF唯一构象数、≥2/5/10、重复/收敛比例、大小/可旋键/环数相关、PM7 HOF范围、跨来源RMSD分布；冻结各来源三套置换。原始N选择策略继续查`legacy/`、`workflows/dataset_rebuild/`及服务器历史，列出处/SHA，仍找不到则明确“未找到”。|
|1.4 / D-2 注册表|`configs/data_v1/label_registry_v3.json`和`docs/data_v1/label_registry_v3.md`为实际生成的元数据草案；146统计分量不是146预测头。size试点4520541完成129物理目标/146分量。|最终TRAIN元素参考残差上的逐字段rho/pairN、abs(rho)≥0.95 size归类；sigma/pi等非标量旋转一致聚合、各单位/原生精度/物理范围、池化、vector/tensor实际参考系证据；Pprime同字段独立上下文，最终注册表冻结与manifest。43P+26分子D及原子SASA与指南42P+27分子D的口径差异必须逐项解释，不能改标签凑数。|
|1.5 全人口异常与mask|`docs/data_v1/validity_masks.md`、`labels/streaming_v1/`及CPU变体实现canonical owner、范围/一致性/median/MAD。最终小试点闭合`control/label_cpu_closed_4520564_v3.json`为512分子/4251记录/146分量，新增mask均0；七EA只读诊断实际完成，根因UNKNOWN。|全人口逐字段SUCCESS但converged NULL/异常计数，包括约390条EA口径重建；TRAIN稳健阈值、z>20复核、物理与跨字段/同分子跨构象一致性。逐记录/逐字段mask+reason/codebook、每字段数量/原因分布、每类最严重20例（不是最先20例）；>1%逐字段单独报告。NULL不自动等于SCF失败；只mask标签不删记录。Pprime和扩充D另跑同一检查。|
|1.6 / D-4 归一化|`labels/normalization_v1/`及`docs/data_v1/normalization.md`已有最终输入门和算法；`control/final_normalization_fixture_actual_closure_v1.json`确认24项fixture/16worker实际通过，不是D4。4251记录median/MAD也不是最终D4。|最终共同人群+ROUTINE角色+geometry+diagnostic排除+全量mask绑定后，仅有效TRAIN拟合能量元素参考；精确0.1/99.9百分位缩尾统计mean/std、系数/残差、逐元素原子统计；Pprime独立统计。保留原标签，固定版本/排序，从parquet独立重建并验证统计哈希/逐位复现。|
|1.7 / D-5 清单|`export/pipeline_v1/materialize.py`及`materialize_v2.py`已有磁盘表、诊断anti-join、独立来源training_orders；wire/subset与source-pair有合成边界证据。采样桥接实际6项PASS。|消费真正冻结的common/roles/order/geometry，生成12万⊂24万⊂60万⊂全部TRAIN、固定seed、分布对比；从12万取5万TRAIN，另取5000VAL；2万TRAIN分子两来源均≥2，分别留固定随机末构象并排除所有训练条件及派生view。真实parquet清单/索引/哈希、抽样守恒/无泄漏验证和独立报告。bridge PASS不能替代这批产物。|
|1.8 / D-3 试点导出|`export/wire_v1/`、`pipeline_v1/export_source_v2.py`、`source_v2.py`与granular store已有候选编码/真实源选择/稀疏pair适配；合成LMDB往返、损坏拒绝、多worker关闭、4项source-pair增量测试存在实际日志。|实际5万TRAIN+5000VAL按最终契约输出分家族float32 LMDB（PM7、UFF、mask、清单分开）；记录/分子/构象计数守恒，随机1万记录逐字段与永久float64 parquet对照仅允许一次float32转换，完整文件SHA/大小；模型provider真实加载确认。|
|1.8 / D-6 全量及分发|只有候选导出/验证实现，没有全量交付或节点本地实测。|必须先获D3真实加载确认，再全量导出与同等校验；逐GPU节点现场核`/tmp`容量、分发文件SHA、证明真实本地文件系统/只读句柄；在GPU节点本地磁盘以多worker实测随机读取分子/秒和总大小。CPU数据读取测试无需占用GPU，不能用provider的node_local布尔声明代替现场证据。|
|1.9 Pprime|`docs/data_v1/pprime_labels.md`、`pprime/retention_v1/`与`formal_common_v1/`已有输入、稳定raw、once、执行/闭合实现及受控fixture。1000分子/2000UFF已准备；72输入准备4520552完成；frame实际QM4520961、retention准备4520962排队。|先取得72实际QM/parsed/16worker+原frame evaluator PASS、稳定raw retention manifest；再实际2000构象×12任务试点、全任务成功率≥99.5%、实际父分配核秒/2000≤11.7，失败分类/float64读回。合格后全共同人群每分子2真实UFF几何、12原任务、相同扰动协议；完整WP5同级审计、raw保留证据、1.5异常扫描、P/Pprime分布相关、独立TRAIN归一化与最终家族parquet。N=1必须单独闭合。|

## 恢复、N=1、模型接口和真实导出的关键依赖

- S′恢复成功也不能直接进入旧formal planner。`conformers/recovery_v1/close_recovered.py`输出`RECOVERED_SPRIME336_PILOT_CLOSURE_V1`，并保持`pilot_accepted_for_planning=false`；`formal_v1/full_common.py`仍要求旧`PILOT_COMPLETED_REQUIRES_ROOT_REVIEW`及原pilot父C0。Root需在真实恢复闭合后新增显式兼容adapter/validator及边界证据，绑定336联合包、全部原TIMEOUT/新恢复成本与独立控制；不能改旧状态或伪造一个C0回执去骗旧validator。

- `configs/data_v1/conformers/n1_pprime2_proposal_v1.json`及同名源码README中的5040是**原PM7 N=1来源母群**，不是已冻结共同人群5040。必须与最终common、TRAIN/VAL和严格可用baseline交集重算；remaining FULL、UFF_UNSUPPORTED/common=false不冒充最终覆盖。
- N=1只有planner、choose_second/expanded_orders和6项纯fixture；`production_science_runner_present=false`。Root还需登记并验证独立生产adapter：保留原N=1和原baseline计数/坐标，以原N的10N=10个真实候选、原ETKDG/UFF/graph/stereo/atom-order/0.5Å规则取得第二个实际优化事件，保存seed/candidate/source/geometry SHA；不足唯一性时只允许真实maxmin并标below，不复制或删分子。无候选则明确PPRIME2_UNRESOLVED，不能把“2”放宽成“1”。先实测小试点，再生成实际最终范围。
- N1新物理命名域、opaque geometry_id、supplementary view、稳定三顺序和Pprime engine非负int64整数桥接必须独立绑定/测试，不能将字符串或NULL塞入原sprime_conf_idx、用native trace顶替物理身份。`pprime/formal_common_v1/README_v1.md`明确baseline runner不接受N1扩展；ALL_COMMON验收必须等全部common都有两个真实接受parent，不能只完成BASELINE_READY_COMMON_SUBSET就结束。
- 数据侧tensor六分量与稀疏leaf原因已实现，不能继续称这两项“尚无数据实现”。模型`current/phychem_mfm/phase1/v3_contract.py`的representation仍只有scalar/vector/magnitude；需要模型线正式决定tensor消费和等变验证，不静默拆成六个不变标量。`v3_sampling.py`仅单套conformers/minimum ID，桥接按来源分别投影，最低能取诊断排除后energy training_rank=0。真实provider必须返回相同geometry_id/源原子顺序/对应坐标和标签，并保真暴露reason sidecar/codebook；不改模型树代替模型线签署。

## 第二部分：全部2.1到2.9

|指南/交付|现有最高证据|剩余下一证据|
|---|---|---|
|2.1 v1分布/覆盖|`nearest_exact.py`、ranking/external_sort源码与合成oracle存在；`docs/expansion/exact_nearest_and_sort_v1.md`明确真实近邻成本试点未完成。|最终common结构投影+指纹/身份/骨架计数真实SHA；元素/重原子/分子量/环及芳香环/环系/通用Murcko频率/官能团/立体中心/logP/TPSA/HBD/HBA/可旋键统计。相同规则PubChem随机100万基准、每query到全v1的精确ECFP4 Tanimoto最近邻及覆盖不足类别；先测成本，再完成并输出`docs/expansion/v1_distribution.md`和作图脚本。|
|2.2 获取PubChem|真实完成：4520348官方CID–SMILES下载，完整SHA/CRC/EOF已闭合，见`docs/expansion/pubchem_raw_actual_v1.md`及`artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json`。|该项原始获取已闭合；后续均绑定同一版本/完整SHA并保留CID及来源行，若换版本则新独立获取/回归，不用旧HEAD替代新文件hash。|
|2.3 回归与全源筛选|4520414全原始X回放15879477记录、一致率100%、未解释0；共同人群范围仍待最终绑定。原前10000输入已跑；593因320环系漂移FAILED，597兼容候选实际C0：8198旧成功全部保留、753恢复、1049排除不变。见`x_full_regression_v3.md`及`paired_prefix_compat_actual_v1.md`。|将真实最终common/原选入定义绑定回归≥99.9%且逐差异解释；将已测试兼容feature fallback登记到新全源执行入口，完整PubChem流式筛选/逐规则漏斗/所有CID别名守恒、完整终态/输入SHA。10k候选评估既未改旧pool，也不等于全量screen或pool放行。|
|2.4 去重/全源去污染|`decontamination.py`、`data_authority_v1.py`及`configs/data_v1/decontamination_sources.json`有严格全来源门；4520547只完成76物理locator current pins，未导出完整identity。|PubChem完整InChIKey内部去重；v1全部TRAIN/VAL/FULL+4900隔离记录，不仅common。全部下游全划分identity export+独立coverage证明：ExpansionRx、全部SoM、QM9、已用QM7、22 TDC端点、完整已选MoleculeNet、MARCEL Kraken/Drugs-75K、COCONUT OOD（active/inactive范围须证明）。逐来源版本/物理path/bytes/SHA/角色/子集、unresolved保守规则和实际排除计数；来源manifest从PENDING到真实READY，之后生成实际filtered pool。|
|2.5 排序与首批|`external_sort.py`、`ranking.py`、`nearest_exact.py`有合成精确/外部排序实现；尚无完整来源filtered pool或真实全池排序。|基于完整去污染池与v1-only精确指纹结果固定两个互斥队列；R/N各500万，累计10000000，首批各1250000共2500000。R均匀固定seed；N按重原子区间×元素组合分层，score仅v1/PubChem骨架/环系频数/最近邻距离。全池身份count/SHA守恒、R/N无交集、前缀嵌套；下游仅排除不参与选样评分。|
|2.6 扩充UFF|已有S′内核和选择规则可复用；**无完成的无PM7适配器或10000分子UFF试点**。前10000行筛选不是该试点。|无PM7图输入adapter与原配方参数/原子/立体/去重等价实测；实际1万分子试点，每构象耗时、成功率/失败/below标记、三套顺序、成本预测；合格后仅首批250万分子，每分子最多10个真实UFF，缺额依1.2补足并标记，正式14–19/64GiB。不对后续1000万全部生成。|
|2.7 D标签|v1 D20/D3定义及现有家族导出可参照；未见扩充真实D数据/审计。|同v1代码：图D20去Kappa；每UFF几何PMI1–3/PBF/体积/SASA及逐原子SASA。绑定实际atom order和geometry SHA，float64家族parquet逐字段读回；完整1.5异常扫描及mask/reason，不运行PM7/xTB/Pprime。|
|2.8 存储|仅候选SQLite/诊断产物，不是永久首批交付。|与v1相同家族parquet，`dataset_version=v2_candidate`、stream、CID/版本、manifest/SHA、记录/构象/失败清单；实际峰值与永久占用、含临时/失败/收尾空间的quota预算及向1000万分子线性外推。|
|2.9 首批报告|`docs/expansion/batch1_report.md`尚不存在。|由实际数据/脚本生成六项：筛选漏斗、去污染、R/N各自对v1和PubChem分布、加入后最近邻覆盖变化、UFF成功率/失败、实际全部父核时及存储；每项有输入hash/规则/异常/限制。第一批完成后单独PR。|

## 完成前必须统一核验的产物与不变量

|项目|最终必须取得的证据|
|---|---|
|已命名仓库产物|最终`docs/interfaces/training_format_v3.md`、`configs/data_v1/label_registry_v3.json`、`docs/data_v1/label_registry_v3.md`、`sprime_fill_and_common_population.md`、`conformer_statistics.md`、`validity_masks.md`、`pprime_labels.md`均需真实最终状态；1.6/1.7/1.8各自报告和哈希清单。`docs/data_v1/DATASET_V1_CARD.md`目前不存在，须包括来源/筛选/人群/角色/标签/mask/归一化/限制。`docs/expansion/v1_distribution.md`和`batch1_report.md`也尚不存在。|
|外部真实产物|共同人群、geometry map、三种orders、全量/Pprime家族parquet、mask/codebook、D4统计、D5清单、D3/D6 LMDB、节点本地交付、完整filtered PubChem池、R/N千万队列及首批UFF/D均需真实manifest、counts、hash和source/seed/recipe/code lineage，不填未来SHA。|
|角色与人群|ROUTINE VAL分子级权威为7610分子/72525 PM7记录；原11322仅record membership，不代替全部VAL几何。最终common只TRAIN/VAL且PM7完整+足够严格SUCCESS&&converged S′；原source_role保留，FULL/embargo仍进入去污染但不进入TRAIN拟合。某些旧identity说明仍写VAL11322/FULL旧计数，最终报告必须采用4520334角色权威。|
|科学停止门|UFF_UNSUPPORTED排除，不换力场；仅Se允许元素排除>20%例外，总排除>2%/其他元素>20%不变。新增mask>1%、Pprime<99.5%或>11.7分配核秒/构象、任一批实际核时>试点估计1.5倍均需报告并停止后续相关派发。任何恢复不能抹去原TIMEOUT/失败成本。|
|资源/存储/网络|CPU任务选实际cpu分区；正式UFF/QM只14–19/至少16CPU/64GiB/全部用户申报内存85%，未把memory0当零占用。每作业≤48h，普通/排队路径启动前均 fresh strict proof、account quota剩余≥200GB，失败/临时/收尾同预算；不强杀在跑任务、不改他人或模型GPU，不用付费学校服务器；只走原软件版本/keywords。不删除已有文件；新raw按失败+1%审计+复现包保留规则验证后清理。|
|全范围与最终PR|所有报告含目的、输入hash、规则参数、脚本生成数字、异常和限制；负面方案保留。每项提交前check_repository。第一部分全部完成开一个PR，首批扩充完成再开一个，交由用户合并。用户当前goal要求等队列并持续至全指南完成，不能把初始四任务终态或源码发布当结束。|

本矩阵只是一份completion-readiness审计，不改变任何冻结源码、契约、科学阈值、数据或Root目标。Root应在每行取得对应实际producer/验收收据后逐项消除缺口；没有真实结果的行继续保留待完成。
