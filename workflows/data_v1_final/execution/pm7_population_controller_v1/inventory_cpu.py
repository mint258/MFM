"""Independent CPU metadata inventory; lstat/scandir only, no payload reads."""
from __future__ import annotations
import argparse,hashlib,os,pathlib,socket,stat,sys,time
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO))
from workflows.data_v1_final.execution.pm7_population_controller_v1 import contract as C
from workflows.data_v1_final.execution.pm7_population_controller_v1.controller import source_inventory
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import metadata as M,contract as P
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import PY
SCOPE='pm7_existing247_final_metadata_inventory_v1'
PARAMETERS={'stage':'PM7_EXISTING247_FINAL_PREFIX_METADATA_INVENTORY','existing_shards':247,'content_reads':0,
    'directory_scope':'PM7_POPULATION_CACHE_V1_ENTIRE_PREFIX_INCLUDING_CLAIMS_AND_PREVIOUS_PARTIALS',
    'logical_size_basis':'LSTAT_ST_SIZE','allocated_size_basis':'CPU_FILESYSTEM_REPORTED_ST_BLOCKS_TIMES512',
    'common':False,'full_cache_release':False,'new_QM_calls':0,'new_UFF_calls':0}


def scan(root,observe):
    digest=hashlib.sha256();logical=allocated=files=directories=0;seen=set();unique_logical=unique_allocated=0
    stack=[root]
    while stack:
        C.need(files+directories<20000000,'FINITE_MAXIMUM_METADATA_OBJECTS_REACHED')
        path=stack.pop();info=path.lstat();C.need(info.st_uid==1278 and not stat.S_ISLNK(info.st_mode),'OWN_PREFIX_NO_SYMLINK_OR_FOREIGN_OBJECT')
        C.need(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode),'ORDINARY_FILES_AND_DIRECTORIES_ONLY')
        frame=[str(path.relative_to(root)),info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_uid,info.st_size,info.st_mtime_ns,info.st_ctime_ns,getattr(info,'st_blocks',None)]
        digest.update(C.canonical(frame)+b'\n')
        if stat.S_ISDIR(info.st_mode):
            directories+=1
            if directories%512==0:observe()
            children=[]
            with os.scandir(path) as entries:
                for entry in entries:
                    children.append(pathlib.Path(entry.path));C.need(len(children)<=2000000,'FINITE_DIRECTORY_ENTRY_WORKING_SET')
                    if len(children)%4096==0:observe()
            children.sort(reverse=True)
            stack.extend(children)
        else:
            C.need(hasattr(info,'st_blocks'),'ACTUAL_CPU_FILESYSTEM_ALLOCATED_BLOCKS_REQUIRED')
            files+=1;logical+=info.st_size;allocated+=info.st_blocks*512;identity=(info.st_dev,info.st_ino)
            if identity not in seen:unique_logical+=info.st_size;unique_allocated+=info.st_blocks*512;seen.add(identity)
            if files%512==0:observe()
    return dict(files=files,directories=directories,path_logical_bytes=logical,path_filesystem_reported_allocated_bytes=allocated,
        unique_inode_count=len(seen),unique_inode_logical_bytes=unique_logical,unique_inode_filesystem_reported_allocated_bytes=unique_allocated,
        stat_frame_sha256=digest.hexdigest(),file_content_reads=0,allocated_bytes_are_filesystem_reported_not_storage_backend_guarantee=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=pathlib.Path)
    p.add_argument('--root-preflight',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);args=p.parse_args()
    # Only source/small locator metadata is read before fresh actual admission.
    plan_ref=M.pin(args.plan);plan=M.actual(plan_ref)
    C.need(REPO==C.REPO and C.HERE==C.REPO/'workflows/data_v1_final/execution/pm7_population_controller_v1'
        and plan['schema']=='ROOT_PM7_EXISTING247_FINAL_INVENTORY_PLAN_V1' and plan['status']=='APPROVED_METADATA_INVENTORY_ONLY'
        and plan['reviewer']=='root' and plan['endpoint']=='202.38.247.57:22' and plan['uid']==1278
        and plan['prefix']==str(P.BASE) and plan['output']==str(args.output) and plan['scope_parameters']==PARAMETERS
        and type(plan['other_future_output_reserve_bytes']) is int and plan['other_future_output_reserve_bytes']>=0,'EXACT_NEW_ROOT_INVENTORY_PLAN')
    C.need(C.RUN/'artifacts' in args.output.parents and not args.output.exists() and '..' not in args.output.parts
        and P.BASE not in args.output.parents,'NEW_INVENTORY_OUTSIDE_OBSERVED_PREFIX')
    proof=runtime.require_startup(args.root_preflight,expected_scope_key=SCOPE,expected_scope_parameters=PARAMETERS,
        expected_execution_argv=[PY,'-B',str(C.HERE/'inventory_cpu.py'),*sys.argv[1:]],expected_source=__file__,expected_kind='analysis',
        required_references=(plan_ref,*plan['source_references'],plan['all247_retired_state_reference'],plan['provider_review_reference'],plan['publisher_identity_reference']))
    request=proof['request'];C.need(request['node']=='compute-0-13' and request['cpus']==16 and request['pilot'] is False
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['stage_output_cap_bytes']==C.INVENTORY_CAP
        and 600<=request['wall_seconds']<=7200 and os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-13','REAL_CPU16_NO_MEMORY_FINITE_INVENTORY')
    expected_sources=source_inventory()
    C.need(all(r in plan['source_references'] for r in expected_sources),'ALL_NEW_INVENTORY_SOURCES_AUTHORIZED')
    state=M.actual(plan['all247_retired_state_reference']);C.need(C.inventory_ready(state),'ACTUAL_ALL247_SAFE_RETIREMENT_BEFORE_FINAL_INVENTORY')
    quota=Q.Client(plan['provider_review_reference'],request);began=time.monotonic();last=0;last_quota=None
    args.output.mkdir(mode=0o700);report={'schema':'ACTUAL_PM7_EXISTING247_PREFIX_METADATA_INVENTORY_V1','status':'INVENTORY_PENDING',
        'job_id':proof['job_id'],'uid':1278,'node':request['node'],'endpoint':'202.38.247.57:22','plan_reference':plan_ref,
        'all247_retired_state_reference':plan['all247_retired_state_reference'],'prefix':str(P.BASE),'scientific_payloads_opened':0,
        'common':False,'full_cache_release':False,'physical_ID_release':False}
    def observe(force=False):
        nonlocal last,last_quota
        C.need(time.monotonic()-began<request['wall_seconds']-120,'BOUNDED_INVENTORY_STOP_NO_SIGNALS')
        status=pathlib.Path('/proc/self/status').read_text().splitlines();mem=pathlib.Path('/proc/meminfo').read_text().splitlines()
        rss=int(next(line.split()[1] for line in status if line.startswith('VmRSS:')))*1024
        available=int(next(line.split()[1] for line in mem if line.startswith('MemAvailable:')))*1024
        C.need(rss<=8<<30 and available>=4<<30,'INVENTORY_MEMORY_SOFT_STOP_NO_SIGNALS')
        if force or time.monotonic()-last>=60:
            last_quota=quota.observe();last=time.monotonic()
            C.need(last_quota['identity_reference']==plan['publisher_identity_reference']
                and last_quota['free_bytes']-plan['other_future_output_reserve_bytes']-Q.CAP-C.INVENTORY_CAP>=200000000000,'CURRENT_SHARED200GB_PLUS_ALL_FUTURE_RESERVES')
    code=0
    try:
        observe(True);a=scan(P.BASE,observe);observe(True);b=scan(P.BASE,observe)
        C.need(a==b,'PREFIX_STAT_INVENTORY_CHANGED_PRESERVE_UNKNOWN_NO_FAKE_FINAL_BYTES')
        report.update(status='ACTUAL_STABLE_CPU_PREFIX_INVENTORY_ROOT_REVIEW_REQUIRED',inventory=b)
    except Exception as exc:report.update(status='PENDING_INVENTORY_FAILURE_NO_RELEASE',error=repr(exc));code=3
    finally:
        report.update(elapsed_seconds=time.monotonic()-began,last_quota=last_quota,stop_has_no_science_signals=True)
        M.write(args.output/'inventory.json',report)
    return code


if __name__=='__main__':sys.exit(main())
