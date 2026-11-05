# Future fill input I/O omission runtime

`workflows.data_v1_final.conformers.window2_fill_runtime_v1.run` is an independent future entry point. Active `window2_population_v1/fill.py` is untouched. The original worker returns before reading records, UFF coordinates or any SCIENCE method when its closed D7 unique-ID list length is at least the original S_conformers. Its initial SCIENCE assignment does not require initialized science for that return.

The runtime uses only existing closed-part metadata to separate this exact fast case. The original meta/d7/max_original_attempt_idx plus empty records/uff go to original safe_fill in the parent. This preserves every state field and original unsupported precedence. All remaining molecules go through original d7.tasks and original safe_fill in the original pool, unchanged. Malformed qualification metadata falls back to the original path/error handling. Results are restored to original metas order.

The producer loop is copied from the original with exactly the full-job-materialization/pool-map block replaced by this helper. Original part numbers, closed-part skipping, files, checkpoint schema/writes, geometry aggregation, final manifest and science parameters remain the same. No source/checkpoint scan, new numerical check, quality pass, benchmark, hashing, scientific parameter or worker change is added.

Root alone switches at the intended closed-part materialization boundary; this implementation sends no signals and submits no jobs. Future actual parent runs exactly this one new test (not the old three):

    python -B -m unittest workflows.data_v1_final.conformers.window2_fill_runtime_v1.test_v1
    python -B -m workflows.data_v1_final.conformers.window2_fill_runtime_v1.run --plan ORIGINAL_EXISTING_FILL_PLAN

The one test compares original safe_fill outputs for mock full tasks versus stubs, checks original order/keep IDs/state fields, proves fast-only avoids tasks/pool, and checks nonclosed/short cases still call original tasks/safe_fill. It uses no real scientific files or Native reads.