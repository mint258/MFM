#!/bin/bash
#SBATCH --job-name=perf-A800-prepare
#SBATCH --partition=cpuXeon6458
#SBATCH --account=a_xk
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/202264640132/perf_A800_prepare_%j.log
set -euo pipefail
task_home=/share/home/202264640132
task_python="$task_home/precision_20261115/env/bin/python"
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
findmnt -T "$task_home"
df -B1 / "$task_home"
df -Pi / "$task_home"
exec "$task_python" -B "$task_home/precision_school_guard.py" -- bash -se <<'PREPARE'
task_home=/share/home/202264640132
task_root="$task_home/perf_A800_20261120"
mkdir -p "$task_root"
if [[ ! -d "$task_root/source" ]]; then
 cp -a "$task_home/precision_20261115/source" "$task_root/source"
fi
tar -xzf "$task_home/A800_source_20261120.tar.gz" -C "$task_root/source"
mkdir -p "$task_root/tmp" "$task_root/cache" "$task_root/inductor" "$task_root/triton"
cd "$task_root/source"
export PYTHONPATH="$PWD/current:$PWD/tools/perf_sync" TMPDIR="$task_root/tmp"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
"$task_home/precision_20261115/env/bin/python" -B -c 'import ast;from pathlib import Path;[ast.parse(p.read_text()) for p in Path("tools/perf_sync").glob("a800*.py")];import a800_portable;a800_portable.install();from phychem_mfm.phase1.p_recipe_training import train;from a800_final import capacity;print(capacity());print("A800 final source/portable reader/train import PASS")'
"$task_home/precision_20261115/env/bin/python" -B - <<'CHECK_READER'
import json
import numpy as np
from pathlib import Path
import a800_portable as adapter
adapter.install()
from phychem_mfm.phase1 import p_recipe_data
home=Path('/share/home/202264640132')
c=json.loads(Path('configs/perf_sync/M2_5090.json').read_text())
c.update(root=str(home/'descriptor_analysis_migration_20261115/data/training_lmdb'),
         compressed_lmdb=True,label_parameters=str(home/'descriptor_analysis_migration_20261115/models/label_parameters/PM7_A1.json'))
kwargs=p_recipe_data.dataset_configuration(c)
old=adapter.released.PRecipeDataset(**kwargs)
try:
    molecule=int(old.indices[0]);conformer=int(old.choices(molecule)[0])
    a=old.read(molecule,conformer)
finally:
    old.close()
new=adapter.PortableDataset(**kwargs)
try:
    b=new.read(molecule,conformer)
    for name in a['targets']:
        for attribute in ('raw','values','valid'):
            left,right=getattr(a['targets'][name],attribute),getattr(b['targets'][name],attribute)
            assert left.dtype==right.dtype and np.array_equal(left,right,equal_nan=True),(name,attribute)
    print('PORTABLE_OLD_NEW_TARGETS_EXACT',len(a['targets']),molecule,conformer,flush=True)
finally:
    new.close()
CHECK_READER
"$task_home/precision_20261115/env/bin/python" -B -m pytest current/tests/test_step_overhead_grouped_loss.py -q -p no:cacheprovider
printf '%s\n' 'A800_PREPARATION_COMPLETE'
PREPARE
