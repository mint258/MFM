"""Scientific adapter contract tests; native execution is a separate Root pilot."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from . import core as C, native as N, store as S

SOURCE = {"pubchem_version": "fixture-v1", "cid": 1, "full_key": "X" * 14 + "-" + "Y" * 10 + "-N",
          "source_smiles": "CC", "isomeric_smiles": "CC", "stream": "R", "stream_rank": 1}


class FakeKernel:
    def __init__(self, points=None, failures=()):
        self.points = [0., 1., 2., 3., 4.] if points is None else points
        self.failures = set(failures)
        self.prepare_calls = self.embed_calls = self.d20_calls = self.d3_calls = 0
        self.optimizer_ids = []

    def prepare(self, source):
        self.prepare_calls += 1
        self.d20_calls += 1
        return {"atomic_numbers": [6], "D20": {"names": ["f" + str(i) for i in range(20)],
            "values": [float(i) for i in range(20)], "valid_mask": [True] * 20, "issues": []},
            "unassigned_stereo": [], "uff_supported": True}

    def embed(self, seed, count):
        self.embed_calls += 1
        if count != 30 or seed != C.seed_for(C.molecule_id(SOURCE)):
            raise AssertionError("NONFIXED_POOL_OR_SEED")
        return list(range(len(self.points)))

    def optimize(self, index):
        self.optimizer_ids.append(index)
        if index in self.failures:
            raise RuntimeError("scientific failure")
        # Energies deliberately reverse native order to prove original selection,
        # rather than first-three-converged processing order, determines outputs.
        return {"candidate_id": index, "coordinates": [[self.points[index], 0., 0.]],
                "energy": float(len(self.points) - index), "optimizer_code": 0,
                "stereo_valid": True, "iterations": 7}

    def distance(self, a, b):
        return abs(a["coordinates"][0][0] - b["coordinates"][0][0])

    def attach(self, cache):
        pass

    def d3(self, row):
        self.d3_calls += 1
        return {"PMI1": float(row["candidate_id"]), "SASA_atom_A2": [1.]}, []

    def orders(self, rows, mid, seed):
        from workflows.data_v1_final.conformers.selection import conformer_orders
        return conformer_orders(rows, self.distance, mid, "uff_sprime", seed)


class ContractTests(unittest.TestCase):
    def test_initial_max3_graph_once_and_fixed_candidate_pool(self):
        kernel = FakeKernel()
        cache = C.create_cache(SOURCE, kernel)
        packet = C.export_cache(cache, SOURCE, kernel)
        self.assertEqual([r["candidate_id"] for r in packet["conformers"]], [4, 3, 2])
        self.assertEqual((kernel.d20_calls, kernel.embed_calls, kernel.d3_calls), (1, 1, 3))
        self.assertEqual(kernel.optimizer_ids, [0, 1, 2, 3, 4])
        self.assertFalse(packet["insufficient_conformers"])
        with self.assertRaisesRegex(ValueError, "MAXIMUM_THREE"):
            C.export_cache(cache, SOURCE, kernel, limit=4)

    def test_original_no_fill_phase_and_exact_half_angstrom_boundary(self):
        from workflows.data_v1_final.conformers.selection import select_fill
        kernel = FakeKernel(points=[0., .1, .5, 1.])
        cache = C.create_cache(SOURCE, kernel)
        actual = cache["canonical_candidates"]
        original = select_fill([], cache["valid_candidates"], len(actual), kernel.distance, .5)
        self.assertEqual(C.canonical(actual), C.canonical(original))
        self.assertTrue(all(not r["below_dedup_threshold"] for r in actual))
        self.assertEqual(len(actual), 3)

    def test_extension_retains_old_bytes_no_native_or_d20_repeat(self):
        kernel = FakeKernel()
        cache = C.create_cache(SOURCE, kernel)
        packet = C.export_cache(cache, SOURCE, kernel)
        native_before = (kernel.embed_calls, list(kernel.optimizer_ids), kernel.d20_calls)
        old_bytes = C.canonical(packet["conformers"])
        extended = C.export_cache(cache, SOURCE, kernel, limit=5,
            previous_packet=packet, allow_future_extension=True)
        self.assertEqual(C.canonical(extended["conformers"][:3]), old_bytes)
        self.assertEqual((kernel.embed_calls, kernel.optimizer_ids, kernel.d20_calls), native_before)
        self.assertEqual(kernel.d3_calls, 5)
        self.assertEqual([r["conformer_id"] for r in extended["conformers"]], list(range(5)))
        with self.assertRaisesRegex(ValueError, "TRUNCATE"):
            C.export_cache(cache, SOURCE, kernel, limit=2, previous_packet=packet)

    def test_shortage_retains_actual_no_fill_and_no_retry(self):
        kernel = FakeKernel(points=[0., .1, .2, .3], failures={2})
        cache = C.create_cache(SOURCE, kernel)
        packet = C.export_cache(cache, SOURCE, kernel)
        self.assertEqual(packet["actual_conformers"], 1)
        self.assertTrue(packet["insufficient_conformers"])
        self.assertEqual(kernel.optimizer_ids, [0, 1, 2, 3])
        self.assertEqual(len(cache["attempts"]), 4)
        self.assertEqual(cache["attempts"][2]["status"], "NATIVE_FAILED")
        self.assertEqual(packet["state"], "INSUFFICIENT_UNIQUE_CONFORMERS")

    def test_empty_embedding_has_no_fallback(self):
        kernel = FakeKernel(points=[])
        cache = C.create_cache(SOURCE, kernel)
        packet = C.export_cache(cache, SOURCE, kernel)
        self.assertEqual((kernel.embed_calls, kernel.optimizer_ids, packet["actual_conformers"]), (1, [], 0))
        self.assertTrue(packet["insufficient_conformers"])

    def test_fixed_original_sprime_seed(self):
        import hashlib
        for mid in ("a", "expansion-pubchem:release:1:key", "molecule-9"):
            expected = max(int.from_bytes(hashlib.sha256(("sprime-ETKDGv3-v1:" + mid).encode()).digest()[:4], "big") & 0x7fffffff, 1)
            self.assertEqual(C.seed_for(mid), expected)

    def test_native_exact_parameters_and_single_call(self):
        calls = []
        class AllChem:
            @staticmethod
            def ETKDGv3():
                return SimpleNamespace()
            @staticmethod
            def EmbedMultipleConfs(mol, **kwargs):
                calls.append(kwargs)
                return []
        self.assertEqual(N.embed_once(object(), AllChem, 17), [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["numConfs"], 30)
        self.assertEqual(vars(calls[0]["params"]),
            {"randomSeed": 17, "numThreads": 1, "enforceChirality": True, "pruneRmsThresh": -1., "maxIterations": 200, "useRandomCoords": False})
        class Field:
            def MinimizeTrajectory(self, **kwargs):
                self.kwargs = kwargs
                return 0, []
        field = Field()
        self.assertEqual(N.minimize_once(field), (0, []))
        self.assertEqual(field.kwargs, C.RECIPE["uff"])

    def test_changed_cache_or_source_and_changed_prefix_are_rejected(self):
        kernel = FakeKernel()
        cache = C.create_cache(SOURCE, kernel)
        packet = C.export_cache(cache, SOURCE, kernel)
        corrupt = copy.deepcopy(cache)
        corrupt["canonical_candidates"][0]["coordinates"][0][0] += 1
        with self.assertRaisesRegex(ValueError, "CACHE_CONTENT_CHANGED"):
            C.validate_cache(corrupt, SOURCE)
        corrupt = copy.deepcopy(packet)
        corrupt["conformers"][0]["coordinates"][0][0] += 1
        with self.assertRaisesRegex(ValueError, "PREFIX_CHANGED"):
            C.export_cache(cache, SOURCE, kernel, limit=4, previous_packet=corrupt, allow_future_extension=True)
        changed_source = dict(SOURCE, cid=2)
        with self.assertRaisesRegex(ValueError, "CACHE_SOURCE_CHANGED"):
            C.validate_cache(cache, changed_source)

    def test_durable_closed_cache_reuse_and_interrupted_directory_never_retried(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            kernel = FakeKernel()
            first = S.run_one(SOURCE, root / "first", kernel=kernel)
            before = (kernel.embed_calls, list(kernel.optimizer_ids), kernel.d20_calls)
            second = S.run_one(SOURCE, root / "extension", kernel=kernel,
                prior_cache_path=first["candidate_cache"]["path"],
                previous_packet_path=first["selected_packet"]["path"],
                export_limit=4, allow_future_extension=True)
            self.assertEqual((kernel.embed_calls, kernel.optimizer_ids, kernel.d20_calls), before)
            old = S.read_json(first["selected_packet"]["path"])
            new = S.read_json(second["selected_packet"]["path"])
            self.assertEqual(C.canonical(old["conformers"]), C.canonical(new["conformers"][:3]))
            with self.assertRaises(FileExistsError):
                S.run_one(SOURCE, root / "first", kernel=kernel)
            self.assertEqual((kernel.embed_calls, kernel.optimizer_ids, kernel.d20_calls), before)
            events = S.read_events(root / "first/events.jsonl")
            self.assertEqual(sum(e["phase"] == "embedding_intent" for e in events), 1)
            self.assertEqual(sum(e["phase"] == "optimizer_intent" for e in events), 5)
            path = root / "interrupted.jsonl"
            path.write_bytes((root / "first/events.jsonl").read_bytes() + b'{"partial":')
            with self.assertRaisesRegex(ValueError, "INTERRUPTED"):
                S.read_events(path)