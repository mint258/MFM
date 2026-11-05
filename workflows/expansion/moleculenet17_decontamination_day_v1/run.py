"""One real generic16CPU/day: complete17 projection plus bounded27 official GET."""
import argparse,collections,hashlib,io,json,os,sys,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from . import contract as C,projection as P,runtime as I,acquisition as A
OPEN_WRITERS=[]

def fixtures(out):
    from . import test_v1,atoms
    test_v1.WORKSPACE=out;output=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT3_SOURCE_BOUNDARIES_BEFORE_DATA');r=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':output.getvalue(),
      'all_before_any_original_DATA_or_network':True,'atoms_source_inverse':atoms.proof()}
    C.Q.write_new(out/'source3.json',value);C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAIL_NO_DATA');return value

def positive_close(writer):
    ref=writer.close();return ref if ref['bytes'] else None

def execute(plan,proof,context,authority,out,budget):
    from rdkit import Chem,rdBase
    C.need(rdBase.rdkitVersion=='2025.09.5','EXACT_ORIGINAL_RDKIT_NO_VERSION_CHANGE')
    identity=I.Lines(out/'identities.strict5.jsonl',budget);audit=I.Lines(out/'projection_evidence.DATA.jsonl',budget);holds=I.Lines(out/'unresolved_original_sources.DATA.jsonl',budget)
    OPEN_WRITERS.extend((identity,audit,holds))
    native_entities=set();native_records=set();native_kinds=collections.Counter();seen_sources=set();local=collections.Counter();csv=collections.Counter();index=collections.Counter();quantum={};outputs=collections.Counter();blank=collections.Counter();unresolved=0;native=0
    def emit(values,evidence,section,source):
        nonlocal unresolved
        unknown=evidence.get('unresolved',0);C.need(type(unknown)is int and unknown>=0,'EXACT_UNKNOWN_COUNT_NOT_QUALITY_EXCLUSION');unresolved+=unknown
        for row in values:
            P.identity_keys(row);key=row['source_id'];C.need(key not in seen_sources,'NO_IDENTITY_RECORD_DEDUP_OR_DUPLICATE');seen_sources.add(key)
            identity.append(row);outputs[row['subdataset']]+=1
        item={'section':section,'original_source_locator':source,'evidence':evidence,'strict_rows_emitted':len(values),'unknown_is_chemical_exclusion':False}
        audit.append(item)
        if unknown:holds.append(item)
    for unit in context['local6_original_units']:
        n=0
        for ordinal,row in I.parquet(unit['file'],plan,budget):
            n+=1;values,evidence=P.local_row(row,unit['file'],ordinal,Chem)
            if evidence is not None:local[row['dataset']]+=1;emit(values,evidence,'local6',{'reference':unit['file'],'physical_row':ordinal})
        C.need(n==sum(unit['datasets'].values()),'EVERY_ACTUAL_LOCAL_UNIT_ROW_READ_NO_HIDDEN_FILTER')
    ref=authority['selected']['csv6'];last={sid:0 for sid in C.CSV}
    for ordinal,row in I.parquet(ref,plan,budget):
        sid=row['source_id'];C.need(sid in last and row['source_row_ordinal']==last[sid]+1,'ALL_CSV6_ORIGINAL_ORDINALS_ONCE');last[sid]+=1;csv[sid]+=1
        values,evidence=P.csv_row(row,ref,Chem);blank[sid]+=int(evidence['nonmolecular']);emit(values,evidence,'csv6',{'reference':ref,'physical_row':ordinal})
    ref=authority['selected']['native_unions']
    for value,segment in I.json_rows(ref,budget):
        values,evidence=P.native_union(value,ref,segment['line_ordinal']);key=P.locator(*value['entity_identity'])
        C.need(key not in native_entities,'NO_DUPLICATE_OR_ALIAS_NATIVE_ENTITY');native_entities.add(key);native+=evidence['native_members']
        for member in value['members']:
            C.need(member['record_id'] not in native_records,'EVERY_NATIVE_PHYSICAL_RECORD_IN_EXACTLY_ONE_ORIGINAL_ENTITY');native_records.add(member['record_id'])
        native_kinds.update(m['kind'] for m in value['members']);emit(values,evidence,'native_union',segment)
    C.need(len(native_entities)==39438 and len(native_records)==57480 and dict(native_kinds)=={'SDF':39633,'MOL2':17847},'ACTUAL39438_ENTITIES57480_CONTEXTS39633_SDF_NOT_SAME_COUNT_AXIS')
    missing=[]
    for value,segment in I.json_rows(authority['selected']['native_relations'],budget):
        sid=value['source_id'];C.need(sid in C.IDS and value['original_index_ordinal']==index[sid] and value['original_index_row_not_dropped'] is True
          and value['same_ID_implies_same_graph'] is False,'EVERY44510_ORIGINAL_INDEX_ORDINAL');index[sid]+=1
        matching=value['matching_existing_native_entities'];C.need(type(matching)is list and all(P.locator(*e) in native_entities for e in matching),'INDEX_REFERENCES_ACTUAL_NATIVE_ENTITIES')
        C.need(value['no_native_context_in_all_components']==(matching==[]),'EXACT_RECORDED_CONTEXT_GAP')
        if not matching:missing.append((sid,value['original_index_ordinal']))
        audit.append({'section':'native_index','source_locator':segment,'original_index_relation':value,'identity_representative_chosen':False})
    C.need(len(missing)==27 and all(sid=='pdbbind_general' for sid,_ in missing),'EXACT27_CONTEXT_GAPS_NOT12119_GRAPH_UNKNOWNS')
    selected=authority['selected']
    for name,key,n in (('QM7','qm7',7165),('QM9','qm9',133885),('QM7b','qm7b',7211)):
        count=0
        for value,segment in I.json_rows(selected[key],budget):
            P.identity_keys({k:value[k] for k in P.ALLOWED_IDENTITY_FIELDS if k in value})
            C.need(value['role']=='all' and type(value['source_id'])is str,'EXACT_ALL_ORIGINAL_QUANTUM_SOURCE_ROLES')
            row=P.strict(name,P.locator('MoleculeNet',name,selected[key]['sha256'],value['source_id']),value['inchikeys'],value['non_h_composition'])
            emit([row],{'unresolved':0,'graph_or_MAT_mapping_newly_accepted':False},name,segment);count+=1
        C.need(count==n,'ALL_ORIGINAL_QUANTUM_POPULATION_NOT_SUBSET');quantum[name]=count
    official=A.Official(authority['remote'],out/'official27',budget);gap_seen=set();gap_complete=0
    try:
        with I.held(selected['pdb27_raw'],[C.Q.ROOT/'artifacts'],plan['data_references']) as (raw,_):
            for event,segment in I.json_rows(selected['pdb27'],budget):
                key=(event['source_id'],event['original_index_ordinal']);C.need(key in missing and key not in gap_seen,'EXACT27_EVIDENCE_JOIN_NO_EXTRA_SOURCE');gap_seen.add(key)
                part=event['opaque_full_line_output_segment'];C.need(part['path']==authority['pdb27_raw_origin']['path'] and type(part['offset'])is int and part['offset']>=0
                  and type(part['bytes'])is int and 0<part['bytes']<=1<<20,'ORIGINAL_OPAQUE_LINE_SEGMENT_BOUNDARY')
                raw.seek(part['offset']);body=raw.read(part['bytes']);C.need(len(body)==part['bytes'] and hashlib.sha256(body).hexdigest()==part['sha256']
                  and len(body)==event['original_details']['line_bytes'] and hashlib.sha256(body).hexdigest()==event['original_details']['line_sha256'],'ORIGINAL_RAW_LINE_FULL_LENGTH_SHA')
                try:
                    row,evidence=A.resolve(event,body,official,Chem);gap_complete+=1;emit([row],dict(evidence,unresolved=0),'official27',segment)
                except Exception as exc:
                    if budget.stop_new is not None:raise
                    emit([],{'unresolved':1,'original_event':event,'status':'OFFICIAL_ORIGINAL_LIGAND_CORRESPONDENCE_HOLD',
                      'error_type':type(exc).__name__,'error':str(exc),'no_neighbor_or_whole_protein_composition':True},'official27',segment)
    finally:remote=official.finish()
    C.need(gap_seen==set(missing),'ALL27_MISSING_ORIGINALS_RETAINED')
    conservation=P.mass(local,csv,native,index,quantum);ids=identity.close();evidence=audit.close();unknown=positive_close(holds)
    readback=I.readback(ids,['all'],sorted(outputs),lambda:budget.check())
    C.need(readback['rows']==sum(outputs.values()) and readback['subdatasets']==dict(outputs),'ALL_OUTPUT_ROWS_ORIGINAL_CONSUMER_READBACK')
    coverage={'schema':'expansion_all_source_identity_coverage_v1','dataset':'moleculenet','all_splits':True,'covered_roles':['all'],
      'covered_subdatasets':sorted(outputs),'expected_identity_records':ids['rows'],'unresolved_without_identity_or_composition':unresolved,
      'raw_artifacts':C.unique([*plan['data_references'],*remote['actual_response_references']]),'identities':ids,'identity_rows_by_subdataset':dict(outputs),'physical_conservation':conservation,
      'actual_empty_nonmolecular_records_by_CSV_source':dict(blank),'official27_successful_exact_ligand_composition_rows':gap_complete,
      'projection_evidence_reference':evidence,'unresolved_original_source_evidence_reference':unknown,'remote_acquisition':remote,'readback':readback,
      'all_source_bodies_whole_SHA_current_FD_and_EOF_verified':True,'all_native_variants_and_unknowns_retained':True,
      'graph_UNKNOWN_is_chemical_exclusion':False,'original17_graphs_or_native_splits_accepted':False,'global_pool_release':False}
    complete=unresolved==0 and set(outputs)==set(C.NAMES);coverage['strict17_complete_candidate']=complete
    cov=I.write(out/'coverage.json',coverage,budget)
    return {'complete':complete,'coverage_reference':cov,'identities_reference':ids,'unresolved':unresolved,'all17_subdatasets':sorted(outputs),
      'identity_rows':ids['rows'],'blank_physical_records':sum(blank.values()),'official27_completed':gap_complete,
      'conservation':conservation,'readback':readback,'projection_evidence_reference':evidence,'unresolved_reference':unknown,'remote':remote}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=C.meta(C.Q.pin(a.plan));context=C.meta(plan['input_context_reference']);authority=C.inputs(context)
    argv=[C.Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,
      expected_execution_argv=argv,expected_source=C.HERE/'run.py',required_references=[C.Q.pin(a.plan),plan['input_context_reference'],*plan['source_references']])
    req=proof['request'];C.need(plan['schema']=='MOLECULENET17_DECONTAMINATION_DAY_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
      and req['cpus']==16 and req['kind']=='analysis' and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and req['wall_seconds']==plan['wall_seconds']==C.WALL and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==plan['output_cap_bytes']==C.CAP
      and req['data_references']==plan['data_references']==authority['data_references'] and not req.get('deferred_authority_references'),
      'ACTUAL_GENERIC16_DAY_EXACT_SCOPE_DATA_CAP')
    review=C.meta(req['scope']['review']);C.need(review['all17_original_identity_and_exact27_official_acquisition_authorized'] is True
      and review['unknown_or_ambiguous_is_HOLD'] is True and review['global_pool_release_authorized'] is False,'REAL_ROOT_EXACT_SCOPE_NOT_SELF_RELEASE')
    for ref in C.sources():C.need(ref in req['source_references'],'FULL_CURRENT_SOURCE_CLOSURE')
    out=Path(plan['output_directory']);C.need(C.Q.ROOT/'artifacts/expansion/moleculenet17_decontamination_day_v1' in out.parents
      and not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_OWN_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    gate=fixtures(out);budget=I.Budget(plan,proof,out)
    try:
        result=execute(plan,proof,context,authority,out,budget);budget.check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENTS_STABLE_AFTER_ALL_DATA')
        C.Q.write_new(out/'receipt.json',{'schema':'MOLECULENET17_DECONTAMINATION_DAY_RECEIPT_V1',
          'status':'STRICT17_COMPLETE_PENDING_ROOT_ACTUAL_C0_ADOPTION' if result['complete'] else 'ALL_DECLARED_CONTEXTS_READBACK_COMPLETE_UNRESOLVED_ORIGINALS_HOLD',
          'job_id':str(proof['job_id']),'uid':1278,'endpoint':'202.38.247.57:22','node':req['node'],'plan_reference':C.Q.pin(a.plan),
          'startup_proof_reference':C.Q.pin(a.startup_proof),'input_context_reference':plan['input_context_reference'],'fixtures':gate,'result':result,
          'old_DATA_or_once_modified':False,'existing39633_graph_attempts_repeated':False,'new_QM_UFF_calls':0,'global_pool_training_release':False,
          'quota_observation_guard':{'source_reference':I.QuotaGuard.source_reference(),
            'event_references':budget.quota_guard_event_references,'original_Client_and_0_to120_expiry_validator_changed':False,
            'maximum_rereads_per_eligible_observation':1,'maximum_near_clock_wait_seconds':1.1,'provider_auto_renewed':False}})
        return 0
    except BaseException as exc:
        I.write(out/'failure.DATA.json',{'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),
          'all_prefix_files_and_costs_retained':True,'automatic_retry':False},budget);raise
    finally:
        for writer in OPEN_WRITERS:writer.close()
        budget.check(dispatch=False,force=True)
if __name__=='__main__':raise SystemExit(main())
