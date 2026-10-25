"""Meaningful metadata/algorithm checks; no real data, network or QM calls."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from . import common, decontamination, ranking, source

K1 = "AAAAAAAAAAAAAA-BBBBBBBBBB-N"
K2 = "AAAAAAAAAAAAAA-CCCCCCCCCC-N"


class PreparationTests(unittest.TestCase):
    def test_wp5_key_ignores_stereo_and_retains_protonation(self):
        self.assertEqual(common.wp5_key(K1), common.wp5_key(K2))
        self.assertNotEqual(common.wp5_key(K1), common.wp5_key(K1[:-1] + "O"))
        with self.assertRaises(ValueError):
            common.wp5_key("not-an-inchikey")

    def test_pending_manifest_cannot_become_clean(self):
        m = {"schema": "expansion_decontamination_sources_v1", "sources": [
            {"dataset": name, "status": "PENDING"} for name in sorted(decontamination.REQUIRED)]}
        self.assertEqual(decontamination.metadata_status(m)["status"], "PENDING")
        with self.assertRaises(ValueError):
            decontamination.validate_ready(m)
        m["sources"].pop()
        with self.assertRaises(ValueError):
            decontamination.metadata_status(m)

    def test_identity_firewall_and_conservative_composition(self):
        row = {"source_id": "s1", "role": "all", "inchikeys": [K1]}
        keys = decontamination.identity_keys(row)
        self.assertIn(("wp5", common.wp5_key(K1)), keys)
        with self.assertRaises(ValueError):
            decontamination.identity_keys(dict(row, activity=3.5))
        with self.assertRaises(ValueError):
            decontamination.identity_keys(dict(row, inchikeys=[]))
        comp = decontamination.identity_keys(dict(row, inchikeys=[], non_h_composition=[[6, 2], [8, 1]]))
        self.assertEqual(comp, [("composition", "[[6,2],[8,1]]")])

    def test_stereoisomer_and_unresolved_composition_are_excluded(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT)")
        db.execute("INSERT INTO excluded VALUES(?,?,?)", ("wp5", common.wp5_key(K1), "v1"))
        db.execute("INSERT INTO excluded VALUES(?,?,?)", ("composition", "[[6,2]]", "qm7"))
        hits = decontamination.contamination({"full_key": K2, "non_h_composition": "[[6,2]]"}, db)
        self.assertEqual(hits, [("composition", "qm7"), ("wp5", "v1")])
        db.close()

    def test_pubchem_head_pin_is_not_download_evidence(self):
        class Response:
            status = 200
            url = source.URL
            headers = {"Content-Length": "100", "Last-Modified": "today"}
            def __enter__(self): return self
            def __exit__(self, *_): return False
        class Client:
            def open(self, *_, **__): return Response()
        pin = {"url": source.URL, "content_length": 100, "last_modified": "today"}
        self.assertEqual(source.probe(pin, Client())["content_length"], 100)
        with self.assertRaises(ValueError):
            source.probe(dict(pin, last_modified="yesterday"), Client())

    def test_zero_soft_quota_uses_real_positive_hard_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "Filesystem blocks quota limit grace files quota limit grace\n/dev/sda1 1000 0 500000000 25 0 0\n"
            q = {"schema": "expansion_user_quota_receipt_v1", "username": "zixiao", "uid": 1278,
                 "basis": "login_node_quota", "returncode": 0, "observed_unix_seconds": time.time(),
                 "available_bytes": (500000000 - 1000) * 1024, "raw_stdout": raw,
                 "raw_stdout_sha256": hashlib.sha256(raw.encode()).hexdigest()}
            p = Path(tmp) / "quota.json"
            common.dump_new(p, q)
            common.check_quota(p, 1000)
            with self.assertRaises(ValueError):
                common.check_quota(p, q["available_bytes"])
            with self.assertRaises(FileExistsError):
                common.dump_new(p, {})

    @staticmethod
    def pool():
        return [{"cid": i + 1, "full_key": str(i), "heavy_atoms": 5 if i % 2 else 999,
                 "element_combination": "6", "generic_murcko": str(i % 3), "generic_ring_systems": [],
                 "nearest_v1_tanimoto": i / 100, "v1_scaffold_count": i % 3, "v1_ring_system_count": i % 2,
                 "v1_reference_sha256": "a" * 64} for i in range(40)]

    def test_queues_are_disjoint_nested_and_independent_of_input_order(self):
        rows = self.pool()
        first = ranking.queues(rows, queue_size=10)
        self.assertEqual(first, ranking.queues(list(reversed(rows)), queue_size=10))
        self.assertFalse({r["full_key"] for r in first["R"]} & {r["full_key"] for r in first["N"]})
        # Every subsequent batch takes a prefix of the SAME frozen ten-million queue.
        self.assertEqual(first["N"][:4], [r for r in first["N"] if r["stream_rank"] <= 4])
        self.assertEqual(ranking.heavy_bin(999), "above_100")
        with self.assertRaises(ValueError):
            ranking.queues(rows, queue_size=30)

    def test_downstream_features_cannot_change_novelty_order(self):
        rows = self.pool()
        rows[0]["downstream_nearest_similarity"] = .9
        with self.assertRaises(ValueError):
            ranking.queues(rows, queue_size=10)

    def test_release_rejects_index_without_actual_candidate_filtering(self):
        with self.assertRaises(ValueError):
            ranking.release_gate(screen_receipt={"status": "COMPLETE", "complete_source": True},
                regression_receipt={"status": "PASS", "agreement": 1, "unexplained_mismatches": 0,
                                    "full_v1_selection_regression_passed": True},
                decontamination_receipt={"schema": "expansion_exclusion_index_v1", "status": "COMPLETE"},
                novelty_receipt={})


if __name__ == "__main__":
    unittest.main()
