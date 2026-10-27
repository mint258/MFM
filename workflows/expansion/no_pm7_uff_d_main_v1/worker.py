"""One global new-source claim,no old ledger/no QM,no retry;durable cache packet."""
import math,os,pathlib,stat,time,traceback
from . import contract as C,io as I,core
Q=C.Q;EVENT=None;CATALOG=None
def init(event,catalog,barrier,initializations):
    global EVENT,CATALOG
    EVENT=event;CATALOG=catalog
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import platform
    Q.need(platform.python_version()=='3.11.14','FROZEN_SAMPLER_PYTHON31114')
    core.load()
    barrier.wait(timeout=120)
    initializations.put({'pid':os.getpid(),'pid_start_ticks':I.ticks(os.getpid()),'uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID']})
def warm():return os.getpid()
def one(source,claim_ref,session,domain):
    plan=I.continuation(session);claim=C.meta(claim_ref);recipe=C.fingerprint(CATALOG);key=C.once(plan['ranking_receipt_reference']['sha256'],recipe,source)
    Q.need(claim['once_key']==key and claim['source_row_sha256']==source['source_row_sha256'] and claim['job_id']==session['job_id']
        and claim['recipe_fingerprint']==recipe and claim['startup_proof_reference']==session['startup_proof_reference'],'EXACT_SOURCE_RECIPE_CURRENT_JOB_ONCE_INTENT')
    root=C.CACHE/domain/key[:2]/key;Q.need(root.name==key and all(c in '0123456789abcdef' for c in key) and C.CACHE in root.parents,'SAFE_HASH_ONLY_CACHE_PATH')
    root.mkdir(parents=True,exist_ok=False,mode=0o700);store=I.Store(root,256<<20);journal=I.Journal(root/'candidate_journal.inflight',128<<20);result=None
    start=store.json(root/'worker_start.json',{'once_key':key,'pid':os.getpid(),'pid_start_ticks':I.ticks(os.getpid()),'job_id':session['job_id'],
        'uid':os.getuid(),'node':session['node'],'boot_id':session['boot_id'],'source_row_sha256':source['source_row_sha256'],'claim_reference':claim_ref})
    store.reserve(128<<20)  # entire transient/raw journal,not a scratch hard limit
    try:
        journal.write({'phase':'source_before_native','source':source,'claim_reference':claim_ref,'worker_start_reference':start,'PM7_context':None})
        Q.need(not EVENT.is_set(),'NO_NEW_MOLECULE_NATIVE_WORK_AFTER_SOFT_STOP')
        result=core.process(source,journal,EVENT,compat=plan['mode']=='compat',checkpoint=lambda:I.live_parent(session))
    except BaseException as exc:
        EVENT.set();result={'molecule_id':C.new_mid(source['pubchem_version'],source['cid'],source['full_key']),'source':source,'state':'TECHNICAL_UNKNOWN',
            'error':repr(exc),'traceback':traceback.format_exc(),'D20':None,'conformers':[],'orders':{},'audit_sample':False,
            'optimizer_attempted':None,'optimizer_returned':None,'raw_candidates_complete':False}
    finally:journal.close()
    I.live_parent(session);raw_ref=I.seal_closed_output(journal.path,_ReservedClose());result.update(schema='NO_PM7_UFF_D_CACHE_PACKET_V1',once_key=key,recipe_fingerprint=recipe,
        ranking_receipt_reference=plan['ranking_receipt_reference'],producer_job_id=session['job_id'],producer_node=session['node'],producer_uid=1278,
        claim_reference=claim_ref,worker_start_reference=start,producer_plan_reference=session['plan_reference'],producer_startup_proof_reference=session['startup_proof_reference'],
        raw_candidate_journal_reference=raw_ref,raw_journal_frames=journal.rows,dataset_version='v2_candidate',training_eligible=False)
    # Failures and deterministic1% retain ALL native events/coordinates so far.
    # Successful nonaudit raw is a newly owned transient,removed only AFTER a
    # full packet commit;no old cache/ledger/source is ever changed or removed.
    graph_ok=result.get('D20') is not None and all(result['D20']['valid_mask']);labels_ok=graph_ok and bool(result['conformers'])
    for row in result['conformers']:
        d=row['D3'];labels_ok &= not row['D3_issues'] and all(d.get(n) is not None and math.isfinite(d[n]) for n in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2'))
        labels_ok &= d.get('SASA_atom_A2') is not None and len(d['SASA_atom_A2'])==len(result['atomic_numbers']) and all(math.isfinite(v) for v in d['SASA_atom_A2'])
    keep=result['state']!='SUCCESS' or not labels_ok or result.get('audit_sample',False)
    result['raw_candidate_journal_reference']=raw_ref if keep else None
    result['success_nonaudit_transient_journal_SHA']=None if keep else raw_ref['sha256']
    result['raw_retention']='FAILED_OR_PROPERTY_UNKNOWN_OR_HASH1PCT_ALL_EVENTS' if keep else 'NEW_OWN_TRANSIENT_REMOVE_ONLY_AFTER_PACKET_COMMIT'
    result['label_state']='D20_ONLY_D3_UNAVAILABLE' if graph_ok and not result['conformers'] else 'COMPLETE_FLOAT64_VALUES_FOR_ACTUAL_GEOMETRIES' if labels_ok else 'PROPERTY_UNKNOWN_PRESERVED'
    packet=I.packet(store,root/'packet.json.gz',result)
    if not keep:
        info=journal.path.lstat();Q.need(journal.path.parent==root and stat.S_ISREG(info.st_mode) and info.st_uid==1278 and not journal.path.is_symlink()
            and info.st_size==raw_ref['bytes'],'ONLY_THIS_NEW_OWNED_TRANSIENT_JOURNAL_CLEANUP')
        journal.path.unlink()
    terminal=store.json(root/'terminal.json',{'schema':'NO_PM7_UFF_D_CACHE_TERMINAL_V1','once_key':key,'source_ordinal':source['ordinal'],
        'packet_reference':packet,'raw_journal_kept':keep,'raw_reference':raw_ref if keep else None,'removed_new_transient_SHA':None if keep else raw_ref['sha256'],
        'producer_job_id':session['job_id'],'claim_reference':claim_ref,'automatic_retry':False,'state':result['state'],'label_state':result['label_state']})
    size=sum(p.stat().st_size for p in root.iterdir() if p.is_file())+claim_ref['bytes'];Q.need(size<=256<<20,'QUIESCENT_PRIVATE_CACHE256M')
    return {'ordinal':source['ordinal'],'once_key':key,'terminal_reference':terminal,'packet_reference':packet,'state':result['state'],
        'new_cache_bytes':size,'worker_pid':os.getpid(),'compatibility':result.get('compatibility'),'optimizer_attempted':result.get('optimizer_attempted'),
        'optimizer_returned':result.get('optimizer_returned'),'conformers':len(result['conformers']),'worker_cpu_seconds':result.get('worker_cpu_seconds')}
class _ReservedClose:
    # seal_closed_output observes only this already closed new private journal;
    # parent owns the full reserved256M and actual quota/RSS monitor.
    def check(self,*args,**kwargs):pass
