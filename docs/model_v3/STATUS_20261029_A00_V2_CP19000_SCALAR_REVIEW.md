# A00-v2 首项复核、Native CP19000 与 FP32 逐字段复查

本报告补充此前的 [CPU 自动内存与负结果报告](STATUS_20261029_CPU_AUTO_A5_V2_FP32_NATIVE.md)。完整 Stage0–7 仍未完成；这里分别记录已闭合结果、正在运行的验证和后续方法。

## 问题与预先规则

本轮验证旧 A00 manual 通过项在当前源码和新梯度规则下是否仍通过，并检查残差 FP32 的通过案例数变化是否掩盖退化。A 梯度 v2 先于运行公开于 [4f6ba16](https://github.com/mint258/MFM/commit/4f6ba16973ea4a30472c7fb33d3aadec974a4462)：全部梯度元素满足 |a−b|≤1e−8+1e−4|b|，六个解析零 bias 还要求两边范数≤1e−8。原 forward≤1e−5、完整500步 loss 相对差≤1e−3 保持。物理测试仍为完整48案例、原绝对1e−5和rtol=0。

## A00 manual：完整通过

实际使用 local 7ffe8a5557590b1481f4ca74073007f070dc6a50 / [public 2b4a4df](https://github.com/mint258/MFM/commit/2b4a4df8636e5d65915d535472ba01084ea72dab)。运行方法先公开于 [cf816e1](https://github.com/mint258/MFM/commit/cf816e1441a245b80d90bc409a6fdc94cd3eea41)。配置身份为 7c43e0feacec4a5cdffb7c297500897fe5debd95b472e0103415e072fb8310b1；Native S manifest 2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997，seed0、P8M、workers8、双模型驻留、manual，无packing。

| 项目 | 实际结果 |
| --- | --- |
| GPU父4524712 | COMPLETED 0:0，2305s，16CPU，C35/5090 |
| 固定20批次，8输出、329命名参数/批 | 全部通过，forward及梯度最大差均0 |
| 解析零参数 | 120条通过，最大范数8.722549703540776e−10 |
| 双方disabled | 4240条，单独分类 |
| 原500步轨迹 | 全部通过，最大loss相对差0，201216条base记录 |
| 原容量消费者CPU4524717 | COMPLETED 0:0，6s；305必需源码、实际500行及六引用均通过 |

[Root闭合记录](results/manual_Av2_GPU4712_CPU4717_Root_closure.json)保留源码、配置、规则、GPU/CPU实际sacct及进程/私有空间证据。它是九组旧PASS复核中的首个当前源码观测（3976类型）；原3976记录身份不改。A5 packing 的1779条逐参数批次失败仍保留，未被此项覆盖。

容量观察的实际边界为1536图、92355原子、单图331原子、padded cost7998894；采样GPU内存上界观察为14183038976B。该边界不授予全N/全批形状或最优checkpoint策略资格。原策略消费者未初始化CUDA，也未执行auto选择、R1/ABBA或新GPU数值门。[实际六引用profile与后续auto请求](posthoc_methods/performance_manual_R2_Av2_capacity_consumer_v1_source/actual/BINDING.json)只供后续复核使用。

下一项 [head-off manual复核方法](pre_registered_methods/performance_head_off_R2_Av2_v2/METHODS_README.md)使用原a03、当前7ffe和同一v2规则。它补用已有registry_lock登记独立hold，避免与Native quota feed并发更新冲突。源码、AST、bash及当前完整CPU来源已核验；新GPU结果在本报告时尚未产生。

## 残差：存在真实退化，继续不采用

CPU4524715实际C0/1s，对同参数捕获来源、同fixture/视图/变换的全部48对案例、1872对既有标量完成配对检查；104项元数据来源前后及当前一致。原参数捕获来源是作业4521492，1492不是模型参数数量。未打开或重跑NPZ、模型、权重、SDK或原生标签。

| 指标 | FFN4610 | residual4701 |
| --- | ---: | ---: |
| 完整48案例通过/失败 | 14 / 34 | 22 / 26 |
| 1872个字段×变换观测的失败数 | 56 | 43 |
| p_extensive失败数（144观测） | 10 | 4 |
| p_dipole失败数（144观测） | 31 | 35 |
| p_dipole_magnitude失败数（144观测） | 15 | 4 |

案例转移：13个FAIL→PASS，5个PASS→FAIL，9个保持PASS，21个保持FAIL；字段观测则39个FAIL→PASS、26个PASS→FAIL。偶极矢量最大绝对误差由1.9415126989275056e−5增至2.3365020751953125e−5。H0诊断最大值下降不能替代终端物理门，也不是已证明的因果解释。两候选都未通过，均不采用。

可审阅 [完整字段/变换与48案例汇总](posthoc_methods/residual4701_vs_FFN4610_scalar_CPU_v2_source/residual4701_vs_FFN4610_scalar_compact_public_summary_actual_v1.json)、[薄分析源码](posthoc_methods/residual4701_vs_FFN4610_scalar_CPU_v2_source/compare_scalars.py)和[Root闭合](posthoc_methods/residual4701_vs_FFN4610_scalar_CPU_v2_source/residual4701_vs_FFN4610_scalar_CPU4715_Root_closure_actual_v1.json)。完整1872行输出1482099B，SHA256为4abb608899fe30046d0382e388ba462d1d5c4d94c16877884b6b0873e38503bb，保存在服务器原记录所列路径。

首次CPU4524714因旧FFN闭合无顶层failed/passed别名退出；v1源与失败记录保留。v2只改读已有权威counts，原counts相等和全48门保持。Root首次逐字检查未通过时仍提交了4715；随后确认差异仅为该字段读取和拆行，完成原始字节核对与104来源复核后才接受统计。数值规则及原GPU实验未改。

## Native、日志与数据依赖

Native seed0/FP32 的4524713实际C0/2529s，安全CP推进到19000更新、7741355样本，检查点为slot020/checkpoint_u19000_log19039。原v7 Source/科学3d9、UUID22e、32GiB及全部保护保持。下一实际作业4524716执行19000→20000；四成员仍0/4完成20k，完整bf16决策尚未形成。

两条A5-v2 failed/0-history日志 n7wb3txh、0dtrjv10 已经独立审计、同步并读回；[Root记录](posthoc_methods/logging_89_20261029/A5_v2_failed_SDK_sync_CPU_4524708_4524709_Root_closure_actual_v1.json)和[89条已知在线账](posthoc_methods/logging_89_20261029/WandB_known_online_closed_records_89_20261029_v1.json)保留状态与来源。旧87由原50加18份既有补充闭合独立重建去重，再追加新2；没有声称重新查询全部89。A00本轮日志及后续Native段另行审计。

最新 [D1–D6直接证据审计](posthoc_methods/data_delivery_gate_audit_20261029/READONLY_REFS_AND_GATES.json)仍显示joint ACK未完成，registry为DRAFT；来源角色FROZEN不授予Common人口、D5/D6或归一化资格。继续现有S和合成工作，真实D3/D4/D5/D6模型侧验收保留。

成本ledger53是点时快照：591父=424CPU+100GPU+67other，1761936 allocated CPU秒、86153 GPU节点作业秒。该快照未包含4711起的新任务，不是最终成本或利用率。原始文件runs/model_v3_20261025/job_ledger_model_v3_active_v53.json，729656B，SHA256 a324be5f2179ba54c65a890ab3431fd08e7a91e9ce7f0c0e4adcc294b25ea20e。

后续继续旧A-PASS逐项复核、四条20k曲线、严格FP32物理门和真实数据依赖。最终架构、配方/B*、共同冻结和交接仍待完成；本报告不授予正式预训练或最终测试资格。
