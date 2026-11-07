# Streaming CPU 小试点适配

五份源从实际Root `labels/streaming_v1/` 复制：`scan_v2.py`、`reduce.py`、`compact.py`、`calibration.py`、`support.py`。原件和原配置不改。`compact.py`、`calibration.py`整文件原字节相同；另三份只包含 `edits_v1.json` 逐项列明的控制改动。创建时已核五份逆编辑恢复原UTF8字节；AST证明和四个新boundary fixtures等待Root实际运行。

`support.root_guard(path,pinned_path,cap,wall_limit=3600)`原签名原样转发中央 `workflows.data_v1_final.execution.cpu_analysis_v1.runtime.root_guard`，没有本地后备放行逻辑。中央runtime尚由Root负责实现/绑定。`checkpoint`通过`DATA_V1_CPU_INTENT`和`DATA_V1_CPU_GUARD_DIR`关联同allocation，spawn worker不依赖父进程Python全局状态。

`checkpoint_iter`在每次`next(iterator)`之前检查STOP，避免在for-body检查前已经读入下一源batch。scan在worker初始化、owner读、source文件/批读、group开始与父进程提交每group前检查；reduce在owner批读、DuckDB批读与新SQL/归并阶段前检查。STOP只抛出异常，沿既有失败/保留partial证据路径返回；不杀进程。数学、掩码、单位、阈值、float64、精确radix/MAD和原NULL/z review口径不变。

本变体只供Root授权的既有4251record/512molecule小试点：request `scope_key=label_canonical_512`、`pilot=true`、`resource_policy=CPU_BOUNDED_TEST_LIVE_MEMORY_V1`，cpu分区已授权节点2及8–19，16CPU/32GiB。实际节点/内存监控/launcher/submitter由Root集中选择、绑定；21未授权。此目录不创建Slurm请求或分配资源，不能把小试点策略用于formal/full；生产资源要求与普通85%准入不变。

继续median/MAD/refine/mask可沿原CLI和原固定plan/config/query引用，改用新目录的scan/reduce入口，并以Root新中央launcher启动，`PYTHONPATH=repository:deps`。原plan内legacy adapter pins仍指Root原四个解码/掩码源码；其科学语义未改。新request另需逐个绑定新五源码、manifest/edits及中央runtime/launcher的真实Root SHA，不把child同SHA路径冒称Root观测。

Root整合后，独立静态源码证明入口：

```text
python -B <Root>/workflows/data_v1_final/labels/streaming_cpu_v1/verify_equivalence.py --output <新control/proof.json>
python -B <Root>/workflows/data_v1_final/labels/streaming_cpu_v1/test_boundary.py --output <新control/boundary.json>
```

证明核实际旧Root source SHA及新文件SHA，严格按edit清单正向重建、逆向恢复整文件原字节，再逐函数报告原字节是否相同，并仅去掉明确的checkpoint语句/迭代包装、恢复已声明guard函数后比较全模块和所有非guard函数AST。加入checkpoint的函数不会被误报为未编辑原字节；逆编辑字节和去控制AST分别呈现。验证器只解析源码，不导入科学模块或读数据。四个fixture仅检验中央签名转发、STOP前不推进迭代器、对象/顺序不变及五文件等价，不重复旧19/24/13套科学测试。实际PASS、节点资源和新科学结果均待Root闭合。
