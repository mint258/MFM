"""Small real JSON/SQLite -> DuckDB -> Parquet round trip; no source data."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from .common import dump_new, load, reference
from . import external_sort
from . import test_exact_and_external as cases


class ExternalIOTest(unittest.TestCase):
    def test_real_bound_projection_and_parquet_publication(self):
        try:
            import duckdb
        except ImportError as exc:
            raise unittest.SkipTest("DuckDB unavailable; IO route not validated") from exc
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            rows = cases.ExternalSortingTests.pool(40)
            projection = p / "novelty.jsonl"
            projection.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            pool_path = p / "pool.sqlite"
            db = sqlite3.connect(pool_path)
            db.execute("CREATE TABLE candidates(full_key TEXT,cid INTEGER)")
            db.executemany("INSERT INTO candidates VALUES(?,?)", [(r["full_key"], r["cid"]) for r in rows])
            db.commit(); db.close()
            screen = p / "screen.json"
            regression = p / "regression.json"
            filtered = p / "filtered.json"
            query = p / "queries.json"
            novelty = p / "novelty.json"
            dump_new(screen, {"status": "COMPLETE", "complete_source": True})
            dump_new(regression, {"status": "PASS", "agreement": 1., "unexplained_mismatches": 0,
                                  "full_v1_selection_regression_passed": True})
            dump_new(filtered, {"schema": "expansion_filtered_pool_v1", "status": "COMPLETE", "all_sources_all_splits_verified": True,
                                "screen": reference(screen), "regression": reference(regression), "database": reference(pool_path)})
            dump_new(query, {"filtered_pool_receipt": reference(filtered)})
            dump_new(novelty, {"schema": "expansion_exact_novelty_v1", "status": "COMPLETE", "fingerprint_recipe": external_sort.RECIPE,
                "query_manifest": reference(query), "filtered_pool_receipt": reference(filtered), "nearest_similarity_exact": True,
                "downstream_features_used": False, "projection": {**reference(projection), "rows": 40}, "queries": 40})
            out = p / "out"
            # Only environment/quota/output-root checks are stubbed. All physical
            # pins, source/pool association, SQL, integer ordering and COPY run.
            with patch.multiple(external_sort, require_compute=lambda *_: "synthetic_compute", check_quota=lambda *_: None,
                                external_output=lambda path: Path(path)):
                external_sort.run(novelty, out, p / "unused_quota.json", 2_000_000_000,
                                  workers=2, queue_size=10, first_batch_each=4, memory_gb=1, temporary_gb=1)
            result = load(out / "receipt.json")
            self.assertEqual(result["pool_molecules"], 40)
            reader = duckdb.connect()
            try:
                self.assertEqual(reader.execute("SELECT count(*) FROM read_parquet(?)", [str(out / "queues.parquet")]).fetchone()[0], 20)
                self.assertEqual(reader.execute("SELECT count(*) FROM read_parquet(?)", [str(out / "batch1.parquet")]).fetchone()[0], 8)
            finally:
                reader.close()


if __name__ == "__main__":
    unittest.main()
