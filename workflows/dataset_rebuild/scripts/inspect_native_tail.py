"""Read only this native pilot job's live process metadata on its compute node."""
import argparse, concurrent.futures, json, os, re, subprocess, sys, time
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--job')
    parser.add_argument('--pairs',nargs='+')
    args=parser.parse_args()
    if args.pairs:
        def fetch(pair):
            node,job=pair.split(':')
            result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',node,
                sys.executable,'-B',str(Path(__file__).resolve()),'--job',job],
                capture_output=True,text=True,timeout=30)
            return {'node':node,'job_id':job,'exitcode':result.returncode,
                    'stdout':result.stdout,'stderr':result.stderr}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            output={'UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    'results':list(pool.map(fetch,args.pairs))}
        root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
        (root/'reports/native_tail_process_metadata.json').write_text(json.dumps(output,indent=2)+'\n')
        print(json.dumps(output),flush=True)
        return
    if not args.job:
        parser.error('--job or --pairs is required')
    uid=os.getuid()
    rows=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            if proc.stat().st_uid!=uid:
                continue
            groups=(proc/'cgroup').read_text()
            if not re.search(r'(?:^|/)job[_-]'+re.escape(args.job)+r'(?:/|$)',groups,re.M):
                continue
            argv=(proc/'cmdline').read_bytes().split(b'\0')
            executable=Path(os.fsdecode(argv[0])).name
            if executable not in ('mopac','xtb','zstd'):
                continue
            cwd=(proc/'cwd').resolve()
            if executable!='zstd' and not cwd.name.startswith(f'wp4native_{uid}_{args.job}_'):
                continue
            stat=(proc/'stat').read_text().rsplit(') ',1)[1].split()
            cpu_seconds=(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK')
            modes=[os.fsdecode(x) for x in argv[1:] if x.startswith(b'--')]
            keywords=None
            if executable=='mopac' and (cwd/'input.mop').exists():
                keywords=(cwd/'input.mop').open().readline().strip()
            rows.append({'pid':int(proc.name),'executable':executable,'cpu_seconds':cpu_seconds,
                         'modes':modes,'mopac_keywords':keywords,'scratch':str(cwd)})
        except (OSError,ValueError,IndexError):
            continue
    print(json.dumps({'job_id':args.job,'node':os.uname().nodename,'processes':rows}),flush=True)

if __name__=='__main__':
    main()
