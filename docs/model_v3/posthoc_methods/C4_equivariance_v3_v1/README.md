# C4用户v3：决策消费与原base FP32保存输出诊断

规则原文：MFM_model_v3_delivery_integration_v2/docs/model_v3/USER_MAINLINE_AMENDMENT_V3_20261029.md，同源N/MODEL_LINE_USER_AMENDMENT_V3_20261029.md；用户Root生效记录N/MODEL_LINE_USER_AMENDMENT_V3_effective_20261029.json。原文已明确唯一C4硬门为FP64相对<=1e-9，既有CPU4524734为48/48 PASS，C4立即PASS；FP32只报告，不判PASS/FAIL、不阻塞。不重跑v1/v2、不采用任何FP32补偿。

## 独立模块与已有证据

c4_v3.py的c4_decision是纯stdlib metadata消费。request.json精确引用实际4734 summary/COMPLETE/sup/submission及Root用户v3生效记录，并保留其实际C4快照。现4734的数学输入在变换前promoteF64，全48/192F64/0errors/0mathematical_failures，relative1e-9/epsilon0。新decision输出C4=PASS，明确旧HOLD被用户v3替代，不把FP32报告、SDK、fixture或SHA问题加回硬门。若当前元数据读取/绑定发生问题，记录具体issue/current_read=false；PASS仍来自已冻结的用户Root明确生效快照与已知4734事实，不伪称读取校验成功，不发起新模型/验收矩阵。该模块不修改DECISION_RULES、A资格、阶段5科学选择或真实Data准入。

Root可先用--decision-only只消费小metadata落地C4_DECISION.json，完全不打开NPZ。正常单次CPU报告先写同一decision，再读取唯一已存未补偿baseline1160的48个52终端NPZ；不重新运行旧重判worker，也不导入任何model/Torch/compensation模块。原rejudge request只作为实际case路径/原Source引用，严格只选择baseline_original1160/compensation_history=false，不打开其余13个历史矩阵。实际数组仅Root后续CPU>=16作业内以allow_pickle=False读取，保原SHA/dtype/shape/大小/owner/ordinary-file约束。

## 诊断定义与人口

矢量/张量为每分子每字段norm(actual-reference)/norm(reference)；标量函数为abs(delta)/(abs(y)+该字段实际TRAINstd)。不使用1、epsilon、数据相关floor或临时从合成fixture估出的std，也不把Data normalizer scale/winsorized mean直接充当原TRAINstd。当前没有真实逐字段TRAINstd，request为null，全部scalar诊断标TRAIN_STD_UNAVAILABLE且计数，不阻塞C4。pure diagnostic_values接口支持已真实验证的有限非负std；本次不发明Data发行schema或接受自报统计manifest。r674没有保存于此原13field，不追加它的计算，原LOSS_DISABLED头保留。

原fixture三个分子为water-like3/ethanol-like9/decane-like32；原Source绑定native atom3/9/32、clean bond2/8/31、原physical views按每分子重复。PD graph/atom/pair以及S clean-bond/physical-atom按这一实际原Source顺序归属，验证每字段shape人口一致。矢量每分子跨其原physical views取一次L2/Frobenius范数，scalar保留每scalar entry的定义（当前无std所以无值），不混为graph label或新增target。原三变换、原base及记录的R64/t64 law不改；Source参考在CPU double中计算仅为报告，没有新forward或数值实现分支。全部48×3transform×13field×3molecule=5616逐分子字段行。

normY恰为0或非有限、除法结果非有限时，分别计undefined/nonfinite，只对可定义有限值汇总p50/p99/max；没有未经授权的“近零”阈值/epsilon。任何小而非零的有限分母仍按原式报告其真实比值。scalar std缺失计unavailable，未知不等于通过/失败。旧domain/nonzero容差不作为新FP32门。报告不输出FP32 PASS/FAIL或阈值筛选。

输出fp32_per_molecule_field.csv（5616行）、fp32_field_summary.csv（39个transform/field组）、summary.json与C4_DECISION.json。p50/p99用定义明确的linear quantile，vector/tensor每分子一个norm ratio；统计人口和不可得/非有限/零分母计数分列。不存在新的物理采纳或TEST访问。

## 有限预算与Root调用

复用既有CPU自动内存/监督器，不建新提交器/监控/QA父。至少16CPU、CUDA隐藏、Root实际合法CPU node、实际MemAvailable/quota，原RSS12GiB/whole-private各2GiB；建议原900s监督、worker最多780s、自身输出128MiB。Root提交时设置MODEL_V3_EXPECTED_NODE；作者未运行项目/AST/NPZ/Slurm/Git。

PY -B S/c4_v3.py --request S/request.json --output FRESH_N_OUTPUT --prior-diagnostic-seconds ACTUAL_CUMULATIVE_SECONDS --consecutive-failures ACTUAL_CONSECUTIVE_FAILURE_COUNT

所有路径在handoff中提供完整单一argv元素。两预算值由Root据实际诊断/修复人口填写，无伪造0默认。累计达到4h、连续失败>=2，或预算状态未知，直接UNRESOLVED_CONSERVATIVE_OLD_PATH_CONTINUE，不打开数组、不启动新修复/候选，C4仍PASS。实际工程错误保留原因与已有部分文件、不自动重试、不改老结果；未解决只作诊断状态，主线继续。缺TRAINstd属于正常不可得，不是失败重试理由。Root负责实际计时/失败streak合账，DAILY仅按用户既有规则记录，不加新的daily/账本。
