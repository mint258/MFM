# S4：torch.compile

开关：`step_overhead.compile=none|encoder|encoder_heads`，默认none。按层调用Module.compile(dynamic=True)，encoder_heads同时原位编译预测头，避免包装Module导致state_dict参数名前缀变化。默认恢复none清除编译调用，旧checkpoint键名及参数共享身份保持。若实际1000步重编译超过20次，唯一一次后续尝试可启用compile_mark_dynamic在编译层外标记原子维；不得无限重试。

编译兼容性CPU单测已独立通过（1 passed；eager编译后端，只验证状态字典/参数别名/动态输入，不作为速度或GPU等价性结论）。

本次5090/4090/3090均SKIPPED_NO_FREE_GPU，实际CUDA编译耗时、1000步重编译数、吞吐和倍率均null；encoder及encoder_heads的B类GPU验收均未执行。**不判为有效，不建议开启**。见S0_PROFILE.md。
