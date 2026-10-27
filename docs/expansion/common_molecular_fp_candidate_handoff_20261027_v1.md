# Common 分子结构特征 producer 候选交接

状态：**SOURCEFINAL / NONEXECUTABLE_CANDIDATE**。新独立目录
`workflows/expansion/common_molecular_fp_candidate_v1`，9 个 Python 源文件、1 份
原创建者源码证据 JSON、1 份 README；本交接文档另外入包。旧 features、精确近邻、
排序、外排、finalCommon 代码与所有 DATA 均未改。

## 已解决的字段歧义

原 `RDKitDescriptorGenerator._annotate_impl` 明确从 `data.smiles.strip()` 建图。
`canonical_smiles` 由 `isomericSmiles=False` 生成；`isomeric_smiles` 由同一
template 以 `isomericSmiles=True` 生成。因此不能按字段名字选择前者作为完整立体图。
新候选提出原创建者的 `smiles.strip()` 入口，须 Root 依该证据独立审阅。

原 WP5 原样保留 source 和 geometry-reidentified 身份，并保留全键变体、
`QC_key_reproduction_mismatch_accepted_difference` 和
`QC_other_layer_accepted_difference`。新候选要求投影携带这两个原标记，完整保存
历史键与差异，**没有新增“全部历史键必须等于新 derived full key”的门**。
创建者/传递链/原 finalizer/现有 consumer 的实际 source26 字节 SHA 和行号均在
`source_evidence_v1.json`，不是 DATA 当前观测或执行授权。

## 新接口做什么

- 原 `features_legacy_compatible_v2.features_candidate` 对象直调，仍只允许旧成功
  passthrough 与原精确 ring-Kekulize fallback。没有新特征实现或化学修复。
- 原 source graph/key/QC 每条物理记录先写 SOURCE；每个图结果在 reduction 与
  未来 Parquet 之前持久化。当前仅提供要求真实 fsync sink 的库接口，不伪称已有写盘。
- 每 MID 所有合法 source graph 形成 rich union。唯一 canonical isomeric graph /
  full-key 且各特征相同才形成旧 consumer strict5 候选；真正多图、未知或特征冲突
  全部保留并 HOLD，不任挑代表、不 OR FP、不新增化学排除。
- MID/role 长度前缀有序 digest + 各角色分子数/原物理记录数核对。一个 MID
  只计一次；不同 MID 同 full key 仍分别计。CID 无原 authority 就为 null。
- 无环 Murcko 空串、原 ring list 不变；现有 consumer 的每 MID ring set-presence
  频率语义和精确近邻数学不重写。

## Root 可直接审阅的入口

仅 small metadata CLI：

```
python -m workflows.expansion.common_molecular_fp_candidate_v1.materialize \
  --request /absolute/actual_request.json \
  --output-directory /absolute/fresh/common_fp_candidate
```

请求 schema=`COMMON_MOLECULAR_FP_CANDIDATE_REQUEST_V1`，
`requested_scope=FINAL_COMMON_TRAIN_VAL_ONLY`；必须给实际
`source_evidence_reference` 与 `contracts.KERNEL_PATHS` 顺序的 4 个旧 kernel
small triples。可缺、须显式 null 的当前父件字段：

```
common_population_manifest_reference
canonical_authority_receipt_reference
graph_selection_review_reference
final_parent_accounting_reference
origin_relocation_review_reference
```

只读取已给的小 metadata/source 并校 SHA；若有真正 final manifest，检查其
`COMMON_POPULATION_V1_FROZEN`、16 membership locators、TRAIN/VAL 实际 roles
及 canonical receipt 关系。DATA 使用独立大文件 locator validator，绝不打开/哈希。
输出始终 `NONEXECUTABLE_CANDIDATE`，不生成 Root approval / submit / COMPLETE。
README 有可选语义 review 的精确字段；helper 不代签该 review。

## 仍需的实际门与边界

当前未提供最终真实 Common 父件与完整终态 accounting，也未在 CPU 读取 membership
或 canonical DATA，因此不造 MID census、未来 refs、成功标记或 actual 图唯一性。
后续真正 CPU port 必须独立实现 fresh resource admission/全 argv/source、原3 pure
before DATA、全部 input wholeSHA+stableFD、Arrow/DuckDB 有界原列投影、16workers/
32pending、真实 durable writer/readback、全 MID/role/records 守恒和 Root 实测预算。
当前库不是 allocation guard，不能直接当正式 runner 使用。

Alpha 移位须保存原 Main UID1278、endpoint、origin refs；另有明确相同 bytes/SHA
origin→target map，并在 Alpha UID1264/scope7 的实际 allocation 首次 fullSHA。
不得改写原 Main JSON 路径后声称原字节或把 Main 执行冒作 Alpha。

baseline1M 的“PubChem 相同规则筛选” authority 仍须 Root 另冻结，不能借 R/N
已去污染域、成功子集或 Common query 代替。NN/图表/1M 均无实际完成声称。
orders/P′、identity、pool/decontam/D4 release 与原15协变 FAIL/HOLD 不变。

## 新纯测试（SB4 未执行）

`test_boundaries.py` 恰好3方法：原字段与 accepted-key 差异、真多图/UNKNOWN HOLD、
MID/role 守恒与 strict5/空串/ring/large DATA-v-small metadata。无 RDKit 导入和
科学 DATA。Root 可用既有真实 CPU source-only fixture stage 运行；不能把源码静态
审阅称测试 PASS。本轮没有 Python/AST/tests、DATA、SSH、Slurm、Git 或远程安装。

所有源文件在 SB4 worktree 新目录；只读 Source26 cache 用于读原小源码。外部 source
artifact ZIP/manifest 由纯 PowerShell 源码打包，Root 应逐 entry 复核再决定安装。
