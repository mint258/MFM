"""Finite CPU-only D6 copy/local-loader entry; node permission is never inferred."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,shutil,stat,time
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_name]='1'
from . import contract as C,io as I
from .store import Reader


def context(plan,proof_path):
    proof=C.Q.load(proof_path);review=C.meta(plan['actual_node_CPU_policy_reference'])
    C.need(review['schema']=='ROOT_D6_ACTUAL_NODE_CPU_ONLY_DELIVERY_POLICY_V1' and review['status']=='APPROVED_EXACT_NODE_CPU_TRANSFER_AND_LOADER'
        and review['reviewer']=='root' and review['node']==os.uname().nodename.split('.')[0]
        and review['no_GPU_allocation_or_training_or_Model_edit'] is True and review['actual_allocation_evidence_reference'],
        'MISSING_REAL_CPU_PERMISSION_ON_GPU_NODE_IS_NONEXECUTABLE_NOT_GENERIC_ANALYSIS_ALIAS')
    # A future node-local launcher must bind this precise CPU entry and actual
    # allocation. This module supplies no SSH, sbatch, GPU allocation or queue.
    C.need(proof['schema']=='ACTUAL_D6_CPU_ONLY_DELIVERY_STARTUP_V1' and proof['plan_reference']==C.Q.pin(plan['_plan_path'])
        and proof['node']==review['node'] and proof['uid']==os.getuid()==1278 and proof['cpus']==16
        and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and proof['CPU_only'] is True and proof['GPU_resources_requested']==0,'REAL_CPU16_ALLOCATION_NOT_LOGIN_OR_GPU_TRAINING')
    from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
    clock=wall_clock(proof,plan['wall_seconds']);C.need(remaining_wall(clock,time.monotonic())>900,'FINITE_TRANSFER_WALL_INCLUDES_DRAIN')
    argv=[C.PY,'-B','-m','workflows.data_v1_final.export.family_export_day_v1.transfer','--plan',plan['_plan_path'],'--startup-proof',str(proof_path)]
    import sys
    C.need(proof['execution_argv']==argv and sys.argv[1:]==argv[3:] and pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'transfer.py',
        'EXACT_ACTUAL_D6_PRIMARY_AND_FULL_ARGV')
    C.need(proof['actual_node_CPU_policy_reference']==plan['actual_node_CPU_policy_reference']
        and proof['source_references']==plan['source_references'],'ROOT_DECLARED_DELIVERY_SOURCE_SET')
    exact=C.meta(proof['exact_execution_review_reference'])
    C.need(exact['schema']=='ROOT_EXACT_D6_CPU_DELIVERY_EXECUTION_REVIEW_V1' and exact['status']=='APPROVED_EXACT_CPU_ENTRY'
        and exact['reviewer']=='root' and exact['plan_reference']==proof['plan_reference']
        and exact['execution_argv']==argv and exact['source_references']==plan['source_references']
        and exact['data_references']==plan['data_references'] and exact['output_directory']==plan['output_directory']
        and exact['output_cap_bytes']==plan['output_cap_bytes'],'SEPARATE_ROOT_EXACT_PLAN_SOURCE_DATA_AND_COPY_BUDGET')
    from datetime import datetime,timezone
    observed=datetime.fromisoformat(proof['root_observed_at'].replace('Z','+00:00'))
    C.need(observed.tzinfo is not None and 0<=(datetime.now(timezone.utc)-observed).total_seconds()<=120,'FRESH_ROOT_ACTUAL_LOCAL_CPU_PROOF')
    for r in plan['source_references']:C.need(C.Q.pin(r['path'])==r,'DELIVERY_SOURCE_OR_SMALL_RELEASE_CHANGED')
    boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();ticks=int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    C.need(proof['boot_id']==boot and proof['pid']==os.getpid() and proof['process_start_ticks']==ticks,'ACTUAL_SAME_PID_BOOT_TICKS_NO_DETACHED_OR_REUSED_PROOF')
    evidence=C.meta(review['actual_allocation_evidence_reference']);C.need(str(evidence['job_id'])==str(proof['job_id']) and evidence['node']==proof['node']
        and evidence['uid']==1278 and evidence['cpus']==16 and evidence['GPU_resources_requested']==0,'ROOT_TRUE_ALLOCATION_EVIDENCE_NOT_NODE_NAME_ALONE')
    return proof,clock


def copy_exact(reference,destination,check):
    p=pathlib.Path(destination);C.need(not p.exists() and not p.with_suffix(p.suffix+'.partial').exists(),'FRESH_LOCAL_COPY_NO_OVERWRITE_OR_AUTO_RETRY')
    temporary=p.with_suffix(p.suffix+'.partial');h=hashlib.sha256();size=0
    with I.held(reference,[reference],check) as (_,fd,_):
        with os.fdopen(os.dup(fd),'rb') as source,temporary.open('xb') as target:
            while True:
                block=source.read(1<<20)
                if not block:break
                check();target.write(block);h.update(block);size+=len(block)
            target.flush();os.fsync(target.fileno())
    C.need(size==reference['bytes'] and h.hexdigest()==reference['sha256'],'COPY_EOF_AND_COMPLETE_SHA')
    os.rename(temporary,p);ref=I.actual_ref(p);C.need(ref['bytes']==reference['bytes'] and ref['sha256']==reference['sha256'],'LOCAL_CPU_REOPEN_WHOLE_SHA')
    return ref


def run(plan,proof,clock):
    from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import remaining_wall
    release=C.meta(plan['accepted_export_reference']);C.need(release['schema']=='ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1' and release['consumer_release'] is True,
        'ACTUAL_EXTERNAL_C0_EXPORT_RELEASE_REQUIRED')
    root=pathlib.Path(plan['output_directory']);C.need(str(root).startswith('/tmp/') and '..' not in root.parts and not root.exists()
        and not any(p.is_symlink() for p in root.parents),'FRESH_LITERAL_NODE_LOCAL_TMP_ROOT');root.mkdir(parents=True,mode=0o700)
    cap=plan['output_cap_bytes'];C.need(type(cap) is int and cap>0,'FINITE_LOCAL_COPY_CAP');used=0
    def check():
        C.need(remaining_wall(clock,time.monotonic())>900,'STOP_NEW_COPY_WORK_NATURAL_DRAIN')
        v=os.statvfs(root);C.need(v.f_bavail*v.f_frsize-max(0,cap-used)>=plan['local_disk_reserve_bytes'],'ACTUAL_TMP_AVAILABLE_SPACE_AND_DECLARED_REMAINDER')
        C.need(used<=cap,'FINITE_LOCAL_COPY_OUTPUT_CAP')
    catalogue=release['stores_catalogue_reference'];C.need(catalogue in plan['data_references'],'ORIGINAL_CPU_DATA_CATALOGUE_DECLARED');copies=[];stores=[]
    for store in I.jsonl(catalogue,plan['data_references'],check):
        local=root/store['name'];local.mkdir();check()
        for key,filename in (('data','data.mdb'),('manifest','manifest.json')):
            r=store[key];C.need(r in plan['data_references'] or plan['transitive_source_catalogue_authority']==catalogue,'EXACT_RELEASED_TRANSITIVE_STORE_OBJECT_ONLY')
            C.need(used+r['bytes']<=cap,'NO_PARTIAL_COPY_CLAIMED_COMPLETE');copy=copy_exact(r,local/filename,check);used+=copy['bytes'];copies.append({'origin':r,'local':copy})
        with Reader(local) as reader:C.need(reader.count==store['records'] and reader.molecule_count==store['molecules'],'LOCAL_LMDB_EXACT_ALL_COUNTS_SCHEMA_AND_CLOSED_HANDLES')
        stores.append(dict(store,path=str(local)))
    C.need(stores,'NONEMPTY_ACTUAL_D6_TRANSFER');I.data_json_new(root/'copy_inventory.DATA.json',copies)
    # The same actual spawn reader object used by D3; one whole-MID queue per
    # worker, every required local family/conformer read and every PID joined.
    from . import verify
    import multiprocessing as mp,concurrent.futures as cf
    queues=[[] for _ in range(16)];mids=[]
    for store in stores:
        with Reader(store['path']) as reader:
            with reader.env.begin() as tx,tx.cursor(db=reader.molecules) as cursor:
                for key,_ in cursor:
                    mid=key.decode()
                    if mid not in mids:mids.append(mid)
                    if len(mids)>=16:break
        if len(mids)>=16:break
    C.need(len(mids)==16,'SIXTEEN_ACTUAL_LOCAL_MOLECULES')
    for i,mid in enumerate(mids):
        records=[]
        for store in stores:
            with Reader(store['path']) as reader:records.extend((store['path'],gid) for gid in reader.records_for_molecule(mid))
        queues[i]=[(mid,records)]
    ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);start=time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=verify.read_initializer,initargs=(barrier,)) as pool:
        results=list(pool.map(verify.molecule_reader,enumerate(queues),chunksize=1))
    seconds=time.monotonic()-start;C.need(len({r['pid'] for r in results})==16 and all(r['all_handles_closed'] for r in results),'ACTUAL_LOCAL_16_SPAWN_READERS_CLOSED')
    import psutil
    for r in results:
        try:alive=psutil.Process(r['pid']).create_time()==r['process_start']
        except psutil.NoSuchProcess:alive=False
        C.need(not alive,'LOCAL_READER_PROCESSES_NATURALLY_JOINED')
    return I.data_json_new(root/'receipt.json',{'schema':'ACTUAL_D6_NODE_LOCAL_CPU_LOADER_RECEIPT_V1','status':'LOCAL_COPY_SHA_COUNTS_AND16SPAWN_CLOSED_PENDING_ROOT',
        'accepted_export_reference':plan['accepted_export_reference'],'actual_node':proof['node'],'actual_parent_job_id':str(proof['job_id']),
        'local_copied_bytes':used,'actual_tmp_statvfs':list(os.statvfs(root)),'molecules_per_second_including_startup':16/seconds,
        'records_per_second_including_startup':sum(r['records'] for r in results)/seconds,'workers':results,
        'Model_loader_ACK':False,'GPU_requested_or_used':False,'training_started':False,'root_acceptance_required':True})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);plan=dict(plan,_plan_path=a.plan);proof,clock=context(plan,a.startup_proof);print(run(plan,proof,clock))

if __name__=='__main__':main()