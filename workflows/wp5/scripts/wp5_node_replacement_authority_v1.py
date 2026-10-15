"""Root-only metadata relabel of user-approved WP5 node scope; no QM."""
import argparse, ast, collections, copy, hashlib, json, os, socket, subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
MAP={'compute-0-15':'compute-0-12','compute-0-16':'compute-0-13'}
APPROVAL=ROOT/'gates/wp5_node_replacement_user_approved.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def put(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def relabel(obj):
    if isinstance(obj,dict):return {MAP.get(k,k):relabel(v) for k,v in obj.items()}
    if isinstance(obj,list):return [relabel(v) for v in obj]
    if isinstance(obj,str):return MAP.get(obj,obj)
    return obj

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--prepare',action='store_true');p.add_argument('--cancel-old-pending',action='store_true');a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('AST_PASS_METADATA_ONLY');return
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('Root login zixiao/sonmi required')
    authority=read(APPROVAL)
    if authority['status']!='USER_APPROVED' or authority['old_to_new']!=MAP or authority['G3_capacity_waived']:raise ValueError('Exact explicit WP5 node approval required')
    if a.prepare:
        source=ROOT/'packing/node_assignment_v2/tasks.json';old_manifest=ROOT/'packing/node_assignment_v2/manifest.json'
        if sha(source)!='b150ab15d336c7dbfec280b114ce9b69b689f11484728021678db04a75a9404c':raise ValueError('Frozen original node plan changed')
        old=read(source);new=copy.deepcopy(old)
        if len(old['tasks'])!=72:raise ValueError('72 original tasks required')
        for before,after in zip(old['tasks'],new['tasks']):
            after['node']=MAP.get(before['node'],before['node'])
            if {k:v for k,v in before.items() if k!='node'}!={k:v for k,v in after.items() if k!='node'}:raise ValueError('Scientific/task scheduling fields changed')
        new['authorized_node_slots']=relabel(old['authorized_node_slots'])
        if new['authorized_node_slots']!=authority['authorized_node_slots']:raise ValueError('Authorized slots differ')
        target=ROOT/'packing/node_assignment_v3/tasks.json';put(target,new)
        manifest=relabel(read(old_manifest))
        manifest.update(schema='WP5_NODE_ASSIGNMENT_V3',source_tasks=str(source),source_tasks_sha256=sha(source),tasks=str(target),tasks_sha256=sha(target),
            previous_node_assignment_manifest={'path':str(old_manifest),'sha256':sha(old_manifest)},
            user_approval={'path':str(APPROVAL),'sha256':sha(APPROVAL)},modified_task_fields=['node'],
            assignment_rule='User approved this WP5 actual15->12 and16->13; exact task content, node_slot and predicted ordering unchanged',
            node_capacity=new['authorized_node_slots'],node_counts=dict(collections.Counter(t['node'] for t in new['tasks'])),
            all_other_task_fields_unchanged=True,new_QM_calls=0,original_dataset_written=False)
        put(target.parent/'manifest.json',manifest)
        print(json.dumps({'status':'EXACT_NODE_ONLY_REPLACEMENT_PASSED','tasks':str(target),'tasks_sha256':sha(target),'manifest_sha256':sha(target.parent/'manifest.json'),'approval_sha256':sha(APPROVAL),'task_count':len(new['tasks']),'records':sum(t['records'] for t in new['tasks']),'molecules':sum(t['molecules'] for t in new['tasks']),'node_counts':manifest['node_counts']}))
    if a.cancel_old_pending:
        evidence=[]
        for jid,name,node in [('4513919','wp5_g6_v6_15','compute-0-15'),('4513920','wp5_g6_v6_16','compute-0-16')]:
            result=subprocess.run(['scontrol','show','job','-o',jid],text=True,capture_output=True,check=True)
            fields=dict(x.split('=',1) for x in result.stdout.split() if '=' in x)
            if fields.get('UserId')!='zixiao(1278)' or fields.get('JobName')!=name or fields.get('JobState')!='PENDING' or fields.get('RunTime')!='00:00:00' or fields.get('ReqNodeList')!=node:raise ValueError('Only exact own unstarted replacement jobs can be cancelled: '+result.stdout)
            evidence.append({'job_id':jid,'scontrol_before':{'stdout':result.stdout,'stderr':result.stderr,'returncode':result.returncode}})
        cancel=subprocess.run(['scancel','4513919','4513920'],text=True,capture_output=True,check=True)
        for entry in evidence:
            q=subprocess.run(['sacct','-X','-j',entry['job_id'],'-n','-P','--format=JobID,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],text=True,capture_output=True)
            entry['sacct_after']={'stdout':q.stdout,'stderr':q.stderr,'returncode':q.returncode}
        put(ROOT/'reports/obsolete_pending_15_16_cancel_v1.json',{'status':'OWN_UNSTARTED_REPLACEMENT_QUEUE_CANCELLED','approval':{'path':str(APPROVAL),'sha256':sha(APPROVAL)},'jobs':evidence,'scancel':{'stdout':cancel.stdout,'stderr':cancel.stderr,'returncode':cancel.returncode},'QM_stopped':False})
        print('OWN_UNSTARTED_4513919_4513920_CANCELLED')
if __name__=='__main__':main()
