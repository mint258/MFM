"""CPU-only: six immutable original calls -> fifteen exact target inputs, zero QM."""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,json,os,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.pprime.causal15_main_v1 import contract as C,io as I,render as T
OPTIONS=('plan','root-preflight','quota-reuse-review','output')


def inventory_row(inventory,kind,path):
    hits=[r for r in inventory['entries'] if r['kind']==kind and r['origin']['path']==str(path)]
    C.need(len(hits)==1,'EXACT_FIXED_ORIGIN_INVENTORY_LOCATOR');return hits[0]


def raw_reader():
    directory=C.PPRIME/'frame_native_precision_diagnosis_v2';sys.path.insert(0,str(directory))
    from raw_reader import BoundedRawReader
    return BoundedRawReader


def original(reference,inventory,engine,protocol,out):
    from common import read_staging
    record=read_staging(I.body(reference,C.RESULT_CAP));case=record['case'];case_id=case['case_id'];condition=C.source_identity(case_id,case)
    C.need(record['case_id']==case_id and record['QM_call_attempted'] is True,'ACTUAL_ORIGINAL_CALL_REQUIRED')
    expected=C.OLD/'run'/case_id/'result.json';C.need(reference['path']==str(expected),'ONLY_FIXED_ORIGINAL_RESULT_PATH')
    C.need(C.triple(inventory_row(inventory,'pinned_case_result_metadata',expected)['origin'])==C.triple(reference),'EXACT_FROZEN_CASE_RESULT_SHA')
    task=next(t for t in protocol['tasks'] if t['name']==case['calc_type']);raw=record['raw_reference']
    C.need(raw['record_id']==case['row']['record_id'] and raw['calc_type']==case['calc_type'] and raw['execution_id']==case_id
        and raw['raw_call_durable'] is True and raw['output_retained'] is True and raw['input_bodies_saved'] is False,'PER_CALL_RAW_IDENTITY')
    db_path=expected.parent/'all_output_raw.sqlite';C.need(raw['container_path']==str(db_path),'FIXED_TRANSITIVE_SQLITE_LOCATOR_ONLY')
    declared=inventory_row(inventory,'raw_sqlite_locator_no_main_SHA',db_path)['origin'];before=db_path.stat()
    C.need(before.st_size==declared['bytes'],'ORIGINAL_SQLITE_STAT_LOCATOR_SIZE')
    reader=raw_reader()(db_path,engine.OUTPUT_ARCHIVE,C.RAW_CAP,C.RESULT_CAP)
    try:retained=reader.get(raw['record_id'],raw['calc_type'],raw['execution_id'],raw['raw_sha256'],raw['raw_bytes'])
    finally:reader.close()
    after=db_path.stat();C.need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'ORIGINAL_SQLITE_CURRENT_FRAME_STABLE')
    inputs={};refs=[]
    for reference_input in record['actual_postcall_input_references']:
        r=C.triple(reference_input);path=pathlib.Path(r['path']);C.need(path.parent==expected.parent/'actual_postcall_inputs','FIXED_ACTUAL_INPUT_LEAF')
        loc=inventory_row(inventory,'actual_input_stat_locator',path)['origin'];C.need(loc['bytes']==r['bytes'],'ORIGINAL_INPUT_STAT_SIZE')
        C.need(reference_input['matches_prepared_bytes'] is True,'ORIGINAL_POSTCALL_PREPARED_BYTES_MATCH')
        prepared=[v for v in case['input_files'] if pathlib.Path(v['path']).name==path.name]
        C.need(len(prepared)==1 and (prepared[0]['bytes'],prepared[0]['sha256'])==(r['bytes'],r['sha256']),'PREPARED_ACTUAL_INPUT_SHA_CHAIN')
        C.need(path.name not in inputs,'NO_DUPLICATE_INPUT_NAMES');inputs[path.name]=I.body(r,C.INPUT_CAP);refs.append(r)
    names={'input.xyz','input.mop'} if task['family']=='mopac' else {'input.xyz','native.inp'}
    C.need(set(inputs)==names and sum(map(len,inputs.values()))<=C.INPUT_CAP,'EXACT_ORIGINAL_INPUT_MEMBER_SET')
    native,seed=T.bridge(case,inputs,task,protocol,engine)
    hashes=[{'name':name,'sha256':C.sha(data)} for name,data in sorted(inputs.items())]
    metadata=retained['metadata'];C.need(metadata['input_file_sha256']==hashes
        and record['parsed_wp5_result']['provenance']['input_file_sha256']==hashes,'ACTUAL_PER_CALL_RAW_TO_INPUT_SHA')
    bundled=engine.OUTPUT_ARCHIVE.bundle([{'name':n,'data':b,'role':'input','sha256':C.sha(b),'byte_count':len(b)} for n,b in sorted(inputs.items())])[0]
    C.need(C.sha(bundled)==metadata['input_bundle_sha256']==record['parsed_wp5_result']['provenance']['input_bundle_sha256'],'ORIGINAL_INPUT_BUNDLE_SHA')
    return {'case':case,'condition':condition,'task':task,'inputs':inputs,'source_result_reference':reference,
        'original_actual_input_references':refs,'original_raw_reference':raw,'seed':seed,
        'old_vectors':record.get('independent_raw_readback'),'old_result':record.get('parsed_wp5_result'),
        'old_raw_call_current_SHA_verified':True,'original_database_whole_SHA_claimed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    args=p.parse_args();plan,proof,session=I.admit(__file__,args,OPTIONS,'prepare');out=I.new_output(args.output)
    budget=I.Budget(proof,session,out);budget.start();error=None
    try:
        C.need(budget.observe() is None,'FRESH_RESOURCE_BEFORE_BODY');fixtures=I.fixtures(out)
        original_account=I.read(plan['original_accounting_reference'],1<<20)
        I.authorized(proof,[original_account['raw_sacct_reference']])
        original_parent=I.F.accounting(plan['original_accounting_reference'],['4521124'])['4521124']
        inventory=I.read(C.INVENTORY,1<<20);engine,contract,protocol,pilot=T.engine(plan,I.read)
        by_case={}
        for r in plan['case_result_references']:
            C.need(budget.observe() is None,'STOP_BEFORE_NEXT_ORIGINAL_CASE')
            row=original(r,inventory,engine,protocol,out);case_id=row['case']['case_id'];C.need(case_id not in by_case,'SOURCE_CASE_DUPLICATE');by_case[case_id]=row
        C.need(set(by_case)=={c for pair in C.CASES.values() for c in pair},'EXACT_ALL_SIX_NOT_REPLACED')
        for name in ('tasks','targets','original_evidence'):(out/name).mkdir()
        tasks=[]
        for condition,pair in C.CASES.items():
            base,rotated=(by_case[c] for c in pair)
            for arm in C.ARMS:
                C.need(budget.observe() is None,'PREPARATION_STOP_NO_PARTIAL_READY')
                source=rotated if arm=='R1' else base;case=source['case'];qa_id='qa-%02d'%len(tasks)
                inputs=dict(source['inputs'])
                if arm.startswith('P'):
                    inputs={n:T.p90(b,n) if n in {'input.xyz','input.mop'} else b for n,b in inputs.items()}
                native,seed=T.bridge(case,inputs,source['task'],protocol,engine)
                folder=out/'targets'/qa_id;folder.mkdir()
                targets=[I.write(folder/name,body,out) for name,body in sorted(inputs.items())]
                evidence={k:source[k] for k in ('source_result_reference','original_actual_input_references','original_raw_reference',
                    'old_vectors','old_result','old_raw_call_current_SHA_verified','original_database_whole_SHA_claimed')}
                evidence_ref=I.json_new(out/'original_evidence'/(qa_id+'.json'),evidence,out)
                task={'schema':'PPRIME_CAUSAL15_QA_TASK_V1','qa_id':qa_id,'condition':condition,'arm':arm,'case':case,
                    'target_input_references':targets,'seed':seed,'original_record_id':case['row']['record_id'],
                    'original_task':source['task'],'native_coordinates_A':native['coords'].tolist(),'original_evidence_reference':evidence_ref,
                    'rotation_matrix':C.P90 if arm.startswith('P') else case['rotation_matrix'],
                    'source_result_reference':source['source_result_reference'],'source_plan_reference':session['plan_reference'],
                    'scientific_PASS':False,'full_or2000_release':'HOLD','production_once_ledger_opened':False}
                reference=I.json_new(out/'tasks'/(qa_id+'.json'),task,out)
                tasks.append({'qa_id':qa_id,'condition':condition,'arm':arm,'task_reference':reference,'target_input_references':targets,
                    'original_evidence_reference':evidence_ref,'source_result_reference':source['source_result_reference']})
        C.need(len(tasks)==15 and budget.observe() is None,'EXACT15_BYTE_BRIDGES_AND_FRESH_RESOURCE')
        I.json_new(out/'prepared.json',{'schema':'PPRIME_CAUSAL15_PREPARED_V1','status':'ACTUAL15_EXACT_INPUTS_PREPARED_ZERO_QM',
            'job_id':session['job_id'],'plan_reference':session['plan_reference'],'startup_proof_reference':session['proof_reference'],
            'fixtures_reference':fixtures,'source_cases_verified':6,'tasks':tasks,'actual_target_input_sets':15,
            'original_parent_actual_accounting':original_parent,
            'same_record_id_and_seed':True,'frozen_task_timeout_seconds':900,'new_QM_calls':0,'new_UFF_calls':0,
            'original15FAIL_preserved':True,'full_or2000_release':'HOLD','execute_authorized_by_this_receipt':False},out)
        return 0
    except BaseException as exc:
        error={'status':'PREPARE_INCOMPLETE_NO_EXECUTE_AUTHORITY','error':repr(exc),'new_QM_calls':0,'original15FAIL_preserved':True}
        I.json_new(out/'failure.json',error,out);raise
    finally:budget.close()


if __name__=='__main__':raise SystemExit(main())
