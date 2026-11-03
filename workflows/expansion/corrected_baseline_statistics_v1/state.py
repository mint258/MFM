"""Closed SQLite cloning and exact Common logical row digest; no moment subtraction."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import struct
from ..alpha_runtime_v1 import common as Q

TABLES={'populations':('name',('name',)), 'required_members':('population',('population','identity')),
    'seen':('population',('population','identity')),'counts':('population',('population','kind','key')),
    'moments':('population',('population','field'))}


def stamp(s):return {k:getattr(s,k)for k in('st_dev','st_ino','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}


def digest(db,population,check):
    sha=hashlib.sha256();counts={}
    for table,(column,order)in sorted(TABLES.items()):
        count=0
        for row in db.execute('SELECT * FROM '+table+' WHERE '+column+'=? ORDER BY '+','.join(order),(population,)):
            raw=json.dumps([table,*row],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            sha.update(struct.pack('<Q',len(raw)));sha.update(raw);count+=1
            if count%8192==0:check()
        counts[table]=count
    return dict(sha256=sha.hexdigest(),logical_rows_by_table=counts)


def file_sha(stream,check):
    stream.seek(0);sha=hashlib.sha256()
    while True:
        raw=stream.read(8<<20)
        if not raw:break
        sha.update(raw);check()
    return sha.hexdigest()


def clone(source_path,expected_frame,destination,check):
    source_path=Path(source_path);before=stamp(source_path.lstat())
    Q.need(stat.S_ISREG(source_path.lstat().st_mode)and before['st_uid']==1264 and before['st_nlink']==1
        and all(before[k]==value for k,value in expected_frame.items()if k!='st_dev'),
        'Same closed source inode/owner/size/times; device is mount-local and is not compared across nodes')
    Q.need(not any(Path(str(source_path)+suffix).exists()for suffix in('-wal','-shm','-journal')),'Closed DELETE-mode SQLite with no active sidecars required')
    source=sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(destination)
    try:
        source.execute('PRAGMA main.cache_size=-1048576');target.execute('PRAGMA main.cache_size=-1048576')
        Q.need(source.execute('PRAGMA journal_mode').fetchone()[0]=='delete','Actual original DELETE journal mode required')
        source.execute('BEGIN');source.execute('SELECT count(*) FROM sqlite_master').fetchone() # real shared READ transaction
        Q.need(dict(source.execute('SELECT name,expected FROM populations WHERE complete=1'))==dict(pubchem_1m=1000000,v1_common=1196122),
            'Exact closed source populations, not a partial state')
        Q.need(source.execute('SELECT count(*) FROM comparisons').fetchone()[0]==source.execute('SELECT count(*) FROM nearest').fetchone()[0]==0,
            'This clone is only population statistics; no old comparison may be silently reused')
        with source_path.open('rb')as stream:
            Q.need(stamp(os.fstat(stream.fileno()))==before,'Actual same source FD required')
            first=file_sha(stream,check);common=digest(source,'v1_common',check)
            source.backup(target,pages=512,progress=lambda *args:check())
            with Path(destination).open('rb')as copied:clone_sha=file_sha(copied,check)
            with target:
                for table,(column,order)in TABLES.items():target.execute('DELETE FROM '+table+' WHERE '+column+'=?',('pubchem_1m',))
            Q.need(digest(target,'v1_common',check)==common,'Removing old baseline from private clone must leave every Common row unchanged')
            second=file_sha(stream,check)
            Q.need(first==second and stamp(os.fstat(stream.fileno()))==before==stamp(source_path.lstat()),'Read-locked closed source FD bytes/frame changed')
        return dict(source_path=str(source_path),source_current_frame=before,review_frame=expected_frame,
            cross_node_device_identity_claimed=False,source_FD_SHA_before=first,source_FD_SHA_after=second,
            clone_SHA_before_baseline_removal=clone_sha,Common_logical_digest=common,
            old_baseline_deleted_only_from_private_clone=True,Common_or_old_source_rows_reenriched=0)
    finally:target.close();source.rollback();source.close()
