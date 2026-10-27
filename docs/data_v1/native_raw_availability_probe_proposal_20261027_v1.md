# Main native-frame前置：既存raw/input可得性探测提案

PROPOSAL_ONLY / NOT_IMPLEMENTED，2026-10-27。先交Root审阅再实现；0QM、0UFF，不运行原producer/重算入口，不修改已有数据、frame/质量容差或D1。本文只由源码与已闭合小metadata制定，child未读Parquet/SQLite/cache/raw正文、执行Python/测试/SSH/Slurm。目标首先取得每原条件/字段的**准确可用locator与缺证据分类**，不是再跑20k样本或宣告native-frame PASS。

## 1. 最小范围与原依据

建议一次Main合法CPU allocation、16实际元数据worker、32个固定canonical record上限、每record原12个QM task的execution键上限384。D20/D3不是原量化raw条件，base另作输入定位；不把其当缺少第13/14种程序raw。先检查原投影witness是否属于既存audit membership，若在则优先；其余从原audit成员按canonical record_ordinal、record_id固定次序补足32。不是新的随机代表性样本，不以结果优劣挑选；不足则明确PARTIAL/UNKNOWN，不自动扩大到20k/全源。

不要求为选择这32条再读整个typed缓存或原Parquet values。原closed cache/witness只作已有locator/provenance交叉线索；真正raw保留依据是原record-level membership与完整canonical execution。32和384均为待Root确认的scope ceiling，不是成功数量或运行时间forecast。示例资源上限可为16CPU/no_mem/900s、whole128MiB（含报告、partial、observer/log；不是每worker）；Root需按当前scope/并发存储预留和≥200GB余量另行审查，不由本文授权提交。

以下均相对Main `/share/home/zixiao/descriptor_analysis`。小manifest实际读核，较大DATA引用仅从既有producer manifest继承；child没有打开/新hash这些DATA：

| 用途 | 精确locator / inherited pin |
|---|---|
| 原retained audit权威 | `runs/phase1_wp5_20261011/audit_membership/job_4513945/manifest.json`；4253B / SHA7703f183c86de567f26a5354357ed0debba276a936542c34e63a0b8d8fc9159f；状态AUDIT_MEMBERSHIP_CLOSED |
| 审计成员DATA | 同目录`selected_records.parquet`；568576B / SHAcb8fd23bab6090b804eb397fbbbc35f112647df9a29b0a7e547c33def2637ffb；原manifest rows112223，非本次重数 |
| 全canonical owner DATA | `runs/data_v1_20261025/artifacts/labels/source_status_v1/auto_memory_v1/prepared/canonical.sqlite`；1733042176B / SHA290c4b7dd55eaf89c34d5a6c09b5201ccbb27a5c20db4b17876d7283a20a4b32；只取所选record的完整owner/ordinal/lane/natom |
| 最新SCI执行/容器DATA | `runs/phase1_wp5_20261011/acceptance/final_20261016_v1/catalog_closed_v2/latest_molecules.parquet`；30233309B / SHAc6ea21ab66b62415011fb71f475a803c895418d5a8b69a31302d7ac3805c1d80；取archive_path、execution_id、完整owner、COMPLETE及receipt/export一致性 |
| archive producer引用DATA | `runs/phase1_wp5_20261011/acceptance/final_20261016_v1/catalog/catalog.json`；3485465B / SHAb5aed096ae0dc4c479a64b9b05e8709205911a0f9a474b71ae1490992ce28765。各archive路径/bytes/SHA必须由这里及上列SCI执行双向绑定，不猜路径，不全盘glob |
| 已闭投影线索 | `runs/data_v1_20261025/artifacts/labels/source_status_v1/bounded_projection32_v1/{manifest.json,witness_discovery.json}`；manifest226933B/SHA344b7e3dadd09075307b171296e7ae88d008cbe1bd032fd932531230bbf49694；witness23579B/SHAce85cdd2bbd9c78e8c24ee631ced6db4eb7c639a48a7c868adaa84e39ac42ed0 |
| 字段/condition映射 | Root `configs/data_v1/label_registry_v3.json`及原raw registry；用实际registry_id/task/path/component，r73=73/pm7_B，r674=674/xtb_singlepoint；不按人类别名猜 |

原typed witness record_ordinal2535608的task2/file29、task11/file33、task10/file27均为RG0/physical-row5；分别可定位r73/r82、r674、r625。**尚未证明该record属于audit，不能据witness身份预期raw必在。** 其parity0diff也不证明native输出/坐标轴。source prepared manifest的authority_locators/canonical_index已记录上表大DATA的pin，可复用而不登录节点hash数GB正文。

## 2. 两级只读探测，先元数据后决定是否读任何native输出

### A0：只查容器元数据，不取科学BLOB

1. 在CPU中核小pin；按上表membership/owner/execution选定32条，冻结候选清单及选择原因，再做任何raw查找。canonical `record_id,molecule_id,attempt_id,job_id,task_id,lane`必须与latest_molecules一致，状态必须为已闭SCI；若矛盾则UNKNOWN/拒绝，不退回历史attempt。执行键始终为`(record_id,calc_type,execution_id)`，不能让reader从部分raw自行挑latest。
2. 每个archive只开一个`sqlite3 mode=ro`连接，`PRAGMA query_only=ON; BEGIN`只读snapshot；按archive分组分配最多16worker。先核schema/metadata格式、原policy、audit/package/dictionary manifest身份及容器当前UID/regular/no-symlink/size/fstat稳定。producer整文件SHA仅作继承lineage，若未本轮全读就不声称fresh wholeSHA。
3. 原WP5是`WP5_OUTPUT_ONLY_DICT_ZSTD_V2`，表为`records`，含dictionary-Zstd的raw_frame/metadata_frame。它与P′retained72的gzip `raw`表不同。首级查询只显式取record/task/execution/molecule/dict_id/source_status/scope_status/retention_reason/input_bundle_sha256/hex(raw_sha256)/raw_bytes/metadata_bytes及`length(raw_frame),length(metadata_frame)`；不`SELECT *`，不fetch/decompress raw_frame，不访问parsed_molecules/wire_frame，不pickle。记录不存在、执行错配、schema不符分别报告，不自动换旧执行。
4. 结果先记`RAW_ROW_PRESENT_NOT_BODY_VERIFIED`或`RAW_KEY_MISSING`；source status/SCF NULL不等于本次确定失败。只有metadata存在不能称某一字段的native token已找到。

### A1：可选，仅有界metadata_frame解压，不读raw_frame

若Root同意在同scope增加此步：先核压缩/未压缩metadata声明长度和软件cap，绑定archive dictionaries表→原dictionary manifest→字典bytes/SHA，再fetch该行metadata_frame并用原`wp5_archive_v4.Zstd.decompress`按metadata_bytes有界解压。这里只读原raw metadata JSON，不读科学输出成员。

检查原context/owner/execution、program/version/keywords、input_bundle/file hashes、audit/reproduction身份及`output_file_manifest`的member名/bytes/SHA；与source/cache的`raw_output_locator_json`等已存证据作精确匹配。按task/field给出`MEMBER_DECLARED_NOT_READ`与后续native-field parser入口；声明某member存在不意味着其内部r73/r674/梯度数值可读或物理frame正确。metadata cap/字典不符均失败留证，不放大cap自动重试。

原policy明确`input_bodies_saved=false`；原ArchiveWriter forbids输入文件。故首级输入状态通常只能是`INPUT_HASH_ONLY`，不能把output member或hash当原input正文。若某独立已登记保留包确有实际input locator，只记录它的精确ref/owner/执行来源；不通过文件名猜测，也不本次读取内容。

## 3. 可复用函数与必须新增的薄边界

| 原能力 | 本提案使用边界 |
|---|---|
| `labels/lossless_projection_pilot_v1/projection.py:{verify_cache_row,decode,at}` | 若需要已知固定cache row的source_status_and_precision/provenance，仅复用精确typed解释；不重跑原512、重算mask或扫全部values。未需cache则不加载科学float pool |
| `labels/payload_audit_v1/run.py:143–167` | 既有details.raw_precision_candidates已保存record/task/raw_locator_json/program/input/package hashes；优先复用，旧候选不足不改原报告 |
| `wp5_archive_v5.py:{retention,ArchiveReader.get}`与v4 schema | retention定义原audit/failure范围；get只作后续原格式解析参考。A0/A1**不调用get**，因为它会fetch/decompress raw科学BLOB；更不能调用含pickle的iter_staged |
| `wp5_archive_v4.py:{load_dictionaries,Zstd.decompress,unbundle}` | A1只复用前二者验证metadata；unbundle是未来确切输出成员读回的原函数，现在不调用 |
| `wp5_engine_v3.py:{render_inputs,perturb_seed}` | 后续独立frame阶段才可对已绑定base原Z/坐标/record/protocol重建input bytes并逐file/bundle SHA匹配；纯renderer，不调用initialize_worker/compute_molecule/NATIVE.invoke/任何程序 |
| `pprime/frame_native_precision_diagnosis_v2/{tokens,precision}.py` | 后续有限native token/轴诊断可复用其原算法，不把旧run_v2的retained72人群/guard套给本scope；其gzip BoundedRawReader不得套给WP5 Zstd archive |

**唯一待Root审阅的新实现范围**：一个独立source-specific metadata driver，负责小权威/有界候选、canonical join、archive元数据SQL投影/A1 cap、fstat/句柄关闭、16worker和状态矩阵；复用当前中央准入/observer/Root唯一提交。不新增queue、通用数据层、raw格式转换器、QM调用或新的native数学。无需重跑既有1620/2048fixture；只为新SQL“不取raw BLOB”、显式execution/schema及metadata边界做必要小验证。本文还未写driver。

## 4. 输出、判定与后续最小数据需求

输出新外部manifest＋候选/availability矩阵：原12task ×其登记字段，每项带record/完整owner/execution/archive/dict refs、原audit标记、raw-row及member声明状态、input hash/actual-input locator状态、program/keyword/package身份。列出未覆盖条件/字段、所有missing/ambiguous/error、实际元数据I/O/opens=closes、16worker与Root会计；不回写mask/registry/原统计。最强状态只能是`FINITE_NATIVE_LOCATORS_DISCOVERED_FRAME_AND_VALUES_PENDING`，不足则PARTIAL，不是native frame PASS。

Root接受矩阵后再单独决定真正native读取范围：每必要task/物理目标最多若干既存retained执行，原输出BLOB/字典/精确member refs、对应base与真实perturbed child坐标/原子序、原输入hash及原protocol/package作为明确DATA。先证原input能按纯renderer逐字节重建（含原perturb seed与噪声一次），再做输出token/坐标/单位/参考系检查。未保存input且不能哈希复现的case继续UNKNOWN；无raw不另跑QM补证。原P′15FAIL与本次PM7 native可得性矩阵分开，均不能替代全view与最终D1联签。