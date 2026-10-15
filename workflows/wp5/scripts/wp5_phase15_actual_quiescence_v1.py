"""Root metadata-only, fresh actual463 terminal accounting and six-node /proc proof."""
import concurrent.futures,hashlib,json,os,pathlib,shlex,socket,subprocess,time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
QUEUE=ROOT/'queue/pending.sqlite'
NODES=['compute-0-'+str(n) for n in (12,13,14,17,18,19,20)]
NODE_CODE=r'''
import pathlib,os,json,socket,time
queue='/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/queue/pending.sqlite'
root='/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011'
patterns=('wp5_runner_v','wp5_queue_reconcile_v','wp5_queue_mirror_copy_v','wp5_terminal_export_repair_v','wp5_hourly_observe_v','wp5_production_bootstrap_v')
hits=[];errors=[];transport=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  if p.stat().st_uid!=1278:continue
  argv=(p/'cmdline').read_bytes().split(b'\0');args=[x.decode(errors='replace') for x in argv if x]
  if not args:continue
  comm=(p/'comm').read_text().strip()
  if (args==['(sd-pam)'] and comm=='(sd-pam)') or (args==['sshd: zixiao@notty'] and comm=='sshd'):
   transport.append({'pid':int(p.name),'argv':args,'comm':comm,'role':'OWN_SSH_AUTH_TRANSPORT_NO_SCIENCE'});continue
  exact=[a for a in args if a.startswith(root+'/scripts/') and pathlib.Path(a).name.startswith(patterns)]
  fds=[]
  for f in (p/'fd').iterdir():
   try:
    target=os.readlink(f)
    if target==queue or target.startswith(queue+'-'):
     fds.append({'fd':f.name,'target':target,'fdinfo':(p/'fdinfo'/f.name).read_text()})
   except (FileNotFoundError,ProcessLookupError):pass
  if exact or fds:hits.append({'pid':int(p.name),'argv':args,'matched_scripts':exact,'queue_fds':fds})
 except (FileNotFoundError,ProcessLookupError):pass
 except OSError as exc:errors.append({'pid':p.name,'errno':exc.errno,'message':str(exc),'argv':args,'comm':(p/'comm').read_text().strip()})
print(json.dumps({'node':socket.gethostname().split('.')[0],'uid':os.getuid(),'time':time.time(),'hits':hits,'errors':errors,'excluded_own_ssh_auth_transport':transport}))
'''
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def node_probe(node):
 cmd='/share/home/zixiao/.conda/envs/chemprop/bin/python -B -c '+shlex.quote(NODE_CODE)
 p=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',node,cmd],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
 if p.returncode:raise RuntimeError('NODE_PROBE_FAILED:'+node+':'+p.stderr)
 d=json.loads(p.stdout);assert d['uid']==1278 and d['node']==node
 return d

def main():
 assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
 control=ROOT/'reports/wp5_acceptance_control_jobmap_actual463_v1.json';doc=json.loads(control.read_text())
 ids=sorted({str(x['job_id']) for x in doc['jobs']},key=int);assert len(ids)==463 and doc['actual_job_count']==463
 p=subprocess.run(['sacct','-X','-n','-P','-j',','.join(ids),'--format=JobIDRaw,User,State,ExitCode,Start,End,ElapsedRaw,AllocCPUS,NodeList'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
 assert p.returncode==0
 rows=[x.split('|') for x in p.stdout.splitlines() if x.strip()];states={x[0]:x[2].split()[0].rstrip('+') for x in rows if x[0] in set(ids) and x[1]=='zixiao'}
 terminal={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED','REVOKED'}
 all_terminal=set(states)==set(ids) and all(v in terminal for v in states.values())
 results=list(concurrent.futures.ThreadPoolExecutor(max_workers=7).map(node_probe,NODES))
 stamp=str(time.time_ns());out=ROOT/'reports'/('actual463_terminal_process_evidence_'+stamp+'.json')
 evidence={'created_epoch':time.time(),'jobmap':ref(control),'sacct':{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},'states':states,'all_terminal':all_terminal,'nodes':results,'source':ref(pathlib.Path(__file__))}
 save(out,evidence)
 clean=all_terminal and not any(x['hits'] or x['errors'] for x in results)
 proof={'schema':'WP5_QUEUE_MIRROR_QUIESCENCE_V1','status':'QUIESCENT' if clean else 'NOT_QUIESCENT','created_epoch':time.time(),'queue':str(QUEUE),'uid':1278,'actual_registered_job_count':463,'all_approved_nodes_checked':True,'no_remaining_queue_writers':clean,'control_readers_exited':clean,'evidence':[ref(out)],'source_SQLite_opened':False,'science_signalled':False}
 target=ROOT/'reports'/('actual463_quiescence_'+stamp+'.json');save(target,proof)
 print(json.dumps({'proof':ref(target),'status':proof['status'],'all_terminal':all_terminal,'node_hits':{x['node']:len(x['hits']) for x in results},'node_errors':{x['node']:len(x['errors']) for x in results}}))
if __name__=='__main__':main()