# C2 仅 TRAIN 求解诊断预注册

原真实坐标查表作业4520482保持FAILED。它在TRAIN拟合阶段拒绝了LSQR返回，
没有保存实际stop code/iteration；未读取PRETRAIN_VAL几何。不能根据其耗时、
旧上限500或后续结果反推原停止原因。

这次仅诊断数值求解，不创建新基线验收或模型选择。精确协议与8个冻结源码/测试
在`tools/model_v3/analysis_sources/c2_solver_diagnostic_v1/`；执行仍用原始外部
同字节目录，逐文件SHA及输入注册commit在实际run收据绑定。原ecdb6eb C2
核心、请求、8,192条TRAIN选择、几何/噪声、特征分桶和ridge均不改。

1. 用透明临时包装捕获原固定CSR/RHS；转发原LinearOperator和LSQR返回，finally
   恢复原模块绑定。只重放TRAIN，BLAS固定1线程，仍为原500次上限/原容差。
   返回后先持久保存实际stop/iterations/rnorm/arnorm/anorm/acond/xnorm，再做KKT。
   所有线程状态前/中/后都记录；这不是482的逐位重放，其原线程状态未知。
2. 同一个只读TRAIN CSR/RHS再做分析性预条件：活跃列、
   D=sqrt(column_norm_squared/n_atoms+ridge)，显式增强系统
   [A_active/(sqrt(n_atoms)*D); sqrt(ridge)/D]，damp=0，原容差，上限2,000。
   不使用非零x0+damp的先验中心变更；未知零列的原坐标系数固定0。
3. 分别保存原坐标目标与g=A.T@(A@c-b)/n_atoms+ridge*c。相对KKT仅在真实
   RHS梯度范数>0时定义，不设新的接受阈值，不读验证集，不把任何结果称为C2通过。

原预算不增加：3,300秒、进程RSS24GiB、全部输出128MiB、numeric上界8GiB；
工作在3,240秒前停止，余量用于核验、SDK.finish和监督收尾。未返回的求解统计
保持未知；deadline结果明确censored。CSR不保存，活跃系数等可选NPZ有32MiB
上限，数据产物只在外部run，不进Git。W&B持久offline，实际终态与日志另核。

实际20项小型数学/真实旧core捕获/TRAIN-only测试在4520551通过，CPU节点
compute-0-12，C0/6秒，源前后SHA相同，监督闭合无剩余进程。测试后提交本协议
并公开；真实诊断必须在公开注册之后单独提交，
输入包含原request、selection plan、FAILED字节引用及本协议实际Git blob。
测试通过不构成真实TRAIN求解、基线通过或正式预训练授权。
