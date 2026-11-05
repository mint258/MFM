"""Exact physical735 partition; chemistry and original UNKNOWNs are unchanged."""
import collections
import hashlib
import json

EXPECTED={'FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL':3,
          'OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS':3,
          'SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE':729}
BINDING=('source_table','copy_block','source_row_ordinal','source_row_sha256')
PROPOSAL='44f8d7eb53cb8e45687b132aa88bb7dda17c1aa2'


def need(value,message):
    if not value:raise ValueError(message)


def source_id(src):
    identifier=json.loads(src['identity_fields_json'])['id']
    need(src['source_table']=='entries','ORIGINAL_ENTRIES_ONLY')
    return 'entries:'+identifier+':'+str(src['copy_block'])+':'+str(src['source_row_ordinal'])


def approval(value,proposal):
    need(value['schema']=='PUBCHEM_COCONUT_MOLECULAR_SCOPE_USER_APPROVAL_V1'
         and value['status']=='USER_APPROVED_EXACT_732_WITH_FULL_AUDIT_RETAINED'
         and value['proposal_public_commit']==PROPOSAL
         and value['user_answer_verbatim']=='批准，仅隔离这 732 条并保留审计'
         and value['approved_scope_dispositions']==732
         and value['provided_structure_underspecified']==729
         and value['official_abstract_or_nonmolecular_entries']==3
         and value['recovered_specific_molecules_retained']==3
         and all(value[k] is True for k in ('all_other_COCONUT_rows_retained',
             'all_original_text_and_per_row_audit_retained','only_exact_proposal_records_may_be_scoped_out'))
         and value['chemical_X_or_key_or_fingerprint_rules_changed'] is False,'EXACT_ACTUAL732_USER_AUTHORIZATION')
    need(proposal['schema']=='COCONUT_FINITE_MOLECULAR_SOURCE_SCOPE_PROPOSAL_V1'
         and proposal['partition_counts']==EXPECTED and proposal['rows']==735
         and proposal['source_records_deleted']==0 and not proposal['insufficient_evidence_source_ids'],
         'EXACT_FROZEN735_PROPOSAL_NO_NEW_SCOPE_INFERENCE')
    scoped=proposal['proposed_quarantined_source_ids']
    need(len(scoped)==len(set(scoped))==732
         and len(proposal['retained_exact_source_recovery_ids'])==3
         and not set(scoped)&set(proposal['retained_exact_source_recovery_ids']),
         'EXACT732_APPROVED_IDS_THREE_RETAINED')
    # The public proposal's digest is produced by its original canonical helper.
    from_text=('\n'.join(sorted(scoped))+'\n').encode()
    need(hashlib.sha256(from_text).hexdigest()==proposal['proposed_source_id_set_sha256'],
         'FROZEN_PROPOSAL_SOURCE_ID_SET_SHA256')
    return set(scoped)


def assemble(originals,audit,proposal,user_approval,primary,overlay,evidence):
    """Inputs have already been read through immutable, whole-SHA-owned FDs."""
    scoped=approval(user_approval,proposal)
    expected={}
    for row in originals:
        src=row['source'];sid=source_id(src)
        need(sid not in expected and row['original_UNKNOWN_unchanged'] is True,'UNIQUE_ORIGINAL735_UNKNOWN_RETAINED')
        expected[sid]={k:src[k] for k in BINDING}
    need(len(expected)==len(originals)==735,'WHOLE_ORIGINAL735_NOT_SUBSET')
    by_audit={}
    for row in audit:
        sid=row['original_source_id'];src=row['original_source']
        need(sid in expected and sid not in by_audit and row['world_nonexistence_inferred'] is False
             and all(src[k]==v for k,v in expected[sid].items()),'EXACT735_AUDIT_SOURCE_ROW_BINDING')
        by_audit[sid]=row
    need(set(by_audit)==set(expected) and collections.Counter(r['partition'] for r in audit)==EXPECTED,'FULL735_AUDIT_EOF_CENSUS')
    need(primary['schema']=='ROOT_PRIMARY3_EXACT_FORMULA_SOURCE_REVIEW_V1'
         and primary['original_graph_UNKNOWN735_retained'] is True
         and primary['formula_non_H_compositions_match_complete_source_fields'] is True
         and primary['comparison_semantics']=='EXACT_NON_H_COMPOSITION_EQUALITY'
         and primary['greater_or_equal_lower_bounds_created'] is False
         and primary['full_key_or_stereo_promoted'] is False,'ORIGINAL_PRIMARY3_COMPOSITION_ONLY_CONTRACT')
    rows={r['source_id']:r for r in overlay};specific={}
    need(len(rows)==len(overlay)==3,'ALL_THREE_SOURCE_BOUND_COMPOSITION_ROWS')
    for binding in primary['source_bindings']:
        sid=binding['original_source_record_id'];rid=binding['strict5_source_id']
        need(sid in expected and sid not in specific and rid in rows
             and binding['original_source_row_sha256']==expected[sid]['source_row_sha256']
             and all(binding['locator'][k]==expected[sid][k] for k in ('source_table','copy_block','source_row_ordinal'))
             and binding['original_graph_identity_resolution']=='UNKNOWN_UNCHANGED'
             and binding['full_keys']==[] and binding['source_rows_dropped'] is False,
             'UNIQUE_EXACT_PRIMARY3_PHYSICAL_BINDING')
        r=rows[rid]
        need(r['source_id']==sid+':composition:0' and r['inchikeys']==[]
             and r['role']=='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN' and r['subdataset']=='entries'
             and r['non_h_composition']==binding['exact_composition']
             and r['non_h_composition'],'ACTUAL_STRICT5_COMPOSITION_WITHOUT_GRAPH_PROMOTION')
        specific[sid]=(rid,r['non_h_composition'])
    need(set(specific)==set(proposal['retained_exact_source_recovery_ids'])
         and set(scoped)|set(specific)==set(expected),'NO_OTHER_SOURCE_ROWS_OR_SCOPES_CHANGED')
    result=[]
    for sid in sorted(expected):
        common=dict(source_id=sid,binding=expected[sid],original_identity_resolution='UNKNOWN_UNCHANGED',
                    evidence_references=evidence,rule_ids=[],identity_source_ids=[])
        if sid in scoped:
            need(by_audit[sid]['partition']!='FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL',
                 'SPECIFIC_FINITE_MOLECULE_CANNOT_BE_QUARANTINED')
            common.update(new_exclusion_status='APPROVED_SOURCE_SCOPE_DISPOSITION',
                          not_a_chemical_exclusion_rule=True,
                          approved_original_partition=by_audit[sid]['partition'])
        else:
            need(by_audit[sid]['partition']=='FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL',
                 'RECOVERED_THREE_RETAINED_IN_MOLECULAR_DECONTAMINATION')
            rid,comp=specific[sid]
            common.update(new_exclusion_status='EXACT_COMPOSITION_COVERED',
                          identity_source_ids=[rid],exact_compositions=[comp])
        result.append(common)
    need(collections.Counter(r['new_exclusion_status'] for r in result)=={
        'APPROVED_SOURCE_SCOPE_DISPOSITION':732,'EXACT_COMPOSITION_COVERED':3},'EXACT735_CONSERVED_PHYSICAL_LEDGER')
    return result


