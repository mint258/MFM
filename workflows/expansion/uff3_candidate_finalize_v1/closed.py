"""Bounded closed native files and per-MID saved evidence, no RDKit/UFF calls."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
from ..alpha_runtime_v1 import common as Q
from ..uff3_candidate_v1 import core as C,store as S
from . import validation as V


def frame(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def content(ref,maximum):
    path=Path(ref['path']);Q.need(path.is_absolute()and path.is_relative_to('/gfshome/alpha'),'Actual Alpha evidence, no fake original Main path')
    Q.need(type(ref['bytes'])is int and 0<=ref['bytes']<=maximum,'Finite reviewed closed artifact read allowance')
    before=path.lstat();Q.need(stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_size==ref['bytes'],'Own closed artifact regular type/size/UID')
    with path.open('rb')as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'Same closed native FD')
        data=f.read(maximum+1);after=os.fstat(f.fileno())
    Q.need(len(data)==ref['bytes']and frame(before)==frame(after)==frame(path.lstat())
        and hashlib.sha256(data).hexdigest()==ref['sha256'],'Whole closed artifact SHA/native frame differs')
    return data


def document(ref,maximum):
    raw=content(ref,maximum)
    return json.loads(gzip.decompress(raw)if Path(ref['path']).suffix=='.gz'else raw)


def events(ref,maximum):
    previous='0'*64;out=[]
    for ordinal,raw in enumerate(content(ref,maximum).splitlines(keepends=True)):
        record=json.loads(raw)
        Q.need(raw.endswith(b'\n')and record['ordinal']==ordinal and record['previous_sha256']==previous
            and C.canonical(record)+b'\n'==raw,'Closed scientific event chain')
        previous=hashlib.sha256(raw[:-1]).hexdigest();out.append(record['event'])
    return out


def verify_stream(ref):
    """Whole large-family SHA with O(8MiB) memory and same native FD/frame."""
    path=Path(ref['path']);before=path.lstat()
    Q.need(stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_size==ref['bytes'],'Own closed family file')
    h=hashlib.sha256()
    with path.open('rb')as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'Same actual family FD')
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
        after=os.fstat(f.fileno())
    Q.need(frame(before)==frame(after)==frame(path.lstat())and h.hexdigest()==ref['sha256'],'Closed family whole SHA/frame')
    return frame(before)


def read_one(item):
    ordinal,source,manifest_ref,worker_pid,reused,maximum=item
    m=document(manifest_ref,maximum);artifacts=[manifest_ref]
    if m['schema']=='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1':
        result=V.interrupted(source,m);packet_ref=manifest_ref;cache_ref=event_ref=None
        # These bytes remain UNKNOWN: pin them without treating an incomplete
        # cache/journal as a completed packet or replaying its scientific calls.
        directory=Path(m['output_directory'])
        for base,dirs,files in os.walk(directory,followlinks=False):
            Q.need(not any((Path(base)/n).is_symlink()for n in dirs),'Interrupted directory symlink rejected')
            for name in files:
                ref=Q.reference(Path(base)/name);verify_stream(ref);artifacts.append(ref)
    else:
        Q.need(m['schema']=='PUBCHEM_UFF3_MOLECULE_OUTPUT_MANIFEST_V1'
            and m['source_identity_sha256']==C.source_identity(source)and m['recipe_sha256']==C.recipe_sha()
            and m['dataset_version']=='v2_candidate'and m['training_eligible']is False and m['new_QM_calls']==0,
            'Exact closed production molecule manifest, no new QM/training')
        cache_ref=m['candidate_cache'];packet_ref=m['selected_packet'];event_ref=m['events']
        cache=document(cache_ref,maximum);p=document(packet_ref,maximum);journal=events(event_ref,maximum)
        Q.need(len(journal)==m['event_count']and m['state']==p['state'],'Closed actual event/state census')
        result=V.packet(source,cache,p,m,journal);artifacts.extend([cache_ref,packet_ref,event_ref])
    once=C.sha(C.canonical([C.recipe_sha(),C.source_identity(source)]))
    return dict(ordinal=ordinal,source=source,molecule_id=C.molecule_id(source),source_identity_sha256=C.source_identity(source),
        once_key=once,manifest_reference=manifest_ref,packet_reference=packet_ref,cache_reference=cache_ref,
        events_reference=event_ref,producer_job_id=m.get('producer_job_id'),
        family_verification_worker_pid=worker_pid,closed_reused=reused,
        original_native_worker_pid_not_recorded_per_molecule=True,artifacts=artifacts,**result)