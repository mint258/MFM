"""One metadata-only ledger census per locked allocation; never a poll scan.

Old accounting DBs remain evidence. Every allocation starts a new ledger from
current native inode facts, including abandoned no-retry partial output bytes.
This also avoids carrying mount-local inode/device facts across node epochs.
The caller must own the stage namespace and hold its parent lock before calling.
"""
import fcntl
import os
from pathlib import Path
import socket
import stat
import time
from decimal import Decimal


def locked_scope(root, parent_lock, registered_writers=()):
    root=Path(root).absolute()
    if parent_lock is None or Path(parent_lock.name).absolute()!=root/'parent.lock':
        raise RuntimeError('LOCKED_STAGE_PARENT_REQUIRED_FOR_LEDGER_CENSUS')
    before=os.fstat(parent_lock.fileno());current=(root/'parent.lock').lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid()
            or (before.st_dev,before.st_ino)!=(current.st_dev,current.st_ino)):
        raise RuntimeError('OWN_SAME_FD_STAGE_PARENT_LOCK_REQUIRED')
    fcntl.flock(parent_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert_registered_writers_gone(registered_writers)
    return {'node':socket.gethostname(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'scope_device_u64':str(root.stat().st_dev),'scope_inode_u64':str(root.stat().st_ino),
            'pid':os.getpid(),'parent_lock_held':True,'old_open_output_handles':0,
            'cross_node_inode_identity_assumed':False}


def assert_registered_writers_gone(writers):
    """Inspect only registered related writers, never unrelated own PIDs.

    Actual prior plan/startup and terminal Slurm metadata inventory every old attempt.
    Unknown existing stages are rejected by resume_authority, not guessed from
    an all-UID /proc search. PID reuse is distinguished by boot and start ticks.
    """
    node=socket.gethostname();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for writer in writers:
        if writer['node']!=node or writer['boot_id']!=boot:continue
        pid=writer['pid']
        if type(pid)is not int or pid<=0 or type(writer['start_ticks'])is not int:
            raise RuntimeError('EXACT_REGISTERED_WRITER_PID_START_TICKS_REQUIRED')
        try:
            text=(Path('/proc')/str(pid)/'stat').read_text()
            actual=int(text[text.rfind(')')+2:].split()[19])
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError as exc:raise RuntimeError('REGISTERED_WRITER_LIFETIME_UNREADABLE')from exc
        if actual==writer['start_ticks']:
            raise RuntimeError('REGISTERED_OLD_WRITER_STILL_ALIVE:'+str(pid))


def resume_authority(plan,root):
    """Direct prior plan/startup/terminal evidence; no per-job Root approval."""
    from ..alpha_runtime_v1 import common as Q
    from ..uff3_alpha_runtime_v1.terminal import parent
    from . import core as C
    history=any((root/name).exists()for name in ('molecules','families','interrupted','index.sqlite'))
    binding=plan.get('resume_binding')
    if not history:
        if binding:raise RuntimeError('RESUME_BINDING_WITHOUT_ACTUAL_STAGE_HISTORY')
        return []
    if not binding:raise RuntimeError('EXISTING_UFF_STAGE_REQUIRES_ACTUAL_MACHINE_RESUME_BINDING')
    Q.need(binding['output_scope_root']==str(root)and binding['source_manifest']==plan['source_manifest']
        and binding['recipe_sha256']==plan['recipe_sha256']==C.recipe_sha(),
        'Same actual stage/source/scientific recipe on continuation')
    previous=binding['previous_allocations'];Q.need(bool(previous),'Every prior scope attempt needs actual plan/startup/terminal metadata')
    expected=set();writers=[]
    for item in previous:
        old=Q.load(Q.verify(item['plan_reference']));proof=Q.load(Q.verify(item['startup_proof_reference']))
        Q.need(old['output_directory']==str(root)and old['source_manifest']==plan['source_manifest']
            and old['recipe_sha256']==C.recipe_sha()
            and proof['request']['producer_plan_reference']==item['plan_reference']
            and proof['uid']==Q.UID and proof['endpoint']==Q.ENDPOINT,
            'Actual previous same-stage plan bound to native startup and Alpha identity')
        runtime={'job_id':str(proof['job_id']),'uid':proof['uid'],'endpoint':proof['endpoint']}
        if item.get('runtime_receipt_reference'):
            receipt=Q.load(Q.verify(item['runtime_receipt_reference']));runtime=receipt['runtime']
            Q.need(str(runtime['job_id'])==str(proof['job_id'])and receipt['source_manifest']==plan['source_manifest'],
                   'Actual previous producer receipt, no fabricated per-worker birth')
            if all(k in runtime for k in ('hostname','boot_id','pid','start_ticks')):
                writers.append({'node':runtime['hostname'],'boot_id':runtime['boot_id'],
                    'pid':runtime['pid'],'start_ticks':runtime['start_ticks']})
        parent(runtime,item['accounting_reference'],require_C0=False)
        expected.add(Q.canonical(item['plan_reference']))
    observed=set()
    for path in root.glob('derived_runtime_plan_*.json'):
        old=Q.load(path);ref=old.get('original_launcher_plan_reference')
        if ref and ref!=plan.get('original_launcher_plan_reference'):observed.add(Q.canonical(ref))
    Q.need(bool(observed)and observed==expected,'All historical stage attempts inventoried; unknown stages cannot be silently adopted')
    return writers

def rebuild(budget):
    """Register actual allocated blocks once, using O(depth) traversal memory."""
    root=budget.root;files=directories=0
    for base,names,items in os.walk(root,followlinks=False):
        base=Path(base)
        for name in names:
            if (base/name).is_symlink():raise RuntimeError('OUTPUT_DIRECTORY_SYMLINK')
        # The two-level molecule routing directories remain mutable as new MIDs
        # arrive. Completed molecule/batch subdirectories are immutable forever.
        mutable=(base in (root,root/'molecules',root/'families',root/'interrupted')
                 or base.parent==root/'molecules')
        if mutable:budget.mutable_dirs.add(base)
        else:budget.ledger.register_directory(base)
        directories+=1
        for name in items:
            path=base/name
            budget.register(path);files+=1
            if files%4096==0 and getattr(budget,'startup_guard',None):budget.startup_guard.sample();budget.startup_guard.check()
    budget.ledger.flush()
    return {'census_files':files,'census_directories':directories,
            'includes_retained_interrupted_bytes':True,'native_census_per_allocation':1,
            'per_poll_tree_walk':False,'actual_totals':budget.ledger.totals()}
class StartupCensus:
    """Closed native baseline plus only actual new accounting-file growth.

    Old outputs cannot change under the reviewed writer-closure and parent lock.
    Only immutable old regular files receive conservative prequery credit. The
    complete baseline is never confused with an incomplete rebuilt ledger.
    """
    def __init__(self,root,ledger_path,plan):
        self.root=Path(root);self.path=Path(ledger_path);self.plan=plan
        self.total=0;self.credit=0;self.maximum_eligible_ns=0;self.files=0;seen=set()
        self.initial_root_blocks=self.root.lstat().st_blocks*512;last=0.
        for base,dirs,files in os.walk(self.root,followlinks=False):
            for name in [Path(base),*(Path(base)/n for n in files)]:
                before=name.lstat();after=name.lstat()
                stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_size,s.st_blocks,s.st_mtime_ns,s.st_ctime_ns)
                if (before.st_uid!=os.getuid()or not(stat.S_ISREG(before.st_mode)or stat.S_ISDIR(before.st_mode))
                        or stamp(before)!=stamp(after)):
                    raise RuntimeError('STABLE_OWN_NON_SYMLINK_STARTUP_CENSUS_REQUIRED')
                key=(before.st_dev,before.st_ino)
                if stat.S_ISREG(before.st_mode)and before.st_nlink>1:
                    if key in seen:continue
                    seen.add(key)
                blocks=before.st_blocks*512;self.total+=blocks
                if stat.S_ISREG(before.st_mode):
                    self.files+=1
                    if not ClosedMutable(name)and not name.name.startswith('derived_runtime_plan_'):
                        self.credit+=blocks
                        self.maximum_eligible_ns=max(self.maximum_eligible_ns,before.st_mtime_ns,before.st_ctime_ns)
                if time.monotonic()-last>=5:
                    self.check_memory();last=time.monotonic()
            if any((Path(base)/n).is_symlink()for n in dirs):raise RuntimeError('OUTPUT_DIRECTORY_SYMLINK')
        self.reserved=plan['ledger_rebuild_reserved_bytes']
        if type(self.reserved)is not int or self.reserved<1<<20 or self.total+self.reserved>plan['output_cap_bytes']:
            raise RuntimeError('ACTUAL_COMPLETE_BASELINE_PLUS_REVIEWED_LEDGER_RESERVATION_EXCEEDS_CAP')
        self.peak_growth=0

    def check_memory(self):
        from ..alpha_runtime_v1.guard import memory
        rss,available=memory()
        if rss>=self.plan['software_rss_budget_bytes']or available<self.plan['minimum_node_available_bytes']:
            raise RuntimeError('ACTUAL_STARTUP_CENSUS_RSS_OR_NODE_RESERVE')

    def usage(self):
        growth=self.root.lstat().st_blocks*512-self.initial_root_blocks
        for suffix in ('','-journal','-wal','-shm'):
            path=self.path.parent/(self.path.name+suffix)
            try:s=path.lstat()
            except FileNotFoundError:continue
            if not stat.S_ISREG(s.st_mode)or s.st_uid!=os.getuid():raise RuntimeError('OWN_NATIVE_NEW_LEDGER_FILE_REQUIRED')
            growth+=s.st_blocks*512
        growth=max(growth,0);self.peak_growth=max(getattr(self,'peak_growth',0),growth)
        if growth>self.reserved:raise RuntimeError('NEW_ACCOUNTING_NAMESPACE_EXCEEDS_RESERVED_BYTES')
        return self.total+growth

    def credit_before(self,cutoff):
        # Strict boundary; old mutable databases/directories get no credit.
        ns=Decimal(str(cutoff))*Decimal(1000000000)
        return self.credit if ns>self.maximum_eligible_ns else 0

    def receipt(self):
        return dict(complete_native_baseline_allocated_bytes=self.total,old_immutable_file_credit_bytes=self.credit,
            old_immutable_maximum_mtime_ctime_ns=self.maximum_eligible_ns,baseline_files=self.files,
            ledger_rebuild_reserved_bytes=self.reserved,observed_new_ledger_peak_allocated_bytes=self.peak_growth,
            baseline_unchanged_under_parent_lock_and_terminal_registered_writer_closure=True,
            partial_rebuild_totals_used_for_admission=False)


def ClosedMutable(path):
    from .credit import ClosedLedger
    return ClosedLedger.is_mutable(path)