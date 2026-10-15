"""Delete only16 owned synthetic worker dirs of terminal job4514281.
Never delete report/source/AST evidence, scientific artifacts or original data.
"""
from __future__ import annotations
import argparse,getpass,hashlib,json,os,socket,stat,time,traceback
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
FIXTURE=ROOT/'gates/cleanup_scope_fixture/job_4514281'
REPORT=ROOT/'reports/cleanup_scope_fixture_job4514281_temporary_cleanup_v1.json'
UID=1278
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def meta(path):
    s=path.lstat()
    if s.st_uid!=UID or stat.S_ISLNK(s.st_mode):raise ValueError('UNOWNED_OR_LINK:'+str(path))
    kind='directory' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else None
    if kind is None or kind=='file' and s.st_nlink!=1:raise ValueError('NONREGULAR_OR_HARDLINK:'+str(path))
    return {'path':str(path),'kind':kind,'uid':s.st_uid,'device':s.st_dev,'inode':s.st_ino,
            'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode,'nlink':s.st_nlink}
def inspect():
    # Verify exact absolute targets and every path component inside this phase.
    if FIXTURE.resolve()!=ROOT.resolve()/'gates/cleanup_scope_fixture/job_4514281':
        raise ValueError('FIXED_PHASE_FIXTURE_TARGET_DIFFERS')
    for p in (ROOT,ROOT/'gates',ROOT/'gates/cleanup_scope_fixture',FIXTURE):
        if meta(p)['kind']!='directory':raise ValueError('FIXTURE_ANCESTOR_NOT_NORMAL_DIR')
    targets=[FIXTURE/('worker_'+str(i)) for i in range(16)]
    actual={p.name for p in FIXTURE.iterdir() if p.name.startswith('worker_')}
    if actual!={p.name for p in targets}:raise ValueError('EXACT_FIXED16_WORKER_DIRECTORIES_REQUIRED')
    entries=[]
    def walk(path):
        m=meta(path);entries.append(m)
        if m['kind']=='directory':
            for child in sorted(path.iterdir()):walk(child)
        else:m['sha256']=sha(path)
    for p in targets:
        if meta(p)['kind']!='directory' or p.resolve().parent!=FIXTURE.resolve():
            raise ValueError('WORKER_DIRECTORY_TARGET_DIFFERS')
        walk(p)
    proof=json.loads((FIXTURE/'report.json').read_bytes())
    if (proof.get('job_id')!='4514281' or proof.get('status')!='CLEANUP_STATIC_SCOPE_FIXTURE_PASS' or
        proof.get('effective_worker_count')!=16 or proof.get('QM_calls')!=0 or
        proof.get('production_queue_written') is not False or proof.get('issues')):
        raise ValueError('ACTUAL_SYNTHETIC_FIXTURE_REPORT_SCOPE_DIFFERS')
    if {item['worker'] for item in proof['scenarios']}!=set(range(16)):
        raise ValueError('ACTUAL16_WORKER_REPORT_SCOPE_DIFFERS')
    for item in proof['scenarios']:
        if Path(item['private_queue'])!=targets[item['worker']]/'fixture.sqlite' or item.get('QM_calls')!=0 or item.get('production_queue_written') is not False:
            raise ValueError('WORKER_PRIVATE_SYNTHETIC_QUEUE_SCOPE_DIFFERS')
    preserved=[]
    for key in ('source','AST_bridge','runner12','runner13'):
        ref=proof[key]
        if sha(ref['path'])!=ref['sha256']:raise ValueError('PRESERVED_JOB_SOURCE_OR_AST_SHA_DIFFERS:'+key)
        preserved.append({'role':key,**ref})
    preserved.append({'role':'actual_fixture_report','path':str(FIXTURE/'report.json'),'sha256':sha(FIXTURE/'report.json'),'bytes':(FIXTURE/'report.json').stat().st_size})
    return targets,entries,preserved
def terminal_evidence():
    import wp5_accounting_v2 as A
    r=A.run_sacct(['-X','-n','-P','-j','4514281','--format=JobID,User,State'],
        evidence_path=ROOT/'reports/cleanup_scope_fixture_job4514281_accounting_v1.json',
        wait_seconds=0,max_age_seconds=180)
    if r.returncode!=0:return {'valid':False,'reason':'FRESH_PUBLISHER_ACCOUNTING_UNAVAILABLE','evidence_path':r.evidence_path,'returncode':r.returncode,'stderr':r.stderr}
    rows=[line.strip().split('|') for line in r.stdout.splitlines() if line.strip()]
    if len(rows)!=1 or rows[0][:3]!=['4514281','zixiao','COMPLETED']:
        return {'valid':False,'reason':'EXACT_ACTUAL_COMPLETED_JOB_REQUIRED','evidence_path':r.evidence_path,'returncode':r.returncode,'stdout':r.stdout}
    return {'valid':True,'job_id':'4514281','user':'zixiao','state':'COMPLETED',
            'evidence_path':r.evidence_path,'evidence_sha256':sha(r.evidence_path),'publisher_provenance':r.evidence.get('provenance')}
def same_entry(path,before):
    now=meta(path)
    if any(now[k]!=before[k] for k in ('kind','uid','device','inode','mode')):
        raise ValueError('OWNED_DELETE_IDENTITY_CHANGED:'+str(path))
    if now['kind']=='file' and any(now[k]!=before[k] for k in ('bytes','mtime_ns','nlink')):
        raise ValueError('OWNED_DELETE_FILE_CHANGED:'+str(path))
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    if os.getuid()!=UID or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0] not in {'sonmi','compute-0-20'}:
        raise ValueError('AUTHORIZED_SAME_UID_METADATA_CLEANUP_HOST_REQUIRED')
    if REPORT.exists():raise FileExistsError('Cleanup receipt already exists; inspect instead of repeating')
    report={'schema':'WP5_OWNED_SYNTHETIC_FIXTURE_TEMP_CLEANUP_V1','job_id':'4514281',
        'source':{'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'created_epoch':time.time(),
        'actor_uid':os.getuid(),'actor_user':getpass.getuser(),'actor_host':socket.gethostname(),
        'exact_fixture_root':str(FIXTURE),'explicit_execute':a.execute,'deleted':[],
        'scientific_or_production_data_deleted':False,'original_LMDB_opened':False,
        'job_signal_sent':False,'submission_control_modified':False}
    try:
        targets,before,preserved=inspect()
        report.update(before=before,preserved=preserved,before_files=sum(m['kind']=='file' for m in before),
                      before_bytes=sum(m['bytes'] for m in before if m['kind']=='file'),fixed_worker_directories=[str(p) for p in targets])
        proof=terminal_evidence();report['accounting']=proof
        if not proof['valid']:
            report['status']='PREPARED_NOT_DELETED_NO_FRESH_TERMINAL_EVIDENCE'
        elif not a.execute:report['status']='REVIEWABLE_EXACT16_TEMPORARY_CLEANUP_PLAN'
        else:
            # One Python process, exact enumerated ordinary files then empty dirs.
            # No rmtree/glob/follow-link or shell deletion.
            for m in sorted((m for m in before if m['kind']=='file'),key=lambda m:m['path']):
                path=Path(m['path']);same_entry(path,m)
                path.unlink();report['deleted'].append({'path':str(path),'bytes':m['bytes'],'sha256':m['sha256']})
            for m in sorted((m for m in before if m['kind']=='directory'),key=lambda m:len(Path(m['path']).parts),reverse=True):
                path=Path(m['path']);same_entry(path,m);path.rmdir()
            for ref in preserved:
                if sha(ref['path'])!=ref['sha256']:raise ValueError('PRESERVED_REPORT_SOURCE_OR_AST_CHANGED')
            if any(p.exists() or p.is_symlink() for p in targets):raise ValueError('WORKER_TEMP_DIRECTORY_REMAINS')
            report.update(status='EXACT16_SYNTHETIC_TEMPORARIES_REMOVED_VERIFIED',after={
                'worker_directories_remaining':0,'temporary_files_remaining':0,
                'fixture_root_remaining':FIXTURE.is_dir(),'fixture_report_remaining':(FIXTURE/'report.json').is_file(),
                'remaining_top_level':[p.name for p in sorted(FIXTURE.iterdir())],
                'preserved_source_report_AST_SHA_verified':True},
                deleted_bytes=sum(m['bytes'] for m in report['deleted']))
    except BaseException:
        report.update(status='CLEANUP_RECORDED_ERROR_NO_OTHER_SCOPE_TOUCHED',error=traceback.format_exc(limit=12))
    with REPORT.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({k:report.get(k) for k in ('status','before_files','before_bytes','deleted_bytes','after','accounting','error')},allow_nan=False))
    return 0 if report['status']=='EXACT16_SYNTHETIC_TEMPORARIES_REMOVED_VERIFIED' else 1
if __name__=='__main__':raise SystemExit(main())
