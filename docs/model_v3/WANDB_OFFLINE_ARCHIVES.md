# 完整离线 W&B 文件包

| 候选 | 实际执行 | SDK 状态 | 文件数 | 压缩字节 | 下载与恢复 |
|---|---|---|---:|---:|---|
| P / C1-b / seed0 | 4526378 → 4529098 → 4529110 | 六个训练/诊断 run 均 finished | 110 | 30,209,948 | [GitHub 归档](https://github.com/mint258/MFM/tree/model-v3-wandb-archives-20261111) |
| P / C1-0 / seed0 | 当前 4529108 | 训练中 | — | — | SDK 关闭后归档 |
| P / C1-a / seed0 | 当前 4529109 | 训练中 | — | — | SDK 关闭后归档 |

C1-b 包含三个实际训练分段及各自配对诊断目录的全部原始普通文件：原生 `.wandb`、逐更新损失、1000 更新均值、实际系统观测、快照及完成状态。SDK 导航符号链接省略，其指向的普通文件均已包含。服务器原文件保留，未进行 W&B 云端同步。

文件清单：[P_C1_b_seed0.json](../../results/model_v3_wandb/archives/P_C1_b_seed0.json)。归档分支的 README 提供十个二进制分段的合并与解压命令；顺序拼接 part01–part10 即为原始 gzip 文件。训练权重、检查点和科学数据不在此包内。

后继执行使用同一归档入口。先等待实际训练和配对 SDK 关闭，目的目录须登记在现有全局模型输出预算中；在实际 compute-0-20 的 MFM_model_v3 目录运行：

```bash
/usr/bin/python3 -B tools/model_v3/v2_archive_wandb.py \
  --manifest /share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M3_wandb_manifest_20261110.json \
  --jobs 4526378 4529098 4529110 \
  --destination /lfshome/zixiao/model_v31_20261105/WANDB_ARCHIVES_20261111 \
  --name P_C1_b_seed0_complete_wandb
```

上述已交付 C1-b 会复用现有归档与清单，不重复压缩；其他候选使用其实际执行 ID 和名称。命令不读取训练权重或科学数据，保留原 SDK 文件及已有中断文件。新归档开始和写入期间沿用完整的实际节点字节/inode、全局并发预测和 native quota 检查，不增加新的科学门。输出只有 gzip 与一份路径/字节/文件数清单，之后由根协调器上传 GitHub 分段文件并更新本索引。新增归档逻辑定向8PASS/0.06秒，无额外模型冒烟或完整回归。
