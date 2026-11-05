# 来源与技能盘点

本包只发布项目有关、可跨电脑理解的知识。
“会话可用技能”不等于“每项都曾在项目执行过”。

## 项目相关来源

| 来源 | 本次处理 |
| --- | --- |
| 自定义huagong_hpc_requirement v1.0.145，11-05更新 | 提炼成mfm-hpc-workflow、科学约定、作用域决策与日期状态；不整份照搬约200KB时间线 |
| 该技能references/commands.md | 保留SSH/stdin、逻辑解释器、Slurm、会计、路径与恢复经验；剥离机器命令和旧进程 |
| 该技能references/wandb_archive.md | 保留持久记录、状态、归档/同步区别和来源绑定；不保存绝对归档根或服务PID |
| 自定义molecular-training-triage | 指导内容完整保留为仓库技能 |
| 当前项目AGENTS与本地工作入口AGENTS | 保留执行/数据/科学边界；项目根改为可移植导航，不复制旧电脑配置 |
| 数据线、模型线根任务书 | 汇总目标、分工、交付、方法及科学决策；后续明确修订优先 |
| Phase1正式指示 | 保留受控比较、H0、监督定义及S的物理混杂 |
| 数据卡、注册表、导出报告、P′报告、11-05每日汇总 | 保留定义、修订、当前交付与限制，旧版状态明确不升级为当前 |
| 模型EXECUTION与接口STATUS | 用作时间/接口差异证据；旧10-26状态不冒充11-05最新 |
| 历史Stage A–C结果、Stage B/D实现比较 | 摘取科学认识和比较限制，剥离本机链接 |
| 本会话可见的工作要求 | 保留用户优先、真实证据、明确停止/暂停范围和跨机需求；不导出聊天原文 |
| Codex本地自动记忆目录 | 盘点为0文件，未生成“全量记忆已迁移”的声明 |

来源字节身份见source-manifest.json。摘要保留了影响后续决策的信息，
不穷举每个历史job、每轮曲线或每个旧交接版本；完整证据仍由原分支/外部清单追溯。

## 新的可发现技能

| 路径 | 用途 |
| --- | --- |
| .agents/skills/mfm-project-context | 跨机恢复目标、科学背景和交接 |
| .agents/skills/mfm-hpc-workflow | 服务器、调度、恢复、资源与存储 |
| .agents/skills/molecular-training-triage | 分子模型/ADMET诊断顺序 |

旧个人技能不在本次被覆盖或删除。新HPC技能改用连字符名以符合技能命名，
并与原个人技能区分。将来同一环境有两套技能时，以当前项目AGENTS和本包
版本化科学记录为准，不能把旧机器操作细节重新注入。

## 系统与插件技能

下列是会话环境提供的通用能力；它们不是本项目的科学记忆，不复制缓存或
系统包进仓库。新环境按所需功能启用对应插件/技能。

| 类别 | 本会话可用名称/能力 |
| --- | --- |
| 系统帮助/创作/安装 | openai-docs、skill-creator、skill-installer、imagegen |
| 文件与图示 | documents:documents、pdf:pdf、presentations:Presentations、spreadsheets:Spreadsheets、visualize:visualize |
| 本机应用 | computer-use:computer-use、spreadsheets:excel-live-control |
| Google Drive | google-drive:google-drive、google-docs、google-sheets、google-slides、google-drive-comments |
| 网站/模板 | sites:sites、sites:sites-remix、template-creator:template-creator |
| 插件/安全入口 | plugin-management:plugin-management、defense-factory:open-defense-factory |
| 页面 | pages:maintain-space、manage-schedules、organize-space、write-page；本会话已禁用Page skills，不作为迁移依赖 |
| 宠物 | work-pets:create-pet、work-pets:pets、work-pets:update-pet；与项目无关 |

本次整理实际使用HPC规则与Skill Creator；此前同步机制说明使用OpenAI Docs。
其他通用能力是否在完整项目历史中用过，不由可用列表推断。
插件授权、系统技能版本及平台行为留给目标环境管理，不复制服务凭据。
GitHub发布使用当前连接器，认证不会写入本包。

## 剥离的内容

- 客户端用户名、个人主目录、盘符、OneDrive路径、私钥位置。
- 服务器IP/账号与具体私有绝对根；使用角色和待绑定的路径约定。
- 密码、API key、token、私钥、认证文件、浏览器状态、聊天原文。
- SSHFS盘符修复、本地代理端口、临时SFTP适配器和本机进程。
- 旧会话ID、PID/boot/start ticks具体值、节点瞬时占用、quota瞬时读数。
- 一次性清理目标/删除许可作为未来操作命令，和已被修订规则作为当前硬门。
- 重资产、活动SQLite、原始科学数据、checkpoint和未同步SDK文件。

保留进程身份核验的方法，不保留旧进程值；保留quota正确计量，不保留旧空间
快照作为准入依据。保留“发生过并已结束”的科学结论，不保留危险的旧续跑指令。

