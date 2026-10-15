#!/usr/bin/env python3
"""WP4 native v2: read-only original geometries, sparse Mulliken pairs and resumable molecule checkpoints.

All outputs are analysis Parquet/JSON/compressed logs. No LMDB is created or
written. Only the explicitly separate xTB noise task changes coordinates.
"""
from __future__ import annotations
import argparse
import atexit
import concurrent.futures
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import pickle
import re
import resource
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
PROJECT = Path("/share/home/zixiao/descriptor_analysis")
DEFAULT_PLAN = PROJECT/"docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/plan.json"
AUDIT = DEFAULT_PLAN.parent
# Reuse installed read/Parquet dependencies; do not import old workflow guards.
sys.path[:0] = [str(AUDIT/"deps"),str(AUDIT/"scripts/deps")]
THREAD_ENV = {k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","BLIS_NUM_THREADS")}
HANDLES, SOURCES, CONFIG, PARSER, OUTPUT, DEADLINE, STOP_EVENT, MULLIKEN = {}, None, None, None, None, None, None, None
UNFINISHED = ("INTERRUPTED_DEADLINE","NOT_STARTED_DEADLINE","INTERRUPTED_STOP","NOT_STARTED_STOP")

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""): h.update(block)
    return h.hexdigest()

def stable_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def package_version(name):
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        module=__import__(name)
        return {"distribution_metadata":"UNAVAILABLE","module_version":str(getattr(module,"__version__","UNREPORTED"))}

def save_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+".pending")
    with pending.open("w",encoding="utf-8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    pending.replace(path)

def plain(value):
    if hasattr(value,"detach"): value=value.detach().cpu().numpy()
    return value

def raw_field(raw,name):
    return raw.get(name) if isinstance(raw,dict) else getattr(raw,name,None)

def close_handles():
    for handle in HANDLES.values(): handle.close()
    HANDLES.clear()

def initialize(sources,config,output,parser_path,deadline,stop_event):
    global SOURCES,CONFIG,OUTPUT,PARSER,DEADLINE,STOP_EVENT,MULLIKEN
    os.environ.update(THREAD_ENV); os.environ["CUDA_VISIBLE_DEVICES"]=""
    import torch
    import pyarrow as pa
    torch.set_num_threads(1)
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    SOURCES,CONFIG,OUTPUT,DEADLINE,STOP_EVENT=sources,config,Path(output),deadline,stop_event
    spec=importlib.util.spec_from_file_location("wp4_pinned_parsers",parser_path)
    PARSER=importlib.util.module_from_spec(spec); spec.loader.exec_module(PARSER)
    pair_spec=importlib.util.spec_from_file_location("wp4_pinned_mulliken_pairs",OUTPUT/"source_snapshot"/"wp4_mulliken_pairs_v2.py")
    MULLIKEN=importlib.util.module_from_spec(pair_spec); pair_spec.loader.exec_module(MULLIKEN)
    atexit.register(close_handles)

def read_native(row):
    import lmdb
    import numpy as np
    sid=int(row["shard_id"]); source=SOURCES[sid]["path"]
    if row.get("source_path") and row["source_path"]!=source: raise ValueError("SOURCE_PATH_MISMATCH")
    if sid not in HANDLES:
        HANDLES[sid]=lmdb.open(source,subdir=False,readonly=True,lock=False,create=False,
                              readahead=False,meminit=False,max_readers=512)
    real=int(row.get("real_index",row.get("source_record_index")))
    with HANDLES[sid].begin(buffers=False) as transaction:
        payload=transaction.get(f"{real:09d}".encode())
    if payload is None: raise ValueError("SOURCE_RECORD_MISSING")
    if hashlib.sha256(payload).hexdigest()!=row["record_payload_sha256"]: raise ValueError("SOURCE_PAYLOAD_SHA_MISMATCH")
    raw=pickle.loads(payload)
    atom_values=np.asarray(plain(raw_field(raw,"x"))).reshape(-1)
    if not np.isfinite(atom_values).all() or not np.equal(atom_values,np.floor(atom_values)).all():
        raise ValueError("SOURCE_ATOM_ENCODING_INVALID")
    z=atom_values.astype(np.int64)+1
    xyz=np.asarray(plain(raw_field(raw,"pos")),dtype=np.float64)
    energy_raw=raw_field(raw,"energy")
    energy_values=np.asarray(plain(energy_raw)).reshape(-1) if energy_raw is not None else []
    if xyz.shape!=(len(z),3) or not np.isfinite(xyz).all() or len(energy_values)>1:
        raise ValueError("SOURCE_GEOMETRY_OR_ENERGY_SHAPE")
    energy=float(energy_values[0]) if len(energy_values) else None
    if energy is not None and not math.isfinite(energy): energy=None
    if not len(z) or not ((z>=1)&(z<=118)).all():
        raise ValueError("SOURCE_NONFINITE_ENERGY_OR_ATOMS")
    sample=raw_field(raw,"sample_key")
    if row.get("sample_key") is not None and sample!=row["sample_key"]: raise ValueError("SOURCE_SAMPLE_KEY_MISMATCH")
    if row.get("total_atoms") is not None and len(z)!=int(row["total_atoms"]): raise ValueError("SOURCE_ATOM_COUNT_MISMATCH")
    expected=row.get("energy_raw",row.get("energy"))
    if expected is not None and math.isfinite(float(expected)) and float(expected)!=energy:
        raise ValueError("SOURCE_STORED_ENERGY_MISMATCH")
    from rdkit import Chem
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(int(value)) for value in z]
    pairs=list(zip(*np.tril_indices(len(z),-1)))
    keep=[(int(i),int(j)) for i,j in pairs if np.linalg.norm(xyz[i]-xyz[j])<=CONFIG["pair_cutoff_A"]]
    # Bonded pairs beyond the cutoff remain present when an ordered native graph is available.
    source_mol=Chem.MolFromSmiles(row["smiles"]) if row.get("smiles") else None
    source_h=Chem.AddHs(source_mol) if source_mol is not None else None
    if source_h is not None and source_h.GetNumAtoms()==len(z) and all(source_h.GetAtomWithIdx(i).GetAtomicNum()==int(z[i]) for i in range(len(z))):
        keep.extend((max(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),min(b.GetBeginAtomIdx(),b.GetEndAtomIdx())) for b in source_h.GetBonds())
    return {"symbols":symbols,"z":z,"coords":xyz,"energy":energy,"pairs":sorted(set(keep)),
            "native_coordinates_sha256":hashlib.sha256(xyz.astype("<f8").tobytes()).hexdigest(),
            "native_atom_order_sha256":hashlib.sha256(z.astype("<i8").tobytes()).hexdigest()}

def cleanup_scratch(path):
    path=Path(path)
    if not path.name.startswith(f"wp4native_{os.getuid()}_") or path.parent!=Path(CONFIG["scratch_base"]).absolute():
        raise RuntimeError("SCRATCH_PATH_OUTSIDE_PRIVATE_LOCAL_ROOT")
    entries=[path,*path.rglob("*")]
    for item in entries:
        info=item.lstat()
        if info.st_uid!=os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise RuntimeError("SCRATCH_OWNER_OR_TYPE:"+str(item))
    size=sum(item.lstat().st_size for item in entries if item.is_file())
    shutil.rmtree(path)
    return size

def output_archive(paths,target,member_prefix):
    """Stream only selected native-generated logs/AUX into one zstd archive."""
    target=Path(target); target.parent.mkdir(parents=True,exist_ok=True)
    pending=target.with_name(target.name+".pending")
    with pending.open("wb") as sink:
        process=subprocess.Popen([CONFIG["zstd_executable"],"-T1","-3","-c"],stdin=subprocess.PIPE,
                                  stdout=sink,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdin,mode="w|") as archive:
                for path in paths:
                    info=Path(path).lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid(): raise RuntimeError("NONREGULAR_ARCHIVE_INPUT")
                    archive.add(path,arcname=member_prefix+"/"+Path(path).name,recursive=False)
        finally: process.stdin.close()
        error=process.stderr.read(); code=process.wait()
        if code: raise RuntimeError("ZSTD_FAILED:"+error.decode(errors="replace")[-1000:])
        sink.flush(); os.fsync(sink.fileno())
    pending.replace(target)
    return {"path":str(target),"bytes":target.stat().st_size,"sha256":sha(target)}

def sparse_sigma_pi(text,pairs):
    """Same lower-triangle parser as the audited probe; discard distant pairs while reading."""
    start=text.find("SIGMA-PI BOND-ORDER MATRIX")
    if start<0: return []
    text=text[start:].split("TOTAL ENERGY PARTITIONING")[0]
    labels=r"[SPDF]-(?:SIGMA|PI|DELL|DELTA|DEL)"
    header=re.compile(r"^\s*(?:"+labels+r"\s*)+$")
    row=re.compile(r"^\s*("+labels+r")\s+([A-Z][a-z]?)\s+(\d+)\s+(.*)$")
    keys,entries,offset,previous=[],[],0,0
    selected=set(pairs)
    for line in text.splitlines():
        if header.fullmatch(line):
            offset+=previous; previous=len(re.findall(labels,line)); continue
        hit=row.match(line)
        if not hit: continue
        key=(int(hit.group(3))-1,hit.group(1))
        if key not in keys: keys.append(key)
        try: values=[PARSER.f(x) for x in hit.group(4).split()]
        except ValueError: continue
        for col,value in enumerate(values,offset):
            if col>=len(keys): continue
            other=keys[col]
            if key[0]==other[0] or (max(key[0],other[0]),min(key[0],other[0])) in selected:
                entries.append({"atom_i":key[0],"basis_i":key[1],"atom_j":other[0],"basis_j":other[1],"value":value})
    return entries

def native_aux_labels(path):
    """Stream the small label fields; do not materialize huge MO/density blocks."""
    path=Path(path)
    if not path.exists(): return {},["AUX_MISSING"]
    wanted={"BOND_ORDERS","EIGENVALUES","MOLECULAR_ORBITAL_OCCUPANCIES","DIP_VEC:DEBYE",
            "AO_ATOMINDEX","ATOM_SYMTYPE","AO_CHARGES","GRADIENTS:KCAL/MOL/ANGSTROM","MULLIKEN_ATOM_CHARGES"}
    header=re.compile(r"^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*(.*)$")
    result,errors={},[]; active=None; count=None; tokens=[]
    def finish():
        if active is None: return
        selected=tokens[:count] if count is not None else tokens
        if count is not None and len(selected)!=count: errors.append("AUX_COUNT_MISMATCH:"+active)
        result[active]=[PARSER.f(x) if re.fullmatch(PARSER.FLOAT,x) else x.strip('"') for x in selected]
    with path.open(errors="replace") as stream:
        for line in stream:
            match=header.match(line.rstrip("\n"))
            if match:
                finish(); name=match.group(1).strip(); active=name if name in wanted else None
                count=int(match.group(2)) if match.group(2) else None
                tokens=match.group(3).split() if active else []
            elif active and not line.lstrip().startswith("#"): tokens.extend(line.split())
        finish()
    return result,errors

def child_limits():
    ceiling=int(CONFIG["per_file_limit_bytes"])
    resource.setrlimit(resource.RLIMIT_FSIZE,(ceiling,ceiling))

def proc_identity(pid):
    """Read identity from the actual process; do not infer it from argv alone."""
    root=Path("/proc")/str(pid)
    try:
        fields=(root/"stat").read_text().rsplit(")",1)[1].split()
        status=(root/"status").read_text()
        uid_line=next(line for line in status.splitlines() if line.startswith("Uid:"))
        return {"pid":int(pid),"ppid":int(fields[1]),"start_ticks":int(fields[19]),
                "state":fields[0],"uids":[int(x) for x in uid_line.split()[1:]],
                "cgroup":(root/"cgroup").read_text()}
    except (FileNotFoundError,ProcessLookupError): return None

def same_process(current,bound):
    return current is not None and bound is not None and current["pid"]==bound["pid"] and current["start_ticks"]==bound["start_ticks"] and current["uids"]==bound["uids"] and current["cgroup"]==bound["cgroup"]

def stop_qm(process,launch_identity):
    """Signal only this Popen and verified descendants, one PID at a time."""
    if process.poll() is not None: return {"status":"ALREADY_EXITED","returncode":process.returncode,"signalled":[]}
    parent=proc_identity(process.pid)
    if parent is None:
        try: return {"status":"EXITED_DURING_IDENTITY_READ","returncode":process.wait(timeout=2),"signalled":[]}
        except subprocess.TimeoutExpired: raise RuntimeError("QM identity unavailable while Popen remains running")
    own_cgroup=Path("/proc/self/cgroup").read_text()
    if not same_process(parent,launch_identity) or parent["uids"]!=[os.getuid()]*4 or parent["cgroup"]!=own_cgroup:
        raise RuntimeError("QM PID/UID/start_ticks/Slurm cgroup identity differs; no signal sent")
    identities={}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit(): continue
        try:
            identity=proc_identity(int(directory.name))
            if identity: identities[identity["pid"]]=identity
        except (PermissionError,OSError): continue
    selected={process.pid:parent}
    changed=True
    while changed:
        changed=False
        for pid,identity in identities.items():
            if pid not in selected and identity["ppid"] in selected:
                if identity["uids"]!=[os.getuid()]*4 or identity["cgroup"]!=own_cgroup:
                    raise RuntimeError("QM descendant owner/cgroup differs; no unverified signal sent")
                selected[pid]=identity; changed=True
    events=[]
    def send(bound,sig):
        current=proc_identity(bound["pid"])
        if current is None or current["state"]=="Z": return
        if not same_process(current,bound): raise RuntimeError("QM identity changed before per-PID signal")
        pidfd=None
        try:
            if hasattr(os,"pidfd_open") and hasattr(signal,"pidfd_send_signal"):
                try: pidfd=os.pidfd_open(bound["pid"])
                except OSError: pidfd=None
            # Recheck after opening a pidfd; where unavailable, retain the close
            # /proc recheck and report that signals were ordinary per-PID calls.
            if not same_process(proc_identity(bound["pid"]),bound): return
            if pidfd is not None: signal.pidfd_send_signal(pidfd,sig)
            elif bound["pid"]==process.pid:
                if process.poll() is None:
                    if sig==signal.SIGTERM: process.terminate()
                    else: process.kill()
            else: os.kill(bound["pid"],sig)
            events.append({"pid":bound["pid"],"uid":bound["uids"][0],"start_ticks":bound["start_ticks"],
                           "signal":int(sig),"pidfd":pidfd is not None})
        except ProcessLookupError: pass
        finally:
            if pidfd is not None: os.close(pidfd)
    for pid,bound in reversed(list(selected.items())): send(bound,signal.SIGTERM)
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired: pass
    for pid,bound in reversed(list(selected.items())): send(bound,signal.SIGKILL)
    code=process.wait(timeout=5)
    return {"status":"VERIFIED_POPEN_TREE_ENDED","returncode":code,"signalled":events,
            "slurm_job_id":os.environ["SLURM_JOB_ID"]}

def invoke(task,native,row,mol_dir):
    """Copy of the proven invocation lifecycle, with native numerical parsing before cleanup."""
    import numpy as np
    symbols=native["symbols"]; coords=native["coords"]
    perturb_seed=1+int(hashlib.sha256((str(CONFIG["seed"])+"|"+row["record_id"]).encode()).hexdigest()[:16],16)%2147483646
    if task.get("perturbed"): coords=coords+np.random.default_rng(perturb_seed).normal(0,CONFIG["perturb_sigma_A"],coords.shape)
    scratch=Path(tempfile.mkdtemp(prefix=f"wp4native_{os.getuid()}_{os.environ['SLURM_JOB_ID']}_",dir=CONFIG["scratch_base"]))
    key=hashlib.sha256((row["record_id"]+"|"+task["name"]).encode()).hexdigest()[:24]
    result={"record_id":row["record_id"],"molecule_id":row["molecule_id"],"conformer_id":row.get("conformer_id"),
            "split":row.get("split"),"natoms":len(symbols),"heavy_atoms":int((native["z"]>1).sum()),
            "task":task["name"],"family":task["family"],"source_payload_sha256":row["record_payload_sha256"],
            "size_stratum":row.get("size_stratum"),
            "native_coordinates_sha256":native["native_coordinates_sha256"],"native_atom_order_sha256":native["native_atom_order_sha256"],
            "stored_HOF_kcal_mol":native["energy"],"job_id":os.environ["SLURM_JOB_ID"],"worker_pid":os.getpid(),
            "status":"RUNNER_ERROR","failure_code":None,"failure_reason":None,"values":{},"qc_codes":[]}
    started=time.monotonic(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
    process=None; launch_identity=None
    try:
        text=str(len(symbols))+"\nWP4 native geometry; coordinates Angstrom; "+row["record_id"]+"\n"
        text+="\n".join(f"{s} {x:.12f} {y:.12f} {z:.12f}" for s,(x,y,z) in zip(symbols,coords))+"\n"
        (scratch/"input.xyz").write_text(text)
        reread=np.array([[float(x) for x in line.split()[1:]] for line in text.splitlines()[2:]])
        result["xyz_roundtrip_max_error_A"]=float(np.max(np.abs(reread-coords)))
        if result["xyz_roundtrip_max_error_A"]>=1e-6: raise ValueError("XYZ_ROUNDTRIP_FAILED")
        env={**os.environ,**THREAD_ENV,"CUDA_VISIBLE_DEVICES":"","TMPDIR":str(scratch),"TMP":str(scratch)}
        env.update(CONFIG[task["family"]+"_environment"])
        if task["family"]=="mopac":
            keywords=task["keywords"]+" THREADS=1"; result["keywords"]=keywords
            mop=keywords+"\n"+row["record_id"]+"\nStored native PM7 coordinates; single point, no optimization\n"
            mop+="\n".join(f"{s} {x:.12f} 1 {y:.12f} 1 {z:.12f} 1" for s,(x,y,z) in zip(symbols,coords))+"\n"
            (scratch/"input.mop").write_text(mop)
            argv=[CONFIG["mopac_executable"],"input.mop"]
        else:
            (scratch/"native.inp").write_text(task.get("xcontrol","$write\n json=true\n$end\n"))
            argv=[CONFIG["xtb_executable"],"input.xyz","--input","native.inp","--norestart","--parallel","1",*task["args"]]
            result["arguments"]=task["args"]
        result["argv"]=argv
        allowance=float(task.get("timeout_seconds",CONFIG["timeout_seconds"]))
        remaining=DEADLINE-time.time()-30
        if STOP_EVENT.is_set():
            result.update(status="NOT_STARTED_STOP",failure_code="STOP_REQUEST"); return result
        if remaining<=0:
            result.update(status="NOT_STARTED_DEADLINE",failure_code="DEADLINE"); return result
        timeout=min(allowance,remaining)
        with (scratch/"process.out").open("wb") as stream:
            process=subprocess.Popen(argv,cwd=scratch,env=env,stdin=subprocess.DEVNULL,stdout=stream,
                                     stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_limits)
            launch_identity=proc_identity(process.pid)
            timed_out=False; interrupted_stop=False
            while True:
                wait_left=timeout-(time.monotonic()-started)
                if STOP_EVENT.is_set() or wait_left<=0:
                    interrupted_stop=STOP_EVENT.is_set()
                    timed_out=True
                    result.update(status="INTERRUPTED_STOP" if interrupted_stop else "INTERRUPTED_DEADLINE" if remaining<allowance else "TIMEOUT",
                                  failure_code="STOP_REQUEST" if interrupted_stop else "DEADLINE" if remaining<allowance else "CALCULATION_TIMEOUT",
                                  failure_reason="Own QM interrupted by stop request" if interrupted_stop else "Own QM reached wall deadline" if remaining<allowance else "Own QM exceeded per-call timeout")
                    result["qm_termination"]=stop_qm(process,launch_identity)
                    code=process.wait()
                    if not result["qm_termination"]["signalled"]:
                        timed_out=False; result.update(status="RUNNER_ERROR",failure_code=None,failure_reason=None)
                    break
                try: code=process.wait(timeout=min(2,wait_left)); break
                except subprocess.TimeoutExpired: continue
        result.update(returncode=code,elapsed_seconds=time.monotonic()-started)
        if timed_out:
            result.update(status="INTERRUPTED_STOP" if interrupted_stop else "INTERRUPTED_DEADLINE" if remaining<allowance else "TIMEOUT",
                          failure_code="STOP_REQUEST" if interrupted_stop else "DEADLINE" if remaining<allowance else "CALCULATION_TIMEOUT")
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        result["qm_child_cpu_seconds"]=(after.ru_utime-before.ru_utime)+(after.ru_stime-before.ru_stime)
        main=(scratch/"input.out") if task["family"]=="mopac" and (scratch/"input.out").exists() else (scratch/"process.out")
        out_text=main.read_text(errors="replace")
        result["software_version_lines"]=[x.strip() for x in out_text.splitlines() if re.search(r"MOPAC v\d|xtb version",x,re.I)]
        result["diagnostic_lines"]=[x.strip() for x in out_text.splitlines() if re.search(r"error|fail|does not work|not available|abnormal|warning|not converg|fragile",x,re.I)][-30:]
        if task["family"]=="mopac":
            PARSER.read_aux=native_aux_labels
            PARSER.sigma_pi_entries=lambda body:sparse_sigma_pi(body,native["pairs"])
            values=PARSER.parse_mopac(scratch,symbols,pair_indices=native["pairs"],reconstruct_mulliken=False)
            if task["name"]=="pm7_B":
                overlap=MULLIKEN.sparse_mulliken_from_aux(scratch/"input.aux",symbols,native["pairs"],
                    reference_charges=values.get("mulliken_charges_e"),
                    charge_tolerance_e=CONFIG["mulliken_overlap_charge_tolerance_e"],
                    min_absolute_eigenvalue=CONFIG["mulliken_minimum_absolute_eigenvalue"])
                values["mulliken_overlap_population_pairs"]=overlap["pairs"]
                values["mulliken_overlap_qc"]=overlap["qc"]
                values["mulliken_reconstruction_charge_max_error_e"]=overlap["qc"].get("reconstructed_charge_max_error_e")
            population=values.get("ao_population_e"); ao_atoms=values.get("ao_atom_index_1based"); ao_types=values.get("ao_types")
            if population and ao_atoms and ao_types and len(population)==len(ao_atoms)==len(ao_types):
                shell_population=[{"s":0.0,"p":0.0,"d":0.0,"f":0.0,"unknown":0.0} for _ in symbols]
                for atom,kind,value in zip(ao_atoms,ao_types,population):
                    kind=str(kind).upper()
                    shell="s" if kind=="S" else "p" if kind.startswith("P") else "d" if kind.startswith("D") or kind in ("X2","XZ","Z2","YZ","XY") else "f" if kind.startswith("F") else "unknown"
                    shell_population[int(atom)-1][shell]+=float(value)
                values["atomic_shell_population_e"]=shell_population
            # These are basis mapping/intermediates, not additional duplicated labels.
            for key_to_remove in ("ao_population_e","ao_atom_index_1based","ao_types"): values.pop(key_to_remove,None)
        else:
            values=PARSER.parse_xtb(scratch,symbols)
            if values.get("wiberg_pairs"):
                allowed=set(native["pairs"])
                values["wiberg_pairs"]=[p for p in values["wiberg_pairs"] if (max(p["i"],p["j"]),min(p["i"],p["j"])) in allowed]
        result["values"]=values
        if task.get("perturbed"):
            values.update(positions_A=coords.tolist(),elements=symbols,perturb_seed=perturb_seed,perturb_sigma_A=CONFIG["perturb_sigma_A"])
        basic=values.get("heat_of_formation_kcal_mol") if task["family"]=="mopac" else values.get("energy_Eh")
        scf_failed=bool(re.search(r"SCF DOES NOT CONVERGE|SCF NOT CONVERGED|SCF FAILED|UNABLE TO ACHIEVE SELF-CONSISTENCY|SCC IS NOT CONVERGED",out_text,re.I))
        base_good=code==0 and values.get("normal_end") is True and basic is not None and not timed_out and not scf_failed
        if not timed_out and not base_good: result.update(status="CALCULATION_FAILED",failure_code="QM_EXIT_OR_SCF_FAILED")
        elif not timed_out: result["status"]="SUCCESS"
        if code==-signal.SIGXFSZ or "file too large" in out_text.lower():
            result.update(status="RESOURCE_LIMIT_FAILED",failure_code="OUTPUT_FILE_LIMIT")
        if values.get("property_failure_lines") and result["status"]=="SUCCESS":
            result.update(status="PROPERTY_FAILED",failure_code="METHOD_PROPERTY_UNSUPPORTED")
        missing=[name for name in task["required_values"] if values.get(name) is None or values.get(name)==[] or values.get(name)=={}]
        if missing:
            result["missing_properties"]=missing
            if result["status"]=="SUCCESS": result.update(status="PROPERTY_FAILED",failure_code="NUMERIC_PROPERTY_MISSING")
        lengths={
            "net_charges_e":len(symbols),"mulliken_charges_e":len(symbols),"esp_charges_e":len(symbols),
            "atomic_shell_population_e":len(symbols),"gradient_kcal_mol_A":3*len(symbols),
            "charges_e":len(symbols),"D4_atomic_C6_au":len(symbols),"D4_atomic_alpha_bohr3":len(symbols),
            "FOD_atom_e":len(symbols),"fukui":len(symbols),"forces_eV_A":len(symbols),
            "frequencies_cm_inverse":3*len(symbols),"IR_km_mol":3*len(symbols)}
        length_issues=[key for key,size in lengths.items() if values.get(key) is not None and values.get(key)!=[] and len(values[key])!=size]
        if length_issues:
            result["length_issues"]=length_issues
            if result["status"]=="SUCCESS": result.update(status="PROPERTY_FAILED",failure_code="ATOMIC_ARRAY_LENGTH_MISMATCH")
        if task["name"]=="pm7_B":
            result["B_base_success"]=base_good and values.get("gradient_norm_kcal_mol_A") is not None
            if not result["B_base_success"] and result["status"] not in UNFINISHED:
                result["qc_codes"].append("Q03")
            result["Q02_delta_HOF_kcal_mol"]=values.get("heat_of_formation_kcal_mol")-native["energy"] if basic is not None and native["energy"] is not None else None
            result["Q01_gradient_norm_kcal_mol_A"]=values.get("gradient_norm_kcal_mol_A")
            alpha=values.get("static_polar_block")
            if alpha and alpha["max_antisymmetric_component_bohr3"]>CONFIG["polar_asymmetry_qc_bohr3"]:
                result["qc_codes"].append("POLAR_TENSOR_ASYMMETRIC")
            result["qc_codes"].extend(values.get("mulliken_overlap_qc",{}).get("codes",[]))
        # Specialty xTB calls can dump properties of their final internal ionic
        # state. Retain requested labels with explicit scope; the main log keeps
        # all intermediate diagnostics. This prevents duplicate/mis-scoped labels.
        xtb_labels={
            "xtb_singlepoint":("energy_Eh","dipole_Debye","charges_e","D4_atomic_C6_au","D4_atomic_alpha_bohr3","molecular_quadrupole_traceless_au","wiberg_pairs","homo_eV","lumo_eV"),
            "xtb_vipea":("IP_eV","EA_eV"),
            "xtb_vfukui":("fukui",),
            "xtb_ALPB_water":("energy_Eh","Gsolv_Eh"),
            "xtb_ALPB_octanol":("energy_Eh","Gsolv_Eh"),
            "xtb_fod":("NFOD_e","FOD_atom_e"),
            "xtb_perturbed_gradient":("energy_Eh","gradient_Eh_bohr","forces_eV_A","positions_A","elements","perturb_seed","perturb_sigma_A"),
            "xtb_hessian":("frequencies_cm_inverse","IR_km_mol","ZPE_Eh","enthalpy_Eh","thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K")}
        if task["name"] in xtb_labels:
            result["values"]={key:values[key] for key in (*xtb_labels[task["name"]],"method","version","warnings") if key in values}
        if task["name"]=="xtb_hessian" and result["values"].get("frequencies_cm_inverse") is not None:
            frequencies=result["values"]["frequencies_cm_inverse"]
            result["values"]["negative_frequency_count_raw"]=sum(x<0 for x in frequencies)
            result["values"]["imaginary_frequency_count_below_minus20"]=sum(x<-20 for x in frequencies)
        if result["status"]!="SUCCESS": result["failure_reason"]=" | ".join(result["diagnostic_lines"]) or result["failure_code"]
        files=[x for x in scratch.iterdir() if x.is_file()]
        result["raw_total_bytes"]=sum(x.stat().st_size for x in files)
        result["stdout_bytes"]=(scratch/"process.out").stat().st_size
        result["aux_bytes"]=(scratch/"input.aux").stat().st_size if (scratch/"input.aux").exists() else 0
        keep=[main]
        if task["family"]=="mopac" and main.name!="process.out" and (scratch/"process.out").stat().st_size:
            keep.append(scratch/"process.out")
        aux_selected=int(hashlib.sha256((str(CONFIG["seed"])+"|AUX|"+row["record_id"]).encode()).hexdigest()[:16],16)%10000<CONFIG["aux_sample_basis_points"]
        if aux_selected and (scratch/"input.aux").exists(): keep.append(scratch/"input.aux")
        archive=mol_dir/"partial_archives"/(key+"_"+os.environ["SLURM_JOB_ID"]+"_"+uuid.uuid4().hex[:8]+".tar.zst")
        result["archive"]=output_archive(keep,archive,key)
        result["archived_files"]=[{"name":path.name,"bytes":path.stat().st_size,"sha256":sha(path)} for path in keep]
        result["aux_archived"]=aux_selected and (scratch/"input.aux").exists()
        return result
    except Exception as exc:
        if result["status"] not in UNFINISHED and result["status"]!="TIMEOUT":
            result.update(status="RUNNER_ERROR",failure_code="INVOCATION_OR_PARSE_ERROR")
        first_error=f"{type(exc).__name__}: {exc}"
        if result.get("failure_reason") is None: result["failure_reason"]=first_error
        else: result.setdefault("secondary_errors",[]).append(first_error)
        if process is not None and process.poll() is None:
            try: result["qm_termination"]=stop_qm(process,launch_identity)
            except Exception as termination_error:
                result["qm_termination_error"]=f"{type(termination_error).__name__}: {termination_error}"
                STOP_EVENT.set()
        # Preserve available diagnostics even when numeric parsing fails.
        keep=[x for x in (scratch/"input.out",scratch/"process.out") if x.exists()]
        if keep:
            try:
                result["archive"]=output_archive(keep,mol_dir/"partial_archives"/(key+"_error_"+uuid.uuid4().hex[:8]+".tar.zst"),key)
                result["archived_files"]=[{"name":path.name,"bytes":path.stat().st_size,"sha256":sha(path)} for path in keep]
            except Exception as archive_error: result["archive_error"]=str(archive_error)
        return result
    finally:
        result.setdefault("elapsed_seconds",time.monotonic()-started)
        if process is not None and process.poll() is None:
            result["preserved_scratch"]=str(scratch)
            result["scratch_cleanup_error"]="Live or unverified QM process remains; scratch preserved"
        else:
            try: result["scratch_bytes_removed"]=cleanup_scratch(scratch)
            except Exception as exc: result["scratch_cleanup_error"]=str(exc); result["preserved_scratch"]=str(scratch)

def skipped(row,native,task,code):
    return {"record_id":row["record_id"],"molecule_id":row["molecule_id"],"conformer_id":row.get("conformer_id"),
            "split":row.get("split"),"natoms":len(native["symbols"]) if native else row.get("total_atoms"),
            "heavy_atoms":int((native["z"]>1).sum()) if native else row.get("heavy_atoms"),
            "task":task["name"],"family":task["family"],"source_payload_sha256":row["record_payload_sha256"],
            "size_stratum":row.get("size_stratum"),
            "status":code,"failure_code":code,"failure_reason":None,"values":{},"qc_codes":[],
            "elapsed_seconds":0.0,"job_id":os.environ["SLURM_JOB_ID"],"worker_pid":os.getpid()}

def row_for_parquet(value):
    values=value["values"]
    return {"record_id":value["record_id"],"molecule_id":value["molecule_id"],"conformer_id":value.get("conformer_id"),
            "split":value.get("split"),"size_stratum":value.get("size_stratum"),"natoms":value.get("natoms"),"heavy_atoms":value.get("heavy_atoms"),
            "task":value["task"],"family":value["family"],"status":value["status"],"failure_code":value.get("failure_code"),
            "failure_reason":value.get("failure_reason"),"elapsed_seconds":value["elapsed_seconds"],
            "qm_child_cpu_seconds":value.get("qm_child_cpu_seconds"),"raw_total_bytes":value.get("raw_total_bytes"),
            "aux_bytes":value.get("aux_bytes"),"archive_bytes":value.get("archive",{}).get("per_call_compressed_bytes",value.get("archive",{}).get("bytes")),
            "HOF_kcal_mol":values.get("heat_of_formation_kcal_mol"),"energy_Eh":values.get("energy_Eh"),
            "Q01_gradient_norm_kcal_mol_A":value.get("Q01_gradient_norm_kcal_mol_A"),
            "Q02_delta_HOF_kcal_mol":value.get("Q02_delta_HOF_kcal_mol"),"payload_sha256":value["source_payload_sha256"],
            "details_json":json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)}

def compact_archives(results,target):
    refs=[x["archive"] for x in results if x.get("archive")]
    if not refs: return None
    pending=target.with_name(target.name+".pending")
    with pending.open("wb") as sink:
        compressor=subprocess.Popen([CONFIG["zstd_executable"],"-T1","-3","-c"],stdin=subprocess.PIPE,stdout=sink,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=compressor.stdin,mode="w|") as final:
                for ordinal,ref in enumerate(refs):
                    path=Path(ref["path"])
                    if path.stat().st_size!=ref["bytes"] or sha(path)!=ref["sha256"]: raise ValueError("PARTIAL_ARCHIVE_CHANGED")
                    decoder=subprocess.Popen([CONFIG["zstd_executable"],"-d","-c",str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    try:
                        with tarfile.open(fileobj=decoder.stdout,mode="r|") as source:
                            for member in source:
                                if not member.isfile() or member.name.startswith("/") or ".." in Path(member.name).parts: raise ValueError("INVALID_OWNED_ARCHIVE_MEMBER")
                                stream=source.extractfile(member); member.name=f"attempt_{ordinal:05d}/"+member.name
                                final.addfile(member,stream)
                    finally:
                        decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()
                    if code: raise RuntimeError("ARCHIVE_DECOMPRESSION_FAILED:"+error.decode(errors="replace")[-500:])
        finally: compressor.stdin.close()
        error=compressor.stderr.read(); code=compressor.wait()
        if code: raise RuntimeError("ARCHIVE_COMPRESSION_FAILED:"+error.decode(errors="replace")[-500:])
        sink.flush(); os.fsync(sink.fileno())
    pending.replace(target)
    final_ref={"path":str(target),"bytes":target.stat().st_size,"sha256":sha(target)}
    offsets={ref["path"]:ordinal for ordinal,ref in enumerate(refs)}
    for result in results:
        old=result.get("archive")
        if old:
            member_key=hashlib.sha256((result["record_id"]+"|"+result["task"]).encode()).hexdigest()[:24]
            result["archive"]={**final_ref,"member_prefix":f"attempt_{offsets[old['path']]:05d}/{member_key}",
                               "per_call_compressed_bytes":old["bytes"],"retired_partial_archive_sha256":old["sha256"]}
    return final_ref

def molecule_worker(item):
    import pyarrow as pa
    import pyarrow.parquet as pq
    molecule_id,rows=item
    mol_dir=OUTPUT/"molecules"/hashlib.sha256(molecule_id.encode()).hexdigest()[:24]
    mol_dir.mkdir(parents=True,exist_ok=True)
    receipt_path=mol_dir/"receipt.json"
    identity=stable_sha([(r["record_id"],r["record_payload_sha256"]) for r in rows])
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if receipt["input_identity_sha256"]!=identity: raise ValueError("COMPLETED_MOLECULE_INPUT_DIFFERS")
        for key in ("parquet","archive"):
            ref=receipt.get(key)
            if ref and (not Path(ref["path"]).exists() or sha(ref["path"])!=ref["sha256"]): raise ValueError("COMPLETED_MOLECULE_OUTPUT_DIFFERS")
        return {**receipt,"resumed_without_QM":True,"resumed_worker_pid":os.getpid()}
    native,read_errors={},{}
    for row in rows:
        try: native[row["record_id"]]=read_native(row)
        except Exception as exc: read_errors[row["record_id"]]=f"{type(exc).__name__}: {exc}"
    marked=[r for r in rows if r.get("molecule_lowest_energy_conformer") is True]
    if len(marked)>1: raise ValueError("MULTIPLE_DECLARED_LOWEST_CONFORMERS")
    minimum=marked[0] if marked else None
    all_results=[]; interrupted=False
    for row in rows:
        state_path=mol_dir/"states"/(hashlib.sha256(row["record_id"].encode()).hexdigest()[:24]+".json")
        state=json.loads(state_path.read_text()) if state_path.exists() else {"record_id":row["record_id"],"payload_sha256":row["record_payload_sha256"],"attempts":[]}
        if state["payload_sha256"]!=row["record_payload_sha256"]: raise ValueError("CHECKPOINT_INPUT_DIFFERS")
        tasks=[*CONFIG["tasks"]]
        if minimum is not None and row["record_id"]==minimum["record_id"]: tasks.append(CONFIG["hessian_task"])
        latest={v["task"]:v for v in state["attempts"] if v["status"] not in UNFINISHED}
        b_failed=not latest.get("pm7_B",{}).get("B_base_success",False) if "pm7_B" in latest else False
        for task in tasks:
            if task["name"] in latest: continue
            if time.time()>=DEADLINE-30 or STOP_EVENT.is_set(): interrupted=True; break
            if row["record_id"] in read_errors:
                result=skipped(row,None,task,"Q03_SOURCE_READ_FAILED"); result["failure_reason"]=read_errors[row["record_id"]]
            elif b_failed: result=skipped(row,native[row["record_id"]],task,"SKIPPED_Q03")
            else: result=invoke(task,native[row["record_id"]],row,mol_dir)
            state["attempts"].append(result); save_json(state_path,state)
            if result["status"] in UNFINISHED: interrupted=True; break
            latest[task["name"]]=result
            if task["name"]=="pm7_B" and not result.get("B_base_success",False): b_failed=True
        all_results.extend(state["attempts"])
        if interrupted: break
    if interrupted:
        return {"molecule_id":molecule_id,"status":"PARTIAL_DEADLINE","results":len(all_results),"path":str(mol_dir),"resumed_without_QM":False}
    # Each requested slot has one final outcome; historical interrupted attempts stay in details/archive.
    final={}
    for value in all_results:
        if value["status"] not in UNFINISHED: final[(value["record_id"],value["task"])]=value
    for row in rows:
        record_id=row["record_id"]
        def get(name):
            outcome=final.get((record_id,name),{})
            return outcome.get("values",{}) if outcome.get("status")=="SUCCESS" or (name=="pm7_B" and outcome.get("B_base_success")) else {}
        neutral,plus,minus=get("pm7_B"),get("pm7_cation"),get("pm7_anion")
        derived={}
        if neutral.get("heat_of_formation_kcal_mol") is not None:
            e0=neutral["heat_of_formation_kcal_mol"]
            if plus.get("heat_of_formation_kcal_mol") is not None: derived["vertical_IP_eV"]=(plus["heat_of_formation_kcal_mol"]-e0)/23.060548867
            if minus.get("heat_of_formation_kcal_mol") is not None: derived["vertical_EA_eV"]=(e0-minus["heat_of_formation_kcal_mol"])/23.060548867
            for name in ("pm7_water","pm7_octanol"):
                solvent=get(name).get("heat_of_formation_kcal_mol")
                if solvent is not None: derived[name+"_HOF_difference_kcal_mol"]=solvent-e0
        q0,qp,qm=neutral.get("net_charges_e"),plus.get("net_charges_e"),minus.get("net_charges_e")
        if q0 and qp and qm and len(q0)==len(qp)==len(qm):
            derived["fukui_Coulson"]={"plus":[a-b for a,b in zip(q0,qm)],"minus":[b-a for a,b in zip(q0,qp)],"radical":[(b-c)/2 for b,c in zip(qp,qm)]}
        if (record_id,"pm7_B") in final: final[(record_id,"pm7_B")]["values"]["derived_from_same_geometry_charged_states"]=derived
    archive=compact_archives(all_results,mol_dir/"raw_outputs.tar.zst")
    parquet=mol_dir/"results.parquet"; pending=parquet.with_suffix(".parquet.pending")
    pq.write_table(pa.Table.from_pylist([row_for_parquet(v) for v in final.values()],schema=parquet_schema(pa)),pending,compression="zstd")
    with pending.open("rb") as stream: os.fsync(stream.fileno())
    pending.replace(parquet)
    from collections import Counter
    receipt={"molecule_id":molecule_id,"status":"COMPLETE_WITH_RECORDED_OUTCOMES","input_identity_sha256":identity,
             "records":len(rows),"requested_outcomes":len(final),"statuses":dict(Counter(v["status"] for v in final.values())),
             "minimum_original_energy_record_id":minimum["record_id"] if minimum else None,"source_read_failures":read_errors,
             "hessian_scope":"LOWEST_ORIGINAL_ENERGY_CONFORMER" if minimum else "SKIPPED_MISSING_ORIGINAL_MINIMUM_ENERGY",
             "parquet":{"path":str(parquet),"bytes":parquet.stat().st_size,"sha256":sha(parquet)},
             "archive":archive,"total_qm_attempts":sum(v.get("argv") is not None for v in all_results),
             "qm_child_cpu_seconds":sum(v.get("qm_child_cpu_seconds",0) for v in all_results),"worker_pid":os.getpid(),
             "job_id":os.environ["SLURM_JOB_ID"],"resumed_without_QM":False}
    save_json(receipt_path,receipt)
    # Only this completed molecule's redundant per-call archives/states are removed.
    for folder in (mol_dir/"partial_archives",mol_dir/"states"):
        if folder.exists():
            for path in folder.iterdir():
                if path.lstat().st_uid!=os.getuid() or not path.is_file() or path.is_symlink(): raise RuntimeError("NONOWNED_CHECKPOINT_CLEANUP")
                path.unlink()
            folder.rmdir()
    return receipt

def parquet_schema(pa):
    string_cols=("record_id","molecule_id","split","size_stratum","task","family","status","failure_code","failure_reason","payload_sha256","details_json")
    integer_cols=("conformer_id","natoms","heavy_atoms","raw_total_bytes","aux_bytes","archive_bytes")
    float_cols=("elapsed_seconds","qm_child_cpu_seconds","HOF_kcal_mol","energy_Eh","Q01_gradient_norm_kcal_mol_A","Q02_delta_HOF_kcal_mol")
    return pa.schema([(x,pa.string()) for x in string_cols]+[(x,pa.int64()) for x in integer_cols]+[(x,pa.float64()) for x in float_cols])

def load_panel(panel,index,workers):
    import pyarrow.parquet as pq
    import pyarrow as pa
    import duckdb
    pa.set_cpu_count(workers); pa.set_io_thread_count(min(8,workers))
    rows=pq.read_table(panel).to_pylist()
    required=("record_id","molecule_id","shard_id","real_index","record_payload_sha256","retained","retained_conformer_count",
              "molecule_lowest_energy_conformer","size_stratum")
    if not rows or any(any(key not in row for key in required) for row in rows): raise ValueError("WP1_PANEL_REQUIRED_COLUMNS_MISSING")
    if any(row["retained"] is not True for row in rows): raise ValueError("WP1_PANEL_HAS_UNASSESSED_OR_EXCLUDED_RECORD")
    if len({r["record_id"] for r in rows})!=len(rows): raise ValueError("DUPLICATE_PANEL_RECORD")
    selected=sorted({r["molecule_id"] for r in rows})
    db=duckdb.connect(); db.execute(f"SET threads={workers}")
    db.register("selected_molecules",pa.table({"molecule_id":selected}))
    original=db.execute("SELECT i.record_id,i.molecule_id,i.record_payload_sha256 FROM read_parquet(?) i JOIN selected_molecules s USING(molecule_id)",[str(index)]).fetchall()
    db.close()
    expected={(str(record),str(molecule),str(payload)) for record,molecule,payload in original}
    actual={(r["record_id"],r["molecule_id"],r["record_payload_sha256"]) for r in rows}
    if not actual.issubset(expected): raise ValueError(f"PANEL_SOURCE_RECORD_OR_SHA_NOT_IN_INDEX: extra={len(actual-expected)}")
    from collections import defaultdict
    groups=defaultdict(list)
    for row in rows: groups[row["molecule_id"]].append(row)
    for molecule,records in groups.items():
        if any(int(r["retained_conformer_count"])!=len(records) for r in records):
            raise ValueError("PANEL_MISSING_RETAINED_CONFORMERS:"+molecule)
        known=[r for r in records if r.get("energy_raw") is not None and math.isfinite(float(r["energy_raw"]))]
        marked=[r for r in records if r["molecule_lowest_energy_conformer"] is True]
        if known:
            minimum=min(known,key=lambda r:(float(r["energy_raw"]),r.get("conformer_id") or 0,r["record_id"]))
            if len(marked)!=1 or marked[0]["record_id"]!=minimum["record_id"]: raise ValueError("LOWEST_CONFORMER_MARKER_INVALID:"+molecule)
        elif marked: raise ValueError("UNKNOWN_ENERGY_CANNOT_DECLARE_MINIMUM:"+molecule)
    return [(key,sorted(value,key=lambda r:(r.get("conformer_id") or 0,r["record_id"]))) for key,value in groups.items()]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel"); p.add_argument("--panel-manifest"); p.add_argument("--record-index"); p.add_argument("--output")
    p.add_argument("--config",default=str(HERE/"wp4_native_v2_config.json"))
    p.add_argument("--source-plan",default=str(DEFAULT_PLAN)); p.add_argument("--workers",type=int,default=16)
    p.add_argument("--wall-seconds",type=float,default=72000); p.add_argument("--resume",action="store_true")
    p.add_argument("--max-molecules",type=int); p.add_argument("--bucket-count",type=int,default=1); p.add_argument("--bucket",type=int,default=0)
    p.add_argument("--check",action="store_true"); args=p.parse_args()
    config=json.loads(Path(args.config).read_text())
    for reference in config["mulliken_official_references"].values():
        if sha(reference["path"])!=reference["sha256"]: raise ValueError("MULLIKEN_OFFICIAL_SOURCE_BINDING_DIFFERS")
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text()); ast.parse((HERE/"wp4_parsers.py").read_text())
        getter_path=HERE/"wp4_mulliken_pairs_v2.py"; ast.parse(getter_path.read_text())
        spec=importlib.util.spec_from_file_location("static_mulliken_check",getter_path)
        getter=importlib.util.module_from_spec(spec); spec.loader.exec_module(getter)
        parameter_check=getter.validate_official_parameters(config["mulliken_official_references"]["parameters"]["path"])
        assert set(parameter_check["elements"])=={"H","B","C","N","O","F","Si","P","S","Cl","Se","Br","I"}
        assert "mulliken_overlap_population_pairs" in config["tasks"][0]["required_values"]
        for reference in config["mulliken_official_references"].values():
            assert sha(reference["path"])==reference["sha256"]
        assert len(config["tasks"])==13 and len({t["name"] for t in config["tasks"]})==13
        assert all("1SCF" in t["keywords"] and "OPT " not in t["keywords"] for t in config["tasks"] if t["family"]=="mopac")
        print(json.dumps({"status":"AST_AND_NATIVE_CONFIG_PASS","native_calculation_started":False,"LMDB_opened":False})); return 0
    if not all((args.panel,args.record_index,args.output)): p.error("--panel, --record-index and --output required")
    if args.wall_seconds<=150 or (args.max_molecules is not None and args.max_molecules<1):
        p.error("Positive molecule limit and wall-seconds>150 required")
    allocated=int(os.environ.get("SLURM_CPUS_PER_TASK","0"))
    if not os.environ.get("SLURM_JOB_ID") or not 16<=args.workers<=allocated: raise ValueError("REQUIRES_SLURM_16_EFFECTIVE_CPUS")
    if not 0<=args.bucket<args.bucket_count: raise ValueError("INVALID_MOLECULE_BUCKET")
    os.environ.update(THREAD_ENV); os.environ["CUDA_VISIBLE_DEVICES"]=""
    scratch=Path(config["scratch_base"]).absolute()
    if str(scratch).startswith(("/share/","/home/")) or not scratch.is_dir(): raise ValueError("NODE_LOCAL_SCRATCH_REQUIRED")
    config["zstd_executable"]=shutil.which(config["zstd_executable"]) or config["zstd_executable"]
    for name in ("mopac_executable","xtb_executable","zstd_executable"):
        if not Path(config[name]).is_file() or not os.access(config[name],os.X_OK): raise ValueError("EXECUTABLE_UNAVAILABLE:"+config[name])
    output=Path(args.output).absolute()
    owned_root=PROJECT/"runs/phase1_dataset_rebuild_20261010"
    if not output.is_relative_to(owned_root) or output==owned_root:
        raise ValueError("USE_NEW_PILOT_OUTPUT_DIRECTORY_INSIDE_THIS_PHASE_ROOT")
    output.mkdir(parents=True,exist_ok=True)
    plan=json.loads(Path(args.source_plan).read_text()); sources=plan["sources"]
    if len(sources)!=11: raise ValueError("EXPECTED_ORIGINAL_ELEVEN_LMDB_SOURCES")
    panel_sha=sha(args.panel); source_sha=sha(__file__); parser_sha=sha(HERE/"wp4_parsers.py")
    binding={"panel_sha256":panel_sha,"record_index_path":str(Path(args.record_index).absolute()),
             "record_index_bytes":Path(args.record_index).stat().st_size,"source_plan_sha256":sha(args.source_plan),
             "runner_sha256":source_sha,"parser_sha256":parser_sha,"config_sha256":sha(args.config),
             "mulliken_getter_sha256":sha(HERE/"wp4_mulliken_pairs_v2.py"),
             "mulliken_official_references":config["mulliken_official_references"],
             "bucket_count":args.bucket_count,"bucket":args.bucket,"max_molecules":args.max_molecules}
    if args.panel_manifest: binding["panel_manifest_sha256"]=sha(args.panel_manifest)
    metadata_path=output/"metadata.json"
    if metadata_path.exists():
        metadata=json.loads(metadata_path.read_text())
        if not args.resume or metadata["input_and_implementation_binding"]!=binding: raise ValueError("RESUME_BINDING_DIFFERS_OR_NOT_REQUESTED")
    else:
        snapshot=output/"source_snapshot"; snapshot.mkdir()
        for src,name in ((Path(__file__),"wp4_native_pilot_v2.py"),(HERE/"wp4_parsers.py","wp4_parsers.py"),
                         (HERE/"wp4_mulliken_pairs_v2.py","wp4_mulliken_pairs_v2.py"),(Path(args.config),"config.json")):
            shutil.copyfile(src,snapshot/name)
        metadata={"scope":"WP4_NATIVE_RETAINED_PANEL_ANALYSIS_ONLY_NO_LMDB_WRITES","seed":config["seed"],
                  "input_and_implementation_binding":binding,"config":config,"source_lmdb_paths":[x["path"] for x in sources],
                  "python_logical_entry":sys.executable,"packages":{name:package_version(name) for name in ("numpy","pyarrow","torch","rdkit","lmdb","duckdb")},
                  "software":{"mopac_expected":"23.0.3","xtb_expected":"6.7.1","executables":{name:{"path":config[name],"sha256":sha(config[name])} for name in ("mopac_executable","xtb_executable","zstd_executable")}},
                  "mulliken_pair_method":config["mulliken_pair_method"],"coverage_cost_notes":config["coverage_cost_notes"],
                  "units":config["units"],"pair_storage":"Native graph edges plus native-distance cutoff; no full atom NxN labels stored.",
                  "panel_manifest":json.loads(Path(args.panel_manifest).read_text()) if args.panel_manifest else None,
                  "lmdb_options":{"readonly":True,"lock":False,"create":False},"coordinates":"Raw pos Angstrom; no optimization; only separate noise task uses changed coordinates."}
        save_json(metadata_path,metadata)
    molecules=load_panel(args.panel,args.record_index,args.workers)
    molecules=sorted((item for item in molecules if int(hashlib.sha256(item[0].encode()).hexdigest()[:16],16)%args.bucket_count==args.bucket),
                     key=lambda item:hashlib.sha256((str(config["seed"])+"|"+item[0]).encode()).hexdigest())
    if args.max_molecules: molecules=molecules[:args.max_molecules]
    deadline=time.time()+args.wall_seconds-120
    if os.environ.get("SLURM_JOB_END_TIME"): deadline=min(deadline,float(os.environ["SLURM_JOB_END_TIME"])-120)
    stop=False; spawn_context=multiprocessing.get_context("spawn"); stop_event=spawn_context.Event()
    def stopping(signum,frame):
        nonlocal stop
        stop=True; stop_event.set()
    signal.signal(signal.SIGTERM,stopping); signal.signal(signal.SIGINT,stopping)
    started=time.monotonic(); receipts=[]; failures=[]; iterator=iter(molecules)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=spawn_context,
            initializer=initialize,initargs=(sources,config,str(output),str(output/"source_snapshot"/"wp4_parsers.py"),deadline,stop_event)) as pool:
        pending={}
        def fill():
            while not stop and not stop_event.is_set() and time.time()<deadline-30 and len(pending)<args.workers:
                try: item=next(iterator)
                except StopIteration: break
                pending[pool.submit(molecule_worker,item)]=item[0]
        fill()
        while pending:
            done,_=concurrent.futures.wait(pending,timeout=10,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                molecule_id=pending.pop(future)
                try: receipts.append(future.result())
                except Exception as exc: failures.append({"molecule_id":molecule_id,"error":f"{type(exc).__name__}: {exc}"})
            if done:
                save_json(output/"progress.json",{"job_id":os.environ["SLURM_JOB_ID"],"hostname":socket.gethostname(),
                    "planned_molecules":len(molecules),"closed_or_partial_molecules":len(receipts),"worker_failures":failures,
                    "elapsed_seconds":time.monotonic()-started,"active_workers":len(pending)})
            fill()
    complete=[r for r in receipts if r["status"]=="COMPLETE_WITH_RECORDED_OUTCOMES"]
    summary={"status":"NATIVE_PANEL_ATTEMPT_COMPLETE" if len(complete)==len(molecules) and not failures else "PARTIAL_RESUMABLE",
             "job_id":os.environ["SLURM_JOB_ID"],"seed":config["seed"],"planned_molecules":len(molecules),
             "planned_records":sum(len(rows) for _,rows in molecules),"completed_molecules":len(complete),
             "receipts":receipts,"failures":failures,"elapsed_seconds":time.monotonic()-started,
             "actual_worker_pids":sorted({r.get("resumed_worker_pid",r["worker_pid"]) for r in complete if r.get("worker_pid")}),
             "output_bytes":sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
             "pilot_report_complete":False,"LMDB_written":False}
    save_json(output/("job_"+os.environ["SLURM_JOB_ID"]+"_summary.json"),summary)
    print(json.dumps({key:summary[key] for key in ("status","job_id","planned_records","completed_molecules","pilot_report_complete")}),flush=True)
    return 2 if failures else 0

if __name__=="__main__": raise SystemExit(main())
