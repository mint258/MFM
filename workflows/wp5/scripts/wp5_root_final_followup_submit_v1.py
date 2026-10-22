#!/usr/bin/env python3
"""Root-only actual submission of bounded WP5 final metadata follow-ups."""
import argparse,copy,hashlib,json,pathlib,re,subprocess,time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
F=ROOT/'acceptance/final_20261016_v1'
STATE=ROOT/'reports/home_stat_inventory_v2_20261016'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def save(p,x):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise RuntimeError('Refuse replacing existing output '+str(p))
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def call(a):
 t=time.time();r=subprocess.run(list(map(str,a)),text=True,capture_output=True,stdin=subprocess.DEVNULL)
 return {'argv':list(map(str,a)),'epoch':t,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def ok(a):
 x=call(a)
 if x['returncode']:raise RuntimeError(json.dumps(x))
 return x
def mem(s):
 m=re.fullmatch(r'([0-9.]+)([KMGTP]?)',s)
 if not m:raise RuntimeError('Unknown memory '+s)
 return float(m[1])*{'':1,'K':1/1024,'M':1,'G':1024,'T':1024**2,'P':1024**3}[m[2]]
def kv(s):return dict(re.findall(r'(\w+)=([^\s]+)',s))
def prepare_node(node):
 z={'sinfo':ok(['sinfo','-N','-n',node,'-o','%N %P %t %c %m']),
 'node':ok(['scontrol','show','node',node,'-o']),
 'partition':ok(['scontrol','show','partition','cpu','-o']),
 'all_user_queue':ok(['squeue','-w',node,'-t','RUNNING,COMPLETING','-h','-o','%i|%u|%C|%m|%N'])}
 n=kv(z['node']['stdout']);total=0;ds=[]
 for ln in z['all_user_queue']['stdout'].splitlines():
  if not ln.strip():continue
  j=ln.split('|')[0];o=ok(['scontrol','show','job',j,'-o']);d=kv(o['stdout'])
  if 'MinMemoryNode' in d:v=mem(d['MinMemoryNode'])
  elif 'MinMemoryCPU' in d:v=mem(d['MinMemoryCPU'])*int(d['NumCPUs'])
  else:raise RuntimeError('Unknown declared job memory '+j)
  total+=v;ds.append({'job':j,'declared_memory_mib_for_node_or_conservative_full_job':v,'query':o})
 free=int(n.get('CPUEfctv',n['CPUTot']))-int(n['CPUAlloc'])
 ratio=(max(float(n['AllocMem']),total)+32768)/float(n['RealMemory'])
 if free<24 or ratio>0.85 or any(s in n['State'] for s in ['DOWN','DRAIN','FAIL']):raise RuntimeError('Node admission failed')
 z.update(job_declarations=ds,gate={'cpu_free':free,'requested_cpu':24,'requested_memory_mib':32768,'declaration_ratio':ratio})
 return z
def main():
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['g0resume','shared'],required=True)
 a.add_argument('--base-map',required=True);a.add_argument('--new-map',required=True);a.add_argument('--out',required=True)
 a.add_argument('--shard',type=int);a.add_argument('--old-parent');a.add_argument('--collector',default='4515513')
 a.add_argument('--node-reports',nargs='*');a.add_argument('--execute',action='store_true');x=a.parse_args()
 out=pathlib.Path(x.out);assert out.parent==F and not out.exists()
 oldmap=pathlib.Path(x.base_map);newmap=pathlib.Path(x.new_map)
 assert oldmap.parent==F and newmap.parent==F and not newmap.exists()
 base=json.loads(oldmap.read_text());assert len(base['jobs'])==base['actual_job_count']
 formal=json.loads((F/'control_jobmap_actual542_v1.json').read_text());assert formal['actual_job_count']==542
 formalids={str(z['job_id']) for z in formal['jobs']};assert len(formalids)==542
 assert not formalids.intersection(str(z['job_id']) for z in base['jobs'])
 if x.mode=='g0resume':
  assert x.shard in [0,3,4] and x.old_parent and x.old_parent.isdigit()
  node={0:'compute-0-12',3:'compute-0-17',4:'compute-0-18'}[x.shard]
  report=STATE/('shard_'+str(x.shard)+'_last_report.json')
  z=json.loads(report.read_text());assert z['job_id']==x.old_parent and z['error_directories']==0
  assert sum(v for k,v in z['states'].items() if k!='DONE')>0
  term=ok(['sacct','-X','-n','-P','-j',x.old_parent,'--format=JobIDRaw,User,State,ExitCode,Start,End,ElapsedRaw,AllocCPUS'])
  row=[s.split('|') for s in term['stdout'].splitlines() if s.startswith(x.old_parent+'|')]
  assert len(row)==1 and row[0][1]=='zixiao' and row[0][2]=='COMPLETED' and row[0][3]=='0:0'
  batch=ROOT/'scripts/wp5_file_inventory_v3.sbatch';src=ROOT/'scripts/wp5_file_inventory_v3.py'
  assert ref(src)['sha256']=='dea339a9b6444791c575738cad7185a202ec0578002c3d8adff385a9ba9571b2'
  assert ref(batch)['sha256']=='e50e02a52c674f19bf1ebf41b816acaa6a5d1f3977e5683dc282920903544519'
  args=['scan',str(STATE),str(x.shard),'--directory-budget-seconds','165600']
  extra={'prior_actual_terminal_accounting':term,'checkpoint':ref(report),'checkpoint_states':z['states'],'directory_budget_seconds':165600,'DONE_directories_retained':True}
  col=ok(['scontrol','show','job',x.collector,'-o']);assert kv(col['stdout'])['JobState']=='PENDING'
  extra['collector_before']=col
 else:
  node='compute-0-17';assert x.node_reports and len(x.node_reports)==6
  reports=[]
  for p in x.node_reports:
   z=json.loads(pathlib.Path(p).read_text());assert z['status']=='PASS' and z['actual_scratch_empty'] and not z['issues']
   assert z['bindings']['jobmap_sha256']==ref(F/'control_jobmap_actual542_v1.json')['sha256']
   reports.append({'node':z['node'],'reference':ref(p)})
  assert {v['node'] for v in reports}=={'compute-0-'+str(n) for n in [12,13,14,17,18,19]}
  batch=ROOT/'scripts/wp5_acceptance_storage_v3.sbatch';src=ROOT/'scripts/wp5_acceptance_storage_v3.py'
  assert ref(src)['sha256']=='5ff8474f1f376ada63fa62dd08848832bbd5160c8956a0401a0b799e23c94a12'
  assert ref(batch)['sha256']=='67d45197cacbe8c7d3b008c2ff7efff89b7cee14360e46a0f7fc0b13a8f8c664'
  args=['--scope','shared','--jobmap',str(F/'control_jobmap_actual542_v1.json'),'--node-storage-reports']+x.node_reports
  extra={'actual_six_node_reports':reports}
 pre={'epoch':time.time(),'node':prepare_node(node),'quota':ok(['quota','-v','-u','zixiao'])}
 lines=[s.split() for s in pre['quota']['stdout'].splitlines() if s.strip().startswith('/dev/')]
 assert len(lines)==1
 remaining=(int(lines[0][3])-int(lines[0][1]))*1024;assert remaining>=600_000_000_000
 pre['quota_remaining_bytes']=remaining
 compile(src.read_text(),str(src),'exec');syntax=ok(['bash','-n',str(batch)])
 out.mkdir();save(out/'preflight.json',pre)
 request={'epoch':time.time(),'mode':x.mode,'node':node,'root_metadata_dispatcher':ref(__file__),'source':ref(src),'batch':ref(batch),'base_actual_qa_map':ref(oldmap),'preflight':ref(out/'preflight.json'),'bash_n':syntax,'extra':extra,'new_QM_calls':0}
 save(out/'request.json',request)
 if not x.execute:print(json.dumps({'status':'PREPARED_ONLY','out':str(out)}));return
 if x.mode=='g0resume':save(out/'collector_hold.json',ok(['scontrol','hold',x.collector]))
 argv=['sbatch','--parsable','--nodelist='+node,str(batch)]+args
 receipt=call(argv);save(out/'submission.json',receipt)
 if receipt['returncode']:raise RuntimeError('sbatch failed; inspect receipt and collector hold')
 j=receipt['stdout'].strip().split(';')[0];assert j.isdigit()
 snap=ok(['scontrol','show','job',j,'-o']);save(out/'scontrol_actual.json',snap)
 if x.mode=='g0resume':
  deps=['4515531','4515552',j] if x.shard==4 else ([j,'4515552'] if x.shard==3 else [j])
  # Retain actual other unfinished G0 scans found in current dependency and actual map.
  prior=extra['collector_before']['stdout']
  deps.extend(re.findall(r'afterany:(\d+)\(unfulfilled\)',prior))
  deps=sorted(set(deps)-{x.old_parent},key=int)
  save(out/'collector_update.json',ok(['scontrol','update','JobId='+x.collector,'Dependency=afterany:'+':'.join(deps)]))
  save(out/'collector_release.json',ok(['scontrol','release',x.collector]))
  save(out/'collector_after.json',ok(['scontrol','show','job',x.collector,'-o']))
 formal=json.loads((F/'control_jobmap_actual542_v1.json').read_text())
 assert j not in {str(z['job_id']) for z in formal['jobs']} and j not in {str(z['job_id']) for z in base['jobs']}
 entry={'job_id':j,'role':'G0_UNFINISHED_SHARD_MAX46H_DIRECTORY_RESUME' if x.mode=='g0resume' else 'FINAL_SHARED_STORAGE3_AUDIT_AFTER_SIX_ACTUAL_NODE_PASS',
 'node':node,'node_basis':'Actual sbatch nodelist override and saved scontrol ReqNodeList','user':'zixiao',
 'actually_submitted':True,'submission_time':receipt['epoch'],'submission_verified_from_actual_receipt':True,
 'saved_scheduler_snapshot_state':kv(snap['stdout'])['JobState'],'scheduler_snapshot_is_current_claim':False,
 'terminal_accounting_bound':False,'terminal_state_from_bound_accounting':None,
 'source_evidence':[{'kind':'ACTUAL_SBATCH_RECEIPT','reference':ref(out/'submission.json'),'stdout_pointer':'/stdout'},
 {'kind':'ACTUAL_SCONTROL_SNAPSHOT','reference':ref(out/'scontrol_actual.json'),'stdout_pointer':'/stdout'},
 {'kind':'ROOT_SOURCE_AND_ACTUAL_INPUT_BINDING_REVIEW','reference':ref(out/'request.json')}]}
 result=copy.deepcopy(base);result['jobs'].append(entry);result['actual_job_count']=len(result['jobs']);result['created_epoch']=time.time()
 result['supersedes']=ref(oldmap);result['formal_overlap_count']=0
 result['evidence_coverage']={'actual_submissions_verified':len(result['jobs']),'new_submission_receipt_and_scontrol_bound':True,'terminal_state_claims':'Historical snapshots only; final actual terminal accounting required'}
 save(newmap,result)
 save(out/'submitted_actual.json',{'schema':'WP5_ROOT_ACTUAL_FINAL_FOLLOWUP_SUBMISSION_V1','job_id':j,'role':entry['role'],'node':node,'actual_qa_map':ref(newmap),'request':ref(out/'request.json'),'receipt':ref(out/'submission.json')})
 print(json.dumps({'job_id':j,'node':node,'actual_qa_map':ref(newmap),'out':str(out)}))
if __name__=='__main__':main()
