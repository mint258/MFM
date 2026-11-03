"""Supplement the original Alpha735 opaque rows without rerunning norm or SQL."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,stat,sys,traceback,unittest
from pathlib import Path
from . import kernel as K,support as S

SQL_BYTES=37876914074
SQL_SHA='bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29'
HEADER_OFFSET=309479406
HEADER_BYTES=445
HEADER_SHA='cfc5d0971f328328d50ec052224942f28f6f78477f8b415cffccd4c9c927f5a2'


def admit(plan,proof,plan_path,proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16)
    req=proof['request']
    K.need(plan['schema']=='COCONUT_ALPHA_NATIVE735_PLAN_V1' and plan['scope_key']=='coconut_alpha_native735_v1'
      and req['scope_key']==plan['scope_key'] and req['producer_plan_reference']==S.pin(plan_path),'EXACT_NATIVE735_PLAN_AND_ROOT_REQUEST')
    K.need(req['execution_argv']==plan['execution_argv'] and '--plan' in req['execution_argv']
      and req['execution_argv'][req['execution_argv'].index('--plan')+1]==str(plan_path)
      and req['execution_argv'][req['execution_argv'].index('--startup-proof')+1]==str(proof_path),'EXACT_ROOT_LAUNCH_ARGUMENTS')
    K.need(os.getuid()==1264 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_PARENT_AND_BOOT')
    refs={r['path']:r for r in req['source_references']}
    for file in Path(__file__).parent.glob('*.py'):K.need(refs.get(str(file.absolute()))==S.pin(file),'CURRENT_NATIVE735_SOURCE')
    for ref in req['source_references']:S.verify(ref)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    return authority


def source_tests(out):
    from .test_source import Source
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Source);stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=S.save(out/'source_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),transcript=stream.getvalue(),before_DATA=True))
    K.need(result.wasSuccessful() and result.testsRun==4 and not result.skipped,'FOUR_ORIGINAL_COPY_AND_FORMULA_SOURCE_CASES');return ref


def header(plan,original_A,out):
    ref=plan['original_SQL_reference']
    K.need(ref==original_A['input_reference'] and ref['bytes']==SQL_BYTES and ref['sha256']==SQL_SHA,'ORIGINAL_WHOLE_SQL_AUTHORITY')
    inventory=original_A['inventory']
    K.need(original_A['job_id']=='1884772' and original_A['status']=='FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE'
      and inventory['full_EOF_and_all_tables_proven'] is True and inventory['current_full_SQL_SHA_reverified'] is True
      and inventory['read_region_SHA256']==SQL_SHA and inventory['source_bytes_consumed_at_record_boundary']==SQL_BYTES
      and len(inventory['physical_COPY_rows_by_table'])==15 and inventory['COPY_blocks_by_table']['entries']==1,'ORIGINAL_CLOSED_FULL_SOURCE_NOT_NEW_SELF_C0')
    path=Path(ref['path']);K.need(not any(p.is_symlink() for p in (path,*path.parents)),'NO_SQL_LINK')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);K.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1 and before.st_size==SQL_BYTES,'ORIGINAL_OWNED_SQL_HEADER_SOURCE')
        raw=os.pread(fd,HEADER_BYTES,HEADER_OFFSET)
        K.need(S.frame(before)==S.frame(os.fstat(fd))==S.frame(path.stat()),'IMMUTABLE_HEADER_SOURCE')
    finally:os.close(fd)
    K.need(len(raw)==HEADER_BYTES and hashlib.sha256(raw).hexdigest()==HEADER_SHA,'EXACT_ACTUAL_COPY_COLUMN_ORDER_NOT_DDL_GUESS')
    names=K.columns(raw);schema=json.loads(S.read(plan['original_schema_reference']))
    entry=[t for t in schema['tables'] if t['table_identifiers']==['public','entries']]
    K.need(len(entry)==1 and entry[0]['complete_CREATE_TABLE_in_bounded_region'] is True
      and set(names)=={c['name'] for c in entry[0]['columns']},'ACTUAL_COPY_AND_ORIGINAL_DDL_COLUMN_SET')
    receipt=S.save(out/'original_COPY_header_witness.json',dict(SQL_reference=ref,offset=HEADER_OFFSET,bytes=HEADER_BYTES,sha256=HEADER_SHA,
      literal_header=raw.decode('ascii'),current_SQL_frame=list(S.frame(before)),current_read_bytes=HEADER_BYTES,
      original_full_SQL_authority=plan['original_A_receipt_reference'],current_whole_SQL_SHA_recomputed=False))
    return names,receipt


def execute(plan,out,guard):
    for job in ('1884772','1885088','1885095'):
        accounting=json.loads(S.read(plan['original_parent_accounting_references'][job]))
        parent=accounting['actual_parent']
        K.need(accounting['endpoint']=='218.192.171.238:22' and accounting['uid']==1264 and accounting['job_id']==job
          and accounting['actual_terminal'] is True and accounting['query_returncode']==0
          and parent['JobIDRaw']==job and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0'
          and parent['User']=='alpha' and parent['UID']=='1264','ORIGINAL_PARENT_ACTUAL_C0_AND_ALPHA_OWNER')
        S.read(accounting['raw_sacct_reference'],2<<20)
    strict=json.loads(S.read(plan['original_strict_receipt_reference']))
    receipt=json.loads(S.read(plan['original_diagnosis_receipt_reference']))
    summary=json.loads(S.read(plan['original_diagnosis_summary_reference']))
    K.need(strict['job_id']=='1885088' and strict['counters']['unresolved_without_identity_or_composition']==735
      and strict['READY_candidate'] is False and strict['global_decontamination_or_pool_release'] is False,'ORIGINAL_STRICT735_HOLD')
    K.need(receipt['job_id']=='1885095' and receipt['READY'] is False
      and receipt['original_parent_chain']['receipt']==plan['original_strict_receipt_reference']
      and receipt['summary_reference']==plan['original_diagnosis_summary_reference'],'EXACT_ORIGINAL_DIAGNOSIS_PARENT_CHAIN')
    K.need(summary['diagnosis_complete'] is True and summary['diagnostic_rows']==735 and summary['opaque_rows_captured']==735
      and summary['graph_identity_acceptance'] is False and summary['original_UNKNOWN735_not_upgraded'] is True,'EXACT735_DIAGNOSIS_NOT_GRAPH_ACCEPTANCE')
    for name,field in [('diagnosis_reference','diagnosis_DATA_reference'),('opaque_manifest_reference','opaque_SQL_DATA_reference')]:
        K.need(plan[name]==summary[field],'ORIGINAL_SUMMARY_BINDS_CURRENT_DATA')
    K.need(plan['original_unknown_locator_reference']==strict['outputs']['unknown_locators'],'STRICT_UNKNOWN_LOCATORS_BIND_ALL735')
    diagnoses=S.rows(plan['diagnosis_reference']);opaque=S.rows(plan['opaque_manifest_reference']);unknown=S.rows(plan['original_unknown_locator_reference'])
    K.need(len(diagnoses)==len(opaque)==len(unknown)==735,'ALL_AND_ONLY_ORIGINAL735')
    K.need(len({S.canonical(r) for r in unknown})==735
      and {S.canonical(r['original_unresolved']) for r in diagnoses}=={S.canonical(r) for r in unknown},'EXACT_ORIGINAL_UNKNOWN735_PHYSICAL_COVERAGE')
    names,header_ref=header(plan,json.loads(S.read(plan['original_A_receipt_reference'])),out)
    source_ids=set();counts=collections.Counter();pending=collections.deque();maximum=2*plan['workers']
    destination=out/'native735_original_fields.DATA.jsonl'
    with destination.open('xb') as target,cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(plan,)) as pool:
        def collect():
            value=pending.popleft().result();guard.check()
            raw=S.canonical(value);target.write(raw);counts['rows']+=1
            formula=value['native_formula_observation'];counts['native_formula_candidates']+=formula.get('composition') is not None
            counts['native_formula_reason/'+formula['reason']]+=1
            for key,text in value['supplemental_original_fields'].items():counts['nonempty_field/'+key]+=text is not None and text!=''
        for diagnosis,item in zip(diagnoses,opaque):
            guard.check();row=item['source'];key=(row['source_table'],row['copy_block'],row['source_row_ordinal'])
            K.need(key not in source_ids,'NO_DUPLICATE_ORIGINAL_SOURCE');source_ids.add(key)
            ref=item['opaque_original_row_reference'];K.need(ref['bytes']==row['source_bytes'] and ref['sha256']==row['source_row_sha256'],'OPAQUE_REFERENCE_EQUALS_ORIGINAL_SQL_ROW')
            raw=S.read(ref);pending.append(pool.submit(K.work,(diagnosis,item,raw,names,plan.get('selected_field_cap_bytes',8<<20))))
            if len(pending)>=maximum:collect()
        while pending:collect()
        target.flush();os.fsync(target.fileno())
    K.need(counts['rows']==735,'NO_SOURCE_ROW_LOSS')
    guard.check()
    return dict(schema='COCONUT_ALPHA_NATIVE735_DIAGNOSTIC_V1',status='ORIGINAL735_NATIVE_FIELDS_OBSERVED_NOT_EXCLUSION_ACCEPTANCE',
      counts=dict(counts),DATA=dict(S.pin(destination),rows=735),header_witness=header_ref,
      original_strict_receipt_reference=plan['original_strict_receipt_reference'],original_diagnosis_receipt_reference=plan['original_diagnosis_receipt_reference'],
      original_parent_accounting_references=plan['original_parent_accounting_references'],
      original_graph_UNKNOWN_retained=True,new_full_key_computations=0,new_normalization_calls=0,new_QM_UFF_network_calls=0,
      native_formula_or_ID_association_accepted=False,all11_ready=False,global_pool_release=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text());authority=admit(plan,proof,a.plan,a.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    out=Path(plan['output_directory']);guard=Guard(plan)
    try:
        guard.check();out.mkdir(parents=True,exist_ok=False);K.initialize(plan);tests=source_tests(out)
        result=execute(plan,out,guard)
        S.save(out/'receipt.json',dict(schema='COCONUT_ALPHA_NATIVE735_PRODUCER_V1',plan=S.pin(a.plan),startup_proof=S.pin(a.startup_proof),
          source_tests=tests,profile_admission=authority,result=result,runtime=guard.receipt(),actual_parent_C0_pending_root_readback=True,all11_ready=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),original_UNKNOWN_unchanged=True,partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
