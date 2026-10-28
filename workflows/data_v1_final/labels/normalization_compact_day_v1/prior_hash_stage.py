"""Explicit actual-C0 hash-stage reuse; metadata never reads numeric catalogues."""
import hashlib,io,json,os,re,sqlite3,stat,zipfile
from pathlib import Path
from . import contract as C,io as I

SCHEMA='ROOT_LABEL_DAY_ACTUAL_C0_PRIOR_HASH_STAGE_V1'
STATUS='APPROVED_READONLY_COMPLETE_HASH_STAGE_REUSE_NOT_ADOPTION'


def layout(inventory,count):
    root=Path(inventory['stage_root']);rows=inventory['files']
    expected={str(root/'hash_chunks'/('hash_chunk_%04d.json'%i)) for i in range(count)}|{str(root/'verified_files.sqlite')}
    C.need(type(count)is int and count>0 and inventory['file_count']==len(rows)==count+1
      and len({r['path'] for r in rows})==len(rows) and {r['path'] for r in rows}==expected
      and sum(r['bytes'] for r in rows)==inventory['total_bytes'],'COMPLETE_PRIOR_HASH_CHUNKS_AND_CATALOGUE_REQUIRED')
    for r in rows:
        C.need(type(r['bytes'])is int and r['bytes']>0 and type(r['uid'])is int and r['uid']==1278
          and type(r['nlink'])is int and r['nlink']==1 and type(r['mode'])is int
          and stat.S_ISREG(r['mode']) and all(type(r[k])is int for k in ('inode','mtime_ns','ctime_ns')),
          'EXACT_POSITIVE_PRIOR_HASH_OUTPUT_FRAME')
    return {r['path']:r for r in rows}


def authority(ref,failed_ref):
    from .recovery import authority as failed_authority
    d=C.meta(ref);a,old_inventory,failed_plan=failed_authority(failed_ref)
    C.need(d['schema']==SCHEMA and d['status']==STATUS and d['reviewer']=='root'
      and d['failed_prefix_recovery_reference']==failed_ref
      and d['same_storage_mapping_review_reference']==a['same_storage_mapping_review_reference']
      and d['reuse_only_current_frame_unchanged_whole_SHA_catalogue'] is True
      and d['typed_readback_or_adoption_claimed'] is False and d['old_FAILED_C0_costs_preserved'] is True,
      'EXPLICIT_ROOT_HASH_PROGRESS_ONLY_NOT_PROJECTION_OR_TYPED_ACCEPTANCE')
    parent=d['actual_parent'];C.need(set(parent)=={'manifest','proof','accounting','raw'},'EXACT_ACTUAL_HASH_PARENT_CHAIN')
    m=C.meta(parent['manifest']);proof=C.meta(parent['proof']);account=C.meta(parent['accounting']);req=proof['request']
    jid=str(proof['job_id']);C.need(jid==str(m['job_id']) and proof['uid']==1278 and req['cpus']==64
      and proof['node']==req['node'] and req['node'] in ('compute-0-14','compute-0-18')
      and req['scope_key']==C.KEY and req['producer_plan_reference']==m['plan_reference']
      and C.meta(proof['request_reference'])==req and req['execution_argv']==[C.A.PY,'-B','-m',C.MODULE,
        '--plan',m['plan_reference']['path'],'--startup-proof',parent['proof']['path']],
      'REAL_HASH_PARENT_MACHINE_JOB_UID64_SOURCE_ARGV_NOT_CHAT_ID')
    C.need(m['schema']=='COMPACT_NUMERIC_DAY_PARENT_RECEIPT_V1' and m['status']=='DAY_CLEAN_CHECKPOINTS_PENDING'
      and m['resource_stop'] is True and m['held'] is False and m['errors']==[] and m['quality_hold_fields']==[]
      and m['projection_outputs']==[] and m['UNKNOWN_promoted'] is False,'REAL_RESOURCE_STOP_NO_HASH_ADOPTION_ALREADY_CLAIMED')
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and account['uid']==1278 and account['endpoint']=='202.38.247.57:22' and account['query_returncode']==0
      and account['raw_sacct_reference']==parent['raw'],'REAL_HASH_STAGE_ACCOUNT_AND_RAW')
    rows=[r for r in account['parents'] if str(r['job_id'])==jid]
    C.need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0' and rows[0]['alloc_cpus']==64,
      'ACTUAL_HASH_STAGE64_C0_NOT_FAILED_OR_NEW16_ALIAS')
    raw=C.A.O.pin_bytes(parent['raw'],C.A.Q.read_small).decode('utf-8-sig').splitlines();head=raw[0].split('|')
    records=[dict(zip(head,r.split('|'))) for r in raw[1:] if r.split('|')[0]==jid]
    C.need(len(records)==1 and records[0]['UID']=='1278' and records[0]['AllocCPUS']=='64'
      and records[0]['State']=='COMPLETED' and records[0]['ExitCode']=='0:0','ACTUAL_HASH_STAGE_RAW_C0')
    old=C.meta(m['plan_reference']);C.need(old['failed_prefix_recovery_reference']==failed_ref
      and old['scientific_config_reference']==failed_plan['scientific_config_reference'] and old['requested_cpus']==64
      and old['output_directory']==str(Path(parent['manifest']['path']).parent),'SAME_ORIGINAL_CONFIG_AND_ACTUAL_HASH_ROOT')
    archive=C.meta(d['source_archive_reference']);source_rows=archive['files']
    names=set(C.FILES)-{'prior_hash_stage.py'}
    C.need(archive['schema']=='ROOT_SOURCE15_OPAQUE_COPY_V1' and len(source_rows)==15
      and {Path(r['path']).name for r in source_rows}==names and all(r in req['source_references'] for r in source_rows),
      'REAL_ORIGINAL15_SOURCE_ARCHIVE_MATCHES_ACTUAL_HASH_PARENT')
    archive_raw=C.A.O.pin_bytes(archive['zip_reference'],C.A.Q.read_small)
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as z:
        C.need(len(z.namelist())==15,'ORIGINAL15_SOURCE_ARCHIVE_NO_EXTRA')
        for r in source_rows:
            matches=[n for n in z.namelist() if Path(n).name==Path(r['path']).name]
            C.need(len(matches)==1,'EXACT_ORIGINAL_ARCHIVE_SOURCE_MEMBER')
            body=z.read(matches[0]);C.need(len(body)==r['bytes'] and hashlib.sha256(body).hexdigest()==r['sha256'],
              'ORIGINAL_HASH_SOURCE_ARCHIVE_COMPLETE_BYTES_SHA_WITNESS_NEVER_EXECUTED')
    inv=C.meta(d['lstat_inventory_reference'])
    C.need(inv['schema']=='ACTUAL_LABEL4524608_CLOSED_RECOVERY_STAGE_LSTAT_V1' and str(inv['job_id'])==jid
      and inv['parent_manifest_reference']==parent['manifest']
      and inv['scientific_SQL_or_parts_or_body_opened_or_hashed'] is False
      and inv['stage_root']==str(Path(old['output_directory'])/'failed_prefix_adoption'),'REAL_LSTAT_ONLY_HASH_OUTPUT_AUTHORITY')
    # The lstat was captured with a combined actual account; the later Root
    # descriptor has a separately queried account for the same actual parent.
    inventory_account=C.meta(inv['actual_parent_accounting_reference'])
    ir=[r for r in inventory_account['parents'] if str(r['job_id'])==jid]
    C.need(inventory_account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and inventory_account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and inventory_account['uid']==1278
      and inventory_account['endpoint']=='202.38.247.57:22' and inventory_account['query_returncode']==0
      and len(ir)==1 and all(ir[0][k]==rows[0][k] for k in ('state','exit_code','alloc_cpus','elapsed_raw_seconds')),
      'LSTAT_AND_INDEPENDENT_ACCOUNT_SAME_REAL_C0_PARENT_FACTS')
    inventory_raw=C.A.O.pin_bytes(inventory_account['raw_sacct_reference'],C.A.Q.read_small).decode('utf-8-sig').splitlines()
    ih=inventory_raw[0].split('|');iv=[dict(zip(ih,r.split('|'))) for r in inventory_raw[1:] if r.split('|')[0]==jid]
    C.need(len(iv)==1 and all(iv[0][k]==records[0][k] for k in ('UID','AllocCPUS','State','ExitCode','ElapsedRaw')),
      'LSTAT_CAPTURE_ACCOUNT_ACTUAL_RAW_PARENT_PARITY')
    layout(inv,len(old_inventory['lstat_observation_chunk_references']))
    sources=[ref,*parent.values(),m['plan_reference'],proof['request_reference'],d['source_archive_reference'],archive['zip_reference'],
      d['lstat_inventory_reference'],inv['actual_parent_accounting_reference'],inventory_account['raw_sacct_reference'],
      d['same_storage_mapping_review_reference'],m['fixture_gate'],m['repository_check_actual_reference']]
    gate=C.meta(m['fixture_gate']);check=C.meta(m['repository_check_actual_reference'])
    C.need(gate['status']=='PASS' and gate['tests']==6 and gate['errors']==gate['failures']==0
      and check['status']=='PASS' and check['returncode']==0,'REAL_HASH_STAGE_SOURCE6_AND_WHOLECHECK')
    original=C.meta(gate['original_compact3_reference']);result=C.meta(check['result_reference'])
    C.need(original['status']=='PASS' and original['tests_run']==3 and original['errors']==original['failures']==0
      and result['status']=='PASS' and result['export_verification_required'] is False,'REAL_HASH_STAGE_ORIGINAL3_AND_WHOLE_RESULT')
    sources.extend([gate['original_compact3_reference'],check['result_reference']])
    return d,inv,old_inventory,proof,C.M.M.unique(sources)


def frozen_file(row,root,maximum):
    from .recovery import safe_old,_frame
    p,s=safe_old(row['path'],row,root);C.need(s.st_size<=maximum,'BOUNDED_PRIOR_HASH_STAGE_FILE')
    h=hashlib.sha256();raw=[]
    with p.open('rb') as stream:
        before=_frame(os.fstat(stream.fileno()));C.need(before==_frame(s),'PRIOR_HASH_CURRENT_FD')
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
            if maximum<=2<<20:raw.append(block)
        C.need(before==_frame(os.fstat(stream.fileno()))==_frame(p.lstat()),'PRIOR_HASH_STAGE_FILE_CHANGED')
    return {'path':str(p),'bytes':s.st_size,'sha256':h.hexdigest()},before,b''.join(raw)


def inherit_entry(row,observed,oldroot,prior_node,current_node):
    from .recovery import safe_old,_frame
    ref=row['reference'];C.reference(ref);expected=row['current_CPU_frame']
    C.need(type(expected)is list and len(expected)==5 and all(type(v)is int for v in expected)
      and ref['path']==observed['path'] and ref['bytes']==observed['bytes'],'EXACT_HASH_ROW_AND_ORIGINAL_LSTAT')
    p,s=safe_old(ref['path'],observed,oldroot);current=_frame(s)
    C.need(current[1:]==expected[1:] and (prior_node!=current_node or current==expected),
      'UNCHANGED_ALL_INTRINSIC_CURRENT_FRAME_REQUIRED_FOR_SHA_REUSE')
    with p.open('rb') as stream:
        C.need(current==_frame(os.fstat(stream.fileno()))==_frame(p.lstat()),'UNCHANGED_OLD_FILE_CURRENT_FD_NO_BODY_READ')
    return ref,current


def reuse(plan,cfg,proof,root,budget):
    d,inv,original,prior_proof,_=authority(plan['prior_hash_stage_reference'],plan['failed_prefix_recovery_reference'])
    C.need(proof['node'] in ('compute-0-14','compute-0-18') and proof['request']['cpus']==plan['requested_cpus']>=16,
      'CURRENT_REAL_DYNAMIC_CPU_PARENT_NOT_PRIOR64_ALIAS')
    stage=Path(inv['stage_root']);by_path=layout(inv,len(original['lstat_observation_chunk_references']))
    catalog_path=stage/'verified_files.sqlite';catalog_ref,catalog_frame,_=frozen_file(by_path[str(catalog_path)],stage,128<<20)
    db=sqlite3.connect(root/'verified_files.sqlite');db.execute('CREATE TABLE files(path TEXT PRIMARY KEY,bytes INTEGER,sha TEXT,frame TEXT) WITHOUT ROWID')
    olddb=sqlite3.connect(catalog_path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=120)
    refs=[];n=total=0;oldroot=Path(original['exact_closed_projection_directory'])
    try:
        for i,original_ref in enumerate(original['lstat_observation_chunk_references']):
            budget.observe();C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_PRIOR_HASH_STAGE_REUSE')
            ref,frame,raw=frozen_file(by_path[str(stage/'hash_chunks'/('hash_chunk_%04d.json'%i))],stage,2<<20)
            item=json.loads(raw);source=C.meta(original_ref)
            C.need(item['schema']=='FAILED_PREFIX_CURRENT_CPU_HASH_CHUNK_V1' and item['source_lstat_chunk_reference']==original_ref
              and item['first_scientific_whole_SHA_only_on_CPU'] is True and item['observed_device_is_current_CPU_only'] is True
              and source['schema']=='LABEL_FAILED_CLOSED_PREFIX_LSTAT_CHUNK_V1','EXACT_COMPLETE_PRIOR_HASH_CHUNK_BINDING')
            observed={r['path']:r for r in source['observations']};files=item['files']
            C.need(len(files)==len(observed)==len(source['observations'])==len({r['reference']['path'] for r in files})
              and {r['reference']['path'] for r in files}==set(observed)
              and sum(r['reference']['bytes'] for r in files)==item['bytes'],'NO_PRIOR_HASH_CHUNK_GAP_DUPLICATE_OR_EXTRA')
            for r in files:
                q,current=inherit_entry(r,observed[r['reference']['path']],oldroot,prior_proof['node'],proof['node'])
                prior=olddb.execute('SELECT bytes,sha,frame FROM files WHERE path=?',(q['path'],)).fetchone()
                C.need(prior is not None and prior[0]==q['bytes'] and prior[1]==q['sha256']
                  and json.loads(prior[2])==r['current_CPU_frame'],'COMPLETE_PRIOR_SQL_CATALOGUE_EQUALS_HASH_CHUNKS')
                db.execute('INSERT INTO files VALUES(?,?,?,?)',(q['path'],q['bytes'],q['sha256'],json.dumps(current)));n+=1;total+=q['bytes']
            refs.append(ref)
        C.need(n==original['files']==olddb.execute('SELECT count(*) FROM files').fetchone()[0] and total==original['bytes'],
          'EXACT_COMPLETE_PRIOR_HASH_FILES_BYTES_CATALOGUE')
        db.commit()
    finally:olddb.close();db.close()
    from .recovery import _frame
    C.need(_frame(catalog_path.lstat())==catalog_frame,'PRIOR_CATALOGUE_CHANGED_DURING_READONLY_REUSE')
    I.save(root/'prior_hash_stage_reuse.json',{'schema':'ACTUAL_PRIOR_HASH_STAGE_CURRENT_FD_REUSE_V1',
      'prior_hash_stage_reference':plan['prior_hash_stage_reference'],'prior_parent_job_id':str(prior_proof['job_id']),
      'current_parent_job_id':str(proof['job_id']),'prior_catalogue_reference':catalog_ref,
      'hash_chunk_references':refs,'files':n,'bytes':total,'current_old_file_FD_frames_verified':True,
      'old_scientific_bodies_rehashed':False,'typed_readback_or_adoption_complete':False,
      'old_FAILED_and_C0_and_UNKNOWN_costs_preserved':True})
    return refs,total
