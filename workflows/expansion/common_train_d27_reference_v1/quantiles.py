"""Original exact F64 median/MAD, reading only closed TRAIN valid leaf streams."""
import hashlib
from pathlib import Path
import uuid
from ..common import load,reference,dump_new
from ..portable_sources_v1.transport import verify
from .inventory import need
from .coverage import WORK,check,sidecar_frames


def field(work):
    import numpy as np
    fid,refs,scope=work;base=WORK['root']/('field_%02d'%fid);base.mkdir(exist_ok=True);closed=base/'manifest.json'
    if closed.exists():
        old=load(closed);need(old['scope_fingerprint']==scope,'Closed field scope mismatch');return reference(closed)
    sources=[]
    for ref in refs:
        path=verify(ref);need(ref['bytes']==ref['leaves']*8,'Only complete closed F64 observations may fit')
        sources.append(path)
    before_sidecars=sidecar_frames();first_digest=None
    cal=WORK['calibration'];fieldmap=[WORK['byid'][fid]];med=None;median_n=0;result={};passes=[]
    for purpose in('median','MAD'):
        if purpose=='MAD'and med is None:
            result['MAD']=None;result['MAD_n']=0;break
        query=cal.initial_queries(fieldmap,purpose,centers={fid:med}if purpose=='MAD'else None)
        finished=[]
        while query['fields']:
            check();counter=cal.RadixCounts(query);count=0;digest=hashlib.sha256()
            for path in sources:
                with path.open('rb')as stream:
                    while True:
                        raw=stream.read(8<<20)
                        if not raw:break
                        check();need(len(raw)%8==0,'F64 stream truncated');digest.update(raw)
                        values=np.frombuffer(raw,dtype='<f8');counter.add(fid,values);count+=len(values)
            need(count==sum(ref['leaves']for ref in refs),'Whole field TRAIN leaf mass changed')
            if first_digest is None:first_digest=digest.hexdigest()
            need(digest.hexdigest()==first_digest,'The exact same immutable TRAIN F64 leaves must feed every radix/MAD pass')
            rows=counter.rows();new,done=cal.advance(query,rows);finished.extend(done)
            passes.append({'purpose':purpose,'round':query['round'],'input_leaves':count,'input_F64_sha256':digest.hexdigest(),
                'histogram_rows':len(rows),'complete':not new['fields']});query=new
        need(len(finished)==1 and finished[0]['field_id']==fid,'Exact original radix field must close once')
        value=finished[0]['value'];n=finished[0]['n']
        if purpose=='median':med=value;median_n=n;result.update(median=value,TRAIN_n=n)
        else:need(n==median_n,'MAD must use identical TRAIN valid leaves');result.update(MAD=value,MAD_n=n)
    for ref in refs:verify(ref)
    need(sidecar_frames()==before_sidecars,'Immutable eligibility sidecars changed while fitting')
    result.update(schema='PUBCHEM_FULL_COMMON_TRAIN_D27_FIELD_V1',status='COMPLETE_EXACT_MEDIAN_MAD',field_id=fid,
        scope_fingerprint=scope,passes=passes,worker_pid=__import__('os').getpid(),original_RadixCounts_and_advance=True,
        normalization_mean_std_or_Pprime_claimed=False)
    dump_new(closed,result);return reference(closed)
