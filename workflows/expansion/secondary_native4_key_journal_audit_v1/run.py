"""Read only one closed journal; persist bounded original pairs as DATA examples."""
import argparse,collections,hashlib,io,json,os,stat,sys,time,traceback,unittest
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,reducer as R
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_JSON_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'before_original_DATA_and_Budget':True,'old_B3_or_native3_reexecuted':False,'new_graph_parse_key_QM_calls':0}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'NEW_PURE3_BEFORE_DATA_AND_MONITOR');return v


def imports(plan):
    for name,module in list(sys.modules.items()):
        file=getattr(module,'__file__',None)
        if name.startswith('secondary_') and file and Path(file).suffix=='.py':
            Q.need(C.ROOT/'code' in Path(file).absolute().parents and Q.ref(file) in plan['source_references'],'ACTUAL_TRANSITIVE_ALPHA_SOURCE_PIN:'+name)


class Examples:
    def __init__(self,out,budget):
        self.out,self.budget=out,budget;self.path=out/'recorded_cause_example_pairs.DATA.jsonl';self.f=self.path.open('xb');self.keys={};self.by_cause=collections.defaultdict(list);self.n=0
    def consider(self,pair):
        sid,ordinal=pair['key'];groups=[(sid,axis,label) for axis,label in pair['audit']['causes'] if len(self.by_cause[(sid,axis,label)])<3]
        if not groups:return
        key=pair['key'];locator=self.keys.get(key)
        if locator is None:
            value={'event':'ORIGINAL_PAIR_DATA_EXAMPLE_NO_NEW_PARSE_OR_KEYS','physical_identity':{'source_id':sid,'source_format_ordinal':ordinal},
                'original_source':pair['source'],'original_result':pair['result'],'source_event_input_segment':pair['source_event_locator'],
                'result_event_input_segment':pair['result_event_locator'],
                'recorded_error_axis_observation':{k:v for k,v in pair['audit'].items() if k!='messages'}}
            raw=Q.canonical(value)+b'\n';offset=self.f.tell();J.append(self.f,value,self.budget)
            locator={'path':str(self.path),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};self.keys[key]=locator;self.n+=1
        for group in groups:self.by_cause[group].append(locator)
    def close(self):
        self.f.flush();os.fsync(self.f.fileno());self.f.close()
        return {'DATA_reference':J.pin(self.path),'unique_original_pairs':self.n,'maximum_per_source_axis_cause':3,
            'selection':'FIRST3_RECORDED_RESULTS_PER_SOURCE_AXIS_CLASS_NOT_UNIFORM_OR_COST_MEAN',
            'cause_examples':[{'source_id':s,'axis':a,'recorded_cause_class':c,'DATA_segments':v} for (s,a,c),v in sorted(self.by_cause.items())],
            'scientific_pairs_are_not_login_metadata_or_source_references':True}


def audit(ref,populations,budget,examples,progress):
    p=Q.literal(ref['path']);Q.need(not any(v.is_symlink() for v in (p,*p.parents)),'LITERAL_CLOSED_OWNED_JOURNAL_NO_SYMLINK')
    info=p.lstat();before=frame(info);Q.need(stat.S_ISREG(info.st_mode) and info.st_uid==1264 and info.st_size==ref['bytes'],'CURRENT_ORIGINAL_JOURNAL_OWNER_AND_SIZE')
    reducer=R.Reducer(C.COUNTS,populations,32)
    with p.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==before,'SAME_OPENED_JOURNAL_FD');h=hashlib.sha256();n=0
        while True:
            budget.check();block=f.read(1<<20)
            if not block:break
            n+=len(block);Q.need(n<=ref['bytes'],'ORIGINAL_WHOLE_JOURNAL_BOUND');h.update(block)
        Q.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==before,'CURRENT_WHOLE_SHA_BEFORE_JOURNAL_JSON_DECODING')
        f.seek(0);h2=hashlib.sha256();offset=0
        while True:
            budget.check();raw=f.readline(C.LINE_CAP+1)
            if not raw:break
            Q.need(len(raw)<=C.LINE_CAP and raw.endswith(b'\n'),'COMPLETE_ORIGINAL_BOUNDED_EVENT_NO_TRUNCATION')
            value=json.loads(raw,object_pairs_hook=R.pairs_unique,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('NONFINITE_JSON_CONSTANT')))
            locator={'input_reference':ref,'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};h2.update(raw);offset+=len(raw)
            pair=reducer.feed(value,locator)
            if pair:examples.consider(pair)
            progress.update(input_bytes=offset,events_seen=reducer.lines,paired_results=len(reducer.done),pending_pairs=len(reducer.pending))
        summary=reducer.finish()
        Q.need(offset==ref['bytes'] and h2.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'ENTIRE_SECOND_PASS_SHA_STABLE_FSTAT_AND_EOF')
    Q.need(summary['has_unknown_counts']==C.UNKNOWN_COUNTS and summary['any_observed_key_union_counts']==C.KEY_COUNTS,
        'ACTUAL856_RECEIPT_UNKNOWN_AND_ANY_KEY_COUNTS_REPRODUCED')
    return summary,{'current_full_SHA_before_any_event_decode':True,'second_pass_full_SHA':h2.hexdigest(),'current_frame':list(before),
        'source_reference':ref,'EOF_complete':True,'source_result_events':6390,'source_rows':3195,'result_rows':3195}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan,proof=G.require_startup(args.plan,args.startup_proof);parent,populations=C.inputs(plan)
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_DIAGNOSIS_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    started=time.monotonic();budget=None;examples=None;progress={};fx=None
    try:
        fx=fixtures(out);imports(plan);budget=Budget(plan,proof,out);examples=Examples(out,budget)
        summary,integrity=audit(C.JOURNAL,populations,budget,examples,progress);example_refs=examples.close();examples=None
        budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_NO_COMPLETE_DIAGNOSIS_CLAIM')
        summary.update({'schema':'NATIVE4_RECORDED_KEY_JOURNAL_CAUSE_SUMMARY_V1','status':'READONLY_RECORDED_CAUSE_COUNTS_COMPLETE_ORIGINAL_UNKNOWNS_UNCHANGED',
            'new_graph_parse_key_UFF_QM_calls':0,'original_unknowns_changed':False,'original_reader_or_boundary_flags_changed':False,
            'graph_unavailability_or_failure_root_cause':'UNKNOWN_NOT_ESTABLISHED_BY_ERROR_COUNTS','source_full_profile_accepted':False,
            'examples_DATA_reference':example_refs['DATA_reference'],'global_release':False})
        summary_ref=J.write_json(out/'diagnosis_summary.json',summary,budget)
        issue_count=sum(v['count'] for v in summary['contract_issues']);status='CLOSED_JOURNAL_AUDIT_COMPLETE_NOT_PROFILE_ACCEPTANCE' if issue_count==0 else 'CLOSED_JOURNAL_AUDIT_CONTRACT_ISSUES_RETAINED_HOLD'
        receipt={'schema':'SECONDARY_NATIVE4_KEY_JOURNAL_AUDIT_RECEIPT_V1','status':status,'job_id':str(proof['job_id']),
            'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),
            'native_profile_receipt_reference':plan['native_profile_receipt_reference'],'native_profile_accounting_reference':plan['native_profile_accounting_reference'],
            'scope_parameters':C.PARAMETERS,'fixtures':fx,'input_integrity':integrity,'diagnosis_summary_reference':summary_ref,'examples':example_refs,
            'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,'actual_RDKIT_module_names_loaded':[n for n in sys.modules if n=='rdkit' or n.startswith('rdkit.')],
            'RDKit_import_absence_assumed':False,'new_SDF_MOL2_parse_fullkey_UFF_QM_calls':0,'original_parameters_results_flags_or_unknowns_modified':False,
            'cause_from_high_unknown_rate_inferred':False,'automatic_fallback_policy_acceptance':False,'global_pool_full_decontamination_release':False,
            'cost_overrun_action':'REPORT_AND_CONTINUE','actual_new_parent_terminal_cost_pending_Root':True}
        J.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':status,'receipt_reference':J.pin(out/'receipt.json')}));return 0 if issue_count==0 else 3
    except BaseException as exc:
        example_refs=examples.close() if examples else None;examples=None
        Q.write_new(out/'failure.json',{'schema':'NATIVE4_KEY_JOURNAL_AUDIT_PARTIAL_FAILURE_V1','status':'PREFIX_RETAINED_NO_CLOSURE_OR_PROFILE_ACCEPTANCE',
            'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),'progress':progress,'fixtures':fx,
            'examples':example_refs,'runtime':budget.receipt() if budget else None,'new_graph_parse_keys_QM_calls':0,
            'original_results_changed':False,'global_release':False,'actual_new_parent_cost_pending_Root':True})
        raise
    finally:
        if examples:examples.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
