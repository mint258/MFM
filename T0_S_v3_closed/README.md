# T0 S frozen-backbone training and evaluation

Actual jobs: 4529723, 4529739, 4529724, 4529740. All included SDK sessions are closed. 51 regular files (original SDKs plus derived readable system reports), 166124897 uncompressed bytes, 22394470 gzip bytes. Original server files are retained. No cloud synchronization.

Download every binary part and manifest.json from this directory, then join and extract:

```bash
cat T0_S_offline_SDK_20261111.tar.gz.part{01..08} > T0_S_offline_SDK_20261111.tar.gz
tar -xzf T0_S_offline_SDK_20261111.tar.gz
```

Windows PowerShell:

```powershell
$out=[IO.File]::Create((Join-Path $PWD 'T0_S_offline_SDK_20261111.tar.gz'))
try { 1..8 | ForEach-Object { $p=Join-Path $PWD ('T0_S_offline_SDK_20261111.tar.gz.part{0:D2}' -f $_); $s=[IO.File]::OpenRead($p); try { $s.CopyTo($out) } finally { $s.Dispose() } } } finally { $out.Dispose() }
tar -xzf T0_S_offline_SDK_20261111.tar.gz
```

The archive includes the complete regular-file SDK directories, original .wandb streams and their existing histories/snapshots/completion markers, plus native timestamped hardware JSONL and observed-mean/min/max summaries. SDK navigation symlinks are omitted; their regular-file targets are retained. Model weights, checkpoints, task-label arrays and credentials are excluded.

[Readable native system summaries](system_report_summary.json) preserve all native metric names and units. Device-wide GPU statistics can include other compute contexts. Legacy diagnostic StatsRecords describe the recorder host; customized remote training observations remain in original HistoryRecords/system_metrics.jsonl. They are not relabeled as native training-device measurements.
