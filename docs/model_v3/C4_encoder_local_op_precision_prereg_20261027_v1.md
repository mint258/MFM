# C4：当前编码器局部算子精度诊断预注册

本提交在实验执行前公开协议、完整源快照及审阅记录。诊断要回答：当前编码器的局部数值误差，如何在相同真实 FP32 输入的重放与独立 FP64 参考之间体现。它不自动选择新算子或批准候选。

此前当前候选的完整物理检查仍为 **21 PASS / 27 FAIL**，阈值维持 absolute 1e-5、rtol 0，C4 保持 HOLD。历史 H64 的纯 CPU 量化实验1917已实际完成，A/B/C三臂各432项均在阈值内；该有限历史结果不能替代当前候选的 CUDA 验收。完整结果见[1917报告](reports/H0_interface_quantization_20261027_v1/PROGRESS.md)。

## 固定配置和预先注册规则

候选固定为 local cf8ce66d97cd518ebf279b40ee20294919bb95e1、独立公开分支 f8417157dc23326d1beca8e19e4725755d9f13c6、tree 2389ab046ee23f2ba92fcb61179d853dfdee8357。全六层 centered_fp32_v1、原 COMPENSATED stack、48 case、两 seed、head policies、视图与变换均不变；H0签名、512维和FP32接口不变。预注册提交号为本文件及冻结源首次公开的提交，Root须完成精确tree读回后才可提交实验。

计划192次完整FP32 encoder forward、0次完整FP64 encoder forward；全部192个H0及2496个外部终端数组须与闭合1838结果逐位一致。完整forward期间仅保留引用，移除observer后，原模块用相同GPU输入对象、layout、mask和上下文重放；padding也纳入逐位控制。

六层norm、attention、FFN及实际距离模块统一覆盖，不选择层或case。计划5312次局部FP32重放、5312次独立FP64模块参考、4368项module-port/transform观察。FP64参考仅提升同一模块的实际FP32输入，不注入其他参考输出；数值算法也有变化，因此结论限定为precision + algorithm contrast。

记录同分量D32、Dref、D32-Dref及有符号closure。统计只取真实有效节点和原子对，保留各自分母；局部scope可能重叠，不能相加为全模型因果排名。数值不一致保留完整48项后HOLD/nonzero；输入、来源或资源损坏单列执行失败。禁止选seed/layer、放宽阈值、fallback或自动重试。

## 资源与执行条件

沿用 compute-0-21 / GPU-c35f2434-9137-9723-1af5-dc69b6295243及公共物理UUID锁，16CPU / 32GiB，RSS 28GiB，监督1100秒、Slurm20分钟，whole/private各2GiB，读取输入和新artifact各128MiB。提交时仍须现场核验CPU、全用户内存、MemAvailable、quota和foreign GPU进程。源码审阅与输入stat符合上限不能代替实际资源准入。

## 结果、决策与限制

| 项目 | 当前状态 |
| --- | --- |
| 新GPU诊断及5312/4368覆盖 | 未执行，不能填PASS |
| 原物理验收 | 21 PASS / 27 FAIL，HOLD |
| 新算法或候选采用 | 无 |
| 仓库检查与公开读回 | 执行前由Root核验实际记录 |
| 最终训练配方、B*、tag与交接 | 尚未冻结 |

源快照位于[analysis_sources](../../tools/model_v3/analysis_sources/encoder_local_op_precision_v1/)。[原始最终协议](reports/encoder_local_op_precision_prereg_20261027_v1/FINAL_PREREG_SOURCE_v2.md)完整保留固定分母、失败规则和资源限制；[复制清单](reports/encoder_local_op_precision_prereg_20261027_v1/SOURCE_COPY_PLAN.json)绑定原件字节。Root静态、装配、源码审计、SA4审阅及v21/v23点时成本原件均在[证据目录](reports/encoder_local_op_precision_prereg_20261027_v1/)。历史DRAFT字段保留其生成时间含义，后续实际证明另列，未将它们改写成运行成功。
