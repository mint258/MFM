# 全六层中心化attention：完整48组合GPU预注册

2026-10-27。当前为FINAL metadata已绑定、运行器与本协议待Root公开读回、科学GPU尚未提交/运行的状态。Root先完成普通仓库检查、精确提交、API公开和读回，再以原资源准入唯一提交；本文件不记录尚未发生的GPU结果。

## 唯一候选、源码与已有CPU证据

只评估一个全六层attention_aggregation_mode=centered_fp32_v1候选，其余encoder/head/distance/reducer沿用numeric_mode=compensated_fp32_v1。默认legacy路径和原参数/初始化/架构/512维H0/API保持各自原定义；本次显式选择全六层中心化，没有按层、case、head、seed或结果挑选，也没有不支持时退回legacy的路径。

执行工作树为MFM_model_v3_attention_centering_v1，独立实验分支[model-v3-attention-centering-20261027-v1](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)。已公开候选f8417157dc23326d1beca8e19e4725755d9f13c6对应本地cf8ce66d97cd518ebf279b40ee20294919bb95e1、同树2389ab046ee23f2ba92fcb61179d853dfdee8357；reporting树仅发布协议、证据与源快照，不是执行runtime。

普通检查1699及完整CPU父4521707已实际C0。1707为16CPU/132秒，实际2712采集=2709PASS+3项与1421同身份的可选SKIP；73项新测试和47项原numeric测试全部PASS/0skip。最终绑定实际消费完整114模块、四份JUnit、来源前后和独立raw sacct/supervisor，不将规划数当实测。完整证据见[CPU Root闭合](reports/attention_av_diagnostic_20261027_v1/CPU_ROOT_CLOSURE.json)、[原汇总](reports/attention_av_diagnostic_20261027_v1/CPU_FULL_SUMMARY.json)及[候选公开读回](reports/attention_av_diagnostic_20261027_v1/CANDIDATE_PUBLICATION.json)。

## 固定人口、参数与原门槛

全部48组合固定为C1-0/C1-a/C1-b × two/three两种视图数策略 × H1_fixed/H1_learned/H2_fixed/H3_fixed × seed20261026/20261027。最终request的48个ID及顺序必须与原1435固定fixture完全相等，不删失败人口或改seed。原始88/132 packed views、clean/noisy坐标、边和全部物理公式由冻结fixture复用，不重采样。

原fixture源码SHA为0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8。每个case构造的完整参数SHA必须等于4521492同seed捕获，参数不来自新初始化选择或新权重。原1492 CAPTURE_MANIFEST绑定为16202字节、SHA 670bf0a21b113d1b11bad4cb82e7e6a3995ac789524fb48b285e4ab33ef713a4；其原路径为/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_capture_GPU_v2_4521492/CAPTURE_MANIFEST.json。本任务不复制或公开NPZ/参数payload。

沿用原13个终端字段、3种变换与全部非零/原始不变量/domain/edge/正交R控制。绝对阈值1e-5、rtol=0原样使用，所有字段和变换均受门约束。每case的52个完整终端数组（原始输出+3变换）及完整measured JSON须先fsync持久化，再调用原assert_case_passed；结构异常另留case异常记录。全部case继续执行，无fail-fast，无事后层选择、阈值放宽、丢case或失败后自动重试。覆盖缺失只能报告partial/失败，不能将成功子集命名完整PASS。

固定科学encoder前向数为192，F64 encoder前向数为0。同GPU tiny控制单列，调用实际centered_attention_value，检查可精确表示输入、logits/V梯度及allmasked/empty/bf16/active-dropout拒绝边界；它们不代替48组合门，也不迁移有效dropout或NativeRuntimeDense/bf16生产路径。

## 先验证局部假设，再运行完整网络

原1641固定输入AV诊断保留全部1152项及负结果：相对Rnorm的聚合RMS约改善11.3%，第0层192/192局部项RMS更差，Rraw参照下总体也更差。Rnorm和Rraw含义分别是存储logits的高精度归一化参照和存储p/V乘积参照，不能混称准确率；这些局部观察不预言本次完整网络结果。[原分析](reports/attention_av_diagnostic_20261027_v1/ANALYSIS.md)和[全部标量](reports/attention_av_diagnostic_20261027_v1/SCALAR_SUMMARY.json)保留，原FP32的10PASS/38FAIL不改写。

本次仅为完整synthetic C4 gate。即使全部48通过，也不自动构成架构/训练/配方采用，不替代TRAIN内层dev panel、D5、真实标签/SDP验收、种子噪声或Native/bf16验收。所有原FAILED、partial、操作错误和新失败继续保留；无adoption，无最终recipe/B*或模型线交接。

## 最终机器绑定与执行来源

下列摘要从原S目录实际文件读取并逐字节复制，供执行和公开审阅使用：

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| [execution_request_v1.json](../../tools/model_v3/analysis_sources/attention_centered_e2e_v1/execution_request_v1.json) | 324104 | 1049ca8e8a56ad3f9ff7e0c5e214acb485b81a4f8efbc6c7bf6f3c601c7cceb0 |
| [source_pins_v1.json](../../tools/model_v3/analysis_sources/attention_centered_e2e_v1/source_pins_v1.json) | 321228 | 52d4ad7679a9d40807d8899371811381e93bec9041fd88cad042de61d99002df |
| [FINAL_BINDING_RESULT.json](../../tools/model_v3/analysis_sources/attention_centered_e2e_v1/FINAL_BINDING_RESULT.json) | 4386 | 668ceae97579423e9c356db7b025f783a6cac524cbac01aea77da4f5c7d8a210 |

当前绑定结果status为FINAL_METADATA_BOUND_PENDING_RUNNER_PREREGISTRATION_AND_GPU，已绑定actual CPU QA及候选public/local同树；没有reservation或GPU提交。草案和README保留原始准备阶段文字，当前执行只接受上述最终request/pins及其精确raw SHA。全部本层源、最终metadata、QA binding及历史draft见[原字节快照](../../tools/model_v3/analysis_sources/attention_centered_e2e_v1/README.md)；真实执行路径仍为远端runs/model_v3_20261026/attention_centered_e2e_v1_source，原件与旧manifests不改。

## 资源、停止和发布边界

固定节点compute-0-21、物理GPU UUID GPU-c35f2434-9137-9723-1af5-dc69b6295243（原c35），共享fd9锁；16CPU/32GiB、28GiB RSS、1100秒supervisor、20分钟SBATCH、whole/private各2GiB。沿用原quota和max(all-user declared,AllocMem)内存85%、实际MemAvailable与NVML准入/公共锁、身份/cleanup边界，不新增runtime、监控器、dispatcher或放宽guard。资源、来源或定义不符即实际失败并留证据。

Root已实际完成metadata-only启动audit，最终request的1213项runtime refs及15项自身源绑定通过，没有GPU计算或提交。Root先公开本运行器和本协议并读回，再通过原launcher完成现场资源准入和唯一提交。当前GPU48矩阵没有结果；发布/源绑定、实际提交、完整终态和科学门分别记录。

