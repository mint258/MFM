# Native-S operational v4: same science, bounded quota retry, same-host census

Prepared source only. No tests, model job, repair, quota reservation, SSH or
submission were executed while preparing this package. Root performs actual
source/AST review, failed-metadata reconciliation and any next submission.

The frozen v3 directory and failed job4521411 remain unchanged. Its actual
terminal is FAILED1:0 after29:28, not a successful segment. The last observed
history metadata reached723 updates, but no committed endpoint checkpoint or
member_result exists. Those partial updates are not accepted or resumed.

The primary failure was the original `Quota feed stale or future` refusal.
The exact refused feed was not saved, so stale versus future is undetermined.
The current clock observations cannot establish the old refusal's cause.
Only `Native_S_1411_host_clock_and_inode_actual_v2.json` is referenced here;
the earlier trust-configuration probe is superseded.

The later Root seal failed after it had already appended index8
`failed_attempts` and index9 `segment_terminal`. Root login and compute21 have
different host-local st_dev values for the same shared directory, with the
same inode. This is separate from the original quota failure.

## Changes

- `quota_retry.py` decorates only this policy instance's `ledger.refresh`.
  Only exact `ValueError('Quota feed stale or future')` is retried. Each episode
  permits at most30 monotonic seconds, with1s re-read intervals. The original
  full validator must pass its unchanged0..90s freshness, lease, source,
  principal, quota, inode and all other checks before model work resumes.
  Other errors and timeout fail. There is no model/optimizer/cursor callback
  inside the retry, and no rollback, skipped validation, feed rewrite or age
  tolerance change.
- Rejected bytes come from the exact original validator traceback frame,
  verified against its feed_ref and parsed feed. They are saved byte-for-byte
  under child/quota_age_rejections with age, observation time, host, source
  and bound validator SHA. At most256 rejections/segment are retained; raw
  feed<=2MiB and compact observation<=64KiB. Only selected metadata locals are
  extracted; model/data locals are not serialized. Missing evidence fails.
- Original wall/finalization reserve, GPU/resource guard, child/whole output
  census run during waiting, before each write and after a successful refresh.
  Original2h Slurm/7100s supervisor/6900s child/RSS28GiB/whole2GiB/private2GiB,
  existing128GiB durable reservation and all lifetime counters remain.
- New child configuration and SDK config explicitly record the retry source.
  Model Core, seed, precision, optimizer/RNG, data, plan, principal, shared
  scientific configuration and existing readiness/profile authority do not change.
- `same_host_census.py` executes the original `long_frames.whole_census` on
  compute-0-21 as UID1278. The original baseline device+inode gate remains
  intact. `seal_support.py` records the real trusted SSH command and result;
  it uses `OLD/compute21_known_hosts_v1`, StrictHostKeyChecking=yes and -n,
  matching frozen V8 resources.py. It neither changes user known_hosts nor
  reads model/SDK payloads. The command is metadata-only.
- `long_seal.py` uses that original-host census. The remaining durable hold
  is recalculated after writing the final seal receipt, including its bytes.
- `repair_failed.py` is a one-off FAILED1411 metadata reconciliation. It
  requires exactly9 already-materialized intents, reuses8/9 and the original
  actual FAILED terminal/supervisor/storage closure. It uses a read-only
  DurableLedger view for original chain/root checks; it does not construct a
  live ledger, refresh authority, append, call seal_segment or create a CP.
  It fills only missing Root seal/FAILED closure metadata and updates the
  original registry remainder from an actual inclusive retained-root census.
  Partial repair never automatically replays. All original bytes remain.
- `adopt_operational.py` appends OPERATIONAL_ADOPTION_v4.json, binding the
  exact existing VALIDATED/config/profile/roots/runtime/principal to this new
  operational source manifest. It never rewrites VALIDATED or scientific
  configuration, resets counts, creates a new reservation, or claims science.
  Submission checks this explicit adoption; next slot2 begins at u0.

## Root commands

Use the existing Root login metadata environment. These are instructions,
not records of execution. Replace PROJECT with the real absolute project root.
The SHA is obtained from the actual machine file, never copied from a terminal
line wrap. Root must inspect actual AST/hash results before using the package.

```bash
P=/share/home/zixiao/descriptor_analysis
S=$P/runs/model_v3_20261026/native_S_long_operational_v4
F=$P/runs/model_v3_20261026/native_S_B20k_v3
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins.json" | cut -d' ' -f1)
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
"$PY" -B "$S/repair_failed.py" --phase "$F" --pins-sha256 "$PIN"
"$PY" -B "$S/adopt_operational.py" --phase "$F" --pins-sha256 "$PIN"
"$PY" -B "$S/long_operations.py" dryrun --phase "$F" --retry-failed
# Root alone, after reviewing real FAILED repair and u0 dryrun:
"$PY" -u -B "$S/long_operations.py" submit-next --phase "$F" --pins-sha256 "$PIN" --retry-failed
```

Only the last command can submit a model job. Original Root resource checks,
public UUID lock,20s quota publisher, finite intent/attempt accounting and
actual terminal closure remain. New source receipt is operational; it does not
grant final-D authority, proxy selection, four-curve acceptance or final recipe.

## Meaningful preflight tests

Actual next model job runs original4 metadata cases plus new4 quota cases in
one pytest process, exact8/zeroSkip/source-before-after required, failed-retention
enabled. No separate QA parent or full regression is requested. The4 new cases
cover exact transient refusal with original validator success and exact raw
snapshot, persistent30s timeout, unrelated failure without retry, and missing
traceback/budget fail-closed behavior. All tests use metadata/fake clock, no
model, SDK, CP, native data or scheduler. Their output is small and caps stay
unchanged. Synthetic success would prove operational cases only; the actual
next segment still needs its own Root C0, safe CP and independent SDK audit.

`source_pins.json` binds all leaf files. Unchanged copied v3 leaves retain
their raw bytes; dependency_pins.json binds the original package/source files,
V8/V2 authorities, actual v2 clock/inode proof and trusted knownhost file.
No Python/tests/SSH/Git/Slurm were run during preparation.
