"""Four closed producer DATA inputs -> original27 identity/opaque index evidence only."""
import argparse,hashlib,io,json,os,stat,sys,time,unittest
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,projection as P
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_OPAQUE_EVIDENCE_BOUNDARIES')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
        'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'before_original_DATA_and_Budget':True,'old_fixtures_reexecuted':False}
    Q.write_new(out/'fixtures3.json',value);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'NEW3_PURE_BEFORE_DATA_AND_RESOURCE_MONITOR');return value


def imports(plan):
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if p and Path(p).suffix=='.py' and (name.startswith('secondary_') or name=='workflows' or name.startswith('workflows.')):
            Q.need(C.ROOT/'code' in Path(p).absolute().parents and Q.ref(p) in plan['source_references'],'ALL_ACTUAL_IMPORTED_SOURCE_PINS:'+name)


class Inputs:
    def __init__(self,refs,budget):
        self.refs=refs;self.budget=budget;self.files=[];self.frames=[]
        try:
            for ref in refs:
                C.data_locator(ref);p=Q.literal(ref['path']);s=p.lstat();Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_size==ref['bytes'],'EXACT_CURRENT_ALPHA_OWNED_REGULAR_DATA_SIZE')
                f=p.open('rb');self.files.append(f);fr=frame(s);self.frames.append(fr);Q.need(frame(os.fstat(f.fileno()))==fr,'OPENED_SAME_SOURCE_FD')
                h=hashlib.sha256();n=0
                while True:
                    budget.check();raw=f.read(1<<20)
                    if not raw:break
                    n+=len(raw);h.update(raw);Q.need(n<=ref['bytes'],'FINITE_CURRENT_DATA_BYTES')
                Q.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==fr==frame(p.lstat()),'WHOLE_CURRENT_SHA_STABLE_FD_BEFORE_ANY_DATA_DECODING');f.seek(0)
        except BaseException:self.close();raise
    def rows(self,index):
        f=self.files[index];ref=self.refs[index];Q.need(f.tell()==0,'ONE_WHOLE_SECOND_PASS');offset=0;h=hashlib.sha256()
        while True:
            self.budget.check();raw=f.readline(P.LINE_CAP+1)
            if not raw:break
            Q.need(len(raw)<=P.LINE_CAP and raw.endswith(b'\n'),'BOUNDED_COMPLETE_ORIGINAL_JSONL_ROW')
            segment={'input_reference':ref,'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};offset+=len(raw);h.update(raw)
            yield P.decode(raw),segment
        Q.need(offset==ref['bytes'] and h.hexdigest()==ref['sha256'],'WHOLE_SECOND_PASS_JSONL_SHA_AND_EOF')
        self.stable(index)
    def stable(self,index):
        Q.need(frame(os.fstat(self.files[index].fileno()))==self.frames[index]==frame(Q.literal(self.refs[index]['path']).lstat()),'ALL_ORIGINAL_DATA_FDS_AND_PATHS_UNCHANGED')
    def finish(self):
        for i in range(len(self.refs)):self.stable(i)
        return [{'source_reference':r,'current_frame':list(fr),'whole_SHA_before_any_DATA_decode':True,'stable_held_FD_and_path_after_complete_read':True} for r,fr in zip(self.refs,self.frames)]
    def close(self):
        for f in self.files:f.close()
        self.files=[]


class Evidence:
    def __init__(self,out,budget):
        self.out,self.budget=out,budget;self.files={name:(out/name).open('xb') for name in ('original27_relations.DATA.jsonl','original27_projections.DATA.jsonl','original27_rows.DATA.jsonl','original27_index_lines.DATA.raw','original_index_comments.DATA.raw')};self.rows=0
    def event(self,name,value):
        f=self.files[name];raw=Q.canonical(value)+b'\n';offset=f.tell();J.append(f,value,self.budget)
        return {'path':str(self.out/name),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    def raw(self,name,raw):
        self.budget.check(len(raw),drain=True);f=self.files[name];offset=f.tell();f.write(raw);f.flush();os.fsync(f.fileno())
        return {'path':str(self.out/name),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    def emit(self,raw,ordinal,offset,row):
        segment=self.raw('original27_index_lines.DATA.raw',raw)
        self.event('original27_rows.DATA.jsonl',{'event':'EXACT_ORIGINAL_INDEX_ID_AND_OPAQUE_LINE_NO_GRAPH_OR_TARGET_DECODE','source_id':'pdbbind_general',
            'original_index_ordinal':ordinal,'original_ID':row['projection']['ID'],'original_details':row['projection']['details'],'original_index_member':C.INDEX,
            'original_member_offset':offset,'opaque_full_line_output_segment':segment,'relation_input_segment':row['relation_input_segment'],
            'projection_input_segment':row['projection_input_segment'],'graph_identity_charge_stereo':'UNKNOWN','missing_structure_reason':'UNKNOWN',
            'automatic_structure_pool_or_decontamination_release':False});self.rows+=1
    def comment(self,raw,offset):self.raw('original_index_comments.DATA.raw',raw)
    def close(self):
        refs=[]
        for name,f in self.files.items():
            if not f.closed:f.flush();os.fsync(f.fileno());f.close()
            refs.append(J.pin(self.out/name))
        return refs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan,proof=G.require_startup(a.plan,a.startup_proof);d=C.inputs(plan);out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'FRESH_EVIDENCE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    started=time.monotonic();budget=None;inputs=None;evidence=None;fx=None;progress={};data_refs=[]
    try:
        fx=fixtures(out);imports(plan);budget=Budget(plan,proof,out);inputs=Inputs(d['data'],budget);evidence=Evidence(out,budget)
        relations=P.Relations(C.COUNTS,C.MISSING)
        for value,segment in inputs.rows(0):
            selected=relations.feed(value,segment)
            if selected:evidence.event('original27_relations.DATA.jsonl',selected)
            progress['relation_rows']=sum(relations.counts.values())
        selected=relations.finish();project=P.Projection(selected,C.COUNTS)
        for value,segment in inputs.rows(1):
            bound=project.feed(value,segment)
            if bound:evidence.event('original27_projections.DATA.jsonl',{'projection':bound['projection'],'projection_input_segment':segment})
            progress.update(source_index_rows=sum(project.counts.values()),source_native_rows=project.native_rows)
        bound=project.finish();Q.need(project.native_rows==57480,'ALL_ORIGINAL57480_NATIVE_CONTEXT_ROWS_NOT_REPARSED')
        lines=P.IndexLines(bound,C.INDEX_N,evidence.emit,evidence.comment);inventory=(v for v,s in inputs.rows(3))
        container=P.scan_tar(inputs.files[2],inventory,d['expected_container'],C.INDEX,lines,budget.check,progress)
        Q.need(inputs.files[2].tell()==d['data'][2]['bytes'],'WHOLE_COMPRESSED_FILE_EOF_ON_SAME_VERIFIED_FD')
        integrity=inputs.finish();Q.need(evidence.rows==C.N,'EXACT27_OPAQUE_ROWS_BOUND');data_refs=evidence.close();evidence=None
        mapping=out/'frozen_source_version_download_mapping.DATA.json';J.write_json(mapping,d['version_mapping_DATA'],budget);data_refs.append(J.pin(mapping))
        budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_RETAINS_PREFIX_NO_COMPLETE_CLAIM')
        summary={'schema':'PDBBIND_GENERAL27_OPAQUE_INDEX_EVIDENCE_SUMMARY_V1','status':'ALL27_EXACT_ORIGINAL_INDEX_ROWS_AND_FROZEN_SOURCE_MAPPING_CLOSED_NOT_IDENTITY_ACCEPTANCE',
            'all_original_index_rows':sum(relations.counts.values()),'index_rows_by_source':dict(relations.counts),'missing_context_rows_by_source':C.MISSING,
            'original_source_index_rows':sum(project.counts.values()),'original_native_context_rows':project.native_rows,'selected_exact_rows':C.N,
            'original_index_noncomment_rows':container['original_index']['noncomment_rows'],'original_index_comment_lines':container['original_index']['comment_lines'],
            'complete_TAR_members':container['all_members_verified'],'complete_gzip_EOF_CRC_and_decoded_SHA':True,'DATA_references':data_refs,
            'IDs_raw_lines_SMILES_or_target_values_in_summary':False,'new_graphparse_key_UFF_QM_network_calls':0,'general12119_key_UNKNOWNs_are_the27_index_gaps':False,
            'missing_structure_reason':'UNKNOWN','original_UNKNOWNs_unchanged':True,'version_labels_prove_missing_structure_cause':False,'global_pool_decontamination_release':False}
        sr=J.write_json(out/'finding_summary.json',summary,budget)
        receipt={'schema':'SECONDARY_PDBBIND_UNRESOLVED27_INDEX_RECEIPT_V1','status':summary['status'],'job_id':str(proof['job_id']),'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],
            'plan_reference':Q.ref(a.plan),'startup_proof_reference':Q.ref(a.startup_proof),'full_inventory_receipt_reference':plan['full_inventory_receipt_reference'],
            'full_inventory_accounting_reference':plan['full_inventory_accounting_reference'],'scope_parameters':C.PARAMETERS,'fixtures':fx,'input_integrity':integrity,
            'TAR_inventory_and_index_integrity':container,'finding_summary_reference':sr,'DATA_references':data_refs,'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,
            'actual_RDKIT_module_names_loaded':[n for n in sys.modules if n=='rdkit' or n.startswith('rdkit.')],'RDKit_import_absence_assumed':False,
            'new_graphparse_key_UFF_QM_network_calls':0,'automatic_policy_identity_pool_decontamination_release':False,'actual_new_parent_terminal_cost_pending_Root':True,'cost_overrun_action':'REPORT_AND_CONTINUE'}
        J.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':summary['status'],'receipt_reference':J.pin(out/'receipt.json')}));return 0
    except BaseException as exc:
        if evidence:data_refs=evidence.close();evidence=None
        Q.write_new(out/'partial_hold.json',{'schema':'PDBBIND_GENERAL27_EVIDENCE_PARTIAL_HOLD_V1','status':'PARTIAL_EVIDENCE_RETAINED_NOT_CLOSED',
            'error_type':type(exc).__name__,'error_code':str(exc) if isinstance(exc,ValueError) else 'NONCONTRACT_EXCEPTION_DETAILS_NOT_IN_HUMAN_SUMMARY',
            'progress':progress,'fixtures':fx,'partial_DATA_references':data_refs,'runtime':budget.receipt() if budget else None,
            'new_graphparse_key_UFF_QM_calls':0,'original_UNKNOWNs_unchanged':True,'global_release':False,'actual_new_parent_terminal_cost_pending_Root':True});raise
    finally:
        if inputs:inputs.close()
        if evidence:evidence.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
