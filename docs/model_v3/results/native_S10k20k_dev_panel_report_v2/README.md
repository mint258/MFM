# Saved Native 10k and 20k development panel

The flat CSV contains exactly two actual evaluator runs, vcxcfx54/job4524476 and i59ur33t/job4525060. Each numeric metric column copies its original saved CSV token. Per-task, change and aggregate Markdown tables retain the original 36/18/6 rows. The three original generated CSVs remain under the source run directory, with rejected publication working copies retained after checker5113; no dataset or scientific result was removed.

config_sha256 is the exact raw GPU operator spec SHA, code_sha is the actual evaluator code, and data_version hashes the complete saved data-version value using sorted compact JSON. GPU elapsed seconds are the actual parent518/519s, not CPU plotting times or per-cell jobs. Bootstrap CIs describe saved endpoint normalized improvements; no change CI or pretraining seed SD is claimed. Reference errors differ in seven nonlinear cells, so no common random zero-step point is fabricated. Only seed0 FP32 and inner-TRAIN evaluation are represented.

The v2 source changes plot layout only; all three generated CSVs are raw-byte equal to v1. The original numeric/source/geometry gates are unchanged. No D5, B*, bf16 or formal acceptance is granted by this report.

{
  "run_bindings": [
    {
      "run_id": "vcxcfx54",
      "actual_job_id": "4524476",
      "Root_closure": {
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S10000_dev_panel_GPU_4524476_Root_closure_v3.json",
        "bytes": 610173,
        "sha256": "fbf2e2dea8fb93dfbff46737b8b4b0f1c4d485b9c9f892eeac0eaf21c9c95d82"
      },
      "actual_result": {
        "bytes": 1488340,
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Native_S10000_seed0_fp32_dev9_v2/panel/evaluation/result.json",
        "sha256": "7a5b11f3cbfb952d34284bd4cf1fa01f7f9d85d0e70508d2cfafdbcc20c32861"
      },
      "config_sha256_is_exact_raw_spec": {
        "bytes": 19976,
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Native_S10000_seed0_fp32_dev9_v2/panel/control/launch_spec.public_method_bound_v1.json",
        "sha256": "1b8d00c1a86004a1e400754d98c15a9b83c79f24e35aae4ff4374e9381179204"
      },
      "data_version_canonical_sha256": "545a3dda5d6c4558477b8dc1b0d29e1d66dc6e5d1da34e8d82f115b5092aa865",
      "raw_data_version": "selectedTRAIN-v1-f92a0cbe9b064fe7-294e051ead61b232"
    },
    {
      "run_id": "i59ur33t",
      "actual_job_id": "4525060",
      "Root_closure": {
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S20000_dev_panel_GPU_4525060_Root_closure_v1.json",
        "bytes": 616038,
        "sha256": "3605a8cfef566ada7377f757f3d8d46a67c15364345502aea12af77cb84fab11"
      },
      "actual_result": {
        "bytes": 1488178,
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Native_S20000_seed0_fp32_dev9_auto_v1/panel/evaluation/result.json",
        "sha256": "b018ce20c61c0dd4122c318a4b6287d79e793445520a8cda4f391a4fc0aca4f2"
      },
      "config_sha256_is_exact_raw_spec": {
        "bytes": 15863,
        "path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Native_S20000_seed0_fp32_dev9_auto_v1/panel/cpu_prepare/launch_spec.json",
        "sha256": "3fd35cda581c6c93161afd5f97663299f23763f441cc81b8d28be213e9d02096"
      },
      "data_version_canonical_sha256": "545a3dda5d6c4558477b8dc1b0d29e1d66dc6e5d1da34e8d82f115b5092aa865",
      "raw_data_version": "selectedTRAIN-v1-f92a0cbe9b064fe7-294e051ead61b232"
    }
  ],
  "column_prefixes": [
    {
      "prefix": "cyp_2D6_linear64_relu",
      "task_id": "cyp.2D6",
      "readout": "linear64_relu",
      "error_metric": "one_minus_hit1",
      "unit": "binary"
    },
    {
      "prefix": "cyp_2D6_ridge",
      "task_id": "cyp.2D6",
      "readout": "ridge",
      "error_metric": "one_minus_hit1",
      "unit": "binary"
    },
    {
      "prefix": "cyp_3A4_linear64_relu",
      "task_id": "cyp.3A4",
      "readout": "linear64_relu",
      "error_metric": "one_minus_hit1",
      "unit": "binary"
    },
    {
      "prefix": "cyp_3A4_ridge",
      "task_id": "cyp.3A4",
      "readout": "ridge",
      "error_metric": "one_minus_hit1",
      "unit": "binary"
    },
    {
      "prefix": "exp_LogD_linear64_relu",
      "task_id": "exp.LogD",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "source_label:LogD"
    },
    {
      "prefix": "exp_LogD_ridge",
      "task_id": "exp.LogD",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "source_label:LogD"
    },
    {
      "prefix": "exp_LogS_linear64_relu",
      "task_id": "exp.LogS",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "source_label:LogS"
    },
    {
      "prefix": "exp_LogS_ridge",
      "task_id": "exp.LogS",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "source_label:LogS"
    },
    {
      "prefix": "exp_Log_HLM_CLint_linear64_relu",
      "task_id": "exp.Log_HLM_CLint",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "source_label:Log_HLM_CLint"
    },
    {
      "prefix": "exp_Log_HLM_CLint_ridge",
      "task_id": "exp.Log_HLM_CLint",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "source_label:Log_HLM_CLint"
    },
    {
      "prefix": "qm9_U0_linear64_relu",
      "task_id": "qm9.U0",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "Ha"
    },
    {
      "prefix": "qm9_U0_ridge",
      "task_id": "qm9.U0",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "Ha"
    },
    {
      "prefix": "qm9_alpha_linear64_relu",
      "task_id": "qm9.alpha",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "bohr^3"
    },
    {
      "prefix": "qm9_alpha_ridge",
      "task_id": "qm9.alpha",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "bohr^3"
    },
    {
      "prefix": "qm9_homo_linear64_relu",
      "task_id": "qm9.homo",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "Ha"
    },
    {
      "prefix": "qm9_homo_ridge",
      "task_id": "qm9.homo",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "Ha"
    },
    {
      "prefix": "qm9_lumo_linear64_relu",
      "task_id": "qm9.lumo",
      "readout": "linear64_relu",
      "error_metric": "mae",
      "unit": "Ha"
    },
    {
      "prefix": "qm9_lumo_ridge",
      "task_id": "qm9.lumo",
      "readout": "ridge",
      "error_metric": "mae",
      "unit": "Ha"
    }
  ]
}
