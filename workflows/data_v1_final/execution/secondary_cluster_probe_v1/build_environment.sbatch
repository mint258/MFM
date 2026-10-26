#!/bin/bash
#SBATCH --job-name=dv1_secondary_environment_build_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:30:00
#SBATCH --output=/gfshome/alpha/codex_data_v1_20261026/environment_build_%j.out
set -euo pipefail
test "$(id -u)" = 1264
test "$SLURM_JOB_PARTITION" = cpu
test "$SLURM_CPUS_PER_TASK" = 16
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CONDA_PKGS_DIRS=/gfshome/alpha/codex_data_v1_20261026/conda_packages
export PIP_CACHE_DIR=/gfshome/alpha/codex_data_v1_20261026/pip_cache
cd /gfshome/alpha/codex_data_v1_20261026
test ! -e /gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v1
/share/home/alpha/miniconda3/bin/conda create --yes --quiet --json --no-default-packages --override-channels -c conda-forge --prefix /gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v1 python=3.11.14 rdkit=2025.09.5 numpy=2.2.6 scipy=1.15.3 pandas=2.3.3 pyarrow=25.0.1 python-lmdb=1.7.5 > conda_environment_build_result.json
/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v1/bin/python -B -c 'import rdkit,numpy,scipy,pyarrow,lmdb,pandas,sys,json; print(json.dumps({"python":sys.version,"rdkit":rdkit.__version__,"numpy":numpy.__version__,"scipy":scipy.__version__,"pyarrow":pyarrow.__version__,"lmdb":lmdb.__version__,"pandas":pandas.__version__}))' > exact_environment_versions.json
