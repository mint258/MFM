# 已保存数组的等变性v2一次CPU重判

仅读取13套已完成FP32完整48矩阵（1160/1435/1492/1776/1838/3505/4448/4550/4563/4579/4595/4610/4701）及1561完整FP64 H0；不运行模型、重建权重、新forward或新矩阵。所有补偿/候选历史无论新门是否通过都不采用，旧失败/数组/报告不改。重复passive记录独立列为历史，不当新增模型证据。

参考严格沿原0c49 fixture v3_composed_equivariance.py311–316与367–392：原始52 NPZ终端的original为基值，invariant直接用原值，vector用base.double() @ recorded_R64，coordinate再加recorded_t64；实际transform0/1/2按原顺序对应general_rotation、translation_only、other_rotation_and_translation。真正逐元素计算FP32 abs(actual-reference)<=1e-6+1e-4*abs(reference)，不是从旧maxabs推断。保留原domain/边界及nonzero资格单独列，原nonzero域floor不是新相对分母epsilon。

Root已明确采用FP64逐元素 abs(delta)<=1e-9*abs(reference)，无epsilon；reference=0只能delta精确0通过。1561保存四role44×512 FP64 H0，所以可按不变H0比较，但它使用原F32生成的变换输入再promote，不能冒充纯FP64数学输入/完整终端验证。1561终端仅旧D max/argmax/绝对计数；1842只存D/H/G/I分解；1917保存全D但没有完整reference/y；这些完整FP64终端相对门一律UNPROVEN，不能用maxabs/某点/roundback构造通过。原0c49注册的是abs1e-5、rtol0，并无另一个已登记norm-relative门。

Root执行（源码未由作者运行/AST/提交）：
PY -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_rejudge_20261029/rejudge.py --request /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_rejudge_20261029/request.json --output FRESH_N_OUTPUT
canonical薄SB为N/run_equivariance_v2_rejudge_v1.sbatch，默认输出N/equivariance_v2_rejudge_actual_v1，显式MODEL_V3_EXPECTED_NODE由Root现场准入绑定。CPU>=16自动内存，无mem/exclusive；沿原run_cpu_supervised_v3，RSS12GiB/900s/whole-private各2GiB；worker780s及CSV+JSON128MiB上限。所有NPZ只在实际CPU Slurm内np.load(allow_pickle=False)，核原记录SHA/dtype/shape，source/login不打开数组。Root统一提交，不另造调度/资源/receipt/SHA/QA管线。

输出field_results.csv是真正逐元素计算后的逐field/transform计数、最坏分量actual/reference/threshold，含原域资格；summary.json汇总每cohort完整48覆盖与新门结果并保留旧passed。数值FAIL是重判观测，不触发重新forward；缺失/异常输入HOLD并保留实际错误，Root可仅修metadata路径。数学/容差重判不等于架构采纳、D5/B*或最终交付。