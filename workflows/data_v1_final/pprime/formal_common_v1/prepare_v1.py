"""Plan fixed first-two baseline views, or materialize one bounded batch. No QM."""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

from common_v1 import IO, frozen_authorities, load, paths_sql, pilot_review, q, refs, runtime, task_key

VERIFIED_SOURCES = {}


@lru_cache(maxsize=2)
def row_group(path, number):
    import pyarrow.parquet as pq
    return pq.ParquetFile(path).read_row_group(number)


def coordinate_sha(xyz):
    flat = [float(v) for row in xyz for v in row]
    if any(len(row) != 3 for row in xyz) or not flat or not all(__import__('math').isfinite(v) for v in flat):
        raise ValueError('FINITE_N_BY_THREE_COORDINATES_REQUIRED')
    return hashlib.sha256(struct.pack('<' + 'd'*len(flat), *flat)).hexdigest()


def order_contract(rows, mid):
    """Pure fixture boundary: original int64 IDs only, never an expanded N1 view."""
    ids = [r['sprime_conf_idx'] for r in rows]
    if any(type(i) is not int or i < 0 or i > 9223372036854775807 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('BASELINE_ONLY_DISTINCT_INTEGER_CONFORMERS_REQUIRED')
    expected = sorted(rows, key=lambda r: (IO.stable_key(20261025, mid, 'uff_sprime', r['sprime_conf_idx']), str(r['sprime_conf_idx'])))
    if [r['rank'] for r in expected] != list(range(len(rows))):
        raise ValueError('FROZEN_ORDER_DISAGREES_WITH_SB2_STABLE_KEY')
    return expected[:2]


def connect():
    import duckdb
    import shutil
    import tempfile
    if shutil.disk_usage('/tmp').free<8*1024**3:
        raise ValueError('METADATA_LOCAL_SCRATCH_REQUIRES8GIB_FREE')
    class MetadataDB:
        def __init__(self):
            self.path=Path(tempfile.mkdtemp(prefix='pprime_meta_',dir='/tmp'))
            self.connection=duckdb.connect()
            self.connection.execute("SET threads=16; SET memory_limit='20GB'")
            self.connection.execute('SET temp_directory='+q(self.path))
            self.connection.execute("SET max_temp_directory_size='4GB'")
        def __getattr__(self,name):return getattr(self.connection,name)
        def close(self):
            self.connection.close()
            if self.path.exists() and not any(self.path.iterdir()):self.path.rmdir()
    return MetadataDB()


def plan(a, c, pilot):
    decision, real, gates = pilot_review(a.pilot_review, c['pilot_config']['path'])
    if real.get('retention_policy')!=c['raw_policy']:
        raise ValueError('ACTUAL_PILOT_MUST_HAVE_REGISTERED_STABLE_RAW_RETENTION_POLICY')
    cp, op, gp = IO.reference(a.common_manifest), IO.reference(a.order_manifest), IO.reference(a.geometry_manifest)
    common, members, orders, maps = frozen_authorities(cp, op, gp)
    if common.get('roles_manifest_sha256')!=pilot['role_manifest']['sha256']:
        raise ValueError('FROZEN_TRAIN_ROUTINE_VAL_ROLE_AUTHORITY_CHANGED')
    import pyarrow as pa
    import pyarrow.parquet as pq
    db = connect()
    for name, pins in (('m', members), ('o', orders), ('g', maps)):
        db.execute('CREATE VIEW '+name+' AS SELECT * FROM read_parquet('+paths_sql(pins)+')')
    mc = {r[0]: r[1] for r in db.execute('DESCRIBE m').fetchall()}
    gc = {r[0]: r[1] for r in db.execute('DESCRIBE g').fetchall()}
    if mc.get('common_population') != 'BOOLEAN' or gc.get('sprime_conf_idx') != 'BIGINT':
        raise ValueError('FROZEN_BOOLEAN_MEMBERSHIP_AND_INT64_BASELINE_UFF_IDS_REQUIRED')
    if db.execute('SELECT count(*)-count(DISTINCT molecule_id) FROM m').fetchone()[0] or db.execute('SELECT count(*) FROM m WHERE common_population IS NULL').fetchone()[0]:
        raise ValueError('UNIQUE_EXPLICIT_COMMON_MEMBERSHIP_REQUIRED')
    if db.execute('SELECT count(*) FROM (SELECT geometry_id FROM g GROUP BY 1 HAVING count(*)<>1)').fetchone()[0]:
        raise ValueError('CANONICAL_GEOMETRY_ID_NOT_UNIQUE')
    if db.execute("SELECT count(*) FROM g WHERE geometry_source='uff_sprime' AND (sprime_conf_idx IS NULL OR sprime_conf_idx<0)").fetchone()[0]:
        raise ValueError('OPAQUE_OR_NULL_N1_EXTENSION_FORBIDDEN_IN_BASELINE_MAP')
    if db.execute("SELECT count(*) FROM (SELECT molecule_id,geometry_source,method,rank FROM o GROUP BY ALL HAVING count(*)<>1)").fetchone()[0]:
        raise ValueError('ORDER_RANK_COLLISION')
    if db.execute("""SELECT count(*) FROM o JOIN m USING(molecule_id) LEFT JOIN g USING(geometry_id,molecule_id,geometry_source)
       WHERE m.common_population AND o.geometry_source='uff_sprime' AND o.method='fixed_random' AND g.geometry_id IS NULL""").fetchone()[0]:
        raise ValueError('ORDER_GEOMETRY_MISSING_FROM_CANONICAL_MAP')
    order_manifest=json.loads(a.order_manifest.read_text())
    basis=order_manifest.get('random_identity_basis')
    if basis=='canonical_sprime_conf_idx':
        identity_expr='CAST(g.sprime_conf_idx AS VARCHAR)'
    elif basis=='original_physical_conformer_identity' and 'random_order_conformer_id' in gc:
        identity_expr='CAST(g.random_order_conformer_id AS VARCHAR)'
    else:
        raise ValueError('FROZEN_ORDER_RANDOM_IDENTITY_BASIS_AND_EXPLICIT_MAP_REQUIRED_NO_CANONICAL_REHASH_GUESS')
    db.execute("""CREATE TABLE u AS SELECT o.molecule_id,o.geometry_id,o.rank,g.sprime_conf_idx,"""+identity_expr+""" AS random_order_conformer_id
      FROM o JOIN g USING(geometry_id,molecule_id,geometry_source)
      JOIN m USING(molecule_id) WHERE m.common_population AND o.geometry_source='uff_sprime' AND o.method='fixed_random'""")
    if db.execute("SELECT count(*) FROM u WHERE rank<0").fetchone()[0]:
        raise ValueError('ZERO_BASED_NONNEGATIVE_RANK_REQUIRED')
    # Validate the entire fixed-random baseline sequence, not merely two plausible IDs.
    db.execute("""CREATE TABLE checked AS SELECT *,row_number() OVER(PARTITION BY molecule_id ORDER BY
      sha256('data-v1-conformer-order:20261025:'||molecule_id||':uff_sprime:'||random_order_conformer_id),
      random_order_conformer_id)-1 AS expected_rank FROM u""")
    if db.execute('SELECT count(*) FROM u WHERE random_order_conformer_id IS NULL').fetchone()[0]:
        raise ValueError('NULL_FIXED_RANDOM_IDENTITY_FORBIDDEN')
    if db.execute("""SELECT count(*) FROM g JOIN m USING(molecule_id) LEFT JOIN u USING(geometry_id,molecule_id)
      WHERE m.common_population AND g.geometry_source='uff_sprime' AND u.geometry_id IS NULL""").fetchone()[0]:
        raise ValueError('EVERY_COMMON_UFF_GEOMETRY_NEEDS_A_FIXED_RANDOM_RANK')
    if db.execute('SELECT count(*) FROM checked WHERE rank<>expected_rank').fetchone()[0]:
        raise ValueError('ALL_FROZEN_RANDOM_RANKS_MUST_MATCH_SB2_STABLE_KEY')
    expected_col = 'S_conformers' if 'S_conformers' in mc else 'expected_conformers'
    db.execute('CREATE TABLE counts AS SELECT m.*,coalesce(u.n,0) AS parent_count FROM m LEFT JOIN (SELECT molecule_id,count(*) AS n FROM u GROUP BY 1) u USING(molecule_id) WHERE m.common_population')
    if db.execute("SELECT count(*) FROM counts WHERE effective_role NOT IN ('TRAIN','VAL') OR source_role NOT IN ('TRAIN','FULL')").fetchone()[0]:
        raise ValueError('ONLY_FROZEN_TRAIN_ROUTINE_VAL_COMMON_ALLOWED')
    if db.execute('SELECT count(*) FROM counts WHERE parent_count<2 AND '+expected_col+'<>1').fetchone()[0]:
        raise ValueError('NON_N1_COMMON_HAS_INSUFFICIENT_FROZEN_ORDER_GEOMETRIES')
    if db.execute('SELECT count(*) FROM counts WHERE parent_count<'+expected_col).fetchone()[0]:
        raise ValueError('COMMON_UFF_COUNT_SHORT_OF_ORIGINAL_PM7_N')
    # A common N1 molecule remains common and pending. It is never deleted or copied.
    pending = db.execute('SELECT molecule_id,effective_role,'+expected_col+' AS original_N,parent_count FROM counts WHERE parent_count<2 ORDER BY molecule_id').fetch_arrow_table()
    source_anchor = 'native_anchor_record_id' if 'native_anchor_record_id' in gc else 'source_record_id'
    for required in ('source_path','source_sha256','source_bytes','source_format','source_row_index','atom_order_sha256'):
        if required not in gc:
            raise ValueError('CANONICAL_MAP_MISSING_PHYSICAL_POINTER:' + required)
    if db.execute("""SELECT count(*) FROM (SELECT g.molecule_id,g.source_path,g.source_row_index,g.source_member
       FROM g JOIN m USING(molecule_id) WHERE m.common_population AND g.geometry_source='uff_sprime'
       GROUP BY ALL HAVING count(*)>1)""").fetchone()[0]:
        raise ValueError('DUPLICATED_PHYSICAL_ROW_CANNOT_INVENT_SECOND_UFF_GEOMETRY')
    # The formal source SHA is inherited from the registered pilot authority. This
    # metadata scan runs on compute20; it never opens original LMDB environments.
    for pin in pilot['large_authority_pins']:
        IO.require_pin(pin, full_hash=False)
    columns = [name for name in gc if name not in {'effective_role','source_role','record_id','file_group','size_stratum','batch_id','random_order_rank','native_source_json'}]
    projection = ','.join('g."'+name+'"' for name in columns)
    db.execute('CREATE VIEW native_index AS SELECT * FROM read_parquet('+q(pilot['record_index'])+')')
    db.execute('CREATE VIEW molecules AS SELECT * FROM read_parquet('+q(pilot['molecule_index'])+')')
    db.execute('''CREATE TABLE tasks AS SELECT '''+projection+''',m.effective_role,m.source_role,
      o.rank AS random_order_rank,to_json(r) AS native_source_json,
      CAST(x.file_group AS INTEGER) AS file_group,
      CASE WHEN x.max_heavy_atoms<=20 THEN '0_20' WHEN x.max_heavy_atoms<=40 THEN '21_40'
           WHEN x.max_heavy_atoms<=75 THEN '41_75' ELSE 'above_75' END AS size_stratum,
      'pprime:'||g.molecule_id||':'||CAST(g.sprime_conf_idx AS VARCHAR) AS record_id,
      CAST(floor((dense_rank() OVER(ORDER BY g.molecule_id)-1)/512) AS BIGINT) AS batch_id
      FROM checked o JOIN g USING(geometry_id,molecule_id) JOIN counts m USING(molecule_id)
      JOIN molecules x USING(molecule_id) JOIN native_index r ON r.record_id=g.'''+source_anchor+'''
      WHERE m.parent_count>=2 AND o.rank<2 AND r.molecule_id=g.molecule_id''')
    ready, ncommon = db.execute('SELECT count(*) FROM counts WHERE parent_count>=2').fetchone()[0], db.execute('SELECT count(*) FROM counts').fetchone()[0]
    nrecords, nunique = db.execute('SELECT count(*),count(DISTINCT geometry_id) FROM tasks').fetchone()
    if nrecords != 2*ready or nrecords != nunique:
        raise ValueError('EXACT_FIRST_TWO_PHYSICAL_POINTERS_NOT_COMPLETE_AND_UNIQUE')
    out = IO.new_output(a.output, c)
    pq.write_table(pending, out/'n1_pending.parquet', compression='zstd')
    db.execute('COPY (SELECT * FROM tasks ORDER BY batch_id,molecule_id,random_order_rank) TO '+q(out/'tasks.parquet')+" (FORMAT PARQUET,COMPRESSION ZSTD)")
    IO.output_guard(out,c,reserve=16<<20)
    from retention_policy_v1 import stable_source_row,audit_key
    from prepare_pilot import source_paths
    sources=source_paths(json.loads(IO.require_pin(pilot['source_plan']).read_text()))
    shard_by_path={s['path']:int(s['shard_id']) for s in sources}
    explicit={};identity_manifest_ref=None
    identity_pins=[]
    if a.audit_identity_manifest:
        frozen=json.loads(a.audit_identity_manifest.read_text());identity_manifest_ref=IO.reference(a.audit_identity_manifest)
        if frozen.get('status')=='COMMON_POPULATION_V1_FROZEN' and identity_manifest_ref==cp and frozen.get('finalizer_variant')=='formal_v2_preserved_physical_ids':
            identity_pins=refs(frozen,('uff_identity_tables',))
        elif frozen.get('status')=='PPRIME_PHYSICAL_AUDIT_IDENTITY_MAP_FROZEN_V1' and frozen.get('common_manifest')==cp and frozen.get('geometry_manifest')==gp:
            identity_pins=refs(frozen,('identity_tables',))
        else:raise ValueError('EXPLICIT_FROZEN_FILL_AUDIT_IDENTITY_MAP_REQUIRED')
    elif common.get('finalizer_variant')=='formal_v2_preserved_physical_ids':
        identity_manifest_ref=cp;identity_pins=refs(common,('uff_identity_tables',))
    if identity_pins:
        for pin in identity_pins:
            for row in pq.read_table(pin['path']).to_pylist():
                gid=row['geometry_id']
                if gid in explicit:raise ValueError('DUPLICATE_FROZEN_PHYSICAL_AUDIT_IDENTITY')
                if 'physical_identity_json' not in row:
                    ns=row.get('identity_namespace')
                    if ns=='accepted_original_sprime':
                        identity={'namespace':ns,'source_conformer_id':row['source_conformer_id']}
                    elif ns=='data_v1_fill':
                        identity={'namespace':ns,'seed':row['seed'],'candidate_id':row['candidate_id'],'task_key':row['task_key']}
                        ledger={'path':row['once_ledger_path'],'bytes':row['once_ledger_bytes'],'sha256':row['once_ledger_sha256']}
                        observed=json.loads(IO.require_pin(ledger).read_text())
                        if observed.get('schema') not in {'SPRIME_ONCE_ATTEMPT_STARTED_V1','SPRIME_PILOT_ATTEMPT_IMPORTED_V1'} or observed.get('task_key')!=row['task_key'] or observed.get('molecule_id')!=row['molecule_id']:
                            raise ValueError('FROZEN_FILL_IDENTITY_HAS_NO_MATCHING_ACTUAL_ONCE_LEDGER')
                    else:raise ValueError('UNKNOWN_OR_N1_NAMESPACE_NOT_APPROVED_FOR_BASELINE_RAW_AUDIT')
                    row=dict(row,physical_identity_json=IO.canonical(identity).decode())
                explicit[gid]=row
    def audit_row(row):
        source=json.loads(row['native_source_json']);source.update(shard_id=shard_by_path[source['source_path']],
            file_group=row['file_group'],size_stratum=row['size_stratum'])
        if row['source_format']=='parquet' and row['original_sprime_conf_idx'] is not None:
            identity={'namespace':'accepted_original_sprime','source_conformer_id':int(row['original_sprime_conf_idx'])}
        else:
            bound=explicit.get(row['geometry_id'])
            if bound is None or bound['molecule_id']!=row['molecule_id']:
                raise ValueError('FILL_AUDIT_IDENTITY_PENDING_EXPLICIT_FROZEN_MAP_NO_GUESS')
            identity=json.loads(bound['physical_identity_json'])
            if identity.get('namespace')!='data_v1_fill' or identity.get('seed')!=row['seed'] or identity.get('candidate_id')!=row['candidate_id']:
                raise ValueError('FROZEN_FILL_AUDIT_IDENTITY_DISAGREES_WITH_PHYSICAL_MAP')
        selected=stable_source_row(row['record_id'],row['molecule_id'],source,identity,sources)
        selected['physical_identity_json']=IO.canonical(selected.pop('physical_identity')).decode()
        selected['canonical_geometry_id']=row['geometry_id']
        return selected
    audit=[];denominators=defaultdict(int);hits=defaultdict(int);writer=None
    audit_query=db.execute('SELECT * FROM tasks ORDER BY batch_id,molecule_id,random_order_rank').fetch_record_batch(rows_per_batch=8192)
    with ThreadPoolExecutor(max_workers=16) as pool:
        try:
            for chunk in audit_query:
                rows=list(pool.map(audit_row,chunk.to_pylist()))
                table=pa.Table.from_pylist(rows)
                if writer is None:writer=pq.ParquetWriter(out/'source_audit.parquet',table.schema,compression='zstd')
                writer.write_table(table)
                IO.output_guard(out,c,reserve=table.nbytes+(16<<20))
                for row in rows:
                    stratum=(row['source_shard_id'],row['size_stratum']);denominators[stratum]+=1
                    if row['selected']:
                        hits[stratum]+=1
                        audit.append({'record_id':row['record_id'],'file_group':row['legacy_engine_file_group'],'size_stratum':row['size_stratum']})
        finally:
            if writer is not None:writer.close()
    audit_table = pa.Table.from_pylist(audit) if audit else pa.table({'record_id':pa.array([],type=pa.string()),'file_group':pa.array([],type=pa.int32()),'size_stratum':pa.array([],type=pa.string())})
    pq.write_table(audit_table,out/'audit_selected.parquet',compression='zstd')
    IO.write_json(out/'audit_membership.json',{'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1','status':'AUDIT_MEMBERSHIP_CLOSED',
        'selected_records':dict(IO.reference(out/'audit_selected.parquet'),rows=len(audit)), 'basis_points':100,'seed':20261010,
        'audit_policy':c['raw_policy'],'source_audit':IO.reference(out/'source_audit.parquet'),
        'scope':'stable physical-identity threshold100/10000, source_shard_id x fixed heavy bins; legacy group retained only for engine guard',
        'exact_old_WP5_sample_identity_claimed':False})
    batches = [{'batch_id':b,'records':n,'molecules':m} for b,n,m in db.execute('SELECT batch_id,count(*),count(DISTINCT molecule_id) FROM tasks GROUP BY 1 ORDER BY 1').fetchall()]
    estimate = (nrecords*gates['allocated_core_seconds_per_requested_conformer']+gates['allocated_core_seconds'])/3600
    IO.output_guard(out,c,reserve=4<<20)
    IO.write_json(out/'plan.json',{'schema':'PPRIME_FORMAL_BASELINE_PLAN_V1',
        'status':'BASELINE_READY_COMMON_SUBSET_N1_PENDING_NOT_FULL' if len(pending) else 'ALL_COMMON_BASELINE_PLANNED_NOT_QM_AUTHORIZED',
        'common_manifest':cp,'order_manifest':op,'geometry_manifest':gp,'pilot_review':IO.reference(a.pilot_review),
        'config':IO.reference(a.config),'common_molecules':ncommon,'ready_molecules':ready,
        'pending_two_real_geometries':len(pending),'requested_records':nrecords,'batches':batches,
        'tasks':IO.reference(out/'tasks.parquet'),'n1_pending':IO.reference(out/'n1_pending.parquet'),
        'audit_membership':IO.reference(out/'audit_membership.json'), 'audit_selected':IO.reference(out/'audit_selected.parquet'),
        'raw_policy':c['raw_policy'],'source_audit':IO.reference(out/'source_audit.parquet'),
        'explicit_fill_audit_identity_manifest':identity_manifest_ref,
        'stable_audit_rates':[{'source_shard_id':k[0],'size_stratum':k[1],'universe':n,'hits':hits[k],'actual_fraction':hits[k]/n} for k,n in sorted(denominators.items())],
        'estimated_allocation_core_hours':estimate,'actual_pilot_core_seconds_per_conformer':gates['allocated_core_seconds_per_requested_conformer'],
        'estimate_scope':'conservative all planned baseline records plus already-incurred full pilot allocation; actual ledger deduplicates pilot reuse',
        'whole_common_complete':False,'N_or_common_membership_changed':False,'QM_started':False})
    db.close()


def physical_row(row, c):
    """Read exactly one pinned physical row, preserving original identity trace."""
    pin = {'path':row['source_path'],'bytes':int(row['source_bytes']),'sha256':row['source_sha256']}
    path=Path(pin['path']);before=path.stat()
    identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
    previous=VERIFIED_SOURCES.get(str(path))
    if previous is None:
        IO.require_pin(pin)  # hash each selected source file once per materialization process
        VERIFIED_SOURCES[str(path)]=(pin,identity)
    elif previous!=(pin,identity):
        raise ValueError('PHYSICAL_SOURCE_CHANGED_DURING_BATCH_MATERIALIZATION')
    index = int(row['source_row_index'])
    if index < 0:
        raise ValueError('NEGATIVE_PHYSICAL_ROW_INDEX')
    if row['source_format'] == 'parquet':
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        offset = 0
        for group in range(pf.num_row_groups):
            metadata = pf.metadata.row_group(group)
            if index < offset+metadata.num_rows:
                if metadata.total_byte_size > c['maximum_source_decode_bytes']:
                    raise ValueError('PHYSICAL_ROW_GROUP_EXCEEDS_PREDECLARED_DECODE_BOUND')
                result = row_group(str(path),group).slice(index-offset,1).to_pylist()[0]
                break
            offset += metadata.num_rows
        else:
            raise ValueError('PHYSICAL_SOURCE_ROW_MISSING')
    elif row['source_format'] == 'reproduction_json_gz':
        if path.stat().st_size > c['maximum_source_decode_bytes']:
            raise ValueError('COMPRESSED_PACKET_EXCEEDS_DECODE_BOUND')
        with gzip.open(path,'rb') as stream:
            raw = stream.read(c['maximum_source_decode_bytes']+1)
        if len(raw)>c['maximum_source_decode_bytes'] or row.get('source_member')!='conformers':
            raise ValueError('BOUNDED_CONFORMER_REPRODUCTION_PACKET_REQUIRED')
        packet=json.loads(raw);result=packet['conformers'][index]
        if packet['summary']['molecule_id']!=row['molecule_id']:
            raise ValueError('GENERATED_PACKET_MOLECULE_MISMATCH')
    else:
        raise ValueError('UNSUPPORTED_PHYSICAL_SOURCE_FORMAT_NO_PICKLE_FALLBACK')
    if result.get('molecule_id',row['molecule_id']) != row['molecule_id'] or result['status']!='SUCCESS' or result['converged'] is not True:
        raise ValueError('ACTUAL_SOURCE_ROW_NOT_USABLE_FOR_THIS_MOLECULE')
    if result['atom_order_sha256']!=row['atom_order_sha256']:
        raise ValueError('PHYSICAL_ATOM_ORDER_MISMATCH')
    if row.get('original_sprime_conf_idx') is not None and result['sprime_conf_idx']!=row['original_sprime_conf_idx']:
        raise ValueError('ORIGINAL_SOURCE_CONFORMER_ID_MISMATCH')
    after=path.stat()
    if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('PHYSICAL_SOURCE_CHANGED_WHILE_READING')
    return result


def materialize(a, c, pilot):
    saved=json.loads(a.plan.read_text())
    if saved['config']!=IO.reference(a.config):
        raise ValueError('EXACT_REGISTERED_FORMAL_CONFIG_REQUIRED')
    for key in ('tasks','audit_membership','audit_selected','n1_pending','source_audit'):
        IO.require_pin(saved[key])
    frozen_authorities(saved['common_manifest'],saved['order_manifest'],saved['geometry_manifest'])
    pilot_review(saved['pilot_review']['path'],c['pilot_config']['path'])
    db=connect()
    rows=db.execute('SELECT * FROM read_parquet('+q(saved['tasks']['path'])+') WHERE batch_id=? ORDER BY molecule_id,random_order_rank',[a.batch_id]).fetch_arrow_table().to_pylist()
    if not rows or len(rows)>1024 or len(rows)%2:
        raise ValueError('ONE_NONEMPTY_BOUNDED512_MOLECULE_BATCH_REQUIRED')
    from prepare_pilot import source_paths
    paths=source_paths(json.loads(IO.require_pin(pilot['source_plan']).read_text()))
    shards={s['path']:int(s['shard_id']) for s in paths}
    contract=json.loads(IO.require_pin(pilot['legacy_contract']).read_text())
    protocol_pin=contract['protocol'];IO.require_pin(protocol_pin)
    pairs=[]
    wanted=[r['record_id'] for r in rows]
    db.register('wanted',__import__('pyarrow').table({'record_id':wanted}))
    source_audits={r['record_id']:r for r in db.execute('SELECT s.* FROM read_parquet('+q(saved['source_audit']['path'])+') s JOIN wanted USING(record_id)').fetch_arrow_table().to_pylist()}
    if len(source_audits)!=len(rows):raise ValueError('EVERY_PREPARED_RECORD_NEEDS_STABLE_SOURCE_AUDIT')
    for row in rows:
        raw=physical_row(row,c)
        if row.get('geometry_sha256') and raw.get('geometry_sha256')!=row['geometry_sha256']:
            raise ValueError('FROZEN_GENERATED_GEOMETRY_SHA_DISAGREES_WITH_ACTUAL_SOURCE_ROW')
        source=json.loads(row['native_source_json'])
        anchor=row.get('native_anchor_record_id',row.get('source_record_id'))
        if raw['source_record_id']!=anchor or source['record_id']!=anchor or source['molecule_id']!=row['molecule_id']:
            raise ValueError('CANONICAL_UFF_AND_NATIVE_ANCHOR_POINTER_MISMATCH')
        source.update(shard_id=shards[source['source_path']],effective_role=row['effective_role'],source_role=row['source_role'],
                      file_group=row['file_group'],size_stratum=row['size_stratum'])
        conformer=dict(raw,sprime_conf_idx=int(row['sprime_conf_idx']))
        xyz_sha=coordinate_sha(raw['coordinates'])
        key=task_key(row['molecule_id'],row['atom_order_sha256'],xyz_sha,protocol_pin['sha256'],row['record_id'])
        pairs.append({'record_id':row['record_id'],'molecule_id':row['molecule_id'],'random_order_rank':int(row['random_order_rank']),
          'geometry_source':'uff_sprime','canonical_geometry_id':row['geometry_id'],'parent_view_id':'baseline_common_v1',
          'source':source,'conformer':conformer,'uff_coordinate_sha256':xyz_sha,
          'conformer_row_sha256':hashlib.sha256(IO.canonical(conformer)).hexdigest(), 'once_key':key,
          'physical_source':{k:row.get(k) for k in ('source_path','source_sha256','source_bytes','source_format','source_row_index','source_member','original_sprime_conf_idx')},
          'original_source_conformer_id':raw.get('sprime_conf_idx'), 'protocol_sha256':protocol_pin['sha256']})
        pairs[-1].update(stable_raw_audit_key_sha256=source_audits[row['record_id']]['audit_key_sha256'],
                         stable_raw_audit_selected=source_audits[row['record_id']]['selected'],
                         physical_audit_identity=json.loads(source_audits[row['record_id']]['physical_identity_json']))
        if row.get('geometry_sha256'):pairs[-1]['uff_geometry_sha256']=row['geometry_sha256']
    if len({p['once_key'] for p in pairs})!=len(pairs):
        raise ValueError('TWO_VIEWS_REFER_TO_IDENTICAL_SCIENTIFIC_INPUT_ONCE_KEY')
    out=IO.new_output(a.output,c)
    with (out/'pairs.jsonl').open('xb') as stream:
        for pair in pairs:stream.write(IO.canonical(pair)+b'\n')
        stream.flush();os.fsync(stream.fileno())
    # Use global record audit; new engine IDs remain identical to baseline record IDs.
    membership=json.loads(Path(saved['audit_membership']['path']).read_text())
    IO.write_json(out/'audit_membership.json',membership)
    IO.write_json(out/'prepared.json',{'status':'PPRIME_FORMAL_BATCH_INPUTS_READY_NOT_QM_EXECUTED',
       'config':IO.reference(a.config),'plan':IO.reference(a.plan),'batch_id':a.batch_id,'records':len(pairs),
       'pairs':IO.reference(out/'pairs.jsonl'),'audit_membership':IO.reference(out/'audit_membership.json'),
       'protocol':protocol_pin,'original_LMDB_opened':False,'N1_expanded_rows_accepted':False,'QM_started':False})
    db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['plan','materialize'])
    for name in ('config','root-preflight','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('pilot-review','common-manifest','order-manifest','geometry-manifest','audit-identity-manifest','plan'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--batch-id',type=int)
    a=p.parse_args();c,pilot=load(a.config);runtime(c,a.root_preflight,a.config)
    if a.stage=='plan':
        if not all((a.pilot_review,a.common_manifest,a.order_manifest,a.geometry_manifest)):
            p.error('plan requires real pilot review and all three frozen authority manifests')
        plan(a,c,pilot)
    else:
        if a.plan is None or a.batch_id is None:p.error('materialize requires --plan and --batch-id')
        materialize(a,c,pilot)


if __name__=='__main__':main()
