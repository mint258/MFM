# S4：torch.compile

开关：`step_overhead.compile=none|encoder|encoder_heads`，默认none。按层调用Module.compile(dynamic=True)，encoder_heads同时原位编译预测头，避免包装Module导致state_dict参数名前缀变化。默认恢复none清除编译调用，旧checkpoint键名及参数共享身份保持。若实际1000步重编译超过20次，唯一一次后续尝试可启用compile_mark_dynamic在编译层外标记原子维；不得无限重试。

编译兼容性CPU单测已独立通过（1 passed；eager编译后端，只验证状态字典/参数别名/动态输入，不作为速度或GPU等价性结论）。

本次5090/4090/3090均SKIPPED_NO_FREE_GPU，实际CUDA编译耗时、1000步重编译数、吞吐和倍率均null；encoder及encoder_heads的B类GPU验收均未执行。**不判为有效，不建议开启**。见S0_PROFILE.md。

2026-11-18 编译基础设施恢复：node5驱动520.61.05（CUDA11.8），Torch2.7.1+cu118/Triton3.3.1默认ptxas12.4首次生成的kernel报device kernel image is invalid。仅本线子进程改用现有/usr/local/cuda-11.8/bin/ptxas，使用inductor_cuda118_v2/triton_cuda118_v2独立缓存，原错误日志与缓存保留；没有更换驱动或包、没有修改其他任务环境，没有打开TF32。原4535718预约/UUID锁保持，resume_suite_1只续跑未完成S4/S5；已观测恢复后的S4_encoder前几批实际GPU前反向运行并通过B类门槛，完整验收仍在进行。

恢复后encoder模式已完成两组权重各20批单步验收：随机组通过B门槛，B3组梯度相对L2差超标（最大0.00643813，对比门槛1.15446e-5），该模式B单步FAIL。1000更新测速继续；encoder_heads尚待执行，不用随机组通过代替B3组验收。

encoder模式1000更新已完成：71.0852样本/秒（1.03592倍，+3.59%），309.96W；末200均损失0.4694998796，短训练PASS。计时1000更新内实际重编译8次（排除预热，以Torch CompileId去重计数），编译器16条时间记录和完整时间表见S4_encoder_benchmark.json。部分distance-tiling形状命中Torch自身recompile_limit=8而回退eager，此行为如实计入测速；总重编译未超过任务书20次门槛，不额外启动mark_dynamic重试。B3单步验收FAIL且提速<5%，本模式无效、不建议开启。encoder_heads仍在运行。
