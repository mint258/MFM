# 原规则回放修复：实际试点复验

job4520376在compute-0-20、16CPU/32GiB实际COMPLETED0，63s、1,008分配核秒。8,741条原分层记录的native/raw/enriched/metadata比较均无未解释差异；入选、最终和portable决定不变。状态PILOT_RULE_REPLAY_CLOSED，不是全量验收。

首试job4520357的335条X01缓存差异来自旧unassigned解析失败分支：旧enrichment无条件coalesce NULL→false，初版回放遗漏该分支。只读诊断job4520359从原始源投影了全部335条，并绑定历史enrichment源码及真实作业依据。隔离v2恢复原始层／enrichment层区别，修正cohort与原335 ID对称差为0；没有修改原数据、阈值或过滤决定。

原FAILED1试点、全部差异与源SHA保留，修复不抹去负面结果。6项针对性合成测试实际通过；首轮1项details计数字段错误及其失败日志也保留。

全15,879,477条原始人口回放尚未执行。common_population尚未冻结，全部下游全部划分去污染仍PENDING。官方PubChem raw已获取不代表已筛选；不据本试点启动正式扩充UFF。

外部证据相对run根：`control/x_replay_v2_actual_closure_v1.json`、`artifacts/expansion/regression/pilot_v2/receipt.json`、`artifacts/expansion/regression/pilot_v1/`、`artifacts/expansion/regression/stop_diagnosis_v1/`。源实现为独立`workflows/expansion/regression_x_v2.py`，原v1保持字节。
