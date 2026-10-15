"""Root metadata publisher with real parent accounting, including failed prototypes."""
import argparse,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='pilot_v4');a=ap.parse_args()
    submissions=[]
    for p in (ROOT/'submission').glob('*.json'):
        r=json.loads(p.read_text())
        if r.get('job_id'):submissions.append((p.stem,r['job_id']))
    ids=sorted({jid for _,jid in submissions})
    argv=['sacct','-j',','.join(ids),'--noheader','--parsable2','--format=JobIDRaw,User,JobName,State,ExitCode,AllocCPUS,ElapsedRaw,NodeList']
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    assert p.returncode==0,(p.returncode,p.stderr)
    (ROOT/'reports/accounting_actual.stdout').write_text(p.stdout)
    (ROOT/'reports/accounting_actual.exitcode').write_text(str(p.returncode)+'\n')
    columns=['JobIDRaw','User','JobName','State','ExitCode','AllocCPUS','ElapsedRaw','NodeList']
    records={}
    for line in p.stdout.splitlines():
        row=dict(zip(columns,line.split('|')))
        if row['JobIDRaw'] in ids:
            assert row['User']=='zixiao';records[row['JobIDRaw']]=row
    assert set(records)==set(ids)
    prefixes=[a.stage+'_group']
    if a.stage=='pilot_v5':prefixes.append('pilot_v4_group')
    selected={jid:records[jid] for name,jid in submissions if any(name.startswith(prefix) for prefix in prefixes)}
    save(ROOT/'reports/pilot_accounting.json',selected)
    save(ROOT/'reports/all_work_accounting.json',{'stage':a.stage,'timestamp':time.time(),'query_argv':argv,'query_rc':p.returncode,'parent_jobs':records,'actual_core_hours_all_work':sum(int(r['AllocCPUS'])*int(r['ElapsedRaw'])/3600 for r in records.values()),'selected_jobs':selected})
    print(json.dumps({'stage':a.stage,'states':{jid:r['State'] for jid,r in selected.items()}}))

if __name__=='__main__':main()
