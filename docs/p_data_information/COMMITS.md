# 分阶段交付记录

工作分支：`docs/p-data-information-20261115`。起点为已发布的任务书计划提交27484f89b722abdf0de0ec40abfac847b3bdf49b，冻结科学来源p-recipe@5b42908d364e84e39bf384b19a5c6ab08d13ab63、data-v1@bc47699c709f57bb00108473f17bf4652333d2ec。未移动其他工作树或修改其在跑任务。

|交付|提交|证据范围|
|---|---|---|
|阶段0方法与范围|[bdd0a85](https://github.com/mint258/MFM/commit/bdd0a85)|冻结来源、真实身份/字段方法|
|阶段0实际统计|[cb84974](https://github.com/mint258/MFM/commit/cb84974)|55k身份/角色与109字段|
|阶段1初始交付|[e263f17](https://github.com/mint258/MFM/commit/e263f17)|几何覆盖有效；原局部索引配对相关结果现为探索性|
|阶段2初始交付|[79b9c40](https://github.com/mint258/MFM/commit/79b9c40)|当时已检查来源/精度未知；后续有来源补充|
|阶段3初始交付|[5cd3e13](https://github.com/mint258/MFM/commit/5cd3e13)|原局部索引配对相关结果现为探索性|
|阶段4初始交付|[b334753](https://github.com/mint258/MFM/commit/b334753)|原局部索引配对相关结果现为探索性|
|阶段1正式物理ID更正|[24dc75b](https://github.com/mint258/MFM/commit/24dc75b)|唯一native_record_id、重编号不变、旧结果归档|
|阶段2正式候选刷新|[b957b92](https://github.com/mint258/MFM/commit/b957b92)|依照正式冻结对刷新2B候选，未新增QM|
|阶段3正式重算|[1c5772c](https://github.com/mint258/MFM/commit/1c5772c)|从相同缓存按物理ID配对重算|
|阶段4正式重算|[6c81c57](https://github.com/mint258/MFM/commit/6c81c57)|联合距离、分层缺失、共同尺度核实|
|原输入/2B来源补充|[65a1713](https://github.com/mint258/MFM/commit/65a1713)|匹配原输入与二进制、8次PM7收紧SCF案例|
|原始图标量与A1|[8cec62d](https://github.com/mint258/MFM/commit/8cec62d)|原F64数值量化、11字段A1实际覆盖与幅度、原生能量定义|

每次交付前均在服务器的独立稀疏源码工作树运行默认`tools/check_repository.py`，检查日志保留外部分析目录。它不包含未检出的大型历史资产，不代表原整仓202项旧错误已清除。科学计算均在compute-0-20、CPU完成。大缓存/物理记录列表未提交Git。

最终阶段已推送：[54b0cb8](https://github.com/mint258/MFM/commit/54b0cb8f6de8052005fcf7e2d55267985220a962)，包含实际CPU处理链、原F64局部标量、结论矩阵与FINAL_REPORT.md。默认仓库检查PASS（642个实际Python文件、errors=0）；科学边界与未解决项见最终报告。

随后文档闭合提交仅记录本提交URL、最终状态与共享磁盘通知，不增加数值任务。
