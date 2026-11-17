# S5：共享内存和异步传输

开关：`step_overhead.async_transfer=false`。读进程显式共享准备后的张量；主进程锁页，在独立CUDA stream上提前一批non_blocking拷贝；计算stream等待event，并为设备张量record_stream。锁页源保持到拷贝event完成，提前结束时也等待自己的stream，避免数据生命周期错误。批次/RNG状态仍来自原有有序预取器。

CPU单测覆盖共享张量、类型化PyG批次及映射不改源值；设备stream/event正确性仍需GPU A类对照。

5090/4090/3090均SKIPPED_NO_FREE_GPU，吞吐/倍率均null。1000批真实CPU采样/RNG及20批原有输入张量对照已通过；两组权重×20批GPU逐位梯度/损失未测，不宣称A类通过，**不判为有效，不建议开启**。不采用CPU共享内存单测替代这些GPU/真实输入验收。

补充CPU真实输入验收：4535482/node16/16CPU、14读进程、B32，使用PR8 input_equivalence完成1000批分子/构象与逐批RNG一致，前20批原模型输入及标签/mask/成对张量严格一致，PASS。未执行CUDA stream/event路径、两组权重×20批GPU损失/完整梯度或测速，完整A类仍未通过、仍不建议开启。SampleClock中的optimizer_updates=1000为采样批计数，此任务实际优化器更新为0。

2026-11-18 GPU补充：同一3090，两组权重各20批已运行实际共享/锁页/独立stream/event传输；未达到A类逐位一致，按规则转B类，40/40单步门槛通过。既有1000批CPU采样/RNG验收复用。1000次真实更新质量及吞吐仍在运行，未判为有效。

1000更新完成：71.2032样本/秒（1.03764倍，+3.76%），312.63W；末200均损失0.4367126504，差0.0156958878≤0.0235722561，无NaN/Inf，B类短训练PASS。单步及既有1000批采样/RNG均通过；未达单卡5%提速门槛，记无效。已超过3%，不追加测速。见S5_benchmark.json和assessments.json。
