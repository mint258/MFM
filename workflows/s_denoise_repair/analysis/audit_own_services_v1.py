"""One-shot Sonmi metadata audit of this task's two existing services; never starts/stops a process."""
import argparse,hashlib,json,os,socket,time
from collections import Counter
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')

def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))

def service(pointer_path,required):
    pointer=json.loads(pointer_path.read_text());path=Path(pointer['identity_path']);assert path.is_relative_to(R/'control')
    assert ref(path)['sha256']==pointer['identity_sha256'];identity=json.loads(path.read_text())
    assert identity['uid']==os.getuid()==1278 and identity['host']=='sonmi' and identity['scientific_processes_started']==0
    pid=identity['pid'];proc=Path('/proc')/str(pid)
    assert proc.stat().st_uid==1278
    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    assert fields[0]!='Z' and fields[19]==str(identity['start_ticks'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==identity['boot_id']
    argv=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
    assert argv==identity['argv']
    source=Path(identity.get('source_path',argv[-1]));assert source.is_relative_to(R)
    assert ref(source)['sha256']==identity['source_sha256']
    remaining=identity['expires_unix_seconds']-time.time();assert remaining>=required,'SERVICE_LEASE_TOO_SHORT'
    return pointer,path,identity,dict(pid=pid,uid=1278,start_ticks=fields[19],boot_id=identity['boot_id'],
        process_state=fields[0],argv=argv,source_reference=ref(source),remaining_seconds=remaining,identity_reference=ref(path))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job-wall-seconds',type=int,default=18000);a=ap.parse_args()
    assert socket.gethostname().split('.')[0]=='sonmi' and os.getuid()==1278 and 0<a.job_wall_seconds<=86400
    required=a.job_wall_seconds+1800
    qp,_,qi,quota_service=service(R/'control/live_quota_v1/current.json',required)
    latest=Path(qp['latest_path']);q=json.loads(latest.read_text());now=time.time()
    assert q['complete'] and q['returncode']==0 and q['owner_uid']==1278 and q['publisher_pid']==qi['pid']
    assert q['publisher_source_sha256']==qi['source_sha256'] and 0<=now-q['sampled_unix_seconds']<=90
    assert hashlib.sha256(q['raw_stdout'].encode()).hexdigest()==q['raw_stdout_sha256']
    assert q['limit_kib']>q['used_kib'] and q['limit_kib']-q['used_kib']>=8*1024**2
    _,archive_path,ai,archive_service=service(R/'control/wandb_archive_service_v1/current.json',required)
    archiver=R/'analysis/archive_s_repair_wandb_v4.py';assert ref(archiver)['sha256']==ai['archiver_sha256']
    status_path=archive_path.with_name('status.json');status=json.loads(status_path.read_text())
    assert status['status']=='ARCHIVE_SERVICE_HEALTHY' and status['returncode']==0 and 0<=now-status['timestamp']<=1200
    receipt_path=Path(status['receipt_path']);assert ref(receipt_path)['sha256']==status['receipt_sha256']
    receipt=json.loads(receipt_path.read_text());assert receipt['errors']==[]
    doc=dict(status='OWN_SREPAIR_METADATA_SERVICES_ACTUAL_IDENTITY_AND_LEASE_PASS',captured_unix=now,required_job_wall_seconds=a.job_wall_seconds,
        required_close_margin_seconds=1800,quota_service=quota_service,archive_service=archive_service,
        quota_latest_reference=ref(latest),quota_sample_age_seconds=now-q['sampled_unix_seconds'],
        quota_used_KiB=q['used_kib'],quota_limit_KiB=q['limit_kib'],
        archive_status_reference=ref(status_path),archive_receipt_reference=ref(receipt_path),
        archive_counts=dict(Counter(row['archival_status'] for row in receipt['records'])),
        scientific_processes_started=0,processes_changed=0)
    folder=R/'control/service_health_audits';folder.mkdir(exist_ok=True);dest=folder/('audit_'+str(time.time_ns())+'.json')
    with dest.open('x') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=doc['status'],quota_pid=qi['pid'],archive_pid=ai['pid'],archive_counts=doc['archive_counts'],output=str(dest))))

if __name__=='__main__':main()
