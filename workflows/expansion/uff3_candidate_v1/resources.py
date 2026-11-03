"""Thin resource adapter to the shared Root quota/safety implementation."""
from pathlib import Path
import os
import stat
import time
from .credit import ClosedLedger,synchronized
import threading


class Budget:
    def __init__(self, plan, output):
        self.lock=threading.RLock();self.alpha_guard=None
        self.plan=plan;self.root=Path(output);self.last=0.;self.latest=None
        self.mutable_paths=set()
        self.mutable_dirs={self.root,self.root/'molecules',self.root/'families',self.root/'interrupted'}
        self.root.mkdir(parents=True,exist_ok=True)
        self.ledger=ClosedLedger(self.root/'output_accounting.sqlite')
        for name in ('index.sqlite','output_accounting.sqlite','validity.duckdb','parent.lock'):
            for suffix in ('','-journal','-wal','-shm'):self.mutable_paths.add(self.root/(name+suffix))
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
        mutable=0
        for path in self.mutable_paths:
            try:value=path.lstat()
            except FileNotFoundError:continue
            if not stat.S_ISREG(value.st_mode) or value.st_uid!=os.getuid():
                raise RuntimeError('OWN_MUTABLE_ACCOUNTING_OUTPUT_REQUIRED')
            mutable+=value.st_blocks*512
        for path in self.mutable_dirs:
            try:value=path.lstat()
            except FileNotFoundError:continue
            if not stat.S_ISDIR(value.st_mode) or value.st_uid!=os.getuid():raise RuntimeError('OWN_MUTABLE_DIRECTORY_REQUIRED')
            mutable+=value.st_blocks*512
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
