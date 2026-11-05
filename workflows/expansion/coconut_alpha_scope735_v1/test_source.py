"""Metadata adversarial cases; no scientific imports or invented C0."""
import copy
import hashlib
import json
import unittest
from .assemble import assemble,EXPECTED,PROPOSAL


def fixture():
    original=[];audit=[];scoped=[];bindings=[];overlay=[]
    for n in range(735):
        sid='entries:'+str(n)+':1:'+str(n)
        source=dict(source_table='entries',copy_block=1,source_row_ordinal=n,
                    source_row_sha256=hashlib.sha256(str(n).encode()).hexdigest(),
                    identity_fields_json=json.dumps({'id':str(n)}))
        original.append(dict(source=source,original_UNKNOWN_unchanged=True))
        partition=('FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL' if n<3 else
                   'OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS' if n<6 else
                   'SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE')
        audit.append(dict(original_source_id=sid,original_source=source,
                          world_nonexistence_inferred=False,partition=partition))
        if n>=3:scoped.append(sid);continue
        rid=sid+':composition:0';comp=[[6,n+1]]
        overlay.append(dict(source_id=rid,role='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN',
                            subdataset='entries',inchikeys=[],non_h_composition=comp))
        bindings.append(dict(original_source_record_id=sid,strict5_source_id=rid,
            original_source_row_sha256=source['source_row_sha256'],
            locator={k:source[k] for k in ('source_table','copy_block','source_row_ordinal')},
            original_graph_identity_resolution='UNKNOWN_UNCHANGED',full_keys=[],
            source_rows_dropped=False,exact_composition=comp))
    proposal=dict(schema='COCONUT_FINITE_MOLECULAR_SOURCE_SCOPE_PROPOSAL_V1',
        partition_counts=EXPECTED,rows=735,source_records_deleted=0,insufficient_evidence_source_ids=[],
        proposed_quarantined_source_ids=sorted(scoped),
        retained_exact_source_recovery_ids=[b['original_source_record_id'] for b in bindings],
        proposed_source_id_set_sha256=hashlib.sha256(('\n'.join(sorted(scoped))+'\n').encode()).hexdigest())
    approval=dict(schema='PUBCHEM_COCONUT_MOLECULAR_SCOPE_USER_APPROVAL_V1',
        status='USER_APPROVED_EXACT_732_WITH_FULL_AUDIT_RETAINED',proposal_public_commit=PROPOSAL,
        user_answer_verbatim='批准，仅隔离这 732 条并保留审计',approved_scope_dispositions=732,
        provided_structure_underspecified=729,official_abstract_or_nonmolecular_entries=3,
        recovered_specific_molecules_retained=3,all_other_COCONUT_rows_retained=True,
        all_original_text_and_per_row_audit_retained=True,only_exact_proposal_records_may_be_scoped_out=True,
        chemical_X_or_key_or_fingerprint_rules_changed=False)
    primary=dict(schema='ROOT_PRIMARY3_EXACT_FORMULA_SOURCE_REVIEW_V1',
        original_graph_UNKNOWN735_retained=True,formula_non_H_compositions_match_complete_source_fields=True,
        comparison_semantics='EXACT_NON_H_COMPOSITION_EQUALITY',greater_or_equal_lower_bounds_created=False,
        full_key_or_stereo_promoted=False,source_bindings=bindings)
    return [original,audit,proposal,approval,primary,overlay,[{'fixture':'no_actual_approval_or_parent_claimed'}]]


class Source(unittest.TestCase):
    def test_scope_is_exact_and_finite_three_never_quarantined(self):
        data=fixture();rows=assemble(*data)
        self.assertEqual(len(rows),735)
        self.assertEqual(sum(r['new_exclusion_status']=='EXACT_COMPOSITION_COVERED' for r in rows),3)
        self.assertTrue(all(r['original_identity_resolution']=='UNKNOWN_UNCHANGED' for r in rows))
        swapped=copy.deepcopy(data)
        swapped[2]['proposed_quarantined_source_ids'][0]=swapped[2]['retained_exact_source_recovery_ids'][0]
        with self.assertRaises(ValueError):assemble(*swapped)
        unapproved=copy.deepcopy(data);unapproved[3]['status']='PENDING'
        with self.assertRaises(ValueError):assemble(*unapproved)

    def test_source_sha_and_composition_graph_claims_cannot_drift(self):
        data=fixture()
        for change in ('sha','composition','key','missing'):
            altered=copy.deepcopy(data)
            if change=='sha':altered[1][2]['original_source']['source_row_sha256']='0'*64
            elif change=='composition':altered[5][1]['non_h_composition']=[[8,900]]
            elif change=='key':altered[5][0]['inchikeys']=['FAKE-FULL-KEY']
            else:altered[0].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):assemble(*altered)

        import sqlite3
        from .impact_sql import query
        db=sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE candidates(non_h_composition TEXT)')
            db.executemany('INSERT INTO candidates VALUES(?)',[('[[6,1]]',),('[[8,2]]',),
                ('[[6,1]]',),('[[6,1],[8,2]]',),(None,),('[[8,2],[6,1]]',)])
            impact=query(db,[('s1','[[6,1]]'),('s2','[[6,1]]'),('s3','[[8,2]]')],6)
            self.assertEqual(impact['input_unique_molecules'],6)
            self.assertEqual(impact['excluded_by_coconut735_exact_compositions'],3)
            self.assertEqual(impact['eligible_after_coconut735_rules'],3)
            self.assertEqual([r['matching_candidates'] for r in impact['per_source']],[2,2,1])
            self.assertEqual(impact['overlaps_counted_once_in_union'],2)
            self.assertFalse(impact['all11_filter_performed'])
            with self.assertRaises(ValueError):query(db,[('s1','a'),('s2','b'),('s3','c')],5)
        finally:db.close()

if __name__=='__main__':unittest.main()

