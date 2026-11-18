## 2026-11-18 用户新规则：CPU 任务只在 CPU 节点提交

适用于所有工作线、Codex 窗口和子 agent，覆盖以前把 CPU 工作放在 GPU 节点或 compute-0-2 空闲核上的做法。

- **不用 GPU 的任务一律提交到 CPU 节点 compute-0-8 ~ compute-0-19**（共 12 个）。包括：标签计算（PM7、xTB、UFF、RDKit）、数据预处理和打包、参数拟合、统计分析和 bootstrap、传统 ML 基线、环境搭建、下载和安装。
- 用 sbatch 时用 `--nodelist` 或 `--exclude` 限定到这 12 个节点。提交前按实际节点查看空闲 CPU 和内存，只申请实际需要的量。
- **不占 GPU 节点的 CPU。** GPU 节点包括 compute-0-20、21、22 和其他带 GPU 的节点，它们的 CPU 只留给 GPU 任务。GPU 训练在 GPU 节点上也只申请自身数据加载等实际需要的 CPU。
- Alpha 集群同理，只用没有 GPU 的主机。
- CPU 节点占满时，排队等待，不退到 GPU 节点上。排队不是停止条件，日报记一行即可。
- GPU 节点上已经在跑的 CPU 任务不中途停止。能从检查点或分批边界续接的，在下一个边界迁到 CPU 节点；不能续接的跑完为止。以后不再往 GPU 节点新提交 CPU 任务。
- 同步更新全局技能 huagong_hpc_requirement。
- 节点磁盘保护、按需申请 CPU、不使用 exclusive 等既有规则不变。

## PubChem current scientific quality and Alpha metadata continuation

For this expansion, preserve the taskbook strict new canonical-record mask fraction above1% stop-and-user-report condition. User removal of per-job Root approvals did not remove scientific quality. Exactly1% continues; source NA/component fractions/robust-z review are separate. Do not add Root approval receipts. Use complete external full-QA reference catalogs and original function-preserving native timing metadata. Alpha compute-local sacct is unusable; the tested native accounting prefix is ssh -n -o BatchMode=yes -o ConnectTimeout=5 218.192.171.238 sacct. Keep1885201 untouched and preserve immutable source/runtime history.
## 2026-11-04 PubChem concurrency follow-up

The user explicitly allows an appropriate increase in computation concurrency when needed. Recheck live free CPU allocations and actual RAM; prefer idle pure CPU nodes. When those are occupied, using idle CPU cores on a free Alpha host in partition all is within this CPU-only continuation, with no GPU request or GPU computation and no paid server. Root's current operational selection is compute-0-2/all 32 CPUs plus sonmi1/cpu 16 CPUs after the current filter, not a permanent user mandate for these counts/nodes. Use disjoint fingerprint search partitions and preserve identical full-reference exact math, source identity, R/N rules and max3 UFF/D recipe. Keep 1885201 running untouched; do not restart the active filter merely to raise its worker count. Update only unstarted downstream plans or deploy a new immutable source for continuation. Root remains the sole submission coordinator; real CPU/RSS/shared quota accounting and the one daily human summary remain.

## 2026-11-04 PubChem exact structure decontamination and direct execution

Current explicit user correction overrides all older composition/wildcard decontamination and per-job Root approval requirements for this expansion. Use only complete InChIKey and the original v1 wp5 key (first 14 InChIKey characters + ":" + final protonation character). Remove every elemental-composition exact/lower-bound and wildcard veto, including MoleculeNet case:18/PDBbind 1pts and case:00/ClinTox. Exclude all PDBbind from decontamination sources because it is outside the planned downstream evaluation. Any downstream record without a determined exact structure contributes no structural veto; exclude it from downstream evaluation and preserve a record-level exclusion list and original evidence.

Stop and archive further 1slg/1pts correspondence research. Rebuild source keys from original physical identity rows (filter PDBbind before insertion so shared keys from other datasets remain), then run one whole-pool filter, directly build R/N queues and the 2.5M first batch, followed by UFF (maximum 3 actual conformers, no filling/retry) and D labels. Keep the existing fixed 1M nearest-neighbor job running in the background; it must not block this expansion. There is no new per-job Root acceptance/receipt or approval schema: keep necessary producer checkpoints/manifests and actual resource/accounting facts, and write one daily summary. Preserve old reports as superseded history. Exact full reference NN math, v1 ranking rules, original UFF/D science and real shared quota/resource protection remain unchanged.

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
