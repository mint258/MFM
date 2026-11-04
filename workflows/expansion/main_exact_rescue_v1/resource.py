"""Main node-local scratch and process-tree protections; no fake Alpha quota."""
import os
from pathlib import Path
import threading
import stat
import time
from ..alpha_runtime_v1.guard import memory
from .common import need


class Guard:
    def __init__(self,plan,stop):
        self.plan=plan;self.stop=stop;self.done=threading.Event();self.failure=None;self.samples=0
        self.peak_bytes=self.peak_rss=0;self.minimum_available=None
        rss,available=memory()
        need(available>=plan['software_rss_budget_bytes']+plan['minimum_node_available_bytes']+plan.get('future_tmpfs_output_bytes',0),
            'Actual startup RAM must fit all software workers/parent plus node reserve')
        self.sample();self.thread=threading.Thread(target=self.observe,daemon=True);self.thread.start()
    def sample(self):
        p=self.plan;root=Path(p['output_directory']);total=0;seen=set()
        for base,dirs,files in os.walk(root):
            need(not any((Path(base)/n).is_symlink()for n in dirs),'Scratch directory symlink')
            for path in [Path(base),*(Path(base)/n for n in files)]:
                try:s=path.lstat()
                except FileNotFoundError:continue  # Own compiler/spill cleanup raced this metadata sample.
                need(s.st_uid==1278 and(stat.S_ISDIR(s.st_mode)or(stat.S_ISREG(s.st_mode)and s.st_nlink==1)),
                    'Own literal regular scratch files/directories, no symlink or hidden hardlink')
                if (s.st_dev,s.st_ino)not in seen:total+=s.st_blocks*512;seen.add((s.st_dev,s.st_ino))
        rss,available=memory();parent=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        need(total<=p['output_cap_bytes'],'Actual full Main rescue output cap')
        free=os.statvfs(root);remaining=max(0,p['output_cap_bytes']-total)
        need(free.f_bavail*free.f_frsize-remaining-p['other_scratch_reserved_bytes']>=p['minimum_scratch_free_bytes'],
             'Actual node-local scratch free minus all declared remaining outputs/reserve')
        need(rss<=p['software_rss_budget_bytes']and parent<=p['parent_rss_cap_bytes']
            and available>=p['minimum_node_available_bytes']+(remaining if p.get('future_tmpfs_output_bytes',0)else 0),'Actual Main RSS/tree/node reserve')
        self.samples+=1;self.peak_bytes=max(total,self.peak_bytes);self.peak_rss=max(rss,self.peak_rss)
        self.minimum_available=available if self.minimum_available is None else min(available,self.minimum_available)
    def observe(self):
        while not self.done.wait(5):
            try:self.sample()
            except BaseException as exc:self.failure=repr(exc);self.stop.set();return
    def check(self):need(not self.stop.is_set(),self.failure or 'Actual rescue resource stop')
    def close(self):
        self.done.set();self.thread.join();self.check();self.sample()
    def receipt(self):return dict(samples=self.samples,peak_actual_output_blocks_bytes=self.peak_bytes,
        peak_actual_tree_RSS_bytes=self.peak_rss,minimum_observed_MemAvailable_bytes=self.minimum_available,
        failure=self.failure,node_local_tmp_not_Alpha_account_quota=True,signals_sent=False)