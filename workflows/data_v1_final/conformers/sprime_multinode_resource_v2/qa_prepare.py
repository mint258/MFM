"""CPU-only independent32 original-task/baseline binding;no UFF or prod once."""
import argparse,gzip,hashlib,json,math,os,pathlib
from . import contract as C,edge as E,runtime_io as R
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.bridge import scientific_sha
def select(closed,excluded=()):
    eligible=[]
    for row in closed:
        s=row['summary'];heavy=s.get('heavy_atoms');n=s.get('expected_conformers');elapsed=row.get('science_worker_seconds')
        if s.get('status')!='SUCCESS' or row['detail'].get('new_real_accepted_count',0)<1:continue
        if type(heavy)is not int or not 0<heavy<=32 or type(n)is not int or not 0<n<=30:continue
        if type(elapsed)not in (float,int) or not math.isfinite(elapsed) or not 0<=elapsed<=60 or elapsed!=s.get('elapsed_seconds'):continue
        key=hashlib.sha256(('sprime-multinode-control32-20261027:'+row['molecule_id']).encode()).hexdigest();eligible.append((key,row['molecule_id'],row))
    eligible.sort(key=lambda x:(x[0],x[1]));remaining=[r for _,mid,r in eligible if mid not in set(excluded)]
    return remaining[:32] if len(remaining)>=32 else [],len(eligible),len(remaining)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);n=C.node(plan['node']);argv=[C.Q.PY,'-B','-m',C.MODULE+'.qa_prepare','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_qa_prepare_v2',expected_scope_parameters=C.parameters('qa_prepare',n),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[ref,*C.own_sources(),*plan['source_references']])
    E.source3(plan['source3_reference']);binding=E.binding(plan['node_binding_reference'],active=True);C.need(binding['node']==proof['request']['node']==n,'ACTUAL_NODE_QA_PREPARATION')
    C.need(C.DIAG in a.output.parents and not a.output.exists(),'FRESH_INDEPENDENT32_PREPARE_OUTPUT');a.output.mkdir(parents=True)
    R.OUT=a.output;R.PROOF=proof;R.VALUE=C.config(plan['config_reference']);R.SESSION={'quota_reuse_review_reference':plan['quota_reuse_review_reference']}
    budget=R.Budget(proof,R.SESSION,R.VALUE,a.output);C.need(budget.observe() is None,'ACTUAL_QUOTA_BEFORE_QA_DATA');budget.start_monitor()
    try:
        audit=E.meta(plan['original_audit_reference']);C.need(audit['status']=='PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL'
            and audit['original_job_id']=='4520364' and audit['original_parent_state']=='TIMEOUT' and audit['complete_reusable_molecules']==334,'UNCHANGED_ORIGINAL334_AUDIT_NOT_FORMAL_ACCEPTANCE')
        closed_ref=next(r for r in audit['outputs'] if pathlib.Path(r['path']).name=='complete_packages.json');R.authorized(proof,[closed_ref,audit['tasks_reference']])
        closed_raw=C.pinned(closed_ref,C.CAP).read_bytes();C.need(len(closed_raw)==closed_ref['bytes'] and hashlib.sha256(closed_raw).hexdigest()==closed_ref['sha256'],'ACTUAL334_BODY_BYTES_AFTER_CPU_ADMISSION')
        closed=json.loads(closed_raw);C.need(len(closed)==334 and len({r['molecule_id'] for r in closed})==334
            and not {'principal_01112964','principal_00509656'}&{r['molecule_id'] for r in closed},'FULL334_ORIGINAL_CLOSED_CENSUS_NO_TWO_UNRESOLVED_REPLAY')
        exclusion=E.exclusions(plan['excluded_mid_authority_reference']);chosen,eligible,remaining=select(closed,exclusion['excluded_molecule_ids']);tasks={}
        C.need(eligible==49 and remaining==33 and len(chosen)==32,'EXACT_REAL49_MINUS_OLD16_REMAINING33_THEN32_OR_HOLD')
        raw_task_bytes=C.pinned(audit['tasks_reference'],C.CAP).read_bytes();C.need(len(raw_task_bytes)==audit['tasks_reference']['bytes']
            and hashlib.sha256(raw_task_bytes).hexdigest()==audit['tasks_reference']['sha256'],'FULL_ORIGINAL336_TASK_BYTE_SHA')
        import io
        with io.BytesIO(raw_task_bytes) as stream:
            for raw in stream:
                C.need(len(raw)<=64<<20,'BOUNDED_FULL_ORIGINAL_TASK_LINE');t=json.loads(raw);mid=t['meta']['molecule_id'];C.need(mid not in tasks,'UNIQUE_ORIGINAL336_TASK');tasks[mid]=t
        C.need(len(tasks)==336 and set(r['molecule_id'] for r in closed)<=set(tasks),'ALL336_TASKS_AND334_CLOSED_RELATION')
        expected=[];output=[]
        for row in chosen:
            budget.observe();C.need(budget.stop is None,'QA_PREPARATION_RESOURCE_STOP_NO_NATIVE')
            mid=row['molecule_id'];task=tasks[mid];baseline_ref=row['reference']
            C.need(C.RUN/'artifacts' in pathlib.Path(baseline_ref['path']).parents and not any(p.is_symlink() for p in (pathlib.Path(baseline_ref['path']),*pathlib.Path(baseline_ref['path']).parents)),
                'ONLY_ORIGINAL334_CPU_PARSED_PRODUCER_PINNED_BASELINE_PATH')
            baseline=C.pinned(baseline_ref,128<<20);before=C.frame(baseline.stat())
            C.need(before['uid']==1278,'ORIGINAL_BASELINE_MAIN_UID')
            with gzip.open(baseline,'rb') as stream:raw=stream.read((1<<30)+1)
            C.need(len(raw)<=1<<30 and C.frame(baseline.stat())==before,'ORIGINAL_BASELINE_FULL_GZIP_CRC_EOF_STABLE_FRAME')
            packet=json.loads(raw)
            C.need(packet['summary']['molecule_id']==mid and packet['summary']['status']=='SUCCESS'
                and packet['summary']['seed']==C.seed_for(mid,task['meta']['cohort']=='retry_once'),'ACTUAL_ORIGINAL_TASK_SEED_BASELINE_SUCCESS')
            expected.append({'molecule_id':mid,'task_sha256':C.sha_value(task),'scientific_sha256_excluding_elapsed_seconds':scientific_sha(packet),
                'baseline_packet_reference':C.triple(baseline_ref),'baseline_actual_node_frame':C.frame(pathlib.Path(baseline_ref['path']).stat()),'origin_frame':row['file_identity']})
            output.append(C.canonical(task)+b'\n')
        data=R.atomic_bytes(a.output/'control32_tasks.jsonl',b''.join(output)) if chosen else None
        R.write_json_new(a.output/'receipt.json',{'schema':'ACTUAL_SPRIME_MULTINODE_CONTROL32_PREPARATION_V2','status':'ORIGINAL32_TASKS_AND_BASELINES_CLOSED_NO_UFF' if len(chosen)==32 else 'ELIGIBLE_BELOW32_HOLD_NO_WIDENING',
            'job_id':str(proof['job_id']),'node':n,'uid':1278,'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'tasks_reference':data,
            'eligible_count':eligible,'remaining_eligible_count':remaining,'excluded_mid_count':16,'excluded_mid_authority_reference':plan['excluded_mid_authority_reference'],'expected':expected,'original_audit_reference':plan['original_audit_reference'],'original334_reference':closed_ref,
            'original336_tasks_reference':audit['tasks_reference'],'source_references':C.own_sources(),'production_once_accessed':False,'new_UFF_QM_calls':0})
    finally:budget.close_monitor()
    return 0
if __name__=='__main__':
    failure=None
    try:outcome=main()
    except BaseException as exc:
        failure={'error':repr(exc),'traceback':__import__('traceback').format_exc()};raise
    finally:R.finish_resource_entry(failure)
    raise SystemExit(outcome)
