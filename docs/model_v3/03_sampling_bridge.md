# 按来源 typed 采样桥接（候选，未验收）

日期：2026-10-26（Asia/Shanghai）。基线为 Root clean commit `e47d066e53f000d71c05bf1c772597f2a5c42c30`，隔离工作树 `MFM_model_v3_sampling_bridge`、分支 `model-v3-sampling-bridge`。

当前状态：**独立实现与测试源码已准备，尚未实际运行**。本次没有修改旧 sampler、factory、v3_data、公共 contract、数据线文件或冻结审阅记录，没有执行 Python/pytest、SSH、科学计算、训练或 Git 提交。Root 统一进行 Slurm CPU、源码前后核验、checker 和完整 pre/post merge 回归；源码准备不等于 PASS。

## 接入范围与来源

新模块为 `current/phychem_mfm/phase1/v3_sampling_bridge.py`，消费 DataB 的真实
`D5_PER_SOURCE_TRAINING_SAMPLING_PROJECTION_V1` 候选结构。原纯投影函数位于：

`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/wire_v1/sampling_projection_v1.py`

本次只读核对实际 SHA256 为
`50aceee73de4718b7f35dbd2a37a207a7739d57f8ed53f39a36da16bfbc0e2dd`。
数据侧第 41–50、119–153 行已经定义来源独立 entry、opaque geometry_id、保留后的 energy training_rank=0 minimum 与 candidate 状态，模型桥接保留这些语义，不重命名为正式 release。
现有 `phase1/v3_sampling.py` 实际 SHA256 为
`031c387f60697f7b8d0ba1bc38ed64bb08664fddbd00a7a425c597171aac04f8`，本次保持原文件不变。

候选投影只保存 fixed/diversity rank 与最低能 ID，没有携带完整 energy orders 或 diagnostic 表。因此 `CandidateProjectionInput` 同时要求原函数调用的已界定输入，而不是只相信转换后的 dict：

```python
CandidateProjectionInput(
    molecule_id,
    projection,             # DataB 原纯函数返回结构
    training_arguments,     # 该次调用的原 kwargs
    projection_source_sha256,
)
```

training_arguments 必须含 effective_role、training_geometries、training_orders、diagnostic_targets、native_atom_counts、group_mask、family_mask，可选 max_rows；这沿用候选函数输入，不发明真实 D5 manifest/schema。当前入口只接受已明确审阅的投影源 SHA。候选测试实际执行经 SHA 核对的 DataB 原源码字节，未复制其函数为本地镜像。

## typed index 与验证

`build_candidate_sampling_index(..., data_version=..., geometry_source=..., selected_molecule_ids=..., allow_candidate=True)` 显式开启候选路径。caller 的 data_version 原值直接成为 index.version，便于现有 dataset/provider 对齐；版本名本身不作为内容证明。

返回的 CandidateSamplingIndex 实现现有 SamplingIndex 协议：molecule_at、len、version、content_sha256、role。authority 固定为 **synthetic_fixture**，status 为 **CANDIDATE_MODEL_SAMPLING_NOT_RELEASE**，contract_finalized/real_data_export_accepted 均为 false。没有 data_line 或正式 release 升级入口；原投影如宣称 FROZEN、contract_finalized=true 或换成未知 schema 会拒绝。

每个分子保留两个互不对齐的 typed source entry；实际 index.molecules 根据单来源或 mixed 显式选择，每分子只有一个 entry。PM7 与 Sprime_UFF 分别持有本来源的独立 IDs、构象数和 locator。mixed_sources 必须精确覆盖选中分子，且每个分子只指定一个模型来源；不拼接两来源构象，不复制分子作为两个均匀采样单元，不用 native_record_id 伪造跨来源对应。

桥接逐分子重新核对：

- 原 TRAIN 角色、真实 bool group/family masks，以及投影 masks 与原调用一致；不接受 1 代替 true。
- base/view 与 parent 事实、诊断 base/child anti-join、原子数精确键集合与正整数类型。
- PM7 原 native_record_id 与 UFF 原 sprime_conf_idx；UFF native_record_id 仅作 provenance，允许原值为 null，不借 PM7 ID 补齐。
- 三种来源内 orders 的完整成员集合、连续零基 training_rank、保留原 rank 顺序；fixed/diversity 的 typed ranks 与投影一致。
- minimum_energy_conformer_id 必须等于**保留集 energy training_rank=0**，原 energy rank 可以大于 0。
- 单字段 locator 只能引用该 source 的同一个 opaque geometry_id；native identity sidecar 必须逐项等于原几何行。
- 整个候选输入中拒绝重复 molecule、跨分子/来源 geometry ID 碰撞、诊断 ID 回流，以及重复物理身份。off-equilibrium view 不进入基础构象采样。

ConformationSelection 使用原类型；index.make_sampler(seed=..., sample_budget=...) 把已绑定 selection/source 交给原 UniformMoleculeSampler，不改其均匀分子→均匀允许构象、speculative iteration、commit 或恢复逻辑。应从该入口创建 sampler，以采用本次已核对的配置；旧通用 sampler 构造函数仍保持原 API。

候选工程路径对 first_k/diversity_first_k 的 k 不足一律拒绝，不截断补齐或复制构象。该 fail-closed 边界明确写入 bindings，不替最终 D5 决定 N=1/N=2、诊断后不足 k 的科学策略。

## 内容绑定与 native sidecar

所有输入先生成独立 JSON 快照，输出为不可变 dataclass/tuple，避免 caller 修改原 dict 后让已建 index 无声漂移。bindings 返回独立 dict，不暴露内部可变内容。

index.content_sha256 绑定内部候选工程记录，明确不是训练 release schema。记录包括：

- data_version、选中分子的明确顺序、逐分子选中来源、selection 与 k 边界；
- 每个输入 projection、原 arguments、training_geometry、training_orders、diagnostic、原子数、native identity 和各 source entry 的内容 SHA；
- 选中 typed molecules 与完整 native sidecar 摘要；
- DataB 投影源、实际模型 bridge 文件及实际旧 sampler 文件的逐源 SHA256；
- 本候选实现的有界 metadata 参数。

规范化摘要使用 UTF-8 JSON：ensure_ascii=false、sort_keys=true、separators=(',', ':')、allow_nan=false，再取 SHA256。输入版本相同但 orders/diagnostic/native provenance/原子数等绑定改变，原 sampler checkpoint 会被拒绝。DataB 源 pin 是明确的 upstream 实现身份；本桥接不通过一个声明 SHA 就声称真实 D5 表已认证，真实输入文件/manifest 权威仍待交付和验收。

`index.native_identity_for(geometry_id)` 返回冻结 NativeConformerIdentity：geometry_id、molecule_id、geometry_source（原 pm7/uff_sprime）、native_record_id、sprime_conf_idx；as_dict() 原样返回这五项，content_sha256 按上述规范取摘要，model_geometry_source 属性仅映射为既有 PM7/Sprime_UFF 名称。该接口供独立 wire provider 按已有 SampleChoice.locator 联通，不改变 v3_data。

此版本是小规模 fixture/候选索引，不声称解决全量 metadata 的 worker 复制。默认限制为 4096 个输入分子、每分子 4096 几何行、65536 个 base conformer、131072 个总几何行及诊断行；每个原投影/arguments JSON 快照上限 16 MiB。原 kwargs 的 max_rows/default=4096 也单独核对。不足时明确拒绝，不截断科学人口；真实全量需另有 data-line adapter/memory-map。

## 新测试源码与预计覆盖

`current/tests/test_model_v3_sampling_bridge.py` 静态参数化预计 **59 项 CPU 测试**，尚未执行、未观察到通过结果。fixture 默认读取上述 DataB 原文件，也可由 MODEL_V3_D5_PROJECTION_SOURCE 显式定位，但仍要求固定 SHA；执行前后核对相同原字节。

测试链实际为 DataB 固定 SHA 纯函数→候选投影→typed index→原 UniformMoleculeSampler→ManifestSampleDataset/collate。三个合成分子的 PM7 构象数为 1/4/9，UFF 为 5/2/3，ID 和三种顺序各自独立；保留允许的 off-equilibrium 证据，但不将其作为基础 draw。

覆盖内容：

1. PM7、UFF、mixed 三条路径及原子数/opaque locator/native ID/值/暴露 mask 保真；三分子仍为三个均匀采样单元。
2. 原 energy rank=0 已排除后，minimum 使用保留后的 training_rank=0；all/first_k/minimum/diversity_first_k 分别使用本来源顺序。
3. 固定 seed=20261025、30000 次样本、预先声明 alpha=.01 的分子/构象卡方，不重试或挑 seed。
4. 已实际解码但未 commit 的 speculative draws，在重建相同 index/恢复 cursor 后 draw 与 decoded tensors 逐位一致；Python/NumPy/Torch global RNG 不变。
5. 相同 version 但 orders/diagnostic 证据、未选来源 provenance、atom count、molecule 顺序等改变时，旧 sampler 状态拒绝恢复；不可变 snapshot 与实际 bridge/sampler/source 字节摘要核对。
6. candidate opt-in、权威升级、未知 schema、错误 ranks/minimum/locator/native identity/masks、诊断 base/child 回流、跨来源引用、全局碰撞、重复/未知分子、mixed/k 和 metadata 边界的负例。

建议 Root 在已有受控 Slurm CPU wrapper/依赖/源码前后核验下执行：

```bash
PYTHONPATH=current:$PYTHONPATH /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest \
  current/tests/test_model_v3_sampling_bridge.py \
  current/tests/test_model_v3_labels.py \
  current/tests/test_model_v3_native_bond_transport.py -q
```

定向测试通过后仍需完整 premerge 与 postmerge；旧回归或 DataB 原六项候选测试不能代替本修订验收。最终 D1/D2/D5 权威、真实共同人口、D3/D4/D6、实际 wire provider 与正式训练均不由本模块完成或推定。

## 当前源清单

- 新 `phase1/v3_sampling_bridge.py`：`2c15a8b61fa5b071d3e64cd8f769a8e43930174dbaa0555e70a1ef233809d946`。
- 新 `current/tests/test_model_v3_sampling_bridge.py`：`e6e137777b7598a0e8c628b686a1c61c44132f4a36e01145d93c1c1ccaaeb711`。

以上源码 hash 对应本次准备版本，不绑定尚未发生的测试/提交结果。运行证据应另记录实际 Slurm、代码版本、输出路径、检查结果与源码前后核验。
