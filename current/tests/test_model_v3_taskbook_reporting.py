import csv
import importlib.util
import io
from pathlib import Path


def module(path, name):
    repo = Path(__file__).absolute().parents[2]
    spec = importlib.util.spec_from_file_location(name, repo / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_training_tail_uses_last_complete_record(tmp_path):
    collector = module('tools/model_v3/v2_collect_runs.py', 'v2_collect_runs')
    path = tmp_path / 'losses.csv'
    path.write_text('samples,updates,total,element,noise,bond,preclip_norm,lr,seconds\n'
                    '32,1,1,1,1,1,1,.0001,2.5\n64,2,')
    assert collector.last_training_row(path) == dict(samples=32, updates=1, seconds=2.5)


def test_taskbook_run_summary_is_allowed_without_digest_columns():
    collector = module('tools/model_v3/v2_collect_runs.py', 'v2_collect_runs_format')
    checker = module('tools/check_repository.py', 'repository_taskbook_checker')
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=collector.FIELDS)
    writer.writeheader()
    row = dict.fromkeys(collector.FIELDS, '')
    row.update(run_id='S_C1_0_seed0', stage=5, samples=32, updates=1,
               slurm_job_id=12345, status='RUNNING')
    writer.writerow(row)
    raw = output.getvalue().encode()
    assert checker.model_summary_csv('results/model_v3_v2_runs.csv', raw)
    assert not checker.model_summary_csv('results/model_v3_v2_runs.csv', b'raw,data\n1,2\n')
