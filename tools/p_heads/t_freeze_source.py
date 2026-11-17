"""Freeze the small executable source; share only unchanged inputs/configuration."""
import argparse,pathlib,shutil
from h_resources import REPO,CONTROL,guard,watchdog

def main():
    watchdog()
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='T3_source',choices=['T3_source','T12_source','T1_source','T2_source','B3_seed1_source','T1_seed1_source','T2_seed1_source','T3_seed1_source'])
    args=parser.parse_args()
    destination=CONTROL/args.name
    if destination.exists():raise FileExistsError(destination)
    trees=['current','tools']
    size=sum(p.stat().st_size for name in trees for p in (REPO/name).rglob('*') if p.is_file())
    if size>600*1024**2:raise OSError('Unexpected source snapshot exceeds600MiB')
    destination.mkdir()
    def ignore(path,names):return [n for n in names if n in ('__pycache__','.pytest_cache')]
    for name in trees:
        guard(force=True);shutil.copytree(REPO/name,destination/name,ignore=ignore)
    for source in REPO.iterdir():
        if source.name in (*trees,'.git'):continue
        (destination/source.name).symlink_to(source,target_is_directory=source.is_dir())
    print(str(destination),size,flush=True)
if __name__=='__main__':main()
