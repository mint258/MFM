# S3：SDPA注意力

开关：`step_overhead.sdpa=false`。仅打开时替换attention.py及v3_latent.py的手写注意力，保留原距离加性偏置、padding及radius mask数值、dropout概率；不强迫不支持加性偏置的后端。两种实际模块均改动，默认关闭保持原公式及返回值。

CPU单测覆盖有/无radius、不同长度padding、距离偏置的前反向及PMA交叉注意力。真实CUDA所用后端必须由运行trace记录；本次未运行GPU，后端为null，不能从CPU测试推断使用了flash/efficient。

验收B；5090/4090/3090均SKIPPED_NO_FREE_GPU，吞吐/倍数/噪声底/单步门槛/1000步质量均未测，**不判为有效、不建议开启**。现场依据见S0_PROFILE.md。

2026-11-18 GPU补充：已实际观测aten::_scaled_dot_product_efficient_attention及其backward（memory-efficient后端）。随机/B3 3M各20批已完成，B3若干批的完整梯度相对L2差超过10×epsilon_grad=1.15446e-5（例第17批0.00287919），B类单步门槛FAIL；不放宽阈值。原始逐字段CSV留scratch，汇总见S3_numerical.json。按任务书继续完成1000更新质量和测速；当前不建议开启。

1000更新测速完成：71.2058样本/秒，1.03768倍（+3.77%），314.71W；末200均损失0.4387715039，对基线差0.0136370343≤0.0235722561，短训练PASS。但单步B类FAIL且提速不足5%，最终无效、不建议开启；提速超过3%不重复测速。
