from pathlib import Path
import json, os, stat, subprocess, time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
BASE=ROOT/'gates/metadata_queue_production_shape'
MANIFESTS=('production_shape_r12_v2_test_v3_lifecycle',)
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','BOOT_FAIL','PREEMPTED','DEADLINE','REVOKED'}
report={'schema':'WP5_ENDED_OWN_METADATA_FIXTURE_CLEANUP_V2','uid':os.getuid(),'time':time.time(),'files':[],'fixtures':[]}
assert os.getuid()==1278
for name in MANIFESTS:
    receipt=ROOT/'submission'/name/'submitted_jobs.json'
    d=json.loads(receipt.read_text())
    assert d['production_writes'] is False and d['QM'] is False
    fixture=Path(d['fixture'])
    assert fixture.parent.resolve()==BASE.resolve() and not fixture.is_symlink()
    job_ids=[str(j['job_id']) for j in d['jobs']]
    q=subprocess.run(['squeue','-h','-j',','.join(job_ids),'-o','%i %u %T'],text=True,capture_output=True,check=True)
    if q.stdout.strip():raise RuntimeError('Fixture still has live test jobs: '+q.stdout)
    a=subprocess.run(['sacct','-n','-X','-P','-j',','.join(job_ids),'--format=JobIDRaw,User,UID,State,AllocCPUS,ElapsedRaw'],text=True,capture_output=True,check=True)
    actual={}
    for line in a.stdout.splitlines():
        fields=line.split('|')
        if len(fields)>=6 and fields[0] in job_ids:actual[fields[0]]=fields
    assert set(actual)==set(job_ids),('Missing actual accounting',set(job_ids)-set(actual))
    for jid,fields in actual.items():
        assert fields[1]=='zixiao' and fields[2]=='1278'
        assert fields[3].split()[0].split('+')[0] in TERMINAL,(jid,fields[3])
    saved={'fixture':str(fixture),'submission':str(receipt),'actual_jobs':actual,'scientific_data_deleted':False}
    report['fixtures'].append(saved)
    for filename in ('fixture.sqlite','fixture.sqlite-journal','fixture.sqlite-wal','fixture.sqlite-shm'):
        p=fixture/filename
        try:s=p.lstat()
        except FileNotFoundError:continue
        assert p.parent.resolve()==fixture.resolve() and stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1
        row={'path':str(p),'bytes':s.st_size,'uid':s.st_uid,'deleted':False}
        report['files'].append(row)
        preview=ROOT/'reports/ended_metadata_fixture_cleanup_v2.json'
        preview.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        p.unlink();row['deleted']=True
report['deleted_bytes']=sum(r['bytes'] for r in report['files'] if r['deleted'])
report['status']='OWN_ENDED_FIXTURE_DATABASES_REMOVED_EVIDENCE_RETAINED'
(ROOT/'reports/ended_metadata_fixture_cleanup_v2.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':report['status'],'deleted_bytes':report['deleted_bytes'],'files':len(report['files'])}))
