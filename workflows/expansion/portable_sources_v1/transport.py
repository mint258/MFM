"""Verify actual local replicas while preserving original endpoint references.

Only new expansion adapters opt into this metadata context. Original scientific
modules, old Main SDKs, original manifests and proofs are never monkeypatched.
"""
from collections import OrderedDict
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import stat
from ..common import verify as original_verify,load,require

_CONTEXT=ContextVar('pubchem_explicit_parent_transport',default=None)


def triple(ref):return {key:ref[key] for key in ('path','bytes','sha256')}


def identity(ref):
    return json.dumps(triple(ref),sort_keys=True,separators=(',',':'))


class Transport:
    def __init__(self,reference,expected_endpoint,expected_uid):
        self.reference=triple(reference);self.cache=OrderedDict();self.uid=expected_uid;self.endpoint=expected_endpoint
        require(os.getuid()==expected_uid,'Actual destination UID differs; imported Main proof cannot authorize Alpha execution')
        path=self.local(self.reference);manifest=load(path)
        require(manifest.get('schema')=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
            and manifest.get('status')=='VERIFIED_REPLICAS_CLOSED'
            and manifest['destination']=={'endpoint':expected_endpoint,'uid':expected_uid},'Actual endpoint-specific closed transport manifest required')
        self.entries={}
        for item in manifest['replicas']:
            origin=triple(item['source_reference']);replica=triple(item['replica_reference'])
            require(origin['bytes']==replica['bytes'] and origin['sha256']==replica['sha256']
                and item['origin_endpoint'] and type(item['origin_uid'])is int,'Replica must retain exact original bytes/hash and origin identity')
            key=identity(origin);require(key not in self.entries,'Ambiguous imported source reference')
            self.entries[key]=replica

    def local(self,ref):
        ref=triple(ref);path=Path(ref['path'])
        require(path.is_absolute() and '..' not in path.parts,'Actual absolute replica path required')
        if self.endpoint=='218.192.171.238:22':
            require(path.is_relative_to('/gfshome/alpha'),'Alpha replicas must use real Alpha paths, never fake Main paths')
        before=path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid==self.uid and before.st_size==ref['bytes'],
            'Actual own regular replica type/UID/size differs')
        stamp=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns,before.st_uid)
        key=(str(path),ref['sha256'])
        if self.cache.get(key)==stamp:
            self.cache.move_to_end(key);return path
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            opened=os.fstat(stream.fileno())
            require((opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns,opened.st_ctime_ns,opened.st_uid)==stamp,'Same replica FD required')
            for block in iter(lambda:stream.read(8<<20),b''):digest.update(block)
            closed=os.fstat(stream.fileno())
        after=path.lstat()
        require((closed.st_dev,closed.st_ino,closed.st_size,closed.st_mtime_ns,closed.st_ctime_ns,closed.st_uid)==stamp
            ==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns,after.st_uid)
            and digest.hexdigest()==ref['sha256'],'Replica changed or original source SHA differs')
        self.cache[key]=stamp
        if len(self.cache)>4096:self.cache.popitem(last=False)
        return path

    def verify(self,ref):return self.local(self.entries.get(identity(ref),triple(ref)))


def bind_plan(plan):
    _CONTEXT.set(None)
    profile_ref=plan.get('runtime_profile_reference')
    if not profile_ref:
        require(not plan.get('parent_transport_manifest'),'Transport requires an explicit destination runtime profile')
        return None
    from ..alpha_runtime_v1.profile import admit
    admit(plan,minimum_workers=16)
    profile=load(original_verify(profile_ref))
    require(profile['endpoint']=='218.192.171.238:22' and profile['uid']==1264 and os.getuid()==1264,
        'Actual Alpha endpoint/UID required; no Main identities are substituted')
    if plan.get('parent_transport_manifest'):
        _CONTEXT.set(Transport(plan['parent_transport_manifest'],profile['endpoint'],profile['uid']))
    return profile


def verify(ref):
    context=_CONTEXT.get()
    return original_verify(ref) if context is None else context.verify(ref)


def provenance(plan):
    if not plan.get('runtime_profile_reference'):return None
    profile=load(original_verify(plan['runtime_profile_reference']))
    return {'actual_endpoint':profile['endpoint'],'actual_uid':os.getuid(),
        'runtime_profile_reference':plan['runtime_profile_reference'],
        'parent_transport_manifest':plan.get('parent_transport_manifest'),
        'imported_parent_proofs_are_original_origin_not_current_runtime_proof':True}
