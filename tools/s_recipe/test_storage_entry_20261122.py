"""Only the new entry's storage binding; no GPU/model forward."""
import unittest
from unittest.mock import patch
import train_shared_storage_20261122 as future


class StorageBindingTests(unittest.TestCase):
    def exercise(self, fails):
        original = future.entry.capacity
        c = {'batch_size': 32, 'microbatch_size': 32, 'seed': 0}
        calls = []
        def fake_run(actual, *, scheduler_record):
            self.assertIs(actual, c)
            self.assertEqual(scheduler_record, {'real': 'allocation'})
            for _ in range(3):
                future.entry.capacity()
            if fails:
                raise RuntimeError('fixture exception')
            return {'status': 'HANDOFF_SAVED'}
        with patch.object(future, 'admit', side_effect=lambda: calls.append('unified')):
            with patch.object(future.entry, 'run', side_effect=fake_run):
                if fails:
                    with self.assertRaisesRegex(RuntimeError, 'fixture exception'):
                        future.run(c, scheduler_record={'real': 'allocation'})
                else:
                    self.assertEqual(future.run(c, scheduler_record={'real': 'allocation'}),
                                     {'status': 'HANDOFF_SAVED'})
        self.assertEqual(calls, ['unified'])
        self.assertIs(future.entry.capacity, original)

    def test_one_startup_admission_no_repeated_storage_walk(self):
        self.exercise(False)

    def test_original_entry_restored_after_exception(self):
        self.exercise(True)


if __name__ == '__main__':
    unittest.main()
