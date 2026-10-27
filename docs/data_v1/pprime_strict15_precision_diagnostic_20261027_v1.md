# P′ 独立精度诊断15次：实际结果

本报告记录用户单独批准的15次精度诊断，不是P′全量或2000构象试点验收。完整数据线尚未完成，原15次失败及其所有输出、账本和成本保留。

## 目的、输入与参数

检查既有六个来源、15组B1/B2/R1/P1/P2输入在更严格数值设置下的重复性、旋转与P90坐标轴变换协变性（原子顺序始终未打乱）和同几何梯度/单点偶极矩一致性。唯一协议差异：pm7_B追加`SCFCRT=1.D-9`；xtb_singlepoint、xtb_perturbed_gradient追加`--acc 0.01`，其余九项任务未改变。

原协议：`runs/phase1_wp5_20261011/configs/protocol.json`，18720B，SHA256 `3e831aa57d4d90376c6107e309484e231038a3536ed0f28371d2f8554149a6bc`。

本次独立诊断协议：`configs/data_v1/pprime/strict_numerics15_qa_v1_protocol_proposed.json`，19218B，SHA256 `f72bb07780b28026df5931478b50495d3cb4d75fe5edecac7593b90af9356302`。该文件不是原生产协议。二进制版本、环境、原输入/原子顺序、种子、坐标、900秒单调用超时及全部原质量容差不变。

用户授权及确切父链见外部小清单：`runs/data_v1_20261025/control/pprime_strict15_actual_user_approval_20261027_v1.json`、`pprime_strict15_actual_user_approved_root_request_v1.json`。原调用器与精度适配器的3项检查已在Main作业4523054实际通过；另有Alpha源代码检查，二者不能互相替代。

## 实际结果

Main作业4523473在compute-0-13使用16CPU，无SBATCH内存/exclusive/GPU申请，实际COMPLETED/0，45秒、720分配核秒。恰好调用15次，15次均返回并持久保存；无未返回派发、替补或重试，独立once上界为15，所有工作进程已退出。

- 15组比较共25项向量检查，全部通过原协变性容差；没有新增数值容差。
- 5组同实际输入几何的梯度/单点伴随检查全部通过。
- 新调用自身的原始输出与存储字段读回检查通过。单点伴随输出不提供自身坐标时仍明确记录“坐标不可用”，没有把它解释为坐标已验证。
- 原先协议与本次精度协议的同臂数值差异保留；两种设置数值不同本身不是修复证明或额外验收门槛。

以下量直接摘自实际CPU分析回执中B1/R1比较，不是登录节点重新计算：

| 量 | 最大绝对残差 | 原容差允许值 |
| --- | ---: | ---: |
| PM7偶极矩，Debye | 5.236352e-6 | 2.886834831336e-4 |
| PM7梯度，kcal/mol/Å | 7.126237333334e-5 | 6.061709370067e-4 |
| xTB偶极矩，Debye | 3.439830229546e-7 | 3.166617636496e-4 |
| xTB梯度，Eh/bohr | 2.983580799087e-9 | 3.389977603348e-5 |

## 可审计输出与限制

原始输出、输入、每调用意图/身份/返回记录、全部分析及SHA均在外部`artifacts/pprime_strict_numerics15_qa_v1/run_v1/`。关键回执为`receipt.json`、`strict15_analysis.json`；实际会计为`control/accounting/pprime_strict15_4523473_actual_C0_v1.json`。Root独立结果审查为`control/root_actual_strict15_limited_diagnostic_review_20261027_v1.json`。脚本在`workflows/data_v1_final/pprime/strict_numerics15_qa_v1/`。

这只覆盖原固定来源的三个条件，不证明20个分子的全部12项任务、最终共同人群、全部原生基组/张量语义或独立P′归一化通过。失败的确切物理/数值原因仍为UNKNOWN，不能仅凭本次通过归因。生产协议没有更改，科学PASS与2000/全量放行仍为HOLD。

下一步应先提出并审核20分子、全12任务及原旋转/P90坐标轴变换QA的具体输入、最大调用数、独立once和资源上限。本次用户授权仅覆盖这15次；使用精度协议的新QA调用须另获明确授权。现有S′、标签和扩充工作继续，不因这项HOLD停止独立任务。