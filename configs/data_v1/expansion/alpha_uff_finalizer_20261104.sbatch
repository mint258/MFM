#!/bin/bash
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=0
#SBATCH --job-name=metrics_b2e63fd_finalize
#SBATCH --output=/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/node_epochs/uff_final_metrics_b2e63fd_finalize_%j.out
set -euo pipefail
unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU
export CUDA_VISIBLE_DEVICES=
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /gfshome/alpha/codex_data_v1_20261026/code/pubchem_completion_20261103_497c584
exec /gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python -I -B /gfshome/alpha/codex_data_v1_20261026/code/uff_final_metrics_b2e63fd/layer_entry.py workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase finalize --config /gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/uff_final_metrics_b2e63fd_finalizer_runtime_config.json --upstream-job 1885227 --upstream-tag uff_quality_timed_86e1e2e_uff_qa_full --generation-job 1885226 --generation-tag uff_quality_timed_86e1e2e_uff_full --entry /gfshome/alpha/codex_data_v1_20261026/code/uff_final_metrics_b2e63fd/layer_entry.py --tag uff_final_metrics_b2e63fd_finalize
