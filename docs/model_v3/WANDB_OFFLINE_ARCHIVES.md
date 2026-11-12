# 完整离线 W&B 文件包

| 候选 | 实际执行 | SDK 状态 | 文件数 | 压缩字节 | 下载与恢复 |
|---|---|---|---:|---:|---|
| P / C1-b / seed0 | 4526378 → 4529098 → 4529110 | 六个训练/诊断 run 均 finished | 110 | 30,209,948 | [GitHub 归档](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111) |
| P / C1-0 / seed0 | 4526376 → 4529096 → 4529108 | 六个训练/诊断 run 均 finished | 110 | 31,671,522 | [GitHub 归档](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/P_C1_0_seed0) |
| P / C1-a / seed0 | 4526377 → 4529097 → 4529109 | 六个训练/诊断 run 均 finished | 110 | 30,929,928 | [GitHub 归档](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/P_C1_a_seed0) |

C1-0、C1-a、C1-b 各包含三个实际训练分段及各自配对诊断目录的全部原始普通文件：原生 `.wandb`、逐更新损失、1000 更新均值、实际系统观测、快照及完成状态。SDK 导航符号链接省略，其指向的普通文件均已包含。服务器原文件保留，未进行 W&B 云端同步。

文件清单：[C1-0](../../results/model_v3_wandb/archives/P_C1_0_seed0.json)、[C1-a](../../results/model_v3_wandb/archives/P_C1_a_seed0.json)、[C1-b](../../results/model_v3_wandb/archives/P_C1_b_seed0.json)。各候选目录的 README 提供二进制分段的合并与解压命令；a/b为part01–part10，0为part01–part11。训练权重、检查点和科学数据不在此包内。

后继执行使用同一归档入口。先等待实际训练和配对 SDK 关闭，目的目录须登记在现有全局模型输出预算中；在实际 compute-0-20 的 MFM_model_v3 目录运行：

```bash
/usr/bin/python3 -B tools/model_v3/v2_archive_wandb.py \
  --manifest /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M3_wandb_manifest_20261110.json \
  --jobs 4526378 4529098 4529110 \
  --destination /lfshome/zixiao/model_v31_20261105/WANDB_ARCHIVES_20261111 \
  --name P_C1_b_seed0_complete_wandb
```

上述已交付 C1-b 会复用现有归档与清单，不重复压缩；其他候选使用其实际执行 ID 和名称。命令不读取训练权重或科学数据，保留原 SDK 文件及已有中断文件。新归档开始和写入期间沿用完整的实际节点字节/inode、全局并发预测和 native quota 检查，不增加新的科学门。输出只有 gzip 与一份路径/字节/文件数清单，之后由根协调器上传 GitHub 分段文件并更新本索引。新增归档逻辑定向8PASS/0.06秒，无额外模型冒烟或完整回归。


## 2026-11-12: new closed SDK delivery

[Download and reconstruction instructions](https://github.com/mint258/MFM/blob/model-v3-wandb-archives-20261111/CLOSED_20261112.md). Published artifact commit: `9f04191835763790e148e14f8f1ee87f8ed3cf78`. Four additional bundles contain21 closed SDK sessions,249 regular files including derived hardware series/summaries,118918066 gzip bytes and40 binary parts. The previous330 files remain available.

| Bundle | Actual jobs | Sessions | Regular files | Gzip bytes | Manifest |
| --- | --- | ---: | ---: | ---: | --- |
| C1 v2 evaluations plus matched reference | 4529715-4529721 | 7 | 71 | 74961392 | [manifest](../../results/model_v3_wandb/archives/C1_v2_v3_closed.json) |
| T0 S training and evaluation | 4529723/4529724/4529739/4529740 | 4 | 51 | 22394470 | [manifest](../../results/model_v3_wandb/archives/T0_S_v3_closed.json) |
| T0 P training and evaluation | 4529730/4529731/4529746/4529747 | 4 | 51 | 14834564 | [manifest](../../results/model_v3_wandb/archives/T0_P_v3_closed.json) |
| Historical stopped seed1 training/diagnostics | 4529691/4529704/4529711 | 6 | 76 | 6727640 | [manifest](../../results/model_v3_wandb/archives/cancelled_seed1_partial_v3_closed.json) |

The seed1 bundle preserves historical stopped partial executions; none was resumed or represented as a completed6M run. Continuing T1 SDK sessions are still open and are not included as closed archives. Each README provides Linux and PowerShell joining/extraction commands. Original files remain on the server, navigation symlinks are omitted, and W&B cloud synchronization was not performed.

[Readable hardware table](CLOSED_SDK_HARDWARE_20261112.md) and [complete native-key summaries](../../results/model_v3_wandb/closed_sdk_hardware_20261112.json) reuse the completed exporter outputs. Timestamped raw JSONL is included in each bundle. Device-wide GPU metrics differ from own-process torch allocator peaks. Legacy diagnostic SDK StatsRecords describe the recorder host; customized remote training observations remain in original HistoryRecords/system_metrics.jsonl and are not relabeled as native training-device measurements.

SDK reading/compression is single-threaded operational work. After verifying ownership, exact commands, zero-work PENDING state and actual node20 capacity, the four archive jobs changed NumCPUs/CPUsPerTask/MinCPUsNode to1. Jobs4529839/4529840/4529986/4529987 completed0:0 on node20 with1CPU each in28/17/15/17seconds. Training, readout evaluation and regression requests were unchanged. Existing filesystem/inode, shared forecast, native quota and runtime protection remained active. No SDK files were modified or deleted; no model or extra validation was rerun.


## T1 first two S continuations: closed training SDKs

[A0/S and A1/S complete training bundle](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/T1_A0_A1_S_training_closed), artifact commit `df701c50af64a66e08e4bcce953cfe0d1fb84758`: two successful closed training sessions,51 ordinary files,18890531 gzip bytes,7 parts. Jobs4529725/4529726 each reached1.5M continuation samples (7.5M cumulative). Archive4529994 completed0:0 on node20 in14seconds with1CPU. [Manifest](../../results/model_v3_wandb/archives/T1_A0_A1_S_training_closed.json).

Paired evaluations are separate SDKs; later T1 arms are not included. The new-delivery index now totals23 sessions,300 files and47 parts across five bundles; original P0/a/b330 files remain. The earlier statement that T1 sessions were open describes the previous delivery. System summaries extend the same hardware table/JSON; raw native-key JSONL is in the complete bundle. No cloud sync, deletion or model rerun.


## First T1 S paired evaluations: closed SDKs

[A0/S and A1/S complete evaluation bundle](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/T1_A0_A1_S_evaluation_closed), artifact commit `213ab9ad241a01f623a4f0dafe1f0d383c9cfb3e`: jobs4529741/4529742,2 closed sessions,21 ordinary files,20800946 gzip bytes,7 parts. Archive4529995 completed0:0 on node20,1CPU,11seconds. [Manifest](../../results/model_v3_wandb/archives/T1_A0_A1_S_evaluation_closed.json).

The six new bundles now total25 closed SDK sessions,321 ordinary files,158609543 gzip bytes and54 parts. Both first S continuation training and their paired evaluation SDKs are complete; remaining T1 arms await actual closure. The original P0/a/b330 files are retained. Native hardware summaries are extended without replay or new scientific analysis.

## First T1 P continuation training: closed SDKs

[A0/P and A1/P complete training bundle](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111/T1_A0_A1_P_training_closed), artifact commit `86c9541a80c95bfc0f83c0131fbbe86bdeaae38f`: jobs4529732/4529733,2 closed sessions,51 ordinary files,18928411 gzip bytes,7 parts. Both continuations reached1.5M samples (7.5M cumulative). Archive4530008 completed0:0 on compute-0-20,1CPU,14seconds. [Manifest](../../results/model_v3_wandb/archives/T1_A0_A1_P_training_closed.json).

The seven new bundles now total27 closed SDK sessions,372 ordinary files,177537954 gzip bytes and61 parts. Full native .wandb files, per-update loss,1000-update means,snapshots and original hardware observations/producer-derived native-key system JSONL and summaries are included. The first P paired evaluations are separate and await closure. The original P0/a/b330 files remain; no cloud sync, file deletion or training rerun.
