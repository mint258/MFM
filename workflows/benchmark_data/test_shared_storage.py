import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from workflows.benchmark_data import shared_storage as S


def policy():
    return {'schema': 'benchmark-shared-storage-reservations-v1',
            'owned_scopes': sorted(S.SCOPES),
            'components': {key: 100 for key in S.COMPONENTS},
            'concurrent_total_bytes': 600,
            'node_local_tmp_peer_future_bytes': {'compute-0-7': 24*1024**3,
                                               'compute-0-17': 12*1024**3}}


class SharedStorageTests(unittest.TestCase):
    def test_unknown_or_inconsistent_declarations_refuse_admission(self):
        self.assertEqual(S.declared_pool(policy()), 600)
        bad = []
        for key, value in (('schema', 'unknown'), ('owned_scopes', []),
                           ('concurrent_total_bytes', 599)):
            p = policy(); p[key] = value; bad.append(p)
        for value in (-1, True, None):
            p = policy(); p['components']['model_P_NFS'] = value; bad.append(p)
        p = policy(); p['components']['duplicate_pool'] = 1; bad.append(p)
        for p in bad:
            with self.subTest(policy=p), self.assertRaises(RuntimeError):
                S.declared_pool(p)

    def test_closed_growth_does_not_double_count_pool_and_never_lowers_old_guard(self):
        self.assertEqual(S.combined_pool(174, 201, True), 201)
        self.assertEqual(S.combined_pool(220, 201, True), 220)
        self.assertEqual(S.combined_pool(174, 201, False), 375)

    def test_peer_root_claim_requires_same_actual_filesystem(self):
        with patch.object(S.os, 'stat', side_effect=[SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2)]):
            with self.assertRaisesRegex(RuntimeError, 'filesystem'):
                S.local_peer_guard(policy(), 'compute-0-17')

    def test_local_peak_and_inode_reserves_are_enforced(self):
        gib = 1024**3
        stat = SimpleNamespace(f_blocks=80*gib, f_frsize=1, f_bavail=21*gib, f_favail=4000)
        with patch.object(S.os, 'stat', return_value=SimpleNamespace(st_dev=1)), patch.object(S.os, 'statvfs', return_value=stat):
            with self.assertRaisesRegex(RuntimeError, 'reserve'):
                S.local_peer_guard(policy(), 'compute-0-17')
            stat.f_bavail = 30*gib
            S.local_peer_guard(policy(), 'compute-0-17')
            stat.f_favail = 1000
            with self.assertRaisesRegex(RuntimeError, 'reserve'):
                S.local_peer_guard(policy(), 'compute-0-17')

    def test_seal_owner_and_shared_access_are_required_to_retire_geometry_growth(self):
        root = S.BASE/'artifacts/benchmark_B0_20261119'
        seal = {'immutable': True, 'cross_node_read_allowed': True, 'publishing_uid': os.getuid()}
        for change, expected in (({}, 600), ({'immutable': False}, 774),
                                 ({'cross_node_read_allowed': False}, 774),
                                 ({'publishing_uid': -1}, 774)):
            with self.subTest(change=change), patch.object(Path, 'read_text', side_effect=[json.dumps(policy()), json.dumps(dict(seal, **change))]), patch.object(Path, 'exists', return_value=True), patch.object(S, 'local_peer_guard'):
                self.assertEqual(S.current_pool(root, 174), expected)

    def test_foreign_output_scope_is_not_admitted(self):
        with self.assertRaisesRegex(RuntimeError, 'own output scope'):
            S.current_pool(Path('/tmp/foreign'), 1)


if __name__ == '__main__':
    unittest.main()
