# 有限物理范围的 typed label 投影（SOURCE，尚未实际执行）

本目录6件独立源码，不改 frozen lossless_projection_pilot_v1、payload_audit_v1、
footer_inventory_v1、footer_continuation_v1、streaming、normalization、queue 或原方案2docs。
尚未执行Python/AST/fixtures/科学扫描/SSH/Git/Slurm。Root先sourcecheck、审阅新request，
再实际CPU。实现的是可继续的有限批次，不授权全人口投影、最终mask、registry或D4。

## 已有真实依据与精确输入

Root实际footer续算4521749为C0/113s/16CPU19；输入应取实际
`artifacts/labels/source_status_v1/footer_continuation_full_v1/manifest.json`。
manifest必须是`ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING`，errors/pending均空；
其32layers连接原407及新1801的实际小report和gzip metadata inventory。
本实现从实际小manifest/book/report取SHA、bytes、owner/frame和member位置，
不把1317456实际RG数写成算法假设，不捏造未来hash。
label物理157254650、原canonical157245956/差8694与base物理11232475、
canonical11231854/差621分别保留。footer不证明numeric值、数组长度、SCF或native precision。

profile必须取Root实际4521610的512 typed cache manifest及其真实C0 accounting/raw/proof；
旧4251records/512molecules/494609729B是已测样本，不是本批预定记录数或全量体积保证。
需要Main实际`DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1`形状的parents、原sacct header和旧startup
proof来绑定job/output/config；旧proof只作历史证据，实际运行必须重新取得中央新鲜证明。
helper不读Parquet/SQLite/gzip/cache正文，也不stat/hash这些大body；小代码/JSON逐pin读回。

初次selector直接沿用原512 owner plan的label/base source列表，校对全sourcebook的path/bytes/SHA。
默认每source取第1个**实际**RG，并在同次CPU中从旧512 produced cache/provenance确定固定witness RG。
按source path/physical row/ordinal/task固定最小序选择task/base、146 enabled字段的既存表示、
实际CELL kind/native-family/storage float-width和非空layout witness；最多512类别/额外RG。
未在旧512观察到的kind/width不宣称已核。每个固定witness都必须实际覆盖且科学签名相等。
它会投影所选范围内所有canonical行，不按512 RID过滤，也不反复按512记录重扫owner。
首次prefix最多64RG/source，另只加实际witness RG；source数严格小于2208，不能借此放行full。
实际记录数、覆盖task和原512 overlap都在CPU测得，不预先冒称4251/146全部已验证。

## Root元数据入口

先把本目录6件按实际字节安装到Root repo，再运行小metadata helper：

```text
PY -B -m workflows.data_v1_final.labels.bounded_projection_v1.materialize
  --footer-manifest ACTUAL_FOOTER_MANIFEST
  --footer-proof ACTUAL_1749_STARTUP_PROOF
  --footer-accounting ACTUAL_1749_ACCOUNTING
  --footer-raw-accounting ACTUAL_1749_RAW_SACCT
  --profile-manifest ACTUAL_4521610_MANIFEST
  --profile-proof ACTUAL_4521610_STARTUP_PROOF
  --profile-accounting ACTUAL_4521610_ACCOUNTING
  --profile-raw-accounting ACTUAL_4521610_RAW_SACCT
  --resource-authority CURRENT_NO_MEM_AUTHORITY
  --metadata-directory FRESH_CONTROL
  --output RUN/artifacts/labels/source_status_v1/FRESH_BATCH
  --row-groups-per-file 1 --whole-output-cap-bytes 34359738368
  --approve --reason ROOT_FINITE_BATCH_REVIEW
```

helper只生成selector/config/resource binding/Rootreview/stage_spec，不提交。原common/roles不冻结
也能做source投影，但不能fit。centralv2仍是唯一新鲜准入和Root提交入口，无新queue：
analysis/pilot=true/16CPU/no_mem/7200s/whole32GiB（Root可明确选8–32GiB有限cap）。
`--approve`与reason必须由Root实际审阅提供，不是child替Root批准。
whole是上限而非forecast，Root另保留全部未写Sprime、copy/spill和200GB quota reserve。

主入口`bounded_projection_v1.run --config ... --startup-proof ... --output ...`只允许
上述有限scope。freshguard及所有source pin之后，原6payload+3projection与新4boundary
必须实际全PASS/no skip，才打开真实gzip metadata、canonical SQLite、cache或label Parquet。
原6/3 test body不复制、不修改。metadata directory的大gzip正文在本次CPU中fullSHA验证；
先读旧produced cache实际定位witness，随后只解压所选source的完整member、核其compressed/raw
signatures，取得prefix和witness的实际RG物理范围。稀疏witness不要求重读到它之前的所有RG。
Root生成metadata helper时不必在login处理数GB footer正文。

## 逐源读法与科学边界

每source可含数个不相交physical `[lo,hi)` 段，16实际spawn workers；同源全部段分配同worker，
按实际物理次序共享唯一Parquet句柄，不读取段间未选择RG。每段独立ticket/cursor，gap不能算coverage。
完整关句柄并清掉旧iterator/batch引用后才开下一源，避免旧EA重复footer持有问题。
RG目录来自实际footer；source当前UID/type/inode/size/mtime/ctime必须等于闭合footer
观察，再核本轮fd/path前后稳定和当前RG行数。st_dev是节点本地mount编号：若与footer节点不同，
必须额外用原footer_only核当前原始footer SHA等于实际已闭SHA，再允许同Main路径的device别名；
否则拒绝。额外metadata读bytes单列；同一个原fd再交给Arrow，不另开原source。Arrow source
pre_buffer=False，CPU/IO各1，避免预装整个RG多个列的压缩页。producer整个文件SHA仍只作lineage，本轮不称重新
wholebodyhash；current footer SHA也明确继承实际footer阶段，不凭大小宣称数值已完整读回。
decoded rows、boundary prefix/suffix另报，producer referenced bytes不是storage read bytes。

使用已有immutable canonical.sqlite，16MiB/worker只读page cache；每批最多256 RID查9列
`record_ordinal,record_id,molecule_id,attempt_id,job_id,task_id,lane,total_atoms,new_role`。
formal ordinal不是label文件seek。完整五键匹配，quantum另核lane/natom；shadow或不在authority的
物理行分别计数，不转成新mask。TRAIN/VAL/FULL均保留，source角色不等于最终common fit资格。

`records.project`只组合未改冻结函数：

| 实际功能 | 直接调用 |
|---|---|
| 原CELL/JSON/原list ordinal | `lossless_projection_pilot_v1.projection.scientific_cells` |
| 264声明/146 enabled及ordered leaf paths | 同模块`component_map` |
| 原storage F32/F64位证据 | 同模块`source_float_signature` |
| 原source/new/review mask规则 | `payload_audit_v1.payload.evaluate`及原common/pilot_masks |
| typed tree/F64 pool/原类型及bit签名 | 同模块`cache_row`与`verify_cache_row` |
| 同任务compact编码 | 原`streaming_v1.compact.encode` |

evaluate是**单task完整行**API，fields严格按task过滤；不把未读另13task伪装成missing。
同PM7 B的derived IP/EA/HOMO/LUMO与charge检查仍只在该原行内进行，不跨Hamiltonian。
14task+base只能在最终跨批coverage契约核完整，不能从一个part宣称全记录已聚齐。
base独立task255，空/失败/异常坐标或Z完整保留并显式review，不套旧512全成功前提、不伪Z或删行。
原整数/bool/string/bytes/null、F64位、原F32位池、全部ordered atom/basis/compound键和list顺序
照原codec保留；r73不dedup、不symmetrize、不均值，one-center空N/A不当新missing atom mask。

本broader source批没有匹配full-TRAIN median/MAD；向原evaluate传空calibration映射，
清楚记录`PENDING_MATCHED_FULL_TRAIN_NO_512_SCALE_REUSE`，不把旧512统计评审充作full结果。
原label、source/new physical/convergence/crossfield mask公式和阈值不改；robust-z不自动mask。
NULL SCF不推断未收敛，unit/native print precision/actual frame未知仍未知。

## Whole ticket、原子part与真实cursor

跨process共享单个`state.sqlite`，BEGIN IMMEDIATE在写前预留每task最多128MiB part及256KiB receipt，
同时预留inode。任务数最多2/source（或base1），不允许独立16worker各花whole cap。
同range存在RESERVED/UNKNOWN ticket时拒绝第二dispatch；异常可能写过的reservation不回收。
whole减去1GiB admin和64MiB observer后才可花data tickets，inode cap8192。
state DB软件64MiB、共享rollback journal至多同级；可重建coverage DB软件768MiB且journal OFF，
其余admin余量留report/manifest/目录。coverage不是权威cursor，未完整闭合的index不能发布。
worker3GiB软件RSS与4GiB MemAvailable STOP都只停新batch/source，自然完成当前有界窗口，不强杀。

private bounded Arrow buffer逐write检查128MiB，不先写超额再删除；单scientific row仍64MiB。
64行/8MiB flush格式沿冻结writer，window可跨RG，避免真实131万RG产生每RG一批小文件。
window到32MiB软target或8192物理行关闭，并在物理gap前关闭；每family/task独立typed part，part只含一种task。
全part写入新`.partial`，fsync、rename、重开逐typed/key/order/bit检查；全部成功后写receipt、
再在一个SQLite事务中推进物理cursor。改名但未commit的文件仍UNPUBLISHED，不进coverage。
错误留下ticket/部分文件与最后闭合cursor，不截断科学值，不自动重试或改mask。

下一次Root显式续跑用同helper的`--resume-manifest`，再提供`--resume-proof/--resume-accounting/
--resume-raw-accounting`；必须已terminal、无source科学错误/duplicate/真实parity mismatch。
若有UNPUBLISHED，Root还须显式`--accept-unpublished-retained`，保留旧文件而非假已完成。
新输出从每range最后闭合cursor继续，旧coverage只读导入；前一generation的part仍通过
`previous_manifest_reference`链引用，不复制、不重算、不重复计coverage。
source完整闭合RG不回扫；cursor落在RG内只重decode该boundary前缀。崩溃/错误造成的未commit
window不是已完成RG，最多8192已处理但未发布物理行可能需Root另审再读，必须与boundary额外IO分报。
新batch range_id绑定本次精确source+区间，跨generation以source物理区间和闭合链判断非重叠。

## 实际parity、coverage与停止

part本身先重开科学签名核对；父进程再流式扫描这些闭合part，生成磁盘(ord,task)唯一索引，
发现duplicate保留全部原part并HOLD，不first-wins接受。source、base的非canonical计数独立于duplicate。
对原实际512 cache逐行核wholeSHA/typed签名，比较当前批覆盖到的重叠键：全部科学值/键序/位、
source/new mask均须相同；source review也比较，只排除物理provenance及ROBUST_Z/ZeroMAD/
TrainScale三类不适用的旧512统计review。统计review轴单列PENDING，不能因此忽略任何new-mask差异。
actual overlap/每task和family数如实报告；overlap0、缺任何固定witness/encoding或任何mismatch均HOLD。
146字段witness包含NULL等原存储表示，不冒充全部字段数值有效、native precision或物理正确性已验。
当前批若出现旧512未观察的CELL kind或storage float-width，也单列并HOLD；RAW kind计数witness
只证明原已缓存的计数轴，不冒称重建未引用的原程序metadata payload。source/new-mask/source-review
PASS只针对实际重叠键，完整当前批及全人口都不能借此宣称通过。统计review仍独立PENDING。

partial observed新mask/structural率与`count/11231854`全人口下界分别报；原>1%全人口硬停阈值
不变，观察到的局部高比例也HOLD交Rootreview，不能因下界小宣称full PASS。所有未处理范围、原因、
source异常和UNKNOWN ticket明确pending；只有本次有限请求范围全部闭合、无hold时才C0。
状态仍`BATCH_CACHE_CLOSED_FULL_COVERAGE_PENDING`，绝非full numeric/guide1.5/Common/D4完成。

首个实际试点建议原228源各1prefix RG+实际固定witness RG、32GiB whole ceiling、2h；
同一次allocation先13pure，再旧cache witness定位、真实目录解析/投影/重开/parity/coverage，
测输入decoded rows、opens=closes、RSS、wall、part数和unique bytes。
不从旧494MB/4251线性外推“廉价full”。下一批是否增RG由Root根据实际成本/cap/parity再审批。
全2208/full放行仍需独立Root资源/存储review及范围守恒计划，本入口guard明确禁止自动full。

## Common后norm接口仍待实施与冻结

当前没有norm reader路径伪替换、median/MAD/元素reference/winsor/TSQR调用。
物理part UUID、worker完成次序不能充当统计逻辑分区；coverage按ordinal/task计算逻辑科学签名，
仅在duplicate0时可用于重建核验。最终norm须另冻结共同人口、effective TRAIN、opaque geometry
map/order、PM7/Sprime具体diagnostic及所有perturbed parent目标排除；Pprime独立来源/统计。
再显式cache adapter按固定logical ordinal/task/ordered leaf顺序读出，冻结TSQR分块与合并树、
NumPy/BLAS/LAPACK/线程环境并实际replay。物理part改变不许改变数学归并树；cache位相等
不等于跨环境norm位相等。统计缩尾/能量元素残差不改本缓存原值，也不擅定模型各向异性norm。
