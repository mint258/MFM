"""Stream exact original strict5 keys into a fresh independently admitted index."""
import collections
import json
import os
from pathlib import Path
import sqlite3
from .reader import S


def legacy_header(reader,source):
    S.need(source['status']=='READY' and source.get('version') and source.get('raw_artifacts'),'ORIGINAL_READY_SOURCE_VERSION_AND_PHYSICAL_INPUTS')
    for ref in source['raw_artifacts']:reader.verify(ref)
    coverage=reader.json(source['coverage_evidence'])
    S.need(coverage['schema']=='expansion_all_source_identity_coverage_v1'
           and coverage['dataset']==source['dataset'] and coverage['all_splits'] is True
           and coverage['unresolved_without_identity_or_composition']==0
           and set(coverage['covered_roles'])==set(source['required_roles'])
           and set(coverage['covered_subdatasets'])==set(source.get('required_subdatasets',[]))
           and coverage['raw_artifacts']==source['raw_artifacts'] and coverage['identities']==source['identities']
           and type(coverage['expected_identity_records']) is int and coverage['expected_identity_records']>0
           and coverage['expected_identity_records']==source['identities']['rows'],'ORIGINAL_ALL_SOURCE_ALL_ROLE_COVERAGE_NOT_REDUCED')
    return [source['identities']],coverage['expected_identity_records'],coverage


def insert_rows(db,reader,source,refs,expected,C,guard,coco=None):
    n=0;roles=collections.Counter();datasets=collections.Counter();batch=[];seen={}
    wanted=set() if coco is None else coco['expected_identity_source_ids']
    for ref in refs:
        for row in reader.rows(ref):
            S.need(row['role'] in source['required_roles'] and row.get('subdataset','') in source.get('required_subdatasets',['']),
                   'EVERY_ORIGINAL_ROLE_AND_SUBDATASET_RETAINED')
            if coco is not None:
                base=':'.join(row['source_id'].split(':',4)[:4])
                S.need(base not in coco['scope_source_ids'],'APPROVED_SCOPE_DISPOSITION_CANNOT_APPEAR_AS_AN_IDENTITY_OR_CHEMICAL_VETO')
                if row['source_id'] in wanted:
                    S.need(row.get('inchikeys')==[] and row.get('non_h_composition') is not None
                           and row['source_id'] not in seen,'UNKNOWN_GRAPH_RECOVERY_IS_EXACT_COMPOSITION_ONLY')
                    seen[row['source_id']]=row['non_h_composition']
            batch.extend((kind,key,source['dataset']) for kind,key in C.identity_keys(row))
            roles[row['role']]+=1;datasets[row.get('subdataset','')]+=1;n+=1
            if n%4096==0:
                db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)',batch);batch=[];db.commit();guard.check()
    if batch:db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)',batch)
    S.need(n==expected and set(roles)==set(source['required_roles'])
           and set(datasets)==set(source.get('required_subdatasets',[''])),'COMPLETE_PHYSICAL_IDENTITIES_AND_ROLE_CENSUS_NOT_DEDUP_INDEX_SIZE')
    if coco is not None:
        S.need(set(seen)==wanted,'EVERY_ACCEPTED_EXACT_COMPOSITION_IDENTITY_ACTUALLY_READ')
        for row in coco['ledger']:
            if row['new_exclusion_status']=='EXACT_COMPOSITION_COVERED':
                S.need(all(':'.join(sid.split(':',4)[:4])==row['source_id'] for sid in row['identity_source_ids'])
                       and len(row['exact_compositions'])==len(row['identity_source_ids'])
                       and [seen[sid] for sid in row['identity_source_ids']]==row['exact_compositions'],
                       'ACTUAL_COMPOSITION_ONLY_ROWS_MATCH_EXACT_ACCEPTED_PHYSICAL_SOURCE_EVIDENCE')
    return dict(records=n,roles=dict(roles),subdatasets=dict(datasets))


def constraints(db,reader,source,context,C):
    rules=[];bindings=[row['binding'] for row in context['ledger']]
    for rule in reader.rows(source['lower_bounds']):
        if source['dataset']=='moleculenet':
            S.need(rule['policy_reference']==context['policy'] and rule['subdataset'] in ('ClinTox','PDBbind'),
                   'EXACT_ACCEPTED_CLOSED21_POLICY_AND_SOURCE_BOUND_RULE')
        C.insert_constraint(db,rule,expected_dataset=source['dataset'],accepted_physical_bindings=bindings)
        rules.append(rule)
    if source['dataset']=='moleculenet':
        S.need(len(rules)==2 and {r['subdataset'] for r in rules}=={'ClinTox','PDBbind'},'BOTH_ACTUAL_MOLNET_TYPED_VETOS_RETAINED')
    else:
        S.need({r['rule_id'] for r in rules}==context['expected_rule_ids']
               and len(rules)==len(context['expected_rule_ids']),'ONLY_ACTUALLY_ACCEPTED_COCONUT_RULES_NO_UNAPPROVED_COS_ANTICHAIN')
        by_id={r['rule_id']:r for r in rules}
        for row in context['ledger']:
            for rid in row.get('rule_ids',[]):S.need(by_id[rid]['binding']==row['binding'],'RULE_BOUND_TO_ITS_EXACT_ORIGINAL735_RECORD')
    return len(rules)


def build(plan,proof,out,reader,guard,manifest,ready9,C):
    from .headers import approvals
    sources,mol,coco=approvals(reader,manifest,ready9,C)
    path=out/'excluded_identities_v3.sqlite';S.need(not path.exists(),'FRESH_PRIVATE_SQLITE_ONLY')
    S.need(type(plan['sqlite_cache_bytes']) is int and plan['sqlite_cache_bytes']>=4096,'EXPLICIT_REVIEWED_SQLITE_CACHE_BYTES')
    spill=out/'spill';spill.mkdir();os.environ['SQLITE_TMPDIR']=str(spill)
    db=sqlite3.connect(path);counts={};rule_counts={}
    try:
        db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA cache_size=-'+str(plan['sqlite_cache_bytes']//1024))
        C.install_tables(db)
        for name in sorted(sources):
            guard.check();source=sources[name]
            if name not in ('moleculenet','coconut'):
                refs,expected,coverage=legacy_header(reader,source)
            else:
                for ref in source['raw_artifacts']:reader.verify(ref)
                refs=source['identity_parts'];S.need(refs and all(type(r['rows']) is int and r['rows']>0 for r in refs),'COMPLETE_CLOSED_IDENTITY_PARTS_CENSUS')
                expected=sum(r['rows'] for r in refs);coverage=None
            counts[name]=insert_rows(db,reader,source,refs,expected,C,guard,coco if name=='coconut' else None)
            if coverage and coverage.get('role_counts'):S.need(counts[name]['roles']==coverage['role_counts'],'ORIGINAL_ROLE_MULTIPLICITIES_NOT_RESAMPLED')
            if name in ('moleculenet','coconut'):rule_counts[name]=constraints(db,reader,source,mol if name=='moleculenet' else coco,C)
            db.commit();print(json.dumps(dict(event='ALL11_SOURCE_INDEXED',dataset=name,records=expected)),flush=True)
        S.need(len(C.rules(db))==sum(rule_counts.values()),'DURABLE_COMPLETE_RULE_CENSUS')
        S.need(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'CLOSED_NATIVE_SQLITE_INTEGRITY')
        db.commit()
    finally:db.close()
    S.need(all(not Path(str(path)+suffix).exists() for suffix in ('-wal','-shm','-journal')),'NO_ACTIVE_INDEX_SIDECARS_AT_CLOSURE')
    for ref in plan['data_references']:
        from .reader import key
        if key(ref) in reader.verified:
            actual,_=reader.resolve(ref);S.need(S.frame(actual.stat())==reader.verified[key(ref)],'INPUT_CHANGED_BEFORE_INDEX_CLOSURE')
    guard.check()
    binding=dict(job_id=str(proof['job_id']),uid=os.getuid(),node=proof['node'],boot_id=proof['boot_id'],
        pid=os.getpid(),pid_start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    result=dict(schema=C.INDEX_SCHEMA,status='COMPLETE',source_manifest_reference=plan['source_manifest_reference'],
        sources=counts,database=S.pin(path),all_physical_source_rows_covered=True,original_graph_unknowns_retained=True,
        constraint_source_datasets=['coconut','moleculenet'],actual_constraint_rule_counts=rule_counts,
        constraint_source_datasets_meaning='ORIGINAL_V3_ALLOWED_SOURCE_DOMAINS;_ACTUAL_COUNTS_REPORTED_SEPARATELY',
        original_UNKNOWN_resolved=False,downstream_targets_consumed=False,producer_parent_binding=binding,
        coconut_unknown_physical_dispositions=coco['disposition_counts'],
        physical_coverage_axis='SOURCE_EXCLUSION_OR_PRIOR_ACTUAL_USER_SCOPE_DISPOSITION;_NOT_GRAPH_IDENTITY_REPAIR',
        actual_user_approved_COCONUT_scope_dispositions=len(coco['scope_source_ids']),
        imported_Main_MolNet_original_parent=mol['original_parent'],current_producer_endpoint='218.192.171.238:22',
        parent_transport_manifest=plan['parent_transport_manifest'],
        source_replica_readback=S.save(out/'source_consumption.json',dict(files=reader.consumption)),
        actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING',filtered_pool_complete=False,global_pool_release=False)
    C.index_header(result);guard.check();return result
