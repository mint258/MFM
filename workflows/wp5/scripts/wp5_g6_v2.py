"""Six-node G6: real whole molecules, artificial cutoff, resume and immutable readback."""
from __future__ import annotations
import argparse,hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
SCREEN=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011")

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(8<<20),b""):h.update(block)
    return h.hexdigest()
def save(path,value):
    p=Path(path);tmp=p.with_name(p.name+".pending");tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n");tmp.replace(p)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dictionaries",type=Path,required=False)
    p.add_argument("--protocol",type=Path,default=ROOT/"configs/protocol.json")
    p.add_argument("--policy",choices=("ALL","SELECTIVE"),default="ALL")
    p.add_argument("--hours",type=float,default=8)
    p.add_argument("--check",action="store_true")
    a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print("AST_PASS_NO_QM");return
    node=socket.gethostname().split(".")[0];job=os.environ["SLURM_JOB_ID"]
    if node not in {"compute-0-"+str(i) for i in range(14,20)} or int(os.environ["SLURM_CPUS_PER_TASK"])<24:
        raise ValueError("G6_REQUIRES_ACTUAL_14_TO19_NODE24CPU")
    if not a.dictionaries:raise ValueError("Passed G3 dictionaries required")
    out=ROOT/"gates/g6"/node/("job_"+job);out.mkdir(parents=True,exist_ok=False)
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    db=duckdb.connect();db.execute("SET threads=24");db.execute("SET memory_limit='20GB'")
    def q(path):return "'"+str(path).replace("'","''")+"'"
    molpath=ROOT/"population/molecule_index.parquet"
    pilot=SCREEN/"c_engineering/xyz/analysis_geometry.parquet"
    db.execute("CREATE VIEW eligible AS SELECT m.* FROM read_parquet("+q(molpath)+") m "
               "WHERE molecule_id IN (SELECT DISTINCT molecule_id FROM read_parquet("+q(pilot)+"))")
    # Twenty whole molecules in one test cover all formal size strata, five
    # file groups and the pilot-eligible largest total-atom representative.
    # Node-specific ordering gives additional samples; the largest is shared.
    chosen=[];selected_info={}
    columns="molecule_id,records,max_heavy_atoms,max_total_atoms,file_group"
    def add(row):
        if row[0] not in selected_info:chosen.append((row[0],));selected_info[row[0]]=row
    def pick(condition,params=()):
        clause=" AND molecule_id NOT IN ("+",".join(q(molecule) for molecule in selected_info)+")" if selected_info else ""
        row=db.execute("SELECT "+columns+" FROM eligible WHERE "+condition+clause+
                       " ORDER BY CASE WHEN records>=4 THEN 0 ELSE 1 END,md5(molecule_id || ?) LIMIT 1",tuple(params)+(node,)).fetchone()
        if row is None:raise ValueError("G6_REQUIRED_COHORT_HAS_NO_ELIGIBLE_WHOLE_MOLECULE")
        add(row)
    largest=db.execute("SELECT "+columns+" FROM eligible ORDER BY max_total_atoms DESC,max_heavy_atoms DESC,molecule_id LIMIT 1").fetchone()
    if largest is None:raise ValueError("G6_PILOT_ELIGIBLE_FRAME_EMPTY")
    add(largest)
    ranges=[(0,10),(11,20),(21,30),(31,50),(51,75),(76,100),(101,1000000)]
    for lower,upper in ranges:
        if not any(lower<=row[2]<=upper for row in selected_info.values()):
            pick("max_heavy_atoms BETWEEN ? AND ?",(lower,upper))
    for group in range(1,6):
        if not any(row[4]==group for row in selected_info.values()):pick("file_group=?",(group,))
    while len(chosen)<20:
        group=min(range(1,6),key=lambda value:(sum(row[4]==value for row in selected_info.values()),value))
        pick("file_group=?",(group,))
    ids=[row[0] for row in chosen]
    if len(ids)!=20 or len(set(ids))!=20:raise ValueError("G6_WHOLE_MOLECULE_SELECTION_NOT20")
    save(out/"selected_molecules.json",{"selection":"all7strata/all5filegroups/piloteligible largest; node-specific deterministic ordering",
        "node":node,"source_pilot_geometry_sha256":digest(pilot),"largest_pilot_eligible_molecule":largest[0],
        "largest_total_atoms":largest[3],"molecules":[dict(zip(columns.split(","),row)) for row in selected_info.values()]})
    db.register("selected",pa.table({"molecule_id":ids}))
    directory=out/"record_index";directory.mkdir()
    db.execute("COPY (SELECT p.* FROM read_parquet("+q(ROOT/"population/formal_record_index.parquet")+
               ") p JOIN selected s USING(molecule_id) ORDER BY p.molecule_id,p.conformer_id,p.record_id) TO "+
               q(directory/"records.parquet")+" (FORMAT PARQUET, COMPRESSION ZSTD)")
    stats=db.execute("SELECT molecule_id,records,max_heavy_atoms,max_total_atoms,file_group FROM eligible JOIN selected USING(molecule_id)").fetchall()
    measured=db.execute("SELECT a.molecule_id,a.planned_allocated_seconds FROM read_parquet("+
                        q(ROOT/"packing/molecule_assignments.parquet")+") a JOIN selected s USING(molecule_id)").fetchall()
    costs=dict(measured)
    if len(costs)!=20 or any(not isinstance(value,(int,float)) or value<=0 for value in costs.values()):
        raise ValueError("G6_REAL_PACKING_COSTS_NOT_CLOSED")
    stats.sort(key=lambda row:(-costs[row[0]],row[0]))
    assignments=[{"molecule_id":mol,"records":records,"file_group":group,"task_id":0,
                  "sequence_in_task":i,"planned_allocated_seconds":costs[mol]}
                 for i,(mol,records,heavy,natoms,group) in enumerate(stats)]
    pq.write_table(pa.Table.from_pylist(assignments),out/"assignments.parquet",compression="zstd")
    save(out/"tasks.json",{"tasks":[{"task_id":0,"node":node,"record_directory":str(directory)}]})
    expected_records=sum(r[1] for r in stats);db.close()
    runner=ROOT/"scripts/wp5_runner_v2.py";queue=out/"queue.sqlite"
    base=[sys.executable,str(runner),"--plan",str(out/"tasks.json"),"--assignments",str(out/"assignments.parquet"),
          "--queue",str(queue),"--task-id","0","--dictionaries",str(a.dictionaries),"--protocol",str(a.protocol),
          "--policy",a.policy,"--hours",str(a.hours),"--export-reserve-hours","0.5","--smoke"]
    p99_ratio=4.671507082406139/1.71
    phase_hours={0:max(a.hours,max(costs[row[0]] for row in stats[:16])*p99_ratio/3600+.7),
                 1:max(a.hours,max(costs[row[0]] for row in stats[16:])*p99_ratio/3600+.7)}
    if sum(phase_hours.values())>45:
        raise ValueError("G6_REAL_PACKING_P99_NEEDS_MORE_THAN45H_COMBINED_PHASE_BUDGET")
    save(out/"phase_deadlines.json",{"phase_hours":phase_hours,"combined_budget_hours":sum(phase_hours.values()),
        "p99_ratio":p99_ratio,"source":"real frozen packing assigned whole-molecule cost; largest eligible molecule included",
        "allocation_hours":48,"extra_global_report_reserve_hours":48-sum(phase_hours.values())})
    phases=[]
    first_files={}
    for phase,cap in [(0,16),(1,0)]:
        root=out/("phase_"+str(phase))
        command=base+["--run-root",str(root),"--claim-cap",str(cap),"--hours",str(phase_hours[phase])]
        started=time.time();result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True)
        save(out/("phase_"+str(phase)+"_command.json"),{"argv":command,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr,"seconds":time.time()-started})
        if result.returncode!=0:raise RuntimeError("G6_RUNNER_NONZERO_"+str(phase))
        info=json.loads((root/"completion.json").read_text());phases.append(info)
        if info["error"] or not info["scratch_clean"] or any(row["error_count"] for row in info["workers"]):
            raise ValueError("G6_RUNTIME_OR_SCRATCH_FAILURE")
        if any(not r["cleanup"]["work_root_removed"] or not r["cleanup"]["LMDB_handles_closed"] for r in info["workers"]):
            raise ValueError("G6_EXPLICIT_CLOSE_WORKER_FAILED")
        if phase==0:
            if info["completed_molecules_this_run"]!=16 or info["queue"]["pending_molecules"]!=4:raise ValueError("G6_ARTIFICIAL_CUTOFF_NOT16_PLUS4")
            active={r["pid"] for r in info["workers"] if r["completed"]}
            if len(active)<16:raise ValueError("G6_ACTUAL_SCIENTIFIC_WORKERS_BELOW16")
            for ref in info["families"]+[info["archive"]]:first_files[ref["path"]]=ref["sha256"]
        else:
            if info["completed_molecules_this_run"]!=4 or info["queue"]["pending_molecules"]!=0:raise ValueError("G6_RESUME_RECOMPUTED_OR_LEFT_PENDING")
            for path,sha in first_files.items():
                if digest(path)!=sha:raise ValueError("G6_RESUME_MUTATED_PERMANENT_PHASE0")
    from wp5_archive_v2 import ArchiveReader
    raw_count=0;completed=set();scope_rows=[];compression_rows=[];active_intervals=[]
    heavy_by_mol={row[0]:row[2] for row in stats}
    def stratum(heavy):
        return next(label for limit,label in [(10,"0_10"),(20,"11_20"),(30,"21_30"),(50,"31_50"),(75,"51_75"),(100,"76_100"),(10**9,"above_100")] if heavy<=limit)
    def member(item,record_id,calc_type,molecule,role):
        return {"record_id":record_id,"molecule_id":molecule,"calc_type":calc_type,
                "size_stratum":stratum(heavy_by_mol[molecule]),"name":item["name"],"role":role,
                "bytes":item.get("byte_count",item.get("bytes",len(item["data"]) if "data" in item else None)),
                "sha256":item.get("sha256"),"unknown_scope_is_zero":False}
    for info in phases:
        archive=info["archive"];reader=ArchiveReader(archive["path"],a.dictionaries)
        try:
            for record_id,calc_type in reader.db.execute("SELECT record_id,calc_type FROM records"):
                raw=reader.get(record_id,calc_type);raw_count+=1;molecule=raw["molecule_id"]
                for item in raw["input_files"]:scope_rows.append(member(item,record_id,calc_type,molecule,"input"))
                for item in raw["original_output_manifest"]:scope_rows.append(member(item,record_id,calc_type,molecule,"output"))
                packed=reader.db.execute("SELECT input_bytes,raw_bytes,metadata_bytes,length(input_frame),length(raw_frame),length(metadata_frame) FROM records WHERE record_id=? AND calc_type=?",(record_id,calc_type)).fetchone()
                compression_rows.append({"record_id":record_id,"molecule_id":molecule,"calc_type":calc_type,
                    "size_stratum":stratum(heavy_by_mol[molecule]),"logical_input_bundle_bytes":packed[0],
                    "logical_output_bundle_bytes":packed[1],"logical_metadata_bytes":packed[2],
                    "input_frame_bytes":packed[3],"raw_frame_bytes":packed[4],"metadata_frame_bytes":packed[5],
                    "output_retained":raw["output_retained"],"source_status":raw["source_status"],"scope_status":raw["scope_status"],
                    "source_directory_total_bytes":sum(item["byte_count"] for item in raw["input_files"])+sum(item["bytes"] for item in raw["original_output_manifest"]) if raw["input_files"] or raw["original_output_manifest"] else None,
                    "directory_total_definition":"complete regular-file directory snapshot at frozen engine capture; includes binary restarts",
                    "excluded_restart_cache_bytes":0 if raw["input_files"] or raw["original_output_manifest"] else None,
                    "captured_directory_complete":bool(raw["input_files"] or raw["original_output_manifest"]),
                    "scope_unknown_reason":None if raw["input_files"] or raw["original_output_manifest"] else "No native-directory snapshot was produced; see archive input_missing_reason. Empty outputs are not evidence of zero-size original directory."})
            for molecule,receipt_json in reader.db.execute("SELECT molecule_id,receipt_json FROM completion_receipts"):
                receipt=json.loads(receipt_json);completed.add(molecule)
                if info is phases[0]:active_intervals.append((receipt["molecule_started_epoch"],receipt["completed_epoch"],receipt["worker_pid"]))
        finally:reader.close()
    if raw_count!=expected_records*12 or completed!=set(ids):raise ValueError("G6_RAW_RECORD_MOLECULE_CLOSURE")
    events=sorted([(start,1,pid) for start,end,pid in active_intervals]+[(end,-1,pid) for start,end,pid in active_intervals])
    active=set();max_active=0
    for _,change,pid in events:
        if change==1:active.add(pid)
        else:active.discard(pid)
        max_active=max(max_active,len(active))
    if len({pid for start,end,pid in active_intervals})<16 or max_active<16:
        raise ValueError("G6_MEASURED_CONCURRENT_SCIENTIFIC_WORKERS_BELOW16")
    pq.write_table(pa.Table.from_pylist(scope_rows),out/"raw_scope_members.parquet",compression="zstd")
    pq.write_table(pa.Table.from_pylist(compression_rows),out/"raw_compression_by_record.parquet",compression="zstd")
    save(out/"report.json",{"status":"G6_FULL_CHAIN_PASSED","node":node,"job_id":job,"molecules":20,
         "records":expected_records,"raw_calc_rows":raw_count,"five_file_groups":sorted({r[4] for r in stats}),
         "seven_size_strata":sorted({stratum(row[2]) for row in stats}),
         "largest_pilot_eligible_molecule":largest[0],"largest_pilot_eligible_total_atoms":largest[3],
         "phase_hours":phase_hours,"combined_phase_budget_hours":sum(phase_hours.values()),
         "large_molecules":sum(r[2]>75 for r in stats),"measured_peak_active_whole_molecule_workers":max_active,"artificial_cutoff_completed":16,"resume_new_completed":4,
         "permanent_first_phase_unchanged":True,"scratch_and_lmdb_handles_closed":True,
         "source_runner_sha256":digest(runner),"phases":[str(out/("phase_"+str(i))/"completion.json") for i in (0,1)],
         "resource_peaks":[r["resource_peaks"] for r in phases],
         "raw_scope_members":str(out/"raw_scope_members.parquet"),"raw_compression_by_record":str(out/"raw_compression_by_record.parquet"),
         "staged_compressed_wire_bytes":sum(r["staged_compressed_wire_bytes"] for r in phases),
         "staged_uncompressed_wire_bytes":sum(r["staged_uncompressed_wire_bytes"] for r in phases),
         "packing_cost_source":str(ROOT/"packing/molecule_assignments.parquet"),"new_QM":True,"original_data_written":False,"lmdb_created":False})
    print(json.dumps({"report":str(out/"report.json"),"node":node,"status":"G6_FULL_CHAIN_PASSED"}))
if __name__=="__main__":main()
