#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == compute-0-20 ]]
root=/share/home/zixiao/descriptor_analysis/MFM_precision_20261115
receiver='srun --unbuffered -N 1 -n 1 -c 1 -p cpuXeon6458 -t 02:00:00 /share/home/202264640132/.conda/envs/torchgpu/bin/python -B /share/home/202264640132/precision_school_guard.py -- /usr/bin/rsync'
rsync -av --partial --append-verify -e 'ssh -o BatchMode=yes -o UpdateHostKeys=no -o StrictHostKeyChecking=yes' --rsync-path="$receiver" "$root/results/precision_20261115/school_wheels/" 202264640132@202.38.252.202:/share/home/202264640132/precision_school_wheels/
rsync -av -e 'ssh -o BatchMode=yes -o UpdateHostKeys=no -o StrictHostKeyChecking=yes' --rsync-path="$receiver" "$root/results/precision_20261115/precision_source_patch.tar.gz" "$root/tools/model_v3/precision_school_prepare.sh" 202264640132@202.38.252.202:/share/home/202264640132/
