"""Private observer adapter; only the inherited16GiB RSS stop changes."""
import os,socket,time
from pathlib import Path
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as Original
from . import contract as C
Q=Original.Q

class Budget(Original.Budget):
    # Root-selected finite software budget for formal16-worker Pprime.
    # These are not Slurm requests or guarantees of available physical memory.
    SOFTWARE_WORKING_BUDGET_BYTES=C.SOFTWARE_WORKING_BUDGET_BYTES
    RSS_LIMIT_BYTES=C.RSS_LIMIT_BYTES
    def check(self,dispatch=True,force=False):
        now=time.monotonic()
        if not force and now-self.last<1:
            if dispatch:Q.need(self.stop_new is None,self.stop_new or 'RESOURCE_STOP')
            return
        self.last=now;req=self.proof['request']
        Q.need(os.getpid()==self.pid and Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]==self.ticks
            and os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node'] and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_LIVE_ADMITTED_PARENT')
        rss=0
        for pid in [str(self.pid),*Path('/proc/self/task/'+str(self.pid)+'/children').read_text().split()]:
            try:rss+=int(Path('/proc/'+pid+'/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            except FileNotFoundError:pass
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        used=self.used();v=os.statvfs(Q.ROOT);reserve=(258<<20) if dispatch else (2<<20)
        Q.need(used+reserve<self.cap and v.f_bavail*v.f_frsize-max(0,self.cap-used)>=200000000000,'WHOLE_OUTPUT_OR_CURRENT200GB_STOP')
        if rss>=self.RSS_LIMIT_BYTES or mem['MemAvailable']<max(4<<30,.15*mem['MemTotal']):self.stop_new=self.stop_new or 'RSS_MEMAVAILABLE_STOP_NEW_DISPATCH'
        if self.elapsed+now-self.start>=self.plan['wall_seconds']-180:self.stop_new=self.stop_new or 'FINITE_WALL_RESERVE_NATURAL_DRAIN'
        if dispatch:Q.need(self.stop_new is None,self.stop_new or 'RESOURCE_STOP')
