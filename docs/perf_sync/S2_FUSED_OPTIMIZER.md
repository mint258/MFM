# S2：融合优化器及裁剪

开关：`step_overhead.fused_optimizer=false`。打开时AdamW请求fused=True，构造器不支持时回退foreach=True；裁剪使用foreach=True。默认关闭时保持原AdamW及原裁剪选择，参数名/检查点格式不变。新CPU单测覆盖不支持fused时的回退及旧优化器状态加载；加载旧param_groups后重新应用已选执行后端，避免旧fused/foreach字段静默关闭开关，不改变检查点格式。

验收类别B。5090、4090、3090本次均无符合准入的空闲卡，均SKIPPED_NO_FREE_GPU，样本/秒及相对基线均null；未运行GPU噪声底、单步对照或1000更新短训练。未产生测速值，因此不触发“<3%补测”。**有效性未证实，不建议开启**。资源依据见S0_PROFILE.md。

2026-11-18 3090补充：两组权重各20批均通过B类单步门槛；1000更新无NaN/Inf，末200均损失0.4556789409对基线0.4524085382，差0.0032704027≤0.0235722561，B类短训练PASS。71.1502样本/秒（1.03687倍，+3.69%），313.52W；未达到单卡5%有效门槛，记无效。提速超过3%，不重复测速。此轮请求fused=True/foreach裁剪，没有运行异常；原始汇总见results/perf_sync/gpu_20261118/S2_benchmark.json和S2_numerical.json。
