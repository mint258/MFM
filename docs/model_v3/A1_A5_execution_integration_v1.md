# A1 / A5 execution integration v3

Status: v3 source overlay prepared for CPU QA and independent review. The v1/v2 frozen inventories and raw snapshots remain historical evidence; none is an actual QA pass. No new CPU, CUDA, native20-batch/500-update acceptance, speed or adoption is asserted. This isolated branch starts from the Root-designated combined 3d9 runtime; existing running/frozen trees, recipes and scientific thresholds are untouched.

## Actual opt-in entry points

`build_performance_model(model_config, PerformanceOptions(...), execution=payload)` installs the policy and/or padding implementation before optional backbone compilation. Alternatively put the same payload under `model_config["performance_execution_v1"]`; declaring both is rejected. The real A paired and standalone training CLIs accept:

```
--performance-execution /absolute/config.json
--performance-execution-sha256 ACTUAL_RAW_SHA256
```

These flags extend the existing native-S commands; their original Slurm/UUID lock, source/publication admission, deterministic-controls, raw snapshot, limits, private-storage, output and foreign-process guards remain required. This document does not authorize running a project script on Windows or the login node. Root executes CPU QA and all GPU work.

Two usable **manual** configurations are supplied:

- `current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json`: unchanged full logical encoder call, with measured size/source observations enabled.
- `current/configs/model_v3/performance/a5_logical_batch_chunks_v1.json`: encoder-only chunks, width16 / at most32 complete graphs / target1,000,000 dense pairs per chunk. Intrinsically oversized singleton graphs remain present and explicitly counted.

The candidate options file still declares precision, distance/head/layer checkpoints, compile, TF32 and fused optimizer. Its original twelve defaults and `asdict` schema are unchanged. No radius mask is added to the global-attention baseline. No failed fused/TF32 gate is relaxed. Execution configuration is an additional, explicit identity; data/snapshot/record/noise receipt algorithms remain unchanged, while newly authored code necessarily receives a new code SHA.

## A5: same logical batch, before any head/loss

`LogicalBatchBackbone` reuses the original backbone's exact child modules, Parameter objects and state keys. It only supports the declared original `RealCoordTransformerBackbone`, fp32 positions, no outer AMP and zero backbone dropout. Cross-graph BatchNorm is rejected. The default path does not install this class.

The original stream/provider prepares the complete logical batch, including all three views, original padded degradation/noise draws, masks, labels and associations. Only then does the encoder stably sort complete graph indices by atom-count bucket / size / original graph index. Each chunk invokes the original backbone, then `index_copy` restores the exact original packed atom and graph order. All three views remain in the same optimizer step. Element/bond/geometry/PD heads receive the complete restored batch once, and the existing masked losses, field/SDP group means and global denominators execute once. No chunk creates targets, redraws noise, normalizes a local loss or performs an optimizer step. The source `CorpusBatch` and committed sampler cursor are not modified.

Chunking changes dense layouts and FP32 accumulation order. CPU algebra closeness is not proof of the original CUDA per-parameter relative-gradient gate, including analytically null biases. It can fail that gate. Actual native20/500 tests and standalone A/B/B/A speed measurements on 3090/4090/5090, singly and combined, remain necessary before adoption. Memory saving applies to encoder padding; head memory remains governed by the original head/tile options.

The old `--atom-bucket-width` / `--exact-atom-sort` sampler changes remain standalone exploration only and are still rejected by the paired A gate. They are not this new encoder path.

`V3StepTrainer` conditionally records the padding/profile execution contract in its configuration and execution checkpoint. Loading a checkpoint with a different layout/profile contract rejects before restoring weights/RNG/cursors. With no opt-in its previous configuration/checkpoint keys remain unchanged. The bounded A diagnostic still explicitly rejects resume, and integrated candidate checkpoint export is refused until its separate H0 artifact adapter is admitted; neither limitation is hidden.

## A1: automatic selection from actual closed capacity observations

Use `checkpoint_policy="auto_closed_profile_v1"`, a bound `capacity_profile` rawref and the workload SHA. `PerformanceExecution` is the typed schema. Manual mode has no profile prerequisite, so a first real measurement is possible. There is no OOM retry/fallback and no marketing-name capacity table.

The A CLI binds its actual model/seed/native input/raw snapshot/reference and A4 configurations/losses/supervision to `workload_sha256`, and binds its original padded-cost budget and model residency (paired2, standalone1). An explicit inconsistent value is rejected. The policy additionally pins a mandatory complete source projection: every Python file under current/phychem_mfm (including routes, normalization, outputs, specs, supervision, schema/decoder and the numeric acceptance implementation), every original workflows/sprime_s/scripts Python file, and the explicit outside-package A runner/profile/guard/export sources. There are bounded source-only directory scans (at most2048 Python files /32MiB source bytes; no data payloads). Both opt-in A entry points merge this same projection into their actual saved config.source_sha256 before allocation/configuration saving, and reject changed pre-existing entries. The capacity reader requires the whole mandatory projection in that saved actual graph, checks every mandatory value against current bytes and also rehashes each saved dynamic extra. Paired/single dynamic extra sets need not be identical; saved extras are not ignored. Direct API callers must provide the equivalent workload binding themselves for auto mode.

The small external profile JSON has exactly this shape; Root obtains all six refs from each actual closed run, retaining the raw Slurm observation rather than inventing successful booleans:

```json
{
  "schema": "model_v3_closed_checkpoint_capacity_profiles_v1",
  "observations": [
    {
      "configuration": {"path": "/actual/run/configuration.json", "bytes": 1, "sha256": "ACTUAL"},
      "summary": {"path": "/actual/run/summary.json", "bytes": 1, "sha256": "ACTUAL"},
      "run_status": {"path": "/actual/run/run_status.json", "bytes": 1, "sha256": "ACTUAL"},
      "supervisor": {"path": "/actual/supervisor.json", "bytes": 1, "sha256": "ACTUAL"},
      "parent_sacct": {"path": "/actual/raw_sacct.json", "bytes": 1, "sha256": "ACTUAL"},
      "steps": {"path": "/actual/run/steps.jsonl", "bytes": 1, "sha256": "ACTUAL"}
    }
  ]
}
```

This is a schema illustration, not a runnable/accepted receipt. `parent_sacct` is `{argv,returncode,stdout,stderr}` with the explicit parent job and `--format=JobIDRaw,State,ExitCode` columns; the actual parent must be COMPLETED/0:0. For a paired run use `resources.jsonl` and its full500 trajectory rows instead of `steps.jsonl`. Ordinary owned, nonaliased, stable files are streamed/hashed; each JSON is at most2MiB, the journal at most16MiB, each line at most1MiB, and at most32 observations are allowed.

Only actual execution-enabled native runs qualify: full paired20/500 with original gates passed and cleanup closed, or standalone2warmup+20measured with cleanup/foreign status clear. Historical8ece runs lack new per-step packed-graph observations and are deliberately rejected; do not fabricate/retrofit those fields. Each observation provides actual three checkpoint booleans and the observed maximum graph count, atoms, max nodes, dense padded pairs, allocator peaks and own-NVML memory, including materialized optimizer state. Unknown memory is rejected, not zero. Model options other than those three flags must match. Every actual step remains under the existing85% physical cap.

Selection runs before candidate model allocation. It requires the same physical UUID, GPU name/total memory, Torch/CUDA/cuDNN/driver and deterministic/TF32 controls, actual current free memory with10% device reserve, and total current use plus the measured resident peak at most85%. A fresh NVML compute-process query rejects a foreign process. Profile order is explicit preference order; the first compatible measured policy is selected. This is an applicable capacity choice, not a claim of fastest speed or a guarantee over unobserved future workloads.

Every subsequent forward checks its actual graph/atom/max-node/padded-size envelope against that observation. Auto selection with both `compile_backbone=true` and logical-batch packing is explicitly unsupported and refused before allocation: a full-batch `(graphs,max_nodes)` is not evidence for the actual chunk shapes/workspaces. This v3 does not claim that combination implemented/admitted. Without packing, compiled auto execution additionally requires an observed full dense `(graphs,max_nodes)` shape because unseen workspace sizes are unknown. Manual compile+packing remains an explicit unaccepted experiment under the original gates; it receives no automatic capacity claim. Larger inputs reject before forward, without silently reducing the logical batch, dropping data or changing checkpoints. The original supervisor remains authoritative for live85%/RSS/output/private limits.

A real profile must be obtained under this same frozen implementation/source graph. Begin with manual options, then Root creates a **fresh external** rawref profile manifest and auto configuration. CPU fixtures test the evidence predicates only; no CPU fixture is a CUDA, Slurm-C0 or capacity certificate. One-resident timing evidence cannot authorize two-resident paired training, and vice versa.

## Paired acceptance, speed and verification

The existing paired runner still performs20 fixed logical batches with output and **all** parameter-gradient gates, then the same-seed500-update trajectory. No denominator, tolerance or parameter exclusion changes. It now records the explicit execution configuration/source receipt and actual graph counts. The existing standalone runner still uses the original reference path and two candidate members for A/B/B/A, with2warmup+20timed windows. Its original full input receipts and committed cursor are retained.

The speed report additionally requires the same candidate padding, effective checkpoint/options, workload and implementation bytes in both candidates and the separate numeric gate. Capacity source pointers and resident1/2 observations can differ; actual execution mathematics/layout/options cannot. References must explicitly retain the original full logical path. No report grants adoption on timing alone.

Planned CPU command (Root's actual CPU Slurm environment, CUDA hidden, at least16 allocated CPUs, scientific dependencies/PYTHONPATH as the existing suite):

```
python -m pytest current/tests/test_model_v3_performance_integration.py current/tests/test_model_v3_checkpoint_policy.py -q
```

The static planned test count is50 (integration14, checkpoint-policy36), not an actual collection/result. The tests exercise actual constructors/forward/backward and whole S+D+P masked/count paths; unchanged keys/defaults/RNG/input receipt; empty/malformed packed graphs and stochastic-context refusal; actual `V3StepTrainer` optimizer/RNG/provider/cursor checkpoint resume after speculative prefetch; mismatched resume refusal; exact closed-metadata parsing and source/workload/residency/budget/foreign/incomplete/unknown-memory refusal; physical-capacity selection; source-bound CLI routing and retained old rebatching rejection. They make no GPU-performance claim. Root should then run the original affected performance/A-execution/trainer regression and repository checker, with source hashes before/after. GPU admission/publication is a separate Root action after QA/review.

## v3 source handoff and CPU resource scope

The external overlay is a source bundle, not an executable package/runtime. Root first preserves the original v1 thirteen leaves plus inventory, installs these relative-path leaves into the complete performance-integration worktree, then creates the actual v3 inventory and checks the resulting __file__/ROOT/package source identities. Never prepend an incomplete overlay beside the old package and claim the combined tree was tested. The author has not executed Python, AST, tests, models, Git, SDKs or Slurm.

Only four of the thirteen leaves change from v2 to v3: checkpoint policy, A shared execution metadata binding, the policy tests and this document. The A5 mathematical forward, model integration, trainer, paired/single numerical loops, thresholds and speed-report bodies remain the original frozen v1 bytes.

The50 planned cases construct17 actual models in total:9 tiny dim16/two-layer/four-head models and8 original structural-fixture dim512/one-layer/eight-head models. At most two512x1 models are live in one case. The policy cases use typed CPU source/receipt fixtures and never create a model or mock a CUDA admission. No W&B SDK is initialized: the trainer uses its existing explicit in-memory UnitTracker.

The new resume cases write six genuine model/AdamW safe checkpoint payloads in pytest-owned output directories: three on the original2/4/6 sample path, two4/6 on the resumed lineage, and one for changed-layout refusal. Other fixture JSON/journal/source files are small. No data LMDB, scientific NPZ or historical artifact is opened. Static, unmeasured planning estimate: approximately3–6GiB peak RSS and0.5–1.2GiB cumulative new checkpoint output; exact shape/numel/bytes and wall time await the real CPU run. Original16CPU/16GiB/RSS12GiB/800s/whole2GiB/private2GiB limits are a reasonable bounded first attempt, not an observed guarantee, and must not increase on failure.

Old affected regression filenames are test_model_v3_performance.py, test_model_v3_a_execution.py, test_model_v3_structural.py, test_model_v3_training.py and test_model_v3_trainer.py. The first four form a lighter group; training.py only checkpoints a4→8→1 MLP. The trainer.py group uses actual512x1 fixtures and approximately eleven large payloads and should run separately, with the already verified pytest failed-retention policy cleaning passed temporary fixtures normally. Do not mix it with these new resume cases or the large WSD/storage group inside one retained2GiB output. All these are plans, not measurements or successful parent-job claims.

## v3: qualify the actual measured A invocation and guard

A capacity record must come from the actual fixed paired or standalone tool, not merely a successful JSON with matching output/code flags. The opt-in shared helper now records `performance_execution_invocation={source_root,cwd,logical_python,argv}` directly from the active runtime. This field is absent when the old default path is used. It is joined to the supervisor's original `command` and kernel `launch_identity`; a self-declared cwd alone cannot qualify a run.

The real original child format includes `[logical_python, "-u", "-B", "tools/model_v3/paired_a_acceptance.py", ...]`. Only these existing optional Python flags are admitted, each at most once; `-c`/`-m` or an absent/different entry are rejected. `sys.argv` excludes the interpreter and its `-u/-B` flags and is compared to the corresponding exact command suffix. Relative scripts and argument paths resolve using the captured actual cwd to the fixed source-root paired/single entry. Its bytes must equal both the complete actual run source graph and current mandatory graph.

The original successful549 supervisor was inspected as metadata only to ground this schema: its guard record contains `supervisor_source_sha256`, **not** a `sources_sha256` dictionary. That recorded self-hash must equal the pinned original guard in the actual run graph/current source projection. The guard's physical path is not invented; an already proven byte-identical guard path is allowed. The child interpreter, exact argv and NUL-delimited argv SHA, recorded PID/PGID/SID, boot/start-ticks, UID, Slurm job/cgroup and selected GPU UUID are cross-checked. Historical exited PIDs are not probed.

The command must actually select the saved input/code/seed/output, source-bound `--performance-execution` and its SHA, and the original candidate-options bytes. Required values use the existing explicit separate-value form and reject duplicates. Paired qualification requires the saved actual20/500 dimensions and no standalone role arguments. Standalone qualification requires candidate role at ABBA position2 or3, same config/summary/CLI series and position, and actual2warmup+20measured. Smoke, resume and old logical-batch-changing sampler exploration cannot qualify capacity. Raw SDK/history payloads are not read by this policy.

Two positive CPU typed fixtures cover relative `-u/-B` and absolute no-prefix invocation forms. Ten new negative mechanisms cover a byte-identical but wrongly named entry, missing entry, wrong standalone role/series, wrong original guard source, launch-argv/sys.argv disagreement, changed opt-in SHA, Python `-c`, and a paired record invoking the standalone tool. These add no model instances, checkpoints, SDKs or new QA parent. They remain CPU protocol fixtures, not genuine Slurm/CUDA or scientific acceptance.

## v4 test-fixture correction after actual CPU3408

The frozen v3 suite actually ran as CPU4523408 and the parent failed:98 tests passed and one integration fixture failed, with no skips (new integration13P/1F, policy36P, old core39P, old trainer10P). The original artifacts and v3 source snapshot are retained. The failing test assigned `.p=.2` to the zero-dropout FFN's `nn.Identity`; that arbitrary attribute never enabled a stochastic operator. This failure is not evidence that the guard accepted real Dropout.

v4 changes that test fixture only: assert the actual Identity layout, install a genuine training-mode `nn.Dropout(.2)`, assert its guard-visible type/reachability, and demonstrate output change plus CPU RNG consumption inside a fixed-seed `fork_rng(devices=[])` control. The control restores the caller's CPU RNG and does not seed CUDA. The original forward must still raise the same RNG-preservation error and leave external RNG unchanged. The pre-construction nonzero-dropout refusal remains. No production code, model arithmetic, tolerance, parameter set or scientific population changes.

The planned full rerun is still99 cases (14 integration+36 policy+39 old core+10 old trainer); no v4 execution or pass is claimed. The same17 model instances, six genuine safe checkpoint payloads and zero SDK runs remain, under the unchanged16CPU/16GiB/RSS12GiB/800s/whole2GiB/private2GiB envelope. The Root-materialized v4 source inventory and actual CPU/GPU gates remain required.
