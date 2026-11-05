"""Read-only existing-S precision inputs; no D5/PM7/uniform-molecule claim.

The original TRAIN record sampler, native transport and deterministic views are
reused. The already frozen PRETRAIN_VAL selection supplies membership only.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import sys

import torch

from .v3_contract import canonical_hash, require, LabelRegistry, FieldSpec
from .v3_structural import StructuralViews, StructuralViewConfig, StructuralFieldBinding
from .v3_trainer import PreparedV3Batch

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
OLD = PROJECT / 'runs/sprime_s_convergence_20261013/training_inputs_v1'
COHORT = PROJECT / 'runs/model_v3_20261025/c2_prepare_4520477/selection_plan.json'
COHORT_SHA = '9ef81dcd5d3a84411328a76c5fbe7ccf123bc032e72e87a580d0b4c0bdf11e67'
MANIFEST_SHA = '2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997'
REFERENCE_SHA = 'af26f79be41d99bac5de410b686bccdf608b830b772d0dde06491bb146d35324'
SNAPSHOT_SHA = 'd2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f'
POPULATION = PROJECT / 'runs/phase1_wp5_20261011/population/manifest.json'
POPULATION_SHA = 'd21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e'
SCOPE = 'existing_native_S_original_TRAIN_record_sampler_not_D5'
VAL_ROLE = 'PRETRAIN_VAL'


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def source_registry(data_version):
    fields = (FieldSpec('s_element', 'S', 'structural', 'atom', kind='classification', classes=119, unit='element_class'),
        FieldSpec('s_noise', 'S', 'structural', 'atom', kind='denoise_eps_mse', representation='vector', unit='angstrom'),
        FieldSpec('s_bond', 'S', 'structural', 'pair', kind='classification', classes=5, unit='bond_order_class'))
    return LabelRegistry(fields, data_version, digest(__file__)), StructuralFieldBinding('s_element', 's_noise', 's_bond')


def runtime_module(name):
    repo = Path(__file__).absolute().parents[3]
    for directory in (repo / 'tools/model_v3', repo / 'workflows/sprime_s/scripts'):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    value = importlib.import_module(name)
    expected = [directory / (name + '.py') for directory in (repo / 'tools/model_v3', repo / 'workflows/sprime_s/scripts')]
    require(Path(value.__file__).absolute() in expected, 'Native runtime imported from another source tree or archived copy')
    return value


@dataclass(frozen=True)
class NativeRecordChoice:
    logical_index: int
    record_id: str
    molecule_id: str
    native_atoms: int
    geometry_scope: str = 'original_native_record_coordinates_no_D5_source_alias'


def bridge_native_corpus(corpus, *, config, data_version, role, choices=None, fixture=False):
    """Wrap the existing three views without generating, filtering or reordering."""
    batch = corpus.encoder_batch
    count = len(corpus.logical_indices)
    require(count > 0 and batch.num_graphs == 3 * count and batch.x.device.type == 'cpu',
            'CPU original three-view corpus required')
    require(tuple(batch.sample_type_id.reshape(-1).tolist()) == (0, 1, 2) * count,
            'Native clean/geometry/topology view order differs')
    require(len(corpus.record_keys) == len(corpus.native_atom_counts) == count
            and len(set(corpus.logical_indices)) == count, 'Native corpus identity/count mismatch')
    clean_rows, atom_map, base_offset = [], [], 0
    for index, (logical, atoms, key) in enumerate(zip(corpus.logical_indices, corpus.native_atom_counts, corpus.record_keys)):
        # Original fast_collate temporarily renames index attributes. Its slice
        # dictionary is not a public unbatch interface after restoration.
        slices = [slice(int(batch.ptr[3 * index + view]), int(batch.ptr[3 * index + view + 1])) for view in range(3)]
        require(all(value.stop - value.start == atoms for value in slices), 'View changed native atom count')
        require(all(torch.equal(batch.target_x[slices[0]], batch.target_x[value])
                    and torch.equal(batch.target_pos[slices[0]], batch.target_pos[value]) for value in slices),
                'Native targets/order differ across views')
        require(torch.equal(batch.x[slices[0]], batch.target_x[slices[0]])
                and torch.equal(batch.pos[slices[0]], batch.target_pos[slices[0]]),
                'Clean view changed source targets')
        for view, value in enumerate(slices):
            require(torch.equal(batch.x[value].ne(batch.target_x[value]).any(-1),
                                batch.element_corrupt_mask[value].reshape(-1).bool()),
                    'Original element corruption mask differs')
            if not fixture:
                graph = 3 * index + view
                require(batch.pretrain_base_key[graph] == key
                        and int(batch.pretrain_recipe_seed[graph]) == config.noise_seed(int(logical)),
                        'Original native view identity/noise seed differs')
        start, end = int(batch.ptr[3 * index]), int(batch.ptr[3 * index + 1])
        clean_rows.append(torch.arange(start, end))
        atom_map.extend(torch.arange(base_offset, base_offset + atoms) for _ in range(3))
        base_offset += atoms
    views = StructuralViews(batch, torch.cat(clean_rows), torch.arange(0, 3 * count, 3),
        torch.arange(count).repeat_interleave(3), torch.cat(atom_map),
        {name: torch.ones(count, dtype=torch.bool) for name in ('element', 'noise', 'bond')},
        tuple(map(int, corpus.logical_indices)), config, True)
    if choices is None:
        require(fixture, 'Actual record identities must be supplied for native input')
        choices = tuple(NativeRecordChoice(int(i), str(key), 'synthetic_fixture_molecule', int(n), 'synthetic_fixture_coordinates')
                        for i, key, n in zip(corpus.logical_indices, corpus.record_keys, corpus.native_atom_counts))
    require(len(choices) == count and all((choice.logical_index, choice.record_id, choice.native_atoms)
        == (int(i), str(key), int(n)) for choice, i, key, n in zip(choices, corpus.logical_indices,
            corpus.record_keys, corpus.native_atom_counts)), 'Native identity sidecar differs from decoded corpus')
    return PreparedV3Batch(tuple(choices), views, {}, digest(__file__), data_version, role)


class NativeSamplerFacade:
    """Only expose the original sealed committed cursor to safe checkpoint I/O."""
    def __init__(self, stream):
        self.stream = stream

    @property
    def content_sha256(self):
        return self.stream.sampler.contract_sha256

    @property
    def samples_consumed(self):
        return self.stream.committed_base_samples

    def state_dict(self):
        value = self.stream.sampler.state_dict()
        require(value['samples_consumed'] == self.samples_consumed, 'Uncommitted native stream state')
        return value

    def load_state_dict(self, value):
        # reset closes/joins existing speculative prefetch before restoring cursor.
        self.stream.reset()
        self.stream.sampler.load_state_dict(deepcopy(value))
        self.stream.committed_base_samples = value['samples_consumed']


class ExistingNativeSInputs:
    """Actual native source. Shared storage is recorded honestly, never node_local=True."""
    scope, read_only, node_local = SCOPE, True, False

    def __init__(self, *, seed, workers=8, verify_train_disjoint=True):
        require(seed in (0, 1) and type(seed) is int, 'Native precision seed0/1 required')
        repo = Path(__file__).absolute().parents[3]
        self.reference_path = repo / 'workflows/sprime_s/formal_s/B1_seed0_v2.json'
        require(digest(self.reference_path) == REFERENCE_SHA, 'Original S reference configuration changed')
        self.reference = json.loads(self.reference_path.read_text())
        require(digest(OLD / 'manifest.json') == MANIFEST_SHA and digest(COHORT) == COHORT_SHA,
                'Frozen native source/1024 validation membership changed')
        self.train = self.validation_index = self.validation_dataset = None
        self.closed = False
        self.seed, self.workers = seed, workers
        try:
            self.train = runtime_module('s_input_stream').SInputStream(self.reference, seed=seed, input_kind='native_s',
                workers=workers, max_padded_cost=8_000_000, snapshot_sha256=SNAPSHOT_SHA)
            require(len(self.train.index) == 11104772, 'Original native TRAIN count differs')
            # Reuse only the accepted source-role verifier, never a fitted
            # coordinate model, NPZ, metrics or target-based selection.
            from .v3_coordinate_lookup_source import role_evidence
            require(digest(POPULATION) == POPULATION_SHA, 'Original WP5 role/component provenance changed')
            protocol = json.loads(Path(self.reference['frozen_protocol_reference']['path']).read_text())
            role_receipt = role_evidence(self.reference, json.loads((OLD / 'manifest.json').read_text()),
                                         json.loads(POPULATION.read_text()), protocol)
            selection = json.loads(COHORT.read_text())
            self.validation_rows = tuple(selection['records'][VAL_ROLE])
            require(len(self.validation_rows) == 1024 and len({row['record_id'] for row in self.validation_rows}) == 1024,
                    'Exact fixed1024 original PRETRAIN_VAL membership required')
            require(sum(int(row['native_n_atoms']) for row in self.validation_rows) == 55650,
                    'Fixed PRETRAIN_VAL native atom population differs')
            self._open_validation()
            self.disjoint_receipt = self._verify_disjoint() if verify_train_disjoint else None
            # B production must not bypass full TRAIN membership proof.
            require(verify_train_disjoint, 'Full original TRAIN/validation identity disjointness check is mandatory')
            self.data_version = canonical_hash({'scope': SCOPE, 'manifest': MANIFEST_SHA, 'snapshot': SNAPSHOT_SHA,
                'validation_selection': COHORT_SHA, 'validation_role': VAL_ROLE})
            self.registry, self.structural_binding = source_registry(self.data_version)
            a4 = json.loads((repo / 'workflows/s_denoise/configs/A4_seed0_v3.json').read_text())
            self.model_configuration = deepcopy(a4['model'])
            self.model_configuration['backbone'].update(dim=512, layers=6, heads=8)
            self.model_configuration['expert']['heads'] = 8
            self.loss_mapping = {**self.reference['training']['loss'], 'denoise_sigma': .1,
                                 'geom_angle_std_deg': 0., 'geom_bond_scale_std': 0.}
            self.bindings = {'scope': SCOPE, 'geometry': 'native_original_pos_no_PM7_or_Sprime_alias',
                'sampling': 'original_TRAIN_record_natural_counts_not_molecule_uniform',
                'read_only': True, 'node_local': False, 'storage': 'existing_declared_shared_sources',
                'TRAIN': deepcopy(self.train.bindings), 'validation_selection': {'path': str(COHORT), 'sha256': COHORT_SHA},
                'validation_records': 1024, 'validation_atoms': sum(int(row['native_n_atoms']) for row in self.validation_rows),
                'validation_role': VAL_ROLE, 'validation_seed': 0, 'validation_epoch': 0,
                'TRAIN_UNSEEN_CONFORMATION': 'NOT_PROVIDED_D5', 'disjointness': self.disjoint_receipt,
                'original_role_provenance': role_receipt, 'population_manifest_sha256': POPULATION_SHA}
            self.sampler = NativeSamplerFacade(self.train)
        except BaseException as initial:
            try:
                self.close()
            except BaseException as cleanup:
                raise initial from cleanup
            raise

    def _open_validation(self):
        adapter = runtime_module('s_native_adapter_v2')
        binding = self.train.index.manifest['native_transport']
        snapshot = runtime_module('native_runtime_bindings').bind_original_snapshot(OLD / 'shard_snapshot_v1.json', SNAPSHOT_SHA)[0]
        self.validation_index = adapter.MappedRecordIndex('full', binding, snapshot, verify_hashes=True)
        require(len(self.validation_index) == 127082, 'Original full validation role differs')
        # Reuse the exact already verified transport object and original views.
        self.validation_dataset = adapter.ManifestViewsDataset(self.validation_index,
            native_transport=self.train.dataset.native_transport, native_transport_binding=binding,
            seed=0, noise_seed_includes_epoch=True, **self.reference['views'])
        for row in self.validation_rows:
            ref = self.validation_index.ref(row['logical_index'])
            require((ref.record_id, ref.molecule_id, ref.native_n_atoms, ref.payload_sha256)
                == (row['record_id'], row['molecule_id'], row['native_n_atoms'], row['payload_sha256']),
                'Frozen PRETRAIN_VAL native record identity differs')

    def _verify_disjoint(self):
        # Arrow scans only identity metadata. No TRAIN geometry/target is read.
        import pyarrow as pa
        import pyarrow.compute as pc
        molecules = pa.array(sorted({row['molecule_id'] for row in self.validation_rows}))
        records = pa.array([row['record_id'] for row in self.validation_rows])
        count = 0
        with pa.memory_map(str(self.train.index.path), 'r') as source:
            reader = pa.ipc.open_file(source)
            for number in range(reader.num_record_batches):
                batch = reader.get_batch(number)
                for name, values in (('molecule_id', molecules), ('record_id', records)):
                    field_index = batch.schema.get_field_index(name)
                    require(field_index >= 0, 'TRAIN identity column missing')
                    column = batch.column(field_index)
                    require(column.null_count == 0, 'TRAIN identity metadata contains nulls')
                    typed = pa.array(values.to_pylist(), type=column.type)
                    require(not bool(pc.any(pc.is_in(column, value_set=typed)).as_py()), 'Full TRAIN and frozen validation overlap')
                count += batch.num_rows
        require(count == 11104772, 'Full TRAIN metadata scan incomplete')
        return {'TRAIN_records_checked': count, 'validation_records': 1024, 'record_overlap': 0, 'molecule_overlap': 0,
                'metadata_only': True, 'original_split_unchanged': True}

    def _prepared(self, corpus, index, *, role, seed):
        choices = tuple(NativeRecordChoice(int(i), str(key), index.ref(i).molecule_id, int(n))
                        for i, key, n in zip(corpus.logical_indices, corpus.record_keys, corpus.native_atom_counts))
        return bridge_native_corpus(corpus, config=StructuralViewConfig(seed=seed, epoch=0,
            topology_level=self.reference['views']['topology_level'], geometry_level=self.reference['views']['geometry_level']),
            data_version=self.data_version, role=role, choices=choices)

    def next_train(self):
        corpus = self.train.next()
        return corpus, self._prepared(corpus, self.train.index, role='TRAIN', seed=self.seed)

    def commit(self, corpus):
        self.train.commit(corpus)

    def probe_train(self, corpus, maximum=4):
        from .full_corpus_loader import collate_native_views
        indices = corpus.logical_indices[:maximum]
        self.validation_dataset.close()
        try:
            value = collate_native_views([self.train.dataset[index] for index in indices])
            return self._prepared(value, self.train.index, role='TRAIN', seed=self.seed)
        finally:
            # Worker copies are separate processes. Do not retain a second
            # parent-process LMDB environment when validation opens the shard.
            self.train.dataset.close()

    def validation_batches(self):
        # Greedy packing preserves frozen member order and fixed source budgets.
        # It never uses target values, training cursor or model/precision state.
        from .full_corpus_loader import collate_native_views
        self.train.dataset.close()
        try:
            yield from self._validation_batches_impl(collate_native_views)
        finally:
            self.validation_dataset.close()

    def _validation_batches_impl(self, collate_native_views):
        group, atoms, maximum = [], 0, 0
        for row in self.validation_rows:
            n = int(row['native_n_atoms'])
            next_max = max(maximum, n)
            if group and (len(group) + 1 > 512 or atoms + n > 65536 or 3 * (len(group) + 1) * next_max**2 > 8_000_000):
                corpus = collate_native_views([self.validation_dataset[value['logical_index']] for value in group])
                yield self._prepared(corpus, self.validation_index, role=VAL_ROLE, seed=0)
                group, atoms, maximum = [], 0, 0
            group.append(row)
            atoms += n
            maximum = max(maximum, n)
        if group:
            corpus = collate_native_views([self.validation_dataset[value['logical_index']] for value in group])
            yield self._prepared(corpus, self.validation_index, role=VAL_ROLE, seed=0)

    def close(self):
        errors = []
        for name in ('validation_dataset', 'validation_index', 'train'):
            value = getattr(self, name, None)
            if value is not None:
                try:
                    value.close()
                except BaseException as exc:
                    errors.append({'component': name, 'type': type(exc).__name__, 'message': str(exc)})
        self.closed = not errors
        if errors:
            raise RuntimeError('Native input cleanup failed: ' + str(errors))
