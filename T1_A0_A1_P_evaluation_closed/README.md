# T1_A0_A1_P_evaluation_closed

Complete closed offline SDK bundle: 4530187,4529749. 21 original/derived ordinary files, 20824400 gzip bytes, 7 ordered binary parts. Raw .wandb, histories and native-key hardware series/summaries included; server originals retained. No cloud sync, model rerun or scientific rescoring.

Linux reconstruction (download all parts into one directory):
```bash
cat T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz.part* > T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz
tar -xzf T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$out = [IO.File]::Create('T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz')
try {
  1..7 | ForEach-Object {
    $part = [IO.File]::OpenRead('T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz.part'+$_.ToString('00'))
    try { $part.CopyTo($out) } finally { $part.Dispose() }
  }
} finally { $out.Dispose() }
tar -xzf T1_A0_A1_P_evaluation_offline_SDK_20261112.tar.gz
```

See manifest.json for source paths and part sizes.
