#!/bin/bash
# 此脚本用于批量生成 sbatch 脚本，并自动提交
# 生成的 sbatch 脚本除了 start_idx 和 end_idx 之外，其余参数均与下列示例一致：
#
# #!/bin/bash
# #SBATCH --job-name=mopac_dispatch
# #SBATCH --nodes=1
# #SBATCH --ntasks=1
# #SBATCH --cpus-per-task=32
# #SBATCH --time=365-00:00:00
#
# python3 QM_slurm.py \
#     --xyz_dir train_data/train_01000001_10000000/ \
#     --output_dir train_result_geometric_optimization \
#     --start_idx 1000001 \
#     --end_idx 1200000 \
#     --max_jobs 128 \
#     --cores 1 \
#     --user alpha \
#     --structure_nums 10 \
#     --mode geom \
#     --geom_frames
#
# 本脚本将批量生成从 start_idx=1200001 到 end_idx=6000000（间隔 200000）的 sbatch 文件

# 设置起始、终止索引及间隔（与示例保持一致：200000 个分子）
START=50001
FINAL=3000000
INTERVAL=50000

# 用于存放生成的 sbatch 文件的目录
OUTPUT_DIR="sbatch_files"
mkdir -p "${OUTPUT_DIR}"

# 循环生成 sbatch 脚本
for (( idx=${START}; idx<=${FINAL}; idx+=${INTERVAL} )); do
    job_start=${idx}
    job_end=$(( idx + INTERVAL - 1 ))
    # 如果 job_end 超过 FINAL，则调整为 FINAL（此处理论上正好整除）
    if [ ${job_end} -gt ${FINAL} ]; then
        job_end=${FINAL}
    fi
    filename="${OUTPUT_DIR}/mopac_${job_start}_${job_end}.sbatch"
    cat <<EOF > "${filename}"
#!/bin/bash
#SBATCH --job-name=mopac_dispatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=365-00:00:00
#SBATCH --partition=cpu

python3 QM_slurm.py \\
    --xyz_dir train_data/ \\
    --output_dir train_result_geometric_optimization \\
    --start_idx ${job_start} \\
    --end_idx ${job_end} \\
    --max_jobs 128 \\
    --cores 1 \\
    --user zixiao \\
    --structure_nums 10 \\
    --mode geom \\
    --geom_frames
EOF
    # 使用 dos2unix 转换文件格式
    dos2unix "${filename}" >/dev/null 2>&1
    echo "生成并转换脚本: ${filename}"
    # 自动提交 sbatch 脚本
    sbatch "${filename}"
    echo "已提交: ${filename}"
done
