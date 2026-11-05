# 正式 S′ 补齐批次与共同人群接口 v1（只准备）

本目录是新实现；原 S′、WP5、336 试点 prepared/config/science/32GiB
wrapper 均保持原字节。没有提交器，没有执行过全量 UFF，也没有冻结共同人群。
Root 负责实际审核、普通提交守卫、现场硬件准入、Slurm 提交及实际记账。
在仍有其他用户以 MinMemoryNode=0 申报的节点，原声明内存准入可能拒绝；
本实现不借用 336 分子试点的 32GiB/实测内存例外。

## 科学与范围

配置为 configs/data_v1/conformers/formal_v1.json。科学内核复用父目录
science.py（SHA 2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f）；
原 pilot_v1.json 只提供已冻结的化学配方，不提供正式运行授权。
完整缺口为 99,351 分子；UFF_UNSUPPORTED 保存清单并排除，其他缺口每分子
仅消费一次补齐尝试。原不足唯一数使用 10N、最多 300 候选；原技术/partial
只进行配方中一次 retry。保持原 ETKDG/UFF、固定原子图/立体/顺序核验、
0.5Å proper fixed-map RMSD、maxmin 补足及 below_dedup_threshold 标记。
已实际计算过的试点缺口成功和失败都导入一次账本，绝不因转正式再计算。

所有输出均为新路径。每次输出目录上限 8GiB，写入前核算现存文件、
本次写入和收尾预留；剩余配额至少 200GB。全局 once 账本在独立子目录，
每个 <=500 分子批次预留 2MiB 元数据空间，不删除历史锁。失败和 partial
原始候选、geometrySHA、seed、原子身份、来源和复现 JSON gzip 全部保留；
成功仍按原固定 1% 留未入选候选。已选真实几何都保留。

正式科学作业固定节点 14–19、16CPU、64GiB、普通全用户声明内存 <=85%；
不得有 memory_basis 试点规则。每批配置 8h（校验最大 48h），6h 后停止
派发，让当前分子自然完成；无信号、无 kill、无自动重试。按实际
elapsed × allocatedCPUs 超过该批试点预测 1.5 倍也停止派发并留证。
若单分子超过自然 drain 余量，Slurm 仍可能 TIMEOUT；已有 once 账本将
阻止再次科学运行，需 Root 查明真实状态，不能作为普通续批。

## 实测预算与证据 schema

只能在真实 336 试点完整结果及父 Slurm COMPLETED/0:0 闭合后 draft。
Root 提供 DATA_V1_SPRIME_FULL_ROOT_REVIEW_V1 JSON：

    {
      "schema": "DATA_V1_SPRIME_FULL_ROOT_REVIEW_V1",
      "status": "PILOT_ACCEPTED_FOR_PLANNING",
      "pilot_receipt": {"path": ".../pilot_32g_v1/receipt.json", "bytes": 0, "sha256": "..."},
      "pilot_accounting": {"path": ".../actual_accounting.json", "bytes": 0, "sha256": "..."},
      "pilot_reproduction_manifest": {"path": ".../reproduction_manifest.json", "bytes": 0, "sha256": "..."},
      "pilot_tasks": {"path": ".../prepared_v1/tasks.jsonl", "bytes": 4912072, "sha256": "d10c09845799fa1d54945e93f6b22458030d7c45303adb59305b0ef2174d8917"},
      "accept_scientific_failure_disclosure": true
    }

也接受 status=APPROVED。示例 bytes=0 是待填字段，不能作为真实证据。
receipt 必须完整 336、无资源拒绝、原 float64 SHA parquet 回读 PASS。
复现 manifest 中每一项必须有 molecule_id,path,bytes,sha256。

每个 accounting JSON 格式：

    {
      "schema": "DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1",
      "status": "ACTUAL_PARENT_ACCOUNTING_CLOSED",
      "query_returncode": 0,
      "raw_sacct_reference": {"path": ".../sacct.txt", "bytes": 0, "sha256": "..."},
      "parents": [{"job_id": "4520364", "state": "COMPLETED", "exit_code": "0:0",
                   "alloc_cpus": 16, "elapsed_raw_seconds": 0}]
    }

raw_sacct_reference 必须绑定真实原始管道分隔输出，含表头
JobIDRaw（或 JobID）|State|ExitCode|ElapsedRaw|AllocCPUS；可有额外列。
数字父 job 与 parents 一一精确核对，步骤行不重复收费。实际失败父作业
也保留；针对要接纳的试点/批次，其父必须 COMPLETED/0:0。

draft 预算用 cohort/file_group 内实测最长分子时间，缺测层用全局最长，
乘真实父分配 core-seconds/全部分子 elapsed 的开销比例，每批再加真实
固定开销。输出每层依据和 estimated_formal_core_hours；这是可审的保守
预测，不是实际全量费用。它没有凭空给出固定 core-hour 数。
Root cap 应为 pilot+正式批次+前处理/失败父作业留余量，估计或最终实际
超过 500 coreh 必须 approved_over_500_core_hours=true。

freeze 另需 Root 审阅实际 draft 后创建 SPRIME_FORMAL_PLAN_ROOT_APPROVAL_V1：

    {
      "schema": "SPRIME_FORMAL_PLAN_ROOT_APPROVAL_V1",
      "status": "APPROVED",
      "draft_reference": {"path": ".../draft/draft.json", "bytes": 0, "sha256": "..."},
      "approved_total_core_hours_cap": 0,
      "approved_over_500_core_hours": false
    }

cap 必须有限且足够，不能照抄 0。freeze 只产
FULL_SPRIME_PLAN_FROZEN，scientific_execution_completed=false；
它绝非 common 已冻。Root 的 source_references 应绑定所有本目录脚本、
配置、审核 JSON、prepared/plan/task 小引用；大源通过配置内小 authority
receipt/manifest 绑定，禁止登录 guard 扫 GiB。正式准备在 node20 核源身份；
共同人群最终分析才在 node20 对旧 S′ 五个大 conformer 文件做全 SHA。

## 精确 argv 模板

以下变量值均为 Linux 绝对路径。Root 先 cherry-pick，再在自己的
sbatch 中设置代码版本、解释器逻辑路径和已核对依赖环境。
PY 应使用 Root 已核实的 chemprop Python 逻辑路径，不能 realpath 改环境。
每一项都由 Root 独立 16CPU Slurm 提交，参数中的 PREFLIGHT 是该项
新鲜的普通 submit_reviewed.py intent/receipt，不共用旧 11:47 快照。

    REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
    MOD=$REPO/workflows/data_v1_final/conformers/formal_v1
    CFG=$REPO/configs/data_v1/conformers/formal_v1.json
    OUT=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/formal_v1

node20，16CPU64GiB，建议首次 draft 1h / 8GiB cap：

    "$PY" "$MOD/plan_batches.py" draft --config "$CFG" --root-preflight "$PREFLIGHT" --pilot-review "$PILOT_REVIEW" --output "$OUT/draft_v1"

Root 看完 draft 与实际总预算后写 FULL_REVIEW。node20，16CPU64GiB，1h：

    "$PY" "$MOD/plan_batches.py" freeze --config "$CFG" --root-preflight "$PREFLIGHT" --draft "$OUT/draft_v1/draft.json" --full-review "$FULL_REVIEW" --output "$OUT/plan_v1"

node20，16CPU64GiB，建议单批准备 1h / 8GiB cap：

    "$PY" "$MOD/materialize_batch.py" --config "$CFG" --plan "$OUT/plan_v1/plan.json" --batch-id batch-00000 --root-preflight "$PREFLIGHT" --output "$OUT/prepared/batch-00000"

节点14–19，16CPU64GiB，8h / 8GiB cap，普通声明内存准入：

    "$PY" "$MOD/run_batch.py" --config "$CFG" --prepared "$OUT/prepared/batch-00000/prepared.json" --root-preflight "$PREFLIGHT" --output "$OUT/batches/batch-00000"

自然墙钟 partial 续批仅接受 receipt.status=FORMAL_BATCH_PARTIAL_UNSTARTED_ONLY、
stop_reason=WALL_DISPATCH_CUTOFF、无 error/unknown、实际父 C0、未开始的 once
键不存在。node20：

    "$PY" "$MOD/plan_batches.py" continuation --config "$CFG" --root-preflight "$PREFLIGHT" --batch-receipt "$OUT/batches/batch-00000/receipt.json" --accounting "$BATCH_ACCOUNTING" --output "$OUT/continuation_draft_00000"

新 draft 仍需新的 FULL_REVIEW 和 freeze；不重投原 job、不重跑当前分子。
其他失败、未知提交、成本超阈值均停给 Root，不自动续批。

## 共同人群冻结与 SB1/SB3 接口

Root 创建小 completion-index JSON 后在 node20 16CPU64GiB、建议首跑 8h：

    {
      "status": "ALL_SPRIME_ATTEMPTS_TERMINAL",
      "root_plan": {"path": ".../plan_v1/plan.json", "bytes": 0, "sha256": "..."},
      "batch_closures": [{
        "receipt": {"path": ".../batches/batch-00000/receipt.json", "bytes": 0, "sha256": "..."},
        "accounting": {"path": ".../accounting.json", "bytes": 0, "sha256": "..."}
      }],
      "additional_accounting": []
    }

additional_accounting 是已闭合的准备/分析/失败父账单引用；应纳入本阶段
完整成本。各 job 去重收费；最终与 Root cap 再核。管线其他阶段费用仍以
Root 全局账本为准。每个 batch 必须源/配方一致、真实回读 PASS、实际 C0、
费用未过 1.5 倍。续批 plan 必须沿 parent_plan 回溯至 root_plan。
所有 90,069 个非 unsupported 原缺口必须各有一个终态包，试点本身永不够。

    "$PY" "$MOD/finalize_common.py" --config "$CFG" --completion-index "$COMPLETION_INDEX" --root-preflight "$PREFLIGHT" --output "$OUT/common_v1"

母数固定原 TRAIN+ROUTINE 整分子 VAL=1,214,218，剩余 FULL 不入 common。
PM7 完整是原几何记录全覆盖和已审计原子身份，不是全部 P 任务成功；
失效标签只能 mask。unsupported 排除，补齐仍不足 N 的分子才因 UFF 不足排除。
总排除 >2% 或任一非 Se 元素排除 >20% 保存 exclusion_evidence.json，
写 COMMON_POPULATION_V1_NOT_FROZEN_STOP_THRESHOLD 并退出2。
Se 的唯一例外仍有独立计数证据。成功写：

- manifest.status/schema=COMMON_POPULATION_V1_FROZEN，roles_manifest_sha256、
  membership_tables（16 parquet 的 path/bytes/sha256），physical_geometry_tables
  （PM7 16片、UFF 16片），size/element_set/scaffold 比较和元素 presence 闸门。
- membership 全原 authority 唯一 molecule_id；common_population:bool
  （同值 common_population_v1），source_role、effective_role（同值 new_role）、
  legacy_routine_molecule、expected_conformers、pm7_records、
  uff_usable_conformers、exclusion_reasons、generic_scaffold、scaffold_status。
  FULL 行保留审计且 common=false；消费方必须按 bool 筛选。
- PM7 物理表：molecule_id,native_record_id,geometry_source='pm7',
  geometry_id='pm7:'+sha256(native_record_id),source_path,real_index,
  native_lmdb_key（至少9位十进制，不截断）,record_payload_sha256，
  source_format='native_lmdb'、source_role/effective_role、
  legacy_routine_member（原 ROUTINE record membership，独立于整分子 VAL）。
  source_path 若相对，基于 manifest.native_source_project_root。
- UFF 物理表：molecule_id,sprime_conf_idx（新 canonical 非负整数）,
  geometry_source='uff_sprime',geometry_id='uff_sprime:'+sha256(mid+':'+idx),
  source_path/source_sha256/source_bytes/source_row_index/source_format/source_member,
  native_anchor_record_id,atom_order_sha256,uff_energy_kcal_mol,
  original_sprime_conf_idx,candidate_id,seed,below_dedup_threshold,origin,
  geometry_sha256,source_role/effective_role/legacy_routine_molecule。

UFF 原有 key 仍为 (molecule_id,original_sprime_conf_idx)。先按原 idx 排序严格
SUCCESS&&converged 的旧行，给予连续 canonical sprime_conf_idx；新增候选接后。
原旧 idx 显式保留，不能把 canonical idx 误当原 parquet key。
旧来源 source_format=parquet，source_row_index 是**过滤前原物理行号**；
geometry_sha256=NULL 明确表示沿原大文件 SHA 认证、没有假称逐几何新观测。
新增来源 source_format=reproduction_json_gz，source_member='conformers'，
source_row_index 指已 pin gzip 解码后该数组原位置，完整坐标/原子序/geometrySHA
在该数组内；source_sha256 绑定 gzip 文件本身，不是未压缩字节。
接受的旧构象在新包内仅作坐标守恒核验，不加两次数、不复制到新构象。

所有物理表仅含 common=true 分子。完整基线原始坐标不复制。
最终 manifest 显式 orders_frozen=false,order_manifest=null,
geometry_map_frozen_by_this_manifest=false。SB1 独立生产
CANONICAL_GEOMETRY_MAP_V1_FROZEN 和 order_manifest；不可把 common 冻结冒充
三种顺序/全部几何映射已冻。后续 order 长表统一
(molecule_id,geometry_source,order_type,rank,geometry_id)，order_type 为
fixed_random|energy|diversity，rank 从0，random seed20261025，使用父
selection.stable_key 相同身份。PM7 HOF 必须来自 canonical registry60，
不从 LMDB energy_raw 代替。当前 profile 不是全共同人群统计。

N=1 不排除 common、不改 N/原 S′ count、不复制构象；写 pprime_n1_pending.parquet
和 PENDING_N1_POLICY，P′每mol2条件仍未满足。第二真实候选另走独立 proposal、
Root 审阅后才可生成，其来源和顺序必须显式接入。

## 验证

静态检查（可在 login；AST/源码 manifest，不运行科学）：

    cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/sb2
    python tools/check_repository.py --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sb2_formal_static_check_v1.json

Root 在 compute20 已核 chemprop/依赖环境运行 15 个合成 fixture：

    "$PY" -B workflows/data_v1_final/conformers/formal_v1/test_formal.py -v

定向生命周期及阈值：

    "$PY" -B workflows/data_v1_final/conformers/formal_v1/test_formal.py LifecycleTests -v
    "$PY" -B workflows/data_v1_final/conformers/formal_v1/test_formal.py CommonTests -v

覆盖 once 独占与 PID/startticks、32G正式拒绝、500h与NaN预算、真实原始
accounting对照/步骤去重、分片无漏、N1保留、P失效不删几何、FULL排除、
2%精确边界/Se唯一例外、旧行不双计、新候选重复拒绝、
below-threshold真实不同candidate身份、原 parquet 物理行定位。
这些测试没有 UFF/LMDB/sbatch 或大源扫描；不能代替正式实测验收。
