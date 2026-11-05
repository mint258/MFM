# 336 试点只读闭合适配器 v1

独立新源码，不修改已登记 producer、配置、prepared、结果或 formal_v1/v2。
不开 UFF/QM/LMDB，不提交 Slurm，不产生 task/once key，不猜测物理 ID。
Root 应在336完整收尾且真实父 Slurm终态后，于 node20 小分析 allocation 执行。

## 已有收尾产物与缺口

run_pilot_live_memory_32g_v1.py 原生收尾已经写：
reproduction_manifest.json（每项 molecule_id/path/bytes/SHA）、molecules.parquet、
conformers.parquet、worker_failures.json、orders/statistics、memory_evidence，
receipt.outputs 已 pin；receipt 也有 status_counts、science_worker_seconds
和 float64 geometrySHA parquet 回读。适配器引用原 manifest，不重建/重写/复制。

Root 还需要实际 sacct父成本 schema、原 prepared/task/ref/结果之间的闭合、
cohort失败与耗时/旧行守恒/真实新增几何披露及待人工审阅的 review 草案。
适配器只补这几项，复用原 verify_readback/geometry_sha，未再实现相同科学算法。

## 输入与拒绝条件

配置 configs/data_v1/conformers/pilot_closure_v1.json 绑定原 pilot_config/
prepared SHA和实际 job4520364。receipt 必须为
PILOT_COMPLETED_REQUIRES_ROOT_REVIEW，expected/submitted/completed 全336、
never_dispatched=0、failure/resource_denial为空、monitor已关闭、
原回读PASS、无改配方/原数据/发送信号。未终态立即拒绝，不能靠 progress
或目录内已有326/335包冒充完整 closure。

所有 producer outputs/prepared outputs 的现存 bytes/SHA 重验，完整336唯一
任务与原 manifest 唯一 molecule/path 集合完全一致。并行16读闭合复现包，
核原cohort/N/源锚、geometry/atom SHA、真实old原idx/seed/坐标不变、new
候选来源/ID唯一；失败 raw候选和固定1% raw留存符合 producer字段。
检查 source P′/native anchor，不重算随机或几何排序，也不重排物理ID。
package 内连续 sprime_conf_idx 仅是科学包内部行位置；
正式身份由 formal_v2 保留旧ID/append新ID。

每个成功结果必须含全部原accepted旧引用及N条真实输出。失败结果可能在输出
旧引用前就返回，报告会分别列 original_accepted_count 与
old_references_in_package；旧baseline在原来源仍独立保留，不能把其缺少的
package引用误算为删除原构象。merged count=原baseline数+真正新增数，
旧引用不双计。科学失败（非 IMPLEMENTATION_ERROR）照实列出，不自动判Root接受。

parquet按每分子core summary及每几何 atom/geometry/source/origin/seed/oldidx/
candidate/below字段交叉对照复现包。float64SHA直接复用 producer原检查。
原monitor/RSS原始证据和统计JSON已被pin，适配器不重做同实现科学测试，
也不声称原producer提供了16个distinct workerPID实测。

## Root 实际 sacct 证据格式

Root 用自己的持久控制会话查询实际父作业并保留原始 stdout，建议列：

    sacct --jobs=4520364,4520335 --parsable2 --format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS

实际命令依现场既有可用语法，必须保留表头和管道分隔，不能 noheader；
可加额外列。此命令只示例 argv，不意味着已查询或重新提交作业。
根作业可能含失败/前处理父作业，应保留；batch/extern不重复收费。
Root 在本次真正查询完成后创建小JSON：

    {
      "schema": "DATA_V1_SACCT_QUERY_EVIDENCE_V1",
      "query_returncode": 0,
      "command_argv": ["sacct","--jobs=4520364,4520335","--parsable2",
                       "--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS"],
      "observed_at": "真实查询时间且含时区",
      "requested_parent_job_ids": ["4520364","4520335"],
      "raw_sacct_reference": {"path":".../真实sacct原始输出.txt","bytes":0,"sha256":"..."}
    }

bytes=0/省略SHA是待填示例，必须换成实际文件引用。Root 给所有本阶段已知
需要计费的父作业（包括失败）时，requested列表要与原stdout数字父行集合
一致。pilot父必须真实 COMPLETED/0:0；任一仍RUNNING/未知父不生成最终closure。
适配器输出 DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1、status
ACTUAL_PARENT_ACCOUNTING_CLOSED、query_returncode/raw_ref/parents，
再调用原正式 accounting validator核准。原stdout和query证据都只读。
该成本范围仅为输入中列明父作业，不冒称全数据线费用已闭合；
本适配器自己的新Slurm父成本由Root随后加到全局账本。

## 执行与输出

Root 在 node20 的独立16CPU分析 allocation，建议32GiB/1h；
普通全用户声明内存85%准入，不是336科学试点live-memory例外。
输出cap1GiB、剩余配额200GB；不会复制8GiB源数据。
每个解压包读上限1GiB，16读线程；过界显式拒绝后交Root，不静默截断。
REPO/PY逻辑路径和依赖用Root已核实环境，新鲜普通preflight的
source_references绑定新配置/本目录脚本/原最终receipt/实际query evidence。

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/pilot_closure_v1/close_pilot.py" \
      --config "$REPO/configs/data_v1/conformers/pilot_closure_v1.json" \
      --pilot-receipt /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_32g_v1/receipt.json \
      --sacct-evidence "$SACCT_EVIDENCE" --root-preflight "$PREFLIGHT" \
      --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_closure_v1/closed_v1

输出：

- actual_accounting.json：正式 planner直接消费的真实父成本 schema。
- cohort_report.json：cohort/prior_status/file_group 的成功失败数、worker秒、
  min/median/max、原baseline/包内旧引用/新增/低RMSD/raw留存。
- molecule_report.json：336逐分子身份、N/old/new/merged计数、耗时、原包pin。
- closure_report.json：CLOSED_EVIDENCE_REQUIRES_ROOT_REVIEW、原最终receipt/
  manifest/tasks pins、parquet核验、全部状态及实际父费用，所有授权标志false。
- root_review_draft.json：正式 schema DATA_V1_SPRIME_FULL_ROOT_REVIEW_V1，
  **status=ROOT_REVIEW_PENDING、accept_scientific_failure_disclosure=false**。

原 manifest ref直接写入草案 pilot_reproduction_manifest，原tasks ref直接
写入pilot_tasks；不生成替代 producer 结果。Root阅读真实报告后，另建新的
review decision，才能填写 PILOT_ACCEPTED_FOR_PLANNING/APPROVED及接受失败披露。
程序绝不替Root审批，草案无法通过正式 review() 闸门。
即使 Root 接受小试点，正式16CPU64GiB/14–19/普通声明内存准入仍须现场满足，
不能延用32GiB小试点例外；本closure不授予正式硬件准入。

## 新接口 fixture

Root compute20：

    "$PY" -B workflows/data_v1_final/conformers/pilot_closure_v1/test_closure.py -v

6个fixture只测新接口：336终态门、资源拒绝/实际job绑定、原始实际父行与步骤
去重、Root草案始终待审、prepared/manifest身份集合、科学失败按cohort披露。
没有新增同实现UFF/RMSD/生成测试，也没有实际跑producer或扫大源。
