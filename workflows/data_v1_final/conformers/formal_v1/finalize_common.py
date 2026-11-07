"""Freeze full TRAIN+ROUTINE common membership only after all attempts close."""
from __future__ import annotations
import argparse
from collections import Counter
import concurrent.futures as cf
import gzip
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path

from full_common import IO,KERNEL_SHA,authority_roles,config,formal_source,q,require_actual_accounting,require_budget_review,runtime


def normalize_package(ref):
    import numpy as np
    IO.require_pin(ref)
    packet=json.loads(gzip.decompress(Path(ref["path"]).read_bytes()))
    mid=packet["summary"]["molecule_id"]
    if mid!=ref["molecule_id"]:raise ValueError("PACKAGE_MOLECULE_ID_MISMATCH")
    rows=[];indices=set();candidate_keys=set();numbers=None
    for position,row in enumerate(packet["conformers"]):
        if type(row["sprime_conf_idx"]) is not int or any(type(z) is not int or not 1<=z<=118 for z in row["atomic_numbers"]):
            raise ValueError("ATOM_NUMBERS_AND_CONFORMER_ID_MUST_REMAIN_INTEGERS")
        if type(row["below_dedup_threshold"]) is not bool:
            raise ValueError("EXPLICIT_BOOLEAN_DEDUP_FLAG_REQUIRED")
        index=int(row["sprime_conf_idx"])
        if index!=position or index in indices or row["molecule_id"]!=mid:raise ValueError("DUPLICATE_OR_REORDERED_SUPPLEMENT_CONFORMER")
        indices.add(index)
        z=np.asarray(row["atomic_numbers"],dtype="<i8")
        xyz=np.asarray(row["coordinates"],dtype="<f8")
        atom_sha=hashlib.sha256(z.tobytes()).hexdigest()
        if row["status"]!="SUCCESS" or row["converged"] is not True or atom_sha!=row["atom_order_sha256"] or IO.geometry_sha(z,xyz)!=row["geometry_sha256"]:
            raise ValueError("SUPPLEMENT_COORDINATES_OR_ATOM_ORDER_INVALID")
        if row["source_record_id"]!=packet["summary"]["source_record_id"] or atom_sha!=packet["summary"]["atom_order_sha256"]:
            raise ValueError("SUPPLEMENT_SOURCE_ANCHOR_OR_SUMMARY_ATOM_ORDER_CHANGED")
        if numbers is not None and numbers!=z.tolist():raise ValueError("SUPPLEMENT_ATOM_SEQUENCE_CHANGED")
        numbers=z.tolist()
        origin=row["origin"]
        if origin=="accepted_sprime":
            if row["original_sprime_conf_idx"] is None:raise ValueError("OLD_ORIGINAL_INDEX_MISSING")
        elif origin in {"data_v1_fill_10N","data_v1_fill_retry1"}:
            key=(row["seed"],row["candidate_id"])
            if key in candidate_keys or type(row["candidate_id"]) is not int or row["candidate_id"]<0:raise ValueError("GENERATED_CANDIDATE_REUSED_OR_MISSING")
            candidate_keys.add(key)
        else:raise ValueError("UNREGISTERED_GEOMETRY_ORIGIN")
        if not math.isfinite(float(row["uff_energy_kcal_mol"])):
            raise ValueError("NONFINITE_ACCEPTED_UFF_ENERGY")
        rows.append({"molecule_id":mid,"kernel_sprime_conf_idx":index,"origin":origin,
            "original_sprime_conf_idx":row["original_sprime_conf_idx"],"candidate_id":row["candidate_id"],
            "seed":row["seed"],"uff_energy_kcal_mol":float(row["uff_energy_kcal_mol"]),
            "atom_order_sha256":atom_sha,"geometry_sha256":row["geometry_sha256"],
            "source_record_id":row["source_record_id"],"below_dedup_threshold":bool(row["below_dedup_threshold"]),
            "source_path":ref["path"],"source_sha256":ref["sha256"],"source_bytes":ref["bytes"],
            "source_format":"reproduction_json_gz","source_member":"conformers","source_row_index":position})
    return {"molecule_id":mid,"summary":packet["summary"],"rows":rows,"atomic_numbers":numbers,"source":ref}


def merge_counts(old_count,new_rows,expected):
    generated=[row for row in new_rows if row["origin"]!="accepted_sprime"]
    if any(row["kernel_sprime_conf_idx"]<old_count for row in generated):
        raise ValueError("NEW_CANDIDATE_OVERWRITES_OLD_CANONICAL_SLOT")
    if len({(row["seed"],row["candidate_id"]) for row in generated})!=len(generated):
        raise ValueError("DUPLICATE_NEW_CANDIDATE")
    if sorted(row["kernel_sprime_conf_idx"] for row in generated)!=list(range(old_count,old_count+len(generated))):
        raise ValueError("NEW_CANONICAL_CONFORMER_INDICES_HAVE_GAPS")
    if old_count+len(generated)>expected:raise ValueError("MERGED_CONFORMER_COUNT_EXCEEDS_ORIGINAL_N")
    # Old rows in a replacement view are verification references, never added twice.
    return old_count+len(generated)


def membership(row):
    reasons=[]
    in_scope=row["effective_role"] in {"TRAIN","VAL"}
    if not in_scope:reasons.append("OUTSIDE_TRAIN_ROUTINE_VAL")
    if row["S_usable_conformers"]!=row["S_conformers"] or row["records"]!=row["S_conformers"] or row["S_conformers"]<=0:
        reasons.append("INCOMPLETE_PM7_GEOMETRY_OR_IDENTITY")
    if row["Sprime_status"]=="UFF_UNSUPPORTED":reasons.append("UFF_UNSUPPORTED")
    if row["merged_uff_count"]<row["S_conformers"]:reasons.append("INSUFFICIENT_ACCEPTED_SPRIME")
    included=not reasons
    return {"common_population":included,"common_population_v1":included,
            "exclusion_reasons":reasons,"pprime_two_conformers_pending":included and row["merged_uff_count"]<2}


def exclusion_gates(rows):
    mother=[r for r in rows if r["effective_role"] in {"TRAIN","VAL"}]
    if not mother:raise ValueError("EMPTY_TRAIN_VAL_DENOMINATOR")
    excluded=[r for r in mother if not r["common_population"]]
    before=Counter(z for row in mother for z in set(row["elements_atomic_numbers"]))
    after=Counter(z for row in mother if row["common_population"] for z in set(row["elements_atomic_numbers"]))
    element_rows=[{"atomic_number":z,"before":n,"after":after[z],"excluded":n-after[z],
                   "excluded_fraction":(n-after[z])/n,"se_exception":z==34} for z,n in sorted(before.items())]
    failed=[row for row in element_rows if row["atomic_number"]!=34 and row["excluded"]*5>row["before"]]
    overall_bad=len(excluded)*50>len(mother)
    return {"mother_molecules":len(mother),"excluded_molecules":len(excluded),
            "excluded_fraction":len(excluded)/len(mother),"overall_gt2_percent":overall_bad,
            "elements":element_rows,"non_se_elements_gt20_percent":failed,
            "passed":not overall_bad and not failed}


def scaffold_chunk(rows):
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    result=[]
    for mid,smiles in rows:
        try:
            mol=Chem.MolFromSmiles(smiles)
            if mol is None:raise ValueError("SMILES_PARSE_FAILED")
            core=MurckoScaffold.GetScaffoldForMol(mol)
            generic=MurckoScaffold.MakeScaffoldGeneric(core)
            key=Chem.MolToSmiles(generic,canonical=True,isomericSmiles=False) or "ACYCLIC_EMPTY_MURCKO"
            status="SUCCESS"
        except Exception as exc:key="SCAFFOLD_UNAVAILABLE";status=str(exc)
        result.append({"molecule_id":mid,"generic_scaffold":key,"scaffold_status":status})
    return result


def require_plan_lineage(child_ref,root_ref,config_ref):
    seen=set()
    for _ in range(128):
        path=IO.require_pin(child_ref)
        if child_ref["sha256"] in seen:raise ValueError("PLAN_LINEAGE_CYCLE")
        seen.add(child_ref["sha256"]);plan=json.loads(path.read_text())
        if plan["status"]!="FULL_SPRIME_PLAN_FROZEN" or plan["config"]!=config_ref or plan["kernel_sha256"]!=KERNEL_SHA:
            raise ValueError("BATCH_IS_OUTSIDE_THIS_SCIENTIFIC_PLAN")
        approval=json.loads(IO.require_pin(plan["root_review"]).read_text())
        if approval.get("status")!="APPROVED" or approval.get("draft_reference")!=plan["draft"]:
            raise ValueError("PLAN_ROOT_REVIEW_BINDING_INVALID")
        require_budget_review(float(plan["estimated_formal_core_hours"]),approval)
        if child_ref==root_ref:return
        child_ref=plan.get("parent_plan")
        if not child_ref:raise ValueError("BATCH_PLAN_NOT_DESCENDED_FROM_ROOT_PLAN")
    raise ValueError("PLAN_LINEAGE_TOO_DEEP")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True);p.add_argument("--completion-index",type=Path,required=True)
    p.add_argument("--root-preflight",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();value=config(a.config);env=runtime(value,a.root_preflight,a.config)
    index=json.loads(a.completion_index.read_text())
    if index.get("status")!="ALL_SPRIME_ATTEMPTS_TERMINAL" or not index.get("batch_closures"):
        raise ValueError("PILOT_ONLY_OR_INCOMPLETE_WORK_NEVER_COMMON_FROZEN")
    root_plan=json.loads(IO.require_pin(index["root_plan"]).read_text())
    if root_plan["status"]!="FULL_SPRIME_PLAN_FROZEN" or root_plan["pilot_only"] is not False or root_plan["config"]!=IO.reference(a.config):
        raise ValueError("MATCHING_ACTUAL_FORMAL_PLAN_REQUIRED")
    IO.require_pin(root_plan["root_review"])
    draft=json.loads(IO.require_pin(root_plan["draft"]).read_text())
    pilot_decision=json.loads(IO.require_pin(draft["pilot_review"]).read_text())
    pilot_accounting,_=require_actual_accounting(IO.require_pin(pilot_decision["pilot_accounting"]))
    actual_parents={str(row["job_id"]):row for row in pilot_accounting["parents"]}
    imports=json.loads(IO.require_pin(root_plan["pilot_imports"]).read_text())
    source_refs=[row["source"] for row in imports]
    for closure in index["batch_closures"]:
        receipt=json.loads(IO.require_pin(closure["receipt"]).read_text())
        if receipt["status"] not in {"FORMAL_BATCH_COMPLETED_REQUIRES_ACTUAL_ACCOUNTING","FORMAL_BATCH_PARTIAL_UNSTARTED_ONLY"} or receipt.get("errors") or receipt.get("unknown_started_tasks"):
            raise ValueError("FAILED_UNKNOWN_OR_UNCLOSED_BATCH_CANNOT_FREEZE_COMMON")
        if receipt.get("stop_reason") not in {None,"WALL_DISPATCH_CUTOFF"}:
            raise ValueError("BATCH_STOP_RULE_MUST_BE_REPORTED_NOT_BYPASSED")
        if receipt["kernel_sha256"]!=KERNEL_SHA or receipt["config"]!=IO.reference(a.config) or receipt["recipe_config"]!=value["recipe_config"]:
            raise ValueError("BATCH_SCIENTIFIC_SOURCE_OR_CONFIG_CHANGED")
        require_plan_lineage(receipt["plan"],index["root_plan"],IO.reference(a.config))
        if receipt["parquet_readback"]["status"]!="ALL_FORMAL_BATCH_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED":
            raise ValueError("ACTUAL_BATCH_FLOAT64_READBACK_REQUIRED")
        accounting,_=require_actual_accounting(IO.require_pin(closure["accounting"]),receipt["runtime"]["job_id"])
        parent=next(row for row in accounting["parents"] if str(row["job_id"])==str(receipt["runtime"]["job_id"]))
        for row in accounting["parents"]:
            jid=str(row["job_id"])
            if jid in actual_parents and actual_parents[jid]!=row:
                raise ValueError("CONFLICTING_PARENT_ACCOUNTING_CLOSURES")
            actual_parents[jid]=row
        if parent["alloc_cpus"]*parent["elapsed_raw_seconds"]>1.5*receipt["estimated_allocated_core_seconds"]:
            raise ValueError("ACTUAL_BATCH_COST_GT1P5_REQUIRES_STOP_REPORT_NOT_FREEZE")
        IO.require_pin(receipt["reproduction_manifest"])
        source_refs.extend(json.loads(Path(receipt["reproduction_manifest"]["path"]).read_text()))
        for ref in receipt["outputs"]:IO.require_pin(ref)
    # Additional actual analysis/preparation or failed-parent rows are kept in the
    # same budget scope when supplied by Root; no step rows are charged twice.
    for ref in index.get("additional_accounting",[]):
        accounting,_=require_actual_accounting(IO.require_pin(ref))
        for row in accounting["parents"]:
            jid=str(row["job_id"])
            if jid in actual_parents and actual_parents[jid]!=row:
                raise ValueError("CONFLICTING_PARENT_ACCOUNTING_CLOSURES")
            actual_parents[jid]=row
    actual_core_hours=sum(int(row["alloc_cpus"])*int(row["elapsed_raw_seconds"]) for row in actual_parents.values())/3600
    root_approval=json.loads(IO.require_pin(root_plan["root_review"]).read_text())
    require_budget_review(actual_core_hours,root_approval)
    packages={};expected_old={};numbers={};new_metadata=[]
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for packet in pool.map(normalize_package,source_refs):
            mid=packet["molecule_id"]
            if mid in packages:raise ValueError("MOLECULE_ATTEMPTED_MORE_THAN_ONCE")
            packages[mid]=packet["summary"]
            if packet["atomic_numbers"] is not None:numbers[mid]=packet["atomic_numbers"]
            for row in packet["rows"]:
                if row["origin"]=="accepted_sprime":expected_old[(mid,int(row["original_sprime_conf_idx"]))]=row
                else:new_metadata.append(row)
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    roles_ref,role_refs=authority_roles(value)
    db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='40GB'")
    db.execute("CREATE TABLE p AS SELECT * FROM read_parquet("+q(value["per_molecule"]["path"])+")")
    db.execute("CREATE TABLE roles AS SELECT * FROM read_parquet(["+",".join(q(r["path"]) for r in role_refs)+"])")
    deficits=db.execute("SELECT molecule_id FROM p WHERE Sprime_conformers<S_conformers AND Sprime_status<>'UFF_UNSUPPORTED'").fetchall()
    if {r[0] for r in deficits}!=set(packages):
        raise ValueError("NOT_ALL_ORIGINAL_DEFICITS_HAVE_ONE_TERMINAL_OUTCOME")
    old_manifest=json.loads(IO.require_pin(value["sprime_manifest"]).read_text())
    old_refs=[r for r in old_manifest["references"] if r["kind"]=="conformers"]
    # This future node20 analysis stage performs the full baseline hashes.
    # Login submission guards bind only the small authority manifests.
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(IO.require_pin,old_refs))
    # Scalar-only baseline view preserves physical positions without copying coordinates.
    paths="["+",".join(q(r["path"]) for r in old_refs)+"]"
    db.execute("""CREATE TABLE old AS SELECT molecule_id,sprime_conf_idx AS original_sprime_conf_idx,
        row_number() OVER(PARTITION BY molecule_id ORDER BY sprime_conf_idx)-1 AS canonical_sprime_conf_idx,
        filename AS source_path,file_row_number AS source_row_index,uff_energy_kcal_mol,
        atom_order_sha256,source_record_id,seed FROM read_parquet(PATHS,filename=true,file_row_number=true)
        WHERE status='SUCCESS' AND converged IS TRUE""".replace("PATHS",paths))
    if db.execute("SELECT count(*) FROM (SELECT molecule_id,original_sprime_conf_idx FROM old GROUP BY ALL HAVING count(*)>1)").fetchone()[0]:
        raise ValueError("DUPLICATE_OLD_CONFORMER_KEY")
    mismatch=db.execute("""SELECT count(*) FROM p LEFT JOIN
        (SELECT molecule_id,count(*) AS n FROM old GROUP BY molecule_id) b USING(molecule_id)
        WHERE coalesce(b.n,0)<>p.Sprime_conformers""").fetchone()[0]
    if mismatch:raise ValueError("OLD_STRICT_USABLE_COUNTS_CHANGED")
    # Only old rows referenced by replacements need coordinate re-read; unchanged
    # physical rows retain the original closed file and physical row locator.
    wanted=list(numbers)
    checked=set()
    for ref in old_refs:
        table=pq.read_table(ref["path"],columns=["molecule_id","sprime_conf_idx","coordinates","atom_order_sha256","source_record_id","seed","status","converged"],
            filters=[("molecule_id","in",wanted),("status","=","SUCCESS"),("converged","=",True)])
        for row in table.to_pylist():
            key=(row["molecule_id"],int(row["sprime_conf_idx"]))
            expected=expected_old.get(key)
            if expected is None:continue
            if row["atom_order_sha256"]!=expected["atom_order_sha256"] or row["source_record_id"]!=expected["source_record_id"] or row["seed"]!=expected["seed"] or IO.geometry_sha(numbers[key[0]],row["coordinates"])!=expected["geometry_sha256"]:
                raise ValueError("OLD_ACCEPTED_COORDINATE_OR_ATOM_ORDER_NOT_CONSERVED")
            checked.add(key)
    if checked!=set(expected_old):raise ValueError("OLD_REPLACEMENT_REFERENCE_NOT_FOUND")
    if expected_old:
        db.register("old_expectations",pa.Table.from_pylist(list(expected_old.values())))
        if db.execute("""SELECT count(*) FROM old_expectations e JOIN old o
            ON e.molecule_id=o.molecule_id AND e.original_sprime_conf_idx=o.original_sprime_conf_idx
            WHERE e.kernel_sprime_conf_idx<>o.canonical_sprime_conf_idx""").fetchone()[0]:
            raise ValueError("OLD_CONFORMER_ID_RENUMBERING_NOT_CONSERVED")
    old_counts=dict(db.execute("SELECT molecule_id,count(*) FROM old GROUP BY molecule_id").fetchall())
    p_rows={r["molecule_id"]:r for r in db.execute("SELECT * FROM p").fetch_arrow_table().to_pylist()}
    by_new={}
    for row in new_metadata:by_new.setdefault(row["molecule_id"],[]).append(row)
    counts=[]
    for mid,packet in packages.items():
        count=merge_counts(old_counts.get(mid,0),by_new.get(mid,[]),p_rows[mid]["S_conformers"])
        counts.append({"molecule_id":mid,"merged_uff_count":count,"fill_status":packet["status"]})
    db.register("filled",pa.Table.from_pylist(counts))
    db.execute("""CREATE TABLE membership AS SELECT p.*,roles.source_role,roles.effective_role,roles.records,
        roles.file_group,roles.legacy_routine_molecule,coalesce(filled.merged_uff_count,p.Sprime_conformers) AS merged_uff_count,
        filled.fill_status FROM p JOIN roles USING(molecule_id) LEFT JOIN filled USING(molecule_id)""")
    rows=db.execute("SELECT * FROM membership").fetch_arrow_table().to_pylist()
    if len(rows)!=value["expected_source_molecules"] or len({r["molecule_id"] for r in rows})!=len(rows):
        raise ValueError("FULL_SOURCE_ROLE_JOIN_COUNT_MISMATCH")
    for row in rows:
        if row["split_role"]!=row["source_role"]:raise ValueError("FROZEN_ROLE_SOURCE_MEMBERSHIP_CHANGED")
        row.update(membership(row))
        row.update(new_role=row["effective_role"],expected_conformers=row["S_conformers"],
                   pm7_records=row["S_conformers"],uff_usable_conformers=row["merged_uff_count"])
    gates=exclusion_gates(rows)
    if gates["mother_molecules"]!=value["expected_train_val_molecules"]:
        raise ValueError("TRAIN_PLUS_ROUTINE_VAL_DENOMINATOR_CHANGED")
    out=IO.new_output_directory(a.output,value)
    IO.write_json_new(out/"exclusion_evidence.json",gates)
    if not gates["passed"]:
        IO.write_json_new(out/"manifest.json",{"status":"COMMON_POPULATION_V1_NOT_FROZEN_STOP_THRESHOLD",
            "evidence":IO.reference(out/"exclusion_evidence.json"),"no_records_deleted":True,
            "roles_manifest_sha256":roles_ref["sha256"],"pilot_only":False})
        raise SystemExit(2)
    full=pa.Table.from_pylist(rows);db.register("common_rows",full)
    formal=formal_source(value)
    smiles=db.execute("SELECT molecule_id,first(canonical_smiles) AS smiles FROM read_parquet("+q(formal["path"])+") GROUP BY molecule_id").fetchall()
    chunks=[smiles[i:i+5000] for i in range(0,len(smiles),5000)]
    scaffold_rows=[]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context("spawn")) as pool:
        for chunk in pool.map(scaffold_chunk,chunks):scaffold_rows.extend(chunk)
    db.register("scaffolds",pa.Table.from_pylist(scaffold_rows))
    db.execute("CREATE TABLE final_membership AS SELECT c.*,s.generic_scaffold,s.scaffold_status FROM common_rows c JOIN scaffolds s USING(molecule_id)")
    (out/"membership").mkdir();members=[]
    for part in range(16):
        table=db.execute("SELECT * FROM final_membership WHERE hash(molecule_id)%16=? ORDER BY molecule_id",[part]).fetch_arrow_table()
        path=out/"membership"/f"part-{part:04d}.parquet";IO.write_parquet_new(path,table);members.append(IO.reference(path))
    # Long comparison tables keep all categories, including explicit parse failures.
    for name,query in {
        "size":"SELECT heavy_atoms AS category,count(*) AS before,count(*) FILTER(WHERE common_population) AS after FROM final_membership WHERE effective_role IN ('TRAIN','VAL') GROUP BY heavy_atoms ORDER BY heavy_atoms",
        "element_set":"SELECT list_sort(list_distinct(elements_atomic_numbers)) AS category,count(*) AS before,count(*) FILTER(WHERE common_population) AS after FROM final_membership WHERE effective_role IN ('TRAIN','VAL') GROUP BY category ORDER BY category",
        "scaffold":"SELECT generic_scaffold AS category,count(*) AS before,count(*) FILTER(WHERE common_population) AS after FROM final_membership WHERE effective_role IN ('TRAIN','VAL') GROUP BY generic_scaffold ORDER BY generic_scaffold"
    }.items():IO.write_parquet_new(out/(name+"_comparison.parquet"),db.execute(query).fetch_arrow_table())
    n1=[{"molecule_id":r["molecule_id"],"effective_role":r["effective_role"]} for r in rows if r["pprime_two_conformers_pending"]]
    IO.write_parquet_new(out/"pprime_n1_pending.parquet",pa.Table.from_pylist(n1) if n1 else pa.table({"molecule_id":pa.array([],type=pa.string()),"effective_role":pa.array([],type=pa.string())}))
    # Physical-key mapping is metadata, not a claim that all three order tables exist.
    db.register("old_file_pins",pa.Table.from_pylist([{"source_path":r["path"],"source_sha256":r["sha256"],"source_bytes":r["bytes"]} for r in old_refs]))
    db.execute("""CREATE TABLE uff_keys AS SELECT o.molecule_id,o.canonical_sprime_conf_idx AS sprime_conf_idx,
       o.source_path,o.source_row_index,'parquet' AS source_format,NULL::VARCHAR AS source_member,o.atom_order_sha256,o.source_record_id AS native_anchor_record_id,
       f.source_sha256,f.source_bytes,o.original_sprime_conf_idx,NULL::BIGINT AS candidate_id,o.seed,
       false AS below_dedup_threshold,o.uff_energy_kcal_mol,'accepted_original_sprime' AS origin,NULL::VARCHAR AS geometry_sha256
       FROM old o JOIN old_file_pins f USING(source_path)""")
    if new_metadata:
        db.register("generated",pa.Table.from_pylist(new_metadata))
        db.execute("""INSERT INTO uff_keys SELECT molecule_id,kernel_sprime_conf_idx,source_path,source_row_index,
            source_format,source_member,atom_order_sha256,source_record_id,source_sha256,source_bytes,NULL::BIGINT,candidate_id,seed,
            below_dedup_threshold,uff_energy_kcal_mol,origin,geometry_sha256 FROM generated""")
    if db.execute("SELECT count(*) FROM (SELECT molecule_id,sprime_conf_idx FROM uff_keys GROUP BY ALL HAVING count(*)>1)").fetchone()[0]:
        raise ValueError("CANONICAL_UFF_KEY_COLLISION")
    if db.execute("""SELECT count(*) FROM final_membership m LEFT JOIN
        (SELECT molecule_id,count(*) AS n FROM uff_keys GROUP BY molecule_id) u USING(molecule_id)
        WHERE coalesce(u.n,0)<>m.merged_uff_count""").fetchone()[0]:
        raise ValueError("PHYSICAL_UFF_MAPPING_COUNT_NOT_CONSERVED")
    maps=[];(out/"physical_geometry").mkdir()
    for source in ("pm7","uff_sprime"):
        for part in range(16):
            if source=="pm7":
                sql="""SELECT r.molecule_id,r.record_id AS native_record_id,NULL::BIGINT AS sprime_conf_idx,
                  'pm7' AS geometry_source,'pm7:'||sha256(r.record_id) AS geometry_id,r.source_path,r.real_index,
                  r.record_payload_sha256,'native_lmdb' AS source_format,m.effective_role,m.source_role,
                  r.member_routine AS legacy_routine_member,m.legacy_routine_molecule,
                  CASE WHEN length(CAST(r.real_index AS VARCHAR))<9 THEN lpad(CAST(r.real_index AS VARCHAR),9,'0')
                       ELSE CAST(r.real_index AS VARCHAR) END AS native_lmdb_key
                  FROM read_parquet(FORMAL) r JOIN final_membership m USING(molecule_id)
                  WHERE m.common_population AND hash(r.molecule_id)%16=PART"""
                sql=sql.replace("FORMAL",q(formal["path"])).replace("PART",str(part))
            else:
                sql="""SELECT u.*,NULL::VARCHAR AS native_record_id,'uff_sprime' AS geometry_source,
                  'uff_sprime:'||sha256(u.molecule_id||':'||CAST(u.sprime_conf_idx AS VARCHAR)) AS geometry_id,
                  m.effective_role,m.source_role,m.legacy_routine_molecule
                  FROM uff_keys u JOIN final_membership m USING(molecule_id)
                  WHERE m.common_population AND hash(u.molecule_id)%16=PART""".replace("PART",str(part))
            table=db.execute(sql).fetch_arrow_table()
            path=out/"physical_geometry"/f"{source}-{part:04d}.parquet";IO.write_parquet_new(path,table);maps.append(IO.reference(path))
    record_counts=db.execute("SELECT effective_role,count(*) AS molecules,sum(S_conformers) AS pm7_records,sum(merged_uff_count) AS uff_records FROM final_membership WHERE common_population GROUP BY effective_role").fetch_arrow_table().to_pylist()
    IO.write_json_new(out/"manifest.json",{"schema":"COMMON_POPULATION_V1_FROZEN","status":"COMMON_POPULATION_V1_FROZEN",
        "membership_tables":members,"physical_geometry_tables":maps,"roles_manifest":roles_ref,"roles_manifest_sha256":roles_ref["sha256"],
        "completion_index":IO.reference(a.completion_index),"config":IO.reference(a.config),"runtime":env,
        "old_sprime_manifest":value["sprime_manifest"],"formal_population_authority_receipt":value["formal_source_receipt"],
        "denominator_molecules":gates["mother_molecules"],"excluded_molecules":gates["excluded_molecules"],
        "roles":record_counts,"exclusion_evidence":IO.reference(out/"exclusion_evidence.json"),
        "actual_accounted_core_hours":actual_core_hours,"actual_parent_jobs":sorted(actual_parents),
        "actual_cost_scope":"pilot plus batch closures plus explicitly supplied analysis/failure closures; Root global ledger remains authoritative for other pipeline stages",
        "element_set_comparison":IO.reference(out/"element_set_comparison.parquet"),
        "size_comparison":IO.reference(out/"size_comparison.parquet"),"scaffold_comparison":IO.reference(out/"scaffold_comparison.parquet"),
        "pprime_n1_pending":IO.reference(out/"pprime_n1_pending.parquet"),"pprime_n1_molecules":len(n1),
        "pprime_two_conformer_policy_status":"PENDING_N1_POLICY" if n1 else "NO_N1_PENDING",
        "native_source_project_root":"/share/home/zixiao/descriptor_analysis",
        "pm7_completeness_basis":"full original geometry counts and valid identity from pinned canonical S audit; P-task success not required",
        "orders_frozen":False,"order_manifest":None,"geometry_map_frozen_by_this_manifest":False,
        "original_data_modified":False,"pilot_only":False})
    db.close()


if __name__=="__main__":main()
