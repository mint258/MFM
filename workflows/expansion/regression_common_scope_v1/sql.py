"""Original common_member(MID) mask on stored decisions; no graph evaluator."""
from collections import Counter
import json


def need(value,message):
    if not value:raise ValueError(message)


def decode_view(db,boolean_order,cause_order):
    required={'old_chemical_admit','new_graph_admit','old_final','conditional_new_final','native_rule_mismatch',
      'portable_flag_mismatch','unexplained','legacy_native_rule_mismatch','historical_unassigned_x1_coalesce'}
    need(required<=set(boolean_order) and len(boolean_order)==len(set(boolean_order))<=16,'CLOSED_BOOLEAN_BIT_ORDER')
    need(len(cause_order)==len(set(cause_order))<=16,'CLOSED_CAUSE_BIT_ORDER')
    need(all(name.replace('_','').isalnum() for name in boolean_order),'LITERAL_REGISTERED_BOOLEAN_FIELDS')
    expressions=[f'((decision_bits & {1<<i})<>0) AS {name}' for i,name in enumerate(boolean_order)]
    db.execute('CREATE VIEW decisions AS SELECT record_id,molecule_id,source_family,cause_bits,'+','.join(expressions)+' FROM compact')
    bad=db.execute(f'SELECT count(*) FROM compact WHERE decision_bits IS NULL OR cause_bits IS NULL OR decision_bits<0 OR cause_bits<0 OR (decision_bits >> {len(boolean_order)})<>0 OR (cause_bits >> {len(cause_order)})<>0 OR record_id IS NULL OR molecule_id IS NULL OR record_id=\'\' OR molecule_id=\'\'').fetchone()[0]
    need(bad==0,'EVERY_COMPACT_ROW_USES_COMPLETE_REGISTERED_BITS_AND_IDS')


def explanation_rows(rows,cause_order):
    counts=Counter();result=[]
    for row in rows:
        value=json.loads(row['details_json']);causes=value['causes']
        need(isinstance(causes,list) and causes and set(causes)<=set(cause_order) and value['unexplained'] is False,'ALL_MISMATCH_EXPLANATIONS_COMPLETE_AND_REGISTERED')
        need(all(value[k]==row[k] for k in ('record_id','molecule_id','source_family')),'MISMATCH_DETAIL_ORIGINAL_SOURCE_IDS')
        counts.update(causes);bits=sum(1<<i for i,cause in enumerate(cause_order) if cause in causes)
        result.append(dict(record_id=row['record_id'],molecule_id=row['molecule_id'],source_family=row['source_family'],cause_bits=bits))
    return result,dict(counts)


def bind(db,boolean_order,common_expected,source_formal_equivalent):
    """Tables compact/decisions,formal,membership,explanations are actual inputs."""
    checks={};metrics={}
    def check(name,value):checks[name]=bool(value)
    n,u,m=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM decisions').fetchone()
    metrics.update(original_records=int(n),original_unique_records=int(u),original_molecules=int(m));check('unique_original_record_IDs',n==u and n>0)
    sums=db.execute('SELECT '+','.join(f'count(*) FILTER(WHERE {name})' for name in boolean_order)+' FROM decisions').fetchone()
    metrics['boolean_counts']={name:int(value) for name,value in zip(boolean_order,sums)}
    chemistry,conditional=db.execute('SELECT count(*) FILTER(WHERE old_chemical_admit IS DISTINCT FROM new_graph_admit),count(*) FILTER(WHERE old_final IS DISTINCT FROM conditional_new_final) FROM decisions').fetchone()
    metrics.update(chemical_changed_records=int(chemistry),global_conditional_changed_records=int(conditional))
    global_molecules=db.execute('SELECT count(*),count(*) FILTER(WHERE old_selected),count(*) FILTER(WHERE new_selected),count(*) FILTER(WHERE old_selected IS DISTINCT FROM new_selected) FROM (SELECT molecule_id,bool_or(old_final) AS old_selected,bool_or(conditional_new_final) AS new_selected FROM decisions GROUP BY molecule_id)').fetchone()
    metrics['global_molecular_selection']={'molecules':int(global_molecules[0]),'old_selected_molecules':int(global_molecules[1]),'new_selected_molecules':int(global_molecules[2]),'changed_molecules':int(global_molecules[3])}
    nf,uf=db.execute('SELECT count(*),count(DISTINCT record_id) FROM formal').fetchone();check('unique_formal_record_IDs',nf==uf and nf>0)
    metrics['formal_records']=int(nf)
    for field in ('old_final','conditional_new_final'):
        left=db.execute(f'SELECT count(*) FROM decisions d ANTI JOIN formal f USING(record_id,molecule_id) WHERE d.{field}').fetchone()[0]
        right=db.execute(f'SELECT count(*) FROM formal f ANTI JOIN (SELECT record_id,molecule_id FROM decisions WHERE {field}) d USING(record_id,molecule_id)').fetchone()[0]
        metrics[field+'_formal_anti_join']={'selected_not_formal':int(left),'formal_not_selected':int(right)}
        check(field+'_exact_complete_formal_set',left==right==0)
    member_n,member_u=db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM membership').fetchone()
    check('unique_membership_MIDs',member_n==member_u);metrics['membership_rows']=int(member_n)
    db.execute('CREATE VIEW common AS SELECT molecule_id,effective_role,records FROM membership WHERE common_population')
    invalid=db.execute("SELECT count(*) FROM common WHERE molecule_id IS NULL OR molecule_id='' OR effective_role NOT IN ('TRAIN','VAL') OR records IS NULL OR records<=0").fetchone()[0]
    check('valid_actual_Common_rows',invalid==0)
    nc=db.execute('SELECT count(*) FROM common').fetchone()[0];metrics['common_molecules']=int(nc)
    check('full_actual_Common_census',nc==common_expected['molecules'])
    absent=db.execute('SELECT count(*) FROM common c ANTI JOIN decisions d USING(molecule_id)').fetchone()[0]
    metrics['common_MIDs_absent_from_complete_decisions']=int(absent);check('no_missing_Common_MIDs',absent==0)
    db.execute('CREATE TABLE common_counts AS SELECT c.molecule_id,c.effective_role,c.records,count(d.record_id) FILTER(WHERE d.old_final) AS old_records,count(d.record_id) FILTER(WHERE d.conditional_new_final) AS new_records FROM common c LEFT JOIN decisions d USING(molecule_id) GROUP BY c.molecule_id,c.effective_role,c.records')
    mismatched=db.execute('SELECT count(*) FROM common_counts WHERE records<>old_records OR records<>new_records').fetchone()[0]
    metrics['common_MIDs_with_different_native_record_counts']=int(mismatched)
    check('original_formal_source_equivalence',source_formal_equivalent)
    check('native_record_count_contract',source_formal_equivalent and mismatched==0)
    metrics['common_record_role_comparison']=[dict(effective_role=r,declared_native_records=int(declared),actual_old_records=int(old),actual_new_records=int(new),molecules=int(count)) for r,declared,old,new,count in db.execute('SELECT effective_role,sum(records),sum(old_records),sum(new_records),count(*) FROM common_counts GROUP BY effective_role ORDER BY effective_role').fetchall()]
    # Execute exactly the original AND-common_member predicate on both sides.
    db.execute('CREATE VIEW bounded AS SELECT d.*,c.molecule_id IS NOT NULL AS common_member,(d.old_final AND c.molecule_id IS NOT NULL) AS bound_old_final,(d.conditional_new_final AND c.molecule_id IS NOT NULL) AS bound_new_final FROM decisions d LEFT JOIN common c USING(molecule_id)')
    old_records,new_records,changed=db.execute('SELECT count(*) FILTER(WHERE bound_old_final),count(*) FILTER(WHERE bound_new_final),count(*) FILTER(WHERE bound_old_final IS DISTINCT FROM bound_new_final) FROM bounded').fetchone()
    selected=db.execute('SELECT count(*),count(*) FILTER(WHERE old_selected),count(*) FILTER(WHERE new_selected),count(*) FILTER(WHERE old_selected IS DISTINCT FROM new_selected) FROM (SELECT molecule_id,bool_or(bound_old_final) AS old_selected,bool_or(bound_new_final) AS new_selected FROM bounded GROUP BY molecule_id)').fetchone()
    metrics['bound_selection']={'old_records':int(old_records),'new_records':int(new_records),'changed_records':int(changed),
      'all_original_molecules':int(selected[0]),'old_selected_molecules':int(selected[1]),'new_selected_molecules':int(selected[2]),'changed_molecules':int(selected[3])}
    check('complete_Common_selected_both_sides',selected[1]==selected[2]==nc)
    ne,ue=db.execute('SELECT count(*),count(DISTINCT record_id) FROM explanations').fetchone();check('unique_mismatch_detail_IDs',ne==ue)
    trigger='(old_chemical_admit IS DISTINCT FROM new_graph_admit) OR (old_final IS DISTINCT FROM conditional_new_final) OR portable_flag_mismatch OR legacy_native_rule_mismatch OR native_rule_mismatch OR historical_unassigned_x1_coalesce'
    missing=db.execute(f'SELECT count(*) FROM (SELECT * FROM decisions WHERE {trigger}) d ANTI JOIN explanations e USING(record_id,molecule_id,source_family)').fetchone()[0]
    extra=db.execute(f'SELECT count(*) FROM explanations e ANTI JOIN (SELECT * FROM decisions WHERE {trigger}) d USING(record_id,molecule_id,source_family)').fetchone()[0]
    different=db.execute('SELECT count(*) FROM explanations e JOIN decisions d USING(record_id,molecule_id,source_family) WHERE e.cause_bits<>d.cause_bits').fetchone()[0]
    metrics['mismatch_explanations']={'rows':int(ne),'missing_details':int(missing),'extra_details':int(extra),'different_cause_vectors':int(different),
      'within_Common_records':int(db.execute('SELECT count(*) FROM explanations e SEMI JOIN common c USING(molecule_id)').fetchone()[0])}
    check('all_actual_mismatch_details_exactly_explained',missing==extra==different==0)
    check('zero_unexplained_and_native_drift',all(metrics['boolean_counts'].get(name,0)==0 for name in ('unexplained','native_rule_mismatch','raw_native_rule_mismatch','enriched_native_rule_mismatch','enrichment_metadata_mismatch')))
    metrics['chemical_admission_agreement']=1-int(chemistry)/n
    metrics['conditional_common_record_agreement']=1-int(changed)/n
    metrics['conditional_common_molecule_agreement']=1-int(selected[3])/int(selected[0])
    metrics['agreement']=min(metrics['chemical_admission_agreement'],metrics['conditional_common_record_agreement'],metrics['conditional_common_molecule_agreement'])
    check('original_99_9_percent_selection_threshold',metrics['agreement']>=.999)
    return dict(checks=checks,metrics=metrics,passed=all(checks.values()),failed_checks=[name for name,good in checks.items() if not good])
