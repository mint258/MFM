"""The requested raw perf CSVs are admitted without admitting dataset CSVs."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('repository_check',Path(__file__).parents[2]/'tools/check_repository.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)


def test_real_closed_timing_and_telemetry_artifacts_are_allowed():
    root=Path(__file__).parents[2]
    paths=list((root/'results/model_v3_perf_20261112/profiling_4530262').rglob('*.csv'))
    assert len(paths)==5
    for path in paths:
        assert check.model_summary_csv(path.relative_to(root).as_posix(),path.read_bytes())


def test_numeric_dataset_and_nonfinite_or_unknown_perf_schemas_stay_excluded():
    path='results/model_v3_perf_20261112/profiling_4530262/segments/summary.csv'
    assert not check.model_summary_csv('data/train.csv',b'Z,target\n6,1.0\n')
    assert not check.model_summary_csv(path,b'Z,target\n6,1.0\n')
    assert not check.model_summary_csv(path,b'stage,median_seconds,share_of_measured_time\nforward,nan,0.2\n')
    assert not check.model_summary_csv(path,b'stage,median_seconds,share_of_measured_time\nunknown,0.2,0.2\n')
