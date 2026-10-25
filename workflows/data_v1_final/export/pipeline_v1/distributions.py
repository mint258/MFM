"""Element membership, exact heavy-atom size and scaffold frequency comparisons."""
from __future__ import annotations
import argparse
import json
import concurrent.futures
import multiprocessing as mp
import os
from pathlib import Path
from .io import check_allocation, connect, fresh_dir, manifest, query_parquet, verify, write_json


def dimension_worker(task):
    source, start, stop, destination = task
    original = connect(source, readonly=True)
    db = connect(destination)
    count = 0
    try:
        db.execute("CREATE TABLE dimensions(molecule_id TEXT,dimension TEXT,category TEXT,PRIMARY KEY(molecule_id,dimension,category))")
        cursor = original.execute("SELECT molecule_id,elements_json,heavy_atoms,scaffold_id FROM features WHERE rowid>=? AND rowid<? ORDER BY rowid", (start, stop))
        while True:
            rows = cursor.fetchmany(512)
            if not rows:
                break
            for row in rows:
                values = [(row["molecule_id"], "element_presence", str(z)) for z in json.loads(row["elements_json"])]
                values += [(row["molecule_id"], "heavy_atoms_exact", str(row["heavy_atoms"])), (row["molecule_id"], "scaffold", row["scaffold_id"])]
                db.executemany("INSERT INTO dimensions VALUES(?,?,?)", values)
            db.commit(); count += len(rows)
    finally:
        db.close(); original.close()
    return {"path": str(destination), "molecules": count, "rowid_start": start, "rowid_stop_exclusive": stop, "pid": os.getpid()}


def run(d5_path, output, fixture=False):
    import pyarrow as pa
    check_allocation(fixture)
    d5, d5_ref = manifest(d5_path, "FIXTURE_ONLY" if fixture else "D5_PARQUET_LISTS_FROZEN")
    source = verify(d5["database"])
    out = fresh_dir(output)
    db = connect(out / "distributions.sqlite")
    try:
        db.execute("ATTACH DATABASE ? AS source", (source.as_uri() + "?mode=ro",))
        db.execute("CREATE TABLE dimensions(molecule_id TEXT,dimension TEXT,category TEXT,PRIMARY KEY(molecule_id,dimension,category))")
        last = db.execute("SELECT coalesce(max(rowid),0) FROM source.features").fetchone()[0]
        width = max(1, (last + 15) // 16)
        with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn")) as pool:
            workers = list(pool.map(dimension_worker, [(str(source), 1 + i * width, 1 + (i + 1) * width, str(out / ("dimension-" + str(i).zfill(2) + ".sqlite"))) for i in range(16)], chunksize=1))
        for result in workers:
            db.execute("ATTACH DATABASE ? AS part", (result["path"],))
            db.execute("INSERT INTO dimensions SELECT * FROM part.dimensions")
            db.commit(); db.execute("DETACH DATABASE part")
        db.executescript("""
          CREATE TABLE counts AS SELECT m.subset,d.dimension,d.category,count(*) AS molecules
            FROM source.subset_members m JOIN dimensions d USING(molecule_id) GROUP BY m.subset,d.dimension,d.category;
          CREATE UNIQUE INDEX counts_key ON counts(subset,dimension,category);
          CREATE TABLE totals AS SELECT subset,count(*) AS molecules FROM source.subset_members GROUP BY subset;
        """)
        db.commit()
        schema = pa.schema([("subset", pa.string()), ("dimension", pa.string()), ("category", pa.string()),
             ("molecules", pa.int64()), ("fraction", pa.float64()), ("baseline_subset", pa.string()),
             ("baseline_molecules", pa.int64()), ("baseline_fraction", pa.float64()), ("fraction_difference", pa.float64())])
        # Include categories absent from a subset: zero frequency is data.
        query = """SELECT t.subset,b.dimension,b.category,coalesce(c.molecules,0) AS molecules,
          1.0*coalesce(c.molecules,0)/t.molecules AS fraction,b.subset AS baseline_subset,b.molecules AS baseline_molecules,
          1.0*b.molecules/bt.molecules AS baseline_fraction,
          1.0*coalesce(c.molecules,0)/t.molecules-1.0*b.molecules/bt.molecules AS fraction_difference
          FROM totals t JOIN counts b ON b.subset=CASE WHEN t.subset IN('pilot_val','val_all') THEN 'val_all' ELSE 'train_all' END
          JOIN totals bt ON bt.subset=b.subset LEFT JOIN counts c ON c.subset=t.subset AND c.dimension=b.dimension AND c.category=b.category
          ORDER BY t.subset,b.dimension,b.category"""
        ref = query_parquet(db, query, out / "subset_distributions.parquet", schema)
        result = {"status": "FIXTURE_ONLY" if fixture else "D5_SUBSET_DISTRIBUTIONS_MATERIALIZED", "d5_manifest": d5_ref,
            "tables": [ref], "dimensions": ["element_presence", "heavy_atoms_exact", "scaffold"],
            "element_denominator": "molecules with element / molecules in subset; one count per molecule+element", "scaffold_policy": "exact supplied frozen scaffold_id; empty string is explicit acyclic category; never infer from storage directory", "fixture": fixture, "disjoint_feature_range_workers": workers}
        write_json(out / "manifest.json", result)
        return result
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--d5-manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixture", action="store_true")
    a = p.parse_args(); run(a.d5_manifest, a.output, a.fixture)


if __name__ == "__main__":
    main()
