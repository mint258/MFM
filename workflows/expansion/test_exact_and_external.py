"""Numerical oracle and independent in-memory/external sorting parity checks."""
import json
from pathlib import Path
import tempfile
import unittest

from . import external_sort, nearest_exact, ranking
from .screen import chemical_flags, features


def fake_key(i):
    text = ""
    for _ in range(14):
        text += chr(65 + i % 26)
        i //= 26
    return text + "-BBBBBBBBBB-N"


def bits(indices):
    data = bytearray(256)
    for i in indices:
        data[i // 8] |= 1 << (i % 8)
    return bytes(data)


class ExactNearestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            nearest_exact.rdkit_modules()
        except ImportError as exc:
            raise unittest.SkipTest("RDKit is absent; actual exact-neighbor validation remains pending") from exc

    def test_every_reference_is_compared_and_ties_keep_first_ordinal(self):
        refs = [bits([1, 3, 5]), bits([1, 3, 7]), bits([2, 4]), bits([7]), bits([1, 3, 7])]
        query_bytes = [bits([1, 3, 7]), bits([2, 4, 9]), bits([1, 5, 2047])]
        query = [{"cid": i + 1, "full_key": fake_key(i), "heavy_atoms": 3,
                  "element_combination": "6", "generic_murcko": "", "generic_ring_systems": [],
                  "ecfp4_2048_hex": b.hex()} for i, b in enumerate(query_bytes)]
        expected = []
        for q in query_bytes:
            qint = int.from_bytes(q, "little")
            scores = [(qint & int.from_bytes(r, "little")).bit_count() / (qint | int.from_bytes(r, "little")).bit_count() for r in refs]
            expected.append((max(scores), scores.index(max(scores))))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fp.bin"
            p.write_bytes(b"".join(refs))
            s = p.stat()
            for block_size in (1, 2, 5):
                try:
                    nearest_exact._initialize_worker(str(p), [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns], 5, block_size)
                    got = nearest_exact._nearest_batch(query)
                    self.assertEqual(got["nearest"], expected)
                    self.assertEqual(got["comparisons"], 15)
                finally:
                    nearest_exact._MAP.close()
                    nearest_exact._REF.close()

    def test_query_does_not_accept_downstream_metadata(self):
        refs = [bits([1])]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fp.bin"
            p.write_bytes(refs[0])
            s = p.stat()
            try:
                nearest_exact._initialize_worker(str(p), [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns], 1, 1)
                with self.assertRaises(ValueError):
                    nearest_exact._nearest_batch([{"downstream_activity": 1.0}])
            finally:
                nearest_exact._MAP.close()
                nearest_exact._REF.close()

    def test_original_X_flags_preserve_isotopes_and_have_no_heavy_atom_cap(self):
        _, flags = chemical_flags("CC.O")
        self.assertTrue(flags["X01"])
        _, flags = chemical_flags("[Na+]")
        self.assertTrue(flags["X02"])
        self.assertTrue(flags["X03"])
        _, flags = chemical_flags("[CH3]")
        self.assertTrue(flags["X04"])
        self.assertTrue(flags["X05"])
        mol, flags = chemical_flags("C" * 253)
        self.assertEqual(mol.GetNumHeavyAtoms(), 253)
        self.assertFalse(any(flags.values()))
        labelled = features(1, "[2H]O[2H]", 1)
        natural = features(2, "O", 2)
        self.assertEqual(labelled["isotopic_atoms"], 2)
        self.assertNotEqual(labelled["full_key"], natural["full_key"])


class ExternalSortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import duckdb
        except ImportError as exc:
            raise unittest.SkipTest("DuckDB is absent; actual external-sort validation remains pending") from exc
        cls.duckdb = duckdb

    @staticmethod
    def pool(n=120):
        return [{"cid": i + 1, "full_key": fake_key(i), "heavy_atoms": (5, 20, 125)[i % 3],
                 "element_combination": ("6", "6,8", "6,7,8")[i % 3], "generic_murcko": str(i % 4),
                 "generic_ring_systems": [], "nearest_v1_tanimoto": (i % 11) / 12,
                 "v1_scaffold_count": i % 7, "v1_ring_system_count": i % 5,
                 "v1_reference_sha256": "a" * 64} for i in range(n)]

    def db(self, rows):
        db = self.duckdb.connect()
        db.execute("SET threads=2")
        db.execute("""CREATE TABLE pool(cid BIGINT,full_key VARCHAR,heavy_atoms BIGINT,element_combination VARCHAR,
            generic_murcko VARCHAR,generic_ring_systems VARCHAR[],nearest_v1_tanimoto DOUBLE,
            v1_scaffold_count BIGINT,v1_ring_system_count BIGINT,v1_reference_sha256 VARCHAR)""")
        names = [r[0] for r in db.execute("DESCRIBE pool").fetchall()]
        db.executemany("INSERT INTO pool VALUES (?,?,?,?,?,?,?,?,?,?)", [[row[k] for k in names] for row in rows])
        return db

    def test_external_integer_finish_matches_exact_fraction_reference(self):
        rows = self.pool()
        reference = ranking.queues(rows, queue_size=25)
        for input_rows in (rows, list(reversed(rows))):
            db = self.db(input_rows)
            try:
                external_sort.create_queues(db, seed=20261025, queue_size=25)
                for stream in ("R", "N"):
                    got = db.execute("SELECT stream,cid,full_key,stream_rank FROM queues WHERE stream=? ORDER BY stream_rank", [stream]).fetchall()
                    want = [(r["stream"], r["cid"], r["full_key"], r["stream_rank"]) for r in reference[stream]]
                    self.assertEqual(got, want)
            finally:
                db.close()

    def test_no_implicit_zero_heavy_atom_exclusion(self):
        rows = self.pool(40)
        rows[0]["heavy_atoms"] = 0  # Neutral H-only molecules are not forbidden by X01-X05.
        db = self.db(rows)
        try:
            external_sort.create_queues(db, seed=20261025, queue_size=20)
            self.assertEqual(db.execute("SELECT count(*) FROM queues WHERE full_key=?", [rows[0]["full_key"]]).fetchone()[0], 1)
        finally:
            db.close()

    def test_duplicated_pool_and_mixed_reference_are_rejected(self):
        rows = self.pool(40)
        rows[1]["v1_reference_sha256"] = "b" * 64
        db = self.db(rows)
        try:
            with self.assertRaises(ValueError):
                external_sort.create_queues(db, seed=20261025, queue_size=10)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
