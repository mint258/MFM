# 既有512数值／原键无损投影试点

SOURCE ONLY；未执行Python、fixture、科学正文或Slurm。只允许原512完整分子／4251记录／16 canonical owners／14 tasks；不full、不新UFF/QM、不拟合归一化、不冻结mask或registry。8GiB是cap，不是输出预测。Root完成静态检查及审核后统一实际运行。

本目录没有复制／修改旧科学函数：直接调用原payload source_columns/evaluate、经既有legacy精确pin载入的common.component_values与pilot_masks规则、原compact编码。新代码只提取typed tree、定位component原有序path、绑定physical row provenance、写缓存与重开逐bit/顺序/类型验收。来源复用清单和实际Root source pins由metadata helper保存；不存在“原科学代码全文逆编辑”等价的伪声明（新sink是新增实现）。冻结原文件全部保持。

缓存schema每canonical task一行、每base geometry另1行，列row_kind/record_ordinal/task_code/record_id/molecule_id/tree_json/values_float64/scientific_signature。tree_json以显式tag保留int任意精确十进制、bool、str、bytes、None、list、tuple、ordered object；浮点独立F64 pool保留binary64 NaN payload/signedzero/Inf，reopen必须逐bit匹配。不是把所有源类型改成F64：原Arrow float宽度从实际buffer取，F32另存原bit pool；F64先验证as_py未改变原buffer bits。原storage schema及buffer bit hash留下，native程序打印精度仍UNKNOWN。JSON number按冻结json.loads解释，原科学JSON的UTF8 SHA留下；这不承诺重建JSON原空格/数字词法，更不冒充原程序输出precision。

全部264声明的科学CELL按实际registry ID保留，另原registry明确的扰动positions_A/elements/seed/sigma四个provenance CELL；缺失/NULL/EMPTY/N/A/constant/legacy区分。只排除注册表声明之外且未被该pipeline引用的源CELL包装/非目标metadata；排除集合可由原raw registry与264列表重建。坏／重复CELL不修复，原列表ordinal和科学payload保留。r73有序atom_i/basis_i/atom_j/basis_j/value、compound的原atom_index、每list ordinal与全部原值保持；不调用unordered pair_keys去替换原键，不dedup/symmetrize/平均。pair_keys仍仅传给旧review逻辑。NA empty的覆盖review作为原review保留，非新增缺原子判断。

component_map把每field/component定位到该原科学CELL及其原有序leaf path；值与冻结component_values逐类型/bit校验；不将pair的atom_indices=None冒充缺少原键。候选compact整行、field observations与所有source/new/review编码保留；不发明逐leaf因果。row provenance记录source producer ref、row_group/row_within_group/physical_row_ordinal、owner五键/lane/natom/role，以及status/SCF三态/precision/raw evidence。base保存原Z/positions_A/order/source hashes/graph与physical源键，核natom及原atom order，不打开LMDB。opaque geometry/order/Common尚未冻结，全部显式pending。

Root精确输入：原Root payload pilot config（sources里含原payload plan/census/registry/raw_registry/frozen_source_plan、adapter pins、matched4251 calibration）、原streaming prepared_pilot_v1/group_plan.json（16owner/209label/19base）、实际Alpha1884791 closure的Main逐SHA小复本作为已审profile、当前no_mem resource authority。canonical.sqlite、roleledger、16 owner_index、label与base只从这些冻结小plan继承data locator triples；helper实际去重和加和，不硬编码246或未来SHA。没有data正文stat/hash。Root source路径必须真实匹配原pin，不能同SHA借child路径冒充部署。

metadata helper需Root物理源整合后调用，纯stdlib，不自动提交：

    PY -B -m workflows.data_v1_final.labels.lossless_projection_pilot_v1.materialize \
      --payload-config MAIN_ORIGINAL_CONFIG --owner-plan MAIN_ORIGINAL_GROUP_PLAN \
      --parent-profile ACTUAL_ACCEPTED_PROFILE_CLOSURE_COPY \
      --parent-accounting ACTUAL_ALPHA_C0_ACCOUNTING_COPY --parent-raw-accounting EXACT_RAW_SACCT_COPY \
      --authority CURRENT_RESOURCE_AUTHORITY \
      --metadata-directory NEW_METADATA --output NEW_ARTIFACTS_CHILD --approve --reason ROOT_REVIEW_REASON

output必须是原artifacts/labels/source_status_v1下面的新目录，以复用未改resource observer路径授权。生成config/resource_binding/scope_review/stage_spec/preparation_receipt；Root独立centralv2物化请求，不修改原注册请求。16CPU/no_mem/7200s；worker原软件3GiB、4GiB MemAvailable软floor，仅停止下一source/派发并自然drain。64MiB row/384MiB group/8GiB whole（含64MiB observer）是可审上限，超限保留partials并STOP、不截断字段、不自动重试。

fresh central admission＋全部small/source精确pin核验后，原6测试原文＋新3cache边界必须实际全PASS/no skip，才打开任何数据。source schema/data stat在该gate以后。本轮源大body仅继承producer SHA并核稳定fstat，**不声称当前wholeSHA**；若Root要求新wholeSHA，要另显式登记CPUhash步骤及成本，不在本helper暗做正文读取。原Alpha227实际wholeSHA是历史证据，不冒充Main新观察。

source读法沿旧loop：每源只一个ParquetFile，row_group循环复用handle，Arrow predicate后转Python，SQLite readonly批次canonical join，finally close；同时保留原物理行位置。writer有界flush，完成后重开所有cache行，验证typed/order/bit签名及15slot（base＋14task）数量。实际16PID/opens/closes/RSS/producer byte上界/输出bytes/elapsed单列；producer bytes不冒充实际storage read bytes。>1%新增mask或启用field新结构invalid仍QUALITY_HOLD，数据缓存留存但不冻结。

3项新fixture只覆盖typed/F64特殊bit与unsupported STOP、真实ArrowF32/F64 buffer与slice偏移、r73原ordered键＋NA empty＋cache损坏拒绝；不替代真实512 profile。未来Alpha只搬实际cache及manifest，另Root新端点proof、UID、transfer verification；本版不实现跨端点执行或full。
