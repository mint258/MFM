# 最终开发面板 A/B/C 的执行衔接

本页只把任务书第5节接到已有执行器，不增加训练臂、调参预算或科学判定。当前配方未冻结、选定9M未完成；没有启动A/B/C，也没有最终对照结果。

## 实际入口与顺序

1. 全部3M关卡完成后冻结CURRENT_BEST；按[冷确认入口](COLD_CONFIRMATION_ENTRY.md)运行规定的seed0 9M。选定9M的原末层前向保留最终H0，原主R3和分子bootstrap同时保留。A直接使用这些原产物。
2. 只为选定9M构造一份development_panel配置。GPU阶段运行已有B_MLP和C；CPU阶段接续LightGBM、组成ridge和统计。两阶段共用output和除phase外完全相同的配置；已有summary以这些键绑定条件，不能更换终点后继续写入。
3. GPU阶段通过managed_entry与resident_bootstrap启动，resource-command为development_panel、kind=gpu；实际Slurm EndTime前预留收尾窗口。CPU≤16且预计≤4小时的后续阶段按11-26规则走`tools.d_recipe.cpu_science_ssh`，5秒实测空闲核、真实父进程/UID/start/cgroup/deadline和独立CPU预留，不伪造Slurm身份；超出范围才使用合规sbatch。管理并核验自有子树退出。
4. CPU transport的scientific_configuration引用GPU实际runtime.json快照，入口只把phase改为cpu，保留原输入/结果绑定；实际CPU节点、根目录、RAM/本地/共享future和reservation_ids在另一份transport中独立登记。新统一Guard使用这份CPU预算，不消费原GPU作业身份或旧预留。CPU线程按真实亲和性及原cpu_threads上限取较小值，另记cpu_threads_effective，模型/划分/内层预算不变。GPU UUID、健康、目标字节/inode、UID与跨窗口预留仍在启动时准入；全部新结果、临时序列化、保留H0均登记。
5. 原执行器逐cell保留模型/预测，关闭cell直接续用；统计按已有文件续接。A不重拟合或重新抽样，缺H0时报错而不增加编码器前向。11-25规则继续：工程失败修复后续同一未完步骤，不记科学失败；仅同根因科学/方法失败按任务书计数。没有删除或额外科学臂授权。

## 配置必须绑定的来源

| 键 | 实际来源或固定约束 |
| --- | --- |
| current_best | 全部关卡后最终FROZEN的configs/d_recipe/CURRENT_BEST.json |
| readout_configuration | 实际选定9M seed0配置；D-R0对应9M-D-R0，其他最终臂对应9M-D-final；保留原run/output/reference_manifest/store |
| library | 与最终CURRENT的D20/L1/L2相同，不用R3分数再选库 |
| descriptor_manifest | 阶段0已接收、所采纳库的开发清单；D20使用原复制清单，新库使用原开发导出；不重新筛列或拟合 |
| d3_manifest | /share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/merged/manifest.json |
| training_view / normalizations | 原D20/D3字段注册及11-07全TRAIN参数来源，不用A1残差作直接化学特征 |
| capacity_policy | total_params_matching；解析最近正整数隐藏宽度，报告参数差额，不扫宽度 |
| mlp_descriptor_value_source / lightgbm_descriptor_value_source | 在开跑前明确写定raw或frozen_train_standardized的既有输入口径，不按下游成绩选择；标准化只消费原TRAIN仿射参数，不重新拟合或截尾 |
| output | 本次选定9M的独立控制目录；不得写回旧3M结果 |
| cpu_threads | CPU阶段线程上限；实际SSH亲和性较小时仅下调执行线程，并记录cpu_threads_effective |
| phase | 先gpu，原GPU cells关闭后改为cpu，其余绑定不变 |

七任务和划分由原protocol.scored_tasks、dev_panel_v3及原packed成员读取，不另传任务子集。成员按(dataset, member_uid)连接，保留每成员原几何。完整15751开发D3已闭合，QM9为native_only，ExpansionRx为用户批准的B6固定原坐标补H；不生成构象。分子向量只附六项D3，逐原子SASA不混入向量。

## 关闭与交付

GPU阶段状态为GPU_DEVELOPMENT_READOUTS_COMPLETE_WAITING_CPU；只有原CPU执行器写COMPLETE及scores.json后才可报告A/B/C完成。A、B_MLP、B_LightGBM、C及composition_ridge逐任务结果进入最终报告；C对两种B的区间只消费原对齐的1000次分子bootstrap，不触发配方选择或新种子。

最终基准由原基准窗口执行。最终采纳库/终点冻结后追加STATUS交接，保持其封存S′ UFF、终点与协议；开发A/B/C完成不等于最终C1完成。原D20/L1基准绑定UNRESOLVED及L2源完成/接收pending的事实继续保留。当前无需重复读取已闭合科学数组或重做既有测试。

实现位置：[development_panel](../../tools/d_recipe/development_panel.py)、[描述符读出](../../tools/d_recipe/dev_descriptor_readouts.py)、[C1 LightGBM](../../tools/d_recipe/dev_lightgbm.py)。已有270项新逻辑验证含本管线；本次仅整理执行衔接，没有新增模型/数据/指标逻辑，完整回归仍只在最终PR前一次。


