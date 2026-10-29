2026-10-30运行修订v2：原Native Root协调器最长等待7800秒，v1同步等待会占住总调度锁。
v2只将该原协调器以独立进程启动，总调度器即返回；共享原control/state.json，不清空旧intent。
原Native CLI自身phase锁和已持久化slot意图照旧。小时检查发现原Root进程还活着时不再提交；
进程退出后，只有原ROOT_LONG_SEGMENT_CLOSURE真实C0才允许下一段，失败/缺失/歧义停该线。
其他两条线仍可每小时检查。旧v1和全部运行/失败原件保留，模型、数据、20k、资源门均未改。
新增3项调度安全UNIT，总14项；实际结果由Root验证，不能把进程启动当作GPU完成。
以下v1方法中源路径改用hourly_resource_dispatch_20261030_v2_source，其余政策保持。

# 用户授权：模型线每小时资源检查与自动提交

2026-10-30，用户要求“之后每小时检查一次，在可用时提交上任务”。

开发服务器 sonmi/zixiao 的用户 cron 每小时整点执行一次，时区 Asia/Shanghai。
源目录 runs/model_v3_20261026/hourly_resource_dispatch_20261030_v1_source；
状态目录 runs/model_v3_20261026/hourly_resource_dispatch_user_20261030_v1。
此为服务器定时器；没有创建 ChatGPT/Page 云任务，也不调用付费模型 API。

范围仅为已授权、已冻结的三个入口：未测3090/5090 C1-a（不重跑4090），原438
当前v2验收，以及原Native B四条20k曲线的后续段。不加入新候选或正式预训练。
现有有界等待进程仍存活时只核验实际内核身份并让原进程管理，避免重复提交；
其退出后，定时器能接续只读等待/未提交的入口。已有调用、输出、原始intent、
活跃Root子进程或失败/歧义都不能自动重放。

每次实际探测Slurm空闲CPU、物理MemAvailable、GPU UUID及实际进程，已知循环作业
在两个GPU进程间的空隙仍视为占用。保留至少16CPU、32/64GiB原软件预算及15%余量。
真正提交仍由原冻结Root CLI再次核验资源、软件预算、85%、共享UUID锁、RSS和配额，
GPU Slurm仍不声明固定内存。Cron只做轻量metadata/调度，不在登录节点跑模型。

Native只允许已明确核清的031前模型失败→032/9000至10000这一项原授权retry；
任何新的实际失败或不明intent均停该线，不自动retry。历史失败不抹除，
原108次总attempt/12次failure/96段成功上限及四成员/20k计划仍由原入口约束。
A/C1-a各入口最多调用一次；日志、W&B和周记账节奏不因每小时检查扩增。

hourly.lock保证Cron不重入；当前Root调用状态先持久化intent，调用歧义不可重放。
某条线metadata异常只记录，不抑制另外两条线。最近状态见last_tick.json；
--check-only只探测及预览，不提交、不写调用intent。仍在执行的原Root调用由
调度器锁和真实进程双重防重复；不会杀运行的模型或他人作业。

禁用方式：仅删除crontab中CODEX_MODEL_V3_HOURLY_20261030标记块。
不修改其他cron项，不终止已经提交的Slurm任务。全部结果仍须按原科学门实际验收；
定时器的“已提交”绝不代表科学通过。
