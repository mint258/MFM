"""Closed-source coverage checks; scope dispositions require a real prior reply."""
import ast
import collections
import csv
import io
import json
from .reader import S,triple,MAIN,ALPHA

FIELDS=('dataset','status','version','required_roles','required_subdatasets','raw_artifacts','identities','coverage_evidence')


def parent(reader,ref,job,endpoint,uid):
    account=reader.json(ref)
    S.need(account['endpoint']==endpoint and account['uid']==uid and account['query_returncode']==0,'ORIGINAL_PARENT_ENDPOINT_UID_NOT_CURRENT_ALPHA_IDENTITY')
    if account.get('raw_sacct_reference'):raw=reader.read(account['raw_sacct_reference']).decode()
    else:raw=account.get('actual_sacct')
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|')) if raw else account.get('actual_parents',[account.get('actual_parent',{})])
    matched=[r for r in rows if str(r.get('JobIDRaw'))==str(job)]
    S.need(len(matched)==1 and matched[0]['State']=='COMPLETED' and matched[0]['ExitCode']=='0:0'
           and str(matched[0]['UID'])==str(uid),'ACTUAL_ORIGINAL_SOURCE_PARENT_C0')
    return matched[0]


def domain(reader,value,C):
    S.need(value['schema']=='FROZEN_X02_CANDIDATE_DOMAIN_AUTHORITY_V1'
           and value['allowed_atomic_numbers']==list(C.X02_ATOMIC_NUMBERS)
           and value['per_candidate_elements_and_composition_enforcement_required'] is True
           and value['closed_screen_authority_references'],'EXACT_ORIGINAL_X02_DOMAIN_AUTHORITY')
    raw=reader.read(value['screen_source_reference']);tree=ast.parse(raw.decode('utf-8-sig'))
    values=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='WHITELIST' for t in n.targets)]
    S.need(values==[set(C.X02_ATOMIC_NUMBERS)],'FROZEN_SCREEN_WHITELIST_AST_UNCHANGED')
    for ref in value['closed_screen_authority_references']:reader.verify(ref)


def molnet(reader,manifest,source,C):
    review=reader.json(manifest['root_molnet21_acceptance_reference'])
    S.need(review['schema']=='ROOT_MOLNET21_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1'
           and review['status']=='APPROVED_FOR_CLOSED21_CONSERVATIVE_EXCLUSION_V2' and review['reviewer']=='root'
           and review['original_identity_unknowns_and_all_physical_rows_retained'] is True
           and review['full_filtered_pool_release_authorized'] is False,'EXISTING_ACTUAL_MOLNET_ROOT_ADOPTION')
    receipt=reader.json(review['receipt_reference']);account=parent(reader,review['accounting_reference'],receipt['job_id'],MAIN,1278)
    S.need(receipt['schema']=='MOLNET21_CONSERVATIVE_CLOSURE_RECEIPT_V1'
           and receipt['status']=='CANDIDATE_EVIDENCE_CLOSED_PENDING_ROOT_C0_ADOPTION'
           and receipt['READY_or_pool_release'] is False and receipt['uid']==1278 and receipt['endpoint']==MAIN,
           'UNCHANGED_ACTUAL_MAIN_CLOSURE_NOT_ALPHA_PRODUCER')
    f=receipt['fixtures'];S.need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ORIGINAL_THREE_NATIVE_MOLNET_FIXTURES')
    proof=reader.json(receipt['startup_proof_reference']);old_plan=reader.json(receipt['plan_reference']);request=reader.json(proof['request_reference'])
    S.need(proof['request']==request and str(proof['job_id'])==str(receipt['job_id']) and proof['uid']==1278
           and request['scope_key']=='moleculenet21_conservative_closure_v1'
           and request['scope_parameters']==old_plan['scope_parameters'] and request['cpus']==16
           and receipt['node']==proof['node']==request['node']==old_plan['node']
           and request['execution_argv']==['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m',
               'workflows.expansion.moleculenet21_conservative_closure_v1.closure','--plan',receipt['plan_reference']['path'],
               '--startup-proof',receipt['startup_proof_reference']['path']], 'ORIGINAL_FULL_MOLNET_PLAN_ARGV_PROOF')
    result=receipt['result'];S.need(result['cases']==result['original_identity_UNKNOWN_cases']==21
           and result['remaining_exclusion_HOLD']==0 and result['complete_exclusion_coverage_candidate'] is True
           and result['original_graph_statuses_modified'] is False and result['policy_reference']==receipt['policy_reference']
           and result['candidate_domain_authority']==manifest['candidate_domain_authority'],'EXACT_CLOSED21_UNKNOWN_RETAINED')
    S.need(reader.json(result['report_reference'])=={k:v for k,v in result.items() if k!='report_reference'},'WHOLE_CLOSED_MOLNET_REPORT')
    reader.verify(result['policy_reference']);domain(reader,result['candidate_domain_authority'],C)
    base=reader.json(result['base_coverage_reference'])
    S.need(source['status']=='READY_FOR_CONSERVATIVE_EXCLUSION_V3' and source['required_roles']==['all']
           and source['required_subdatasets']==base['covered_subdatasets']
           and source['identity_parts']==[result['base_strict5_reference'],result['overlay_reference']]
           and source['raw_artifacts']==result['raw_artifacts'] and source['coverage_evidence']==result['report_reference']
           and source['lower_bounds']==result['lower_bound_reference'] and source['physical_dispositions']==result['physical_dispositions_reference'],
           'COMPLETE_ORIGINAL_ALL17_BASE_OVERLAY_BOUNDS_AND_LEDGER')
    ledger=list(reader.rows(result['physical_dispositions_reference']))
    expected={'AUTHOR_SOURCE_INVALID_MOLECULAR_INPUT':15,'CANDIDATE_DOMAIN_DISJOINT_X02':3,
              'CONSERVATIVE_LOWER_BOUND_COVERED':2,'CONSERVATIVE_ARG_AND_CURRENT_COMPONENT_UNION_COVERED':1}
    S.need(len(ledger)==21 and len({r['binding']['hold_ordinal'] for r in ledger})==21
           and all(r['original_identity_resolution']=='UNKNOWN_UNCHANGED' for r in ledger)
           and collections.Counter(r['new_exclusion_status'] for r in ledger)==expected,'ALL21_ORIGINAL_PHYSICAL_DISPOSITIONS')
    return dict(ledger=ledger,expected_rules=2,policy=result['policy_reference'],original_parent=account,
        receipt_reference=review['receipt_reference'])


def original735(reader,closed):
    receipt=reader.json(closed['original735_receipt_reference'])
    S.need(receipt['schema']=='COCONUT_ALPHA_NATIVE735_PRODUCER_V1'
           and receipt['profile_admission']['endpoint']==ALPHA and receipt['profile_admission']['uid']==1264
           and receipt['result']['DATA']==closed['original735_DATA_reference'],'ACTUAL_ORIGINAL735_NATIVE_DATA_AUTHORITY')
    parent(reader,closed['original735_actual_accounting_reference'],receipt['profile_admission']['job_id'],ALPHA,1264)
    result={}
    for row in reader.rows(closed['original735_DATA_reference']):
        src=row['source'];identifier=json.loads(src['identity_fields_json'])['id']
        sid='entries:'+identifier+':'+str(src['copy_block'])+':'+str(src['source_row_ordinal'])
        S.need(sid not in result and src['source_table']=='entries' and row['original_UNKNOWN_unchanged'] is True,'UNIQUE_ORIGINAL_UNKNOWN735_PHYSICAL_SOURCE')
        result[sid]={k:src[k] for k in ('source_table','copy_block','source_row_ordinal','source_row_sha256')}
    S.need(len(result)==735,'ALL_ORIGINAL735_SOURCE_IDS_NOT_A_SUBSET');return result


def scope_authority(reader,ref,scoped,expected):
    authority=reader.json(ref)
    S.need(authority['schema']=='ROOT_COCONUT_SOURCE_SCOPE_ACTUAL_APPROVAL_V1'
           and authority['status']=='ACTUAL_USER_APPROVAL_RECORDED' and authority['reviewer']=='root'
           and authority['actual_user_reply_observed'] is True and authority['original_records_retained'] is True
           and authority['original_graph_unknowns_retained'] is True
           and len(authority['approved_source_ids'])==len(set(authority['approved_source_ids']))
           and set(authority['approved_source_ids'])==set(scoped),'ACTUAL_USER_APPROVED_EXACT_SCOPE_IDS_REQUIRED_NOT_PENDING_PROPOSAL')
    reply=reader.json(authority['actual_user_reply_reference'])
    S.need(reply['role']=='user' and isinstance(reply['text'],str) and reply['text'].strip(),'ACTUAL_USER_REPLY_SOURCE_NOT_ASSISTANT_OR_EMPTY')
    audit=reader.json(authority['audit_receipt_reference']);admission=audit['profile_admission']
    S.need(audit['schema']=='COCONUT_ALPHA_STRUCTURAL_AUDIT_PRODUCER_V1'
           and audit['result']['DATA']['rows']==735 and admission['endpoint']==ALPHA and admission['uid']==1264,
           'ACTUAL_COMPLETE735_STRUCTURAL_AUDIT_NOT_GRAPH_DISPOSAL_INFERENCE')
    parent(reader,authority['audit_actual_accounting_reference'],admission['job_id'],ALPHA,1264)
    seen=set()
    for row in reader.rows(audit['result']['DATA']):
        sid=row['original_source_id'];src=row['original_source']
        S.need(sid in expected and sid not in seen and all(src[k]==v for k,v in expected[sid].items())
               and row['world_nonexistence_inferred'] is False,'WHOLE_AUDIT_BOUND_TO_ORIGINAL735_RECORDS')
        seen.add(sid)
    S.need(seen==set(expected),'COMPLETE_SCOPE_AUDIT_SOURCE_CENSUS');return authority


def coconut(reader,manifest,source,C):
    review=reader.json(manifest['root_coconut735_acceptance_reference'])
    S.need(review['schema']=='ROOT_COCONUT735_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1'
           and review['status']=='APPROVED_FOR_CLOSED735_CONSERVATIVE_EXCLUSION_V3' and review['reviewer']=='root'
           and all(review[k] is True for k in ('original_unknowns_retained','all_original735_rows_exclusion_covered',
               'no_source_records_dropped','no_guessed_keys','veto_impact_measured_on_complete_candidate_pool')),
           'EXISTING_COMPLETE735_ROOT_SOURCE_REVIEW_REQUIRED')
    closed=reader.json(review['coverage_reference'])
    S.need(closed['schema']=='COCONUT735_ACCEPTED_EXCLUSION_COVERAGE_V1' and closed['physical_unknown_rows']==735
           and closed['remaining_exclusion_HOLD']==0 and closed['all_physical_source_rows_retained'] is True
           and closed['original_graph_identities_repaired'] is False,'COMPLETE735_LEDGER_CLOSURE_NOT_735_GRAPH_PROMOTION')
    impact=reader.json(review['veto_impact_reference'])
    S.need(impact['complete_candidate_pool'] is True and impact['input_unique_molecules']>0
           and impact['eligible_after_all_exclusions']>0 and impact['no_universal_or_empty_bound'] is True,
           'ACTUAL_FULL_POOL_IMPACT_OF_ACCEPTED_RULES_NOT_UNADOPTED_COS_PROPOSAL')
    S.need(source['status']=='READY_FOR_CONSERVATIVE_EXCLUSION_V3' and source['version']==closed['source_version']
           and all(source[k]==closed[k] for k in ('required_roles','required_subdatasets','raw_artifacts','identity_parts','lower_bounds','physical_dispositions'))
           and source['coverage_evidence']==review['coverage_reference'],'EXACT_COMPLETE_ACCEPTED_COCONUT_SOURCE_BINDINGS')
    expected=original735(reader,closed);ledger=list(reader.rows(closed['physical_dispositions']));seen=set();scoped=set();identity_ids=set();rule_ids=set()
    statuses={'EXACT_COMPOSITION_COVERED','CONSERVATIVE_LOWER_BOUND_COVERED','CANDIDATE_DOMAIN_DISJOINT_X02','APPROVED_SOURCE_SCOPE_DISPOSITION'}
    for row in ledger:
        sid=row['source_id'];binding=row['binding'];status=row['new_exclusion_status']
        S.need(sid in expected and sid not in seen and all(binding[k]==v for k,v in expected[sid].items())
               and row['original_identity_resolution']=='UNKNOWN_UNCHANGED' and row['evidence_references']
               and status in statuses,'EACH_ORIGINAL735_HAS_ONE_SOURCE_BOUND_ACCEPTED_DISPOSITION')
        seen.add(sid)
        for ref in row['evidence_references']:reader.verify(ref)
        if status=='EXACT_COMPOSITION_COVERED':
            S.need(row['identity_source_ids'] and not row.get('rule_ids'),'COMPOSITION_ONLY_REFERENCE_NOT_INVENTED_BOUND')
            identity_ids.update(row['identity_source_ids'])
        elif status=='CONSERVATIVE_LOWER_BOUND_COVERED':
            S.need(row['rule_ids'] and not row.get('identity_source_ids'),'SOURCE_BOUND_POSITIVE_RULE_REFERENCE')
            rule_ids.update(row['rule_ids'])
        elif status=='CANDIDATE_DOMAIN_DISJOINT_X02':
            counts=C.vector(row['fixed_non_H_atom_observation'])
            S.need(set(counts)-set(C.X02_ATOMIC_NUMBERS) and not row.get('rule_ids') and not row.get('identity_source_ids'),
                   'EXPLICIT_OUTSIDE_X_SOURCE_ATOMS_NOT_TRUNCATED_INTO_BOUNDS')
        else:
            S.need(row['not_a_chemical_exclusion_rule'] is True and not row.get('rule_ids') and not row.get('identity_source_ids'),
                   'SCOPE_DISPOSITION_DOES_NOT_INVENT_CHEMICAL_IDENTITIES_OR_RULES')
            scoped.add(sid)
    S.need(len(ledger)==735 and seen==set(expected),'ALL_ORIGINAL735_RETAINED_ON_PHYSICAL_LEDGER')
    authority=None
    if scoped:authority=scope_authority(reader,closed['source_scope_authority_reference'],scoped,expected)
    return dict(ledger=ledger,expected_rule_ids=rule_ids,expected_identity_source_ids=identity_ids,
        scope_source_ids=scoped,source_scope_authority=authority,coverage=closed,
        disposition_counts=dict(collections.Counter(r['new_exclusion_status'] for r in ledger)))


def approvals(reader,manifest,ready9,C):
    S.need(manifest['schema']=='expansion_decontamination_sources_with_constraints_v3'
           and manifest['status']=='ALL11_SOURCE_EVIDENCE_COMPOSED_PENDING_ACTUAL_INDEX_AND_FILTER'
           and len(manifest['sources'])==11 and {s['dataset'] for s in manifest['sources']}==C.legacy.REQUIRED
           and manifest['original_graph_unknowns_retained'] is True and manifest['ranking_uses_downstream_features'] is False,
           'EXACT_ALL11_COMPLETE_SOURCE_MANIFEST_NOT_READY9_OR_SCOPE_PROPOSAL')
    source={s['dataset']:s for s in manifest['sources']};old={s['dataset']:s for s in ready9['sources']}
    for name in C.legacy.REQUIRED-{'moleculenet','coconut'}:
        S.need({k:source[name].get(k) for k in FIELDS}=={k:old[name].get(k) for k in FIELDS}
               and source[name]['status']=='READY','ORIGINAL_NINE_ALL_SPLIT_SOURCE_BINDINGS_UNCHANGED '+name)
    return source,molnet(reader,manifest,source['moleculenet'],C),coconut(reader,manifest,source['coconut'],C)
