"""Freeze the small executable source; share only unchanged inputs/configuration."""
import pathlib,shutil
from h_resources import REPO,CONTROL,guard,save

def main():
    guard(force=True)
    destination=CONTROL/'T3_source'
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
