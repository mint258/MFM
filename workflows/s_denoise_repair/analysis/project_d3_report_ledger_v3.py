"""Immutable report-only projection of the actual current D3 ledger, not a new experiment phase."""
import hashlib,json,os,socket,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    source=ROOT/'control/d3_local_blocks_v1';out=ROOT/'control/d3_report_projection_v3'
    jobs=(source/'jobs.json').read_bytes();status=(source/'status.json').read_bytes()
    assert json.loads(status)['status']=='D3_RUNNING'
    out.mkdir(exist_ok=False)
    (out/'jobs.json').write_bytes(jobs)
    doc={'status':'REPORT_ONLY_IMMUTABLE_D3_LEDGER_PROJECTION','not_a_scientific_phase':True,
       'timestamp_unix':time.time(),'original_phase':'d3_local_blocks_v1',
       'original_jobs_sha256':hashlib.sha256(jobs).hexdigest(),'original_status':json.loads(status),
       'formal_training_authorized':False}
    (out/'status.json').write_text(json.dumps(doc,indent=2)+'\n')
    print('REPORT_PROJECTION_CREATED',len(json.loads(jobs)),flush=True)
if __name__=='__main__':main()
