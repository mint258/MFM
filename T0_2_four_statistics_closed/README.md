# T0_2_four_statistics_closed

Complete closed offline SDK bundle: 4529737. 11 original/derived ordinary files, 12345092 gzip bytes, 4 ordered binary parts. Raw .wandb, histories and native-key hardware series/summaries included; server originals retained. No cloud sync, model rerun or scientific rescoring.

Linux reconstruction (download all parts into one directory):
```bash
cat T0_2_four_statistics_offline_SDK_20261112.tar.gz.part* > T0_2_four_statistics_offline_SDK_20261112.tar.gz
tar -xzf T0_2_four_statistics_offline_SDK_20261112.tar.gz
```

PowerShell:
```powershell
$out = [IO.File]::Create('T0_2_four_statistics_offline_SDK_20261112.tar.gz')
try {
  1..4 | ForEach-Object {
    $part = [IO.File]::OpenRead('T0_2_four_statistics_offline_SDK_20261112.tar.gz.part'+$_.ToString('00'))
    try { $part.CopyTo($out) } finally { $part.Dispose() }
  }
} finally { $out.Dispose() }
tar -xzf T0_2_four_statistics_offline_SDK_20261112.tar.gz
```

See manifest.json for source paths and part sizes.
