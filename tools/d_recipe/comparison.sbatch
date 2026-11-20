#!/bin/bash
#SBATCH --job-name=D-registered-comparison
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/%x_%j.log
set -euo pipefail
candidate=${1:?registered candidate CPU configuration required}
control=${2:?registered control configuration required}
output=${3:?comparison JSON under results/d_recipe required}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_d_recipe"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$PWD/current:$root/MFM_d_descriptors_20261120:$root/MFM_d_descriptors_20261120/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$python" -B - "$candidate" "$output" <<'PY'
import json,sys
from pathlib import Path
from tools.d_recipe.resources import admit_output,execution_site
c=json.load(open(sys.argv[1]));execution_site(c,cpu=True)
admit_output(c,Path(sys.argv[2]).parent)
PY
exec "$python" -B -m tools.d_recipe.compare --candidate "$candidate" --control "$control" --output "$output"
