# Streaming CPU v2：节点本地心跳

v1 MAD0实际job4520497因共享FS心跳5s新鲜度误停而FAILED1；四个CPU边界fixture已独立PASS。失败的一个闭合group和其它partial证据全部保留，不能供下游reducer或覆盖重用。此目录只为新控制实现提供独立入口，不改旧10+5文件或任何中央冻结文件。

五生产源取自实际Root的已验CPUv1：scan/compact/calibration原字节复制；reducer取已批准的`reduce_stage_v1.py`，保持显式7200资源守卫；support仅把中央import从`runtime`换成`runtime_v2`。每个函数源码字节/AST保持一致。数学、标签、阈值、dtype、mask和精确median/MAD完全没有重写。`source_mapping_v2.json`、`edits_v2.json`及标准库`verify_equivalence_v2.py`提供唯一import逆编辑整文件原字节和逐函数证明；不重复旧四fixture或19/24/13套。

中央runtime_v2/launch_v2由Root实现：1s监控/5s新鲜度、75%自身/85%节点等资源门保持；heartbeat/STOP/samples在节点本地/tmp用boot-monotonic时钟，child自然结束后监控闭合再稳定stat/完整SHA导出到原持久guard目录。source不会把共享FS异步可见性当作实时心跳。新的CPU父C0除原闭合身份门外，还必须有`durable_evidence_exported=true`、`heartbeat_clock=BOOT_MONOTONIC`及heartbeat/samples导出ref；metadata链不重读大的samples正文。没有强杀/timeout kill或自动重试。

Root整合、静态及等价证明后，初次MAD0命令：

```text
python -B <Root>/workflows/data_v1_final/labels/streaming_cpu_v2/verify_equivalence_v2.py --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sb3_stream_cpu_equivalence_v2.json
python -B <Root>/workflows/data_v1_final/labels/streaming_cpu_v2/materialize_next_v2.py --reduction /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/streaming_v1/reduce_med_r6_p32_v1/reduction.json --job 4520444 --node <Root选择CPU2或8-19>
```

materializer仍只做sacct/小metadata验证与调用`prepare_request_v2`，不Slurm。引导仅接受原r6/4520444 C0，并绑定原四fixture真实PASS文件作为独立历史证据；新命令直接执行一次CPUv2 source scan，不使用driver、不重跑测试。固定4251/512/16/146/14tasks、原roles、1%门、父C0/monitor/command身份门保留。后续Root每轮手动用`--scan`或`--reduction`闭合和准备，不自动跟链。命名与输出全为新的`*_cpu_v2`，包括`scan_mad_r0_cpu_v2`及新的closure/command/request；不碰v1旧文件。formal/full/finalD4仍未授权或完成。

所有新AST/中央v2边界/实际科学结果等待Root执行。创建时已核五源唯一逆编辑恢复原UTF8字节；不预填执行PASS。EA/size的19文件继续等待Root检查，不在本次变动范围。
