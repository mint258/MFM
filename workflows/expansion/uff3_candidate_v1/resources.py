"""Thin resource adapter to the shared Root quota/safety implementation."""
from pathlib import Path
import os
import stat
import time
import uuid
from .credit import ClosedLedger,synchronized
import threading


class Budget:
    def __init__(self, plan, output, parent_lock=None):
        self.lock=threading.RLock();self.alpha_guard=None
        self.plan=plan;self.root=Path(output);self.last=0.;self.latest=None
        if plan.get('runtime_profile_reference')and Path(plan['output_scope_root'])!=self.root:
            raise RuntimeError('UFF_LEDGER_MUST_COVER_ENTIRE_DECLARED_ALPHA_OUTPUT_SCOPE')
        self.mutable_paths=set()
        self.mutable_dirs={self.root,self.root/'molecules',self.root/'families',self.root/'interrupted'}
        self.root.mkdir(parents=True,exist_ok=True)
        self.ledger_rebuild=None
        if parent_lock is not None:
            from .ledger_resume import locked_scope,rebuild,resume_authority
            epoch=locked_scope(self.root,parent_lock,resume_authority(plan,self.root))
            ledger_path=self.root/('output_accounting_v2_'+uuid.uuid4().hex+'.sqlite')
        else:
            if plan.get('runtime_profile_reference'):
                raise RuntimeError('ALPHA_GENERATION_REQUIRES_EXCLUSIVE_PARENT_LOCK')
            ledger_path=self.root/'output_accounting_v2.sqlite'
        self.startup_guard=None;startup=None
        if parent_lock is not None and plan.get('runtime_profile_reference'):
            from .ledger_resume import StartupCensus
            from workflows.expansion.alpha_runtime_v1.guard import Guard
            startup=StartupCensus(self.root,ledger_path,plan)
            self.startup_guard=Guard(plan,usage_provider=startup.usage,prequery_credit_provider=startup.credit_before)
        try:
            self.ledger=ClosedLedger(ledger_path,maximum_bytes=plan['ledger_rebuild_reserved_bytes']if startup else None)
        except BaseException:
            if self.startup_guard:self.startup_guard.close()
            raise
        self.mutable_paths.update(ledger_path.parent/(ledger_path.name+suffix)
                                  for suffix in ('','-journal','-wal','-shm'))
        for name in ('index.sqlite','output_accounting.sqlite','validity.duckdb','validity.duckdb.wal','parent.lock'):
            for suffix in ('','-journal','-wal','-shm'):self.mutable_paths.add(self.root/(name+suffix))
        if parent_lock is not None:
            try:
                self.ledger_rebuild={'epoch':epoch,**rebuild(self)}
                if self.startup_guard:
                    self.startup_guard.sample();self.startup_guard.check()
                    self.ledger_rebuild.update(startup_census=startup.receipt(),startup_guard=self.startup_guard.receipt())
            finally:
                if self.startup_guard:self.startup_guard.close()
                self.startup_guard=None
        if plan.get('runtime_profile_reference'):
            if Path(plan['output_scope_root'])!=self.root:
                raise RuntimeError('UFF_LEDGER_MUST_COVER_ENTIRE_DECLARED_ALPHA_OUTPUT_SCOPE')
            from workflows.expansion.alpha_runtime_v1.guard import Guard
            self.alpha_guard=Guard(plan,usage_provider=self.used,prequery_credit_provider=self.ledger.credit_before)
        self.check(True)

    @synchronized
    def register(self, path):
        path=Path(path)
        if path!=self.root and self.root not in path.parents:
            raise RuntimeError('ONLY_OWN_OUTPUT_ACCOUNTING')
        if path.is_symlink():raise RuntimeError('OWN_OUTPUT_SYMLINK_REJECTED')
        if path.is_dir():
            self.mutable_dirs.add(path.parent)
            for base,dirs,files in os.walk(path,followlinks=False):
                for name in dirs:
                    if (Path(base)/name).is_symlink():raise RuntimeError('OUTPUT_DIRECTORY_SYMLINK')
                for name in files:self.register(Path(base)/name)
                self.ledger.register_directory(base)
                self.mutable_dirs.discard(Path(base))
        else:
            value=path.lstat()
            if not stat.S_ISREG(value.st_mode) or value.st_uid!=os.getuid():
                raise RuntimeError('OWN_REGULAR_OUTPUT_REQUIRED')
            if ClosedLedger.is_mutable(path):self.mutable_paths.add(path)
            else:self.ledger.register(path)

    @synchronized
    def used(self):
        totals=self.ledger.totals()
        mutable=0;seen=set()
        for path in self.mutable_paths:
            try:value=path.lstat()
            except FileNotFoundError:continue
            if not stat.S_ISREG(value.st_mode) or value.st_uid!=os.getuid():
                raise RuntimeError('OWN_MUTABLE_ACCOUNTING_OUTPUT_REQUIRED')
            key=(value.st_dev,value.st_ino)
            if key not in seen:mutable+=value.st_blocks*512;seen.add(key)
        for path in self.mutable_dirs:
            try:value=path.lstat()
            except FileNotFoundError:continue
            if not stat.S_ISDIR(value.st_mode) or value.st_uid!=os.getuid():raise RuntimeError('OWN_MUTABLE_DIRECTORY_REQUIRED')
            key=(value.st_dev,value.st_ino)
            if key not in seen:mutable+=value.st_blocks*512;seen.add(key)
        return totals['closed_allocated_bytes']+mutable

    @synchronized
    def require_dispatch_capacity(self):
        pending=2*self.plan['workers']*(self.plan.get('maximum_molecule_output_bytes',64<<20)+(64<<10))
        family=self.plan.get('parent_family_reserved_bytes',128<<20)
        if self.used()+pending+family>self.plan['output_cap_bytes']:
            raise RuntimeError('OUTPUT_CAP_RESERVE_ALL_IN_FLIGHT_MOLECULES_AND_FAMILY_BATCH')

    @synchronized
    def check(self,force=False):
        if self.alpha_guard is not None:
            if force:self.ledger.flush()
            self.alpha_guard.check()
            self.latest=self.alpha_guard.receipt()
            return self.latest
        now=time.monotonic()
        if force or self.latest is None or now-self.last>=30:
            if self.plan['quota_authority'].get('kind')=='lustre':
                from workflows.expansion.completion_runtime_v1.lustre_quota import budget_check
            else:
                from workflows.expansion.completion_runtime_v1.quota import budget_check
            self.latest=budget_check(self.plan,self.used(),self.root,
                prequery_credit_provider=self.ledger.credit_before)
            self.last=now
        return self.latest

    def seal_ledger(self):
        """Current persisted closed bytes, not historical peak or a tree scan."""
        if self.alpha_guard is not None:self.alpha_guard.close()
        self.ledger.flush();totals=self.ledger.totals();path=self.ledger.path
        maximum=self.ledger.maximum_native_ns
        self.ledger.close()
        s=path.lstat()
        return {'path':str(path),'schema_version':2,'closed_totals':totals,
            'maximum_recorded_native_ns':maximum,
            'closed_at_unix_ns':max(time.time_ns(),maximum,s.st_mtime_ns,s.st_ctime_ns),
            'producer_frame':{'uid':s.st_uid,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'nlink':s.st_nlink},
            'mutable_paths':[str(p)for p in sorted(self.mutable_paths)],
            'mutable_routing_directories':[str(p)for p in sorted(self.mutable_dirs)],
            'whole_tree_root_blocks_used_as_total':False,'historical_peak_used_as_current':False}