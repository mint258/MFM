"""Real-kernel same-task handoff controls; no GPU/model/data computations."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import exit_lifecycle as lifecycle
from a5_takeover_entry import wait_for_source

CHILD=r'''import json,os,signal,sys
from pathlib import Path
path=Path(sys.argv[1]);mode=sys.argv[2]
def identity():
 p=Path("/proc")/str(os.getpid());raw=(p/"stat").read_text();f=raw[raw.rfind(")")+2:].split()
 return dict(pid=os.getpid(),start_ticks=int(f[19]),uids=[1278]*4,cgroup=(p/"cgroup").read_text())
record=dict(execution_id="ssh:P_A5_handoff_test",node=os.uname().nodename,gpu_uuid="synthetic_no_GPU",
 supervisor=identity(),launcher=identity(),status="RUNNING")
def write():path.write_text(json.dumps(record))
def stop(sig,frame):
 record.update(status="CURSOR_SAVED_NOT_COMPLETE",returncode=75,owned_tree_reaped=True,remaining_children=[],preserved_state=dict(optimizer=7,scheduler=37,RNG="unchanged"))
 write();raise SystemExit(75)
signal.signal(signal.SIGUSR1,stop)
if mode=="complete":record.update(status="COMPLETE",returncode=0,owned_tree_reaped=True,remaining_children=[])
write();print("READY",flush=True)
if mode!="complete":
 import time
 time.sleep(30)
'''

def source(tmp_path,mode):
 receipt=tmp_path/"source.json"
 process=subprocess.Popen([sys.executable,"-B","-c",CHILD,str(receipt),mode],stdout=subprocess.PIPE,text=True)
 assert process.stdout.readline().strip()=="READY"
 c=dict(ssh_runtime_receipt=str(receipt),ssh_execution_id="ssh:P_A5_handoff_test",
  node=os.uname().nodename,gpu_uuid="synthetic_no_GPU",work_unit_seconds=1)
 return process,c,receipt

def test_running_source_saves_then_exits_before_resume(tmp_path,monkeypatch):
 process,c,path=source(tmp_path,"running")
 monkeypatch.setenv("P_MANAGED_STOP_NEW_UNITS_AT",str(time.time()+60))
 def actual(pid):
  process.poll()
  return lifecycle.identity(pid)
 try:
  result=wait_for_source(c,SimpleNamespace(requested=False),identity=actual,poll=.01)
  assert result=="RESUME_READY"
  assert process.wait(timeout=3)==75
  saved=json.loads(path.read_text())
  assert saved["preserved_state"]==dict(optimizer=7,scheduler=37,RNG="unchanged")
  assert lifecycle.identity(process.pid) is None
 finally:
  if process.poll() is None:
   bound=lifecycle.identity(process.pid);scope=next(x for x in bound.cgroup.splitlines() if x.startswith("0::"))
   lifecycle.signal_owned(bound,signal.SIGTERM,uid=1278,scope=scope);process.wait(timeout=3)

def test_completed_source_neither_signalled_nor_rerun(tmp_path,monkeypatch):
 process,c,path=source(tmp_path,"complete");assert process.wait(timeout=3)==0
 monkeypatch.setenv("P_MANAGED_STOP_NEW_UNITS_AT",str(time.time()+60))
 with mock.patch.object(lifecycle,"signal_owned",side_effect=AssertionError("Completed source must not be signalled")):
  assert wait_for_source(c,SimpleNamespace(requested=False),poll=.01)=="ALREADY_COMPLETE"
 assert lifecycle.identity(process.pid) is None
