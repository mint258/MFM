# ExpansionRx 的评分口径

在本次九终点拟合前固定以下口径。数据为官方公开释放，revision `6b898ccc43d10d25b230fb09e22a6e30c30022b5`。B0 原 TRAIN / TEST 成员按 Molecule Name 与完整原始 InChIKey 绑定；原始 TRAIN 标签保留，新增 TEST 标签经统一 B0 补充入口读取。没有新增 raw-only RLM 终点。

B1 一次性任务筛选使用计划书 §2.2、§4.3 的 RAE：原始目标单位，相对该次拟合 TRAIN 标签的算术均值。RF、LightGBM、Chemprop 都拟合相同原始标签；Chemprop 仅在 TRAIN 上标准化回归目标并在预测时还原。域外 TEST 用该 TRAIN 均值，九终点的有限 TEST 标签全部保留。

官方榜单指标另列：LogD 原尺度，其他终点按官方函数先截断负数为零再作 log10(y+1)，RAE 分母为转换后 TEST 标签相对其均值的绝对偏差。MA-RAE 为九终点 RAE 的等权平均。来源为 [官方 utils.py](https://huggingface.co/spaces/openadmet/OpenADMET-ExpansionRx-Challenge/blob/b52c9475126776c38edf3c6d6ab2ff671683c90d/utils.py)；该指标不代替 B1 的 TRAIN 均值规则。原始预测保存供最终报告消费者生成官方尺度结果，不重新训练或重定义标签。

本线置信区间遵循用户要求：1000 次、完整分子分组、模型间配对；这与榜单网站按行抽样的误差条实现有所区别，报告时明确标注。官方尺度的点指标及宏平均由 `expansion_metrics.py` 生成；该模块没有任务去留功能，7 个新逻辑测试已通过。

C1 保留全部盲测记录。域外为 TRAIN 均值预测；域内原生 D / P′ 完全缺失的点保留空预测和原因，不能用填补伪装为完整榜单结果。仅原生特征可用的诊断结果会明确标注有效点数和未完成的官方覆盖。
