"""Actual3953→3878/B32 parents; only their exact1152 DATA locators."""
from __future__ import annotations
import hashlib
from pathlib import Path
from workflows.data_v1_final.export.native_frame_summary32_v1 import contract as S

Q=S.Q;ROOT=S.ROOT;REPO=S.REPO;PY=S.PY;need=S.need;meta=S.meta;unique=S.unique;triple=S.triple
HERE=REPO/'workflows/data_v1_final/export/native_precision384_v1'
FILES=('__init__.py','contract.py','metadata.py','precision.py','reader.py','run.py','test_v1.py','README.md')
MODULE='workflows.data_v1_final.export.native_precision384_v1.run'
SCOPE='native_precision384_readonly_v1';WALL=7200;CAP=1<<30;RESERVE=192<<20
TAG='26b28010e805f7d1aeeef39813feb473e69cc4be'
OFFICIAL_PATHS={'src/type/molecule.f90','src/setparam.f90','src/scc_core.f90','src/prog/main.F90','src/main/property.F90'}


def parameters():
    return {'records':32,'conditions':12,'execution_keys':384,'exact_retained_DATA_files':1152,'worker_threads':16,
        'new_source_boundary_methods':3,'all3_before_DATA_and_monitor':True,'original_QM_UFF_calls':0,
        'complete_label_parser_replayed':False,'engine_or_worker_initialized':False,
        'direct_residual_and_conditional_printing_intervals_only':True,'f12_3_trace_bound_is_QC':False,
        'fit_centering_rotation_permutation_or_repair':False,'original_tolerances_or_masks_modified':False,
        'native_units_sign_origin_axes_accepted':False,'D1_jointly_frozen':False,'full20k_completed':False,
        'wall_seconds':WALL,'whole_output_cap_bytes':CAP,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def official(reference,summary):
    value=meta(reference)
    need(value['schema']=='OFFICIAL_XTB671_EXACT_CALLCHAIN_SOURCE_ACQUISITION_V1'
        and value['status']=='ALL5_PUBLIC_TAG_BLOB_SHA1_AND_FULL_BYTE_SHA256_VERIFIED_SOURCE_ONLY'
        and value['tag_commit']==TAG and {r['source_path'] for r in value['entries']}==OFFICIAL_PATHS
        and len(value['entries'])==5,'ACTUAL_EXACT_OFFICIAL5_SOURCE_CONTEXT_NOT_PHYSICS')
    refs=[reference]
    for row in value['entries']:
        ref=row['local_reference'];raw=Q.read_small(ref['path']);need(Q.pin(ref['path'])==ref,'OFFICIAL_SOURCE_FULL_SHA_BYTES')
        need(row['source_url']=='https://github.com/grimme-lab/xtb/blob/'+TAG+'/'+row['source_path']
            and hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()==row['git_blob_sha1'],
            'EXACT_TAG_GIT_BLOB_SOURCE_BYTES')
        refs.append(ref)
    aes=[r for r in summary['official_context_source_references'] if r['path'].endswith('/xtb_v6_7_1_aespot.f90')]
    need(len(aes)==1 and aes[0]['bytes']==38736 and aes[0]['sha256']=='155da3359cc01a0d8afc3b86f28bfaf2ecffbfc07ae8d2117423249b7455a5c8','ORIGINAL_OFFICIAL_AESpot_CONTEXT')
    raw=Q.read_small(aes[0]['path']);need(Q.pin(aes[0]['path'])==aes[0]
        and hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()=='c10d90b672c482026a69e78c9879349cccac0df8','OFFICIAL_AESpot_FULL_SHA_AND_GIT_BLOB')
    return [*refs,*aes]


def derive(plan):
    summary,sp,extra=S.B.actual_closure(plan['summary_closure_references'],'summary','NATIVE_FRAME_SUMMARY32_OBSERVATIONS_V1',
        'EXACT384_NATIVE_PARSER_INPUT_DOMAIN_STATISTICS_OBSERVED_PHYSICAL_D1_REVIEW_PENDING',S.MODULE,S.scope('summary'),S.parameters('summary'))
    need(summary['job_id']=='4523953' and summary['completed_key_observations']==384 and summary['held_keys']==0
        and summary['native_units_sign_property_axes_accepted'] is False and summary['D1_jointly_frozen'] is False,'ACTUAL3953_NO_PHYSICAL_OR_JOINT_ACCEPTANCE')
    need(all(r['records']==r['original_parser_exact_records']==r['actual_original_input_binding_exact_records']==32
        and r['held_keys']==0 for r in summary['per_condition_counts']) and len(summary['per_condition_counts'])==12,'ACTUAL384_FULL_PARSER_INPUT_BINDING_PARENT')
    body,bp,rows,prepared,data,parents=S.derive(sp)
    need(body['job_id']=='4523708' and prepared['job_id']=='4523878' and len(prepared['locators'])==384
        and len(data)==1152 and data==sp['data_references'],'EXACT1152_CLOSED_B32_PREPARED_LOCATORS_NOT_NEW_DATA')
    for r in data:triple(r)
    refs=unique([*extra,*parents,*official(plan['official_callchain_acquisition_reference'],summary),
        summary['fixtures3_reference'],*sp['source_references']])
    return summary,bp,prepared['locators'],data,refs


def source_paths():return list(dict.fromkeys([*(HERE/n for n in FILES),*S.source_paths()]))
