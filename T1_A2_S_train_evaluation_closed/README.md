# Closed T1 A2/S training and evaluation SDKs

Jobs4530010/4530011 completed0:0. Two actual closed SDK sessions,36 ordinary files,26007007 gzip bytes,9 ordered3MiB parts. Raw .wandb files, histories/losses,1000-update means and original/native-key hardware statistics are retained. Archive4530190 completed0:0/1CPU/18seconds on compute-0-20. Original server files remain; no model rerun, cloud sync or deletion.

Download every part into one directory. Linux:
```bash
cat T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz.part* > T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz
tar -xzf T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$out=[IO.File]::Create('T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz')
try {
  1..9 | ForEach-Object {
    $part=[IO.File]::OpenRead('T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz.part'+$_.ToString('00'))
    try {$part.CopyTo($out)} finally {$part.Dispose()}
  }
} finally {$out.Dispose()}
tar -xzf T1_A2_S_train_evaluation_offline_SDK_20261112.tar.gz
```

Source paths and part sizes are in manifest.json. A2/P is a separate running execution, excluded here.
