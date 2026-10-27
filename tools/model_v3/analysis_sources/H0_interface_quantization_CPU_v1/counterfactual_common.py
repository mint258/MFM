"""Only typed I/O and metadata comparability; no new model or arithmetic policy."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

B = Path('/share/home/zixiao/descriptor_analysis')
N = B/'runs/model_v3_20261026'
HERE = Path(__file__).absolute().parent
INPUT_CAP = 128*1024**2
REPLAY_BOUND = 1e-10

def need(value, message):
    if not value:
        raise ValueError(message)

def reference(path, cap=2*1024**2):
    path = Path(path).absolute()
    st = path.stat()
    need(path.is_file() and not path.is_symlink() and stat.S_ISREG(st.st_mode)
         and st.st_nlink == 1 and st.st_uid == os.getuid() and st.st_size <= cap, 'Ordinary bounded input required: '+str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    after = path.stat()
    need((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_uid,after.st_nlink) ==
         (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_uid,st.st_nlink), 'Input identity changed during hash')
    return {'path': str(path), 'bytes': st.st_size, 'sha256': digest.hexdigest()}

def read_json(leaf):
    need(reference(leaf['path']) == leaf, 'Metadata raw reference differs')
    return json.loads(Path(leaf['path']).read_bytes(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def helpers():
    # Verify frozen imports before executing even their metadata-only top level.
    deps = json.loads((HERE/'DRAFT_DEPENDENCIES.json').read_bytes())
    for leaf in deps['implementation_sources']:
        need(reference(leaf['path']) == leaf, 'Frozen implementation source changed')
    facade = load(N/'centered_fixed_H0_diagnostic_v1_source/diagnostic_common.py', '_H0_quantization_frozen_IO')
    return facade, facade.load_shadow()

class Budget:
    def __init__(self):
        self.identities = {}
        self.total = 0
    def add(self, leaf, *, payload=False, hash_payload=True):
        path = Path(leaf['path'])
        st = path.stat()
        need(not path.is_symlink() and stat.S_ISREG(st.st_mode) and st.st_nlink == 1
             and st.st_uid == os.getuid() and st.st_size == leaf['bytes'], 'Raw input stat differs')
        key = (st.st_dev, st.st_ino)
        identity = (str(path), st.st_size, st.st_mtime_ns, leaf['sha256'])
        if key in self.identities:
            need(self.identities[key] == identity, 'Aliased or changed physical input')
        else:
            need(self.total+st.st_size <= INPUT_CAP, 'Combined payload+all selected metadata/source exceeds128MiB')
            self.total += st.st_size
            self.identities[key] = identity
        if not payload or hash_payload:
            need(reference(path, 8*1024**2 if payload else 2*1024**2) == leaf, 'Bound input digest differs')
        return st
    def json(self, leaf):
        self.add(leaf)
        return read_json(leaf)

def equal_case(original, centered, historical):
    """Raw metadata gate; actual typed array validation remains in the CPU job."""
    identity = original['case_id']
    need(identity == centered['case_id'] == historical['case_id'], 'Case identity mismatch')
    need(original['case'] == centered['case'] and original['transforms'] == centered['transforms'],
         'Case/seed/transform/role metadata differ')
    need(centered['centered_lineage'] == 'fresh_centered_capture_not_1776_hidden_H0'
         and centered['same_forward_control'] and original['same_forward_control'], 'Fresh typed bank-input capture required')
    sha = original['original_measurement']['weight_summary']['all_named_parameter_sha256']
    need(sha == historical['original_parameter_sha256'] == centered['original1492_parameter_sha256']
         == centered['original_measurement']['weight_summary']['all_named_parameter_sha256'], 'Full original parameter SHA differs')
    for key in ('bank_state_identity', 'bank_constructor', 'registry', 'forms', 'state_names', 'state_extra', 'state_tensor_bytes'):
        need(original[key] == centered[key], 'Bank state/config differs: '+key)
    for name in original['state_names'].values():
        need(original['packed']['arrays'][name] == centered['packed']['arrays'][name], 'Bank typed tensor header differs')
    for key in ('fixture_geometry_sha256', 'original_physical_geometry_sha256', 'original_view_identity_sha256',
                'encoder_forward_shapes', 'fixture_native_atoms', 'case'):
        need(original['original_measurement'][key] == centered['original_measurement'][key],
             'Actual fixture/view/role geometry metadata differs: '+key)
    need(len(original['calls']) == len(centered['calls']) == 4, 'Four roles required')
    for old, new in zip(original['calls'], centered['calls']):
        need(old == new, 'Role bank-call keys/groups/fields differ')
        # H0/output values intentionally differ; geometry/index inputs must be exact.
        for name in old['keys']:
            if name in ('pos', 'batch') or name.startswith('pair_'):
                need(original['packed']['arrays'][old['keys'][name]] == centered['packed']['arrays'][new['keys'][name]],
                     'Role geometry/index typed header differs')
    nodes = 88 if original['case']['views'] == 'two' else 132
    need(historical['actual_input_only'] is True and historical['ideal_or_polar_coordinate_counterfactual'] is False
         and historical['reference_encoder_input_was_clean44_only'] is False
         and historical['reference_physical_input_nodes_per_role'] == [nodes]*4
         and historical['canonical_PD_nodes_per_role'] == 44, 'Historical F64 reference physical lineage differs')
    return {'case_id': identity, 'parameter_sha256': sha, 'bank_state_identity': centered['bank_state_identity'],
            'role_pos_batch_pair_headers_equal': True, 'old_F64_encoder_is_current_centered_encoder': False}

def load_H64(historical, budget):
    import numpy as np
    import torch
    packed = historical['FP64_clean_H0']
    budget.add(packed['file'], payload=True)
    expected = {'role%d_clean_H0'%role for role in range(4)}
    need(set(packed['arrays']) == expected, 'All four historical H64 roles required')
    rows = []
    with np.load(packed['file']['path'], allow_pickle=False) as archive:
        need(set(archive.files) == expected, 'No extra/untyped historical arrays')
        for role in range(4):
            key = 'role%d_clean_H0'%role
            value, header = archive[key], packed['arrays'][key]
            need(value.dtype == np.float64 and value.shape == (44,512) and value.nbytes == header['bytes']
                 and header['dtype'] == 'torch.float64' and header['shape'] == [44,512]
                 and np.isfinite(value).all() and hashlib.sha256(value.tobytes()).hexdigest() == header['sha256'],
                 'Historical H64 dtype/shape/value hash differs')
            rows.append(torch.from_numpy(value.copy()))
    return rows

def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False, indent=2)+'\n').encode()
    need(len(raw) <= 2*1024**2, 'New metadata exceeds2MiB')
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return reference(path)
def validate_authorities(root64, root32, budget):
    """Use actual raw observations inside the existing Root closures, never invented C0."""
    raw = root64['raw_accounting']
    need(raw['returncode'] == 0 and hashlib.sha256(raw['stdout'].encode()).hexdigest() == raw['stdout_sha256'],
         'Actual1561 raw accounting differs')
    expected = ['sacct','-X','-n','-P','-j','4521561',
                '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,AllocTRES']
    rows = [row.split('|') for row in raw['stdout'].splitlines() if row.strip()]
    need(raw['argv'] == expected and len(rows) == 1 and len(rows[0]) == 8
         and rows[0][:4] == ['4521561','zixiao','COMPLETED','0:0']
         and rows[0][5:7] == ['16','compute-0-21'], 'Actual1561 parent C0 scope differs')
    for root in (root64,root32):
        supervisor = budget.json(root['supervisor'])
        need(supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
             and supervisor['first_failure'] is None
             and supervisor['remaining_recorded_processes_before_retirement'] == []
             and supervisor['private_storage_cleanup_errors'] == [], 'Actual successful input supervisor closure required')
    deps = json.loads((HERE/'DRAFT_DEPENDENCIES.json').read_bytes())
    leaf = next(item for item in deps['implementation_sources'] if item['path'].endswith('/cpu_metadata_v3.py'))
    budget.add(leaf)
    old = load(leaf['path'],'_H0_quantization_original_CPU_metadata')
    old.validate_capture_accounting(budget.json(root32['accounting']),'4521838')