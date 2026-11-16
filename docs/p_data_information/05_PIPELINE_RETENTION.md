# 阶段5：同一物理记录到实际输入的差值保留

状态：COMPLETE_WITH_EXPLICIT_UNRESOLVED_VECTOR_FRAME。新训练0、GPU0；2B实际新增8次PM7单点，未额外跑原设置、未改生产代码或参数。

按MID/native_record_id连接，使用实际共同GID的source_to_M验证原子映射；不将两个导出的局部索引直接相等。只检查冻结面板。

|角色|pilot→当前同物理记录|原子映射明确|身份缺失/歧义|当前D5/k10排除|
|---|---:|---:|---:|---:|
|TRAIN|39220|39220|0|0|
|VAL|3741|3741|0|0|

原始WP5图标量与坐标无关原子/pair标量F64已按登记定位恢复；源输入参考系集成生产者连续两次实现故障，依任务书“单项修复累计4小时或连续失败2次后记为未解决，继续独立部分”不再重试。失败是导入/缓存父目录封装问题，不是源数据本身无定义的证据。原始向量全量处理链保留未知，pilot层proper对齐统计与既有参考系审查保留。原子映射和native base缓存成功部分另存，独立的原子/pair标量读取继续完成。

原生TOTAL ENERGY与生成热包含不同项，不能仅按单位换算/元素常数视为相同性质，定义见[原生能量说明](ENERGY_DEFINITIONS.md)。

原始标量通过单次F32 cast与历史pilot逐记录核对；下列为原始非零数值差变为pilot零差的计数，不是可靠物理信息损失率：

|角色|字段|原始非零对→pilot零对/原始非零对|原始单次F32 cast匹配pilot记录|
|---|---|---:|---:|
|TRAIN|P.pm7_B.r83.value|414/23432|39220/39220|
|TRAIN|P.xtb_singlepoint.r670.value|89/23448|39220/39220|
|TRAIN|P.pm7_B.r60.value|1/23447|39220/39220|
|VAL|P.pm7_B.r83.value|42/2260|3741/3741|
|VAL|P.xtb_singlepoint.r670.value|8/2262|3741/3741|
|VAL|P.pm7_B.r60.value|0/2262|3741/3741|

核心/富集、近似重复/明显几何差异、分子等权率、消失差值的原单位分布见comparison_supplements.json与original_local_information.json。源程序打印/计算精度不足的部分仍不作物理显著判定。

当前D6→实际CPU准备调用现有collate/prepare/unpack及真实物理头元数据，不构造神经网络、不前向、不优化。原子序数/几何、数值、联合向量mask与有向pair端点逐项比较；实际源码快照见retention.json。数据mask、loss_enabled、有限值和联合物理向量掩码分开。总计检查结果：

- prepared_numeric_change_records: 0
- prepared_mask_mismatch_records: 0
- prepared_pair_endpoint_changes: 0
- unmasked_nonfinite_raw_leaves: 0
- unmasked_nonfinite_normalized_leaves: 0
- loss_disabled_record_targets: 0

native base F64容器→pilot坐标cast的所有42961条记录均可由已登记原子映射连接；native已有不同存储坐标的冻结对没有在这一步合并。pilot→D6与实际CPU准备也未观察到新的清洁/扰动坐标合并。该结果不替代未完成的全量原程序输入/向量参考系链，也不声称存储坐标不同即物理不同。

下表列生成热与出现其他数值变化的字段；完整逐字段分母/核心富集率见retention.json。原始→pilot、pilot→当前和归一化各段分开：

|角色|字段|pilot非零→D6零/非零对|D4非零组件→零/非零组件对|pilot零→当前非零|距离差最大绝对改变|
|---|---|---:|---:|---:|---:|
|TRAIN|P.pm7_B.r60.value|0/23446|0/23446|0|0|
|TRAIN|P.pm7_B.r73.value.sigma|0/23448|0/23448|0|2.83372e-08|
|TRAIN|P.pm7_B.r73.value.pi|0/23448|0/23448|0|3.82506e-09|
|VAL|P.pm7_B.r60.value|0/2262|0/2262|0|0|
|VAL|P.pm7_B.r73.value.sigma|0/2262|0/2262|0|2.55451e-08|
|VAL|P.pm7_B.r73.value.pi|0/2262|0/2262|0|1.41889e-09|

r73历史pilot先将通道变F32再聚合，当前D6可从原F64聚合后单次cast；小幅新差异不自动指认为当前数据错误。原始r73标量复用已发表纯sigma/sigma、pi/pi F64左折叠，保留方向、onsite与重复项，不另造pair标签。缺失不填0。

跨组分保持原首个允许物理记录；若当前k10不暴露则不可比较，不换一条构象。同式中在前后完全相同的共同有效构象集上比较中位数，避免把样本更换误计为量化损失。最初局部索引排序汇总只保留为外部探索性历史，正式结果见graph_pipeline_retention.json。纠正所需额外图标量定点读取数如实列在该文件，不新增物理成员。

2B同一批输入的已启用能量字段，还直接展示“大绝对值误差小”不等于“小差值无损”。下表相对改变为差值相对误差，不是原始大绝对能量相对误差：

|固定分子|字段|原F64差|F32后差|差值相对改变|收紧SCF的差值改变|
|---|---|---:|---:|---:|---:|
|principal_00515644|P.pm7_B.r60.value|0.24186|0.241859|2.33178e-06|0|
|principal_00515644|P.pm7_B.r83.value|0.01826|0.0181885|0.00391695|0|
|molecule_03822896|P.pm7_B.r60.value|13.2917|13.2917|2.09761e-07|0|
|molecule_03822896|P.pm7_B.r83.value|0.08509|0.0849609|0.00151678|0|
|molecule_03806715|P.pm7_B.r60.value|1.08116|1.08116|3.77673e-07|1.77636e-15|
|molecule_03806715|P.pm7_B.r83.value|0.01036|0.0102539|0.0102407|0|
|molecule_01623775|P.pm7_B.r60.value|0.01305|0.0130539|0.000298394|1e-05|
|molecule_01623775|P.pm7_B.r83.value|0.00088|0.000976562|0.10973|0|

相同存储值与相同组成经确定的D4/A1仿射处理不能恢复非零差；正常可逆尺度/元素参考改变与量化、掩码和错配分开。source_scalar_authority.json逐项给已有D4/A1组成分量与残差，未新增拟合。各有符号原始差的全域物理可靠性未建立，所以可靠物理符号翻转率仍null、分母0；以上仅为数值方向/设置敏感性证据。
