# Centered fixed-H0 diagnostic — DRAFT source only

This is one measurement, not another candidate. The candidate remains local `cf8ce66d97cd518ebf279b40ee20294919bb95e1`, public `f8417157dc23326d1beca8e19e4725755d9f13c6`, exact tree `2389ab046ee23f2ba92fcb61179d853dfdee8357`. All six coupled attention layers use `centered_fp32_v1`; the existing COMPENSATED encoder, distance/reducer and heads remain enabled. No production file, default, parameter, architecture, 512-dimensional H0 API, case, seed or threshold changes.

The actual1776 complete48 failed gate (21 pass / 27 fail, 71 failed P/D observations) is retained. Its NPZ files contain only terminal outputs, not the bank-input H0. New H0 therefore comes from a fresh, separately identified GPU job. Neither old1492 H0 nor supposed1776 hidden H0 is substituted. The historical `fresh_capture_not_1435_H0` field is retained only for the frozen1503 decoder; the new explicit lineage is `fresh_centered_capture_not_1776_hidden_H0`.

## Exact reuse

`capture_centered_H0.py` is a narrowly derived copy of frozen1492 `capture_fixed_h0_v1.py`: the original hooks retain Python references, return None, and copy CPU arrays only after the original full forward returns. It still checks same-forward PD outputs against all52 original terminal arrays and removes hooks/restores the forward override in finally. The adaptations are import/source binding, existing centered construction, each case's original1492 full named-parameter SHA, the new lineage and external1776 controls. The original constructor is restored separately from the temporary centered constructor so contexts cannot leak into later cases.

The GPU run performs exactly the original48 cases × four full FP32 encoder forwards =192. Clean bank H0 has44×512 entries; packed encoder returns remain88×512 or132×512. There are zero FP64 encoder forwards. The existing candidate tiny CUDA controls and1503 head-math tiny controls run inline and have separate counts; no new suite or parent QA task is introduced.

`analyze_centered_H0_CPU.py` calls the frozen1503 implementation's `tiny_selfcheck`, `decode_case`, and `evaluate` directly. It does not copy/rewrite `functional64`, reduction, dipole, pooling, transform or decomposition math. Its population is the original three P fields × three transforms ×48 cases =432 observations, not all13 full-model terminal fields. Original FP32 head state and actual captured H0/coordinates are loaded without changing their values; only the existing diagnostic head calculation promotes operands to FP64. No encoder executes on this CPU task. Actual Python/Torch/NumPy/thread metadata are saved; equivalence to the old1503 environment is not invented.

## Controls and interpretation

The original case/seed/fixture/transform/geometry/domain, full parameter identity, all52 terminal identities and exact array values are compared against actual1776 external outputs. Root metadata assembly only stats these original NPZ files and binds their existing raw refs; it does not open or hash NPZ payloads. The GPU task later reads at most128MiB of this fixed input (the48 original1776 terminals total about10MiB), checks original raw hashes, and compares every FP32 array bitwise. `complete_terminal_count` is13 unique fields;52 arrays are13×four forwards. Original and newly measured physics-pass flags are recorded explicitly.

A numerical external replay mismatch is recorded per case, all48 cases continue, and completion/CPU attribution is rejected after the complete matrix. There is no retry or selected subset. Corrupt input/source/config or a resource failure remains an execution failure and cannot be disguised as a complete measurement. Physics failures themselves do not stop capture. No tolerance changes: absolute1e-5, relative0.

If all external controls and the new GPU closure succeed, the CPU task emits the original signed H/G/I decomposition, GPU_FP32_D, CPU_FP32_D and head_arithmetic_delta at the same component and the complete signed components. F64 residual above1e-5 alone does not identify the encoder: H, G and I must distinguish inherited representation, geometry and interaction contributions. A reduction of residuals identifies a local arithmetic hypothesis, not adoption or FP32 acceptance. No FP64 production, training, label changes, NativeRuntimeDense/bf16 generalization or architecture selection is authorized.

## Root review and metadata assembly

No Python/AST/model/NPZ/SDK/network/Slurm execution has been performed by this author. `DRAFT_SOURCE_INVENTORY.json` and `DRAFT_DEPENDENCIES.json` are raw-byte source/closed-JSON inventories, not QA or publication certificates. Root should AST/read-review these files and inspect the exact derived capture/launcher changes. A new full model regression is not requested: the model is the already CPU-verified/published candidate and only the thin diagnostic source is new.

Root may assemble metadata after review, before publishing this diagnostic request, using the server's existing Python:

```bash
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/centered_fixed_H0_diagnostic_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
"$PY" -B "$S/prepare_metadata.py" --assemble
```

Assembly creates fresh `execution_request_v1.json` and `source_pins_v1.json` in this package, refuses overwrite, preserves the actual candidate publication/CPU QA and failed1776 raw closure, and adds per-case original1492 parameter identities plus actual1776 case refs/stat observations. It does not submit or claim that the new source has been published or executed. Root must publish the final request/source/preregistration before actual GPU execution. These final artifacts do not exist in the author's draft.

## Original finite GPU launcher

The launcher/SBATCH are narrowly renamed copies of the actual1776 launcher. Original resource guard `gpu_runtime_retry_v4/submit_composed_eq_gpu_runtime_retry_v4.py` remains the resource authority. Node `compute-0-21`, GPU `GPU-c35f2434-9137-9723-1af5-dc69b6295243`, shared fd9 UUID lock,16CPU32GiB, RSS28GiB,1100s supervised wall,20min allocation, whole output2GiB and private2GiB remain fixed. Quota, max(queue,AllocMem)85%, actual MemAvailable, NVML foreign-process checks and all existing fallback rules remain unchanged. The child inherits the original supervisor ceiling (outer minus96MiB); no new monitor is added. Input/capture artifacts retain the original128MiB cap. This is a proposed bound, not a measured time claim.

After Root publication, obtain `PINS_SHA` from the actual new pins, then Root alone runs:

```bash
"$PY" -B "$S/launch_centered_H0_GPU_v1.py" audit --source-pins-sha "$PINS_SHA"
"$PY" -B "$S/launch_centered_H0_GPU_v1.py" submit --source-pins-sha "$PINS_SHA" \
  --submission-receipt "$B/runs/model_v3_20261025/centered_fixed_H0_capture_GPU_v1_attempt1.json"
```

No automatic retry. New capture output is `O/centered_fixed_H0_capture_GPU_v1_ACTUALJOB`; supervisor/worker/stdout use the matching new basename. Original1492/1503/1776 and their files remain untouched. A complete capture is diagnostic-only even if all physical gates happen to pass.

## CPU continuation after real GPU C0

Root captures the actual new GPU's unfiltered accounting with the existing six-column `sacct -n -P -j JOB --format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS` JSON envelope; original1503 `cpu_metadata_v3.validate_capture_accounting` requires actual C0 parent/batch/extern,16CPU. Do not relabel1776 FAILED as C0 or borrow1492 C0.

Set the existing `MODEL_V3_H0_CAPTURE_{COMPLETE,COMPLETE_SHA,SUPERVISOR,SUPERVISOR_SHA,ACCOUNTING,ACCOUNTING_SHA}`, `MODEL_V3_H0_SOURCE_PINS_SHA` to these actual new refs and pins, and `MODEL_V3_EXPECTED_NODE` to the freshly admitted CPU node. Root submits `run_centered_H0_CPU_v1.sbatch` using the established CPU-only helper/admission. This preserves16CPU16GiB, RSS12GiB,120s child /3min allocation and original output guard; CUDA is hidden. The wrapper uses the declared5090 Python on CPU and records its actual versions. Root performs actual terminal/source/supervisor closure afterwards. There is no SDK/online action in either stage.