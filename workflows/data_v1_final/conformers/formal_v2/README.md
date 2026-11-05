# S′物理身份保持的 common finalizer v2

这是独立新入口，复制并修正 formal_v1/finalize_common.py 的身份物化部分。
原 v1 SHA=9df88518e58bbf50b15f3477497129b334c64778c39b5aaeb8cc47501a22949c，
保持原字节。正式批次、科学内核、共同人群/N 定义和排除闸门不变；
没有生成/优化构象，没有提交作业，没有将任何 common/order 标为已冻结。

## 原索引来源及问题

原源 runs/sprime_s_convergence_20261013/scripts/sprime_v6.py，
SHA d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3：

- 229–239：优化 ETKDG candidate cid 并存 candidates tuple。
- 242–246：按 energy/cid 排序与0.5Å去重，得到 selected。
- 248–251：对 selected enumerate，写 sprime_conf_idx=index；
  不收敛结果也写行，converged=false/status=UFF_NOT_CONVERGED。
- 283：按 molecule_id,sprime_conf_idx 排序输出。
- 288–291：坐标float64；空表显式 sprime_conf_idx:int64。

所以 sprime_conf_idx 是**原选中结果的物理索引**，不是原 ETKDG cid。
严格 SUCCESS&&converged 筛选可能留下 gapped IDs；旧未收敛行占过的 ID
也是历史范围，不能给新候选再用。原 cid 没有作为物理 ID 输出，
不能从 sprime_conf_idx 反推 cid。

v1 把 accepted 旧行改成连续 rank，可能改变固定随机次序，
进而改变 pprime:{mid}:{idx} 及扰动 seed。因此 v1 不适合拿来保证旧 P′复用。
v2 保持旧 ID 原值；science.process_task 包内连续索引仅保留为
kernel_sprime_conf_idx 诊断，不用于物理 ID、random identity 或 perturb ID。

实际五个旧 parquet footer 用 probe_source_schema_v2.py 仅读元数据核验
sprime_conf_idx:int64；不扫描数据页、不重 hash 15GB。这只是 schema 观测，
不冒称已经获得全人群 index range 统计。最终正式 node20 分析仍按旧
manifest 全 SHA 核验后，读标量列取得所有行的实际范围/重复/非负检查。

## 新身份规则

accepted 旧行：

    physical sprime_conf_idx = canonical_sprime_conf_idx = original_sprime_conf_idx
    identity_namespace = accepted_original_sprime
    source_conformer_id = original_sprime_conf_idx

对每个 molecule 的新 generated，按 (实际 task_key,seed,candidate_id)
稳定排序。追加起点：

    max(original_PM7_N, max(sprime_conf_idx of ALL original rows)+1)

ALL 包括失败/未收敛行。没有原行时下界是原 N。新增 ID 为起点加稳定顺序
rank，统一非负 int64；检查溢出与重复。这样保留原 N 以内未使用的历史空间，
也不会占用任何已有失败行 ID。物理 ID 允许 gaps；连续0-based只用于 order rank。
新增 raw identity 为 {namespace:data_v1_fill,task_key,seed,candidate_id}。

task_key 不由 molecule_id 猜测：正式新包读取 formal_start 并与实际
SPRIME_ONCE_ATTEMPT_STARTED_V1 文件逐字段相等；导入336试点读取冻结的
pilot_imports 对应行，再核真实 SPRIME_PILOT_ATTEMPT_IMPORTED_V1 文件及包 ref。
身份表记录账本 path/bytes/SHA。缺失、冲突、重复、未知启动立即拒绝。
N1 P′第二候选提案不归 data_v1_fill，也不混入本 v2 统计。

旧 accepted 在新复现包内仍只作逐坐标/原子/来源守恒核验，不双计。
package 原行位置与 seed/candidate_id 不重写；source_row_index 继续指向
pin 的原 parquet 行或 gzip 解码后 conformers 数组的实际位置。

## 随机/P′兼容与冻结接口

根 manifest 仍为 COMMON_POPULATION_V1_FROZEN，并新增：

- finalizer_variant='formal_v2_preserved_physical_ids'
- random_identity_basis='canonical_sprime_conf_idx'，明确 canonical 在本变体
  指保存原 ID/新 append ID，不指 dense rank。
- random_order_algorithm=原 selection.py 的 path/bytes/SHA；
  SHA 41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb。
- identity_algorithm=identity_v2.py 的 path/bytes/SHA；
  canonical_sprime_conf_idx_policy、raw namespace 字段定义和 reuse_rule。
- uff_identity_tables：16个 metadata parquet pins。

物理 UFF 表和 identity 表增加 canonical_sprime_conf_idx、
kernel_sprime_conf_idx、identity_namespace、source_conformer_id、
task_key、once_ledger_path/bytes/sha256、source_attempt_max_sprime_conf_idx、
original_N；保留 original_sprime_conf_idx、seed/candidate_id、source ref、
geometrySHA、opaque geometry_id 和前版全部几何来源字段。
accepted old 的 geometry_id='uff_sprime:'+sha256(mid+':'+原idx)，新 append
使用新 append idx，避免 ID 碰撞。source_record_id/native_anchor_record_id
仍是独立原 LMDB 锚，不参与 UFF物理/random身份。

固定随机与 SB4 已核字节定义一致：

    SHA256(UTF8 f'data-v1-conformer-order:20261025:{mid}:uff_sprime:{idx}')
    sort by (hash,str(idx))

SB4 旧 common.py SHA
4001d905b2b9fcb253fabf5a4d5e72f18cd445277b628ec65319399d126057ad。
P′ record_id=f'pprime:{mid}:{idx}'；旧扰动seed20261010，实际 seed =
1 + int(SHA256(f'20261010|{record_id}').hexdigest()[:16],16) % 2147483646。
因此复用必须同 frozen physical ID、坐标和完整扰动科学输入；单看坐标相等不够。

没有新增几何的完整旧分子，其固定 random 前2/perturb record ID 保持。
原缺口分子补入新候选后，固定排序须对新集合重新计算；新增 hash 可能排在旧行
之前，不能承诺这类分子的旧前2不变。旧 P′345 source 前2来自已闭合 pairs，
新正式 P′只能在冻结 order/map 逐项一致后复用，不能按本文件的样例猜全体。
SB4 小证据：

    artifacts/pprime/prepared_v1/prepared.json
    4012B SHA3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca
    control/pprime_preparation_actual_closure_v1.json
    1627B SHA29c4787a57d10180837116f178dacf160be64610d7bba37ed716764aab18b2d4

实际例 molecule_01200493 原 idx2,6；molecule_01201800 原 idx2,9。
本 v2 不改 source_shard_id/legacy_engine_file_group；原11个 LMDB shard ID
与旧科学分组1–5是不同身份，不得互换。

v2 仍只冻结 common/物理表，不产生三 order：
orders_frozen=false、order_manifest=null；SB1/SB4 后续从冻结物理 ID 计算
fixed_random|energy|diversity，只有 order rank 连续。不得消费复现包内基于
kernel rank 的 orders 字段作为正式 order authority。

## 消费者检查及界限

只读定位当前 Root 仓库（本轮源码，不声称未来版本）：

- export/pipeline_v1/materialize.py:66–73 仅要求 UFF idx 为非负 int；
  :126 为 (molecule_id,sprime_conf_idx) 唯一索引；
  :132 连续性约束针对 orders.rank。没有发现物理 idx dense 假设。
- export/pipeline_v1/export.py:38–47 按 molecule+idx 等值查映射，支持 gaps。
- pprime/common.py:91–101 仅唯一、严格可用、hash排序取2，支持 gaps。
- pprime/engine_adapter.py:24 将物理 idx 转 int，不按 idx 建长度为N的数组。
- pprime/export_families.py:31 旧输出 schema 使用 int32，窄于本 v2 int64。
  当前未全扫范围，不能凭经验宣称全体不会越界；正式消费者应改新 variant
  的 int64 或在写前显式范围检查。没有改旧已登记源。

## argv/资源/测试

Root 沿 formal_v1/README.md 的真实完整 accounting/completion-index 交接。
配置继续用已 pin formal_v1.json（不改变科学/角色/配额规则）。
Root 新普通 preflight.source_references 加入本目录所有源码和配置/闭合证据。
node20 16CPU64GiB、普通声明内存85%、8GiB写前 cap、建议8h：

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/formal_v2/finalize_common_v2.py" \
      --config "$REPO/configs/data_v1/conformers/formal_v1.json" \
      --completion-index "$COMPLETION_INDEX" --root-preflight "$PREFLIGHT" \
      --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/formal_v1/common_v2

原正式90,069非unsupported缺口全终态、真实父C0、2%/20%仅Se例外、
N=1留common/P′pending、原TRAIN+ROUTINE VAL母数均按v1保持。

Root node20 有界元数据观测：

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/formal_v2/probe_source_schema_v2.py" \
      --manifest /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/dataset/manifest.json \
      --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sb2_sprime_footer_schema_v2.json

Root node20 9个 fixture：

    "$PY" -B workflows/data_v1_final/conformers/formal_v2/test_identity_v2.py -v

覆盖旧 gapped IDs、跳过全部失败范围及N下界、来源稳定分配、旧完整随机前2/
perturb record ID、拒绝推测taskkey/重复/溢出、算法SHA契约、真实import账本绑定、
physical gaps与dense order rank、生产v2标量SQL在3行parquet的物理行/旧ID保存。
无 UFF/LMDB/提交或大数据扫描。v1 的15个 fixture 仍独立保留。
