"""Parallel, read-only directory entry counts; never delete or move files."""
import argparse,concurrent.futures,csv,json,os,stat,time
from pathlib import Path
def walk(task):
    label,start=task;stack=[start]
    out={'top_level':label,'entries':0,'regular_files':0,'directories':0,'symlinks':0,'other':0,
         'logical_bytes':0,'allocated_bytes':0,'vanished_entries':0,'errors':[]}
    while stack:
        p=stack.pop()
        try:s=os.lstat(p)
        except FileNotFoundError:out['vanished_entries']+=1;continue
        except OSError as e:
            if len(out['errors'])<100:out['errors'].append({'path':str(p),'error':str(e)})
            continue
        out['entries']+=1;out['logical_bytes']+=s.st_size;out['allocated_bytes']+=getattr(s,'st_blocks',0)*512
        if stat.S_ISLNK(s.st_mode):out['symlinks']+=1
        elif stat.S_ISREG(s.st_mode):out['regular_files']+=1
        elif stat.S_ISDIR(s.st_mode):
            out['directories']+=1
            try:
                with os.scandir(p) as entries:
                    for item in entries:stack.append(item.path)
            except OSError as e:
                if len(out['errors'])<100:out['errors'].append({'path':str(p),'error':str(e)})
        else:out['other']+=1
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--home',default='/share/home/zixiao')
    p.add_argument('--output',required=True);p.add_argument('--workers',type=int,default=24)
    a=p.parse_args();started=time.time();root=Path(a.home).absolute()
    tasks=[];top_seed=[]
    for item in os.scandir(root):
        s=item.stat(follow_symlinks=False)
        if stat.S_ISDIR(s.st_mode):
            top_seed.append((item.name,s))
            for child in os.scandir(item.path):
                cs=child.stat(follow_symlinks=False)
                if stat.S_ISDIR(cs.st_mode):
                    top_seed.append((item.name,cs))
                    try:
                        tasks.extend((item.name,x.path) for x in os.scandir(child.path))
                    except OSError:tasks.append((item.name,child.path));top_seed.pop()
                else:tasks.append((item.name,child.path))
        else:tasks.append((item.name,item.path))
    grouped={}
    def add(r):
        d=grouped.setdefault(r['top_level'],{k:0 for k in ('entries','regular_files','directories','symlinks','other',
             'logical_bytes','allocated_bytes','vanished_entries')})
        d.setdefault('errors',[])
        for k,v in r.items():
            if k=='errors':d[k].extend(v[:max(0,100-len(d[k]))])
            elif k!='top_level':d[k]+=v
    for label,s in top_seed:
        add({'top_level':label,'entries':1,'regular_files':0,'directories':1,'symlinks':0,'other':0,
             'logical_bytes':s.st_size,'allocated_bytes':getattr(s,'st_blocks',0)*512,'vanished_entries':0,'errors':[]})
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(walk,tasks,chunksize=1):add(r)
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'READ_ONLY_SCAN_COMPLETED','home':str(root),'uid':os.getuid(),'host':os.uname().nodename,
      'job_id':os.environ.get('SLURM_JOB_ID'),'workers':a.workers,'parallel_subtrees':len(tasks),
      'started':started,'finished':time.time(),'directories':grouped,
      'limitations':['Counts directory entries, not deduplicated hardlink inodes.',
        'Live tree observed over scan interval; vanished concurrent entries explicitly counted.',
        'Quota file count covers filesystem UID accounting, which can include paths outside this home.']}
    tmp=output.with_name(output.name+'.pending');tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');os.replace(tmp,output)
    print(json.dumps({'status':report['status'],'output':str(output),'entries':sum(x['entries'] for x in grouped.values()),
         'elapsed_seconds':report['finished']-started}))
if __name__=='__main__':main()
