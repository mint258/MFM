"""Root-only final quota and scheduler snapshot, no scientific data work."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')


def query(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
    return {'argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


receipts = [json.loads(p.read_text()) for p in (ROOT / 'logs').glob('*_submission.json')]
ids = sorted({r['job_id'] for r in receipts}, key=int)
accounting = query(['sacct','-X','-j',','.join(ids),'-n','-P',
                    '-o','JobID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
queue = query(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%M|%C|%N|%R'])
quota = query(['quota','-v','-u','zixiao'])
if any(r['returncode'] for r in (accounting,queue,quota)):
    raise RuntimeError('Scheduler/quota metadata query failed')
registered_live = [line for line in queue['stdout'].splitlines() if line.split('|')[0] in ids]
if registered_live:
    raise ValueError('This round registered jobs remain live: ' + repr(registered_live))
timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
snapshot = {'UTC':timestamp,'registered_job_ids':ids,'accounting':accounting,'own_queue':queue,
            'quota':quota,'this_round_live_jobs':registered_live}
(ROOT / 'reports/final_job_snapshot.json').write_text(json.dumps(snapshot,indent=2) + '\n')
measurements = []
for line in quota['stdout'].splitlines():
    parts = line.split()
    if len(parts) >= 4 and parts[0].startswith('/'):
        used = int(parts[1].rstrip('*')); hard = int(parts[3].rstrip('*'))
        measurements.append({'filesystem':parts[0],'used_KiB':used,'hard_limit_KiB':hard,
            'free_bytes':max(0,hard-used)*1024,'free_TB_decimal':max(0,hard-used)*1024/1e12})
if not measurements:
    raise ValueError('No account quota numeric row available')
storage = json.loads((ROOT / 'c_engineering/storage/storage_report.json').read_text())
forward = []
for row in storage['writeback_peak_scenarios']:
    if row['population'] != 'relaxed' or row['value_format'] != 'per_record_4KiB_rounding_estimate_bytes':
        continue
    if row['raw_policy'] != 'SUCCESS_B_MINIMUM_OTHER_OUTPUTS_UNCHANGED' and row['hessian_fraction'] in (0,.1,1):
        peak = row['writeback_peak_forward_bytes'] + 96486
        forward.append({'raw_policy':row['raw_policy'],'raw_model':row['raw_model'],
            'hessian_fraction':row['hessian_fraction'],'projected_new_writeback_peak_bytes':peak,
            'headroom_vs_final_quota_bytes':measurements[0]['free_bytes']-peak,
            'compression_source':'Old WITH_POLAR full10020 calibration; fresh NOPOLAR coefficients listed separately',
            'temporary_margin_bytes':400_000_000_000,
            'scope':'Full parsed-label candidate, success ordinary raw minimum/all failure raw retained; scope alternatives are ratio models'})
final = {'UTC':timestamp,'quota_query':quota,'measurements':measurements,
    'relaxed_full_candidate_peak_vs_current_quota':forward,
    'not_disk_df':True,'capacity_reserved':False,'formal_storage_format_adopted':False}
(ROOT / 'reports/final_quota.json').write_text(json.dumps(final,indent=2) + '\n')
print(json.dumps({'status':'FINAL_METADATA_CAPTURED','free_TB':measurements[0]['free_TB_decimal'],
                  'registered_jobs':len(ids),'this_round_live':len(registered_live)}))
