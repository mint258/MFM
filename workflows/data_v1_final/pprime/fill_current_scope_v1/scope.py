"""Actual old-ready anti-join and complete ordinary fixed-random metadata scope."""
import itertools,json,pathlib
from . import contract as C
from .source_io import SourceIO
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.identity import fixed_random_ids
from workflows.data_v1_final.conformers.ordinary_postprocess_resume_v1.reuse import common_component
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as OriginalPrepare,io as I
q=OriginalPrepare.q


def references(plan):
    common=C.meta(plan['closed_common_manifest_reference']);qa=C.meta(plan['original_ready_partition_reference'])
    C.need(qa['schema']=='PPRIME_READY_MID_PARTITION_QA_V1' and qa['eligible_MIDs']==1110751 and qa['pairwise_disjoint'] and qa['union_covers_original_ready_MID_universe'],'ORIGINAL_CLOSED_ALL_READY_DOMAIN')
    hrefs=[*qa['shard_header_references'],qa['main190_exclusion_header_reference'],qa['legacy_pilot_exclusion_header_reference']]
    refs=[C.meta(r)['record_reference'] for r in hrefs]
    C.need(len({r['path'] for r in refs})==len(refs),'EXACT_DISJOINT_ORIGINAL_READY_COMPONENT_FILES')
    data=C.unique([*common['membership_tables'],*common['physical_geometry_tables'],*common['uff_identity_tables'],*refs])
    return common,qa,hrefs,refs,data


def freeze(plan,proof,out,b,budget,store):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    out=pathlib.Path(out);out.mkdir();reader=SourceIO(plan,b,budget);db=duckdb.connect(str(out/'scope.duckdb'))
    db.execute('SET threads=16');common,qa,hrefs,ready,data=references(plan)
    # Original closed-function reader retains5659 FAILED1:0 and verifies only its
    # already closed membership/maps, never upgrading the whole parent.
    class Context:
        def __init__(self):self.plan=plan
        def read(self,r):return C.meta(r)
        def require(self,r):return reader.hold(r)
    try:
        common_component(Context(),db)
        db.execute('CREATE TABLE original_ready(molecule_id VARCHAR PRIMARY KEY)')
        for ref in ready:
            path=reader.hold(ref)
            db.execute('INSERT INTO original_ready SELECT molecule_id FROM read_json_auto('+q(path)+',format=\'newline_delimited\')')
        C.need(db.execute('SELECT count(*) FROM original_ready').fetchone()[0]==1110751,'ACTUAL_ALL_ORIGINAL_READY_MID_UNION_NOT_COUNTS_SUBTRACTION')
        db.execute('CREATE TABLE chosen AS SELECT m.* FROM final_common m ANTI JOIN original_ready r USING(molecule_id) WHERE m.common_population AND m.fill_status=\'SUCCESS\' AND m.S_conformers>=2')
        n=db.execute('SELECT count(*) FROM chosen').fetchone()[0]
        C.need(db.execute('SELECT count(*) FROM chosen c LEFT JOIN (SELECT molecule_id,count(*) n FROM uff_sources GROUP BY molecule_id) g USING(molecule_id) WHERE g.n<>c.merged_uff_count OR g.n<c.S_conformers').fetchone()[0]==0,'SAME_COMPLETE_ORDINARY_GEOMETRY_DOMAIN')
        identity_paths=[reader.hold(r) for r in common['uff_identity_tables']]
        db.execute('CREATE VIEW identities AS SELECT * FROM read_parquet(['+','.join(q(p)for p in identity_paths)+'])')
        C.need(db.execute("SELECT count(*) FROM chosen c WHERE NOT EXISTS(SELECT 1 FROM identities i WHERE i.molecule_id=c.molecule_id AND i.identity_namespace='data_v1_fill')").fetchone()[0]==0,'ACTUAL_FILL_PHYSICAL_IDENTITY_WITNESS')
        db.execute('CREATE TABLE ranks(molecule_id VARCHAR,geometry_id VARCHAR,sprime_conf_idx BIGINT,rank BIGINT)')
        cursor=db.cursor();cursor.execute('SELECT g.molecule_id,g.geometry_id,g.sprime_conf_idx FROM uff_sources g JOIN chosen c USING(molecule_id) ORDER BY g.molecule_id,g.sprime_conf_idx')
        def rows():
            while block:=cursor.fetchmany(8192):yield from block
        for mid,group in itertools.groupby(rows(),key=lambda r:r[0]):
            group=list(group);by={r[2]:r[1]for r in group};C.need(len(by)==len(group),'UNIQUE_CLOSED_PHYSICAL_IDS')
            db.executemany('INSERT INTO ranks VALUES(?,?,?,?)',[(mid,by[pid],pid,rank)for rank,pid in enumerate(fixed_random_ids(mid,list(by)))])
            budget.check()
        cursor.close()
        # Original source table and file_group are metadata from the unchanged
        # WP5 pilot/native authorities, not derived from fill package filenames.
        index=next(r for r in b['data'] if r['path']==b['pilot']['record_index']);idx=reader.hold(index)
        molecules=reader.hold(b['population'][1])
        db.execute('CREATE VIEW native_index AS SELECT * FROM read_parquet('+q(idx)+')')
        db.execute('CREATE VIEW molecule_index AS SELECT * FROM read_parquet('+q(molecules)+')')
        db.execute('''CREATE TABLE tasks AS SELECT g.*,c.file_group,
          CASE WHEN x.max_heavy_atoms<=20 THEN '0_20' WHEN x.max_heavy_atoms<=40 THEN '21_40' WHEN x.max_heavy_atoms<=75 THEN '41_75' ELSE 'above_75' END AS size_stratum,
          r.rank AS random_order_rank,to_json(p) AS native_source_json,
          CAST(floor((dense_rank() OVER(ORDER BY g.molecule_id)-1)/50000) AS BIGINT) AS component_index
          FROM uff_sources g JOIN chosen c USING(molecule_id) JOIN ranks r USING(molecule_id,geometry_id,sprime_conf_idx)
          JOIN molecule_index x USING(molecule_id) JOIN native_index p ON p.record_id=g.native_anchor_record_id
          WHERE r.rank<2 AND p.molecule_id=g.molecule_id''')
        C.need(db.execute('SELECT count(*) FROM tasks').fetchone()[0]==2*n,'ACTUAL_TWO_ORIGINAL_FIXED_RANDOM_POINTERS_PER_CHOSEN_MID')
        tables={}
        for name,sql in [('members','SELECT * FROM chosen ORDER BY molecule_id'),('fixed_random','SELECT *,\'fixed_random\' AS method,20261025 AS seed FROM ranks ORDER BY molecule_id,rank'),('tasks','SELECT * FROM tasks ORDER BY component_index,molecule_id,random_order_rank')]:
            path=out/(name+'.parquet');db.execute('COPY ('+sql+') TO '+q(path)+" (FORMAT PARQUET,COMPRESSION ZSTD)");tables[name]=I.pin(path,[out])
        components=[]
        for k,molecules,records in db.execute('SELECT component_index,count(DISTINCT molecule_id),count(*) FROM tasks GROUP BY 1 ORDER BY 1').fetchall():
            components.append(store.json(out/('generation_component_%05d.json'%k),dict(schema='PPRIME_FILL_FIXED_RANDOM_COMPONENT_V1',component_index=k,molecules=molecules,conformer_records=records,maximum_native_calls=12*records,
              scope_source_reference=plan['fill_source_authority_reference'],tasks_reference=tables['tasks'],actual_scope_job_id=str(proof['job_id']),original_first2_seed=20261025,original_protocol_reference=plan['original_protocol_reference'],native_invokes=0)))
        outcomes=C.meta(common['outcome_status_counts'])
        manifest=dict(schema='PPRIME_FILL_FIXED_RANDOM_SCOPE_CLOSED_V1',status='CLOSED_CURRENT_FILL_INPUT_SCOPE_NOT_FINAL_COMMON_OR_QM',actual_job_id=str(proof['job_id']),
          closed_common_manifest_reference=plan['closed_common_manifest_reference'],closed_common_accounting_reference=plan['closed_common_accounting_reference'],original_ready_partition_reference=plan['original_ready_partition_reference'],
          source_ready_molecules=1110751,source_fill_SUCCESS_count=outcomes['train_val_fill_status_counts']['SUCCESS'],source_fill_outcomes_reference=common['outcome_status_counts'],actual_chosen_MIDs=n,actual_first2_records=2*n,tables=tables,component_references=components,
          original_ready_anti_join_performed=True,seed=20261025,complete_ordinary_order_before_first2=True,uses_energy_or_diversity_D7=False,
          new_UFF_QM_calls=0,old_parent_4525659_state='FAILED',old_parent_upgraded=False,final_Common_or_training_release=False)
        return store.json(out/'scope_manifest.json',manifest),manifest
    finally:db.close();reader.close()