"""Actual B3708 lineage and two-stage declaration of retained input bundles."""
from __future__ import annotations
import pathlib
from workflows.data_v1_final.export.native_body_frame32_v1 import contract as B
Q=B.Q;ROOT=B.ROOT;REPO=B.REPO;PY=B.PY;meta=B.meta;need=B.need;unique=B.unique;triple=B.triple
HERE=REPO/'workflows/data_v1_final/export/native_frame_summary32_v1'
FILES=('__init__.py','contract.py','metadata.py','reader.py','analysis.py','run.py','test_v1.py','README.md')
MODULE='workflows.data_v1_final.export.native_frame_summary32_v1.run'
WALL={'prepare':600,'summary':1800};CAP={'prepare':128<<20,'summary':512<<20};CALCS=B.CALCS


def scope(mode):need(mode in WALL,'EXACT_TWO_SUMMARY_MODES');return 'native_frame_summary32_'+mode+'_v1'


def parameters(mode):
    return {'mode':mode,'records':32,'conditions':12,'execution_keys':384,'workers':16,'source_fixture_methods':3,
        'all3_before_DATA_and_resource_observer':True,'original_QM_UFF_calls':0,'original_DATA_or_masks_modified':False,
        'reconstructed_input_bundle_open_allowed':mode=='summary','whole_DATA_SHA_fstat':True,
        'r73_AO_ATOMINDEX_basis_map_allowed':False,'r73_channel_onsite_duplicate_entry_ordinal_preserved':True,
        'r674_native_order':['xx','xy','yy','xz','yz','zz'],'native_values_parser_exact_replay':mode=='summary',
        'unit_sign_property_axis_unknown_not_PASS':True,'D1_jointly_frozen':False,
        'wall_seconds':WALL[mode],'whole_output_cap_bytes':CAP[mode],'cost_overrun_action':'REPORT_AND_CONTINUE'}


def parent(refs):
    body,plan,extra=B.actual_closure(refs,'body','NATIVE_BODY_FRAME32_OBSERVATIONS_V1',
        'FINITE_NATIVE_BODY_OBSERVED_PHYSICAL_CONVENTIONS_PENDING',B.MODULE,B.scope('body'),B.parameters('body'))
    need(body['job_id']=='4523708' and body['completed_key_observations']==body['observed_keys']==384
        and body['held_keys']==0 and body['raw_bundles_SHA_and_members_verified']==384
        and body['native_physical_axes_verified'] is False and body['D1_jointly_frozen'] is False,
        'ACTUAL_B3708_COMPLETE_NATIVE_OBSERVATIONS_NOT_PHYSICAL_ACCEPTANCE')
    gate=meta(body['fixtures6_reference'])
    need(gate['tests_run']==6 and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_B_ORIGINAL3_NEW3_PASSED')
    prepared,probe,loc,data,parents=B.derivation(plan)
    for ref in plan['source_references']:need(Q.pin(ref['path'])==ref,'ACTUAL_B_ORIGINAL_SOURCE_AND_METADATA_BYTES_STILL_EXACT')
    rows=body['record_evidence_references']
    need(len(rows)==384 and [r['position'] for r in rows]==list(range(384))
        and all(r['state']=='OBSERVED_NATIVE_EVIDENCE_PHYSICAL_CONVENTIONS_PENDING' and r['input_byte_binding_verified'] is True for r in rows),
        'EXACT384_RETAINED_B_EVIDENCE_REFERENCE_MATRIX')
    refs=unique([*extra,*parents,*plan['source_references'],plan['protocol_reference'],body['fixtures6_reference'],*prepared['input_authority_references'].values()])
    return body,plan,rows,refs


def expected_bundle_path(evidence_reference):return str(pathlib.Path(evidence_reference['path']).parent/'hash_verified_reconstructed_input.bundle')


def prepared(refs,body_refs):
    value,plan,extra=B.actual_closure(refs,'prepare','NATIVE_FRAME_SUMMARY32_INPUT_LOCATORS_V1','EXACT384_RETAINED_INPUT_BUNDLE_LOCATORS_NOT_OPENED',
        MODULE,scope('prepare'),parameters('prepare'))
    need(value['body_closure_references']==body_refs and plan['body_closure_references']==body_refs
        and value['input_bundles_opened']==0,'REAL_NEW_PREPARATION_NOT_FUTURE_INPUT_READ')
    body,_,rows,more=parent(body_refs);locators=value['locators']
    need(len(locators)==384 and [r['position'] for r in locators]==list(range(384)),'EXACT384_RETAINED_INPUT_LOCATORS')
    for loc,row in zip(locators,rows):
        need(loc['evidence_reference']==row['evidence_reference'] and loc['raw_reference']==row['raw_reference']
            and loc['input_reference']['path']==expected_bundle_path(row['evidence_reference']),'ONLY_SAME_CLOSED_B_OUTPUT_BUNDLE_PATH')
        triple(loc['input_reference'])
    need({r['calc_type'] for r in locators}==set(CALCS)
        and all(sum(r['calc_type']==c for r in locators)==32 for c in CALCS),'EXACT32_RECORDS_PER_ORIGINAL12_CONDITIONS')
    data=unique([triple(loc[key]) for loc in locators for key in ('evidence_reference','raw_reference','input_reference')])
    return value,data,unique([*extra,*more])


def derive(plan):
    body,oldplan,rows,refs=parent(plan['body_closure_references'])
    if plan['mode']=='prepare':return body,oldplan,rows,None,unique([triple(r['evidence_reference']) for r in rows]),refs
    prior,data,more=prepared(plan['input_locator_closure_references'],plan['body_closure_references'])
    return body,oldplan,rows,prior,data,unique([*refs,*more])


def source_paths():
    paths=[*(HERE/n for n in FILES),*B.source_paths()]
    need(all(p.exists() for p in paths),'ALL_NEW_AND_REUSED_NATIVE_SUMMARY_SOURCES_INSTALLED')
    return list(dict.fromkeys(paths))
