"""Clone the small audited code tree, excluding caches and Git metadata. No science."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,shutil,socket,stat,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
SOURCE=ROOT/'source_v3';DEST=ROOT/'source_v4'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert not DEST.exists() and not SOURCE.is_symlink()
    binding=ROOT/'configs/D3_source_binding_v4.json';pins=json.loads(binding.read_text())['files']
    def check(row):assert sha(row['path'])==row['sha256'];return True
    with ThreadPoolExecutor(16) as pool:list(pool.map(check,pins))
    files=[];total=0
    for directory,dirs,names in os.walk(SOURCE,followlinks=False):
        dirs[:]=[n for n in dirs if n not in {'.git','__pycache__','.pytest_cache','.ruff_cache'}]
        assert all(not (Path(directory)/n).is_symlink() for n in dirs)
        for name in names:
            path=Path(directory)/name;info=path.lstat();assert stat.S_ISREG(info.st_mode) and not path.is_symlink()
            relative=path.relative_to(SOURCE);assert info.st_size<=2*(1<<20)
            assert path.suffix not in {'.pt','.pth','.ckpt','.lmdb','.mdb','.npy','.npz','.pkl','.parquet','.arrow','.sqlite','.db','.zip','.gz'}
            files.append((path,relative));total+=info.st_size
            assert len(files)<=2000 and total<=16*(1<<20)
    DEST.mkdir()
    def copy(item):
        path,relative=item;target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);before=sha(path);assert sha(target)==before
        return {'relative_path':relative.as_posix(),'sha256':before,'bytes':target.stat().st_size}
    with ThreadPoolExecutor(16) as pool:rows=list(pool.map(copy,files))
    with ThreadPoolExecutor(16) as pool:list(pool.map(check,pins))
    out=ROOT/'control/atom_projection_opt_v1';out.mkdir(parents=True,exist_ok=False)
    doc={'status':'AUDITED_CODE_CLONE_COMPLETE_CANDIDATE_NOT_FROZEN_OR_ACTIVE','source':str(SOURCE),'destination':str(DEST),
         'files':rows,'total_bytes':total,'original_99_pins_verified_before_and_after':True,'timestamp_unix':time.time()}
    with (out/'source_copy_receipt.json').open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
    print('CODE_CLONE_COMPLETE',len(rows),total,flush=True)
if __name__=='__main__':main()
