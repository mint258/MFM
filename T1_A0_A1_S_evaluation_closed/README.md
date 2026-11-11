# T1 A0/S and A1/S: complete closed evaluation SDKs

Actual frozen-encoder evaluation jobs4529741/4529742 completed successfully on the final continuation checkpoints. This bundle includes both original evaluation SDKs and derived native system reports. Training SDKs are in the separate T1_A0_A1_S_training_closed bundle; remaining T1 arms are pending their own closures.

Archive job4529995 completed0:0 on compute-0-20,1CPU,11seconds. 21 ordinary files;20800946 gzip bytes. Original SDKs are retained. No cloud sync or weight/data upload.

Download all seven `T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz.part01` through `.part07` into one directory. Linux:

```bash
cat T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz.part0[1-7] > T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz
tar -xzf T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz
```

PowerShell:

```powershell
$target = [IO.File]::Create('T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz')
try {
    1..7 | ForEach-Object {
        $part = [IO.File]::OpenRead(('T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz.part{0:D2}' -f $_))
        try { $part.CopyTo($target) } finally { $part.Dispose() }
    }
} finally { $target.Dispose() }
tar -xzf T1_A0_A1_S_evaluation_offline_SDK_20261112.tar.gz
```

The manifest lists ordered part offsets/lengths and returned GitHub blob SHAs. Raw evaluation SDKs preserve original probe/evaluation histories and native system metrics every30seconds. Per-update training losses/1000-update means/100k snapshots reside in the separate training bundle. Device-wide GPU metrics differ from own-process torch allocator peaks; earlier node5 sharing remains documented. Native names/units are preserved.
