# 10k 前缀兼容候选评估实际记录

本报告仅汇总已完成任务的小型证据，未读取 raw 或 SQLite 正文，未重跑测试或科学计算。

4520597 在 compute-0-17 以16CPU、4GiB完成；8198个旧成功CID的本轮全部特征保持原样，8197条历史完整特征一致；753条旧环片段异常全部恢复，1049条化学排除及顺序不变。输入共10000条，16个worker均实际处理记录。

历史只有8197条完整去重特征和8198个alias；重复alias没有单独历史完整特征。本轮分别核对历史完整特征、alias身份和8198次独立legacy/candidate全字段比较，不从旧trace推造缺失字段。

4520593 保留为FAILED/1:0：首次generic-first候选导致320条旧成功记录仅generic_ring_systems变化；原历史特征与旧代码重放零差异。Root只读审计确认753条原异常均为KekulizeException，具体radical/implicit-H机制未被宣称实证。

兼容候选优先原样返回旧结果；仅精确KekulizeException且真实traceback命中已pin旧features代码对象的第70行sanitize才调用已验证fallback。其他异常重抛；证明为组合证明，不声称新wrapper的AST等于旧features。

新增兼容fixtures由4520597实际日志证明Ran 4 tests及OK，耗时0.339秒；旧3项prefix fixtures沿用4520593实际PASS，未在597重跑。两轮原始raw/旧pool的完整SHA与前后stat证据一致。597监控9个样本、无memorydenial，持久证据导出完成。

| 父任务 | 实际状态 | Exit | ElapsedRaw秒 | CPU | 分配核秒 |
|---|---|---|---:|---:|---:|
| 4520593 | FAILED | 1:0 | 8 | 16 | 128 |
| 4520597 | COMPLETED | 0:0 | 8 | 16 | 128 |

两次父任务合计256分配核秒（0.071111111111核时）。成本取owned_accounting_cpu_v14实际父任务ElapsedRaw×AllocCPUS，包含593失败，不重复计steps；不是CPU利用率或receipt内部计时。

新评估产物含8951个alias、8949个full key，保持未放行。repair_applied=false、pool_modified=false；COMMON_PENDING继续保留，未证明全来源去污染，未授权正式pool、UFF、QM、训练或全源筛选。593 STOP及原pool均保留。

Compact proof（全部小证据path/bytes/SHA、实际父任务和日志引用）：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/diagnostics/paired_prefix_compat_actual_v1.json`。

报告生成时间：2026-10-25T21:25:04.020649+08:00。

报告生成器v1/v2在写输出之前分别因accounting/audit哈希字串抄录错误拒绝；两旧源码保留。v3的两引用从实际文件自动绑定，原证据未改，没有重跑科学或Slurm任务。
