# Stage5 首 seed 准备：用户 v3，20项科学设计 + 20项真实 D3 接线模板

状态：SOURCE_ONLY / DRAFT_NOT_TRAINABLE，2026-10-29。
实施模型基线 e92b6125e0b3ea430970bc7ee24fc152e26919c5；
只读时 canonical 文档 HEAD 为866b2d4a42b36e62abda730585b66c52a011fde1。
本独立 N 目录未修改 canonical、Data、DECISION_RULES.md 或任何旧测试。

## 用户 v3 已生效

C4 依据4524734的纯FP64相对1e-9数学测试48/48，立即PASS；不再HOLD。
FP32仅诊断，不作为Stage5门。旧v1/v2与全部补偿候选就地归档，停止、不采用、不重跑。
日志/SDK/记账/fixture/SHA的失败诚实记录但不阻塞科学下一步；实际身份、
资源、TRAIN边界及真实数据权威仍执行。W&B按天、账目按周集中处理。
任何诊断/修复4小时或连续失败2次即未解决、保守旧路径继续。
r674保持LOSS_DISABLED，预测头保留，不再追加诊断或处理。

## 真实清单

PLAN.json列出首seed0的完整20项，顺序与原architecture_plan一致：

- C1_0_S、C1_0_P、C1_a_S、C1_a_P、C1_b_S、C1_b_P。
- C3_v2_S、C3_v2_SDP、C3_v3_S、C3_v3_SDP。
- H_H1_P、H_H1_D、H_H1_SDP、H_H2_P、H_H2_D、H_H2_SDP、
  H_H3_P、H_H3_D、H_H3_SDP。
- H_H1_P_learned_pooling。

scientific/下20份保留原D5 240000 TRAIN分子、全部授权构象、PM7、
6x512、lr3e-4/betas0.9,0.95/clip1/2%warmup+cosine。
6M仍是提案，平台证据、B0/容量、registry/normalization/D3/D5/reader均待真实绑定。
后14项前序C1/C3选择显式deferred，不把C1-0或视图3冒胜者；
共同头也由真正登记政策决定。约6次补seed只预留设计，不伪造获选trial/SD/分数。

smoke/下另20份仅作D3接线。候选本身仍保留：
C3测自己的2/3views，H测自己的H1/H2/H3，pooling测原H1/P learned mixer；
只有前序依赖暂用C1-0、3views、H1 anchor，所有模板明确
NOT_SELECTED_NOT_SCIENTIFIC。保持plain C、bias=False、H0=512、A4、
FP32/TF32false，不塞当前C路径不支持的training_execution。
C1-0实际沿未扩展的legacy distance配置；C1-a/b才写v3_architecture。

## 静态检查入口

Root可在CPU metadata环境运行：

```bash
"$MODEL_V3_PYTHON" "$N/stage5_first_seed_user_v3_20261029_v1/check_stage5_templates.py"
```

该脚本只读PLAN及40份JSON，检查20唯一名称、6+4+9+1、
首seed、声明6x512x8/H0/FFN形状、固定优化器、6M提案/待容量、
科学选择deferred和50/2000冒烟边界；无Torch、数据读取、模型或Slurm。
作者未运行此Python。作者的JSON/文本静态核对与Root实际运行/模型shape验收分开。
实际目标输出shape仍须真实registry及D3模型前向；没有臆造字段数或尺度。

## 薄源码接点及合并

新增overlay：
current/phychem_mfm/phase1/v3_architecture_smoke.py、
tools/model_v3/prepare_architecture_wiring_smoke.py、
current/tests/test_model_v3_architecture_wiring_smoke.py。

patches/v3_proxy_run_purpose.patch只在原update_limit后插2行目的验证，
base rawSHA 970ce88404a7310eedb6e248d18234f26d9b84cba9028cfe967ef889498965e0。
不碰SA2约195–204的operational admission。
patches/run_proxy_experiment.patch只选50更新上限并标注完成结果，
base rawSHA 1adfd598a3c067e1ed95b4cfc12e00f7e53a19034b9429d3cd79d330e7070453。
Root按patch合并，不用旧整文件覆盖其他人的改动。
v3_pilot_smoke.py及其原2000验证/stop/CP函数字节不改。

## D3 到达：每项真实50有效更新

合并后使用原完整已准入authoritative_pilot基请求。新prepare入口先经过原
validate_request + bind_inputs，实际验证同release/ACK/reader/registry/normalization/
TRAIN/两VAL人口；没有Data或只有UNIT/draft就拒绝，且不创建prepared输出。
它不读取最终TEST，也不要求未来D5或自己未产生的三卡2000证书。

```bash
"$MODEL_V3_PYTHON" "$W/tools/model_v3/prepare_architecture_wiring_smoke.py" \
  --base-request "$REAL_ADMITTED_D3_PILOT_REQUEST" \
  --base-request-sha256 "$ACTUAL_BASE_REQUEST_SHA256" \
  --trial C1_0_S --output "$FRESH_OUTSIDE_GIT_PREPARED_DIR"
```

对PLAN的20个名字分别准备。输出configuration、request.UNADMITTED、PREPARED；
新request仍authoritative_pilot/pilot_smoke、engineering_only=false，
另显式purpose=architecture_wiring_smoke。清空旧Root_admission/registrations，
不可借旧配置准入；Root用原finalize_training_request（现recipe CLI admit）绑定
实际新配置登记/资源/真实D3后，仍由原run_proxy_experiment run执行：

```bash
"$MODEL_V3_PYTHON" "$W/tools/model_v3/run_proxy_experiment.py" run \
  --input authoritative_pilot --request "$ACTUAL_ADMITTED_REQUEST" \
  --request-sha256 "$ACTUAL_REQUEST_SHA256" --output "$FRESH_SEGMENT" \
  --lineage-root "$FRESH_LINEAGE_ROOT" --lineage "$DECLARED_TRIAL_LINEAGE" \
  --segment-id wiring50 --until-samples "$BOUND_SAMPLE_ENDPOINT"
```

原supervisor/Slurm/资源/UUID锁照常由Root提交，不提供新调度器。
until-samples是原样本预算端点，不是50更新。真正停止只看有效optimizer_updates；
暂停/恢复累计到50，跳过/全disabled批次不增加更新。预算提前耗尽照实未完成。
原2000 pilot合同不改，50是本purpose的独立接线上限；原preflight→两验证→safeCP沿用。
写结果前只标ARCHITECTURE_WIRING_50_COMPLETE_NOT_SELECTION_NOT_PILOT_2000，
不冒Stage4三卡2000完成、6M科学试验、胜者或Data验收。
真2000整合仍使用原无purpose的pilot请求独立执行。

## D5 科学试验

D5到达并有真实平台预算/登记/前序选择后，继续原
prepare_architecture_experiment.py resolve / prepare；它重新从已闭合证据解析选择，
用实际registry及240k/PM7/all输入，拒未解析symbol。
本目录不提供假Data refs、假可训练plan、赢家、seedSD或性能数据。
DECISION_RULES科学选择、硬TRAIN、6M确认、用户Stage6最终确认均未改变。

## 检查边界

新测试含20 metadata布局、跨scope/错误anchor/类型拒绝、普通2000与旧默认保留、
有效更新50/非样本计数、UNIT不授实际D3，以及复用原UNIT provider/两fresh CLI的
50更新stop→CP→resume→SDK机制控制。UNIT用低频恢复间隔避免大量CP堆积，
不修改生产checkpoint政策；它不是实际D3或20个C模型运行通过。
作者未运行项目/AST/测试/Git/SSH/Slurm/模型/SDK，实际测试结果全部待Root。
