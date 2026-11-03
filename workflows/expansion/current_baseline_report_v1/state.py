"""Private closed-state clone preserving both complete populations, without deletion."""
import json
import os
from pathlib import Path
import sqlite3
import stat
from ..alpha_runtime_v1 import common as Q
from ..corrected_baseline_statistics_v1.state import stamp,digest,file_sha


def populations(db,expected):
    actual={name:(json.loads(ref),n,complete) for name,ref,n,complete in
      db.execute('SELECT name,manifest,expected,complete FROM populations')}
    Q.need(actual==expected,'Both exact closed population bindings must remain unchanged')


def digests(db,check):return {name:digest(db,name,check) for name in ('pubchem_1m','v1_common')}


def clone(source_path,expected_frame,destination,expected,check):
    source_path=Path(source_path);before=stamp(source_path.lstat())
    Q.need(stat.S_ISREG(source_path.lstat().st_mode) and before['st_uid']==1264 and before['st_nlink']==1
      and all(before[k]==v for k,v in expected_frame.items() if k!='st_dev'),
      'Same reviewed closed source inode/owner/size/times; client device is node-local')
    Q.need(not Path(destination).exists() and not any(Path(str(source_path)+s).exists()
      for s in ('-wal','-shm','-journal')),'Fresh clone and closed source without SQLite sidecars required')
    source=sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(destination)
    try:
        source.execute('PRAGMA main.cache_size=-1048576');target.execute('PRAGMA main.cache_size=-1048576')
        Q.need(source.execute('PRAGMA journal_mode').fetchone()[0]=='delete','Closed DELETE-mode source required')
        source.execute('BEGIN');source.execute('SELECT count(*) FROM sqlite_master').fetchone()
        populations(source,expected)
        Q.need(source.execute('SELECT count(*) FROM comparisons').fetchone()[0]==
          source.execute('SELECT count(*) FROM nearest').fetchone()[0]==0,'Population-only source: no historical NN reuse')
        with source_path.open('rb') as stream:
            Q.need(stamp(os.fstat(stream.fileno()))==before,'Actual held source FD required')
            first=file_sha(stream,check);logical=digests(source,check)
            source.backup(target,pages=512,progress=lambda *args:check())
            populations(target,expected)
            Q.need(digests(target,check)==logical,'Both populations and all five logical tables must clone exactly')
            second=file_sha(stream,check)
            Q.need(first==second and stamp(os.fstat(stream.fileno()))==before==stamp(source_path.lstat()),
              'Held source bytes/frame changed across read-locked complete clone')
        return dict(source_path=str(source_path),source_current_frame=before,review_frame=expected_frame,
          cross_node_device_identity_claimed=False,source_FD_SHA_before=first,source_FD_SHA_after=second,
          population_logical_digests=logical,all_ten_population_table_partitions_retained=True,
          source_or_clone_population_rows_deleted=0,population_feature_rows_recomputed=0)
    finally:target.close();source.rollback();source.close()
