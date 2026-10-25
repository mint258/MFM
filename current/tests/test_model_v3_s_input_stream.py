import importlib.util
from pathlib import Path

import pytest
import torch


def stream_class(monkeypatch):
    folder = Path(__file__).absolute().parents[2] / "tools/model_v3"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location("model_v3_s_stream_test", folder / "s_input_stream.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SInputStream


def test_synthetic_stream_reset_restores_input_ids_and_noise_without_global_rng_use(monkeypatch):
    stream = stream_class(monkeypatch)({}, seed=14, input_kind="synthetic")
    before = torch.get_rng_state().clone()
    first = stream.next()
    stream.next()
    stream.reset()
    restored = stream.next()
    assert first.record_keys == restored.record_keys
    assert torch.equal(first.encoder_batch.pos, restored.encoder_batch.pos)
    assert torch.equal(torch.get_rng_state(), before)
    stream.close()
    assert stream.last_cleanup["input_descriptors_closed"]


def test_failed_iterator_cleanup_does_not_skip_later_owned_closes(monkeypatch):
    stream = stream_class(monkeypatch)({}, seed=1, input_kind="synthetic")
    seen = []
    class Broken:
        def close(self):
            seen.append("iterator")
            raise RuntimeError("intentional close failure")
    class Remaining:
        def close(self):
            seen.append("later_component")
    stream.iterator, stream.dataset = Broken(), Remaining()
    with pytest.raises(RuntimeError, match="intentional"):
        stream.close()
    assert seen == ["iterator", "later_component"]
