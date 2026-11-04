# case18 来源覆盖更新后的实际全来源索引

Alpha 作业 **1885205 已 COMPLETED / 0:0**：sonmi1、16 CPU、144 秒，无 GPU。4 项原生测试全部通过。Root 已独立核对实际账本、关闭后的新库计数和 quick_check，以及原输入与新库的 metadata。当前验收只覆盖新全来源索引，尚无新的完整候选重筛或 R/N 放行。

## 完整身份集合守恒

| 核查项 | 实际结果 |
|---|---:|
| 原索引 excluded 完整 PK 数 | 6,324,307 |
| 新索引 excluded 完整 PK 数 | 6,324,307 |
| 原集合缺少的新 PK | 0 |
| 新集合缺少的原 PK | 0 |
| 新建图或身份行 | 0 |
| 当前 MolNet 下界约束数 | 1 |
| 当前 COCONUT 下界约束数 | 0 |

两个完整 BINARY 排序游标分别到达 EOF，逐项双向比较全部 `(kind,key,dataset)` 主键。使用长度前缀和 canonical UTF8 行计算的两个 SHA256 均为 `00cf8ebecee8a85a56e875bd85344779cf0f1516ff42808935a31325f0c659c8`。这不是只比较行数。ClinTox case00 的 binding UTF8 原字节及全部 atom 行保持一致。

原 1885187 数据库在只读事务及完整同 FD SHA 校验下备份到新私有文件。只有新副本中的 case18 约束行及其 C3 atom 行被移除；该条有限分子记录由已存在的 MolNet 精确非 H 组成 C36N11O12 覆盖，依据是[独立来源审查](../case18_source_recovery_20261104/actual_source_review.md)。原 1PTS 三个位点、graph/charge/stereo UNKNOWN、原 C3 规则和旧数据库均保留。COCONUT 仅原批准的 732 条隔离，不扩大范围。

新库为 342,609,920 字节，SHA256 `002f59435db56210ef1086896a4b723faa4ed2e8f3fde6fe48f2c95af10d4e69`。生产者核验两个关闭后的完整 FD SHA、源库前后 frame、integrity_check 及无 journal/WAL/SHM；Root 复用这些完整 SHA，随后独立只读查询确认 6,324,307 条身份、唯一保留 case00 约束、既有精确组成和 quick_check=ok。Root 未重复宣称整库 SHA 读取。

## 来源、角色与审计继承

11 来源共 15,291,170 条身份来源记录、v1 全角色及 embargo 范围保持不变；没有移除来源记录或角色。新的 source manifest 明确包含完整旧 manifest、原 187 收据、实际 577 项 EOF/SHA 消费索引，以及 case18 的新覆盖依据。577 份大来源和原 203 的 28 次来源读取是诚实继承，**本次父作业未重读这些全部大来源**；本次实际读取另有独立索引。

203 的原账本捕获未记录查询返回码，本次严格保留未知值，未补造零；其完整 raw 字节、所有父行（含 202 的 FAILED 历史）与独立 Root 来源验收匹配。187 原账本确实记录了返回码 0。两种真实格式均有严格校验及边界测试。原 V3 header、identity_keys 和过滤科学函数未改。

## 后续任务及当前限制

新的全部候选数量仍需使用原过滤函数对 109,875,599 个当前候选完整重筛。旧 1885199 的 52,859 个结果仍保留为旧策略的真实结果，不能当作新策略结果，也不能在重筛前声称获得了新的完整 R/N 池。

固定 100 万条精确近邻作业 1885201 保持原样运行。它的旧存储预算仍有效，因此新的大规模重筛写入需等待其自然闭合并重新核算所有未来空间。总 scope caps 和 200GB 账户余量不变，不因等待而重启该作业。

另新增了[全池 Alpha 启动入口](../alpha_full_pool_entry_source_v1.md)，用于兼容 launcher 的 startup-proof 参数并直接调用原全池 `run.run(plan)`。其 3 项元数据边界测试已在 Main compute-0-20 通过（0.058 秒），profile 和科学入口均用 stub；这不表示实际 Alpha Slurm/精确数学验证已经执行。没有合入 census 优化或修改现有 Guard。未来私有输出 scope 仍须独立预算验收，不能借路径变更扩大 exact 的 300GB 总预算。

1000 万固定队列、实际 1 万分子 UFF/D pilot、首批 250 万正式 UFF/D、扩充后覆盖及最终报告尚未完成。

实际证据：[Root 全来源验收](all11_case18_amended_index_1885205_root_actual_v1.json)、[原生收据](case18_amendment_1885205_receipt.json)、[完整 PK 与约束核查](case18_amendment_1885205_private_database_invariants.json)、[新来源 manifest](case18_amendment_1885205_all11_source_manifest_case18_amendment.json)、[本次实际读取](case18_amendment_1885205_actual_source_reads.json)、[原生测试](case18_amendment_1885205_source_tests.json)、[实际账本](case18_amendment_1885205_actual_accounting_v1.json)、[raw sacct](case18_amendment_1885205_actual.sacct.txt)、[Root 当前 frame/关闭库查询](case18_amendment_1885205_current_frames_v1.json)。大 SQLite 保留在 Alpha，Git 仅保存代码、证据索引与哈希。
