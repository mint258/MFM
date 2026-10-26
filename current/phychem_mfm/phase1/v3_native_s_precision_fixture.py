"""Tiny explicit fixtures for the native-S lifecycle; never a real source."""
from .v3_contract import canonical_hash, require
from .v3_native_s_precision_data import runtime_module, source_registry, bridge_native_corpus
from .v3_structural import StructuralViewConfig


class SyntheticNativeSInputs:
    scope = 'synthetic_native_fixture'

    def __init__(self, *, seed):
        self.seed, self.committed, self.read_cursor = seed, 0, 0
        self.sampler = self
        self.data_version = 'synthetic_native_precision_fixture_v1_not_D5'
        self.registry, self.structural_binding = source_registry(self.data_version)
        self.model_configuration = {'architecture': {'preset': 'shared_light'},
            'backbone': {'dim': 512, 'layers': 1, 'heads': 8, 'ff_mult': 2, 'n_atom_types': 119},
            'head': {'profile': 'phase1', 'geometry_head': 'equivariant_noise', 'geometry_hidden_dim': 16,
                     'geometry_message_layers': 0, 'geometry_pair_chunk_size': 8192}}
        self.loss_mapping = {'denoise_sigma': .1, 'geom_angle_std_deg': 0., 'geom_bond_scale_std': 0.}
        self.bindings = {'scope': self.scope, 'validation_records': 3, 'physical_source_authority': False,
                         'geometry': 'synthetic_fixture_coordinates', 'seed': seed}
        self.closed = False

    @property
    def content_sha256(self):
        return canonical_hash({'scope': self.scope, 'seed': self.seed, 'records_per_batch': 3})

    @property
    def samples_consumed(self):
        return self.committed * 3

    def state_dict(self):
        return {'contract_sha256': self.content_sha256, 'samples_consumed': self.samples_consumed,
                'committed_batches': self.committed}

    def load_state_dict(self, state):
        require(state['contract_sha256'] == self.content_sha256 and state['samples_consumed'] == state['committed_batches'] * 3,
                'Fixture sampler cursor differs')
        self.committed = self.read_cursor = state['committed_batches']

    def _prepare(self, corpus, *, role, seed):
        return bridge_native_corpus(corpus, config=StructuralViewConfig(seed=seed), data_version=self.data_version,
                                    role=role, fixture=True)

    def next_train(self):
        corpus = runtime_module('profile_s_baseline').synthetic_corpus(self.seed, self.read_cursor)
        self.read_cursor += 1
        return corpus, self._prepare(corpus, role='TRAIN', seed=self.seed)

    def commit(self, corpus):
        expected = tuple(f'synthetic-{self.committed}-{i}' for i in range(3))
        require(corpus.record_keys == expected, 'Fixture commit is not the next actual batch')
        self.committed += 1

    def probe_train(self, corpus, maximum=4):
        return self._prepare(corpus, role='TRAIN', seed=self.seed)

    def validation_batches(self):
        corpus = runtime_module('profile_s_baseline').synthetic_corpus(0, 999)
        yield self._prepare(corpus, role='PRETRAIN_VAL', seed=0)

    def close(self):
        self.closed = True
