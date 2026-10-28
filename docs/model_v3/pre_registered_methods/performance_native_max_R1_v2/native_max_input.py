"""Selected native maximum-count input; not an A sampler or capacity qualifier."""
from __future__ import annotations

import array
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import time

B = Path('/share/home/zixiao/descriptor_analysis')
N = B / 'runs/model_v3_20261026'
ROOT = B / 'MFM_model_v3_performance_integration_v1'
HERE = Path(__file__).absolute().parent
CODE = '9e16d4c5a15c558051499d3dc0c55c9bd3787734'
PUBLIC = '8147f44baa1ea1ecc3822af7affd0a95401ed248'
GPU = 'GPU-c35f2434-9137-9723-1af5-dc69b6295243'
KIND = 'native_train_global_max_singleton_R1_v1'
ROWS = 11_104_772
COUNT_BYTES = 44_419_088
MAX_N = 712
VIEWS = 3
META_CAP = 2 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def deadline_check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Bounded native maximum probe deadline reached')


def identity(path):
    value = Path(path).lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_uid == 1278 and value.st_nlink == 1,
            'Owned ordinary single-link file required')
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def bind(raw, maximum=META_CAP, deadline=None):
    require(type(raw) is dict and set(raw) == {'path', 'bytes', 'sha256'},
            'Exact path/bytes/sha256 rawref required')
    path = Path(raw['path'])
    require(path.is_absolute() and type(raw['bytes']) is int and 0 < raw['bytes'] <= maximum,
            'Bounded absolute rawref required')
    before = identity(path)
    require(before[2] == raw['bytes'], 'Raw byte count differs')
    hasher = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == before[:2], 'File changed before opening')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                if deadline is not None:
                    deadline_check(deadline)
                hasher.update(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    require(before == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            == identity(path) and hasher.hexdigest() == raw['sha256'],
            'Exact raw file changed')
    return path


def reference(path, maximum=META_CAP):
    path = Path(path)
    before = identity(path)
    require(0 < before[2] <= maximum, 'Output/source reference bound exceeded')
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            hasher.update(block)
    require(identity(path) == before, 'Reference changed while hashing')
    return dict(path=str(path), bytes=before[2], sha256=hasher.hexdigest())


def read(raw):
    path = bind(raw)
    def unique(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def write(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    require(len(payload) <= META_CAP, 'Bounded metadata output required')
    with Path(path).open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)


def verify_sources(expected, deadline):
    pin = reference(HERE / 'source_pins.json')
    require(pin['sha256'] == expected, 'Explicit source package rawSHA differs')
    pins = read(pin)
    require(pins['schema'] == 'model_v3_native_max_R1_sources_v1', 'Exact source schema required')
    for item in pins['files']:
        require(Path(item['path']) == HERE / item['relative_path'], 'Package leaf location differs')
        bind({k: item[k] for k in ('path', 'bytes', 'sha256')}, deadline=deadline)
    deps = json.loads((HERE / 'dependencies.json').read_bytes())
    require(deps['runtime_root'] == str(ROOT) and deps['code_sha'] == CODE
            and deps['public_prereg_sha'] == PUBLIC and deps['producer_kind'] == KIND,
            'Fixed immutable performance runtime required')
    for raw in deps['raw_refs'].values():
        bind(raw, deadline=deadline)
    pub = read(deps['raw_refs']['publication'])
    qa = read(deps['raw_refs']['CPU_99_Root_closure'])
    pack = read(deps['raw_refs']['packaging_Root_closure'])
    require((pub['local_code_sha'], pub['public_commit_sha'], pub['tree_sha']) ==
            (CODE, PUBLIC, deps['tree_sha']) and pub['actual_public_git_tree'] == deps['tree_sha']
            and pub['actual_readback'][deps['branch']] == PUBLIC
            and pub['force'] is False and pub['main_modified'] is False,
            'Actual tested/public performance tree differs')
    require(pub['Root_CPU_closure'] == deps['raw_refs']['CPU_99_Root_closure']
            and pub['packaging_Root_closure'] == deps['raw_refs']['packaging_Root_closure']
            and qa['status'] == 'ACTUAL_C0_99_TESTS_FOUR_GROUPS_AND_REPOSITORY_CHECKER'
            and qa['counts'] == dict(tests=99, passed=99, failures=0, errors=0, skipped=0)
            and pack['CPU_99_test_closure'] == deps['raw_refs']['CPU_99_Root_closure']
            and pack['status'] == 'ACTUAL_C0_METADATA_ATTRIBUTE_ONLY_MODEL13_SOURCES_AND99_TESTS_PRESERVED',
            'Actual CPU/public source closure differs')
    # This is the existing complete tested 2131-file projection. Root validates
    # HEAD/tree/clean and publication before submission; compute hashes bytes.
    mapping = pack['full_current_source_map']
    require(type(mapping) is dict and len(mapping) == 2131, 'Complete tested source projection required')
    for path, sha in mapping.items():
        deadline_check(deadline)
        actual = reference(path, 16 << 20)
        require(actual['sha256'] == sha, 'Complete tested source graph changed')
    counts = read(deps['raw_refs']['counts_Root_closure'])
    require(counts['schema'] == 'model_v3_geometry_precommit_counts_Root_closure_v1'
            and counts['status'] == 'ACTUAL_C0_GEOMETRY_REPOSITORY_CHECKER_AND_FULL_TRAIN_COUNTS_500_PREFIX_SOURCE_CLOSED'
            and counts['counts_before_after_raw_and_source_match'] is True
            and counts['global_counts']['records'] == ROWS
            and counts['global_counts']['max_native_atoms'] == MAX_N
            and counts['global_counts']['views_per_base_record'] == VIEWS
            and counts['global_counts']['maximum_singleton_padded_cost'] == VIEWS * MAX_N**2,
            'Actual full TRAIN count evidence differs')
    gate = read(deps['raw_refs']['head_off_R2_qualification'])
    require(gate['schema'] == 'model_v3_Root_head_off_R2_full_A_numeric_closure_v1'
            and gate['status'] == 'ACTUAL_GPU_C0_HEAD_OFF_R2_FULL20_500_NUMERIC_SOURCE_RESOURCE_CLOSED'
            and gate['code_sha'] == CODE and gate['public_prereg_sha'] == PUBLIC
            and gate['resident_models'] == 2 and gate['manual_checkpoint_policy'] == 'manual'
            and gate['resolved_checkpoint_flags'] == dict(distance=True, backbone=True, head=False),
            'Actual head-off numeric qualification differs; it is not R1 capacity')
    require(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID')
            and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) == 16
            and socket.gethostname().split('.')[0] == os.environ['MODEL_V3_EXPECTED_NODE'] == 'compute-0-21'
            and os.environ['CUDA_VISIBLE_DEVICES'] == os.environ['MODEL_V3_GPU_UUID'] == GPU,
            'Owned exact CPU16/node21/C35 allocation required')
    require(int(os.environ['MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES']) == (2 << 30) - (96 << 20),
            'Preserve the original supervisor-derived child ceiling')
    frames = {}
    for prefix in ('MODEL_V3_ROOT_ADMISSION', 'MODEL_V3_QUOTA', 'MODEL_V3_HOLD', 'MODEL_V3_METHOD_PUBLICATION'):
        path = Path(os.environ[prefix + '_PATH'])
        raw = reference(path)
        require(raw['sha256'] == os.environ[prefix + '_SHA256'], 'Actual Root frame rawSHA differs')
        frames[prefix] = raw
    return pin, deps, frames


def select_maximum(deps, output, deadline):
    """Full-count scan only, before Torch import/CUDA/model construction."""
    raw = deps['atom_counts']
    require(raw['bytes'] == COUNT_BYTES and COUNT_BYTES == 4 * ROWS, 'Exact TRAIN counts size required')
    manifest = read(deps['raw_refs']['S_manifest'])
    require(manifest['roles']['train']['records'] == ROWS, 'Actual TRAIN role size differs')
    item, = [x for x in manifest['references'] if x['role'] == 'train' and x['kind'] == 'atom_counts']
    require({k: item[k] for k in ('path', 'bytes', 'sha256')} == raw,
            'Counts must be the exact declared TRAIN source')
    path = Path(raw['path'])
    before = identity(path)
    require(before[2] == COUNT_BYTES, 'Actual counts bytes differ')
    maximum, number, digest = 0, 0, hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            deadline_check(deadline)
            require(len(block) % 4 == 0, 'Truncated counts')
            digest.update(block)
            values = array.array('I')
            values.frombytes(block)
            require(values.itemsize == 4, 'Platform uint32 width differs')
            if sys.byteorder != 'little':
                values.byteswap()
            require(values and min(values) > 0, 'Invalid native atom count')
            maximum = max(maximum, max(values))
            number += len(values)
    require(number == ROWS and maximum == MAX_N and digest.hexdigest() == raw['sha256']
            and identity(path) == before, 'Full TRAIN maximum/raw hash differs')
    target = output / 'global_max_ordinals.u32'
    first, ties, ordinal, digest2, selected_sha = None, 0, 0, hashlib.sha256(), hashlib.sha256()
    with path.open('rb') as stream, target.open('xb') as destination:
        for block in iter(lambda: stream.read(1 << 20), b''):
            deadline_check(deadline)
            digest2.update(block)
            values = array.array('I')
            values.frombytes(block)
            if sys.byteorder != 'little':
                values.byteswap()
            chosen = bytearray()
            for offset, count in enumerate(values):
                if count == maximum:
                    if first is None:
                        first = ordinal + offset
                    chosen.extend(struct.pack('<I', ordinal + offset))
                    ties += 1
            require(4 * ties <= COUNT_BYTES, 'Bounded maximum-ordinal inventory exceeded')
            destination.write(chosen)
            selected_sha.update(chosen)
            ordinal += len(values)
        destination.flush()
        os.fsync(destination.fileno())
    require(target.stat().st_size == 4 * ties, 'Actual ordered maximum inventory byte count differs')
    require(first is not None and ties > 0 and ordinal == ROWS
            and digest2.hexdigest() == raw['sha256'] and identity(path) == before,
            'Counts changed during exact ordered tie selection')
    selection = dict(schema='model_v3_native_global_max_selection_v1', producer_kind=KIND,
        original_counts=raw, counts_identity=list(before), full_TRAIN_records=ROWS,
        maximum_native_atoms=maximum, all_maximum_tie_count=ties,
        ordered_all_maximum_ordinals=dict(path=str(target), bytes=4 * ties, sha256=selected_sha.hexdigest()),
        selected_logical_ordinal=first, selection_policy='first_global_maximum_ordinal_no_search_or_substitution',
        selected_base_records=1, actual_views_expected=VIEWS, expected_dense_shape=[VIEWS, maximum],
        expected_padded_cost=VIEWS * maximum**2, all_TRAIN_payloads_read=False,
        production_sampler_changed=False, original_sampler_trajectory=False,
        universal_8M_capacity_coverage=False, automatic_capacity_qualification=False)
    return selection, write(output / 'selection.json', selection)


def open_native_input(reference_config, selection, selection_ref, deps):
    """Use unchanged native record/transport/three-view implementations."""
    from profile_s_baseline import digest
    from s_input_stream import SInputStream
    from s_native_adapter_v2 import MappedRecordIndex, ManifestViewsDataset, identity as native_identity
    from native_runtime_bindings import bind_original_snapshot
    from phychem_mfm.phase1.full_corpus_loader import _load_bound_native_transport, NATIVE_TRANSPORT_POLICY

    class MaximumNativeInput(SInputStream):
        def __init__(self):
            self.iterator = self.dataset = self.index = self.count_index = self.sampler = None
            self.committed_base_samples = 0
            self.selected_ordinal = selection['selected_logical_ordinal']
            self.read_count = 0
            self.seed = 0
            try:
                protocol_ref = reference_config['frozen_protocol_reference']
                require(digest(protocol_ref['path']) == protocol_ref['sha256'], 'Frozen native protocol changed')
                protocol = json.loads(Path(protocol_ref['path']).read_bytes())
                transport = protocol['draft_provenance']['runner_artifacts']['native_transport']
                binding = dict(policy=NATIVE_TRANSPORT_POLICY, source_sha256=transport['sha256'])
                native = _load_bound_native_transport(Path(transport['path']), binding, native_identity(transport['path']))
                manifest_ref = deps['raw_refs']['S_manifest']
                require(digest(manifest_ref['path']) == reference_config['input_manifest_sha256']
                        == manifest_ref['sha256'], 'Exact original TRAIN manifest required')
                snapshot, snapshot_ref = bind_original_snapshot(
                    deps['raw_refs']['S_original_snapshot']['path'], deps['raw_refs']['S_original_snapshot']['sha256'])
                self.index = MappedRecordIndex('train', binding, snapshot, verify_hashes=True)
                require(len(self.index) == ROWS and self.index.atoms_ref['sha256'] == deps['atom_counts']['sha256'],
                        'Real TRAIN index differs from full-count selection')
                actual = self.index.ref(self.selected_ordinal)
                require(actual.native_n_atoms == MAX_N, 'Selected actual native record is not the global maximum')
                self.dataset = ManifestViewsDataset(self.index, native_transport=native,
                    native_transport_binding=binding, seed=0, noise_seed_includes_epoch=True,
                    **reference_config['views'])
                self.dataset.set_epoch(0)
                require([cfg.mode for cfg in self.dataset.cfgs] == ['clean', 'geom', 'topo']
                        and len(self.dataset.cfgs) == VIEWS
                        and all(cfg.topo_delete_frac == cfg.geom_angle_std_deg == cfg.geom_bond_scale_std == 0
                                for cfg in self.dataset.cfgs),
                        'Original non-cropping/count-preserving native three-view policy required')
                self.bindings = dict(producer_kind=KIND, input_kind='native_s', seed=0, epoch=0,
                    manifest=manifest_ref, original_shard_snapshot=snapshot_ref, native_transport=transport,
                    selection=selection_ref, views=reference_config['views'],
                    original_sampler_used=False, direct_CPU_reader_workers=0,
                    original_A_loader_queue_or_8M_stream_capacity_claimed=False)
            except BaseException as original:
                try:
                    self.close()
                except BaseException as cleanup:
                    raise original from cleanup
                raise

        def next(self):
            from phychem_mfm.phase1.full_corpus_loader import collate_native_views
            item = self.dataset[self.selected_ordinal]
            require(item.logical_index == self.selected_ordinal and item.native_n_atoms == MAX_N
                    and len(item.views) == VIEWS, 'Actual native maximum record/views changed')
            corpus = collate_native_views([item])
            require(corpus.logical_indices == (self.selected_ordinal,)
                    and corpus.native_atom_counts == (MAX_N,) and corpus.padded_cost(VIEWS) == 1_520_832,
                    'Maximum molecule may not be cropped, replaced, duplicated or regrouped')
            self.read_count += 1
            return corpus

    return MaximumNativeInput()
