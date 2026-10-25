# 数据线与模型线接口状态

更新：2026-10-25 15:20 +08:00。分支 data-v1。实际执行源码和GitHub发布提交分开登记，公开草案不代表数据验收。

- 用户仅批准Se单元素排除>20%例外，继续排除UFF_UNSUPPORTED；其他停止阈值不变。VAL为既有ROUTINE分子：实际job4520334闭合，VAL7,610分子/72,525完整PM7记录，旧ROUTINE11,322记录另标记。TRAIN1,206,608分子/11,104,772记录保持。
- D-1为[契约draft.3](training_format_v3.md)，补充物理target分组、二阶tensor、Pprime继承P、exposure masks及已冻角色。候选MFM3/分家族LMDB/mask库有实际8测试及16spawn/32读回/全部退出证据。参见[接口交叉审阅](model_contract_review_20261025.md)；模型线意见仍待接收，未共同定为v3.0。
- D-2注册表仍为草案：146 enabled统计分量、63源字段对应103个N/A分量、10常量分量删除、5legacyESP另列。146不是head数量。最终family/size-rho、物理范围、vector/tensor实际参考系仍有待闭合项。
- 标签canonical40-record I/O真实job4520344已闭合，新增mask0；新的compact streaming实现避免复制正常原值，实际19语义测试job4520361 COMPLETED0/14s。512完整分子/4251记录/16来源组metadata job4520370实际COMPLETED0/8s且18输出SHA匹配；Arrow16进程资源probe4520373通过，真实profile job4520374实际COMPLETED0/34s、16真实workers，reducer4520380实际COMPLETED0/3s、146字段newmask率全0。精确median/MAD逐轮source读取继续，未运行full；详见[compact实际报告](../data_v1/compact_label_profile_actual_v1.md)。normalization_v1新增实际24fixture/16spawn PASS（4520382/2s），不是最终D4。最终D4仍等待common/diagnostic冻结与实际重建，当前TRAIN校准不能冒充它。
- 用户回复允许小规模测试降低资源使用、正式生成仍使用原硬件要求。336分子S′试点改用16CPU/32GiB/4h，仅本次按实测内存监控；job4520364已提交且启动于compute-0-17。32项边界/幂等/失败落盘测试实际PASS，1s监控、24GiB自身RSS派发停止、保留完整32GiB节点余量；紧张时只停新派发并自然drain。原科学源、配方、prepared均未改，正式批次不沿用这次调整。
- Pprime输入准备job4520345闭合：1000分子/2000UFF构象、20审计记录；量化尚未开始。受控vector/tensor审计输入准备请求已备，真实frame验收未完成。
- PubChem官方raw job4520348已COMPLETED0/282s，1,488,715,010B，整体SHA与gzip CRC/EOF通过，16个真实range worker。见[实际获取报告](../expansion/pubchem_raw_actual_v1.md)。没有扩充UFF/QM或训练。
- 首个X原始输入试点job4520357保留FAILED1/43s：8741分层记录的入选决定一致，335条X01缓存flag差异触发严格重放检查暂停。只读诊断job4520359已COMPLETED0/3s，确认335条均为unassigned解析失败、旧缓存coalesce未知→false；新6项针对性测试已通过，隔离v2真实复验job4520376实际COMPLETED0/63s，8741条各规则层未解释差异0，决定不变；见[修复实际报告](../expansion/x_rule_repaired_pilot_actual_v2.md)。全量源回放尚未完成，不改变原数据或筛选规则。原STOP结果和完整差异保留。全部下游全部划分去污染仍PENDING。
- D-3/D-4/D-5/D-6/D-7最终真实交付尚未完成。D7只读profile实际准备job4520383已提交（256完整分子、至多16owner jobs），不做构象生成，既有已完成S/WP5流程未重启。每个实际任务的父作业成本含失败单独登记。

不可变用户决定：configs/data_v1/run_decisions_v2.json（Se/ROUTINE）及run_decisions_v3.json（小试点资源范围）。实际阶段凭外部receipt、原数据SHA和源文件SHA，不用源码或合成测试代替科学验收。
