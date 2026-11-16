# 阶段0：固定来源、成员与物理语义

2026-11-16（Asia/Shanghai）。状态：COMPLETE_WITH_EXPLICIT_UNKNOWNS。

本阶段只读取固定55,000成员的身份、角色、图与注册表元数据，没有读取P数值载荷。分支起点沿用任务书计划提交27484f89b722abdf0de0ec40abfac847b3bdf49b；字段视图沿用其冻结p-recipe来源。

|角色|原分子数|成功连接|当前排除|角色冲突|无法连接|可执行成员|
|---|---:|---:|---:|---:|---:|---:|
|TRAIN|50000|50000|8|0|0|49992|
|VAL|5000|5000|0|0|0|5000|

源formal_record_index中，这55k成员的已保留记录均找到身份，元素计数、形式电荷、连接图签名冲突为0。成员选择继续使用原selection_rank；只应用既有323排除清单中与pilot相交的8项，没有重新去污染。正式QM电荷取注册表实际任务身份，不以形式电荷替代。

启用P字段109项，家族分布：{'charge': 17, 'reactivity': 11, 'energy': 17, 'bonding': 6, 'response': 2, 'off-equilibrium': 3, 'size': 17, 'solvation': 6, 'frontier/IP-EA': 12, 'multipole': 18}。逐字段单位、方法、任务电荷/电子态、环境、几何、源路径与已知代数关系见configs/p_data_information/fields.json。未关闭或启用任何字段。原始精度与程序版本尚待定点证据，明确登记为未知；不能由FP64容器推断。既有参考系UNKNOWN/失败状态保留，不能把源策略ACTUAL_TARGET_CONDITION_SOURCE_ENABLED解释为所有物理校验通过。

可直接复用：母集D5成员与v3.1映射、11-07 D4生产routes和既有A1参数。仅作背景：全人口D7、256分子生成热、512分子异常试点、P0总体相关与A阶段训练；都不作为本面板的数值结论。源输出精度、实际冻结结构对的对齐和处理链保留尚未覆盖，留待阶段1–5。

外部完整成员与状态：/share/home/zixiao/descriptor_analysis/runs/p_data_information_20261115_v1/mother_metadata.json。已发表大文件hash仅引用，未重算。生产者检查了成员唯一性、原数量、角色与元数据连接；未添加独立全量验收。

本次身份元数据处理耗时95.6秒，含55000行组的pilot ID-map读取；不是标签读取性能基准。后续几何与数值仍按任务书1–3小时/阶段估计，待首次实际面板读取更新。

阶段1–5现已完成；原始F64补充、8次PM7校准及同记录处理链见FINAL_REPORT.md。阶段0所列“尚待”是当时的证据状态；最终仍未知项按字段保留。训练、归一化、源标签和在跑任务均未变更。

提交前已运行默认 tools/check_repository.py：当前稀疏工作目录 PASS，9399 个 Git 路径、608 个实际 Python 文件、errors=0。该检查跳过未检出的大型历史资产，因此不宣称原整仓202项历史错误已消失。计算节点未安装git，首次检查未运行；改用登录节点执行纯标准库源码检查，数值处理仍只在compute-0-20。


字段集合补充核对：已直接读取固定数据提交bc47699c709f57bb00108473f17bf4652333d2ec的training_view_v1.json（Git已有blob 800cd02bfbdde63c4c8b29e34da2b329cceba90c），与本次实际视图启用P字段逐名一致，均为109项；未新增文件内容hash。


后续语义补充：原生TOTAL ENERGY与生成热并非只差元素常数/单位，见[定义区别](ENERGY_DEFINITIONS.md)。原始F64恢复43个图标量、35个局部标量；原向量全量参考系仍未知。
