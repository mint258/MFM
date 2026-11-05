# Native B四成员最终验收：现有入口交接（只读核查）

当前不是B通过。原训练与在用v8/prewait-v3不改、不重启；不读取SDK、steps/resource journals、checkpoint或数组。实际最终数值报告/未来SDK证书均未生成。本交接不创建runner、dispatcher或新验收门。

## 1. 已有最终数值CLI，直接复用

`MFM_model_v3/tools/model_v3/run_native_s_precision.py:242–250` 的 `report` 已调用 `phase1/v3_native_s_precision.py:317–352::compare_native_s_members`，再调用 `training/v3_performance_acceptance.py:89–131::bf16_curve_report`。它只对已有member结果中的数值曲线计算门，不重新训练/验证模型；应由Root在既有>=16CPU自动内存作业中执行，不能在login运行项目。

```text
cd /share/home/zixiao/descriptor_analysis/MFM_model_v3
PY -B tools/model_v3/run_native_s_precision.py report --members \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_B20k_v3/slots/slot_021/child/member_result.json \
  ACTUAL_FP32_SEED1_FINAL_MEMBER_JSON \
  ACTUAL_BF16_SEED0_FINAL_MEMBER_JSON \
  ACTUAL_BF16_SEED1_FINAL_MEMBER_JSON \
  --output FRESH_OUTSIDE_GIT_NUMERIC_REPORT_JSON
```

后三项是必须由真实闭合终点填入的CLI占位符，不是预填未来路径或可执行FINAL。顺序无科学选择作用，函数核四种seed/precision组合唯一、四个最终tracker lineage不同。

原门完整保留：每成员恰20,000有效更新，41个验证点0/500/.../20,000；common/model/data/plan一致；同seed两精度实际samples、训练input-chain、sampler合同相同；每点实际验证人口、输入SHA、noise seed0/epoch0完全匹配。10.24M是原sample budget上限，不把它伪称实际消耗或替代20k更新。

对每个验证点的每个已保存metric，每个bf16 seed均须在两个真实fp32 seed的闭区间[min,max]内；不是均值、只看最后点或额外容差。另对原`s_noise/RMSE`逐同seed核`abs(bf16-fp32)/max(abs(fp32),1e-12)<=0.02`。此分母是原B实现，不借新等变性规则改动。两个条件逐行合取；不换成其他noise-RMSE/epsilon字段。

返回值保留`numeric_gate`的每点/metric/seed/上下界/配对差/通过标志，并明确`scientific_acceptance=False`、`D5_authority=False`，独立段终态/监督/SDK/实际CUDA dtype/存储证明仍由Root闭合。不能直接把CLI JSON的数值pass升级成完整B采用。

## 2. 当前真实端点与来源资格

slot021是seed0/fp32，`UPDATES_COMPLETE_PENDING_OUTER_TERMINAL`，20,000更新/8,151,040samples/41点，最终tracker `vgfs8jeh`；其management/ROOT_LONG_SEGMENT_CLOSURE.json已真实闭合。

slot028是seed0/bf16，`SEGMENT_PAUSED`，7,000更新/2,851,328samples/15点，tracker `2wh2cs0m`；它不是最终member。slot029按Root当前观察正在7k→8k，未读其运行中产物。seed1两支未开始。

已只读比较slot021/028的全部common_binding顶层属性，无差异；共同science code3d9b1cc0...、原prereg ce7cbf5776ff546cd47538b120c8f884e2e5867d、scope=`existing_native_S_original_TRAIN_record_sampler_not_D5`。最终仍须四个实际final文件再次由原函数核验，当前一致不冒未来资格。v8仅操作/自动资源版本，不改变此原science/core。

现成相关测试源码：`test_model_v3_native_s_precision.py:218–234` 包含四成员、同seed输入链和人口分母拒绝；`test_model_v3_performance.py:170–183`包含不完整/越包络曲线。这里只定位既有测试，不声称本交接重新执行或把合成fixture当真实四曲线。

## 3. 完整SDK批量审计/官方选择同步：复用已C0方法，补实际selector即可

最近成熟包：

- `N/native_closed024027_sdk_audit_v1_source/`：`audit_closed_segments.py prepare/run`、原`long_segment_log.py`、28项metadata QA；literal749/tap2/rb-framing保持。当前selector明确仅(24,25)/(26,27)，不能直接拿该包审028或未来member。
- `N/native_closed024027_long_sync_v1_source/`：`prepare.py`、`long_common.proof_rows`、`one_run_long.py`、`sync_selected_long.py`；本地自动CPU allocation已实际接通。当前同样只认可四个既有ID和该exact audit producer，不能改一个CLI参数就假称通用。
- `N/native_closed024027_long_sync_fixture_v1_source/`：原fixture-aware监督/六功能selfchecks/原4metadata QA，持续lstat规则与原whole/private各2GiB不变。

实际成功来源链：`N/Native_B_closed020023_SDK_Root_closure_actual_v1.json`与`N/Native_B_closed024027_SDK_Root_closure_actual_v1.json`。后者真实audit4983/4985 C0、sync4990/4993 C0；原失败分组审计也保留。已闭SDK无需再扫描，最终总链引用其原证书/Rootclosure即可。这里不把旧声明或全局online计数当作任何新run证明。

后续只需在新namespace机械绑定当时**明确已关闭且尚未审计的1..3段**：实际closure/submission/member/config/SDK-stat及真实package/adoption/source rawrefs、对应明确run IDs。SDK正文/完整mirror只由实际CPU作业读。source selector和`closed_audit_source`依赖必须一起诚实重绑，不能直接编辑024027原件或接受未知操作版本；原long_segment_log/28QA/reader/tap/framing/transport/计数与退出规则逐字复用。不必等四成员都结束才集中重审已完成段，也不能只审四个最后SDK替代完整resume分段链。

原prepare接口：

```text
PY -B NEW_EXACT_AUDIT_SOURCE/audit_closed_segments.py prepare \
  --phase N/native_S_B20k_v3 --slot ACTUAL_CLOSED_SLOT [--slot ACTUAL_CLOSED_SLOT] \
  --output FRESH_INPUT_DIR

# 只有同父28QA+全SDK证书和外层C0真实通过后：
PY -B NEW_EXACT_SYNC_SOURCE/prepare.py \
  --entry ACTUAL_VERIFICATION_JSON ACTUAL_BATCH_RESULT_JSON ACTUAL_AUDIT_SUPERVISOR_JSON \
  [--entry OTHER_ACTUAL_VERIFICATION_JSON SAME_OR_ACTUAL_BATCH_JSON ACTUAL_SUPERVISOR_JSON] \
  --pins-sha256 ACTUAL_NEW_SYNC_SOURCE_SHA --output FRESH_PLAN_DIR --job-output FRESH_SYNC_DIR
```

`prepare.py`明确接受1..3 proof triples，捕获实际audit C0；官方运输exact-copy、真实RunRecord项目/entity、native config/summary/history typed exact、CRC/EOF/exit、global cursor和云端route/state/history count/端点规则不变。不宣称远端逐metric独立二次比对。无sync-all、不删原SDK、不拿directory顺序猜role/精度/记录数。

资源继续原16CPU自动内存、RSS12GiB、whole/private各2GiB；audit900s/20min、每SDK180s完整scan；sync3300s/1h及原fixture setup<=30s。旧包内SB的nodes/ntasks历史字节保留，新真实提交用Root已成熟canonical auto CPU薄SB（无mem/exclusive、清SBATCH_*、合法cpu2/8–19、鲜MemAvailable/quota/身份），不要把旧内嵌SB误报为新版canonical。无新增QA父或监控层。

## 4. 真实缺口与最终拼接

尚缺bf16 seed0剩余到20k、seed1两条真实20k曲线及相应所有实际closed段的独立SDK差集/官方同步证明。最终Root将四个实际final member rawrefs、整条resume/COMPLETE/source/C0/监督/储存/dtype和已闭SDK证据表精确拼接，再运行原report；数值失败如实保留，不改门、不选seed/point。

原report已是所需数值入口，没有必要重写gate或另造manager。本次只交路径/CLI/实际refs的非执行性说明；未来有限selector的实际ID/终态/新source pins未发生，保持未填，待Root依据真实闭合记录机械prepare。当前B128GiB持有、训练/控制器/活跃029、canonical/reporting和所有原SDK/产物均未触碰。S fallback结果不获得D5人口、最终精度采用或指南全部完成资格。
