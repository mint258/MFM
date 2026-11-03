"""Known-byte CAS pools and byte-identical closed publication; never Native."""
import fcntl,hashlib,json,os,pathlib,stat,uuid
from . import contract as C,io as I

def allocation(total,used,n):
    C.need(type(n)is int and n>0 and type(total)is int and type(used)is int and 0<=used<=total,'EXACT_CAS_BYTE_COUNTS')
    return used+n<=total

class Pool:
    def __init__(self,ref,kind):
        self.reference=ref;review=C.meta(ref)
        C.need(review['schema']=='ROOT_APPROVED_PPRIME_BOUNDED_SHARED_PUBLICATION_POOLS_V2'
          and review['status']=='APPROVED_EXACT_SHARED_POOLS_COUNTED_ONCE' and review['reviewer']=='root'
          and review['total_PREP_and_EXEC_future_bytes']==64<<30,'EXACT_ROOT_TWO32G_POOLS_NO_PER_PARENT_DOUBLE_COUNT')
        spec=review['pools'][kind];self.root=pathlib.Path(spec['root']);self.cap=spec['cap_bytes'];self.kind=kind
        C.need(self.cap==32<<30 and C.BASE in self.root.parents and not any(p.is_symlink() for p in (self.root,*self.root.parents)),'FIXED_SHARED_POOL_ROOT')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700);C.need(self.root.stat().st_uid==1278,'OWN_SHARED_POOL')
        self.lock=self.root/'pool.lock';self.state=self.root/'pool_state.json'
    def update(self,n,identity,commit=None):
        with self.lock.open('a+b') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if self.state.exists():
                value=C.meta(C.Q.pin(self.state));C.need(value['pool_review_reference']==self.reference and value['kind']==self.kind,'UNCHANGED_GLOBAL_POOL_AUTHORITY')
            else:value={'schema':'PPRIME_KNOWN_CLOSED_BYTE_CAS_POOL_V2','pool_review_reference':self.reference,'kind':self.kind,'tokens':{}}
            tokens=value['tokens']
            if commit is None and len(tokens)>=20000:return None
            if commit is None:
                used=sum(t['reserved_bytes'] for t in tokens.values());amount=n+(64<<10)
                if not allocation(self.cap-(16<<20),used,amount):return None
                key=uuid.uuid4().hex;tokens[key]={'reserved_bytes':amount,'identity':identity,'status':'RESERVED_UNKNOWN_UNTIL_COMMITTED'}
            else:
                key=commit;C.need(key in tokens and tokens[key]['identity']==identity,'EXACT_OWN_RESERVED_PUBLICATION_TOKEN');tokens[key]['status']='COMMITTED_BYTE_VERIFIED'
            payload=C.O.canonical(value)+b'\n'
            if commit is None and len(payload)>=2<<20:return None
            C.need(len(payload)<2<<20,'SMALL_BOUNDED_POOL_STATE')
            tmp=self.root/('pool_state.partial_'+uuid.uuid4().hex)
            with tmp.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.state);fd=os.open(self.root,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            return key

def closed_files(root,paths):
    root=pathlib.Path(root);result=[];seen=set()
    for scope in paths:
        scope=pathlib.Path(scope);C.need(root==scope or root in scope.parents,'EXACT_LOCAL_BUNDLE_SCOPE')
        for p in ([scope] if scope.is_file() else sorted(scope.rglob('*'))):
            if p in seen:continue
            seen.add(p);st=p.lstat();C.need(st.st_uid==1278 and not stat.S_ISLNK(st.st_mode),'OWN_CLOSED_BUNDLE_NO_ALIAS')
            if stat.S_ISDIR(st.st_mode):continue
            C.need(stat.S_ISREG(st.st_mode) and not p.name.endswith(('-journal','-wal','-shm')) and '.partial_' not in p.name,'ONLY_CLOSED_STABLE_FILES')
            ref=I.pin(p,[root]);result.append({'relative_path':str(p.relative_to(root)),'origin_reference':ref})
    C.need(len(result)<=8192 and len({x['relative_path'] for x in result})==len(result),'BOUNDED_UNIQUE_CLOSED_BUNDLE')
    return result

def ready(root,paths,kind,proof,identity,store,extra):
    root=pathlib.Path(root);rows=closed_files(root,paths)
    C.need(rows,'NONEMPTY_CLOSED_PUBLICATION')
    value={'schema':'PPRIME_CLOSED_LOCAL_PUBLICATION_READY_V2','uid':1278,'node':proof['request']['node'],'job_id':str(proof['job_id']),
      'boot_id':proof['boot_id'],'parent_pid':os.getpid(),'parent_ticks':I.ticks(os.getpid()),'local_root':str(root),
      'kind':kind,'identity':identity,'files':rows,'actual_file_bytes':sum(x['origin_reference']['bytes'] for x in rows),
      'budgeted_publish_bytes':sum(x['origin_reference']['bytes']+8192 for x in rows)+(2<<20),'extra':extra,
      'native_invocations_by_publication':0,'original_scientific_bytes_rewritten':False}
    return store.json(root/('publication_ready_'+identity+'.json'),value)

def copy_ref(origin,target):
    """No source reopen between hash/copy: one stable source FD verifies EOF."""
    p=pathlib.Path(origin['path']);before=p.lstat();C.need(I.pin(p,[p.parent])==origin,'CLOSED_ORIGIN_SHA_BEFORE_COPY')
    target=pathlib.Path(target);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    C.need(not target.exists(),'FRESH_PUBLICATION_DESTINATION');h=hashlib.sha256();n=0
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as src,target.open('xb') as dst:
        C.need(I.stamp(os.fstat(src.fileno()))==I.stamp(before),'SOURCE_FD_COPY_BINDING')
        while block:=src.read(1<<20):dst.write(block);h.update(block);n+=len(block)
        dst.flush();os.fsync(dst.fileno())
        C.need(I.stamp(os.fstat(src.fileno()))==I.stamp(before)==I.stamp(p.lstat()) and n==origin['bytes'] and h.hexdigest()==origin['sha256'],'WHOLE_COPY_STABLE_FD_SHA')
    ref=I.pin(target,[target.parent]);C.need(ref['bytes']==origin['bytes'] and ref['sha256']==origin['sha256'],'SHARED_REOPEN_FULL_SHA')
    return ref

def publish(ready_ref,budget,parent_store,out,pool):
    # ready is a CPU-produced closed-file locator manifest, not raw/QM values.
    budget.check(dispatch=False)
    C.need(I.pin(ready_ref['path'],[budget.local_root])==ready_ref,'LOCAL_READY_FULL_SHA')
    local=json.loads(I.body(ready_ref,[ready_ref],budget))
    C.need(local['schema']=='PPRIME_CLOSED_LOCAL_PUBLICATION_READY_V2' and local['uid']==1278
      and local['node']==budget.plan['node'] and local['local_root']==str(budget.local_root),'SAME_NODE_EXACT_CLOSED_LOCAL_BUNDLE')
    n=local['budgeted_publish_bytes'];identity=local['identity']
    locator={'schema':'PPRIME_LOCAL_PUBLICATION_RECOVERY_LOCATOR_V2','ready_reference':ready_ref,'node':local['node'],'uid':1278,
      'job_id':local['job_id'],'boot_id':local['boot_id'],'local_root':local['local_root'],'identity':identity,
      'kind':local['kind'],'original_scientific_bytes_rewritten':False,'native_retry_authorized':False}
    if budget.roles.bound()+n>budget.cap:
        ref=parent_store.json(out/('unpublished_'+identity+'.json'),dict(locator,status='PARENT_SHARED_CAP_KEEP_NODE_RAW_UNKNOWN'))
        return {'published':False,'recovery_locator_reference':ref}
    token=pool.update(n,identity)
    if token is None:
        ref=parent_store.json(out/('unpublished_'+identity+'.json'),dict(locator,status='GLOBAL_POOL_FULL_KEEP_NODE_RAW_UNKNOWN'))
        return {'published':False,'recovery_locator_reference':ref}
    budget.roles.add_publish(n);final=pool.root/('bundle_'+token);tmp=pool.root/('.partial_'+token);tmp.mkdir(mode=0o700)
    mapping=[]
    try:
        for row in local['files']:
            rel=pathlib.PurePosixPath(row['relative_path']);C.need(not rel.is_absolute() and '..' not in rel.parts,'SAFE_RELATIVE_PUBLICATION_PATH')
            C.need(pathlib.Path(row['origin_reference']['path'])==budget.local_root/pathlib.Path(*rel.parts),'EXACT_ORIGIN_ROOT_RELATIVE_PATH_BINDING')
            partial=copy_ref(row['origin_reference'],tmp/pathlib.Path(*rel.parts))
            target=dict(partial,path=str(final/pathlib.Path(*rel.parts)));mapping.append(dict(row,target_reference=target))
        manifest={'schema':'PPRIME_BYTE_IDENTICAL_LOCAL_TO_SHARED_PUBLICATION_V2','origin_ready_reference':ready_ref,'local_origin_root':local['local_root'],
          'actual_origin_job_id':local['job_id'],'original_node':local['node'],'pool_token':token,'pool_reference':pool.reference,
          'kind':local['kind'],'identity':identity,'entries':mapping,'extra':local['extra'],'all_file_SHA_bytes_equal':True,
          'raw_or_record_embedded_local_paths_preserved_with_explicit_resolver':True,'not_new_native_or_scientific_success':True}
        encoded=C.O.canonical(manifest)+b'\n';C.need(len(encoded)<2<<20,'SMALL_PUBLICATION_MAP_BOUND')
        with (tmp/'publication_manifest.json').open('xb') as f:f.write(encoded);f.flush();os.fsync(f.fileno())
        # Sync every containing directory before one same-filesystem rename.
        for directory in sorted({tmp,*[p.parent for p in tmp.rglob('*')]},key=lambda x:len(x.parts),reverse=True):
            fd=os.open(directory,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        os.rename(tmp,final);fd=os.open(pool.root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        pool.update(n,identity,commit=token);ref=I.pin(final/'publication_manifest.json',[pool.root])
        return {'published':True,'publication_manifest_reference':ref,'entries':mapping,'extra':local['extra']}
    except BaseException:
        # Never release reserved UNKNOWN bytes or remove partial/original files.
        parent_store.json(out/('unpublished_'+identity+'.json'),dict(locator,status='COPY_UNKNOWN_RESERVED_TOKEN_NOT_RELEASED',pool_token=token))
        raise

def relocated(ref,mapping):
    matches=[x['target_reference'] for x in mapping if x['origin_reference']==ref]
    C.need(len(matches)==1,'EXACT_ONE_PUBLICATION_PATH_ALIAS_SAME_BYTES_SHA');return matches[0]
