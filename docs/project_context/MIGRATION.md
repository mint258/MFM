# 在另一台电脑恢复使用

## 获取同一份上下文

先克隆包含本包的文档分支：

```bash
git clone --branch docs/portable-project-context-20261105 https://github.com/mint258/MFM.git
cd MFM
```

在这个目录启动Codex，先读根AGENTS.md及docs/project_context/README.md。
支持仓库技能发现的客户端会扫描.agents/skills；看不到时重启客户端，
也可直接在任务中引用对应SKILL.md。无需复制整个个人Codex目录。

这是知识/技能分支。运行或开发当前模型/数据实现时使用实际model-v3/data-v1
分支，把本包的文档改动通过审阅合并/挑选到目标分支，不把main旧代码当最新实现。
本包没有合并科学代码，也不表示最终验收或正式预训练获批。

## 绑定环境

| 角色/逻辑量 | 新环境需确认 |
| --- | --- |
| checkout root | 当前实际Git工作树，不假设固定盘符 |
| development endpoint / project root | 用户指定开发服务器、身份与真实目录 |
| expansion endpoint / storage root | 扩充集群身份、当前工作根与独立账户配额 |
| paid pretraining endpoint | 单独配置；仅明确授权正式预训练才使用 |
| Python entry | 当前逻辑venv/conda入口及实际依赖，不复制另一台电脑绝对路径 |
| persistent data / runs / scratch | 三类物理根及各自quota、inode、容量和恢复依赖 |
| authentication | 目标电脑安全密钥/连接器及已核主机指纹，不从本包找秘密 |
| scheduler | 该集群既有partition/account/QoS/节点策略和当前资源 |
| tracking | 持久W&B/同等工具及输出/归档根，准确标离线/同步状态 |

这些绑定放在各电脑的未跟踪本地配置或安全配置中。
不要把凭据、用户目录、真实私钥路径补回公共文档。
需要远程文件编辑时确认它确实指向目标服务器；普通克隆不是科学数据同步。

## 检查加载是否正确

让Codex解释当前任务的研究目的、TRAIN-only边界、D3/D6状态及所需环境绑定。
若它仍要求旧盘符、旧用户主目录或从历史ACTIVE续跑，说明加载了旧指引或
没有正确应用日期/作用域。核对.agents/skills和当前AGENTS，而不是重跑科学验收。

本包是显式文档，不自动导入Codex的memories/memories_v2生成状态，
也不保证聊天历史或插件授权跨机可见。必需规则留在Git，临时状态现场核验。

## 维护方式

- 稳定科学定义写SCIENTIFIC_CONTRACT，工作习惯写WORKING_METHOD。
- 用户修订在DECISIONS记日期、范围和替代项，不只是前面追加矛盾条款。
- 新交接另存带日期状态并更新索引；保留失败、未知和暂停。
- 来源变更更新小型来源清单，不为文档迁移重哈希大数据。
- 按需更新三个简短技能入口；通用系统/插件技能从目标环境获取。
- 提交前跑原仓库检查器，检查链接、技能格式与本机/秘密残留。
  不启动训练、数据重导出、Slurm或后台服务来“验证迁移”。

