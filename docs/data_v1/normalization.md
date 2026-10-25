# TRAIN-only 归一化：实现与待执行验收

目的：在最终训练人群上生成可追溯的尺度和能量元素参考，保留训练标签的原始物理值。目前交付代码与参数协议；尚未拟合新科学统计量。

## 输入和角色

入口是 `workflows/data_v1_final/labels/fit_normalization.py`。所有输入都要求 path/bytes/SHA：mask 后的外部 observations 文件、字段登记、最终 record manifest、split authority。历史输入 SHA 在注册表报告中；尚未生成的 common population、diagnostic 排除和 observations 不填写未来哈希。

用户已决定使用既有 ROUTINE 作为 VAL；原 TRAIN 不再抽家族。程序要求 `split_authority.status=FROZEN`、全部构象同角色且 `validation_source=ROUTINE`，否则拒绝拟合。实际拟合还限定 TRAIN、共同人群、`training_eligible=true`，排除诊断几何；既有 FULL 和 VAL 不进入统计。

final 额外要求共同人群与诊断排除冻结，并逐字段实际核对全部期望 TRAIN records、唯一性和角色一致性。试点输出标 `PILOT_NOT_FINAL`，不能直接作为 D-4。P′ 使用相同字段但 `geometry_source=uff_sprime`，独立拟合。

## 规则

能量元素参考只用于已明确登记的分子级能量类字段；IP/EA、轨道能、原子能量不因单位含eV而误用分子元素回归。元素计数包含氢和所有实际元素，basis为原子序数1–118，另含截距；按 record_id 固定顺序，以4096行分块 float64 TSQR 后最小二乘，保存系数、rank、奇异值和rcond。

在有效原值（能量先扣元素参考）上计算精确 type-7 q0.001/q0.999，仅将它们用于 winsorized mean/std(ddof=0)。原训练标签不裁剪。另保存未缩尾范围、median、MAD、z>20复核计数；MAD=0和std=0显式标记，不能默默除零。

原子及原子向量字段按来源 atom_index 映射元素，额外输出逐元素统计。缺少原子对应关系时拒绝生成该统计，不按化学式或排序猜原子位置。

size ρ 对分子标量在有效交集上重新按平均ties排名，报告pairN。生成热使用元素参考残差。非标量仍需决定旋转一致的分子聚合规则，因此即使完成一个归一化试点，也不能据此冻结整个标签家族。

## 资源、复现与异常

必须在16核 Slurm中运行；16个worker各单线程DuckDB/BLAS，默认每worker1GB内存、2GiB spill。Root 提交前将所有spill、输出和失败证据计入账户quota预算，保留至少200GB。脚本要求新鲜真实quota收据，不使用整盘df替代账户配额。

输出包含输入哈希、job、依赖版本、拟合人口、各字段系数与统计。相同环境和顺序是可复现前提；还需要独立从 parquet 重建并实际核对逐位一致性。当前没有声称这一重建已执行，也未把旧q01/q99统计误用作新q001/q999归一化。

## 待完成

最终 common/角色/诊断清单、全人群新 mask、P′标签和完整 observations 仍是前置依赖。新 mean/std/元素系数、实际核时、峰值存储及分布报告均尚未生成，不以合成数据或旧统计代替。
