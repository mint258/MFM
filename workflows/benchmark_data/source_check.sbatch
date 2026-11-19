#!/bin/bash
#SBATCH --job-name=B0-source-check
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_source_check_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import importlib.util,json,socket
from pathlib import Path
from workflows.benchmark_data.pprime_tmpfs_queue import capacity
root=Path.cwd();control=root.parents[1]/'control'
data=root.parents[1]/'artifacts/benchmark_B0_20261119'
assert socket.gethostname().split('.')[0] in {'compute-0-'+str(i) for i in range(8,20)}
capacity(data,control/'benchmark_B0_quota_20261119.json',1048576)
paths=[p.decode('utf-8') for p in (control/'B0_source_paths_20261119.nul').read_bytes().split(b'\0') if p]
spec=importlib.util.spec_from_file_location('b0_required_repository_check',root/'tools/check_repository.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=module.check(root,paths,verify_export=False)
result.update(git_path_source='Actual native login git ls-files --cached --others --exclude-standard -z; Git absent on CPU nodes',actual_compute_node=socket.gethostname())
capacity(data,control/'benchmark_B0_quota_20261119.json',1048576)
(control/'B0_source_check_20261119.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
PY