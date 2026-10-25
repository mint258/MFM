# 精确近邻与全池外部排序：阶段 2

本阶段新增独立实现，不改阶段 1 的已登记源与下载/筛选 pins。暂未运行真实
分子近邻成本试点，也没有生成扩充候选。所有状态均由实际 receipt 区分。

`nearest_exact.py` 使用 RDKit 2025.09.5 的 ECFP4、2048 bits、radius=2、
不含 chirality。原始立体/同位素身份仍在完整 InChIKey 中保留，不能将指纹
不含 chirality 误读为去掉分子立体信息。参考人口必须是共同人群 TRAIN/VAL，
每个分子一行；允许不同源分子有相同化学身份。结构投影、共同人群清单、
投影生成器、指纹文件、身份文件和骨架计数均有物理 SHA256。

参考文件以每条 256 bytes 的 fingerprint binary 与每条 28 bytes 的
InChIKey ASCII 保存。每个 spawn worker 只读 mmap 同一文件，每次最多解码
8,192 条参考指纹；查询分块默认 8 条，最多两倍 worker 数的块排队。16 个
worker 先经过初始化 barrier，再独立计算 query blocks。每个 query 都与全部
参考指纹逐块调用 `BulkTanimotoSimilarity`，不做近似、不采样参考库、不在
相似度为 1 时提前跳过其余参考。并列最近邻保留最早的参考 ordinal。输出
包含精确相似度和单独最近邻身份审计、真实 worker PID/计算量/耗时/峰值 RSS。

成本试点与正式候选投影使用不同 schema。`expansion_exact_query_cost_pilot_v1`
只可使用固定的 v1 结构投影、`candidate_release_authorized=false`，输出始终为
BOUNDED_COST_PILOT。这样可在扩充全部来源尚未齐备时测精确计算成本，但不能
据此发布候选。正式 query schema 要求完整、已去污染的候选池 receipt。
默认最多 512 queries、总比较次数最多 10 亿；初始建议 16 queries，实测后
再决定是否扩至 512。大于 500 核时的正式全量由 Root 根据试点审阅提交。

`external_sort.py` 用 DuckDB 的 16 个真实执行线程、显式内存与 spill 上限
处理全池。输出前必须逐身份重算排序投影的 count/SHA，并与真实 filtered
SQLite 池比对，不能把仅排好部分样本的文件当全池。默认 R 与 N 各 500 万，
首批各取 125 万；R/N 无交集，后续始终取同一冻结队列的更长前缀。

R 为种子 20261025 的 SHA256 均匀序。N 排除整个未来 R 队列后，在重原子
区间×元素组合内按新骨架、新环系、到 v1 的最近邻距离、v1 频数排序，再按
PubChem 候选自身各层人口做比例交错。整个排序投影只允许 v1/PubChem 字段，
不携带下游身份命中细节、标签或特征。

层间 finish time 为 `(2i−1)/(2n)`。外部排序用 HUGEINT 按 10^24 缩放后
取整，限定全池不超过 10 亿；不同有理数的最小差严格大于一个缩放刻度，
因此其顺序与内存 Fraction 参考实现一致，避免 float 取整导致跨层顺序漂移。
零重原子分子仍可排序；是否能生成 UFF 构象另行记录，不能在图筛选阶段暗删。

独立测试包括 bit-count Tanimoto 数值 oracle、全参考分块与最近邻 tie、
目标/下游字段防混入，以及外部 HUGEINT 排序与 Fraction 参考逐条一致。
实际测试由 Root 运行并保留日志。缺 RDKit/DuckDB 会明确 SKIP，不当作功能
通过；正式使用前必须补齐真实环境下的实际通过证据。

只运行纯代码测试的命令：

```bash
python -B -m unittest workflows.expansion.test_preparation \
  workflows.expansion.test_exact_and_external -v
```

真实成本试点先准备外部、带 SHA 的 reference/query manifests 和五分钟内的
用户 quota receipt。参数模板为 `configs/data_v1/expansion/exact_profile_v1.json`。
该模板故意不填尚未产生的实际输入 SHA，也不自动下载、提交或运行。
