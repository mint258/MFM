# T1 A0/S and A1/S: complete closed training SDKs

Actual training jobs4529725/4529726 each completed1,500,000 continuation samples (cumulative7,500,000), seed0, effective batch32. Both original SDK finish markers report success. This bundle contains both complete training SDK directories and derived native system-statistics JSONL/summaries; evaluation SDKs and the remaining T1 arms are outside this bundle.

Archive job4529994 completed0:0 on compute-0-20,1CPU,14seconds. 51 ordinary files;18890531 gzip bytes. Original SDKs are retained. No cloud sync or weight/data upload.

Download all seven `T1_A0_A1_S_training_offline_SDK_20261112.tar.gz.part01` through `.part07` into one directory. Linux:

```bash
cat T1_A0_A1_S_training_offline_SDK_20261112.tar.gz.part0[1-7] > T1_A0_A1_S_training_offline_SDK_20261112.tar.gz
tar -xzf T1_A0_A1_S_training_offline_SDK_20261112.tar.gz
```

PowerShell:

```powershell
$target = [IO.File]::Create('T1_A0_A1_S_training_offline_SDK_20261112.tar.gz')
try {
    1..7 | ForEach-Object {
        $part = [IO.File]::OpenRead(('T1_A0_A1_S_training_offline_SDK_20261112.tar.gz.part{0:D2}' -f $_))
        try { $part.CopyTo($target) } finally { $part.Dispose() }
    }
} finally { $target.Dispose() }
tar -xzf T1_A0_A1_S_training_offline_SDK_20261112.tar.gz
```

The manifest lists ordered part offsets/lengths and returned GitHub blob SHAs. Raw SDK records include per-update losses,1000-update means,100k sample snapshots and native system metrics every30seconds. Device-wide GPU metrics differ from own-process torch allocator peaks; earlier node5 sharing remains documented. Native names/units are preserved.
