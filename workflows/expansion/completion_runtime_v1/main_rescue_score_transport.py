"""Transport whole closed Main exact-rescue scores with external replica metadata."""
import argparse,hashlib,io,json,os,pathlib,socket,stat,sys,tarfile,threading,time
from decimal import Decimal
MAIN='202.38.247.57:22';ALPHA='218.192.171.238:22'
def need(ok,message):
    if not ok:raise ValueError(message)
def frame(path):
    s=pathlib.Path(path).lstat()
    need(stat.S_ISREG(s.st_mode)and s.st_uid==os.getuid()and s.st_nlink==1,'Own literal regular transport source/file')
    return(s.st_dev,s.st_ino,s.st_uid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def ref(path):
    path=pathlib.Path(path).absolute();before=frame(path);h=hashlib.sha256()
    with path.open('rb')as f:
        need(tuple(getattr(os.fstat(f.fileno()),k)for k in('st_dev','st_ino','st_uid','st_size','st_mtime_ns','st_ctime_ns'))==before,'Same input FD')
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    need(frame(path)==before,'Transport metadata changed')
    return dict(path=str(path),bytes=before[3],sha256=h.hexdigest())
def verify(value):
    need(ref(value['path'])=={k:value[k]for k in('path','bytes','sha256')},'Whole transport input bytes/SHA')
    return pathlib.Path(value['path'])
def read(value,cap=2<<20):
    need(0<=value['bytes']<=cap,'Bounded explicit metadata');p=verify(value);stamp=frame(p);raw=p.read_bytes()
    need(frame(p)==stamp and hashlib.sha256(raw).hexdigest()==value['sha256'],'Whole stable metadata read')
    return json.loads(raw)
def write(path,value):
    with pathlib.Path(path).open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def native_C0(actual,path):
    lines=pathlib.Path(path).read_text().splitlines();need(lines and 'JobIDRaw'in lines[0].split('|'),'Actual native accounting header')
    names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    job=str(actual['job_id']);rows=[r for r in rows if r['JobIDRaw']==job or r['JobIDRaw'].startswith(job+'.')]
    parents=[r for r in rows if r['JobIDRaw']==job]
    need(len(parents)==1 and parents[0]['UID']=='1278'and any(r['JobIDRaw']==job+'.batch'for r in rows)
        and all(r['State']=='COMPLETED'and r['ExitCode']=='0:0'for r in rows),'Real Main parent/batch/all recorded steps C0')
def make_index(a):
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-16','Actual source Main16 UID1278')
    manifest=ref(a.manifest);main=read(manifest);raw=ref(a.native_accounting)
    need(main['schema']=='MAIN_EXACT_FP_RESCUE_SCORES_V1'and main['status']=='COMPLETE'
        and main['actual']['uid']==1278 and main['actual']['endpoint']==MAIN and main['actual']['job_id']==a.job
        and main['actual']['node']=='compute-0-16'and main['reference_molecules']==1196122,'Closed actual Main rescue only')
    native_C0(main['actual'],raw['path'])
    files=[];origins=set();names=set()
    def add(name,origin):
        path=pathlib.Path(origin['path']);need(path.is_absolute()and not any(p.is_symlink()for p in(path,*path.parents)),'Literal source path')
        stamp=frame(path);need(stamp[3]==origin['bytes']and name not in names and origin['path']not in origins,'Unique original size/path')
        names.add(name);origins.add(origin['path'])
        files.append(dict(archive_path=name,origin={k:origin[k]for k in('path','bytes','sha256')},source_frame=list(stamp)))
    metadata=[('metadata/manifest.json',manifest),('metadata/native_sacct.txt',raw),
        ('metadata/parts_catalog.jsonl',main['parts_catalog_reference']),('metadata/preflight.json',main['preflight_reference']),
        ('metadata/build_new.json',main['builds']['new']),('metadata/build_old.json',main['builds']['old'])]
    pre=read(main['preflight_reference'])
    metadata += [('metadata/native_tests.stderr',pre['native_test_stderr_reference']),
        ('metadata/native_tests.stdout',pre['native_test_stdout_reference'])]
    for name,origin in metadata:verify(origin);add(name,origin)
    catalog=verify(main['parts_catalog_reference']);stamp=frame(catalog);counts={b:0 for b in '0123456789abcdef'};parts=0
    with catalog.open('rb')as f:
        for line in f:
            need(line.endswith(b'\n')and len(line)<=1<<20,'Whole newline Main score catalog')
            part=json.loads(line);bucket=part['fp_bucket'];need(bucket in counts and type(part['rows'])is int and 0<part['rows']<=4096,'Actual bounded result part')
            p=pathlib.Path(part['path']);need(p.is_relative_to(a.manifest.parent/'scores'/bucket),'Score part remains within original root/bucket')
            add('scores/'+bucket+'/'+p.name,part);counts[bucket]+=part['rows'];parts+=1
    need(frame(catalog)==stamp and counts==main['per_bucket_counts']and sum(counts.values())==main['distinct_fingerprints']
        and parts==main['part_count'],'All original closed parts and FP mass')
    result=dict(schema='MAIN_ALPHA_EXACT_RESCUE_TAR_INDEX_V1',source_endpoint=MAIN,source_uid=1278,destination_endpoint=ALPHA,
        destination_uid=1264,source_node='compute-0-16',actual_main=main['actual'],main_manifest_reference=manifest,
        main_native_sacct_reference=raw,file_count=len(files),score_part_count=parts,score_rows=sum(counts.values()),
        total_file_bytes=sum(f['origin']['bytes']for f in files),files=files)
    write(a.output,result);r=ref(a.output);need(r['bytes']<=64<<20,'Explicit64MiB tar index bound')
    print(json.dumps(dict(index_reference=r,main_manifest_reference=manifest,main_native_sacct_reference=raw,
        file_count=len(files),score_parts=parts,score_rows=result['score_rows'],total_file_bytes=result['total_file_bytes'])),flush=True)
class HashReader:
    def __init__(self,stream):self.stream=stream;self.h=hashlib.sha256();self.n=0
    def read(self,n=-1):
        b=self.stream.read(n);self.h.update(b);self.n+=len(b);return b
def send(a):
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-16','Actual Main source')
    index_ref=ref(a.index);index=read(index_ref,64<<20)
    need(index['schema']=='MAIN_ALPHA_EXACT_RESCUE_TAR_INDEX_V1','Actual closed score index')
    native_C0(index['actual_main'],verify(index['main_native_sacct_reference']))
    with tarfile.open(fileobj=sys.stdout.buffer,mode='w|')as archive:
        raw=a.index.read_bytes();info=tarfile.TarInfo('_transport_index.json');info.size=len(raw);info.uid=1278;archive.addfile(info,io.BytesIO(raw))
        for item in index['files']:
            origin=item['origin'];p=pathlib.Path(origin['path']);need(list(frame(p))==item['source_frame'],'Original source frame changed')
            info=tarfile.TarInfo(item['archive_path']);info.size=origin['bytes'];info.uid=1278
            with p.open('rb')as f:
                reader=HashReader(f);archive.addfile(info,reader)
                need(reader.read(1)==b''and reader.n==origin['bytes']and reader.h.hexdigest()==origin['sha256'],'Source whole streamed bytes/SHA/EOF')
            need(list(frame(p))==item['source_frame'],'Streamed original source changed')
    need(ref(a.index)==index_ref,'Closed index changed')
    print(json.dumps(dict(event='MAIN_CLOSED_SCORE_STREAM_COMPLETE',index_reference=index_ref,files=index['file_count'])),file=sys.stderr,flush=True)
class Ledger:
    def __init__(self,root):self.root=root;self.closed=[];self.partial=None;self.lock=threading.RLock();self.dirs={root};self.mutable=set()
    def close(self,path):
        with self.lock:
            s=path.stat();self.closed.append((s.st_blocks*512,max(s.st_mtime_ns,s.st_ctime_ns)))
            self.mutable.discard(path)
            if self.partial==path:self.partial=None
            self.dirs.update(p for p in path.parents if p==self.root or self.root in p.parents)
    def usage(self):
        with self.lock:
            total=sum(x[0]for x in self.closed)
            for p in self.dirs:
                if p.exists():total+=p.stat().st_blocks*512
            dynamic=set(self.mutable)
            if self.partial:dynamic.add(self.partial)
            for p in dynamic:
                if p.exists():total+=p.stat().st_blocks*512
            return total
    def credit(self,cutoff):
        with self.lock:return sum(n for n,stamp in self.closed if Decimal(stamp)<Decimal(str(cutoff))*Decimal(1000000000))
def receive(a):
    need(os.getuid()==1264,'Actual Alpha destination UID1264')
    cfg=read(ref(a.config));need(cfg['schema']=='ALPHA_NATIVE_RESCUE_TRANSPORT_IO_PLAN_V1'
        and cfg['scientific_computation']is False,'Actual IO resource plan, never fake Slurm/SCI completion')
    import runpy
    runpy.run_path(cfg['source_entry'],run_name='_Alpha_IO_source_bootstrap')
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    out=pathlib.Path(cfg['output_scope_root'])
    need(out==pathlib.Path(cfg['output_directory'])and out.is_relative_to('/gfshome/alpha/codex_data_v1_20261026/inputs')
        and not out.exists()and not any(p.is_symlink()for p in out.parents),'Fresh actual own Alpha transport scope')
    os.umask(0o077);out.mkdir(mode=0o700,parents=True);ledger=Ledger(out)
    guard=Guard(cfg,usage_provider=ledger.usage,prequery_credit_provider=ledger.credit)
    print('READY',flush=True);started=time.monotonic();seen=set();total=0
    try:
        with tarfile.open(fileobj=sys.stdin.buffer,mode='r|')as archive:
            first=archive.next();expected_index=cfg['source_index_reference']
            need(first is not None and first.name=='_transport_index.json'and first.isfile()
                and first.size==expected_index['bytes']<=64<<20,'Complete explicitly bound source tar index')
            raw=archive.extractfile(first).read();need(hashlib.sha256(raw).hexdigest()==expected_index['sha256'],'Exact original source index SHA')
            index=json.loads(raw)
            need(index['schema']=='MAIN_ALPHA_EXACT_RESCUE_TAR_INDEX_V1'and index['source_endpoint']==MAIN and index['source_uid']==1278
                and index['destination_endpoint']==ALPHA and index['destination_uid']==1264
                and index['main_manifest_reference']==cfg['main_manifest_reference']
                and index['main_native_sacct_reference']==cfg['main_native_sacct_reference'],'Actual Main-to-Alpha index identity')
            expected={v['archive_path']:v['origin']for v in index['files']}
            need(len(expected)==index['file_count']<=100000 and index['total_file_bytes']+len(raw)+16_000_000<=cfg['output_cap_bytes'],
                'Full input count and real metadata/output headroom')
            index_path=out/'_transport_index.json';index_path.write_bytes(raw);ledger.close(index_path)
            cat=out/'transport_files.jsonl'
            with cat.open('xb')as catalog:
                ledger.mutable.add(cat)
                while True:
                    member=archive.next()
                    if member is None:break
                    name=member.name;rel=pathlib.PurePosixPath(name)
                    need(name in expected and name not in seen and member.isfile()and not rel.is_absolute()and '..'not in rel.parts,
                        'Exactly listed unique regular relative tar member')
                    origin=expected[name];need(member.size==origin['bytes'],'Exact member size')
                    target=out.joinpath(*rel.parts);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                    with ledger.lock:ledger.dirs.update(p for p in target.parents if p==out or out in p.parents)
                    need(target.parent.resolve().is_relative_to(out),'Owned literal destination directory')
                    partial=target.with_name(target.name+'.partial');need(not partial.exists()and not target.exists(),'Preserve previous partials')
                    h=hashlib.sha256();n=0
                    with ledger.lock:ledger.partial=partial
                    with archive.extractfile(member)as source,partial.open('xb')as dest:
                        while True:
                            guard.check();block=source.read(8<<20)
                            if not block:break
                            dest.write(block);h.update(block);n+=len(block)
                        dest.flush();os.fsync(dest.fileno())
                    need(n==origin['bytes']and h.hexdigest()==origin['sha256'],'Whole destination FD bytes/SHA')
                    with ledger.lock:partial.rename(target);ledger.close(target);ledger.mutable.add(cat)
                    replica=dict(path=str(target),bytes=n,sha256=h.hexdigest())
                    catalog.write(json.dumps(dict(origin=origin,replica=replica),sort_keys=True).encode()+b'\n');catalog.flush()
                    total+=n;seen.add(name);guard.check()
                catalog.flush();os.fsync(catalog.fileno())
            ledger.close(cat);need(seen==set(expected)and total==index['total_file_bytes'],'Every whole listed file received exactly once')
        transport=out/'transport.json'
        write(transport,dict(schema='EXACT_RESCUE_TRANSPORT_V1',source_endpoint=MAIN,source_uid=1278,destination_endpoint=ALPHA,
            destination_uid=1264,files_catalog_reference=ref(cat),file_count=len(seen),source_index_reference=expected_index))
        ledger.close(transport)
        main=read(ref(out/'metadata/manifest.json'));native_C0(main['actual'],out/'metadata/native_sacct.txt')
        guard.sample();guard.check()
        summary=dict(schema='ALPHA_MAIN_EXACT_SCORE_TRANSFER_COMPLETE_V1',actual_endpoint=ALPHA,actual_uid=1264,node=socket.gethostname(),
            source_index_reference=expected_index,main_manifest_reference=cfg['main_manifest_reference'],main_native_sacct_reference=cfg['main_native_sacct_reference'],
            transport_reference=ref(transport),file_count=len(seen),transferred_file_bytes=total,score_rows=index['score_rows'],
            wall_seconds=time.monotonic()-started,resource_plan_reference=ref(a.config),scientific_import_completed=False)
        completion=out/'transfer_completed.json';write(completion,summary);ledger.close(completion);guard.sample();guard.check()
        print(json.dumps(summary),flush=True)
    finally:guard.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('index');q.add_argument('--manifest',required=True,type=pathlib.Path);q.add_argument('--native-accounting',required=True,type=pathlib.Path)
    q.add_argument('--job',required=True);q.add_argument('--output',required=True,type=pathlib.Path)
    q=sub.add_parser('send');q.add_argument('--index',required=True,type=pathlib.Path)
    q=sub.add_parser('receive');q.add_argument('--config',required=True,type=pathlib.Path)
    a=p.parse_args();{'index':make_index,'send':send,'receive':receive}[a.mode](a)
if __name__=='__main__':main()
