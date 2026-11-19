---
name: mfm-branch-management
description: MFM 仓库的分支与跨线协作规则：主干与分支拓扑、分支/目录/臂/运行命名、提交与 PR 规则、CURRENT_BEST 作为当前最优配方的唯一来源、线之间的结果交接、docs/interfaces/STATUS.md 只追加的惯例。开新线或新分支、推送、开 PR、读取或发布 CURRENT_BEST、交接胜出项、写跨线公告时使用。
metadata:
  version: "1.0.0"
  updated: "2026-11-19"
---

# 分支管理与跨线交接

一条线 = 一个任务书 + 一个分支 + 一个执行窗口。线之间只通过**已发布的文件**交换信息（CURRENT_BEST、共享参照、最终报告、STATUS），不读别人的工作目录，不改别人的文件。

## 1. 拓扑（2026-11-19）

```
main ── 稳定基线；只接收已收尾的 PR（用户合并）
 ├─ docs/<主题>-YYYYMMDD           论文素材、发现记录、主线、文献、skills → PR 到 main
 ├─ data-v1、data-v1-pubchem-completion-20261103、delivery/<名>-YYYYMMDD   数据线 → PR 到 main
 ├─ integration/<名>-YYYYMMDD      多分支有序集成
 └─ model-v3                       模型线 v3（PR #5 → main；旧任务 11-13 已终止）
     ├─ perf/<主题>-YYYYMMDD       早期提速（#6 已并入 model-v3）
     └─ p-recipe                   P 研究主干 = 配方线（PR #7 → model-v3）
         ├─ perf/<主题>-YYYYMMDD   提速线（#8 已合并；#10、#13 → p-recipe）
         ├─ p-heads-20261117       head 类型线（起点 p-recipe@0463aff）
         └─ p-followup-20261116    任务解耦线（#14 草稿 → p-recipe）
基准线：docs/benchmark-plan-20261117 → data-benchmark-b0-20261119 → benchmark-b1-20261119
archive/<名>-YYYYMMDD：冻结的历史状态，不再开发
```

- **PR 的 base 就是分支起点所在的线**：侧线 → p-recipe；p-recipe → model-v3；model-v3 → main；docs 与数据 → main。合并顺序自下而上。
- 新研究阶段（例：P 结项后的 S、D 研究）的主干和起点由用户在任务书里写定；没有写定前不开新主干。结构仿照 P 研究：一条主干线持有 CURRENT_BEST，侧线从它分出、PR 回它。
- 论文素材和发现记录一律从 `main` 分出 `docs/...` 分支，与实验分支无依赖。
- 每条线在服务器上有独立工作树（例 `X:\MFM_p_recipe` ↔ `/share/home/zixiao/descriptor_analysis/MFM_p_recipe`）。一个工作树只检出本线分支。

## 2. 命名

| 对象 | 规则 | 例 |
| --- | --- | --- |
| 长期主干 | 不带日期 | `main`、`model-v3`、`p-recipe`、`data-v1` |
| 线 / 主题分支 | `<线或主题>-YYYYMMDD`，日期为开线日；按用途加前缀 `perf/`、`docs/`、`delivery/`、`integration/`、`archive/`；小写、连字符 | `p-heads-20261117`、`perf/sync-free-20261117`、`docs/finding-last-layer-collapse-20261115` |
| 线的目录 | 分支名去日期，连字符改下划线；四类目录同名 | `docs/p_heads/`、`configs/p_heads/`、`tools/p_heads/`、`results/p_heads/` |
| 规则文件 | `TASKBOOK[_Vn].md`；`USER_DIRECTIVE_YYYYMMDD[B].md`（同日第二份加 B） | `docs/p_recipe/USER_DIRECTIVE_20261118B.md` |
| 日报 | 沿用该线已有写法，不在中途改 | `docs/p_recipe/daily/2026-11-19.md`、`docs/p_heads/DAILY_20261119.md` |
| 臂 | 字母 = 轮次或部分，数字 = 序号；合并配方 `M<n>`；基线 `B0` | 配方线 A1–A5（第 1 轮）、B1–B4（第 2 轮）、C1–C4（第 3 轮）、X/F/PP（第 4 轮）；head 线 H/T；M2 = A1+B3+B4 |
| 运行 | `<配置集>_<轮或部分>_<臂>_..._seed<k>`；重试、迁移、续跑加后缀，不复用旧名、不覆盖旧输出目录 | `fixed_20261115_round3_M2_infra_recovery_20261117_sbatch`、`..._attempt2` |

- 新臂命名前先查本线已有名字，避免撞名（例：第 4 轮 G1/G2 因与 `calibration_20261114` 的 G1、G2 冲突改为 X1/X2）。`D1–D6` 在配方线专指 P0 诊断。
- 不同线可以用同一个字母（任务解耦线也有 C、D）。**跨线提到臂时一律带线名**："配方线 C3"、"任务解耦线 D′"。
- 路径和运行名里不用 ′，写 `Sprime` / `Pprime`。

## 3. 提交与推送

- 每完成一个里程碑提交并推送一次（预注册、每臂训练完成、判定、CURRENT_BEST 更新、冻结、最终报告）。不攒到最后。
- 推送前 `git fetch` 并 rebase 到远端同名分支。用户会直接往分支上提交（常见是 AGENTS.md 的新规则），**这些提交必须保留为祖先**；不 force-push，不改写已推送的历史。
- 同一分支上的多个子 agent：各写各的目录，推送前 rebase，冲突只在自己目录内解决。
- 每次提交前跑 `python tools/check_repository.py`。真实数据、权重、checkpoint、计算标签、缓存、凭据不进 Git。
- 新代码放在默认关闭的开关后面，不改既有配置文件；这样合并任何侧线都不会改变主线配置。
- 执行窗口只写本线目录、`current/phychem_mfm/` 中默认关闭的新开关，以及 STATUS 的追加。不改其他线的分支和文件，不改 `docs/paper/`。

## 4. PR

- **只有用户合并 PR。** agent 开 PR、更新 PR 描述，不合并、不关闭、不改别人的 PR。
- 开 PR 的时机：本线科学工作全部有最终判定 → 最终报告 → 一次完整回归（仓库默认测试 + `tools/check_repository.py`）→ 开 PR。有未完成项时开**草稿** PR，并在描述第一段写明还差什么。
- 描述包含：任务书与指示的路径；每臂 Δ、CI、判定；胜出项的配置键和对照基底（无胜出项也写明"无胜出项交接"）；回归结果，历史失败如实列出（不为全绿改检查器或删历史资产）；"开 PR，不合并"。
- docs 类 PR（论文素材、发现、skills）只含文档，可在实验分支之外独立合并。
- PR 合并后不删除分支；线结束后由用户决定是否改名进 `archive/`。

## 5. CURRENT_BEST：当前最优配方的唯一来源

文件：研究主干上的 `configs/p_recipe/CURRENT_BEST.json`（P 研究）。下一阶段照此在新主干上建同名文件。

- **只有主干线（配方线）写它。** 内容：配方名与组成、配置路径（仓库相对与服务器绝对）、运行名、seed、样本数、完整训练状态 checkpoint 路径、R1/R3 均值与 1000 次 bootstrap CI 及其来源文件、`authority`（依据哪份指示）、`status`、`updated_at`。
- 更新时机：每轮合并得到新 M 且按合并规则确认后（见 `mfm-experiment-decisions` 第 5 节）。更新后日报记一行、STATUS 追加一条、推送。
- **其他线不自行判断哪个配方最优**，也不从 `scores.csv`、日报或别人的结果里推断。
- 读取方式：每条新运行启动前读一次，解析到实际配置 JSON，复制后只改任务书列出的键；把所用 CURRENT_BEST 的 `recipe` 与 `updated_at` 写进该运行的配置或日志。
- 已启动的运行不因 CURRENT_BEST 更新而切换基底；它的对照就是它启动时用的基底。基底变化后的合并由配方线按合并规则处理（例：M3 ≠ M2 时加一条 3M 合并运行）。
- 最终 CURRENT_BEST 发布即配方冻结（`status` 写明冻结）。冻结前不提交任何 9M。
- 共享参照照同一模式：配方线发布、其他线只读复用。例：`configs/p_recipe/M2_SEED1_REFERENCE.json`（M2 seed1，供各线补 seed1 时作对照，不各自另跑）。`status` 不是 READY 时，等待并在日报记一行，不自己训练替代品。

## 6. 跨线交接

| 方向 | 发布方做什么 | 接收方做什么 |
| --- | --- | --- |
| 主干 → 侧线（基底、共享对照） | 更新 CURRENT_BEST / 共享参照；STATUS 追加一条 | 新运行启动前读取；在跑的不切换 |
| 侧线 → 主干（胜出项） | 两种子判定完成后，在最终报告写清每个胜出项的配置键、对照基底、每个 seed 的 Δ 和 CI；日报记一行；STATUS 追加一条。**没有胜出项也要明确发布**，配方线要等所有线有判定才能冻结 | 配方线把各线结论记入 `configs/p_recipe/fixed_20261115/external_line_decisions.json`（来源文件 URL + git blob、每臂状态、采纳组件），按合并规则并入最终配方。侧线不改配方线的配置 |
| 数据线 → 模型/训练线 | 发布交付清单（manifest、store 引用、归一化、配置引用、实际作业记账）；STATUS 追加一条 | 用真实 loader + 逐头过拟合验收后才算接收；在此之前 ACK 记为 false，不以数据端"导出完成"代替 |
| 一条线复用另一条线的工具或结果 | — | 按路径直接调用或在本线 `tools/<line>/` 里包装，不复制、不修改原文件；只读对方已发布的结果，不写进对方的 results 目录 |
| GPU 让卡 | 按用户写定的优先顺序（例：提速线先于配方线，配方线先于侧线；主线要新卡时主线优先） | 只用让出的卡，不抢占在跑任务 |

交接的内容以文件为准，不以对话或日报里的口头描述为准。

## 7. STATUS：跨线公告，只追加

文件：`docs/interfaces/STATUS.md`。

- **只在文件末尾追加，不修改、不删除、不重排已有条目。** 更正也写成新条目，并指明更正的是哪一条；被更正的旧条目保留为历史。
- 一条公告一段，以 `[<线名> <主题> YYYY-MM-DD HH:MM CST]` 开头（例：`[P heads T1 LIVE 2026-11-18 01:15 CST]`），写：发生了什么、权威文件在哪、其他线需要做什么。细节放本线文档，这里只放链接。
- 该发公告的事：CURRENT_BEST 或共享参照更新、配方冻结、胜出项或"无胜出项"交接、用户新规则影响其他线、让卡与占卡、数据交付。
- 影响其他线的公告，同一条也追加到这些线工作树里的 STATUS（各分支各有一份副本）。这是允许写入其他线文件的唯一情况，而且只能追加。
- 文件顶部数据线早期"最新在上"的段落是历史写法，保留原样，不整理、不迁移。
- 合并或 rebase 时 STATUS 冲突：两边条目全部保留，不去重、不改写。

## 8. 不做清单

- 不合并 PR，不 force-push，不改写已推送历史，不丢弃用户直接提交的 commit。
- 不在别人的分支、目录、配置上提交；STATUS 追加除外。
- 不从 CURRENT_BEST 以外的地方推断"当前最优"；不在运行中途切换基底。
- 不复用运行名、不覆盖旧输出目录、不删除旧分支。
- 不把一次性运行事实（PID、job ID、哪张卡空着）写进本 skill。
