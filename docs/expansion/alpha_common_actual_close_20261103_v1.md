# Actual Alpha Common closure command

This is a Root-owned metadata step after the actual graph/variants/HOLD review. The helper is source-only until Root invokes it; it creates no approval during an active job. It calls the existing alpha_common.component_ready and alpha_common.finalize, queries actual sacct, preserves raw accounting, and emits the already-defined Root acceptance document. There is no new scientific gate, job submission, chemical recomputation or large journal rehash.

Actual1885153 producer receipt will be `/gfshome/alpha/pubchem_expansion_20261103/exact/common_grouped_node_v2_job_1885153/receipt.json`. Its actual plan/startup are under `/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/node_epochs/common_grouped_node_v2_job_1885153/`. While RUNNING there is no terminal producer and no approval. The source6/fresh16/64-task and groupedIO3 gates have actually passed; checkpoints remain partial evidence, not C0 or a substitute reference.

Once actual C0 and Root review are complete, deploy only the helper to a new control/source path (do not overwrite immutable layers), then run:

```bash
PY=/gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python
"$PY" -I -B /ACTUAL_NEW_SOURCE_LAYER/workflows/expansion/alpha_common_root_close_v1.py \
  --producer /gfshome/alpha/pubchem_expansion_20261103/exact/common_grouped_node_v2_job_1885153/receipt.json \
  --output-directory /gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/common_actual_close_1885153
```

The helper defaults to the already deployed exact_uff_runtime_cb98b34_namespace_v2 layer and Base497. Both workflows and workflows.expansion namespace paths include layer then base. Base497 alone lacks alpha_common.py, but Root has confirmed the existing layer contains the whole current exact_nn_cached_v1 package; no new consumer package deployment is needed. Metadata helpers do not call the old Main external_output/UID gate or resolve Main origin paths as local Alpha paths.

Expected existing component checks: full mode, true full_population_graph_computed/full_reference_candidate, strict5/Common1,196,122, TRAIN1,188,592 and VAL7,530, native records10,973,084 and71,884 (sum11,044,968), HOLD0, identical expected/scanner/strict5 molecular census and digest, all33 actual Alpha held-FD input frames, all4 exact journal readbacks,16 actual worker proofs and16 worker count entries summing to Common. The original common header remains denominator1,214,218/excluded18,096/UNKNOWN3436/orders_frozen false. The full source scanner separately reports scan.formal_physical_rows_scanned from whole-Parquet EOF; source journal rows are selected Common physical records, while graph journal event rows are not molecular cardinality. Never infer completed MIDs from partial event-line counts.

The existing finalizer also verifies source_tests6/fresh16/synthetic64, actual full plan/startup pins, original copied common header/roles and every actual worker proof. GroupedIO3/policy/checkpoint references are retained as review evidence; no new consumer gate is invented. The source producer retains its pending-C0 wording and Main4525659 STOPPED/C0false even after Alpha closure. Fresh Alpha actual accounting is the acceptance basis.

Outputs are actual_sacct.txt, actual_accounting.json, root_actual_graph_review.json and common_reference_manifest.json in the fresh closure directory. The final manifest uses the existing expansion_common_v1_structure_projection_v1 schema with status COMPLETE_ALPHA_FULL_COMMON_REFERENCE and producer_schema ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1. Subsequent pack_reference before-mode uses this manifest as plan.input_manifest and the existing Alpha resource/profile/transport fields; coverage before-mode then consumes the packed full Common reference. Both consumers independently validate the Alpha branch. These are allocated data stages; the closure helper is small metadata only. No55k or all-TRAIN proxy is introduced.
