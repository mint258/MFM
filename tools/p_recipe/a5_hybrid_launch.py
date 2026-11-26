"""Launch the two registered A5 frozen readouts with native SSH and same-task standby."""
import argparse,base64,copy,importlib.util,json,shlex,subprocess,sys,time
from pathlib import Path
R=Path("/share/home/zixiao/descriptor_analysis");Q=R/"MFM_p_recipe";C=R/"runs/p_recipe_20261113/fixed_20261115";D=C/"A5_GPU_20261126"
sys.path[:0]=[str(Q/"tools"),str(Q/"tools/p_recipe")]
from execution_ledger import read,write,locked_ledger
from resident_bootstrap import render_sbatch
import shared_guard
OLD="/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python"
NEW=str(R/"docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python")
DEPLOY="import csv,fcntl,json,os,subprocess,sys,time\nfrom pathlib import Path\np=json.load(sys.stdin);c=p[\"runtime\"];node=os.uname().nodename.split(\".\")[0]\nif os.getuid()!=1278 or node!=c[\"node\"] or node not in {\"compute-0-20\",\"compute-0-22\"}:raise RuntimeError(\"Actual authorized native GPU host required\")\nnative=subprocess.run([\"/usr/bin/scontrol\",\"show\",\"node\",node,\"-o\"],capture_output=True,text=True,check=True,timeout=10).stdout\nstate=dict(x.split(\"=\",1) for x in native.split() if \"=\" in x)[\"State\"]\nif any(x in state for x in (\"DRAIN\",\"DOWN\",\"NOT_RESPOND\",\"FAIL\",\"UNKNOWN\")):raise RuntimeError(\"Unhealthy actual node\")\nsys.path.insert(0,p[\"repo\"]+\"/tools\");import shared_guard\nclaim=json.loads((shared_guard.REGISTRY/\"p-recipe.json\").read_text());entries=claim[\"entries\"]\nram=sum(x[\"bytes\"] for x in entries if x[\"kind\"]==\"node_ram\" and x.get(\"node\")==node)\ndisk=sum(x[\"bytes\"] for x in entries if x[\"kind\"]==\"node_disk\" and x.get(\"node\")==node)\nfuture=sum(x[\"bytes\"] for x in entries if x[\"kind\"]==\"shared_fs\" and x.get(\"path\")==\"/share\")\nguards=[shared_guard.check_with_timeout(\"p-recipe\",\"node_ram\",ram,node=node),shared_guard.check_with_timeout(\"p-recipe\",\"node_disk\",disk,path=\"/tmp\",node=node),shared_guard.check_with_timeout(\"p-recipe\",\"shared_fs\",future,path=\"/share\")]\nraw=subprocess.run([\"/usr/bin/nvidia-smi\",\"--id=\"+c[\"gpu_uuid\"],\"--query-gpu=uuid,memory.used,memory.total\",\"--format=csv,noheader,nounits\"],capture_output=True,text=True,check=True,timeout=10).stdout\nrow=next(csv.reader(raw.splitlines()));used,total=float(row[1]),float(row[2])\nif row[0].strip()!=c[\"gpu_uuid\"] or total<24000 or used/total>.30 or total-used<22000:raise RuntimeError(\"Fresh GPU memory admission failed\")\nlock=Path(p[\"repo\"]).parent/\"docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks\"/(c[\"gpu_uuid\"]+\".lock\")\nwith lock.open(\"a\") as stream:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)\ndef snap():\n d={}\n for line in Path(\"/proc/stat\").read_text().splitlines():\n  f=line.split()\n  if f and f[0].startswith(\"cpu\") and f[0][3:].isdigit():\n   v=list(map(int,f[1:9]));d[int(f[0][3:])]=(sum(v),v[3])\n return d\na=snap();time.sleep(5);b=snap();idle={k:(b[k][1]-a[k][1])/max(1,b[k][0]-a[k][0]) for k in a}\nc[\"cores\"]=[k for k,v in sorted(idle.items(),key=lambda x:(-x[1],-x[0]))[:16]]\nbase=Path(\"/tmp/P_A5_GPU_20261126\");base.mkdir(exist_ok=True)\nresident=base/\"resident_v2.py\"\nif resident.exists() and resident.read_text()!=p[\"resident\"]:raise RuntimeError(\"Do not overwrite a running/frozen GPU resident\")\nif not resident.exists():resident.write_text(p[\"resident\"])\nlocal=base/(p[\"key\"]+\".json\")\nif local.exists():raise RuntimeError(\"Original GPU attempt exists; observe its handle\")\nlocal.write_text(json.dumps(c));log=base/(p[\"key\"]+\".log\");timing=base/(p[\"key\"]+\".time.txt\")\nenv=os.environ.copy()\nfor key in list(env):\n if key.startswith(\"SLURM_\"):env.pop(key)\nenv.update(OMP_NUM_THREADS=\"16\",MKL_NUM_THREADS=\"16\",OPENBLAS_NUM_THREADS=\"16\",CUDA_VISIBLE_DEVICES=c[\"gpu_uuid\"],\n PYTHONPATH=p[\"repo\"]+\"/tools:\"+p[\"repo\"]+\"/tools/p_recipe:\"+p[\"repo\"]+\"/current\")\ncommand=[\"/usr/bin/setsid\",\"/usr/bin/nohup\",\"/usr/bin/taskset\",\"-c\",\",\".join(map(str,c[\"cores\"])),\n \"/usr/bin/timeout\",\"--signal=TERM\",\"7200\",\"/usr/bin/time\",\"-v\",\"-o\",str(timing),\"/usr/bin/python3\",\"-B\",str(resident),\"--configuration\",str(local)]\nwith log.open(\"x\") as out:\n child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,env=env,close_fds=True)\nraw=Path(\"/proc/%d/stat\"%child.pid).read_text();fields=raw[raw.rfind(\")\")+2:].split()\nprint(json.dumps(dict(execution_id=c[\"execution_id\"],node=node,gpu_uuid=c[\"gpu_uuid\"],cores=c[\"cores\"],\n launcher_pid=child.pid,launcher_start_ticks=int(fields[19]),launch_at=time.time(),runtime_receipt=c[\"receipt\"],\n local_log=str(log),local_time_report=str(timing),command=command,guards=guards,initial_used_mib=used,total_mib=total)),flush=True)\n"
PATH=C/"A5_GPU_submission_20261126.json"
def renewal():
 spec=importlib.util.spec_from_file_location("P_claim_observer",C/"confirmation_slurm_claim_monitor_20261122.py")
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.refresh_own_claims()
def guard():
 claim=read(shared_guard.REGISTRY/"p-recipe.json")
 future=sum(x["bytes"] for x in claim["entries"] if x["kind"]=="shared_fs" and x.get("path")=="/share")
 return shared_guard.check_with_timeout("p-recipe","shared_fs",future,path="/share")
def resident():
 life=base64.b64encode((Q/"tools/p_recipe/exit_lifecycle.py").read_bytes()).decode()
 runtime=base64.b64encode((Q/"tools/p_recipe/gpu_ssh_runtime.py").read_bytes()).decode()
 return ("import base64,sys,types\nm=types.ModuleType('exit_lifecycle');sys.modules[m.__name__]=m\n"
  +"exec(compile(base64.b64decode("+repr(life)+"),'<resident-exit>','exec'),m.__dict__)\n"
  +"r=types.ModuleType('gpu_ssh_runtime');sys.modules[r.__name__]=r\n"
  +"exec(compile(base64.b64decode("+repr(runtime)+"),'<resident-A5-SSH>','exec'),r.__dict__)\nraise SystemExit(r.main())\n")
def prepare():
 assert not PATH.exists();guard();D.mkdir(exist_ok=True)
 observation=read(C/"CPU_SSH_20261126/latest_observation.json")
 assert next(x for x in observation["rows"] if x["key"]=="A5_shared_UFF_cohort_attempt2")["state"]=="CLOSED_SUCCESS"
 assert next(x for x in observation["rows"] if x["key"]=="A5_handoff_control_tests")["state"]=="CLOSED_SUCCESS"
 complete=read(C/"A5_20261125/cohort/primary_complete.json")
 assert complete["status"]=="COMPLETE" and complete["accepted_members"]==5106
 scopepath=C/"p_recipe_shared_claim_scope_20261122.json";scope=read(scopepath)
 write(C/"A5_GPU_scope_before_20261126.json",scope)
 choices=[("T2_9M","compute-0-22","GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef",NEW,"RTX5090_32GiB"),
          ("T4_9M","compute-0-20","GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5",OLD,"RTX4090_48GiB")]
 jobs=[]
 for label,node,uuid,python,hardware in choices:
  ids=["P_A5_"+label+"_RAM","P_A5_"+label+"_tmp","P_A5_"+label+"_NFS"]
  for entry in [dict(id=ids[0],kind="node_ram",node=node,bytes=32*2**30),
                dict(id=ids[1],kind="node_disk",node=node,path="/tmp",bytes=64*2**20),
                dict(id=ids[2],kind="shared_fs",path="/share",bytes=2*2**30)]:
   assert all(x["id"]!=entry["id"] for x in scope["fixed_entries"]);scope["fixed_entries"].append(entry)
  draft=Q/("configs/p_recipe/fixed_20261115/analysis_20261122/A5_"+label+"_readout_20261125_draft.json")
  c=read(draft);target=draft.with_name("A5_"+label+"_readout_20261126_managed.json")
  handle="ssh:P_A5_UFF_"+label+"_20261126";receipt=D/(label+"_SSH_runtime.json")
  c.update(ready=True,node=node,gpu_uuid=uuid,reservation_ids=ids,execution_backend="ssh_gpu",
   ssh_execution_id=handle,ssh_runtime_receipt=str(receipt),scheduling_authority="docs/interfaces/SCHEDULING_RULE_20261126.md",
   handoff_requires_worker_ready=True,
   source_validation="Actual closed CPU SSH producer5106 and two contract PASS; actual closed real-process handoff tests",
   resource_note="Nov26 routing to available cards with at least24GiB, same B32/FP32/frozen protocol",actual_card=hardware)
  assert not target.exists();write(target,c)
  environment=dict(OMP_NUM_THREADS="16",MKL_NUM_THREADS="16",OPENBLAS_NUM_THREADS="16",CUDA_VISIBLE_DEVICES=uuid,
   PYTHONPATH=str(Q/"tools")+":"+str(Q/"tools/p_recipe")+":"+str(Q/"current"),
   CUDA_CACHE_PATH=c["output"]+"/cuda_cache",TORCH_EXTENSIONS_DIR=c["output"]+"/torch_extensions")
  script=C/("P_A5_"+label+"_standby_20261126.sbatch")
  directives=["#SBATCH --job-name=P_A5_"+label+"_standby","#SBATCH --partition=gpu","#SBATCH --nodelist="+node,
   "#SBATCH --nodes=1","#SBATCH --ntasks=1","#SBATCH --cpus-per-task=16","#SBATCH --mem=32G",
   "#SBATCH --time=02:00:00","#SBATCH --signal=B:USR1@180","#SBATCH --chdir=/","#SBATCH --export=NONE",
   "#SBATCH --output=/tmp/P_A5_"+label+"_standby_%j.log","#SBATCH --error=/tmp/P_A5_"+label+"_standby_%j.log"]
  assert not script.exists()
  script.write_text(render_sbatch([python,"-B",str(Q/"tools/p_recipe/a5_takeover_entry.py"),"--configuration",str(target)],
   (Q/"tools/p_recipe/exit_lifecycle.py").read_text(),directives=directives,child_environment=environment,
   allowed_nodes=[node],cleanup_seconds=180,root_future_bytes=64*2**20,cooperative=True))
  jobs.append(dict(label=label,node=node,gpu_uuid=uuid,configuration=str(target),python=python,execution_id=handle,
   runtime_receipt=str(receipt),script=str(script),state="READY_NATIVE_AND_SAME_TASK_STANDBY",environment=environment))
 write(scopepath,scope);renewal();actual_guard=guard()
 value=dict(schema="P_A5_GPU_HYBRID_20261126_V1",status="READY",authority="docs/interfaces/SCHEDULING_RULE_20261126.md",
  jobs=jobs,common_cohort=complete,guard=actual_guard,science_unchanged=True)
 write(PATH,value);print(json.dumps(dict(status=value["status"],jobs=[dict(label=x["label"],node=x["node"],gpu_uuid=x["gpu_uuid"]) for x in jobs],guard=actual_guard)),flush=True)
def start():
 v=read(PATH);assert v["status"] in ("READY","NATIVE_SOURCES_LAUNCHED","BOTH_NATIVE_WITH_SAME_TASK_SLURM_STANDBY")
 for row in v["jobs"]:
  if row.get("native_launch") or row.get("state")=="WAIT_ACTUAL_RAM_CAPACITY":continue
  if row.get("native_launch_intent"):raise RuntimeError("Unreconciled original native launch; observe it, do not restart")
  c=read(row["configuration"]);guard()
  root=dict(node=row["node"],gpu_uuid=row["gpu_uuid"],execution_id=row["execution_id"],receipt=row["runtime_receipt"],
   output=c["output"],worker_argv=[row["python"],"-B",str(Q/"tools/p_recipe/a5_readout_entry.py"),"--configuration",row["configuration"]],
   ram_peak_bytes=c["ram_peak_bytes"],root_future_bytes=64*2**20,cleanup_seconds=180,expected_seconds=3600,timeout_seconds=7200)
  row["native_launch_intent"]=dict(at=time.time(),execution_id=row["execution_id"]);write(PATH,v)
  result=subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=8",row["node"],
   "/usr/bin/timeout --signal=TERM 90 /usr/bin/python3 -B -c "+shlex.quote(DEPLOY)],
   input=json.dumps(dict(repo=str(Q),key=row.get("launch_key",row["label"]),runtime=root,resident=resident())),text=True,capture_output=True)
  if result.returncode:
   write(D/(row["label"]+"_launch_control_failure_"+str(time.time_ns())+".json"),dict(at=time.time(),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,no_restart_on_observation_failure=True))
   raise RuntimeError(result.stderr[-1200:]+result.stdout[-600:])
  row["native_launch"]=json.loads(next(x for x in result.stdout.splitlines() if x.startswith("{")))
  v["status"]="NATIVE_SOURCES_LAUNCHED";write(PATH,v)
  with locked_ledger() as ledger:
   ledger.setdefault("runs",{})["A5_UFF_"+row["label"]+"_20261126"]=dict(backend="SSH_GPU",state="STARTING",job_id=None,
    execution_id=row["execution_id"],node=row["node"],gpu_uuid=row["gpu_uuid"],configuration=row["configuration"],
    runtime_receipt=row["runtime_receipt"],actual_launch=row["native_launch"],stage="A5_registered_frozen_readout",prior_native_attempts=row.get("prior_native_attempts",[]))
  print(json.dumps(dict(label=row["label"],native=row["native_launch"])),flush=True)
  ensure_standby(v,row)
 print(json.dumps(dict(status=v["status"],next="Observe actual native root before releasing same-task standby")),flush=True)
def ensure_standby(v,row):
 if row.get("standby_job") or not row.get("native_launch"):return
 # Register immediately in the native-launch transaction, before another source.
 until=time.monotonic()+30
 while not Path(row["runtime_receipt"]).exists():
  if time.monotonic()>=until:raise RuntimeError("Source receipt unavailable; observe original handle, never duplicate")
  time.sleep(.2)
 receipt=read(row["runtime_receipt"])
 assert receipt["execution_id"]==row["execution_id"]
 if receipt["status"]=="COMPLETE":
  assert receipt["returncode"]==0 and receipt["owned_tree_reaped"] and not receipt["remaining_children"]
  row["standby_state"]="SOURCE_ALREADY_COMPLETE_NO_NEW_JOB";write(PATH,v);return
 if receipt["status"]!="RUNNING":raise RuntimeError("Original source requires actual outcome reconciliation")
 job=int(subprocess.run(["sbatch","--hold","--parsable",row["script"]],capture_output=True,text=True,check=True,timeout=15).stdout.strip().split(";")[0])
 row["standby_job"]=job;row["standby_state"]="HELD_REGISTERING_SAME_TASK";write(PATH,v)
 with locked_ledger() as ledger:
  ledger.setdefault("reservations",{})["A5_UFF_"+row["label"]+"_standby_20261126"]=dict(backend="Slurm",job_id=str(job),
   state="SUBMITTED",node=row["node"],gpu_uuid=row["gpu_uuid"],source_SSH=row["execution_id"],configuration=row["configuration"],
   role="SAME_TASK_CHECKPOINT_TAKEOVER_NO_DOUBLE_RUN",submitted_at=time.time())
 subprocess.run(["scontrol","release",str(job)],capture_output=True,text=True,check=True,timeout=15)
 row["standby_state"]="RELEASED_SAME_TASK_TAKEOVER";write(PATH,v)
 print(json.dumps(dict(label=row["label"],native=row["execution_id"],same_task_standby_job=job)),flush=True)

def standby():
 v=read(PATH)
 for row in v["jobs"]:ensure_standby(v,row)
 v["standby_registration_checked_at"]=time.time();write(PATH,v)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("action",choices=["prepare","start","standby"]);a=p.parse_args()
 {"prepare":prepare,"start":start,"standby":standby}[a.action]()
