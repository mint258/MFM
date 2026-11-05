"""Real Linux fixture reconstruction, frozen-kernel parity and safe resume."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest
from . import facts, kernel
from .plan import scientific_source_check, validate
from .run import baseline_comparison, initialize_worker, process_shard
from .support import BASELINE, reference


class ReconstructionTests(unittest.TestCase):
    def test_original_kernel_and_source_fact_asts_remain_frozen(self):
        self.assertEqual(len(scientific_source_check()['sha256']), 64)

    def test_exact_source_facts_preserve_original_cid_text_and_crlf(self):
        raw = b'0007\tCCO\r\n'
        fact = facts.row_fact(raw, 17, 2, 31)
        value = facts.record(raw, fact, {'path': '/synthetic/source.tsv', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        self.assertEqual(value['cid_source_ascii'], '0007')
        self.assertEqual(value['source_terminator_hex'], '0d0a')
        self.assertEqual(value['source_row_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual((value['ordinal'], value['part_index'], value['offset_bytes']), (17, 2, 31))

    def test_actual_tiny_full_shard_all_states_typed_outputs_and_resume(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix='pubchem_reconstruction_fixture_') as directory:
            root = Path(directory)
            raw = b'1\tC\n2\t[Na+]\n3\tnot_a_smiles\n'
            path = root / 'source_000000.tsv'
            path.write_bytes(raw)
            part = {'index': 0, 'first_ordinal': 1, 'last_ordinal': 3, 'records': 3, 'bytes': len(raw), 'first_cid': facts.cid_summary(b'1'), 'last_cid': facts.cid_summary(b'3'), 'reference': reference(path)}
            plan = {'output_directory': str(root / 'fixture_not_production_output'), 'scientific_scope_sha256': 'FIXTURE_ONLY_NO_FULL_DATA_ADMISSION', 'workers': 2, 'batch_rows': 1}
            context = mp.get_context('spawn')
            stop = context.Event()
            with ProcessPoolExecutor(max_workers=2, mp_context=context, initializer=initialize_worker, initargs=(stop,)) as pool:
                receipt = process_shard(part, plan, pool)
                again = process_shard(part, plan, pool)
            self.assertEqual(again, receipt)
            self.assertEqual(receipt['counts'], {'accepted': 1, 'chemReject': 1, 'technicalUnresolved': 1})
            self.assertEqual(len(list((Path(plan['output_directory']) / 'fragments' / '000_0').glob('attempt_*'))), 1)
            all_rows = pq.read_table(receipt['outputs']['all_results']['path']).to_pylist()
            fact_rows = pq.read_table(receipt['outputs']['source_facts']['path']).to_pylist()
            accepted = pq.read_table(receipt['outputs']['accepted']['path']).to_pylist()
            self.assertEqual([r['ordinal'] for r in all_rows], [1, 2, 3])
            self.assertEqual([r['ordinal'] for r in fact_rows], [1, 2, 3])
            self.assertEqual([r['cid'] for r in accepted], [1])
            self.assertIsNone(all_rows[2]['molecular_weight_Da'])
            self.assertEqual(fact_rows[0]['source_row_sha256'], hashlib.sha256(b'1\tC\n').hexdigest())
            with path.open('ab') as stream:
                stream.write(b'4\tCC\n')
            with self.assertRaisesRegex(ValueError, 'bytes differ'):
                process_shard(part, plan, None)

    def test_original_main_and_isolated_science_have_same_scientific_results(self):
        from ..raw_uniform_cost_v1 import run as old
        stop = mp.get_context('spawn').Event()
        old.STOP = kernel.STOP = stop
        old.INITIALIZATION = kernel.INITIALIZATION = {'fixture': True}
        # Includes the historical successful409/554 ring semantics and the
        # exact original ring-Kekulize fallback, not just easy acyclic inputs.
        cases = ('C', '[Na+]', 'not_a_smiles', 'C[N+]1(CCCC1C2=CN=CC=C2)[O-]', 'C[N+]1(CCCC1C(=O)[O-])C', 'CCN1C=NC2=C(N=CN=C21)N')
        for ordinal, smiles in enumerate(cases, 1):
            raw = (str(ordinal) + '\t' + smiles + '\n').encode()
            original = facts.record(raw, facts.row_fact(raw, ordinal, 0, 0), {'path': '/synthetic/source.tsv', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            a, b = old.chemical_task(original), kernel.chemical_task(original)
            for key in ('input', 'category', 'technical_codes', 'audit_parse_succeeded', 'audit_flags', 'legacy_dispatcher_result'):
                self.assertEqual(a[key], b[key], (smiles, key))

    def test_changed_technical_counts_are_reported_without_faking_equality(self):
        observed = dict(BASELINE)
        observed['accepted'] += 1
        observed['technicalUnresolved'] -= 1
        result = baseline_comparison(observed)
        self.assertFalse(result['matches_original_baseline'])
        self.assertFalse(result['counts_forced_equal'])
        self.assertTrue(result['unattributed_difference'])
        self.assertEqual(result['known_causes'], [])

    def test_narrowed_pool_cannot_be_admitted_as_full_reconstruction(self):
        with self.assertRaisesRegex(ValueError, 'No narrowed fallback'):
            validate({'schema': 'PUBCHEM_FULL_RAW_RECONSTRUCTION_PLAN_V1', 'endpoint': '202.38.247.57:22', 'uid': 1278, 'scientific_scope': {'source_rows': 10000, 'parts': []}})

    def test_user_approved_cpu21_records_real_all_partition(self):
        from .run import validate_cpu21_policy
        approval={'schema':'PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1','status':'USER_APPROVED','node':'compute-0-21','partition':'all','GPU_used':False,'paid_server_used':False}
        validate_cpu21_policy('compute-0-21','all',approval)
        with self.assertRaisesRegex(ValueError,'cpu-partition'):
            validate_cpu21_policy('compute-0-21','cpu',approval)


if __name__ == '__main__':
    unittest.main()
