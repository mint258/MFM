# Closed T1 A0/P and A1/P training SDKs

Jobs4529732/4529733 each completed the original1.5M continuation (7.5M cumulative). Two closed offline SDK sessions,51 ordinary files,18928411 gzip bytes. Archive4530008 completed0:0 on compute-0-20 with1CPU in14seconds. Seven binary parts retain all original bytes.

Download all seven parts into the same directory. Linux:
```bash
cat T1_A0_A1_P_training_offline_SDK_20261112.tar.gz.part0{1..7} > T1_A0_A1_P_training_offline_SDK_20261112.tar.gz
tar -xzf T1_A0_A1_P_training_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$joined = [IO.File]::Create('T1_A0_A1_P_training_offline_SDK_20261112.tar.gz')
try {
  1..7 | ForEach-Object {
    $partPath = 'T1_A0_A1_P_training_offline_SDK_20261112.tar.gz.part' + $_.ToString('00')
    $part = [IO.File]::OpenRead($partPath)
    try { $part.CopyTo($joined) } finally { $part.Dispose() }
  }
} finally { $joined.Dispose() }
tar -xzf T1_A0_A1_P_training_offline_SDK_20261112.tar.gz
```

The native .wandb files, per-update loss/history,1000-update loss means,snapshots and producer-derived native-key system JSONL/summaries are included. Files remain on the server. Navigation symlinks are omitted. No checkpoints, scientific data, cloud sync, model rerun or file deletion. Paired evaluations are separate executions and are not represented here as completed. See manifest.json for paths and sizes.
