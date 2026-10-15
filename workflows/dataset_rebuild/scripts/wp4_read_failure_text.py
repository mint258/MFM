#!/usr/bin/env python3
"""Read compact audit metadata and one small archived text member only."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
report=json.loads((root/'reports/wp4_bounded_failure_audit_job_4512826.json').read_text())
failures=report['failures']
print(json.dumps({'B_reasons':dict(collections.Counter(r['mulliken_qc']['failure_reason'] for r in failures if r['task']=='pm7_B')),
                  'ESP_code_counts':dict(collections.Counter(r['failure_code'] for r in failures if r['task']=='pm7_ESP')),
                  'ESP_without_property_marker':[{'record_id':r['record_id'],'molecule_id':r['molecule_id'],'archive':r['archive'],
                       'out':r['archived_text'].get('input.out')} for r in failures if r['task']=='pm7_ESP' and not r.get('property_failure_lines')],
                  'vfukui_records':[{'record_id':r['record_id'],'molecule_id':r['molecule_id'],'failure_reason':r['failure_reason']} for r in failures if r['task']=='xtb_vfukui']},indent=2))
target=next(r for r in failures if r['task']=='pm7_ESP' and not r.get('property_failure_lines') and
            r['archived_text'].get('input.out',{}).get('bytes',1000000)<10000)
reference=target['archive']; path=Path(reference['path'])
assert path.stat().st_size<1000000
assert hashlib.sha256(path.read_bytes()).hexdigest()==reference['sha256']
member_name=reference['member_prefix']+'/input.out'
decoder=subprocess.Popen(['/usr/bin/zstd','-d','-c',str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
selected=None
try:
    with tarfile.open(fileobj=decoder.stdout,mode='r|') as files:
        for member in files:
            if member.name==member_name:
                assert member.isfile() and member.size<10000
                selected=files.extractfile(member).read()
finally:
    while decoder.stdout.read(1<<20): pass
    decoder.stdout.close(); stderr=decoder.stderr.read(); code=decoder.wait()
assert code==0,stderr
assert selected is not None
assert hashlib.sha256(selected).hexdigest()==target['archived_text']['input.out']['sha256']
print('PINNED_SMALL_ESP_OUTPUT '+target['record_id'])
print(selected.decode(errors='replace'))
