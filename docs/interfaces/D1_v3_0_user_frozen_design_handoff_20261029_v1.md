# D1 v3.0用户设计定稿交接

本包只有新文档和小型机器政策，不含科学DATA、模型改动、计算入口或运行证明。实际用户policy已按Root提供的正引用验证本机字节，未重新读取服务器/科学文件。旧draft3/4/5、Source审阅、失败/UNKNOWN及活Source均未修改。

建议由Root逐SHA精确安装：

|包成员|仓库目标|
|---|---|
|training_format_v3_0_user_frozen_design_20261029_v1.md|docs/interfaces/training_format_v3_0_user_frozen_design_20261029_v1.md|
|D1_v3_0_user_frozen_design_policy_20261029_v1.json|configs/data_v1/interfaces/D1_v3_0_user_frozen_design_policy_20261029_v1.json|
|D1_v3_0_five_layer_mapping_selections_20261029_v1.json|configs/data_v1/interfaces/D1_v3_0_five_layer_mapping_selections_20261029_v1.json|
|HANDOFF.md|docs/interfaces/D1_v3_0_user_frozen_design_handoff_20261029_v1.md|

正式设计version=v3.0，用户1–4已冻结；5A是有条件物理政策，不是再次草案。design policy刻意不使用发布器的JOINTLY_FROZEN schema，不自签Model ACK。五层是冻结的映射选择规则；尚不存在的最终fieldIDs/targetIDs/人口/实际layer refs保持null，而不是拿当前draft registry冒最终实例。

## 当前发布器接合

既有 `workflows/data_v1_final/labels/final_release_v1/contract.validate_directive` 仍使用真实Root `ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1/JOINTLY_FROZEN`。正式joint对象必须绑定新合同/机器policy/五层SHA、用户实际policy、Root逐field科学签认和同版本非conditional Model ACK。

现有final_release9要求root_review_reference/model_ack_reference/contract_reference、registry_source_reference/mapping_source_reference、scientific_field_definitions、size_rules_by_field、normalization_by_target、partial_mask_policy_reference、field_geometry_policy_reference、structure_recipe_reference和分开的evidence_source/DATA refs。其unit/sign/basis/frame验证不能以本设计choice替代。未知项按实际target范围处理，不设“全部轴通过”的总旗标。

r674每个已解析实际target的 `normalization_by_target` 已选择：dataset=P_D或独立Pprime，真实 `series_key=physical/674/<actual task>/frobenius_norm`、scale=SERIES_STD_DDOF0、centering=FIXED_ZERO、per_head_single_scale=true。不能在实际series/D4尚缺时填数值或未来SHA。

需要如实完成的窄接合，而不是重选算法：

1. 当前 `originals.exact_series_recipe` 对缺series/空/零std整候选raise；`produce.normalization`对所有物理target直接调用它。尚未实现本用户policy的target-local `LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE`。后续最窄adapter须保留该target值/源mask、明确未绑定normalizer与disabled-loss状态，同时允许其他就绪目标；不能造s=1/epsilon或把disabled当数值invalid。本包不改冻结9源。
2. 当前D4既有row.mean是winsor均值，`audit_series_mean`也来自它。原始mean(F)/s若尚未计算须准确待补；不能把row.mean改名成原始均值。该新增报告不改变原winsor尺度。
3. complete6排除比例与元素/可靠化学结构分层、UNKNOWN覆盖率须由真实CPU产物提供；>10%预警、>20%/集中偏差论文披露。不能以本政策存在就声称这些表已计算，也不能让eligibility构造新的数值mask。
4. Model已给conditional原则反馈，本用户决议关闭选择分歧；ordered-entry与tensor6 consumer/head/loss/count/恢复及实际数据消费仍须同版本实现/验收。新vector公开Source仅证明旧vector radial分母/3，不等于tensor已实现。

## 物理证据与测试边界

Root的真实407-ref物理报告已经到达，不请求再跑同一summary：已有100tensor/100gradient一致性、MOPAC160+gradient32坐标受控事实，六xTB单点192无独立坐标仍UNKNOWN。先前B32原parser/input绑定与Decimal trace11非零均保留；不从打印舍入、Source默认或当前rc absence推新PASS/FAIL。

Root/SB4正在处理用户唯一≤1800秒带电旋转/平移试验；本包未收到实际结果，不造test ref。后续Root只需将真实结果与原条件/程序/关键词绑定并作逐target物理判断，Model同SHA ACK后再生成joint发布对象。若不可核实，按用户已授权fallback关闭原点敏感带电target exposure，其余可确认目标继续；无需就已选1–4反复发草案。

## 验证与停止编辑

仅做本机SOURCE/小JSON字节SHA、实际用户ref相等、JSON字段与五层顺序检查和ZIP逐member读回；未运行Python、AST、测试、Native、网络、SSH或Slurm，未读科学体。安装后的真实checker与后续CPU/Model验收由Root统一完成。manifest与artifact_receipt记录机器SHA，不从聊天折行抄录。

交付后本包 `SOURCE_ONLY_FINAL / STOPEDIT`。设计定稿不是D1双方签认、D4数值发布或全指南完成。
