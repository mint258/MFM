# P′ 留存输出物理核验：2026-10-28 实际结果

目的：在不新增量子化学调用的前提下，复核已留存的限定诊断和原生输出。

输入：实际 manifest `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/physical_closure_day_v1/day02_r2/manifest.json`，310774B，SHA256 `e55a9053c5f9e0037e3f96d765241e951e0538b174af3f38ee59a4c1fe15210b`；独立技术审阅 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/root_actual_pprime_physical_day_r2_technical_review_v1.json`，SHA256 `0d4c7329f050c96920d50812672a508ae13ea3cc53f487221b4b6504ce6e2451`。原输入及所有原生输出沿该闭合清单溯源。

规则：复用原读回函数、旋转/张量函数和容差；修复的只是严格输入清单漏登记任务文件及原 once 记录的问题。原读取闸门、数学、标签和质量阈值没有更改。

| 项目 | 实际结果 |
| --- | --- |
| Slurm | 4524581，COMPLETED/0:0，16CPU，121秒，1936分配核秒 |
| 作业内预检 | producer3＋resource3，全部通过 |
| 已定义向量比较 | 500项通过；其余900行属于原字段未定义，不计科学通过 |
| 留存SP张量旋转 | 100/100通过原容差 |
| 留存扰动梯度与力关系 | 100/100通过；未做能量有限差分验证 |
| 原72控制 | 原点8、张量24、同几何伴随16通过；原15项矛盾及FAILED父任务仍保留 |
| 原生证据 | 384项，12条件各32；MOPAC及梯度坐标可核，其他xTB缺独立坐标块仍UNKNOWN |
| 新QM / UFF / native初始化 / once写入 | 0 |

异常：首次只读核验4524577因输入定位清单遗漏而FAILED，34秒/544分配核秒，源码、输出和成本全部保留。修复后以新输入清单和独立输出重新核验，不重算化学标签。原SCF状态保持TRUE=1000、NULL_UNKNOWN=200，未知不改为失败或成功。

限制：这些结果支持有限留存窗口的技术闭合；官方程序的单位、符号、原点、实际输出轴和原生身份仍要综合审阅。没有据此签署D1、授权新的精度设置，或放行2000构象试点/全量。当前后台S′与标签扫描继续。
