"""Prepare the prescribed C arm from the actual current M1, without new fitting."""
import copy,json,pickle
import numpy as np
from resources import REPO,R as ROOT,CONTROL,load,save,guard
from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_training import head_layout
from phychem_mfm.phase1.p_recipe import selected_training_fields

def main():
 guard();path=REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/M1.json';base=load(path);c=copy.deepcopy(base)
 # Runtime recovery/control keys belong to M1's run, not a fresh scientific arm.
 removed=[]
 for k in ['resume','resume_samples','resume_from_output','attempt','replaces_run','predecessor_samples','restart_reason','recovery_reason','handoff_request','handoff_ack','required_gpu_uuid']:
  if k in c:removed.append(k);c.pop(k)
 rule=load(REPO/'configs/p_followup/C_preregistration.json');c['p_recipe']['excluded_fields']=rule['excluded_fields']
 c.update(run='p_followup_20261116_C_dedup',arm='C',output='/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/p_followup_20261116/C_dedup',run_prefix='p_followup_20261116_',results_directory='results/p_followup',control_directory=str(CONTROL))
 assert (c['samples'],c['batch_size'],c['microbatch_size'],c['lr'],c['seed'],c['activation_checkpointing'])==(3000000,32,32,.0003,0,False)
 view=TrainingView(load(c['root']+'/schema.json'),load(c['training_view']),load(c['normalizations']));fields=[f for f in view.fields if f['group']=='P'];selected=[f for f in fields if f['name'] not in rule['excluded_fields']]
 assert len(fields)==109 and len(selected)==99
 heads,_,_,_,_=head_layout(view,selected);assert len(heads)==87
 actual={f['name'] for f in fields};assert set(rule['excluded_fields'])<=actual
 with (ROOT/'runs/p_data_information_20261115_v1/source_graph_scalars.pkl').open('rb') as stream:source=pickle.load(stream)
 comparisons={}
 for n in ['P.pm7_anion.r194.value','P.pm7_cation.r263.value','P.pm7_octanol.r330.value','P.pm7_water.r397.value']:
  matches=valid=0;largest=0.
  for role,molecules in source.items():
   for rows in molecules.values():
    for r in rows.values():
     a,b=r.get(n),r.get('P.pm7_B.r43.value')
     if a is None or b is None:continue
     a,b=np.float32(a),np.float32(b)
     if not np.isfinite(a) or not np.isfinite(b):continue
     valid+=1;matches+=int(a.tobytes()==b.tobytes());largest=max(largest,float(abs(float(a)-float(b))/abs(float(b))) if b else (0. if a==0 else float('inf')))
  comparisons[n]=dict(common_records=valid,bitwise_equal_records=matches,maximum_relative_difference=largest,descriptive_only=True)
 result=dict(status='C1_C2_READY',baseline_configuration=str(path),baseline_commit='e1926db',configuration='configs/p_followup/C_dedup.json',excluded_fields=rule['excluded_fields'],stored_fields=99,physical_loss_fields=87,loss_denominator='Existing M1 physical-head equality gives87 terms; user clarification pending before C/D launch',source_values='Existing original F64 graph cache cast once to F32; earlier all-record source/pilot match reused',volume_comparisons=comparisons,removed_M1_runtime_keys=removed,scientific_changes=['p_recipe.excluded_fields'],new_fit=False,mainline_modified=False,sidecar_enabled=False)
 save(REPO/'configs/p_followup/C_dedup.json',c);save(REPO/'results/p_followup/C_preparation.json',result)
 lines=['# C：去冗余侧线臂','','状态：C1–C2准备完成，C3待3M训练与既定R1/R3评价。','','以当前固定B32的临时M1（仅含A1）为基底，排除任务书的10个字段。其余科学配置不变；独立seed0、3M、首32样本及1M/2M/3M完整保存，FP32/TF32关闭，不接入sidecar。M1恢复链执行键仅从新臂配置移除，不改变或恢复M1。','','## 损失口径','','用户2026-11-17确认：99个存储字段对应87个物理损失项。保留原三轴向量组合及M1物理头等权；共同缺失处理保持原实现，不将99列误当99个独立损失项。','','## 限定的描述性体积核对','','复用冻结42961条记录的原图标量缓存，单次F32 cast与pilot的既有逐记录匹配已由前研究完成。不重读全库、不为本结论另设门槛；下表不改变排除清单。','','|字段|共同记录|逐位相同|最大相对差|','|---|---:|---:|---:|']
 lines.extend(f'|{n}|{r["common_records"]}|{r["bitwise_equal_records"]}|{r["maximum_relative_difference"]:.9g}|' for n,r in comparisons.items())
 lines+=['','## 评价与判定','','3M后只运行主线同一R1/R3，C减M1按主线配对bootstrap计算95%CI；R3区间全正为win、全负为loss，其余tie。win/tie只形成去冗余建议，实际接入主线仍由用户确认。VAL逐字段原单位MAE只作描述。A4改变基底时保留M1证据范围，不自动重跑。']
 guard();(REPO/'docs/p_followup/C_DEDUP.md').write_text('\n'.join(lines)+'\n');print('C_PREPARED',99,87,flush=True)
if __name__=='__main__':main()