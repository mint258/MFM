# Sparse32 原始读取链：Main 导出，Alpha 独立读回

本阶段只处理实际 v4 `prepared32` 的32个原 PM7 pointer。Main 从原 LMDB 复制原 key/value 字节，Alpha 用 SHA 固定的原 `sprime_v6.read()` 真正打开新稀疏 LMDB、原样解码并逐字段读回。新 UFF/QM 调用均为0，不打开/消费 once ledger，不调用 N1 generation/core，不生成第二几何，不把本读取控制变为 common、dataset membership 或正式跨端点生成授权。4599/89749的派发归属、QA replay 和 importer 留待独立 Root 审查。

所有新文件均在独立 namespace；旧 N1/v4、原 common/reader/prepare、原32 task/base/receipt 和旧运行证明不修改。Main 来源 UID1278，Alpha 实际 UID1264，各自独立新 allocation、新鲜证明和输出。原文件的 Main inode/UID/path 仅溯源，不能当成 Alpha 文件身份。

## 固定输入及传输

唯一来源是 Root 的实际32审查 `control/n1_actual32_pilot_science_cost_root_review_v1.json` 指向的 v4 `prepared.json`（实际 prepare4521417）和 pilot receipt（实际 generation4521418）。读取小 accounting/raw sacct 证实两父均 C0。选取 `prepared.tasks[32]` 和 `baseline_packets[32]`，与 `source_population_authority.selected_molecule_ids` 精确守恒；task 的唯一 original pointer、baseline 原 row/validation/atom order 保持不变。原32的生成包/claims只在原 receipt 中溯源，本 stage 不读取 claim 文件或再消费任务。

`real_index` 必须是真实非负 int64，原 key 就是 `f'{real_index:09d}'.encode('ascii')`。9是最小宽度，超过9位不截断。pickle 内原生 `idx` 是独立字段，原样保留，不强行设成 `real_index`。同 key 出现在不同 origin LMDB 时分别建库；同一 origin/key 重复立即 STOP，不静默去重。必须32个唯一 molecule/record、32个唯一原 KV。

Main 只访问这32个原 value 和原数据库 footer/page，不遍历或 hash 整个约715GB数据集，也不打开 LMDB 的其它 key。每 value 先核实际长度和 `record_payload_sha256`，之后原 reader 才解码。原 loader 本身没有单 value 上限。本新链增加 **8MiB/value、256MiB全部 raw value** 的有限软件界，超限显式 `UNKNOWN_STOP`，不截断、不重试。

按 origin 原路径分组，新库 `map_size=round_up(2*actual_group_raw_bytes+16MiB,page_size)`，单库≤528MiB、所有 map 之和≤1GiB；map 总界在创建任何库前检查。没有自动 grow/resize。写原 key 和原 value，`overwrite=False`，sync/close 后另开 read-only 环境完整比较 key set、entries 和每个 value 的字节；只对**新库**做全文件 SHA/fstat。再用冻结原 `read()` 对32个新库 execution pointer 真正读回，比较 Main 原字段、原 idx 和 graph。原数据整文件 SHA 明确 `null`，不编造。

Main `manifest.json` 的 `alpha_data_references` 是实际产生的新文件的预期 Alpha locator triple（path/bytes/SHA），不是已完成传输声明。组成：每 origin 1个新 LMDB +32原 task JSON +32原 baseline JSON +32个 Main typed signature JSON，即 `number_of_origins+96` 件。原 writer 的 lock 文件保留在 Main 输出内，但不传输；Alpha 原 reader 使用 `lock=False`。源原 value 实际 bytes 和总传输 bytes 要由本次 Main CPU 产生，准备时不捏造。

另外部署3个原 source 原字节 `common.py/sprime_v6.py/prepare.py` 到同一个 `original_sources/` 目录；原 recipe JSON 单独原字节保留。一个新 `alpha_recipe.json` 只改变 `science_source_pins` 的2个 path（legacy/prepare）以及 `external_output_root`，保留其 bytes/SHA、科学参数及其它字段。Alpha 对新 recipe 与原 recipe 做完整 dictionary 差异限定，不覆盖原 JSON，不改 frozen globals。绝对 execution pointer 使原 reader 的 Main `PROJECT` 分支不被使用，完全不 monkeypatch `read/PROJECT/HANDLES`。

Root 搬运时，按 manifest 的 `alpha_target_locator` 路径部署。建议 `alpha_input_root=/gfshome/alpha/codex_data_v1_20261026/inputs/n1_sparse32_readchain_v1/<fresh_tag>`，须为该前缀严格新子目录。Main 原 task/base 内的引用仍是 Main 原路径；Alpha 只比较溯源字面值，不跟随这些路径读取原 Parquet、全 LMDB、roles 或 once ledger。

## 字段与 graph 签名

`signatures.py` 对 PyG `Data.to_dict()` 的实际字段生成有类型结构，不声称覆盖该接口之外的隐藏对象状态或跨字段 storage alias。包括 Python None/bool/int/IEEE754 binary64原 bits（区分±0、NaN payload）、字符串/bytes、顺序容器、NumPy dtype/shape/logical-C-order原 bytes、Torch dtype/shape/stride/layout/requires_grad/device 和 logical-C-order原 bits。tensor 用 uint8 bit view，绝不转 float64；例如 bfloat16 也不先 cast。NumPy object/subclass、Torch非strided/quantized/subclass/特殊 view、任意未支持类型、循环容器均是 `UNKNOWN_FIELDS_NOT_EQUIVALENCE`，两个 UNKNOWN 也不能判相等。

有限签名界：depth32、nodes100000、单 leaf逻辑64MiB、单 record逻辑128MiB、结构 JSON1MiB；超界只产生显式 UNKNOWN，不能靠该不完整签名接受等价。原 value bytes 不改、不裁剪。比较是原 dtype 与精确逻辑 bits，不作容差、缺失填补、单位或 precision 改写。PyG idx 同时单独签名，缺失明确 `present=false`，不推导新 idx。

graph 使用原冻结 `graph/fix_stereo/ordered_graph`；原 `geometry_sha` 规范构造 z int64 + PM7 xyz float64 SHA，核对原 v4 baseline validation 的 atomic numbers/atom order/ordered graph/PM7 geometry/stereo。调用这些原读取/graph函数不做 UFF/QM。Main 和 Alpha 原源函数文件要求 byte/SHA相同；新包装函数没有宣称自己与旧 generation/core 整函数 AST 相同。

Main/Alpha 两次真正原 reader pool 都是16 spawn进程，每个进程1组2条；16方 barrier 在开读前保证实际16个 reader PID，不把请求16CPU冒充16实际 workers。每个 worker 的 `legacy.HANDLES` 由原 `read()` 自己维护，上限仍4；额外 raw SHA 读取若已有同环境则只读复用，避免同一进程重复 open 同库。没有修改或替换 frozen globals。

## Main metadata 协议与 CLI

固定 scope key `n1_sparse32_readchain_export_v1`；`scope_parameters` 必须精确等于新 `guard.PARAMETERS`（纯stdlib literal）。analysis / **pilot=false** /16CPU /`SLURM_DEFAULT_UNSPECIFIED`/wall≤3600s/output2GiB/selected input2GiB。这里 nonpilot 指只读归档 stage，32范围仍严格封闭，不能放行全量或生成。采用现有 central `cpu_auto_memory_queue_v2.runtime.require_startup`，新鲜真实 CPU13 allocation、Root 正式 request/plan/source pins 和现有同存储 quota provider；不另造队列或 publisher。

Root 新 plan schema `MAIN_N1_SPARSE32_READCHAIN_EXPORT_PLAN_V1` 必须有：

- `scope_key,scope_parameters,wall_seconds,output_cap_bytes=2147483648,selected_input_cap_bytes=2147483648,output_directory,alpha_input_root`；Main 输出为 `RUN/artifacts/conformers/n1_sparse32_readchain_v1/<fresh_tag>` 严格新子目录。
- `prepared_reference,pilot_receipt_reference,science_cost_review_reference,accounting_reference,catalog_reference,recipe_reference,quota_provider_review_reference` 真实小 triple。
- `science_sources={common:catalog.references.io,legacy:catalog.references.graph_stereo_rmsd,prepare:catalog.references.legacy_prepare_import}`；catalog 就是 prepared 的原 v4 frozen catalog。

Main request source pins：新 namespace 全 `.py/.md`、plan、上述小 authority/catalog/recipe、3原 source；实际 v4 `__init__/io/contract/quota_provider`、quota provider `references()` 全部小 authority；Main实际 centralv2所有 source 与 Root新审查/决策。package父级 `__init__.py` 也应由 Root SourceRefs明确包含。request data pins：prepared32 原 task/base 64件。原 source population authority、raw accounting 必须列为批准小 source；原大 pointer index、原 Parquet只作 task/header 溯源，不作为这次运行正文输入、不做其全 SHA。

```text
MainPY -B -m workflows.data_v1_final.conformers.n1_sparse32_readchain_v1.main_export --plan ABS --root-preflight ABS
```

源码-only核验可由 Root 在许可位置运行，不 import 科学库或读取 LMDB：

```text
MainPY -B -m workflows.data_v1_final.conformers.n1_sparse32_readchain_v1.verify_port --catalog ORIGINAL_V4_CATALOG --output NEW_SMALL_PROOF.json
```

这份 proof 只核冻结3文件与原 read/graph函数 AST、无 repickle/生成调用/旧模块属性赋值；不冒称实际32读回/Alpha科学等价。

## Alpha metadata 协议与 CLI

新独立 primary 必须是 `AlphaRoot/code/n1_sparse32_readchain_v1/alpha_read.py`，module `n1_sparse32_readchain_v1.alpha_read`，同一个新 package 的所有 `.py/.md` 原字节部署。新薄 controller 由 Root 实现；本包不复制或替换旧 controller/gate。

key `n1_sparse32_readchain_alpha_v1`；stage `READ_ORIGINAL_LMDB_VALUES_FIELD_GRAPH_CONTROL32`；plan schema `SECONDARY_N1_SPARSE32_READCHAIN_PLAN_V1`，proof schema `SECONDARY_N1_SPARSE32_READCHAIN_STARTUP_V1`。scope PARAMETERS 与 Main 相同；kind analysis、pilot=false、16CPU、no_mem、wall≤3600s、whole output2GiB；endpoint218.192.171.238:22/uid1264/真实允许 node。输出为 `AlphaRoot/artifacts/n1_sparse32_readchain_v1/<fresh_tag>` 严格新子目录。

```text
AlphaPY -B -m n1_sparse32_readchain_v1.alpha_read --plan ABS --startup-proof ABS
```

plan 基础字段：`schema,scope_key,producer_key,stage,endpoint,uid,run_root,node,python,kind,pilot,cpus,memory_policy,wall_seconds,output_cap_bytes,output_directory,scope_parameters,execution_argv,source_references,data_references,parent_evidence_references,root_review_reference`。标准 Root review schema `EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1`/`APPROVED_FOR_EXACT_STAGE`/reviewer=root，批准 exact scope/argv/locators；proof复用现有 Alpha标准6字段 request（kind/pilot/cpus/memory_policy/wall_seconds/execution_argv）及 actual gate/job/source-target/controller/storage 证据，但 schema/key/stage是这次新 scope。

此外 plan 必须有以下字段：

- `origin_manifest_reference` 是 Main 实际 manifest triple；`input_manifest_reference` 是 Alpha原字节 copy 的真实 triple，两者 bytes/SHA相同但路径不同。
- `science_sources,recipe_reference,original_recipe_reference` 等于 manifest `alpha_science_sources,alpha_recipe_reference,alpha_original_recipe_reference`；均在批准的小 source pins。`data_references` 精确等于 manifest `alpha_data_references`。
- `main_export_accounting_origin_reference` 是 Main export **实际新job** C0 accounting triple；`main_export_accounting_reference,main_export_raw_sacct_reference` 是 Alpha 原字节 copy，小 parent evidence/source pins。原 accounting 的 Main raw sacct locator仅溯源；Alpha读取的是明确批准的新 copy，核对bytes/SHA、export manifest真实job、UID1278/16CPU/node13/C0。不用原1417/1418或 Main startup proof当成新 Main exporter C0。
- `transfer_verification_reference=null`；没有未来 receipt SHA。actual `transfer_verification.json` 由本次 Alpha allocation 的6 fixture全PASS后，再16线程stream/hash全部 data refs、核fstat稳定性产生。Root 不须先创建独立全hash任务。
- SourceRefs明确包括新全package、原3 source复制件、原/新 recipe、Main manifest copy、ParentC0/accounting/raw小证据、Root审查/plan，以及真实 Alpha `secondary_cpu_queue_v1/__init__.py,common.py`、薄 controller/gate/storage/policy/runtime 全transitive小 source。source-target证明必须包括plan/review/pinned小件；data refs不可提前当source hash。

Main原 task/base/signature、Alpha新 LMDB全文件正文只在 admission/sourcepins/**原6 synthetic方法**全PASS后读取/hash。六个方法在Main/Alpha各自同allocation顺序运行并保存实际 transcript/count/sourcepin；不另占父job，不克隆旧10生成测试，也不造fixture PASS。native Torch/RDKit/NumPy/lmdb/PyG实际版本写 receipt；RDKit必须原2025.09.5；Main Torch2.10/Alpha2.5.1的差异保留，不宣称环境相同，只有实际原32字段/graph等价结果才能接受这个窄读取控制。

## 资源、STOP 与实际验收

16CPU/no scheduler memory request。每阶段有限 input/output各2GiB；软件 RSS软界32GiB、MemAvailable软floor4GiB，wall留120s自然drain，输出预留16MiB failure/metadata；这些是软件界，不是 Slurm内存请求或正式生产资源豁免。Main每60s消费原same-storage真实登录 quota provider，保留200GB加整stage和provider reserve。Alpha需新鲜实际Root quota/storage proof，明确全部pending输出cap和2GiB当前stage reserve；共享Gluster本次搬运输入也要Root单独纳入storage scope。Root新controller可继续现有全storage观测，不以Main compute-local df替代Main account quota。

resource STOP只停止派发下一个record group/源库/hash件，已在运行的自然完成并保留结果，不给科学进程发kill/terminate、不自动重试。所有cap/原SHA/shape/graph/fixture不满足写UNKNOWN/FAIL，不生成PASS receipt。不会因跨端点传输不完整而把旧Main原路径偷偷当fallback。

Main成功只声明原32 raw KV实际导出、重开逐KV验证及原reader读回；未知字段单列，不伪造字段等价。Alpha只有32条全部 `EXACT_ORIGINAL_READ_FIELDS_IDX_GRAPH_MATCH`、实际16 reader PID、所有原bytes/graph/idx相同且无resource STOP才C0。任何UNKNOWN返回3；actual drift或资源错误非零并留failure。尚未实际运行的源码交付不是科学结果；本stage无合法自动启动下一轮nativeQA或production入口。
