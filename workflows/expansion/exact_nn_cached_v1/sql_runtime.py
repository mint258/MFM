"""Own SQL-attempt resource observation; no queue, scheduler or scientific retry."""
import os
from pathlib import Path
import socket
import stat
import threading
import time
from ..common import require
from .engine import current_rss
from ..pubchem_closed500_bulk_v2.merge import literal
from ..portable_sources_v1.transport import bind_plan


class SqlGuard:
    def __init__(self,plan,root):
        self.plan=plan;self.root=Path(plan['output_scope_root']) if plan.get('runtime_profile_reference') else Path(root)
        self.last=0;self.done=threading.Event();self.errors=[]
        if plan.get('runtime_profile_reference'):
            bind_plan(plan)
            from ..alpha_runtime_v1.profile import admit
            admit(plan,minimum_workers=16)
            require(plan['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],'SQL software allowance exceeds Alpha tree budget')
        else:
            require(socket.gethostname().split('.')[0].startswith('compute-0-') and os.environ.get('SLURM_JOB_ID')
                and 16<=plan['workers']<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')),'Actual16+ allocated Main CPU SQL required')
        if plan['quota_authority'].get('kind')=='gluster_directory_quota_deem_statfs':
            from ..alpha_runtime_v1.quota import budget_check
        elif plan['quota_authority'].get('kind')=='lustre':
            from ..completion_runtime_v1.lustre_quota import budget_check
        else:from ..completion_runtime_v1.quota import budget_check
        self.checker=budget_check;self.check(True)

    def check(self,force=False):
        if not force and time.monotonic()-self.last<30:return
        used=0
        # Dedicated small SQL tree only; never generation per-MID directories.
        for path in self.root.rglob('*'):
            try:value=path.lstat()
            except FileNotFoundError:continue  # Own DuckDB spill cleanup raced this observation; no quota credit is granted.
            require(not stat.S_ISLNK(value.st_mode) and value.st_uid==os.getuid(),'Own SQL output tree required')
            if stat.S_ISREG(value.st_mode):used+=max(value.st_size,value.st_blocks*512)
            else:require(stat.S_ISDIR(value.st_mode),'Regular SQL files/directories required')
        if self.plan.get('runtime_profile_reference'):
            from ..alpha_runtime_v1.common import allocated_bytes
            used=allocated_bytes(self.root)
        require(used<=self.plan['output_cap_bytes'],'SQL output/spill allowance exceeded')
        require(current_rss()<=self.plan['parent_rss_cap_bytes'],'Actual SQL parent RSS allowance exceeded')
        available=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
        require(available>=self.plan.get('minimum_node_available_bytes',4<<30),'Actual node memory reserve insufficient')
        self.latest=self.checker(self.plan,used,self.root,prequery_credit_provider=lambda cutoff:0)
        self.last=time.monotonic()

    def start(self,db):
        def observe():
            while not self.done.wait(30):
                try:self.check(True)
                except BaseException as exc:self.errors.append(repr(exc));db.interrupt();return
        self.thread=threading.Thread(target=observe,daemon=True);self.thread.start()

    def close(self):
        self.done.set()
        if hasattr(self,'thread'):self.thread.join()
        require(not self.errors,'Own SQL resource observation failed: '+str(self.errors))
        self.check(True)


def configure(db,plan,spill):
    require(0<plan['sql_memory_bytes']<plan['parent_rss_cap_bytes'] and 0<plan['spill_cap_bytes']<=plan['output_cap_bytes'],
        'Finite SQL memory, RSS and spill declarations required')
    db.execute('SET threads='+str(int(plan['workers'])));db.execute('SET memory_limit='+literal(str(plan['sql_memory_bytes'])+'B'))
    db.execute('SET max_temp_directory_size='+literal(str(plan['spill_cap_bytes'])+'B'))
    db.execute('SET temp_directory='+literal(spill));db.execute('SET preserve_insertion_order=false')
