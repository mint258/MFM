"""Observe one actual Main rescue parent, then index its genuinely closed scores."""
import argparse,json,os,pathlib,subprocess,time
CONTROL=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103')
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/pubchem_completion_20261103')
PY='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/software/pubchem_completion_20261103_venv/bin/python'
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',required=True);a=p.parse_args()
    if os.getuid()!=1278 or a.job!='4525875':raise ValueError('Actual own Main875 observation only')
    rawpath=CONTROL/('main_exact_rescue_'+a.job+'_native_terminal.psv')
    index=CONTROL/('main_exact_rescue_'+a.job+'_return_index.json')
    summary=CONTROL/('main_exact_rescue_'+a.job+'_return_index_summary.json')
    if any(p.exists()for p in(rawpath,index,summary)):raise ValueError('Preserve previous native observation/index; inspect before rerunning')
    while True:
        result=subprocess.run(['sacct','-P','-j',a.job,'--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],
            text=True,capture_output=True)
        if result.returncode:
            print(json.dumps(dict(event='NATIVE_OBSERVATION_TEMPORARILY_UNAVAILABLE',returncode=result.returncode)),flush=True)
            time.sleep(30);continue
        lines=result.stdout.splitlines()
        if not lines:time.sleep(30);continue
        names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
        parents=[r for r in rows if r.get('JobIDRaw')==a.job]
        if len(parents)!=1:time.sleep(30);continue
        parent=parents[0]
        if parent['UID']!='1278':raise ValueError('Actual native producer UID differs')
        state=parent['State'].split()[0].rstrip('+')
        if state not in TERMINAL:time.sleep(30);continue
        if not all(r['State'].split()[0].rstrip('+')in TERMINAL for r in rows):time.sleep(30);continue
        with rawpath.open('x')as f:f.write(result.stdout);f.flush();os.fsync(f.fileno())
        if state!='COMPLETED'or parent['ExitCode']!='0:0':
            raise ValueError('Main producer terminal without C0; preserve all outputs, do not index/restart scientific work: '+repr(parent))
        break
    command=['ssh','-n','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519',
        '-o','UserKnownHostsFile='+str(CONTROL/'main16_verified_known_hosts_20261104'),'compute-0-16',
        PY,'-I','-B',str(ROOT/'workflows/expansion/completion_runtime_v1/main_rescue_score_transport.py'),'index',
        '--manifest','/dev/shm/zixiao_pubchem_rescue_20261104/main_exact_rescue_job_4525875/manifest.json',
        '--native-accounting',str(rawpath),'--job',a.job,'--output',str(index)]
    result=subprocess.run(command,text=True,capture_output=True)
    if result.returncode:raise RuntimeError('Closed index failed; producer is not restarted: '+result.stderr)
    value=json.loads(result.stdout)
    with summary.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(event='MAIN_NATIVE_C0_AND_CLOSED_SCORE_INDEX_READY',summary_path=str(summary),**value)),flush=True)
if __name__=='__main__':main()
