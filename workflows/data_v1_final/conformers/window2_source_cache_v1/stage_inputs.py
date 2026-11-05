"""Copy original immutable LMDB inputs once for optional physical read caching."""
import argparse,json,os,socket,subprocess
from pathlib import Path

def stage(template,output):
    plan=json.loads(Path(template).read_text(encoding='utf-8-sig'))
    job=os.environ['SLURM_JOB_ID']
    root=Path('/tmp')/('window2_native_lmdb_cache_20261105_'+job)
    root.mkdir(exist_ok=False)
    output=Path(output)
    plan.update(cache_root=str(root),cache_node=socket.gethostname(),closed_source_path_map={},integrity_hashes_computed=False,numerical_data_decoded=False)
    def save():
        temporary=output.with_suffix('.next.json')
        temporary.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(temporary,output)
    save()
    for source in plan['sources']:
        destination=root/source['name']
        subprocess.run(['rsync','--sparse','--times','--',source['path'],str(destination)],check=True)
        plan['closed_source_path_map'][source['path']]=str(destination)
        save()
        print(json.dumps({'stage':'NATIVE_INPUT_CACHE','closed_sources':len(plan['closed_source_path_map']),'total_sources':len(plan['sources']),'source':source['name'],'bytes':destination.stat().st_size}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--output',required=True);a=p.parse_args();stage(a.template,a.output)
