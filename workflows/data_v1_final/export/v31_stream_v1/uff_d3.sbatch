#!/bin/bash
#SBATCH --job-name=window2_uff_d3
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=64
#SBATCH --ntasks=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/uff_d3_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
plan=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/UFF_D3_20261105_v1.plan.json
export PYTHONPATH="$repo/current:$repo${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$repo"
# One invocation for the new eight storage/source seam unit tests. The already
# passed normalization suite is not repeated; kernel/policy run in PM7 parent.
"$python" -B -m unittest workflows.data_v1_final.export.v31_stream_v1.test_stream
# Read the closed Common metadata once and bind its accepted pointer tables.
"$python" -B - "$plan" <<'PY'
import json,pathlib,sys
path=pathlib.Path(sys.argv[1]);plan=json.loads(path.read_text())
common=json.loads(pathlib.Path(plan['common']).read_text())
if common['status']!='COMMON_POPULATION_V1_FROZEN':raise ValueError('CLOSED_FINAL_COMMON_REQUIRED')
plan['extra_geometry_tables']=common['registered_extra_geometry_map_tables']+common.get('diagnostic_addressable_geometry_tables',[])
pending=path.with_name(path.name+'.writing');pending.write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n');pending.replace(path)
PY
"$python" -B -m workflows.data_v1_final.export.v31_stream_v1.uff_d3 --plan "$plan"