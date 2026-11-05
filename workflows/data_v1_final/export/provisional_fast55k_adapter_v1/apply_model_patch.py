"""Apply the reviewed literal three-file patch to an ISOLATED Model copy only.

Source utility, not run by the author. It does not create a copy/worktree, run
Git, tests, data readers, admission or training. Root owns copy/registration.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--model-copy',required=True)
    p.add_argument('--patch',required=True);p.add_argument('--receipt',required=True);a=p.parse_args()
    root=Path(a.model_copy).absolute();patch_path=Path(a.patch).absolute();receipt=Path(a.receipt).absolute()
    need(root.name.startswith('MFM_model_v3_provisional_')and root.is_dir()
      and all(not q.is_symlink()for q in(root,*root.parents)),
      'EXPLICIT_ISOLATED_COPY_REQUIRED_NOT_SHARED_MODEL_TREE')
    need(not receipt.exists(),'FRESH_PATCH_RECEIPT')
    patch_raw=patch_path.read_bytes();patch=json.loads(patch_raw)
    need(patch['schema']=='MODEL_V3_PROVISIONAL_FAST55K_LITERAL_PATCH_V1'
      and patch['shared_model_modified_by_author']is False,'EXACT_SOURCE_PATCH_SCHEMA')
    names={'current/phychem_mfm/phase1/'+n for n in
      ('v3_data_adapter.py','v3_pilot_smoke.py','v3_physical_policy.py')}
    need({f['relative_path']for f in patch['files']}==names and len(patch['files'])==3,'EXACT_THREE_MODEL_FILES')
    changes=[]
    for item in patch['files']:
        target=root/item['relative_path'];need(root in target.parents and target.resolve()==target
          and not target.is_symlink(),'COPY_TARGET_ONLY')
        raw=target.read_bytes();need(sha(raw)==item['before_sha256'],'EXACT_REVIEWED_MODEL_BASE_SHA')
        # Preserve all existing source bytes except the listed UTF-8 literals.
        text=raw.decode('utf-8');newline='\r\n'if '\r\n'in text else'\n'
        for edit in item['replacements']:
            before=edit['before'].replace('\n',newline);after=edit['after'].replace('\n',newline)
            need(text.count(before)==1,'EXACT_SINGLE_LITERAL_PATCH_SITE')
            text=text.replace(before,after,1)
        new=text.encode('utf-8');changes.append((target,raw,new,item['relative_path']))
    # All preconditions for all three files pass before the first replacement.
    written=[]
    try:
        for target,old,new,name in changes:
            temporary=target.with_name(target.name+'.provisional_patch.partial')
            with temporary.open('xb')as f:f.write(new);f.flush();os.fsync(f.fileno())
            need(target.read_bytes()==old,'COPY_SOURCE_CHANGED_DURING_PATCH')
            os.replace(temporary,target);written.append(name)
        status='ISOLATED_SOURCE_PATCH_APPLIED_NOT_TESTED_OR_REGISTERED'
    except BaseException:
        status='PARTIAL_ISOLATED_SOURCE_PATCH_NO_EXECUTION_AUTHORITY'
        raise
    finally:
        report={'schema':'MODEL_V3_PROVISIONAL_FAST55K_PATCH_RECEIPT_V1','status':status,
          'model_copy':str(root),'patch_reference':{'path':str(patch_path),'bytes':len(patch_raw),'sha256':sha(patch_raw)},
          'written_files':written,'files':[{'relative_path':n,'before_sha256':sha(old),
            'after_sha256':sha(new)}for _,old,new,n in changes],
          'shared_model_source_changed':False,'tests_or_science_run':False,'Model_payload_ACK':False}
        with receipt.open('x',encoding='utf-8')as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')

if __name__=='__main__':main()
