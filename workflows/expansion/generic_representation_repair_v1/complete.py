"""Complete original fullCommon using immutable1196003 rows plus reviewed119.

No old5h graph producer, RDKit, UFF or QM computation is executed here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from ..alpha_common_graph_continuation_v1 import io as I
from ..common_molecular_fp_candidate_v1.census import Census
from ..common_molecular_fp_main_v1.io import read_strict5_rows
from ..exact_nn_cached_v1 import alpha_common_repaired as Authority


def rows(ref,guard):
    body=I.Body(ref,guard)
    try:
        for raw in body.stream:
            guard.check();yield raw,json.loads(raw)
        body.check()
    finally:body.close()


def source_rows(ref,members,guard,kind):
    body=I.Body(ref,guard);values={}
    try:
        for raw in body.stream:
            guard.check();value=json.loads(raw);mid=value['molecule_id']
            I.need(mid in members and mid not in values and raw.endswith(b'\n'),'Original exact native Common source row with no duplicate')
            if kind=='features':I.need((value['effective_role'],value['native_records'])==members[mid],'Original feature MID/role/native count unchanged')
            values[mid]=raw
        body.check();return values,dict(reference=body.reference,frame=list(body.frame))
    finally:body.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    I.need(plan['schema']=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PLAN_V1'
      and proof['request']['producer_plan_reference']==Q.reference(a.plan) and proof['request']['execution_argv']==plan['execution_argv']
      and proof['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ['SLURM_JOB_ID']
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual independent new Alpha completion parent')
    for path in [Path(__file__),Path(Authority.__file__)]:I.need(Q.reference(path) in proof['request']['source_references'],'Actual completion/new consumer startup source pin')
    actual=admit(plan);validation,technical_review=Authority.validated(plan['repair_validation_receipt_reference'],plan['repair_validation_review_reference'])
    old=I.read(plan['original_full_source_receipt_reference']);old_review=I.read(plan['original_full_source_actual_accounting_reference'])
    I.need(old['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1' and str(old['job_id'])=='1885153'
      and old['result']['HOLD_MIDs']==119 and old['result']['strict5_rows']==1196003
      and old_review['producer_receipt_reference']==plan['original_full_source_receipt_reference']
      and old_review['full_reference_accepted'] is False,'Original immutable Common C0 with119 historical HOLDs')
    Authority.c0(old,dict(actual_parent=old_review['actual_parent'],actual_accounting_reference=plan['original_full_source_actual_accounting_reference']))
    native=I.read(validation['native_diagnostic_receipt_reference']);audit=I.read(native['origin']['audit_receipt'])
    I.need(audit['original_Common_receipt']==plan['original_full_source_receipt_reference'], 'Repair validation exact original5153 source lineage')
    oldplan=I.read(old['plan']);origin=I.read(oldplan['origin_input_manifest_reference'])
    mapping={row['origin_reference']['path']:row['destination_reference'] for row in oldplan['transport_bindings']}
    common=I.read(old['result']['Alpha_common_manifest_copy'])
    refs=[mapping[ref['path']] for ref in common['membership_tables']]
    I.need(len(refs)==16,'Exact full16 original membership parts')
    out=Path(plan['output_directory']);I.need(not out.exists(),'Fresh fullCommon completion output preserving all old artifacts');out.mkdir(parents=True);guard=Guard(plan)
    try:
        members={};frames=[];denominator=excluded=physical=0
        for ref in refs:
            body=I.Body(ref,guard)
            try:
                pf=body.parquet()
                for batch in pf.iter_batches(columns=['molecule_id','effective_role','records','common_population'],batch_size=8192,use_threads=False):
                    guard.check();body.check()
                    for row in batch.to_pylist():
                        physical+=1;role=row['effective_role']
                        I.need(type(row['common_population']) is bool,'Original exact membership boolean required')
                        if role in ('TRAIN','VAL'):
                            denominator+=1;excluded+=not row['common_population']
                        if row['common_population']:
                            mid=row['molecule_id'];I.need(mid not in members and role in ('TRAIN','VAL')
                              and type(row['records']) is int and row['records']>0,'Unique exact original Common MID and native integer count')
                            members[mid]=(role,row['records'])
                body.check();frames.append(dict(reference=body.reference,frame=list(body.frame)))
            finally:body.close()
        I.need(len(members)==1196122 and denominator==1214218 and excluded==18096,'Full original denominator/exclusions/Common, not a subset')
        census=Census()
        for mid in sorted(members):census.add(mid,*members[mid])
        expected=census.result();I.need(expected==old['result']['expected_all_common_census'],'Exact original full native MID/role/record digest')
        repairs={}
        for raw,value in rows(validation['repaired119_complete_features'],guard):
            mid=value['molecule_id'];I.need(mid in members and mid not in repairs and members[mid]==('TRAIN',value['native_records'])
              and value['independent_native_all_non_generic_values_exactly_equal'] is True
              and value['independent_native_generic_keys_exactly_equal'] is True,'Only validated119 single-source repairs')
            f=value['features'];provenance=value['repair_provenance']
            I.need(provenance['representation_repair_applied'] is True and provenance['original_kernel_passed'] is False
              and provenance['original_error']['type']=='AtomValenceException' and f['reasons']==[], 'Retain actual original failure and separate successful representation repair')
            repairs[mid]=value
        I.need(len(repairs)==119 and sum(v['native_records'] for v in repairs.values())==352,'Exact119/352 reviewed repair mass')
        old_projection,projection_frame=source_rows(old['result']['projection'],members,guard,'projection')
        old_features,feature_frame=source_rows(old['result']['structural_features'],members,guard,'features')
        original_set=set(members)-set(repairs)
        I.need(len(original_set)==1196003 and set(old_projection)==set(old_features)==original_set,'Every old successful MID reused once, every119 repair added once')
        projection=out/'strict5_projection.DATA.jsonl';features=out/'structural_features.DATA.jsonl'
        with projection.open('xb') as pstream,features.open('xb') as fstream:
            for mid in sorted(members):
                guard.check()
                if mid in repairs:
                    value=repairs[mid];f=value['features'];pvalue={key:f[key] for key in ('full_key','ecfp4_2048_hex','generic_murcko','generic_ring_systems')};pvalue['molecule_id']=mid
                    fvalue=dict(f,molecule_id=mid,effective_role=members[mid][0],native_records=members[mid][1])
                    praw=I.canonical(pvalue);fraw=I.canonical(fvalue)
                else:praw=old_projection.pop(mid);fraw=old_features.pop(mid)
                pvalue=json.loads(praw);fvalue=json.loads(fraw)
                I.need(all(pvalue[key]==fvalue[key] for key in ('molecule_id','full_key','ecfp4_2048_hex','generic_murcko','generic_ring_systems')),
                  'Every old and repaired strict5 value must equal its full feature source row')
                pstream.write(praw);fstream.write(fraw)
            for stream in (pstream,fstream):stream.flush();os.fsync(stream.fileno())
        I.need(not old_projection and not old_features,'All original raw row bytes consumed unchanged')
        output_refs=[I.pin(projection,guard.check),I.pin(features,guard.check)];readbacks=[]
        pbody=I.Body(output_refs[0],guard)
        try:
            count,observed=read_strict5_rows(pbody.stream,lambda mid:members.get(mid))
            I.need(count==1196122 and observed==expected,'Original strict5 readback with exact full dictionary membership, no remote point queries')
            readbacks.append(dict(reference=pbody.reference,frame=list(pbody.frame)));pbody.check()
        finally:pbody.close()
        fbody=I.Body(output_refs[1],guard);seen=set();feature_census=Census()
        try:
            previous=None
            for raw in fbody.stream:
                guard.check();row=json.loads(raw);mid=row['molecule_id']
                I.need(mid in members and mid not in seen and (previous is None or previous<mid)
                  and (row['effective_role'],row['native_records'])==members[mid],'Exact sorted feature full MID/role/native records')
                seen.add(mid);previous=mid;feature_census.add(mid,*members[mid])
            I.need(len(seen)==1196122 and feature_census.result()==expected,'Whole feature readback census')
            fbody.check();readbacks.append(dict(reference=fbody.reference,frame=list(fbody.frame)))
        finally:fbody.close()
        result=dict(schema='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_COMPONENT_V1',
          status='COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_TECHNICAL_REVIEW',HOLD_MIDs=0,historical_HOLD_MIDs=119,strict5_rows=1196122,
          expected_all_common_census=expected,observed_projection_census=observed,membership_census=expected,
          projection=output_refs[0],structural_features=output_refs[1],common_population_manifest=old['result']['Alpha_common_manifest_copy'],
          fingerprint_recipe='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',representation_version=validation['representation_version'],
          merge_counts=dict(original_rows_reused=1196003,single_variant_repaired_rows=119,final_rows=1196122),
          original_successful_row_bytes_preserved=True,original_output_file_bytes_unchanged_claimed=False,
          all_repaired119_source_bound=True,new_UFF_QM_calls=0,old_HOLDs_and_old_receipts_preserved=True,
          membership_input_current_SHA_frames=frames,reused_source_current_SHA_frames=[projection_frame,feature_frame],
          all_output_journals_current_SHA_readback=readbacks,full_original_membership_physical_rows=physical,
          original_execution_UNKNOWN3436_excluded=True,original_source_graph_stage_reexecuted=False)
        producer=dict(schema=Authority.PRODUCER,mode='full_common_completion',uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],
          plan=Q.reference(a.plan),startup_proof=Q.reference(a.startup_proof),profile_admission=actual,result=result,
          original_full_source_receipt_reference=plan['original_full_source_receipt_reference'],
          original_full_source_actual_accounting_reference=plan['original_full_source_actual_accounting_reference'],
          repair_validation_receipt_reference=plan['repair_validation_receipt_reference'],repair_validation_review_reference=plan['repair_validation_review_reference'],
          Main_origin_parent_C0_claimed=False,old_artifacts_modified=False,all_final_orders_or_D7_release=False,runtime=guard.receipt())
        Authority.component_ready(producer)
        I.save(out/'receipt.json',producer)
    finally:guard.close()


if __name__=='__main__':main()
