param(
 [Parameter(Mandatory=$true)][ValidatePattern('^/gfshome/alpha/codex_data_v1_20261026/control/pubchem_completion_environment_20261103/[A-Za-z0-9_.-]+\.json$')][string]$TargetConfig,
 [Parameter(Mandatory=$true)][ValidatePattern('^/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103/[A-Za-z0-9_.-]+\.json$')][string]$SourceIndex
)
$ErrorActionPreference='Stop'
$taskTargetCmd='/gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python -I -B /gfshome/alpha/codex_data_v1_20261026/control/pubchem_completion_environment_20261103/main_rescue_score_transport_20261104_v1.py receive --config '+$TargetConfig
$taskTargetInfo=[Diagnostics.ProcessStartInfo]::new('ssh.exe','-T -o BatchMode=yes -o ConnectTimeout=10 alpha@218.192.171.238 "'+$taskTargetCmd+'"')
$taskTargetInfo.UseShellExecute=$false;$taskTargetInfo.CreateNoWindow=$true
$taskTargetInfo.RedirectStandardInput=$true;$taskTargetInfo.RedirectStandardOutput=$true;$taskTargetInfo.RedirectStandardError=$true
$taskTarget=[Diagnostics.Process]::Start($taskTargetInfo)
$taskTargetErr=$taskTarget.StandardError.ReadToEndAsync()
$taskSource=$null;$taskSourceErr=$null
try {
 $taskReady=$taskTarget.StandardOutput.ReadLine()
 if($taskReady -ne 'READY'){$taskTarget.WaitForExit();throw('Target not ready: '+$taskReady+' stderr='+$taskTargetErr.Result)}
 $taskTargetOut=$taskTarget.StandardOutput.ReadToEndAsync()
 $taskMainPython='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/software/pubchem_completion_20261103_venv/bin/python'
 $taskMainScript='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/pubchem_completion_20261103/workflows/expansion/completion_runtime_v1/main_rescue_score_transport.py'
 $taskKnown='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103/main16_verified_known_hosts_20261104'
 $taskSourceCmd='ssh -n -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519 -o UserKnownHostsFile='+$taskKnown+' compute-0-16 '+$taskMainPython+' -I -B '+$taskMainScript+' send --index '+$SourceIndex
 $taskSourceInfo=[Diagnostics.ProcessStartInfo]::new('ssh.exe','-n -T -o BatchMode=yes -o ConnectTimeout=10 descriptor-analysis-remote "'+$taskSourceCmd+'"')
 $taskSourceInfo.UseShellExecute=$false;$taskSourceInfo.CreateNoWindow=$true
 $taskSourceInfo.RedirectStandardOutput=$true;$taskSourceInfo.RedirectStandardError=$true
 $taskSource=[Diagnostics.Process]::Start($taskSourceInfo);$taskSourceErr=$taskSource.StandardError.ReadToEndAsync()
 Write-Output ('BINARY_SCORE_COPY_STARTED source_pid='+$taskSource.Id+' target_pid='+$taskTarget.Id)
 $taskSource.StandardOutput.BaseStream.CopyTo($taskTarget.StandardInput.BaseStream,1048576)
 $taskTarget.StandardInput.Close();$taskSource.WaitForExit();$taskTarget.WaitForExit()
 if($taskSource.ExitCode -ne 0 -or $taskTarget.ExitCode -ne 0) {
  throw('Closed-score IO failed source='+$taskSource.ExitCode+' target='+$taskTarget.ExitCode+' source_stderr='+$taskSourceErr.Result+' target_stderr='+$taskTargetErr.Result)
 }
 Write-Output $taskTargetOut.Result
 Write-Output ('SOURCE_IO_STATUS '+$taskSourceErr.Result)
} catch {
 if($taskTarget.HasExited){Write-Output ('TARGET_IO_STDERR '+$taskTargetErr.Result)}
 if($taskSource -and $taskSource.HasExited){Write-Output ('SOURCE_IO_STDERR '+$taskSourceErr.Result)}
 # Only the two exact newly-created local SSH IO processes are stopped on copy error.
 # Their remote commands transfer closed files; neither runs or restarts scientific computation.
 if($taskSource -and -not $taskSource.HasExited){$taskSource.Kill();$taskSource.WaitForExit()}
 if(-not $taskTarget.HasExited){$taskTarget.Kill();$taskTarget.WaitForExit()}
 throw
}
