# S3：SDPA注意力

开关：`step_overhead.sdpa=false`。仅打开时替换attention.py及v3_latent.py的手写注意力，保留原距离加性偏置、padding及radius mask数值、dropout概率；不强迫不支持加性偏置的后端。两种实际模块均改动，默认关闭保持原公式及返回值。

CPU单测覆盖有/无radius、不同长度padding、距离偏置的前反向及PMA交叉注意力。真实CUDA所用后端必须由运行trace记录；本次未运行GPU，后端为null，不能从CPU测试推断使用了flash/efficient。

验收B；5090/4090/3090均SKIPPED_NO_FREE_GPU，吞吐/倍数/噪声底/单步门槛/1000步质量均未测，**不判为有效、不建议开启**。现场依据见S0_PROFILE.md。
