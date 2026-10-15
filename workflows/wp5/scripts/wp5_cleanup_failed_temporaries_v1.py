"""Root cleanup of four verified redundant, new WP5 failed temporary files."""
import hashlib,json,os,stat,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def main():
    if os.getuid()!=1278 or os.uname().nodename.split('.')[0]!='sonmi':raise ValueError('Actual Root login required')
    out=ROOT/'reports/owned_failed_temporary_cleanup_v1.json'
    if out.exists():raise ValueError('Cleanup already recorded; inspect exact result')
    review=ROOT/'reports/G4_G6_four_node_review_v1.json';candidates=json.loads(review.read_text())['cleanup_candidates']
    observation=json.loads((ROOT/'reports/observation_latest.json').read_text())
    if observation['sacct']['returncode']!=0 or observation['uid']!=1278:raise ValueError('Actual accounting required')
    states=observation['registered_job_states'];verified=[]
    for item in candidates:
        if states.get(item['current_run'],'').split()[0]!='COMPLETED' or states.get(item['original_source_job'],'').split()[0]!='FAILED':
            raise ValueError('Exact source and recovery jobs are not closed')
        path=Path(item['path']);info=path.lstat()
        if not path.resolve().is_relative_to(ROOT.resolve()) or not path.name.startswith('failed_consolidation_') or path.suffix!='.sqlite':
            raise ValueError('Only named new WP5 temporary files')
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=1278 or info.st_nlink!=1 or info.st_size!=item['bytes'] or sha(path)!=item['evidence_sha256']:
            raise ValueError('Temporary scope, owner, bytes or SHA differs')
        closure=Path(item['closure_report'])
        if sha(closure)!=item['closure_report_sha256'] or not Path(item['evidence_json']).is_file():raise ValueError('Closure evidence differs')
        report=json.loads(closure.read_text())
        if report['issues'] or report['status']!='G6_FULL_CHAIN_PASSED_WITH_RECORDED_SCIENTIFIC_OUTCOMES':raise ValueError('No complete readback proof')
        final=Path(item['closed_archive_path'])
        refs=[phase['archive'] for phase in report['phases'] if phase['archive']['path']==str(final)]
        if len(refs)!=1 or refs[0]['sha256']!=item['closed_archive_sha256'] or final.stat().st_size!=refs[0]['bytes']:
            raise ValueError('Permanent archive or proven reference differs')
        verified.append((item,info.st_ino,info.st_mtime_ns))
    result={'time':time.time(),'uid':os.getuid(),'review_sha256':sha(review),'policy':'Only new redundant failed temporary consolidation; failure JSON and all permanent science/history preserved','files':[],'released_bytes':0}
    for item,inode,mtime in verified:
        path=Path(item['path']);current=path.lstat()
        if (current.st_ino,current.st_mtime_ns)!=(inode,mtime):raise ValueError('Temporary changed before unlink')
        path.unlink();result['files'].append({**item,'deletion_performed':True});result['released_bytes']+=item['bytes']
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'OWN_NEW_REDUNDANT_TEMPORARIES_CLEANED','files':len(result['files']),'released_bytes':result['released_bytes']}))
if __name__=='__main__':main()
