# S2：融合优化器及裁剪

开关：`step_overhead.fused_optimizer=false`。打开时AdamW请求fused=True，构造器不支持时回退foreach=True；裁剪使用foreach=True。默认关闭时保持原AdamW及原裁剪选择，参数名/检查点格式不变。新CPU单测覆盖不支持fused时的回退及旧优化器状态加载。

验收类别B。5090、4090、3090本次均无符合准入的空闲卡，均SKIPPED_NO_FREE_GPU，样本/秒及相对基线均null；未运行GPU噪声底、单步对照或1000更新短训练。未产生测速值，因此不触发“<3%补测”。**有效性未证实，不建议开启**。资源依据见S0_PROFILE.md。
