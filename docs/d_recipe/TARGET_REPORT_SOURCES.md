# 阶段2目标报告来源

任务书§4.2、§6、§9要求的逐字段截断比例，直接消费原全TRAIN A1拟合器首次生产输出；不另起原数组扫描、拟合或独立复核。[11-25补做指示](USER_DIRECTIVE_20261125.md)已撤销L2 A1/D-L2的旧工程类UNRESOLVED，现原拟合已实际成功。

| 库 | 原全TRAIN生产 | 字段与冻结报告 |
| --- | --- | --- |
| L1 | 4539166 / CPU11，COMPLETED0:0，79720秒×1CPU | 197分子字段，[原完整报告](../../results/d_recipe/L1_original_A1_fit_20261124.json)，FROZEN_FIT / unresolved=[] |
| L2 | ssh:P_D_L2_A1_full_fit1_20261127 / CPU11，实际COMPLETE/0/reaped/父子与worker均消失 | 1320分子字段，[原逐字段报告](../../results/d_recipe/L2_original_A1_fit_20261127.json)，FROZEN_FIT / unresolved=[]；734残差、586原目标 |

两库均使用原1194228唯一TRAIN。L2原alpha=1、五折seed20261112和旧D4保持；原1320个fit.fields按原序转录，R²/target_policy/n_valid/clipped_TRAIN_count/clipping_fraction没有重新计算。734/586仅汇总原目标策略，不按结果重分档或选择库。完整冻结系数与normalizations保存在原参数文件，版本报告用来源指针代替重复系数数组。

L1参数：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L1/label_parameters.json`。L2参数：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L2/label_parameters.json`，7299154B，原拟合原子发布成功。实际L2拟合墙钟1625.637849330902秒、CPU11439.778441999999秒、峰值49778836KiB；[原执行和成本](../../results/d_recipe/safe_L1_handoff_and_L2_SSH_segments_20261126.json)包含五段收集及最终拟合的退出证明。仅退役已关闭CPU11未用RAM/本地future，所有源文件与局部数组保留。

L2旧4539164的收集根目录准入失败和4539169在729600行的额度拒绝保留为[失败历史](../../results/d_recipe/L2_A1_unresolved_20261124.json)，属于工程失败，不是R3 TIE/LOSS。原游标已续至全1194228，未拟合部分TRAIN。报告转录在CPU19按短CPU SSH执行，只读取一次冻结参数，没有读取原标签/预测载荷或再拟合；实际成本随原执行记录保留。

D-L2下一步仍是原3M/seed0，对照复用D-R1，同seed配对，只有seed0 WIN触发seed1。[启动准备](../../configs/d_recipe/continuations/L2_after_A1_20261127_plan.json)不可直接运行，实际GPU/CPU/RAM/磁盘/UID准入后才生成绑定配置。目标库选择等待L1/L2及各自按规则触发的seed1，之后才是条件K1、冻结、冷9M和A/B/C。

分子字段±6计数是本原A1目标策略下的原报告；旧D20/D3和逐原子SASA另沿4538573闭合的[原全TRAIN截断报告](../../results/d_recipe/native_TRAIN_clipping_20261122.json)。旧定义、D4、存储值和原计数不改，不重复读取旧SASA数组。L1固定VAL/完整断点仅是训练观测，不能替代3M/R3判定或目标截断比例。
