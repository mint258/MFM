# 提速线执行结果（2026-11-18）

**本轮没有可采纳的提速开关，建议全部关闭；有效组合为空，代码收益1.00×。** 按补充指示在同一张3090上完成S0–S8必做实测，固定M2/A1+B3+B4、B32、FP32、TF32关闭。S8空组合实测1.04052×，其约4%的计时变化不能归因于新开关。[一页GPU结果](GPU_RESULTS_20261118.md)包含逐项吞吐、倍数与验收结论。

S1短训练失败；S2/S5通过B验收但未达到单卡5%门槛；S3及S4两个模式未通过B3梯度门槛，其中encoder_heads短训练也失败。S1仍126.03次同步/步，S6不适用。S7全部12格完成，最快比4核/14读进程仅高0.34%，未显示明确加核收益；此结论仅适用本次3090/M2早段，不外推零同步或其他卡型。5090/4090可选补测未执行。

## 最终完整回归

4535749，node16、真实16CPU、非exclusive，原生Slurm退出1:0，Elapsed1452秒。**194模块、3655项：3629通过，24跳过，2失败，0错误。** 所有模块本次重新执行，没有retained_from，没有复用前一轮全回归。test_execution.py的13项与test_disk_guard.py的4项全部通过；wire模块26项全部通过。

两项失败与原CPU阶段相同，均不修改既有科学路径来消除：

- test_p_recipe_exclusion：保留的旧测试仍引用已按用户决定移除的tools/p_recipe/refit_d4.py，触发FileNotFoundError；不恢复废止D4。
- test_phase1_initialization：未改动的初始化/归一化代码在meta设备上触发Tensor.item RuntimeError，测试期待ValueError。相关源文件及既有测试不在本分支变更范围内。

原始XML/log完整保留于/share/home/zixiao/descriptor_analysis/.perf_sync_scratch_20261117/final_regression_20261118/；汇总为results/perf_sync/final_regression_20261118_summary.json。此前回归与CPU输入验收均保留，不覆盖原始输出。

最终仓库检查4535779通过（0:0/7秒）：9656文件、1994 Python文件、1309份冻结服务器源码校验，0错误。此前4535753因本次原始JUnit XML超过2MiB源码限制而失败（1:0/7秒）；将未跟踪的原始输出按同文件系统重命名保留至scratch后复查通过，没有重跑测试、修改检查器或删除历史资产。首次失败保留final_repository_check_20261118_attempt1.json，最终结果为final_repository_check_20261118.json。此检查基于完整运行源码和规范Git索引的部分检出，未下载历史非运行大资产，不能当作完整GitHub CI全绿。

## 输入与科学协议

S1/S5复用已通过的真实CPU输入验收：各1000批分子/构象与逐批RNG一致、前20批原输入张量/标签/mask一致。S1新增传输元数据perf_sync_layout排除于原输入比较，原FAIL及更正记录均保留。GPU逐位不一致按任务书转B，不用CPU输入通过冒充GPU A通过。

全部新增开关默认关闭；每条最多1000实际优化更新，测速100次无优化更新预热后恢复RNG。科学预算/LR分母、标签、mask、归一化、采样及全部既有FP64预处理不改，不做完整训练或下游评价，不改其他三线配置/分支/任务，不启动9M。

## 基础设施与资源

GPU原生预约4535718 FAILED/4001秒、4535744 FAILED/8533秒、4535772 COMPLETED/504秒；同一3090 UUID固定。前两次为临时目录竞争、剖析临时副本超过20GiB保护；后续只续做未完成部分，未重跑已完成测量。S0/S1及失败partial trace无损gzip保留，梯度/CSV和失败训练输出保留，导出预留12GiB。当前合计scratch约10.57GB，源/报告3GiB与scratch20GiB上限、实际字节/inode/UID quota和root系统余量继续保护。node21未用、非exclusive、无数据或检查点复制。

GPU预约累计3.6217卡时，对应76.9089分配CPU核时；本次最终回归6.4533核时，此前CPU阶段7.4567核时，两次最终检查共0.0039核时，合计已记录90.8228核时，原生调试未计量。未使用付费学校集群。

此前已核对的合并GitHub CI203项=历史202项+主线b8685bb新增noise_seed1硬件CSV的1项，提速分支新增0项；最终提交的检查记录与错误集合归属见PR13说明。没有修改检查器或删除历史资产。[草稿PR13](https://github.com/mint258/MFM/pull/13)保持未合并，9M开关由用户在交付后决定。
