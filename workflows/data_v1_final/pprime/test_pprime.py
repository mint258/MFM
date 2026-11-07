"""Controlled serialization/guard checks. No LMDB, QM child, Slurm submission or GPU."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from common import (TASKS, load_config, load_engine, ordered_two, read_staging,
                    stable_key, staging_bytes)
from geometry import adapt_native, geometry_hash, Q02_REASON
from prepare_pilot import stratified_audit
from close_pilot import assess

CONFIG_PATH = None
SB2_SOURCE = None


def specimen():
    import numpy as np
    z = np.asarray([6, 1], dtype='<i8')
    original = {'z': z, 'coords': np.asarray([[0., 0., 0.], [1., 0., 0.]], dtype='<f8'),
                'symbols': ['C', 'H'], 'energy': 5., 'pairs': [(1, 0)],
                'native_atom_order_sha256': hashlib.sha256(z.tobytes()).hexdigest(),
                'native_coordinates_sha256': 'a' * 64}
    coordinates = [[8., 7., 6.], [10., 7., 6.]]
    conf = {'sprime_conf_idx': 3, 'coordinates': coordinates, 'status': 'SUCCESS',
            'converged': True, 'source_record_id': 'source:1',
            'atom_order_sha256': original['native_atom_order_sha256']}
    source = {'record_id': 'source:1', 'molecule_id': 'm1',
              'record_payload_sha256': 'b' * 64, 'source_path': '/external/readonly.lmdb',
              'real_index': 1, 'effective_role': 'TRAIN', 'conformer_id': 3}
    pair = {'record_id': 'pprime:m1:3', 'source': source, 'conformer': conf,
            'bond_pairs': [[0, 1]], 'uff_geometry_sha256': geometry_hash([6, 1], coordinates),
            'uff_coordinate_sha256': hashlib.sha256(np.asarray(coordinates, dtype='<f8').tobytes()).hexdigest()}
    return original, pair


class PprimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG_PATH)
        cls.engine, cls.contract, cls.protocol = load_engine(cls.config)
        cls.engine.CONFIG = cls.protocol
        cls.no_child = patch('subprocess.Popen', side_effect=AssertionError('NO_CHILD_PROCESS_IN_SYNTHETIC_TEST'))
        cls.no_child.start()

    @classmethod
    def tearDownClass(cls):
        cls.no_child.stop()

    def test_fixed_order_matches_actual_sb2_source(self):
        spec = importlib.util.spec_from_file_location('_actual_sb2_order', SB2_SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for mid in ['m1', 'molecule_00000001']:
            for idx in [0, 1, 3, 10]:
                self.assertEqual(stable_key(20261025, mid, 'uff_sprime', idx),
                                 module.stable_key(20261025, mid, 'uff_sprime', idx))

    def test_two_means_two_distinct_usable_conformers(self):
        rows = [{'sprime_conf_idx': i, 'status': 'SUCCESS', 'converged': True} for i in [0, 3, 1]]
        chosen = ordered_two(rows, 'm1')
        self.assertEqual([r['sprime_conf_idx'] for r in chosen],
                         sorted([0, 3, 1], key=lambda i: stable_key(20261025, 'm1', 'uff_sprime', i))[:2])
        with self.assertRaises(ValueError):
            ordered_two(rows[:1], 'm1')
        with self.assertRaises(ValueError):
            ordered_two([rows[0], rows[0]], 'm1')
        with self.assertRaises(ValueError):
            ordered_two([rows[0], dict(rows[1], converged=False)], 'm1')

    def test_geometry_is_uff_and_source_energy_cannot_enter_q02(self):
        import numpy as np
        original, pair = specimen()
        adapted, provenance = adapt_native(original, pair, pair_cutoff_A=1.)
        np.testing.assert_array_equal(adapted['coords'], pair['conformer']['coordinates'])
        np.testing.assert_array_equal(original['coords'], [[0., 0., 0.], [1., 0., 0.]])
        self.assertEqual(adapted['pairs'], [(1, 0)])  # bonded pair retained beyond cutoff
        self.assertIsNone(adapted['energy'])
        self.assertFalse(provenance['Q02_applicable'])
        self.assertEqual(provenance['Q02_reason'], Q02_REASON)
        self.assertEqual(provenance['pm7_source_geometry_sha256'], 'a' * 64)
        self.assertNotEqual(provenance['uff_coordinate_sha256'], 'a' * 64)
        self.assertEqual(original['energy'], 5.)

    def test_changed_coordinate_and_atom_order_rejected(self):
        original, pair = specimen()
        with self.assertRaises(ValueError):
            adapt_native(original, dict(pair, uff_coordinate_sha256='0' * 64))
        bad = dict(pair, conformer=dict(pair['conformer'], atom_order_sha256='0' * 64))
        with self.assertRaises(ValueError):
            adapt_native(original, bad)
        with self.assertRaises(ValueError):
            geometry_hash([6, 1], [[float('nan'), 0., 0.], [1., 0., 0.]])

    def test_actual_wp5_input_serialization_receives_uff(self):
        import numpy as np
        original, pair = specimen()
        native, _ = adapt_native(original, pair)
        row = dict(pair['source'], record_id=pair['record_id'])
        for task in self.protocol['tasks']:
            rendered = self.engine.render_inputs(task, native, row, self.protocol)
            xyz = rendered['input.xyz'].decode().splitlines()[2:]
            observed = np.asarray([[float(v) for v in line.split()[1:]] for line in xyz])
            expected = native['coords'].copy()
            if task.get('perturbed'):
                seed = self.engine.perturb_seed(row['record_id'], self.protocol)
                expected += np.random.default_rng(seed).normal(0, 0.1, expected.shape)
            np.testing.assert_allclose(observed, expected, rtol=0., atol=0.5001e-12)
            self.assertFalse(np.allclose(observed, original['coords']))
            if task['family'] == 'mopac':
                self.assertEqual(rendered['input.mop'].decode().splitlines()[0],
                                 task['keywords'] + ' THREADS=1')

    def test_stratified_one_percent_is_deterministic_and_exact(self):
        rows = [{'record_id': str(i), 'file_group': i % 5, 'size_stratum': str(i % 4)} for i in range(2000)]
        first, second = stratified_audit(rows), stratified_audit(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertEqual(len({r['record_id'] for r in first}), 20)

    def test_json_staging_preserves_nonfinite_bits_and_negative_zero(self):
        original = {'values': [float('nan'), float('inf'), -0.0, 1. / 3.]}
        encoded = staging_bytes(original)
        self.assertNotIn(b'NaN', encoded)
        self.assertNotIn(b'Infinity', encoded)
        decoded = read_staging(encoded)
        self.assertEqual([struct.pack('<d', v) for v in original['values']],
                         [struct.pack('<d', v) for v in decoded['values']])

    def test_real_raw_policy_durable_readback_and_input_rejection(self):
        from raw_archive import RawReader, RawSink
        with tempfile.TemporaryDirectory(prefix='pprime_raw_test_') as tmp:
            sink = RawSink(Path(tmp) / 'raw.sqlite', self.engine.OUTPUT_ARCHIVE, 4 << 20)
            record = {'record_id': 'r', 'calc_type': 'pm7_B', 'execution_id': 'e',
                      'scope_status': 'SUCCESS', 'audit_selected': False, 'files': []}
            self.assertFalse(sink(record)['output_retained'])
            body = b'synthetic output\n'
            member = {'name': 'process.out', 'data': body, 'role': 'output',
                      'sha256': hashlib.sha256(body).hexdigest(), 'byte_count': len(body)}
            audit = dict(record, audit_selected=True, files=[member])
            self.assertTrue(sink(audit)['raw_call_durable'])
            failed = dict(record, execution_id='failed', scope_status='PROPERTY_FAILED', files=[member])
            self.assertTrue(sink(failed)['raw_call_durable'])
            with self.assertRaises(ValueError):
                sink(dict(record, execution_id='input', audit_selected=True,
                          files=[dict(member, name='input.xyz', role='input')]))
            sink.close()
            reader = RawReader(Path(tmp) / 'raw.sqlite', self.engine.OUTPUT_ARCHIVE)
            self.assertEqual(reader.get('r', 'pm7_B', 'e')['output_files'][0]['data'], body)
            self.assertFalse(reader.get('r', 'pm7_B', 'e')['input_bodies_saved'])
            reader.close()

    def test_float64_family_export_roundtrip_and_geometry_metadata(self):
        import pyarrow.parquet as pq
        from export_families import export
        original, pair = specimen()
        native, geom = adapt_native(original, pair)
        record = {'record_id': pair['record_id'], 'molecule_id': 'm1',
                  'source_row': pair['source'], 'geometry': geom, 'lane': 0,
                  'base_geometry': {'z': [6, 1], 'positions_A': native['coords'].tolist()},
                  'tasks': []}
        for task in self.protocol['tasks']:
            detail = {'task': task['name'], 'job_id': '123', 'status': 'SUCCESS',
                      'source_status': 'SUCCESS', 'scope_status': 'SUCCESS',
                      'values': {'heat_of_formation_kcal_mol': 1. / 3.,
                                 'dipole_Debye': [-0.0, 1. / 3., 2.]},
                      'B_base_success': True}
            record['tasks'].append(detail)
        with tempfile.TemporaryDirectory(prefix='pprime_family_test_') as tmp:
            refs, qc = export([record], Path(tmp) / 'parquet', self.engine, 'c' * 64,
                              {'max_output_bytes': 64 << 20})
            self.assertEqual(sum(r['rows'] for r in refs if r['family'] not in {'base_geometry', 'QC'}), 12)
            base = pq.read_table(Path(tmp) / 'parquet/base_geometry.parquet').to_pylist()[0]
            self.assertEqual(struct.pack('<d', base['new_PM7_HOF_kcal_mol']), struct.pack('<d', 1. / 3.))
            self.assertEqual(base['geometry_source'], 'uff_sprime')
            self.assertIsNone(base['Q02_delta_HOF_kcal_mol'])
            self.assertFalse(base['Q02_applicable'])
            self.assertEqual(len(qc), 1)

    def test_actual_parent_allocation_threshold_and_no_batch_double_count(self):
        result = {'runtime': {'job_id': '123', 'node': 'compute-0-14'},
                  'completed_records': 2000, 'status': 'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING',
                  'failures': [], 'all_workers_joined': True, 'record_success_rate': .995}
        parent = {'JobIDRaw': '123', 'User': 'zixiao', 'State': 'COMPLETED', 'ExitCode': '0:0',
                  'ElapsedRaw': '1462', 'AllocCPUS': '16', 'NodeList': 'compute-0-14'}
        closed = assess(result, [parent, dict(parent, JobIDRaw='123.batch', ElapsedRaw='999999')], self.config)
        self.assertTrue(all(closed['gates'].values()))
        self.assertEqual(closed['allocated_core_seconds'], 1462 * 16)
        bad_time = assess(result, [dict(parent, ElapsedRaw='1463')], self.config)
        self.assertFalse(bad_time['gates']['allocated_seconds_within_1_5x_wp5'])
        bad_rate = assess(dict(result, record_success_rate=1989 / 2000), [parent], self.config)
        self.assertFalse(bad_rate['gates']['record_success_at_least_99_5_percent'])


def main():
    global CONFIG_PATH, SB2_SOURCE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--sb2-selection', type=Path, required=True)
    args = p.parse_args()
    CONFIG_PATH, SB2_SOURCE = args.config, args.sb2_selection
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PprimeTests))
    print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAIL',
                      'tests': result.testsRun, 'QM_calls': 0, 'LMDB_opened': False,
                      'Slurm_submitted': False, 'GPU_used': False}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
