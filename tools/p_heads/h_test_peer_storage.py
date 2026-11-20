"""Synthetic cases for peer growth, closure and sparse physical accounting."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import h_peer_storage as storage


class PeerStorage(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.labels = self.root / 'labels'
        self.geometry = self.root / 'geometry'
        self.full = self.root / 'full'
        for folder in (self.labels, self.geometry, self.full):
            folder.mkdir()
            (folder / 'data.sqlite').write_bytes(b'x' * 4096)
        self.publish(self.geometry / 'access.json', {})
        self.publish(self.geometry / 'queue.manifest.json', dict(storage_forecast_bytes=2**26 + 4096))
        self.registry = dict(schema='D_STAGE0_REGISTERED_STORAGE_RESERVATIONS_V1',
            registered_model_share_future_bytes=1000,
            registered_model_share_components=dict(existing_model_and_P=900, S_study_NFS=100),
            benchmark_peer_environment_bytes=20, benchmark_miscellaneous_future_bytes=30,
            B0_labels=[dict(directory=str(self.labels), forecast_bytes=2**26 + 4096)],
            B0_geometry=[str(self.geometry)])
        self.plan = dict(schema='D_FULL_PRODUCTION_PLAN_V1',
            budget=dict(peak_new_bytes=8192),
            configs=dict(produce=dict(output=str(self.full / 'stores'), peak_bytes=20000)))
        self.policy = dict(peer_storage_registry=str(self.root / 'registry.json'),
            peer_D_production_plan=str(self.root / 'plan.json'),
            peer_D_full_root=str(self.full), existing_other_NFS_future_bytes=18)
        self.refresh()

    @staticmethod
    def publish(path, value):
        Path(path).write_text(json.dumps(value))

    def refresh(self):
        self.publish(self.policy['peer_storage_registry'], self.registry)
        self.publish(self.policy['peer_D_production_plan'], self.plan)

    def calculate(self):
        return storage.concurrent(self.policy, legacy_model=1100, followup=7)

    def test_all_forecasts_and_existing_reserves_are_preserved(self):
        result = self.calculate()
        self.assertEqual(result['model_share_future'], 1200)
        self.assertEqual(result['D_full_committed'], 4096)
        self.assertEqual(result['total'], 1200 + 20 + 30 + 2 * 2**26 + 15904 + 18 + 7)

    def test_only_real_published_closure_releases_geometry_future(self):
        old = self.calculate()['total']
        access = dict(immutable=True, cross_node_read_allowed=True, publishing_uid=os.getuid(),
                      actual_closure_evidence=dict(raw='JobState=COMPLETED ExitCode=0:0'))
        self.publish(self.geometry / 'access.json', access)
        self.assertEqual(self.calculate()['total'], old - 2**26)
        access['publishing_uid'] += 1
        self.publish(self.geometry / 'access.json', access)
        self.assertEqual(self.calculate()['total'], old)

    def test_sparse_files_and_hardlinks_cannot_overdebit_D_forecast(self):
        original = self.calculate()
        data = self.full / 'data.sqlite'
        with data.open('r+b') as stream:
            stream.truncate(4 * 2**20)
        (self.full / 'hardlink').hardlink_to(data)
        self.assertEqual(self.calculate()['D_full_committed'], original['D_full_committed'])
        data.write_bytes(b'x' * 16384)
        self.assertEqual(self.calculate()['D_full_committed'], 8192)
        (self.full / 'linked').symlink_to(data)
        with self.assertRaises(OSError):
            self.calculate()

    def test_unknown_forecasts_and_metadata_fail_closed(self):
        for value in (-1, True, 1.5):
            with self.subTest(value=value):
                self.registry['benchmark_peer_environment_bytes'] = value
                self.refresh()
                with self.assertRaises(ValueError):
                    self.calculate()
        self.registry['benchmark_peer_environment_bytes'] = 20
        self.registry['registered_model_share_future_bytes'] += 1
        self.refresh()
        with self.assertRaises(ValueError):
            self.calculate()
        self.registry['registered_model_share_future_bytes'] -= 1
        self.registry['schema'] = 'UNKNOWN'
        self.refresh()
        with self.assertRaises(ValueError):
            self.calculate()

    def test_each_admission_reads_current_peer_forecasts(self):
        first = self.calculate()
        self.registry['registered_model_share_future_bytes'] += 50
        self.registry['registered_model_share_components']['S_study_NFS'] += 50
        self.refresh()
        self.assertEqual(self.calculate()['total'], first['total'] + 50)
        self.plan['configs']['produce']['peak_bytes'] += 70
        self.refresh()
        self.assertEqual(self.calculate()['total'], first['total'] + 120)


if __name__ == '__main__':
    unittest.main()
