"""Stable atomic Store, same live parent continuation and quiescent-only inventory."""
import json,os,pathlib,socket,stat
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store,claim_create,ticks
from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1.run import body
from . import contract as C
Q=C.Q
def continuation(session):
    Q.need(os.getppid()==session['parent_pid'] and ticks(os.getppid())==session['parent_ticks'] and os.getuid()==1278
        and os.environ.get('SLURM_JOB_ID')==session['job_id'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and socket.gethostname().split('.')[0]==session['node'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],
        'SAME_LIVE_ADMITTED_PARENT_BOOT_TICKS_JOB_NODE_NOT_FAKE_FRESHNESS')
    for r in session['source_references']:Q.need(Q.pin(r['path'])==r,'FROZEN_SOURCES_OR_AUTHORITY_CHANGED')
    plan=C.meta(session['plan_reference']);C.require_user(plan);return plan
def task(reference,expected,plan):
    value=json.loads(body(reference,1<<20));qa=expected['qa_id'];root=pathlib.Path(plan['prepared20_reference']['path']).parent
    Q.need(reference['path']==str(root/'tasks'/(qa+'.DATA.json')) and value['schema']=='PPRIME_NEW20_ALL12_RENDERED_TASK_V1'
        and value['qa_id']==qa and value['molecule_id']==expected['molecule_id'] and value['condition']==expected['condition'] and value['arm']==expected['arm']
        and value['case']['case_id']==qa and value['case']['arm']==value['arm'] and value['case']['condition']==value['condition']
        and value['case']['molecule_id']==value['molecule_id'] and value['case']['row']['molecule_id']==value['molecule_id']
        and value['case']['geometry_source']=='uff_sprime' and 1<=len(value['case']['symbols'])<=80
        and value['candidate_protocol_reference']==plan['candidate_protocol_reference'] and value['original_protocol_reference']==plan['original_protocol_reference'],
        'EXACT_PRODUCER_TASK_CELL_SAME_MID_ATOM_ORDER_AND_PROTOCOL')
    refs=value['target_input_references'];names={'input.xyz','input.mop'} if value['candidate_task']['family']=='mopac' else {'input.xyz','native.inp'}
    Q.need(len(refs)==len(names) and {pathlib.Path(r['path']).name for r in refs}==names,'EXACT_PREPARED_INPUT_NAMES')
    for r in refs:
        C.O.triple(r);Q.need(pathlib.Path(r['path'])==root/'candidate_targets'/qa/pathlib.Path(r['path']).name,'SIGNED_PRODUCER_DESCENDANT_INPUT_REFERENCE_NO_ARBITRARY_PATH')
    return value
def quiescent(folder):
    total=0;rows=[]
    for p in sorted(pathlib.Path(folder).rglob('*')):
        info=p.lstat();Q.need(info.st_uid==1278 and not stat.S_ISLNK(info.st_mode) and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),'ONLY_OWN_QUIESCENT_WORKER_OUTPUT')
        if stat.S_ISREG(info.st_mode):
            Q.need(not p.name.endswith(('-journal','-wal','-shm')),'QUIESCENT_RAW_NO_SQLITE_SIDECAR')
            total+=info.st_size;rows.append({'relative_path':str(p.relative_to(folder)),'bytes':info.st_size})
    return total,rows
