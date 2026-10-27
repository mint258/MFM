# 当前centered候选固定H0诊断：执行前预注册

2026-10-27。本次只测量当前候选，模型、参数、默认值和门槛不变。上一轮完整GPU1776的21PASS/27FAIL及全部退化保留，C4仍HOLD、无adoption；其结果和不确定性已在[v13报告](https://github.com/mint258/MFM/commit/8949d7cb4344e0f8270793ae1967df08b56bf669)公开。当前新诊断已完成最终metadata组装和源码审阅，没有新GPU/CPU测量、作业或QA结果。Root先公开本协议及源快照、读回精确证明，再唯一提交。

## 固定候选与新鲜来源

执行仍为独立候选MFM_model_v3_attention_centering_v1，本地cf8ce66d97cd518ebf279b40ee20294919bb95e1、公开f8417157dc23326d1beca8e19e4725755d9f13c6、同树2389ab046ee23f2ba92fcb61179d853dfdee8357。全六层centered_fp32_v1与原compensated_fp32_v1组合不改，不扩展到NativeRuntimeDense、bf16或有效dropout。已有1707完整CPU回归仍为原候选证据，不为本次薄诊断另造suite或QA父。

原48组合、两种two/three视图数策略、四head policy、两seed及C1-0/a/b人口全部保持。每case完整命名参数SHA须与原1492同seed捕获相等；原fixture源码、原视图/几何/物理变换/registry不变。只新增fresh_centered_capture_not_1776_hidden_H0谱系：1776的52数组NPZ只有终端输出，没有bank内部H0。原1492/1503 H0也不能替代当前centered内部量。

## GPU捕获及不可跳过的对照

固定48×4=192次完整FP32 encoder前向，0次F64 encoder。clean bank H0为44×512，packed返回88×512或132×512。原hook只保留Python引用并返回None；原完整forward返回后，才复制同一次前向的bank H0、pos/batch与原始typed bankstate。hook和临时构造器/forward覆盖均在finally恢复，捕获不改变模型数值路径。

每case先按原规则核对same-forward PD输出与全部52终端数组，再对外部实际1776的52数组逐元素逐位重放，并要求逐case physics-pass矩阵精确相等（原21/27），不只比较计数。绝对1e-5、rtol0、原全部控制保持。原物理失败不提前结束捕获；外部数值重放或pass标记不一致必须逐case持久记录，全部48继续，完整人口记录后判对照失败并阻断CPU归因，不选择成功子集。输入损坏、结构或资源异常保留partial并诚实失败，不冒充全矩阵完成；不自动重试。

实际候选tiny CUDA和原1503 head-math tiny控制在同一作业内单列，不能替代上述外部全52重放或48人口。新输入/捕获沿用128MiB上限，不公开或复制weights/NPZ进入本仓库。本协议不借1776的失败终态或1492的旧C0作为新捕获C0。

## 仅在新GPU真实闭合后进行CPU分解

CPU直接调用冻结1503的tiny_selfcheck、decode_case、evaluate，不重写functional64、reduction、dipole、pooling、transform或分解数学。原FP32头state和实际捕获H0/坐标不改值；仅诊断性头计算将操作数提升F64，不执行encoder。实际Python/Torch/NumPy/线程元数据照实记录，不假定与旧环境等同。

人口为48case×3个P字段（extensive/dipole/magnitude）×3变换=432项观察，不冒充13字段全1872项归因。在同一个失败分量给出F00/Ft0/F0t/Ftt、带符号H/G/I、GPU_FP32_D、CPU_FP32_D及head_arithmetic_delta并核闭合；不同row/component的最大值不能相加。相同H0下F64头仍有残差，只说明head-arithmetic-only精度提高不足；须先看同分量H/G/I，再选表征、几何或相互作用干预，不能自动归因encoder、LayerNorm或GEMM。任何局部解释都不构成采用、FP32通过、dev panel/D5或真实标签验收。

CPU只消费本次新GPU的COMPLETE/supervisor和独立真实sacct parent/batch/extern C0/16CPU绑定。外部重放失败、人口/来源不全或终态未闭合时不进入归因。

## 原资源与独立发布边界

GPU固定compute-0-21、GPU-c35f2434-9137-9723-1af5-dc69b6295243（c35）、共享fd9锁；16CPU32GiB、28GiB RSS、1100秒supervisor/20分钟SBATCH、whole/private各2GiB。原quota、max(全部用户声明内存,AllocMem)85%、实际MemAvailable、NVML及身份/cleanup/锁规则完全保留，无新runtime/监控/dispatcher。CPU使用原CPU分区16CPU16GiB、120秒child/3分钟SBATCH、12GiB RSS、whole/private2GiB且CUDA隐藏。以上是固定预算，不是已测耗时。

Root+SA4对薄源独立审阅无blocker，实际5份Python AST和2份bash语法检查已通过；[静态记录](../../tools/model_v3/analysis_sources/centered_fixed_H0_diagnostic_v1/ROOT_DRAFT_STATIC_ACTUAL.json)与[最终source audit](../../tools/model_v3/analysis_sources/centered_fixed_H0_diagnostic_v1/ROOT_FINAL_SOURCE_AUDIT_ACTUAL.json)记录源码/候选公开绑定，audit status为FINAL_SOURCE_GRAPH_AND_CANDIDATE_PUBLICATION_AUDIT_PASS_NO_SUBMISSION，无NPZ/SDK读取或GPU执行。静态记录不能当作新测量/QA通过。

| 最终原件的原字节快照 | bytes | SHA256 |
| --- | ---: | --- |
| [execution_request_v1.json](../../tools/model_v3/analysis_sources/centered_fixed_H0_diagnostic_v1/execution_request_v1.json) | 407366 | 37dfb098f341adcb02d552a5beeaea37f7666935ba86de6d29a9204f87b60cd4 |
| [source_pins_v1.json](../../tools/model_v3/analysis_sources/centered_fixed_H0_diagnostic_v1/source_pins_v1.json) | 324805 | d1ebfc3e46415a0aac8f6f82dac652cf950fc7747a2ef876865bcf66e8af132b |

摘要从S原件机器读取并与已通过audit的rawrefs核对。实际执行目录仍为远端runs/model_v3_20261026/centered_fixed_H0_diagnostic_v1_source；[README与历史draft](../../tools/model_v3/analysis_sources/centered_fixed_H0_diagnostic_v1/README.md)原字节保留，当前最终request/pins已组装，原准备阶段文字不视为运行结果。Root公开/读回本协议及源后才启动真实作业；所有旧FAILED、21/27和后续失败保留，未改变模型、门槛、数据、配方或main。

