# WP5 第6步验收接口（准备完成，尚未执行）

所有文件位于本轮新根；原始数据、历史源码、永久 Parquet/归档不修改、不删除。执行及 Slurm 提交均由 Root 统一负责。G5 历史 raw 缺口使用用户已批准的独立例外；该例外不免除新结果、随机200或科学差异的验收。

## 顺序及接口

1. `wp5_acceptance_catalog.py --queue <正式queue.sqlite> --plan <最终node authority tasks.json> --jobmap <最终actual jobmap.json> --runtime <正式runtime> --out <新目录>`。
   默认正式人口为 population/formal_record_index.parquet，11,231,854记录 /1,220,466分子 /134,782,248 record×12。queue latest owner + context.attempt/job/task +已发布 archive 指针决定最终 attempt；原 attempt0/1全部保留。输出 catalog.json、latest_molecules.parquet、latest_record_tasks.parquet、missing_record_index.parquet。检查任务名、ID、文件组、物理重复/缺失、全人口及每个任务分母。正式 plan SHA 必须与 queue.meta一致；不假定原 packing/tasks.json 的 node 字段。jobmap须包含 job_id/node，格式可嵌套dict/list。

2. `wp5_acceptance_verify_v2.py --catalog <catalog.json> --dictionaries <最终12字典manifest> --registry <冻结registry> --out <新目录>`。
   24独立worker逐文件校验 bytes/SHA、Arrow exact schema、registry全字段、N/finite、base/D20/D3/QC，逐 raw member读回SHA；每个最新 physical family/raw key与canonical locator相符。每个非QM family亦必须闭合11,231,854行。失败允许显式NULL/缺失/QC，不伪称SUCCESS，不填0。输出 verification_report.json、标签/原子数组元素统计及按7大小层/元素存在的缺失分类、任务状态、QC。ANY为可加记录分母；多元素存在分母相互重叠，不能相加。数组统计按同一registry字段内有限元素汇总，索引整数不作物理标量分布。原 verify.py不修改，v2仅补D20/D3/QC元素分母和原子SASA缺失统计。

3. `wp5_acceptance_recompute.py plan --catalog <catalog.json> --dictionaries <manifest> --runner scripts/wp5_runner_v6.py --regression-fields <已关闭G5 field_regression.parquet> --out <新目录>`。
   必须显式传最终冻结runner；原planner默认runner5属于准备时历史值，wrapper已显式覆盖为runner6。从正式记录按 seed20261011 +md5(record_id||seed)均匀确定性抽200，不按大小人为配额。仅这200条记录，按真实molecule_id组合，独立队列/输出根，共2400任务槽；不重算所选分子的其它未抽中构象。输出 recompute_plan.json及200条参考行/2400槽/4个非QM参考表、独立field_precision_manifest.json。
   `wp5_acceptance_launch.py --recompute-plan <recompute_plan.json>`只校验该计划的runner/protocol/dictionary SHA，再调用其中argv；Root提交后才产生这轮指南授权的重算。ALL仅用于验收证据，不变更正式 raw policy。临时scope/最低能量标记只影响验收raw保留；科学字段不改。
   完成后 `wp5_acceptance_recompute.py compare --recompute-plan <plan.json> --completion <新runtime/export_completion.json> --out <新目录>`。输出逐字段差异Parquet+recompute_comparison.json；科学/QC/derived/dedup字段全比较，排除run/time provenance，NULL/ABSENT/合法0分开。严格float64位比较；只有已声明、该record/field精度证据才能使用0.5×10^-dp（dipole单位转换同冻结G5）。未知context严格；不加通用epsilon，不修改active parser。

4. `wp5_acceptance_pilot.py --catalog <catalog.json> --registry <registry> --regression-fields <G5字段证据> --out <新目录>`。
   比较正式人口与原pilot的实际record交集；同时列出pilot分子在正式人口新增/未被pilot代表的构象，不虚构对照、不重跑完整pilot。24worker按单分子读取旧receipt SHA/科学Parquet，避免将120k宽科学行全部驻留内存。输出逐差异、registry/7层/元素的两人口缺失/标签分布及任务QC状态。只有明确G5授权的D4/删除POLAR诊断差异单列；原POLAR_FRAGILE且base好/无其它required缺失或长度失败，可解释原旧B与新scope状态差；保留物理值仍独立比较，绝不把其余差异吞掉。D20/D3没有伪造旧QM-pilot对照，由全量schema检查和新200重算覆盖。

5. `wp5_acceptance_storage.py --jobmap <actual jobmap> --scope node`由Root在14–19各节点执行；只检查本批formal job的 /tmp/wp5runtime_UID_JOB_*。旧G6/其它UID目录单列，不删除。`--scope shared --runtime <formal runtime>`核对lane临时/stage/pending和独立input.out/aux/xtbout等计算小文件均无残留，核对每个runner scratch_clean证据。均只读，输出storage_report.json。全账户文件数沿用G0/实际quota metadata，不混为本轮文件数。

6. `wp5_acceptance_delivery.py --catalog ... --verification ... --recompute ... --pilot ... --jobmap ... --accounting <Root实际sonmi observation JSON> --storage-reports <六节点及shared report>`。
   输出独立验收目录delivery_summary.json +WP5_delivery.md，第一页仅完成率、12任务成功率、实际核时/墙钟、存储占用/余量、待用户事项。allocated核时=每个正式main/cleanup实际ElapsedRaw×AllocCPUS，不替代成计划65450核时。墙钟需actual sacct Start/End；原publisher当前无这两列时明确NULL/待补，Root最终只读sacct可加Start,End发布相同JSON接口。Unknown MaxRSS或accounting缺口不变0。报告不代写Root独占最终报告，不直接创建LMDB。

## 资源、期限与批处理

统一 `scripts/wp5_acceptance.sbatch <stage> <CLI args>`；stage为 catalog /verify /plan-200 /recompute-200 /compare-200 /pilot /storage /delivery。24CPU、32GiB、48h，DuckDB20GiB，OMP/BLAS单线程，Arrow/worker池科学核验实际24进程并报告PID。Root可显式选原14–19任一节点。登录节点只做 --check/AST，不执行数据核验。

metadata/catalog/verify等wrapper内部46h timeout仅管理自己进程组，保部分证据，预留2h，不等Slurm48h硬TIMEOUT。新200由冻结runner自己 --hours46持有QM/最终导出期限；不再叠加外部科学进程kill。工作目录与spill在新job独有本地/tmp，结束只清本job temp。正式源码/永久结果不清。

最终所有formal main+6cleanup收尾后再跑catalog；catalog CLOSED后verify、pilot和200计划可独立提交。Root统一编依赖，未关闭人口可 --allow-incomplete出明确未闭合证据，但不能冒充验收PASS。200重算可能有指南允许的偶发失败，私有queue按同一一次收尾规则由Root处理，不能盲加多轮。

长期运行的每日第一页由Root正式监视器生成；本验收delivery只聚合已有科学/元信息，不另造每日科学任务。文件布局/存储audit脚本可在每日汇报中复用。未执行任何新科学/Slurm；无需因这些准备再次问用户。
