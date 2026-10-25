# MFM3 wire → model candidate provider

状态：实现准备完成，**尚未执行测试，未验收真实 D3 或共同冻结 D1**。基于 Root 提供的 e47d066e53f000d71c05bf1c772597f2a5c42c30 隔离树 `model-v3-wire-provider`。本次只编辑该树，未提交 Slurm、连接服务器运行计算、执行本地科学 Python 或改动数据线/旧冻结科学源码。

新增 `v3_wire_provider.py` 与 `v3_wire_audit.py`，并在 `v3_data.py` 的 `DecodedSample`、`V3Batch` 末尾增加默认 None 的可选审计字段。原 sampler、heads、loss、S native transport 和 PreparedV3Batch 没有修改。旧调用继续得到 audit=None；审计不进入图输入或学习特征。

## 可实施的真实文件链路

测试在 Root 的 PrivateStorage 所提供的节点本地 TMPDIR 中新建小型 LMDB，通过数据侧原 `encode_record`/FamilyWriter/GranularFamilyWriter 写入 MFM3，关闭 writer 后以原 FamilyReader/GranularFamilyReader 实际 readonly 打开。不存在时或依赖 SHA 不同直接失败，无 skip、替代 decoder 或合成 provider 假读。

`CandidateWireFactory(index, registry, manifest, node_local_root=..., allow_candidate=True)` 只接受明确的 synthetic_fixture index/registry 和 `synthetic_candidate_fixture_only_not_D3` 绑定。manifest 是模型自有固定 fixture 的原始文件/locator/target/codebook 引用，不是对 D3 release schema 的发明或接受。factory 把配置规范化保存为不可变 JSON；读取属性返回副本，spawn 不传递任何 LMDB 句柄。

每个 worker 在自身 PID 中打开实际只读环境；分别校验 data.mdb SHA、schema SHA、COMPLETE、记录/独立 mask 数量和 LMDB readonly flag。真实 resolve 后的路径必须在声明的 /tmp fixture root 内，/proc/self/mountinfo 必须显示本地文件系统；NFS/CIFS/SSHFS/Lustre/GPFS 均拒绝。记录实际节点、root/文件 inode/device/UID 和文件系统类型；不靠 node_local=True 自我声明。打开后每样本检查文件 stat 身份/大小/mtime，原 codec 对每条 payload/header/索引进行校验，不每条重 hash 整个库。

worker 的 Finalize 调用真实 close，显式 close 也走同一幂等关闭路径。可选 handle-events 写入私有 fixture 根。测试把小型本地文件身份与 worker open/close closure 留在共享 pytest 输出，关闭后只清理自身在 TMPDIR 新建且复核归属的 fixture 子目录；原始数据和既有证据不删除，LMDB 不复制进 Git/共享 unit 输出。

固定 DataB export 目录为 `runs/data_v1_20261025/repository/workflows/data_v1_final/export`。完整导入依赖固定为 codec/mapping/store/granular_store 和两个包 __init__，都按原 SHA 检查；导入期间关闭 bytecode 写入，模块实际路径不符也失败。模型 source pins 另记录这些外部依赖，不复制数据线源码冒充模型实现。

## 身份、数值与原因

每条 choice 使用 opaque geometry locator，manifest 显式指定 export_record_id，跨 geometry/family 核对 molecule、source、effective/source role、n_atoms、parent/view 和 identity SHA。source 拼写仅采用已声明的 pm7→PM7、uff_sprime→Sprime_UFF。A typed index 存在 `native_identity_for` 时逐值核对其原五字段，并按相同 canonical UTF8 JSON 记录 native identity SHA。不把 native_record_id 当跨来源构象号。

固定 synthetic fixture 的 atom-order 证据绑定 source_atom_ids、Z 原数组摘要及原 fp32 positions 摘要。各 fixture record 另有明确的 `model_fixture_atom_order_sha256` 收据；这是 **test-only 模型收据**，不是声明真实 DataB 已输出该字段或完成原子序科学验收。真实 D3 必须提供共同确认的原子序/坐标/来源证据后另行接线。

Z int16 原样转 long[n,1] 后减1；坐标保持已有 fp32 数值，不重排/旋转。graph scalar []→[1,1]、atom scalar [n]→[n,1]、graph vector [3]→[1,3]、atom-vector [n,3] 原样；vector 按 all_components 得到模型 row validity。缺失分量仍是原 NaN/invalid，不补有效零。各字段 pairs 独立转置成 long[2,p]，collate 仅添加本分子的 atom offset。

`SampleSourceAudit`/`FieldReasonAudit`/`MemberReasonAudit` 只保存 tuple、字符串、数字和布尔，无 Tensor、ndarray 或 MappingProxyType。原逐分量 validity 与模型 row validity 分别保存，source/new/review field reason sets 与 sparse leaf exceptions 原样分开；65535 保留 unresolved leaf cause 含义。字段原因集不被展开成每个 leaf 的稠密因果。review 不改变 validity，group/family exposure 独立记录，collate 后的训练 mask 不回写源有效性。按 export_record_id/target/member/leaf 可查询原证据；未知 codebook SHA 或原因码拒绝。

V3Batch.to/pin_memory 原样保留 CPU 审计对象，不迁上 GPU；PreparedV3Batch 训练接口保持原样，`WirePreparedProvider.audit_for(choices)` 可重新查询原 CPU 审计，不保存预取游标或修改 consumed clock。采样仍由原 sampler 的 commit_batch/原 trainer 提交；prefetch 不消费未提交 draws。

## S+D+P 合成贯通与明确拒绝

只有 fixture 提供带原始文件 SHA 的 synthetic bond codebook、逐码 wire→旧 native 类别映射和旧 descriptor_schema SHA，才生成既有 NativeBondTransport。这个 toy 映射不声称真实 wire codebook 科学含义。未提供映射、未知 wire code 或请求真实权威时拒绝启用 S，不静默删除 S 标签。S views、A4 三头和原损失没有变更。

准备的模型测试使用真正6层512维/8heads/ff_mult2 encoder、现有 V3HeadBank/V3MultiViewModel、真实 fixture decode/collate/PreparedV3Batch，执行 S+D+P 一次 CPU optimizer 更新并检查各组及 S element/noise/bond 与 D/P 有效人口非零、loss/梯度 finite。这只是候选工程贯通，不是正式训练、性能/数值验收或 D3 科学读回。

当前明确不支持：tensor 头/损失、r73 basis 身份、实际 off-equilibrium 标签 view、真实 D4/D5 权威/VAL 人口、跨 condition 的归一化混合、真实 bond codebook 接受、真实 source atom-order 科学验收。生产权威与 VAL 路径硬拒绝。所有 P/D fixture 字段必须有显式一对一投影，family 的声明目标不允许静默忽略；单来源 base clean scalar/vector 的合成实现不等于全部146分量已接入。

## Root 测试请求

预计 **26 个参数化测试**，目前未执行。依赖 torch、torch_geometric、numpy、lmdb 和上述固定 DataB 文件；不允许因外部缺失而 skip。Root 使用实际可用 CPU 节点、至少16CPU，建议16GiB/15min，GPU 隐藏，提供经 PrivateStorage 绑定的实际 /tmp 私有 TMPDIR，设置 PYTHONDONTWRITEBYTECODE=1。pytest basetemp 可留共享 unit 输出，里面只写小 closure，不创建 LMDB。

```bash
PYTHONPATH=current:current/tests python -m pytest -q -p no:cacheprovider \
  current/tests/test_model_v3_wire_provider.py --basetemp SHARED_UNIT_PYTEST_ROOT
```

另跑现有 native bond transport、v3 data/trainer/structural 相关测试，再由 Root 对整树执行完整 pre/post suite 与源码 SHA 核对。包含实际两 worker spawn/退出、部分 vector、review/exposure 分离、字段 pairs offset、原默认行为、WRITING、payload/mask identity、source/record/atom-order/codebook、未知原因/键 code、真实只读句柄、文件后续变更、未提交预取恢复与 S+D+P 单步。审计 .to(meta)/pin 协议测试不宣称 CUDA 验收；所有实际结果另由 Root 回填。

最终 A→B 集成由 Root 在两线通过后统一合并完成；本树没有复制尚未冻结的 A 源码或绕过其独立核对。
