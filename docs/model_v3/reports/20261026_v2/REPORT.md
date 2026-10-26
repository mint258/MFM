# 模型 v3 进度：075回归闭合，最新Native整合回归待完成

本轮已闭合缓存、proxy runner、WSD fork 和长期存储工具的 CPU 集成回归；Native-S 接线完成候选级检查；A06 的真实诊断及独立原生 SDK 核验已完成。最终 D 权威交付、20k 精度曲线和等变性验收仍未闭合。当前继续推进整份工作指南，尚不具备最终训练配方或正式预训练放行条件。

本报告是2026-10-26证据快照。候选提交、Root最新整合提交和已有完整回归的执行代码分别记录，不能互相替代。Root最新Native整合提交为`3d9b1cc0c580dacc9398a5570b0c2fff3e257618`，tree`73a9e47af34aa6e46c2b421c946b1dc39209a584`，完整新Root回归仍为PENDING。

| 工作 | 已有权威证据 | 结果与适用范围 |
|---|---|---|
| Root 工程集成 | `075123e2fa2c511bf074a31f42df272d692e5356`；8个实际父作业 | 2566 collected：2564通过、2个CUDA依赖测试跳过，0失败/错误。覆盖缓存、proxy、WSD及long-run storage的CPU回归；没有据此宣布真实D3、GPU容量或长期科学实验验收。 |
| Native-S 候选及Root整合 | 候选`0d395b665a4136e39ea70f9d852f5585dcae2180`；1103/1104/1119；Root最新`3d9b1cc…` | 核心/CLI25通过；真实reader1通过；source checker通过。Root已提交整合12文件并逐字节匹配候选；最新整合代码的完整回归仍待闭合，尚无GPU/20k结果。候选SHA不是Root执行码，075历史回归不覆盖这次新增整合。 |
| A06真实诊断 | 4521091，实际C0/106秒 | 15updates、5120base；全部15点精确重放原457的输入和标量。原门槛首次在14失败，15继续失败，`FAILED_UNCHANGED`。 |
| A06独立SDK | 4521123，Root观测实际C0/1秒 | 原生SDK74条records、17条history、step0–16、cleanEOF及exit0；完整公开config、summary及所有history字段逐项精确一致。未在线同步、未修改SDK。 |
| C4等变性归因 | 实际执行4521049、报告4521066 | 7变体×48case，336case及13,104项观测完整；所有变体均0/48整例达到原组合门槛。绝对容差保持1e-5、相对容差0；没有模型采用或FP32验收。 |

完整工程计数见[集成汇总](data/integration_075.public.json)，Native的提交和检查范围见[候选汇总](data/native_candidate.public.json)。

缓存/训练接线的目的，是让样本消费、恢复、稳定点分叉、不可变checkpoint待评估事件和显式长期quota准入具备可追踪的工程实现。CPU回归证明本次测试范围内的契约和恢复行为；真实D人口、最终完整头部checkpoint成本、GPU/SDK/panel成本及长期曲线仍须实际测量。没有用工程fixture代替数据权威、配置注册或科学实验。

## A06：证据更完整，原失败结论不变

A06诊断的reference/free路径真实运行；optimizer-only shadow直接使用同一份真实clipped reference梯度值/None并独立更新参数及moment。shadow没有model forward，保存的before/after/reference梯度摘要一致。它提供优化器演化与反馈路径的诊断证据，不构成可相加的因果百分比。

原始指标为 `abs(free-reference)/max(abs(reference),1e-12)`，容差0.001。下表包含全部15点，不只展示门槛附近的点。该曲线是单seed、15步仪器化诊断，不是20k精度曲线或独立速度计时。

| Update | 已消费base | 原相对loss差 | 原点门槛 |
|---:|---:|---:|:---:|
|1|512|0.0|通过|
|2|1024|0.0|通过|
|3|1536|2.323983274999669e-6|通过|
|4|2006|1.8428514563440775e-6|通过|
|5|2433|1.2955832456655337e-6|通过|
|6|2815|7.239414558197231e-6|通过|
|7|3110|1.5557456734388708e-6|通过|
|8|3405|4.5952796106196385e-7|通过|
|9|3621|2.798167480117271e-7|通过|
|10|3831|1.5201091194617198e-5|通过|
|11|3976|3.6290002904440916e-5|通过|
|12|4066|0.00041159207685252056|通过|
|13|4096|0.0003384982106606295|通过|
|14|4608|0.0029128788627426007|失败|
|15|5120|0.003909828508023756|失败|

[公开聚合JSON](data/a06_diagnostic.public.json)保留原loss、相对差和消费计数；[完整诊断报告](A06_DIAGNOSTIC_REPORT.md)保留所有固定logger的聚合比较字段及gradient norm。[typed CSV](../../results/A06_native_feedback_4521091.csv)保持`NOT_ACCEPTED`，以免把运行/日志成功写成模型验收通过。

首次独立核验4521122在SDK解码前拒绝了65字符的手抄输入SHA。4521123改用机器绑定后通过；原拒绝记录保留为来源校验的基础设施负例，不计作一次模型数值失败。SDK的record数与history数分别统计，没有使用packetcount等于historycount的假设。

## C4：保留原分母和1e-5门槛

每个variant有48case；每case组合13个terminal与3类transform，形成1872项观测。7个variant共13,104项。`0/48`表示没有整例同时满足全部组合门槛，不能解释成13,104项观测全部失败。

以下是原重放中发生超阈值的3个terminal，以及两种归因参考的实际统计。每格分母是该terminal的144项观测，max error使用该terminal原输出单位，不混作坐标RMSE或跨terminal物理量比较。完整13字段×7变体汇总见[安全聚合JSON](data/c4_equivariance.public.json)。

| 变体/terminal | 超阈值观测/144 | 最大绝对误差 |
|---|---:|---:|
|original / PD/p_dipole|82|5.14984130859375e-5|
|original / PD/p_dipole_magnitude|50|3.0875205993652344e-5|
|original / PD/p_extensive|20|2.288818359375e-5|
|charge_center_only / PD/p_dipole|54|4.7534704208374023e-5|
|charge_center_only / PD/p_dipole_magnitude|52|2.0593404769897461e-5|
|pool_fp64_reference_only / PD/p_extensive|14|1.52587890625e-5|

`cdist_direct_only`没有改变这批观测数值；charge-center对不同terminal的影响并不一致；FP64 pooling仅为reference诊断。七个变体均未通过48case组合门槛，没有放宽阈值，也没有据此采用poolFP64或宣布等变问题已修复。新layer/head的CPU单测范围与这批原诊断结果分别记录。

| 图中标记 | 实际variant名称 | 整例组合通过 |
|---|---|---:|
|V0|original_formula_replay|0/48|
|V1|cdist_direct_only|0/48|
|V2|charge_center_only|0/48|
|V3|pool_fp64_reference_only|0/48|
|V4|cdist_direct_and_charge_center|0/48|
|V5|cdist_direct_and_pool_fp64_reference|0/48|
|V6|charge_center_and_pool_fp64_reference|0/48|

## 组件通过与父级闭合分别记录

4521126中，Native storage39、C4 layer/head24、A01 ABBA52三个组件测试均通过、源SHA前后一致；该父级仍为FAILED。失败来自GPU-runtime测试fixture中的Root-C0 frame SHA文本长度错误。生产helper/template保持原字节，测试修订改用冻结manifest中的机器值。Root将以新的C0父级重跑并建立准入证据；当前不把1126组件通过写成父级C0。逐组件计数见[范围汇总](data/unit_components_1126.public.json)。

A01的原4520456实际硬件为4090，已有20batch/500update数值资格。新的standalone ABBA仅完成工具/协议准备和上述52组件测试；四个顺序计时成员尚未运行，不填速度数值。其窗口保持2warmup+20测量，原500步仅用于numeric资格。

## 来源绑定与下一步

执行与发布采用不同标识：Root已有完整回归的执行码`075123e…`、最新Native整合码`3d9b1cc…`（新full回归待运行）、A06模型执行码`8ece64c…`、诊断源公开注册`f69bea231f4d7004c519f0514c85be43c138e504`、Native候选码`0d395b…`分别记录。已有Root注册回执将local`2c1d5e78c82c63db205d4006bd0b3ce0d168a7a9`与public`f69bea…`绑定到同tree`5db4896539f1f1efe414f6e868226633b3847229`。

原等变实现的标识是**源码文件raw SHA256** `0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8`，不是Git commit。其公开路径、快照commit及本次报告发布SHA由Root的[机器映射](data/public_source_mapping.root.json)补齐后提供，不能从短SHA或不同作用域的提交推断相等。

后续继续关闭最新Native整合代码的完整回归、immutable runtime和实际profile证据，执行必要的GPU/20k实验，处理最终D权威交付和等变性设计。Stage5/6科学矩阵、两seed统计与Stage7用户确认/最终tag或PR仍未完成。本文未读取最终下游测试标签，不据此启动正式预训练，也不将本次发布视为整份指南完成。
