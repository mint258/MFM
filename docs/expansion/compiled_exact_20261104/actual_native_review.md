# 完整 Common 参考上的新编译实现实际验证

Alpha **1885206 已 COMPLETED / 0:0**：sonmi1、16 CPU、68 秒，无 GPU、无显式 Slurm 内存请求。8 项新后端边界测试及 9 项原数学测试全部通过。Root 已独立核对实际账本、64 条测量的全部字段和 F64 位值、16 个完整参考缓存、原输入来源及构建/二进制/源码校验引用。

这是**新的编译实现**，不是原 RDKit 相似度函数的执行记录。原 Python engine、workers、cache、run 及正在运行的 1885201 均未修改。原型源文档记录源交付时状态；本页记录随后真实原生验证。正式 worker/入口接线尚未完成原生验收，不表示已启动全候选池计算。

## 精确性与范围

每个 worker 分别加载原实现和新实现的完整 **1,196,122** 条 Common 参考，保留全部原参考 ordinal 及重复指纹。实际 64 条查询与原 1885200 的身份摘要及逐条指纹 SHA 相同，没有用别的样本替换。所有八个结果字段一致，包括最早 reference ordinal、未约分的交并计数、实际评估/严格界剪枝数量、searched groups 次序，以及 score 的全部 F64 位。两类数量之和逐条覆盖全部参考；历史 200 保留的七字段也全部一致。

算法仍按精确有理上界排序 popcount 组，只在原组边界使用严格小于剪枝；上界相等仍扫描，组内无提前退出。新实现用私有连续缓冲区、整数 popcount 和融合 argmax，最后由 Python 作一次整数除法得到 score。没有参考采样、近似索引、更强剪枝、score1 提前退出或化学输入改动。原测试覆盖零分未约分值、zero/zero、相等上界、重复及最早 tie；新测试还覆盖所有 2049 个 q-popcount 顺序、全部 2048 位位置、私有副本、源文件替换和资源/ABI/pin 拒绝。

## 这组固定 64 查询的实测

| 项目 | 原实现 | 新编译实现 |
|---|---:|---:|
| 64 条配对查询累计 wall 秒 | 30.6604 | 3.7882 |
| 64 条配对查询累计 CPU 秒 | 30.3454 | 3.7439 |
| 每 worker 平均完整参考加载秒 | 9.6184 | 1.1087 |

同一配对测量的累计查询 wall 比为 **8.09**。八个 worker 先加载原实现，另八个先加载新实现；查询执行顺序也各占 32 条。两份缓存并存的单 worker RSS 约 1.02GB，全进程树实际峰值 16.20GB，低于 40GiB 软件预算。并存 RSS 不能当作新后端单独的内存占用。

这些是固定 64 条历史操作样本的实际观测，**不是全池代表性证明或完工 ETA**。1885200 原记录的整段 24 秒还包含进程启动、参考加载和 barrier，不能把它作为纯稳态查询耗时外推。正式工作量还取决于不同指纹数量；本次没有读取旧 QueryCache 来制造缓存命中的速度提升。

## 构建和采纳边界

实际构建使用 Alpha `/usr/bin/gcc` 4.8.5、C11、CPython 3.11.14 ABI；不链接 RDKit C++、Boost、NumPy C ABI 或 C++ 标准库。没有 fast-math、reciprocal 优化或 march=native。实际运行分支为 `x86_runtime_popcnt`。完整 flags、编译器、SOABI、CPU、源码及加载库校验引用见[构建 manifest](cpp206_build_manifest.json)。23,360 字节二进制 SHA256 为 `f173affaa1bd8cb876ec9156eff8f78b98892ee1c6417cc4500850808f4a3466`，二进制保留在 Alpha，未提交 Git。

[Root 实际验收](popcount_validation_1885206_root_actual_v1.json)仅允许未来在相同 Common 参考、构建、Python ABI 和已验证 CPU 分支上接线验证，要求新缓存命名空间和明确的新后端来源。原构建 manifest 保留编译完成当时的待采纳状态，后续决定由独立 Root 验收记录表达。正式 worker/入口仍需单独原生验证；原缓存复用、扩充后更大参考的内存/性能、全池时长和训练均未放行。

另已部署完整基准报告的不可变源层并验证旧 190 的两个人口元数据和原十份统计模块路径。没有读取未完成的近邻结果，也未重新统计人口。待 1885201 实际完整结束和 Root 验收后，再复用关闭统计库生成完整 2.1 报告。1000 万固定队列、实际 1 万 R/N 各半 pilot、首批 250 万 UFF/D 及最终扩充报告尚未完成。

实际证据：[生产收据](cpp206_receipt.json)、[全部配对测量](cpp206_measurements.json)、[16 worker 完整加载](cpp206_worker_readiness.json)、[新 8 项测试](cpp206_test_native_suite.json)、[原 9 项测试](cpp206_test_exact_suite.json)、[真实输入绑定](popcount_cpp_validation_v1_inputs.json)、[账本](popcount_validation_1885206_actual_accounting_v1.json)、[raw sacct](popcount_validation_1885206_actual.sacct.txt)。源码及实际引导脚本见 [bootstrap archive](../../../configs/data_v1/compiled_exact_and_baseline_actual_bootstrap_sources_20261104_v1.json)。
