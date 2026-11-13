# W&B 归档与阅读

用户于2026-10-07要求训练结束后集中归档并命名，当前用于sonmi Phase1。读取此文件后，在提交正式训练、归档或纠正入口时执行相应检查。

- 单一阅读入口：`/share/home/zixiao/descriptor_analysis/W&B_训练记录.html`。
- 实体目录：`/share/home/zixiao/descriptor_analysis/runs/phase1_full_corpus/wandb_archive`。
- 命名：`<模型>_seed<seed>/<SDK日期>_<SDK时间>_job<Slurm ID>_<状态>_<run ID>/`。日期时间沿用原SDK文件名；索引刷新与服务寿命明确按Asia/Shanghai显示。
- 每项包括原`offline-run-*` SDK记录（在`wandb/`内）、指标`metrics.csv`、`last_metrics.json`、曲线`index.html`、`manifest.json`及源journal副本。不含checkpoint或整份cache。
- 原记录路径被冻结receipt及恢复引用，因此归档是字节核对后的副本。SDK日志链接只复制经过UID/普通祖先/自有phase范围验证的日志目标；归档内部为单链接普通文件。所有字节及临时导出计入既有`runs/phase1_full_corpus`森林预算。

已部署脚本：`/share/home/zixiao/descriptor_analysis/scripts/archive_phase1_wandb_v2.py`，raw SHA256 `3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e8f975a`。

在sonmi登录节点，以既有chemprop逻辑入口执行一次收尾归档：

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/scripts/archive_phase1_wandb_v2.py
```

这是有界metadata与已关闭W&B日志导出，不执行模型、优化器或数据集处理。退出0与`index.json`中的`errors: []`共同核验。归档依据真实squeue/sacct/receipt；Slurm COMPLETED但科学闭合未验证时标UNVERIFIED，只有genuine V15 epoch validator、成功receipt、退出0及完整三轮末端验证都通过才标FINAL。FAILED的完整raw记录保留，CSV尾部可能超出安全checkpoint，不能从最后记录重建规范进度。

当前metadata服务证据在`docs/phase1/evidence/stage60_wandb_archive_v1/watcher.service.json`，对应stdout/stderr同目录。进程以`--watch-seconds 86400`启动，每60秒处理结束的run；同一归档锁协调手动调用和服务。提交前以`/proc/<精确PID>/{stat,status,cmdline}`核对UID1278、start_ticks、实际argv及脚本SHA，并确认余下寿命大于本段墙钟上限加收尾余量。服务到期必须更新，不能仅凭旧receipt声称它仍运行。更新服务须记录新的PID/身份/argv/寿命，避免同名盲目pkill。

实际2026-10-07首次v1因源类型catalog摘要误录65字符未发布任何归档，失败输出及原文件保留。v2改为实际64字符pin，并复用经逐文件SHA核对的自有临时副本；真实一次运行退出0，归档9项、运行中1项、errors0。v1和v2结果不是模型训练完成证据。原型脚本v1不可用于后续收尾。
