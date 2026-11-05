# 数据线实际进度 v5

## 目的与输入

本报告只汇总实际CPU产物和父作业会计。机器证据为`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/secondary_main_actual_progress_20261026_v5.json`，源码为本报告生成器；其中source_references保存各输入的小回执完整SHA。大数据仍在仓库外。

## 规则和参数

CPU-only、至少16CPU、SBATCH不申请内存、最长48小时、保留200GB余量；核时超标报告后继续。数据质量门槛及Se唯一元素例外保持。TRAIN拟合和ROUTINE整分子VAL保持；当前不释放最终mask、common、D4或候选池。

## 实际统计

| 实际任务 | 结果 |
|---|---|
| Main 4521316 | C0/293秒，原空间均匀10000：{'accepted': 8773, 'chemReject': 1223, 'technicalUnresolved': 4}；另独立longest16，不冒充指南的筛选后1M |
| Main 4521321 | C0/69秒，334原包与14同seed控制闭合，2个超时未决保留；未生成新UFF |
| Main 4521326 | FAILED3/123秒：实际N1母群5105；旧5040全局比较导致eligible0，不是全部baseline失败 |
| Alpha 1884772 | C0/2055秒，全部15 SQL表EOF/整源SHA，molecules 1140133，entries 1799004 |
| Alpha 1884783/1884784 | 单文件试点C0/10秒；正式C0/338秒，11官方载荷共2501171487B，逐容器完整性核验，Sider复用 |
| Alpha 1884785 | C0/222秒，标准化20000条物理记录、16个实际worker；观察{'rows_with_any_valid_full_key': 19980, 'rows_without_any_valid_full_key': 20, 'invalid_stored_key_values': 0, 'unresolved_present_variants': 23, 'missing_variants': 37, 'rows_stored_vs_computed_disagreement': 0} |
| Alpha 1884786 | FAILED1/8秒，启动guard误比较原始storage与归一化摘要，未运行fixture或读取科学body；新独立版本修复中 |

Main已记录126父、233.44444444分配核时；Alpha已记录19父、46.20888889分配核时。两端点独立，失败、超时、启动费用均纳入，batch/extern不重复相加；这不是最终总成本。

## 异常与后续

N1保留全部5105行，旧5040仅为未证常量；差65的组成待新CPU交叉聚合，不能猜作FULL/VAL/失败。新版本使用同task/seed及原once账本，不复制第二几何。P′原15协变FAIL和2000/full HOLD保持；只读诊断C0不等于科学PASS。20条无有效身份键的标准化试点行保留，不删除、不用作筛选放行。

标签281件原件继续按原清单接入Alpha；6原测试通过后同allocation校验227正文SHA，才扫描512分子/4251记录，Arrow17实际兼容性须由该运行证明。正式COCONUT全表标准化和N1校正尚待实际新作业。

## 已知限制

D1草案尚未共同冻结，D1–D7、全S′/P′、共同人群、真实导出、全部下游去污染、ordered10M与首2.5M仍有未完成项。11载荷容器完整不等于身份覆盖；COCONUT物理全表清点不等于化学标准化或去污染已完成。未开最终PR，也未开始训练或使用GPU/学校付费服务器。
