"""The model metrics exception must not admit raw datasets or credentials."""
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).absolute().parents[2]
spec = importlib.util.spec_from_file_location('model_summary_repository_check', ROOT / 'tools/check_repository.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def summary(**overrides):
    row = dict(run_id='unit_run', stage='4', config_sha256='a'*64,
               code_sha='b'*40, data_version='synthetic-unit-v1', seed='0',
               gpu_model='CPU', elapsed_seconds='2.5', status='COMPLETED',
               preregistration_sha='c'*40, metric__synthetic_MAE='0.1')
    row.update(overrides)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader(); writer.writerow(row)
    return stream.getvalue().encode()


def test_summary_exception_has_exact_location_and_schema():
    raw = summary()
    assert checker.model_summary_csv('docs/model_v3/results/runs.csv', raw)
    assert not checker.model_summary_csv('data/runs.csv', raw)
    assert not checker.model_summary_csv('docs/model_v3/results/nested/runs.csv', raw)
    assert not checker.model_summary_csv('docs/model_v3/results/../runs.csv', raw)
    assert not checker.model_summary_csv('docs/model_v3/results/runs.csv', b'smiles,target\nCCO,1\n')
    assert not checker.model_summary_csv('docs/model_v3/results/runs.csv', summary(smiles='CCO'))


@pytest.mark.parametrize('changes', [dict(config_sha256='x'), dict(code_sha='unknown'),
    dict(seed='-1'), dict(elapsed_seconds='nan'), dict(metric__synthetic_MAE='inf'),
    dict(metric__synthetic_MAE='CCO'), dict(status='PASS_WITHOUT_RUN'),
    dict(peak_memory_bytes='-1'), dict(peak_memory_bytes='1.5'),
    dict(allocated_cpu_seconds='0.5'), dict(denoise_rmse='-0.1'),
    dict(throughput_molecules_s='-1')])
def test_summary_types_are_not_an_arbitrary_csv_whitelist(changes):
    assert not checker.model_summary_csv('docs/model_v3/results/runs.csv', summary(**changes))


def test_credential_scan_still_applies_to_admitted_summary(tmp_path):
    path = 'docs/model_v3/results/runs.csv'
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/SOURCE_MANIFEST.json').write_text(json.dumps({'files': []}))
    (tmp_path / path).parent.mkdir(parents=True)
    # Construct the test credential at runtime so the source checker itself
    # does not find a literal credential-looking string in this fixture.
    (tmp_path / path).write_bytes(summary(data_version='gh' + 'p_' + 'a'*30))
    result = checker.check(tmp_path, [path], verify_export=False)
    assert result['status'] == 'FAIL'
    assert any('credential' in error['reason'] for error in result['errors'])


def test_oversized_and_duplicate_run_summaries_are_rejected():
    path = 'docs/model_v3/results/runs.csv'
    raw = summary()
    header, row = raw.split(b'\r\n', 1)
    assert not checker.model_summary_csv(path, header + b'\r\n' + row + row)
    assert not checker.model_summary_csv(path, b' '*(128*1024+1))
