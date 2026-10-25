# 已登记阶段与实际持续观察

目的：核实实际Slurm提交、资源、依赖、监控身份和全部已观测成本。以下是排队/运行状态，不代表科学交付完成。

|ID|步骤|节点|状态|原因|CPU/GiB|
|---|---|---|---|---|---|
|4520959|原22边界检查|compute-0-17|PENDING|Resources|16/64|
|4520960|2缺包恢复+14独立控制|compute-0-17|PENDING|Dependency|16/64|
|4520961|72真实QM帧控制|compute-0-17|PENDING|Dependency|16/64|
|4520962|2000UFF retention准备|compute-0-17|PENDING|Dependency|16/64|
|4521022|14队列+8来源审计边界|compute-0-8|PENDING|Resources|16/64|
|4521023|全人口磁盘索引准备|compute-0-8|PENDING|Dependency|16/64|
|4521036|原物理成员身份导出试点|compute-0-8|PENDING|Dependency|16/64|
|4521037|PubChem全原字节盘点|compute-0-8|PENDING|Dependency|16/64|

实际登记8项，3个独立监控均核对UID、boot/start_ticks、完整argv、PGID/SID、cgroup、源码及新鲜心跳。所有registry的job/request/proof/name不重合。旧监控及其他用户/模型作业未改动。

新2项来源阶段依赖4521022实际C0，并各自在读真实正文前执行4项新增边界。身份试点只投影65536 formal记录、全部4900 embargo及本地全来源小集合；SOURCE_*是原逐记录成员标记，未应用新的整分子TRAIN/VAL/FULL或最终common。训练VAL仍为7610分子/72525记录。外部全来源去污染仍待实际证据。

原始文件盘点完整重验原gzip SHA/EOF/CRC并保留原字节TSV和有界JSONL索引，测真实N，不化学筛选或释放池。正文8880849781B已由原producer观测；元数据保守界及256MiB余量构成9247376245B逻辑预算，实际allocation/目录开销仍须监控，整体10GiB。

来源标签准备是诚实nonpilot：全11231854记录磁盘索引，stage24GiB、wholephase60GiB。实际prepare闭合后只可审首片，实测CPU/RSS/输出再决定余15片；560分配核时是全部预设分配上限，不是耗时预测或全片放行。

所有任务均实际readback16CPU/64GiB、exclusive=user、Requeue=0。启动仍需目标节点120秒内Root证明，重核所有用户声明85%、live memory和实际quota至少200GB剩余。内存0不解释为零占用；S/UFF/QM仍限14–19。

S′6900s追加申请预算加原230800分配核秒为94.777778核时；实际总账仍含失败、重复、控制、cleanup与闭合成本，须守原96核时门槛。申请wall不是保证实际计费上限。Pprime2000QM仍待实际frame PASS和retention闭合；其99.5%/11.7分配核秒门槛未变。

全run实际父任务82个，点时已观测分配核时76.55555555555556；包含所有FAILED/TIMEOUT，step不重复加费，0整秒不代表真实零耗时。

D1–D7、最终common/掩码/归一化/导出、全Pprime及扩充第一批尚未完成；目标保持active。观测时间：2026-10-26T05:12:09.913513+08:00。全部输入SHA、实际scontrol/父会计和监控进程证据：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/registered_phases_actual_all_eight_20261026_v1.json。
