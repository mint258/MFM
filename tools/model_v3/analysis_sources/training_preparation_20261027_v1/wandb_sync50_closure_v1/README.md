# Root closure and next-three listing, source-only

Root supplies an explicit complete list of the accepted pilot/batch
`RESULT.json` paths. This metadata-only helper verifies frozenv3 sources and
requests, source hashes before/after and now, actual same-job supervision,
four zero-skip QA counts/XML refs, every successful child invocation and
per-run source/state/row-count/step/action metadata. It does not open original
or staged SDK payloads, query cloud APIs, submit/monitor jobs or retry.

It captures one exact raw `sacct -X -n -P -j EXPLICIT_JOB_LIST
--format=JobIDRaw,State,ExitCode` on Root sonmi. Alternatively `--raw-sacct`
accepts that exact actual raw-command JSON. Every supplied parent must be
COMPLETED0:0, with a successful matching supervisor and per-run results.
Failed1408/1410 are preserved and cannot enter this accepted-C0 list. The
existing actual1410 upload is not relabeled or replayed.

```bash
PY5090 -B N/wandb_sync50_closure_v1/close_and_next.py \
  --completed N/WandB_sync50_pilot_actual_v3/RESULT.json \
              N/WandB_sync50_batch01_actual_v3/RESULT.json \
  --output N/WandB_sync50_closure_after_batch01_v1 \
  --pins-sha256 ACTUAL_HELPER_MANIFEST_SHA
```

Root expands PY5090 and N as usual. Append every subsequently completed
batch to `--completed`, use a fresh output, and invoke again explicitly.
The helper retains all supplied closures and deduplicates accepted runIDs;
it subtracts them from the original fixed50 order and lists at most3 next
IDs. Its output includes an argv TEMPLATE for the existing frozen
`prepare_sync.py`; Root chooses fresh plan/job paths and separately invokes
prepare and the existing live-admission submit helper. No command in the
template is executed here. Budgets and the three-run limit do not change.

4sgxpx8j is flagged when its turn arrives: only
REMOTE_ALREADY_MATCHED_NO_REPLAY is accepted for that already-uploaded ID.
Root must keep that batch's cloud preflight present/matching; do not replay
it if the cloud lookup fails or is unavailable. This helper cannot enforce
a future network operation: it validates existing results and lists next
IDs only. A previously accepted cloud route does not grant another replay.

At authoring time, Root reported actual1412/1414 C0 and4/50 accepted IDs;
the helper itself has not run. It will derive counts and next IDs from
the actual metadata and raw terminal output, rather than trusting this prose.
