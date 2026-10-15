"""Compare final/pilot record intersection with bounded per-molecule workers; no QM."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,json,os,time,math
from pathlib import Path
from wp5_acceptance_catalog import ROOT,sha,publish,q,copy,require_slurm
from wp5_acceptance_recompute import compare_quantum,read_rows,init_compare
OLD=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010")
_P={}
def initialize(options):
    global _P
    _P=options;init_compare(options["entries"])
def pilot_one(arg):
    receipt_path,locators,precision,authorized,record_meta=arg
    import pyarrow.parquet as pq,wp5_parquet as wire
    receipt=json.loads(Path(receipt_path).read_text());reference=receipt["parquet"]
    if Path(reference["path"]).stat().st_size!=reference["bytes"] or sha(reference["path"])!=reference["sha256"]:
        raise ValueError("PILOT_IMMUTABLE_PARQUET_SHA_CHANGED")
    lookup={(row["record_id"],row["calc_type"]):row for row in locators}
    ids={key[0] for key in lookup};originals={};polar_only=set()
    for batch in pq.ParquetFile(reference["path"]).iter_batches(batch_size=16,columns=["details_json"]):
        for item in batch.to_pylist():
            detail=json.loads(item["details_json"]);key=(detail["record_id"],detail["task"])
            if key not in lookup:continue
            # Preserve original status. G5 proves a deleted-scope status delta;
            # it does not authorize silently converting failed physics to success.
            detail=dict(detail);detail["source_status"]=detail["status"];detail["scope_status"]=detail["status"]
            row=wire.task_row(detail["record_id"],detail["molecule_id"],detail["task"],detail,_P["entries"].values(),detail["natoms"])
            row.update(attempt_id=0,job_id=int(detail["job_id"]),task_id="PILOT_REFERENCE",lane=None)
            if key in originals:raise ValueError("PILOT_ORIGINAL_DUPLICATE_SLOT")
            originals[key]=row
            if key[1]=="pm7_B" and detail.get("status")=="PROPERTY_FAILED" and "POLAR_FRAGILE" in (detail.get("qc_codes") or []) and detail.get("B_base_success") is True and not detail.get("length_issues") and not (set(detail.get("missing_properties") or [])-{"static_polar_block"}):polar_only.add(key)
    paths={}
    for row in locators:paths.setdefault(row["family_parquet_path"],set()).add(row["record_id"])
    actual={}
    for path,selected in paths.items():
        _,rows=read_rows(path,list(selected))
        for row in rows:
            key=(row["record_id"],row["calc_type"]);expected=lookup.get(key)
            if expected and all(row[name]==expected[name] for name in ("attempt_id","job_id","task_id","lane")):
                if key in actual:raise ValueError("PILOT_COMPARISON_DUPLICATE_LATEST")
                actual[key]=row
    differences=[];counts=collections.Counter();byfield=collections.Counter();missing=collections.Counter();statuses=collections.Counter();scalars={}
    def distribution(population,rows):
        for (record,calc),row in rows.items():
            meta=record_meta[record];size=meta["size_stratum"]
            statuses[(population,calc,size,row["status"])]+=1
            for cell in row["values"]:
                rid=cell["registry_id"];kind=cell["kind"];value=wire.decode(cell)
                category={0:"NULL",9:"ABSENT",10:"NONFINITE"}.get(kind,"EMPTY_CONTAINER" if value==[] or value=={} else "PRESENT")
                elements=meta.get("elements") or ["UNKNOWN"]
                if isinstance(elements,str):elements=[elements]
                for element in ["ANY"]+list(dict.fromkeys(elements)):missing[(population,rid,calc,size,str(element),category)]+=1
                if _P["entries"][rid].get("classification")!="provenance" and kind in (1,5):
                    for number in ([value] if kind==1 else cell["array_f64"]):
                        if not math.isfinite(number):continue
                        key=(population,rid,calc,size);item=scalars.setdefault(key,[0,0.,0.,None,None])
                        item[0]+=1;item[1]+=number;item[2]+=number*number
                        item[3]=number if item[3] is None else min(item[3],number);item[4]=number if item[4] is None else max(item[4],number)
    distribution("original_pilot_eligible_intersection",originals)
    distribution("formal_same_record_intersection",actual)
    for key in sorted(lookup):
        changed,statuses,fields,_=compare_quantum((key,originals.get(key),actual.get(key),precision.get(key,{})))
        counts.update(statuses);byfield.update(fields)
        for row in changed:
            proof=authorized.get((row["record_id"],row["calc_type"],row["registry_id"]))
            if proof:row.update(comparison=proof[0],reason=proof[1])
            elif row["registry_id"] is None and row["source_path"] in {"status","source_status","failure_code"} and key in polar_only:
                # Only explicit original POLAR_FRAGILE QC with good base/no other required missing/length failure proves this case.
                # Retained scientific values are compared independently above.
                if actual.get(key,{}).get("status")=="SUCCESS":
                    row.update(comparison="DELETED_POLAR_SCOPE_STATUS_CHANGE",reason="Original PM7 B POLAR_FRAGILE; authorized WP5 deletes POLAR; all retained fields still independently compared.")
            differences.append(row)
    return {"worker_pid":os.getpid(),"expected_slots":len(lookup),"original_slots":len(originals),"formal_slots":len(actual),
        "differences":differences,"comparison_counts":dict(counts),"field_counts":dict(byfield),
        "receipt_sha256":sha(receipt_path),"pilot_parquet_sha256":reference["sha256"],
        "missingness":dict(missing),"status_distribution":dict(statuses),"scalar_distribution":scalars}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog",type=Path);ap.add_argument("--registry",type=Path)
    ap.add_argument("--pilot-root",type=Path,default=OLD/"wp4_native_full_v4")
    ap.add_argument("--pilot-panel",type=Path,default=OLD/"wp4_native_panel/pilot_panel.parquet")
    ap.add_argument("--regression-fields",type=Path,help="Closed G5 field_regression.parquet precision and authorized D4/deleted-POLAR proof")
    ap.add_argument("--workers",type=int,default=24);ap.add_argument("--out",type=Path);ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print("ACCEPTANCE_PILOT_AST_PASS_NO_QM_NO_DATA");return
    require_slurm(args.workers)
    if not args.catalog or not args.registry:raise ValueError("catalog/registry required")
    import duckdb,pyarrow as pa,pyarrow.parquet as pq,wp5_parquet as wire,multiprocessing
    catalog=json.loads(args.catalog.read_text())
    if catalog["status"]!="CLOSED":raise ValueError("Closed final catalog required")
    out=args.out or ROOT/"acceptance"/("pilot_compare_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    db=duckdb.connect();db.execute("SET threads="+str(args.workers));db.execute("SET memory_limit='20GB'")
    db.execute("CREATE VIEW final_records AS SELECT * FROM read_parquet("+q(catalog["authority"]["population"])+")")
    db.execute("CREATE VIEW pilot AS SELECT * FROM read_parquet("+q(args.pilot_panel)+")")
    by_molecule=db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM final_records WHERE molecule_id IN (SELECT DISTINCT molecule_id FROM pilot)").fetchone()
    copy(db,"SELECT f.record_id,f.molecule_id,f.elements,CASE WHEN f.molecule_max_heavy_atoms<=10 THEN '0_10' WHEN f.molecule_max_heavy_atoms<=20 THEN '11_20' WHEN f.molecule_max_heavy_atoms<=30 THEN '21_30' WHEN f.molecule_max_heavy_atoms<=50 THEN '31_50' WHEN f.molecule_max_heavy_atoms<=75 THEN '51_75' WHEN f.molecule_max_heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END AS size_stratum FROM final_records f JOIN pilot p USING(record_id)",out/"pilot_record_intersection.parquet")
    db.execute("CREATE VIEW selected AS SELECT * FROM read_parquet("+q(out/"pilot_record_intersection.parquet")+")")
    copy(db,"SELECT c.* FROM read_parquet("+q(catalog["latest_record_tasks"])+") c JOIN selected s USING(record_id)",out/"pilot_reference_locators.parquet")
    locators=pq.read_table(out/"pilot_reference_locators.parquet").to_pylist()
    record_meta={row["record_id"]:row for row in pq.read_table(out/"pilot_record_intersection.parquet").to_pylist()}
    by_mol={};by_record={}
    for row in locators:
        by_mol.setdefault(row["molecule_id"],[]).append(row);by_record[row["record_id"]]=row["molecule_id"]
    precision_by_mol={};authorized_by_mol={}
    if args.regression_fields:
        for record,calc,rid,tolerance,comparison,reason in db.execute(
            "SELECT record_id,calc_type,registry_id,rounding_tolerance,comparison,reason FROM read_parquet("+q(args.regression_fields)+")").fetchall():
            mol=by_record.get(record)
            if mol is None:continue
            if tolerance is not None:precision_by_mol.setdefault(mol,{}).setdefault((record,calc),{})[rid]=tolerance
            if comparison in {"AUTHORIZED_D4_CORRECTION","DELETED_POLAR_DIAGNOSTIC_REMOVED"}:
                authorized_by_mol.setdefault(mol,{})[(record,calc,rid)]=(comparison,reason)
    entries={entry["registry_id"]:entry for entry in wire.registry(args.registry)}
    receipts={}
    for path in sorted(args.pilot_root.glob("bucket_*/molecules/*/receipt.json")):
        receipt=json.loads(path.read_text())
        mol=receipt["molecule_id"]
        if mol in receipts:raise ValueError("DUPLICATE_PILOT_MOLECULE_RECEIPT")
        receipts[mol]=path
    missing_receipts=set(by_mol)-receipts.keys()
    if missing_receipts:raise ValueError("PILOT_MOLECULE_RECEIPTS_MISSING:"+str(len(missing_receipts)))
    schema=pa.schema([("record_id",pa.string()),("calc_type",pa.string()),("registry_id",pa.int16()),("source_path",pa.string()),("comparison",pa.string()),("reason",pa.string()),("expected_sha256",pa.string()),("actual_sha256",pa.string()),("expected_summary",pa.string()),("actual_summary",pa.string()),("rounding_tolerance",pa.float64())])
    pending=out/"pilot_scientific_differences.parquet.pending";writer=pq.ParquetWriter(pending,schema,compression="zstd")
    counts=collections.Counter();byfield=collections.Counter();classified=collections.Counter();pids=set();proofs=[]
    missing=collections.Counter();statuses=collections.Counter();scalars={}
    n_old=n_actual=n_expected=0;started=time.monotonic();ctx=multiprocessing.get_context("spawn")
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=initialize,initargs=({"entries":entries},)) as pool:
            arguments=((str(receipts[mol]),rows,precision_by_mol.get(mol,{}),authorized_by_mol.get(mol,{}),{row["record_id"]:record_meta[row["record_id"]] for row in rows}) for mol,rows in sorted(by_mol.items()))
            for result in pool.map(pilot_one,arguments,chunksize=1):
                pids.add(result["worker_pid"]);counts.update(result["comparison_counts"]);byfield.update(result["field_counts"])
                n_old+=result["original_slots"];n_actual+=result["formal_slots"];n_expected+=result["expected_slots"]
                missing.update(result["missingness"]);statuses.update(result["status_distribution"])
                for key,value in result["scalar_distribution"].items():
                    item=scalars.setdefault(key,[0,0.,0.,None,None]);item[0]+=value[0];item[1]+=value[1];item[2]+=value[2]
                    item[3]=value[3] if item[3] is None else min(item[3],value[3]);item[4]=value[4] if item[4] is None else max(item[4],value[4])
                rows=result["differences"]
                if rows:writer.write_table(pa.Table.from_pylist(rows,schema=schema))
                classified.update(row["comparison"] for row in rows)
                proofs.append({"receipt_sha256":result["receipt_sha256"],"pilot_parquet_sha256":result["pilot_parquet_sha256"]})
    finally:writer.close()
    with pending.open("rb") as stream:os.fsync(stream.fileno())
    pending.rename(out/"pilot_scientific_differences.parquet")
    accepted={"AUTHORIZED_D4_CORRECTION","DELETED_POLAR_DIAGNOSTIC_REMOVED","DELETED_POLAR_SCOPE_STATUS_CHANGE"}
    unresolved=sum(value for code,value in classified.items() if code not in accepted)
    ids=len(by_record)
    def distribution_file(name,rows):
        if rows:pq.write_table(pa.Table.from_pylist(rows),out/name,compression="zstd")
        else:publish(out/(name+".empty.json"),{"rows":0})
    distribution_file("pilot_vs_formal_field_missingness.parquet",[{"population":pop,"registry_id":rid,"task":calc,"size_stratum":size,"element_presence":element,"category":category,"count":number} for (pop,rid,calc,size,element,category),number in missing.items()])
    distribution_file("pilot_vs_formal_task_status.parquet",[{"population":pop,"task":calc,"size_stratum":size,"status":status,"count":number} for (pop,calc,size,status),number in statuses.items()])
    distribution_file("pilot_vs_formal_label_distribution.parquet",[{"population":pop,"registry_id":rid,"task":calc,"size_stratum":size,"finite_values":item[0],"mean":item[1]/item[0] if item[0] else None,"stddev":math.sqrt(max(0.,item[2]/item[0]-(item[1]/item[0])**2)) if item[0] else None,"min":item[3],"max":item[4]} for (pop,rid,calc,size),item in scalars.items()])
    report={"stage":"WP5_ACCEPTANCE_PILOT_INTERSECTION","status":"PASS" if not unresolved and n_old==n_actual==n_expected==ids*12 else "DIFFERENCES_REQUIRE_REVIEW",
        "formal_records_in_pilot_molecules":by_molecule[0],"formal_pilot_molecules":by_molecule[1],"exact_record_intersection":ids,"compared_quantum_slots":n_actual,"original_quantum_slots":n_old,
        "formal_conformers_of_pilot_molecules_without_original_pilot_record":by_molecule[0]-ids,"unrepresented_conformer_policy":"No original counterpart; report separately, never invent comparison or rerun whole pilot.",
        "comparison_counts_before_scope_classification":dict(counts),"classified_difference_counts":dict(classified),"difference_rows":sum(classified.values()),"unresolved_difference_rows":unresolved,
        "differences":str(out/"pilot_scientific_differences.parquet"),"field_counts":[{"registry_id":rid,"comparison":status,"count":count} for (rid,status),count in byfield.items()],
        "distribution_scope":"Matched original pilot/formal record intersection per registry/size/element; compare separately with final full-population verifier tables. ANY is additive record denominator. No threshold deletion. D20/D3 are covered by fresh200 and full schema checks; no fabricated original QM-pilot counterpart.",
        "precision":"Strict default with only actual G5 per-record field precision observations; no generic epsilon.",
        "effective_worker_pids":sorted(pids),"effective_workers":len(pids),"seconds":time.monotonic()-started,"source_receipts":proofs,
        "G5_raw_exception":"Approved historical raw absence only. Physical mismatches remain explicit; exception does not authorize fresh/formal numerical changes.",
        "bindings":{"catalog_sha256":sha(args.catalog),"pilot_panel_sha256":sha(args.pilot_panel),"registry_sha256":sha(args.registry),"regression_fields_sha256":sha(args.regression_fields) if args.regression_fields else None,"script_sha256":sha(__file__)},"new_QM_calls":0,"original_data_written":False}
    publish(out/"pilot_comparison.json",report);db.close()
    print(json.dumps({"report":str(out/"pilot_comparison.json"),"status":report["status"],"record_intersection":ids}))
if __name__=="__main__":main()
