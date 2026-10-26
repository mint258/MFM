# 双集群与主数据线实际进度（脚本生成）

观测时间：2026-10-26T00:27:59.067626+00:00

## 目的

落实用户新增 alpha 集群授权，记录主集群已闭合工作及仍需通过的科学门槛。当前集群没有金钱计算费用；分配核时仍用于效率验收。

## 输入与哈希

- `raw`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/raw/sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/receipt.json`；4626 B；SHA256 `048dda8b56cc1ba91cf95e488c94f5bc88ecae1e71269db9e29b809a844cd9b2`。
- `shard0`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/auto_memory_v1/shard_00/manifest.json`；96380 B；SHA256 `dc17172def8719654889f0013b342312b3773cf037623bcd775fe34f393ecf53`。
- `shard0_resource`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/auto_memory_v1/shard_00_resource_observation/closure.json`；7322 B；SHA256 `b8ab389e1972563bc2175ade2ade3a625eb1895f0018b9f8e896bdca567cfe15`。
- `frame`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json`；766822 B；SHA256 `36732244c5bcdaddfec9e22be847f3244076fdb3594d0ab8a663fbc9b3b91725`。
- `frame_run`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/run/run_closed.json`；22422 B；SHA256 `8e5357a490ed25104243216da057e71d3499c79d04983d5fd4e793bcff5c908d`。
- `retention`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/pprime_retention_v1/cpu_auto_memory_20261026_v2/stage_receipt.json`；2613 B；SHA256 `221b0d2ae697f745b1fb3066453d20090aefb62f6c3daa5329b4fd84fdb14054`。
- `secondary_environment`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_cluster_20261026_v1/offline_environment_1884762.json`；1868 B；SHA256 `0bbf0a5afd129728e2dd6d991c2118305ce056848018d99a791f4805cb681f7b`。
- `primary_authority`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/user_cpu_auto_memory_20261026_v1.json`；3196 B；SHA256 `25c1b2f301ce2b07aa8eb57db9b406e003bf97f76aa5d50e2186b75317713fdc`。
- `secondary_authority`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/secondary_cluster_user_authorization_20261026_v1.json`；1616 B；SHA256 `bcd8ef0d83b84645b2fa9fe99dcf5d24ce5fc89ed9879761fc9bd76868772604`。
- `source_check`：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_all_new_sources_check_20261026_v1.json`；177 B；SHA256 `02c7f7fa70d67562d299dbc61d938c656e669d52467fb32dc89de5460a7eff06`。

## 规则与参数

Main CPU 分析节点为实际 cpu 分区2、8–19；S′/UFF/QM 11–19。Alpha 实际 CPU 分区1、3–6、sonmi1。每任务16CPU、最长48h、CPU-only；SBATCH 不指定内存或 exclusive，保留实际RSS/可用内存观察和200GB存储余量。两集群按端点、UID及实际job分别记录。UFF/QM配方、ROUTINE整分子VAL及除Se外的阈值不变。

## 脚本计算的实际统计

```json
{
  "pubchem_cid_smiles_records": 124857440,
  "pubchem_gzip_crc_full_eof": true,
  "pubchem_source_parts": 500,
  "first_label_source_files": 127,
  "first_label_canonical_task_rows": 9827994,
  "first_label_allocation_parent": "4521118",
  "first_label_output_bytes": 30636144,
  "first_label_peak_rss_bytes": 4708581376,
  "retained_frame_cases": 72,
  "frame_measurements": 72,
  "frame_contradictions": 15,
  "frame_execution_errors": [],
  "same_geometry_controls": 16,
  "retention_counts": {
    "original_pairs": 2000,
    "source_rows": 2000,
    "original_frozen_audit_records": 20,
    "stable_full_hits": 23,
    "union_records": 42,
    "required_full_raw_calls": 504,
    "engine_parquet_independent_readback_records": 42,
    "new_UFF_QM_calls": 0
  },
  "secondary_environment_status": "READY_FOR_GOLDEN16_COMPATIBILITY_TEST",
  "secondary_environment_actual_job": "1884762",
  "secondary_actual_versions": {
    "executable": "/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/bin/python",
    "lmdb": "1.7.5",
    "numpy": "2.2.6",
    "pyarrow": "17.0.0",
    "python": "3.11.14",
    "rdkit": "2025.09.5",
    "scipy": "1.15.3",
    "torch": "2.5.1+cpu",
    "torch_cuda_build": null,
    "torch_geometric": "2.7.0",
    "toy_numpy_svd_passed": true,
    "toy_pickle_tensor_PyG_float64_exact": true,
    "toy_rdkit_parse_atoms": 3
  },
  "source_check": "PASS"
}
```

选定阶段的实际主集群父任务如下；本表不是全项目总成本，RUNNING耗时只是本次快照。

|Job|状态|退出码|分配秒|CPU|节点|
|---|---|---|---:|---:|---|
|4521092|COMPLETED|0:0|170|16|compute-0-12|
|4521093|COMPLETED|0:0|834|16|compute-0-13|
|4521094|COMPLETED|0:0|139|16|compute-0-12|
|4521110|RUNNING|0:0|5131|16|compute-0-17|
|4521118|COMPLETED|0:0|434|16|compute-0-13|
|4521124|FAILED|3:0|135|16|compute-0-14|
|4521125|FAILED|1:0|36|16|compute-0-15|
|4521129|COMPLETED|0:0|64|16|compute-0-15|
|4521130|RUNNING|0:0|327|16|compute-0-12|
|4521131|RUNNING|0:0|324|16|compute-0-14|
|4521132|RUNNING|0:0|324|16|compute-0-18|

## 异常与处理

原72项frame试验全部执行留存，但原15个协变准则失败仍保留；不放宽容差、不将READY或解析完成称作PASS，2000/full P′ QM保持HOLD。新只读诊断将核查实际输入几何与原生打印精度。retention首次4521125因共享父目录缺失失败；只修复该目录，采用新输出4521129成功，旧失败和成本保留。Alpha首次两次环境构建失败记录保留，离线安装1884762完成；只达到软件兼容测试准备状态。

## 已知限制

PubChem 124M原始行清点不是化学筛选、去污染或候选池。标签首分片不是完整1.5或D4；共同人群、单位/原生精度/数组shape及TRAIN-only统计仍未定稿。Alpha软件环境就绪不代表16个真实科学控制通过，也不代表已生成正式新数据。S′恢复仍按真实终态判断，不依据进度快照声明完成。D1模型共同签认及D1–D7、ordered10M、第一批2.5M实际生成仍未全部完成。

完整机器证据：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_main_actual_progress_20261026_v1.json`；本报告生成器：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/secondary_main_progress_v1.py`。
