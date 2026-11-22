"""Critical final-report readiness rules; synthetic metadata only."""
from copy import deepcopy
from pathlib import Path
import pytest
import final_report_22B as report

def metrics(sources):
 rows=[]
 for source in sources:
  rows += [dict(source=source,representation='mean(H)',CEV=.2,CEV_size=.1,CVF=.02,CVF_res=.03,PR=5.),dict(source=source,representation='atomic(H)',EEV=.4)]
 return rows

def ready():
 ft=[dict(condition=prefix+'_I1_3M',task=t,seed_count=count) for prefix,count in [('full',3),('frozen',1)] for t in sorted(report.TASKS)]
 base=[dict(condition='base'+str(n),task=t) for n in range(27) for t in sorted(report.TASKS)]
 return dict(budget=dict(status='COMPLETE',closed_readouts=22,closed_original_9M_arms=['T1','T2','T4','T5','T6']),budget_task_rows=486,
  H_comp=dict(status='COMPLETE',atomic_metrics=['EEV']),H_comp_rows=metrics(report.H_SOURCES),A2_rows=metrics(report.B4_SOURCES),
  A1=dict(status='COMPLETE',all_source_count=4,current_decision_rules_changed=False),A3=dict(status='COMPLETE',rows=[{}]*4,current_recipe_changed=False,I2_condition=dict(I2_triggered=False)),
  F1={},F2=dict(status='COMPLETE_BASE60',base_fits=60),F_rows=base+ft,A6=dict(status='COMPLETE',new_GPU_R3_cells=16,rows=[{}]*32,molecule_count_effect=[{}]*8),
  A5=dict(status='UNRESOLVED_SKIPPED',attempts=[{},{}],stop_reason='Two implementation failures'),
  A4=dict(status='COMPLETE',source_delivery='closed D fixture',rows=[{}],new_computation_performed=False),
  I1=dict(status='COMPLETE',candidate=dict(arm='I1',samples=3000000,source_training_budget=3000000),baseline=dict(arm='F2',samples=3000000,source_training_budget=3000000),frozen_recipe_changed=False,pretraining_seed_count=1,conditional_seed1_required=False,conditional_seed1_complete=False,verdict='loss',rule_recommendation='RETAIN'),
  I1_F=dict(status='COMPLETE',source_training_budget=3000000,rows=ft),
  I1_composition=dict(status='COMPLETE',atomic_metrics=['EEV'],rows=metrics({'F2_3M','I1_3M'})))

def test_current_incomplete_scopes_cannot_be_promoted():
 b=ready();b['I1']=None;b['A4']=None
 with pytest.raises(report.ReportNotReady) as error:report.validate_bundle(b)
 assert 'I1 original decision' in str(error.value) and 'external D section5' in str(error.value)

def test_no_9M_midpoint_baseline_or_unconfirmed_WIN():
 b=ready();assert report.validate_bundle(b) is b
 b['I1']['baseline']['source_training_budget']=9000000
 with pytest.raises(report.ReportNotReady):report.validate_bundle(b)
 b=ready();b['I1'].update(verdict='win',rule_recommendation='DROP')
 with pytest.raises(report.ReportNotReady):report.validate_bundle(b)
 b['I1'].update(pretraining_seed_count=2,conditional_seed1_required=True,conditional_seed1_complete=True)
 assert report.validate_bundle(b) is b

def test_atomic_CEV_is_rejected_and_explicit_undefined_metric_is_reportable():
 b=ready();atom=next(x for x in b['H_comp_rows'] if x['representation']=='atomic(H)');atom['CEV']=.1
 with pytest.raises(report.ReportNotReady):report.validate_bundle(b)
 b=ready();mean=next(x for x in b['I1_composition']['rows'] if x['representation']=='mean(H)')
 mean.update(CEV=None,metric_undefined_reasons={'CEV':'Native zero variance'})
 assert report.validate_bundle(b) is b

def test_training_duration_is_not_implementation_timebox():
 assert report.valid_timebox_skip(ready()['A5'])
 assert not report.valid_timebox_skip(dict(status='UNRESOLVED_SKIPPED',timebox_scope='training',training_seconds=50000))
 b=ready();b['I1_F']['rows'][0]['seed_count']=2
 with pytest.raises(report.ReportNotReady):report.validate_bundle(b)

def test_renderer_blocks_before_original_artifacts_or_hashes(tmp_path,monkeypatch):
 import render_report
 directive=tmp_path/'docs/p_recipe/USER_DIRECTIVE_20261122B.md';directive.parent.mkdir(parents=True);directive.write_text('fixture')
 monkeypatch.setattr(render_report,'REPO',tmp_path)
 def forbidden(*args,**kwargs):pytest.fail('Original report producer accessed before new scope closed')
 monkeypatch.setattr(render_report,'completed_configurations',forbidden)
 monkeypatch.setattr(render_report,'checkpoint_sha',forbidden)
 with pytest.raises(report.ReportNotReady):render_report.render({}, {}, [], {}, 'source')
 assert not (tmp_path/'docs/p_recipe/REPORT.md').exists()
