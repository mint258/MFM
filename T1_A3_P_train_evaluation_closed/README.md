# Complete T1 A3/P training and evaluation offline SDKs

Jobs 4530203/4530204: 2 closed sessions, 36 ordinary files, 23587202 gzip bytes, 8 ordered parts. Archive job 4530194 completed 0:0 on compute-0-20. Includes original .wandb files, per-update loss/history, 1000-update means and producer-derived native hardware series/summaries. Original files retained. These are historical original-panel logs; the separately queued atomization/report-only re-evaluations do not overwrite them.

Download all parts into one directory. Linux:
```bash
cat T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz.part* > T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz
tar -xzf T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$out=[IO.File]::Create('T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz')
try {
  1..8 | ForEach-Object {
    $part=[IO.File]::OpenRead('T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz.part'+$_.ToString('00'))
    try {$part.CopyTo($out)} finally {$part.Dispose()}
  }
} finally {$out.Dispose()}
tar -xzf T1_A3_P_train_evaluation_offline_SDK_20261112.tar.gz
```

See manifest.json for source paths, original byte counts and ordered GitHub parts.
