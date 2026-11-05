"""Copy closed Node21 input replicas to an actual pure-CPU Node16 allocation."""
import hashlib,json,os,pathlib,socket,subprocess,tarfile,time
R=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
CONTROL=R/'control/pubchem_alpha_return_20261103'
OLD=pathlib.Path('/tmp/zixiao_pubchem_rescue_20261104')
NEW=pathlib.Path('/dev/shm/zixiao_pubchem_rescue_20261104')
def ref(path):
    path=pathlib.Path(path);s=path.stat();h=hashlib.sha256()
    with path.open('rb')as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    e=path.stat()
    assert e.st_uid==1278 and (s.st_ino,s.st_size,s.st_mtime_ns)==(e.st_ino,e.st_size,e.st_mtime_ns)
    return dict(path=str(path),bytes=e.st_size,sha256=h.hexdigest())
def write(path,value):
    with path.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-16'
    assert os.environ.get('SLURM_JOB_ID')and int(os.environ['SLURM_CPUS_PER_TASK'])==96
    assert not NEW.exists()
    NEW.mkdir(mode=0o700)
    assert os.statvfs(NEW).f_bavail*os.statvfs(NEW).f_frsize>=162000000000
    command="test -f /tmp/zixiao_pubchem_rescue_20261104/alpha_queries_v1/transfer_completed.json && exec tar -C /tmp -cf - zixiao_pubchem_rescue_20261104/reference zixiao_pubchem_rescue_20261104/alpha_queries_v1"
    started=time.monotonic();total=0;seen=set()
    proc=subprocess.Popen(['ssh','-n','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519',
        '-o','UserKnownHostsFile='+str(CONTROL/'main21_verified_known_hosts_20261104'),'compute-0-21',command],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode='r|')as archive:
            for member in archive:
                relative=pathlib.PurePosixPath(member.name)
                assert relative.parts[0]==NEW.name and '..'not in relative.parts and not relative.is_absolute()
                assert member.name not in seen and member.uid==1278
                seen.add(member.name);path=NEW.joinpath(*relative.parts[1:])
                if member.isdir():path.mkdir(mode=0o700,parents=True,exist_ok=True);continue
                assert member.isfile()and not member.issym()and not member.islnk()
                total+=member.size;assert total<=2000000000
                path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with archive.extractfile(member)as source,path.open('xb')as dest:
                    while True:
                        block=source.read(8<<20)
                        if not block:break
                        dest.write(block)
                    dest.flush();os.fsync(dest.fileno())
        assert proc.wait()==0
    finally:
        if proc.poll()is None:proc.terminate();proc.wait()
    folder=NEW/'alpha_queries_v1';old_transport=folder/'transport.json';old_complete=folder/'transfer_completed.json'
    old_transport.rename(folder/'Node21_origin_transport.json')
    old_complete.rename(folder/'Node21_origin_transfer_completed.json')
    original_transport=ref(folder/'Node21_origin_transport.json')
    value=json.loads((folder/'Node21_origin_transport.json').read_text())
    for item in value['files']:
        replica=item['replica'];original=pathlib.Path(replica['path'])
        assert original.is_relative_to(OLD)
        path=NEW/original.relative_to(OLD);actual=ref(path)
        assert actual['bytes']==replica['bytes']and actual['sha256']==replica['sha256']
        item['replica']=actual
    value['actual_replica_node']='compute-0-16';value['preserved_Node21_transport_reference']=original_transport
    write(old_transport,value)
    write(old_complete,dict(schema='MAIN_NODE16_CLOSED_INPUT_COPY_V1',actual_uid=1278,node=socket.gethostname(),
        job_id=os.environ['SLURM_JOB_ID'],source_node='compute-0-21',transport_reference=ref(old_transport),
        source_completion_copy_reference=ref(folder/'Node21_origin_transfer_completed.json'),files_verified=len(value['files']),
        copied_bytes=total,wall_seconds=time.monotonic()-started,no_original_Alpha_metadata_rewritten=True))
    print(json.dumps(dict(event='NODE16_COMPLETE_INPUT_COPY',files_verified=len(value['files']),bytes=total,
        completion_reference=ref(old_complete))),flush=True)
if __name__=='__main__':main()
