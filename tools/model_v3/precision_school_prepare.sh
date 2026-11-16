#!/bin/bash
set -euo pipefail
school_home=/share/home/202264640132
root="$school_home/precision_20261115"
mkdir -p "$root"
if [[ ! -d "$root/source" ]]; then
 cp -a "$school_home/descriptor_analysis_migration_20261115/models/source" "$root/source"
fi
tar -xzf "$school_home/precision_source_patch.tar.gz" -C "$root/source"
mkdir -p "$root/source/.git"
printf '%s\n' 'uncommitted-precision-20261115' > "$root/source/.git/HEAD"
python="$school_home/.conda/envs/torchgpu/bin/python"
if [[ ! -x "$root/env/bin/python" ]]; then "$python" -m venv --system-site-packages "$root/env"; fi
export TMPDIR="$root/tmp"
mkdir -p "$TMPDIR" "$root/pip_cache"
"$root/env/bin/python" -m pip install --no-cache-dir --no-index --find-links "$school_home/precision_school_wheels" torch==2.8.0 pytest==8.4.2 exceptiongroup tomli
export CUDA_VISIBLE_DEVICES= PYTHONPATH="$root/source/current"
"$root/env/bin/python" -B -c 'import torch,torch_geometric,lmdb,wandb;print(dict(torch=torch.__version__,cuda=torch.version.cuda,pyg=torch_geometric.__version__,wandb=wandb.__version__))'
"$root/env/bin/python" -B -m pytest -q -p no:cacheprovider "$root/source/current/tests/test_p_precision_islands.py"
