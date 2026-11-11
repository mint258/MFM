# P / C1-0 / seed0：完整离线 W&B

三个实际训练执行4526376→4529096→4529108及配对诊断的六个SDK run均已finished。110个原始普通文件，未压缩227870694字节，gzip31671522字节；服务器原文件保留。SDK导航符号链接省略，其指向的普通文件均包含。未做云端同步，不包含模型权重或科学数据。

下载此目录全部part01–part11及manifest.json。在该目录运行：

```bash
cat P_C1_0_seed0_complete_wandb.tar.gz.part{01..11} > P_C1_0_seed0_complete_wandb.tar.gz
tar -xzf P_C1_0_seed0_complete_wandb.tar.gz
```

Windows PowerShell：

```powershell
$out=[IO.File]::Create((Join-Path $PWD 'P_C1_0_seed0_complete_wandb.tar.gz'))
try { 1..11 | ForEach-Object { $p=Join-Path $PWD ('P_C1_0_seed0_complete_wandb.tar.gz.part{0:D2}' -f $_); $s=[IO.File]::OpenRead($p); try { $s.CopyTo($out) } finally { $s.Dispose() } } } finally { $out.Dispose() }
tar -xzf P_C1_0_seed0_complete_wandb.tar.gz
```

每次实际执行独立run，保留原micro4/8/32分段、实际重放成本、逐更新loss、1000更新均值、真实系统观测及快照。文件明细见manifest.json。
