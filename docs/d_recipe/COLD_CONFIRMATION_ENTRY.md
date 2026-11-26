# 冻结后的冷9M配置入口

此入口落实TASKBOOK第7节，不作配方选择、不提交作业、不读取权重或数值数组。

`tools.d_recipe.confirmation_plan.plan_confirmation(best, baseline, selected, output_root=..., run_prefix=...)`仅在`best.status=FROZEN`且`recipe_frozen=true`后返回配置。当前CURRENT尚未冻结，因此没有生成或启动实际9M确认。

- baseline为原D-R0 seed0/3M科学配置，始终保留9M-D-R0；selected为全部关卡完成后冻结的最终科学配置，仅不同于D-R0时增加9M-D-final。
- 两条均冷启动、seed0、9M；完整断点按1M至9M保留，固定下游读出只在9M。没有9M seed1。
- 清除旧resume/断点、handoff、基础设施续接元信息、3M诊断/特征路径、节点/UUID及旧本地/共享盘预算；原TRAIN参数、字段定义、块权重及已采纳组件保留。每条重新从60000–150000窗口拟合自己的p99，不继承3M fitted状态。
- 仅被选定的9M终点设置persist_final_features=true；已有train.final_readout实际消费该开关并把特征写到新9M路径，供最终七任务A/B/C使用。不回读已退役R0 3M缓存，不因缺缓存新增编码器前向。
- 配置标明resource_admission_pending=true，未绑定实际硬件与新存储预算；Root须先登记并准入9M断点、最终H0/序列化、读出和节点临时峰值，再填实际GPU/CPU/磁盘/TimeLimit及退出窗口。两个9M运行对应18个1M间隔断点，不能沿用3M槽位或旧GPU20续接预算。
- 新统一守卫的reservation_ids、canonical_phase_admission、safe_exit_control及SSH句柄也在新任务中清除；条件seed1同样重新绑定。已存在的同条件seed1控制仍直接复用。此清理不改变科学字段、TRAIN参数、采纳规则或当前运行源码。

输入优先使用CURRENT.stage2.original_training_configurations所指的原冷配置，之后合入已经冻结的最终科学决定；不得拿当前1M基础设施续接配置直接作为可运行9M配置。

新增定向测试覆盖冻结门、只允许规定1/2条seed0运行、无旧resume/cache/硬件预算、重新校准、最终H0实际路径、条件mask seed和几何决定的最终组合。测试只用微型配置，不做训练/前向/数组读取。[测试状态](../../results/d_recipe/confirmation_plan_tests_20261125.json)。完整默认回归和check_repository仍只在最终PR前一次。

2026-11-26按最新短CPU调度规则取消原零运行排队作业4539987后，复用原冻结测试命令在node19/core65单次执行，10项全部通过；[实际SSH测试结果](../../results/d_recipe/confirmation_plan_tests_SSH_20261126.json)取代旧排队状态。未冻结最终配方或启动9M。

