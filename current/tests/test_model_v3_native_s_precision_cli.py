"""CPU-only CLI/protocol/source admission tests; no CUDA or jobs are mocked."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).absolute().parents[2]
TOOLS = ROOT / 'tools/model_v3'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import run_native_s_precision as cli


def test_cli_production_defaults_and_explicit_source_scope():
    args = cli.parser().parse_args(['member', '--input', 'existing_native_S', '--precision', 'bf16',
        '--seed', '1', '--output', '/tmp/not_executed', '--code-sha', 'a' * 40, '--prereg-sha', 'b' * 40])
    assert args.updates == 20000 and args.until_update is None and not args.deterministic_controls
    assert args.storage_hook is None and args.resume_checkpoint is None
    assert cli.production_protocol()['D5_authority'] is False


@pytest.mark.parametrize('key,value', [('updates', 6000000), ('validation_noise_seed', 42),
    ('validation_role', 'TRAIN_UNSEEN_CONFORMATION'), ('validation_records', 240000), ('D5_authority', True)])
def test_serialized_protocol_drift_rejected(key, value, tmp_path):
    data = cli.production_protocol()
    data[key] = value
    path = tmp_path / 'changed.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='protocol differs'):
        cli.production_protocol(path)


def test_sources_bind_original_native_reader_configs_and_new_controller():
    sources = cli.collect_native_sources()
    for path in ('tools/model_v3/s_input_stream.py', 'workflows/sprime_s/scripts/s_native_adapter_v1.py',
        'workflows/sprime_s/scripts/s_native_adapter_v2.py', 'workflows/sprime_s/scripts/s_loader_recovery_v2.py',
        'tools/model_v3/native_runtime_bindings.py', 'workflows/sprime_s/formal_s/B1_seed0_v2.json',
        'current/phychem_mfm/phase1/v3_native_s_precision.py'):
        assert sources[path] == cli.digest(ROOT / path)


def test_missing_or_changed_long_run_storage_hook_is_internal_dependency(tmp_path):
    args = SimpleNamespace(storage_hook=None, storage_hook_sha256=None)
    with pytest.raises(ValueError, match='not a D5 dependency'):
        cli.load_storage_hook(args, {})
    path = tmp_path / 'hook.py'
    path.write_text('raise RuntimeError("must not execute unpinned source")\n')
    args.storage_hook, args.storage_hook_sha256 = path, 'a' * 64
    with pytest.raises(ValueError, match='source differs'):
        cli.load_storage_hook(args, {})


def test_pinned_storage_request_and_bound_policy_are_explicit(tmp_path):
    path = tmp_path / 'hook.py'
    path.write_text('''class Bound:
    binding = {"scope": "unit_storage_policy_only", "total_byte_limit": 123}
    def guard(self, action, experiment): pass
    def close(self): pass
def bind_native_s_precision_storage(request):
    assert request["scope"] == "unit_not_D5"
    return Bound()
''')
    value = cli.load_storage_hook(SimpleNamespace(storage_hook=path, storage_hook_sha256=cli.digest(path)),
                                  {'scope': 'unit_not_D5'})
    assert value.binding['scope'] == 'unit_storage_policy_only'
    value.close()
