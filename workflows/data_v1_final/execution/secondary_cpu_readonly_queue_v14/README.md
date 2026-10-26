# v14：仅稀疏32原始字段读取控制

只允许 `n1_sparse32_readchain_alpha_v1`，stage `READ_ORIGINAL_LMDB_VALUES_FIELD_GRAPH_CONTROL32`，primary `AlphaRoot/code/n1_sparse32_readchain_v1/alpha_read.py`，module `n1_sparse32_readchain_v1.alpha_read`。不接受旧 Alpha16 QA、其它只读 key、UFF/QM、新数据生成、4599/89749全源派发或 dataset/common release。

consumer原11件保持 SOURCEFINAL，不修改。精确逐件Main/Alpha target pins的handoff源文件是 child `docs/data_v1/n1_sparse32_readchain_v1_source_handoff.json`。它列出 actual child source triples 与 expected Root/Alpha target triples；部署仍须实际Root/Alpha逐件bytes/SHA核对，handoff不声称已经安装。adapter另固定这11份bytes/SHA，并检查Alpha实际文件；不能靠新metadata悄改consumer。

沿用已部署v11的controller实现，源码复制只做3种错误标签替换：

```text
EXACT_V11_PUBCHEM_AB_SCRIPT_SCOPE_REQUIRED -> EXACT_V14_SPARSE32_READ_SCRIPT_SCOPE_REQUIRED
ONLY_EXACT_PUBCHEM_AB_PROTOCOL_ALLOWED -> ONLY_EXACT_SPARSE32_READ_PROTOCOL_ALLOWED
EXACT_CURRENT_PUBCHEM_SCOPE7_REQUIRED -> EXACT_CURRENT_SPARSE32_SCOPE7_REQUIRED
```

其它控制逻辑/有限wait/hold+release/once提交/实际job读回/parent+steps记账不变；源码逆编辑验证交Root执行，未运行Python/AST/tests。脚本仍唯一 `PYTHONPATH=AlphaRoot/code`，复用现有 `secondary_cpu_queue_v1.gate/probe/common`，storage scope固定 `control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json`。没有代理、跨端点SSH或新常驻服务。

协议基础字段沿 SOURCEFINAL consumer README。新增 `scope_mode="EXACT_CANONICAL32_ORIGINAL_READ_ONLY_CONTROL"`、`performance_profile=false`，analysis/pilot=false/16CPU/no_mem/whole2GiB，wall为整分钟且120<wall≤3600。Root review同时绑定exact output_directory。独立新Alpha proof schema `SECONDARY_N1_SPARSE32_READCHAIN_STARTUP_V1`，actual UID1264/node/gate/start ticks/boot/clock/script/argv仍由Alpha真实controller生成；Main历史证明永远只作父证据。

adapter在Alpha登录侧只读取≤2MiB源码/小metadata。所有新LMDB、32原task、32原baseline和32Main field signature，即使后缀为JSON，也只是批准locator，绝不在登录节点stat/open/hash/解析。Body refs与SourceRefs必须不相交；真实Alpha CPU的6方法全PASS后才完整hash正文并原reader读回。`transfer_verification_reference=null`，`transfer_verification_expected_output_path=output_directory/transfer_verification.json`；禁止编造future hash/通过状态。

## 必需小metadata

consumer已有plan字段之外，v14要求：

- `resource_authority_reference,cost_decision_reference,source_handoff_reference,copy_relocation_reference`，均为实际Alpha小件SourceRefs。resource authority由现有Q.authority校验，Rootreview/decision仍须真实授权，不能借旧QA权限。
- `input_manifest_reference` 为Main实际export manifest原字节Alpha copy，同时列入ParentEvidence/SourceRefs；`origin_manifest_reference`为真实Main triple。原manifest必须实际新job、UID1278/node13、严格32字段signature完整/UNKNOWN0，Main稀疏库原reader比较全为明确MATCH，32raw SHA/全部新库全SHA/16+16实际workers/无resourceSTOP。字段/shape/graph未知不得自动放行。
- `main_export_accounting_origin_reference`为Main实际export新job的C0 closure原triple；`main_export_accounting_reference,main_export_raw_sacct_reference`为原字节Alpha copies，ParentEvidence/SourceRefs。核对标准Main accounting/raw的UID1278/C0/16CPU/node13/elapsed及manifest真实job，不接受原4521417/1418或Alpha1884766/768替代。
- `main_export_startup_proof_reference,main_export_request_reference,main_export_script_reference`为实际新Main export的三件小Alpha copies，ParentEvidence/SourceRefs。它们的Main原locator依次取自manifest.actual_parent_proof_reference、Main proof.request_reference、Main request.script_reference。核完整原字节、原request equality、Main source set与固定11Root code、原primary8argv及scope/no_mem资源。这里只核历史父链，不把其旧时间/UID当作新Alpha fresh proof。
- `science_sources,original_recipe_reference,recipe_reference`由真实Main manifest继承，SourceRefs须含三原source原字节copy及两recipe。新recipe相对原JSON只能改两个science_source_pins.path和external_output_root，不能动阈值/seed/shape/数值。

Main export实际metadata未到时，代码只是拒绝缺证据的schema/验证器；Root不能填placeholder/未来bodySHA或假C0来提前submit。v14不创建plan、request、未来receipt或任何Slurm任务。

## Root独立copy relocation

字段 `copy_relocation_reference` 指向Root独立生成的新小JSON：

```text
schema = ROOT_MAIN_SPARSE32_ALPHA_COPY_RELOCATION_V1
status = ROOT_REVIEWED_EXPECTED_LOCATORS_NOT_BODY_HASH_ACCEPTANCE
reviewer = root
source_endpoint = 202.38.247.57:22
target_endpoint = 218.192.171.238:22
Main_export_manifest_origin_reference = plan.origin_manifest_reference
Alpha_manifest_copy_reference = plan.input_manifest_reference
Alpha_body_hash_acceptance_claimed = false
entries = [{kind,origin_reference,target_locator}, ...]
```

每个origin/target均精确triple且bytes/SHA相同；origin与target各自唯一，entries顺序任意但集合必须完全等于实际Main manifest/parent chain可独立重建的以下条目：

1. 每个database.reference→database.alpha_target_locator，kind=`sparse_lmdb`。
2. 每record的 main_task_copy_reference→alpha_task_reference，kind=`original_task`；main_baseline_copy_reference→alpha_baseline_reference，kind=`original_baseline`；main_signature_reference→alpha_signature_reference，kind=`main_signature`。
3. science_source_copies的 main_copy_reference→alpha_target_locator，kind=`frozen_common`/`frozen_legacy`/`frozen_prepare`。
4. original_recipe_copy_reference→alpha_original_recipe_reference，kind=`original_recipe`；alpha_recipe_copy_reference→alpha_recipe_reference，kind=`relocated_recipe`。
5. Main原manifest→Alpha manifest copy，kind=`Main_export_manifest`；Main原accounting→Alpha accounting copy，kind=`Main_export_accounting`；accounting.raw_sacct_reference→Alpha raw copy，kind=`Main_export_raw_sacct`。
6. manifest.actual_parent_proof_reference→Alpha proof copy，kind=`Main_export_startup_proof`；Main proof.request_reference→Alpha request copy，kind=`Main_export_request`；Main request.script_reference→Alpha script copy，kind=`Main_export_script`。

若有g个origin，新科学data为g+96件，整个copy map为g+107条。Main原32task/base的旧路径只溯源，不读取原全Parquet/715GB LMDB；不得给这些整源补猜SHA。数据部分必须精确等于manifest.alpha_data_references并守恒32record/molecule/origin-key；每新库entries/key/valueSHA/length、mapSize、实际新库fullSHA都要有真实Main producer证据。Root copy metadata是独立locator批准，不能冒充Alpha body实际hash通过。

实际部署source pins包括新v14全部`.py/.md`、冻结consumer11件、现有base `secondary_cpu_queue_v1`所有`.py`、Rootreview/plan、上列authority/handoff/copy map/全部parent小件、三原reader source和两recipe。controller另把source review/authority/storage/input及其actual target pins纳入request，fresh gate/probe/controller证据沿原框架。Root执行实际sourcecheck/逆编辑审查后才可登记并实际运行；本交付没有运行源码或科学测试。
