"""Private, job-owned legacy MPS service for a subsequent controlled benchmark.

No service starts on import. Clients must be drained with terminate_clients()
before the caller sends process signals, as required by NVIDIA's MPS interface.
"""
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from cpu_bottleneck_step1 import capacity
from model_gpu_registry import IDENTITY
from runtime_monitor import capture_process_identity
from v2_watch_disk import filesystem_status, require_capacity


def numeric_pids(text):
    rows = [row.strip() for row in text.splitlines() if row.strip()]
    if any(not row.isdecimal() or int(row)<=0 for row in rows):
        raise RuntimeError('Unexpected MPS control response: '+text[:200])
    return {int(row) for row in rows}


def same_identity(bound, current):
    return current.get('status')=='ACTIVE' and all(bound.get(k)==current.get(k) for k in IDENTITY)


class PrivateMPS:
    binary = '/usr/bin/nvidia-cuda-mps-control'

    def __init__(self, gpu, output):
        if not re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',gpu):
            raise ValueError('Bind exactly one full physical GPU UUID')
        self.job = os.environ['SLURM_JOB_ID']
        if not self.job.isdecimal():
            raise ValueError('An actual Slurm job is required')
        self.gpu, self.output = gpu, Path(output)
        self.pipe = Path('/tmp')/f'mfm_cpu_mps_{os.getuid()}_{self.job}'
        self.logs = self.output/'mps_logs'
        self.env = dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,
            CUDA_MPS_PIPE_DIRECTORY=str(self.pipe),CUDA_MPS_LOG_DIRECTORY=str(self.logs))
        self.process = self.controller = self.server = self.stream = None
        self.seen_clients = set()

    def check(self):
        capacity()
        require_capacity(filesystem_status(self.pipe),64*1024**2,32)
        require_capacity(filesystem_status(self.logs),64*1024**2,32)
        if self.pipe.exists():
            info=self.pipe.lstat()
            if info.st_uid!=os.getuid() or not stat.S_ISDIR(info.st_mode) or info.st_mode&0o077:
                raise RuntimeError('MPS pipe directory must remain private and owned')

    def command(self, text):
        if self.controller is None or not same_identity(self.controller,
                capture_process_identity(self.controller['pid'])):
            raise RuntimeError('Private MPS controller identity changed')
        result=subprocess.run([self.binary],input=text+'\n',env=self.env,
            text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,check=True)
        return result.stdout

    def clients(self):
        if self.server is None or not same_identity(self.server,
                capture_process_identity(self.server['pid'])):
            raise RuntimeError('Private MPS server identity changed')
        return numeric_pids(self.command(f'get_client_list {self.server["pid"]}'))

    def terminate_clients(self, identities):
        """Drain only identified clients belonging to this job, before any signal."""
        clients=self.clients()
        if not clients <= set(identities):
            raise RuntimeError('Unknown MPS client; no shutdown or signals permitted')
        for pid in clients:
            bound=identities[pid]
            current=capture_process_identity(pid)
            if bound.get('slurm_job_id')!=self.job or not same_identity(bound,current):
                raise RuntimeError('MPS client identity unavailable; refusing termination')
            reply=self.command(f'terminate_client {self.server["pid"]} {pid}').strip()
            if reply!='0':
                raise RuntimeError('MPS did not confirm safe CUDA client termination: '+reply)

    def validate_gpu_contexts(self, active, cohort):
        """The NVIDIA-visible server replaces client contexts; never mask others."""
        self.check()
        if not same_identity(self.server,capture_process_identity(self.server['pid'])):
            raise RuntimeError('MPS support process identity changed')
        clients=self.clients()
        if not clients <= set(cohort):
            raise RuntimeError('MPS client is outside the registered measurement cohort')
        if (set(active)&set(cohort))-clients:
            raise RuntimeError('A benchmark client bypassed its private MPS server')
        self.seen_clients.update(clients)
        return set(active)-{self.server['pid']}

    def confirm_clients(self, cohort):
        if not set(cohort) <= self.seen_clients:
            raise RuntimeError('MPS connection was not observed for every benchmark participant')

    def __enter__(self):
        import psutil
        self.check()
        for process in psutil.process_iter(['pid','name','cmdline']):
            try:
                argv=process.info['cmdline'] or []
                if ((argv and Path(argv[0]).name in ('nvidia-cuda-mps-control','nvidia-cuda-mps-server'))
                        or str(process.info.get('name','')).startswith('nvidia-cuda-mps')):
                    raise RuntimeError('An MPS service already exists on this node; leave it untouched')
            except psutil.NoSuchProcess:
                continue
        self.pipe.mkdir(mode=0o700,exist_ok=False)
        self.logs.mkdir(parents=True,exist_ok=False)
        self.stream=(self.logs/'controller.log').open('x')
        self.process=subprocess.Popen([self.binary,'-f'],env=self.env,stdin=subprocess.DEVNULL,
            stdout=self.stream,stderr=subprocess.STDOUT,start_new_session=True)
        self.controller=capture_process_identity(self.process.pid)
        if self.controller.get('status')!='ACTIVE':
            raise RuntimeError('MPS control process was not admitted')
        try:
            while True:
                try:
                    self.command('get_server_list')
                    break
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                    if self.process.poll() is not None:
                        raise
                    time.sleep(.5)
            self.command(f'start_server -uid {os.getuid()}')
            servers=numeric_pids(self.command('get_server_list'))
            if len(servers)!=1:
                raise RuntimeError('Exactly one private MPS server is required')
            server=capture_process_identity(next(iter(servers)))
            environment=Path(f'/proc/{server["pid"]}/environ').read_bytes().split(b'\0')
            if (server.get('status')!='ACTIVE' or Path(server['argv'][0]).name!='nvidia-cuda-mps-server'
                    or ('CUDA_MPS_PIPE_DIRECTORY='+str(self.pipe)).encode() not in environment):
                raise RuntimeError('MPS server is not bound to this private namespace/job')
            self.server=server
            return self
        except Exception:
            self.command('quit')
            self.process.wait(timeout=20)
            self.stream.close()
            raise

    def __exit__(self, kind, value, traceback):
        if self.clients():
            raise RuntimeError('MPS clients must exit or be safely drained before private service shutdown')
        self.command('quit')
        self.process.wait(timeout=20)
        self.stream.close()
