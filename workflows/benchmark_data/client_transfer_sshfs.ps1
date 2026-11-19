param([string]$Attempt,[string[]]$Datasets)
$ErrorActionPreference='Stop'
$base='X:\runs\data_v1_20261025\artifacts\benchmark_B0_20261119'
$control=Join-Path $base ('transfer_control\'+$Attempt)
$plan=Get-Content -LiteralPath 'X:\runs\data_v1_20261025\worktrees\benchmark_data_20261119\configs\benchmark_data\B0.plan.json' -Encoding UTF8 -Raw|ConvertFrom-Json
$script:lastSeq=$null
$script:seenAdvance=$false
$script:lastFresh=[System.Diagnostics.Stopwatch]::StartNew()
function Wait-TransferLease {
 while($true){
  try{$lease=Get-Content -LiteralPath (Join-Path $control 'lease.json') -Encoding UTF8 -Raw|ConvertFrom-Json}catch{Start-Sleep -Milliseconds 200;continue}
  if($lease.attempt -ne $Attempt){throw 'Foreign capacity lease'}
  if($lease.seq -ne $script:lastSeq){
    if($null -ne $script:lastSeq){$script:seenAdvance=$true}
    $script:lastSeq=$lease.seq
    $script:lastFresh.Restart()
  }
  if($lease.state -ne 'RUNNING'){throw "Capacity guard is $($lease.state)"}
  if($script:lastFresh.Elapsed.TotalSeconds -gt 15){throw 'Capacity guard heartbeat expired; stop writes'}
  if($script:seenAdvance -and $lease.admitted -and $script:lastFresh.Elapsed.TotalSeconds -lt 5){return}
  Start-Sleep -Milliseconds 200
 }
}
$closed=[System.Collections.Generic.List[object]]::new()
foreach($group in $Datasets){
 foreach($asset in $plan.assets.PSObject.Properties[$group].Value.files){
  $r=Invoke-WebRequest -UseBasicParsing -Uri $asset.url -TimeoutSec 45
  $data=$r.RawContentStream.ToArray()
  if($data.Length -ne $asset.bytes){throw "Transport size mismatch $($asset.name)"}
  Wait-TransferLease
  $folder=Join-Path $base ('raw\'+$group)
  [System.IO.Directory]::CreateDirectory($folder)|Out-Null
  $target=Join-Path $folder $asset.name
  if([System.IO.File]::Exists($target)){
   if(([System.IO.FileInfo]::new($target)).Length -ne $data.Length){throw 'Existing source mismatch; preserve it'}
  }else{
   $f=[System.IO.File]::Open($target,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write)
   try{
    for($offset=0;$offset -lt $data.Length;$offset+=1048576){
     Wait-TransferLease
     $n=[Math]::Min(1048576,$data.Length-$offset)
     $f.Write($data,$offset,$n)
    }
   }finally{$f.Dispose()}
  }
  $closed.Add(@{dataset=$group;name=$asset.name})
  $progress=@{attempt=$Attempt;closed=@($closed.ToArray());done=$false}|ConvertTo-Json -Depth 5 -Compress
  [System.IO.File]::WriteAllText((Join-Path $control 'progress.json'),$progress,[System.Text.UTF8Encoding]::new($false))
  Write-Output "CLIENT_SOURCE_CLOSED $group $($asset.name) $($data.Length)"
 }
}
$progress=@{attempt=$Attempt;closed=@($closed.ToArray());done=$true}|ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText((Join-Path $control 'progress.json'),$progress,[System.Text.UTF8Encoding]::new($false))
