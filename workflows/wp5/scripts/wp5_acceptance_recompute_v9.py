"""Prepare exactly 200 random formal record recalculations and compare scientific fields."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,math,os,struct,time
from pathlib import Path
from wp5_acceptance_catalog_v3 import ROOT,CALCS,sha,publish,q,copy,require_slurm
OLD=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010")
def bits_equal(a,b):
    from wp5_parquet_v2 import MISSING
    if a is MISSING or b is MISSING:return a is b
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(bits_equal(a[key],b[key]) for key in a)
    if isinstance(a,list):return len(a)==len(b) and all(bits_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,float):return struct.pack(">d",a)==struct.pack(">d",b)
    return a==b
def rounding_equal(a,b,tolerance):
    if type(a)!=type(b):return False
    if isinstance(a,list):return len(a)==len(b) and all(rounding_equal(x,y,tolerance) for x,y in zip(a,b))
    if isinstance(a,dict):return a.keys()==b.keys() and all(rounding_equal(a[key],b[key],tolerance) for key in a)
    if isinstance(a,float):return math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tolerance
    return a==b
def value_sha(value):
    from wp5_parquet_v2 import MISSING
    def wire(item):
        if item is MISSING:return {"MISSING":True}
        if isinstance(item,float):return {"float64_bits":struct.pack(">d",item).hex()}
        if isinstance(item,list):return [wire(x) for x in item]
        if isinstance(item,dict):return {str(key):wire(x) for key,x in sorted(item.items())}
        return item
    return hashlib.sha256(json.dumps(wire(value),sort_keys=True,separators=(",",":")).encode()).hexdigest()
def summary(value):
    from wp5_parquet_v2 import MISSING
    if value is MISSING:return "ABSENT"
    if value is None:return "NULL"
    if isinstance(value,list):return "list["+str(len(value))+"]"
    if isinstance(value,dict):return "dict:"+",".join(value)[:150]
    return str(value)[:200]
def read_rows(path,ids,keys=("record_id",)):
    import pyarrow.dataset as ds,pyarrow as pa
    pa.set_cpu_count(1)
    rows=ds.dataset(path,format="parquet").to_table(filter=ds.field("record_id").isin(ids),use_threads=False).to_pylist()
    return path,rows
def precision_manifest(basis,regression,out,selected_ids=None):
    rules=[];observations=[]
    if regression:
        import duckdb
        db=duckdb.connect();db.execute("SET threads=24")
        where="rounding_tolerance IS NOT NULL"
        if selected_ids:where+=" AND record_id IN ("+",".join(q(item) for item in selected_ids)+")"
        observations=[dict(zip(("record_id","calc_type","registry_id","source_path","absolute_tolerance","reason"),row)) for row in db.execute(
            "SELECT DISTINCT record_id,calc_type,registry_id,source_path,rounding_tolerance,reason FROM read_parquet("+q(regression)+") WHERE "+where).fetchall()]
        db.close()
    result={"strict_default":"recursive exact float64 bits, scalar types, shape and dict keys",
        "basis_script":str(basis),"basis_script_sha256":sha(basis),
        "rounding_policy":{"context_key":"rounding_decimal_places","tolerance":"0.5*10**(-decimal_places)",
            "dipole_Debye_conversion":"multiply explicit stdout au dipole precision by parser.AU_DIPOLE_TO_DEBYE",
            "required_evidence":"per-record field source=context stdout/AUX/JSON. No tolerance for unknown context; no generic relative epsilon."},
        "source_regression":str(regression) if regression else None,"source_regression_sha256":sha(regression) if regression else None,
        "observations":observations,"unknown_context":"STRICT_ONLY"}
    publish(out,result);return result
def prepare(args):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    require_slurm(args.workers)
    if not all((args.catalog,args.dictionaries,args.audit_membership,args.reproduction_package,args.production_contract)):raise ValueError("Closed final catalog/dictionaries/current audit/package/contract required")
    from wp5_submit_formal_v13 import validate_current_contract
    contract=validate_current_contract(args.production_contract,args.node_authority)
    from wp5_acceptance_verify_v9 import execution_authorities,run_execution_binding,reference_identity
    authorities=execution_authorities(args.production_contract);execution_cache={}
    runners=[ref for name,ref in contract['current_runtime'].items() if name.startswith('wp5_runner_v') and name.endswith('.py')]
    if len(runners)!=1:raise ValueError('UNIQUE_FROZEN_CURRENT_ACCEPTANCE_RUNNER_REQUIRED')
    current_runner=runners[0]
    if args.runner is None:args.runner=Path(current_runner['path'])
    if str(args.runner)!=current_runner['path'] or sha(args.runner)!=current_runner['sha256']:raise ValueError('ACCEPTANCE_RUNNER_DIFFERS_FROM_ACTUAL_CURRENT_CONTRACT')
    if reference_identity(contract['audit_manifest'])!={'path':str(args.audit_membership),'sha256':sha(args.audit_membership)} or reference_identity(contract['reproduction_package'])!={'path':str(args.reproduction_package),'sha256':sha(args.reproduction_package)}:raise ValueError('ACCEPTANCE_CURRENT_PACKAGE_AUDIT_CONTRACT_DIFFERS')
    catalog=json.loads(args.catalog.read_text())
    if sha(args.node_authority)!="32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f" or sha(args.node_scope_plan)!="dd195e994628c75b710de6e267f99556df59e918b875117907753693af638f3b":raise ValueError("CURRENT_APPROVED_NODE_SCOPE_SHA_REQUIRED")
    authority=json.loads(args.node_authority.read_text())
    if authority.get("status")!="USER_APPROVED" or authority.get("scientific_configuration_changed") is not False or authority.get("other_gates_and_200_recompute_waived") is not False:raise ValueError("NODE_SCOPE_DOES_NOT_CHANGE_200_SCIENCE")
    if catalog["status"]!="CLOSED":raise ValueError("Recompute acceptance requires a closed latest catalog")
    out=args.out or ROOT/"acceptance"/("recompute_plan_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    db=duckdb.connect();db.execute("SET threads="+str(args.workers));db.execute("SET memory_limit='20GB'")
    population=catalog["authority"]["population"]
    copy(db,"SELECT * FROM read_parquet("+q(population)+") ORDER BY md5(record_id||"+q(str(args.seed))+"),record_id LIMIT 200",out/"selected_record_index.parquet")
    selected=pq.read_table(out/"selected_record_index.parquet").to_pylist()
    if len(selected)!=200 or len({row["record_id"] for row in selected})!=200:raise ValueError("EXACT_200_RANDOM_UNIQUE_RECORDS_REQUIRED")
    db.execute("CREATE VIEW selected AS SELECT * FROM read_parquet("+q(out/"selected_record_index.parquet")+")")
    directory=out/"record_index";directory.mkdir()
    # Preserve the full-population context and fixed record-level audit membership.
    # Acceptance adds no ALL/minimum/forced-audit retention exception.
    copy(db,"SELECT * FROM selected ORDER BY molecule_id,conformer_id,record_id",directory/"records.parquet")
    db.execute("CREATE VIEW costs AS SELECT * FROM read_parquet("+q(ROOT/"packing/molecule_assignments.parquet")+")")
    assignments=[dict(zip(("molecule_id","records","file_group","original_total_records","planned_allocated_seconds"),row)) for row in db.execute(
        "SELECT s.molecule_id,count(*)::BIGINT,max(s.file_group)::INTEGER,max(c.records),max(c.planned_allocated_seconds)*count(*)/max(c.records) "
        "FROM selected s JOIN costs c USING(molecule_id) GROUP BY s.molecule_id ORDER BY 5 DESC,s.molecule_id").fetchall()]
    for index,row in enumerate(assignments):row.update(task_id=0,sequence_in_task=index)
    pq.write_table(pa.Table.from_pylist(assignments),out/"molecule_assignments.parquet",compression="zstd")
    node=os.uname().nodename.split(".")[0]
    if node not in {"compute-0-"+str(i) for i in (12,13,14,17,18,19)}:raise ValueError("Acceptance same authorized six-node environment required")
    publish(out/"tasks.json",{"schema":"WP5_AUTHORIZED_200_RECORD_ACCEPTANCE","tasks":[{"task_id":0,"node":node,"record_directory":str(directory)}],
        "record_scope":"Exactly 200 authorized random records, grouped by real molecule_id. This is an acceptance subset, not a new whole-population scientific pilot."})
    db.execute("CREATE VIEW canonical AS SELECT * FROM read_parquet("+q(catalog["latest_record_tasks"])+")")
    copy(db,"SELECT c.* FROM canonical c JOIN selected s USING(record_id) ORDER BY c.record_id,c.calc_type",out/"reference_record_tasks.parquet")
    reference=pq.read_table(out/"reference_record_tasks.parquet").to_pylist()
    if len(reference)!=2400:raise ValueError("REFERENCE_200_BY12_NOT_CLOSED")
    paths={}
    for row in reference:paths.setdefault(row["family_parquet_path"],[]).append(row["record_id"])
    originals={};lookup={(item["record_id"],item["calc_type"]):item for item in reference};record_lookup={item["record_id"]:item for item in reference}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for path,rows in pool.map(read_rows,paths,list(paths.values())):
            for row in rows:
                locator=lookup.get((row["record_id"],row["calc_type"]))
                if locator and all(row[key]==locator[key] for key in ("attempt_id","job_id","task_id","lane")):
                    key=(row["record_id"],row["calc_type"])
                    if key in originals:raise ValueError("REFERENCE_DUPLICATE_SELECTED_OUTCOME")
                    originals[key]=row
    if len(originals)!=2400:raise ValueError("REFERENCE_SCIENTIFIC_ROWS_NOT2400")
    artifact_refs={ref['path']:ref for ref in catalog['artifacts']}
    for key,row in originals.items():
        ref=artifact_refs[lookup[key]['family_parquet_path']]
        binding=run_execution_binding(ref,authorities,execution_cache)
        if row['reproduction_package_sha256']!=binding['package']['sha256']:
            raise ValueError('REFERENCE_ROW_NOT_OWN_ACTUAL_EXECUTION_PACKAGE')
    import wp5_parquet_v2 as wire
    pq.write_table(pa.Table.from_pylist(list(originals.values()),schema=wire.SCHEMA),out/"reference_quantum_rows.parquet",compression="zstd")
    for family,schema in (("base_geometry",wire.BASE_SCHEMA),("D20",wire.D20_SCHEMA),("D3",wire.D3_SCHEMA),("QC",wire.QC_SCHEMA)):
        paths={}
        for row in reference:paths.setdefault(str(Path(row["family_parquet_path"]).parent/(family+".parquet")),[]).append(row["record_id"])
        family_rows={}
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for path,rows in pool.map(read_rows,paths,list(paths.values())):
                for row in rows:
                    locator=record_lookup.get(row["record_id"])
                    if locator and all(row[key]==locator[key] for key in ("attempt_id","job_id","task_id")):
                        if row["record_id"] in family_rows:raise ValueError("REFERENCE_NONQM_DUPLICATE")
                        family_rows[row["record_id"]]=row
        if len(family_rows)!=200:raise ValueError("REFERENCE_NONQM_NOT200:"+family)
        pq.write_table(pa.Table.from_pylist(list(family_rows.values()),schema=schema),out/("reference_"+family+".parquet"),compression="zstd")
    precision=precision_manifest(args.precision_basis,args.regression_fields,out/"field_precision_manifest.json",[row["record_id"] for row in selected])
    protocol=ROOT/"configs/protocol.json"
    publish(out/"recompute_plan.json",{"selected_records":200,"selected_molecules":len(assignments),"requested_quantum_slots":2400,"seed":args.seed,
        "population":population,"catalog":str(args.catalog),"catalog_sha256":sha(args.catalog),"selection":"deterministic uniform record hash md5(record_id||seed), no element/size quota bias",
        "tasks":str(out/"tasks.json"),"assignments":str(out/"molecule_assignments.parquet"),"reference_quantum_rows":str(out/"reference_quantum_rows.parquet"),
        "dictionaries":str(args.dictionaries),"dictionaries_sha256":sha(args.dictionaries),"protocol":str(protocol),"protocol_sha256":sha(protocol),
        "runner":str(args.runner),"runner_sha256":sha(args.runner),"node_authority":str(args.node_authority),"node_authority_sha256":sha(args.node_authority),
        "node_scope_plan":str(args.node_scope_plan),"node_scope_plan_sha256":sha(args.node_scope_plan),"actual_node":node,"original_designed_node":{"compute-0-12":"compute-0-15","compute-0-13":"compute-0-16"}.get(node,node),"field_precision_manifest":str(out/"field_precision_manifest.json"),
        "expected_python":"/share/home/zixiao/.conda/envs/chemprop/bin/python","runtime_policy":"FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT; fixed original audit membership, no forced ordinary-success raw",
        "audit_manifest":{"path":str(args.audit_membership),"sha256":sha(args.audit_membership)},
        "reproduction_package":{"path":str(args.reproduction_package),"sha256":sha(args.reproduction_package)},
        "production_contract":{"path":str(args.production_contract),"sha256":sha(args.production_contract)},
        "reference_execution_bindings":execution_cache,
        "reference_package_validation":"Validated each selected original row against its actual immutable formal contract lineage (3/4/5/6), run and package; scientific comparisons do not relabel that provenance.",
        "command":["/share/home/zixiao/.conda/envs/chemprop/bin/python",str(args.runner),"--plan",str(out/"tasks.json"),"--assignments",str(out/"molecule_assignments.parquet"),
            "--node-authority",str(args.node_authority),"--node-scope-plan",str(args.node_scope_plan),
            "--queue",str(out/"queue.sqlite"),"--task-id","0","--dictionaries",str(args.dictionaries),"--policy","FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT","--audit-membership",str(args.audit_membership),"--reproduction-package",str(args.reproduction_package),"--production-contract",str(args.production_contract),"--smoke","--hours","46",
            "--run-root",str(out/"recomputed_runtime")],
        "scientific_record_subset_authorized_by":"WP5 guide Step6 random200 acceptance; no extra pilot/population scan",
        "new_QM_started_by_planner":False,"actual_QM_submission":"Root only"})
    db.close();print(json.dumps({"plan":str(out/"recompute_plan.json"),"records":200,"slots":2400}))
def normalized_scientific(value,entry):
    if entry["source_path"]=="values.mulliken_overlap_qc" and isinstance(value,dict):
        return {key:item for key,item in value.items() if key not in {"elapsed_seconds","wall_seconds"}}
    return value
_COMPARE_ENTRIES={}
def init_compare(entries):
    global _COMPARE_ENTRIES
    _COMPARE_ENTRIES=entries
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
def compare_quantum(arg):
    key,left,right,tolerances=arg
    entries=_COMPARE_ENTRIES
    import wp5_parquet_v2 as wire
    differences=[];counts=collections.Counter();field_counts=collections.Counter()
    def row(rid,path,status,x,y,tolerance=None,reason=None):
        differences.append({"record_id":key[0],"calc_type":key[1],"registry_id":rid,"source_path":path,"comparison":status,"reason":reason,
            "expected_sha256":value_sha(x),"actual_sha256":value_sha(y),"expected_summary":summary(x),"actual_summary":summary(y),"rounding_tolerance":tolerance})
    if left is None or right is None:
        row(None,None,"SLOT_MISSING",left,right,reason="formal/recomputed slot absent")
        return differences,{"SLOT_MISSING":1},{},os.getpid()
    for name in ("status","source_status","total_atoms","failure_code","software_version_id","scf_iterations","converged","input_file_sha256","input_bundle_sha256","raw_audit_selected"):
        if not bits_equal(left[name],right[name]):row(None,name,"STATUS_OR_N_DIFF",left[name],right[name]);counts["STATUS_OR_N_DIFF"]+=1
    a={cell["registry_id"]:cell for cell in left["values"]};b={cell["registry_id"]:cell for cell in right["values"]}
    required={rid for rid,entry in entries.items() if entry['task']==key[1]}
    if set(a)!=required or set(b)!=required or len(a)!=len(left['values']) or len(b)!=len(right['values']):row(None,'values','REGISTRY_CELL_SET_DIFF',sorted(a),sorted(b))
    declarations=[json.loads(item.get('precision_by_field_json') or '{}') for item in (left,right)]
    for rid in sorted(a.keys()|b.keys()):
        entry=entries.get(rid)
        if entry is None:raise ValueError("UNREGISTERED_FIELD_IN_RECOMPUTE")
        if entry.get("classification")=="provenance" or entry["source_path"] in {"values.mulliken_overlap_qc.elapsed_seconds","values.mulliken_overlap_qc.wall_seconds"}:continue
        x=wire.decode(a[rid]) if rid in a else wire.MISSING;y=wire.decode(b[rid]) if rid in b else wire.MISSING
        x=normalized_scientific(x,entry);y=normalized_scientific(y,entry)
        tolerance=None;precision_key=entry['source_path'].removeprefix('values.')
        p1,p2=(item.get(precision_key,item.get(entry['source_path'])) for item in declarations)
        if type(p1) is int and type(p2) is int and 0<=p1<=18 and 0<=p2<=18:
            tolerance=min(.5*10**(-p1),.5*10**(-p2))
            if precision_key=='dipole_Debye':
                from wp5_parser_v2 import AU_DIPOLE_TO_DEBYE
                tolerance*=AU_DIPOLE_TO_DEBYE
            if tolerances.get(rid) is not None:tolerance=min(tolerance,tolerances[rid])
        if bits_equal(x,y):status="MATCH_BITS"
        elif tolerance is not None and rounding_equal(x,y,tolerance):status="ROUNDING_MATCH"
        else:status="DIFF"
        counts[status]+=1;field_counts[(rid,status)]+=1
        if status=="DIFF":row(rid,entry["source_path"],status,x,y,tolerance,"strict or explicitly recorded precision only")
    return differences,dict(counts),dict(field_counts),os.getpid()


def compare(args):
    require_slurm(args.workers)
    if not args.recompute_plan or not args.completion:raise ValueError("--recompute-plan and new immutable --completion required")
    import pyarrow as pa,pyarrow.parquet as pq,wp5_parquet_v2 as wire
    plan=json.loads(args.recompute_plan.read_text());completion=json.loads(args.completion.read_text())
    out=args.out or ROOT/"acceptance"/("compare_200_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    old={(row["record_id"],row["calc_type"]):row for row in pq.read_table(plan["reference_quantum_rows"]).to_pylist()}
    current={}
    for ref in completion["families"]:
        if ref["family"] in {"base_geometry","D20","D3","QC"}:continue
        if sha(ref["path"])!=ref["sha256"]:raise ValueError("RECALC_FILE_SHA_CHANGED")
        for row in pq.read_table(ref["path"]).to_pylist():
            key=(row["record_id"],row["calc_type"])
            if key in current:raise ValueError("RECALC_DUPLICATE_SLOT")
            current[key]=row
    entries={entry["registry_id"]:entry for entry in wire.registry(json.loads((ROOT/"configs/protocol.json").read_text())["registry"]["path"])}
    precision=json.loads(Path(plan["field_precision_manifest"]).read_text())
    tolerances={(row["record_id"],row["calc_type"],row["registry_id"]):row["absolute_tolerance"] for row in precision["observations"]}
    precision_by_slot={}
    for (record,calc,rid),tolerance in tolerances.items():precision_by_slot.setdefault((record,calc),{})[rid]=tolerance
    bindings=plan['reference_execution_bindings']
    reference_locations={(r['record_id'],r['calc_type']):r for r in pq.read_table(Path(plan['reference_quantum_rows']).parent/'reference_record_tasks.parquet').to_pylist()}
    for key,row in old.items():
        location=reference_locations[key]['family_parquet_path']
        matches=[binding for root,binding in bindings.items() if Path(location).resolve().is_relative_to(Path(root).resolve())]
        if len(matches)!=1 or row['reproduction_package_sha256']!=matches[0]['package']['sha256']:
            raise ValueError('REFERENCE_RECORDED_EXECUTION_PACKAGE_DIFFERS')
    for row in current.values():
        if row['reproduction_package_sha256']!=plan['reproduction_package']['sha256']:
            raise ValueError('RECOMPUTED_ROW_NOT_PREPARED_CURRENT_PACKAGE')
    differences=[];counts=collections.Counter();field_counts=collections.Counter();worker_pids=set()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,initializer=init_compare,initargs=(entries,)) as pool:
        comparisons=((key,old.get(key),current.get(key),precision_by_slot.get(key,{})) for key in sorted(old.keys()|current.keys()))
        for changed,statuses,byfield,pid in pool.map(compare_quantum,comparisons,chunksize=4):
            worker_pids.add(pid);differences.extend(changed);counts.update(statuses);field_counts.update(byfield)
    family_ignored={"record_id","molecule_id","file_group","attempt_id","job_id","task_id",
        "source_path","real_index","source_payload_sha256","new_role","member_routine","conformer_id","population_QC_json"}
    for family in ("base_geometry","D20","D3","QC"):
        expected_path=Path(plan["reference_quantum_rows"]).parent/("reference_"+family+".parquet")
        expected={row["record_id"]:row for row in pq.read_table(expected_path).to_pylist()}
        actual={}
        for ref in completion["families"]:
            if ref["family"]==family:
                if sha(ref["path"])!=ref["sha256"]:raise ValueError("RECALC_NONQM_SHA_CHANGED")
                for row in pq.read_table(ref["path"]).to_pylist():
                    if row["record_id"] in actual:raise ValueError("RECALC_DUPLICATE_NONQM_RECORD")
                    actual[row["record_id"]]=row
        for record in sorted(expected.keys()|actual.keys()):
            a=expected.get(record);b=actual.get(record)
            if a is None or b is None:
                differences.append({"record_id":record,"calc_type":family,"registry_id":None,"source_path":None,"comparison":"NONQM_ROW_MISSING","reason":None,
                    "expected_sha256":value_sha(a),"actual_sha256":value_sha(b),"expected_summary":summary(a),"actual_summary":summary(b),"rounding_tolerance":None});continue
            for name in sorted(a):
                if name in family_ignored:continue
                x=a[name];y=b[name]
                if family=="QC" and name=="task_statuses":
                    x=[{key:value for key,value in row.items() if key not in {"elapsed_seconds","predicted_seconds"}} for row in x]
                    y=[{key:value for key,value in row.items() if key not in {"elapsed_seconds","predicted_seconds"}} for row in y]
                if not bits_equal(x,y):
                    differences.append({"record_id":record,"calc_type":family,"registry_id":None,"source_path":name,"comparison":"NONQM_SCIENTIFIC_DIFF","reason":"exact scientific family field",
                        "expected_sha256":value_sha(x),"actual_sha256":value_sha(y),"expected_summary":summary(x),"actual_summary":summary(y),"rounding_tolerance":None})
    schema=pa.schema([("record_id",pa.string()),("calc_type",pa.string()),("registry_id",pa.int16()),("source_path",pa.string()),("comparison",pa.string()),("reason",pa.string()),("expected_sha256",pa.string()),("actual_sha256",pa.string()),("expected_summary",pa.string()),("actual_summary",pa.string()),("rounding_tolerance",pa.float64())])
    pq.write_table(pa.Table.from_pylist(differences,schema=schema),out/"scientific_field_differences.parquet",compression="zstd")
    report={"status":"PASS" if len(old)==len(current)==2400 and not differences else "NOT_PASS","effective_compare_workers":len(worker_pids),"effective_compare_worker_pids":sorted(worker_pids),"selected_records":200,"reference_slots":len(old),"recomputed_slots":len(current),
        "comparison_counts":dict(counts),"differences":len(differences),"field_counts":[{"registry_id":rid,"comparison":status,"count":number} for (rid,status),number in field_counts.items()],
        "provenance_excluded":"registry classification=provenance and row attempt_id/job_id/task_id/lane/elapsed/qm_cpu_seconds/packageSHA; each package validated against its own actual execution before comparison; scientific/QC/derived/dedup fields retained",
        "missing_values":"ABSENT/NULL/legal zero remain distinct; no zero imputation",
        "precision_manifest":plan["field_precision_manifest"],"precision_sha256":sha(plan["field_precision_manifest"]),"diff_file":str(out/"scientific_field_differences.parquet"),
        "formal_artifacts_overwritten":False,"history_preserved":True,"new_QM_started_by_comparator":False,"bindings":{"plan_sha256":sha(args.recompute_plan),"completion_sha256":sha(args.completion),"script_sha256":sha(__file__)}}
    publish(out/"recompute_comparison.json",report);print(json.dumps({"report":str(out/"recompute_comparison.json"),"status":report["status"]}))
    if report["status"]!="PASS":raise SystemExit(2)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("operation",choices=("plan","compare"))
    ap.add_argument("--catalog",type=Path);ap.add_argument("--dictionaries",type=Path);
    ap.add_argument("--audit-membership",type=Path);ap.add_argument("--reproduction-package",type=Path);ap.add_argument("--production-contract",type=Path);ap.add_argument("--recompute-plan",type=Path);ap.add_argument("--completion",type=Path)
    ap.add_argument("--runner",type=Path,help="Defaults to the unique SHA-bound active runner in the actual current production contract")
    ap.add_argument("--node-authority",type=Path,default=ROOT/"gates/wp5_node_replacement_user_approved.json")
    ap.add_argument("--node-scope-plan",type=Path,default=ROOT/"packing/node_assignment_v3/tasks.json")
    ap.add_argument("--precision-basis",type=Path,default=ROOT/"scripts/wp5_parser_regression.py");ap.add_argument("--regression-fields",type=Path)
    ap.add_argument("--seed",type=int,default=20261011);ap.add_argument("--workers",type=int,default=24);ap.add_argument("--out",type=Path);ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());assert bits_equal([1.,None],[1.,None]);assert not bits_equal([-0.],[0.]);assert rounding_equal([1.],[1.0001],.0005)
        if args.production_contract:
            from wp5_acceptance_verify_v9 import execution_authorities
            authorities=execution_authorities(args.production_contract)
            print(json.dumps({'status':'FORMAL_CONTRACT_LINEAGE_METADATA_CHECK_PASS',
                              'contracts':list(authorities.values()),'SCI_or_population_opened':False,'QM_started':False}))

        print("ACCEPTANCE_RECOMPUTE_COMPARATOR_PASS_NO_QM_NO_DATA");return
    (prepare if args.operation=="plan" else compare)(args)
if __name__=="__main__":main()
