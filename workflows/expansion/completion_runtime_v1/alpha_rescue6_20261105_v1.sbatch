#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodelist=sonmi1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=0
#SBATCH --job-name=pubchem_rescue6
#SBATCH --output=/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/node_epochs/alpha_rescue6_20261105_v1_%j.out
set -euo pipefail
unset SBATCH_MEM SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU
export CUDA_VISIBLE_DEVICES=
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /gfshome/alpha/codex_data_v1_20261026/code/pubchem_completion_20261103_497c584
if test -f /gfshome/alpha/pubchem_expansion_20261103/exact/partitioned_novelty_ded6679_low11_job_1885213/manifest.json; then echo RESCUE_NOT_RUN_ORIGINAL_LOW_MANIFEST_ALREADY_EXISTS; exit 0; fi
exec /gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python -I -B /gfshome/alpha/codex_data_v1_20261026/code/shard_guard_cadence_20261105_v2/entry.py workflows.expansion.alpha_sharded_novelty_v1.prepare_pipeline --mode nn --seed /gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/alpha_rescue6_20261105_v1_seed.json --upstream /gfshome/alpha/pubchem_expansion_20261103/exact/exact_key_filter_ea3057e_job_1885209/manifest.json --entry /gfshome/alpha/codex_data_v1_20261026/code/shard_guard_cadence_20261105_v2/entry.py --tag alpha_rescue6_20261105_v1
