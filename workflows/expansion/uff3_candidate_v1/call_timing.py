"""Per-call metadata clocks; original kernel arguments/results stay untouched.

Timings join existing return events, with no extra scientific call or fsync.
Wall and process CPU measure the original method invocation. Unreturned calls
are retained on the existing cache/packet close event, never retried.
"""
import time


class CallTimings:
    def __init__(self, wall=time.perf_counter_ns, cpu=time.process_time_ns):
        self.wall=wall;self.cpu=cpu;self.pending={}

    def finish(self, operation, identifier, started_wall, started_cpu, error_type):
        wall=self.wall()-started_wall;cpu=self.cpu()-started_cpu
        if wall<0 or cpu<0:raise RuntimeError('NONNEGATIVE_NATIVE_CALL_CLOCK_REQUIRED')
        key=(operation,identifier)
        if key in self.pending:raise RuntimeError('UNCONSUMED_NATIVE_CALL_TIMING_NO_RETRY')
        self.pending[key]=dict(operation=operation,identifier=identifier,
            wall_nanoseconds=wall,process_CPU_nanoseconds=cpu,
            returned=error_type is None,error_type=error_type,
            measurement='original_kernel_method_invocation_not_journal_fsync')

    def annotate(self,event):
        phase=event.get('phase');key=None
        if phase=='graph_return':key=('prepare',None)
        elif phase=='embedding_return':key=('embed',None)
        elif phase=='optimizer_return':key=('optimize',event['candidate_id'])
        elif phase=='descriptor_return':key=('d3',event['conformer']['conformer_id'])
        timing=self.pending.pop(key,None)if key is not None else None
        if timing is not None:
            event=dict(event);event['native_call_timing']=timing
        if phase in ('cache_closed','packet_closed')and self.pending:
            event=dict(event)
            event['native_call_timings_without_matching_return']=list(self.pending.values())
            self.pending.clear()
        return event


class TimedKernel:
    def __init__(self,kernel,timings):self.kernel=kernel;self.timings=timings
    def __getattr__(self,name):return getattr(self.kernel,name)

    def _call(self,name,identifier,*args):
        wall=self.timings.wall();cpu=self.timings.cpu();error=None
        try:return getattr(self.kernel,name)(*args)
        except BaseException as exc:
            error=type(exc).__name__;raise
        finally:self.timings.finish(name,identifier,wall,cpu,error)

    def prepare(self,source):return self._call('prepare',None,source)
    def embed(self,seed,count):return self._call('embed',None,seed,count)
    def optimize(self,candidate_id):return self._call('optimize',candidate_id,candidate_id)
    def d3(self,row):return self._call('d3',row['conformer_id'],row)
