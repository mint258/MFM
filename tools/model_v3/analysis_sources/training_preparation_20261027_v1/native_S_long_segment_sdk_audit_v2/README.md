# Closed Native-S long SDK audit v2

Prepared source only; no active SDK, history, checkpoint or model payload was
read. No Python, tests, SSH, Git, Slurm or network ran during preparation.
This package does not claim v4 execution or SDK verification has passed.
The v1 auditor and operational_v4 sources remain unchanged.

Static review found no17-key config whitelist in the long auditor. It uses
generic `tap.Audit`, which compares the entire saved expected config exactly
before every native history record and at EOF. It does not call the short20
profile-specific `tap.prepare` function. Thus the extra v4 retry fields would
already be fully compared. However, v1 pins v3 long_child.py and rejects an
actual v4 producer before scanning. This v2 binds the actual v4 producer.

Changes are limited to the v4 child/seal/package/quota source dependencies,
explicit operational provenance validation,28 metadata tests instead of21,
and the new source directory in the CPU batch entry. The literal-key reader749,
tap Audit and read-only full-framing decoder are reused unchanged. All old21
test cases remain;7 additional cases cover full native comparison with the
v4 addition, path/SHA/wait/count/saved-config drift, and a changed native quota
SHA field. The SDK byte limit128MiB, native-record500k/history100k caps,
4MiB record,64MiB export and180s inclusive per-segment deadline remain.

`check_operational_sources` requires the actual child/Core raw refs, both
saved configs' identical typed retry metadata, exact30s/256 policy, true
unchanged-numerics marker and actual quota_retry path/SHA. The auditor binds
the actual segment package and operational adoption, configuration and
original principal. All those raw refs are checked before and after decode.
Full native config comparison still includes every field; no field is
filtered to make v4 pass. Summary, history fields, typed values, runID,
explicit global steps/cursor, physical consumed draws, parent continuation,
source/code/data/seed/precision, exit0 and complete fragment EOF all retain
the original checks. Scope remains LONG_SEGMENT_LOG_ONLY, never B acceptance.

Only explicit actually closed C0 segments may be prepared, at most3 per CPU
batch. Failed1411 is rejected by this auditor and requires its separate
honest failed-log integrity scan. Short-profile or readiness C0 is not a
substitute for any long segment's native proof. The future segment jobID and
terminal are never prefilled.

Root uses its existing source/AST/hash review, then after actual closure:

```bash
P=/share/home/zixiao/descriptor_analysis
S=$P/runs/model_v3_20261026/native_S_long_segment_sdk_audit_v2
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
# Metadata-only: select an actually closed slot, fresh output. This performs
# no SDK/history payload decode; the true future closed slot is a Root input.
"$PY" -B "$S/audit_closed_segments.py" prepare \
  --phase "$P/runs/model_v3_20261026/native_S_B20k_v3" \
  --slot CLOSED_SLOT_NUMBER --output FRESH_ABSOLUTE_INPUT_DIRECTORY
```

One original supervised16CPU/16GiB CPU allocation runs28 metadata tests
(zeroSkip, failed-retention) followed by the1..3 explicit closed SDK scans.
No extra per-component QA parent is needed. The included batch keeps20min
Slurm,900s supervisor/RSS12GiB and2GiB original CPU output/private protection.
Root sets `MODEL_V3_EXPECTED_NODE`, `MODEL_V3_LONG_LOG_INPUTS`,
`MODEL_V3_LONG_LOG_INPUTS_SHA`, `MODEL_V3_LONG_LOG_PINS_SHA`, and
`MODEL_V3_LONG_LOG_OUTPUT` to machine-bound actual paths/SHAs, then uses the
normal CPU submission helper with the thin OLD wrapper. Every SHA should be
read from the machine file, never hand-copied from terminal wrapping.

Raw SDK originals are read-only and retained. Only compact aggregate
certificates/raw source references are exported, no prediction/member IDs,
weights, native target records or SDK history payloads. Actual CPU parent
C0, source-before/after and supervisor closure must be supplied by Root
after the run; child output alone never declares outer C0.
