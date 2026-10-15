"""Root-only read-only WP5 observations, accounting and quota stop flag."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def run(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    return {'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def atomic(path,obj):
    tmp=path.with_name(path.name+'.pending');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,path)
def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='latest');a=p.parse_args()
    submissions=[]
    for path in sorted((ROOT/'logs').glob('*_submission.json')):
        r=json.loads(path.read_text());submissions.append({'job_id':str(r['job_id']),'node':r['node'],
           'name':r.get('argv',[]),'receipt':str(path),'script':r['script'],'script_sha256':r['script_sha256']})
    ids=[r['job_id'] for r in submissions]
    result={'time':time.time(),'uid':os.getuid(),'hostname':os.uname().nodename,'registered':submissions,
        'queue':run(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%M|%N|%R']),
        'quota':run(['quota','-v','-u','zixiao'])}
    if ids:result['sacct']=run(['sacct','-X','-j',','.join(ids),'-n','-P','--format=JobID,JobName,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    parts=[x.split() for x in result['quota']['stdout'].splitlines() if x.strip().startswith('/dev/')]
    if result['quota']['returncode']==0 and len(parts)==1:
        q=parts[0];remaining=(int(q[3])-int(q[1]))*1024
        result['quota_parsed']={'used_kib':int(q[1]),'hard_limit_kib':int(q[3]),'remaining_bytes':remaining,'files_reported':int(q[4])}
        if remaining<300_000_000_000:
            stop=ROOT/'STOP_NEW_MOLECULES.json'
            if not stop.exists():atomic(stop,{'time':time.time(),'reason':'QUOTA_REMAINING_BELOW_300GB','remaining_bytes':remaining})
    result['closed_metadata']={}
    for key,relative in [('population','population/manifest.json'),('packing','packing/manifest.json'),
         ('inventory','reports/account_top_level_inventory.json'),
         ('g6_14','gates/g6/compute-0-14/report.json')]:
        path=ROOT/relative
        if path.is_file():
            info=json.loads(path.read_text())
            result['closed_metadata'][key]={'path':str(path),'status':info.get('status'),'bytes':path.stat().st_size,
                 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    result['gate_jobs']={}
    for gate,folder in [('g3','gates/g3'),('g5','gates/G5_parser_regression')]:
        entries=[]
        for directory in sorted((ROOT/folder).glob('job_*')):
            item={'directory':str(directory),'job_id':directory.name.removeprefix('job_')}
            for name in ['report.json','progress.json','formal_pilot_source_context.context_closure.json','benchmark.json']:
                path=directory/name
                if path.is_file():
                    obj=json.loads(path.read_text())
                    item[name]={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':obj.get('status'),'progress':obj if name=='progress.json' else None}
            entries.append(item)
        result['gate_jobs'][gate]=entries
    actual_hours=0.0
    states={}
    for line in result.get('sacct',{}).get('stdout','').splitlines():
        fields=line.split('|')
        if len(fields)>=8 and fields[2]=='zixiao':
            states[fields[0]]=fields[3]
            try:actual_hours+=int(fields[5])*int(fields[6])/3600
            except ValueError:pass
    result['registered_actual_allocated_core_hours']=actual_hours
    result['registered_job_states']=states
    result['current_run_file_count']=None
    if a.tag!='latest':
        count=0;size=0
        for directory,dirs,files in os.walk(ROOT,followlinks=False):
            for name in files:
                path=Path(directory)/name
                if not path.is_symlink():
                    try:count+=1;size+=path.stat().st_size
                    except FileNotFoundError:pass
        result['current_run_file_count']=count;result['current_run_bytes']=size
    destination=ROOT/'reports'/('observation_'+a.tag+'.json');atomic(destination,result)
    print(json.dumps({'observation':str(destination),'quota':result.get('quota_parsed'),'closed_metadata':result['closed_metadata'],
          'queue':result['queue']['stdout'],'sacct':result.get('sacct',{}).get('stdout','')},ensure_ascii=False))
if __name__=='__main__':main()
