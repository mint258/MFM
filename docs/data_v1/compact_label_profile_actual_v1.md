# 紧凑标签扫描的实际小试点

截至2026-10-25 15:20 +08:00，512完整分子／4,251记录的真实源读取及汇总已闭合。没有全人口或最终D4验收。

|实际Slurm父作业|状态／分配|实际墙钟|分配核秒|
|---|---|---:|---:|
|4520370，来源索引准备|COMPLETED0，16CPU/32GiB|8s|128|
|4520373，Arrow实际16进程资源probe|COMPLETED0，16CPU/8GiB|2s|32|
|4520374，真实compact profile|COMPLETED0，16CPU/64GiB|34s|544|
|4520380，逐组覆盖与统计汇总|COMPLETED0，16CPU/32GiB|3s|48|
|4520382，最终归一化流程合成fixture|COMPLETED0，16CPU/8GiB|2s|32|

以上是实际AllocCPUS×ElapsedRaw，不是利用率或耗时预测。最终归一化生产仍要求申请与实际至少16CPU/64GiB；8GiB仅用于不读取科学正文的合成fixture。

真实profile包含TRAIN4,211、VAL20、FULL20记录，16来源组和16个真实worker PID。汇总核对146字段、51,012个量化record/task槽、59,514个含D20/D3槽及ordinal摘要，均守恒。146字段新增mask记录率均为0，未触发>1%停止；8个同分子数量级跳变组保留review，既有失败和NULL收敛保持来源/review语义，不删除记录。

该profile结束时唯一inode输出为11,620,283字节（manifest自己写入前观测值）；不复制正常标签原值。临时TRAIN直方图、压缩mask、审计及异常预览分别保留在外部run。这是偏向较小源文件的有界I/O试点，不能把其压缩率或耗时直接当作全人口保证。

精确float64 median/MAD仍须多轮原源读取，每轮单独Root审查、Slurm提交及计费，不用近似分位替代。当前TRAIN参考在最终common/diagnostic过滤之前，仅用于异常参考和size分析，禁止冒充D4。非标量size相关仍有旋转不变聚合定义、vector/tensor实际参考系和独立偶极模来源待闭合。

新增normalization_v1实现真正的common＋role＋geometry_map＋diagnostic输入门、持久mask/原子序读回、TRAIN元素参考、精确尾分位、逐元素缩尾统计及独立重建。实际fixture发现并通过24项、16个distinct spawn PID；提出范围曾写25，以实际JSON的24项为准，未增加镜像测试凑数。真实冻结输入尚未齐，不发布最终数值或D4完成状态。

## 外部证据

所有路径相对外部run根 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`。原数据和大产物不进Git。

- `control/label_stream_preparation_actual_closure_v1.json`
- `control/stream_arrow_v2_probe_actual_closure_v1.json`
- `control/label_stream_profile_actual_closure_v1.json`
- `control/label_chain_actual_4520380_v1.json`
- `control/final_normalization_fixture_actual_closure_v1.json`
- `artifacts/labels/streaming_v1/profile_pilot_v2/scan_manifest.json`
- `artifacts/labels/streaming_v1/reduction_profile_v2/reduction.json`
- `control/final_normalization_fixtures_v1.json`

脚本为已提交的 `workflows/data_v1_final/labels/streaming_v1/` 和 `labels/normalization_v1/`；各实际提交intent绑定当时源文件精确SHA，后续文档更新不覆盖登记源码。
