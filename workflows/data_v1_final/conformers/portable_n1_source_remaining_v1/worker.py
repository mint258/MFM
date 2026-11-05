"""Fresh endpoint/context plus unchanged original N1 callable; no old admission."""
import gzip,importlib,json,os,pathlib,socket,traceback
from . import contract as C,runtime as R,storage as S,io as I,science_port as P
from .source import proof as source_proof
CTX={}


def parent_continuation():
    binding=CTX['parent'];proc=pathlib.Path('/proc')/str(binding['pid']);fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    actual=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]
    C.need(os.getuid()==1264 and proc.stat().st_uid==1264 and fields[19]==binding['start_ticks']
        and R.boot()==binding['boot_id'] and actual==binding['actual_argv']
        and os.environ['SLURM_JOB_ID']==CTX['job_id'] and int(os.environ['SLURM_CPUS_PER_TASK'])==CTX['cpus']
        and socket.gethostname().split('.')[0]==CTX['node'],'ACTUAL_LIVE_NATIVE_PARENT_CONTINUATION_NOT_OLD_MAIN_GUARD')


def initialize(context):
    global CTX
    CTX=context;parent_continuation();source_proof()
    from portable_secondary_uff_v1 import bridge as B
    B.install_sources(context['legacy_deployment'],initialize_science=True)
    from importlib import metadata
    actual={**B.STATE['actual_versions'],'pyarrow':metadata.version('pyarrow')}
    C.need(all(actual[k]==v for k,v in context['expected_versions'].items()),'ACTUAL_ACCEPTED_ALPHA_ENVIRONMENT_BUILD')
    selection=importlib.import_module('selection');common=B.STATE['common'];core=B.STATE['core']
    recipe=common.load_config(context['legacy_deployment']['recipe_target_locator']['path'])
    stat=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    runtime={'job_id':context['job_id'],'uid':os.getuid(),'endpoint':context['endpoint']['address'],'node':context['node'],
        'pid':os.getpid(),'start_ticks':int(stat[19]),'boot_id':R.boot(),'allocated_cpus':context['cpus'],
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,'rdkit_version':B.STATE['actual_versions']['rdkit'],
        'seed_domain':'sprime-ETKDGv3-v1-n1-pprime2:'}
    P.initialize({'io':common,'science':core,'selection':selection,'recipe':recipe,'checkpoint_output_root':context['out'],
        'source_population_authority_reference':context['source_population_authority_reference'],
        'prepared_manifest_reference':context['prepared_manifest_reference'],'catalog_reference':context['catalog_reference'],
        'startup_proof_reference':context['startup_proof_reference'],'runtime':runtime})
    CTX.update(bridge=B,common=common,runtime=runtime)


def one(value,member,claim_reference):
    parent_continuation()
    task=CTX['bridge'].bind_envelope(value,member);C.validate_task(task,CTX['source_population_authority_reference'])
    C.need(task['task_key']==member['task_key']==C.task_key(member['molecule_id']) and C.reserve_task(task)==member['reservation_bytes'],'ORIGINAL_TASK_KEY_AND_RESERVATION')
    out=pathlib.Path(CTX['out']);I.TASK_STORE=I.TaskStore(out,task,member['reservation_bytes']);key=task['task_key']
    start=I.TASK_STORE.write(I.TASK_STORE.root/'worker_start.json',{'schema':'N1_FOREIGN_NATIVE_STARTED_V1','task_key':key,
        'native_claim_reference':claim_reference,'original_Main_assignment_claim_reference':value['original_Main_assignment_claim_reference'],
        'runtime':CTX['runtime'],'task_sha256':value['task_sha256'],'assignment_manifest_reference':CTX['assignment_manifest_reference']})
    try:
        saved=P.process_task(task) # direct unchanged science_port callable
        raw=C.canonical(saved);C.need(len(raw)<=C.PACK_RAW,'FULL_N1_PACKET_256MIB')
        packed=gzip.compress(raw,mtime=0);C.need(len(packed)<=C.PACK_COMPRESSED,'FULL_N1_COMPRESSED_PACKET_BOUND')
        packet=S.write(out,I.TASK_STORE.root/'packet.json.gz',packed,key);I.TASK_STORE.written+=len(packed)
        C.need(I.packet(packet,task,CTX['endpoint'],CTX['job_id'],CTX['common'].geometry_sha)==saved,'INDEPENDENT_FULL_N1_F64_EVENT_READBACK')
        result={'schema':'N1_FOREIGN_NATIVE_PACKET_DURABLE_V1','task_key':key,'molecule_id':member['molecule_id'],
            'packet_reference':packet,'worker_start_reference':start,'native_claim_reference':claim_reference,
            'original_Main_assignment_claim_reference':value['original_Main_assignment_claim_reference'],
            'summary':saved['summary'],'runtime':CTX['runtime'],'written_bytes':I.TASK_STORE.written,'automatic_retry':False}
        result_ref=I.TASK_STORE.write(I.TASK_STORE.root/'finished.json',result)
        return {**result,'finished_reference':result_ref}
    except BaseException as e:
        failure={'task_key':key,'error':repr(e),'traceback':traceback.format_exc(),'runtime':CTX['runtime'],
            'native_claim_reference':claim_reference,'automatic_retry':False,'science_result_unknown_not_retried':True}
        I.TASK_STORE.write(I.TASK_STORE.root/'failure.json',failure)
        raise
