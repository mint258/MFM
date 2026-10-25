# CPU 数据线实际进度与成本

观测时间：2026-10-26T03:28:26.505775+08:00。本报告仅从小型来源/回执元数据生成；科学数据正文没有在登录节点读取。

目的：核对有限 CPU 分析试点、保存失败和超时成本，避免将进程成功当成 v1 最终验收。

输入及其完整 path/bytes/SHA：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/owned_accounting_cpu_queue_20261026_v1.json`；以下元数据引用由同一脚本核验。

```json
[
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/partial_pilot_audit_v1/audit_v1/audit_report.json",
    "bytes": 37509,
    "sha256": "9fb99edd7fb447949be3d2e7e113c30d4fc8e5529ab83864aa79f4934cdf21a2"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/partial_pilot_audit_v1/audit_v1/cohort_report.json",
    "bytes": 24013,
    "sha256": "f4b713d8337796da5a22bb4d415214d6057d61790ff699ce9c35594c88775e56"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/size_rho_v1/dv1_size_rho_cpu_v2/manifest.json",
    "bytes": 10261,
    "sha256": "376b08edbcb265542857c49efc2d9d34c6a25d051b4935458381cc1fb837e524"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/cpu_analysis_v1/write_actual_report_v3.py",
    "bytes": 10437,
    "sha256": "7429c7af371d0a6a3b17deb2c73ce9a2630cd38a9c52cef2a6671a775bd1d513"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/run_decisions_v4.json",
    "bytes": 2090,
    "sha256": "27590b15716c4caaccd7335758e2dbd2e7e20f1047bd3f770ee858dba8d74fa2"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/cpu_analysis_small_scopes_v1.json",
    "bytes": 149568,
    "sha256": "76cc26d0da07e2ca05af56ad3195c51b3c42591961263c75986399c1498fa221"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/identity/identity_source_pins_cpu_v2/receipt.json",
    "bytes": 225642,
    "sha256": "5f61e0d0d96fd11e8d4c208922c7728c1b2699df5ef597fcac4d5db7f0255c38"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/streaming_v1/reduce_mask_v1_cpu_v3/reduction.json",
    "bytes": 66596,
    "sha256": "2c861533835f26cf2d99131e15e15e9cb28a85a834b05c9f503547754dfb69b0"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/label_cpu_closed_4520564_v3.json",
    "bytes": 2557,
    "sha256": "14907cf6bc6b156a08b43bc8e30caec8fb1fbcc6f7e7dce539e01f0be890a1a1"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/vector_frame_audit/prepared_cpu_v4/prepared.json",
    "bytes": 31628,
    "sha256": "2174920c5c32948d4dc48828522dde38265c3ea5517b9fbdae372504ab5f472c"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/diagnostics/candidate_feature_eval_v2/receipt.json",
    "bytes": 35917,
    "sha256": "58b0faebcd403961e1c9cbd05b43bf62c4b3620b95bd78020a39f8231f1bff5f"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/formal_resources_cpu_v11.json",
    "bytes": 169066,
    "sha256": "b2ffa3e65e4170518d971174ce422aeead3b6c633b2176c1887f06193c2be934"
  },
  {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/diagnostics/paired_prefix_cpu_v2/candidate_evaluation/receipt.json",
    "bytes": 7050,
    "sha256": "b7cf68fa4a8089371a9958885d12fde963aa543e82ac75cd25923a7ae59c285b"
  }
]
```

规则：实际 cpu 分区、16 CPU；有限分析使用已登记的实测内存政策和本地 monotonic 监控。正式 S′/UFF/QM 仍要求14–19、64GiB、全部用户声明内存85%，Se唯一科学例外及 ROUTINE VAL 保持。

原 S′ 336 试点4520364为 TIMEOUT，不能用 Exit0:0 代替完成。只读审计为独立任务，不是恢复生成：

- 完整可复用包：334；这些包的科学状态分别为 {"SUCCESS": 102, "INSUFFICIENT_CONVERGED_CANDIDATES": 42, "EMBED_FAILED": 41, "PM7_STEREO_UNRESOLVED": 25, "SOURCE_CONFORMER_GRAPH_OR_ATOM_ORDER_MISMATCH": 33, "SOURCE_SMILES_ATOM_MAPPING_FAILED": 41, "SOURCE_SMILES_GRAPH_MISMATCH": 50}。包完整不代表补齐成功。
- 完整包字节：10578730；闭合包已保存 worker 秒：129637.2584685646，不包括缺包分子的未保存工作。
- 缺包名单见同目录 missing_tasks.json；原包不修改，恢复需独立方案、资源批准和真实联合验收。

尺寸相关性结果：SIZE_RHO_PROVISIONAL_SCIENTIFIC_RESULTS_REVIEW_REQUIRED。129物理目标/146统计分量，16个实际worker每遍；当前原始source TRAIN小试点，不能作为最终共同人群注册表或D4。

去污染来源：CURRENT_BOUND_INPUT_PINS_COMPLETE。来源当前pin成功不代表已导出全部identity、去污染已通过或候选池已放行。

标签精确median/MAD/mask已闭合：4251记录/512分子/146分量；新增mask标签槽总数0，最大单字段新mask比例0.0。TRAIN仅用4211条拟合，VAL20/FULL20仅应用冻结阈值。最终共同人群/D4未冻结。

P′只读准备：VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED，72组输入完成；不是QM成功率或参考系科学验收。

PubChem 3CID候选评估保持；完整10k兼容回放4520597已实际完成，8198旧成功全字段不变、753恢复、1049化学排除不变。首轮4520593因320个generic_ring_systems漂移实际FAILED，负面结果保留。详细逐项校验及来源见 docs/expansion/paired_prefix_compat_actual_v1.md；候选池未修改或放行。

正式资源本次符合声明门槛的节点：[]。声明为0的其他作业记为无明确上限，不解释为零占用；未改动他人，未放宽正式条件。

异常：原MAD0共享文件系统心跳失败；原小审计缺partition、第二轮reducer跨主机时间差、EA单进程RSS、vector历史相对路径、候选评估旧quota均保留实际失败与日志。新提交时间取目标节点内存probe时钟，登录时间独立保存，不放宽运行时新鲜度或内存门槛。

限制：共同人群、构象顺序、最终掩码/归一化、P′真实QM、D3/D5/D6及扩充第一批均未最终验收。契约仍draft.3，不能据源代码或小试点伪造最终交付。

本run实际父任务 78 个；当前活动 ["4520959", "4520960", "4520961", "4520962"]；已观测分配核时 76.55555555555556。包括所有失败/超时，步骤不重复计费；ElapsedRaw=0是整秒下取值，不能宣称真实零成本。

| 父任务 | 名称 | 状态 | Exit | 秒 | CPU | 已观测分配核秒 |
|---|---|---|---|---:|---:|---:|
| 4520334 | dv1_routine_roles_v1 | COMPLETED | 0:0 | 23 | 16 | 368 |
| 4520335 | dv1_sb2_prepare_v1 | COMPLETED | 0:0 | 606 | 16 | 9696 |
| 4520341 | dv1_label_owner_prepare_v1 | COMPLETED | 0:0 | 4 | 16 | 64 |
| 4520344 | dv1_label_mask_io_v1 | COMPLETED | 0:0 | 5 | 16 | 80 |
| 4520345 | dv1_pprime_prepare_v1 | COMPLETED | 0:0 | 8 | 16 | 128 |
| 4520348 | dv1_pubchem_raw_v1 | COMPLETED | 0:0 | 282 | 16 | 4512 |
| 4520356 | dv1_x_source_pins_v2 | COMPLETED | 0:0 | 248 | 16 | 3968 |
| 4520357 | dv1_x_regression_pilot_v1 | FAILED | 1:0 | 43 | 16 | 688 |
| 4520359 | dv1_x_stop_diagnosis_v1 | COMPLETED | 0:0 | 3 | 16 | 48 |
| 4520361 | dv1_label_stream_tests_v1 | COMPLETED | 0:0 | 14 | 16 | 224 |
| 4520364 | dv1_sb2_fill_32g_v1 | TIMEOUT | 0:0 | 14425 | 16 | 230800 |
| 4520370 | dv1_label_stream_prepare_v1 | COMPLETED | 0:0 | 8 | 16 | 128 |
| 4520373 | dv1_label_arrow_probe_v1 | COMPLETED | 0:0 | 2 | 16 | 32 |
| 4520374 | dv1_label_stream_profile_v2 | COMPLETED | 0:0 | 34 | 16 | 544 |
| 4520376 | dv1_x_replay_pilot_v2 | COMPLETED | 0:0 | 63 | 16 | 1008 |
| 4520380 | dv1_label_stream_reduce_v1 | COMPLETED | 0:0 | 3 | 16 | 48 |
| 4520382 | dv1_d4_fixtures_v1 | COMPLETED | 0:0 | 2 | 16 | 32 |
| 4520383 | dv1_d7_prepare_v1 | COMPLETED | 0:0 | 180 | 16 | 2880 |
| 4520386 | dv1_label_med_r1_v1 | COMPLETED | 0:0 | 18 | 16 | 288 |
| 4520388 | dv1_label_reduce_med_r1_v1 | FAILED | 1:0 | 1 | 16 | 16 |
| 4520390 | dv1_d7_profile_v1 | COMPLETED | 0:0 | 40 | 16 | 640 |
| 4520392 | dv1_label_reduce_med_r1_v2 | FAILED | 1:0 | 1 | 16 | 16 |
| 4520394 | dv1_label_reduce_med_r1_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520395 | dv1_pipeline_fixtures_v4 | COMPLETED | 0:0 | 27 | 16 | 432 |
| 4520397 | dv1_label_med_r2_v1 | COMPLETED | 0:0 | 14 | 16 | 224 |
| 4520400 | dv1_label_reduce_med_r2_v1 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520403 | dv1_label_med_r3_v1 | COMPLETED | 0:0 | 15 | 16 | 240 |
| 4520404 | dv1_label_reduce_med_r3_v1 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520414 | dv1_x_full_replay_v3 | COMPLETED | 0:0 | 385 | 16 | 6160 |
| 4520422 | dv1_label_med_r4_p32_v1 | COMPLETED | 0:0 | 34 | 16 | 544 |
| 4520423 | dv1_label_reduce_med_r4_p32_v1 | COMPLETED | 0:0 | 10 | 16 | 160 |
| 4520427 | dv1_pubchem_prefix_v2 | COMPLETED | 0:0 | 14 | 16 | 224 |
| 4520430 | dv1_size_fixtures_v1 | COMPLETED | 0:0 | 5 | 16 | 80 |
| 4520435 | dv1_label_med_r5_p32_v1 | COMPLETED | 0:0 | 14 | 16 | 224 |
| 4520436 | dv1_label_reduce_med_r5_p32_v1 | COMPLETED | 0:0 | 0 | 16 | 0 |
| 4520440 | dv1_label_med_r6_p32_v1 | COMPLETED | 0:0 | 17 | 16 | 272 |
| 4520444 | dv1_label_reduce_med_r6_p32_v1 | COMPLETED | 0:0 | 4 | 16 | 64 |
| 4520476 | dv1_cpu_runtime_boundaries_v1 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520484 | dv1_prefix_feature_diag_cpu_v1 | COMPLETED | 0:0 | 195 | 16 | 3120 |
| 4520496 | dv1_sb2_cpu_closure_fixtures_v1 | COMPLETED | 0:0 | 0 | 16 | 0 |
| 4520497 | dv1_label_mad_r0_cpu_v1 | FAILED | 1:0 | 28 | 16 | 448 |
| 4520510 | dv1_cpu_runtime_boundaries_v2 | COMPLETED | 0:0 | 0 | 16 | 0 |
| 4520511 | dv1_label_mad_r0_cpu_v2 | COMPLETED | 0:0 | 22 | 16 | 352 |
| 4520512 | dv1_label_reduce_mad_r0_cpu_v2 | COMPLETED | 0:0 | 15 | 16 | 240 |
| 4520515 | dv1_label_mad_r1_cpu_v2 | COMPLETED | 0:0 | 16 | 16 | 256 |
| 4520516 | dv1_label_reduce_mad_r1_cpu_v2 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520523 | dv1_label_mad_r2_cpu_v2 | COMPLETED | 0:0 | 15 | 16 | 240 |
| 4520524 | dv1_partial_sprime_audit_cpu_v2 | FAILED | 1:0 | 0 | 16 | 0 |
| 4520526 | dv1_label_reduce_mad_r2_cpu_v2 | FAILED | 1:0 | 0 | 16 | 0 |
| 4520527 | dv1_partial_sprime_audit_cpu_v3 | COMPLETED | 0:0 | 2 | 16 | 32 |
| 4520532 | dv1_label_reduce_mad_r2_cpu_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520538 | dv1_label_mad_r3_cpu_v3 | COMPLETED | 0:0 | 16 | 16 | 256 |
| 4520539 | dv1_ea_known_seven_cpu_v2 | FAILED | 1:0 | 13 | 16 | 208 |
| 4520541 | dv1_size_rho_cpu_v2 | COMPLETED | 0:0 | 48 | 16 | 768 |
| 4520542 | dv1_vector_cpu_v2 | FAILED | 1:0 | 37 | 16 | 592 |
| 4520543 | dv1_label_reduce_mad_r3_cpu_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520545 | dv1_feature_candidate_checks_v1 | FAILED | 1:0 | 0 | 16 | 0 |
| 4520547 | dv1_identity_source_pins_cpu_v2 | COMPLETED | 0:0 | 119 | 16 | 1904 |
| 4520548 | dv1_label_mad_r4_cpu_v3 | COMPLETED | 0:0 | 15 | 16 | 240 |
| 4520552 | dv1_vector_cpu_v4 | COMPLETED | 0:0 | 26 | 16 | 416 |
| 4520553 | dv1_label_reduce_mad_r4_cpu_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520554 | dv1_label_mad_r5_cpu_v3 | COMPLETED | 0:0 | 16 | 16 | 256 |
| 4520555 | dv1_feature_candidate_eval_v2 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520556 | dv1_label_reduce_mad_r5_cpu_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520558 | dv1_label_mad_r6_cpu_v3 | COMPLETED | 0:0 | 14 | 16 | 224 |
| 4520560 | dv1_ea_known_seven_memory_v3 | FAILED | 1:0 | 4 | 16 | 64 |
| 4520561 | dv1_label_reduce_mad_r6_cpu_v3 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520563 | dv1_label_mask_v1_cpu_v3 | COMPLETED | 0:0 | 16 | 16 | 256 |
| 4520564 | dv1_label_reduce_mask_v1_cpu_v3 | COMPLETED | 0:0 | 4 | 16 | 64 |
| 4520567 | dv1_ea_known_seven_rss1280_v1 | FAILED | 1:0 | 4 | 16 | 64 |
| 4520570 | dv1_ea_known_seven_io_v4 | COMPLETED | 0:0 | 20 | 16 | 320 |
| 4520593 | dv1_paired_prefix_replay_cpu_v1 | FAILED | 1:0 | 8 | 16 | 128 |
| 4520597 | dv1_paired_prefix_replay_cpu_v2 | COMPLETED | 0:0 | 8 | 16 | 128 |
| 4520608 | dv1_sampling_projection_fixtures_cpu_v1 | COMPLETED | 0:0 | 1 | 16 | 16 |
| 4520959 | dv1_q_checks_20261026_v1 | PENDING | 0:0 | 0 | 16 | 0 |
| 4520960 | dv1_q_sprime_recovery_20261026_v1 | PENDING | 0:0 | 0 | 16 | 0 |
| 4520961 | dv1_q_pprime_frame_20261026_v1 | PENDING | 0:0 | 0 | 16 | 0 |
| 4520962 | dv1_q_pprime_retention_20261026_v1 | PENDING | 0:0 | 0 | 16 | 0 |
