"""Root-submitted exact nine derived-input-cache cleanup and frozen storage re-audit.
No QM, queue, SCI, original receipt, original storage report, or node14 mutation.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, socket, stat, subprocess, sys, time, traceback
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
FINAL=ROOT/'acceptance/final_20261016_v1'
SCOPE=FINAL/'exact9_input_cache_cleanup_scope_v1.json'
SCOPE_SHA='59e94e23d63e6c2d9bde98489a5346b5f2b095e5f762f5b061fc9a1430f4302e'
STORAGE=ROOT/'scripts/wp5_acceptance_storage_v3.py'
STORAGE_SHA='5ff8474f1f376ada63fa62dd08848832bbd5160c8956a0401a0b799e23c94a12'
AUTHORITY=ROOT/'gates/wp5_node_replacement_user_approved.json'
AUTHORITY_SHA='32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f'
ALLOWED={'compute-0-12','compute-0-13','compute-0-17','compute-0-18','compute-0-19'}
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}
KEYS=('device','inode','uid','gid','mode','nlink','bytes','mtime_ns','kind')
def require(value,message):
    if not value:raise ValueError(message)
def reference(path):
    p=Path(path); data=p.read_bytes()
    return {'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def check_ref(r,decode_json=True):
    require(re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None,'INVALID_SHA')
    require(reference(r['path'])=={k:r[k] for k in ('path','bytes','sha256')},'BOUND_METADATA_CHANGED:'+r['path'])
    return json.loads(Path(r['path']).read_text()) if decode_json else None
def metadata(p):
    s=Path(p).lstat();return {'path':str(p),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid,'mode':s.st_mode,'nlink':s.st_nlink,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'kind':'directory' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'UNSUPPORTED'}
def walk(root):
    result=[]; todo=[Path(root)]
    while todo:
        p=todo.pop(); row=metadata(p); result.append(row)
        if row['kind']=='directory':
            with os.scandir(p) as it:todo.extend(Path(e.path) for e in it)
    return result

def same(actual,expected,keys=KEYS):
    require(actual['path']==expected['path'] and all(actual[k]==expected[k] for k in keys),'EXACT_ENTRY_CHANGED:'+expected['path'])
def shape(case):
    root=case['root']; job=case['job_id']; suffix=root.rsplit('_',1)[1]; base=root+'/wp5_'+job+'_'+suffix
    expected={root,root+'/record_index.sqlite',base}|{base+'/lane_'+str(i) for i in range(24)}
    entries=case['entries'];require({e['path'] for e in entries}==expected and len(entries)==27,'EXACT_ONE_CACHE_26_DIR_SCOPE_REQUIRED')
    files=[e for e in entries if e['kind']=='file']
    require(len(files)==1 and files[0]['path']==root+'/record_index.sqlite' and files[0]['bytes']==case['index_bytes'] and files[0]['nlink']==1,'CACHE_IDENTITY_REQUIRED')
    require(all(e['uid']==1278 and e['kind'] in ('file','directory') for e in entries),'OWNER_OR_LINK_DIFFERS')
    return files[0]
def current_matches(case):
    rows=walk(case['root']);old={e['path']:e for e in case['entries']}
    require({e['path'] for e in rows}==set(old),'EXACT_PATH_SET_CHANGED:'+case['root'])
    for e in rows:same(e,old[e['path']])
def header(case):
    expected=shape(case);fd=os.open(expected['path'],os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd); require((s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns)==tuple(expected[k] for k in ('device','inode','uid','mode','nlink','bytes','mtime_ns')),'CACHE_FSTAT_DIFFERS')
        require(os.read(fd,16)==bytes.fromhex('53514c69746520666f726d6174203300'),'SQLITE_HEADER_DIFFERS')
    finally:os.close(fd)
    return {'path':expected['path'],'checked_bytes':16,'header':'SQLite format 3 NUL','SQL_or_payload_read':False}

def fd_review(cases):
    roots=[c['root'] for c in cases];inodes={(e['device'],e['inode']) for c in cases for e in c['entries']};ancestors=set();pid=os.getpid()
    while pid>0 and pid not in ancestors:
        ancestors.add(pid)
        try:pid=int(re.search(r'^PPid:\s*(\d+)',(Path('/proc')/str(pid)/'status').read_text(),re.M).group(1))
        except (FileNotFoundError,AttributeError):break
    processes={};unknown=[];excluded=[];matched=[];examined=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=1278:continue
            text=(p/'status').read_text();row={'pid':int(p.name),'ppid':int(re.search(r'^PPid:\s*(\d+)',text,re.M).group(1)),'comm':(p/'comm').read_text().strip(),'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').strip()};processes[row['pid']]=row
        except FileNotFoundError:continue
        except PermissionError as error:unknown.append({'pid':int(p.name),'error':str(error),'stage':'identity'})
    def target_match(t):
        t=t.removesuffix(' (deleted)');return any(t==r or t.startswith(r+'/') for r in roots)
    for pid,row in processes.items():
        reason=None
        if pid in ancestors:reason='THIS_CLEANUP_AND_ACTUAL_SLURM_OR_SSH_ANCESTRY'
        elif row['comm']=='systemd' and row['cmdline']=='/usr/lib/systemd/systemd --user':reason='IDENTIFIED_OS_USER_SESSION_MANAGER'
        elif row['comm']=='(sd-pam)' and processes.get(row['ppid'],{}).get('comm')=='systemd':reason='IDENTIFIED_OS_PAM_SESSION_HELPER'
        if reason:excluded.append({**row,'reason':reason});continue
        p=Path('/proc')/str(pid);examined.append(row)
        try:
            for special in ('cwd','root'):
                target=os.readlink(p/special)
                if target_match(target):matched.append({**row,'kind':special,'target':target})
            with os.scandir(p/'fd') as it:handles=[e.path for e in it]
            for handle in handles:
                try:
                    target=os.readlink(handle);s=os.stat(handle)
                    if target_match(target) or (s.st_dev,s.st_ino) in inodes:matched.append({**row,'kind':'fd','fd':Path(handle).name,'target':target})
                except FileNotFoundError:continue
        except FileNotFoundError:continue
        except PermissionError as error:
            if row['comm']=='sshd' and re.fullmatch(r'sshd: zixiao@(?:notty|pts/\d+)',row['cmdline']):excluded.append({**row,'reason':'IDENTIFIED_ORDINARY_SSH_CONTROL_WITH_PROC_PERMISSION_BOUNDARY','error':str(error)})
            else:unknown.append({**row,'error':str(error),'stage':'references'})
    return {'actual_ancestor_pids':sorted(ancestors),'excluded_identified_control_processes':excluded,'other_same_UID_processes_examined':examined,'matching_references':matched,'unknown_process_or_permission_errors':unknown,'no_unknown_scientific_active_reference':not matched and not unknown}

def accounting_rows(report,job_ids):
    require(report['sacct_returncode']==0 and report['job_count']==541,'ORIGINAL_541_ACCOUNTING_REQUIRED')
    fields=report['fields'];out={}
    for line in report['sacct_stdout'].splitlines():
        values=line.strip().split('|')
        if not values or values[0] not in job_ids:continue
        row=dict(zip(fields,values));job=row['JobIDRaw']
        require(job not in out and row['User']=='zixiao' and row['State'].split()[0].rstrip('+') in TERMINAL,'ACTUAL_TERMINAL_PARENT_REQUIRED:'+job)
        out[job]=row
    require(set(out)==set(job_ids),'EXACT_PARENT_ACCOUNTING_MISSING')
    return out

def open_dir(path):
    p=Path(path);require(p.is_absolute() and '..' not in p.parts,'ABSOLUTE_FIXED_PATH_REQUIRED');fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in p.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException:os.close(fd);raise

def delete_cache(case,report):
    root=Path(case['root']);expected={e['path']:e for e in case['entries']};cache=shape(case);fd=open_dir(root)
    try:
        s=os.fstat(fd);r=expected[str(root)];require((s.st_dev,s.st_ino,s.st_uid,s.st_mode)==tuple(r[k] for k in ('device','inode','uid','mode')),'ROOT_OPEN_FSTAT_CHANGED')
        same(metadata(root/'record_index.sqlite'),cache)
        os.unlink('record_index.sqlite',dir_fd=fd);report['deleted_files'].append({'path':cache['path'],'bytes':cache['bytes'],'category':'REBUILDABLE_DERIVED_INPUT_INDEX_CACHE','backup_body_required':False})
    finally:os.close(fd)
    for d in sorted((e for e in case['entries'] if e['kind']=='directory'),key=lambda e:len(Path(e['path']).parts),reverse=True):
        p=Path(d['path']);same(metadata(p),d,('device','inode','uid','gid','mode','kind'));parent=open_dir(p.parent)
        try:
            s=os.stat(p.name,dir_fd=parent,follow_symlinks=False);require((s.st_dev,s.st_ino,s.st_uid,s.st_mode)==tuple(d[k] for k in ('device','inode','uid','mode')),'RMDIR_FSTAT_CHANGED')
            os.rmdir(p.name,dir_fd=parent);report['removed_empty_directories'].append(str(p))
        finally:os.close(parent)
    require(not os.path.lexists(root),'EXACT_ROOT_REMAINS_AFTER_CLEANUP')

def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def main(args):
    node=socket.gethostname().split('.')[0];require(args.execute,'EXPLICIT_EXECUTE_REQUIRED');require(os.getuid()==1278 and node in ALLOWED,'EXACT_ALLOWED_NODE_UID_REQUIRED');require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=24,'24_CPU_SLURM_REQUIRED')
    require(args.out.is_absolute() and args.out.parent==FINAL and not args.out.exists(),'FRESH_OWN_FINAL_OUTPUT_REQUIRED');require(reference(SCOPE)['sha256']==SCOPE_SHA,'SCOPE_CHANGED');require(reference(STORAGE)['sha256']==STORAGE_SHA and reference(AUTHORITY)['sha256']==AUTHORITY_SHA,'FROZEN_REAUDIT_SOURCE_CHANGED')
    scope=json.loads(SCOPE.read_text());require(scope['schema']=='WP5_EXACT9_DERIVED_INPUT_CACHE_CLEANUP_SCOPE_V1' and len(scope['cases'])==9,'FIXED_SCOPE_REQUIRED');check_ref(scope['runner_source'],False);check_ref(scope['inspector'],False);mapping=check_ref(scope['formal542_jobmap']);accounts=accounting_rows(check_ref(scope['accounting']),{c['job_id'] for c in scope['cases']})
    cases=[]
    for binding in scope['inspection_reports']:
        read=check_ref(binding)
        if read['node']==node:cases.extend(read['cases'])
    selected=[c for c in scope['cases'] if c['node']==node];require({c['job_id'] for c in cases}=={c['job_id'] for c in selected} and cases,'EXACT_NODE_SUBSET_REQUIRED')
    permanent=[]
    for case in cases:
        anchor=next(c for c in selected if c['job_id']==case['job_id']);root=case['root'];require(root==anchor['root'] and re.fullmatch(r'/tmp/wp5runtime_1278_'+case['job_id']+'_'+anchor['session'][:8],root),'EXACT_TEMP_ROOT_REQUIRED');shape(case)
        run=check_ref(case['run_metadata']);index=check_ref(case['input_index_metadata']);o=run['options'];require(run['node']==node and str(o['job_id'])==case['job_id'] and str(o['task_id'])==anchor['task_id'] and o['session']==anchor['session'] and o['scratch_root']==root and o['local_index']==root+'/record_index.sqlite','ORIGINAL_RUN_CACHE_BINDING_DIFFERS');require(index=={'path':o['local_index'],'bytes':case['index_bytes'],'molecules':case['index_molecules']},'ORIGINAL_INPUT_INDEX_DIFFERS')
        source_map={r['path']:r['sha256'] for r in o['source_bindings']};require(source_map.get(scope['runner_source']['path'])==scope['runner_source']['sha256'],'ORIGINAL_CACHE_CREATOR_DIFFERS')
        source_plan=reference(o['source_plan']);require(source_map.get(source_plan['path'])==source_plan['sha256'],'IMMUTABLE_SOURCE_PLAN_DIFFERS')
        mapped=[r for r in mapping['jobs'] if str(r['job_id'])==case['job_id']];require(len(mapped)==1 and mapped[0]['node']==node and str(mapped[0]['task_id'])==anchor['task_id'],'FORMAL542_PARENT_BINDING_DIFFERS')
        current_matches(case);proof=header(case);permanent.append({'job_id':case['job_id'],'run_metadata':case['run_metadata'],'input_index_metadata':case['input_index_metadata'],'source_plan':source_plan,'actual_terminal_accounting':accounts[case['job_id']],'sqlite_header_check':proof})
    fds=fd_review(cases);require(fds['no_unknown_scientific_active_reference'],'ACTIVE_OR_UNKNOWN_SCIENTIFIC_REFERENCE')
    args.out.mkdir();report={'schema':'WP5_EXACT9_DERIVED_INPUT_CACHE_CLEANUP_ACTUAL_V1','status':'PREFLIGHT_CLOSED_MUTATION_NOT_YET_STARTED','created_epoch':time.time(),'node':node,'actual_cleanup_job_id':os.environ['SLURM_JOB_ID'],'source':reference(__file__),'scope':reference(SCOPE),'original_permanent_metadata':permanent,'fd_review_before_cleanup':fds,'deleted_files':[],'removed_empty_directories':[],'new_QM_calls':0,'SCI_or_raw_opened':False,'permanent_science_or_queue_modified':False,'old_storage_reports_or_scratch_clean_rewritten':False}
    write_new(args.out/'execution_intent.json',report)
    try:
        for case in cases:current_matches(case);header(case)
        fds2=fd_review(cases);report['fd_review_immediately_before_mutation']=fds2;require(fds2['no_unknown_scientific_active_reference'],'ACTIVE_OR_UNKNOWN_REFERENCE_BEFORE_MUTATION')
        for case in cases:delete_cache(case,report)
        report['all_exact_roots_absent']=all(not os.path.lexists(c['root']) for c in cases);report['cache_bytes_released']=sum(e['bytes'] for e in report['deleted_files']);report['status']='EXACT_DERIVED_CACHES_REMOVED_PENDING_FROZEN_STORAGE_REAUDIT'
        command=[sys.executable,'-B',str(STORAGE),'--scope','node','--jobmap',scope['formal542_jobmap']['path'],'--node-authority',str(AUTHORITY),'--scratch-root','/tmp','--workers','24','--out',str(args.out/'storage_reaudit')]
        proc=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45*3600,cwd='/share/home/zixiao/descriptor_analysis');(args.out/'storage_reaudit.stdout').write_text(proc.stdout);(args.out/'storage_reaudit.stderr').write_text(proc.stderr);report['frozen_storage_reaudit']={'command':command,'source':reference(STORAGE),'returncode':proc.returncode}
        if (args.out/'storage_reaudit/storage_report.json').exists():
            sr=json.loads((args.out/'storage_reaudit/storage_report.json').read_text());report['frozen_storage_reaudit'].update(report=reference(args.out/'storage_reaudit/storage_report.json'),status=sr['status'])
        require(proc.returncode==0 and report['frozen_storage_reaudit'].get('status')=='PASS','FROZEN_STORAGE_REAUDIT_NOT_PASS');report['status']='EXACT_CACHE_CLEANUP_AND_FROZEN_NODE_STORAGE_REAUDIT_PASS'
    except BaseException as error:
        report['status']='ROOT_REVIEW_REQUIRED_AFTER_EXACT_CLEANUP_ATTEMPT';report['error']=repr(error);report['traceback']=traceback.format_exc();write_new(args.out/'cleanup_report.json',report);raise
    write_new(args.out/'cleanup_report.json',report);print(json.dumps({'status':report['status'],'node':node,'deleted_files':len(report['deleted_files']),'cache_bytes_released':report['cache_bytes_released'],'report':str(args.out/'cleanup_report.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--out',type=Path,required=True);main(p.parse_args())
