# Secondary software compatibility control16 — unregistered DRAFT

状态：未冻结、未运行Python/AST/fixtures/SSH/Slurm/Git，未实际读取tasks/packets/LMDB正文。没有transfer、Alpha science job或兼容PASS记录。Root管理连接；本包不存凭据。

本轮明确是 **secondary software compatibility controls only**：从原334个已保存成功包选16个小而快的独立QA，同一原task/seed在Alpha重放，用已有packet比较；不再算16个新的main baseline。Alpha的16个输出仅为QA artifacts，population_members_added=0。其余原334成员与两个missing均不可进入本批；两个missing无条件禁止。当前main4521110的2+14 scope与原production once ledger保持不变。没有formal入口或可开启formal的参数。

## 不变科学与Torch差异

run_pilot.run_one -> science.process_task + statistics_tools.molecule_statistics；science使用common/selection，加载sprime_v6.py，后者import prepare.py。source_catalog.json记录这7个实际原文件bytes/SHA，部署及Alpha启动逐文件核同字节。原recipe独立固定3629B、cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a。

原Torch只用于线程设置及原Tensor经detach().cpu().numpy()的解码转换；没有Torch模型/数值优化内核。图/立体/RMSD/Kabsch及去重仍原代码，SVD/det由NumPy计算。原pickle可能需要Torch与PyG类解码，不能删import或以JSON数字重建原记录。逐分子统计用NumPy/RDKit；SciPy仅aggregate，本worker不调用aggregate。

Alpha目标为RDKit2025.09.5、Python3.11.14、NumPy2.2.6、Torch2.5.1+cpu、PyG2.7.0。main Torch2.10与Alpha2.5不同，源码和receipt明确不声称build相同；main版本证据由实际environment review提供。旧历史requirements同时有cu128/cu126记录，不能拿它伪造单一当前build。环境create成功/离线wheel到位不等于科学兼容PASS；必须完整control16匹配并由main验收。

原seed域、retry_once、10N/cap300、ETKDG、UFF2000/energy1e-6/force1e-4、source atom order、graph/stereo、fixed-index proper Kabsch及0.5A阈值均不改。只替换SCIENCE.read这个存储入口；所有科学函数源字节保持原样。

## 固定选择与已有基线权威

Root已固定条件，任何一个超出即不合格：

- summary.status=SUCCESS，detail.new_real_accepted_count>0。
- heavy_atoms<=32，expected_conformers<=30。
- 原science_worker_seconds有限且>=0、<=60秒，并与原summary.elapsed_seconds一致。
- 按sha256("secondary-software-control16-v1:20261026:"+MID)、MID排序，取前16；不按新的Alpha耗时、结果或数值漂移择样。

不足16时只生成eligible_count_report.json，状态ELIGIBLE_COUNT_BELOW16_NO_QA_SLICE；不读baseline/LMDB bodies，不调用science，不拓宽阈值，不创建QA slice。旧elapsed仅是筛选观测，绝不是Alpha运行时间forecast。

原pilot4520364仍TIMEOUT。包验证权威是partial audit4520527的C0/2秒、原audit/complete_packages及其fstat/fullSHA；不能把原pilot称C0。main prep读取既有baseline packet计算scientific SHA，只移除summary.elapsed_seconds，绝无新main embedding/UFF/QM。

## main合法CPU prep入口

prepare_existing_controls.py要求新central auto-memory analysis startup proof（实际UID/main node/16CPU、fresh120sec、exact primary/options/source pins、quota等），然后才读原tasks与334元数据。旧recovery bind_inputs保留全task SHA、334目录/文件身份、recipe和原控制来源检查，不走旧64G/85%资源准入。建议Main prep仍选compute-0-17，以保留旧文件device/inode身份；不会为换节点删掉原fstat检查。

Root先创建小授权ROOT_SECONDARY_EXISTING334_CONTROL16_AUTHORIZATION_V1，status=APPROVED_FOR_SECONDARY_SOFTWARE_COMPATIBILITY_ONLY，reviewer=root，mode=SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY，formal_generation_authorized=false，allowed_existing_control_count=16，endpoint_id为实际Alpha target canonical SHA，forbidden_missing_ids恰两missing，selection_rule与contract.control_selection_rule()精确相等。不得以这个授权扩当前main恢复范围。

未来Main argv（必须按此有序绑定）：

`PY -B -m workflows.data_v1_final.conformers.portable_secondary_uff_v1.prepare_existing_controls --recovery-plan ORIGINAL_APPROVED_PLAN --control-authorization ACTUAL_QA_AUTH --root-preflight FRESH_MAIN_PROOF --output NEW_MAIN_EXPORT_CHILD`

scope_key=secondary_existing334_control16_export；scope_parameters见源码PARAMETERS。预算至少1GiB+64MiB，留200GB。输出必须为main artifacts/conformers/secondary_compatibility_controls_v1的新独占子目录。先写计数报告，合格才以授权SHA O_EXCL创建qa_export_slices标记；这是QA导出marker，绝不打开/冒用production once ledger。

每个选中包核原fstat与完整压缩SHA、gzip EOF/CRC和成功状态；只读LMDB取原pickle bytes并核原record_payload_sha256，原始bytes base64导出，不pickle.loads/dumps重建。JSONL中task完全不改，携带canonical task SHA、每个原pointer SHA、原payload bytes/sha/base64。目标最多1GiB，逐行64MiB。

输出control_tasks.jsonl和control_preparation.json（MAIN_EXISTING334_SECONDARY_CONTROL16_PREPARATION_V1/status ROOT_APPROVED_EXISTING_PACKETS_FOR_SECONDARY_SOFTWARE_QA_ONLY）。包含完整336保护集、恰16的allowed_original_control_ids、其余320 forbidden IDs（必含两个missing）、原audit/complete/monitor pins、原packet SHA/fstat/scientific SHA、计数规则、QA marker、实际main prep job来源。没有新增main科学基线。

## metadata部署助手

Root actual target authority：USER_AUTHORIZED_SECONDARY_FREE_CPU_UFF_V1/status USER_AUTHORIZED，target须alpha@218.192.171.238、uid1264、/gfshome/alpha/codex_data_v1_20261026及Root实测CPU节点名；memory_policy=SLURM_DEFAULT_UNSPECIFIED、formal=false、有限wall。不能仅凭同名sonmi判断endpoint。

实际environment review：SECONDARY_UFF_ENVIRONMENT_ROOT_REVIEW_V1/status READY_FOR_GOLDEN16_COMPATIBILITY_TEST、reviewer=root、endpoint_id、formal_compatibility_passed=false、python_executable、expected_versions（含Torch/PyG）、probe_evidence_references、main_torch_version_provenance、torch_build_identical_to_main=false。READY仅可测试，不是PASS。

也可直接传Root已取回的SECONDARY_OFFLINE_ENVIRONMENT_VALIDATION_V1原result（当前1884762，原SHA0bbf0a5afd129728e2dd6d991c2118305ce056848018d99a791f4805cb681f7b）。helper验证真实endpoint/uid16CPU、精确versions、toy SVD/PyG float64 pickle/RDKit parse以及dataset/UFF/QM=0，创建独立小Root review，并把原result原bytes另存；不改完成结果，不把READY升级PASS。Alpha启动重核原结果SHA和转换内容。

未来metadata CLI：

~~~bash
PY -B -m workflows.data_v1_final.conformers.portable_secondary_uff_v1.deploy_metadata \
  --reviewer root \
  --target-authority ACTUAL_SECONDARY_AUTHORITY_JSON \
  --environment-review ACTUAL_ENVIRONMENT_REVIEW_JSON \
  --main-preparation ACTUAL_MAIN_CONTROL_PREPARATION_JSON \
  --original-recipe ACTUAL_FROZEN_MAIN_RECIPE_JSON \
  --staging-directory NEW_MAIN_STAGING_CHILD
~~~

helper只读/copy小源码与小metadata，不读/copy tasks body、baseline packet或LMDB，不调scheduler或网络。复制7科学源原bytes、portable package、原recipe/新locator recipe、Main控制授权与原audit/complete/monitor。recipe仅允许science_source_pins[].path和external_output_root变化，其他值及JSON类型精确相同。main authority/LMDB/packet绝对路径仅为明确来源，不在Alpha打开或造假alias；prepare.py旧PROJECT/ROOT常量保留原字节，其原read/main/save不会调用。

deployment_map schema=PORTABLE_SECONDARY_UFF_CONTROL16_DEPLOYMENT_MAP_V1，mode=SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY。origin_reference和计划target_locator分开，actual_target_installed=false；已知源SHA的target locator不冒充安装证据。Root独立传输代码/metadata/合法Main导出的JSONL，Alpha启动才逐目标实际文件核bytes/SHA/uid，并重新按已复制的334元数据推导固定16 allowlist。

## Alpha worker与独立证明

未来在target根目录/code使用隔离环境的实际python：

`PY -B -m portable_secondary_uff_v1.worker --deployment-map ACTUAL_MAP --startup-proof ACTUAL_ALPHA_PROOF --output NEW_ALPHA_QA_OUTPUT_CHILD`

proof schema=SECONDARY_PORTABLE_UFF_CONTROL16_STARTUP_V1。须实际endpoint_id/UID1264/job/node/boot、120秒内observed_unix_seconds、request(kind=conformer、pilot=true、cpus16、memory omitted、有限wall、exact argv)、实际map/script pins、Slurm job_metadata字段字典、account_free_bytes/quota_raw。另有SECONDARY_PORTABLE_UFF_CONTROL16_ROOT_SCOPE_V1/status APPROVED_FOR_EXACT_SECONDARY_CONTROL16真实Root review pin，精确绑定endpoint/map/argv/wall/script/mode=SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY、population_members_added=0、formal=false。不能复用main proof或UID。

worker核sys.executable、实际__main__与全部options，CPU partition/16CPU、CUDA空、线程1、实际RUNNING/UID/node/墙钟/无requeue与script无mem/GPU/exclusive，留200GB。既不查65536也不用声明85%准入。桥对每条原pointer核payload SHA、直接pickle.loads、执行原total_atoms检查；不重构原数值。随后16个spawn/PID barrier执行同一run_one与persist_result。

本地attempt_spool按slice_id O_EXCL只接受一次，非main once ledger；不覆盖、不自动retry。MemAvailable低/指标无效只标记停止后继派发，当前16个自然结束，无显式signals。任一不全/科学SHA漂移/环境不符都失败；保留packets与gzip memory证据供main诊断。comparison仅去原elapsed，其余bit可见差异不放宽容差。

receipt schema=SECONDARY_PORTABLE_UFF_CONTROL16_RECEIPT_V1，mode明确QA controls，population_members_added=0、two_missing_replayed=false、current_main_recovery_2plus14_scope_changed=false、formal=false。即便全部匹配，也只是CONTROL16_EXACT_SCIENCE_MATCH_REQUIRES_MAIN_SOFTWARE_ACCEPTANCE；main统一验收前无release，不能重复计入population。Alpha terminal sacct须以endpoint/UID/job身份搬回Main合账，不能将相同数字job冒充Main job；免费服务器不等于免记物理成本，原适用96h/科学门槛不因QA授权而豁免。

## 未运行的synthetic fixtures

test_portable.py为5methods：recipe只改locator、原pickle bytes/pointer/atom数、QA allow16与missing/formal/population拒绝、固定32/30/60边界与不足16报告、真实offline schema转换保留READY/不改原result/不伪称Torch相同。未来在合法CPU allocation可用`python -B -m unittest workflows.data_v1_final.conformers.portable_secondary_uff_v1.test_portable -v`。当前未运行，不代表真实环境、transport、control16或正式生成通过。
