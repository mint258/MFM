"""Opaque diagnostic supplement copies in the SAME admitted GPU I/O Parent."""
from __future__ import annotations
import hashlib,os
from pathlib import Path
from .common import need,read,write,reference,frame,compute_context,actual_parent

def copy(supplement_reference,output,*,check_host_resources,copy_cap_bytes,local_disk_reserve_bytes):
    compute_context();need(callable(check_host_resources),'EXISTING_GPU_HOST_GUARD');check_host_resources()
    s=read(supplement_reference)
    need(s['schema']=='ACTUAL_D3_DIAGNOSTIC_SUPPLEMENT_V1'and s['role']=='TRAIN_UNSEEN_CONFORMATION','ACTUAL_DIAGNOSTIC_SUPPLEMENT')
    actual_parent(s['actual_parent_accounting_reference'],s['actual_parent_job_id'])
    root=Path(output);need(str(root).startswith('/tmp/')and not root.exists()
      and not any(p.is_symlink()for p in root.parents),'FRESH_ACTUAL_GPU_PARENT_LOCAL_DIRECTORY')
    need(type(copy_cap_bytes)is int and copy_cap_bytes>(128<<20),'HOST_EXPLICIT_DIAGNOSTIC_COPY_BUDGET')
    root.mkdir(parents=True,mode=0o700);inventory=[];stores=[];used=0
    def one(r,target):
        nonlocal used
        check_host_resources();p=Path(r['path']);before=frame(p)
        need(before[2]==r['bytes']and used+r['bytes']+(128<<20)<=copy_cap_bytes,'FINITE_DIAGNOSTIC_COPY_CAP')
        v=os.statvfs(root);need(v.f_bavail*v.f_frsize-(copy_cap_bytes-used)>=local_disk_reserve_bytes,'ACTUAL_HOST_LOCAL_DISK_RESERVE')
        h=hashlib.sha256();n=0;temporary=target.with_name(target.name+'.partial')
        with p.open('rb')as f,temporary.open('xb')as out:
            while True:
                b=f.read(4<<20)
                if not b:break
                check_host_resources();out.write(b);h.update(b);n+=len(b);used+=len(b)
            out.flush();os.fsync(out.fileno())
        need(frame(p)==before and n==r['bytes']and h.hexdigest()==r['sha256'],'DIAGNOSTIC_COPY_COMPLETE_EOF_SHA')
        os.rename(temporary,target);local=reference(target);need(local['sha256']==r['sha256'],'ACTUAL_LOCAL_F64_AND_LMDB_REOPEN_SHA')
        inventory.append({'origin':r,'local':local});return local
    for r in s['store_references']:
        old=read(r);name=old['name'];need('/'not in name and '\\'not in name,'LITERAL_ORIGINAL_STORE_NAME')
        path=root/name;path.mkdir();one(old['data'],path/'data.mdb');one(old['manifest_reference'],path/'manifest.json')
        f64=one(old['f64_authority']['reference'],root/(name+'.authority_f64.sqlite'))
        stores.append({'name':name,'path':str(path),'origin_reference':r,'f64_authority':f64})
    inv=write(root/'copy_inventory.json',inventory)
    return write(root/'diagnostic_local_copy.json',{'schema':'ACTUAL_PROVISIONAL_DIAGNOSTIC_LOCAL_COPY_V1',
      'diagnostic_supplement_reference':supplement_reference,'local_stores':stores,'local_copy_inventory_reference':inv,
      'actual_host_job_id':os.environ['SLURM_JOB_ID'],'copied_bytes':used,'Model_payload_ACK':False})
