# Failed pretrajectory A cases: archive v11

Prepared, not tested or executed. This incremental CPU-only package preserves the existing task archive and all original files. It changes none of the frozen v7–v10 or scientific sources, performs no SSH/submission/training, and keeps all W&B SDKs offline and unsynced.

The two cases are distinct:

| Case | Actual saved scientific outcome | Child process | Outer Slurm | Native SDK expectation |
| --- | --- | --- | --- | --- |
| 4520589 / A07 TF32 | All 20 fixed batches were evaluated; the fixed numerical gate is false. No trajectory, summary or checkpoint export exists. `failure:null` is not a successful result. | exit 2, supervisor first failure `child_exit:2` | FAILED / 1:0 | Scan each of the two SDKs. The failed producer's `finish` writes exit 1 if persisted; do not substitute exit 0 or child 2. |
| 4520590 / A02 distance checkpoint off | Saved `MemoryError`: `A diagnostic exceeded85% of physical GPU capacity`; supervisor's first failure records the 85% GPU process cap. The child aborts and input-stream/reference/candidate SDK cleanup fails. No fixed gate, trajectory, summary or export exists. | exit -6; no recorded remaining owned processes | FAILED / 1:0 | Each original SDK is currently 7 bytes. A header-only file has no native run identity, paired role or exit record. It must remain incomplete evidence. |

The original request contains 20 fixed batches and 500 trajectory updates. These requested counts are not completed counts. The certificate records the actual saved fixed-batch prefix, actual trajectory updates 0, all original cleanup errors, and the distinct outer/child/native exit domains. It binds the primary cause to raw run-status, supervisor, stdout and (for 589) fixed-gate SHA references. A CUDA allocator OOM is not required or claimed for the 590 soft-cap rejection. Neither case grants numerical, trajectory, speed, recipe or checkpoint acceptance.

The frozen producer is `MFM_model_v3_a_checkpoint/tools/model_v3/paired_a_acceptance.py`, SHA b8b4ad10a848561d69352fe5729a5ace9060a28125775c2f219df9b47dd29ebd. Actual code/preregistration remain 8ece64c685fe287d6863fbbe2f6f52006632a5cc and 61658a4c1f472de035601dbedc17809315774784. An AST check confirms the only scientific `tracker.log` occurs inside the trajectory loop after the fixed-gate rejection branch. The full configuration seal, source bindings, consumption receipts/clock and saved fixed-gate rows are checked. Absence of original histories, reset, trajectory gate, summary and candidate checkpoint is checked before and after archive creation.

The SDK reader first scans every native packet to observe the actual committed-history count, IDs, role/config, exits, partial requests and EOF/decode state. A second independent pass verifies the same observations using the fixed v7 bounded reader. No 500-row count or successful native exit is imposed. For these saved pretrajectory outcomes the expected scientific row set is empty, derived from the pinned producer and saved source state; the comparison is explicitly `code-derivedsavedoutputs_pretrajectory_empty`, not an original fsync SDK history mirror. Any observed science row without matching saved source is rejected rather than discarded or invented.

If a failed SDK has its native run/config, recorded exit 1 and clean EOF, its status is `FAILED_SOURCE_SDK_CLOSED_WITH_EXIT1`. If native run/exit is absent or the stream is incomplete, the status is `FAILED_SOURCE_SDK_INCOMPLETE_RAW_PRESERVED`. EOF at the end of a valid 7-byte header is only a file-reader observation; `native_closed=false`, missing IDs/exits and unknown role remain explicit. Native file names do not prove a recorded run identity or paired role. Where native config exists it must match the original configuration and recorded paired role; incomplete files receive no invented configuration proof. Malformed or contradictory scientific/config/identity data is rejected. The entire original SDK, logs and source artifacts remain available.

Each SDK receives a normalized JSONL, complete scalar CSV (`step,key,value_json`), HTML and machine certificate. An empty scientific history correctly produces empty JSONL and a CSV header, not fabricated null/loss rows. Each case also has a readable failure report and original source manifest. Selected sources remain capped at 128 MiB/case; the complete case remains capped at 256 MiB. Readers retain 500,000 native-packet / 100,000 history / 4 MiB record / 64 MiB export / 180-second scan limits; source journals have a 20-row / 128 KiB line / 4 MiB total bound. The fixed SDK symlink allowlist, owned ordinary-file checks, source rehash, private pending directory, shared task lock and merge/dedup rules are unchanged.

## Root verification request: prepared only

The suite has **40 expected parameterized tests**, including a real offline W&B SDK failed-exit-1 roundtrip with zero scientific rows. Other tests cover outer/child/SDK exit confusion, numeric gate/input/source drift, 85% cap versus OOM claims, cleanup preservation, header-only/absent-exit/broken-EOF evidence, wrong/duplicate native identity, native config changes, unexpected scientific rows, budgets and two-pass source drift. No CUDA is mocked or exercised and no new scientific acceptance is claimed.

Use the existing pytest/W&B 0.28.1/protobuf environment. Root binds a currently available actual CPU node in partition `cpu`, at least 16 CPUs, 4 GiB RAM and 10 minutes. Set `CUDA_VISIBLE_DEVICES=''` and `PYTHONDONTWRITEBYTECODE=1`. The test directory and pytest private base-temp must be admitted by Root's unit-output census. Compare every source pin before and after the test.

```bash
python -m pytest -q -p no:cacheprovider \
  runs/model_v3_20261025/archive_closed_v11_source/test_archive_v11.py \
  --basetemp /tmp/mv3n_JOBID/pytest
```

Only after an actual test PASS, Root creates a fresh SHA-bound sonmi quota/closed-job receipt, at most 120 seconds old, with these exact actual terminal lines: `4520589|FAILED|1:0` and `4520590|FAILED|1:0`. Keep the existing filesystem quota/reserve requirement and refresh CPU/resource admission before submission. The source inventory `source_pins_v11.json` and its separately recorded raw SHA bind this package, all reused implementations, the actual 8ece scientific source bindings, original SDK files and all selected case metadata.

```bash
python runs/model_v3_20261025/archive_closed_v11_source/archive_closed_runs_v11.py \
  --source-pins runs/model_v3_20261025/archive_closed_v11_source/source_pins_v11.json \
  --source-pins-sha256 PIN_RAW_SHA \
  --quota-closed-receipt FRESH_RECEIPT_JSON \
  --quota-closed-sha256 RECEIPT_RAW_SHA \
  --expected-node ACTUAL_CPU_NODE --expected-partition cpu \
  --jobs 4520589 4520590
```

Publication appends under `runs/phase1_full_corpus/wandb_archive/model_v3_20261025/closed_v11/job<ID>` using the existing task `.archive.lock`. The prior 51 entries remain intact. Two SDKs for each new case would produce 55 entries if no conflicting identity intervenes; this is a predicted index count, not execution. No existing original or archive entry is moved, deleted or replaced. A failed attempt retains its pending directory for review.
