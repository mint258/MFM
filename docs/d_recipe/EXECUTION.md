# D 线执行登记

2026-11-20（Asia/Shanghai）。用户明确要求严格执行本任务书的 **D 家族**实验，取代此前消息中的 S 家族名称。

任务书来源：`docs/s-d-taskbooks-20261119` 分支的 `docs/d_recipe/TASKBOOK.md`，原文保留。本次完整执行请求授权阶段 0 先行及书中已有的条件运行和 9M 确认；不增加训练臂。

## 分支及范围

- `d-recipe` 从已发布 p-recipe 提交 `49f1c6bc9d699085474fa86b7d5638a3c5231246` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_recipe`。
- 阶段 0：`data-d-descriptors-20261120`，从已发布 data-v1 提交 `bc47699c709f57bb00108473f17bf4652333d2ec` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120`。
- P 线的实际未提交工作和在跑任务保持原样；仅包装既有 API，不复制或修改 P 训练与评测文件。

## 执行顺序

1. 阶段 0 过滤规则预注册 → CPU 环境准备 → 固定约 5000 TRAIN 分子 → L1/L2 成本测试 → 全量及下游导出 → 新字段 TRAIN 统计 → 生产清单。
2. P 配方冻结且其 9M 已提交后，将实际 P 配置键逐项登记到训练预注册；验证真实 loader、逐头过拟合和 SASA 原子对应，然后 D-R0/D-R1。
3. 按任务书顺序推进 D-L1、D-L2、D-G1、条件 D-K1 和条件 seed1；每个对照只训练一次并复用。
4. 完成规定诊断、开发面板 A/B/C 及组成参照，与基准线交付特征；冻结 CURRENT_BEST，执行规定 seed0 9M；报告、一次完整回归和仓库检查后开 PR，不合并。

## 当前依赖

P 配方 `CURRENT_BEST` 尚未冻结，F1 仍在训练。因此 GPU 训练尚未启动；这不是 D-R1 的 TIE/LOSS 或完成结论。阶段 0 接收验收、全量产物、所有 D 训练与最终报告均未完成。

阶段 0 的 `configs/data_d_descriptors/preregistration.json` 已在读取描述符分布前冻结并发布；训练预注册尚未发布，不能用占位的 P 配方或未核实块权重代替最终配置。

2026-11-20 新逻辑检查已实际通过：compute-0-17 原生 SSH 单核短程测试，UID1278、Python PID1392349，未伪造 Slurm 身份。日志 `/share/home/zixiao/descriptor_analysis/D_native_cpu_tests_20261120_1622.log`：215 tests、OK、exit0，总耗时5.67秒、峰值RSS923640KiB。所用 pyarrow25.0.1 原地只读复用现有 P deps，其他包沿 chemprop 环境，不安装或修改共享环境。NFS 实际挂载点 `/share/home` 的守卫已修正并覆盖测试；本地测试夹具在逐项核查容量的 `/tmp` 下，预留峰值16MiB，不复制真实数据库。

旧7113/7202/7261/7346/7347均已在零运行时间取消。后续成本作业4537408、afterok成本的规划4537409，以及开发/基准无标签输入准备4537410/4537411已重新提交；截至16:21仍PENDING。新逻辑通过不替代真实64分子接收验收，不表示阶段0交付或任何科学臂完成。

## 数据处理与判定

沿用原人群、划分和原子 ID；现有 D20/D3 与 11-07 参数不变，新字段只用 TRAIN 拟合。宽库存储值不截断，损失中的标准化目标统一截至 ±6，报告各字段比例。阶段 0 的真实接收验收仅按任务书第 6 节执行一次。

主指标 R3 七任务均值，R1/CYP 只报告；分子级配对 bootstrap 1000 次，seed 20261025，95% 百分位 CI；τ=max(0.01,0.05×较大 R3)。WIN/LOSS/TIE、删除项和条件种子严格采用任务书 4.6。CI 描述固定模型的抽样不确定性，不代表训练随机性；未做多重比较校正。尚无 D 实验结果可作统计结论。
