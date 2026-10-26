# Retained frame native precision diagnosis v1

Source-only, unexecuted child delivery. Root must review, pin, run the three synthetic fixtures on CPU, and make a new analysis request before the real read-only diagnosis. No registered source, input, raw container, old report, tolerance, program, keyword, or result is edited. No QM/UFF program is initialized or invoked. No LMDB is opened.

This reads the existing 4521124 result set: 72 result references in run_closed.json and exactly the original 15 VECTOR_NOT_COVARIANT entries. It does not replace frame_evaluation.json, erase those failures, release 2000/full P-prime, infer SCF failure, or assert any scientific PASS. A diagnosis that a residual fits a native printing interval remains a diagnosis alongside the original failed criterion.

## Root execution contract

The new namespace belongs in Root repository `workflows/data_v1_final/pprime/frame_native_precision_diagnosis_v1`. Use the existing actual main CPU environment, CPU partition and available CPU node, 16 allocated CPUs, no SBATCH memory/exclusive request, and empty CUDA_VISIBLE_DEVICES. The independent new scope uses central `cpu_auto_memory_queue_v2.runtime.require_startup`, kind `analysis`, key `pprime_frame_native_precision72_v1`, with these exact parameters (also the run module SCOPE constant):

```json
{"original_job_id":"4521124","retained_cases":72,"original_covariance_failures":15,"new_QM_calls":0,"native_raw_read_only":true,"maximum_report_bytes":2097152,"algorithm_rss_soft_cap_bytes":8589934592,"minimum_mem_available_bytes":4294967296}
```

Root is the sole submitter. A reasonable finite request wall is 3600 s; the algorithm stops new case reads at 3000 s and drains up to 16 already running parser tasks. RSS/MemAvailable are observed for the primary plus actual pool workers; 8 GiB RSS and 4 GiB available are software soft stops, not Slurm memory requests. No signals, termination, timeout kill, or automatic retry are used. Numerical library threads are set to one before any NumPy work; there are at most 16 spawned parser workers and 16 active cases. Record actual terminal parent cost including failures via Root's existing accounting.

The startup required references are the four supplied config/report/closure paths and this namespace's frozen_sources.json. Pin all six new source files and the central/old imported sources in the Root request as usual. The driver verifies exact old local analysis source pins in frozen_sources.json. The driver intentionally does not call broad load_config/population pin checks: it reads the exact pinned small pilot JSON only. Original load_engine validates the legacy contract, protocol and old sources before import; parser2 also independently verifies its pinned base and legacy parser. Original 72 result/input/raw-member pins are checked on CPU as they are read, not by a login materializer. The diagnosis reads no source LMDB or full population table.

Concrete primary argv:

```sh
/share/home/zixiao/.conda/envs/chemprop/bin/python -B \
 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/pprime/frame_native_precision_diagnosis_v1/run_v1.py \
 --evaluation /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json \
 --run-closed /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/run/run_closed.json \
 --config /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/pprime/vector_frame_audit_root_v1.json \
 --pilot-config /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/pprime/pilot_v1.json \
 --root-preflight <NEW_ACTUAL_CENTRAL_STARTUP_PROOF> \
 --output <NEW_ABSOLUTE_REPORT_UNDER_THIS_RUN_ARTIFACTS>
```

Actual `__main__.__file__` and argv0 must both be this integrated run_v1.py. Output is a new file, at most 2 MiB, with no overwrite/truncation. Original source vectors/raw are not embedded in full; only the requested fields' native tokens, source lines, selected indices, exact Decimal intervals and consistency diagnostics are emitted. Each worker temporarily copies retained output bodies to a new /tmp directory for the unchanged parser's directory API; only those temporary copies are cleaned up. Originals remain opened read-only. Worst concurrent temporary bodies are bounded by the original 16 MiB/case raw limits and 16 workers (about 256 MiB before ordinary parser overhead); retain the normal effective-free reserve and Root whole-job storage accounting.

## Independent geometry check

For every case, verify the pinned postcall input members against prepared input hashes and the exact frozen engine render_inputs bytes. The module is imported/rendered only; initialize_worker and invoke are never called. Parse the actual program input: MOPAC consumes input.mop Cartesian columns/flags, xTB consumes input.xyz. Compare MOPAC and XYZ, and actual coordinates against both stored prepared/expected coordinates; retain any discrepancy as evidence rather than substituting the expected geometry.

Use the predeclared R and coordinate tolerance to check the actual variant geometry against base @ R.T + t, without best-fit alignment. Check translated SP arms separately. For noisy gradient and its SP companion, derive noise from actual noisy minus actual clean native input coordinates, then separately test `noise_variant = noise_base @ R.T` and the same laboratory-frame-noise hypothesis. Different actual geometries are not classified as a covariance comparison. The original 72 recipe has base/rotated/translated arms and no permutation arm; report that absence explicitly. No nearest-neighbor mapping or inferred atom permutation is used. The synthetic utility additionally accepts only a declared bijective variant-to-base mapping.

## Exact native token check

Read raw via the unchanged RawReader in SQLite read-only mode, verify the original record's raw_call SHA/size, archive body and every member manifest/SHA. Freshly run the original independent parse_outputs and measurement functions. Load the frozen parser2 and reproduce the exact original native_aux_labels/sparse_sigma_pi hooks by compiling their unchanged AST function nodes from the pinned native lifecycle source. Only these read/parser functions are copied; no runner main/initialize/invoke is called.

Select the parser's original numeric locations: PM7 AUX DIP_VEC:DEBYE / GRADIENTS:KCAL/MOL/ANGSTROM first declared-count tokens, xTB JSON's unique dipole / a.u. array, and the exact frozen gradient numeric-row predicate. Duplicate/missing arrays, duplicate JSON keys, count/shape ambiguity, absent JSON dipole, or unsupported fields are UNKNOWN. The audit dipole failures use JSON; no alternative stdout dipole is guessed. Numeric tokens are retained directly from the files, including exponent/trailing zeros. Do not infer precision from dtype, Python float repr, or existing stored float precision.

Every selected token is converted by the frozen parser's float function and unit factor. Require bitwise numeric agreement with the fresh frozen parser result, the fresh independent audit vector, the original audit readback, and the original task label wherever that field is retained. For xTB perturbed-gradient dipoles, the frozen task projection intentionally excludes that label; require that exclusion explicitly and use the unchanged raw full parser/audit comparison. Record this scope fact instead of inventing an absent stored label.

For each original failed field, reproduce the original frozen covariance result using the original token-derived audit halfwidths and unchanged configured atol/rtol. Independently derive each original token's decimal step using Decimal's exponent, halfwidth step/2, and the frozen field unit conversion. Propagate `sum_j abs(R_ij)*base_halfwidth_j + variant_halfwidth_i` for every component. Report exact native token-center residual and the exact linear combination of actual parser floats, each against this print-only bound. Do not add a new atol/rtol, use vector norms/global maxima, refit R, or change the original criteria. All failures remain present even if this independent printing hypothesis explains the discrepancy.

## Three unexecuted synthetic fixtures

Run `python -B <namespace>/test_v1.py -v` directly on an authorized CPU allocation. The fixtures check E/D exponent-aware halfsteps and duplicate JSON rejection; propagation of large base component quantization into a small rotated component; and rejection of independently re-perturbed geometry plus explicit-only P handling. They do not read actual scientific data or contact a network. No test or diagnosis result is asserted by this source package.