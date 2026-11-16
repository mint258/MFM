"""Report observations keep producer clocks, ownership and missing-data gaps."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('v2_training_report',
    Path(__file__).absolute().parents[2] / 'tools/model_v3/v2_training_report.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_incomplete_json_record_is_not_used(tmp_path):
    path = tmp_path / 'rows.jsonl'
    path.write_text('{"job":1}\n{"job":')
    assert m.closed_json_lines(path) == [dict(job=1)]


def test_missing_metrics_and_long_gaps_are_not_interpolated():
    rows = [dict(observed_at=1, available=True, metrics={'gpu/power_watts': 50}),
        dict(observed_at=31, available=False, metrics={}),
        dict(observed_at=200, available=True, metrics={'gpu/power_watts': 75})]
    _, values = m.system_series(rows, 'gpu/power_watts')
    assert len(values) == 4 and values[0] == 50 and values[-1] == 75
    assert math.isnan(values[1]) and math.isnan(values[2])


def test_report_does_not_replace_progress_clock_with_later_system_clock(tmp_path):
    directory = tmp_path / 'diagnostics/23'
    directory.mkdir(parents=True)
    system = dict(job=23, gpu='GPU-x', node='compute-0-20', observed_at=100.,
        available=True, metrics={'samples/cumulative': 100032, 'gpu/power_watts': 90})
    (directory / 'system_metrics.jsonl').write_text(json.dumps(system)+'\n')
    full = dict(updates=1000, partial=False, last_samples=96000, means={'total': .3})
    partial = dict(updates=5, partial=True, last_samples=100000, means={'total': 99})
    (directory / 'loss_windows.jsonl').write_text(json.dumps(full)+'\n'+json.dumps(partial)+'\n')
    manifest = dict(tracking_root=str(tmp_path), runs=[dict(job=23, gpu='GPU-x', node='compute-0-20')])
    progress = dict(observed_at=99., progress=[dict(job=23, candidate='C1-0', samples=100000, state='RUNNING')])
    rows = m.gather(manifest, progress)
    report = m.markdown(rows, progress)
    assert rows[0]['windows'] == [full]
    assert '| 100,000 | RUNNING | 0.300000 | 96,000 |' in report
    assert '对应样本100032' in report
    system['job'] = 24
    (directory / 'system_metrics.jsonl').write_text(json.dumps(system)+'\n')
    with pytest.raises(ValueError, match='identity'):
        m.gather(manifest, progress)
