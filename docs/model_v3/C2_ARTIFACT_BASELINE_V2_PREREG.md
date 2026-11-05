# C2 坐标分析基线 v2：先固定方法，再首次读取验证几何

本注册只涉及查表分析基线，不选择模型架构、预测头或训练配方。原482仍FAILED；
559仍为TRAIN-only诊断，不回写为基线通过。旧两份状态和全部原件保持。

559受控重放的原500次求解stop7；同一TRAIN CSR/RHS、λ=1e-4和原容差下，
active/Jacobi显式增强LSQR在74次后stop2、系数finite。原坐标相对normal residual
8.937747619e-8仅作报告，没有新KKT门槛。全部数据选择和求解决策只用TRAIN；
验证几何此前读取0。完整结果见C2_TRAIN_solver_diagnostic_559.md。

新协议`configs/model_v3/c2_prior_TRAIN_artifact_v2_adopted.json`明确接受559已完成
的TRAIN参数作为v2分析基线的拟合来源。保持原5Å/0.1Å/119元素类型、atom分母、
噪声、原8,192 TRAIN/1,024 PRETRAIN_VAL选择与未知零列规则，不重新拟合、重建
约24分钟的相同TRAIN矩阵。直接恢复已是原坐标c的活跃系数，不再除D。

恢复入口核验NPZ原始SHA/100,361B、精确5键/float64与int64/4,116列/排序范围/
有限性和解压32MiB上限，重建全708,050列未知0。核验原请求/选择/诊断/DONE/
input_binding、原输入bundle及真实Slurm559 C0/1486s、128MiB监督器四源/command/
剩余进程/采样闭合；另有587独立SDK逐标量核验及归档。参数和原生几何不进Git。

源代码第一包575实际17项PASS/C0/6s，artifact恢复第二包591实际31项PASS/C0/10s，
各源前后SHA一致。小TRAIN真实拟合对照证明恢复不二次缩放、与原evaluate一致；
测试不替代实际1024记录验证。两包冻结原字节在analysis_sources下，准备模板仍是
未采用的历史说明；实际入口只能接受本次新公开ADOPTED artifact-origin Git blob。

新独立CPU作业只做元数据准入、恢复参数和首次原1024条PRETRAIN_VAL评估。
结果必须标fit_origin=prior_TRAIN_diagnostic_artifact、参数估计job559、当前TRAIN
geometry reads=0/current VAL reads=1024；原模型/serializer不能误读新artifact schema。
原evaluate计算全部固定coordinate vector/component RMSE、sigma归一化MSE和local
pair指标；不挑指标、不增加接受阈值，不直接拿旧pair-only0.0413Å与坐标误差比较。

预算仍3300s/24GiB RSS/128MiB整作业输出，CPU节点至少16核；持久offline W&B、
完整VAL/source/SDK.finish和外层C0、独立原生SDK核验后才报告v2实际数值。
本协议公开并精确tree核验前，不启动任何真实VAL读取。
