"""Bounded external replica catalogs for complete closed exact-rescue transports."""
import hashlib,json,os
from pathlib import Path
from ..exact_nn_inverted_cpp_v1.artifacts import need,verify,frame,reference
ALPHA='218.192.171.238:22'
MAIN='202.38.247.57:22'
def clean(value):return {k:value[k]for k in ('path','bytes','sha256')}
def read_small(ref):
    need(type(ref['bytes'])is int and 0<=ref['bytes']<=2<<20,'Bounded transport descriptor only')
    path=verify(ref);stamp=frame(path);raw=path.read_bytes()
    need(frame(path)==stamp and len(raw)==ref['bytes']and hashlib.sha256(raw).hexdigest()==ref['sha256'],
        'Whole unchanged transport descriptor')
    return json.loads(raw),stamp
class Transport:
    def __init__(self,ref,source,destination,uid):
        self.reference=ref;value,self.descriptor_frame=read_small(ref)
        need(value['schema']=='EXACT_RESCUE_TRANSPORT_V1'and value['source_endpoint']==source
            and source in (ALPHA,MAIN)and value['source_uid']==(1264 if source==ALPHA else 1278)
            and value['destination_endpoint']==destination and value['destination_uid']==uid==os.getuid(),
            'Actual source/destination endpoint/UID transport')
        need(('files'in value)!=('files_catalog_reference'in value),'Exactly inline or external replica catalog')
        self.files={};self.checked={};self.catalog_ref=None;self.catalog_frame=None
        if 'files'in value:
            need(isinstance(value['files'],list),'Actual inline file list')
            rows=value['files']
        else:
            self.catalog_ref=value['files_catalog_reference'];ref=self.catalog_ref
            need(type(ref['bytes'])is int and 0<=ref['bytes']<=64<<20
                and type(value['file_count'])is int and 0<value['file_count']<=100000,'Bounded64MiB transport metadata catalog')
            path=verify(ref);self.catalog_frame=frame(path);rows=[]
            with path.open('rb')as stream:
                for raw in stream:
                    need(len(raw)<=1<<20 and raw.endswith(b'\n'),'Whole bounded newline replica catalog')
                    rows.append(json.loads(raw))
                    need(len(rows)<=value['file_count'],'No extra replica catalog rows')
            need(frame(path)==self.catalog_frame and len(rows)==value['file_count'],'Exact catalog EOF/count/frame')
        for item in rows:
            origin=clean(item['origin']);replica=clean(item['replica']);key=json.dumps(origin,sort_keys=True)
            need(key not in self.files and type(origin['bytes'])is int and origin['bytes']>=0
                and origin['bytes']==replica['bytes']and origin['sha256']==replica['sha256'],
                'Unique whole origin-to-replica byte/SHA mapping')
            self.files[key]=replica
    def resolve(self,origin):
        key=json.dumps(clean(origin),sort_keys=True);need(key in self.files,'Missing exact transported origin')
        replica=self.files[key]
        if key not in self.checked:self.checked[key]=frame(verify(replica))
        need(frame(replica['path'])==self.checked[key],'Actual transported replica changed')
        return replica
    def finish(self):
        need(frame(self.reference['path'])==self.descriptor_frame,'Transport descriptor changed after admission')
        if self.catalog_ref:need(frame(self.catalog_ref['path'])==self.catalog_frame,'External replica catalog changed')
        for key,stamp in self.checked.items():need(frame(self.files[key]['path'])==stamp,'Transported input changed')
