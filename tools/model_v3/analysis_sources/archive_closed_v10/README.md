# A03 standalone ABBA native SDK archive v10

Prepared source, not yet tested or executed. This is a CPU-only evidence append to the existing task archive. It changes no scientific code, original output or previously archived entry. It does not submit jobs, SSH, synchronize W&B online, run training, or select a recipe.

The four actually closed native-S timing members are 4520576 (position 1/reference), 4520579 (2/candidate), 4520580 (3/candidate), and 4520583 (4/reference). Each has one offline SDK with 22 expected committed history rows: 2 warmup updates followed by 20 measured updates. **22 is the history-row count, not the native SDK packet count.** Actual C0/0:0 is checked through a fresh sonmi closed-job receipt and each child's/supervisor's saved metadata. The actual 4520588 report and separate matched 4520549 numerical gate are also required C0/0:0.

The frozen 8ece producer logs a subset of `steps.jsonl`. This tool derives expected rows from those saved steps under the pinned logger projection and calls the comparison `code-derivedsavedsteps`. It does not claim the saved steps are an original fsync SDK payload mirror. The logger is pinned to SHA e44d33276226de8920f51eabb1e7d35003ddb216ec3d182eef7846cda7f3154a. The code and preregistration are 8ece64c685fe287d6863fbbe2f6f52006632a5cc and 61658a4c1f472de035601dbedc17809315774784. All 22 explicit native steps and all scientific scalars must match exactly, including integer/boolean distinctions and valid-label counters. Missing/extra scientific fields, duplicate/shifted steps, invalid NaN, uncommitted history, wrong run IDs, missing/wrong exits and incomplete EOF are rejected. Native config and display name must match the original saved configuration and role/position; scientific config changes/removals are rejected.

Warmup-versus-measured flags, input receipts, stream cursor, resources and gradient norm are saved-step evidence, not invented native history metrics. Source receipt seals, committed sample counts and the measured 20-input seal/populations are rechecked. All four raw point sets (configuration, status, summary, steps and supervisor) are copied into every case's `all_four_raw_points/positionN`. The actual report, request, closure and report supervisor are retained. The frozen report helper recomputes the four-point pooled report and its independent 549 gate from saved inputs, with no scientific recomputation or timing rerun.

The actual pooled reference/candidate base-record rates are 152.07061073687353 and 131.70667669812963 records/s. Candidate/reference throughput is **0.8660889573595555**. This is a valid timing comparison with no observed foreign-GPU risk and a separate matched numeric PASS; it shows no actual speedup. Head-checkpoint-off is not adopted and no recipe is frozen. Standalone history verification itself grants no numerical, speed or architecture acceptance.

Each case preserves its entire original SDK (including native logs), writes complete normalized 22-row JSONL, a long scalar CSV (`step,key,value_json`), HTML and a verification certificate. All originals remain in place. The fixed v7 bounded reader distinguishes at most 500,000 native packets from at most 100,000 committed history rows, limits each packet to 4 MiB, normalized output to 64 MiB and each scan to 180 s; the new config capture adds at most 10,000 flattened config keys/2 MiB. Selected source bytes are capped at 128 MiB per case and all archived bytes at 256 MiB per case. Before/after source hashes and ownership are checked; the fixed SDK symlink allowlist is retained. Existing task lock, deduplication and atomic pending-directory publication preserve the complete old index.

The explicit future paired-case adapter lists 4520589/TF32 and 4520590/distance-checkpoint-off. It requires an actual terminal receipt and still returns unknown history count/numerical acceptance. These cases are **not enabled by this CLI**, even if C0 is later supplied. No 500-step or numerical result is inferred. The frozen v7/v9 case globals are never modified.

## Root-run verification request (prepared, not executed)

Use the existing tested environment with Python, pytest, W&B 0.28.1 and protobuf. No Torch/CUDA work is needed. Root must choose a currently available CPU node and bind at least 16 CPUs, the `cpu` partition, 4 GiB RAM and a 10-minute wall limit. Set `CUDA_VISIBLE_DEVICES=''` and `PYTHONDONTWRITEBYTECODE=1`; use a private standard-layout unit output directory and a separate pytest base-temp within its authorized production census. The new suite has **41 expected parameterized tests**. It includes a genuine offline W&B 22-step config/history/exit roundtrip and bounded negative cases; this is archive plumbing, not a native scientific or speed acceptance.

```bash
python -m pytest -q -p no:cacheprovider \
  runs/model_v3_20261025/archive_closed_v10_source/test_archive_v10.py \
  --basetemp /tmp/mv3n_JOBID/pytest
```

Compare every pinned source byte before and after the test, including the old imported v7/v9 and fixed archive/producer/report helpers. No actual archive should run until this batch has actually passed. The pins inventory is `source_pins_v10.json`; its own raw SHA must be passed separately and recorded in Root's test/request receipt.

After the tests pass, Root creates a fresh (at most 120 seconds old) SHA-bound sonmi quota/closed-job receipt using the existing format. Require these exact actual lines: `4520576|COMPLETED|0:0`, `4520579|COMPLETED|0:0`, `4520580|COMPLETED|0:0`, `4520583|COMPLETED|0:0`, `4520588|COMPLETED|0:0`, and `4520549|COMPLETED|0:0`. Preserve the original `/dev/sda1` quota guard/reserve rules. Refresh resource/ownership admission immediately before Root submits the archive job, again CPU-only with 16 CPUs, 4 GiB and 10 minutes.

```bash
python runs/model_v3_20261025/archive_closed_v10_source/archive_closed_runs_v10.py \
  --source-pins runs/model_v3_20261025/archive_closed_v10_source/source_pins_v10.json \
  --source-pins-sha256 PIN_RAW_SHA \
  --quota-closed-receipt FRESH_RECEIPT_JSON \
  --quota-closed-sha256 RECEIPT_RAW_SHA \
  --expected-node ACTUAL_CPU_NODE --expected-partition cpu \
  --jobs 4520576 4520579 4520580 4520583
```

The target is `runs/phase1_full_corpus/wandb_archive/model_v3_20261025/closed_v10/job<ID>`, protected by the existing task `.archive.lock`. If the current index still contains 47 entries and no conflicting identity has appeared, the four new standalone SDKs produce 51 entries. This is an expected count, not an execution claim. A partial/failed archive leaves its fresh pending directory for audit and does not replace an old case. All SDKs remain offline and unsynced.
