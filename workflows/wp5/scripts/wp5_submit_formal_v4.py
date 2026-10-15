"""Root-only one-phase WP5 main and dependent cleanup submission."""
import argparse,ast,hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
NODES={f'compute-0-{n}' for n in range(14,20)}
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):value.update(block)
    return value.hexdigest()
def atomic(path,obj):
    temp=path.with_name(path.name+'.pending')
    with temp.open('w') as stream:
        json.dump(obj,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def prepare():
    tasks=json.loads((ROOT/'packing/node_assignment_v2/tasks.json').read_text())['tasks']
    ids=[str(t['task_id']) for t in tasks]
    if len(set(ids))!=len(ids) or not tasks or set(t['node'] for t in tasks)!=NODES:
        raise ValueError('Frozen task/node identity not closed')
    main=[{'name':'wp5_formal_main_'+str(t['task_id']),'task_id':str(t['task_id']),
           'node':t['node'],'mode':'main'} for t in tasks]
    cleanup=[{'name':'wp5_formal_cleanup_'+str(n),'task_id':'cleanup_'+str(n),
              'node':'compute-0-'+str(n),'mode':'cleanup',
              'afterany_main_names':[r['name'] for r in main if r['node']=='compute-0-'+str(n)]}
              for n in range(14,20)]
    return {'status':'PREPARED_NOT_SUBMITTED','main':main,'cleanup':cleanup,
            'tasks_sha256':digest(ROOT/'packing/node_assignment_v2/tasks.json'),'script':str(ROOT/'scripts/wp5_main_v6.sbatch'),
            'script_sha256':digest(ROOT/'scripts/wp5_main_v6.sbatch'),
            'resources':{'cpus':24,'memory_gib':32,'time':'48:00:00'},
            'submission_policy':'All main jobs then all six node-specific afterany cleanup jobs in one phase; no waves'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--submit',action='store_true')
    args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_SUBMISSION');return
    directory=ROOT/'submission';directory.mkdir(exist_ok=True)
    plan=prepare()
    if args.prepare:
        destination=directory/'prepared_plan_v4.json'
        if destination.exists() and json.loads(destination.read_text())!=plan:raise ValueError('Prepared plan changed')
        if not destination.exists():atomic(destination,plan)
        print(json.dumps({'plan':str(destination),'main_jobs':len(plan['main']),'cleanup_jobs':6}));return
    if not args.submit:parser.error('Choose --prepare or --submit')
    gate=ROOT/'gates/g0_ready_for_formal.json'
    if not gate.exists():raise ValueError('Actual remaining G0 evidence is not yet closed')
    ready=json.loads(gate.read_text())
    if ready['status']!='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION':raise ValueError('G0 not ready')
    for name in ['G1','G2','G3','G4','G6']:
        if ready['gates'][name]['status']!='PASS':raise ValueError(name+' not passed')
    if ready['gates']['G5']['status']!='USER_APPROVED_HISTORICAL_RAW_EXCEPTION':raise ValueError('G5 exception not bound')
    for evidence in ready['bindings']:
        if digest(evidence['path'])!=evidence['sha256']:raise ValueError('G0 frozen binding changed: '+evidence['path'])
    if (ROOT/'STOP_NEW_MOLECULES.json').exists():raise ValueError('A real runtime stop condition is still active')
    policy=ready['raw_policy']
    if policy not in ('ALL','SELECTIVE'):raise ValueError('G3 policy not selected')
    result_path=directory/'submitted_jobs.json'
    if result_path.exists():raise ValueError('Submission phase already exists; inspect its actual IDs before any continuation')
    lock=directory/'root_submit.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.write(fd,json.dumps({'pid':os.getpid(),'uid':os.getuid(),'time':time.time()}).encode());os.close(fd)
    result={'status':'ONE_PHASE_SUBMISSION_IN_PROGRESS','start':time.time(),'g0_sha256':digest(gate),
            'prepared_plan':plan,'main':[],'cleanup':[],'error':None}
    atomic(result_path,result)
    try:
        environment=dict(os.environ)
        environment.update(WP5_DICTIONARIES=ready['dictionary_manifest'],WP5_BASELINE=str(ROOT/'configs/pilot_success_baseline.json'),WP5_POLICY=policy)
        for role in ['main','cleanup']:
            for item in plan[role]:
                environment.update(WP5_TASK_ID=item['task_id'],WP5_MODE=item['mode'])
                command=[PYTHON,'-B',str(ROOT/'scripts/submit_wp5_job.py'),'--script',plan['script'],
                  '--name',item['name'],'--node',item['node'],'--cpus','24','--memory-gb','32',
                  '--time','48:00:00','--kind','quantum','--allow-pending']
                if role=='cleanup':
                    ids=[row['job_id'] for row in result['main'] if row['node']==item['node']]
                    if not ids:raise ValueError('Cleanup has no own-node main dependencies')
                    command+=['--dependency','afterany:'+':'.join(ids)]
                process=subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
                if process.returncode:raise RuntimeError(item['name']+': '+process.stderr)
                receipt=json.loads(process.stdout)
                result[role].append({**item,**receipt});atomic(result_path,result)
                print(json.dumps({'role':role,'task_id':item['task_id'],'job_id':receipt['job_id'],'node':item['node']}),flush=True)
        result['status']='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED';result['end']=time.time();atomic(result_path,result)
    except BaseException as exc:
        result['status']='PARTIAL_ONE_PHASE_SUBMISSION_REQUIRES_ROOT_RECONCILIATION'
        result['error']=repr(exc);atomic(result_path,result);raise
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
