"""Panel-v3 historical selections; original v2 results are never rewritten."""
from __future__ import annotations
import itertools
from .v3_selection import paired_difference,select_candidate
from .v3_downstream_targets import PRIMARY_TASK_IDS,REPORT_ONLY_TASK_IDS

def require_panel(panel):
 if (panel.get('panel')!='v3' or not panel.get('complete')
     or set(panel.get('tasks',{}))!=set(PRIMARY_TASK_IDS)
     or panel.get('SoM_selection_use') is not False):
  raise ValueError('Require a complete new seven-task atomization panel')
 return panel

def c1_result(panels):
 if set(panels)!={'C1-0','C1-a','C1-b'} or any(set(value)!={'S','P'} for value in panels.values()):
  raise ValueError('Require all six original C1 checkpoints under the new panel')
 for conditions in panels.values():
  for panel in conditions.values():require_panel(panel)
 decision=select_candidate(panels,('C1-0','C1-a','C1-b'))
 pairs=[dict(A=a,B=b,**paired_difference(panels[a],panels[b]))
  for a,b in itertools.combinations(('C1-0','C1-a','C1-b'),2)]
 return dict(status='C1_SELECTED_PANEL_V3_SEED0',panel='v3',decision=decision,
  pairwise=pairs,historical_18_cell_rank=['C1-a','C1-0','C1-b'],
  rank_differs_from_historical18=decision['ranked']!=['C1-a','C1-0','C1-b'],primary='seven_task_R3_then_equal_S_P',SoM_selection_use=False,
  pretraining_seed=0,model_and_recipe_frozen=False)

def t1_result(panels):
 if set(panels)!={'A0','A1','A2','A3','A4'} or any(set(value)!={'S','P'} for value in panels.values()):
  raise ValueError('Require all ten original paired T1 checkpoints')
 for conditions in panels.values():
  for summaries in conditions.values():
   for panel in summaries.values():require_panel(panel)
 def pick(arm,readout):return {c:panels[arm][c][readout] for c in ('S','P')}
 contrasts=(
  ('primary_A3_vs_A0','A3','R2z','A0','R3'),
  ('parameter_control_A3_vs_A4','A3','R2z','A4','R3'),
  ('readout_A1_vs_A0','A1','R2z','A0','R3'),
  ('exchange_A2_vs_A1','A2','R2z','A1','R2z'),
  ('reconstruction_A3_vs_A2','A3','R2z','A2','R2z'),
  ('information_A3_X_vs_z','A3','R3','A3','R2z'),
  ('linear_A3_vs_A0','A3','R1z','A0','R3'),
  ('fallback_parameter_control_A1_vs_A4','A1','R2z','A4','R3'))
 comparisons={name:dict(A=a,A_readout=ar,B=b,B_readout=br,
  **paired_difference(pick(a,ar),pick(b,br))) for name,a,ar,b,br in contrasts}
 reports={}
 som_rows=[]
 for arm in ('A0','A1','A3'):
  reports[arm]={}
  for condition in ('S','P'):
   report=panels[arm][condition]['R2']['report_only']
   if report.get('selection_use') is not False or set(report['tasks'])!=set(REPORT_ONLY_TASK_IDS):
    raise ValueError('Both original SoM cells remain explicitly report-only')
   reports[arm][condition]=report
   som_rows.extend(dict(arm=arm,condition=condition,task=key,**value)
    for key,value in report['tasks'].items())
 som_comparisons={}
 for arm in ('A3','A1'):
  sources=[reports[a][c] for a in (arm,'A0') for c in ('S','P')]
  exemplar=sources[0]['paired_bootstrap']
  if any(any(source['paired_bootstrap'][key]!=exemplar[key]
      for key in ('groups','seed','samples','confidence')) for source in sources):
   raise ValueError('SoM report source molecule draws must remain aligned')
  available=all(source['complete'] for source in sources) and any(
   all(source['paired_bootstrap']['values'][i] is not None for source in sources) for i in range(1000))
  som_comparisons[arm]=(dict(selection_use=False,status='REPORTED',
   **paired_difference(reports[arm],reports['A0'],expected_task_count=2)) if available else
   dict(selection_use=False,status='UNAVAILABLE',reason='Original SoM metric/draw population unavailable'))
 a3=comparisons['primary_A3_vs_A0']['A_wins'] and comparisons['parameter_control_A3_vs_A4']['A_wins']
 a1=comparisons['readout_A1_vs_A0']['A_wins'] and comparisons['fallback_parameter_control_A1_vs_A4']['A_wins']
 selected='lite_rec' if a3 else 'pma' if a1 else 'none'
 return dict(status='T1_PROVISIONAL_DECISION_PANEL_V3',panel='v3',provisional_latent=selected,
  comparisons=comparisons,SoM_reporting=som_comparisons,SoM_rows=som_rows,SoM_selection_use=False,
  SoM_statistic='native normalized improvements and paired intervals,report only;no adoption veto',
  lambda_k_required=selected=='lite_rec',fresh6M_confirmation_required=selected!='none',
  module_finally_confirmed=False,source_C1_for_paired_checkpoints='C1-0',
  source_roles=['train','train_inner_validation'],downstream_TEST_read=False)
