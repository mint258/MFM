"""Audit the closed bounded lookup pilot; never publish a scientific baseline."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
raw=subprocess.check_output(['sacct','-j','4515550','-n','-X','-P','--format=JobID,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],stdin=subprocess.DEVNULL,text=True,timeout=30)
rows=[line.split('|') for line in raw.splitlines() if line.split('|')[0]=='4515550']
assert len(rows)==1
row=rows[0]
assert row[1]=='zixiao' and row[2]=='TIMEOUT' and row[6]=='compute-0-8'
pilot=ROOT/'diagnostics/lookup_refit_v2/pilot_job4515550'
assert not (pilot/'result.json').exists()
chunks=list((ROOT/'diagnostics/lookup_refit_v2/chunks').glob('chunk_*.json'))
assert not chunks
control=json.loads((pilot/'cache_control.json').read_text())
assert control['status']=='CACHE_ENABLED_AND_REPEAT_HITS_MATCH_ZERO_CACHE_PROBE_BITEXACT'
report=dict(status='LOOKUP_PILOT_TIMED_OUT_WITHOUT_DURABLE_TRAIN_CHUNKS',timestamp=time.time(),
 job_id=row[0],actual_parent=dict(state=row[2],exit_code=row[3],elapsed_seconds=int(row[4]),allocated_cpus=int(row[5]),node=row[6]),
 allocated_core_hours=int(row[4])*int(row[5])/3600,raw_sacct=raw,raw_sacct_sha256=hashlib.sha256(raw.encode()).hexdigest(),
 cache_control_passed=True,committed_TRAIN_chunks=0,committed_TRAIN_records=0,
 pilot_not_scientifically_accepted=True,full_v2_part_jobs_submitted=False,
 original_lookup_job='4515527',original_lookup_not_cancelled=True,
 canonical_lookup_pointer_written_by_this_script=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
dest=ROOT/'reports/lookup_pilot_terminal_v1.json'
with dest.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
print('LOOKUP_PILOT_ACTUAL',row[2],row[3],row[4],row[5],'CORES_H',report['allocated_core_hours'])
