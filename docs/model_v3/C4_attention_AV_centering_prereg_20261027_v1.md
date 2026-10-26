# Attention AV 中心化：固定输入诊断预注册

2026-10-27，执行前提交。此为局部FP32表达式诊断，不实现生产候选，不宣称全模型通过。依据是已实际C0的1561：全encoder+三PD F64参考432观测均低于1e-5，但原FP32仍10PASS/38FAIL。不能凭末LayerNorm误差下降/上升指定单kernel原因。

## 完整人口与透明门

原48组合、两个seed、三C1、两views、四head/pooling保持。192次原完整前向必须在实际启用本次AV捕获hooks及局部TorchFunctionMode时，与1492的bank H0/pos/batch逐位一致；不是只先做unhooked前向。保留原func唯一一次调用与原返回对象，完整forward返回后才复制refs，finally恢复。原参数、typed bank state、完整views/geometry及来源保持。

全部192门通过后，科学人口为六层×四role×48=1152 AV。每项先按原dtype/strides/storage_offset/device/TF32/autocast重建view并重放原AV，要求全输出逐位相同，才能进行该项控制。GPU指针明确重新分配；layout恢复不冒充原pointer。任一位等或人口门失败整体FAILED，保留已做的partial，不丢case/层或自动重试。

## 唯一控制与不同参考

每个graph/head固定第一valid key的V为v0，每AV只做一次C32=v0+p32@(V32−v0)。实数Σp=1是前提；有效dropout非0、empty/allmasked图明确拒绝。原finite−1e9 mask不改，不能暗加safe softmax或epsilon。valid query×head×component为主统计分母，padded人口单独记录，不按结果筛选。

Rraw=p32.double()@V32.double()测实际存储operands的乘积；Rnorm=softmax(actual_masked_logits32.double())@V32.double()只提供同一存储logits的高精度归一化，不能当上游QK/logit已修正。独立Cexact64=v0_64+p32_64@(V32_64−v0_64)，核Cexact64−Rraw=(1−Σp32_64)*v0_64，浮点审计界为原代码128*eps64*scale（非物理1e-5）。不得定义出右式再当独立证据。

C32重新分配centered_v，可能改变layout/kernel与减法/回加舍入；这是一个完整表达式控制，不能把收益唯一归因共同分量消减。C32可能比Rraw更远、同时比Rnorm更近，二者不混称“更准确”。每项全部带符号比较固定在原original−Rnorm有效人口绝对argmax同分量，不能相加不同max。

## 汇总、停止与采用边界

全1152逐项保存maxabs/rms/分量数及描述性1e-5计数。总体按全部有效分量聚合Rnorm误差RMSE，逐AV报告C32与原表达式maxabs改善/相同/变差，并保留C1/views/seed/层全部分组，不选最佳anchor或子集。任何收益仅支持后续独立全网络FP32候选验证，不是C4、训练等价、NativeRuntimeDense、bf16或training-dropout通过；原FP32物理10/38不改。

同job tiny正负控制单列：两类成功forward/原重放/中心表达式；allmasked原forward返回后拒绝、有效dropout在prehook拒绝。192编码器、1152原重放/唯一C32及各1152个Rraw/Rnorm/Cexact调用分别计数；不重做192个F64 encoder。

只读1492原输入128MiB，CPU缓存payload上限2GiB不是落盘或RSS许可；不输出大operands/weights/NPZ。沿用c35/node21/fd9、16CPU32GiB、28GiB RSS、1100秒/20min、whole/private各2GiB，child保留96MiB监督预留且结果另限128MiB，不新增监控或调度器。预算、来源、重放或定义不符均如实失败。

源快照tools/model_v3/analysis_sources/attention_av_centering_v1，原manifest SHA256=1a41f552eb7e9078022578e4f5b1727480d94d2ce640b8e846533c1c689d5556。Root实际279原始refs/171Python AST/12bash语法通过，SA4独立静态复核未见公式阻断；tiny/192/1152均尚待实际执行。先普通仓库检查C0和本预注册公开，再提交GPU。