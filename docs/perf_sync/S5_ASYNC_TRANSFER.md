# S5：共享内存和异步传输

开关：`step_overhead.async_transfer=false`。读进程显式共享准备后的张量；主进程锁页，在独立CUDA stream上提前一批non_blocking拷贝；计算stream等待event，并为设备张量record_stream。锁页源保持到拷贝event完成，提前结束时也等待自己的stream，避免数据生命周期错误。批次/RNG状态仍来自原有有序预取器。

CPU单测覆盖共享张量、类型化PyG批次及映射不改源值；设备stream/event正确性仍需GPU A类对照。

5090/4090/3090均SKIPPED_NO_FREE_GPU，吞吐/倍率均null。1000批真实CPU采样/RNG及20批原有输入张量对照已通过；两组权重×20批GPU逐位梯度/损失未测，不宣称A类通过，**不判为有效，不建议开启**。不采用CPU共享内存单测替代这些GPU/真实输入验收。

补充CPU真实输入验收：4535482/node16/16CPU、14读进程、B32，使用PR8 input_equivalence完成1000批分子/构象与逐批RNG一致，前20批原模型输入及标签/mask/成对张量严格一致，PASS。未执行CUDA stream/event路径、两组权重×20批GPU损失/完整梯度或测速，完整A类仍未通过、仍不建议开启。SampleClock中的optimizer_updates=1000为采样批计数，此任务实际优化器更新为0。
