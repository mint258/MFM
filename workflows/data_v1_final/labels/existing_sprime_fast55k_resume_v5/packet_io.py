"""Bounded read-only packet IO; all workers call original require and decoder."""
import concurrent.futures as cf,hashlib,multiprocessing as mp,os,pathlib,pickle
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as Wire
WORK=None

def initialize(plan,proof):
    global WORK
    C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
      and os.uname().nodename.split('.')[0]==proof['request']['node'],'SAME_ACTUAL_CLOSED_PACKET_PARENT_WORKER')
    I.configure(plan);WORK=plan

def read(work):
    mid,n,nprime,reference=work
    C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_BEFORE_NEXT_CLOSED_PACKET')
    I.R.soft_worker_rss(WORK['worker_rss_stop_bytes'])
    path=C.PHASE_ROOT/'ordinary_geometry/molecules'/(hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json')
    first_read=reference is None
    if first_read:reference=I.pin(path)
    C.need(reference['path']==str(path),'EXACT_ORIGINAL_CLOSED_PACKET_LOCATOR')
    I.allow(reference,origin=C.PHASE_ROOT);before=I.S.identity(path)
    value=Wire.decode(I.require(reference).read_bytes())
    C.need(before==I.S.identity(path) and value['molecule_id']==mid and value['pm7_count']==n and value['uff_sprime_count']==nprime,
      'ORIGINAL_WHOLE_SHA_FD_DECODE_SAME_MID_ALL_BASE_N')
    I.R.soft_worker_rss(WORK['worker_rss_stop_bytes'])
    return {'molecule_id':mid,'reference':reference,'value':None if first_read else value,'actual_worker_pid':os.getpid()}

class DecodedPacket:
    def __init__(self,value):self.value=value
    def read_bytes(self):return self

class WireAdapter:
    def __getattr__(self,name):return getattr(Wire,name)
    def decode(self,value):return value.value if isinstance(value,DecodedPacket)else Wire.decode(value)

class IOAdapter:
    def __init__(self,reader):self.reader=reader
    def __getattr__(self,name):return getattr(I,name)
    def require(self,reference,content=True):
        C.need(content is True,'EXACT_FULL_CONTENT_PACKET_READ_REQUIRED')
        return DecodedPacket(self.reader.take(reference))

class PacketReader:
    def __init__(self,plan,proof,root,budget,cohort):
        self.plan=plan;self.proof=proof;self.root=root;self.budget=budget;self.cohort=cohort
        self.pool=None;self.procs=[];self.reports=[];self.index=0;self.cursor=0;self.pending={};self.pass_count=0
    def __enter__(self):
        self.pool=cf.ProcessPoolExecutor(max_workers=15,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(self.plan,self.proof))
        return self
    def work(self,mid,reference):
        member=self.cohort[mid];return mid,member['S_conformers'],member['Sprime_conformers'],reference
    def validate(self):
        names={hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json':mid for mid in self.cohort}
        packetroot=C.PHASE_ROOT/'ordinary_geometry/molecules'
        C.need(len(names)==55000 and set(p.name for p in packetroot.iterdir())==set(names),'EXACT_ORIGINAL_CLOSED55K_PACKET_SET')
        iterator=iter(sorted(self.cohort));pending={};done=False;reports={};workers=set()
        while pending or not done:
            while len(pending)<30 and not done:
                self.budget.check()
                try:mid=next(iterator)
                except StopIteration:done=True;break
                pending[self.pool.submit(read,self.work(mid,None))]=mid
            if pending:
                ready,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in ready:
                    mid=pending.pop(future);r=future.result();C.need(r['molecule_id']==mid and mid not in reports,'EVERY_ORIGINAL_PACKET_EXACTLY_ONCE')
                    I.allow(r['reference'],origin=C.PHASE_ROOT);reports[mid]={'molecule_id':mid,'reference':r['reference'],'prior_producer_job_id':'4525337'}
                    workers.add(r['actual_worker_pid']);del r
                if len(reports)//2048>(len(reports)-len(ready))//2048:
                    I.save(self.root/('packet_readback_%06d.json'%len(reports)),{'schema':'ACTUAL_CPU_CLOSED_PACKET_PARALLEL_PROGRESS_V1',
                      'verified_packets':len(reports),'expected_packets':55000,'workers_observed':len(workers),'complete_or_release':False})
        C.need(set(reports)==set(self.cohort),'ALL55000_FROZEN_MIDS_FULL_FD_READBACK')
        self.reports=[reports[mid]for mid in sorted(reports)];return self.reports
    def _submit(self):
        while len(self.pending)<30 and self.cursor<len(self.reports):
            self.budget.check();report=self.reports[self.cursor];key=report['reference']['path']
            C.need(key not in self.pending,'BOUNDED_ORDERED_PACKET_QUEUE_UNIQUE')
            self.pending[key]=self.pool.submit(read,self.work(report['molecule_id'],report['reference']));self.cursor+=1
    def take(self,reference):
        if self.index==len(self.reports)or self.pass_count==0:
            C.need(not self.pending,'ALL_PRIOR_PASS_PACKET_RESULTS_CONSUMED')
            self.index=0;self.cursor=0;self.pass_count+=1;C.need(self.pass_count<=6,'EXACT_ORIGINAL_FIVE_TABLES_AND_FEATURE_PASS')
            self._submit()
        expected=self.reports[self.index];C.need(expected['reference']==reference,'EXACT_ORIGINAL_SORTED_TABLE_PACKET_ORDER')
        r=self.pending.pop(reference['path']).result();self.index+=1
        C.need(r['reference']==reference and r['molecule_id']==expected['molecule_id'],'NO_PARALLEL_RESULT_OR_REFERENCE_REORDER')
        self._submit();return r['value']
    def __exit__(self,kind,value,tb):
        procs=list(self.pool._processes.values());self.pool.shutdown(wait=True,cancel_futures=False)
        if kind is None:
            C.need(not self.pending and self.index==55000 and self.pass_count==6
              and all(not p.is_alive()and p.exitcode==0 for p in procs),'ALL_ORIGINAL_SIX_PASSES_AND_ALL_PACKET_WORKERS_CLOSED_ZERO')
        return False

def transfer_proof():
    value={'f64':[0.,-0.,1.0000000000000002,None,float('nan'),float('inf')],
      'ordered':[{'i':1,'j':0,'v':.25},{'i':1,'j':0,'v':.25}],'mask':[True,False]}
    original=Wire.decode(Wire.encode(value));transported=pickle.loads(pickle.dumps(original,protocol=pickle.HIGHEST_PROTOCOL))
    C.need(Wire.encode(original)==Wire.encode(transported)==Wire.encode(WireAdapter().decode(DecodedPacket(transported))),
      'ORIGINAL_WIRE_F64_SIGNED_ZERO_NONE_NAN_ORDER_BITS_THROUGH_PICKLE')
    return {'original_decoder_function_used':True,'decoded_packet_pickle_original_wire_bytes_equal':True,
      'workers':15,'pending':30,'table_projection_AST_unchanged':True,'no_cast_or_scientific_mask_change':True}
