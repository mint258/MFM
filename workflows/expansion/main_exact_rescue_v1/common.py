"""Actual endpoint replicas, native completion and bounded metadata, no relabels."""
import json
import os
from pathlib import Path
from ..exact_nn_inverted_cpp_v1.artifacts import need,reference,verify,frame,write_new

N=1196122
MAIN='202.38.247.57:22'
ALPHA='218.192.171.238:22'
PREFIXES=['8','9','a','e','f']


def clean(ref):return {k:ref[k]for k in ('path','bytes','sha256')}
def body(ref):
    need(type(ref['bytes'])is int and 0<=ref['bytes']<=2<<20,'Bounded exact metadata')
    path=verify(ref);before=frame(path);raw=path.read_bytes()
    need(frame(path)==before and len(raw)==ref['bytes'],'Unchanged whole metadata read')
    import hashlib
    need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'Exact freshly read metadata bytes')
    return json.loads(raw)


class Transport:
    def __init__(self,ref,source,destination,uid):
        self.reference=ref;value=body(ref)
        need(value['schema']=='EXACT_RESCUE_TRANSPORT_V1'and value['source_endpoint']==source
            and value['source_uid']==(1264 if source==ALPHA else 1278)
            and value['destination_endpoint']==destination and value['destination_uid']==uid==os.getuid(),
            'Honest source/destination endpoint and actual destination UID')
        self.files={};self.checked={}
        for item in value['files']:
            origin=clean(item['origin']);replica=clean(item['replica']);key=json.dumps(origin,sort_keys=True)
            need(key not in self.files and origin['bytes']==replica['bytes']and origin['sha256']==replica['sha256'],
                 'Unique origin-to-actual-replica byte/SHA mapping')
            self.files[key]=replica
    def resolve(self,origin):
        key=json.dumps(clean(origin),sort_keys=True);need(key in self.files,'Missing exact transported origin')
        replica=self.files[key]
        if key not in self.checked:self.checked[key]=frame(verify(replica))
        need(frame(replica['path'])==self.checked[key],'Actual local replica mutated')
        return replica
    def finish(self):
        for key,stamp in self.checked.items():need(frame(self.files[key]['path'])==stamp,'Transported input changed')


def native_closed(actual,raw_ref,uid,*,parent_required):
    path=verify(raw_ref);before=frame(path);lines=path.read_text().splitlines()
    need(lines and 'JobIDRaw'in lines[0].split('|'),'Native Slurm accounting header')
    names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    job=str(actual['job_id']);parents=[r for r in rows if r['JobIDRaw']==job]
    need(len(parents)==1 and parents[0]['UID']==str(uid)and actual['uid']==uid,'Actual originating native parent UID/job')
    if parent_required:
        relevant=[r for r in rows if r['JobIDRaw']==job or r['JobIDRaw'].startswith(job+'.')]
        need(any(r['JobIDRaw']==job+'.batch'for r in relevant)
            and all(r['State'].split()[0]=='COMPLETED'and r['ExitCode']=='0:0'for r in relevant),
            'Actual parent and recorded batch/steps C0')
    else:
        step=str(actual['step_id']);need(step.isdigit(),'Real numeric originating step ID')
        found=[r for r in rows if r['JobIDRaw']==job+'.'+step]
        need(len(found)==1 and found[0]['State']=='COMPLETED'and found[0]['ExitCode']=='0:0',
             'Actual originating step C0; parent is not relabelled complete')
    need(frame(path)==before,'Native accounting changed')


def exported_parts(manifest,transport):
    need(manifest['schema']=='ALPHA_EXACT_FP_RESCUE_EXPORT_V1'and manifest['status']=='COMPLETE'
        and manifest['endpoint']==ALPHA and manifest['uid']==1264 and manifest['md5_hex_text_prefixes']==PREFIXES,
        'Actual Alpha209 FP-only export, fixed canonical-hex MD5 tail scope')
    need(('parts'in manifest)!=('parts_catalog_reference'in manifest),'One honest inline/catalog part representation')
    if 'parts'in manifest:parts=manifest['parts']
    else:
        ref=transport.resolve(manifest['parts_catalog_reference']);path=verify(ref);before=frame(path);parts=[]
        with path.open('rb')as stream:
            for raw in stream:
                need(len(raw)<=1<<20 and raw.endswith(b'\n'),'Bounded newline-closed export part catalog')
                parts.append(json.loads(raw))
        need(frame(path)==before,'Part catalog changed while reading')
    counts={c:0 for c in '0123456789abcdef'};seen=set()
    for part in parts:
        bucket=part['physical_fp_bucket'];need(bucket in counts and part['path']not in seen
            and type(part['rows'])is int and part['rows']>0,'Unique bounded physical FP part')
        seen.add(part['path']);counts[bucket]+=part['rows']
    need(len(parts)==manifest['part_count']and counts==manifest['per_bucket_counts']
        and sum(counts.values())==manifest['distinct_fingerprints'],'Whole exported distinct FP mass by physical bucket')
    return parts