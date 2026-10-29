# 当前 A-v2：A00 manual 与 HeadOff 的新 R1 ABBA

本包是原 `performance_manual_R1_ABBA_GPU_v1_source` 与
`performance_head_off_R1_ABBA_GPU_v2_source` 的有限来源/资格接线。沿用当前
`single_a_benchmark.py`、`run_supervised.py`、`a_speed_report.py` 原字节。
唯一提交入口每次只选择一个 case、一个 position，没有调度循环或自动重试。

两组是两个独立 series：`A00_manual_R1_Av2_C35_7ffe_v1` 与
`A03_head_off_R1_Av2_C35_7ffe_v1`。各自顺序 reference1、candidate2、
candidate3、reference4，四成员都重新实跑 2 warmup + 20 measured。
两组不能共用 reference 计时，也不采用旧 R1/旧500性能值。Auto4745 不在本包。

源码固定 local `7ffe8a5557590b1481f4ca74073007f070dc6a50`、public
`2b4a4df8636e5d65915d535472ba01084ea72dab`、tree
`8f9530415034bdb885c1c765aee434797c70e7c7`。A-v2 规则先于实际 numeric
运行公开于 `4f6ba16973ea4a30472c7fb33d3aadec974a4462`。
A 保留距离末层 bias；不引入 C-only 删除或已停止的补偿候选。

A00 必须核实际4712 GPU +4717 CPU消费闭合及原六 rawrefs；HeadOff 必须核
实际4722当前20+500闭合的原六 artifacts。后者真实历史Root closure没有
schema字段，本包仅按其被冻结的 exact rawref/status/字段验证，不虚构别名。
两边均核当前code/GPU/C35、完整305 mandatory源码、模型、原数据/manifest、
native S seed0、workers8、P8M、原options、manual85B配置、deterministic controls、
v2 scope、完整20+500及原监督/清理。原fixed/steps较大元数据只哈希不解析，
不再做数字重判。配对两resident容量不迁移为R1容量，R1 candidate明确一resident、
无padding、无auto/profile或OOM退化。

SDK是独立必要门。A00已有实际Root SDK闭合；HeadOff 尚无实际证明时必须拒绝。
固定期待 `performance_HeadOff_Av2_R2_SDK_Root_closure_v1`，不接受CLI自由指定schema。
该接口约定不是实际证书。必须有固定4722、两个真实run ID、由实际CPU审计确定的
角色映射、500行1..500、完整原config/summary/native history、clean EOF/exit0、
两条官方选择性sync与cloud readback、实际审计/sync/GPU三父C0/16CPU及数值closure
原ref。HeadOff未预定两个ID各自角色。没有实际SDK Root closure就不创建hold、不sbatch。
包自身不打开SDK或原journal正文。

资源固定C35完整UUID `GPU-c35f2434-9137-9723-1af5-dc69b6295243` /
compute-0-21。原16CPU、64GiB SB、两小时、6900s监督、RSS56GiB、85%、
每成员whole持久2GiB+private2GiB不变；GPU自动内存尚未获授权。本机普通CPU自动内存
不代替这里的GPU64GiB。原public UUID锁仅由single benchmark持有；Root仅执行
严格known_hosts下可用锁预检后释放，不外层fd9持锁。每成员独立family/2GiB hold。
Root使用原V8 registry_lock并保留所有其他原登记行；quota须覆盖全remaining+64GiB。
真实scontrol/squeue/MemAvailable/NVML/foreign/public锁和全流程120秒freshness保持；
不取消或迁移其他任务。传sbatch前清除继承的全部SBATCH_*，防止隐式exclusive/
资源覆盖；显式argv仍原16CPU64GiB。

位置2..4仅在同新series的上一成员实际完成后准入：当前元数据、原源图、参数配置/
角色、22步完成/SDK finish、监督/私有清理、fresh sacct C0均核，SDK/journal只stat。
这不替代Root对四成员的正式metadata闭合和后续独立SDK审计。真正速度表仅在四新成员
Root闭合后运行原a_speed_report，并传各自本次当前20+500 summary；实际速度、资源峰值、
科学采用全未填。原report还有20%/资格要求，不能因本包准入成功称R1通过。

Root 在发布此七叶 exact blobs、源审和fresh资源准入后，逐次调用：

```text
STAGE43_PY -u -B PKG/Root_submit.py --case a00_manual --position 1 \
  --source-pins-sha256 ACTUAL_PINS_SHA \
  --method-publication ACTUAL_NEW_METHOD_RECEIPT --method-publication-sha256 ACTUAL_SHA \
  --SDK-closure ACTUAL_A00_SDK_ROOT_CLOSURE --SDK-closure-sha256 ACTUAL_SHA
```

HeadOff 改 `--case head_off` 并提供它自己的实际SDK Root closure；position依次1..4，
每次等待上一成员终态/Root核验，不自动循环。Root CLI必须用真实完整单一路径参数。
预期归档前缀：`docs/model_v3/pre_registered_methods/performance_current_Av2_R1_ABBA_v1/`。
源码pins排除自身、publication在运行时读，避免SHA自引用或未来proof。

作者仅进行了源码和小metadata读取/文本制作，没有执行Python、AST、项目、模型、SDK、
SSH、Slurm、Git、测试或发布。仍需Root实际源码审核/AST/正常checker/精确发布、每次fresh
资源与最终四成员/SDK/报告闭合；本包不宣称新R1、auto、D5、模型或recipe采用。
