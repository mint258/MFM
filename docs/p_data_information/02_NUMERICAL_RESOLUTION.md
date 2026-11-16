# 阶段2：数值分辨率与等价对照

状态：COMPLETE_WITH_UNRESOLVED_SOURCE_PRECISION。

109字段分别登记了容器、历史转换、打印、SCF/重复计算与方法准确性。pilot MFM4为FP32；原WP5/typed为F64权威。F64容器不等于源计算有64位有效精度；FP32可分的两个数也不能自动解释为可靠的化学差异。没有给字段任意设置统一化学显著阈值。

既有native_frame30在5个分子上的30次真实xTB计算，仅支持原适用范围的参考系结论，不是全域SCF噪声上界。q0偶极旋转/平移5/5；中性四极平移4/5、q+1为1/5。r674保持关闭，历史192个坐标独立输出UNKNOWN不改写。未重复旋转套件或旧QM试点。

已检查原WP5注册Parquet的存在、schema与footer，以及现有canonical.sqlite/typed catalog结构。owner索引有record_id和任务所有者，没有源物理行定位；例示源base_geometry的1607行组/205630记录具有宽record-ID范围。没有把缺少定点定位转成全表标签扫描或新全源索引。后续数值最早可追溯层明确为pilot MFM4，WP5→pilot差值保留暂不可判断。

2B已触发评估：关键能量缺适用计算精度证据。候选只从冻结TRAIN核心按原顺序取前4个有真实差异的分子，每个取冻结配对中重原子RMSD最大的一对，清单见resolution.json。实际调用0：原任务的精确输入几何和逐记录版本/状态链未由现有定点定位恢复；不能将FP32 pilot坐标当作原程序精确输入开展对照。MOPAC原关键词及预期23.0.3已找到，SCFCRT默认1e-4与收紧1e-5的参数依据来自[官方SCF说明](https://openmopac.net/Manual/scf_test.html)；仅参数可恢复不代表整组输入可执行。xTB未把--acc改动冒充单独10倍SCF收敛设置。状态为TRIGGERED_UNRESOLVED_INPUT_LINEAGE，不是未触发，也没有启动空实验。

因此阶段3报告原单位/固定D4幅度与真实覆盖，并明确区分存储层描述和计算可靠性未知。精度未知不阻断其余分析；32案例校准即使以后有结果，也不能提供全域确定误差界。
