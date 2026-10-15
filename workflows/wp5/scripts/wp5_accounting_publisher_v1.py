"""Root login metadata publisher; bounded lifetime, no data or calculation scans."""
import argparse,hashlib,json,os,socket,time,traceback
from pathlib import Path
from wp5_monitor_v2 import ROOT,run,atomic

def publish():
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('Actual zixiao sonmi login required')
    registered=[]
    for path in sorted((ROOT/'logs').glob('*_submission.json')):
        row=json.loads(path.read_text())
        registered.append({'job_id':str(row['job_id']),'node':row['node'],'name':row.get('argv',[]),
          'receipt':str(path),'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'script':row['script'],'script_sha256':row['script_sha256']})
    ids=[row['job_id'] for row in registered]
    obj={'time':time.time(),'uid':os.getuid(),'hostname':socket.gethostname(),'registered':registered,
         'publisher':{'pid':os.getpid(),'script':str(Path(__file__).absolute()),
             'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
         'queue':run(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%M|%N|%R']),
         'quota':run(['quota','-v','-u','zixiao'])}
    if ids:obj['sacct']=run(['sacct','-X','-j',','.join(ids),'-n','-P',
           '--format=JobID,JobName,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    parts=[line.split() for line in obj['quota']['stdout'].splitlines() if line.strip().startswith('/dev/')]
    if obj['quota']['returncode']==0 and len(parts)==1:
        row=parts[0];remaining=(int(row[3])-int(row[1]))*1024
        obj['quota_parsed']={'used_kib':int(row[1]),'hard_limit_kib':int(row[3]),
           'remaining_bytes':remaining,'files_reported':int(row[4])}
        stop=ROOT/'STOP_NEW_MOLECULES.json'
        if remaining<300_000_000_000 and not stop.exists():
            atomic(stop,{'time':time.time(),'reason':'QUOTA_REMAINING_BELOW_300GB','remaining_bytes':remaining})
    states={};hours=0.0
    for line in obj.get('sacct',{}).get('stdout','').splitlines():
        fields=line.split('|')
        if len(fields)>=8 and fields[2]=='zixiao':
            states[fields[0]]=fields[3]
            hours+=int(fields[5])*int(fields[6])/3600
    obj['registered_job_states']=states;obj['registered_actual_allocated_core_hours']=hours
    atomic(ROOT/'reports/observation_latest.json',obj)
    return obj

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    parser.add_argument('--interval',type=float,default=60);parser.add_argument('--hours',type=float,default=240)
    args=parser.parse_args()
    if args.interval<30 or not 0<args.hours<=240:raise ValueError('Bounded metadata publisher required')
    started=time.time();deadline=started+args.hours*3600
    if not args.once:
        receipt=ROOT/'reports/accounting_publisher_process.json'
        if receipt.exists():
            prior=json.loads(receipt.read_text());stat=Path('/proc')/str(prior['pid'])/'stat'
            if stat.exists() and stat.read_text().split()[21]==str(prior['start_ticks']):
                raise ValueError('An existing registered publisher is still alive')
        atomic(receipt,{'pid':os.getpid(),'uid':os.getuid(),'hostname':socket.gethostname(),
          'start_ticks':Path('/proc/self/stat').read_text().split()[21],
          'script':str(Path(__file__).absolute()),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'start':started,'expires':deadline,'interval_seconds':args.interval})
    while True:
        try:
            obj=publish()
            if args.once:print(json.dumps({'status':'ACTUAL_LOGIN_METADATA_PUBLISHED','time':obj['time'],
                'registered':len(obj['registered']),'quota':obj.get('quota_parsed'),'states':obj['registered_job_states']}));return
        except BaseException:
            atomic(ROOT/'reports/accounting_publisher_error.json',{'time':time.time(),'traceback':traceback.format_exc()})
            if args.once:raise
        remaining=deadline-time.time()
        if remaining<=0:return
        time.sleep(min(args.interval,remaining))
if __name__=='__main__':main()
