"""Typed capture I/O and frozen metadata helpers; no model or monitoring loop."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).absolute().parent
B = Path('/share/home/zixiao/descriptor_analysis')
BASE = B/'runs/model_v3_20261026/numeric_composed_GPU_v2_source/run_numeric_matrix_v1.py'
BASE_SHA = '88d97d0bfbca8ef93fdb051bed95a3466867dcfaffcc64f9b6af3f1cd6efaba7'
FIELDS = ('p_extensive', 'p_dipole', 'p_dipole_magnitude')
INPUT_CAP = 128*1024**2
STATE_BYTES = {'H1_fixed': 969892, 'H1_learned': 969924, 'H2_fixed': 1225380, 'H3_fixed': 1488036}


def require(ok, message):
    if not ok: raise ValueError(message)


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ref(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'Ordinary bound file required')
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


require(ref(BASE)['sha256'] == BASE_SHA, 'Fixed actual Git identity helper differs')
_metadata = load_file(BASE, 'fixed_h0_original_metadata_helper_v1')
verify_publication = _metadata.verify_publication
metadata_selfcheck = _metadata.metadata_selfcheck
save_plain = _metadata.save


def bound(leaf):
    require(ref(leaf['path']) == leaf, 'Bound bytes/SHA differ: '+leaf['path'])
    return json.loads(Path(leaf['path']).read_bytes())


def source_snapshot(request, pins_sha):
    pins = bound({**ref(HERE/'source_pins_v1.json'), 'sha256': pins_sha})
    require(pins['schema'] == 'model_v3_fixed_h0_capture_launch_source_pins_v1', 'Dedicated source snapshot required')
    sources = {leaf['path']: leaf for leaf in request['source_refs']+pins['files']+pins['protected_dependencies']}
    sources[str(HERE/'source_pins_v1.json')] = ref(HERE/'source_pins_v1.json')
    for leaf in sources.values(): require(ref(leaf['path']) == leaf, 'Source snapshot drift')
    verify_publication(request)
    return sources


class InputBudget:
    def __init__(self): self.used, self.refs = 0, []
    def reserve(self, upper): require(self.used+upper <= INPUT_CAP, 'Predeclared128MiB input budget exceeded')
    def adopt(self, path):
        leaf = ref(path); self.reserve(leaf['bytes']); self.used += leaf['bytes']; self.refs.append(leaf)
        return leaf
    def json(self, path, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False)+chr(10)).encode()
        self.reserve(len(raw)); save_plain(path, value); return self.adopt(path)
    def npz(self, path, arrays):
        import numpy as np
        headers = {}
        for name, value in arrays.items():
            require(type(name) is str and name.isascii() and len(name) < 128, 'Short typed tensor key required')
            require(value.dtype in (np.dtype('float32'), np.dtype('int64')) and value.ndim <= 3,
                    'Only captured FP32/int64 nonobject tensors allowed')
            require(np.isfinite(value).all(), 'Nonfinite capture tensor')
            headers[name] = {'dtype': value.dtype.str, 'shape': list(value.shape), 'nbytes': value.nbytes,
                             'sha256': hashlib.sha256(value.tobytes(order='C')).hexdigest()}
        numeric = sum(a.nbytes for a in arrays.values())
        self.reserve(numeric+2048*len(arrays)+65536)
        with Path(path).open('xb') as stream:
            np.savez(stream, **arrays); stream.flush(); os.fsync(stream.fileno())
        leaf = self.adopt(path)
        require(leaf['bytes'] <= 8*1024**2, 'Per-case packed capture exceeds8MiB')
        return {'file': leaf, 'arrays': headers, 'numeric_bytes': numeric}


def load_npz(packed):
    import numpy as np
    require(ref(packed['file']['path']) == packed['file'] and packed['file']['bytes'] <= 8*1024**2,
            'Bound small capture NPZ required')
    require(sum(h['nbytes'] for h in packed['arrays'].values()) <= 8*1024**2, 'Typed numeric input exceeds8MiB')
    with np.load(packed['file']['path'], allow_pickle=False) as archive:
        require(len(archive.files) == len(packed['arrays']) and set(archive.files) == set(packed['arrays']), 'Exact typed NPZ keys required')
        values = {}
        for key, header in packed['arrays'].items():
            value = archive[key]
            require(value.dtype.str == header['dtype'] and list(value.shape) == header['shape']
                and value.nbytes == header['nbytes'] and value.dtype in (np.dtype('float32'), np.dtype('int64'))
                and hashlib.sha256(value.tobytes(order='C')).hexdigest() == header['sha256']
                and np.isfinite(value).all(), 'Typed capture dtype/shape/value mismatch')
            values[key] = value.copy()
    return values


def state_arrays(bank):
    import torch
    arrays, names, extras = {}, {}, {}
    for name, value in bank.state_dict().items():
        if isinstance(value, torch.Tensor):
            require(value.dtype == torch.float32, 'Captured bank state must remainFP32')
            key = 'state_%03d' % len(names); names[name] = key
            arrays[key] = value.detach().cpu().contiguous().numpy().copy()
        else:
            require(name == '_extra_state' and isinstance(value, dict), 'Unknown bank extra-state type')
            extras[name] = value
    return arrays, names, extras


def tensor_state_identity(arrays, names, extras):
    payload = {'extras': extras, 'tensors': {name: {'dtype': arrays[key].dtype.str,
        'shape': list(arrays[key].shape), 'sha256': hashlib.sha256(arrays[key].tobytes()).hexdigest()}
        for name, key in sorted(names.items())}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
