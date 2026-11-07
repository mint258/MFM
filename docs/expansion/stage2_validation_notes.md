# 阶段 2 验证与负面结果

首次真实执行位置为 compute-0-20，使用既有 chemprop 逻辑 Python 入口和
Stage61 deps overlay。全部输入是合成指纹、合成身份与临时数据库；没有读取
真实分子、下载数据或运行量化。

首次 unittest 返回 1，执行 19 次、16 个不同测试、0 SKIP。精确 Tanimoto
bit-count oracle、全参考分块、最近邻 tie、原 X 规则/同位素保留和 HUGEINT
外部排序与 Fraction 参考均通过。端到端 JSON/SQLite→Parquet 测试发现
DuckDB 1.5.6 在 COPY 内同时绑定 WHERE 阈值和目标文件名时，把数值参数
当作文件名，产生 InternalException。

已将该调用改为先用参数化 SELECT 生成 batch1 表，再仅绑定文件名 COPY。
没有更换依赖或修改排序科学规则。测试模块导入可见 TestCase 导致的 3 个
重复发现也已改为模块导入，之后应执行 16 个不同测试。

原始负面证据保留在外部：

- `artifacts/expansion/code_checks/stage2_first_failure.json`：真实退出码、计数、旧 external_sort 源码 SHA。
- `artifacts/expansion/code_checks/stage2_first_failure_tail.log`：首 9 项日志之后的完整错误、尾部测试日志及 unittest 总结；它不是伪称完整 stdout 的文件。

修复版单测可采用 `python -B -m workflows.expansion.codecheck_stage2 --tests-only`，
保存 sources_before/sources_after、tests.log 与 summary.json；默认也是只运行
合成测试。compute-0-20 没有 git，因此所需的原仓库 CLI 检查必须由 Root 在
sonmi 单独运行 `python -B tools/check_repository.py` 并保留收据。代码 runner
不会把缺 git 当成功，也不改原检查器；单测通过但静态检查未附合时明确标
`UNIT_TESTS_PASS_STATIC_CHECK_PENDING`。Root 的实际三模块测试日志和独立
静态收据共同作为提交前的验证依据。此说明不预写其最终状态。

合成验证通过也不代表真实 v1 全库指纹、512-query 成本试点、PubChem 全池
排序、UFF/D 生成或去污染已经完成。所有这些必须有单独真实输入和 receipt。
