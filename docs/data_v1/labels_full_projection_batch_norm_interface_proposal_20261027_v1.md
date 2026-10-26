# 全源lossless投影：批次、存储和最终norm接口提案

状态SOURCEFINAL_PROPOSAL_NOT_IMPLEMENTED，不是full放行、空间保证或新科学权威。2026-10-27，只读冻结源码和小metadata；不读Parquet/SQLite/LMDB/packet正文，不执行Python/AST/科学/SSH/Git/Slurm。已冻结的projection6件、HoFaugmentation6件均未修改；TDC交SB4，不在本提案实施。

## 1. 已证实量与空间门槛

实际512缓存：4521610 C0，293s allocation/16CPU；manifest为artifacts/labels/source_status_v1/lossless_projection512_v1/manifest.json，22033 B，status=PILOT_CACHE_CLOSED_FULL_NOT_AUTHORIZED。16组均CACHE_REOPEN_VERIFIED_NOT_FINAL_LABELS，原6+新3fixture实际PASS，146字段新mask/新structural invalid为0、quality_stop_fields=[]。manifest算法elapsed248.540s，unique_output_bytes=494,609,729 B。它包括cache与metadata，不能当作仅F64 pool大小。Root另闭合物理/task/base/open-close计数；本方案不抢先将这些计数升级为full。

按记录数算：494,609,729/4251≈116,351.383 B/record；乘原11,231,854记录≈1,306,841,746,203 B（1.307 decimal TB）。这是同样布局的小样本线性量级，不是forecast或上限。源分布、原子/稀疏pair数、重尾大小、无效/缺失状态、JSON/tree/索引开销、part压缩边界都可能改变比值。原512选样不是全人口按bytes均匀抽样。

同样机械放大293s allocation会达约215小时wall／3440 allocated corehours，说明不能借全status397s或HoF三个标量叶的成本冒数值codec成本；该数也不是可靠forecast。需按真实family/row/leaf重尾和后续codec实测校准。Root接受512实测与REPORT_AND_CONTINUE不免除开跑前成本/范围/输出cap审查，也不允许单job超过指南48h。

Root提供当前Main free约1.948TB；182×8GiB S′未完cap为1,563,368,095,744 B，另200,000,000,000 B保留，则示例margin≈184,631,904,256 B。该算式用近似free，**不替代启动前fresh quota/provider和所有并发任务登记**。1.307TB缓存现在不能与这些未完cap重叠预留；1.3TB也不是经过分层实测的硬上界。

原永久label producer引用2024件/563,531,830,997 B；base184件/12,388,979,667 B另列，合计575,920,810,664 B。它们均是producer记录体积，不是新实际read bytes。full原文解码至少面对这些文件；如另验wholeSHA，应分别计hash和解码I/O，不把inherited producer SHA冒称本轮wholeSHA。不能用未读的“715GB主要都是LMDB、labels很小”假设作存储决策。

建议先保持full cache等待S′终态释放未使用的预留，再用真实余量冻结full方案。若Root先推进前批，第一批只给一个明确whole cap（例如32GiB，含所有part/partial/footer/metadata/observer/scratch）；并发批次cap之和、其他在途cap、仍保留的既有cache、转运临时副本、spill以及200GB必须同时满足fresh空间约束。示例32GiB不是默认许可，也不是每worker32GiB。不能把16worker各自未协调的cap相加后超过whole cap；未关闭/未删除的物理副本仍占空间，不因逻辑ticket释放而变成free。

## 2. 最小实现接点：文件物理范围，而非反复按record筛选owner

复用不变：原payload.evaluate、264声明→146启用映射、原common解码/分量、全部source/new/review与mask规则；projection v1的typed tree/F64原bit、original ordered atom/basis/compound键、list ordinal、source provenance和reopen语义。资源仍16CPU/no_mem、当前centralv2、真实RSS/MemAvailable软STOP自然drain、fresh quota200GB；不重引入hard64/声明85%/exclusive。只新增range driver、bounded sink/cursor及coverage归并，暂不新增大pipeline。

先在真正CPU上生成一次footer目录，不读科学values：每个源ref对应actual row-group数、每组physical rows、选列compressed/uncompressed bytes、schema/identity以及必要的file offset元数据。原status audit已保存schema/dtype和每file物理/当前owner数，**没有actual row-group目录**。当前冻结writer默认row_group_size=32768（wp5_parquet_v2.py:142、182），不能替代实际footer，也不能据默认值给出原文件最大RG字节承诺。

新最小接口（候选名，均未实现）：

1. prepare_ranges(census_ref, source_catalog_ref, canonical_index_ref, footer_inventory_ref, quota_ticket, accepted512_profile_ref) → immutable range_plan。
2. project_ranges(plan_ref, range_claims, cursor_ref, fresh_startup_proof, output_ticket) → 一批已关闭part refs、scope counters、完成cursor或明确partial STOP。
3. close_coverage(range_plan_ref, batch_receipt_refs) → 物理range平铺与canonical/base coverage；只有全部闭合才有FULL_SOURCE_NUMERIC_CACHE_CLOSED。
4. observations_from_cache(cache_dataset_ref, fit_side_ref, current_mask_ref, logical_statistics_order_ref) → 现D2/D4统计内核的同形输入，不自行改数学。

每个range用(source_file bytes/SHA, family, owner_job, source_file_group, row_group, physical_row_lo,physical_row_hi)描述；metadata保存原file ref，不重编号record。range ledger以这些物理区间证明互斥及无缝覆盖，同一源file在同一allocation尽量一个worker保持一个句柄，按row-group顺序推进并轮转输出part。**不为每批record_id子集重新扫所有184group/整个owner表。**

canonical.sqlite的record_ordinal是SHA-bound formal_record_index的zero-based physical file_row_number，既不是label Parquet物理行，也不保证某owner/molecule连续。它用于跨表join和coverage，不可直接当label物理row-range。仍以readonly SQLite对当前batch ID批次lookup，不能把整个owner索引复制到16份Python dict/set。范围内每行按五owner键及lane/natom判canonical；非canonical计数另列。

完整数值pass需要array_f64/text等共享CELL叶；不能像HoF-only三个scalar叶那样廉价剪列。按registry_id筛CELL发生在读取共享nested column之后，并不会令Parquet自动跳过不引用的registry数组。任何更早的Arrow过滤只能减少Python展开，且必须保留原CELL ordinal和payload.evaluate对全部原CELL的raw/shape/duplicate审计语义，需另有实际parity证明；本提案不默认它已能减少575.9GB输入。

如果空间允许，优先在RG边界关闭批次。若cap/wall在RG中到界，必须先关闭当前writer、fsync/readback、写next_cursor=(file,RG,next physical row)，再停止新派发。下批只重开该RG，Arrow slice跳过已闭合prefix；已完成RG绝不再遍历。此API最多仍需解码一个边界RG的已读prefix，**不是零复读**。额外I/O上界需要actual该RG选列bytes/reader行为证明，footer读取另计；不同文件不能用一个未经测量的常数上界。不得以不可执行的“解压字节offset”当Parquet seek游标。

输出part可以小于RG；part记录其覆盖的连续物理ranges和canonical row keys，闭合part后再推进cursor。崩溃遗留.part文件不计coverage；已关闭part不能自动重复发布。恢复需Root/新request明确绑定已闭合receipt+cursor，原部分结果保留，不暗中重试或跳过难例。只读分析range账本与生成once ledger分开，不能改N1/S′ attempt键。

## 3. 真正的whole cap与unknown行处理

建议sink从whole ticket领取有限part tokens，而不是16worker各自无限轮转。part上限、Arrow buffer、单行serialized上限、footer/admin余量和spill均写入同一budget；写前要在跨进程锁内核whole已用+预留，输出未关闭也计入。至少留出当前单行/收尾与observer空间后才接收下一行。quota/内存/wall STOP只停止新的source batch/part，已接收行自然完成；不靠强杀保cap。

现v1单行64MiB、worker3GiB是软件界限，不是已证full最大值。full若遇超界，保留source locator/失败证据并将该range留pending；不裁pair、不删记录、不把budget STOP编码成SCF或numeric mask。若单行需要新有限envelope，必须由真实case证据及Root资源审查决定，不能默默放大/跳过。

不能机械克隆pilot的全部资格断言：512所有base可用，但full可能出现本来就缺失/失败的base或标签。保留一条base状态与全部14task记录/原source mask，缺Z/坐标写明确unknown，不能造0、不能因不是ORIGINAL_PM7_GEOMETRY便删除原record或把全扫描异常停掉；对真正损坏/违反source声明的情况另报告。后续按元素统计只对有证Z/order者可定义，缺者仍留人口/缺失质量账本。

现canonical.sqlite只有9列：ordinal、record/molecule、attempt/job/task、lane、natom、new_role；**没有formal record_payload_sha256或heavy_atoms**。base可读Z/positions/order/source_payload SHA并计算heavy count；若要求独立与formal payload逐record对照，需显式一次只投影该小列的辅助侧表，不能伪称现9列已核，也无需读取LMDB。

同一molecule可能跨物理ranges/parts；原人口全部source roles都扫描，不按TRAIN/common先删值。SourceMol是否“完整可统计”在coverage归并后决定，不能每个part就独立算mol-median并平均。withinmol的min/max/符号/有效数/extreme ordinal可外存归并；D2每分子中位数必须以所有有效构象做精确外存选择。主record一票与敏感性mol一票仍各自报告。

## 4. Coverage、mask与guide1.5的不同完成状态

物理label范围必须与157,254,650物理taskrows守恒；canonical为11,231,854×14=157,245,956，8694 shadowed/duplicate保留单列及原source，不悄删。base还应按其独立producer物理/当前row计数闭合，不把base当第15个QM task。canonical每(record_ordinal,task_code)及base(record_ordinal)恰好一份；用磁盘索引/bitsets拒绝重复，保留role/field/leaf质量计数，不能只比较全局总数。

每批状态应是BATCH_CACHE_CLOSED_FULL_COVERAGE_PENDING，报告已覆盖file/RG/physical rows/canonical task keys、剩余范围及实际cache bytes；即使每批C0也不等full。只有全部range账本、canonical14slot、base、所有role和字段声明闭合，才能发布full source cache/数值质量汇总。源body/原值不删除。

每field同时报告已观察数、source invalid、新mask、新structural invalid、review和未知原因；partial率与原population分母下的累计下界分开。不能用global分母稀释批次异常、也不能把一批的比例称为full比例。已证全量下界>1%立即HOLD；批次异常交Root复核，最终按原full阈值判定。0/合法signed-zero、旧缺失/N/A/常量不当作新增异常；z>20仅复核。r73有序atom/basis/值/全部list ordinal保留，方向/basis冲突仍UNKNOWN，不symmetrize/dedup；N/A empty coverage review不变成missing atom。

全source numeric cache闭合仍不等guide1.5全部完成：

- 初遍只能用真实matched full-TRAIN calibration，或者明确PENDING；不能把512 median/MAD套到full。完整sourceTRAIN精确median/MAD后，再在全角色cache做z>20/zero-MAD复核；此标尺仍provisional。
- 原物理范围/crossfield规则完全复用，不能因存储分批改阈值或自动升级NULL SCF为失败。
- 原程序打印precision、真实坐标frame/origin、独立dipole magnitude或缺raw原因仍需独立有界证据。存储bit精确与程序物理语义闭合是两件事。
- 最终candidate mask冻结、>1%报告及D2 family签核独立于cache“能重开”；完整cache不自动授予这些状态。

## 5. 当前空间不足时的最小执行选择

优先方案：S′闭合前只做footer目录/小范围range调度与reopen测量，或不超过fresh margin的首批；保留其partial coverage状态。S′实际终态及输出size闭合后释放“未使用的预留”，再按真实free、真实批次bytes分布和全源分层权重评估full cache。仍保留物理输出本身占用，不把整个182×8GiB全当能回收。

可选低存储路径：独立完整数值审计沿原payload full接口只落compact masks/coverage/extrema/worst，不保正常逐leaf值，先完成全人口shape/status/crossfield盘点。它不产生可任意Common重选的值缓存；后续full median/MAD/D2/D4可能需要再读原源，必须明确额外I/O。Root如果希望一次解码复用，应先给cache足够生命周期空间，而不是宣称mask-only输出能重建未来精确统计。

可选无源重扫的空间试验：将已完成494.6MB typedcache在CPU重打包一个新codec候选，把重复source schema/ref/field定义改为字典ref，保留全部科学tree/精度/键/顺序/值。不能drop实际被QC/复现引用的metadata。先用现有cache而非575.9GB原源检验semantic/bit签名完全一致和真实bytes；未测前不承诺能从1.3TB降到185GB。此项也需要新Root request/source pins，本方案不实现。

若使用Alpha承接批次，必须另核Alpha实际free/reserve与storage scope、Main→Alpha传输额外副本/wholeSHA成本以及独立UID/proof；small readonly scope不自动容纳TB数据。已关闭part实际SHA和安装回执前不声称传输完成。Main副本尚存时仍计Main空间，不因为有远端copy就提前释放其ticket。无自动原数据删除或跨端点source身份伪装。

## 6. Common后TRAIN norm：cache reader新接点，数学保持冻结

现normalization_v1读取旧source/mask manifest和文件名，不能只把cache路径塞进旧manifest骗过。需要一个明确新adapter：按cache的component_map/ordered_leaf_paths和typed tree还原146字段值/atom indices/原pair keys，从原compact整行恢复source/current masks与reasons；检查重开typed signature、registry/codebook/field IDs、源范围和mask版本。继续原common.component_values parity，物理vector/tensor的分组统计照旧，不决定模型各向异性head/norm。

fit资格用独立磁盘侧表join：FROZEN common molecule membership、effective TRAIN角色、frozen geometry_map/order和真实20k PM7＋20k S′ heldout几何/其perturbed target排除。PM7按native record、UFF按(molecule,int64 sprime_conf_idx)映射opaque ID，不从record前缀猜，不误排所有共享parent的UFF。VAL/FULL/embargo/diagnostic不入fit；cache原source_role不回写成新role。当前尚未冻结这些authority，代码必须继续拒绝最终D4。

cache reader需batch/disk join，不照搬旧reader整owner.to_pylist/16份dict。Z/order从base cache引用取，缺失记录给明确不可定义原因。P′另有真实UFF值/cache/mask/元素参考/统计，不能借P替代；缺真实源继续pending。

后续passes：registry指定能量族的TRAIN元素参考与残差；精确type7 q.001/q.999；只在统计副本缩尾的mean/std；逐元素atom统计；物理vector/tensor audit；所有phase的population/field/leaf质量与source/mask hash守恒。原D4最多10遍再独立replay可转为读cache，免原JSON/Parquet反复解码，但并未免统计pass本身。最后同一frozen common TRAIN上重算D2全146组件/129物理target的rho与5HoF context匹配参考，原sourceTRAIN结果不冒最终。

**逐bit缓存相等不自动保证不同分片的norm JSON逐bit相同。** TSQR/moments浮点归并不满足数学实数的结合律。必须冻结logical_statistics_partition与value order和merge tree，使其不依赖物理cache part边界、worker完成顺序或Main/Alpha传输顺序；读取顺序至少绑定source/task/ordinal/原leaf ordinal的明确规则。原run.execute_phase按jobs顺序收集、merge_models沿rows合并，不能换分片后默认相同。

重建还需冻结NumPy/BLAS/LAPACK、线程数、代码与运行环境，并实际做独立replay/hash验证。跨Main/Alpha数值线性代数bit等价未在此证明；Arrow重开值相同不能替代该验证，不为通过而加新容差。原标签与typedcache始终不因winsor/残差改变。

## 7. Root可审的下一输入/输出契约

详见同名_interfaces.json（PROPOSAL，不是READY request）：输入只继承真实census/catalog/source refs、canonical index/role pins、实际512 closure/accounting及未来actual CPU footer目录；没有future file SHA。范围manifest、输出ticket、原子part+cursor receipt、partial/full coverage分开。先冻结此接口与Root可用quota，再决定实现range driver；不继续堆叠与真实full扫描无关的小fixture/通用helper。
