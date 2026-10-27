"""Actual Alpha CPU: two unchanged UNKNOWN rows, independent atoms-only evidence."""
import argparse,collections,hashlib,io,json,os,stat,sys,time,traceback,unittest,zipfile,zlib
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,projection as P
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def checked(ref):
    p=Q.literal(ref['path']);Q.need(not any(v.is_symlink() for v in (p,*p.parents)),'ORIGINAL_ALPHA_DATA_HAS_NO_SYMLINKS')
    s=p.lstat();Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_size==ref['bytes'],'EXACT_ALPHA_DATA_UID_AND_PRODUCER_SIZE')
    return p,frame(s)


def imports(plan):
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).suffix=='.py' and (name.startswith('secondary_') or name=='workflows' or name.startswith('workflows.')):
            Q.need(C.ROOT/'code' in Path(path).absolute().parents and Q.ref(path) in plan['source_references'],'EVERY_ACTUAL_TRANSITIVE_IMPORTED_SOURCE:'+name)


def fixtures(out,plan):
    from .test_v1 import Boundaries
    Chem,functions,parser,kernel=P.load(plan);imports(plan);Boundaries.Chem=Chem;Boundaries.functions=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_SYNTHETIC_METHODS')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'before_any_original_DATA_and_resource_monitor':True,'new_key_UFF_QM_calls':0}
    Q.write_new(out/'fixtures3.json',result)
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_DATA_AND_MONITOR')
    return result,Chem,functions,parser,kernel


def original_events(ref,kind,bindings,budget):
    p,before=checked(ref);events={};h=hashlib.sha256();n=0
    expected={v['physical_record_ordinal']:v for v in bindings}
    with p.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==before,'ORIGINAL_EVENT_SAME_OPENED_FD')
        while True:
            budget.check();raw=f.readline((16<<10)+1)
            if not raw:break
            Q.need(len(raw)<=16<<10 and raw.endswith(b'\n'),'COMPLETE_BOUNDED_ORIGINAL_EVENT_NOT_TRUNCATED');h.update(raw);n+=len(raw)
            v=json.loads(raw);Q.need(P.dump(v)==raw,'ORIGINAL_PRODUCER_EVENT_CANONICAL_BYTES_UNCHANGED')
            if kind=='source_events':Q.need(v['event']=='SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH','ORIGINAL_SOURCE_EVENT_TYPE');row=v['source']
            else:Q.need(v['event']=='ORIGINAL_ROW_IDENTITY_RESULT_COMPLETE','ORIGINAL_RESULT_EVENT_TYPE');row=v['worker_observation']['result']['source']
            ordinal=row['physical_record_ordinal'];Q.need(row['member_name']==C.MEMBER and ordinal in C.ORDINALS and ordinal not in events,'EXACT_TWO_PHYSICAL_EVENTS_NO_DUPLICATES')
            evidence=expected[ordinal];old=evidence['original_source_event' if kind=='source_events' else 'original_result_event']
            Q.need(old['bytes']==len(raw) and old['sha256']==hashlib.sha256(raw).hexdigest() and P.digest(row)==evidence['source_field_sha256'],
                'INDIVIDUAL_ORIGINAL_PRODUCER_EVENT_AND_SOURCE_FIELD_SHA')
            Q.need(row['row_width']==3 and row['original_Drug_ID']['bytes']==evidence['original_Drug_ID_bytes']
                and row['original_Drug']['bytes']==evidence['original_Drug_bytes'] and row['assay_Y_decoded'] is False,'ORIGINAL_LITERAL_ID_DRUG_AND_ROLE')
            events[ordinal]=v
        Q.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'CURRENT_COMPLETE_EVENT_SHA_STABLE_FSTAT')
    Q.need(set(events)==set(C.ORDINALS),'EXACT_TWO_EVENTS_NOT_COMPLETION_ORDER_SELECTION')
    return events,(p,before)


def bind_zip(ref,parent,source_events,parser_type,budget):
    p,before=checked(ref);h=hashlib.sha256();n=0;bound=set()
    old={v['member_name']:v for v in parent['ZIP']['members']};target=old[C.MEMBER]
    def emit(row):
        ordinal=row['physical_record_ordinal']
        if ordinal not in C.ORDINALS:return
        Q.need(ordinal not in bound and row==source_events[ordinal]['source'],'EXACT_OFFICIAL_ZIP_ID_DRUG_ALL_SOURCE_FIELDS');bound.add(ordinal)
    parser=parser_type(C.MEMBER,emit)
    with p.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==before,'SAME_ORIGINAL_ZIP_FD')
        while True:
            budget.check();block=f.read(1<<20)
            if not block:break
            n+=len(block);Q.need(n<=ref['bytes'],'COMPLETE_OFFICIAL_ZIP_SIZE_BOUND');h.update(block)
        Q.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==before,'CURRENT_ZIP_WHOLE_SHA_NOT_LOGIN_OBSERVATION')
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            infos=z.infolist();names=[v.filename for v in infos];regular=[v for v in infos if not v.is_dir()]
            Q.need(len(infos)==68 and len(set(names))==68 and len(regular)==45 and set(v.filename for v in regular)==set(old)
                and sum(v.file_size for v in regular)==5434789,'SAME_FROZEN68_INVENTORY_NO_EXTRA_MEMBER')
            for info in regular:
                Q.need(not info.flag_bits&1 and info.file_size==old[info.filename]['decoded_bytes'] and info.CRC==old[info.filename]['CRC32'],
                    'SAME_ORIGINAL_CENTRAL_DIRECTORY_MEMBER_BYTES_CRC')
            info=z.getinfo(C.MEMBER);sha=hashlib.sha256();crc=0;decoded=0
            with z.open(info) as member:
                while True:
                    budget.check();block=member.read(1<<16)
                    if not block:break
                    decoded+=len(block);Q.need(decoded<=187313,'SELECTED_CSV_DECLARED_FULL_MEMBER_BOUND');sha.update(block);crc=zlib.crc32(block,crc);parser.feed(block)
            summary=parser.finish();Q.need(decoded==info.file_size==target['decoded_bytes']==187313
                and sha.hexdigest()==target['decoded_sha256'] and crc&0xffffffff==info.CRC==target['CRC32'],'SELECTED_MEMBER_FULL_EOF_CRC_SHA')
            counts=summary['record_counts'];Q.need(counts['physical_data_records']==counts['field_count_matches_header']==1997
                and counts['field_count_below_header']==counts['field_count_above_header']==0 and bound==set(C.ORDINALS),'ALL1997_WIDTHS_AND_BOTH_ORIGINAL_ROWS')
        Q.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'ZIP_IMMUTABLE_THROUGH_LITERAL_ROW_BINDING')
    return {'current_whole_ZIP_SHA_and_fstat':True,'selected_member':C.MEMBER,'member_decoded_bytes':decoded,'member_decoded_SHA':sha.hexdigest(),
        'member_EOF_CRC_complete':True,'physical_record_counts':counts,'selected_rows_bound':2,
        'all44_previous_CRC_and81809_scope_inherited_from_unchanged_whole_ZIP_parent_not_recomputed_keys':True},(p,before)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan,proof=G.require_startup(args.plan,args.startup_proof);parent,values,by,relocation=C.inputs(plan)
    out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'NEW_EXACT2_EVIDENCE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    started=time.monotonic();budget=None;writer=None
    try:
        fx,Chem,functions,parser,kernel=fixtures(out,plan)
        import pyarrow as pa
        from rdkit import rdBase
        Q.need(sys.version.split()[0]=='3.11.14' and rdBase.rdkitVersion=='2025.09.5' and pa.__version__=='17.0.0','FROZEN_ALPHA_ENVIRONMENT')
        budget=Budget(plan,proof,out);J.write_json(out/'kernel_proof.json',kernel,budget)
        sources,sframe=original_events(plan['data_references'][0],'source_events',parent['exact2_bindings'],budget)
        results,rframe=original_events(plan['data_references'][1],'result_events',parent['exact2_bindings'],budget)
        archive,zframe=bind_zip(plan['data_references'][2],parent,sources,parser,budget)
        transfer=J.write_json(out/'transfer_verification.json',{'schema':'TDC_EXACT2_ALPHA_ACTUAL_CPU_BODY_VERIFICATION_V1',
            'status':'ALL3_CURRENT_WHOLE_SHA_STABLE_FSTAT_AND_SELECTED_ZIP_ROWS_BOUND',
            'endpoint':Q.ENDPOINT,'uid':1264,'job_id':str(proof['job_id']),'node':plan['node'],
            'verified_body_references':plan['data_references'],'actual_body_frames':[{'path':str(p),'frame':list(fr)} for p,fr in (sframe,rframe,zframe)],
            'all3_fixtures_preceded_any_body_open_or_hash':True,'first_target_SHA_verification_in_this_CPU_allocation':True,
            'new_original_string_parses_started':False,'origin_Main_metadata_preserved_UID':1278,
            'main_relocation_reference':plan['main_relocation_reference'],'ZIP_binding':archive},budget)
        writer=J.Writer(out,budget);observations=[]
        for ordinal in C.ORDINALS:
            budget.check();source=sources[ordinal]['source'];result=results[ordinal]['worker_observation']['result']
            Q.need(source==result['source'],'ORIGINAL_SOURCE_AND_RESULT_LITERAL_EQUALITY')
            # The complete original pair becomes durable before the two new parser calls.
            row={'source_id':'tdc_admet_group_zip:'+C.MEMBER,'source_row_ordinal':ordinal,'role':source['original_split'],
                'source_offset':None,'source_record_bytes':len(P.dump(source)),'source_record_sha256':P.digest(source),
                'original_native_ID':source['original_Drug_ID']['text'],'original_source':source,'original_result':result,
                'source_record_byte_basis':'CANONICAL_ORIGINAL_IDENTITY_FIELDS_NOT_ORIGINAL_CSV_RECORD_BYTES'}
            writer.dispatch(row);budget.check();observed=P.observation(source,result,Chem,functions);Q.need(observed['source']==row,'DURABLE_ORIGINAL_PAIR_EQUALS_OBSERVATION_SOURCE')
            value={'observation':observed,'worker_pid':os.getpid(),'parser_processes':1,'allocated_cpus':16};writer.complete(value)
            observations.append({'physical_record_ordinal':ordinal,'original_identity_state':'ORIGINAL_SMILES_UNRESOLVED',
                'composition_evidence_state':observed['atoms_only_evidence']['state'],'composition':observed['atoms_only_evidence']['composition'],
                'MolFromSmiles_invoked':observed['atoms_only_evidence']['MolFromSmiles_invoked'],
                'graph_charge_stereo_and_original_cause':'UNKNOWN','full_keys':[],'automatic_policy_acceptance':False})
        outputs=writer.close();writer=None
        for path,before in (sframe,rframe,zframe):Q.need(frame(path.lstat())==before,'ALL_ORIGINAL_BODY_FRAMES_STILL_IDENTICAL')
        import pyarrow.parquet as pq
        Q.need(pq.ParquetFile(outputs['Parquet']['path']).metadata.num_rows==2,'TWO_DURABLE_RESULTS_AND_PARQUET_ROWS')
        budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_NO_CLOSURE_CLAIM')
        report={'schema':'TDC_EXACT2_COMPOSITION_EVIDENCE_RECEIPT_V1','status':'EXACT2_ORIGINAL_UNKNOWN_ATOMS_ONLY_OBSERVATIONS_COMPLETE_NOT_POLICY_ACCEPTED',
            'job_id':str(proof['job_id']),'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'allocated_cpus':16,'parser_processes_observed':1,
            'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),'scope_parameters':C.PARAMETERS,
            'main_relocation_reference':plan['main_relocation_reference'],'original_Main_jobs':['4521689','4521757','4521907'],'original_Main_uid':1278,
            'original_Main_endpoint':C.MAIN_ENDPOINT,'fixtures':fx,'ZIP_binding':archive,'observations':observations,'outputs':outputs,
            'kernel_proof_reference':J.pin(out/'kernel_proof.json'),'actual_CPU_transfer_verification_reference':transfer,
            'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,
            'original_two_UNKNOWN_states_and_error_lists_unchanged':True,'original_N4_warnings_row_bound':False,'original_failure_causes':'UNKNOWN',
            'original_string_observation_attempts':2,'new_original_string_MolFromSmiles_calls':sum(v['MolFromSmiles_invoked'] for v in observations),
            'new_full_key_UFF_QM_network_calls':0,'automatic_fallback_policy_acceptance':False,
            'global_decontamination_pool_training_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE','actual_parent_terminal_cost_pending_Root':True}
        J.write_json(out/'receipt.json',report,budget);print(json.dumps({'status':report['status'],'receipt_reference':J.pin(out/'receipt.json')}));return 0
    except BaseException as exc:
        if writer:writer.close();writer=None
        Q.write_new(out/'failure.json',{'schema':'TDC_EXACT2_ATOMS_ONLY_PARTIAL_FAILURE_V1','status':'PREFIX_RETAINED_NO_CLOSURE_OR_POLICY_ACCEPTANCE',
            'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),'runtime':budget.receipt() if budget else None,
            'original_UNKNOWN_states_changed':False,'global_release':False,'actual_terminal_cost_pending_Root':True})
        raise
    finally:
        if writer:writer.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
