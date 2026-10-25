# C2 仅 TRAIN 求解诊断：实际559

原v1作业482仍为FAILED；其stop/iterations未保存，继续保持未知。
新受控诊断559实际COMPLETED/0:0、1,486秒，CPU12/16核，外层无剩余进程或
采样/清理故障，整个输出约1.27MB。只解码原选择的8,192条TRAIN/436,120 atoms，
PRETRAIN_VAL几何读取0。它不是新的基线通过记录。

| 求解观察 | 原固定算法、受控BLAS1 | 同目标active/Jacobi、BLAS1 |
| --- | ---: | ---: |
| 实际LSQR stop code | 7 | 2 |
| 实际迭代数 | 500 | 74 |
| 求解器秒数（不含特征构建） | 34.5504945 | 4.7119295 |
| 原坐标目标 | 0.0131291605665 | 0.0131291373241 |
| 原坐标相对normal residual | 2.61756356e-4 | 8.93774762e-8 |
| 原坐标TRAIN component MSE（Å²） | 0.00426703133168 | 0.00426698957766 |

固定TRAIN矩阵为1,308,360×708,050、25,662,564 nnz，9,771,514 directed edges，
实际活跃列4,116。两阶段共享同一只读CSR/RHS，原缓冲区SHA前后相同；λ=1e-4、
atom分母、几何分桶、噪声和人口不变。记录了BLAS线程前/中/后状态并精确恢复。
相对normal residual无新接受阈值；表中墙钟仅为一次求解观察，不是GPU提速或训练
ABBA结论。大部分总墙钟用于原特征构建，不以单独求解器时间冒充整作业时间。

实际活跃系数/support/D只在外部100,361B NPZ保存，完整SHA在原结果内；不进Git。
后续可在新公开协议明确接受这份TRAIN拟合产物，然后在独立作业首次评估固定验证
人口，避免重复约24分钟的同矩阵构建。必须核验完整源/实际C0/参数artifact，不能
改写559的diagnostic-only状态，也不能把TRAIN收敛或统计当作验证性能/基线验收。

执行规则公开于cd0c434bb39824cd75c24d7c6de0531946da1de5，本地注册c65db8b；
精确源与原始请求/选择/失败绑定见C2_TRAIN_SOLVER_DIAGNOSTIC_PREREG.md及外部
input_binding.json。独立SDK核验、归档和后续验证分别闭合。旧pair-distance查表的
0.0413Å不是坐标vector/component RMSE，本诊断不与其数值直接比较。
