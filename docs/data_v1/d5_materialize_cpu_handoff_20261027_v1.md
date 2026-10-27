# D5 ordinary materializer — SOURCEFINAL handoff

2026-10-27。源码仅 sb1/workflows/data_v1_final/export/d5_materialize_cpu_v1，10件
（8个Python、frozen_sources.json、README），SourceOnly，待Root精确安装/源码检查及
实际Main CPU3。未运行Python/AST/测试、DATA、SSH、Git或Slurm；无Root/Model/旧源修改。

## 完整入口与科学边界

实现 metadata draft→独立Root scope review→finalize/central-v2→materialize实际CPU→
独立actualC0后readback实际CPU→metadata close。无新controller、publisher、submit动作。
metadata缺最终Common/orders/真实geometry+child/atomcounts/N1 policy/seed/release时只写
NONEXECUTABLE_PENDING_ACTUAL_PARENTS和missing列表，不生成plan/spec/作业或未来SHA。

直接保留原materialize.normalize/selection、v2物理父键validate、io.rank_hash/batches/
quota_preflight、原distributions.run和sampling_projection_v1函数对象。旧run/ingest_worker
没有STOP回调，所以不monkeypatch它们，也不声称调用了它们：新资源I/O做相同的原normalize
行投影/SQLite合并，再调用旧selection，最多16spawn/32pending、共享physical RG合并读取。
原12源（含Model钉住的6codec/reader）与外部原proper-Kabsch源均逐SHA绑定，旧源不改。

保留原磁盘SHA256-uniform-order-v1（不冒称旧PCG64同ID）、固定Root seed，nested120k/
240k/600k/allTRAIN，pilot50k来自120k、5000来自全effective ROUTINE VAL，20k同MID诊断。
两普通来源均≥2，分别取fixed_random末位；base及全部真实direct child从所有训练条件
先反连接，三orders重排training_rank，最低能取保留energy training_rank0。
原opaque/native身份和source_role不变，ordinary UFF不混独立N1/P′extra。

实际finalCommon当前finalizer输出16membership+32physicalmap，但明确orders_frozen=false。
本消费器不会把这些base map直接冒称完整D5几何表或构造未提供的child/原子数/三orders。
需要Root真实输入review/实际producerC0父链后才执行；不等待P′数值来填造几何。
父件字段/列映射/新Root review schema逐条见包README和contract.py。

## 两种实际CPU阶段

- materialize：Main16CPU/no_mem/7200s/64GiB whole output，16GiB在跑批次/自然drain/
  admin储量，真实quota与共享物理空间还需whole wave+remaining+200GB；source3在DATA前。
  全文件SHA、UID1278、regular/literal、FD/路径frame，原角色和Common物理映射两向核对。
  所有列表/几何/诊断/三orders/原频率分布落真实Parquet和外部SQLite；partial/failure保留。
- readback：同16CPU/no_mem/7200s/2GiB，在materialize真实C0+account/raw/source3/resource
  闭合后才能生成；大manifest/SQLite等按DATA而非2MiB source处理。全Parquet逐typed row对
  SQLite、完整nested/role/diag排除/训练rank检查，并让全部TRAIN MID通过旧projection，
  16个不重叠范围产生stream digest。VAL不冒称TRAIN，也不授予旧Model provider生产权限。
  原元素/重原子数/骨架统计含零类别，完整Parquet与原counts/fraction计算对照。

复用旧quota Client真实NFS/marker proof目前**只有CPU13**；新runtime据此严格CPU13，
不是科学条件，不声明别的节点同storage。其他节点需要真实新resource适配/证明，不能只改
literal绕guard。source3可在Root已有合法Main CPU源码任务中执行，不初始化Client/DATA。
有限publisher identity+launch+firsthealth事实必须由Root独立审阅并钉住；实际runtime用
current time≤120s健康观测/60s资源线程锁同identity，不续租不切identity。不新增整8h门。
CPU由实际Client样本写旧格式兼容quota收据，原quota_preflight照常执行，未伪login结果。
memory/finite-wall/quota/space问题STOP新派发并自然收尾，不发signal，不改质量门。

所有旧内层FROZEN status为原兼容格式字面值，外层始终D5_jointly_frozen=false：
ORDINARY_D5_LISTS_WRITTEN_READBACK_REQUIRED → actualC0 →
ORDINARY_D5_FULL_READBACK_OBSERVED_ROOT_PUBLICATION_PENDING → actualC0 →技术close。
Root共同发布、D1/D4、真正D3 label50k+5k导出及source10k、Model loader/VAL验收均另守门。

## Root最小CLI

模块前缀 workflows.data_v1_final.export.d5_materialize_cpu_v1；在实际Main安装树：

```
PY -B -m unittest workflows.data_v1_final.export.d5_materialize_cpu_v1.test_boundaries
PY -B -m workflows.data_v1_final.export.d5_materialize_cpu_v1.metadata draft --request ACTUAL_REQUEST --output FRESH_CONTROL_DIR
```

三份随附JSON是明确不可执行/未批准模板，所有未知实际refs/seed均null；不是新Root签认。
可先用materialize模板生成真实missing-parent pending小件。Root填真实父件后另建新request；
draft生成的root_review.template只允许独立review改变status/reviewer和finite-space-review=true。

```
PY -B -m workflows.data_v1_final.export.d5_materialize_cpu_v1.metadata finalize --draft FRESH_CONTROL_DIR/draft_receipt.json --root-review ACTUAL_REVIEW
PY -B -m workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.materialize --spec FRESH_CONTROL_DIR/stage_spec.json --authority ACTUAL_AUTHORITY --node compute-0-13 --job-name dv1_q_UNIQUE_ROOT_NAME
```

Root统一注册、submit/activate；本任务不提交。真实runtime由central完整argv/source/proof绑定：

```
PY -B -m workflows.data_v1_final.export.d5_materialize_cpu_v1.run --plan EXACT_PLAN --startup-proof ACTUAL_PROOF
```

materialize真实C0后，Root用readback模板填真实materialize_closure_references
{receipt,startup_proof,accounting}，另审另提交。readback真实C0后只读小元数据闭合：

```
PY -B -m workflows.data_v1_final.export.d5_materialize_cpu_v1.metadata close --readback-receipt ACTUAL_RECEIPT --readback-proof ACTUAL_PROOF --readback-accounting ACTUAL_ACCOUNT --output FRESH_CONTROL_CLOSURE.json
```

打包ZIP严格10个Root-relative源码member；source_manifest逐path/bytes/SHA，原来源13件
（12repo+1external）闭合清单在包frozen_sources。Root实际source-check/3pure和后续两CPU
结果都尚无，不能以本SourceFinal记PASS。SOURCEFINAL后STOPEDIT，待Root实际反馈另版本修复。
