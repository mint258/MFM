"""Keep resource limits while avoiding per-record shared-filesystem censuses."""
import time,os
from . import contract as C,io as I
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.resource import Budget as PreviousBudget
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as Memory

INTERVAL_SECONDS=10
WRITE_RESERVE_BYTES=4<<30

def observed_worker_rss(cap):
    # ru_maxrss can retain a fork parent's pre-exec peak. VmHWM belongs to
    # this actual exec lifetime, matching the observer PID/start-tick data.
    value=Memory.process_observation(os.getpid())
    parent=Memory.MONITOR is not None and Memory.MONITOR.pid==os.getpid()
    actual_cap=(56<<30)if parent else (3<<30)if cap in (1500000000,3<<30)else cap
    if value['high_water_bytes']>actual_cap:
        Memory.mark_stop('ACTUAL_EXEC_LIFETIME_RSS_CAP',dict(software_cap_bytes=actual_cap,worker=value))
    return value['high_water_bytes']

Memory.soft_worker_rss=observed_worker_rss

class Budget(PreviousBudget):
    def __init__(self,plan,proof,root):
        super().__init__(plan,proof,root)
        I.ACTIVE_CENSUS=self.census_context
        self.next_row_census=0

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
    # The parent monitors whole-output bytes, quota and wall time every ten
    # seconds. Workers retain immediate local STOP/RSS checks; they do not
    # each recursively stat every shared output file for every native row.
    Memory.soft_worker_rss(3<<30)
    C.need(not Memory.stop_requested(),'RESOURCE_STOP_BEFORE_NEXT_ROW')
    if additional:
        C.need(additional+WRITE_RESERVE_BYTES<control['cap'],'ONE_WRITE_WITHIN_OUTPUT_CAP')
