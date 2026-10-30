# 数据线每日汇总：2026-10-30

更新时间：北京时间19:43。优先交付版本为 `v1-pilot-provisional`，截止2026-10-31 17:52:59。共同人群、D-6/D-7、P′和后台扩充均不阻塞D-2至D-5。

| 项目 | 当前核实状态 |
| --- | --- |
| D-1 | v3.0已联合冻结；r73权威F64、有序条目、训练一次转F32；r674原值/部分值/掩码保留，LOSS_DISABLED，不追加QM。 |
| D-2 | 146字段定义字典已发布，入口configs/data_v1/d2_v1_pilot_provisional_registry/published.json，commit e987bb2。数值mask、rho、HoF及D4绑定待真实D3/D4，不冒称完整训练注册表。 |
| D-3 | 固定50,000 TRAIN+5,000 ROUTINE VAL、均已有完整S′。尚未提交；新版16文件消费者Source已安装，真实D4完整C0后自动执行原3项检查、10,000条F64源值对照/一次F32转换、16-reader核验，再发布D2/D3/D4。 |
| D-4 | 4525252实际RUNNING16CPU CPU17，原6项Source检查PASS。55,583个旧闭缓存片已全部只读核验复用；新增11,940片后完整typed覆盖已闭合，checkpoint2于19:20进入GEOMETRY，正在核验已有几何与实际标签输入绑定，尚未数值交付。后续原171组统计与两次TRAIN重放不变，无新QM/UFF。 |
| D-5 | 4525184实际C0并正式交付，入口configs/data_v1/D5_v1_pilot_provisional_delivery.json，commit1b3aa35。TRAIN120k⊂240k⊂600k⊂1,108,366；VAL母人群7,016，试点50k/5k；20k诊断分子各留PM7及普通S′，相关全部子几何/输入视图在first-k前排除。 |
| P′正式计算 | 4525255–4525263九个日级父作业实际RUNNING144CPU，另5266及退回Main的5270各16CPU，当前加上新接续5271–5273、5275/5276共256CPU（16个实际Slurm父作业），覆盖Main专属0000–0008片；每个均原3项Source及独立闭输入CPU核验PASS。原五个输入Parent4525244–48继续RUNNING80CPU，完整38片覆盖1,059,751新MID。 |
| P′旧批产出 | 4525253已结束FAILED3:0/5,030秒/16CPU；13,839条技术完成，其中13,833条全12项成功，1条UNKNOWN consumed保留，不重试；86,144条未派发。精确继承的32GiB结算门与正式64GiB不一致，隔离v2最小工具修复已实际4525266 RUNNING16CPU CPU17，跳过全部已consumed；九个新作业不受影响。旧5243的10成功及6UNKNOWN也保留。 |
| Alpha P′ | 0009片已独占分配给Alpha，无Main Native重叠或预先claim。Main4525264/4525265两次实际CPU打包失败，分别为原LMDB authority参数和Source/runtime Body路径分类检查，零QM/claim。按两次失败上限记未解决、停止该迁移诊断；实际Alpha UID/队列/未部署Source已核实；0009通过独立不可变退回记录交给Main，无重试/预claim，原Alpha分配保留历史。已关闭无后续用途的Windows转发helper，未动Slurm。Alpha正式Native尚未启动。 |
| N1补构象返回 | 原Alpha1885108/1885109及Main4525249实际C0；4,407包返回，4,400有第二真实构象，4生成/输入失败及3不足状态保留。入口configs/data_v1/conformers/N1_original_alpha4407_source_return_20261030_v1.json，commit073d784。物理QA/ID/Common/D6尚未放行，不重试原7条。 |
| PubChem | 原500片124,857,440行已闭合核对：110,046,364 accepted、14,764,875 chemReject、46,201技术UNKNOWN。Alpha1885120实际RUNNING32CPU CPU1，按原SQL从502个闭物理片形成未过滤去重表，无新化学；活动DB只stat、不查询/哈希。 |

D4→D3→D2/D3/D4发布由限定元数据watcher3770374推进，当前WAIT_ACTUAL_D4_C0。原5232虽Slurm C0，回执实际partial/numeric_replays0，保留原55,583缓存及全部成本；不改写为统计完成。旧5251只在数据前synthetic同长度覆盖的mtime/ctime检查失败；独立resume_v2固定该测试夹具后原6项已PASS，科学读写规则不变。无效旧watcher不再提交D3。

原P′元数据operator3667926经精确身份与锁核对后由Root退役，未给Slurm/其他/模型作业发信号；状态明确交接9片Main、1片Alpha。有限元数据续接3813424已运行：复用当前epochs并追加原38片新的真实闭header，最大16个Main Native、计入5266，保留5253历史；只做元数据，不预claim或重试UNKNOWN。新分片按8GiB父上限、每四父32GiB独立EXEC目录计未来预算；PREP物理池只计一次。全部旧failed/UNKNOWN、旧输出、physical-once与成本保留，后续只领未consumed记录，不重复计算原2,000试点。

模型接线Source已安装并提交311cdcc5：独立provisional typed adapter、本地16-reader、最小三文件Model hook提案及D3诊断补充Source。实际Model载荷ACK仍须真实D3；当前final-release reader不能只替换路径。CPU共享盘与真正GPU训练Parent内本地IO证据分别记录，无shared Model修改、付费服务器或训练启动。

Alpha正式P′桥接保留原MOPAC23.0.3/xTB6.7.1、全部12项参数/精度/种子/900秒、原F64/raw保留策略；Main物理once在Alpha真实派发时建立，失联或UNKNOWN不重试。软件使用原Main固定字节和loader的运输前缀，不下载替代版本。两个集群UID/端点/job分别记账。

常规修复一行：D4 quota近时钟计时及synthetic夹具、便携导出的SOURCE/DATA重复分类、Alpha gate→exec argv读写接缝均按已有授权直接修复；P′legacy结算门隔离修复中。原Source/失败保留，不热改运行Slurm或冻结科学函数。必要仓库检查4525254实际C0/8秒/16CPU，PASS4324文件/2954Python/1311server sources；后来仓库检查4525267/4525268在未运行Alpha bridge的两个语法接缝失败；按两次上限停止修复，未跟踪且未执行的Alpha13+controller3原字节移至control/Alpha_original12_source_unresolved_20261030_v1保留，移出生产树。Main component/portable/legacy必要检查4525269实际C0/11秒/16CPU PASS4355文件/2980Python/1311server sources，未启动Alpha QM。

去污染仍9/11 READY，MoleculeNet/COCONUT保守挂起；PubChem只建立MATERIALIZED_UNFILTERED_NO_RELEASE，不进入训练池。Alpha该物化scope全future1,071,938,958,991B，原实际有效free约1.639TB；相关历史+新32CPU×24h上限18,732,832核秒，低于2倍35,104,634.336。此为scope守门，不冒称全线周记账。

本轮P′放行以原试点1989/2000=99.45%为用户门，11失败保留；科学/筛选规则及2倍用量确认线不变。CPU-only、无SBATCH内存/exclusive、不超占CPU、真实RSS/MemAvailable/scratch/全部future后200GB余量、不动其他或模型作业。任一修复累计4小时或连续失败2次停该问题，保守继续其余交付。每天只维护本汇总，每周一次完整记账；收据/SHA限正式交付及既有必要来源绑定。

实时索引：runs/data_v1_20261025/control/current_work_state.json。
D5载荷补充接线：独立pilot_D3_diagnostic_supplement_resume_v1八件已安装，沿实际resume D3及同一D4统计；逻辑store/wire namespace保持原v1，不修改既有adapter或Model。必要仓库检查4525274实际C0/18秒/16CPU PASS4363文件、2987Python、1311server sources，commit97fefc0。已明确预留32GiB输出+128MiB provider/admin，纳入全future保护；元数据watcher3825890真实存活，等待D3/D4公开交付后提交独立16CPU Parent、实际C0后发布D5_diagnostic_payload.json。未知seen交集/输出SHA未捏造，不阻塞D2/D3/D4先发布，不新增QM/UFF/fit。已知D4配额记录计时修复同时应用于未运行D3的私有IO，原Client有效期/新鲜度/identity和原codeobject不变；未改任何活动D4/P′ Source。

资源接续：实测Node17空闲112CPU、MemAvailable355,387,473,920B、tmp60,631,506,944B；Root仅退役自有纯元数据3813424并交给3842811，未向Slurm或其他/模型作业发信号。Node17 Native上限4→6，整体16父作业、原绝对48h deadline、全部epochs/assignment/once/质量/2倍用量线保留；实际5275/5276均已RUNNING16CPU。旧配置/历史不改，D4与D3/D5优先链继续独立运行。

交付文档：已补齐指南要求的DATASET_V1_CARD.md，按v1-pilot-provisional说明正式入口、现有源与引用链、50k/5k和D5母清单、F64/单次F32、r73/r674/MolMR、TRAIN-only统计、held base/child/input-view排除和seen交集、实际GPU本地IO/Model ACK边界。未来数值/哈希/终态未预填。必要仓库检查4525277实际C0/8秒/16CPU，PASS4364文件/2987Python/1311server sources；未增加科学测试。D4实际仍在GEOMETRY。
