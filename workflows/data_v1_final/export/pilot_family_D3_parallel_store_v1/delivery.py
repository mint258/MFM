"""One checksum rsync and one bounded CPU-only local read window."""
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,random,shlex,socket,subprocess,time
from . import contract as C,io as I
from workflows.data_v1_final.export.family_export_day_v1.store import Reader

RESERVE_BYTES=100000000000

def _write(path,value):
    with pathlib.Path(path).open('xb')as stream:
        stream.write((json.dumps(value,separators=(',',':'),ensure_ascii=False)+'\n').encode());stream.flush();os.fsync(stream.fileno())

def _json_output(value):
    for line in reversed(value.splitlines()):
        try:result=json.loads(line)
        except (ValueError,TypeError):continue
        if isinstance(result,dict):return result
    raise ValueError('REMOTE_JSON_RESULT_MISSING')

def _call(argv,budget=None,timeout=None):
    started=time.monotonic()
    with subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)as process:
        while True:
            try:stdout,stderr=process.communicate(timeout=1);break
            except subprocess.TimeoutExpired:
                if budget is not None:budget.check(dispatch=False)
                if timeout is not None and time.monotonic()-started>timeout:
                    process.kill();stdout,stderr=process.communicate()
                    return dict(argv=argv,returncode=124,stdout=stdout[-131072:],stderr=stderr[-131072:],elapsed_seconds=time.monotonic()-started)
    return dict(argv=argv,returncode=process.returncode,stdout=stdout[-131072:],stderr=stderr[-131072:],elapsed_seconds=time.monotonic()-started)

def _remote_command(node,arguments,timeout=False):
    env=['CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1',
      'PYTHONPATH='+str(C.REPO)+(':'+os.environ['PYTHONPATH']if os.environ.get('PYTHONPATH')else '')]
    command=['env',*env,C.PY,'-B','-m',__package__+'.delivery',*arguments]
    if timeout:command=['timeout','--kill-after=5s','280s',*command]
    return ['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=20',node,shlex.join(command)]

def preflight(directory,required,node):
    path=pathlib.Path(directory);actual=socket.gethostname().split('.')[0]
    C.need(actual==node and node in ('compute-0-20','compute-0-21')and os.getuid()==1278,'EXACT_OWN_GPU_HOST_CPU_IO')
    C.need(path.is_absolute()and str(path).startswith('/tmp/')and '..'not in path.parts
      and not any(q.is_symlink()for q in (path,*path.parents)),'LITERAL_NODE_LOCAL_DESTINATION')
    if path.exists():C.need(path.is_dir()and path.stat().st_uid==1278,'OWN_EXISTING_DELIVERY_DIRECTORY')
    mounts=[]
    for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);mount=pathlib.Path(left.split()[4].replace('\\040',' '))
        if path.is_relative_to(mount):mounts.append((len(mount.parts),right.split()[0],line))
    C.need(mounts and max(mounts)[1]in ('xfs','ext4','btrfs','zfs','f2fs'),'PHYSICAL_LOCAL_TMP_NOT_NETWORK_OR_TMPFS')
    space=os.statvfs('/tmp');available=space.f_bavail*space.f_frsize
    C.need(available-required>=RESERVE_BYTES,'TMP_CAPACITY_WITH100GB_REMAINING')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return dict(status='READY',node=actual,uid=os.getuid(),tmp_available_bytes=available,required_copy_bytes=required,
      reserve_bytes=RESERVE_BYTES,mountinfo=max(mounts)[2],GPU_used=False)

def _reader_work(root,items,deadline,seed):
    cache=collections.OrderedDict();rng=random.Random(seed);molecules=records=0
    try:
        while time.monotonic()<deadline:
            mid,requests=rng.choice(items);complete=True
            for relative,gid in requests:
                if time.monotonic()>=deadline:complete=False;break
                if relative not in cache:
                    if len(cache)>=16:cache.popitem(last=False)[1].close()
                    cache[relative]=Reader(pathlib.Path(root)/relative)
                cache.move_to_end(relative);cache[relative].get(gid);records+=1
            if complete:molecules+=1
    finally:
        for reader in cache.values():reader.close()
    return dict(pid=os.getpid(),molecules=molecules,records=records,all_handles_closed=True)

def benchmark(work_path,seconds):
    C.need(0<seconds<=240 and os.environ.get('CUDA_VISIBLE_DEVICES')in ('','-1'),'BOUNDED_CPU_ONLY_BENCHMARK')
    work=json.loads(pathlib.Path(work_path).read_text());root=str(pathlib.Path(work_path).parent)
    C.need(work['molecules']and len(work['molecules'])<=64,'ONE_RANDOM_MID_WORK_WINDOW')
    started=time.monotonic();deadline=started+seconds
    with cf.ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'))as pool:
        futures=[pool.submit(_reader_work,root,work['molecules'],deadline,20261025+i)for i in range(4)]
        results=[future.result()for future in futures]
    elapsed=time.monotonic()-started
    return dict(status='COMPLETE',node=socket.gethostname().split('.')[0],workers=4,worker_results=results,
      duration_seconds=elapsed,requested_seconds=seconds,molecules_per_second=sum(r['molecules']for r in results)/elapsed,
      records_per_second=sum(r['records']for r in results)/elapsed,distinct_sample_MIDs=len(work['molecules']),
      cache_state='AFTER_SINGLE_RSYNC_CHECKSUM_NO_CACHE_FLUSH',GPU_used=False,extra_field_QA=False,extra_hash=False)

def run(plan,proof,root,db,stores,manifest,budget):
    """Return honest distribution/benchmark dicts; never repeat either action."""
    root=pathlib.Path(root);node=plan['gpu_node'];destination=plan.get('gpu_output_directory')or '/tmp/dv1_pilot55k_'+str(proof['job_id'])
    distribution=dict(status='FAILED',node=node,directory=destination,checksum_method='rsync --checksum',extra_postcopy_hash=False)
    performance=dict(status='NOT_RUN',molecules_per_second=None,records_per_second=None,retry_count=0)
    try:
        C.need(node in ('compute-0-20','compute-0-21'),'EXACT_PLANNED_GPU_HOST')
        budget.check();db.execute('CREATE INDEX IF NOT EXISTS exported_gid_delivery ON exported(gid,store)');db.commit()
        mids=[r[0]for r in db.execute("SELECT mid FROM molecules ORDER BY sample_rank('gpu_local_window',mid),mid LIMIT 64")]
        work=[]
        for mid in mids:
            requests=[]
            for path,gid in db.execute('SELECT s.path,e.gid FROM geometries g JOIN exported e ON e.gid=g.gid JOIN stores s ON s.name=e.store WHERE g.mid=? ORDER BY e.store,e.gid',(mid,)):
                relative=str(pathlib.Path(path).relative_to(root));requests.append((relative,gid))
            C.need(requests,'SAMPLED_MID_HAS_EXPORTED_RECORDS');work.append((mid,requests))
        _write(root/'benchmark_work.json',dict(molecules=work,manifest_sha256=manifest['sha256']))
        with (root/'export_manifest.sha256').open('x')as stream:stream.write(manifest['sha256']+'  export_manifest.json\n')
        paths={pathlib.Path(manifest['path']),root/'export_manifest.sha256',root/'benchmark_work.json'}
        for reference in stores:
            value=json.loads(pathlib.Path(reference['path']).read_text())
            paths.update(pathlib.Path(value[k]['path'])for k in ('data','manifest_reference'))
            paths.add(pathlib.Path(value['f64_authority']['reference']['path']))
        relative_paths=sorted(str(path.relative_to(root))for path in paths)
        total=sum(path.stat().st_size for path in paths)
        filelist=root/'delivery_files.list0'
        with filelist.open('xb')as stream:stream.write(b'\0'.join(name.encode()for name in relative_paths)+b'\0')
        ready=_call(_remote_command(node,['--preflight',destination,'--required-bytes',str(total),'--node',node]),budget,timeout=None if plan.get('queue_startup_mode')=='USER_UNLIMITED_CPU21_D3_20261103'else 90)
        distribution['preflight']=ready
        C.need(ready['returncode']==0,'REMOTE_TMP_PREFLIGHT_FAILED');distribution['tmp']=_json_output(ready['stdout'])
        argv=['rsync','-rlt','--checksum','--from0','--relative','--protect-args','--stats','--files-from='+str(filelist),
          '-e','ssh -T -o BatchMode=yes -o ConnectTimeout=20','--',str(root)+'/',node+':'+destination.rstrip('/')+'/']
        copied=_call(argv,budget);distribution.update(transfer=copied,logical_copy_bytes=total,file_count=len(paths),manifest_sha256=manifest['sha256'])
        C.need(copied['returncode']==0,'SINGLE_RSYNC_CHECKSUM_FAILED');distribution['status']='COPIED_WITH_RSYNC_CHECKSUM'
    except Exception as error:
        distribution['error']=str(error);return distribution,performance
    try:
        seconds=int(plan.get('benchmark_seconds',180));C.need(0<seconds<=240,'ONE_BENCHMARK_LESS_THAN5MIN')
        result=_call(_remote_command(node,['--benchmark-work',destination.rstrip('/')+'/benchmark_work.json','--seconds',str(seconds)],timeout=True),budget,timeout=285)
        if result['returncode']!=0:
            performance.update(status='TIMEOUT'if result['returncode']==124 else 'FAILED',execution=result);return distribution,performance
        performance=_json_output(result['stdout']);performance.update(execution=result,retry_count=0)
    except Exception as error:performance.update(status='FAILED',error=str(error))
    return distribution,performance

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preflight');parser.add_argument('--required-bytes',type=int);parser.add_argument('--node')
    parser.add_argument('--benchmark-work');parser.add_argument('--seconds',type=int,default=180);args=parser.parse_args()
    result=preflight(args.preflight,args.required_bytes,args.node)if args.preflight else benchmark(args.benchmark_work,args.seconds)
    print(json.dumps(result,separators=(',',':')))

if __name__=='__main__':main()
