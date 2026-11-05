"""Explicit 1..3 CLOSED+SYNCED Native long runs; CPU copy/export, no SDK decode."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import fcntl,hashlib,html,importlib.util,json,os,re,socket,stat,subprocess,sys,time,unittest
from pathlib import Path
sys.dont_write_bytecode=True
P=Path('/share/home/zixiao/descriptor_analysis');N=P/'runs/model_v3_20261026';O=P/'runs/model_v3_20261025'
HERE=Path(__file__).absolute().parent;ARCH=P/'runs/phase1_full_corpus/wandb_archive';DEST=ARCH/'model_v3_20261025'
V1=N/'native7_offline_archive_v1_source';LONG=N/'native_closed_long_sync_v1';CAP=256<<20
OLD_PIN='30ccd29bdb084fcc7286d17afef45bb52183d8f0b8a22ec7e3459e953674d5e5'
LONG_PIN='36dc47c4661b798486df290a8628f80429f8ea12c0cb0743a99ab4aa20971cf9'

def require(ok,message):
    if not ok:raise ValueError(message)
def ref(path):
    path=Path(path).absolute();a=path.lstat()
    require(path==path.resolve(strict=True) and stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_nlink==1
        and a.st_size<=16<<20,'Owned physical bounded metadata/source required')
    raw=path.read_bytes();b=path.stat()
    require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'Metadata changed')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):
    original=ref(path)
    def pairs(items):
        result={}
        for k,v in items:require(k not in result,'Duplicate metadata key');result[k]=v
        return result
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))
    require(ref(path)==original,'Metadata changed while parsed');return value
def bound(raw):
    require(set(raw)=={'path','bytes','sha256'} and ref(raw['path'])==raw,'Exact raw metadata reference differs')
    return read(raw['path'])
def write(path,value):
    data=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(data)<=1<<20,'Compact metadata output cap exceeded')
    with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return ref(path)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
def sources(pin):
    own=ref(HERE/'source_pins.json');require(own['sha256']==pin,'Archive source inventory differs')
    for row in bound(own)['files']:
        require(ref(HERE/row['file'])==dict(path=str(HERE/row['file']),bytes=row['bytes'],sha256=row['sha256']),'Archive source changed')
    deps=read(HERE/'dependencies.json')
    for value in deps.values():require(ref(value['path'])==value,'Frozen source dependency changed')
    require(deps['archive_v1']['sha256']==OLD_PIN and deps['closed_long_sync']['sha256']==LONG_PIN,'Original methods changed')
    sys.path.insert(0,str(V1));old=load(V1/'archive_native7.py','closed_long_archive_original_v1')
    old.sources(OLD_PIN)
    sys.path.insert(0,str(LONG));common=load(LONG/'long_common.py','closed_long_archive_proof_adapter')
    common.verify(LONG_PIN)
    return own,old,common
def original_indexes():
    paths=[DEST/'index.json',DEST/'native7_20261027_v1/index.json',*sorted(DEST.glob('native_long_*/index.json'))]
    require(len(paths)<=128,'Bounded explicit archive index census exceeded')
    values=[ref(path) for path in paths]
    require(sum(v['bytes'] for v in values)<=2<<20,'Archive index metadata census exceeded')
    return values
def quota_ok(frame):
    q=frame['quota'];require(frame['schema']=='native_S_Root_closed_long_archive_quota_v1'
        and frame['host']=='sonmi' and frame['uid']==1278 and q['returncode']==0
        and frame['captured_unix']==q['completed_unix'] and q['started_unix']<=q['completed_unix']
        and 0<=time.time()-frame['captured_unix']<=120,'Fresh original0..120s actual Root quota required')
    rows=[s.split() for s in q['stdout'].splitlines() if s.split() and s.split()[0]=='/dev/sda1']
    require(len(rows)==1,'Exact quota filesystem missing');used,soft,hard=[int(v.rstrip('*'))*1024 for v in rows[0][1:4]]
    limits=[v for v in (soft,hard) if v>0]
    holds=frame['known_registered_remaining_bytes'];require(all(type(v)is int and v>=0 for v in holds.values()),'Unknown Root hold')
    require(limits and min(limits)-used-sum(holds.values())>=(64<<30)+(2<<30),'Original account headroom+job budget insufficient')
def actual_jobs(jobs):
    argv=['sacct','-X','-n','-P','-j',','.join(sorted(jobs,key=int)),'--format=JobIDRaw,User,State,ExitCode']
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    rows=[s.split('|') for s in p.stdout.splitlines() if s.strip()]
    require(p.returncode==0 and len(rows)==len(jobs) and {r[0] for r in rows}==set(jobs)
        and all(r[1:] == ['zixiao','COMPLETED','0:0'] for r in rows),'Actual model/audit/sync terminals must all be exact C0')
    return dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
def selected(request,common):
    require(request['schema']=='native_S_explicit_closed_synced_archive_request_v1'
        and re.fullmatch(r'native_long_[A-Za-z0-9_]{1,96}',request['archive_name']),'Explicit fresh native_long_ archive name required')
    root=DEST/request['archive_name'];require(not root.exists(),'Fresh output required; no overwrite/resume of archive attempts')
    rows=common.proof_rows(request['entries']) # Frozen metadata-only 1..3 proof/BATCH/sup/actual-C0 adapter.
    closure=bound(request['sync_Root_closure'])
    require(closure['schema']=='native_S_explicit_sync_Root_closure_v1'
        and closure['status']=='ROOT_CLOSED_C0_METADATA_VERIFIED' and closure['scientific_acceptance'] is False
        and closure['active_runs_included'] is False and closure['old_indexes_or_source_SDK_modified'] is False,
        'Existing exact independent Root online closure required')
    result=[];jobs=set()
    for item,row in zip(request['entries'],rows,strict=True):
        proof=bound(item['verification']);batch=bound(item['audit_batch']);terminal=bound(proof['closed_metadata_refs']['terminal'])
        require(row['native_exit_code']==0 and row['original_model_status']=='COMPLETED'
            and terminal['status']=='COMPLETED' and terminal['exit_code_raw']=='0:0'
            and proof['history_reader_source']['sha256']=='74925c58edc61619c78533ff6cce8fc36b2b5f20f876cb011169906d8ba77e88',
            'Only independently verified successful literal749 Native long segments admitted')
        matching=[r for r in closure['records'] if r['run_id']==row['run_id']]
        require(len(matching)==1,'Run absent/duplicated in exact sync closure');synced=matching[0];remote=synced['actual_remote_metadata']
        require(synced['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED' and synced['native_exit_code']==0
            and synced['worker_SDK_before_after_hash_equal'] is True
            and synced['original_SDK_raw_ref_from_sync_job']==proof['sdk']
            and remote['run_id']==row['run_id'] and remote['state']=='finished'
            and remote['history_rows']==row['history_rows'] and remote['first_step']==row['first_explicit_step']
            and remote['last_step']==row['last_explicit_step'],'Sync actual SDK/steps/count/exit differs')
        sync_jobs=[j for j in closure['jobs'] if str(j['job_id'])==str(synced['sync_job_id'])]
        require(len(sync_jobs)==1,'Exact actual sync job missing');sync=sync_jobs[0];sup=bound(sync['supervisor'])
        require(sync['source_before_after_and_current_equal'] is True and sync['actual_terminal']['state']=='COMPLETED'
            and sync['actual_terminal']['exit_code']=='0:0' and sup['status']=='COMPLETED'
            and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
            and sup['private_storage']['first_sampling_failure'] is None,'Actual sync source/process/terminal closure differs')
        require(sync['current_source_hashes'].get(item['verification']['path'])==item['verification']['sha256']
            and sync['current_source_hashes'].get(item['audit_batch']['path'])==item['audit_batch']['sha256'],
            'Root closed sync source graph binds another native audit')
        jobs.update((str(terminal['job_id']),str(batch['actual_job_id']),str(sync['job_id'])))
        history=proof['history'];configuration=bound(proof['closed_metadata_refs']['configuration']);contract=configuration['contract']
        require(type(contract['seed']) is int and contract['seed']>=0 and contract['precision'] in ('fp32','bf16'),'Actual source seed/precision missing')
        result.append(dict(run_id=row['run_id'],job_id=str(terminal['job_id']),label='CLOSED_SYNCED_LONG_LOG_ONLY_NOT_B_ACCEPTANCE',
            kind='long',state='COMPLETED',exit_code='0:0',native_exit=0,rows=row['history_rows'],
            first_step=row['first_explicit_step'],last_step=row['last_explicit_step'],sdk=proof['sdk'],mirror=proof['mirror'],
            normalized_sha256=history['normalized_history_sha256'],normalized_bytes=history['normalized_history_bytes'],
            reader_kind='literal749',mirror_format='committed_envelope',family='native_S_seed'+str(contract['seed'])+'_'+contract['precision'],
            seed=contract['seed'],precision=contract['precision'],configuration=proof['closed_metadata_refs']['configuration'],certificate=item['verification'],audit_batch=item['audit_batch'],
            audit_supervisor=item['audit_supervisor'],actual_audit_C0=item['actual_audit_C0'],
            model_terminal=proof['closed_metadata_refs']['terminal'],sync_Root_closure=request['sync_Root_closure'],
            parent_run_id=proof['parent_run_id'],source_data_contract_sha256=proof['source_data_contract_sha256']))
    prior=original_indexes();existing=set()
    for raw in prior:
        index=bound(raw);existing.update(r['run_id'] for r in index['entries'])
    require(not existing.intersection(row['run_id'] for row in result),'Already archived selected run; duplicate forbidden')
    return root,result,jobs,prior
def prepare(args,pin,old,common):
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Root login metadata prepare only')
    request_ref=ref(args.request);require(request_ref['sha256']==args.request_sha256,'Explicit request SHA differs')
    request=bound(request_ref);root,entries,jobs,indexes=selected(request,common)
    output=Path(args.output);require(output.parent==N and not output.exists(),'Fresh immediate N preparation directory required')
    registry=Path(request['Root_registered_reservations_path']);require(registry.parent==N,'Explicit immediate N Root holds registry required');observed=bound(ref(registry))
    require(observed['authority']=='ROOT_ACTUAL' and observed['uid']==1278,'Existing actual Root finite holds required')
    remaining={k:v['remaining_bytes'] for k,v in observed['reservations'].items()}
    started=time.time();argv=['quota','-v','-u','zixiao'];q=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    completed=time.time();terminals=actual_jobs(jobs)
    frame=dict(schema='native_S_Root_closed_long_archive_quota_v1',host='sonmi',uid=1278,captured_unix=completed,
        quota=dict(argv=argv,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr,started_unix=started,completed_unix=completed),
        known_registered_remaining_bytes=remaining,registry_observation=ref(registry),source_pins=pin,request=request_ref,
        archive_root=str(root),entries=entries,preserved_indexes=indexes,actual_closed_sacct=terminals,
        SDK_or_journal_payload_opened=False,new_reservation_or_phase_counter_written=False)
    quota_ok(frame);output.mkdir(mode=0o700);receipt=write(output/'ROOT_QUOTA_CLOSED.json',frame)
    bindings=write(output/'BINDINGS.json',dict(MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT=receipt['path'],
        MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT_SHA=receipt['sha256'],MODEL_V3_CLOSED_LONG_ARCHIVE_PIN=pin['sha256'],
        MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT=str(root)))
    print(json.dumps(dict(status='PREPARED_NO_SUBMIT_NO_PAYLOAD_READ',receipt=receipt,bindings=bindings)))
def run(args,pin,old,common):
    job=os.environ.get('SLURM_JOB_ID','')
    require(os.getuid()==1278 and job.isdigit() and socket.gethostname()==args.expected_node
        and re.fullmatch(r'compute-0-(?:2|[8-9]|1[0-9])',args.expected_node)
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='' and re.search(r'(?:^|/)job[_/-]'+job+r'(?:/|$)',Path('/proc/self/cgroup').read_text(),re.M),
        'Actual owned16CPU CPU-only allocation/kernel binding required')
    raw=ref(args.root_receipt);require(raw['sha256']==args.root_receipt_sha256,'Root receipt SHA differs')
    frame=bound(raw);quota_ok(frame);require(frame['source_pins']==pin,'Prepared source differs')
    request=bound(frame['request']);root,entries,_,indexes=selected(request,common)
    require(str(root)==frame['archive_root'] and entries==frame['entries'] and indexes==frame['preserved_indexes'],'Prepared cohort/index snapshot changed')
    _,_,deps=old.sources(OLD_PIN);helper=old.load(deps['helper'],'closed_long_original_archive_helper')
    v7=old.load(deps['v7'],'closed_long_original_copy_ref');literal=old.load(deps['literal749'],'closed_long_original_literal749')
    require(sum(p.lstat().st_size for p in ARCH.rglob('*') if p.is_file() and not p.is_symlink())+CAP<=2<<30
        and helper.phase_census()+CAP<=104<<30,'Original archive2GiB/forest104GiB reserve exhausted')
    descriptor=os.open(DEST/'.archive.lock',os.O_RDWR|os.O_NOFOLLOW);lock=helper.owned(DEST/'.archive.lock')
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(lock.st_dev,lock.st_ino),'Original archive lock changed')
    started=time.monotonic()
    with os.fdopen(descriptor,'a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);root.mkdir(mode=0o700)
        import test_exports
        suite=unittest.defaultTestLoader.loadTestsFromModule(test_exports);require(suite.countTestCases()==4,'Exact original four tests required')
        with (root/'metadata_tests.log').open('w') as out:test=unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
        require(test.testsRun==4 and not test.failures and not test.errors and not test.skipped,'Original four zero-skip export tests failed')
        records=[]
        for entry in entries:
            require(time.monotonic()-started<750,'Original finalization reserve reached');quota_ok(frame)
            sdk=Path(entry['sdk']['path']);require(old.ref(sdk)==entry['sdk'],'Selected source SDK content changed')
            source=helper.source_manifest(sdk.parent)
            require(sum(r['bytes'] for r in source)<=128<<20 and all(Path(r['relative_path']).suffix.lower() not in
                {'.pt','.pth','.npz','.npy','.safetensors','.lmdb','.mdb','.parquet','.pkl'} for r in source),'Only selected bounded SDK/log files')
            match=re.fullmatch(r'offline-run-(\d{8})_(\d{6})-([a-z0-9]+)',sdk.parent.name)
            require(match is not None and match[3]==entry['run_id'],'Source SDK date/run identity differs')
            name=match[1]+'_'+match[2]+'_job'+entry['job_id']+'_'+entry['label']+'_'+entry['run_id']
            family=root/entry['family'];family.mkdir(mode=0o700,exist_ok=True)
            pending=family/('.'+name+'.pending');target=family/name;pending.mkdir(mode=0o700)
            for row in source:v7.copy_ref(dict(path=row['read_path'],bytes=row['bytes'],sha256=row['sha256']),
                pending/'wandb'/sdk.parent.name/row['relative_path'])
            for label in ('certificate','audit_batch','audit_supervisor','actual_audit_C0','model_terminal','configuration','sync_Root_closure'):
                v7.copy_ref(entry[label],pending/(label+'.original.json'))
            require(old.ref(entry['mirror']['path'])==entry['mirror'],'Selected certified journal content changed')
            v7.copy_ref(entry['mirror'],pending/'source_history.jsonl')
            with Path(entry['mirror']['path']).open('rb') as mirror:normalized,rows=old.normalize(mirror,entry,literal)
            page=old.curve_page(rows,entry);crumb=b'>Seven-run archive index</a>'
            require(page.count(crumb)==1,'Frozen exporter breadcrumb changed')
            page=page.replace(crumb,b'>Native long archive index</a>') # Presentation label only; all curves/CSV/values unchanged.
            for filename,data in (('history.normalized.jsonl',normalized),('metrics.csv',old.metrics_csv(rows)[0]),('index.html',page)):
                with (pending/filename).open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())
            write(pending/'last_metrics.json',old.latest(rows))
            require(helper.source_manifest(sdk.parent)==source and old.ref(entry['mirror']['path'])==entry['mirror'],'Selected source changed during copy/export')
            manifest=write(pending/'manifest.json',dict(schema='native_S_closed_synced_long_local_archive_v1',**entry,
                source_files=source,normalization_reader=deps['literal749'],source_pins=pin,
                normalized_history_bytes=len(normalized),normalized_history_sha256=hashlib.sha256(normalized).hexdigest(),
                SDK_decoder_executed=False,online_sync_performed_by_this_archive=False,scientific_acceptance=False))
            os.rename(pending,target);manifest=ref(target/'manifest.json')
            records.append(dict(run_id=entry['run_id'],job_id=entry['job_id'],name=entry['label'],
                path=str(target.relative_to(ARCH)),manifest=manifest,history_rows=len(rows)))
            require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAP-(1<<20),'Original256MiB archive cap exhausted')
        quota_ok(frame)
        for original in indexes:bound(original)
        write(root/'index.json',dict(schema='native_S_explicit_closed_long_append_archive_index_v1',entries=records,
            preserved_indexes=indexes,old_indexes_rewritten=False,source_pins=pin,online_sync_performed_by_this_archive=False,
            updated_Asia_Shanghai=datetime.now(timezone(timedelta(hours=8))).isoformat(),scientific_acceptance=False))
        links=''.join('<li><a href="'+html.escape(str(Path(r['path']).relative_to(root.relative_to(ARCH))))+'/index.html">'+html.escape(r['run_id']+' / '+r['name'])+'</a></li>' for r in records)
        (root/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>Explicit closed and synced Native long archives</h1><p>Prior sync proof reused; no SDK decode or online sync here. LONG_SEGMENT_LOG_ONLY; no model/B acceptance.</p><ul>'+links+'</ul>',encoding='utf-8')
        marker='data-model-v3-'+request['archive_name']
        write(root/'UNIFIED_ENTRY_APPEND_PROPOSAL.json',dict(schema='native_S_Root_closed_long_archive_entry_proposal_v1',
            entry_path=str(P/'W&B_训练记录.html'),unique_marker=marker,preserve_all_prior_bytes=True,
            apply_only_after_actual_archive_parent_C0_and_Root_visual_review=True,old_indexes_may_be_rewritten=False,
            html='<p '+marker+'><a href="runs/phase1_full_corpus/wandb_archive/model_v3_20261025/'+request['archive_name']+'/index.html">Native S：'+str(len(records))+'项已闭合长段本地归档</a></p>\n'))
        sources(pin['sha256']);require(helper.phase_census()<=104<<30,'Original physical forest cap exhausted')
        result=write(root/'RESULT.json',dict(schema='native_S_explicit_closed_long_archive_result_v1',
            status='ARCHIVED_EXPLICIT_CLOSED_SYNCED_LONG_PENDING_ACTUAL_CPU_C0',actual_job_id=job,entries=records,
            metadata_tests=dict(tests=4,failures=0,errors=0,skipped=0),preserved_indexes=indexes,old_indexes_rewritten=False,
            source_pins=pin,Root_receipt=raw,SDK_decoder_executed=False,online_sync_performed=False,
            actual_outer_C0_not_self_asserted=True,scientific_acceptance=False,archive_cap_bytes=CAP))
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAP,'Final256MiB archive cap exhausted')
        print(json.dumps(dict(status='ARCHIVED_PENDING_ACTUAL_CPU_C0',result=result)))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-pins-sha256',required=True);sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('prepare');a.add_argument('--request',type=Path,required=True);a.add_argument('--request-sha256',required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--root-receipt',type=Path,required=True);a.add_argument('--root-receipt-sha256',required=True);a.add_argument('--expected-node',required=True)
    args=p.parse_args();pin,old,common=sources(args.source_pins_sha256)
    return prepare(args,pin,old,common) if args.mode=='prepare' else run(args,pin,old,common)
if __name__=='__main__':raise SystemExit(main())

