"""Explicit origin mapping and same-FD full consumption; no implicit path rewrite."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
from workflows.expansion.coconut_alpha_cached735_v1 import support as S

ALPHA='218.192.171.238:22';MAIN='202.38.247.57:22'


def triple(ref):
    S.need(isinstance(ref,dict) and {'path','bytes','sha256'}<=set(ref),'PHYSICAL_REFERENCE_TRIPLE')
    value={k:ref[k] for k in ('path','bytes','sha256')}
    S.need(isinstance(value['path'],str) and type(value['bytes']) is int and value['bytes']>=0
           and isinstance(value['sha256'],str) and len(value['sha256'])==64
           and all(c in '0123456789abcdef' for c in value['sha256']),'EXACT_BYTES_AND_SHA256_REFERENCE')
    return value


def key(ref):return json.dumps(triple(ref),sort_keys=True,separators=(',',':'))


def strict(raw):
    def unique(pairs):
        result={}
        for k,v in pairs:
            S.need(k not in result,'DUPLICATE_JSON_OBJECT_KEY');result[k]=v
        return result
    def bad(value):raise ValueError('NONFINITE_JSON_TOKEN '+value)
    return json.loads(raw,object_pairs_hook=unique,parse_constant=bad)


class Reader:
    def __init__(self,plan,check=lambda:None):
        S.need(os.getuid()==1264 and plan['endpoint']==ALPHA and plan['uid']==1264,'REAL_ALPHA_READER_NOT_IMPORTED_MAIN_PROOF')
        self.check=check;self.declared={key(r) for r in plan['data_references']};self.mapping={};self.verified={};self.consumption=[]
        ref=plan['parent_transport_manifest'];manifest=strict(S.read(ref))
        S.need(manifest['schema']=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
               and manifest['status']=='VERIFIED_REPLICAS_CLOSED'
               and manifest['destination']==dict(endpoint=ALPHA,uid=1264),'ACTUAL_CLOSED_DESTINATION_TRANSPORT')
        self.install(manifest['replicas'])

    def install(self,replicas):
        for item in replicas:
            origin=triple(item['source_reference']);replica=triple(item['replica_reference'])
            expected=(MAIN,1278) if origin['path'].startswith('/share/home/zixiao/') else (ALPHA,1264)
            S.need((item['origin_endpoint'],item['origin_uid'])==expected
                   and (origin['path'].startswith('/share/home/zixiao/') or origin['path'].startswith('/gfshome/alpha/'))
                   and origin['bytes']==replica['bytes'] and origin['sha256']==replica['sha256']
                   and key(origin) not in self.mapping,'EXACT_UNAMBIGUOUS_ORIGIN_IDENTITY_AND_REPLICA_BODY')
            self.mapping[key(origin)]=replica

    def resolve(self,ref):
        logical=triple(ref);S.need(key(ref) in self.declared,'INPUT_NOT_DECLARED_IN_ACTUAL_ROOT_PLAN '+logical['path'])
        replica=self.mapping.get(key(ref))
        if replica is None:
            S.need(logical['path'].startswith('/gfshome/alpha/'),'MISSING_EXPLICIT_MAIN_TO_ALPHA_REPLICA '+logical['path'])
            replica=logical
        p=Path(replica['path'])
        S.need(p.is_absolute() and '..' not in p.parts and p.is_relative_to('/gfshome/alpha')
               and not any(q.is_symlink() for q in (p,*p.parents)),'REAL_ALPHA_PATH_WITHOUT_ALIAS_OR_SYMLINK')
        return p,replica

    @contextmanager
    def held(self,ref):
        p,replica=self.resolve(ref);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            S.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1
                   and before.st_size==replica['bytes'] and S.frame(before)==S.frame(p.stat()),'OWNED_SINGLE_LINK_SAME_FD_REPLICA')
            with os.fdopen(fd,'rb',closefd=False) as stream:yield stream,p,replica,before
            S.need(S.frame(before)==S.frame(os.fstat(fd))==S.frame(p.stat()),'REPLICA_CHANGED_DURING_FULL_READ')
        finally:os.close(fd)

    def done(self,ref,p,replica,before,digest,size,rows=None):
        S.need(size==replica['bytes'] and digest.hexdigest()==replica['sha256'],'WHOLE_REPLICA_EOF_BYTES_SHA_MISMATCH '+str(p))
        self.verified[key(ref)]=S.frame(before)
        self.consumption.append(dict(source_reference=triple(ref),replica_reference=replica,
            actual_uid=1264,current_frame=list(S.frame(before)),whole_SHA256_verified=True,rows=rows))

    def verify(self,ref):
        p,replica=self.resolve(ref)
        if self.verified.get(key(ref))==S.frame(p.stat()):return p
        with self.held(ref) as (stream,p,replica,before):
            digest=hashlib.sha256();size=0
            for block in iter(lambda:stream.read(8<<20),b''):
                digest.update(block);size+=len(block);self.check()
            self.done(ref,p,replica,before,digest,size)
        return p

    def read(self,ref):
        S.need(ref['bytes']<=8<<20,'BOUNDED_METADATA_JSON_OR_TEXT_REFERENCE')
        with self.held(ref) as (stream,p,replica,before):
            raw=stream.read();self.done(ref,p,replica,before,hashlib.sha256(raw),len(raw))
        self.check();return raw

    def json(self,ref):return strict(self.read(ref))

    def rows(self,ref):
        with self.held(ref) as (stream,p,replica,before):
            digest=hashlib.sha256();size=count=0
            for line in stream:
                S.need(line.endswith(b'\n'),'UNCLOSED_SOURCE_JSONL_RECORD')
                digest.update(line);size+=len(line);count+=1
                yield strict(line)
                if count%4096==0:self.check()
            if 'rows' in ref:S.need(count==ref['rows'],'PHYSICAL_JSONL_CENSUS_DIFFERS_FROM_DECLARED_ROWS')
            self.done(ref,p,replica,before,digest,size,count)
        self.check()


class ReplicaVerifier(Reader):
    """Unverified Root-selected bindings for a byte-verification producer only.

    No closed manifest is fabricated to bootstrap verification. Index consumers
    continue to use Reader, whose constructor requires the real closed manifest.
    """
    def __init__(self,plan,bindings,check=lambda:None):
        S.need(os.getuid()==1264 and plan['endpoint']==ALPHA and plan['uid']==1264
               and plan['schema']=='ALPHA_ALL10_SOURCE_REPLICA_PLAN_V1'
               and plan['scope_key']=='alpha_all10_source_replica_v1','REAL_ALPHA_UNVERIFIED_REPLICA_PRODUCER_SCOPE')
        self.check=check;self.declared={key(r['source_reference']) for r in bindings}
        self.mapping={};self.verified={};self.consumption=[];self.install(bindings)
