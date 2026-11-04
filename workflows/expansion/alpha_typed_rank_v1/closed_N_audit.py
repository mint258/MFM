"""Full read-only N sort-key uniqueness; never introduce a new tie rule."""
import os
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..common import stable_hash
from ..exact_nn_cached_v1.sql_runtime import configure
from ..alpha_closed500_handoff_v1.sql import SQLStopper

KEYS="""heavy_stratum,element_combination,(v1_scaffold_count=0),(v1_ring_system_count=0),
  nearest_v1_tanimoto,v1_scaffold_count,v1_ring_system_count,n_hash(full_key)"""


def stamp(s):return {k:getattr(s,k)for k in ('st_dev','st_ino','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}


def summary(db):
    # full_key/CID must NOT be additional GROUP BY terms: that would hide hash
    # collisions in the actual original within-stratum ordering tuple.
    rows,unique_keys,unique_cids=db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM n_candidates').fetchone()
    values=db.execute('''WITH grouped AS (SELECT '''+KEYS+''',count(*) AS members
      FROM n_candidates GROUP BY '''+KEYS+''') SELECT count(*),coalesce(sum(members),0),
      count(*) FILTER(WHERE members>1),coalesce(sum(members) FILTER(WHERE members>1),0),coalesce(max(members),0)
      FROM grouped''').fetchone()
    groups,mass,duplicates,duplicate_rows,largest=map(int,values)
    Q.need(int(rows)==int(unique_keys)==int(unique_cids)==mass,'Complete remaining-candidate identities and grouped mass required')
    return dict(n_candidate_rows=int(rows),distinct_full_keys=int(unique_keys),distinct_CIDs=int(unique_cids),
      grouped_mass=mass,complete_sort_tuple_groups=groups,duplicate_tuple_groups=duplicates,
      rows_in_duplicate_tuples=duplicate_rows,maximum_tuple_multiplicity=largest,
      strict_N_order_independent_of_query_row_order=(duplicates==0),full_relation_scanned=True,
      group_by_original_tuple_only=True,no_tie_rule_added=True)


def audit(rank,plan,out,check):
    import duckdb
    source=Path(rank['queues']['path']).parent/'ranking.duckdb';before=stamp(source.lstat())
    Q.need(source.is_file()and not source.is_symlink()and before['st_uid']==1264 and before['st_nlink']==1
      and not Path(str(source)+'.wal').exists(),'Actual closed checkpointed DuckDB, never active writer/WAL')
    Path(out).mkdir(parents=True,exist_ok=False);db=duckdb.connect(str(source),read_only=True);monitor=None
    try:
        configure(db,plan,Path(out)/'spill');monitor=SQLStopper(db,check)
        with source.open('rb')as held:
            Q.need(stamp(os.fstat(held.fileno()))==before,'Actual held closed DB FD required')
            db.create_function('n_hash',lambda key:stable_hash('N-tie',20261025,key),['VARCHAR'],'VARCHAR')
            result=summary(db)
            Q.need(result['n_candidate_rows']==rank['pool_molecules']-5000000,
              'Entire non-R remainder, not selectedN/firstbatch/prefix, must be audited')
            Q.need(stamp(os.fstat(held.fileno()))==before==stamp(source.lstat()),'Closed rank DB frame changed during read-only scan')
        result.update(schema='ALPHA_CLOSED_COMPLETE_N_SORT_TUPLE_AUDIT_V1',
          status='UNIQUE_ORIGINAL_N_TUPLES_PENDING_ACTUAL_C0_REVIEW'if result['strict_N_order_independent_of_query_row_order']else'REJECT_STRICT_SAME_N_CLAIM_DUPLICATE_TUPLES',
          source_database_path=str(source),source_current_frame_before=before,source_current_frame_after=stamp(source.lstat()),
          source_opened_read_only=True,whole_database_SHA_recomputed=False,full_sql_scan_extra_IO_performed=True,
          source_database_historically_SHA_pinned_by_original_rank_receipt=False,group_by_sql=KEYS,
          original_stable_hash_source_reference=Q.reference(Path(stable_hash.__code__.co_filename)),
          source_plan_reference=rank['resource_plan'])
        return Q.write(Path(out)/'receipt.json',result),result
    finally:
        if monitor is not None:monitor.close()
        db.close()
