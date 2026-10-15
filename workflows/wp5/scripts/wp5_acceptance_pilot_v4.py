"""Compare final/pilot record intersection with bounded per-molecule workers; no QM."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,json,os,time,math,struct,tempfile
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
    qc_categories=qc_distribution(originals,actual,record_meta,_P["entries"])
    for key in sorted(lookup):
        changed,comparison_statuses,fields,_=compare_quantum((key,originals.get(key),actual.get(key),precision.get(key,{})))
        counts.update(comparison_statuses);byfield.update(fields)
        for row in changed:
            row["original_comparison"]=row["comparison"]
            proof=authorized.get((row["record_id"],row["calc_type"],row["registry_id"]))
            if proof:row.update(comparison=proof[0],reason=proof[1])
            elif classify_hb_difference(row,originals.get(key),actual.get(key),_P["entries"],_P.get("hb_proofs",{}).get(key[0])):pass
            elif row["registry_id"] is None and row["source_path"] in {"status","source_status","failure_code"} and key in polar_only:
                # Only explicit original POLAR_FRAGILE QC with good base/no other required missing/length failure proves this case.
                # Retained scientific values are compared independently above.
                if actual.get(key,{}).get("status")=="SUCCESS":
                    row.update(comparison="DELETED_POLAR_SCOPE_STATUS_CHANGE",reason="Original PM7 B POLAR_FRAGILE; authorized WP5 deletes POLAR; all retained fields still independently compared.")
            differences.append(row)
    return {"worker_pid":os.getpid(),"expected_slots":len(lookup),"original_slots":len(originals),"formal_slots":len(actual),
        "differences":differences,"comparison_counts":dict(counts),"field_counts":dict(byfield),
        "receipt_sha256":sha(receipt_path),"pilot_parquet_sha256":reference["sha256"],
        "missingness":dict(missing),"status_distribution":dict(statuses),"scalar_distribution":scalars,"QC_categories":dict(qc_categories)}

def private_check():
    """Owned synthetic Arrow fixtures, never original/pilot/formal SCI data."""
    import tempfile
    import pyarrow as pa,pyarrow.parquet as pq
    import wp5_parquet as legacy_wire,wp5_parquet_v2 as wire
    import wp5_acceptance_recompute as legacy_compare
    import wp5_acceptance_recompute_v10 as current_compare
    entry={"registry_id":1,"task":"pm7_B","source_path":"values.fixture","classification":"physical"}
    entries={1:entry};legacy_compare.init_compare(entries);current_compare.init_compare(entries)
    require_cases=[None,True,1,1.0,-0.0,"fixture",[1.0,-0.0],[1,2],[True,False],[],{},{"x":[1.0,None]}]
    cases=[(value,value) for value in require_cases]
    cases.extend([(legacy_wire.MISSING,wire.MISSING),(None,wire.MISSING),(0.0,-0.0),(1.0,1),(1.0,1.0001)])
    for left_value,right_value in cases:
        left=legacy_wire.encode(1,left_value);right=wire.encode(1,right_value)
        base={"status":"SUCCESS","source_status":"SUCCESS","total_atoms":1,"failure_code":None,
              "software_version_id":1,"scf_iterations":7,"converged":True,
              "input_file_sha256":[{"name":"input.mop","sha256":"a"*64}],
              "input_bundle_sha256":"b"*64,"raw_audit_selected":True,"precision_by_field_json":"{}"}
        pair=(("private","pm7_B"),{**base,"values":[left]},{**base,"values":[right]},{})
        old=legacy_compare.compare_quantum(pair);new=current_compare.compare_quantum(pair)
        assert old[0]==new[0] and old[1]==new[1] and old[2]==new[2],"LEGACY_CURRENT_CELL_COMPARISON_DIFFERS"
    assert legacy_wire.CELL.equals(wire.CELL),"REGISTRY_CELL_SCHEMA_DIFFERS"
    equal={**base,"values":[wire.encode(1,0.0)]};changed={**equal,"software_version_id":2}
    trace_pair=(("private","pm7_B"),equal,changed,{})
    assert legacy_compare.compare_quantum(trace_pair)[0]==[]
    trace_diff=current_compare.compare_quantum(trace_pair)[0]
    assert any(row["source_path"]=="software_version_id" for row in trace_diff),"CURRENT_200_TRACE_CHANGE_NOT_DETECTED"
    with tempfile.TemporaryDirectory(prefix="wp5_pilot_v2_private_") as folder:
        root=Path(folder);record_ids=["private_record_1","private_record_2"];pilot_rows=[];formal_rows=[];locators=[]
        for index,rid in enumerate(record_ids):
            detail={"record_id":rid,"molecule_id":"private_molecule","task":"pm7_B","natoms":1,"job_id":100,
                    "status":"SUCCESS","values":{"fixture":float(index)}}
            pilot_rows.append({"details_json":json.dumps(detail)})
            row=wire.task_row(rid,"private_molecule","pm7_B",detail,entries.values(),1)
            row.update(attempt_id=0,job_id=101,task_id="PRIVATE",lane=0,software_version_id=1,scf_iterations=7,converged=True,
                       input_file_sha256=[{"name":"input.mop","sha256":"a"*64}],input_bundle_sha256="b"*64,raw_audit_selected=True,
                       reproduction_package_sha256="c"*64,precision_by_field_json="{}");formal_rows.append(row)
            locators.append({"record_id":rid,"molecule_id":"private_molecule","calc_type":"pm7_B",
                             "attempt_id":0,"job_id":101,"task_id":"PRIVATE","lane":0,"family_parquet_path":str(root/"formal.parquet")})
        pq.write_table(pa.Table.from_pylist(pilot_rows),root/"pilot.parquet")
        pq.write_table(pa.Table.from_pylist(formal_rows,schema=wire.SCHEMA),root/"formal.parquet")
        reference={"path":str(root/"pilot.parquet"),"bytes":(root/"pilot.parquet").stat().st_size,"sha256":sha(root/"pilot.parquet")}
        (root/"receipt.json").write_text(json.dumps({"parquet":reference}))
        initialize({"entries":entries})
        result=pilot_one((str(root/"receipt.json"),locators,{}, {},
                          {rid:{"size_stratum":"0_10","elements":["H"]} for rid in record_ids}))
        assert result["expected_slots"]==result["original_slots"]==result["formal_slots"]==2
        assert result["differences"]==[] and result["comparison_counts"]=={"MATCH_BITS":2}
        expected={("original_pilot_eligible_intersection","pm7_B","0_10","SUCCESS"):2,
                  ("formal_same_record_intersection","pm7_B","0_10","SUCCESS"):2}
        assert result["status_distribution"]==expected,"STATUS_DISTRIBUTION_WAS_SHADOWED"
        assert all(len(key)==4 for key in result["status_distribution"])
    print(json.dumps({"status":"PILOT_V3_LEGACY_SCI_CURRENT_TRACE_COMPATIBILITY_PRIVATE_PASS",
        "cell_comparison_cases":len(cases),"private_original_and_formal_slots":2,
        "tuple4_status_distribution_verified":True,"common_scientific_cell_comparison_matches":True,"current_200_detects_changed_trace":True,"legacy_reference_has_no_fabricated_trace":True,
        "production_or_original_data_read":False,"QM_started":False}))


def qc_category_leaves(value,path="$"):
    if isinstance(value,bool):yield path,"BOOLEAN","true" if value else "false"
    elif isinstance(value,str):yield path,"CATEGORY",value
    elif isinstance(value,int):yield path,"INTEGER_CODE",str(value)
    elif isinstance(value,list):
        if not value:yield path,"EMPTY_CONTAINER","[]"
        for item in value:yield from qc_category_leaves(item,path+"[]")
    elif isinstance(value,dict):
        if not value:yield path,"EMPTY_CONTAINER","{}"
        for name,item in sorted(value.items()):
            if name not in {"elapsed_seconds","wall_seconds","predicted_seconds"}:
                yield from qc_category_leaves(item,path+"."+name)
    # Float QC scalars/arrays retain the unchanged existing label_distribution.
    # Nested float QC containers remain exact value comparisons; no categorical
    # bin or invented zero is introduced for a continuous quantity.

def qc_distribution(originals,actual,record_meta,entries):
    import wp5_parquet as wire
    result=collections.Counter()
    for record,calc in sorted(set(originals)|set(actual)):
        left={cell["registry_id"]:cell for cell in originals.get((record,calc),{}).get("values",[])}
        right={cell["registry_id"]:cell for cell in actual.get((record,calc),{}).get("values",[])}
        size=record_meta[record]["size_stratum"]
        for rid in sorted(set(left)|set(right)):
            if entries.get(rid,{}).get("classification")!="QC":continue
            a=left.get(rid);b=right.get(rid)
            available=lambda cell:cell is not None and cell["kind"] not in (0,9,10)
            paired=available(a) and available(b)
            for population,cell in (("original_pilot_eligible_intersection",a),("formal_same_record_intersection",b)):
                if not available(cell):
                    state="ABSENT" if cell is None else {0:"NULL",9:"ABSENT",10:"NONFINITE"}.get(cell["kind"],"UNAVAILABLE")
                    result[(population,rid,calc,size,"$","AVAILABILITY","UNAVAILABLE_"+state,False)]+=1
                    continue
                for path,kind,category in qc_category_leaves(wire.decode(cell)):
                    result[(population,rid,calc,size,path,kind,category,paired)]+=1
    return result

HB_CLASS="HB_NATIVE_SUMMARY_NULL_TO_VALUE_REPAIR"
HB_PATH="values.hydrogen_bond_energy_kcal_mol"

def verify_metadata_reference(reference):
    path=Path(reference["path"])
    if sha(path)!=reference["sha256"]:raise ValueError("CLOSED_HB_EVIDENCE_SHA_CHANGED")
    if reference.get("bytes") is not None and path.stat().st_size!=reference["bytes"]:
        raise ValueError("CLOSED_HB_EVIDENCE_SIZE_CHANGED")
    return path

def load_hb_evidence(closure_path,expected_sha,panel):
    import pyarrow.parquet as pq
    closure_ref={"path":str(closure_path),"sha256":expected_sha}
    closed=json.loads(verify_metadata_reference(closure_ref).read_text())
    if closed.get("status")!="PASS_FULL_FIELD_EXTRACTION":raise ValueError("ACTUAL_FULL_FIELD_CLOSURE_REQUIRED")
    if closed["latest_authority"]["QM_methods_keywords_geometry_binary_protocol_or_seeds_changed"] is not False:
        raise ValueError("UNCHANGED_SCIENTIFIC_SCOPE_REQUIRED")
    for ref in (closed["latest_authority"]["reference"],closed["historical_raw_exception"]["reference"]):
        verify_metadata_reference(ref)
    delta=closed["pilot_native_hydrogen_delta"]
    report=json.loads(verify_metadata_reference(delta["report"]).read_text())
    if report.get("status")!="PASS_DELTA_WITH_DISCLOSED_HISTORICAL_GAPS" or report.get("issues"):
        raise ValueError("CLOSED_NATIVE_HB_DELTA_REQUIRED")
    if report["result"]!=delta["result"]:raise ValueError("HB_RESULT_REFERENCE_DIFFERS")
    if sha(panel)!=delta["panel"]["sha256"] or str(panel)!=delta["panel"]["path"]:
        raise ValueError("HB_PROOF_PILOT_PANEL_DIFFERS")
    result_path=verify_metadata_reference(delta["result"])
    rows=pq.read_table(result_path).to_pylist();proofs={}
    for native in rows:
        record=native["record_id"]
        if record in proofs:raise ValueError("NATIVE_HB_PROOF_RECORD_DUPLICATED")
        native["_source_verified"]=True
        native["_delta_report_sha256"]=delta["report"]["sha256"]
        proofs[record]=native
    if len(proofs)!=report["records"]:raise ValueError("NATIVE_HB_PROOF_RECORD_COUNT_DIFFERS")
    return proofs,{"full_field_closure":closure_ref,"native_delta_report":delta["report"],
                   "native_delta_result":delta["result"],"latest_field_extraction_authority":closed["latest_authority"]["reference"],
                   "historical_raw_exception":closed["historical_raw_exception"]["reference"],
                   "scope":"Only per-record verified old NULL to exact native HB value; never a nonNULL value-drift exemption."}

def classify_hb_difference(row,left,right,entries,native):
    import wp5_parquet as wire
    rid=row.get("registry_id")
    if row.get("calc_type")!="pm7_B" or row.get("source_path")!=HB_PATH or entries.get(rid,{}).get("source_path")!=HB_PATH:
        return False
    if not left or not right or not native or native.get("_source_verified") is not True:return False
    if native.get("record_id")!=row["record_id"] or native.get("availability")!="INPUT_OUT_READ_AND_SHA_VERIFIED":return False
    if native.get("old_HB") is not None or native.get("fallback_applied") is not True:return False
    if native.get("old_parser_error") or native.get("new_parser_error"):return False
    if json.loads(native.get("non_HB_differences_json") or "[]"):return False
    token=native.get("native_token");decimals=native.get("rounding_decimal_places");file_sha=native.get("input_out_sha256","")
    if not isinstance(token,str) or not token or not isinstance(decimals,int) or isinstance(decimals,bool) or decimals<0:return False
    if not isinstance(file_sha,str) or len(file_sha)!=64 or any(c not in "0123456789abcdefABCDEF" for c in file_sha):return False
    a=[cell for cell in left["values"] if cell["registry_id"]==rid]
    b=[cell for cell in right["values"] if cell["registry_id"]==rid]
    if len(a)!=1 or len(b)!=1 or a[0]["kind"]!=0 or wire.decode(a[0]) is not None or b[0]["kind"]!=1:return False
    value=wire.decode(b[0]);expected=native.get("new_HB")
    if not isinstance(value,float) or not isinstance(expected,float) or not math.isfinite(value) or not math.isfinite(expected):return False
    if struct.pack(">d",value)!=struct.pack(">d",expected):return False
    row.setdefault("original_comparison",row["comparison"])
    row.update(comparison=HB_CLASS,reason="Source-backed legacy NULL to printed native HB repair; exact Float64 bits match closed per-record G5 delta. Native input.out SHA="+file_sha+
               "; token="+token+"; decimal_places="+str(decimals)+"; delta_report_SHA="+native["_delta_report_sha256"])
    return True

def hb_private_check():
    import wp5_parquet as wire
    entry={"registry_id":62,"source_path":HB_PATH};entries={62:entry}
    left={"values":[wire.encode(62,None)]};right={"values":[wire.encode(62,0.0)]}
    native={"record_id":"PRIVATE","_source_verified":True,"_delta_report_sha256":"d"*64,
            "availability":"INPUT_OUT_READ_AND_SHA_VERIFIED","old_HB":None,"new_HB":0.0,"fallback_applied":True,
            "native_token":"0.000","rounding_decimal_places":3,"input_out_sha256":"a"*64,
            "old_parser_error":None,"new_parser_error":None,"non_HB_differences_json":"[]"}
    def difference():return {"record_id":"PRIVATE","calc_type":"pm7_B","registry_id":62,"source_path":HB_PATH,
                             "comparison":"DIFFERENT","expected_sha256":"OLD_NULL","actual_sha256":"REAL_VALUE"}
    positive=difference();assert classify_hb_difference(positive,left,right,entries,native)
    assert positive["original_comparison"]=="DIFFERENT" and positive["expected_sha256"]=="OLD_NULL" and positive["actual_sha256"]=="REAL_VALUE"
    negative=[
        ({"values":[wire.encode(62,1.0)]},right,native,difference()),
        (left,{"values":[wire.encode(62,-0.0)]},native,difference()),
        (left,{"values":[wire.encode(62,0.001)]},native,difference()),
        (left,right,{**native,"_source_verified":False},difference()),
        (left,right,{**native,"record_id":"OTHER"},difference()),
        (left,right,{**native,"input_out_sha256":""},difference()),
        (left,right,native,{**difference(),"calc_type":"pm7_cation"})]
    for a,b,proof,row in negative:
        original=dict(row);assert not classify_hb_difference(row,a,b,entries,proof);assert row==original
    with tempfile.TemporaryDirectory(prefix="wp5_pilot4_hb_",dir="/tmp") as td:
        path=Path(td)/"private.json";path.write_bytes(b"closed metadata")
        ref={"path":str(path),"sha256":sha(path),"bytes":path.stat().st_size}
        assert verify_metadata_reference(ref)==path
        try:verify_metadata_reference({**ref,"sha256":"0"*64});raise AssertionError("Wrong source SHA accepted")
        except ValueError as exc:assert str(exc)=="CLOSED_HB_EVIDENCE_SHA_CHANGED"
    qc_entries={70:{"registry_id":70,"classification":"QC"}}
    meta={"P":{"size_stratum":"0_10"},"U":{"size_stratum":"0_10"}}
    original={("P","pm7_B"):{"values":[wire.encode(70,True)]},("U","pm7_B"):{"values":[wire.encode(70,None)]}}
    current={("P","pm7_B"):{"values":[wire.encode(70,False)]},("U","pm7_B"):{"values":[wire.encode(70,True)]}}
    observed=qc_distribution(original,current,meta,qc_entries)
    assert any(key[5:]==("BOOLEAN","true",True) and count==1 for key,count in observed.items())
    assert any(key[5:]==("BOOLEAN","false",True) and count==1 for key,count in observed.items())
    assert any(key[5:]==("AVAILABILITY","UNAVAILABLE_NULL",False) and count==1 for key,count in observed.items())
    assert any(key[0]=="formal_same_record_intersection" and key[5:]==("BOOLEAN","true",False) for key in observed)
    assert not any(key[5]=="INTEGER_CODE" for key in observed)
    print(json.dumps({"status":"PILOT4_SOURCE_BACKED_HB_CLASSIFIER_PRIVATE_PASS","positive_NULL_to_native":1,
        "negative_nonNULL_signedzero_drift_unverified_wrongRID_missingSHA_otherTask":len(negative),
        "all_difference_fields_retained":True,"QC_boolean_and_unavailable_categories_verified":True,"no_missing_QC_zero_filled":True,"wrong_source_SHA_rejected":True,
        "original_pilot_G5_or_SCI_opened":False,"new_QM":False,"private_fixture_cleaned":True}))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog",type=Path);ap.add_argument("--registry",type=Path)
    ap.add_argument("--pilot-root",type=Path,default=OLD/"wp4_native_full_v4")
    ap.add_argument("--pilot-panel",type=Path,default=OLD/"wp4_native_panel/pilot_panel.parquet")
    ap.add_argument("--regression-fields",type=Path,help="Closed G5 field_regression.parquet precision and authorized D4/deleted-POLAR proof")
    ap.add_argument("--hb-closure",type=Path);ap.add_argument("--expected-hb-closure-sha256")
    ap.add_argument("--workers",type=int,default=24);ap.add_argument("--out",type=Path);ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());hb_private_check();return
    require_slurm(args.workers)
    if not args.catalog or not args.registry:raise ValueError("catalog/registry required")
    if not args.hb_closure or not args.expected_hb_closure_sha256:raise ValueError("Exact closed native HB evidence path and SHA required")
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
    hb_proofs,hb_bindings=load_hb_evidence(args.hb_closure,args.expected_hb_closure_sha256,args.pilot_panel)
    receipts={}
    for path in sorted(args.pilot_root.glob("bucket_*/molecules/*/receipt.json")):
        receipt=json.loads(path.read_text())
        mol=receipt["molecule_id"]
        if mol in receipts:raise ValueError("DUPLICATE_PILOT_MOLECULE_RECEIPT")
        receipts[mol]=path
    missing_receipts=set(by_mol)-receipts.keys()
    if missing_receipts:raise ValueError("PILOT_MOLECULE_RECEIPTS_MISSING:"+str(len(missing_receipts)))
    schema=pa.schema([("record_id",pa.string()),("calc_type",pa.string()),("registry_id",pa.int16()),("source_path",pa.string()),("comparison",pa.string()),("reason",pa.string()),("expected_sha256",pa.string()),("actual_sha256",pa.string()),("expected_summary",pa.string()),("actual_summary",pa.string()),("rounding_tolerance",pa.float64()),("original_comparison",pa.string())])
    pending=out/"pilot_scientific_differences.parquet.pending";writer=pq.ParquetWriter(pending,schema,compression="zstd")
    counts=collections.Counter();byfield=collections.Counter();classified=collections.Counter();pids=set();proofs=[]
    missing=collections.Counter();statuses=collections.Counter();scalars={};qc_categories=collections.Counter()
    n_old=n_actual=n_expected=0;started=time.monotonic();ctx=multiprocessing.get_context("spawn")
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=initialize,initargs=({"entries":entries,"hb_proofs":hb_proofs},)) as pool:
            arguments=((str(receipts[mol]),rows,precision_by_mol.get(mol,{}),authorized_by_mol.get(mol,{}),{row["record_id"]:record_meta[row["record_id"]] for row in rows}) for mol,rows in sorted(by_mol.items()))
            for result in pool.map(pilot_one,arguments,chunksize=1):
                pids.add(result["worker_pid"]);counts.update(result["comparison_counts"]);byfield.update(result["field_counts"])
                n_old+=result["original_slots"];n_actual+=result["formal_slots"];n_expected+=result["expected_slots"]
                missing.update(result["missingness"]);statuses.update(result["status_distribution"]);qc_categories.update(result["QC_categories"])
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
    accepted={"AUTHORIZED_D4_CORRECTION","DELETED_POLAR_DIAGNOSTIC_REMOVED","DELETED_POLAR_SCOPE_STATUS_CHANGE",HB_CLASS}
    unresolved=sum(value for code,value in classified.items() if code not in accepted)
    ids=len(by_record)
    def distribution_file(name,rows):
        if rows:pq.write_table(pa.Table.from_pylist(rows),out/name,compression="zstd")
        else:publish(out/(name+".empty.json"),{"rows":0})
    distribution_file("pilot_vs_formal_field_missingness.parquet",[{"population":pop,"registry_id":rid,"task":calc,"size_stratum":size,"element_presence":element,"category":category,"count":number} for (pop,rid,calc,size,element,category),number in missing.items()])
    distribution_file("pilot_vs_formal_task_status.parquet",[{"population":pop,"task":calc,"size_stratum":size,"status":status,"count":number} for (pop,calc,size,status),number in statuses.items()])
    distribution_file("pilot_vs_formal_label_distribution.parquet",[{"population":pop,"registry_id":rid,"task":calc,"size_stratum":size,"finite_values":item[0],"mean":item[1]/item[0] if item[0] else None,"stddev":math.sqrt(max(0.,item[2]/item[0]-(item[1]/item[0])**2)) if item[0] else None,"min":item[3],"max":item[4]} for (pop,rid,calc,size),item in scalars.items()])
    distribution_file("pilot_vs_formal_QC_distribution.parquet",[{"population":pop,"registry_id":rid,"task":calc,"size_stratum":size,"qc_path":path,"value_type":kind,"category":category,"comparable_legacy_value_present":paired,"count":number} for (pop,rid,calc,size,path,kind,category,paired),number in qc_categories.items()])
    qc_availability={"common_registry_QC":"Actual shared registry classification=QC values. Boolean/category/integer-code/empty leaves are counted; unavailable legacy values produce explicit UNAVAILABLE rows and unpaired current observations.",
        "no_original_standalone_family_counterpart":{family:"UNAVAILABLE_IN_LEGACY_QM_PILOT; no zero-valued synthetic comparison" for family in ("base_geometry","D20","D3","QC_family")},
        "numeric_QC":"Existing kind1 float64 scalars and kind5 float64 arrays retain the label_distribution moments. Nested continuous float values in QC containers remain exact per-field comparisons and are not converted to categories; no nested numeric moments are claimed.",
        "observation_unit":"QC category leaf/array item or explicit availability event, not fabricated zero counts for missing labels."}
    publish(out/"pilot_QC_comparison_availability.json",qc_availability)
    report={"stage":"WP5_ACCEPTANCE_PILOT_INTERSECTION","status":"PASS" if not unresolved and n_old==n_actual==n_expected==ids*12 else "DIFFERENCES_REQUIRE_REVIEW",
        "formal_records_in_pilot_molecules":by_molecule[0],"formal_pilot_molecules":by_molecule[1],"exact_record_intersection":ids,"compared_quantum_slots":n_actual,"original_quantum_slots":n_old,
        "formal_conformers_of_pilot_molecules_without_original_pilot_record":by_molecule[0]-ids,"unrepresented_conformer_policy":"No original counterpart; report separately, never invent comparison or rerun whole pilot.",
        "comparison_counts_before_scope_classification":dict(counts),"classified_difference_counts":dict(classified),"difference_rows":sum(classified.values()),"unresolved_difference_rows":unresolved,
        "source_backed_HB_parser_repair_rows":classified[HB_CLASS],"all_DIFFERENCE_rows_retained_with_original_comparison":True,
        "PASS_meaning":"Complete matched 12N comparison; every difference is explicitly listed and either source-backed/classified or unresolved. PASS does not mean all original values were unchanged.",
        "HB_repair_evidence":hb_bindings,"QC_distribution":str(out/"pilot_vs_formal_QC_distribution.parquet"),"QC_comparison_availability":qc_availability,
        "differences":str(out/"pilot_scientific_differences.parquet"),"field_counts":[{"registry_id":rid,"comparison":status,"count":count} for (rid,status),count in byfield.items()],
        "historical_trace_comparison":{"status":"NOT_COMPARABLE_TO_LEGACY_SCHEMA","preserved_status_and_N_comparison":True,"not_compared":["software_version_id","scf_iterations","converged","input_file_sha256","input_bundle_sha256","raw_audit_selected"],"elapsed_seconds":"Observed execution duration is provenance and is not an equality label","policy":"No legacy trace backfill or numeric exception. Final200 uses current recompute10 full trace comparator."},
        "distribution_scope":"Matched original pilot/formal record intersection per registry/size/element; compare separately with final full-population verifier tables. ANY is additive record denominator. No threshold deletion. D20/D3 are covered by fresh200 and full schema checks; no fabricated original QM-pilot counterpart.",
        "precision":"Strict default with only actual G5 per-record field precision observations; no generic epsilon.",
        "effective_worker_pids":sorted(pids),"effective_workers":len(pids),"seconds":time.monotonic()-started,"source_receipts":proofs,
        "G5_raw_exception":"Approved historical raw absence only. Physical mismatches remain explicit; exception does not authorize fresh/formal numerical changes.",
        "bindings":{"catalog_sha256":sha(args.catalog),"pilot_panel_sha256":sha(args.pilot_panel),"registry_sha256":sha(args.registry),"regression_fields_sha256":sha(args.regression_fields) if args.regression_fields else None,"script_sha256":sha(__file__)},"new_QM_calls":0,"original_data_written":False}
    publish(out/"pilot_comparison.json",report);db.close()
    print(json.dumps({"report":str(out/"pilot_comparison.json"),"status":report["status"],"record_intersection":ids}))
if __name__=="__main__":main()

