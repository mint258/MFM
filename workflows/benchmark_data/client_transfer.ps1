param(
  [Parameter(Mandatory=$true)][string[]]$Datasets,
  [string]$Workspace = 'X:\runs\data_v1_20261025\worktrees\benchmark_data_20261119',
  [ValidateRange(8,19)][int]$CpuNode = 16
)
# This is a client-side transport only. All quota checks and writes run on the CPU node.
$ErrorActionPreference = 'Stop'
$plan = Get-Content -LiteralPath (Join-Path $Workspace 'configs\benchmark_data\B0.plan.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$remoteBase = '/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119'
foreach ($dataset in $Datasets) {
  if ($dataset -notmatch '^[A-Za-z0-9_]+$') { throw 'Invalid dataset identifier' }
  $assets = $plan.assets.PSObject.Properties[$dataset].Value.files
  if (-not $assets) { throw "No source assets registered for $dataset" }
  $remote = "ssh -o BatchMode=yes compute-0-$CpuNode env PYTHONPATH=$remoteBase python3 -B -m workflows.benchmark_data.receive --plan $remoteBase/configs/benchmark_data/B0.plan.json --dataset $dataset --concurrent-reserve-bytes 114569896448"
  $info = [System.Diagnostics.ProcessStartInfo]::new()
  $info.FileName = (Get-Command ssh).Source
  $info.Arguments = '-o BatchMode=yes descriptor-analysis-remote "' + $remote + '"'
  $info.UseShellExecute = $false
  $info.RedirectStandardInput = $true
  $info.RedirectStandardOutput = $true
  $info.RedirectStandardError = $true
  $proc = [System.Diagnostics.Process]::Start($info)
  $transportError = $null
  try {
    foreach ($asset in $assets) {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $asset.url -TimeoutSec 45
      $data = $r.RawContentStream.ToArray()
      if ($data.Length -ne $asset.bytes) { throw "Transport size mismatch: $($asset.name)" }
      $frame = @{name=$asset.name;data=[Convert]::ToBase64String($data)} | ConvertTo-Json -Compress
      $proc.StandardInput.WriteLine($frame)
    }
  } catch { $transportError = $_.Exception.Message }
  finally { $proc.StandardInput.Close() }
  $outText = $proc.StandardOutput.ReadToEnd()
  $errText = $proc.StandardError.ReadToEnd()
  $proc.WaitForExit()
  Write-Output $outText
  if ($errText) { Write-Output $errText }
  $exitCode = $proc.ExitCode
  $proc.Dispose()
  if ($transportError -or $exitCode -ne 0) {
    Write-Output "SOURCE_BATCH_UNRESOLVED $dataset exit=$exitCode $transportError"
  } else {
    Write-Output "SOURCE_BATCH_CLOSED $dataset"
  }
}
