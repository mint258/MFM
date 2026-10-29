# C 架构 resolve / prepare CLI

本入口补齐 Stage5 的具体配置接点，委托已有
`phychem_mfm.phase1.v3_architecture_readiness`，不新增选择算法或准入证书。
原 `prepare_proxy_plan.py` 仍只生成 symbolic 计划，原 recipe/grid、训练、CP、
H0、物理门和 A 路径均未修改。所有 FP32 补偿候选继续停止、不采用。

## 两个命令

由 Root 在合法 CPU 作业和绑定的解释器下运行；下面环境变量须绑定真实路径、SHA。
`W` 是本分支工作树，`N` 是工作树外的新输出目录。此文档没有执行这些命令。

```bash
"$MODEL_V3_PYTHON" "$W/tools/model_v3/prepare_architecture_experiment.py" resolve \
  --inputs "$RESOLVE_INPUTS" --inputs-sha256 "$RESOLVE_INPUTS_SHA256" \
  --output "$N/C_resolution.proposal.json"

"$MODEL_V3_PYTHON" "$W/tools/model_v3/prepare_architecture_experiment.py" prepare \
  --inputs "$PREPARE_INPUTS" --inputs-sha256 "$PREPARE_INPUTS_SHA256" \
  --output "$N/C_trial_prepared"
```

输入 manifest 使用已有 rawref 约定。顶层只接受下列字段，拒绝额外模型、registry、
执行策略或参数覆盖。文件 SHA 是实际原始字节 SHA，不是 index/registry 的 canonical SHA。

| 命令 | 必需字段 | 可选字段 |
| --- | --- | --- |
| resolve | policy、policy_sha256、resolution_inputs | 无 |
| prepare | policy、policy_sha256、trial、base_request | resolution_inputs |

- `policy` 是已有固定 Git 登记引用
  `{repository, commit, path, sha256}`；`policy_sha256` 是审阅绑定的真实政策 SHA。
  由原 `registered_policy` 核其固定 blob，不能用任意 JSON 冒登记。
- `resolution_inputs` 指原
  `model_v3_architecture_resolution_inputs_v1` 文件及其 raw SHA。原 API 核
  global seed SD、panel/CP/执行证据、C1 timing 和 C3 auxiliary，再调用原规则。
  C3 必须依赖真实 C1；不从预训练 loss 或局部数值统计造选择。
- `trial` 是 symbolic plan 的 `trials` 中一个完整对象，保留七字段
  name/stage/condition/pretraining_seed/sample_budget/parameters/requires。
  参数传输仍为有序二元组的 JSON list，进入原 `PlannedTrial`。
  原编译器核精确20个初始 trial、证据、固定预算和公共配置；
  此入口不生成/批准补 seed、任意参数或新 trial。
- `base_request` 指原已绑定的 `authoritative_proxy` 请求；
  不是 UNIT、pilot、full TRAIN 或 grid 请求。

`resolve` 只写原规则的解析提案和 input_manifest rawref。它不产生训练配置或准入；
`prepare` 不信任该提案输出作为选择许可，而是从 manifest 的原始
`resolution_inputs` 重新调用同一个 resolver。首批 C1 不需要未来 C1/C3 选择，
后续 C3/H/pooling 仍须完整真实依赖。

## 真实 prepare 的门与输出

直接调用原 `prepare_trial`，不接受调用者自带的 LabelRegistry，也没有 plain-builder
或 performance fallback。它首先验证原请求/完整 source map、登记/Root admission、
D1/D2/D3/D4/D5/三卡 SDP smoke 等现有门，再由原 pinned adapter 绑定真实数据：
只读、节点本地、release_accepted、本请求身份、registry/normalization/D5 TRAIN
240000 个分子、PM7/all conformer、两 validation 人口及既有 release/ACK 政策。
policy/config 同版本 joint 或签名 ACK 不能代替最终标签 release。

编译保持六层512、C-only `backbone.distance_bias_projection_bias=False`、
原 A4/global attention、原 registry 和 heads 语义；C1-a/b 的 pair-feature MLP bias
不删除。已登记20项的 distance/views/head/pooling 由原 API 解析。
新 C 尚不支持的 training_execution/performance/Native/compiled 组合仍明确拒绝，
不静默改成别的实现，也不把既有 A 的20+500资格借给 C。

只有上述实际 gate 成功并且符号全部解析后，才建立新目录并由原 API 写：

- configuration.json
- request.UNADMITTED.json：registrations 为空，Root_admission 为 null
- PREPARED.json：CONFIG_CONCRETE_UNADMITTED

输出必须全新且在 Git 工作树外。缺 authority、未闭合选择、未知符号、
错 raw SHA 或错误 scope 均拒绝，不建立可执行 plan。
成功的 PREPARED 也不是科学通过、冻结或执行许可。Root 后续仍须当前源/参数/CP/H0、
当前 FP32 物理规则、真实注册、资源/配额和实际执行证据；FP64 数学成功不授 FP32 PASS。

## 源码交接与验证边界

本分支只新增三个文件：

- tools/model_v3/prepare_architecture_experiment.py
- current/tests/test_model_v3_architecture_cli.py
- docs/model_v3/C_ARCHITECTURE_PREPARE_CLI_V1.md

新测试复用原 architecture fixture。真实固定 Git blob 测政策绑定；
分派正例仅在明确 UNIT 回调中调用原 compile_trial，覆盖 C1/C3/pooling 解析，
不 mock 实际 Data 资格为真、不产生训练请求。另保留真实 prepare 拒绝路径、
原证据 schema 门、输入 SHA/未知覆盖/输出位置/跨 scope 拒绝。

作者未运行 Python、AST、collection、测试、模型、Git、Slurm、SDK 或科学 payload；
新测试数与通过结果均待 Root 实际核验。原112/133/134测试源未改，
当前基线1ac350的完整134证据不能自动授本新增 CLI 通过。
真实 Data D2–D6 未交付时生产入口必须保持拒绝。

指南 Stage7 的最终 model/recipe JSON、HANDOFF_v3.md、model-v3.0 tag 与
120k/k2/1M 单格实际 smoke 仍是独立未交付项；本分支不创建假冻结文件或启动模板。
