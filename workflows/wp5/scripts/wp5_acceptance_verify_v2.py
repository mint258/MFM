"""WP5 immutable family and raw-container verification. No quantum computations."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,math,os,sqlite3,time,traceback
from pathlib import Path
from wp5_acceptance_catalog import ROOT,CALCS,sha,publish,require_slurm
_A={}
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def initializer(options):
    global _A
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    _A=options
def stratum(heavy):
    return next(label for limit,label in ((10,"0_10"),(20,"11_20"),(30,"21_30"),(50,"31_50"),(75,"51_75"),(100,"76_100"),(10**9,"above_100")) if heavy<=limit)
def issue(rows,record,code,field=None):
    rows.append({"record_id":record.get("record_id"),"molecule_id":record.get("molecule_id"),"calc_type":record.get("calc_type"),"status":record.get("status",record.get("geometry_status")),"issue":code,"field":field})
def read_companions(ref):
    import pyarrow.parquet as pq
    source={};z={}
    companions=_A["companions"].get(str(Path(ref["path"]).parent),{})
    if "QC" in companions:
        for batch in pq.ParquetFile(companions["QC"]).iter_batches(batch_size=1024,columns=["record_id","population_QC_json"]):
            for row in batch.to_pylist():
                raw=json.loads(row["population_QC_json"])
                source[row["record_id"]]={"n":raw["total_atoms"],"stratum":stratum(raw.get("molecule_max_heavy_atoms",raw["heavy_atoms"])),"elements":raw.get("elements") or ["UNKNOWN"],"new_role":raw["new_role"],"routine":raw["member_routine"]}
    if "base_geometry" in companions:
        for batch in pq.ParquetFile(companions["base_geometry"]).iter_batches(batch_size=1024,columns=["record_id","atomic_numbers"]):
            for row in batch.to_pylist():z[row["record_id"]]=row["atomic_numbers"]
    return source,z
def selected_molecules(job):
    import pyarrow.dataset as ds
    table=ds.dataset(_A["latest_molecules"],format="parquet").to_table(
        filter=ds.field("job_id")==int(job),columns=["molecule_id","attempt_id","job_id","task_id","receipt_context_consistent","export_published"],use_threads=False)
    return {(row["molecule_id"],row["attempt_id"],row["job_id"],row["task_id"]) for row in table.to_pylist() if row["receipt_context_consistent"] and row["export_published"]}
def authoritative_keys(ref,selected,raw=False):
    import pyarrow.parquet as pq
    index=Path(ref["run_root"])/"canonical_record_attempts.parquet"
    expected=set()
    for batch in pq.ParquetFile(index).iter_batches(batch_size=4096):
        for row in batch.to_pylist():
            family=ref.get("family")
            non_qm=family in {"base_geometry","D20","D3","QC"}
            pointer=row["archive_path"] if raw else row["family_parquet_path"]
            matches=pointer==ref["path"] if not non_qm else row["calc_type"]=="pm7_B" and Path(pointer).parent==Path(ref["path"]).parent
            if matches and key(row) in selected:
                pair=(row["record_id"],family if non_qm else row["calc_type"])
                if pair in expected:raise ValueError("CANONICAL_DUPLICATE_LOCATOR")
                expected.add(pair)
    return expected
def key(row):return (row["molecule_id"],row["attempt_id"],row["job_id"],row["task_id"])
def reconstruct(cells,entries):
    from wp5_parquet import decode,MISSING
    result={"values":{}}
    for cell in cells:
        entry=entries.get(cell["registry_id"])
        if entry is None:continue
        value=decode(cell)
        if value is MISSING:continue
        parts=entry["source_path"].replace("/",".").strip(".").split(".")
        if parts[0] in {"detail","details"}:parts=parts[1:];node=result
        elif parts[0]=="values":node=result
        else:node=result["values"]
        for part in parts[:-1]:node=node.setdefault(part,{})
        node[parts[-1]]=value
    return result
def numeric_leaves(value):
    if isinstance(value,float):yield value
    elif isinstance(value,(list,tuple)):
        for item in value:yield from numeric_leaves(item)
    elif isinstance(value,dict):
        for item in value.values():yield from numeric_leaves(item)
def check_file(ref):
    import pyarrow.parquet as pq,wp5_parquet as wire,wp5_engine
    started=time.monotonic();path=Path(ref["path"]);family=ref.get("family")
    errors=[];counts=collections.Counter();fields=collections.Counter();scalar={}
    expected_sha=ref["sha256"]
    if path.stat().st_size!=ref["bytes"] or sha(path)!=expected_sha:raise ValueError("IMMUTABLE_FILE_SHA_OR_BYTES_CHANGED:"+str(path))
    if path.suffix==".sqlite":
        from wp5_archive_v4 import ArchiveReader
        selected=selected_molecules(ref["job_id"]);expected_keys=authoritative_keys(ref,selected,raw=True)
        reader=ArchiveReader(path,_A["dictionaries"]);raw=0;retained=0;input_files=0;output_files=0;latest_raw=0
        lookup=sqlite3.connect("file:"+_A["latest_sqlite"]+"?mode=ro",uri=True)
        try:latest={row[0]:row[1] for row in lookup.execute("SELECT molecule_id,archive_path FROM current_molecules WHERE archive_path=?",(str(path),))}
        finally:lookup.close()
        try:
            integrity=reader.db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity!="ok":raise ValueError("RAW_ARCHIVE_INTEGRITY_FAILED")
            for record_id,calc,molecule in reader.db.execute("SELECT record_id,calc_type,molecule_id FROM records"):
                value=reader.get(record_id,calc);raw+=1;retained+=value["output_retained"]
                input_files+=len(value["input_files"]);output_files+=len(value["output_files"] or [])
                if calc not in CALCS:raise ValueError("UNREGISTERED_RAW_CALC_TYPE")
                if molecule in latest:
                    latest_raw+=1
                    pair=(record_id,calc)
                    if pair not in expected_keys:raise ValueError("RAW_LATEST_KEY_NOT_IN_CANONICAL_LOCATOR")
                    expected_keys.remove(pair)
                if not value["input_files"] and not value["metadata"].get("input_missing_reason"):raise ValueError("RAW_INPUT_ABSENT_WITHOUT_EXPLICIT_REASON")
            duplicates=reader.db.execute("SELECT count(*) FROM (SELECT record_id,calc_type FROM records GROUP BY 1,2 HAVING count(*)!=1)").fetchone()[0]
            if duplicates:raise ValueError("RAW_DUPLICATE_KEYS")
            if expected_keys:raise ValueError("CANONICAL_LATEST_RAW_KEYS_MISSING:"+str(len(expected_keys)))
        finally:reader.close()
        return {"path":str(path),"sha256":expected_sha,"bytes":ref["bytes"],"family":"raw_archive","raw_calc_rows":raw,"latest_raw_calc_rows":latest_raw,"retained_raw_outputs":retained,"all_input_files_readback":input_files,"retained_output_files_readback":output_files,"raw_member_sha_verified":True,"seconds":time.monotonic()-started,"worker_pid":os.getpid(),"issues":[],"field_counts":[],"status_counts":[],"scalar_stats":[]}
    file=pq.ParquetFile(path)
    if family=="canonical_record_attempts":
        return {"path":str(path),"sha256":expected_sha,"bytes":ref["bytes"],"family":family,"rows":file.metadata.num_rows,"seconds":time.monotonic()-started,"worker_pid":os.getpid(),"issues":[],"field_counts":[],"status_counts":[],"scalar_stats":[]}
    schema={"base_geometry":wire.BASE_SCHEMA,"D20":wire.D20_SCHEMA,"D3":wire.D3_SCHEMA,"QC":wire.QC_SCHEMA}.get(family,wire.SCHEMA)
    if not file.schema_arrow.remove_metadata().equals(schema.remove_metadata()):raise ValueError("UNKNOWN_OR_CHANGED_FAMILY_SCHEMA:"+str(path))
    metadata,z=read_companions(ref);selected=selected_molecules(ref["job_id"]);entries=_A["entries"]
    expected_keys=authoritative_keys(ref,selected)
    row_count=0;latest_count=0
    for batch in file.iter_batches(batch_size=64):
        for row in batch.to_pylist():
            row_count+=1;latest=key(row) in selected
            if latest:
                latest_count+=1
                pair=(row["record_id"],row.get("calc_type",family))
                if pair not in expected_keys:issue(errors,row,"LATEST_FAMILY_KEY_NOT_IN_CANONICAL_LOCATOR")
                else:expected_keys.remove(pair)
            source=metadata.get(row["record_id"])
            if source is None:raise ValueError("COMPANION_RECORD_QC_METADATA_ABSENT")
            n=source["n"];status=row.get("status",row.get("record_status",row.get("geometry_status")))
            if not status:issue(errors,row,"STATUS_ABSENT")
            if latest:counts[(row.get("calc_type",family),source["stratum"],status)]+=1
            if family not in {"base_geometry","D20","D3","QC"}:
                calc=row["calc_type"]
                if calc not in CALCS or wire.FAMILIES[calc]!=family:issue(errors,row,"CALC_FAMILY_MISMATCH")
                if row["total_atoms"]!=n:issue(errors,row,"FORMAL_N_MISMATCH")
                cells=row["values"];ids=[cell["registry_id"] for cell in cells]
                expected={rid for rid,entry in entries.items() if entry["task"]==calc}
                if len(ids)!=len(set(ids)) or set(ids)!=expected:issue(errors,row,"DUPLICATE_UNREGISTERED_OR_MISSING_REGISTRY_CELLS")
                for cell in cells:
                    rid=cell["registry_id"];entry=entries.get(rid)
                    if entry is None:continue
                    kind=cell["kind"];value=wire.decode(cell)
                    if kind not in range(11):issue(errors,row,"UNKNOWN_CELL_KIND",str(rid))
                    if kind==10 and status=="SUCCESS":issue(errors,row,"NONFINITE_SUCCESS_LABEL",str(rid))
                    if kind not in (0,9,10):
                        if any(not math.isfinite(item) for item in numeric_leaves(value)):issue(errors,row,"NONFINITE_LABEL_NOT_ENCODED_EXPLICITLY",str(rid))
                    if kind in (5,6,7):
                        field={5:"array_f64",6:"array_i64",7:"array_bool"}[kind]
                        if math.prod(cell["shape"])!=len(cell[field]):issue(errors,row,"ARRAY_SHAPE_PAYLOAD_MISMATCH",str(rid))
                    category={0:"NULL",9:"ABSENT",10:"NONFINITE"}.get(kind,"EMPTY_CONTAINER" if value==[] or value=={} else "PRESENT")
                    if latest:
                        presence=source["elements"]
                        if isinstance(presence,str):presence=[presence]
                        for element in ["ANY"]+list(dict.fromkeys(presence)):
                            fields[(rid,calc,source["stratum"],str(element),category)]+=1
                        if entry.get("classification")!="provenance" and kind in (1,5):
                            numbers=[value] if kind==1 else cell["array_f64"]
                            for number in numbers:
                                if not finite(number):continue
                                k=(rid,calc,source["stratum"]);stats=scalar.setdefault(k,[0,0.,0.,None,None])
                                stats[0]+=1;stats[1]+=number;stats[2]+=number*number
                                stats[3]=number if stats[3] is None else min(stats[3],number);stats[4]=number if stats[4] is None else max(stats[4],number)
                details=reconstruct(cells,entries)
                array_issues=wp5_engine.validate_atomic_arrays(details,z.get(row["record_id"]) or n)
                for problem in array_issues:
                    issue(errors,row,"ATOMIC_ARRAY_QC_SUCCESS" if status=="SUCCESS" else "ATOMIC_ARRAY_QC_RECORDED_FAILURE",problem)
            elif family=="base_geometry":
                numbers=row["atomic_numbers"];positions=row["positions_A"]
                if numbers is not None:
                    if len(numbers)!=n or positions is None or len(positions)!=n or any(len(v)!=3 or any(not finite(x) for x in v) for v in positions):issue(errors,row,"BASE_GEOMETRY_N_OR_FINITE_MISMATCH")
                elif row["geometry_status"]=="ORIGINAL_PM7_GEOMETRY":issue(errors,row,"SUCCESS_BASE_GEOMETRY_NULL")
                if row["new_PM7_HOF_valid"] and not finite(row["new_PM7_HOF_kcal_mol"]):issue(errors,row,"VALID_NEW_HF_NOT_FINITE")
                if not row["new_PM7_HOF_valid"] and row["new_PM7_HOF_kcal_mol"] is not None:issue(errors,row,"INVALID_NEW_HF_NOT_NULL")
                pairs=row["bond_pairs"];orders=row["bond_order_codes"]
                if pairs is not None:
                    if orders is None or len(pairs)!=len(orders) or any(len(p)!=2 or any(type(i) is not int or not 0<=i<n for i in p) for p in pairs):issue(errors,row,"STORED_BOND_GRAPH_SHAPE_OR_RANGE")
            elif family=="D20":
                values=row["values_float64"];mask=row["valid_mask"];names=row["descriptor_names"]
                if names!=_A["D20_names"]:issue(errors,row,"D20_NAME_SCHEMA_INVALID")
                complete=values is not None and len(values)==20 and mask is not None and len(mask)==20 and all(mask) and all(finite(value) for value in values)
                if status=="SUCCESS" and not complete:issue(errors,row,"D20_INCOMPLETE_PRETENDS_SUCCESS")
                if latest:
                    presence=source["elements"] if isinstance(source["elements"],list) else [source["elements"]]
                    for index,name in enumerate(names or []):
                        category="PRESENT" if values is not None and index<len(values) and finite(values[index]) and mask is not None and index<len(mask) and mask[index] else "MISSING_OR_INVALID"
                        for element in ["ANY"]+list(dict.fromkeys(presence)):fields[(-1000-index,"D20:"+name,source["stratum"],str(element),category)]+=1
            elif family=="D3":
                keys=("PMI1","PMI2","PMI3","PBF_A","volume_A3","SASA_total_A2");atomic=row["SASA_atom_A2"]
                complete=all(finite(row[name]) for name in keys) and atomic is not None and len(atomic)==n and all(finite(value) for value in atomic)
                if status=="SUCCESS" and not complete:issue(errors,row,"D3_INCOMPLETE_PRETENDS_SUCCESS")
                if latest:
                    for index,name in enumerate(keys):
                        presence=source["elements"] if isinstance(source["elements"],list) else [source["elements"]]
                        for element in ["ANY"]+list(dict.fromkeys(presence)):fields[(-2000-index,"D3:"+name,source["stratum"],str(element),"PRESENT" if finite(row[name]) else "MISSING_OR_INVALID")]+=1
                    presence=source["elements"] if isinstance(source["elements"],list) else [source["elements"]]
                    for element in ["ANY"]+list(dict.fromkeys(presence)):fields[(-2100,"D3:SASA_atom_A2",source["stratum"],str(element),"PRESENT" if atomic is not None and len(atomic)==n and all(finite(value) for value in atomic) else "MISSING_OR_INVALID")]+=1
            elif family=="QC":
                slots=row["task_statuses"] or []
                if sorted(item["calc_type"] for item in slots)!=sorted(CALCS) or any(not item["status"] for item in slots):issue(errors,row,"QC_TWELVE_EXPLICIT_OUTCOMES_NOT_CLOSED")
                if latest:
                    for index,name in enumerate(("Q01_gradient_norm_kcal_mol_A","Q02_delta_HOF_kcal_mol","cation_S2_minus_0p75","anion_S2_minus_0p75")):
                        value=row[name]
                        presence=source["elements"] if isinstance(source["elements"],list) else [source["elements"]]
                        for element in ["ANY"]+list(dict.fromkeys(presence)):fields[(-3000-index,"QC:"+name,source["stratum"],str(element),"PRESENT" if finite(value) else "MISSING_OR_INVALID")]+=1
                        if finite(value):scalar.setdefault((-3000-index,"QC:"+name,source["stratum"]),[0,0.,0.,value,value])
                        if finite(value):
                            a=scalar[(-3000-index,"QC:"+name,source["stratum"])];a[0]+=1;a[1]+=value;a[2]+=value*value;a[3]=min(a[3],value);a[4]=max(a[4],value)
    if expected_keys:issue(errors,{},"CANONICAL_LATEST_FAMILY_KEYS_MISSING",str(len(expected_keys)))
    return {"path":str(path),"sha256":expected_sha,"bytes":ref["bytes"],"family":family,"rows":row_count,"latest_rows":latest_count,"issues":errors,"worker_pid":os.getpid(),"seconds":time.monotonic()-started,
        "field_counts":[{"registry_id":rid,"task":task,"size_stratum":size,"element_presence":element,"category":category,"count":count} for (rid,task,size,element,category),count in fields.items()],
        "status_counts":[{"task":task,"size_stratum":size,"status":status,"count":count} for (task,size,status),count in counts.items()],
        "scalar_stats":[{"registry_id":rid,"task":task,"size_stratum":size,"finite_values":v[0],"sum":v[1],"sum_squares":v[2],"min":v[3],"max":v[4]} for (rid,task,size),v in scalar.items()]}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog",type=Path);ap.add_argument("--dictionaries",type=Path);ap.add_argument("--registry",type=Path)
    ap.add_argument("--workers",type=int,default=24);ap.add_argument("--out",type=Path);ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print("ACCEPTANCE_VERIFY_AST_PASS_NO_QM_NO_DATA");return
    require_slurm(args.workers)
    if not args.catalog or not args.dictionaries or not args.registry:raise ValueError("catalog/dictionaries/registry required")
    if not args.out and not os.environ.get("SLURM_JOB_ID"):raise ValueError("Slurm output job directory required")
    catalog=json.loads(args.catalog.read_text());out=args.out or ROOT/"acceptance"/("verify_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    import pyarrow as pa,pyarrow.parquet as pq,wp5_parquet as wire,multiprocessing
    pa.set_cpu_count(args.workers)
    companions={}
    refs=catalog["artifacts"]
    for ref in refs:
        if ref.get("family") in {"base_geometry","QC"}:companions.setdefault(str(Path(ref["path"]).parent),{})[ref["family"]]=ref["path"]
    import importlib.util
    protocol=json.loads((ROOT/"configs/protocol.json").read_text())
    dref=protocol["frozen_dependencies"]["D20_D3"]
    if sha(dref["path"])!=dref["sha256"]:raise ValueError("FROZEN_D20_SCHEMA_SOURCE_CHANGED")
    spec=importlib.util.spec_from_file_location("wp5_acceptance_declared_D20",dref["path"]);dmodule=importlib.util.module_from_spec(spec);spec.loader.exec_module(dmodule)
    d20_names=list(dmodule.metadata()["D20_names"])
    current=sqlite3.connect(out/"latest_readonly_lookup.sqlite")
    current.execute("CREATE TABLE current_molecules(molecule_id TEXT PRIMARY KEY,archive_path TEXT)")
    for batch in pq.ParquetFile(catalog["latest_molecules"]).iter_batches(batch_size=8192,columns=["molecule_id","archive_path","receipt_context_consistent","export_published"]):
        current.executemany("INSERT INTO current_molecules VALUES(?,?)",[(row["molecule_id"],row["archive_path"]) for row in batch.to_pylist() if row["receipt_context_consistent"] and row["export_published"]])
    current.execute("CREATE INDEX archive_lookup ON current_molecules(archive_path)");current.commit();current.close()
    options={"dictionaries":str(args.dictionaries),"entries":{entry["registry_id"]:entry for entry in wire.registry(args.registry)},"companions":companions,"latest_molecules":catalog["latest_molecules"],"latest_sqlite":str(out/"latest_readonly_lookup.sqlite"),"D20_names":d20_names}
    results=[];exceptions=[];pids=set();fields=collections.Counter();statuses=collections.Counter();scalars={};all_issues=[]
    ctx=multiprocessing.get_context("spawn");started=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=initializer,initargs=(options,)) as pool:
        futures={pool.submit(check_file,ref):ref for ref in refs}
        for future in concurrent.futures.as_completed(futures):
            ref=futures[future]
            try:result=future.result()
            except Exception:exceptions.append({"path":ref["path"],"error":traceback.format_exc(limit=8)});continue
            pids.add(result["worker_pid"]);all_issues.extend({**issue,"path":result["path"]} for issue in result["issues"])
            for item in result.pop("field_counts"):fields[(item["registry_id"],item["task"],item["size_stratum"],item["element_presence"],item["category"])]+=item["count"]
            for item in result.pop("status_counts"):statuses[(item["task"],item["size_stratum"],item["status"])]+=item["count"]
            for item in result.pop("scalar_stats"):
                k=(item["registry_id"],item["task"],item["size_stratum"]);old=scalars.setdefault(k,[0,0.,0.,None,None])
                old[0]+=item["finite_values"];old[1]+=item["sum"];old[2]+=item["sum_squares"]
                old[3]=item["min"] if old[3] is None else min(old[3],item["min"]);old[4]=item["max"] if old[4] is None else max(old[4],item["max"])
            result.pop("issues");results.append(result)
            if len(results)%20==0:
                temporary=out/"progress.json";temporary.write_text(json.dumps({"files":len(results),"exceptions":len(exceptions),"worker_pids":sorted(pids),"seconds":time.monotonic()-started})+"\n")
    def table(name,rows):
        if rows:pq.write_table(pa.Table.from_pylist(rows),out/name,compression="zstd")
        else:publish(out/(name+".empty.json"),{"rows":0})
    table("field_missingness.parquet",[{"registry_id":rid,"task":task,"size_stratum":size,"element_presence":element,"category":category,"count":number} for (rid,task,size,element,category),number in fields.items()])
    table("task_status_distribution.parquet",[{"task":task,"size_stratum":size,"status":status,"count":number} for (task,size,status),number in statuses.items()])
    table("label_scalar_distributions.parquet",[{"registry_id":rid,"task":task,"size_stratum":size,"finite_values":v[0],"mean":v[1]/v[0] if v[0] else None,"stddev":math.sqrt(max(0.,v[2]/v[0]-(v[1]/v[0])**2)) if v[0] else None,"min":v[3],"max":v[4]} for (rid,task,size),v in scalars.items()])
    table("schema_array_qc_issues.parquet",all_issues)
    serious=[item for item in all_issues if item["issue"]!="ATOMIC_ARRAY_QC_RECORDED_FAILURE"]
    latest_qm=sum(item.get("latest_rows",0) for item in results if item["family"] not in {"raw_archive","base_geometry","D20","D3","QC","canonical_record_attempts"})
    latest_raw=sum(item.get("latest_raw_calc_rows",0) for item in results)
    latest_non_qm={family:sum(item.get("latest_rows",0) for item in results if item["family"]==family) for family in ("base_geometry","D20","D3","QC")}
    closed=latest_qm==catalog["expected_record_tasks"] and latest_raw==catalog["expected_record_tasks"] and all(rows==catalog["expected_records"] for rows in latest_non_qm.values())
    report={"stage":"WP5_ACCEPTANCE_SHA_ARRAY_RAW_READBACK","status":"PASS" if not exceptions and not serious and closed and catalog["status"]=="CLOSED" and len(pids)>=24 else "NOT_PASS",
        "files_verified":results,"file_exceptions":exceptions,"schema_qc_issue_rows":len(all_issues),"serious_schema_issue_rows":len(serious),
        "latest_qm_rows":latest_qm,"latest_raw_rows":latest_raw,"latest_non_qm_rows":latest_non_qm,"expected_record_tasks":catalog["expected_record_tasks"],"latest_closed":closed,
        "effective_worker_pids":sorted(pids),"effective_workers":len(pids),"seconds":time.monotonic()-started,
        "missingness_definition":"Each scalar/structured registry cell is counted by record element presence; multiple elements overlap. ANY is the additive record denominator. NULL/ABSENT/empty/nonfinite are separate; legal numeric zero is PRESENT.",
        "scalar_array_distributions":"Finite float scalar and float-array elements pooled per registry/size, never mixed across registry IDs. Integer atom/pair indices are excluded from physical distribution.",
        "bindings":{"catalog_sha256":sha(args.catalog),"dictionaries_sha256":sha(args.dictionaries),"registry_sha256":sha(args.registry),"D20_schema_source_sha256":dref["sha256"],"script_sha256":sha(__file__)},"new_QM_calls":0,"original_data_written":False}
    publish(out/"verification_report.json",report)
    Path(out/"latest_readonly_lookup.sqlite").unlink()
    print(json.dumps({"report":str(out/"verification_report.json"),"status":report["status"],"workers":len(pids)}))
    if report["status"]!="PASS":raise SystemExit(2)
if __name__=="__main__":main()
