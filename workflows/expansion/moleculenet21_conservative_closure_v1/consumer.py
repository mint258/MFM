"""Typed V2 exclusion index; original strict5/full/WP5/exact-composition objects."""
import collections,json,os,sqlite3
from pathlib import Path
from workflows.expansion import decontamination as legacy
from . import closure as R
Q=R.Q;I=R.I;need=R.need;meta=R.meta
identity_keys=legacy.identity_keys;contamination_exact=legacy.contamination
MANIFEST='expansion_decontamination_sources_with_constraints_v2';INDEX='expansion_exclusion_index_with_constraints_v2'

def index_header(index):
    need(index['schema']==INDEX and index['status']=='COMPLETE' and set(index['sources'])==legacy.REQUIRED
      and index['typed_lower_bound_rules']==2,'REAL_ALL11_TYPED_V2_INDEX_NOT_LEGACY_OR_CASE_MANIFEST_ONLY');return index

def closed_sqlite(ref,plan,budget):
    for suffix in ('-wal','-shm','-journal'):
        path=Path(ref['path']+suffix);need(not path.exists() and not path.is_symlink(),'CLOSED_SQLITE_NO_ACTIVE_SIDECARS')
    _hash(ref,plan,budget)

def parent_binding(proof):
    return {'job_id':str(proof['job_id']),'uid':os.getuid(),'node':proof['request']['node'],'boot_id':proof['boot_id'],
      'pid':os.getpid(),'pid_start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]}

def vector(value):
    need(type(value)is list and value and all(type(p)is list and len(p)==2 and type(p[0])is int and 2<=p[0]<=118
      and type(p[1])is int and p[1]>0 for p in value) and [p[0] for p in value]==sorted({p[0] for p in value}),'STRICT_POSITIVE_SORTED_NON_H_COUNT_VECTOR')
    return dict(value)

def candidate_domain(row,allowed=R.WHITELIST):
    need(type(row['non_h_composition'])is str,'ORIGINAL_SCREEN_COMPOSITION_SERIALIZATION')
    value=R.M.P.strict_json(row['non_h_composition']);counts=vector(value)
    need(row['elements']==sorted(counts) and set(counts)<=set(allowed)
      and row['non_h_composition']==json.dumps(value,separators=(',',':')),'ACTUAL_EACH_CANDIDATE_WITHIN_FROZEN_X02_DOMAIN')
    return counts

def install_tables(db):
    db.execute('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset)) WITHOUT ROWID')
    db.execute('CREATE TABLE constraints(rule_id TEXT PRIMARY KEY,dataset TEXT,binding TEXT NOT NULL) WITHOUT ROWID')
    db.execute('CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER,PRIMARY KEY(rule_id,z)) WITHOUT ROWID')

def rules(db):
    values=[]
    for rid,dataset in db.execute('SELECT rule_id,dataset FROM constraints ORDER BY rule_id'):
        rows=[[z,n] for z,n in db.execute('SELECT z,n FROM constraint_atoms WHERE rule_id=? ORDER BY z',(rid,))]
        values.append((rid,dataset,vector(rows)))
    need(len(values)<=2,'EXACT_CLOSED21_LOWER_BOUND_SCOPE_NOT_GENERAL_SUBSTRUCTURE');return values

def contamination(row,db,prepared_rules=None):
    counts=candidate_domain(row);result=set(contamination_exact(row,db))
    for rid,dataset,bound in rules(db) if prepared_rules is None else prepared_rules:
        if all(counts.get(z,0)>=n for z,n in bound.items()):result.add(('composition_lower_bound:'+rid,dataset))
    return sorted(result)

def _hash(ref,plan,budget):
    with I.held(R.positive(ref),[Q.ROOT/'artifacts'],plan['data_references']) as (stream,_):
        for _ in iter(lambda:stream.read(1<<20),b''):budget.check()

def _read_rows(ref,plan,budget):
    need(R.positive(ref) in plan['data_references'],'EXACT_DECLARED_SOURCE_DATA_BEFORE_INDEX_READ')
    yield from I.json_rows(ref,budget)

def accepted_molnet(manifest):
    review=meta(manifest['root_molnet21_acceptance_reference'])
    need(review['schema']=='ROOT_MOLNET21_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1'
      and review['status']=='APPROVED_FOR_CLOSED21_CONSERVATIVE_EXCLUSION_V2' and review['reviewer']=='root'
      and review['original_identity_unknowns_and_all_physical_rows_retained'] is True and review['full_filtered_pool_release_authorized'] is False,
      'ACTUAL_ROOT_COVERAGE_ADOPTION_NOT_SOURCE_IMPLEMENTATION_POLICY')
    receipt=meta(review['receipt_reference']);_,raw=R.C.D.K.K.account(review['accounting_reference'],receipt)
    need(receipt['schema']=='MOLNET21_CONSERVATIVE_CLOSURE_RECEIPT_V1' and receipt['status']=='CANDIDATE_EVIDENCE_CLOSED_PENDING_ROOT_C0_ADOPTION' and receipt['READY_or_pool_release'] is False
      and receipt['policy_reference']==manifest['policy_reference'],'ACTUAL_CONSERVATIVE_CLOSURE_C0_POLICY_NOT_FUTURE')
    f=receipt['fixtures'];need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_CLOSURE_SOURCE3')
    proof=meta(receipt['startup_proof_reference']);plan=meta(receipt['plan_reference']);request=meta(proof['request_reference'])
    need(proof['request']==request and str(proof['job_id'])==str(receipt['job_id']) and proof['uid']==1278
      and request['scope_key']==R.KEY and request['scope_parameters']==plan['scope_parameters']==R.parameters(plan['node'])
      and receipt['node']==proof['node']==request['node']==plan['node'] and request['cpus']==16
      and request['execution_argv']==[Q.PY,'-B','-m',R.MODULE,'--plan',receipt['plan_reference']['path'],'--startup-proof',receipt['startup_proof_reference']['path']],
      'TRUE_CLOSED_PRODUCER_PLAN_PROOF')
    result=receipt['result'];need(result['complete_exclusion_coverage_candidate'] is True and result['remaining_exclusion_HOLD']==0
      and result['cases']==result['original_identity_UNKNOWN_cases']==21 and result['original_graph_statuses_modified'] is False
      and result['disposition_counts']=={'invalid_marker':15,'ion_domain_disjoint':3,'dummy_lower_bound':1,'peptide_lower_bound':1,'ARG_component_union':1}
      and result['policy_reference']==manifest['policy_reference'] and result['candidate_domain_authority']==manifest['candidate_domain_authority'],
      'ALL21_EXACT_DISPOSITIONS_NOT_CHANGED_IDENTITIES')
    report=meta(result['report_reference']);need(report=={k:v for k,v in result.items() if k!='report_reference'},'ACTUAL_COMPLETE_REPORT_REFERENCE')
    return result,review,[review['receipt_reference'],review['accounting_reference'],raw,receipt['plan_reference'],receipt['startup_proof_reference'],proof['request_reference']]

def _legacy_header(source,plan,budget):
    need(source['status']=='READY' and source.get('version') and source.get('raw_artifacts'),'ORIGINAL_SOURCE_VERSION_RAW_AND_READY')
    for ref in source['raw_artifacts']:_hash(ref,plan,budget)
    coverage=meta(source['coverage_evidence']);need(coverage['schema']=='expansion_all_source_identity_coverage_v1'
      and coverage['dataset']==source['dataset'] and coverage['all_splits'] is True and coverage['unresolved_without_identity_or_composition']==0
      and set(coverage['covered_roles'])==set(source['required_roles']) and set(coverage['covered_subdatasets'])==set(source.get('required_subdatasets',[]))
      and coverage['raw_artifacts']==source['raw_artifacts'] and coverage['identities']==source['identities']
      and type(coverage['expected_identity_records'])is int and coverage['expected_identity_records']>0
      and coverage['expected_identity_records']==source['identities']['rows'],'ORIGINAL_ALL_SOURCE_ALL_ROLE_COVERAGE_NOT_REDUCED')
    return coverage,[source['identities']]

def _insert_rows(db,source,refs,expected,plan,budget):
    n=0;roles=collections.Counter();datasets=collections.Counter()
    for ref in refs:
        for row,_ in _read_rows(ref,plan,budget):
            need(row['role'] in source['required_roles']
              and row.get('subdataset','') in source.get('required_subdatasets',['']),'ACTUAL_STRICT5_ALL_ROLES_AND_SUBDATASETS')
            db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)',[(kind,key,source['dataset']) for kind,key in identity_keys(row)])
            roles[row['role']]+=1;datasets[row.get('subdataset','')]+=1;n+=1
            if n%4096==0:db.commit();budget.check()
    need(n==expected and set(roles)==set(source['required_roles']) and set(datasets)==set(source.get('required_subdatasets',[''])),
      'COMPLETE_IDENTITY_ROWS_AND_ROLE_CENSUS_NOT_INDEX_SIZE')
    return {'records':n,'roles':dict(roles),'subdatasets':dict(datasets)}

def build_index(plan,proof,budget,out):
    R.admit(plan,proof);budget.check();manifest=meta(plan['source_manifest_reference'])
    need(manifest['schema']==MANIFEST and manifest['policy_reference']==plan['policy_reference']
      and manifest['candidate_domain_authority']==plan['candidate_domain_authority'],'V2_ONLY_SOURCE_MANIFEST')
    sources=manifest['sources'];need(len(sources)==11 and {s['dataset'] for s in sources}==legacy.REQUIRED,'EXACT_ALL11_SOURCE_SET')
    R.domain(manifest['candidate_domain_authority']);mol,review,parents=accepted_molnet(manifest)
    for ref in [plan['source_manifest_reference'],manifest['root_molnet21_acceptance_reference'],*parents]:
        need(ref in proof['request']['source_references'],'ACTUAL_POLICY_AND_C0_PARENTS_IN_ADMITTED_REQUEST')
    out=R.M.fresh(out,'artifacts');out.mkdir(parents=True,mode=0o700);path=out/'excluded_identities_v2.sqlite';db=sqlite3.connect(path);install_tables(db);counts={}
    try:
        for source in sources:
            budget.check()
            if source['dataset']!='moleculenet':
                coverage,refs=_legacy_header(source,plan,budget);expected=coverage['expected_identity_records']
            else:
                need(source['status']=='READY_FOR_CONSERVATIVE_EXCLUSION_V2' and source['required_roles']==['all']
                  and source['required_subdatasets']==list(R.C.NAMES) and source.get('version')
                  and source['raw_artifacts']==mol['raw_artifacts'],'EXACT_REVIEWED_MOLNET_ALL17_ROLES_VERSION_RAW')
                for ref in source['raw_artifacts']:_hash(ref,plan,budget)
                need(source['coverage_evidence']==mol['report_reference'] and source['base_identities']==mol['base_strict5_reference']
                  and source['overlay']==mol['overlay_reference'] and source['lower_bounds']==mol['lower_bound_reference']
                  and source['physical_dispositions']==mol['physical_dispositions_reference'],'ACTUAL_CLOSED_PRODUCER_OVERLAYS_NO_MANIFEST_ONLY_COVERAGE')
                refs=[mol['base_strict5_reference'],mol['overlay_reference']];need(all(ref is not None for ref in refs),'EXACT_CLOSED_BASE_AND_OVERLAY')
                expected=sum(ref['rows'] for ref in refs);ledger=[]
                for record,_ in _read_rows(mol['physical_dispositions_reference'],plan,budget):ledger.append(record)
                need(len(ledger)==21 and len({r['binding']['hold_ordinal'] for r in ledger})==21
                  and all(r['original_identity_resolution']=='UNKNOWN_UNCHANGED' for r in ledger)
                  and collections.Counter(r['new_exclusion_status'] for r in ledger)=={'AUTHOR_SOURCE_INVALID_MOLECULAR_INPUT':15,
                    'CANDIDATE_DOMAIN_DISJOINT_X02':3,'CONSERVATIVE_LOWER_BOUND_COVERED':2,'CONSERVATIVE_ARG_AND_CURRENT_COMPONENT_UNION_COVERED':1},
                  'ACTUAL21_PHYSICAL_DISPOSITION_READBACK')
                records=[]
                for rule,_ in _read_rows(mol['lower_bound_reference'],plan,budget):
                    need(rule['kind']=='NON_H_ATOM_COUNT_LOWER_BOUND' and rule['policy_reference']==manifest['policy_reference']
                      and rule['dataset']=='moleculenet' and rule['subdataset'] in ('ClinTox','PDBbind')
                      and rule['binding'] in [r['binding'] for r in ledger],'EXACT_ROOT_POLICY_CASE_BOUND_CONSTRAINT')
                    bound=vector(rule['bound']);records.append(rule)
                    db.execute('INSERT INTO constraints VALUES(?,?,?)',(rule['rule_id'],rule['dataset'],json.dumps(rule['binding'],sort_keys=True)))
                    db.executemany('INSERT INTO constraint_atoms VALUES(?,?,?)',[(rule['rule_id'],z,n) for z,n in bound.items()])
                need(len(records)==2 and {r['subdataset'] for r in records}=={'ClinTox','PDBbind'},'BOTH_REQUIRED_TYPED_LOWER_BOUND_VETOS_PRESENT')
            counts[source['dataset']]=_insert_rows(db,source,refs,expected,plan,budget)
        db.commit();prepared=rules(db);need(len(prepared)==2,'DURABLE_CONSTRAINTS_READBACK_REQUIRED')
        need(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'CLOSED_INDEX_SQLITE_INTEGRITY')
    finally:db.close()
    ref=I.data_pin(path,[out],check=lambda:budget.check(dispatch=False))
    receipt={'schema':INDEX,'status':'COMPLETE','source_manifest_reference':plan['source_manifest_reference'],'sources':counts,'database':ref,
      'policy_reference':manifest['policy_reference'],'candidate_domain_authority':manifest['candidate_domain_authority'],
      'Root_coverage_acceptance_reference':manifest['root_molnet21_acceptance_reference'],'typed_lower_bound_rules':2,
      'original_strict5_objects_unchanged':True,'original_UNKNOWN_resolved':False,'filtered_pool_complete':False,'global_pool_release':False,
      'producer_parent_binding':parent_binding(proof),'stage_complete_is_not_child_Slurm_C0':True}
    return I.write(out/'receipt.json',receipt,budget)

def filter_rows(incoming,excluded,outgoing,budget):
    prepared=rules(excluded);counts=collections.Counter();outgoing.execute('CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)')
    for raw in incoming.execute('SELECT full_key,cid,wp5_key,features FROM candidates ORDER BY full_key'):
        budget.check();features=R.M.P.strict_json(raw[3]);need(features['full_key']==raw[0] and features['cid']==raw[1],'EXACT_SCREEN_CANDIDATE_BINDING')
        hits=contamination(features,excluded,prepared);counts['input_unique_molecules']+=1
        if hits:
            counts['excluded_molecules']+=1
            for kind,dataset in hits:counts['reason:'+kind+':'+dataset]+=1
            if any(kind.startswith('composition_lower_bound:') for kind,_ in hits):counts['conservative_lower_bound_exclusions']+=1
            if any(kind.startswith('composition_lower_bound:') for kind,_ in hits) and not any(not kind.startswith('composition_lower_bound:') for kind,_ in hits):
                counts['additional_conservative_veto_beyond_exact_possible_over_exclusion']+=1
        else:outgoing.execute('INSERT INTO candidates VALUES(?,?,?,?)',raw);counts['eligible_molecules']+=1
        if counts['input_unique_molecules']%4096==0:outgoing.commit();budget.check()
    outgoing.commit();need(counts['input_unique_molecules']==counts['excluded_molecules']+counts['eligible_molecules'],'FILTERED_POOL_MASS')
    return dict(counts)

def filter_pool(plan,proof,budget,out,*,built_index_reference=None):
    R.admit(plan,proof);budget.check();screen=meta(plan['screen_receipt_reference']);index_ref=built_index_reference or plan['exclusion_receipt_reference'];index=meta(index_ref);regression=meta(plan['regression_receipt_reference'])
    need(all(plan[k] in proof['request']['source_references'] for k in ('screen_receipt_reference','regression_receipt_reference')),'ACTUAL_FULL_SCREEN_AND_REGRESSION_PARENT_AUTHORITY')
    if built_index_reference is not None:
        need(index['producer_parent_binding']==parent_binding(proof) and index['source_manifest_reference']==plan['source_manifest_reference']
          and index['source_manifest_reference'] in proof['request']['source_references'] and index['stage_complete_is_not_child_Slurm_C0'] is True,
          'ONLY_ACTUAL_THIS_PARENT_BUILT_INDEX_NO_FUTURE_HASH_OR_CHILD_C0')
        index_data={'data_references':[index['database']]}
    else:
        need(index_ref in proof['request']['source_references'],'ACTUAL_PRIOR_INDEX_RECEIPT_AUTHORITY');index_data=plan
    need(screen['schema']=='pubchem_screen_v1' and screen['complete_source'] is True,'COMPLETE_SOURCE_SCREEN_NOT_PREFIX');index_header(index)
    need(index['policy_reference']==plan['policy_reference'] and index['candidate_domain_authority']==plan['candidate_domain_authority'],'EXACT_SAME_ROOT_POLICY_DOMAIN')
    need(regression['status']=='PASS' and regression['agreement']>=.999 and regression['unexplained_mismatches']==0
      and regression['full_v1_selection_regression_passed'] is True,'ORIGINAL_FULL_V1_REGRESSION_GATE')
    R.domain(index['candidate_domain_authority']);closed_sqlite(screen['database'],plan,budget);closed_sqlite(index['database'],index_data,budget)
    out=R.M.fresh(out,'artifacts');out.mkdir(parents=True,mode=0o700);path=out/'eligible_candidates.sqlite'
    incoming=sqlite3.connect(Path(screen['database']['path']).as_uri()+'?mode=ro&immutable=1',uri=True)
    excluded=sqlite3.connect(Path(index['database']['path']).as_uri()+'?mode=ro&immutable=1',uri=True);outgoing=sqlite3.connect(path)
    try:
        counts=filter_rows(incoming,excluded,outgoing,budget)
        need(outgoing.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'ACTUAL_FILTER_OUTPUT_INTEGRITY')
    finally:incoming.close();excluded.close();outgoing.close()
    # Rehash declared closed inputs after immutable read; no active SQLite reuse.
    closed_sqlite(screen['database'],plan,budget);closed_sqlite(index['database'],index_data,budget)
    output=I.data_pin(path,[out],check=lambda:budget.check(dispatch=False))
    receipt={'schema':'expansion_filtered_pool_v1','status':'COMPLETE','screen':plan['screen_receipt_reference'],
      'exclusion_index':index_ref,'regression':plan['regression_receipt_reference'],'all_sources_all_splits_verified':True,
      'counts':counts,'examples':{},'database':output,'source_aliases_preserved_by_reference':screen['database'],'downstream_targets_consumed':False,
      'filter_semantics':'FULL_WP5_EXACT_COMPOSITION_PLUS_TYPED_LOWER_BOUND_V2','policy_reference':index['policy_reference'],
      'V2_index_reference':index_ref,'candidate_domain_checked_on_every_row':True,'new_ranking_or_NN_math':False}
    receipt['over_exclusion_measurement']='ADDITIONAL_CONSERVATIVE_VETO_COUNTS_NOT_PROVEN_FALSE_POSITIVES'
    return I.write(out/'receipt.json',receipt,budget)
