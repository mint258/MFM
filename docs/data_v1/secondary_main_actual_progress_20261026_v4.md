# 数据线实际进度，2026-10-26 第四次记录

用户已明确“核时超标报告后继续，质量阈值不变”。本轮仍使用至少16CPU、无SBATCH内存或exclusive申请、单任务不超过48小时、CPU-only、真实RSS/MemAvailable观察和200GB存储余量。Main与Alpha按端点及UID分别记账，不修改其他用户或模型作业。

## 已闭合的实际工作

标签16个源状态扫描与汇总4521201全部C0，覆盖1,220,466分子、11,231,854记录、2,024文件和14任务。余12片实际392,736分配核秒，即109.093333核时，约初始试点外推的3.769倍；原先1.59倍只是运行中观测。全部失败、超时、启动和复核费用保留。源状态清点不代替数组/JSON形状、原生精度、单位、物理范围、跨字段及分子内异常的数值验收。

本地身份404单元的11,398,552唯一身份已由4521192从原4521152的落盘结果只读闭合；18项缺失身份/组成仍保留，不能因此宣布全部外部去污染完成。

Alpha固定16个UFF软件对照1884766 C0/40秒。独立读回1884768 C0/6秒/16CPU/compute-0-6，即96分配核秒：完整核验32份gzip的SHA、EOF/CRC及科学内容，16个结果精确一致，仅排除summary.elapsed_seconds。Root另存当前七件科学源码、原配方及实际环境版本的有限软件兼容性验收；原回执未被修改，人口新增0。这不是全人群或全量生成质量验收，也未冒称在Main UID1278上执行。RDKit2025.09.5/Python3.11.14一致，Torch和PyArrow版本差异继续明示。

COCONUT官方完整CSV下载1884764 C0/47秒，ZIP247,959,854字节、738,794个逻辑数据行。完整SQL1884765 C0/5778秒/16CPU/compute-0-1，实际92,448分配核秒（25.68核时），37,876,914,074字节，完整SHA已核验。其有界结构检查1884767 C0/31秒/16CPU/compute-0-6，496核秒，两项隐私fixture先通过；实际观察到15张PostgreSQL表的DDL、前缀citables COPY和尾部dump完成标记。它只读16MiB前缀及64KiB尾部，未声称全表行数、inactive身份或规范化覆盖。

## 已提交而尚未得到结果

Main最近总账checkpoint22包含126个本任务父作业，已观测231.2888888888889分配核时；这是指定时点会计，Alpha单独记录。当前五项实际排队：

| 实际父作业 | 工作 | 结果边界 |
| --- | --- | --- |
| 4521293 | P′原生打印精度及72例只读诊断 | 原15项协变矛盾与原容差保持 |
| 4521316 | PubChem全原始空间均匀10000成本试点 | 与筛选去重后的指南1M样本不同 |
| 4521321 | S′原334包、14个同seed对照及2个未决项的快照闭合 | 不新增UFF，不伪造两个缺包 |
| 4521326 | PM7 N1完整5040母表及固定32例准备 | 尚无第二真实UFF几何生成 |
| 4521327 | 标签512分子/4251记录实际payload数值试点 | 原六项fixture在数据正文前执行 |

4521315经核仍PENDING/Elapsed0且无proof/输出后，仅按PENDING状态过滤取消，以4521321替换；任何运行中作业均未被强制终止。新快照闭合只核验冻结的历史费用选择，不再等待未来无关作业终态。新N1试点使用原始角色与已验证baseline来源，明确共同人群尚未最终冻结；禁止复制坐标伪造N2。

Main最近现场CPU节点最多只有8个空闲核，未达到16核，因此继续等待调度；未占用他人已分配的CPU。Alpha仍有授权CPU资源，继续在独立端点推进可搬运的工作。

## 第二集群的下一步

PubChem原始文件1,488,715,010字节已通过SFTP传到Alpha；目前只确认传输结束和预期长度。待实际CPU核验完整SHA、8,880,849,781解压字节、124,857,440物理行及gzip EOF/CRC前，不释放原始文件pending cap，不进行化学筛选。

新增独立readonly queue v3仅允许三个固定协议：PubChem原始副本完整性、COCONUT身份字段投影profile/full，以及P′原72例只读诊断。原v1/v2及注册请求保持不变。SQL先实测256MiB投影；该前缀可能仅含citables，不能推断尚未覆盖的身份输出或化学处理吞吐。全SQL投影后仍需单独规范化试点及全量外部身份去污染，不能根据结构观察放行候选池。

P′ Alpha搬运清单固定460件/18,909,196字节，包含72份原SQLite、72份case结果、288份原输入和28份小源码/元数据。Main历史没有整库SHA的事实保持；实际Alpha作业在原四项fixture通过后记录新的整库观测，再通过原per-call SHA、gzip EOF/CRC和member SHA闭合。不得把Alpha新观测回填为历史Main整库SHA。

## 仍未完成的交付

D1 draft.3尚未共同冻结；模型已有候选provider及真实合成串联4521005，真实authority/tensor/basis/perturbed及50kTRAIN+5kVAL加载验收仍待完成。D2最终注册表、D3试点导出、D4最终TRAIN-only统计、D5最终子集、D6全量导出、D7完整构象统计、全量S′/P′、全部外部去污染、ordered10M及首2.5M实际UFF+D生成均未全部完成。P′2000/full QM HOLD及其余质量阈值保持；当前不作最终验收或最终PR。

## 可复核证据

外部路径以`runs/data_v1_20261025/`为根，科学数据未进入Git：

- `control/owned_accounting_checkpoint22_cpu_auto_memory_20261026_v1.json`：Main126父总账与原始sacct引用。
- `control/source_status_all16_actual_C0_review_v1.json`：全部16片及超标核时。
- `control/secondary_cluster_20261026_v1/readback16_1884768/`：Alpha独立报告、实际父会计、原sacct与机器生成的原端点SHA。
- `control/secondary_cluster_20261026_v1/control16_root_software_scope_acceptance_v1.json`：Root有限软件验收。
- `control/secondary_cluster_20261026_v1/coconut_sql_1884765_terminal_metadata_facts_v1.json`：Alpha完整SQL终态、完整SHA和费用事实；原完整receipt仍在Alpha。
- `control/secondary_cluster_20261026_v1/sql_format_1884767/`：实际结构、fixture、启动及会计的字节相同副本与copy_map。
- `control/alpha_pubchem_raw_validation_staging_v1/copy_plan.json`：原348 intent与两份真实父提交/会计的诚实映射，不替换原JSON路径。
- `control/alpha_native72_staging_v1/copy_plan.json`：固定460件原始搬运定位器；不是已执行科学校验。
