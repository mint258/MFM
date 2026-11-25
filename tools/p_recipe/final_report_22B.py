"""22/22B/22C final-report consumers. No fits, resampling or checkpoint hashes."""
import csv,json
from pathlib import Path

TASKS={'qm9.U0_atom','qm9.homo','exp.LogD','exp.LogS'}
H_SOURCES={a+'_'+str(n)+'M' for a in ('T1','T2') for n in (1,3,6,9)}
B4_SOURCES={'round2_M1','round2_B4','round2_B3','round3_M2'}
MEAN_METRICS=('CEV','CEV_size','CVF','CVF_res','PR')

class ReportNotReady(ValueError):pass

def valid_timebox_skip(value):
 if not isinstance(value,dict) or value.get('status')!='UNRESOLVED_SKIPPED':return False
 if value.get('failure_category') not in {'scientific','method'}:return False
 return (value.get('timebox_scope')=='scientific_diagnosis_or_repair'
         and (value.get('same_root_cause_failed_repairs',0)>=2
              or value.get('diagnosis_repair_seconds_excluding_queue_compute',0)>=14400))

def metric_present(row,name):
 return row.get(name) not in (None,'') or bool(row.get('metric_undefined_reasons',{}).get(name))

def metric_rows_ok(rows,sources):
 for source in sources:
  mean=[x for x in rows if x.get('source')==source and x.get('representation')=='mean(H)']
  atom=[x for x in rows if x.get('source')==source and x.get('representation')=='atomic(H)']
  if len(mean)!=1 or len(atom)!=1:return False
  if any(not metric_present(mean[0],k) for k in MEAN_METRICS):return False
  if not metric_present(atom[0],'EEV'):return False
 for row in rows:
  if row.get('representation')=='atomic(H)' and any(row.get(k) not in (None,'') for k in MEAN_METRICS):return False
 return True

def intervention_ready(value,arm):
 if not isinstance(value,dict):return False
 if valid_timebox_skip(value):return True
 if value.get('status')!='COMPLETE' or value.get('frozen_recipe_changed') is not False:return False
 a,b=value.get('candidate',{}),value.get('baseline',{})
 if a.get('arm')!=arm or b.get('arm')!='F2':return False
 if any(x.get('samples')!=3000000 or x.get('source_training_budget')!=3000000 for x in (a,b)):return False
 if not isinstance(value.get('conditional_seed1_required'),bool):return False
 count=value.get('pretraining_seed_count')
 if count not in (1,2) or (value.get('conditional_seed1_required') and (count!=2 or not value.get('conditional_seed1_complete'))):return False
 verdict=value.get('verdict');recommend=value.get('rule_recommendation')
 if verdict=='win' and (count!=2 or not value.get('conditional_seed1_complete')):return False
 if arm=='I1' and verdict=='loss' and recommend!='RETAIN':return False
 if arm=='I2' and recommend!=('ADOPT' if verdict=='win' else 'NOT_ADOPT'):return False
 return verdict in {'win','tie','loss'} and recommend in {'DROP','RETAIN','ADOPT','NOT_ADOPT'}

def validate_bundle(b):
 errors=[]
 def need(condition,label):
  if not condition:errors.append(label)
 budget=b.get('budget') or {}
 need(budget.get('status')=='COMPLETE' and budget.get('closed_readouts')==22 and len(budget.get('closed_original_9M_arms',[]))==5,'22 budget readouts and five endpoints')
 need(b.get('budget_task_rows')==486,'486 original task-score rows')
 h=b.get('H_comp') or {}
 need(h.get('status')=='COMPLETE' and h.get('atomic_metrics')==['EEV'],'22C composition definitions')
 need(metric_rows_ok(b.get('H_comp_rows',[]),H_SOURCES),'all eight H-comp checkpoints, atomic EEV only')
 need(metric_rows_ok(b.get('A2_rows',[]),B4_SOURCES),'initial four H-B4 checkpoints, atomic EEV only')
 a1=b.get('A1') or {};need(a1.get('status')=='COMPLETE' and a1.get('all_source_count')==4 and a1.get('current_decision_rules_changed') is False,'four completed A1 sources')
 a3=b.get('A3') or {};need(a3.get('status')=='COMPLETE' and len(a3.get('rows',[]))==4 and a3.get('current_recipe_changed') is False,'A3 four original penalty primaries')
 f2=b.get('F2') or {};need(f2.get('status')=='COMPLETE_BASE60' and f2.get('base_fits')==60,'base F2 sixty fits')
 need(isinstance(b.get('F1'),dict) and len(b.get('F_rows',[]))>=108,'F1 interpretation and complete base F table')
 a6=b.get('A6') or {};need(a6.get('status')=='COMPLETE' and a6.get('new_GPU_R3_cells')==16 and len(a6.get('rows',[]))==32 and len(a6.get('molecule_count_effect',[]))==8,'A6 four-source labels comparison')
 a5=b.get('A5') or {}
 need(valid_timebox_skip(a5) or (a5.get('status')=='COMPLETE' and a5.get('common_cohort_verified') is True and a5.get('full_inchikey_exact_join') is True),'A5 completed common geometry or authorized timebox exception')
 a4=b.get('A4') or {}
 need(a4.get('status')=='COMPLETE' and bool(a4.get('source_delivery')) and bool(a4.get('rows')) and a4.get('new_computation_performed') is False,'external D section5 A4 delivery, no P-side refit')
 for arm in ['I1']+(['I2'] if a3.get('I2_condition',{}).get('I2_triggered') is True else []):
  decision=b.get(arm) or {};need(intervention_ready(decision,arm),arm+' original decision and conditional-seed closure')
  if valid_timebox_skip(decision):continue
  ft=b.get(arm+'_F') or {};comp=b.get(arm+'_composition') or {}
  if not valid_timebox_skip(ft):
   full=[x for x in ft.get('rows',[]) if x.get('condition')=='full_'+arm+'_3M']
   frozen=[x for x in ft.get('rows',[]) if x.get('condition')=='frozen_'+arm+'_3M']
   need(ft.get('status')=='COMPLETE' and ft.get('source_training_budget')==3000000 and {x.get('task') for x in full}==TASKS and len(full)==4 and all(x.get('seed_count')==3 for x in full) and {x.get('task') for x in frozen}==TASKS and len(frozen)==4 and all(x.get('seed_count')==1 for x in frozen),arm+' full12 and reused frozen readout')
   keys={(x.get('condition'),x.get('task')) for x in b.get('F_rows',[])}
   need(all((x.get('condition'),x.get('task')) in keys for x in ft.get('rows',[])),arm+' complete exported F rows')
  if not valid_timebox_skip(comp):
   need(comp.get('status')=='COMPLETE' and comp.get('atomic_metrics')==['EEV'] and metric_rows_ok(comp.get('rows',[]),{'F2_3M',arm+'_3M'}),arm+' own-budget baseline composition and atomic EEV')
 if errors:raise ReportNotReady('Final REPORT waits for: '+'; '.join(errors))
 return b

def require_closed(repo):
 repo=Path(repo)
 e1=repo/'configs/p_recipe/E1_k_star.json'
 if not e1.is_file() or json.loads(e1.read_text()).get('status')!='COMPLETE':
  raise ReportNotReady('Final REPORT waits for: E1 original registered conformer-count study closure')
 from e1_report import validate_closed
 value=json.loads(e1.read_text())
 try:validate_closed(value)
 except ValueError as error:raise ReportNotReady('Final REPORT waits for: '+str(error)) from error
 d=repo/'results/p_recipe/fixed_20261115/analysis_20261122';k=repo/'results/p_recipe/fixed_20261115/confirmation'
 def read(path):
  return json.loads(path.read_text()) if path.is_file() else None
 def rows(path):
  if not path.is_file():return []
  with path.open() as stream:return list(csv.DictReader(stream))
 b=dict(budget=read(k/'budget_curve_summary.json'),budget_task_rows=len(rows(k/'budget_curve_tasks.csv')),
  H_comp=read(d/'H_comp_joint.json'),H_comp_rows=rows(d/'H_comp.csv'),A2_rows=rows(d/'A2.csv'),
  A1=read(d/'A1_primary.json'),A3=read(d/'A3_primary.json'),F1=read(d/'F1_interpretation.json'),
  F2=read(d/'F2_full60_complete.json'),F_rows=rows(d/'F.csv'),A6=read(d/'A6_primary.json'),
  A5=read(d/'A5_primary.json') or read(d/'A5_unresolved.json'),A4=read(d/'A4_descriptor_upper_controls.json'))
 for arm in ['I1','I2']:
  b[arm]=read(d/(arm+'_decision.json'));b[arm+'_F']=read(d/(arm+'_F_primary.json'));b[arm+'_composition']=read(d/(arm+'_composition_primary.json'))
 b['E1']=value
 return validate_bundle(b)

def number(value):
 return '—' if value in (None,'') else format(float(value),'.8g')

def table(headers,rows):
 def cell(x):return str(x).replace('|','\\|').replace('\n',' ')
 return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(map(cell,row))+' |' for row in rows])

def interval(row,low='CI_low',high='CI_high'):
 return '['+number(row.get(low))+', '+number(row.get(high))+']'

def render_sections(repo,b):
 validate_bundle(b);d='../../results/p_recipe/fixed_20261115/analysis_20261122/'
 text=['## 微调与冻结读出','',
 'F：原开发划分与四任务固定；full/top2/scratch为三种子、50轮、批32、FP32/TF32关闭；编码器lr1e-4、头lr1e-3，AdamW wd0.01、betas(0.9,0.999)，5% warmup后cosine至0，内部10%按seed20261112选轮。frozen复用原seed0、30轮常数lr的R3，协议差异保留。',
 '点估计采用三个种子分数均值及标准差；CI是三个种子平均预测的分数，不是种子均值的CI。bootstrap为1,000次整分子配对、seed20261025。τ=max(0.01,0.05×较大S)，S以共同scratch为参照；随机编码器frozen E_ref分数另列。区间跨0不证明等效，也不单独证明信息未丢失。','',
 f'[完整F表]({d}F.csv)；[F1预注册解释]({d}F1_interpretation.json)；[F2原60次]({d}F2_full60_complete.json)。full只有1/3/6/9M观测，不能定位恰好4M平台。','',
 table(['B4对照/U0','full三种子点差','τ','full均预测95%CI','frozen点差'],[[x['comparison'],number(x['full']['delta_seed_mean']),number(x['full']['tau']),interval(x['full'],'ensemble_ci_lower','ensemble_ci_upper'),number(x['frozen']['delta_seed_mean'])] for x in b['F2'].get('B4_U0_observations',[])]),'',
 '两处基底逐项报告，不能统一归因为冻结读出的限制。T2−T4的full、frozen与模式差分详见F2_remaining_pairs.json和F2_remaining_mode_interactions.json。','',
 '### 原T2九百万轨迹：四任务观测','',
 f'![原T2九百万轨迹的四任务full/frozen观测]({d}F_T2_full_frozen_trajectories.png)','',
 '图中误差条是三个微调种子的标准差，非均预测bootstrap CI；frozen只有原读出seed0。只观察1/3/6/9M，top2只有端点；原冻结/微调训练协议差异保持。','',
 '### 下游标签数：A6','',
 'QM9按原SHA256排序从fold0 TRAIN取嵌套8,192/30,000组，优化组数为7,372/27,000；原2,048评价组及DFT几何不变。T5/T6/T2的预训练分子数分别25万/50万/全量1,194,228，均是原9M预算。读出种子0，随机编码器初始化seed20261025。原8,192主统计直接复用，各标签预算有自己的匹配随机编码器E_ref。','',
 table(['预训练分子数对比','任务','8192 Δ [95%CI]','30000 Δ [95%CI]'],[[x['comparison'],x['task'],number(x['8192']['delta'])+' '+str(x['8192']['ci95']),number(x['30000']['delta'])+' '+str(x['30000']['ci95'])] for x in b['A6']['molecule_count_effect']]),'',
 f'[32行原单位误差与分数]({d}A6.csv)。两个标签预算的原draw序列不同，未制造跨预算差分CI；只比较点差变化及各预算内部的配对区间，结论依任务而异。','',
 '## 读出噪声与B4机制','',
 table(['来源','预算','五种子均值','种子std','std/seed0 CI半宽','提议多种子'],[[x['source'],x['source_training_budget'],number(x['score_seed_mean']),number(x['score_seed_std']),number(x['std_over_seed0_bootstrap_halfwidth']),x['propose_multiseed_readout']] for x in b['A1']['rows'] if x.get('primary_mean')]),'',
 f'逐任务噪声见[A1.csv]({d}A1.csv)。达到τ/2时仅提议今后多种子，不改本次判定。','',
 '### 组成信息','',
 'mean(H)沿用collapse_composition.py的CEV、CEV_size、CVF、CVF_res和参与率；原子H只报告EEV，不改称原子CEV，也不新增原子CVF/CVF_res/参与率。固定5000 VAL、L6/H0与原构象，F64及1,000整分子bootstrap保持。H-comp、H-B4判定只使用mean(H)CEV。','',
 'H-comp：'+b['H_comp']['H_comp']['decision']+'；H-B4：'+b['H_comp']['H_B4']['decision']+'。','',
 f'[八断点全部指标]({d}H_comp.csv)；[H-comp原配对]({d}H_comp_joint.json)；[H-B4与后续诊断]({d}A2.csv)。其余指标只描述，不改变判定。','',
 table(['断点','hinge','decorrelation','0.1 B4','P总损失','0.1 B4 / P'],[[x['checkpoint_samples'],number(x['hinge']),number(x['decorrelation']),number(x['weighted_B4']),number(x['P_loss']),number(x['weighted_B4_over_P'])] for x in b['A3']['rows']]),'',
 'A3按原B32批量与逐分子加权聚合后取比，未重拟合gamma、未给虚构CI。I2触发记录：'+json.dumps(b['A3']['I2_condition'],ensure_ascii=False)+'。','']
 for arm in ['I1']+(['I2'] if b['A3']['I2_condition']['I2_triggered'] else []):
  decision=b[arm]
  text+=['### '+arm+'：注册3M干预','']
  if valid_timebox_skip(decision):
   text+=['按任务书实现/修复时间盒记UNRESOLVED，原输出与成本保留，按未胜出处理。'];continue
  text+=['对照复用round4_F2自身预算完整退火的3M，干预也是自身3M；原11-07 P归一化保持，B32/FP32、单次32、无累积/逐层重算。只有注册改动项不同。前150k clip281.7，60k–150k裁剪前范数p99随后固定，每臂实际阈值记录原样报告。','',
   '原判定：'+decision['verdict']+'；种子数：'+str(decision['pretraining_seed_count'])+'；规则建议：'+decision['rule_recommendation']+'。采用仍留用户，未自行修改冻结配方。','',
   table(['预训练种子','来源','实际clip p99','原始报告'],[[seed,kind,number(item['report']['threshold']),item['path']] for seed,pair in decision.get('gradient_clip_reports',{}).items() for kind,item in pair.items()]),'',
   f'[原判定与完整来源]({d}{arm}_decision.json)；[full与原frozen]({d}{arm}_F_primary.json)；[mean指标与原子EEV]({d}{arm}_composition_primary.json)。full仍是原四任务、三个微调种子，不拿9M中间3M当完整3M基线。','']
 text+=['## P与Pprime的几何对照','',
 '原9M对照沿原几何。A5只限ExpansionRx LogD/LogS/Log_HLM_CLint，QM9不做此项，保持DFT。','']
 if valid_timebox_skip(b['A5']):
  x=b['A5'];text+=['A5按同一根因的科学/方法失败时间盒记UNRESOLVED（工程失败不计）。只完成全InChIKey目录匹配，未接收UFF共同人群和原子映射，没有同UFF几何的T2−T4读出/Δ/CI，不能声称已排除几何因素。',
   f'[失败原因、原输出与成本]({d}A5_unresolved.json)。全键匹配数量不是UFF最终可用人群数量。','']
 else:
  a5=b['A5'];pairs={(r['task'],r['geometry']):r for r in a5['rows']}
  def paired_cell(task,geometry):
   row=pairs[task,geometry]
   return number(row['delta'])+' ['+', '.join(number(v) for v in row['ci95'])+']'
  text+=[table(['任务','原几何 T2−T4 Δ [95%CI]','同一封存UFF T2−T4 Δ [95%CI]'],
   [[task,paired_cell(task,'original'),paired_cell(task,'sealed_UFF_common')]
    for task in ['exp.LogD','exp.LogS','exp.Log_HLM_CLint','three_task_mean']]),'',
   '共同UFF人群接收'+str(a5['accepted_members'])+'，两臂同时剔除'+str(a5['excluded_members'])+'；原因：'+json.dumps(a5['exclusion_reasons'],ensure_ascii=False)+'。原几何列沿用原闭合主表及其保留draws；UFF列两臂使用同一合格人群。','',
   '预注册描述：'+a5['interpretation']+'。冻结配方、T4判定和seed1触发均不改变。','',
   f'[封存S-prime UFF共同人群、排除数及配对Δ/CI]({d}A5_primary.json)。','']
 text+=['### D第5节直接描述符与组成参照','',
 '以下仅转录D线已闭合交付，P侧不重拟合；覆盖与不可比较任务按原交付标识。','',
 f'[逐任务上限参照与R3落后标记]({d}A4_descriptor_upper_controls.json)。来源：'+str(b['A4']['source_delivery'])+'。','',
 '新增章节消费已闭合主统计；不重跑旧读出、不另生成bootstrap、也不重算P归一化。','']
 if b.get('E1') is not None:
  from e1_report import render as render_e1
  text+=['',render_e1(b['E1'])]
 return '\n'.join(text)
