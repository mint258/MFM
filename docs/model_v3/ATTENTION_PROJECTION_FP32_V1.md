# 固定 K64 / row128 的全 FP32 attention 投影候选 v1

**源码候选，尚未执行新CPU/GPU QA，也未采用。** base为cf8 centered-FP32实验分支，不是Core64或正式runtime。Core64实际4524448保留14P/34F，原FP32保留21P/27F；本候选不改变这些历史结果，不把局部误差大小当作因果排名或宣称一定全通过。

## 唯一方法和范围

显式 backbone.attention_projection_mode='blocked_k64_compensated_fp32_v1'；缺省/legacy直接执行原Linear。仅允许原六层512维/8heads、compensated_fp32_v1、centered_fp32_v1、零dropout配置。全部六层的QKV与out projection统一启用，共12处，C1-0/a/b同规则。heads、norm、FFN、distance/RBF/bias、QK、softmax、centered-AV、物理域与H0定义不改。

真实函数仍为 Y=XW^T+b。K固定64，512输入共8块；dense行tile固定128，先按原B×N含padding的行序计算。每块调用FP32 linear(...,bias=None)，8个部分和按固定平衡树使用原Neumaier high/low规则合并，再加入一次原bias并输出FP32。无K/rowtile扫描，没有逐层/seed选择、权重重调、输出缩幅、FP64、BF16、AMP或TF32。该算法不宣称叶GEMM精确、正确舍入或全域误差上界。

128×1536×8个FP32部分和单份约6MiB；high/low、栈与树中间量还需另计。不会构造native_atoms×512×1536矩阵，结果直接写回原行序。投影由一次GEMM变成8次并增加归约/launch；真实容量、吞吐、训练驻留与85%须后续实测，不由源码估计授予。

## 可训练的明确反向

custom autograd的依据是同一真实仿射函数，不是对IEEE舍入的逐指令求导。对于上游G：

- dX = G W；
- dW = G^T X（将所有leading dense rows展平）；
- db = sum_rows G。

这些反向全部FP32，保留saved input/weight和grad_output的可微连接，支持完整二阶交叉导数，不detach输入/参数、不把梯度置零，也不以eval-only绕过训练。FP32 GEMM反向仍有其自身舍入，不能称bit-exact real derivative；CPU独立解析oracle用于验证公式/高阶接线。

## 状态、支持与拒绝

无新Parameter/buffer/initializer/RNG抽样，保留原qkv.weight/qkv.bias/proj.weight/proj.bias及全部state keys。config_dict完整backbone_config和numeric_checkpoint_contract绑定新mode；SharedPair extra_state仅opt-in增加mode。只含裸tensor、不带配置的C1-0 state不能宣称已恢复该方法。

模型入口核声明与实际backbone/all12 mode/原attention与Linear类/shape一致；替换、丢mode或非零dropout拒绝。每个新投影前后向要求输入/权重/bias/梯度已为FP32、autocast关闭、highest且两TF32关闭；混合/无法读取的precision-control API状态也typed拒绝，不静默修全局状态。模型是正常可训练模式，不限制eval。

原Native/performance路径没有此实现，沿既有centered runtime拒绝门明确报错；不能仅记录配置而实际替换为旧RuntimeDense/bf16。原默认不进入新helper，不改变其backend、参数或数据行序。

## 计划测试与未来物理门

新模块目前44项计划，未collect/运行。小oracle覆盖跨block 2^24+1−2^24、bias一次、257行跨tile/置乱/非连续、空行、dtype/AMP/TF32/API拒绝。input/weight/bias一阶梯度用独立实数公式；完整二阶方向对 F=.5||XW^T+b||² 使用 d²F=||UW^T+XV^T+c||²+2<Y,UV^T>，覆盖三变量与交叉项。高精度仅用于这些小CPU oracle，模型路径不转F64。

真实6×512的C1-0/a/b工程forward/backward检查12个投影均有有限非零weight gradient、坐标梯度连接和RNG不变；并核初始参数/state/buffer、checkpoint identity、未实现组合、原legacy直接Linear位等。测试不能替代完整组合C4或真实性能。

Root正常checker/相关与full CPU、源码与方法精确公开后才可实际GPU。必须仍是原48组合、两固定seed、全部C1×views×heads、192原前向、13字段×3变换、52输出、原权重/fixture/域/硬边界/非零、原物理单位abs≤1e-5且rtol0；失败全保留，不failfast，不改阈值或挑案例。原单卡UUID/公共锁、16CPU32GiB/RSS28GiB/1100s/85%/whole与private各2GiB不放宽。超时/OOM也保留，不科学降batch。

即使C4全过，原20+500数值与性能、D/P面板、真实D3/D5/D6及指南其他条件仍独立待验；不直接冻结模型。本文没有运行或批准任何实验。
