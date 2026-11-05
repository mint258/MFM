"""Canonical SDK directories; actual offline SDK layout is tested separately."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).absolute().parents[2]
MONITOR = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py')


def runner():
    spec = importlib.util.spec_from_file_location('model_v3_layout_evaluator', ROOT / 'tools/model_v3/evaluate_dev_panel.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_tracking_layout_uses_canonical_cache_data_and_refuses_redirects(tmp_path, monkeypatch):
    for name in ('WANDB_DIR', 'WANDB_CACHE_DIR', 'WANDB_DATA_DIR', 'WANDB_MODE'):
        monkeypatch.setenv(name, 'caller_value')
    output = tmp_path / 'evaluation'; output.mkdir()
    paths = runner().configure_wandb_layout(output)
    assert paths == {'WANDB_DIR': str(output), 'WANDB_CACHE_DIR': str(output / 'cache'),
                     'WANDB_DATA_DIR': str(output / 'wandb_data')}
    assert all(os.environ[name] == value and Path(value).is_dir() for name, value in paths.items())
    assert os.environ['WANDB_MODE'] == 'offline'
    redirected = tmp_path / 'redirected'; redirected.mkdir()
    (redirected / 'cache').symlink_to(output / 'cache', target_is_directory=True)
    with pytest.raises(ValueError, match='must not be symlinks'):
        runner().configure_wandb_layout(redirected)


def test_actual_offline_sdk_layout_passes_fixed_profiler_accounting(tmp_path):
    """Real installed W&B init/log/finish, not a tracker mock or model run."""
    assert MONITOR.is_file(), 'The Root-validated fixed profiler helper must be present'
    output = tmp_path / 'actual_sdk'; output.mkdir()
    # A fresh process ensures no earlier pytest module imported/configured W&B
    # before the environment helper, and retains the Root's normal dependencies.
    script = r'''
import hashlib, importlib.util, json, pathlib, sys
runner_path, monitor_path, output_text = sys.argv[1:]
output = pathlib.Path(output_text)
spec = importlib.util.spec_from_file_location('actual_layout_runner', runner_path)
runner = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runner; spec.loader.exec_module(runner)
runner.configure_wandb_layout(output)
assert 'wandb' not in sys.modules
import wandb
run = wandb.init(project='model-v3-sdk-layout-synthetic', name='synthetic_layout_only', mode='offline', dir=str(output))
assert run is not None and not run.disabled
run.log({'synthetic_layout_probe': 1.0}, step=0, commit=True)
run.finish(exit_code=0)
spec = importlib.util.spec_from_file_location('fixed_layout_monitor', monitor_path)
monitor = importlib.util.module_from_spec(spec); sys.modules[spec.name] = monitor; spec.loader.exec_module(monitor)
size = monitor.owned_output_bytes(output)
sdk_files = list(output.rglob('*.wandb'))
assert sdk_files and all(path.stat().st_size > 0 for path in sdk_files)
assert size > 0
assert (output/'cache').is_dir() and (output/'wandb_data').is_dir()
print(json.dumps({'status':'REAL_OFFLINE_SDK_LAYOUT_PASS', 'sdk_files':len(sdk_files), 'owned_output_bytes':size,
 'monitor_sha256':hashlib.sha256(pathlib.Path(monitor_path).read_bytes()).hexdigest(),
 'SDK_links':[str(path.relative_to(output)) for path in output.rglob('*') if path.is_symlink()]}))
'''
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'WANDB_MODE': 'offline'}
    result = subprocess.run([sys.executable, '-B', '-c', script,
        str(ROOT / 'tools/model_v3/evaluate_dev_panel.py'), str(MONITOR), str(output)],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout+'\n'+result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report['status'] == 'REAL_OFFLINE_SDK_LAYOUT_PASS' and report['sdk_files'] > 0
