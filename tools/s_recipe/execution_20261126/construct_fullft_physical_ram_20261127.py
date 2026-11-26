"""New two boundaries plus actual same-Python metadata syscall evidence."""
import json
import re
import subprocess
import sys
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
from fullft_ram_envelope_20261127 import read,require_closed_proof,GiB
from fullft_physical_ram_20261127 import estimate_physical,SCHEMA
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_physical_ram_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
trace=C/'fullft_metadata_vfork_20261127.strace'
output=subprocess.check_output(['/usr/bin/strace','-qq','-f','-e','trace=process','-o',str(trace),
    sys.executable,'-B',str(C/'fullft_metadata_spawn_probe_20261127.py')],text=True,timeout=60)
probe=json.loads(output.strip().splitlines()[-1])
lines=[line for line in trace.read_text().splitlines()
    if re.match(str(probe['pid'])+r'\s+(?:clone|vfork|fork)\(',line)]
verified=(probe['use_vfork'] is True and len(lines)>=2 and
    all('vfork(' in line or ('CLONE_VM' in line and 'CLONE_VFORK' in line) for line in lines))
if not verified:raise ValueError('Actual metadata spawn did not establish shared-address vfork/exec')
old=require_closed_proof()
nvidia=read(C/'nvidia_metadata_rusage_20261127.json')
if nvidia.get('actual_exit_code')!=0:raise ValueError('Actual GPU-query footprint missing')
peak=max(probe['metadata_peak_RSS_bytes'],nvidia['max_RSS_KiB']*1024)
bound=estimate_physical(old['estimate']['main_peak_bytes'],peak,
    verified_shared_address_spawn=verified)
if bound['estimated_physical_host_peak_bytes']>8*GiB:raise ValueError('Physical estimate exceeds8GiB')
value=dict(schema=SCHEMA,status='PHYSICAL_RESOURCE_ESTIMATE_READY',new_tests=count,**execution_fields(),
    real_metadata_spawn_trace=True,probe=probe,verified_parent_spawn_lines=lines,trace_source=str(trace),
    original_full_fit_estimate_source=str(C/'fullft_ram_envelope_20261127.json'),
    nvidia_metadata_observation=nvidia,estimate=bound,future_peak_ram_bytes=8*GiB,
    providers_sha256=old['providers_sha256'],python=sys.executable,
    active_contracts_changed=False,pretraining_reservations_changed=False,policy_activated=False,
    new_scientific_work=False,
    interpretation='Measured main/metadata process maxima plus verified vfork topology and conservative allowances; physical envelope is estimated, not measured whole-tree peak')
write(C/'fullft_physical_ram_20261127.json',value)
write(R/'results/s_recipe/fullft_physical_ram_20261127.json',value)
print(json.dumps(dict(status=value['status'],estimate=bound,spawn_lines=lines)),flush=True)
