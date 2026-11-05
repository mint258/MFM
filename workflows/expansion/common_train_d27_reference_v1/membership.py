"""Explicit membership-only Root authority; never an exact-FP reference waiver."""
import re
from ..common import load
from ..portable_sources_v1.transport import verify
from ..exact_nn_cached_v1.alpha_common import MOLECULES,ROLES,RECORDS
from .inventory import need


def component(p):
    need(p.get('schema')=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1'and p.get('mode')=='full'
        and p.get('uid')==1264 and p.get('full_population_graph_computed')is True
        and p.get('Main_origin_parent_state')=='STOPPED'and p.get('Main_origin_parent_C0_claimed')is False
        and p.get('common_scientific_membership_rules_changed')is False and p.get('new_UFF_QM_calls')==0,
        'Actual full Alpha scanner producer required; source-only or fake Main C0 is forbidden')
    admission=p['profile_admission']
    need(admission.get('endpoint')=='218.192.171.238:22'and admission.get('uid')==1264
        and str(admission.get('job_id'))==str(p['job_id'])and admission.get('workers')==16,'Actual Alpha scanner admission required')
    c=p['result'];expected=c['expected_all_common_census'];observed=c['scan']['all_common_observed_census']
    need(c['schema']=='ALPHA_FULL_COMMON_GRAPH_COMPONENT_V1'and expected==observed
        and expected['molecules']==MOLECULES and expected['molecules_by_role']==ROLES
        and expected['native_records_by_role']==RECORDS
        and re.fullmatch('[0-9a-f]{64}',expected.get('sorted_length_prefixed_MID_role_sha256',''))is not None
        and c['scan']['selected_MIDs']==MOLECULES
        and c['scan']['formal_MIDs_contiguous_with_no_recurrence']is True,
        'Complete original pre-descriptor Common MID/role/native-record census and hash required')
    need(len(c['input_current_SHA_frames'])==33 and len(c['actual_worker_proofs'])==16
        and len({r['path']for r in c['actual_worker_proofs']})==16
        and c.get('geometry_bodies_transported_or_revalidated')is False,
        'Actual33 source reads/16 workers and truthful inherited geometry evidence required')
    for item in c['input_current_SHA_frames']:
        frame=item['current_Alpha_frame'];ref=item['destination_reference']
        need(len(frame)==7 and frame[2]==1264 and frame[3]==1 and frame[4]==ref['bytes']>0,'Actual Alpha source FD ownership and byte count required')
    return c


def accepted(reference):
    review=load(verify(reference))
    need(review.get('schema')=='ROOT_ALPHA_FULL_COMMON_MEMBERSHIP_ACTUAL_ACCEPTANCE_V1'
        and review.get('status')=='APPROVED_EXACT_FULL_COMMON_MEMBERSHIP_ONLY'and review.get('reviewer')=='root'
        and review.get('Main_parent_C0_claimed')is False and review.get('graph_reference_accepted')is False
        and review.get('geometry_bodies_revalidated_on_Alpha')is False
        and review.get('original_membership_rules_unchanged')is True
        and review.get('complete_native_and_sufficient_ordinary_Sprime_evidence_reviewed')is True
        and review.get('unknown_or_graph_HOLD_not_promoted_or_dropped')is True,
        'Independent actual Root membership-only acceptance required; no automatic graph waiver')
    p=load(verify(review['producer_receipt']));c=component(p);parent=review['actual_parent']
    need(parent.get('endpoint')=='218.192.171.238:22'and parent.get('uid')==1264
        and str(parent.get('JobIDRaw'))==str(p['job_id'])and parent.get('State')=='COMPLETED'and parent.get('ExitCode')=='0:0',
        'Actual Alpha C0 required for membership; Main STOPPED is not C0')
    accounting=load(verify(review['actual_accounting_reference']))
    need(parent in accounting['actual_parents'],'Real membership parent must occur in independent terminal accounting')
    need(review['graph_HOLD_MIDs_retained']==c['HOLD_MIDs']
        and review['source_identity_journal_reference']==c['source_journal']
        and review['original_membership_evidence_reference']==c['Alpha_common_manifest_copy'],
        'Every descriptor failure remains in the exact complete membership evidence')
    source=load(verify(p['source_tests']));io=load(verify(p['grouped_io_source_tests']))
    need(source['tests']==6 and source['failures']==source['errors']==source['skips']==0
        and source['fresh_spawn_workers']==16 and source['synthetic_tasks']==64
        and io['tests']==3 and io['failures']==io['errors']==io['skips']==0,'Actual source6/IO3/fresh16-worker fixtures required')
    plan=load(verify(p['plan']));startup=load(verify(p['startup_proof']))
    need(plan['mode']=='full'and str(startup['job_id'])==str(p['job_id'])
        and startup['request']['producer_plan_reference']==p['plan'],'Exact actual full producer plan/startup binding required')
    for ref in c['actual_worker_proofs']:
        worker=load(verify(ref));need(worker['uid']==1264 and str(worker['job_id'])==str(p['job_id'])
            and worker['original_function_objects_checked_in_this_worker']is True,'Actual worker scientific-source identity required')
    header=load(verify(c['Alpha_common_manifest_copy']))
    need(header['denominator_molecules']==1214218 and header['excluded_molecules']==18096
        and header['execution_unresolved_molecules']==3436 and header['pilot_only']is False
        and len(header['physical_geometry_tables'])==32 and len(header['uff_identity_tables'])==16,
        'Original complete membership/geometry-source scope and UNKNOWN exclusions required')
    role_rows={row['effective_role']:row for row in header['roles']}
    need(set(role_rows)==set(ROLES)and all(role_rows[r]['molecules']==ROLES[r]and role_rows[r]['pm7_records']==RECORDS[r]for r in ROLES),
        'Original frozen TRAIN/VAL roles and native-record header required')
    return p,c,review
