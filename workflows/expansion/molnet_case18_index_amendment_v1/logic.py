"""Exact source-authority and SQLite invariants for the sole case18 amendment."""
import hashlib
import json

CASE='case:18'
COMP=[[6,36],[7,11],[8,12]]
KEY='[[6,36],[7,11],[8,12]]'
FINDINGS=('sequence_correspondence_reviewed','terminal_correspondence_reviewed',
 'description_FCH_vs_SER_disagreement_retained_and_reviewed','primary_paper_correspondence_reviewed',
 'original1PTS_graph_UNKNOWN_retained','no_missing_atoms_added','source_rows_or_scope_not_removed')


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()+b'\n'


def accounting_header(account):
    """Two real captures; never invent a return code for the login readback."""
    need(account['endpoint']=='218.192.171.238:22' and type(account['uid']) is int and account['uid']==1264,
         'ACTUAL_AUTHENTICATED_ALPHA_ACCOUNTING')
    schema=account['schema'];common={'schema','endpoint','uid','actual_parents'}
    if schema=='ROOT_ACTUAL_ALPHA_ACCOUNTING_V1':
        need(set(account)==common|{'query_returncode','raw_sacct_reference'},'COMPLETE_ORIGINAL_ACCOUNTING_FORMAT')
        fields=['JobIDRaw','UID','User','State','ExitCode','ElapsedRaw','NodeList','AllocCPUS','TotalCPU']
        ref=account['raw_sacct_reference'];source='ORIGINAL_CAPTURE_WITH_RECORDED_RETURN_CODE'
        need(type(account['query_returncode']) is int and account['query_returncode']==0,'OBSERVED_QUERY_RETURN_CODE_MUST_BE_ZERO')
    elif schema=='ROOT_ALPHA_ACTUAL_SACCT_READBACK_V1':
        required=common|{'raw_login_sacct_reference','query_argv','query_executed_on','review_metadata_checked_on'}
        need(set(account) in (required,required|{'query_returncode'})
             and account['query_executed_on']=='Alpha login' and account['review_metadata_checked_on']=='sonmi1',
             'COMPLETE_ALPHA_LOGIN_CAPTURE_AND_SONMI1_REVIEW_DECLARATION')
        if 'query_returncode' in account:
            need(type(account['query_returncode']) is int and account['query_returncode']==0,'OBSERVED_QUERY_RETURN_CODE_MUST_BE_ZERO')
        fields=['JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','UID']
        ids=[p['JobIDRaw'] for p in account['actual_parents']]
        need(ids and len(set(ids))==len(ids) and all(isinstance(x,str) and x.isascii() and x.isdigit()
             and str(int(x))==x and int(x)>0 for x in ids),'EXACT_QUERY_POSITIVE_PARENT_JOB_IDS')
        need(account['query_argv']==['sacct','-j',','.join(ids),'-X','-P','--format='+','.join(fields)],
             'ACTUAL_LITERAL_SACCT_QUERY_ARGV_AND_PARENT_SET')
        ref=account['raw_login_sacct_reference'];source='ROOT_ACCEPTED_ALPHA_LOGIN_RAW_CAPTURE_REVIEWED_ON_SONMI1'
    else:raise ValueError('UNSUPPORTED_ACTUAL_ACCOUNTING_CAPTURE_SCHEMA')
    need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'}
         and ref['path'].startswith('/gfshome/alpha/') and type(ref['bytes']) is int and ref['bytes']>0
         and isinstance(ref['sha256'],str) and len(ref['sha256'])==64
         and all(c in '0123456789abcdef' for c in ref['sha256']),'EXACT_ACTUAL_RAW_CAPTURE_REFERENCE')
    return dict(schema=schema,raw_reference=ref,columns=fields,capture_basis=source,
        query_returncode_recorded='query_returncode' in account,
        query_returncode=account.get('query_returncode'),
        no_return_code_imputed=True)


def parent(account,job):
    accounting_header(account)
    rows=[p for p in account['actual_parents'] if str(p.get('JobIDRaw'))==str(job)]
    need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
         and str(rows[0]['UID'])=='1264' and rows[0]['endpoint']=='218.192.171.238:22'
         and rows[0]['uid']==1264 and int(rows[0]['AllocCPUS'])>=16,'ACTUAL_NATIVE_C0_NOT_RUNNING_OR_FAILED')
    return rows[0]


def accounting_readback(account,raw,job):
    import csv,io
    header=accounting_header(account);fields=header['columns'];ref=header['raw_reference']
    need(type(raw) is bytes and len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],
         'BOUND_ACTUAL_RAW_SACCT_WHOLE_BYTES_SHA')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter='|',strict=True)
    need(reader.fieldnames==fields,'EXACT_RAW_SACCT_COLUMN_HEADER')
    parents=account['actual_parents'];by_id={p['JobIDRaw']:p for p in parents}
    need(len(by_id)==len(parents) and by_id,'UNIQUE_DECLARED_ACTUAL_PARENTS')
    for p in parents:
        need(set(p)==set(fields)|{'endpoint','uid'} and all(type(p[k]) is str for k in fields)
             and p['endpoint']=='218.192.171.238:22' and type(p['uid']) is int and p['uid']==1264,
             'EXACT_PARENT_COLUMNS_PLUS_REAL_ALPHA_IDENTITY')
    observed={};steps=[]
    for row in reader:
        need(set(row)==set(fields) and all(type(row[k]) is str for k in fields),'COMPLETE_UNAMBIGUOUS_RAW_SACCT_ROW')
        rid=row['JobIDRaw']
        if rid in by_id:
            need(rid not in observed and row=={k:by_id[rid][k] for k in fields},'RAW_EVERY_PARENT_COLUMN_EXACTLY_MATCHES_CAPTURE_METADATA')
            observed[rid]=row
        else:
            base,sep,step=rid.partition('.')
            need(header['schema']=='ROOT_ACTUAL_ALPHA_ACCOUNTING_V1' and sep and base in by_id
                 and step in ('batch','extern'),'ONLY_EXPLICIT_LEGACY_STEP_ROWS_NOT_INVENTED_PARENTS')
            need(rid not in steps,'NO_DUPLICATE_RAW_STEP_ROW');steps.append(rid)
    need(set(observed)==set(by_id),'ALL_CAPTURED_PARENTS_INCLUDING_FAILED_HISTORY_MATCH_RAW')
    actual=parent(account,job)
    return dict(**header,matched_parent_job_ids=list(observed),additional_legacy_step_rows=steps,
        selected_completed_parent=actual,all_parent_columns_exactly_matched=True,
        authority_basis=('RECORDED_ZERO_RETURN_CODE_AND_COMPLETE_RAW_PARENT_MATCH' if header['query_returncode_recorded']
                         else 'INDEPENDENT_ACCEPTED_ROOT_SOURCE_REVIEW_AND_COMPLETE_RAW_PARENT_MATCH_RETURN_CODE_NOT_RECORDED'))


def authority(review,policy,native,account,old_review,old_ref):
    need(review['schema']=='ROOT_MOLNET_CASE18_SOURCE_CORRESPONDENCE_ACTUAL_ACCEPTANCE_V1'
         and review['status']=='APPROVED_CASE18_EXISTING_EXACT_COMPOSITION_COVERAGE'
         and review['reviewer']=='root' and review['endpoint']=='218.192.171.238:22' and review['uid']==1264
         and review['case_id']==CASE and review['original_index_root_acceptance_reference']==old_ref,
         'EXPLICIT_ROOT_CASE18_SOURCE_ACCEPTANCE_REQUIRED')
    need(review['original_rule_reference']['bytes']==7190
         and review['original_rule_reference']['sha256']=='462256a904210e4dd5185af88c1f15578e164d3a6483226dc4aa7f90d4d4956c',
         'EXACT_IMMUTABLE_OLD_MOLNET_RULE_BODY')
    rule=review['original_case18_rule']
    need(rule['rule_id']==CASE and rule['kind']=='NON_H_ATOM_COUNT_LOWER_BOUND'
         and rule['dataset']=='moleculenet' and rule['subdataset']=='PDBbind'
         and rule['bound']==[[6,3]] and rule['binding']['hold_ordinal']==18,
         'SOLE_EXACT_ORIGINAL_CASE18_C3_BINDING')
    need(review['replacement']==dict(kind='EXISTING_EXACT_NON_H_COMPOSITION',dataset='moleculenet',non_h_composition=COMP)
         and set(review['source_review_findings'])==set(FINDINGS)
         and all(review['source_review_findings'][k] is True for k in FINDINGS)
         and review['COCONUT_scope_extended'] is False and review['index_amendment_performed'] is False
         and review['global_pool_release'] is False,'NO_OTHER_RULE_OR_SCOPE_ADOPTION')
    need(policy['schema']=='ROOT_MOLNET_CASE18_SOURCE_CORRESPONDENCE_POLICY_V2'
         and policy['status']=='ADOPTED_ONLY_FOR_CASE18_EXISTING_COMPOSITION_SOURCE_COVERAGE'
         and policy['reviewer']=='root' and policy['endpoint']=='218.192.171.238:22' and policy['uid']==1264
         and policy['case_id']==CASE and policy['new_user_scope_exception'] is False
         and policy['index_amendment_performed'] is False
         and policy['original_case18_rule']==rule and policy['old_rule_reference']==review['original_rule_reference']
         and policy['native_evidence_receipt_reference']==review['native_evidence_receipt_reference']
         and policy['native_evidence_actual_accounting_reference']==review['native_evidence_actual_accounting_reference']
         and policy['source_review_findings']==review['source_review_findings']
         and policy['scientific_judgment']==review['scientific_judgment'],'ACTUAL_NARROW_ROOT_POLICY_AND_REVIEW_AGREE')
    need(native['schema']=='ALPHA_MOLNET_CASE18_NATIVE_EVIDENCE_PRODUCER_V1'
         and native['status']=='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW'
         and native['source_correspondence_adopted'] is False and native['index_amendment_performed'] is False
         and native['global_pool_release'] is False
         and native['evidence_reference']==review['observations_reference']
         and native['actual_source_reads_reference']==review['source_readback_reference']
         and native['source_tests_reference']==review['source_tests_reference'],
         'EVIDENCE_ONLY_NATIVE_RECEIPT_BOUND_TO_SEPARATE_SOURCE_REVIEW')
    actual=parent(account,native['profile_admission']['job_id'])
    need(actual==review['actual_parent'] and native['profile_admission']['endpoint']=='218.192.171.238:22'
         and native['profile_admission']['uid']==1264,'EXACT_ACTUAL_REVIEWED_NATIVE_PARENT')
    need(old_review['schema']=='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1'
         and old_review['status']=='APPROVED_COMPLETE_ALL11_INDEX' and old_review['reviewer']=='root'
         and old_review['all_sources_all_splits_verified'] is True
         and old_review['original_graph_unknowns_retained'] is True
         and str(old_review['actual_parent']['JobIDRaw'])=='1885187', 'EXACT_ACCEPTED_187_FULL_SOURCE_BASE')
    return rule


def rows(db,sql,args=()):return db.execute(sql,args).fetchall()


def constraints(db):
    return dict(rules=rows(db,'SELECT rule_id,dataset,binding FROM constraints ORDER BY rule_id'),
                atoms=rows(db,'SELECT rule_id,z,n FROM constraint_atoms ORDER BY rule_id,z'))


def excluded_parity(old,new,check=lambda:None):
    """Full BINARY-ordered merge is a two-direction anti-join without temp writes."""
    sql='SELECT kind,key,dataset FROM excluded ORDER BY kind COLLATE BINARY,key COLLATE BINARY,dataset COLLATE BINARY'
    left=iter(old.execute(sql));right=iter(new.execute(sql));sentinel=object()
    a=next(left,sentinel);b=next(right,sentinel);lh=hashlib.sha256();rh=hashlib.sha256();lc=rc=0;missing_old=missing_new=0
    def order(row):return tuple(x.encode('utf-8') for x in row)
    def consume(row,h):
        need(len(row)==3 and all(isinstance(x,str) for x in row),'EXCLUDED_PK_TEXT_TRIPLE')
        raw=canonical(row);h.update(len(raw).to_bytes(8,'big'));h.update(raw)
    while a is not sentinel or b is not sentinel:
        if a is not sentinel and b is not sentinel and a==b:
            consume(a,lh);consume(b,rh);lc+=1;rc+=1;a=next(left,sentinel);b=next(right,sentinel)
        elif b is sentinel or (a is not sentinel and order(a)<order(b)):
            consume(a,lh);lc+=1;missing_new+=1;a=next(left,sentinel)
        else:
            consume(b,rh);rc+=1;missing_old+=1;b=next(right,sentinel)
        if (lc+rc)%16384==0:check()
    check()
    result=dict(original_count=lc,new_count=rc,original_ordered_PK_sha256=lh.hexdigest(),new_ordered_PK_sha256=rh.hexdigest(),
        missing_from_original=missing_old,missing_from_new=missing_new,both_ordered_cursors_reached_EOF=True,
        algorithm='FULL_BINARY_ORDERED_MERGE_BIDIRECTIONAL_ANTI_JOIN_LENGTH_PREFIXED_CANONICAL_PK_SHA256')
    need(lc==rc and lh.digest()==rh.digest() and missing_old==missing_new==0,'ALL_EXCLUDED_PK_SETS_COUNTS_DIGESTS_AND_BOTH_DIRECTIONS_IDENTICAL')
    return result


def expected_remaining(before,expected):
    need(set(r[0] for r in before['rules'])=={'case:00',CASE} and len(before['rules'])==2,
         'EXACT_OLD_TWO_MOLNET_CONSTRAINTS_NOT_GENERAL_RULE_REMOVAL')
    selected=[r for r in before['rules'] if r[0]==CASE]
    need(len(selected)==1 and selected[0][1]=='moleculenet' and json.loads(selected[0][2])==expected['binding']
         and [r for r in before['atoms'] if r[0]==CASE]==[(CASE,6,3)],'DB_EXACT_CASE18_BINDING_AND_C3_ATOM_ROW')
    need(all(r[1]=='moleculenet' for r in before['rules'])
         and all(r[0] in {'case:00',CASE} for r in before['atoms']), 'NO_HIDDEN_OTHER_SOURCE_CONSTRAINT')
    return {k:[r for r in v if r[0]!=CASE] for k,v in before.items()}


def amend(old,new,expected,check=lambda:None):
    """old is an independently hashed read-locked connection; new is private."""
    before=constraints(old);remaining=expected_remaining(before,expected)
    need(rows(old,'SELECT kind,key,dataset FROM excluded WHERE kind=? AND key=? AND dataset=?',
              ('composition',KEY,'moleculenet'))==[('composition',KEY,'moleculenet')],
         'REPLACEMENT_EXACT_COMPOSITION_MUST_ALREADY_EXIST_NO_NEW_KEYS')
    old.backup(new,pages=1024,progress=lambda *_:check())
    need(constraints(new)==before,'PRIVATE_BACKUP_EXACT_CONSTRAINT_READBACK_BEFORE_AMENDMENT')
    need(new.execute('DELETE FROM constraint_atoms WHERE rule_id=?',(CASE,)).rowcount==1
         and new.execute('DELETE FROM constraints WHERE rule_id=?',(CASE,)).rowcount==1,'ONLY_TWO_EXACT_CASE18_ROWS_AMENDED')
    new.commit();check()
    need(constraints(old)==before and constraints(new)==remaining,'ORIGINAL_UNTOUCHED_AND_ALL_OTHER_CONSTRAINT_BYTES_IDENTICAL')
    parity=excluded_parity(old,new,check)
    need(rows(new,'PRAGMA integrity_check')==[('ok',)],'NEW_PRIVATE_DB_INTEGRITY_READBACK')
    need(rows(old,'SELECT kind,key,dataset FROM excluded WHERE kind=? AND key=? AND dataset=?',('composition',KEY,'moleculenet'))
         ==rows(new,'SELECT kind,key,dataset FROM excluded WHERE kind=? AND key=? AND dataset=?',('composition',KEY,'moleculenet')),
         'EXISTING_EXACT_COMPOSITION_RETAINED_AFTER_AMENDMENT')
    clintox=[r for r in remaining['rules'] if r[0]=='case:00']
    need(len(clintox)==1,'CLINTOX_CASE00_REMAINS')
    return dict(excluded=parity,old_constraints=before,new_constraints=remaining,
        ClinTox_binding_UTF8_sha256=hashlib.sha256(clintox[0][2].encode('utf-8')).hexdigest(),
        ClinTox_binding_and_atom_rows_exactly_unchanged=True,source_database_unmodified=True,
        existing_exact_composition_retained=True,new_graph_or_identity_rows=0,old_case18_rule_preserved_in_original=True,
        only_private_case18_constraint_and_atom_row_removed=True,integrity_check='ok')
