"""Read only exact9 old formal scratch entry metadata; no cache SQL/body scan or deletion."""
import argparse,hashlib,json,os,socket,stat,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011');F=ROOT/'acceptance/final_20261016_v1'
CASES=[('12','4514011','1','cdca4e54'),('13','4514004','61','ef62b93a'),('13','4514012','2','7931809b'),('17','4513981','12','64053ea8'),('17','4514000','50','9e0fb84d'),('17','4513999','49','cbf95ef1'),('17','4513986','36','7247bc11'),('18','4513982','58','ee63ed46'),('19','4513998','48','8a23ee84')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def info(p):
 s=p.lstat();return {'path':str(p),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid,'mode':s.st_mode,'nlink':s.st_nlink,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'kind':'file' if stat.S_ISREG(s.st_mode) else 'directory' if stat.S_ISDIR(s.st_mode) else 'UNEXPECTED'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();node=socket.gethostname().split('.')[0]
 if os.getuid()!=1278 or node not in {'compute-0-'+x[0] for x in CASES}:raise ValueError('EXACT_UID_AND_AUTHORIZED_FIVE_NODES_ONLY')
 if not a.out.absolute().is_relative_to(F):raise ValueError('OWNED_FINAL_METADATA_OUTPUT_REQUIRED')
 results=[];issues=[]
 for n,job,task,session in CASES:
  if node!='compute-0-'+n:continue
  root=Path('/tmp')/('wp5runtime_1278_'+job+'_'+session);run=ROOT/'runtime'/('task_'+task)/('job_'+job+'_'+session);r=json.loads((run/'run.json').read_text());idx=json.loads((run/'input_index.json').read_text());o=r['options']
  if r['node']!=node or str(o['job_id'])!=job or o['session'][:8]!=session or o['scratch_root']!=str(root) or o['local_index']!=str(root/'record_index.sqlite') or idx['path']!=o['local_index']:raise ValueError('ORIGINAL_RUN_INPUT_INDEX_IDENTITY_DIFFERS')
  row={'job_id':job,'node':node,'root':str(root),'run_metadata':ref(run/'run.json'),'input_index_metadata':ref(run/'input_index.json'),'index_molecules':idx['molecules'],'index_bytes':idx['bytes'],'exists':root.exists(),'entries':[]}
  if root.exists():
   entries=[info(root)]
   for current,dirs,files in os.walk(root,followlinks=False):
    for name in dirs+files:entries.append(info(Path(current)/name))
   row['entries']=entries;expected=root/'record_index.sqlite';files=[e for e in entries if e['kind']=='file']
   if len(entries)!=2 or len(files)!=1 or files[0]['path']!=str(expected) or files[0]['bytes']!=idx['bytes'] or any(e['uid']!=1278 or e['kind']=='UNEXPECTED' or (e['kind']=='file' and e['nlink']!=1) for e in entries):issues.append({'job_id':job,'issue':'EXACT_SINGLE_CACHE_SHAPE_OR_OWNER_DIFFERS'})
   else:
    fd=os.open(expected,os.O_RDONLY|os.O_NOFOLLOW)
    try:header=os.read(fd,16)
    finally:os.close(fd)
    row['sqlite_header_hex']=header.hex();row['sqlite_header_valid']=header==b'SQLite format 3\x00'
    if not row['sqlite_header_valid']:issues.append({'job_id':job,'issue':'CACHE_HEADER_NOT_SQLITE'})
  results.append(row)
 report={'schema':'WP5_EXACT9_DERIVED_CACHE_METADATA_INSPECTION_V1','status':'EXACT_SINGLE_REBUILDABLE_INPUT_CACHE_METADATA' if not issues else 'ROOT_REVIEW_REQUIRED','node':node,'uid':os.getuid(),'generated_epoch':time.time(),'cases':results,'issues':issues,'files_deleted':0,'cache_SQL_or_payload_opened':False,'only_16_byte_SQLite_header_read':True,'SCI_or_raw_opened':False,'script':ref(Path(__file__))}
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps({'out':str(a.out),'sha256':sha(a.out),'status':report['status'],'roots':len(results),'files_deleted':0}))
if __name__=='__main__':main()
