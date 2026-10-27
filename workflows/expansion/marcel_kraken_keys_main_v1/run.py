"""Complete native relationships, bounded chosen source keys, no pool release."""
import argparse,collections,concurrent.futures as cf,io,multiprocessing as mp,os,sys,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from . import contract as C,source as S,kernel as K
Q=C.Q


def fixtures(out,refs):
    from .test_v1 import Boundaries
    functions,proof=K.load(refs)
    from workflows.expansion.identity_v2.projection_v2 import rdkit_identity_modules
    Boundaries.functions=functions;Boundaries.chem=rdkit_identity_modules()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_BOUNDARIES_BEFORE_DATA')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'frozen_function_proof':proof,'before_archive_and_inventory_bodies':True}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_DATA');return v


def comparison(root_result,conformer_result):
    if root_result is None or root_result['has_any_unknown'] or conformer_result['has_any_unknown']:return 'UNKNOWN_NOT_COMPARABLE'
    a={p[0] for p in root_result['full_key_and_WP5_pairs']};b={p[0] for p in conformer_result['full_key_and_WP5_pairs']}
    return 'FULL_SOURCE_KEYS_EQUAL' if a==b else 'ROOT_SMILES_AND_NATIVE_MOLBLOCK_FULL_KEYS_DIFFER'


class Dispatch:
    def __init__(self,pool,writer,budget,groups):
        self.pool,self.writer,self.budget,self.groups=pool,writer,budget,groups;self.pending={}
        self.submitted=collections.Counter();self.completed=collections.Counter();self.states=collections.Counter();self.unknown=collections.Counter()
        self.worker_rows=collections.Counter();self.worker_CPU=collections.Counter();self.kind_CPU=collections.Counter();self.journal_bytes=collections.Counter()
    def enqueue(self,row):
        before=self.writer.bytes;self.writer.write({'event':'EXACT_SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},True)
        self.journal_bytes[row['kind']]+=self.writer.bytes-before
        self.pending[self.pool.submit(K.work,row)]=row;self.submitted[row['kind']]+=1
        if len(self.pending)>=32:self.collect(False)
    def collect(self,all_rows):
        while self.pending:
            done,_=cf.wait(self.pending,timeout=1,return_when=cf.FIRST_COMPLETED);self.budget.check(False)
            for future in done:
                row=self.pending.pop(future)
                try:value=future.result();Q.need(value['result']['source']==row,'EXACT_ORIGINAL_SOURCE_RETURNED_UNCHANGED')
                except Exception as exc:value={'worker_pid':None,'worker_CPU_seconds':None,'result':{'source':row,'identity_state':'TECHNICAL_UNRESOLVED',
                    'has_any_unknown':True,'full_key_and_WP5_pairs':[],'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False,'source_or_pool_accepted':False}}
                before=self.writer.bytes;self.writer.write({'event':'SOURCE_KEY_RESULT_DURABLE_BEFORE_AGGREGATE','worker_observation':value})
                kind=row['kind'];self.journal_bytes[kind]+=self.writer.bytes-before;result=value['result'];group=self.groups[row['root_assignment_ordinal']]
                compact={k:result[k] for k in ('identity_state','has_any_unknown','full_key_and_WP5_pairs')}
                if kind=='root_SMILES':Q.need(group['root_result'] is None,'ONE_RESULT_PER_NATIVE_ROOT');group['root_result']=compact
                else:group['conformer_results'].append({'global_conformer_assignment_ordinal':row['global_conformer_assignment_ordinal'],
                    'secondary_assignment_ordinal':row['secondary_assignment_ordinal'],'native_conformer_ID':row['native_conformer_ID'],**compact})
                self.completed[kind]+=1;self.states[result['identity_state']]+=1;self.unknown[kind]+=result['has_any_unknown']
                pid=str(value['worker_pid']);self.worker_rows[pid]+=1
                if value['worker_CPU_seconds'] is not None:
                    self.worker_CPU[pid]+=value['worker_CPU_seconds'];self.kind_CPU[kind]+=value['worker_CPU_seconds']
            if done and not all_rows:return


def unions(groups,writer,mode):
    counts=collections.Counter();comparison_counts=collections.Counter()
    for ordinal,group in enumerate(groups):
        root=group['root_result'];Q.need(root is not None,'EVERY_ROOT_SMILES_HAS_DURABLE_RESULT');pairs=set(map(tuple,root['full_key_and_WP5_pairs']))
        comparisons=[]
        for conf in sorted(group['conformer_results'],key=lambda r:r['secondary_assignment_ordinal']):
            pairs.update(map(tuple,conf['full_key_and_WP5_pairs']));state=comparison(root,conf)
            comparisons.append({**conf,'root_SMILES_vs_conformer_comparison':state})
        full=len(comparisons)==group['source_conformers']
        if mode=='full':Q.need(full,'FULL_UNION_REQUIRES_ALL_NATIVE_CONFORMERS')
        local=collections.Counter(r['root_SMILES_vs_conformer_comparison'] for r in comparisons)
        writer({'root_assignment_ordinal':ordinal,'native_root_ID':group['native_root_ID'],'source_root_SMILES_result':root,
            'all_original_conformer_relationships':group['source_conformers'],'selected_conformer_results':len(comparisons),
            'all_selected_native_conformer_key_observations':comparisons,'comparison_counts':dict(local),
            'conservative_full_InChIKey_union':sorted({k for k,w in pairs}),'conservative_WP5_key_union':sorted({w for k,w in pairs}),
            'all_conformers_covered':full,'coverage_state':'ALL_ORIGINAL_CONFORMERS' if full else 'PROFILE_PARTIAL_CONFORMER_COVERAGE',
            'multiple_observed_full_keys':len({k for k,w in pairs})>1,'representative_source_or_conformer_selected':False,
            'unknowns_or_mismatches_discarded':False,'source_graph_stereo_or_pool_accepted':False})
        counts['root_unions']+=1;counts['partial_conformer_coverage_roots']+=not full;counts['multiple_observed_full_key_roots']+=len({k for k,w in pairs})>1
        counts['unknown_root_SMILES']+=root['has_any_unknown'];counts['roots_with_unknown_selected_conformer']+=any(r['has_any_unknown'] for r in comparisons)
        comparison_counts.update(local)
    Q.need(counts['root_unions']==C.ROOT_N,'ALL_ROOT_UNIONS_DURABLE');return dict(counts),dict(comparison_counts)


def observe(plan,old,out,proof,budget):
    started=time.monotonic();root,verification=S.decode(plan,old,budget);wanted=S.selected(plan['mode']);groups=[];context_rows=0
    Q.write_new(out/'selected_conformer_ordinals.json',{'mode':plan['mode'],'seed':C.SEED if wanted is not None else None,
        'selection':'UNIFORM_WITHOUT_REPLACEMENT' if wanted is not None else 'ALL_SOURCE_CONFORMERS','ordinals':sorted(wanted) if wanted is not None else None,
        'selected_MolBlocks':C.PILOT_N if wanted is not None else C.CONF_N,'all_root_SMILES_selected':C.ROOT_N})
    context=B.Writer(out/'all_native_source_relationships.jsonl',budget);journal=B.Writer(out/'selected_source_key_results.jsonl',budget);dispatch=None
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(proof['request']['source_references'],)) as pool:
            dispatch=Dispatch(pool,journal,budget,groups)
            try:
                for row in S.records(root):
                    budget.check();chosen=row['kind']=='root_SMILES' or wanted is None or row['global_conformer_assignment_ordinal'] in wanted
                    context.write(S.relationship(row,chosen),True);context_rows+=1
                    if row['kind']=='root_SMILES':
                        Q.need(row['root_assignment_ordinal']==len(groups),'CONTIGUOUS_ROOT_SOURCE_ORDINALS')
                        groups.append({'native_root_ID':row['native_root_ID'],'source_conformers':row['all_original_conformer_relationships'],'root_result':None,'conformer_results':[]})
                    if chosen:dispatch.enqueue(row)
                del root;dispatch.collect(True)
                expected={'root_SMILES':C.ROOT_N,'conformer_MolBlock':C.PILOT_N if wanted is not None else C.CONF_N}
                Q.need(dict(dispatch.completed)==dict(dispatch.submitted)==expected and context_rows==C.ROOT_N+C.CONF_N,'EXACT_ALL_CONTEXT_AND_SELECTED_RESULTS')
            finally:dispatch.collect(True)
        context.close();journal.close();unions_writer=B.Writer(out/'all_native_root_conservative_key_unions.jsonl',budget)
        try:summary,comparisons=unions(groups,unions_writer.write,plan['mode'])
        finally:unions_writer.close()
        Q.need(sum(dispatch.journal_bytes.values())==journal.bytes,'EXACT_PROFILE_OUTPUT_BYTES_SEPARATE_BY_SOURCE_KIND')
        return {'complete_source_relationship_rows':context_rows,'completed_by_kind':dict(dispatch.completed),'unknown_by_kind':dict(dispatch.unknown),
            'identity_state_counts':dict(dispatch.states),'root_union_counts':summary,'root_SMILES_vs_MolBlock_comparison_counts':comparisons,
            'selected_journal_bytes_by_kind':dict(dispatch.journal_bytes),'selected_result_journal_reference':journal.reference(),
            'all_source_relationship_journal_reference':context.reference(),'all_root_union_reference':unions_writer.reference(),
            'worker_record_counts':dict(dispatch.worker_rows),'worker_CPU_seconds':dict(dispatch.worker_CPU),
            'observed_worker_CPU_seconds_by_kind_excluding_initializer':dict(dispatch.kind_CPU),
            'current_source_verification':verification,'source_verification_dispatch_and_union_wall_seconds':time.monotonic()-started,
            'source_or_pool_accepted':False}
    finally:
        if not context.stream.closed:context.close()
        if not journal.stream.closed:journal.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);_,old,parents=C.inputs(plan);params=C.parameters(plan['mode'],plan['output_cap_bytes'])
    Q.need(plan['schema']=='MARCEL_KRAKEN_KEYS_PLAN_V1' and plan['scope_parameters']==params,'EXACT_NEW_KEY_SCOPE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.scope_key(plan['mode']),expected_scope_parameters=params,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.M.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is (plan['mode']=='profile') and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=(7200 if plan['mode']=='profile' else 172800)
        and plan['wall_seconds']%60==0 and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
        and req['data_references']==[plan['archive_reference'],plan['inventory_reference']] and not req.get('deferred_authority_references'),
        'EXACT_CPU16_NO_MEM_ACTUAL_RESOURCES_AND_TWO_DATA_LOCATORS')
    review=C.M.meta(req['scope']['review']);Q.need(req['scope']['mode']==('BOUNDED_PERFORMANCE_BATCH' if plan['mode']=='profile' else 'FULL_SOURCE_AFTER_PROFILE')
        and review['all_native_IDs_and_relationships_and_source_key_variants_retained'] is True
        and review['source_graph_stereo_or_pool_release'] is False,'ROOT_EXACT_KEY_OBSERVATION_SCOPE')
    cost=C.M.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_QUALITY_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_ACTUAL_NEW_AND_FROZEN_SOURCE_PINS')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]]
        and sys.version_info[:3]==(3,11,14),'PRIMARY_COMPLETE_ARGV_AND_FROZEN_SAMPLER_PYTHON')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_EXACT_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=B.Budget(plan,proof,out);gate=None
    try:
        gate=fixtures(out,req['source_references']);budget.check(force=True);result=observe(plan,old,out,proof,budget);owned=budget.used()
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_KRAKEN_KEYS_RECEIPT_V1','status':'EXACT_SELECTED_SOURCE_KEYS_OBSERVED_UNKNOWNS_AND_MISMATCHES_RETAINED',
            'mode':plan['mode'],'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22',
            'archive_reference':plan['archive_reference'],'inventory_reference':plan['inventory_reference'],'plan_reference':Q.pin(a.plan),
            'startup_proof_reference':Q.pin(a.startup_proof),'accepted_structure_receipt_reference':plan['accepted_structure_receipt_reference'],
            'accepted_structure_accounting_reference':plan['accepted_structure_accounting_reference'],'fixtures':gate,**result,
            'owned_output_bytes_before_receipt':owned,'observed_parent_and_children_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,
            'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE','source_graph_stereo_or_pool_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'MARCEL_KRAKEN_KEYS_FAILURE_V1','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'fixtures':gate,'partial_durable_source_and_result_prefixes_retained':True,'actual_cost':'PENDING_ROOT_ACCOUNTING','source_or_pool_release':False});raise


if __name__=='__main__':raise SystemExit(main())
