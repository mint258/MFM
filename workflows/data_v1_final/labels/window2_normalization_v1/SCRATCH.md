Optional group output on node-local scratch
==========================================

Keep the existing shared `--output`, source arguments and worker count. Add:

```text
--group-scratch-root /tmp/window2_D4_groups --scratch-from-pass 2
```

These are runtime I/O choices and do not alter the frozen checkpoint inputs.
Only missing groups in the chosen future passes use local output. Existing
checkpoint group references are reused before dispatch, with no replay.

The original group kernel and reader run unchanged in a local group directory.
After all SQLite and Parquet writers close, the producer copies each generated
file once to the new shared attempt/group directory. It rewrites the four output
references and publishes the shared `report.json` last. The existing report is
the closed group manifest; no receipt, hash or numeric readback is added. It
carries the frozen input JSON, original shared stage reference and group identity
so a future retry can adopt that exact closed publication even if the parent
had not yet saved its reference. Shared source references remain authoritative.
Local files and failed publications are retained.

The live runner has no single-pass exit hook and automatically starts the next
pass after saving its boundary checkpoint. New code cannot change an already
running Python process. Do not interrupt busy groups to adopt this option:
unclosed groups have no durable intermediate TSQR state. Root chooses a later
recovery or future parent. This option does not stage compact numeric inputs
or existing derived input SQLite; their original reads remain unchanged.

New fixture only, to run once in an actual parent:

```text
python -B -m unittest workflows.data_v1_final.labels.window2_normalization_v1.test_group_scratch
```
