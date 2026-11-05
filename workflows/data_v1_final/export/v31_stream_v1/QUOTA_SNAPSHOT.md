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