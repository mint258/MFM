2026-10-30 Root整合状态：新接口及23项测试已通过实际4525191的138模块全量回归（3263 passed、3原skip）。首次4525188唯一UNIT辅助函数解包失败已保留并修正；训练实现未因该修正改变。下方为作者STOPEDIT时交接稿，其中“planned/未执行”仅描述作者当时状态。真实排名、第二种子训练和SD仍待D5；输出继续UNADMITTED。

# 阶段5已闭合首seed → 第二seed的薄准备入口

仅补原指南“排名前两位各追加一个seed”的实际配置/UNADMITTED请求接线。原20个首seed、原数学/选择规则、D5真实准入、训练器、模型和Runtime均不改；不运行模型、不给不存在的排名/分数/seed SD，也没有新提交器/审计器。Root拥有v3_proxy_plan预算函数，本包不修改或覆盖该文件，仅import既有second_seed。

## 接点与实际行为

新增phase1/v3_architecture_repeats.py。既有prepare_architecture_experiment.py仅新增repeat子命令，原resolve/prepare保持原行为。原second_seed生成的seed1 trial先验证它对应原20个seed0 trial；原compile_trial编译首seed配置，与inspect_run实际闭合运行的原configuration逐字义canonical内容相等后，才复制并只改变顶层seed=1。budget、condition、C-only biasFalse、模型、heads、views、sampler、geometry、normalization、optimizer/schedule/clip、所有独立噪声/读出seed均不改。原planned scientific_identity排除运行名与pretraining_seed，新旧严格相同；这不是尚未运行的seed1实际科学证据。

生产prepare先执行原registered_policy、validate_request(input_kind=authoritative_proxy)、bind_inputs及240000实际TRAIN/D5门，provider按原方式close。C3/H/pooling原C1/C3依赖仍重新调用resolve_inputs，不能相信saved选择字符串。随后每个选中的首seed均由原inspect_run完整核实际18cell panel/primary reference/checkpoint COMPLETE、safe weights_only payload/训练预算和seed/真实C0/accounting/source snapshot/角色人口。该读取只能在Root安排的CPU计算作业内进行；作者没有执行或读取任何checkpoint、标签、数组或SDK。

## 显式闭合选择输入（模型侧控制metadata，不是新的Data契约）

`selection`是Root/原工作流已经实际闭合并明确指定两名的原字节文件ref。本文不给未来路径/SHA/名字或假closed结果；没有真实排名/闭合输入时保持拒绝。文件包含且仅包含：

- schema=model_v3_architecture_second_seed_selection_v1
- status=ROOT_CONFIRMED_CLOSED_TOP_TWO
- authority=root_verified_stage5_closed_selection
- policy_sha256：原Git固定政策SHA
- selected_names：恰好两个互异原20首trial名字，顺序保留
- first_seed_runs：以上两个名字→原inspect_run的完整entry（request/result/sampler_contract/memberships/execution/source_snapshot_root）
- panel：原完整冻结九任务面板rawref
- panel_preregistration_commit：原面板登记40hex

这个小对象是对Root原已闭合且明确给定两名的输入投影，不是本代码签发的排名证书。代码不重新定义top2排名或对跨S/P条件打分，亦不宣称仅凭status字符串认证Root身份。原两名的正确排名及Root作者身份继续属于原科学流程/独立Root审阅；代码独立重验这两条实际首seed已完成且与原trial匹配、不同run/checkpoint、同panel、原预算和政策先于训练。头部标closed但没有完整实际run证据也会被原inspect_run拒绝。Root后续新的实际registration/admission与D5门不能省略。

CLI inputs沿原rawref/Git政策格式：必需policy、policy_sha256、base_request、first_seed_trials、selected_name、selection；可选resolution_inputs。first_seed_trials是上述两条**原seed0** PlannedTrial完整JSON（parameters有序二元list），不是seed1配置或调用者覆盖；selected_name是本次准备的其中一名。两个名字分别准备时用两个fresh输出目录，不能覆盖或复用一次提交身份。

```text
PY -B W/tools/model_v3/prepare_architecture_experiment.py repeat --inputs ROOT_ACTUAL_INPUTS.json --inputs-sha256 ACTUAL_RAW_SHA --output FRESH_N_OUTPUT
```

输出沿原结构：configuration.json、request.UNADMITTED.json、PREPARED.json。registrations={}、Root_admission=null；原long_run操作ref不偷带，Root需为新成员重新绑定有限资源/源/CP/H0/数据准入。request.architecture_preparation记录原闭合selection、两首seed完整source entries、原/新trial与同planned identity，不新造请求schema。不启动训练、拟合、评估、Slurm、SDK或Git，不冻结任何模型/配方/B*。

## 本包如何整合

- 把两个新增current文件加入Root独立集成树。
- 对tools/model_v3/prepare_architecture_experiment.py应用integration.patch；包内同名文件只供精确复核，不覆盖别人的整棵树。
- before/prepare_architecture_experiment.py是此次唯一修改旧入口的原字节备份；diff仅command choice/required manifest/薄repeat分派。
- 没有改v3_proxy_plan.py/原20 trial/compiler、Data目录、canonical或既有131/原112测试。

新增test_model_v3_architecture_repeats.py **23 planned**，未执行。复用已有metadata-only architecture fixture；正例只调用纯compiler，验证配置仅seed改变和identity不变；负例覆盖未知/重复两名、非20原trial、seed1再次repeat、擅改budget/参数、错首seedhead/LR/seed、pending/failed/missing closed选择、缺run/换policy、fake closed header仍过不了原inspector、真实prepare拒绝UNIT Data base且不创建产物，实际生产同一纯metadata writer清空旧admission/long-run且不授运行权威，以及一次薄CLI UNIT分派。没有mock实际Data准入为真，也不把UNIT选择header/CPU测试当科学排名或GPU通过。

Root统一用原CPU完整回归/正常checker验证和Git；作者没有运行Python、AST、项目、Torch、SDK、Slurm、Git或网络。未来真实排名/seed1训练/SD仍待D5与原工作流；本次仅完成可在数据前准备的接口。不因日志、SHA或fixture建立新的科学阻塞；4h/连续失败2次止损沿用户规则，无新数值分支。