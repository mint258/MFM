"""Correct E1 verdict metadata to the frozen S rule without new arithmetic."""
import json
from pathlib import Path
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
from e1_reporting_20261126 import apply_s_verdict,DECISION_AUTHORITY
names=('test_subthreshold_negative_frozen_ci_is_s_loss_without_mutating_provider',
    'test_subthreshold_negative_full_ci_excludes_a_cell_under_s_rule',
    'test_smallest_nonloss_and_unselected_win_needs_no_seed1',
    'test_selected_win_remains_provisional','test_both_panels_required',
    'test_off_by_default_and_no_ensemble_ci_substitution')
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(
    'test_e1_reporting_20261126.Reporting.'+name) for name in names)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
marker=C/'E1_S_rule_correction_20261127_COMPLETE.json'
deliveries=[]
if not marker.exists():
    for k in (1,2):
        path=R/'results/s_recipe'/f'S_E1_k{k}_s0_3M.json'
        value=json.loads(path.read_text())
        for key,old in value['paired_frozen_vs_k10'].items():
            corrected=apply_s_verdict(old)
            if corrected['decision']['verdict']!=old['decision']['verdict']:
                raise ValueError('Current delivered verdict unexpectedly changed; inspect its existing scalar result')
            value['paired_frozen_vs_k10'][key]=corrected
        value['decision_metadata_correction']=dict(authority=DECISION_AUTHORITY,
            original_delta_CI_and_verdict_unchanged=True,**execution_fields())
        write(path,value)
        deliveries.append(str(path))
    doc=R/'docs/s_recipe/E1_FROZEN_PROGRESS.md'
    text=doc.read_text()
    text=text.replace('没有重抽、重拟合或选层。','判定沿用S任务书4.4，CI上界<0即LOSS。没有重抽、重拟合或选层。')
    doc.write_text(text)
    write(marker,dict(status='FROZEN_S_VERDICT_RULE_RESTORED',deliveries=deliveries,
        original_result_verdicts_changed=[],new_bootstrap_draws=0,new_fits=0))
value=dict(status='COMPLETE',new_tests=2,affected_existing_tests=4,total_tests=6,
    **execution_fields(),authority=DECISION_AUTHORITY,corrected_deliveries=deliveries,
    original_result_verdicts_changed=[],new_bootstrap_draws=0,new_fits=0,
    scope='Existing S LOSS rule restored; P original retained-draw delta/CI/tau reused, no raw score/prediction/checkpoint reread')
write(C/'e1_s_rule_check_20261127.json',value)
write(R/'results/s_recipe/e1_s_rule_check_20261127.json',value)
print(json.dumps(value),flush=True)
