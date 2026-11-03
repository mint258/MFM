"""Actual CPU closed-preselection adoption; never projects canonical HoF."""
import json,os,pathlib,sqlite3
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import hof_resume as H
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare as PRIORITY

class Context:
    def __init__(self,p,proof,out,budget):self.plan=p;self.proof=proof;self.out=pathlib.Path(out);self.budget=budget;self.reserved={}
    def check(self):self.budget.check()
    def require(self,r):return I.require(r)
    def authorized(self,refs):
        root=C.meta(self.plan['hof_closed_prefix_reuse_review_reference'])['old_output_root']
        for r in refs:
            if r['path']not in I.ALLOWED:I.allow(r,origin=root)
    def read(self,r,limit=512<<20):return I.load_data(r,limit)
    def reserve(self,key,n):
        C.need(key not in self.reserved and I.unique_bytes(self.out)+sum(self.reserved.values())+n+(256<<20)<self.plan['whole_output_cap_bytes'],'CLOSED_COPY_REAL_SPACE_CAP');self.reserved[key]=n
    def release(self,key):self.reserved.pop(key,None)
    def reference(self,path):return I.allow(I.pin(path))
    def commit_closed_copy(self,path,n):C.need(pathlib.Path(path).stat().st_size==n,'CLOSED_COPY_SIZE_REAL')
    def write_json_new(self,path,value):return I.save(path,value)

def restore(ctx):
    import duckdb
    _,review,qa,origin,_=C.reviews(ctx.plan);base=C.meta(ctx.plan['base_cache_plan_reference'])
    receipt=I.load_data(review['failed_receipt_reference'],16<<20)
    C.need(receipt['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1' and str(receipt['job_id'])==origin['job_id']=='4524738'
      and receipt['startup_proof_reference']==origin['proof_reference'] and receipt['closed_state_reference']==review['closed_state_reference']
      and receipt['HOF_projection_complete']is False and not receipt['state_counts'] and not receipt['unknown'],
      'EXACT_OLD_FAILED_ZERO_CACHE_PARENT_NOT_C0_OR_HOF_COMPLETE')
    pre=receipt['pilot_preselection_reference'];C.reference(pre)
    C.need(pre['path']==review['pilot_preselection_locator'],'ONLY_OLD_RECEIPT_POSITIVE_PRESELECTION_AT_ROOT_FIXED_LOCATOR')
    I.allow(pre,origin=review['old_output_root']);ctx.hof_resume_preselection_reference=pre
    closed=pathlib.Path(review['closed_state_reference']['path']);C.need(not pathlib.Path(str(closed)+'.wal').exists(),'ORIGINAL_CLOSED_DUCKDB_NO_WAL')
    clone=H.clone(ctx,review['closed_state_reference'],ctx.out/'closed_original.duckdb')
    db=duckdb.connect(str(ctx.out/'work.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
    scratch=ctx.out/'sql_tmp';scratch.mkdir();db.execute('SET temp_directory='+H.C.q(str(scratch)))
    db.execute('ATTACH '+H.C.q(clone['path'])+' AS old (READ_ONLY)')
    for table in ('formal','roster','pilot_scalar_membership','pilot_complete_old_ranked','pilot_priority'):
        db.execute('CREATE VIEW '+table+' AS SELECT * FROM old.'+table)
    C.need(db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM formal').fetchone()==(11231854,11231854,1220466),'FULL_ORIGINAL_CANONICAL_IDENTITIES_NOT_SELECTED_BY_CACHE_SUCCESS')
    descriptors=I.load_data(ctx.plan['future_shards_reference'],8<<20)
    if type(descriptors)is dict:descriptors=descriptors['descriptors']
    # Exact original function copies and bidirectionally checks all existing tables.
    copied,priority,diagnostic,_=H.restore_priority(ctx,db,base,review,descriptors)
    value=I.load_data(copied,8<<20);C.need(set(value['tables'])==C.ALLOWED_TABLES,'EXACT_ALL_NESTED_GUIDE_TABLES_PRESENT_NO_COUNT_DOWNGRADE')
    for n in C.NESTED:C.need(db.execute("SELECT count(*) FROM read_parquet(?)",[value['tables']['train_'+str(n)]['path']]).fetchone()[0]==n,'ORIGINAL_NESTED_TABLE_ACTUAL_COUNT')
    C.need(len(priority)==55000 and len(diagnostic)==20000,'ACTUAL_FROZEN55K_AND_GLOBAL20K_NOT_INTERSECTION')
    policy,sources,refs=PRIORITY.policy(ctx.plan['pilot_priority_review_reference'],base)
    for ref in refs:I.allow(ref,origin=pathlib.Path(ref['path']).parent);I.require(ref)
    I.require(base['formal_source'])
    cols='record_id,molecule_id,source_path,real_index,record_payload_sha256,total_atoms,smiles,file_group,conformer_id'
    current='SELECT '+cols+' FROM read_parquet('+H.C.q(base['formal_source']['path'])+')'
    C.need(db.execute('SELECT count(*) FROM (SELECT '+cols+' FROM formal EXCEPT ALL '+current+')').fetchone()[0]==0
      and db.execute('SELECT count(*) FROM ('+current+' EXCEPT ALL SELECT '+cols+' FROM formal)').fetchone()[0]==0,'CURRENT_WHOLE_SHA_FORMAL_ALL_RECORD_FIELDS_EQUAL_CLOSED_ORIGINAL')
    # Verify source roles/current scalar counts without changing the frozen selection.
    q=H.C.q;roles='read_parquet(['+','.join(q(r['path']) for r in policy['role_refs'])+'])'
    db.execute('CREATE VIEW current_roles AS SELECT * FROM '+roles)
    db.execute('CREATE VIEW current_permol AS SELECT * FROM read_parquet('+q(base['per_molecule']['path'])+')')
    C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id),sum(records) FROM current_roles').fetchone()==(1220466,1220466,11231854),'WHOLE_ORIGINAL_ROLES_CURRENT_MASS')
    db.execute('CREATE TABLE mother AS SELECT * FROM read_parquet('+q(value['tables']['complete_old_mother']['path'])+')')
    db.execute('CREATE UNIQUE INDEX mother_mid ON mother(molecule_id)')
    C.need(db.execute('SELECT count(*) FROM mother m JOIN current_roles r USING(molecule_id) WHERE m.effective_role<>r.effective_role OR m.source_role<>r.source_role OR m.records<>r.records').fetchone()[0]==0,'ALL_ORIGINAL_SOURCE_AND_EFFECTIVE_ROLES_PRESERVED')
    C.need(db.execute('SELECT count(*) FROM mother m JOIN current_permol p USING(molecule_id) WHERE m.S_conformers<>p.S_conformers OR m.Sprime_conformers<>p.Sprime_conformers OR m.S_usable_conformers<>p.S_usable_conformers OR m.Sprime_status IS DISTINCT FROM p.Sprime_status').fetchone()[0]==0,'ACCEPTED_ORIGINAL_COMPLETE_SPRIME_COUNTS_UNCHANGED')
    db.execute('CREATE TABLE diagnostic_mids AS SELECT molecule_id FROM read_parquet('+q(value['tables']['diagnostic20k_molecule_preselection']['path'])+')')
    C.need(db.execute("SELECT count(*) FROM diagnostic_mids d JOIN mother m USING(molecule_id) WHERE m.effective_role='TRAIN' AND m.S_conformers>=2 AND m.Sprime_conformers>=2").fetchone()[0]==20000,'WHOLE20K_CURRENT_TRAIN_AND_BOTH_ORIGINAL_SOURCE_COUNTS')
    return db,base,copied,value,policy
