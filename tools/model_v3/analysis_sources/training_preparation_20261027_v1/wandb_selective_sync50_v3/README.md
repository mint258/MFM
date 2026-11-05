# Explicit selective sync, source-only v3

Actual1410 did upload4sgxpx8j through the official core: original statefailed
was preserved. Its parent remains FAILED because its step-only keyed API
query returned0. Root's subsequent actual read-only diagnosis observed
historyKeys.lastStep500 and an unkeyed HistoryScan with exactly500 ordered
steps1..500; keyed public/direct/sample queries returned0. v3 changes only
that readback to unkeyed streaming with local `_step` projection, and bounds
rows by the original expected count. Other values are neither exported nor
hashed. The original50 selection stays byte-for-byte, including its historic
v1 proposed pilot field; each explicit request selects the actual runIDs.
The new fresh pilot is2ufdeocf, the other closed457 exit1 SDK with500 history
rows/steps1..500. This chain has not replayed that ID. Its real remote
preflight still checks for an existing run and will never blindly replay it.
4sgxpx8j must subsequently follow ALREADY_MATCHED_NO_REPLAY. A new pilot
actualC0, not any rewriting of1410, supplies the existing batch gate.

The original v1 and actual parent4521408 remain unchanged. That parent failed
after its four metadata tests passed. Its child result records CommError in
remote_preflight with no stage copy, CLI invocation or sync action; this
attempt therefore did not upload a run. Its original inner exception was not
recorded, so its underlying communication response is not reconstructed.
The newly-read installed normalize.py wraps a RunNotFoundError as
CommError.exc; v2 admits only that exact typed wrapper (or the raw exact
RunNotFoundError) as a missing run. It still rejects generic communication,
HTTP, authentication and other backend errors. The existing four-case
preflight now tests the actual installed decorator with a synthetic missing
exception and negative typed exceptions, without constructing an API client.
Marker equality is now measured independently of overall operation success;
v1's false marker field was a faulty projection of its unrelated failure.

This package is prepared for Root execution. No network call, CLI replay, CPU
test or Slurm submission has been executed by its author. The fixed input is
the actual 4521403 integrity result: 50 structurally complete native logs
(37 exit0, 13 exit1) and 7 excluded incomplete logs. The two Native-S profile
SDKs from 1331/1332 are not members of this set. Structural completeness does
not grant a failed scientific run a numerical or timing acceptance.

The installed 0.28.1 Python source snapshots are bound in
`installed_sources.json`. Plain `wandb sync --yes --no-sync-tensorboard
--include-offline --entity E --project P --id ID ONE_FILE` meets the installed
CLI's official beta/core reroute conditions. No `--legacy`, `--sync-all`,
append, clean or state-changing API is used. The legacy parser defers its
stored exit until a final record, which these 50 input logs lack. This is a
reason to test the core route; it does not establish compiled core behavior.

The new proposed pilot is 2ufdeocf, the closed exit1 member of job457 with
500 history rows, explicit steps1..500. A successful new replay must read back
the original runID, entity/project, state `failed`, exact history count and
step endpoints. API history streams unkeyed rows, retaining only `_step` locally in an uncached complete
scan. Evidence never exports metric values or API keys. An existing remote
run must already match all these fields; conflicting runs stop before replay.
An already-matching remote pilot proves presence, not failed-exit replay.
No original SDK, summary, history, exit or marker is repaired or deleted.

Each upload uses an exact, fsynced, hash-checked SDK copy under the new job's
`stage/original-offline-run-name/`. Only that single `.wandb` path is passed
to the official CLI. The original SDK and its optional `.synced` marker are
hashed before and after; the CLI may create a marker only beside the copy.
Route comes from the original RunRecord; only an empty native entity receives
the explicit mint_leaf258 default. The source files and installed reviewed
Python files are checked before each run. The original protobuf body is not
decoded again by this package.

Root execution, from `/share/home/zixiao/descriptor_analysis`:

```bash
P=/share/home/zixiao/descriptor_analysis
N=$P/runs/model_v3_20261026
S=$N/wandb_selective_sync50_v3
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins.json" | cut -d' ' -f1)
# First perform the existing server-side AST/source and bash syntax review.
"$PY" -B "$S/prepare_sync.py" --mode pilot --runs 2ufdeocf \
  --output "$N/WandB_sync50_pilot_plan_v3" \
  --job-output "$N/WandB_sync50_pilot_actual_v3" --pins-sha256 "$PIN"
```

`prepare_sync.py` is metadata-only. On Root sonmi it captures the actual
4521403 sacct terminal and checks its real supervisor; it neither uploads nor
reserves resources. Copy `sync_cpu.sbatch` to a new name under OLD, preserving
its source bytes in the submission receipt. Submit it using the existing
`OLD/submit_cpu_task_v2.py --node ACTUAL_CPU_NODE --memory-MiB 16384 --script
OLD/NEW_NAME.sbatch --bindings PLAN/bindings.json --output OLD/NEW_RECEIPT.json`.
Root selects the CPU node only after that helper's live CPU, memory and
account quota checks; no old resource frame is accepted as current.

The actual sync job requests 16CPU/16GiB, hides CUDA, uses the original CPU
supervisor with RSS12GiB, wall3300s within Slurm1h, and the unchanged aggregate
2GiB output/private/stdio bound. Four metadata tests run as its own preflight,
not an independent QA parent. Pytest uses `failed` retention so passed fixture
directories and current links are normally cleaned before the output census.
The child executes at most three explicit SDKs sequentially, each with
CLI600s, cloud verification180s and an enclosing900s subprocess bound.

After the pilot, Root reads its `RESULT.json`, raw one-run result and actual
supervisor, then supplies the actual parent C0 to the next metadata plan:

```bash
"$PY" -B "$S/prepare_sync.py" --mode batch --runs EXPLICIT_ID_1 EXPLICIT_ID_2 \
  --output "$N/WandB_sync50_batch01_plan_v3" \
  --job-output "$N/WandB_sync50_batch01_actual_v3" --pins-sha256 "$PIN" \
  --pilot-result "$N/WandB_sync50_pilot_actual_v3/RESULT.json" \
  --pilot-supervisor "$N/WandB_sync50_pilot_actual_v3.supervisor.json" \
  --pilot-job ACTUAL_PILOT_JOB
```

Batch IDs must be an explicit unique subset of the fixed50, at most3; no
directory expansion or background dispatcher exists. Absent remote exit1
members require an actual newly-replayed exit1 pilot C0. If core changes its
state, retain the failed attempt and stop that failed-exit method. The 37
exit0 members can use their own successful single-run exit0 pilot; this does
not relabel or repair the 13 exit1 originals. A child result deliberately
remains `...PENDING_ROOT_C0`; only actual Slurm/supervisor closure establishes
the CPU parent's terminal result. Subsequent Root review can account all50
explicit runIDs using these per-attempt results without mutating the input
manifest or claiming an unexecuted upload.
