"""Launch the immutable exact200 plan; bootstrap only its private metadata queue."""
from __future__ import annotations
import argparse,ast,importlib.util,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from wp5_acceptance_catalog_v2 import ROOT,sha,require_slurm
FORMAL_QUEUE=ROOT/"queue/pending.sqlite"
RUNNER14_SHA="7d4aa3932be408ff051003446ae7f3fd1eab7b7bdb386d67a41eadb18e3af740"

def private_queue_path(plan_path,plan):
    directory=Path(plan_path).resolve().parent
    acceptance=(ROOT/"acceptance").resolve()
    if not directory.is_relative_to(acceptance) or directory==acceptance:
        raise ValueError("FINAL200_PLAN_PRIVATE_ACCEPTANCE_DIRECTORY_REQUIRED")
    command=plan["command"]
    if command.count("--queue")!=1:raise ValueError("EXACT_ONE_PRIVATE_QUEUE_ARGUMENT_REQUIRED")
    index=command.index("--queue")
    if index+1>=len(command):raise ValueError("PRIVATE_QUEUE_ARGUMENT_MISSING")
    path=Path(command[index+1])
    if path.is_symlink() or path.resolve()==FORMAL_QUEUE.resolve():
        raise ValueError("PRODUCTION_QUEUE_BOOTSTRAP_FORBIDDEN")
    if not path.is_absolute() or path.resolve()!=directory/"queue.sqlite":
        raise ValueError("PLAN_LOCAL_PRIVATE_QUEUE_REQUIRED")
    return path

def bound_runner14(plan):
    path=Path(plan["runner"])
    if path.name!="wp5_runner_v14.py" or plan["runner_sha256"]!=RUNNER14_SHA or sha(path)!=RUNNER14_SHA:
        raise ValueError("EXACT_FROZEN_RUNNER14_REQUIRED")
    name="wp5_acceptance_launch4_bound_runner14"
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def bootstrap_private_queue(plan_path,plan):
    path=private_queue_path(plan_path,plan)
    runner=bound_runner14(plan)
    result=runner.bootstrap_metadata(path,deadline=time.monotonic()+120)
    if result.get("status")!="SCHEMA_READY_READ_ONLY" or result.get("bootstrap_explicit") is not True:
        raise ValueError("PRIVATE_QUEUE_SCHEMA_BOOTSTRAP_NOT_VERIFIED")
    evidence={"schema":"WP5_FINAL200_PRIVATE_QUEUE_BOOTSTRAP_V1","status":"PRIVATE_SCHEMA_READY",
              "plan":{"path":str(plan_path),"sha256":sha(plan_path)},
              "runner":{"path":plan["runner"],"sha256":RUNNER14_SHA},"queue":str(path),
              "result":result,"production_queue_opened":False,"production_queue_written":False,"QM_started":False}
    target=path.parent/("queue_bootstrap_"+str(os.environ.get("SLURM_JOB_ID",os.getpid()))+".json")
    with target.open("x") as stream:json.dump(evidence,stream,indent=2,allow_nan=False);stream.write("\n")
    return evidence

def private_fixture():
    global ROOT
    original_root=ROOT
    runner=original_root/"scripts/wp5_runner_v14.py"
    with tempfile.TemporaryDirectory(prefix="wp5_acceptance_launch4_",dir="/tmp") as temporary:
        try:
            ROOT=Path(temporary)
            directory=ROOT/"acceptance/plan";directory.mkdir(parents=True)
            plan_path=directory/"recompute_plan.json"
            plan={"runner":str(runner),"runner_sha256":RUNNER14_SHA,
                  "command":["python",str(runner),"--queue",str(directory/"queue.sqlite")]}
            plan_path.write_text(json.dumps(plan))
            result=bootstrap_private_queue(plan_path,plan)
            assert result["status"]=="PRIVATE_SCHEMA_READY"
            module=sys.modules["wp5_acceptance_launch4_bound_runner14"]
            queue=module.Queue(directory/"queue.sqlite",deadline=time.monotonic()+30)
            try:
                ready=module.queue_schema_ready(queue.db)
                assert ready["status"]=="SCHEMA_READY_READ_ONLY" and len(ready["tables"])==5
                assert queue.db.execute("SELECT count(*) FROM molecules").fetchone()[0]==0
            finally:queue.db.close()
            forbidden={**plan,"command":["python",str(runner),"--queue",str(FORMAL_QUEUE)]}
            try:private_queue_path(plan_path,forbidden);raise AssertionError("Production queue accepted")
            except ValueError as exc:assert str(exc)=="PRODUCTION_QUEUE_BOOTSTRAP_FORBIDDEN"
        finally:ROOT=original_root
    print(json.dumps({"status":"FINAL200_PRIVATE_BOOTSTRAP_FIXTURE_PASS","schema_ready":True,
                      "production_queue_rejected_before_open":True,"fresh_queue_molecules":0,
                      "private_fixture_cleaned":True,"QM_started":False,"production_queue_opened":False}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--recompute-plan",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());private_fixture();return
    require_slurm(24)
    plan=json.loads(a.recompute_plan.read_text())
    if plan["selected_records"]!=200 or plan["requested_quantum_slots"]!=2400:raise ValueError("AUTHORIZED_200_RECORD_SCOPE_REQUIRED")
    for name in ("runner","protocol","dictionaries","node_authority","node_scope_plan"):
        if sha(plan[name])!=plan[name+"_sha256"]:raise ValueError("PREPARED_RECOMPUTE_BINDING_CHANGED:"+name)
    for name in ('audit_manifest','reproduction_package','production_contract'):
        reference=plan[name]
        if sha(reference['path'])!=reference['sha256']:raise ValueError('PREPARED_CURRENT_SCOPE_REF_CHANGED:'+name)
    command=plan["command"]
    if command[0]!=plan["expected_python"] or command[1]!=plan["runner"]:raise ValueError("PREPARED_EXECUTABLE_BINDING_DIFFERS")
    bootstrap_private_queue(a.recompute_plan,plan)
    result=subprocess.run(command,stdin=subprocess.DEVNULL)
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
