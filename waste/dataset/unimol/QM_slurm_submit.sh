#!/bin/bash

#SBATCH --job-name=mopac_dispatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=365-00:00:00

# 调用 Python 脚本，参数示例：
# 这里 --max_jobs=8 且 --cores=4 表示每个 MOPAC任务用4核，并发8个任务，总共占用 32 核
python3 QM_slurm.py \
    --xyz_dir train_data/train_01000001_10000000/ \
    --output_dir train_result_geometric_optimization \
    --start_idx 1000001 \
    --end_idx 1200000 \
    --max_jobs 128 \
    --cores 1 \
    --user alpha \
    --structure_nums 10 \
    --mode geom \
    --geom_frames
