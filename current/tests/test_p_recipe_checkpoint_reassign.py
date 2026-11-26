"""Exercise checkpoint-boundary pausing on a real isolated CPU process."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'tools/p_recipe'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('checkpoint_reassign', TOOLS / 'reassign_checkpoint.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

WORKER = '''import csv,os,sys,time
from pathlib import Path
root=Path(sys.argv[1])
with (root/'losses.csv').open('w',buffering=1) as stream:
 writer=csv.writer(stream);writer.writerow(['samples','updates','total','preclip_norm','lr','seconds'])
 for point in range(1,5):
  writer.writerow([point,point,1,1,.001,point])
  if point==2:
   temporary=root/'checkpoint.writing';temporary.write_text('closed')
   os.replace(temporary,root/'samples_2.pt')
  if point==3:(root/'third_committed').touch()
  time.sleep(.3)
'''


def start(tmp_path):
    child = subprocess.Popen([sys.executable, '-B', '-c', WORKER, str(tmp_path)], start_new_session=True)
    source = module.identity(child.pid)
    return child, source


def finish(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGCONT)
        os.killpg(child.pid, signal.SIGKILL)
    child.wait(timeout=5)


@pytest.mark.skipif(os.name != 'posix', reason='Uses Linux process identities and signals')
def test_term_pending_while_paused_cannot_commit_another_update(tmp_path):
    child, source = start(tmp_path)
    try:
        checkpoint, observed = module.pause_at_checkpoint(dict(output=str(tmp_path)), source, 2, .001)
        assert checkpoint.is_file() and observed[-1]['samples'] == 2
        for _ in range(1000):
            if module.process_state(child.pid) == 'T':
                break
            time.sleep(.001)
        assert module.process_state(child.pid) == 'T'
        os.killpg(child.pid, signal.SIGTERM)
        os.killpg(child.pid, signal.SIGCONT)
        assert child.wait(timeout=5) == -signal.SIGTERM
        assert module.last_rows(tmp_path)[-1]['samples'] == 2
    finally:
        finish(child)


@pytest.mark.skipif(os.name != 'posix', reason='Uses Linux process identities and signals')
def test_a_stale_checkpoint_resumes_the_original_instead_of_rolling_back(tmp_path):
    child, source = start(tmp_path)
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path/'third_committed').exists() and time.monotonic() < deadline:
            time.sleep(.001)
        assert (tmp_path/'third_committed').is_file()
        result = module.pause_at_checkpoint(dict(output=str(tmp_path)), source, 2, .001)
        assert result is None
        assert child.wait(timeout=5) == 0
        assert module.last_rows(tmp_path)[-1]['samples'] == 4
    finally:
        finish(child)
