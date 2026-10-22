"""Root-only metadata preparation: real FAILED science, completed v3 validation.
No QM, queue writes, adoption, Slurm, or dependency updates. Preserve every byte
of the failed acceptance catalog, with explicit relocation and logical link.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,socket,stat,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
FINAL=ROOT/'acceptance/final_20261016_v1'
OLD_MAP=ROOT/'reports/wp5_acceptance_control_jobmap_actual541_v1.json'
OLD_MAP_SHA='7cfac0397a2b47dc0ab2cd85a77c3c35b15a7cdb4d0b8cbfbcc65187271409df'
OLD_ACCOUNT=FINAL/'formal541_terminal_accounting.json'
NEW_MAP=FINAL/'control_jobmap_actual542_v1.json'
PREPARED=FINAL/'exact_two_budget1_retry_v1/prepared.json'
PREPARED_SHA='86c75e92aebf35f31d22d420885eea6248886eaac7c7a6efe4cdb247ef14b5c1'
VERIFIED=PREPARED.parent/'verified_240_slots_v3.json'
ADOPTION=PREPARED.parent/'production_adoption_v3.json'
VALIDATOR=ROOT/'scripts/wp5_exact_two_retry_validator_v3.py'
VALIDATOR_SHA='387811f9641ad60cc1d25813cd3d36e28c2c3b2525b80338ccf1aeb8fafed110'
V2_SOURCE=ROOT/'scripts/wp5_exact_two_retry_v2.py'
V2_SHA='91c6c7d9f8502a128b2ff70eb78a851cecaae756336fd57b13242aaf319934ef'
SCI_JOB='4515515';META_JOB='4515539'
RUN_JSON=ROOT/'runtime/task_69_exact_budget1_retry_20261016/job_4515515/run.json'
CURRENT=FINAL/'catalog';ARCHIVED=FINAL/'catalog_failed_4515497';NEXT=FINAL/'catalog_closed_v2'
MIDS={'principal_01100742','principal_01152793'}
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED','REVOKED','SPECIAL_EXIT'}
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def ref(path):return {'path':str(path),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def require_reference(reference,path):
    if reference!=ref(path):raise ValueError('BOUND_METADATA_REFERENCE_CHANGED:'+str(path))
def publish(path,value):
    path=Path(path)
    if os.path.lexists(path):raise FileExistsError('WRITE_ONCE_DESTINATION_EXISTS:'+str(path))
    pending=path.with_name(path.name+'.pending')
    with pending.open('xb') as stream:stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
    pending.rename(path)
def accounting(path):
    raw=json.loads(path.read_text());data=raw.get('sacct',raw)
    code=data.get('returncode',data.get('sacct_returncode'));stdout=data.get('stdout',data.get('sacct_stdout',''))
    if code!=0 or not isinstance(stdout,str):raise ValueError('ACTUAL_ACCOUNTING_QUERY_FAILED:'+str(path))
    result={}
    for line in stdout.splitlines():
        fields=[part.strip() for part in line.split('|')]
        if len(fields)<4 or not fields[0].isdigit():continue
        if fields[0] in result:raise ValueError('DUPLICATE_ACTUAL_PARENT_ACCOUNTING:'+fields[0])
        if fields[1]!='zixiao' or not fields[2]:raise ValueError('ACTUAL_ACCOUNTING_USER_OR_STATE_DIFFERS')
        result[fields[0]]={'job_id':fields[0],'user':fields[1],'state':fields[2].split()[0],'exit_code':fields[3],'raw_fields':fields}
    if not result:raise ValueError('ACTUAL_PARENT_ACCOUNTING_EMPTY')
    return result
def exact_parent(path,job,state,exit_code):
    rows=accounting(path)
    if job not in rows or rows[job]['state']!=state or rows[job]['exit_code']!=exit_code:raise ValueError('ACTUAL_PARENT_NOT_EXPECTED_STATUS:'+job)
    return rows[job]
def prepare(args):
    if socket.gethostname().split('.')[0]!='compute-0-20' or os.getuid()!=1278:raise ValueError('METADATA_PREPARATION_COMPUTE20_UID1278_ONLY')
    if not args.out.resolve().is_relative_to(FINAL):raise ValueError('OWN_FINAL_ACCEPTANCE_METADATA_OUTPUT_REQUIRED')
    destinations=[args.out,NEW_MAP,NEW_MAP.with_name(NEW_MAP.name+'.pending'),ARCHIVED,NEXT]
    existing=[str(path) for path in destinations if os.path.lexists(path)]
    if existing:
        print(json.dumps({'status':'NO_MUTATIONS_DESTINATION_ALREADY_EXISTS','existing_destinations':existing,'mutation_replayed':False,'Root_review_required':True}));return 2
    for path,digest in ((OLD_MAP,OLD_MAP_SHA),(PREPARED,PREPARED_SHA),(VALIDATOR,VALIDATOR_SHA),(V2_SOURCE,V2_SHA)):
        if sha(path)!=digest:raise ValueError('FROZEN_METADATA_SOURCE_CHANGED:'+str(path))
    adoption=json.loads(ADOPTION.read_text());verified=json.loads(VERIFIED.read_text())
    if adoption.get('schema')!='WP5_EXACT_TWO_BUDGET1_ATOMIC_ADOPTION_V3' or adoption.get('status')!='EXACT_TWO_TRUE_RETRY_ADOPTED' or adoption.get('new_formal_parent_job_id')!=SCI_JOB or str(adoption.get('metadata_validation_parent_job_id'))!=META_JOB or adoption.get('queue_budget_preserved')!=1 or adoption.get('completion_rank_preserved') is not True or adoption.get('old_scientific_files_written') is not False:raise ValueError('BOUND_V3_ADOPTION_REQUIRED')
    require_reference(adoption['verified'],VERIFIED);require_reference(adoption['script'],VALIDATOR);require_reference(adoption['frozen_prepared_source'],V2_SOURCE)
    require_reference(adoption['actual_terminal_accounting'],args.science_accounting);require_reference(adoption['actual_validation_accounting'],args.validation_accounting)
    science=exact_parent(args.science_accounting,SCI_JOB,'FAILED','1:0');metadata=exact_parent(args.validation_accounting,META_JOB,'COMPLETED','0:0')
    if adoption['scientific_parent_actual'].get('raw_fields')!=science['raw_fields'] or adoption['metadata_validation_parent_actual'].get('raw_fields')!=metadata['raw_fields']:raise ValueError('V3_ADOPTED_ACTUAL_ACCOUNTING_DIFFERENT')
    if verified.get('schema')!='WP5_EXACT_TWO_RETRY_240_SLOTS_VERIFIED_V3' or verified.get('status')!='EXACT_TWO_BUDGET1_SCI_EXPORT_VERIFIED' or str(verified.get('job_id'))!=SCI_JOB or str(verified.get('validation_job_id'))!=META_JOB or verified.get('records')!=20 or verified.get('task_slots')!=240 or verified.get('attempt_id')!=1 or verified.get('new_QM_calls')!=0:raise ValueError('BOUND_V3_EXISTING_240_SLOT_VERIFICATION_REQUIRED')
    require_reference(verified['prepared'],PREPARED);require_reference(verified['script'],VALIDATOR);require_reference(verified['metadata_validator_source'],VALIDATOR);require_reference(verified['frozen_prepared_source'],V2_SOURCE);require_reference(verified['run_json'],RUN_JSON)
    error_path=ROOT/'logs/exact_two_retry_4515515.err';require_reference(verified['original_validator_error'],error_path);require_reference(adoption['original_validator_error'],error_path)
    text=error_path.read_text()
    if text.count('Traceback (most recent call last):')!=1 or 'wp5_exact_two_retry_v2.py", line 153' not in text or not text.rstrip().endswith("KeyError: 'lane'"):raise ValueError('REAL_VALIDATOR_ONLY_FAILURE_CAUSE_DIFFERS')
    old=json.loads(OLD_MAP.read_text());jobs=old['jobs'];old_ids={str(row['job_id']) for row in jobs};old_accounting=accounting(OLD_ACCOUNT)
    if len(jobs)!=541 or len(old_ids)!=541 or SCI_JOB in old_ids or set(old_accounting)!=old_ids or any(row['state'] not in TERMINAL for row in old_accounting.values()):raise ValueError('OLD541_ACTUAL_TERMINAL_SCOPE_DIFFERS')
    run=json.loads(RUN_JSON.read_text());options=run['options']
    if str(options['job_id'])!=SCI_JOB or run['node']!='compute-0-13' or options['task_id']!='69' or options['queue']!=str(PREPARED.parent/'queue.sqlite') or options['session']!=verified['private_session']['session_id']:raise ValueError('REAL_515_SCI_RUN_IDENTITY_DIFFERS')
    if CURRENT.is_symlink() or not CURRENT.is_dir() or CURRENT.resolve().parent!=FINAL.resolve():raise ValueError('ORIGINAL_FAILED_CATALOG_MUST_BE_OWN_REAL_DIRECTORY')
    original=json.loads((CURRENT/'catalog.json').read_text())
    if original.get('status')!='INCOMPLETE_OR_REQUIRES_ACTION' or {row.get('molecule_id') for row in original['issues']}!=MIDS or any(row.get('issue')!='RECEIPT_OR_EXPORT_NOT_AUTHORITATIVE' for row in original['issues']):raise ValueError('ORIGINAL_FAILED_CATALOG_NOT_EXACT_TWO_CASE')
    files=[]
    for path in [CURRENT,*CURRENT.rglob('*')]:
        info=path.lstat()
        if info.st_uid!=1278 or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise ValueError('FAILED_ACCEPTANCE_METADATA_OWNER_OR_TYPE_DIFFERS:'+str(path))
        if stat.S_ISREG(info.st_mode):files.append(path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:proofs=list(pool.map(ref,files))
    for proof in proofs:proof['archived_path']=str(ARCHIVED/Path(proof['path']).relative_to(CURRENT))
    new_entry={'job_id':SCI_JOB,'node':run['node'],'task_id':'69','user':'zixiao','execution_id':options['session'],'role':'EXACT_TWO_TRUE_SCIENTIFIC_RETRY_BUDGET1','scheduler_state':'FAILED','scheduler_exit_code':'1:0','SCI_status':'EXISTING_FROZEN_240_SLOTS_VERIFIED_BY_V3','scheduler_failure_cause':'Frozen runner closed 2 molecules/20 records; subsequent v2 metadata validator raised KeyError lane on COMMON schema.','metadata_validation_parent':{'job_id':META_JOB,'state':'COMPLETED','exit_code':'0:0'},'run_json':ref(RUN_JSON),'verification':ref(VERIFIED),'adoption':ref(ADOPTION)}
    newmap={'schema':'WP5_ACCEPTANCE_ACTUAL_FORMAL_PARENTS_V1','generated_epoch':time.time(),'status':'ACTUAL_542_FORMAL_PARENTS_TERMINAL_SCIENCE_VERIFIED','actual_job_count':542,'sources':[ref(OLD_MAP),ref(OLD_ACCOUNT),ref(args.science_accounting),ref(args.validation_accounting),ref(ADOPTION),ref(VERIFIED),ref(RUN_JSON)],'jobs':jobs+[new_entry],'old541_entries_preserved_exactly':True,'all_542_formal_parents_terminal':True,'scientific_parent_4515515_actual':science,'metadata_parent_4515539_actual':metadata,'metadata_validation_parent_not_counted_as_formal_science':True,'Slurm_queried_by_this_tool':False,'actual_saved_Slurm_evidence_verified':True,'SCI_files_read_by_this_tool':False,'queue_written':False,'new_QM_calls':0}
    if newmap['jobs'][:541]!=jobs or len({str(row['job_id']) for row in newmap['jobs']})!=542:raise ValueError('FLAT542_MAP_PROJECTION_DIFFERS')
    args.out.mkdir(parents=True,exist_ok=False)
    intent={'schema':'WP5_FAILED_ACCEPTANCE_METADATA_RELOCATION_V3','time':time.time(),'source':ref(__file__),'original_directory':str(CURRENT),'archive_directory':str(ARCHIVED),'files':proofs,'total_bytes':sum(row['bytes'] for row in proofs),'relative_link':{'path':str(CURRENT),'text':'catalog_closed_v2','target':str(NEXT)},'new_jobmap_path':str(NEW_MAP),'scientific_source_files_written_or_deleted':False,'adoption':ref(ADOPTION),'verified':ref(VERIFIED),'mutation_replay_allowed':False}
    publish(args.out/'preparation_intent.json',intent)
    publish(NEW_MAP,newmap)
    CURRENT.rename(ARCHIVED)
    for proof in proofs:
        info=Path(proof['archived_path']).lstat()
        if info.st_uid!=1278 or not stat.S_ISREG(info.st_mode) or info.st_size!=proof['bytes']:raise ValueError('RENAMED_METADATA_OWNER_TYPE_OR_BYTES_DIFFERS')
    CURRENT.symlink_to('catalog_closed_v2',target_is_directory=True)
    receipt={**intent,'status':'ACTUAL542_WRITTEN_FAILED_CATALOG_PRESERVED_RELATIVE_LINK_READY','new_jobmap':ref(NEW_MAP),'archive_same_filesystem_rename_preserves_all_bytes':True,'original_JSON_bytes_preserved':True,'historical_JSON_path_projection':'Original JSON paths are historical. Each unchanged original file is located by archived_path in files; no historical JSON was rewritten.','link_actual_text':os.readlink(CURRENT),'no_new_catalog_job_submitted':True,'pending_QA_unmodified':True}
    publish(args.out/'preparation_receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'new_jobmap':str(NEW_MAP),'new_jobmap_sha256':receipt['new_jobmap']['sha256'],'relocation_receipt':str(args.out/'preparation_receipt.json'),'archived_metadata_files':len(proofs),'archived_metadata_bytes':receipt['total_bytes'],'new_QM_calls':0}));return 0
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--science-accounting',type=Path,required=True);ap.add_argument('--validation-accounting',type=Path,required=True);ap.add_argument('--out',type=Path,default=FINAL/'catalog_metadata_preparation_v3');args=ap.parse_args();raise SystemExit(prepare(args))
if __name__=='__main__':main()
