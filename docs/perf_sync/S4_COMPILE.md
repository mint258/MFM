# S4：3090 torch.compile 实测（2026-11-18）

开关step_overhead.compile=none|encoder|encoder_heads，默认none。逐层Module.compile(dynamic=True)，encoder_heads同时编译预测头；保留state_dict键名与共享参数身份。CPU新逻辑兼容单测通过，GPU结论如下。

|3090模式|样本/秒|相对M2|主进程CPU%|整卡W|CUDA分配峰值GB|计时内重编译|
|---|---:|---:|---:|---:|---:|---:|
|encoder|71.0852|1.03592×|100.86|309.96|7.8235|8|
|encoder_heads|79.9832|1.16559×|100.62|317.88|7.4630|17|

5090、4090可选补测未执行。固定同卡M2/B32/FP32/TF32关闭/14读进程。每模式100次无优化更新预热后计时1000实际更新，完整指标、编译时间表与CompileId见对应S4_*_benchmark.json。

**两种模式均无效，保持none。** 两组权重各20批B类：随机组通过，B3组完整梯度超出10ε_grad=1.15446e-5；encoder最大相对L2为0.00643813。encoder短训练末200均损失0.4694998796，差0.0170913415，PASS；encoder_heads为0.4235410847，绝对差0.0288674535>0.0235722561，FAIL。所有训练有限。损失变低同样必须满足绝对差门槛，不放宽验收。

重编译按实际Torch CompileId.frame_compile_id>0去重，排除预热，不能把guard失败条数当重编译。8/17均未超过20，不触发mark_dynamic再试。部分distance-tiling形状命中Torch自身recompile_limit=8并回退eager，计时如实包含。原生编译记录分别16/62条；包括预热和命中缓存的整个frame编译时间总和11.273286/33.083706秒，inductor合计1.333614/4.496836秒。数值验收已预热编译缓存，不能称为冷启动编译成本。提速均超过3%，不补测。

基础设施记录：Torch2.7.1+cu118、Triton3.3.1、node5驱动520.61.05、SM8.6。默认ptxas12.4产物首次报invalid kernel image；仅本线进程改用现有/usr/local/cuda-11.8/bin/ptxas和独立inductor_cuda118_v2/triton_cuda118_v2缓存后成功执行。旧缓存/错误日志保留，未更改驱动、包或其他任务环境，TF32仍关闭。随后磁盘监控遭临时目录删除竞争而误退出，保留4535718失败记录，修复仅此监控并以4535744同UUID续接未完成部分，没有重跑已完成项目。
