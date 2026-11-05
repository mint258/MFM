Prepared Lustre protection for two existing non-Native jobs
========================================================

Root alone installs/starts this control. No signal, background process, actual
profile, Native work, Slurm admin setting or live producer is changed by source.
Allowed jobs are only4526117 D4/start2026-11-05T22:55:09/node20 and4526127
UFF/start2026-11-06T02:36:27/node19, UID1278 with exact established job names.
The controller checks identity again before every STOP/CONT. This cluster's
scancel --full signals batch shell plus all steps; the source always supplies
--signal explicitly, --user1278, exact job name and exact job ID. No cancellation.

Root prepares one profile after actual node checks. Required fields:
- jobs: exact JOBS constant from the helper (identity is immutable)
- quota_reference: unique NFS CONTROL JSON for Lustre quota
- quota_reserve_bytes: at least100000000000
- runtime_margin_bytes: at least8589934592 (8GiB burst for all owned writers)
- runtime_margin_inodes: positive explicit burst allowance
- max_age_seconds: positive, at most5
- nodes: compute-0-20 and compute-0-19 each with reference and targets
- each target: actual path, mount{target,source,fstype} from Root's node check,
  reserve_bytes/reserve_inodes/concurrent_bytes/concurrent_inodes as nonnegative
  integers. Root filesystem automatically retains max10GiB/10percent too.

Actual target paths to inspect, never infer the mount identity:
node20 /lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_normalization_20261105_v1
node19 /lfshome/zixiao/data_v1_20261025/window2_full_UFF_D3_20261105_v1
Quota has100GB reserve. Root accounts other writers once; the held D6 and future
NFS PPstats do not add Lustre writes. CONTROL fixed-size JSON/partial/state fits
Root's existing1GiB NFS metadata allowance. No unbounded per-event file is added.

Use the script's absolute path as HELPER and the checked immutable profile as
PROFILE below. From project-root Python with repo/deps on PYTHONPATH:
login: python -B HELPER --profile PROFILE quota --output QUOTA_REFERENCE
node20: python -B HELPER --profile PROFILE capacity --node compute-0-20
node19: python -B HELPER --profile PROFILE capacity --node compute-0-19
Each runs every2seconds; capacity obtains actual findmnt/df bytes/inodes and
statvfs on that node. A failed probe never refreshes its old timestamp. Snapshot
freshness is checked on every controller read, including immediately before CONT.

Preview (no signal): python -B HELPER --profile PROFILE watch --state STATE
Root start: python -B HELPER --profile PROFILE watch --state STATE --execute
Root safe recovery: python -B HELPER --profile PROFILE resume --state STATE --execute

Unknown/stale/future/capacity-low snapshots cause STOP of identity-verified
RUNNING owned writers. CONT is restricted to this helper's STOP_ACKNOWLEDGED
records and fresh safe capacity. Exit rechecks the same conditions; unsafe or
unknown leaves the job parked and atomically preserves recovery state, printing
the exact recovery command. STOP_REQUESTED without acknowledgement is retained
as uncertain; it never authorizes automatic CONT. Scheduler/identity failures
are reported, never guessed. Root must address a scheduler outage if signal
requests cannot be delivered; no controller can promise delivery during one.

Only one new fixture, Root runs once in an actual safe-temp parent:
python -B -m unittest workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.control_helpers.test_lustre_non_native_writer_guard
No existing quota/temporary/guard tests are repeated.