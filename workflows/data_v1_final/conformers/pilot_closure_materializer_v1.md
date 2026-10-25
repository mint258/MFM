# Root 只读闭合任务 metadata materializer

pilot_closure_materializer_v1.py 只用 Python 标准库，仅读 <=2MiB 单文件元数据，
生成 LF sbatch、request.proposed.json 和 materialization.json。没有 subprocess、
SSH、sbatch、srun、科学模块 import、重试或数据页扫描。仅 Root 手工调用；
默认 request.root_review=ROOT_REVIEW_PENDING，现有提交器会拒绝这种待审 request。
Root 可在阅读本脚本/实际bundle后另写批准文件再用新bundle物化，或自行生成
经审阅的新request；本工具绝不自动提交或赋予自己Root批准。

## 资源与入口

Root可在登录节点运行此纯metadata脚本（不运行计算主体），也可用compute20
现有小allocation；仅默认服务器 UID1278/sonmi或compute20。
repository 参数只接受本轮 repository 或 worktrees/sb2。PY 使用既有逻辑入口，
不 realpath；脚本环境沿原已核 chemprop及scan_v2/deps，未在metadata进程中
导入/猜测 numpy/pyarrow版本。

    BASE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
    REPO=$BASE/worktrees/sb2
    PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
    MAT=$REPO/workflows/data_v1_final/conformers/pilot_closure_materializer_v1.py

独立6fixture：node20、kind=analysis、16CPU、8GiB、10min、64MiB峰值输出。
不读实际336/大数据；不是16个distinct科学worker实测声明。

    "$PY" -B "$MAT" --mode fixtures --repository "$REPO" \
      --job-name dv1_sb2_closure_fixtures_v1 \
      --bundle-output "$BASE/control/materialized/sb2_closure_fixtures_v1"

产出的 sbatch 仅执行 test_closure.py -v。既有请求/intent/receipt/verification
同名即拒绝，bundle必须全新，全部write exclusive，不覆盖、不自动换名重投。

实际336闭合：node20、kind=analysis、16CPU、32GiB、1h，
应用输出cap1GiB、总声明输出1GiB+64MiB收尾/日志余量、配额余量200GB。
普通全用户声明内存85%准入，不用32GiB科学试点的live-memory例外。
**只能在真实336最终receipt和Root新raw sacct query evidence都到齐后手工调用：**

    "$PY" -B "$MAT" --mode closure --repository "$REPO" \
      --job-name dv1_sb2_closure_actual_v1 \
      --pilot-receipt "$BASE/artifacts/conformers/pilot_32g_v1/receipt.json" \
      --sacct-evidence "$ROOT_ACTUAL_SACCT_QUERY_EVIDENCE" \
      --application-output "$BASE/artifacts/conformers/pilot_closure_v1/closed_v1" \
      --bundle-output "$BASE/control/materialized/sb2_closure_actual_v1"

metadata阶段就要求 receipt完整336、无failure/resource_denial、原回读PASS、
原job/config/prepared对应，并用Root真实query evidence中的raw父行核
4520364 COMPLETED/0:0。query有时区且1h内，父集合全部terminal且精确对应
requested_parent_job_ids，失败父保留，步骤不重复收费。不会从运行中的progress
造最终request，不会等待/轮询/查询sacct或自动启动实际闭合。
schema详情见 pilot_closure_v1/README.md。闭合应用输出仍只为
CLOSED_EVIDENCE_REQUIRES_ROOT_REVIEW，不能授权正式planning/full。

Root审核后如要把真实批准一并绑定，可加 --root-review "$ROOT_REVIEW"；
批准文件必须由Root另行创建，不是本工具输出：

    {
      "schema": "DATA_V1_SB2_CLOSURE_REQUEST_ROOT_REVIEW_V1",
      "status": "APPROVED",
      "reviewer": "root",
      "mode": "fixtures",
      "job_name": "dv1_sb2_closure_fixtures_v1",
      "repository": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/sb2",
      "scope": "Root实际阅读后的限定范围与依据"
    }

closure mode/jobname/repository相应精确匹配。真实批准文件纳入source pins。
此批准只限这项analysis request，不是PILOT_ACCEPTED/FULL/UFF/QM批准。
输出bundle仍只物化，只有Root之后调用既有
execution/submit_reviewed.py 才可能提交；现场CPU/全用户内存/配额/锁/幂等/
真实jobID先落盘/未知不重投完全沿原提交器，不在此重复实现。

## 精确Git stage清单

formal_v2 独立5文件（保持其已核源码字节）：

    workflows/data_v1_final/conformers/formal_v2/README.md
    workflows/data_v1_final/conformers/formal_v2/finalize_common_v2.py
    workflows/data_v1_final/conformers/formal_v2/identity_v2.py
    workflows/data_v1_final/conformers/formal_v2/probe_source_schema_v2.py
    workflows/data_v1_final/conformers/formal_v2/test_identity_v2.py

pilot_closure_v1 独立4文件：

    configs/data_v1/conformers/pilot_closure_v1.json
    workflows/data_v1_final/conformers/pilot_closure_v1/README.md
    workflows/data_v1_final/conformers/pilot_closure_v1/close_pilot.py
    workflows/data_v1_final/conformers/pilot_closure_v1/test_closure.py

本次metadata materializer另外2文件（不要与上述4文件混报）：

    workflows/data_v1_final/conformers/pilot_closure_materializer_v1.py
    workflows/data_v1_final/conformers/pilot_closure_materializer_v1.md

未修改原formal_v1、旧science、原pilot或已登记新旧配置/prepared/receipt。
Root代tools/check_repository.py、6fixtures、Git stage/commit/merge；本agent不新SSH。

## 依赖pins

每次materialization.json/source_pins都记录**现场实际**path/bytes/完整SHA，
request.source_references与之相同，script自身单列pin。固定校验：

- execution/submit_reviewed.py：
  6d1e3f5623bcdf04351d50710ccc81b5ca50f23d3b19051cba29f6fee173ee7f
  （始终绑定Root canonical repository；sb2隔离worktree不含这个共享提交器）
- conformers/common.py：
  ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b

两mode还绑定 formal_v1/full_common.py、close_pilot.py、test_closure.py、
pilot_closure_v1.json 和本materializer源码。实际closure另绑定 run_pilot.py、
原最终receipt、Root实际query evidence/raw stdout、producer原manifest JSON、
原pilot config及prepared小authority。fixture不读这些实际大数据。
小authority内的 parquet/gzip/tasks 引用只交compute20 closure应用核验；
metadata materializer不打开它们，不让登录guard读GiB文件。

源配方 config/pilot_v1.json：
cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a；
prepared54827B：
74b1cda893683e070097d1784b557c6600cdf088a77a077f3026ab9d34b72d34。
新的源码SHA以现场pin为准，不在生成器里猜尚未commit的Git SHA。
formal_v2/random算法仍独立固定 selection.py：
41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb；
fixture/closure任务本身不需要导入identity_v2、RDKit或科学生成器。

本次静态元数据观测的依赖pins（文件名相对本轮sb2 worktree；未执行）：

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| formal_v1/full_common.py | 9523 | 7c4aac1f010898efaa6229216c3d0de34b208d8008bd319b4175b2dacb2619c7 |
| pilot_closure_v1/close_pilot.py | 19770 | e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f |
| pilot_closure_v1/test_closure.py | 3631 | 4b2817d082fc7831f618d74dfec3ad01f3a6c2f202ee900256f425bf3901b60f |
| configs/data_v1/conformers/pilot_closure_v1.json | 946 | d68f0ca9bfbe851d5331ab8f6e0950201a4486c85ed55cd193aa1acbb7d144d5 |
| conformers/run_pilot.py | 11440 | f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f |

前3项默认前缀为 workflows/data_v1_final/conformers/。实际materialization仍
重新按当前原字节记录pins，Root guard会在提交前再次核验；本文不是运行收据。
