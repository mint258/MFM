# 七例电子亲和能的原生上下文诊断

目的：复核既有极端EA的同记录SP/VIPEA上下文，不重算QM，不改标签或mask。

输入及完整哈希：

```json
{
  "diagnostic": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/ea_diagnostic_v1/dv1_ea_known_seven_io_v4/diagnostic.json",
    "bytes": 5947202,
    "sha256": "ca5efbbf9ad9a61491b2dfbfff9225f584fa53cf5b5c1f10069ca86fce648855"
  },
  "config": {
    "bytes": 12783,
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/requests/dv1_ea_known_seven_io_v4.run_actual.json",
    "sha256": "eebd5eaf842bc8703ea0826e15a9b7a545d3c9f191672681a392088b3c7e169b"
  },
  "monitor": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/cpu_analysis_guards/dv1_ea_known_seven_io_v4/closure.json",
    "bytes": 2011,
    "sha256": "5fc8ccaf78ff1bef882e540a58e3689bae3ba87894b8b5d3a29e58fb97571913"
  },
  "summary": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/ea_closed_compact_v2.json",
    "bytes": 28097,
    "sha256": "e370a9a3f8e87f642d1d280950c276ba350bd889a9ff54fc537127c108658883"
  }
}
```

规则：严格原canonical owner/record/task/lane；7例、14上下文、6原源文件、16实际worker。读取列、筛选逻辑和xTB参数保持；SP GFN2与VIPEA GFN1不是同一方法，不能将跨方法能量或gap符号直接当成失败证据。

实际父任务4520570：COMPLETED/0:0，20秒×16CPU=0.08888888888888889分配核时。中央monitor无内存denial且证据完整导出。

句柄打开/关闭=96/96；复用=5560；每worker同时最多1个handle，最终全部关闭。worker最高RUsage RSS=385368064B，低于本次1280MiB内部上限。原失败与真实超限证据保留，未进一步提高预算。

| record_id | EA/eV | IP/eV | SP gap/eV | SP原子电荷和/e |
|---|---:|---:|---:|---:|
| principal_01200001_01500000.lmdb:401413 | 8791.0184 | 6.817 | 2.2735556700000004 | -9.999999955705163e-09 |
| principal_01200001_01500000.lmdb:411535 | 8791.0184 | 6.817 | 2.2735556700000004 | -9.999999955705163e-09 |
| principal_00000001_00300000.lmdb:94634 | 5737.3021 | 9.5536 | 5.886257630000001 | 1.9081958235744878e-17 |
| principal_00600001_00900000.lmdb:1070786 | 5633.8674 | 9.0408 | 4.700989700000001 | -2.7755575615628914e-17 |
| principal_00000001_00300000.lmdb:25895 | 5545.9323 | 10.0017 | 4.27039099 | -1.999999998253399e-08 |
| principal_01200001_01500000.lmdb:236073 | 5457.6039 | 8.7776 | 3.76461778 | -1.0000000057186487e-08 |
| principal_00000001_00300000.lmdb:12191 | 3308.3762 | 10.635 | 4.780350240000001 | -2.7755575615628914e-17 |

原生状态/收敛元数据逐条保留：

```json
[
  {
    "record_id": "principal_00000001_00300000.lmdb:25895",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 13,
    "failure_code": null
  },
  {
    "record_id": "principal_00600001_00900000.lmdb:1070786",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 11,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:236073",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 12,
    "failure_code": null
  },
  {
    "record_id": "principal_00000001_00300000.lmdb:94634",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:411535",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:401413",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:411535",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 16,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:401413",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 16,
    "failure_code": null
  },
  {
    "record_id": "principal_00000001_00300000.lmdb:12191",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_00000001_00300000.lmdb:94634",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 12,
    "failure_code": null
  },
  {
    "record_id": "principal_00000001_00300000.lmdb:12191",
    "calc_type": "xtb_singlepoint",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": true,
    "scf_iterations": 13,
    "failure_code": null
  },
  {
    "record_id": "principal_00000001_00300000.lmdb:25895",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_00600001_00900000.lmdb:1070786",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  },
  {
    "record_id": "principal_01200001_01500000.lmdb:236073",
    "calc_type": "xtb_vipea",
    "status": "SUCCESS",
    "source_status": "SUCCESS",
    "converged": null,
    "scf_iterations": null,
    "failure_code": null
  }
]
```

原始输出证据分类：{"CANONICAL_RAW_NOT_RETAINED_OR_NOT_PRESENT_NO_SCF_FAILURE_INFERENCE": 14}。实际找到0份canonical原始输出；未保留或不存在不能推出SCF失败。

异常与限制：最大EA8791.0184eV的异常值保持原样，根因仍UNKNOWN。当前注册的VIPEA wire没有足够的中性/阳离子/阴离子能量和电荷阶段证据；不从绝对能量大小或跨方法差值推断零能量、错误电荷态或不收敛。约390条SUCCESS+NULL的全人口计数未重建，本结果不是全人群扫描或最终mask规则。没有新QM调用或新增mask。

复算脚本：workflows/data_v1_final/labels/ea_cpu_v2/summarize_closed_v2.py；只读取已闭合结果元数据及会计信息，不读取原parquet/SQLite，不启动科学任务。
