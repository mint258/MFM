"""Small read-only Root observation of owned services and durable progress."""
import json,os,socket,time
from pathlib import Path
from prepare import ROOT

def read(path):
    p=ROOT/path
    return json.loads(p.read_text()) if p.exists() else None

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    state=read('formal_s/root_coordinator_v1_status.json')
    output={'timestamp':time.time(),'training_status':state['status'],'conditions':{},'services':{}}
    for name,value in state.get('conditions',{}).items():
        record={k:value.get(k) for k in ['state','consumed_records','latest_job_id']}
        job=value.get('latest_job_id')
        if job:
            journal=ROOT/'s_training'/name/('segment_'+job)/'metrics.jsonl'
            if journal.exists() and journal.stat().st_size:
                with journal.open('rb') as stream:
                    size=journal.stat().st_size;stream.seek(max(0,size-8192));lines=stream.read().splitlines()
                for line in reversed(lines):
                    try:last=json.loads(line)
                    except json.JSONDecodeError:continue
                    if 'train/raw_element' in last:
                        record['durable_last_logged']={k:last.get(k) for k in ['consumed_records','epoch','optimizer_updates','train/raw_element','train/raw_distance','train/raw_bond_order','train/geometry_local_pair_A_rmse','segment_records_per_second','loader_wait_fraction']}
                        break
            guard=read('s_training/'+name+'/segment_'+job+'/validation_full_complete.json')
            if guard:record['latest_FULL']={'consumed_training_records':guard['consumed_training_records'],'local_RMSE_A':guard['result']['geometry_local_pair_A_rmse'],'records':guard['result']['records']}
        output['conditions'][name]=record
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for label,path in [('training','formal_s/root_coordinator_v1_identity.json'),('probes','probe_preparation_control/finish_root_v1_identity.json'),('accounting','formal_s/report_accounting_publisher_identity_v1.json'),('report','report_control/identity_v1.json')]:
        identity=read(path);alive=False
        if identity:
            try:
                process=Path('/proc')/str(identity['pid'])
                alive=process.stat().st_uid==identity['uid']==1278 and (process/'stat').read_text().split()[21]==identity['proc_start_ticks'] and boot==identity['boot_id']
            except FileNotFoundError:pass
        output['services'][label]={'identity_matches_live_process':alive,'pid':identity['pid'] if identity else None}
    probes=read('probe_preparation_control/finish_root_v1_status.json')
    output['probe_status']=probes['status'] if probes else None
    output['closed_probe_endpoints']=sum(bool(v.get('probe_closed')) for v in probes.get('endpoints',{}).values()) if probes else 0
    reports=read('report_control/status_v1.json');output['report_status']=reports['status'] if reports else None
    stop=read('formal_s/scientific_stop.json');output['guide_scientific_stop']=bool(stop)
    print(json.dumps(output),flush=True)

if __name__=='__main__':main()
