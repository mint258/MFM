# 全源身份与原始文件盘点：初稿静态审查

目的：在登记运行前核对新源码、角色口径和输出边界。初稿保留，当前不准其科学执行。

输入：集成清单/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/integrate_sb5_full_sources_v1.json；全部15个源码/文档的path、bytes、SHA见/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/full_sources_static_review_20261026_v1.json。14个Python源码AST通过；未实际运行fixture或科学数据。

原coverage代码中的成员计数常量为{'TRAIN': 11104772, 'VAL': 11322, 'FULL': 115760, 'EMBARGO': 4900}，这些值没有由547读取成员布尔值证实，也不代表本轮整分子VAL。已冻结的VAL仍为7610分子、72525记录。

官方gzip生产回执实测解压正文8880849781字节。初稿按原字节TSV盘点，不添加重复文本列；但元数据总量的独立硬界仍需新版本闭合。

1. Old identity projection uses per-record member_routine; it must not be presented as new whole-molecule frozen training VAL. New source-role variant will retain original membership booleans and explicitly not apply effective training roles. All-source identity union remains required.
2. Inventory v1 retains original TSV bytes once without extra text columns, but per-part/final JSON metadata lacks a separately proven bound. New indexed variant must bound metadata and all temporary/failed output inside10GiB before registration.
3. SB5 startup requires top-level memory_basis. New queue_v3 proof adds only this redundant tag from actual strict admission before writing ready; inverse bytes/AST equivalence is separately recorded. Frozen queue_v1 and old jobs unchanged.

规则与限制：只审查小源码和已有回执；不读原LMDB、标签Parquet或原始gzip正文，不触旧池。后续采用明确SOURCE_*成员角色和有界JSONL分片索引，待Root审查及真实检查后再登记。当前不是全来源去污染完成、筛选放行或任何训练交付。

脚本：workflows/expansion/review_full_sources_v1.py。报告证据：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/full_sources_static_review_20261026_v1.json。
