# 可移植项目上下文

整理日期：2026-11-05，Asia/Shanghai。

本目录整理 descriptor_analysis / PhyChem-MFM 的相关技能、明确用户要求、
科学约定与已记录结论。新电脑克隆**包含本目录的分支**后，Codex 可通过
根 AGENTS.md 和 .agents/skills 加载；不依赖旧电脑的自动记忆、用户目录或盘符。

| 内容 | 入口 |
| --- | --- |
| 研究目的、模型线/数据线、交付物 | [PROJECT_GOALS.md](PROJECT_GOALS.md) |
| H0、S/D/P、几何、标签、掩码、划分、归一化 | [SCIENTIFIC_CONTRACT.md](SCIENTIFIC_CONTRACT.md) |
| 调度、恢复、监控、资源、存储和提交 | [WORKING_METHOD.md](WORKING_METHOD.md) |
| 用户修订、适用范围与旧规则替代关系 | [DECISIONS.md](DECISIONS.md) |
| 整理日已记录的交付、暂停和待验收状态 | [STATE_20261105.md](STATE_20261105.md) |
| 历史实验与诊断的科学认识 | [RESEARCH_LESSONS.md](RESEARCH_LESSONS.md) |
| 技能/记忆来源、纳入与剥离范围 | [SOURCE_INVENTORY.md](SOURCE_INVENTORY.md) |
| 新电脑接入与维护 | [MIGRATION.md](MIGRATION.md) |
| 小型来源文档的字节身份与覆盖说明 | [source-manifest.json](source-manifest.json) |

## 阅读与优先级

1. 当前用户明确要求与适用的 AGENTS.md。
2. 当前任务的版本化科学契约、明确用户修订和原始闭合证据。
3. 本包整理摘要及带日期的状态。
4. 更早任务书、试点报告、自动记忆和历史 ACTIVE 记录。

同级冲突需核对原文、时间与范围；不能把其他任务的最新许可套用过来。
本包不替数据线或模型线签署接口验收，也不宣称所有历史规则都仍有效。

## 覆盖范围

本机自动记忆目录盘点时含 0 个文件。知识主要来自自定义技能、
项目 AGENTS、两线任务书、字段说明和交接，不是导出了隐藏的完整记忆库。
本包是文档快照，不是实时队列、资源或数据库镜像。

本分支以 main 的历史源码快照为基底，只整理知识和技能。
model-v3、data-v1 的当前实现仍在各自分支；这里不表示已合入 main，
也不证明正式预训练已获授权。大数据与完整运行证据保留在外部。

