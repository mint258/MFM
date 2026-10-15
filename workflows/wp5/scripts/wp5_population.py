"""WP5 formal population, whole-molecule identity components and QC; source read-only."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, time
from pathlib import Path

SCREEN = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011")
ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
EXPECTED = dict(physical_records=15879477, analysis_records=11236754,
                analysis_molecules=1220956, excluded_records=4900,
                excluded_molecules=490, formal_records=11231854,
                formal_molecules=1220466)

def quoted(path):
    return "'" + str(path).replace("'", "''") + "'"

def qi(name):
    return '"' + name.replace('"', '""') + '"'

def save(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".pending")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def rows(db, query):
    cursor = db.execute(query)
    names = [entry[0] for entry in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]

def scalar(db, query):
    return db.execute(query).fetchone()[0]

def check_counts(label, observed, expected):
    if observed != expected:
        raise RuntimeError("MANIFEST_COUNT_MISMATCH_" + label + ": " +
                           repr({"observed": observed, "expected": expected}))

def copy(db, query, path):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    if path.exists():
        raise FileExistsError("Permanent population output already exists: " + str(path))
    db.execute("COPY (" + query + ") TO " + quoted(pending) +
               " (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 131072)")
    pending.replace(path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=SCREEN / "a_retained/relaxed_quality_annotations.parquet")
    parser.add_argument("--stereo", type=Path, default=SCREEN / "a_retained/stereo_pair_classification.parquet")
    parser.add_argument("--consistency", type=Path, default=SCREEN / "a_retained/A1_stereo_consistency.parquet")
    parser.add_argument("--out", type=Path, default=ROOT / "population")
    parser.add_argument("--threads", type=int, default=24)
    parser.add_argument("--memory-gb", type=int, default=20)
    parser.add_argument("--expected-counts", type=Path, help="Closed fixture manifest only; production uses fixed WP5 counts.")
    parser.add_argument("--spill-root", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text())
        print("AST_PASS_NO_DATA_NO_QM_NO_LMDB")
        return
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if not os.environ.get("SLURM_JOB_ID") or not 16 <= args.threads <= allocated:
        raise RuntimeError("SLURM_AT_LEAST16_EFFECTIVE_THREADS_REQUIRED")
    expected = EXPECTED.copy()
    if args.expected_counts:
        expected = json.loads(args.expected_counts.read_text())
        if set(expected) != set(EXPECTED):
            raise ValueError("Fixture expected-count manifest must contain the seven population counts")
    if (args.out / "manifest.json").exists() or (args.out / "formal_record_index.parquet").exists():
        raise FileExistsError("Refuse to overwrite already published formal population")
    if not args.out.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Output must remain inside the new WP5 run root")
    args.out.mkdir(parents=True, exist_ok=True)
    import duckdb
    import pyarrow as pa
    started = time.monotonic()
    db = duckdb.connect()
    db.execute("SET threads=" + str(args.threads))
    db.execute("SET memory_limit=" + quoted(str(args.memory_gb) + "GB"))
    db.execute("SET preserve_insertion_order=false")
    spill = args.spill_root / ("phase1_wp5_population_" + os.environ["SLURM_JOB_ID"] + "_" + str(os.getpid()))
    spill.mkdir(parents=True, exist_ok=False)
    db.execute("SET temp_directory=" + quoted(spill))
    required = {
        "record_id", "molecule_id", "shard_id", "real_index", "record_payload_sha256",
        "source_path", "stored_inchikey", "reidentified_inchikey", "smiles", "conformer_id",
        "reidentified_smiles", "total_atoms", "heavy_atoms", "energy_raw",
        "member_train", "member_full", "member_routine", "split", "membership",
        "legacy_QA_status", "retained", "T01", "T01_original", "S01", "S01_backbone", "S02_delta_energy_kcal_mol",
        "H01_abs_energy_per_atom", "B01", "I01_relaxed_to_T01", "quality_codes",
    }
    db.execute("CREATE VIEW input_quality AS SELECT * FROM read_parquet(" + quoted(args.input) + ")")
    columns = [r[0] for r in db.execute("DESCRIBE input_quality").fetchall()]
    missing = sorted(required - set(columns))
    if missing:
        raise RuntimeError("MISSING_REQUIRED_FORMAL_FIELDS: " + repr(missing))
    check_counts("SOURCE_PHYSICAL", scalar(db, "SELECT count(*) FROM input_quality"),
                 expected["physical_records"])
    db.execute("CREATE VIEW analysis_retained AS SELECT * FROM input_quality WHERE retained IS TRUE")
    check_counts("ANALYSIS_RECORDS", scalar(db, "SELECT count(*) FROM analysis_retained"),
                 expected["analysis_records"])
    check_counts("ANALYSIS_MOLECULES", scalar(db, "SELECT count(DISTINCT molecule_id) FROM analysis_retained"),
                 expected["analysis_molecules"])
    # Exclusion is role-based; the original embargo/QC evidence remains in the source.
    unassigned = "(NOT coalesce(member_train,false) AND NOT coalesce(member_full,false))"
    check_counts("UNASSIGNED_RECORDS", scalar(db, "SELECT count(*) FROM analysis_retained WHERE " + unassigned),
                 expected["excluded_records"])
    check_counts("UNASSIGNED_MOLECULES", scalar(db, "SELECT count(DISTINCT molecule_id) FROM analysis_retained WHERE " + unassigned),
                 expected["excluded_molecules"])
    if scalar(db, "SELECT count(*) FROM analysis_retained WHERE (lower(split)='unassigned') != " + unassigned):
        raise RuntimeError("UNASSIGNED_ROLE_AND_SPLIT_DISAGREE")
    excluded_origins = rows(db, "SELECT legacy_QA_status,count(*) AS records,count(DISTINCT molecule_id) AS molecules "
                            "FROM analysis_retained WHERE " + unassigned + " GROUP BY legacy_QA_status")
    copy(db, "SELECT * FROM analysis_retained WHERE " + unassigned, args.out / "excluded_unassigned_index.parquet")
    db.execute("CREATE VIEW eligible AS SELECT *, substr(reidentified_inchikey,1,14)||':'||"
               "right(reidentified_inchikey,1) AS wp5_identity_key FROM analysis_retained WHERE NOT " + unassigned)
    check_counts("FORMAL_RECORDS", scalar(db, "SELECT count(*) FROM eligible"), expected["formal_records"])
    check_counts("FORMAL_MOLECULES", scalar(db, "SELECT count(DISTINCT molecule_id) FROM eligible"), expected["formal_molecules"])
    check_counts("FORMAL_UNIQUE_RECORDS", scalar(db, "SELECT count(DISTINCT record_id) FROM eligible"), expected["formal_records"])
    if scalar(db, "SELECT count(*) FROM eligible WHERE source_path IS NULL OR real_index IS NULL "
                  "OR record_payload_sha256 IS NULL OR molecule_id IS NULL "
                  "OR stored_inchikey IS NULL OR reidentified_inchikey IS NULL "
                  "OR NOT regexp_full_match(stored_inchikey,'[A-Z]{14}-[A-Z]{10}-[A-Z]') "
                  "OR NOT regexp_full_match(reidentified_inchikey,'[A-Z]{14}-[A-Z]{10}-[A-Z]') "
                  "OR substr(stored_inchikey,1,14)!=substr(reidentified_inchikey,1,14) "
                  "OR right(stored_inchikey,1)!=right(reidentified_inchikey,1) "
                  "OR member_train=member_full OR (member_routine AND NOT member_full)"):
        raise RuntimeError("FORMAL_SOURCE_POINTER_OR_AUTHORITY_OR_RELAXED_IDENTITY_INVARIANT")
    db.execute("CREATE TABLE mol_base AS SELECT molecule_id,count(*) AS records,"
               "max(heavy_atoms) AS max_heavy_atoms,max(total_atoms) AS max_total_atoms,"
               "bool_or(member_train) AS original_train,bool_or(member_full) AS original_full,"
               "bool_or(member_routine) AS original_routine,"
               "count(DISTINCT reidentified_inchikey) AS full_key_variant_count,"
               "count(DISTINCT wp5_identity_key) AS identity_key_count FROM eligible GROUP BY molecule_id")
    if scalar(db, "SELECT count(*) FROM mol_base WHERE original_train AND original_full"):
        raise RuntimeError("SOURCE_MOLECULE_STRADDLES_NATIVE_AUTHORITY")

    # Only keys shared by multiple molecules can change a component. All other
    # molecule/key leaves are retained implicitly; all keys of a molecule still
    # participate, so a molecule bridging several shared keys links their groups.
    parent = {}
    def find(value):
        parent.setdefault(value, value)
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root
    def union(left, right):
        a, b = find(left), find(right)
        if a != b:
            if a > b:
                a, b = b, a
            parent[b] = a
    cursor = db.execute("SELECT wp5_identity_key,list(DISTINCT molecule_id ORDER BY molecule_id) "
                        "FROM eligible GROUP BY wp5_identity_key HAVING count(DISTINCT molecule_id)>1 "
                        "ORDER BY wp5_identity_key")
    shared_keys = 0
    while True:
        batch = cursor.fetchmany(1024)
        if not batch:
            break
        for key, molecules in batch:
            shared_keys += 1
            anchor = molecules[0]
            for molecule in molecules:
                union(anchor, molecule)
    mapping = [(molecule, find(molecule)) for molecule in sorted(parent)]
    arrow_mapping = pa.table({"molecule_id": [r[0] for r in mapping],
                              "component_id": [r[1] for r in mapping]},
                             schema=pa.schema([("molecule_id", pa.string()), ("component_id", pa.string())]))
    db.register("shared_components_arrow", arrow_mapping)
    db.execute("CREATE TABLE mol_component AS SELECT m.*,coalesce(c.component_id,m.molecule_id) "
               "AS component_id FROM mol_base m LEFT JOIN shared_components_arrow c USING(molecule_id)")
    db.execute("CREATE TABLE component_summary AS SELECT component_id,count(*) AS molecules,"
               "sum(records) AS records,bool_or(original_full) AS anchored_by_full,"
               "sum(CASE WHEN original_train THEN 1 ELSE 0 END) AS original_train_molecules,"
               "sum(CASE WHEN original_full THEN 1 ELSE 0 END) AS original_full_molecules "
               "FROM mol_component GROUP BY component_id")
    db.execute("CREATE TABLE molecule_index AS SELECT m.*,s.anchored_by_full AS component_anchored_by_full,"
               "CASE WHEN s.anchored_by_full THEN 'full' ELSE 'train' END AS split,"
               "(s.anchored_by_full AND m.original_train) AS moved_train_to_full,"
               "CASE WHEN max_heavy_atoms<=22 THEN 1 WHEN max_heavy_atoms<=26 THEN 2 "
               "WHEN max_heavy_atoms<=30 THEN 3 WHEN max_heavy_atoms<=36 THEN 4 ELSE 5 END AS file_group "
               "FROM mol_component m JOIN component_summary s USING(component_id)")
    # Cache annotations are read and joined, never recomputed from raw coordinates.
    db.execute("CREATE VIEW stereo_pairs AS SELECT * FROM read_parquet(" + quoted(args.stereo) + ")")
    if scalar(db, "SELECT count(*) FROM (SELECT source_smiles,reidentified_smiles FROM stereo_pairs "
                  "GROUP BY source_smiles,reidentified_smiles HAVING count(*)>1)"):
        raise RuntimeError("STEREO_PAIR_CACHE_NOT_UNIQUE")
    db.execute("CREATE VIEW stereo_consistency AS SELECT * FROM read_parquet(" + quoted(args.consistency) + ")")
    db.execute("CREATE TABLE mol_stereo AS SELECT molecule_id,"
               "bool_or(defined_chiral_variants>1) AS chirality_conflict,"
               "bool_or(defined_ez_variants>1) AS ez_conflict,"
               "max(full_geometry_key_variants) AS full_key_variants,"
               "sum(unresolved_conformers) AS unresolved_stereo_conformers "
               "FROM stereo_consistency GROUP BY molecule_id")
    excluded_columns = {"split", "membership", "member_train", "member_full", "member_routine", "file_bin"}
    preserved = ",".join("e." + qi(c) for c in columns if c not in excluded_columns)
    original_file_bin = "e.file_bin" if "file_bin" in columns else "NULL::INTEGER"
    formal_select = (
        "SELECT " + preserved + ",e.split AS original_split,e.membership AS original_membership,"
        "e.member_train AS original_member_train,e.member_full AS original_member_full,"
        "e.member_routine AS original_member_routine," + original_file_bin + " AS original_file_bin,"
        "m.split,upper(m.split) AS new_role,(m.split='train') AS member_train,(m.split='full') AS member_full,"
        "e.member_routine AS member_routine,"
        "list_filter([CASE WHEN m.split='train' THEN 'train' ELSE NULL END,"
        "CASE WHEN m.split='full' THEN 'full' ELSE NULL END,"
        "CASE WHEN e.member_routine THEN 'routine' ELSE NULL END],x->x IS NOT NULL) AS membership,"
        "m.component_id,m.component_anchored_by_full,m.moved_train_to_full,"
        "m.max_heavy_atoms AS molecule_max_heavy_atoms,m.max_total_atoms AS molecule_max_total_atoms,"
        "m.file_group,m.file_group AS file_bin,"
        "CASE m.file_group WHEN 1 THEN 'Nheavy_le22' WHEN 2 THEN 'Nheavy_23_26' "
        "WHEN 3 THEN 'Nheavy_27_30' WHEN 4 THEN 'Nheavy_31_36' ELSE 'Nheavy_gt36' END AS file_group_label,"
        "e.wp5_identity_key AS wp5_backbone_proton_key,"
        "p.difference_class AS stereo_pair_difference_class,"
        "CASE WHEN p.pair_id IS NULL THEN NULL WHEN p.parse_error IS NOT NULL THEN 'UNRESOLVED' "
        "WHEN p.source_inchikey_from_smiles IS DISTINCT FROM e.stored_inchikey "
        "OR p.generated_inchikey_from_smiles IS DISTINCT FROM e.reidentified_inchikey "
        "THEN 'KEY_REPRODUCTION_MISMATCH' ELSE p.difference_class END AS stereo_difference_class,"
        "p.chirality_changed AS stereo_chirality_changed,"
        "p.ez_changed AS stereo_ez_changed,p.other_layer_changed AS stereo_other_layer_changed,"
        "p.source_has_chiral AS source_smiles_has_chiral,p.source_has_ez AS source_smiles_has_ez,"
        "p.parse_error AS stereo_cache_parse_error,"
        "(e.I01_relaxed_to_T01 AND p.difference_class IS NULL) AS QC_stereo_cache_missing,"
        "CASE WHEN s.molecule_id IS NOT NULL THEN s.chirality_conflict "
        "WHEN m.full_key_variant_count<=1 THEN FALSE ELSE NULL END AS QC_molecule_chirality_conflict,"
        "CASE WHEN s.molecule_id IS NOT NULL THEN s.ez_conflict "
        "WHEN m.full_key_variant_count<=1 THEN FALSE ELSE NULL END AS QC_molecule_ez_conflict,"
        "(s.molecule_id IS NOT NULL) AS QC_stereo_consistency_assessed,"
        "s.unresolved_stereo_conformers AS QC_molecule_unresolved_stereo_conformers "
        "FROM eligible e JOIN molecule_index m USING(molecule_id) "
        "LEFT JOIN stereo_pairs p ON e.smiles=p.source_smiles AND e.reidentified_smiles=p.reidentified_smiles "
        "LEFT JOIN mol_stereo s ON e.molecule_id=s.molecule_id")
    db.execute("CREATE VIEW formal_joined AS " + formal_select)
    db.execute("CREATE TABLE formal AS SELECT *,"
               "(stereo_difference_class='KEY_REPRODUCTION_MISMATCH') AS QC_key_reproduction_mismatch,"
               "(stereo_difference_class='OTHER_LAYER_PRESENT') AS QC_other_layer_present,"
               "(I01_relaxed_to_T01 AND stereo_difference_class='KEY_REPRODUCTION_MISMATCH') "
               "AS QC_key_reproduction_mismatch_accepted_difference,"
               "(I01_relaxed_to_T01 AND stereo_difference_class='OTHER_LAYER_PRESENT') "
               "AS QC_other_layer_accepted_difference FROM formal_joined")
    check_counts("FORMAL_AFTER_QC_JOINS", scalar(db, "SELECT count(*) FROM formal"), expected["formal_records"])
    check_counts("FORMAL_MOLECULE_INDEX", scalar(db, "SELECT count(*) FROM molecule_index"), expected["formal_molecules"])
    for name, condition in {
        "ROUTINE_OUTSIDE_FULL": "member_routine AND NOT member_full",
        "TRAIN_AND_FULL": "member_train AND member_full",
        "UNASSIGNED": "NOT member_train AND NOT member_full",
    }.items():
        check_counts(name, scalar(db, "SELECT count(*) FROM formal WHERE " + condition), 0)
    check_counts("ROUTINE_PRESERVED", scalar(db, "SELECT count(*) FROM formal WHERE member_routine"),
                 scalar(db, "SELECT count(*) FROM eligible WHERE member_routine"))
    identity_checks = []
    for name, expression in [
        ("source_full", "stored_inchikey"),
        ("reidentified_full", "reidentified_inchikey"),
        ("reidentified_connectivity14_plus_protonation", "wp5_backbone_proton_key"),
    ]:
        query = ("SELECT " + expression + " AS identity_key,count(*) AS records,"
                 "bool_or(member_train) AS in_train,bool_or(member_full) AS in_full "
                 "FROM formal GROUP BY " + expression)
        shared = scalar(db, "SELECT count(*) FROM (" + query + ") WHERE in_train AND in_full")
        identity_checks.append({"identity_kind": name, "TRAIN_FULL_shared_keys": shared})
        check_counts("ZERO_LEAKAGE_" + name, shared, 0)
    if scalar(db, "SELECT count(*) FROM (SELECT molecule_id,count(DISTINCT split) AS roles,"
                  "count(DISTINCT file_group) AS files FROM formal GROUP BY molecule_id) WHERE roles!=1 OR files!=1"):
        raise RuntimeError("FORMAL_MOLECULE_SPLIT_OR_FILE_NOT_WHOLE")
    copy(db, "SELECT * FROM formal ORDER BY file_group,molecule_id,conformer_id,record_id",
         args.out / "formal_record_index.parquet")
    copy(db, "SELECT * FROM molecule_index ORDER BY file_group,molecule_id",
         args.out / "molecule_index.parquet")
    copy(db, "SELECT * FROM molecule_index WHERE moved_train_to_full ORDER BY molecule_id",
         args.out / "split_migrations.parquet")
    copy(db, "SELECT * FROM component_summary ORDER BY component_id",
         args.out / "identity_components.parquet")
    counts = rows(db, "SELECT split,count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM formal GROUP BY split ORDER BY split")
    groups = rows(db, "SELECT file_group,min(file_group_label) AS label,count(*) AS records,"
                     "count(DISTINCT molecule_id) AS molecules,max(molecule_max_heavy_atoms) AS max_heavy_atoms "
                     "FROM formal GROUP BY file_group ORDER BY file_group")
    migration = rows(db, "SELECT count(*) AS moved_molecules,coalesce(sum(records),0) AS moved_records "
                        "FROM molecule_index WHERE moved_train_to_full")[0]
    qc = rows(db, "SELECT count(*) FILTER(WHERE T01) AS T01_records,"
                  "count(*) FILTER(WHERE T01_original) AS T01_original_records,"
                  "count(*) FILTER(WHERE S01) AS S01_records,count(*) FILTER(WHERE S01_backbone) AS S01_backbone_records,"
                  "count(*) FILTER(WHERE B01) AS B01_records,"
                  "count(*) FILTER(WHERE QC_key_reproduction_mismatch) AS key_reproduction_records,"
                  "count(*) FILTER(WHERE QC_other_layer_present) AS other_layer_records,"
                  "count(*) FILTER(WHERE QC_key_reproduction_mismatch_accepted_difference) AS accepted_difference_key_reproduction_records,"
                  "count(*) FILTER(WHERE QC_other_layer_accepted_difference) AS accepted_difference_other_layer_records,"
                  "count(*) FILTER(WHERE QC_stereo_cache_missing) AS stereo_cache_missing_records,"
                  "count(DISTINCT molecule_id) FILTER(WHERE QC_molecule_chirality_conflict) AS chirality_conflict_molecules,"
                  "count(DISTINCT molecule_id) FILTER(WHERE QC_molecule_ez_conflict) AS ez_conflict_molecules,"
                  "count(DISTINCT molecule_id) FILTER(WHERE QC_molecule_chirality_conflict IS NULL) AS chirality_consistency_unknown_molecules,"
                  "count(DISTINCT molecule_id) FILTER(WHERE QC_molecule_ez_conflict IS NULL) AS ez_consistency_unknown_molecules,"
                  "count(*) FILTER(WHERE H01_abs_energy_per_atom IS NULL) AS H01_unknown_records,"
                  "count(*) FILTER(WHERE S02_delta_energy_kcal_mol IS NULL) AS S02_unknown_records "
                  "FROM formal")[0]
    routine = rows(db, "SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM formal WHERE member_routine")[0]
    routine["subset_of_FULL"] = True
    strata = rows(db, "SELECT CASE WHEN molecule_max_heavy_atoms<=10 THEN '0_10' WHEN molecule_max_heavy_atoms<=20 THEN '11_20' WHEN molecule_max_heavy_atoms<=30 THEN '21_30' WHEN molecule_max_heavy_atoms<=50 THEN '31_50' WHEN molecule_max_heavy_atoms<=75 THEN '51_75' WHEN molecule_max_heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END AS size_stratum,count(*) AS records,"
                      "count(DISTINCT molecule_id) AS molecules,sum(total_atoms) AS atoms,"
                      "max(molecule_max_heavy_atoms) AS max_heavy_atoms FROM formal GROUP BY size_stratum ORDER BY min(molecule_max_heavy_atoms)")
    check_counts("FORMAL_STRATA_RECORDS", sum(r["records"] for r in strata), expected["formal_records"])
    check_counts("FORMAL_STRATA_MOLECULES", sum(r["molecules"] for r in strata), expected["formal_molecules"])
    db.close()
    import shutil
    shutil.rmtree(spill)
    paths = [Path(__file__), args.input, args.stereo, args.consistency]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.threads, len(paths))) as pool:
        digests = list(pool.map(sha256, paths))
    save(args.out / "manifest.json", {
        "status": "WP5_FORMAL_POPULATION_CLOSED", "job_id": os.environ["SLURM_JOB_ID"],
        "seconds": time.monotonic() - started, "duckdb_threads": args.threads,
        "duckdb_memory_limit_gb": args.memory_gb, "local_spill_directory_removed": str(spill),
        "fixture": bool(args.expected_counts), **expected, "new_QM_calls": 0, "original_data_written": False, "lmdb_1_created": False,
        "configuration": {"I01": "connectivity14_plus_protonation_last_character",
                          "excluded_unassigned": True, "whole_molecule_components": True,
                          "FULL_anchor_promotes_entire_TRAIN_component": True,
                          "routine_is_FULL_monitor_subset": True, "file_boundaries": [22,26,30,36],
                          "QC_annotations_not_exclusion_rules": True,
                          "stereo_conflicts_are_prior_cached_molecule_annotations": True},
        "steps": [{"name": "analysis_retained", "records": expected["analysis_records"], "molecules": expected["analysis_molecules"]},
                  {"name": "excluded_UNASSIGNED", "records": expected["excluded_records"], "molecules": expected["excluded_molecules"]},
                  {"name": "formal_before_and_after_components_and_QC", "records": expected["formal_records"], "molecules": expected["formal_molecules"]}],
        "roles": counts, "routine": routine, "excluded_origins": excluded_origins,
        "strata": strata, "stratum_policy": "Each whole molecule uses its maximum formal-retained heavy-atom count.",
        "file_groups": groups, "migration": migration, "identity_checks": identity_checks,
        "component_shared_identity_keys": shared_keys, "QC": qc,
        "annotation_reference_scope": {"prior_analysis_chirality_conflict_molecules": 28146,
                                      "prior_analysis_EZ_conflict_molecules": 8108,
                                      "prior_analysis_key_reproduction_records": 42088,
                                      "prior_analysis_other_layer_records": 2263,
                                      "note": "References describe the prior analysis domain; formal-domain counts are QC above. No added scientific exclusions."},
        "inputs": [{"path": str(p), "bytes": p.stat().st_size, "sha256": digest}
                   for p, digest in zip(paths, digests)],
        "outputs": {"record_index": str(args.out / "formal_record_index.parquet"),
                    "molecule_index": str(args.out / "molecule_index.parquet"),
                    "split_migrations": str(args.out / "split_migrations.parquet"),
                    "identity_components": str(args.out / "identity_components.parquet")},
    })
    print(json.dumps({"status": "WP5_FORMAL_POPULATION_CLOSED", "records": expected["formal_records"],
                      "molecules": expected["formal_molecules"], "migration": migration}, ensure_ascii=False))

if __name__ == "__main__":
    main()
