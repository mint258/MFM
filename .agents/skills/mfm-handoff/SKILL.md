---
name: mfm-handoff
description: MFM / PhyChem-MFM 项目的总入口与交接手册。新 agent 接手、换窗口、丢失记忆、恢复某条工作线，或不确定"现在该听哪份文件"时先读本 skill；它给出阅读顺序、文件权威顺序、角色分工、恢复步骤和其他项目管理 skill 的索引。
metadata:
  version: "1.0.0"
  updated: "2026-11-19"
  owner: Zixiao Yang (@mint258)
---

# MFM 项目交接总入口

本 skill 是项目管理方法的唯一入口。它不替代各线任务书，只规定**怎么找到并遵守**当前有效的规则，防止换人后方法漂移。

## 1. 接手时的阅读顺序（不要跳步）

1. 本文件，以及 [研究背景与科学共识](references/research-context.md)。
2. 当前分支的 `AGENTS.md`（服务器与集群的现行规则按日期倒序写在最上面，**越靠上越新**）。
3. `docs/RESEARCH_MAINLINE.md`：论文主线 v1（研究问题、H1–H4、E0–E7、待定决策 D1–D8）。
4. 自己所属工作线的文件，按这个顺序：任务书（`docs/<line>/TASKBOOK*.md`）→ 按日期排列的全部 `docs/<line>/USER_DIRECTIVE_YYYYMMDD[B].md` → 该线最新日报 / LOG。
5. 共享状态源：`configs/p_recipe/CURRENT_BEST.json`（当前最优配方的唯一来源）、`docs/interfaces/STATUS.md`（跨线公告，只追加）。
6. [状态快照与已作废规则](references/state-and-superseded-rules.md)：知道哪些旧规则已经失效，避免照旧文件执行。
7. 按需读其他 skill（见第 5 节）。

读完前不提交任何作业，不改任何配置。

## 2. 权威顺序（冲突时谁说了算）

从高到低：

1. **用户在当前对话里的明确指示。**
2. 用户写入仓库的最新 `USER_DIRECTIVE_*.md`。同一线内日期新的覆盖旧的；同日的 `B` 版覆盖无后缀版。被覆盖的旧文件会在相应段落加一行引用说明（`> 2026-11-19 起本节由 … 取代`），以新文件为准。
3. 该线任务书（`TASKBOOK*.md`）及其预注册文件（`configs/<line>/preregistration.json` 等）。
4. `AGENTS.md` 中的集群与运行规则（最上面的条目最新）。
5. `docs/RESEARCH_MAINLINE.md`：**科学目标、实验组成和判定口径**以主线为准，工程细节以各线任务书为准。主线改动必须经用户批准并在其"修订记录"追加一行，没有记录的改动无效。
6. 全局技能 `huagong_hpc_requirement`（仓库镜像：`docs/skills/huagong_hpc_requirement/`，在 p-recipe 一系分支上）。它的最上面几节与 AGENTS.md 同步；两者冲突时以 AGENTS.md 和更新日期较新的一方为准。
7. 历史文件（`docs/model_v3/` 旧任务书、旧 DAILY、旧 receipts）只作历史证据，不作执行依据。

规则：**新指示只覆盖它明确写到的条款，其余照旧。** 不要把一条指示推广到它没写的范围，也不要从沉默里推出新授权。

## 3. 角色分工

| 角色 | 做什么 | 不做什么 |
| --- | --- | --- |
| 用户（Zixiao） | 定科学问题、主线、预算、停止条件的答复；合并 PR；申请外部账号权限 | — |
| Claude（对话里） | 和用户讨论方案，起草任务书和 USER_DIRECTIVE，整理论文素材（`docs/paper/`、`docs/findings/`），维护这些 skill | 不替用户合并 PR，不替执行窗口提交作业 |
| Codex 执行窗口（每条工作线一个） | 照任务书和指示执行：写代码、提交作业、判定、日报、推送、开 PR | 不改其他线的分支和文件，不改 `docs/paper/`，不合并 PR，不自行扩大任务 |
| 子 agent | 只做协调窗口分给它的目录和任务，推送前先 rebase | 不重复协调窗口或其他子 agent 的工作 |

每条线只有一个提交协调者（Root / 协调窗口）。子 agent 准备，Root 统一提交和去重。

## 4. 恢复一条工作线的步骤

1. 确认分支和工作树：每条线在服务器上有独立工作树（例如 `X:\MFM_p_recipe` 对应 `/share/home/zixiao/descriptor_analysis/MFM_p_recipe`）。服务器上的编辑走 `X:\` 实时视图，不改 OneDrive 本地副本。
2. `git fetch` 后看本线最新提交、日报和 LOG 末尾，弄清：哪些运行在跑、哪些已判定、哪些在排队、哪些"待用户决定"。
3. 在实际节点上核对在跑作业的真实句柄（Slurm job ID 或原生 PID + start_ticks），不要相信文件里写的旧 PID 或旧锁。
4. **在跑的训练一律不停、不迁移、不重启**，除非用户对那一条明确下了停止指令。规则更新只对新提交生效。
5. 从断点处继续执行任务书，不重做已有结果，不重算已有分数。
6. 当天日报记一行"接手"，写明从哪个提交和哪份指示接手。

## 5. 其他 skill 索引

| 需要做的事 | 读 |
| --- | --- |
| 开分支、合并、跨线交接、CURRENT_BEST、PR | `mfm-branch-management`（**尚未编写**） |
| 给一条线写任务书或补充指示、定停止条件和不做清单 | `mfm-taskbook-standard` |
| 筛选 / 确认预算、R1/R3、胜负判定、种子数、合并与冻结 | `mfm-experiment-decisions` |
| 结果不理想，决定往哪里查、加什么臂、做多深 | `mfm-improvement-exploration`（**尚未编写**） |
| 写测试、做验证、性能等价性验收 | `mfm-testing-standards` |
| 提交作业、选节点和 GPU、断点接管、磁盘保护 | `mfm-cluster-operations` |
| 记录方法、显著性分析和发现，供写论文 | `mfm-paper-records` |

## 6. 修改本组 skill

- 这些 skill 记录的是用户确认过的方法。新的用户决定先进 USER_DIRECTIVE 或 AGENTS.md，再由 Claude 或协调窗口同步到这里，并升 `metadata.version`、改 `updated`。
- 不把一次性的运行事实（PID、job ID、某天哪张卡空着）写进 skill。
- skill 和更新的用户指示冲突时，以指示为准，并尽快修 skill。
