"""An explicit taskbook timebox disposition must preserve the scientific record."""
import csv
import importlib.util
import json
from pathlib import Path

import pytest


def tool(name):
    path = Path(__file__).resolve().parents[2] / 'tools/p_recipe' / (name + '.py')
    spec = importlib.util.spec_from_file_location('test_unresolved_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def study(tmp_path, monkeypatch):
    module = tool('decide_round')
    monkeypatch.setattr(module, 'REPO', tmp_path)
    paths = []
    for arm, score in (('B0', .30), ('A1', .40), ('A2', None)):
        output = tmp_path / 'training' / arm
        config = dict(arm=arm, run='fixed_' + arm, output=str(output),
                      components=[] if arm == 'B0' else [arm])
        path = tmp_path / (arm + '.json')
        path.write_text(json.dumps(config))
        paths.append(str(path))
        if score is not None:
            (output / 'readout').mkdir(parents=True)
            value = dict(mean_normalized_improvement=score,
                         paired_bootstrap=dict(values=[score] * 1000))
            (output / 'readout/scores.json').write_text(json.dumps(dict(R3=value, R1=value)))
    plan = dict(round=1, baseline='B0', baseline_components=[], configurations=paths,
                study_revision='fixed', results_directory='results/fixed')
    return module, plan


def test_explicit_unresolved_arm_keeps_reason_without_a_fabricated_comparison(tmp_path, monkeypatch):
    module, plan = study(tmp_path, monkeypatch)
    plan['unresolved_arms'] = {'A2': 'Taskbook timebox: node I/O unresolved; live process retained.'}
    state = module.close(plan, None, 12.)
    assert state['adopted_winners'] == ['A1']
    assert state['decisions']['A1']['delta'] == pytest.approx(.10)
    assert 'A2' not in state['decisions'] and 'A2' not in state['component_evidence']
    assert state['unresolved_arms']['A2']['reason'] == plan['unresolved_arms']['A2']
    assert state['unresolved_arms']['A2']['run'] == 'fixed_A2'
    assert state['best_single_run'] == 'fixed_A1'
    with (tmp_path / 'results/fixed/deltas.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2 and {row['A'] for row in rows} == {'fixed_A1'}
    assert not (tmp_path / 'training/A2').exists()


def test_missing_scores_without_an_explicit_disposition_still_require_completion(tmp_path, monkeypatch):
    module, plan = study(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        module.close(plan, None, 12.)
    assert not (tmp_path / 'results/fixed/deltas.csv').exists()


@pytest.mark.parametrize('arm, reason, message', [
    ('A1', 'Already scored', 'completed readout'),
    ('B0', 'Missing baseline', 'baseline cannot'),
    ('A9', 'Unknown arm', 'Unknown unresolved'),
    ('A2', '  ', 'recorded reason'),
])
def test_timebox_cannot_hide_scored_evidence_or_remove_the_baseline(tmp_path, monkeypatch, arm, reason, message):
    module, plan = study(tmp_path, monkeypatch)
    plan['unresolved_arms'] = {arm: reason}
    with pytest.raises(ValueError, match=message):
        module.close(plan, None, 12.)


def test_unresolved_candidates_leave_the_baseline_and_empty_round_rule_intact(tmp_path, monkeypatch):
    module, plan = study(tmp_path, monkeypatch)
    plan['configurations'] = [path for path in plan['configurations'] if Path(path).stem != 'A1']
    plan['unresolved_arms'] = {'A2': 'Timebox reached without readout evidence.'}
    state = module.close(plan, None, 12.)
    assert state['best_single_run'] == 'fixed_B0'
    assert state['adopted_winners'] == [] and state['merged_components'] == []
    assert state['consecutive_empty_rounds'] == 1
    assert state['screening_gpu_hours'] == 12. and not state['screening_finished']


def test_final_arm_table_reports_unresolved_and_untriggered_arms_without_numbers():
    module = tool('render_report')
    state = dict(round=1, decisions={}, adopted_winners=[],
                 unresolved_arms={'A2': dict(reason='I/O timebox unresolved.')},
                 skipped_arms={'A5': 'Registered D2 trigger absent.'})
    rows = module.screening_rows([state], Path('unused_deltas.csv'), {})
    by_arm = {row[1]: row for row in rows}
    assert by_arm['A2'][2:6] == ['—', '—', '未解决', '否']
    assert by_arm['A2'][6] == 'I/O timebox unresolved.'
    assert by_arm['A5'][2:6] == ['—', '—', '条件未触发', '否']
