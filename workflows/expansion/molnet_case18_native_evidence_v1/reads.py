"""Same-FD evidence reads with explicit original-to-Alpha bindings."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .parse import exact,need


def triple(ref):return {k:ref[k] for k in ('path','bytes','sha256')}


def key(ref):return json.dumps(triple(ref),sort_keys=True)


class Reads:
    def __init__(self,plan,check):
        self.bindings={};self.check=check;self.records=[]
        for b in plan['input_bindings']:
            src=triple(b['source_reference']);dst=triple(b['replica_reference'])
            need(src['bytes']==dst['bytes'] and src['sha256']==dst['sha256']
                 and key(src) not in self.bindings,'EXACT_UNIQUE_EXPLICIT_SOURCE_REPLICA_BINDING')
            endpoint,uid=b['origin_endpoint'],b['origin_uid']
            if src['path'].startswith('/share/home/zixiao/'):
                need((endpoint,uid)==('202.38.247.57:22',1278),'ORIGINAL_MAIN_UID_RETAINED')
            elif src['path'].startswith('/gfshome/alpha/'):
                need((endpoint,uid)==('218.192.171.238:22',1264),'ORIGINAL_ALPHA_UID_RETAINED')
            else:
                need(endpoint=='WINDOWS_LOCAL_CACHE' and uid is None
                    and src['path'].startswith(('C:\\Users\\mint\\AppData\\Local\\Temp\\','C:/Users/mint/AppData/Local/Temp/')),
                    'EXPLICIT_PUBLIC_LOCAL_CACHE_NOT_LINUX_UID')
            p=Path(dst['path'])
            need(p.is_absolute() and p.is_relative_to('/gfshome/alpha') and '..' not in p.parts
                and not any(x.is_symlink() for x in (p,*p.parents)),'REAL_ALPHA_PATH_WITHOUT_ALIAS')
            self.bindings[key(src)]=b

    @contextmanager
    def held(self,ref,*,lock_database=False):
        need(key(ref) in self.bindings,'INPUT_MUST_HAVE_EXPLICIT_PLAN_BINDING '+ref['path'])
        b=self.bindings[key(ref)];p=Path(b['replica_reference']['path'])
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);db=None;before=os.fstat(fd);slices=[]
        try:
            need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1
                and before.st_size==ref['bytes'] and S.frame(before)==S.frame(p.stat()),'OWNED_IMMUTABLE_SAME_FD_INPUT')
            if lock_database:
                import sqlite3
                db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON');db.execute('BEGIN');db.execute('SELECT name FROM sqlite_schema LIMIT 1').fetchall()
            with os.fdopen(fd,'rb',closefd=False) as stream:
                h=hashlib.sha256();size=0
                for block in iter(lambda:stream.read(8<<20),b''):
                    h.update(block);size+=len(block);self.check()
                need(size==ref['bytes'] and h.hexdigest()==ref['sha256'],'ACTUAL_WHOLE_FD_BYTES_SHA '+str(p))
                def segment(offset,size,expected=None):
                    need(type(offset) is int and type(size) is int and 0<=offset<=ref['bytes']
                        and 0<=size<=2<<20 and offset+size<=ref['bytes'],'BOUNDED_EXACT_SOURCE_SEGMENT')
                    stream.seek(offset);raw=stream.read(size)
                    need(len(raw)==size,'SOURCE_SEGMENT_COMPLETE')
                    observed=dict(offset=offset,bytes=size,sha256=hashlib.sha256(raw).hexdigest())
                    if expected:exact(raw,dict(bytes=size,sha256=expected))
                    slices.append(observed);self.check();return raw
                yield segment,p,db
            need(S.frame(before)==S.frame(os.fstat(fd))==S.frame(p.stat()),'SOURCE_FRAME_CHANGED_DURING_FD_READ')
            self.records.append(dict(source_reference=triple(ref),replica_reference=triple(b['replica_reference']),
                origin_endpoint=b['origin_endpoint'],origin_uid=b['origin_uid'],actual_endpoint='218.192.171.238:22',
                actual_uid=1264,current_frame=list(S.frame(before)),whole_SHA256_verified=True,slices=slices,
                database_read_lock=lock_database,source_written=False))
        finally:
            if db is not None:db.rollback();db.close()
            os.close(fd)

    def read(self,ref):
        need(ref['bytes']<=2<<20,'BOUNDED_METADATA_NOT_FULL_BLOB_DECODE')
        with self.held(ref) as (take,p,db):return take(0,ref['bytes'],ref['sha256'])

    def json(self,ref):return json.loads(self.read(ref))
