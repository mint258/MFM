# Arrow worker资源变体 v2

baseline `b07a67045efbcc7b6f89888eef8317b128589df8` 的19项语义测试已在job4520361实际COMPLETED0，14秒×16CPU＝224分配核秒。该baseline所有.py/config字节保留原样。

静态审阅发现：source worker读取owner_index时使用的 `pq.read_table` 默认可能建立较大的Arrow CPU/IO线程池。新 `scan_v2.py` 只在生产worker initializer增加三行：导入pyarrow、CPU pool设1、IO pool设1。移除这79个字节后，与旧scan.py逐字节相同；输入匹配、mask阈值、NULL收敛、z>20、TRAIN拟合、审计抽样和输出schema完全不变。

精确SHA及重建规则见 `scan_v2_source_difference.json`。新config `streaming_v2.json` 仅新增driver引用和Arrow线程上限；probe还会核对移除这两个键后与baseline配置逐项相等。

`probe_arrow_v2.py` 实际调用这个生产initializer，启动16个barrier同步的真实worker，各自用默认多线程读取接口读取有16个row group的小型合成Parquet。它核Arrow CPU/IO各1、行数、顺序及合计，并记录PID、OS线程数和依赖版本。OS线程含I/O和运行时线程，不把它们都当成CPU计算线程。这个资源probe不重跑19项语义测试，也不读科学label正文。

Root可在自己的16CPU Slurm中运行：

```bash
python -B workflows/data_v1_final/labels/streaming_v1/probe_arrow_v2.py \
  --config configs/data_v1/labels/streaming_v2.json \
  --baseline-config configs/data_v1/labels/streaming_v1.json \
  --output /external/new_arrow_v2_probe.json
```

若Root尚未生成group plan，使用 `prepare_v2.sbatch.in`，只运行资源probe并以新config准备512分子metadata。若baseline group plan已经准备好，无须为线程上限重扫metadata：保留其旧config/owner index/source SHA，Root重新绑定新scan_v2 driver、新config资源说明和全部共享库，使用 `scan_v2.sbatch.in` 扫描原计划。scope fingerprint与科学参数不变，新的Root intent及实际driver路径提供执行来源。

所有新运行仍受真实account quota、全用户声明内存、16CPU、64GiB扫描预算和200GB余量约束；不借用构象试点的其他内存例外。没有自动全量提交、没有重写旧prepared plan或旧验收收据。最终common与diagnostic仍未绑定，D4继续未完成。
