# EA 与 size 的独立 CPU 小试点绑定

原 `ea_diagnostic_v1`、`size_semantics_v1`、`normalization_v1`、`streaming_v1` 及原配置全部不改。新 `ea_cpu_v1/bounded_probe.py` 从实际Root旧入口复制，只加 `checkpoint`/`checkpoint_iter`；新 `size_cpu_v1` 复制7个生产模块，另复制所需normalization runtime/reader至自己的`_normalization/`，仅改变这些模块的支持路径和检查点。size的原guard函数逐字节未改，request和实际allocation仍必须至少64GiB，不从32GiB streaming/EA适配继承降配。

两套新入口依赖 `streaming_cpu_v1/support.py` 的中央guard转发和before-next迭代检查点。它们检查source batch、owner/mask读取、group提交和新阶段；EA也在SHA读块、latest批读、归档主键调用和实际raw读取前检查。没有信号或杀进程逻辑。原数据读取顺序、输出值/掩码、数值处理和所有科学阈值保持。

新配置模板 `configs/data_v1/labels/ea_cpu_v1.template.json` 只替换support_source为新CPU support ref；`size_cpu_v1.template.json`只替换scan_adapter为CPU scan ref。原metadata_sources、plan/mask/registry/lineage等ref逐项保留，不改旧配置内的actual pins。模板尚非已冻结实际request；Root统一builder须读回实际Root源码，重绑定新的配置自身、CPU support/scan、中央runtime/policy/launcher/submitter和decision/scope policy等ref，再生成新且不存在的output/intent。不能把child同SHA路径当作Root的实际观测。必须用`PYTHONPATH=repository:deps`，让完整包路径的CPU support可导入。

Root统一维护 `scope_key`、`decision_reference`、`scope_policy_reference`、`scope_parameters`、`base_request_reference`，`pilot=true`、`formal_generation_authorized=false`、`resource_policy=CPU_BOUNDED_TEST_LIVE_MEMORY_V1`。CPU分区只选授权2及8–19；不使用21。EA仍7既有RID/6文件/3归档、16CPU32GiB1h64MiB；size仍4251records/512molecules/16groups、16CPU64GiB2h8GiB。只能由Root中央launcher建立同allocation heartbeat/STOP，不能直接绕过launcher启动。formal/full继续原正式资源和普通声明85%准入；新CPU小试点不形成full授权。

每套 `source_mapping_v1.json` 列原Root SHA、child准备字节SHA、拟Root路径；`edits_v1.json`逐项列出唯一允许的源码改变。创建时已实际核逆编辑恢复原UTF8整文件字节。Root整合后可用标准库独立核验：

```text
python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v1/verify_bindings.py --variant-dir <Root>/workflows/data_v1_final/labels/ea_cpu_v1 --output <新ea_proof.json>
python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v1/verify_bindings.py --variant-dir <Root>/workflows/data_v1_final/labels/size_cpu_v1 --output <新size_proof.json>
```

验证器只读源码/小JSON，不导入科学模块。它分别验证唯一正向替换、逆编辑整文件原字节、仅复原已声明支持路径并移除checkpoint后的全模块/逐函数AST，报告每个函数真实byte-equal标志；额外强制size guard原字节相同。新数值算法没有重写，故不重复旧19/24/13套；CPU控制边界由streaming_cpu_v1的四个新fixture覆盖。所有AST、fixture和实际科学结果等待Root执行，不预填PASS。
