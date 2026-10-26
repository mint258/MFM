# Actual Main C0 → expected Alpha handoff

与已冻结Main builder、consumer11及v14完全分开。纯stdlib Main登录metadata helper，先Root真实完成Main export并闭合accounting/raw/proof/request/script，之后Root明确 `--approve --reason` 才可生成预期SFTP清单、copy_relocation、Alpha plan和Rootreview；不读/hash任何新LMDB、task、baseline、signature正文，不运行科学或提交。Main32字段 UNKNOWN 或非明确MATCH均拒绝。

```text
MainPY -B -m workflows.data_v1_final.conformers.n1_sparse32_metadata_alpha_v1.prepare \
  --approve --reason "Root exact Main C0 and independent Alpha source install review" \
  --main-manifest ACTUAL_MAIN_EXPORT/manifest.json --accounting ACTUAL_MAIN_C0_CLOSURE.json \
  --source-install-map MAIN_BYTE_COPY_OF_ACTUAL_ALPHA_SOURCE_INSTALL_MAP.json \
  --source-install-map-alpha-path ACTUAL_ALPHA_ORIGINAL_SOURCE_INSTALL_MAP.json \
  --metadata-output NEW_MAIN_CONTROL_DIRECTORY \
  --alpha-metadata-root ALPHA/control/readonly_specs/n1_sparse32_v1 \
  --alpha-output ALPHA/artifacts/n1_sparse32_readchain_v1/read32_v1 \
  --alpha-startup-proof ALPHA/control/secondary_startup/dv1_n1_sparse32_v1.json \
  --alpha-node compute-0-6 --alpha-python ACTUAL_ALPHA_LOGICAL_PYTHON
```

全部替成实际绝对路径；Main输出fresh，Alpha路径只声明locator，不借Main的exists/stat推断Alpha状态。默认wall3600，整分钟且120<wall≤3600，固定analysis/pilot=false/16CPU/no_mem/2GiB。复用冻结Main builder的受限AST参数读取器，只读guard.py源码，不import科学；Main helper三件也须已实际部署Root。新Alpha文件须Rootreview/SFTP后由v14 prepare再逐小件验证，helper不自动操作。

## Root独立actual source-install-map

Root先在Alpha实际观测consumer11、v14三件、base queue全部py及5命名小authority的bytes/SHA，再将该actual观察JSON原字节复制Main作为本helper输入。不能从Main文件hash直接构造“已装Alpha”声明。

```text
schema = ROOT_ALPHA_SPARSE32_ACTUAL_SOURCE_INSTALL_MAP_V1
status = ACTUAL_ALPHA_SMALL_SOURCE_PINS_VERIFIED
reviewer = root
endpoint = 218.192.171.238:22
uid = 1264
observed_references = [actual Alpha {path,bytes,sha256}, ...]
references = {
  resource_authority_reference,
  cost_decision_reference,
  source_handoff_reference,
  controller_source_review_reference,
  storage_scope_reference
}
```

`references`恰好上述5键，每个triple必须出现在实际observed集合。storage固定scope7。`source_handoff_reference`是冻结11pin文档的实际Alpha copy，bytes/SHA必须与Root docs原件完全相同。consumer11逐件比冻结handoff的expected Alpha refs及实际Root代码；v14三件/base所有py也必须实际观察且与Root实际源字节相同。source-install-map本身的真实Alpha原路径单独由 `--source-install-map-alpha-path` 提供，其bytes/SHA来自Root已核Main原字节copy；实际v14还会在Alpha读取该源pin。这里不要求尚未搬运的Main原3reader+recipe假装已安装。

observed集合必须恰好为consumer11、v14三件、base queue全部py及5个named引用的并集；不接受其它payload或不相关文件，防止小JSON正文混入SourceRefs。

## 输入和输出边界

Main manifest、C0 accounting/raw、实际startup proof/request/script都是允许小header；实际Main proof仅历史父证据，不能作为Alpha fresh启动。冻结Main source11须确实出现在实际Main request.source_references；manifest字段完整/未知0、精确32、无generation/once/resourceSTOP。

只从实际manifest继承每新LMDB完整SHA及每record的原task/base/signature refs。body data为g+96件；Root copy map恰g+107，含5原source/recipe及6个Main父metadata。不得造715GB全源SHA或未来Alpha验收SHA。三原source原字节及原/重定位recipe属于接下来Root的实际SFTP，不混进“现有Alpha源码安装”证据。

输出 `copy_relocation.json,root_review.json,plan.json,sftp_inventory.json,metadata_handoff.json`。SFTP库存包括g+107实际来源文件和新生成3件copy-map/review/plan，所有target均EXPECTED_ONLY；source-install-map及已实际部署code不重复当新body搬运。plan.transfer_verification_reference为null，真正body全SHA/fstat及6fixtures由本次新Alpha CPU按冻结consumer顺序完成。

handoff给出v14 controller argv模板，其中新queue目录/jobname仍由Root选择。Root先真实搬运并核小件，再手动调用v14；helper没有automatic transfer/prepare/submit/retry，不开放native32 QA、4599/89749或dataset/common release。
