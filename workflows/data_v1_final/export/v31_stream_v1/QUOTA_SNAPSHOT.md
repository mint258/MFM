One shared login-host quota snapshot
===================================

Prepare only; Root starts one metadata-only publisher on the Main login host.
It runs `/usr/sbin/xfs_quota -c 'quota -u -b zixiao' /share` every2seconds,
checks the exact UID1278/header/mount and explicit positive hardKiB limit,
and publishes max(0,hard-used)*1024 available bytes. Failed probes, parses or
control-target capacity checks leave the last observed_time unchanged. The JSON
is replaced atomically beside the requested existing CONTROL directory; no hash,
label/geometry reads, worker SSH or scientific computation is involved.

Root startup CLI (substitute the unique shared CONTROL path):
`python -B -m workflows.data_v1_final.export.v31_stream_v1.quota_snapshot --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/share_quota_available.json`

The publisher initially resolves actual mount/df bytes/inodes, then protects its
small metadata writes using actual statvfs plus at least100GB filesystem/account
reserve. A stricter site reserve can be passed with --reserve-bytes. Unknown or
insufficient capacity never refreshes the snapshot. Root controls its process;
this source change neither starts it nor edits active plans.

In each limited-quota disk_guard target use:
- quota_available_reference: the absolute JSON path (or {'path':path})
- quota_expected_uid:1278
- quota_expected_filesystem:'/share'
- quota_max_age_seconds:5 (positive and no greater than5)

Retain the original quota peak/concurrent/reserve budget fields. Reference mode
replaces quota_probe_argv; argv-only plans remain supported by disk_guard. Its
reference branch must read/check the tiny JSON on every guard check, rather than
reuse freshness for another poll interval. Reader API:
`read_available(reference, *, expected_uid, expected_filesystem, max_age_seconds, now=None) -> int`
Malformed, unreadable, future-dated, stale or mismatched snapshots raise
SnapshotUnavailable. disk_guard wraps that as DiskUnavailable and its existing
wait preserves all closed work until capacity information recovers.

Only new fixture; Root runs once in its actual safe-temp parent:
`python -B -m unittest workflows.data_v1_final.export.v31_stream_v1.test_quota_snapshot`
Optional conservative clock safety bias
--------------------------------------

Root may explicitly pass `--clock-safety-bias-seconds 1.25` after measuring a client clock lag. Default0 preserves prior timestamps.
Each snapshot retains the actual source_probe_time and records the explicit
clock_safety_bias_seconds; observed_time is source_probe_time minus that bias.
This is a conservative lower timestamp bound, so client-side age is increased.
It does not change a system clock or extend the reader's five-second freshness
window. Bias must be finite, nonnegative and strictly below5seconds, the whole
freshness window; larger values cannot provide a usable fresh publication.

For measured compute0 lag0.995seconds, Root's explicit1.25-second bias leaves
0.255seconds conservative margin at publication. UID, filesystem, future-time
rejection and strict max_age<=5second checks in read_available are unchanged.
Root alone rolls the metadata publisher with the explicit CLI flag; no worker,
scientific parameter or active plan is modified by this source update.

Only new pure fixture for this update; prior snapshot fixture stays passed:
python -B -m unittest workflows.data_v1_final.export.v31_stream_v1.test_quota_snapshot.QuotaSnapshot.test_conservative_clock_bias_preserves_strict_freshness