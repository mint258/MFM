"""New full Common TRAIN D27 reference candidate; Root owns actual C0/application."""
import argparse
import collections
import concurrent.futures as cf
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import uuid
from ..common import load,reference,dump_new
from ..portable_sources_v1.transport import bind_plan,verify
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.common import allocated_bytes
from .inventory import need
from . import science,inputs,coverage,quantiles


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def bounded(pool,function,items,workers,guard):
    iterator=iter(items);waiting={}
    while True:
        while len(waiting)<workers*2:
            item=next(iterator,None)
            if item is None:break
            waiting[pool.submit(function,item)]=True
        if not waiting:return
        done,_=cf.wait(waiting,timeout=5,return_when=cf.FIRST_COMPLETED);guard.check()
        for future in done:
            waiting.pop(future);yield future.result()


def grouped(catalog,logical):
    bysource=collections.defaultdict(list)
    for window in catalog['windows']:bysource[window['source_reference']['path']].append(window)
    out=[];used=set()
    for g in logical['groups']:
        windows=[]
        for ref in g['label_files']:
            if ref['family']not in('D20','D3'):continue
            need(ref['path']in bysource,'Every original logical D file must have its full closed windows')
            for w in sorted(bysource[ref['path']],key=lambda w:w['physical_row_lo']):
                need(w['source_reference']['source_job_id']==g['source_job_id'],'Original logical source job required')
                windows.append(w);used.add(w['window_reference']['path'])
        out.append({'group_index':g['group_index'],'source_job_id':g['source_job_id'],
            'expected_records':g['expected_records'],'windows':windows})
    need(len(out)==171 and sorted(g['group_index']for g in out)==list(range(171))
        and len(used)==len(catalog['windows']),'All original171 groups and every selected window exactly once')
    return out


def run(plan_path,startup_proof=None):
    plan=load(plan_path);need(plan['schema']=='PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_PLAN_V1','Exact independent D27 plan required')
    authority=bind_plan(plan);need(authority is not None,'Actual independent Alpha profile required; no Main execution is invented')
    ctx=mp.get_context('spawn');stop=ctx.Event();guard=Guard(plan,stop_event=stop);root=Path(plan['output_directory'])
    root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(root/'parent.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        codec,calibration,support=science.load(plan)
        catalog=load(verify(plan['source_catalog_reference']));logical=load(verify(plan['logical_group_plan_reference']))
        need(catalog['schema']=='PUBCHEM_D27_CLOSED_WINDOW_INPUTS_V1'
            and catalog['original_all_role_canonical_records']==inputs.N and catalog['original_D27_task_rows']==2*inputs.N,
            'Complete original D27 input catalog required; not55k selected coverage')
        fields=load(verify(plan['field_map_reference']));selected=[f for f in fields if f['task']in('D20','D3')]
        need({f['field_id']for f in selected}==set(range(27))and len(selected)==27,'Original20+7 field map required')
        source_scope={k:plan[k]for k in('source_catalog_reference','logical_group_plan_reference','canonical_index',
            'field_map_reference','diagnostic_delivery_reference','original_mask_config_reference','scientific_sources')}
        source_scope.update({k:plan[k]for k in('common_reference_manifest','common_membership_acceptance_reference')if plan.get(k)})
        fingerprint=hashlib.sha256(canonical(source_scope)).hexdigest();scope_path=root/'scope.json'
        if scope_path.exists():need(load(scope_path)=={'scope_fingerprint':fingerprint,'source_scope':source_scope},'Same closed inputs/science required on resume')
        else:dump_new(scope_path,{'scope_fingerprint':fingerprint,'source_scope':source_scope})
        groups=grouped(catalog,logical)
        eligibility_path=root/'eligibility_closed.json'
        if eligibility_path.exists():
            er=load(eligibility_path);eligible=load(verify(er['manifest_reference']))
            need(er['scope_fingerprint']==fingerprint,'Eligibility scope mismatch')
            for ref in eligible['arrays'].values():verify(ref)
            eligibility_ref=er['manifest_reference']
        else:
            workspace=root/('eligibility_attempt_'+uuid.uuid4().hex);workspace.mkdir()
            eligible,eligibility_ref=inputs.eligibility(plan,workspace,groups,guard,codec,support)
            dump_new(eligibility_path,{'scope_fingerprint':fingerprint,'manifest_reference':eligibility_ref})
        # Conservative full leaf envelope plus existing/failed bytes and admin.
        # It never truncates records or drops atom leaves to meet an output cap.
        need(allocated_bytes(plan['output_scope_root'])+eligible['valid_leaf_output_upper_bound_bytes']+(2<<30)<=plan['output_cap_bytes'],
            'Reviewed output cap must cover the whole D27 valid-leaf upper envelope and retained partials')
        taskroot=root/'tasks';taskroot.mkdir(exist_ok=True)
        with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=ctx,initializer=coverage.initialize,
                initargs=(plan,eligible['arrays'],str(taskroot),stop))as pool:
            closed={}
            for ref in bounded(pool,coverage.group,((g,fingerprint)for g in groups),plan['workers'],guard):
                report=load(verify(ref));closed[report['group_index']]=ref
            need(set(closed)==set(range(171)),'Every complete logical D27 group required')
            import numpy as np
            seen=np.zeros(inputs.N,dtype='u1');masks=collections.defaultdict(collections.Counter);reports={}
            for index in range(171):
                report=load(verify(closed[index]));reports[index]=report;ordinals=np.fromfile(verify(report['coverage_ordinals']),dtype='<u8')
                need(len(ordinals)==report['records']and np.all(ordinals<inputs.N)and not np.any(seen[ordinals]),'Global exact canonical coverage cannot repeat')
                seen[ordinals]=1
                for fid,counts in report['field_mask_counts'].items():masks[fid].update(counts)
            need(int(np.count_nonzero(seen))==inputs.N and all(masks[str(i)]['records']==inputs.N for i in range(27)),
                'Actual full all-role typed coverage and27 denominators required before fitting')
            for ref in eligible['arrays'].values():verify(ref)
            coverage_result={'schema':'PUBCHEM_FULL_D27_CPU_TYPED_COVERAGE_V1','status':'COMPLETE_PENDING_PARENT_C0_AND_ROOT_REVIEW',
                'scope_fingerprint':fingerprint,'records':inputs.N,'D27_task_rows':2*inputs.N,'groups':[closed[i]for i in range(171)],
                'eligibility_reference':eligibility_ref,'field_mask_counts':{k:dict(v)for k,v in masks.items()},
                'all_D27_parts_full_SHA_and_typed_stream_reopened':True,'all_canonical_keys_once_per_family':True,
                'source_NA_and_new_masks_separate':True,'old55k_authority_not_used_as_full_release':True}
            coverage_path=root/('coverage_'+uuid.uuid4().hex+'.json');dump_new(coverage_path,coverage_result);coverage_ref=reference(coverage_path)
            items=[(fid,[reports[i]['fields'][str(fid)]for i in range(171)],fingerprint)for fid in range(27)]
            results={}
            for ref in bounded(pool,quantiles.field,items,plan['workers'],guard):
                item=load(verify(ref));results[item['field_id']]=ref
        need(set(results)==set(range(27)),'All27 exact median/MAD fields required')
        stats={str(fid):{k:load(verify(results[fid]))[k]for k in('median','MAD','TRAIN_n','MAD_n')}for fid in range(27)}
        attempt=root/('reference_'+uuid.uuid4().hex);attempt.mkdir()
        calibration_doc={'schema':'PUBCHEM_FULL_COMMON_TRAIN_D27_CALIBRATION_V1','fit_role':'TRAIN_ONLY',
            'coverage_fingerprint':fingerprint,'fields':stats,'coverage_reference':coverage_ref,
            'field_statistics_references':[results[i]for i in range(27)],'R_N_used_for_fit':False,
            'provisional_scope_not_final_Common':False,'normalization_or_Pprime_release_claimed':False}
        dump_new(attempt/'calibration.json',calibration_doc);calibration_ref=reference(attempt/'calibration.json')
        domain={'schema':'PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_DOMAIN_V1','fit_role':'TRAIN_ONLY',
            'coverage_fingerprint':fingerprint,'calibration_reference':calibration_ref,
            'actual_source_and_role_census_closed':True,'full_Common_census_closed':True,
            'eligibility_reference':eligibility_ref,'source_scope':source_scope,
            'reference_weighting':'original canonical PM7 record frequency; SASA_atom valid atomic leaves',
            'fit_records':eligible['fit_records'],'reference_geometry':'original WP5 PM7 S; no S-prime/P-prime replacement',
            'D3_original_label_geometry_vs_new_UFF_domain_difference_requires_review':True,
            'D20_historical_precision_may_be_F32_promoted_new_outputs_are_F64':True,
            'robust_z_review_only_no_automatic_mask':True,'new_R_N_TRAIN_fit':False}
        dump_new(attempt/'domain.json',domain)
        review={'schema':'ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1','status':'PROPOSED_PENDING_INDEPENDENT_ROOT_DOMAIN_REVIEW',
            'reviewer':None,'R_N_fit_as_TRAIN':False,'same_D_function_units_and_family_field_map_reviewed':False,
            'UFF_D3_vs_original_TRAIN_domain_difference_reviewed':False,'field_map_reference':plan['field_map_reference'],
            'original_mask_config_reference':plan['original_mask_config_reference'],'TRAIN_calibration_reference':calibration_ref,
            'TRAIN_reference_domain_reference':reference(attempt/'domain.json'),'actual_CPU_coverage_reference':coverage_ref,
            'Root_action':'Require real parent C0/accounting and independent full Common/D5/science/domain review; application only, never fit R/N'}
        dump_new(attempt/'review.proposed.json',review)
        guard.sample();guard.check()
        receipt={'schema':'PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_RECEIPT_V1','status':'COMPLETE_REFERENCE_CANDIDATE_PENDING_ACTUAL_C0_AND_ROOT_REVIEW',
            'calibration_reference':calibration_ref,'domain_reference':reference(attempt/'domain.json'),
            'proposed_review_reference':reference(attempt/'review.proposed.json'),'coverage_reference':coverage_ref,
            'eligibility_reference':eligibility_ref,'resource_plan':reference(plan_path),'scope_fingerprint':fingerprint,
            'actual_parent':{'endpoint':'218.192.171.238:22','uid':os.getuid(),'JobIDRaw':os.environ['SLURM_JOB_ID']},
            'actual_parent_C0_acceptance':'PENDING_ROOT_TERMINAL_ACCOUNTING','runtime':guard.receipt(),
            'new_geometry_UFF_QM_Pprime_or_R_N_fit':False,'full_D4_or_training_release_claimed':False,
            'mask_fraction_over_1_percent_is_report_only':True,
            'source_fields_over_1_percent_final_mask':[fid for fid,m in masks.items()if m['final_masked_records']/m['records']>.01]}
        if startup_proof is not None:receipt['launcher_startup_proof_reference']=reference(startup_proof)
        dump_new(attempt/'receipt.json',receipt);return receipt
    finally:
        guard.close();lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',type=Path)
    a=p.parse_args();run(a.plan,a.startup_proof)


if __name__=='__main__':main()
