"""New storage namespace; exact day-v3 checkpoint protocol, truthful native UID."""
import gzip,json,os,pathlib,socket
from . import contract as C,storage as S
TASK_STORE=None


class TaskStore:
    def __init__(self,out,task,cap):
        self.out=pathlib.Path(out);self.key=task['task_key'];self.root=self.out/'tasks'/self.key;self.cap=cap;self.written=0
    def write(self,path,value):
        raw=C.canonical(value)+b'\n';C.need(self.written+len(raw)<=self.cap,'COMPLETE_TASK_BYTES_CAP_NO_TRUNCATION')
        result=S.write(self.out,path,raw,self.key);self.written+=len(raw);return result


def event_checkpoint(out,task,name,value):
    C.need(TASK_STORE is not None and TASK_STORE.root.parent.parent==pathlib.Path(out),'ACTUAL_ISOLATED_TASK_STORE')
    return TASK_STORE.write(TASK_STORE.root/'events'/(name+'.json'),{'schema':'N1_DAY_ACTUAL_EVENT_V1','task_key':task['task_key'],'job_id':os.environ['SLURM_JOB_ID'],
      'uid':os.getuid(),'pid':os.getpid(),'node':socket.gethostname(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'value':value})


class EmbeddingJournal(list):
    def __init__(self,out,task):super().__init__();self.out=out;self.task=task;self.closed=set()
    def append(self,event):self.flush_last();super().append(event);event_checkpoint(self.out,self.task,'embedding_%02d_started'%len(self),event)
    def flush_last(self):
        if self and len(self) not in self.closed:event_checkpoint(self.out,self.task,'embedding_%02d_observed'%len(self),self[-1]);self.closed.add(len(self))


def packet(reference,task,endpoint,job,geometry_sha):
    path=C.verify(reference,C.PACK_COMPRESSED)
    with gzip.open(path,'rb') as stream:
        raw=stream.read(C.PACK_RAW+1);C.need(len(raw)<=C.PACK_RAW and stream.read(1)==b'','FULL_PACKET_CRC_EOF')
    value=json.loads(raw);C.validate_task(task,task['authority_references']['source_population_authority'])
    C.need(value['schema']=='N1_PPRIME2_PILOT_GENERATION_PACKET_V2' and value['task_key']==task['task_key']
        and value['summary']['molecule_id']==task['meta']['molecule_id'] and value['source_population_authority_reference']==task['authority_references']['source_population_authority']
        and value['common']is False and value['production_membership']is False and value['final_common_reference']is None,'ORIGINAL_N1_PACKET_ID_SOURCE_AND_NO_RELEASE')
    runtime=value['runtime'];C.need(runtime['uid']==endpoint['uid'] and str(runtime['job_id'])==str(job)
        and type(runtime['pid'])is int and runtime['pid']>0 and type(runtime['start_ticks'])is int and runtime['start_ticks']>0
        and runtime['boot_id'] and runtime['endpoint']==endpoint['address'],'TRUE_NATIVE_ENDPOINT_NOT_A_MAIN_UID_FICTION')
    z=task['source_atomic_numbers'];old=value['baseline_original_row'];b=value['baseline_identity']
    if b is not None:
        C.need(old==task['existing_conformers'][0] and C.value_sha(old)==task['baseline_row_sha256']==b['full_original_row_sha256']
            and geometry_sha(z,old['coordinates'])==b['geometry_sha256'] and b['geometry_id']==task['baseline_geometry_id']
            and b['original_sprime_conf_idx']==old['sprime_conf_idx'],'EXACT_ORIGINAL_BASELINE_ROW_F64_AND_PHYSICAL_ID')
    for event in value['candidate_optimizer_events']:
        if event['finite']:C.need(geometry_sha(z,event['coordinates'])==event['geometry_sha256'],'ALL_RETAINED_CANDIDATE_F64_SHA')
    extra=value['supplement']
    if extra is not None:
        C.need(b is not None and extra['atomic_numbers']==z and geometry_sha(z,extra['coordinates'])==extra['geometry_sha256']!=b['geometry_sha256']
            and extra['seed']==C.proposed_seed(task['meta']['molecule_id']) and extra['source_record_id']==task['records'][0]['record_id']
            and extra['baseline_geometry_id']==task['baseline_geometry_id'],'REAL_SECOND_F64_NOT_AN_ALIAS_OR_DIFFERENT_SEED')
        events=[e for e in value['candidate_optimizer_events'] if e['candidate_key']==extra['optimizer_event_key']]
        C.need(len(events)==1,'ONE_REAL_SECOND_OPTIMIZER_EVENT');event=events[0]
        C.need(event['optimizer_called']is True and event['optimization_finished']is True and event['geometry_readback_finished']is True
            and event['finite']is True and event['stereo_valid']is True and event['optimizer_code']==0
            and event['coordinates']==extra['coordinates'] and event['geometry_sha256']==extra['geometry_sha256']
            and event['energy']==extra['uff_energy_kcal_mol'],'FULL_FINISHED_NATIVE_EVENT_FOR_EXTRA')
    return value
