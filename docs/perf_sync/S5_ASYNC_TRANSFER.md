# S5：共享内存和异步传输

开关：`step_overhead.async_transfer=false`。读进程显式共享准备后的张量；主进程锁页，在独立CUDA stream上提前一批non_blocking拷贝；计算stream等待event，并为设备张量record_stream。锁页源保持到拷贝event完成，提前结束时也等待自己的stream，避免数据生命周期错误。批次/RNG状态仍来自原有有序预取器。

CPU单测覆盖共享张量、类型化PyG批次及映射不改源值；设备stream/event正确性仍需GPU A类对照。

5090/4090/3090均SKIPPED_NO_FREE_GPU，吞吐/倍率均null。两组权重×20批逐位梯度/损失及1000批真实采样/RNG对照未取得，不宣称A类通过，**不判为有效，不建议开启**。不采用CPU共享内存单测替代这些GPU/真实输入验收。
