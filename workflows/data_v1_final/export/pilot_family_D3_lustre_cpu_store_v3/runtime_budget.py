"""Keep resource limits while avoiding per-record shared-filesystem censuses."""
import time,os,stat,threading,pathlib
from . import contract as C,io as I
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.resource import clone
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as Memory
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import memory as ParentMemory

INTERVAL_SECONDS=10
WRITE_RESERVE_BYTES=4<<30

def observed_worker_rss(cap):
    # ru_maxrss can retain a fork parent's pre-exec peak. VmHWM belongs to
    # this actual exec lifetime, matching the observer PID/start-tick data.
    value=Memory.process_observation(os.getpid())
    parent=ParentMemory.MONITOR is not None and ParentMemory.MONITOR.pid==os.getpid()
    actual_cap=(56<<30)if parent else (3<<30)if cap in (1500000000,3<<30)else cap
    if value['high_water_bytes']>actual_cap:
        Memory.mark_stop('ACTUAL_EXEC_LIFETIME_RSS_CAP',dict(software_cap_bytes=actual_cap,worker=value))
    return value['high_water_bytes']

Memory.soft_worker_rss=observed_worker_rss

class StableOutputCensus:
    """A current owned-file census, tolerant of SQLite journal inode reuse."""
    def __init__(self,root):
        self.root=pathlib.Path(root);self.census_lock=threading.RLock();self.census_sequence=0
        self.descriptors={};self.generation=0

    def allocated(self):
        present={};pending=[os.fspath(self.root)]
        with self.census_lock:
            while pending:
                directory=pending.pop()
                try:
                    with os.scandir(directory)as stream:
                        for entry in stream:
                            try:value=entry.stat(follow_symlinks=False)
                            except FileNotFoundError:continue
                            C.need(value.st_uid==os.getuid() and (stat.S_ISDIR(value.st_mode)or stat.S_ISREG(value.st_mode)),"OWN_REGULAR_OUTPUT_NO_SYMLINK")
                            if stat.S_ISDIR(value.st_mode):pending.append(entry.path);continue
                            C.need(value.st_nlink<=1,"OUTPUT_EXTERNAL_HARDLINK")
                            if value.st_size<64<<20:continue
                            key=(value.st_dev,value.st_ino)
                            if key not in self.descriptors and len(self.descriptors)<512:
                                try:fd=os.open(entry.path,os.O_RDONLY|os.O_NOFOLLOW)
                                except FileNotFoundError:continue
                                opened=os.fstat(fd)
                                if (opened.st_dev,opened.st_ino)!=(value.st_dev,value.st_ino):os.close(fd);continue
                                self.generation+=1;self.descriptors[key]=(fd,self.generation)
                            if key in self.descriptors:present[key]=value.st_blocks*512
                except FileNotFoundError:continue
            answer={(*key,self.descriptors[key][1]):value for key,value in present.items()}
            for key in list(self.descriptors):
                if key not in present:os.close(self.descriptors.pop(key)[0])
            return answer

    def close(self):
        for fd,_ in self.descriptors.values():os.close(fd)
        self.descriptors.clear()

    def __call__(self,path):
        C.need(os.fspath(path)==os.fspath(self.root),'OWN_OUTPUT_ROOT_ONLY')
        with self.census_lock:
            seen={};pending=[os.fspath(path)]
            while pending:
                directory=pending.pop()
                try:
                    value=os.lstat(directory)
                    C.need(value.st_uid==os.getuid() and stat.S_ISDIR(value.st_mode),'OWN_OUTPUT_DIRECTORY')
                    seen[(value.st_dev,value.st_ino)]=value.st_size
                    with os.scandir(directory)as stream:
                        for entry in stream:
                            try:value=entry.stat(follow_symlinks=False)
                            except FileNotFoundError:continue
                            C.need(value.st_uid==os.getuid() and (stat.S_ISDIR(value.st_mode)or stat.S_ISREG(value.st_mode)),'OWN_REGULAR_OUTPUT_NO_SYMLINK')
                            if stat.S_ISDIR(value.st_mode):pending.append(entry.path)
                            else:C.need(value.st_nlink<=1,'OUTPUT_EXTERNAL_HARDLINK')
                            key=(value.st_dev,value.st_ino);seen[key]=max(seen.get(key,0),value.st_size)
                except FileNotFoundError:continue
            return sum(seen.values())

class WholeOutputMath:
    """Count earlier quota-covered owned blocks once, including open stages.

    A retained descriptor pins each inode lifetime; generation tokens prevent
    journal inode reuse. Credit is the overlap of a pre-quota and current
    allocation sample, never an assumed monotonic allocation or changed free.
    """
    def __init__(self,budget,original):
        self.budget=budget;self.original=original;self.samples=[];self.last_report=None
        self.path=budget.census_context.root/'domain.sqlite'
    def __getattr__(self,name):return getattr(self.original,name)
    def remaining_future(self,total,cap,closed):
        current=self.budget.census_context.allocated()
        observed=self.budget.quota['observed_unix_seconds']
        eligible=[(timestamp,sample)for timestamp,sample in self.samples if timestamp<=observed]
        previous=eligible[-1][1]if eligible else {}
        credit=min(cap,sum(min(amount,current.get(key,0))for key,amount in previous.items()))
        C.need(0<=credit<=cap<=total,'CURRENT_OWN_ALLOCATION_WITHIN_RESERVED_CAP')
        remaining=total-credit
        self.samples=[item for item in self.samples if item[0]>observed][-12:]
        if eligible:self.samples.insert(0,eligible[-1])
        self.samples.append((time.time(),current))
        self.last_report=dict(schema='D3_QUOTA_COVERED_WHOLE_OWN_OUTPUT_ONCE_V1',
            quota_snapshot_reference=self.budget.quota['snapshot_reference'],
            quota_observed_unix_seconds=observed,total_future_reserved_bytes=total,
            original_full_parent_cap_bytes=cap,earlier_quota_covered_owned_allocated_bytes=credit,
            inherited_closed_credit_added_again=False,remaining_future_reserved_bytes=remaining,
            free_bytes_rewritten=False,SQL_or_database_body_read=False,
            mutable_allocation_monotonicity_required=False,quota_reserve_bytes=self.budget.account_floor_bytes)
        return remaining
    def report(self):return self.last_report or dict(schema='D3_QUOTA_COVERED_WHOLE_OWN_OUTPUT_ONCE_V1',no_quota_observation=True)

class Budget(I.Budget):
    def __init__(self,plan,proof,root):
        initialize=clone(I.Budget.__init__,ActiveDomainMath=WholeOutputMath,CensusContext=StableOutputCensus)
        initialize(self,plan,proof,root)
        I.ACTIVE_CENSUS=self.census_context
        self.next_row_census=0

    def close(self):
        try:super().close()
        finally:self.census_context.close()

    def loop(self):
        while not self.done.wait(INTERVAL_SECONDS):self.observe()

    def check(self,*,force=False,dispatch=True):
        if force:self.observe()
        if dispatch:C.need(not Memory.stop_requested(),'RESOURCE_STOP_NATURAL_DRAIN')
        if force or time.monotonic()>=self.next_row_census:
            C.need(self.census_context(self.root)+WRITE_RESERVE_BYTES<self.plan['whole_output_cap_bytes'],
                   'WHOLE_OUTPUT_CAP_WITH_WRITE_RESERVE')
            self.next_row_census=time.monotonic()+INTERVAL_SECONDS

def worker_check(control,additional=0):
    if control.get('mode')=='USER_UNLIMITED_CPU21_D3_20261103':
        while pathlib.Path(control['storage_pause_file']).exists():time.sleep(1)
        return
    # The parent monitors whole-output bytes, quota and wall time every ten
    # seconds. Workers retain immediate local STOP/RSS checks; they do not
    # each recursively stat every shared output file for every native row.
    Memory.soft_worker_rss(3<<30)
    C.need(not Memory.stop_requested(),'RESOURCE_STOP_BEFORE_NEXT_ROW')
    if additional:
        C.need(additional+WRITE_RESERVE_BYTES<control['cap'],'ONE_WRITE_WITHIN_OUTPUT_CAP')
