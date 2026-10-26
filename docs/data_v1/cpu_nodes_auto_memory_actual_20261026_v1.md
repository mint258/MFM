# CPU 节点与自动内存规则落实记录

2026-10-26，用户明确要求将11–13加入可用CPU节点，空闲CPU即可提交，sbatch不指定内存大小。该授权覆盖本轮旧64GiB、全用户声明85%与仅14–19的调度条件；科学参数、成功率、排除率及实际成本阈值不变。

本机与服务器 `docs/skills/huagong_hpc_requirement/SKILL.md` 已同步至1.0.120，两份SHA256均为 `1f5ba2de0998d76fb547a3531906915c95d54ec79342fd90d7fa36dfbe88ae39`。本轮资源决策保存在 `configs/data_v1/user_cpu_auto_memory_20261026_v1.json`，SHA256为 `25c1b2f301ce2b07aa8eb57db9b406e003bf97f76aa5d50e2186b75317713fdc`。

一般分析使用实际cpu分区（本次2、8–19），S′/UFF/QM可用11–19，每任务16CPU。新脚本不写内存或exclusive选项，并移除继承的SBATCH_*环境参数；实际调度默认内存如实记录。保留RSS/MemAvailable观察、软件软预算、紧张时停止新派发并自然收尾、quota至少200GB以及48小时上限。不修改或终止其他用户、模型作业及已运行科学任务。

已实际落实：作业4521065在compute-0-12完成，COMPLETED/0:0，28秒、16CPU，30项原队列/构象恢复/retention/标签来源语义边界全部通过。实际SLURM_MEM_PER_NODE、SLURM_MEM_PER_CPU、SLURM_MEM_PER_GPU均未设置。它只验证运行与语义边界，未读取科学记录或调用UFF/QM；不代表后续新适配器通过。

证据：`control/auto_mem_bootstrap/4521065.json`，1812字节，SHA256 `cbba27f6963c6df3287d77a35165c84abe5c73288e6239461a545888688bc79a`。新策略首个独立队列检查4521077已实际提交且仍held/PENDING；放行前校验发现旧Slurm字段解析不识别AllocNode:Sid，正在用新版本修复，尚无该队列8项新检查PASS。旧9项严格内存请求全部核为自身PENDING后hold，原请求、回执与源码保留，待新入口闭合后逐项替换，不重复科学执行。

费用纠正：旧S′恢复预算遗漏原始准备4520335的606秒×16CPU=9696分配核秒。新的补算准入须包含该费用、所有相关历史费用和后续closure/验证预留，再选择较短申请时限，仍遵守原96核时门槛；旧6900秒方案与94.777778核时说法只作为原历史估算保留，不能作为新准入证据。

当前阶段仍未交付D3–D7、正式S′/P′及扩充第一批。Se单元素例外、ROUTINE整分子VAL和其他科学门槛保持。
