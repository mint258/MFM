# A3：B4 惩罚项的实际大小

依据 USER_DIRECTIVE_20261122B 第4节A3。仅对T2同一条9M训练的1M、3M、6M、9M已有完整断点前向；无训练、优化器更新、归一化拟合或gamma重拟合。

## 固定输入和原生算子

使用原PRecipeDataset、dataset_configuration(validation=True)与read_prepared_validation：固定2000个VAL分子、原seed20261112选取及原顺序、每分子原允许构象的第一个。沿用原B32，因此62个完整批次加最后16分子。14个读取进程只初始化VAL角色；read_prepared_validation使用其独立VALIDATION对象，未使用的DATA也不物化TRAIN。

按原训练构造structural与V31PDModel并严格载入整个ModuleDict状态，保留P头、PMA、A1标签定义、启用字段和原准备输入路径。FP32、TF32关闭、重算关闭、eval模式。B4对每批全部原子的第6层H0计算，而非mean(H)：每维总体标准差（unbiased=False）的gamma铰链均值，以及非对角相关平方均值。gamma直接取原T2配置。

P分母复用pd.predict/pd.loss；T2实际采用grouped_fields分支，对counts>0的字段loss取等权均值。新入口仅接受该原分支；未知family/uncertainty/multiplier变体拒绝进入。penalty_statistics的P与B4重组由CPU测试直接对原p_recipe_training.train内部calculate的实际AST比较。原科学文件不修改。

## 汇总口径

逐批保存原生FP32的hinge、decorrelation、B4、0.1*B4和P。CPU节点以F64、按该批实际分子数加权汇总；主比值为sum(n*原生0.1B4)/sum(n*原生P)。P为零时报告未定义，不加人为分母下限。末批16分子保留原分批并按16加权。

A3.csv只报告固定VAL的描述值，不含CI。逐批数值、原分子索引和实际构象索引完整保留。I2条件只计算9M主比值/1M主比值是否≥2；该条件不自行改变配方。若触发，I2初始150k分母政策另按原未决项明确；若比值未定义，明确未定义。

## 续接和生命周期

每个原生批次写入原子JSON，绑定断点路径/字节/mtime、固定人口和已完成批次前缀。续接严格跳过已完成前向；每来源完成后封存。GPU只产出原生逐批值；F64汇总和I2条件在CPU8–19上首次计算。没有特征数据库或大型缓存。

普通sbatch、16CPU/14读进程、非exclusive，GPU仅0–7的空24GiB。GPU6在本线F1队列完成后进入；实际UUID锁、节点/显存/磁盘/RAM/同行future准入仍在启动执行。原样resident/lifecycle监督、真实TimeLimit、提前900秒停止新批次并关闭pool；全部自有worker显式join/reap。所有原权重、输出和成本保留。
