"""Read-only evidence and exact old node14 scratch inspection. Never deletes."""
from pathlib import Path
import argparse,hashlib,json,os,socket,sqlite3,stat,time,zlib
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SCRATCH=Path('/tmp/wp5runtime_1278_4515292_38e2d502')
NATIVE=SCRATCH/'wp5_4515292_38e2d502/lane_16/wp4native_1278_4515292_872wlefa'
CONTAINER=ROOT/'evidence/phase15_archive_io_failure/victim4515292_lane16.sqlite'
RECEIPT=CONTAINER.with_suffix('.receipt.json')
EXPECTED={'RAW_ARCHIVE_FAILURE_PRESERVE.json':(173,'56f3fd58feeced2750d9f5863bf9c38c4ff2eef1b5d5d3f02f90dfbb76f0625d'),'process.out':(4153,'4c3e6c2d60d4f2c766093e7be32fcf066aa4ca1409923acee0eaa07c18aea57e')}
def sha(data):return hashlib.sha256(data).hexdigest()
def reference(path):
    data=Path(path).read_bytes();return {'path':str(path),'bytes':len(data),'sha256':sha(data)}
def metadata(path):
    st=path.lstat();kind='directory' if stat.S_ISDIR(st.st_mode) else 'file' if stat.S_ISREG(st.st_mode) else 'link' if stat.S_ISLNK(st.st_mode) else 'other'
    return {'path':str(path),'kind':kind,'uid':st.st_uid,'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mode':st.st_mode,'nlink':st.st_nlink,'mtime_ns':st.st_mtime_ns}
def backup():
    receipt=json.loads(RECEIPT.read_text());container_ref=reference(CONTAINER)
    if container_ref!={'path':str(CONTAINER),'bytes':20480,'sha256':'3faa606d98419b9a1e2b463d8ae2f96f36bbfe0a5d67e3f4167b1c41f421808a'} or receipt['container']!=container_ref:raise ValueError('PERMANENT_EXACT_CONTAINER_CHANGED')
    if receipt['status']!='PARTIAL_NATIVE_OUTPUT_EVIDENCE_SHA_READBACK_VERIFIED' or receipt['metadata']['original_job_id']!='4515292' or receipt['metadata']['source_node']!='compute-0-14':raise ValueError('EXACT_INCIDENT_RECEIPT_REQUIRED')
    q=sqlite3.connect('file:'+str(CONTAINER)+'?mode=ro',uri=True)
    try:
        if q.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('PERMANENT_CONTAINER_INTEGRITY_FAILED')
        rows=q.execute('SELECT evidence_id,classification,metadata_json FROM evidence').fetchall()
        if len(rows)!=1 or json.loads(rows[0][2])!=receipt['metadata']:raise ValueError('PERMANENT_METADATA_RECEIPT_DIFFERS')
        members={}
        for name,n,digest,codec,body in q.execute('SELECT name,bytes,sha256,compression,body FROM files'):
            data=zlib.decompress(body)
            if name not in EXPECTED or (n,digest)!=EXPECTED[name] or codec!='zlib9' or len(data)!=n or sha(data)!=digest:raise ValueError('PERMANENT_MEMBER_SHA_OR_VALUE_DIFFERS')
            members[name]=data
        if set(members)!=set(EXPECTED):raise ValueError('PERMANENT_EXACT_TWO_MEMBERS_REQUIRED')
        expected_receipt={r['name']:(r['bytes'],r['sha256'],r['SHA_readback_verified']) for r in receipt['members']}
        if expected_receipt!={name:(n,digest,True) for name,(n,digest) in EXPECTED.items()}:raise ValueError('RECEIPT_MEMBER_SET_DIFFERS')
        marker=json.loads(members['RAW_ARCHIVE_FAILURE_PRESERVE.json'])
        if marker.get('record_id')!='principal_00600001_00900000.lmdb:950624' or marker.get('task')!='xtb_singlepoint' or marker.get('execution_id')!=receipt['metadata']['execution_id']:raise ValueError('PERMANENT_PARTIAL_MARKER_IDENTITY_DIFFERS')
        return {'container':container_ref,'receipt':reference(RECEIPT),'members':[{'name':name,'bytes':len(data),'sha256':sha(data),'decompressed_SHA_and_receipt_equal':True} for name,data in members.items()]},members
    finally:q.close()
def terminal(path):
    whole=json.loads(path.read_text());data=whole.get('sacct',whole)
    if data.get('returncode',data.get('sacct_returncode'))!=0:raise ValueError('ACTUAL_ACCOUNTING_FAILED')
    lines=data.get('stdout',data.get('sacct_stdout','')).splitlines();rows=[line.split('|') for line in lines if line.split('|')[0]=='4515292']
    if len(rows)!=1 or rows[0][1:4]!=['zixiao','COMPLETED','0:0']:raise ValueError('EXACT5292_ACTUAL_COMPLETED0_REQUIRED')
    return {'source':reference(path),'raw_fields':rows[0],'job_id':'4515292','user':'zixiao','state':'COMPLETED','exit_code':'0:0'}
def process_refs(entries):
    inodes={(e['device'],e['inode']) for e in entries};matches=[];own_errors=[];own_pids=0;foreign_denied=0
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:uid=process.stat().st_uid
        except FileNotFoundError:continue
        if uid!=1278:continue
        own_pids+=1
        try:
            cwd=os.readlink(process/'cwd')
            if cwd==str(SCRATCH) or cwd.startswith(str(SCRATCH)+'/'):matches.append({'pid':int(process.name),'kind':'cwd','target':cwd})
        except FileNotFoundError:continue
        except PermissionError as error:own_errors.append({'pid':int(process.name),'kind':'cwd','error':str(error)})
        try:
            with os.scandir(process/'fd') as scan:handles=[e.path for e in scan]
            for handle in handles:
                try:
                    target=os.readlink(handle);info=os.stat(handle)
                    if target.removesuffix(' (deleted)')==str(SCRATCH) or target.removesuffix(' (deleted)').startswith(str(SCRATCH)+'/') or (info.st_dev,info.st_ino) in inodes:matches.append({'pid':int(process.name),'kind':'fd','fd':Path(handle).name,'target':target})
                except FileNotFoundError:continue
                except PermissionError as error:own_errors.append({'pid':int(process.name),'kind':'fd','error':str(error)})
        except FileNotFoundError:continue
        except PermissionError as error:own_errors.append({'pid':int(process.name),'kind':'fd_directory','error':str(error)})
    return {'scope':'All currently readable /proc processes owned by actual UID1278 on compute-0-14; same-UID permission failures block readiness. No other process is signalled or modified.','same_uid_processes_examined':own_pids,'matching_open_FDs_or_cwd':matches,'same_uid_inspection_errors':own_errors,'no_same_uid_active_reference':not matches and not own_errors}
def collect(accounting):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-14':raise ValueError('ACTUAL_UID1278_NODE14_ONLY')
    archived,members=backup();account=terminal(accounting);entries=[]
    if os.path.lexists(SCRATCH):
        def walk(path):
            item=metadata(path);entries.append(item)
            if item['kind']=='directory':
                with os.scandir(path) as scan:children=sorted((Path(e.path) for e in scan),key=str)
                item['children_count']=len(children)
                for child in children:walk(child)
        walk(SCRATCH)
    problems=[e for e in entries if e['uid']!=1278 or e['kind'] not in ('directory','file') or e['kind']=='file' and e['nlink']!=1]
    candidates=[];unknown=[]
    for item in entries:
        if item['kind']!='file':continue
        path=Path(item['path'])
        if path.parent==NATIVE and path.name in EXPECTED:
            if item['uid']!=1278 or item['nlink']!=1:raise ValueError('EXACT_SOURCE_OWNER_OR_HARDLINK_DIFFERS')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                before=os.fstat(fd);data=os.read(fd,EXPECTED[path.name][0]+1);after=os.fstat(fd)
            finally:os.close(fd)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or (before.st_dev,before.st_ino)!=(item['device'],item['inode']) or data!=members[path.name]:raise ValueError('EXACT_SOURCE_DIFFERS_FROM_PERMANENT_DECOMPRESSED_MEMBER')
            candidates.append({**item,'sha256':sha(data),'permanent_member':path.name,'full_bytes_equal_permanent_backup':True})
        else:unknown.append(item)
    parents={str(p) for candidate in candidates for p in Path(candidate['path']).parents if p==SCRATCH or SCRATCH in p.parents}
    empty_parent_candidates=[e for e in entries if e['kind']=='directory' and e['path'] in parents]
    unrelated_directories=[e for e in entries if e['kind']=='directory' and e['path'] not in parents]
    fds=process_refs(entries)
    return {'schema':'WP5_EXACT_NODE14_5292_SCRATCH_INSPECTION_V1','status':'REVIEWABLE_EXACT_BACKED_UP_FILES_ONLY' if not problems and fds['no_same_uid_active_reference'] else 'ROOT_REVIEW_REQUIRED','time':time.time(),'hostname':socket.gethostname(),'uid':os.getuid(),'exact_root':str(SCRATCH),'source':reference(__file__),'permanent_evidence':archived,'actual_parent_accounting':account,'entries':entries,'scope_or_type_issues':problems,'open_reference_check':fds,'delete_file_allowlist':candidates,'eligible_empty_parent_directories_deepest_first':sorted(empty_parent_candidates,key=lambda e:len(Path(e['path']).parts),reverse=True),'unrelated_directories_preserve':unrelated_directories,'unknown_unbacked_files_preserve':unknown,'known_backed_file_bytes':sum(e['bytes'] for e in candidates),'files_deleted':0,'directory_removed':0,'scientific_files_or_receipts_written':False,'QM_calls':0,'historical_scratch_clean_rewritten':False}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accounting',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    result=collect(args.accounting)
    if args.out.exists() or not args.out.resolve().is_relative_to(ROOT/'acceptance'):raise ValueError('OWN_WRITE_ONCE_ACCEPTANCE_REPORT_REQUIRED')
    with args.out.open('x') as stream:json.dump(result,stream,ensure_ascii=False,allow_nan=False,indent=2);stream.write('\n')
    print(json.dumps({'report':str(args.out),'status':result['status'],'entries':len(result['entries']),'known_backed_files':len(result['delete_file_allowlist']),'known_backed_bytes':result['known_backed_file_bytes'],'unknown_unbacked_files':[e['path'] for e in result['unknown_unbacked_files_preserve']],'unrelated_directories':[e['path'] for e in result['unrelated_directories_preserve']],'active_references':result['open_reference_check']['matching_open_FDs_or_cwd'],'same_uid_FD_errors':result['open_reference_check']['same_uid_inspection_errors'],'files_deleted':0}))
if __name__=='__main__':main()
