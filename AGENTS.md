## 2026-11-06 用户要求：节点文件传输不得占满磁盘

适用于所有 Codex 窗口、子 agent、CPU/GPU 节点及下载、复制、rsync、缓存、解压和临时输出；执行任何节点大文件传输前必须遵守。

- 在实际目标节点解析目标路径及其文件系统，用 findmnt -T、df -B1 和 df -Pi 检查可用字节与 inode；/tmp、/var/tmp 可能与根分区及 SlurmdSpoolDir 共盘，不能当作独立大容量 scratch。共享盘 df 和账户 quota 不能替代节点本地磁盘检查。
- 估算新增物理占用的峰值，计入源文件、解压/数据库临时文件、旧新文件并存、partial 文件、失败残留及所有窗口已计划/正在进行的同盘写入。跨窗口在同一目标盘协调预留，不能各自拿同一份空闲空间重复预算。
- 根分区默认至少保留 max(10 GiB, 文件系统总容量的 10%) 给系统和 Slurm；站点更严格要求优先。其他文件系统须保留站点要求及覆盖并发增长的余量，既有账户 quota 余量规则继续执行。目标可用量不足覆盖峰值加余量，或无法查明容量时，不得开始复制；换经核实的专用 scratch/共享盘、减小缓存或分批处理。
- 长传输及缓存生成期间持续观察同盘余量，在触及预留空间前停止新增写入并保留可续传状态，不能等到 ENOSPC 才处理。新传输/缓存入口落实容量预检和运行期保护；仅打印 df 不算保护。未核实用途/所有权/依赖的文件不得自动删除，不改管理员目录或自行解除 drain。
- 已核实事故：compute-0-17 作业4526050于2026-11-05 16:33复制约29GB的d7.duckdb到/tmp，留下17,656,872,960字节部分文件并报ENOSPC，同刻节点因SlurmdSpoolDir is full进入drain。compute-0-20作业4526119取消后一个进程未退出并触发Kill task failed；这是不同故障，不误写为该节点磁盘满。

# MFM development workflow

- Read `docs/DEVELOPMENT_HANDOFF.md` and `docs/DATA_PIPELINE.md` first. Develop under `current/phychem_mfm`; root MoE code and `legacy/descriptor` are historical implementations.
- Canonical downstream representation: `SharedBackboneMFM.encode_atoms(batch)` (H0). Preserve source atom order and explicit labels/masks. Do not add task fusion or gates to H0.
- `docs/SOURCE_MANIFEST.json` records exact server exports. Record new source revisions separately; do not silently rewrite historical hashes or checkpoint provenance. Preserve frozen configurations and evidence.
- Keep real data, weights, checkpoints, computed labels, caches, databases and credentials outside Git. Run `python tools/check_repository.py` before committing. Credentials use existing keys or environment variables.
- Server means `zixiao@202.38.247.57:22`; project means `/share/home/zixiao/descriptor_analysis`. `X:\` is its live SSHFS view. Server edits use `X:\`, not the local OneDrive copy. Verify `Test-Path X:\` and key-based `ssh descriptor-analysis-remote` first.
- Linux commands run by SSH after entering `compute-0-20`. Never run server scripts using a local Windows interpreter. Formal computation uses the established Slurm workflow. This source snapshot does not authorize launching experiments or restoring old queues.
- Paid school server `202264640132@202.38.252.202:22` is only for explicitly approved formal pretraining. Recover its existing sbatch workflow before submitting; never use it for development/tests.
- Use the installed `huagong_hpc_requirement` skill for actual server operations. Do not modify/cancel others' tasks or unrelated active WP5 work.
- Normalization and model selection use TRAIN only. Preserve official ExpansionRx membership and source atom IDs. PM7 energy is FINAL HEAT OF FORMATION (kcal/mol); charge is NET ATOMIC CHARGES (e).
