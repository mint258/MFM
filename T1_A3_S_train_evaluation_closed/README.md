# Complete T1 A3/S training and evaluation offline SDKs

Jobs4529728/4529744:2 closed sessions,36 ordinary files,23302334 gzip bytes,8 ordered parts. Archive4530191 completed0:0/1CPU/16seconds on compute-0-20. Raw .wandb, per-update losses/history,1000-update means and producer-derived native-key hardware series/summaries are included. Originals retained; no cloud sync, rerun or deletion. Running A3/P is excluded.

Download all parts into one directory. Linux:
```bash
cat T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz.part* > T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz
tar -xzf T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$out=[IO.File]::Create('T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz')
try {
  1..8 | ForEach-Object {
    $part=[IO.File]::OpenRead('T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz.part'+$_.ToString('00'))
    try {$part.CopyTo($out)} finally {$part.Dispose()}
  }
} finally {$out.Dispose()}
tar -xzf T1_A3_S_train_evaluation_offline_SDK_20261112.tar.gz
```

See manifest.json for source paths and byte counts.
