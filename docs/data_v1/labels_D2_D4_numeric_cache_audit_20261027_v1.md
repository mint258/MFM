# D2／全值审计／D4执行路径审计与数值缓存提案

状态：SOURCE_ONLY_AUDIT_FINAL；缓存设计待Root审阅，尚无缓存实现、实测输出量或全量数值结果。日期：2026-10-27。

本轮只读指南、Root源码、producer引用、已完成任务的小manifest/report/accounting。未读取Parquet／SQLite／LMDB／科学JSONL正文，未执行Python、AST、测试、SSH、Git或Slurm，未改任何已登记源码。原始数据保持只读。对应Root当前物理源码的bytes/SHA和入口行号见同目录的 labels_D2_D4_numeric_cache_audit_20261027_v1_source_pins.json；这些是本轮小源码观测，不是新科学运行证据。

## 1. 当前可以承认的实际完成范围

| 项目 | 实际范围与结果 | 不能由此推出 |
| --- | --- | --- |
| 注册表v3 | 264个声明分量；146 enabled；103 N/A分量对应63原字段；10常量删除分量；5 legacy ESP分量另列。分子标量真实为43P＋26D，另1个D原子SASA | 不是146个独立模型head；D2仍未最终冻结 |
| 全源状态审计 | Main 4521201 C0，16分片归并；1,220,466分子、11,231,854记录、157,245,956 canonical taskrows；2024源文件、171 source jobs、184 file groups；物理taskrows157,254,650，8694 shadowed/duplicate单列保留 | status覆盖不等于实际数组长度／JSON数值布局／最终mask／D4完成 |
| 原512 TRAIN统计与mask链 | 4251记录；TRAIN4211、VAL20、FULL20；精确median/MAD链与mask归并已闭合，146字段新mask0 | 原source TRAIN不是最终common TRAIN；旧69标量rho不能替代新129物理target结果 |
| 新size语义pass | Main 4520541 C0，47.310秒算法elapsed，2遍源、每遍16实际worker；146组件映射129物理target；10,712,554 B输出（manifest前） | scope_provisional明确未应用diagnostic、common未冻结；registry_final=false、normalization_completed=false |
| 实际payload512 | Alpha 1884788 C0／57秒／16CPU，原6fixture先PASS，227输入wholeSHA/fstat全部PASS，16组16实际worker、4251记录；1884791 reducer C0／18秒allocation、算法6.015秒 | Main原1327不是成功科学证据；Alpha Arrow17与Main25差异已留存；不等于全人群数值审计完成 |
| payload512归并 | 209 opens＝209 closes；146字段newly_masked_records之和0，quality_stop_fields=[]；31,552,822 B scan输出 | candidate_masks_frozen=false；native_print_precision_verified=false；actual_frame_origin_verified=false；final_common_D4=false；guide_1_5_completed=false |
| EA极端值诊断 | 4520570 C0，7例／14contexts／16worker，maxRSS385,368,064 B；96 opens＝96 closes、5560复用、max1handle；14contexts原raw未留存／不可得 | 原因仍UNKNOWN；不新增mask，不从NULL推断SCF失败，不重建指南旧约390的口径 |

全状态源：artifacts/labels/source_status_v1/auto_memory_v1/{prepared/manifest.json,reduction/audit.json}。原数值链：artifacts/labels/streaming_v1/reduce_mask_v1_cpu_v3/reduction.json。新size：artifacts/labels/size_rho_v1/dv1_size_rho_cpu_v2/{manifest.json,scope_provisional.json}。Alpha原生metadata的Main逐SHA复本：control/secondary_cluster_20261026_v1/labels788_native789/exact_Alpha_metadata_copies；reducer实际audit/closure复本在同父目录labels_reducer791。EA依据control/ea_closed_compact_v2.json。

## 2. 永久标签体积：不是几十GB

从已冻结prepared manifest的shards[].files[]读取producer记录的bytes，以完整path去重并检查重复引用是否同bytes/SHA：2024唯一引用，重复0，总563,531,830,997 B（563.532 decimal GB；524.830 GiB），等于compressed_source_bytes_upper_bound。没有stat／hash／打开这些正文。按family求和：

| family | files | producer bytes |
| --- | ---: | ---: |
| pm7_neutral | 184 | 375,922,258,533 |
| perturbed | 184 | 58,384,422,831 |
| pm7_solvents | 184 | 35,103,584,001 |
| pm7_ions | 184 | 35,103,382,571 |
| xtb_singlepoint | 184 | 22,392,882,314 |
| xtb_fod | 184 | 10,294,753,268 |
| xtb_alpb | 184 | 8,291,212,077 |
| xtb_vfukui | 184 | 6,513,351,238 |
| D3 | 184 | 5,618,600,593 |
| xtb_vipea | 184 | 5,502,349,100 |
| D20 | 184 | 405,034,471 |

pm7_neutral约占2/3。约715GB旧LMDB不是项目唯一大体积来源。完整永久label直接搬Alpha不可假定便宜。

另从原catalog.artifacts按path去重：184个base_geometry producer引用共12,388,979,667 B，不在上述2024件内。label＋base总575,920,810,664 B。canonical.sqlite另1,733,042,176 B，role ledger另11,231,854 B。上述均为manifest已登记值，未冒称本轮正文验证。512原计划为209个label引用970,140,107 B及19个base引用22,308,690 B；其209文件/分子大小分布不能代表全2024文件，不能用57秒直接外推全量。

14个task slot：D20、D3、pm7_B、pm7_anion、pm7_cation、pm7_octanol、pm7_water、xtb_ALPB_octanol、xtb_ALPB_water、xtb_fod、xtb_perturbed_gradient、xtb_singlepoint、xtb_vfukui、xtb_vipea。family文件含多个task时不得重复当新物理文件计费。canonical owner使用完整(record_id,molecule_id,attempt_id,job_id,task_id)，量子行另核lane和total_atoms；role以真实ROUTINE冻结表及ordinal ledger为准，不能以源字符串自行重切TRAIN。全population TRAIN1,206,608mol/11,104,772records、VAL7610/72,525、FULL6248/54,557，三者均进入源审计；只有未来符合fit侧表者进入最终拟合。

## 3. 最小复用路径与确切缺口

| 既有入口（labels/下） | 可复用内容 | 本轮核到的边界 |
| --- | --- | --- |
| payload_audit_v1/materialize.py:35 initial | 同一closed census、原512计划或171 owner按producer bytes分8个分片；完整owner、14slot守恒、source refs；不重扫status | full已有可物化接口，但尚无真实full数值C0；输出是审计，不是值缓存 |
| payload_audit_v1/run.py:43、61 | 精确family投影、Arrow过滤后转Python、SQLite批次canonical join；每源文件一次open并finally close；Arrow CPU/IO各1、16worker、自然drain | 当前candidate_masks＋coverage＋extrema＋worst20不保存正常逐leaf值；Z未由此入口投影 |
| common.py:89 decode_cell | ABSENT/NULL/empty/bool/JSON/numeric/nonfinite分开；数组prod(shape)==actual length | 把解码后值不加状态直接float化会丢失null／非数值类型信息 |
| common.py:114 component_values；payload.py:53 evaluate | 264声明逐项观察，146启用字段已有source/new/review候选mask、原子索引和crossfield处理；每CELL只解码一次 | pair结果indices全None；raw科学compound键只在瞬时解码值中。现输出不足以重建pair或未来Common子集 |
| size_semantics_v1/size_reader.py:12；aggregate.py:22、47 | source-mask parity，Z，HOF元素参考、旋转不变聚合、record与mol-median两种rho | pair_keys会排序两端，适合已声明候选聚合键，不能当无损缓存原键；rows_for_group整owner.to_pylist不宜机械扩到最大owner16份 |
| normalization_v1/reader.py:56、72 | base_geometry取得atomic_numbers/native_atom_order_sha256/source_payload_sha256；核原子数、heavy count、payload与owner一致，不需要LMDB | base实际positions_A另有F64[NA,3]，可显式加投影；未来缓存reader需要独立适配，不靠修改冻结globals |
| normalization_v1/{authority,sources,run}.py | 真common/角色/opaque geometry/order/diagnostic侧表；TRAIN-only元素参考、精确type7尾分位、仅统计副本缩尾、moment、按元素、物理vector/tensor、replay | 现dataset契约要求旧streaming full/phase=mask的特定manifest/文件名；新payload/cache不能仅换pin冒充此契约，需要显式新adapter及等价验证 |

原payload full命令构造入口已存在（只作接口说明，不在本轮执行）：Root用物理Root路径调用payload_audit_v1/materialize.py initial --mode full --output-directory NEW --artifacts-root NEW，再按scan --shard-id 0..7及reduce生成reviewable请求；其产物必须由Root按当前centralv2/no_mem授权冻结与提交。若现在先跑它，之后想建立逐leaf缓存，仍需再次读源。本提案建议先测小缓存sink，再把全值审计与缓存提取合成一次源遍历，而不是先大改统计数学。

## 4. 两类高频review的源语义核对

### r73：不能当成已证实的源值冲突

原字段P.pm7_B.r73.value，source_path=values.sigma_pi_entries，原存储每项{atom_i,basis_i,atom_j,basis_j,value}。owner来自pm7_B量子行五键、lane/natom与canonical SQLite的匹配，不是从普通atom pair重新拼造。4251原记录里，unordered候选键冲突review4204、same-value重复review4250。

原冻结wp4_parsers.py:84–106的说明是paginated lower triangles，原输出保留两端方向、basis字符串以及列表顺序；局部keys只以(atom_index,basis_label)登记，没有单独打印列ordinal／轨道组ordinal。payload调用size.aggregate.pair_keys:22–34：保留每端(atom,basis)，再对两端排序。因此不是“只剩两个atom ID”；但确实丢掉方向，并继承原parser未保存独立组ordinal的限制。当前小report不能区分：反向条目被折叠、相同basis label对应不同原组、分页解析问题或真正重复值冲突。没有读取case原列表／raw，结论必须UNKNOWN，不能任选解释。

下一次32/512投影应保存原有序全部键、原列表ordinal、每个值及原numeric component；只额外报告有序键重复／仅无序键重复／same-value／conflict分类，绝不dedup、symmetrize、平均、删项或修改mask。若原parser已经丢失区分信息，缓存只能保留其实际表示，不能伪补轨道索引；真正raw对应需独立有限raw证据。

### r199／268／335／402：N/A空数组的覆盖review

这四项分别是anion/cation/octanol/water的values.enpart_one_center_eV，每项3分量，均已声明N/A。actual reducer逐项观察为SOURCE_CELL_EMPTY=4251、numeric_leaves=0，而不是4251个被证实缺失了部分原子值的数组。原wp4_parsers.py:185–191仅在匹配ENPART文本节时追加{atom_index:int(打印原子号)-1,values:[3]}；这是真原子编号域，非AO编号。未匹配时初始化[]。

payload.layout_reviews:14–18对空列表仍执行set(keys)!=set(range(total_atoms))，所以给全部空N/A加覆盖review。这解释了此统计的代码来源；不能据此推翻N/A、发明补值或自动mask整个字段。当前全enabled新structural-invalid与newmask仍0。未来投影必须保留EMPTY/declared_NA及该review上下文，不能把它当全字段1%新增质量失败。

## 5. 建议的32／512无损投影试点（尚未实现）

只新增独立cache-sink及reader adapter，不重写registry、mask、rho、归一化数学。保留原6fixture在fresh中央admission与小source pins之后、任何真实正文前执行。最小新验证只覆盖缓存本身的逐字段/leaf/order/类型往返，以及与冻结现值/compact-mask parity；不要重跑无关的旧19/24/13套以替代真实投影。

人口先从既有512闭合计划取32个完整分子并覆盖16 owner（真实record数由prepare冻结，不凑32条／不切构象），然后Root决定同4251record／512完整分子的实际profile。32子集可能仍读接近原209文件的同一列页，不按record比例估算I/O。两阶段均0新UFF/QM，绝不消费生成once账本。

建议缓存为有明确schema的row-addressable Parquet分区，使用小字典manifest减少反复字符串，不能只写聚合统计。最少保留：

1. record层：稳定record_ordinal、record_id/molecule_id、完整owner五键、lane/natom/heavy count、source/effective角色来源pin（未来effective overlay另版本，不覆盖历史）、原PM7/native或UFF physical key、perturbed view/parent关联。opaque最终geometry ID未冻时保持nullable＋未映射原因，不造前缀。
2. field层：field_id/field_key/registry_id/task/source_path/component、原CELL kind和声明shape、实际layout与length、原source dtype以及F64 cache dtype分别标记。全部264声明保留可观察状态；63 N/A、10常量、5legacy各有独立状态，不默默消失。已有科学值不因暂时disabled或mask false被剪掉。
3. leaf层：所有实际原值与顺序、atom_index/vector xyz-component ordinal、pair原有序两端/basis/列表ordinal、compound原atom_index和各numeric member。科学字符串如basis/index标签是必要值映射，不能作为“metadata字符串”删除。F64用于数值运算，但I64/BOOL/非数值类型、超F64精确整数域、NaN/Inf/signed-zero等另有lossless typed/bit表示与状态；不可把ABSENT/NULL/EMPTY/无效都改成0、NaN或空列表。坏JSON／未支持layout要保留实际科学载荷或完整exception sidecar与locator，超cap则STOP，不截断科学字段。
4. mask层：source_value_mask、candidate value_mask及原compact整行；source/new/review原因与原field/leaf粒度保持，不把field reason伪造成逐leaf因果。z>20、pair冲突与未知SCF仍是review；缓存不得将其自动升级为mask。版本化mask可在缓存值上重新评估，原值不改。
5. provenance层：source file path/bytes/SHA（producer inherited还是本轮fullSHA明确分开）、row-group/physical row或可独立定位的record+owner、base payload/order/geometry hashes、software/protocol/parser/registry/mask rule pins、精度原metadata、status/source_status/failure_code、converged三态与scf_iterations、raw_audit_selected/raw_locator。各字符串字典化可以，科学意义与locator不能丢。
6. geometry与frame：base提供Z、positions_A、native_atom_order_sha256/source_native_geometry_sha256；xtb perturbed自己的positions_A、seed/sigma/view来源也保留，不能把base位置冒充扰动坐标。frame/origin状态保留PENDING_CONTROLLED_READBACK及证据pin，不因数值聚合旋转不变就宣称实际坐标对齐。按实际D4需求可将bond graph保留为独立源ref；不能因cache未存坐标而宣称geometry/frame审计完成。

允许丢弃的是已证实不被科学解码/质量规则/复现/来源定位使用的重复序列化包装字符串；必须先列allowlist及替代字典映射。precision JSON、raw locator、basis、pair/compound键、科学JSON本身不在可随便剔除范围。源文件不删除。

试点验收应给实际：每field/component叶数及dtype/null/非finite质量守恒；14slot覆盖；source-role守恒；原值逐bit或显式typed-semantic parity；leaf顺序/indices/raw compound key往返；compact mask/reason parity；r73的ordered/unordered重复分类；N/A空值独立分类；source opens/closes/max handles、16实际PID、RSS与自然drain；cache unique inode bytes、未压缩buffers、峰值scratch、实际读/hash/写字节和wall/coreseconds。只在源列表/原值可重建并可按record重新选择时，才可宣称缓存可复用。

## 6. Main/Alpha分工与成本边界

推荐先Main合法CPU做原源读取、exact owner/status/typed值投影并校验；Alpha只接收实际完成的cache和small manifests，不搬715GBLMDB，也不默认搬全563.5GBlabel。transport plan保留Main origin与Alpha locator，actual新cache SHA/bytes必须来自真实CPU输出；Alpha安装/UID/runtime证明独立。原件未hashverified不能用同SHA文字或SFTP长度冒充。

一次全label＋base解码的producer物理引用上界约575.9GB；投影列可能减少实际页读取，但需CPU实际I/O证明。若本轮另做完整源SHA，将再读取同等575.9GB，即hash＋decode约1.152TB输入量，不含canonical index/临时文件；若按已接受producer校验链只做stable identity，必须如实标inherited，不能报告“本轮whole hash已验”。输出cache大小、压缩率、跨集群带宽及Alpha校验读取量全部未知，待32/512测量；F64展开和每leaf索引有可能很大，不能从31.6MB的现mask-only输出推导cache尺寸。quota保留200GB应在全部pending作业、缓存/spill/源转运/observer储备中一并核算，超过声明cap自然STOP，不默默剪值。

现有EA_IOv4成功证明“每worker最多1个ParquetFile，复用同文件并显式close”的必要性：v3/v1280首批多次建同ParquetFile使元数据并存，曾真实超限；v4将maxRSS降至385MB。新sink应沿payload的单file try/finally循环，不能对每row-group重新构造ParquetFile。不要把全owner索引复制成16份Python；复用readonly SQLite批次lookup。cache出站按owner＋field分区、bounded batch与source weight分片；实际分片数/输出cap在profile后绑定，不能先假定足够便宜。

当前用户资源策略是Main analysis CPU可用节点2/8–19、16CPU/noSBATCH-memory/noexclusive、真实RSS/MemAvailable软STOP后自然drain、48h上限与quota200GB，以及REPORT_AND_CONTINUE成本报告授权。资源归Root统一。payload已有central cpu_auto_memory_queue_v2接入；旧size/normalization CPUv2 runtime仍包含memory_gib及实际64GiB检查，不兼容当前no_mem，不能原样提交；如要跑，需独立薄guard/consumer wrapper保持数学与来源不变。算法DuckDB12GB/spill等是软件限额，不能混为调度内存申请。

## 7. D2／全mask／D4剩余实际CPU工作

| 顺序 | 必须取得的实际结果 | 可复用/需要的最小新接入 |
| --- | --- | --- |
| A | 32/512科学值＋有序key＋mask/provenance cache往返与成本 | 原payload materializer/run/evaluate；新独立sink/reader；Z/order复用base投影 |
| B | 全canonical人口全14slot实际payload长度/JSON/shape/非finite/状态交叉盘点、物理与crossfield候选mask、每field>1%独立HOLD、worst20 | 源一次遍历同时写cache；现8分片171owner/2024files计划重用；8694非canonical另列审计，不当fit人口，其正文目前不由canonical numeric pass验收 |
| C | 同一full source TRAIN的精确median/MAD，再在全角色缓存上出z>20/zero-MAD/withinmol复核 | 原radix calibration/math复用到cache；不拿512标尺覆盖full。此结果仍provisional，非最终Common拟合 |
| D | 全146组件／129物理target的size rho（记录一票＋分子构象中位数敏感性）；5HOF独立context同scope TRAIN元素残差 | approved size聚合＋rank SQL＋HOF TSQR复用；atom/pair需完整有效语义及Z；AO sigma/pi BASIS_INVARIANCE_UNPROVEN保留，候选rho不能自动冻结family |
| E | retained raw/原程序打印precision、dipole独立模长、frame/origin/扰动坐标与force sign实际证据 | 现raw locator候选供独立bounded probe；当前parser只注册dipole xyz，无独立stored magnitude可直接比较。算sqrt(x²+y²+z²)再和自己比较不是指南交叉验收；raw缺失仍UNKNOWN，不擅自跑QM |
| F | Common＋effectiveTRAIN＋opaque geometry map/order＋精确20k诊断几何/其perturbed target排除后的最终fit、独立replay/hash | 现D4 authority/side table/TSQR/type7 tails/moments复用；新cache adapter与新资源wrapper；不从source_record_id误排所有UFF parent |

逐值cache可以显著降低B以后重复解码/传输成本，但只留全源聚合直方图、median/MAD或相关系数不足以重建未来任意Common子集的精确quantile/元素参考，必须保留行级可选择的真实值和mapping。D4当前实现最多10个source pass（energy→多轮精确tails→moments），加独立replay；缓存adapter可把这些变成读cache，但不会免去每一轮的fit mass/hash/有效mask守恒。

目前normalization配置common/geometry_map/diagnostic与两个dataset manifest均为null，旧runtime仍hard64。旧dataset还拒绝pilot或未冻结mask，这是正确边界；不能把Alpha512 candidate_mask归并改名成最终full冻结mask去通过。最终fit只TRAIN且common且非heldout PM7/S′具体geometry及其perturbed targets；VAL/FULL/embargo/diagnostic都不入fit。P′必须使用真实UFF几何自身的P′值、mask、元素参考、rho和归一化，缺P′保持pending，不借P值补齐。

## 8. 单位／原点／精度未冻结项

可明确引用冻结parser/schema的：pm7_B registry60是FINAL HEAT OF FORMATION文本KCAL解析得到的heat_of_formation_kcal_mol；其anion204/cation273/octanol340/water407分context相同量定义。旧XYZ/LMDB energy_raw只有原SCF能量来源证据，不能因base字段别名或数值接近冒充上述HOF。HOF参考应绑定真实canonical字段及其method/charge/solvent。

冻结schema/转换链明确：MOPAC dipole Debye（DIP_VEC:DEBYE）、MOPAC gradient kcal mol^-1 A^-1；xTB dipole从au乘固定常数转换Debye；xTB gradient Eh/bohr；force=-gradient×EH_TO_EV/BOHR_TO_A为eV/A；quadrupole字段按xx,xy,yy,xz,yz,zz声明e bohr²。D3位置Å、PMI Da A²、PBF Å、volume Å³、SASA Å²由冻结调用/encoder支持。这些只闭合量定义/转换，不等于实际body的frame/origin/control读回完成。

仍须保留UNKNOWN或pending：

- 18个dipole组件、3个atom-vector字段、6个quadrupole组件的实际坐标轴等价；multipole原点，带电体系dipole/四极矩的origin convention；quadrupole traceless实际读回。合成旋转fixture不能代替真实程序frame审计。
- D20.MolMR原数值单位scale与原19旧D20生成runtime。官方定义为原子MR贡献求和估计不自动证明旧数值是cm³/mol；冻结schema明确未声明。C4 receipt的RDKit2025.09.5仅证明C4当次环境，不证明更早19项生成版。
- Fukui协议dimensionless与registry e的ΔN/电荷差约定冲突；bond-order/population的语义单位；SUPER Dn/De的1/eV是源维度推导，不是原列显式单位；AO sigma/pi basis invariance未证。它们保留逐字段pending，不凭rho改物理分类或填界。
- D19旧generator曾cast torch.float32、WIRE clone、WP5 F64容器的代码链提示有效F32精度，但缺旧实际build/runtime receipt；Parquet double不能证明程序原生F64，打印decimal precision也不能由Parquet dtype推断。原precision metadata的known/unknown须分开核。
- 原raw大多按失败/1%审计保留；EA7例14contexts此次raw_found=0，不能由缺日志推出SCF未收敛。VIPEA协议GFN1 --vipea、SP协议GFN2，绝对能量非同Hamiltonian，不能作严格跨法能差证据。full census的SUCCESS+convergedNULL taskrows与指南旧约390不是同一口径，不能相减当新增失败。

>1%新增mask或新结构invalid依原阈值HOLD并报告，review项单列；z>20只人工复核；不删除记录、不放宽物理阈值、不伪造单位/SCF/原点。最终D2家族、mask冻结与模型norm/head约定仍需真实full结果与共同签核。本报告只提出最小下一执行路径。
