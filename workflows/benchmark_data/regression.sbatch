#!/bin/bash
#SBATCH --job-name=B0-full-regression
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=8
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=24:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_full_regression_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
export PYTHONPATH="$repo:$repo/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp
cd "$repo"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import importlib.util,json,os,socket
from pathlib import Path
from workflows.benchmark_data.pprime_tmpfs_queue import capacity
root=Path.cwd();control=root.parents[1]/'control';data=root.parents[1]/'artifacts/benchmark_B0_20261119'
assert socket.gethostname().split('.')[0] in {'compute-0-'+str(i) for i in range(8,20)}
s=os.statvfs('/tmp')
assert s.f_bavail*s.f_frsize>=max(10*1024**3,int(s.f_blocks*s.f_frsize*.1))+4*1024**3
assert s.f_favail>=100000
memory={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
assert memory['MemAvailable']>=24*1024**3+int(memory['MemTotal']*.15)
capacity(data,control/'benchmark_B0_quota_20261119.json',67108864)
paths=[p.decode('utf-8') for p in (control/'B0_source_paths_20261119.nul').read_bytes().split(b'\0') if p]
spec=importlib.util.spec_from_file_location('b0_required_repository_check',root/'tools/check_repository.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=module.check(root,paths,verify_export=False)
result.update(git_path_source='Actual native login git ls-files; Git absent on CPU nodes',actual_compute_node=socket.gethostname())
(control/'B0_source_check_20261119.json').write_text(json.dumps(result,indent=2)+'\n')
print('REPOSITORY_SOURCE_CHECK',json.dumps(result),flush=True)
assert result['status']=='PASS'
print('ACTUAL_FULL_REGRESSION_RESOURCES_ADMITTED',flush=True)
PY
case "${B0_REGRESSION_SCOPE:-repository}" in
 repository) target=. ;;
 benchmark_data) target=workflows/benchmark_data ;;
 *) exit 2 ;;
esac
printf 'REGRESSION_SCOPE %s\n' "$target"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest "$target" -q --import-mode=importlib --continue-on-collection-errors