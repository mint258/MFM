"""Actual node19 exact32 replay; no production cache import or ledger claim."""
import argparse,collections,concurrent.futures as cf,copy,importlib.metadata,multiprocessing as mp,os,pathlib,platform,struct,sys,time,unittest
from . import contract as C,resources as R,io as I,compute as K,worker as W
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as PC,inheritance as H,prepare32 as ORIGINAL_PREPARE
from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1 import contract as HC,derive as HD


def exact(value):
    """IEEE754 equality includes signed zero; no tolerance or numeric casting."""
    if type(value) is float:return ('float64',struct.pack('<d',value).hex())
    if isinstance(value,dict):return {k:exact(v) for k,v in value.items()}
    if isinstance(value,list):return [exact(v) for v in value]
    return (type(value).__name__,value)


def versions():
    out={}
    for name in ('numpy','rdkit','torch','lmdb','scipy'):
        try:out[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:out[name]='DISTRIBUTION_METADATA_UNAVAILABLE'
    return out


def fixtures(out):
    from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.test_cache import CacheBoundaries
    from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1.test_derive import DerivedBoundaries
    from workflows.data_v1_final.conformers.pm7_population_cache_v1.test_boundaries import BatchBoundaries
    from .test_v1 import AdapterBoundaries
    inheritance=I.json_new(out/'source_inheritance.json',{'original':H.proof(),'new_explicit_context':K.inverse_proof()},out)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(t) for t in (CacheBoundaries,DerivedBoundaries,BatchBoundaries,AdapterBoundaries))
    result=unittest.TestResult();suite.run(result)
    ok=result.testsRun==21 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    report={'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'expected_tests':21,'original_methods':17,'adapter_methods':4,
        'failures':[{'test':t.id(),'traceback':e} for t,e in result.failures],'errors':[{'test':t.id(),'traceback':e} for t,e in result.errors],
        'skips':[str(v) for v in result.skipped],'expected_failures':[str(v) for v in result.expectedFailures],
        'unexpected_successes':[str(v) for v in result.unexpectedSuccesses],'source_inverse_reference':inheritance,
        'executed_before_scientific_DATA':True,'old17_unmodified':True,'new_UFF_calls':0,'new_QM_calls':0}
    r=I.json_new(out/'fixtures21.json',report,out);C.need(ok,'ORIGINAL17_AND_NEW4_BEFORE_DATA');return r


def canonical(control,binding,proof,out,budget):
    reference=control['base']['formal_source'];review=I.read(control['base']['mapping_review']);old=I.read(review['formal_source_receipt'])
    prior=I.read(review['prior_cpu_source_validation']);I.authorized(proof,[review['formal_source_receipt'],review['prior_cpu_source_validation'],reference])
    rows=[r for r in old['outputs'] if r['name']=='formal_population'];matches=[r for r in prior['inputs'] if r['reference']==reference]
    C.need(len(rows)==len(matches)==1 and rows[0]['reference']==reference==binding['canonical_reference']
        and old['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and prior['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED'
        and prior['runtime']['job_id']=='4521417' and matches[0]['actual']==reference and matches[0]['status']=='ACTUAL_FULL_SHA_MATCH'
        and rows[0]['after']==review['historical_frame'],'ORIGINAL_CANONICAL_CHAIN_RETAINED_NOT_NODE13_FACTS_RELABELED')
    path=pathlib.Path(reference['path']);before=path.lstat();frame=R.stat_frame(before)
    C.need(not path.is_symlink() and frame==binding['canonical_expected_frame']
        and all(frame[k]==rows[0]['after'][k] for k in ('inode','size','mtime_ns','uid'))
        and all(matches[0][k]==frame[k] for k in ('inode','mtime_ns','uid')),'ACTUAL19_FRAME_AND_ALL_CROSS_MOUNT_STABLE_FIELDS')
    C.need(budget.observe() is None,'FRESH_QUOTA_BEFORE_CANONICAL_SHA');I.P.source_check(reference)
    after=path.lstat();C.need(R.stat_frame(after)==frame,'ALL5_CURRENT_FIELDS_STABLE_ACROSS_CPU_WHOLE_SHA')
    return I.json_new(out/'actual_canonical19.json',{'reference':reference,'historical_frame':rows[0]['after'],'prior_cpu_job_id':'4521417',
        'actual_node':C.NODE,'current_before':frame,'current_after':R.stat_frame(after),'actual_CPU_whole_SHA_verified':True,
        'resource_binding_reference':C.M.pin(binding['_path'])},out)


def compare(task,packet,old,attachment,golden):
    C.need(packet['status']=='PM7_GEOMETRY_CACHE_COMPLETE_HOF_COMPLETE' and old['status']=='PM7_GEOMETRY_CACHE_COMPLETE_HOF_PENDING'
        and attachment['status']=='CANONICAL_HOF_AND_DERIVED_ORDERS_COMPLETE','ALL_REAL_GEOMETRY_AND_HOF_COMPLETE_REQUIRED')
    names=('schema','molecule_id','cache_key','source_population_authority','PM7_source_count','record_ids','source_records','software_bound',
        'atomic_numbers','graph_sha256','atom_order_sha256','graph_anchor_record_id','graph_anchor_policy','stereo_authority_claimed',
        'heavy_atoms','rotatable_bonds','rings','pm7_count','pm7_unique','pm7_duplicate_conformer_fraction',
        'pair_rmsd_A','pair_rmsd_record_ids','actual_original_RMSD_calls','unique_representatives')
    for name in names:C.need(exact(packet[name])==exact(old[name]),'ORIGINAL_GEOMETRY_OR_DIRECTIONAL_RMSD_BITS_CHANGED:'+name)
    geometry=lambda p:[{k:r[k] for k in ('conformer_id','coordinates','geometry_sha256')} for r in p['pm7']]
    C.need(exact(geometry(packet))==exact(geometry(old)) and not packet['source_errors'],'EXACT_FLOAT64_COORDINATES_IDS_AND_GEOMETRY_SHA')
    C.need(attachment['geometry_packet_reference']==task['QA_baseline_geometry_reference']
        and attachment['original_cache_key']==packet['cache_key'] and attachment['molecule_id']==packet['molecule_id']
        and attachment['inherited_directional_matrix_sha256']==HC.digest([packet['pair_rmsd_record_ids'],packet['pair_rmsd_A']])
        and attachment['inherited_pair_rmsd_record_ids']==packet['pair_rmsd_record_ids'],'BOTH_REAL_BASELINES_BOUND_TO_THE_SAME_NATIVE_MATRIX')
    for name in ('hof_by_record','hof_valid_count','hof_range_complete','hof_range_kcal_mol','orders'):
        C.need(exact(packet[name])==exact(attachment[name]),'CANONICAL_HOF_BITS_STATE_OR_ORDERS_CHANGED:'+name)
    hashes={r['conformer_id']:r['geometry_sha256'] for r in packet['pm7']}
    C.need(hashes==attachment['geometry_hashes'] and packet['unique_representatives']==attachment['inherited_unique_representatives'],
        'ORIGINAL_HOF_ATTACHMENT_GEOMETRY_AND_UNIQUE_MATCH')
    for row in packet['pm7']:
        C.need(exact(row['energy'])==exact(attachment['hof_by_record'][row['conformer_id']]['value_kcal_mol']),'PER_NATIVE_RECORD_CANONICAL_HOF_BITS')
    derived={**packet,'geometry_hashes':hashes,'inherited_unique_representatives':packet['unique_representatives']}
    gold=HD.golden_compare(derived,golden)
    C.need(gold['status'] in ('NOT_A_GOLDEN_MEMBER','GOLDEN_CANONICAL_HOF_BITS_STATE_AND_ORDERS_EQUAL'),'ORIGINAL_GOLDEN16_COMPARISON_FAILED')
    return {'status':'EXACT_GEOMETRY_RMSD_HOF_BITS_STATE_ORDERS_EQUAL','golden_comparison':gold,'numeric_tolerance_added':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in C.OPTIONS:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    a=parser.parse_args();plan=C.M.load(a.plan);control=C.controls();binding,_,identity,resource_refs=R.binding(plan['resource_binding_reference'])
    argv=[R.Q.PY,'-B','-m',__package__+'.run','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    sources=C.unique([*C.request_sources(control),*resource_refs,*plan['source_references']])
    proof=R.ADMISSION.require_startup(a.root_preflight,expected_scope_key=C.key('compat32'),expected_scope_parameters=C.scope('compat32'),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[C.M.pin(a.plan),*sources])
    req=proof['request'];C.need(plan['schema']==C.SCHEMA and plan['mode']=='compat32' and plan['status']=='APPROVED_QA_ONLY'
        and plan['reviewer']=='root' and req['node']==C.NODE and req['cpus']==16 and req['pilot'] is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.CAP and 1200<=req['wall_seconds']<=7200
        and req['data_references']==control['data_references'],'EXACT_NEW_CPU19_INDEPENDENT_QA_ONLY_REQUEST')
    C.need(time.time()+req['wall_seconds']+300<=identity['expires_unix_seconds'],'ROOT_MUST_REVIEW_SUFFICIENT_EXISTING_PUBLISHER_LEASE_NO_RENEWAL')
    I.authorized(proof,control['data_references']);out=I.create(a.output)
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    session={'proof_reference':C.M.pin(a.root_preflight),'main_source':C.M.pin(__file__),'execution_argv':argv,'parent_pid':os.getpid(),
        'parent_start_ticks':R.R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),
        'resource_binding_reference':plan['resource_binding_reference'],'output_root':str(out),'source_references':sources}
    budget=R.Budget(proof,session,out);records=[];errors=[];queue=[];next_index=0;fixture_ref=canonical_ref=hof_ref=None;started=time.monotonic()
    try:
        C.need(budget.observe() is None,'FRESH_SHARED_QUOTA200GB_BEFORE_ANY_BODY');budget.start_monitor();fixture_ref=fixtures(out)
        binding=dict(binding,_path=plan['resource_binding_reference']['path']);canonical_ref=canonical(control,binding,proof,out,budget)
        prepared=control['prepared'];authority=I.read(prepared['source_authority_reference']);tasks={};refs={}
        geometry={r['molecule_id']:r for r in control['geometry']['packets']};hof={r['molecule_id']:r for r in control['hof']['packets']}
        for row in prepared['tasks']:
            C.need(budget.observe() is None,'RESOURCE_STOP_BEFORE_NEXT_QA_TASK_DATA')
            original=I.read(row['task_reference']);mid=original['meta']['molecule_id']
            C.need(original['schema']=='PM7_INDEPENDENT_CACHE32_TASK_V1' and mid==row['molecule_id'] and mid not in tasks
                and original['cache_key']==row['cache_key'] and original['source_population_authority']==prepared['source_authority_reference']
                and original['meta']['records']==len(original['records']) and original['software_bound']==row['software_bound']
                and original['software_bound']==PC.software_bound(original['meta']['records'],original['meta']['maximum_total_atoms']),
                'ORIGINAL_FROZEN32_WHOLE_MOLECULE_TASKS_NO_REPLACEMENT')
            tasks[mid]=copy.deepcopy(original);refs[mid]=row['task_reference']
        C.need(len(tasks)==32 and set(tasks)==set(authority['selected_molecule_ids'])==set(geometry)==set(hof)
            and sum(len(t['records']) for t in tasks.values())==203 and sum(t['golden_packet_reference'] is not None for t in tasks.values())==16,
            'EXACT_ORIGINAL32_203_GOLDEN16')
        all_records=[r for t in tasks.values() for r in t['records']]
        C.need(budget.observe() is None,'RESOURCE_STOP_BEFORE_CANONICAL_HOF_DATA')
        values,observations=ORIGINAL_PREPARE.canonical_hof(dict(control['base'],hof_mode='CANONICAL_VERIFIED',
            hof_authority_review=control['hof_plan']['hof_authority_review']),all_records,proof,out,budget)
        hof_ref=I.json_new(out/'actual_canonical_hof_observations.json',{'records':203,'observations':observations,'reader':'ORIGINAL_UNMODIFIED_CANONICAL_HOF'},out)
        qa_refs={}
        for mid,task in tasks.items():
            task.update(hof_mode='CANONICAL_VERIFIED',hof={r['record_id']:values[r['record_id']] for r in task['records']},
                QA_original_task_reference=refs[mid],QA_baseline_geometry_reference=geometry[mid]['packet_reference'],QA_controls_only=True)
            qa_refs[mid]=I.json_new(out/'tasks'/(task['cache_key']+'.json'),task,out)
        active={};queue=sorted(tasks)
        try:
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=W.initialize,initargs=(session,)) as pool:
                while active or next_index<len(queue):
                    budget.observe(list(pool._processes.values()))
                    while budget.stop is None and next_index<len(queue) and len(active)<16:
                        mid=queue[next_index];task=tasks[mid];bound=task['software_bound']['packet_reserve_bytes']
                        reserve=bound+sum(tasks[m]['software_bound']['packet_reserve_bytes'] for m in active.values())
                        if R.R.disk_bytes(out)+2*reserve+C.ADMIN>C.CAP:budget.stop='QA2GIB_RESERVATION_STOP_NEW_DISPATCH';break
                        if budget.observe(list(pool._processes.values())) is not None:break
                        I.json_new(out/'dispatch'/(task['cache_key']+'.json'),{'molecule_id':mid,'task_reference':qa_refs[mid],
                            'original_task_reference':refs[mid],'state':'DURABLE_QA_SUBMIT_INTENT_NOT_WORKER_START','QA_only':True},out)
                        next_index+=1
                        future=pool.submit(W.one,task,qa_refs[mid]);active[future]=mid
                    if not active:break
                    done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        mid=active.pop(future);record=None
                        try:
                            record=future.result();packet=I.read_packet(record['packet_reference']);start=I.read(record['worker_start_reference']);finish=I.read(record['finished_reference'])
                            runtime=record['runtime'];C.need(runtime['job_id']==str(proof['job_id']) and runtime['uid']==1278 and runtime['node']==C.NODE
                                and runtime['boot_id']==proof['boot_id'] and runtime['parent_pid']==os.getpid() and runtime==packet['runtime']==start['runtime']==finish['runtime']
                                and packet['molecule_id']==mid and packet['task_reference']==start['task_reference']==finish['task_reference']==qa_refs[mid]
                                and packet['startup_proof_reference']==start['startup_proof_reference']==session['proof_reference']
                                and start['cache_key']==finish['cache_key']==tasks[mid]['cache_key']
                                and finish['packet_reference']==record['packet_reference'] and finish['worker_start_reference']==record['worker_start_reference'],
                                'ACTUAL19_WORKER_TASK_START_FINISH_PACKET_IDENTITY')
                            old=I.read_packet(geometry[mid]['packet_reference']);attachment=I.read(hof[mid]['packet_reference'])
                            golden=I.read_packet(tasks[mid]['golden_packet_reference']) if tasks[mid]['golden_packet_reference'] else None
                            record['comparison']=compare(tasks[mid],packet,old,attachment,golden);records.append(record)
                        except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc)[:16000],'durable_record':record,
                            'expected_packet_path':str(out/'molecules'/(tasks[mid]['cache_key']+'.json.gz')),'evidence_preserved':True})
        except Exception as exc:
            errors.append({'phase':'pool_or_submit','error':repr(exc)[:16000],'all_durable_evidence_preserved':True});budget.stop=budget.stop or 'QA_POOL_UNKNOWN_NO_RETRY'
    except Exception as exc:
        errors.append({'phase':'admitted_QA','error':repr(exc)[:16000],'all_durable_evidence_preserved':True})
    finally:
        budget.close_monitor();budget.observe();resource_ref=I.json_new(out/'resource_observations.json',budget.report(),out,final=True)
    closed=len(records)==32 and next_index==32 and not(errors or budget.stop)
    golden_count=sum(r['comparison']['golden_comparison']['status']=='GOLDEN_CANONICAL_HOF_BITS_STATE_AND_ORDERS_EQUAL' for r in records)
    closed=closed and golden_count==16
    receipt={'schema':'PM7_MULTINODE_COMPAT32_RECEIPT_V1','status':'ACTUAL_NODE19_EXACT32_COMPATIBLE_REQUIRES_ROOT_REVIEW' if closed else 'QA_PENDING_UNKNOWN_OR_MISMATCH_NO_FULL_RELEASE',
        'endpoint':C.ENDPOINT,'uid':os.getuid(),'node':C.NODE,'job_id':str(proof['job_id']),'boot_id':proof['boot_id'],
        'actual_python':platform.python_version(),'actual_package_versions':versions(),
        'plan_reference':C.M.pin(a.plan),'startup_proof_reference':session['proof_reference'],'resource_binding_reference':plan['resource_binding_reference'],
        'original_control_references':control['references'],'actual_fixtures_reference':fixture_ref,'actual_canonical_reference':canonical_ref,
        'actual_hof_observations_reference':hof_ref,'resource_observations_reference':resource_ref,'configured_workers':16,
        'completed_exact_comparisons':len(records),'expected_molecules':32,'expected_records':203,'golden16_exact_count':golden_count,
        'packets':records,'errors':errors,'unstarted_molecule_ids':queue[next_index:],
        'dispatched_without_validated_return_ids':sorted(set(queue[:next_index])-{r['molecule_id'] for r in records}),
        'elapsed_seconds':time.monotonic()-started,'budget':budget.report(),'actual_parent_terminal_accounting':None,
        'cost_append_required':True,'old_accounts_preserved_in_plan':True,'QA_only':True,'production_ledger_opened':False,
        'new_population_rows':0,'new_UFF_calls':0,'new_QM_calls':0,'numeric_tolerance_added':False,'common':False,'full_cache_release':False}
    I.json_new(out/'receipt.json',receipt,out,final=True);print({'status':receipt['status'],'exact32':len(records),'golden16':golden_count})
    return 0 if closed else 3


if __name__=='__main__':raise SystemExit(main())
