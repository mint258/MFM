"""Clone a closed fixed1M statistics DB and ingest only full accepted Common."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from .. import alpha_common_followup_plans_v1 as H


def stat_frame(s):
    H.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'Own regular single-link database required')
    return [s.st_dev,s.st_ino,s.st_uid,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def frame(path):return stat_frame(Path(path).lstat())


def same_cross_node_frame(actual,planned):
    H.need(len(actual)==len(planned)==6 and all(type(v)is int for v in [*actual,*planned]),'Exact six-field physical witnesses required')
    # st_dev identifies the local mount namespace, not portable file identity.
    # The rest remain strict; a fresh wholeSHA under one locked FD is mandatory.
    return actual[1:]==planned[1:]


def reports_budget_value(budget,plan):
    H.need(budget.get('schema')=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget.get('reviewer')=='root'
      and budget.get('endpoint')=='218.192.171.238:22' and budget.get('uid')==1264
      and budget.get('quota_root')=='/gfshome/alpha' and budget.get('effective_hard_limit_bytes')==2199023255552
      and budget['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes']
      and budget['scope_total_caps_bytes']['reports']==plan['output_cap_bytes'], 'Actual matching Root all-future reports budget required')
    value=budget['other_future_reserved_bytes_for_each_scope']['reports']
    H.need(type(value)is int and value>=0,'Actual nonnegative Root reports other-future reservation')
    return value


def baseline_binding(plan):
    review=H.load(H.verify(plan['baseline_acceptance_reference']))
    parent=review['actual_parent']
    H.need(review['schema']=='ROOT_ALPHA_BASELINE_POPULATION_STATISTICS_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='ACCEPTED_COMPLETE_FIXED_1M_POPULATION_TABLES' and review['reviewer']=='root'
      and review['uid']==1264 and review['populations']=={'pubchem_1m':1000000}
      and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['UID']=='1264'
      and parent in review['actual_parents'],'Independent actual fixed1M C0 acceptance required')
    receipt=H.load(H.verify(review['producer_receipt_reference']))
    H.need(receipt['actual_parent']['SlurmJobID']==parent['JobIDRaw']
      and receipt['population_manifest_references']=={'pubchem_1m':plan['baseline_population_reference']},
      'Original baseline population manifest/source cannot change')
    oldplan=H.load(H.verify(receipt['plan_reference']))
    population=H.load(H.verify(plan['baseline_population_reference']))
    H.verify(plan['baseline_recipe_reference'])
    H.need(population['authority_reference']==oldplan['baseline_receipt_reference'],
      'Original frozen baseline receipt cannot change')
    H.verify(population['authority_reference'])
    H.need(population['population']=='pubchem_1m' and population['expected_molecules']==1000000
      and population['sampling']['uniform'] is True
      and population['baseline_pool_phase']=='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY',
      'Original frozen predecontamination uniform baseline required')
    scope=H.load(H.verify(plan['baseline_scope_reference']))
    H.need(scope['analysis_version']==oldplan['analysis_version']
      and scope['functional_group_recipe_reference']==receipt['functional_group_recipe_reference']
      and plan['baseline_recipe_reference']==receipt['functional_group_recipe_reference'], 'Original scope/recipe cannot change')
    root=Path(oldplan['output_directory'])
    H.need(plan['baseline_database_path']==str(root/'counted_statistics.sqlite')
      and plan['baseline_scope_reference']['path']==str(root/'analysis_scope.json')
      and plan['baseline_population_reference']['path']==str(root/'pubchem_baseline_population.json'),
      'Original closed stage location must remain bound')
    return receipt,oldplan,scope


def strict_addition(plan,old_scope):
    H.need(plan.get('extension_policy')=='STRICT_ADD_ONLY_FULL_ACCEPTED_COMMON_V1'
      and plan.get('population_names')==['pubchem_1m','v1_common']
      and plan.get('analysis_version') and plan['analysis_version']!=old_scope['analysis_version'],
      'Only a new strict fullCommon addition is allowed; no rewritten old scope')
    manifest=H.load(H.verify(plan['common_reference_manifest']))
    if manifest.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
        from ..exact_nn_cached_v1.alpha_common_repaired import validate_manifest
        return validate_manifest(manifest)
    H.actual_common_parent(manifest)
    from ..exact_nn_cached_v1.alpha_common import validate_manifest
    return validate_manifest(manifest)


def logical_baseline(db,check=lambda:None):
    H.need(db.execute('SELECT name,expected,complete FROM populations').fetchall()==[('pubchem_1m',1000000,1)]
      or set(db.execute('SELECT name,expected,complete FROM populations'))=={('pubchem_1m',1000000,1),('v1_common',1196122,1)},
      'Only closed baseline and optional fullCommon populations allowed')
    digest=hashlib.sha256();counts={}
    queries={
      'populations':"SELECT * FROM populations WHERE name='pubchem_1m' ORDER BY name",
      'required_members':"SELECT * FROM required_members WHERE population='pubchem_1m' ORDER BY identity",
      'seen':"SELECT * FROM seen WHERE population='pubchem_1m' ORDER BY identity",
      'counts':"SELECT * FROM counts WHERE population='pubchem_1m' ORDER BY kind,key",
      'moments':"SELECT * FROM moments WHERE population='pubchem_1m' ORDER BY field"}
    for table,query in queries.items():
        count=0;digest.update(table.encode()+b'\0')
        for row in db.execute(query):
            count+=1;raw=json.dumps(row,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
            digest.update(len(raw).to_bytes(8,'big')+raw)
            if count%4096==0:check()
        counts[table]=count
    H.need(counts['required_members']==counts['seen']==1000000 and counts['moments']==11,'Actual closed1M member/numeric census required')
    H.need(db.execute("SELECT count(*) FROM comparisons").fetchone()[0]==0
      and db.execute('SELECT count(*) FROM nearest').fetchone()[0]==0,'No nearest results are substituted or claimed')
    H.need(db.execute("SELECT count(*) FROM required_members r LEFT JOIN seen s USING(population,identity) WHERE r.population='pubchem_1m' AND s.identity IS NULL").fetchone()[0]==0,'Exact baseline membership anti-join required')
    for field,raw in db.execute("SELECT field,state FROM moments WHERE population='pubchem_1m'"):
        value=json.loads(raw);H.need(value['n']==sum(value['bins'])==1000000 and value['field']==field,'Every original moment denominator and bin mass must remain1M')
    return dict(sha256=digest.hexdigest(),logical_rows_by_table=counts)


def clone(plan,out,guard):
    source=Path(plan['baseline_database_path']);expected=plan['baseline_database_physical_frame']
    actual=frame(source)
    H.need(same_cross_node_frame(actual,expected) and expected[2]==1264,'Closed baseline inode/UID/size/times changed since metadata plan')
    for suffix in ('-wal','-journal'):
        H.need(not Path(str(source)+suffix).exists(),'Source must be quiescent closed DELETE-mode DB')
    read=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    try:
        read.execute('BEGIN');read.execute('SELECT count(*) FROM populations').fetchone()
        H.need(read.execute('PRAGMA journal_mode').fetchone()[0]=='delete','Original closed DELETE mode required')
        dest=out/'counted_statistics.sqlite';digest=hashlib.sha256()
        with source.open('rb') as stream,dest.open('xb') as target:
            H.need(stat_frame(os.fstat(stream.fileno()))==actual==frame(source),'Actual same local source FD/path after SQLite read lock')
            while True:
                guard.check();block=stream.read(8<<20)
                if not block:break
                digest.update(block);target.write(block)
            target.flush();os.fsync(target.fileno())
            H.need(stat_frame(os.fstat(stream.fileno()))==actual==frame(source),'Original database changed during locked same-FD copy')
        H.need(frame(source)==actual and same_cross_node_frame(actual,expected),'Original database changed during locked clone')
        target_digest=hashlib.sha256()
        target_frame=frame(dest)
        with dest.open('rb') as copied:
            H.need(stat_frame(os.fstat(copied.fileno()))==target_frame,'Actual destination hash FD')
            while True:
                guard.check();block=copied.read(8<<20)
                if not block:break
                target_digest.update(block)
            H.need(stat_frame(os.fstat(copied.fileno()))==target_frame==frame(dest),'Same stable destination hash FD/path')
        copy_ref=dict(path=str(dest),bytes=dest.stat().st_size,sha256=target_digest.hexdigest())
        H.need(copy_ref['sha256']==digest.hexdigest() and copy_ref['bytes']==expected[3],'Exact source/copy database byte parity required')
        return dict(source_reference=dict(path=str(source),bytes=expected[3],sha256=digest.hexdigest()),
          initial_clone_reference=copy_ref,source_physical_frame=actual,planned_source_physical_frame=expected,
          device_namespace_not_cross_node_identity=True,cross_node_inode_UID_size_times_exact=True,
          actual_same_local_source_FD_frame_verified=True,source_READ_transaction_held_during_copy=True,
          historical_original_C0_database_SHA_claimed=False)
    finally:read.rollback();read.close()


def run(plan_path,startup_path):
    from ..alpha_runtime_v1.profile import admit
    from ..alpha_runtime_v1.guard import Guard
    from ..distribution_report_v1 import __main__ as original
    from ..distribution_report_v1 import functional_groups as F
    plan=H.load(plan_path);proof=H.load(startup_path)
    H.need(plan['schema']=='ALPHA_POPULATION_ONLY_STRICT_COMMON_EXTENSION_PLAN_V1'
      and proof['request']['producer_plan_reference']==H.pin(plan_path)
      and proof['request']['execution_argv']==plan['execution_argv'] and proof['uid']==os.getuid()==1264
      and proof['endpoint']=='218.192.171.238:22'
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
      and str(proof['job_id'])==os.environ['SLURM_JOB_ID'],'Actual independent Alpha extension plan/startup required')
    for source in [*Path(__file__).parent.glob('*.py'),Path(H.__file__)]:
        H.need(H.pin(source) in proof['request']['source_references'],'Actual extension/helper source must be in startup proof')
    if plan.get('all_future_storage_budget_review_reference'):
        budget=H.load(H.verify(plan['all_future_storage_budget_review_reference']))
        H.need(reports_budget_value(budget,plan)==plan['other_future_reserved_bytes'],'Actual reports future reservation must match pinned Root review')
    actual=admit(plan);receipt,oldplan,scope=baseline_binding(plan);common=strict_addition(plan,scope)
    for ref in receipt['source_references']:H.verify(ref)
    original_files=[H.pin(p) for p in sorted(Path(original.__file__).parent.glob('*.py'))]
    H.need(original_files==receipt['source_references'],'Use exact original distribution module sources, never a changed accumulator')
    H.need(F.recipe()==H.load(H.verify(plan['baseline_recipe_reference'])),'Same native functional-group recipe required')
    out=Path(plan['output_directory']);H.need(not out.exists(),'Independent fresh extension output required')
    out.mkdir(parents=True);guard=Guard(plan)
    try:
        clone_proof=clone(plan,out,guard)
        db=sqlite3.connect(out/'counted_statistics.sqlite')
        try:
            row=db.execute("SELECT manifest FROM populations WHERE name='pubchem_1m'").fetchone()
            H.need(row is not None and json.loads(row[0])==plan['baseline_population_reference'],'Cloned DB baseline manifest changed')
            before=logical_baseline(db,guard.check)
        finally:db.close()
        # New root has its own honest scope. Keep the exact original scope as
        # immutable lineage; never edit old analysis_scope or bypass its guard.
        H.save(out/'origin_analysis_scope.json',scope)
        common_population=dict(schema='EXPANSION_DISTRIBUTION_POPULATION_V1',status='COMPLETE',population='v1_common',
          population_scope='FULL_DECLARED_POPULATION',expected_molecules=1196122,
          authority_reference=plan['common_reference_manifest'],authority_count_pointer='/common_molecules',
          authority_kind='FINAL_FULL_COMMON_MEMBERSHIP',is_sample=False,population_roles=['TRAIN','VAL'],
          membership=dict(identity_column='molecule_id',artifacts=[dict(**H.triple(common['projection']),format='jsonl',rows=1196122)]),
          features=dict(identity_column='molecule_id',artifacts=[dict(**H.triple(common['structural_features']),format='jsonl',rows=1196122)]),
          allow_additive_descriptor_completion=False,original_Alpha_Common_reference=plan['common_reference_manifest'])
        common_ref=H.save(out/'v1_common_population.json',common_population)
        derived={**plan,'schema':'EXPANSION_DISTRIBUTION_PLAN_V1','population_manifests':[common_ref],
          'nearest_manifests':[],'stage':'population_tables'}
        derived.pop('baseline_receipt_reference',None)
        derived_ref=H.save(out/'distribution_extension_plan.json',derived)
        H.save(out/'clone_subset_proof.json',dict(schema='ALPHA_FIXED1M_DATABASE_CLONE_SUBSET_PROOF_V1',
          baseline_acceptance_reference=plan['baseline_acceptance_reference'],baseline_population_reference=plan['baseline_population_reference'],
          original_scope_reference=plan['baseline_scope_reference'],original_recipe_reference=plan['baseline_recipe_reference'],
          new_analysis_version=plan['analysis_version'],added_populations=['v1_common'],new_population_reference=common_ref,
          clone=clone_proof,baseline_logical_digest_before=before,old_stage_modified=False))
    finally:guard.close()
    result=original.run(Path(derived_ref['path']),'population_tables',startup_proof=startup_path)
    guard=Guard(plan)
    try:
        db=sqlite3.connect((out/'counted_statistics.sqlite').as_uri()+'?mode=ro',uri=True)
        try:after=logical_baseline(db,guard.check)
        finally:db.close()
        H.need(before==after,'Every retained baseline logical row must remain exactly unchanged')
        H.need(set(result['population_manifest_references'])=={'pubchem_1m','v1_common'}
          and result['population_manifest_references']['pubchem_1m']==plan['baseline_population_reference'],'Exact old baseline and only fullCommon addition required')
        table_receipt=Path(result['artifacts'][0]['path']).parent/'receipt.json'
        return H.save(out/'receipt.json',dict(schema='ALPHA_POPULATION_ONLY_STRICT_COMMON_EXTENSION_PRODUCER_V1',
          status='POPULATION_TABLES_COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_REVIEW',plan=H.pin(plan_path),startup_proof=H.pin(startup_path),
          uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],endpoint='218.192.171.238:22',profile_admission=actual,
          original_population_tables_receipt=result,original_population_tables_receipt_reference=H.pin(table_receipt),
          clone_subset_proof_reference=H.pin(out/'clone_subset_proof.json'),
          baseline_logical_digest_before=before,baseline_logical_digest_after=after,
          populations={'pubchem_1m':1000000,'v1_common':1196122},baseline_rows_reenriched=0,
          task2_1_baseline_comparison_complete=False,nearest_completion_claimed=False,old_stage_modified=False,runtime=guard.receipt()))
    finally:guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.plan,a.startup_proof),sort_keys=True))


if __name__=='__main__':main()
