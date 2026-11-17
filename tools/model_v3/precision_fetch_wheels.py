"""Download Linux Python3.10 wheels on development compute20 for offline setup."""
import os
import signal
import socket
import subprocess
import sys
import time
from precision_quality import capacity,ROOT

if socket.gethostname().split('.')[0]!='compute-0-20':raise RuntimeError('Development compute20 required')
capacity()
destination=ROOT/'school_wheels';destination.mkdir(exist_ok=True)
temporary=ROOT/'wheel_tmp';temporary.mkdir(exist_ok=True)
environment=dict(os.environ,TMPDIR=str(temporary),CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
command=[sys.executable,'-m','pip','download','--no-cache-dir','--only-binary=:all:',
    '--python-version','310','--implementation','cp','--abi','cp310',
    '--index-url','https://download.pytorch.org/whl/cu128','--extra-index-url','https://pypi.org/simple',
    '--dest',str(destination),'torch==2.8.0+cu128',
    'pytest==8.4.2','exceptiongroup','tomli']
for platform in ('manylinux_2_28_x86_64','manylinux_2_27_x86_64','manylinux_2_24_x86_64',
                 'manylinux_2_17_x86_64','manylinux2014_x86_64','manylinux2010_x86_64','manylinux1_x86_64','linux_x86_64'):
    command.extend(['--platform',platform])
process=subprocess.Popen(command,env=environment,start_new_session=True);paused=False
while process.poll() is None:
    try:capacity();ok=True
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('DISK_PROTECTION: '+str(error),flush=True);ok=False
    if ok==paused and process.poll() is None:
        os.killpg(process.pid,signal.SIGCONT if ok else signal.SIGSTOP);paused=not ok
    time.sleep(5)
raise SystemExit(process.wait())
