#!/bin/bash
#SBATCH --job-name=D-native-element-reference
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=1-00:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/%x_%j.log
set -euo pipefail
configuration=${1:?absolute registered reference configuration required}
output=${2:?absolute owned node-local collection output required}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_d_recipe"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$PWD/current:$root/MFM_d_descriptors_20261120:$root/MFM_d_descriptors_20261120/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$python" -B -m tools.d_recipe.fit_reference all --configuration "$configuration" --output "$output"
"$python" -B - "$configuration" "$output" <<'PY'
import json,os,shutil,sys
from pathlib import Path
from tools.d_recipe.resources import admit_output
c=json.load(open(sys.argv[1])); source=Path(sys.argv[2])/'label_parameters.json'
destination=Path(c['shared_parameters_output'])
if destination.exists():
    print(json.dumps(dict(status='REUSE_CLOSED_SHARED_PARAMETERS',path=str(destination))),flush=True)
else:
    peak=c['share_storage_peak_bytes'] if c.get('output_filesystem','/share')=='/share' else c['peak_bytes']
    protection=dict(c,storage_peak_bytes=peak)
    admit_output(protection,destination.parent);destination.parent.mkdir(parents=True,exist_ok=True)
    pending=destination.with_suffix('.partial.json');shutil.copyfile(source,pending);os.replace(pending,destination)
    print(json.dumps(dict(status='FROZEN_PARAMETERS_PUBLISHED',path=str(destination))),flush=True)
PY
