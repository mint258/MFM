"""Portable code patch against verified original export; no source mutation."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
SOURCE=ROOT/'source_v3'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    bound=json.loads((ROOT/'configs/D3_source_binding_v4.json').read_text())
    for row in bound['files']:assert sha(row['path'])==row['sha256']
    original=json.loads((SOURCE/'docs/SOURCE_MANIFEST.json').read_text())
    references={row['path']:row for row in original['files']}
    candidates=sorted((SOURCE/'current/phychem_mfm').rglob('*.py'))+[SOURCE/'current/tests/test_equivariant_denoising.py']
    patch=[];changed=[];before={};after={};verified=0
    for path in candidates:
        name=path.relative_to(SOURCE).as_posix();new=path.read_bytes()
        assert '..' not in Path(name).parts
        if name in references:
            ref=references[name];old_path=Path(ref['source_path']);old=old_path.read_bytes()
            assert hashlib.sha256(old).hexdigest()==ref['sha256'],'Original export source changed'
            verified+=1
        else:old=None
        if old==new:continue
        patch.append('diff --git a/'+name+' b/'+name+'\n')
        if old is None:patch.append('new file mode 100644\n')
        patch.extend(difflib.unified_diff([] if old is None else old.decode('utf-8').splitlines(True),
            new.decode('utf-8').splitlines(True),fromfile='/dev/null' if old is None else 'a/'+name,tofile='b/'+name))
        before[name]=old;after[name]=new
        changed.append(dict(path=name,new_file=old is None,original_sha256=None if old is None else hashlib.sha256(old).hexdigest(),
            repaired_sha256=hashlib.sha256(new).hexdigest(),bytes=len(new)))
    output=ROOT/'reports/core_repair_patch_v1';output.mkdir(exist_ok=False)
    patch_path=output/'s_denoise_core_v3.patch';patch_path.write_text(''.join(patch))
    with tempfile.TemporaryDirectory(prefix='owned_patch_check_',dir=output) as temporary:
        temp=Path(temporary)
        for name,data in before.items():
            if data is not None:
                destination=temp/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
        checked=subprocess.run(['git','apply','--check',str(patch_path)],cwd=temp,text=True,capture_output=True,stdin=subprocess.DEVNULL)
        assert checked.returncode==0,checked.stderr
        applied=subprocess.run(['git','apply',str(patch_path)],cwd=temp,text=True,capture_output=True,stdin=subprocess.DEVNULL)
        assert applied.returncode==0,applied.stderr
        for name,data in after.items():assert (temp/name).read_bytes()==data
        assert sorted(str(p.relative_to(temp)) for p in temp.rglob('*') if p.is_file())==sorted(after)
    report=dict(status='CORE_PATCH_APPLIES_TO_VERIFIED_ORIGINAL_AND_REPRODUCES_BOUND_REPAIR_BYTES',
        original_source_files_verified=verified,changed=changed,patch=dict(path=str(patch_path),sha256=sha(patch_path),bytes=patch_path.stat().st_size),
        source_binding=dict(path=str(ROOT/'configs/D3_source_binding_v4.json'),sha256=sha(ROOT/'configs/D3_source_binding_v4.json')),
        no_original_or_active_source_modified=True,scope='Scientific package and new C6 test only; runtime workflows, v3 configs and SourceManifest are delivered separately',
        scientific_gate_passed=False,formal_training_complete=False)
    with (output/'receipt.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=report['status'],changed_files=len(changed),patch_bytes=patch_path.stat().st_size)))


if __name__=='__main__':main()
