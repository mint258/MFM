#!/bin/bash

# 定义源目录和目标目录
SOURCE_DIR="folded_origin_data/train_1000000_10000000"
TARGET_DIR="train_data/train_01000001_10000000/"

# 创建目标目录（如果不存在）
mkdir -p "$TARGET_DIR"

# 最大并发任务数
MAX_PROCS=10
current_jobs=0

for i in {2..45}; do
    FILE="$SOURCE_DIR/data_subset_ic_batch${i}.tar"
    
    if [[ -f "$FILE" ]]; then
        echo "正在解压 $FILE 到 $TARGET_DIR/"
        tar -xf "$FILE" -C "$TARGET_DIR/" &
    else
        echo "警告：文件 $FILE 不存在，跳过。"
    fi

    ((current_jobs++))
    # 如果达到最大并发数，则等待所有后台任务完成
    if (( current_jobs >= MAX_PROCS )); then
        wait
        current_jobs=0
    fi
done

# 等待剩余的后台任务完成
wait
