#!/usr/bin/env python3
"""Record static checks and source hashes only; no LMDB/QM/matrix work."""
import ast
import hashlib
import json
from pathlib import Path

here=Path(__file__).absolute().parent
names=('wp4_native_pilot_v2.py','wp4_native_pilot_v3.py','wp4_repair_native_v3.py',
       'wp4_polar_cost_probe.py','wp4_parsers.py','wp4_mulliken_pairs_v2.py')
sources={}
for name in names:
    path=here/name; ast.parse(path.read_text())
    sources[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
report={'status':'STATIC_READY_FOR_ROOT_SLURM_ONLY_NOT_NUMERICALLY_EXECUTED','seed':20261010,'sources':sources,
        'actual_static_checks':{'native_v3':'AST_AND_NATIVE_CONFIG_PASS; exit0',
                                'repair_v3':'ARCHIVE_ONLY_REPAIR_AST_PASS; exit0',
                                'polar_cost':'AST_SINGLE_B_NO_POLAR_PASS; exit0'},
        'QM_started':False,'LMDB_opened':False,
        'native_v3_change_scope':'Drain decoder stdout to EOF before wait; snapshot filename only. Reverse patch equals frozen v2 exactly.',
        'repair_plan':'Use a new v3 directory. Copy29 completed molecule Parquet unchanged and keep immutable v2 archive references. Use3 failed molecules stored final task attempts for archive/Parquet commit; invoke is unconditionally forbidden and source reader performs no LMDB access.',
        'repair_guard':'Every requested task must already have a closed final state before repair; missing slots fail instead of starting QM.',
        'decoder_evidence':'Repair workers inspect one existing archive of each failed molecule under both close policies and record actual decoder returncodes; no output changes.',
        'polar_cost_probe':'At most5 lowest original-energy retained records per nonempty size stratum. One B without POLAR, paired B from existing formal pilot; task pm7_B_noPOLAR; no other calls or Hessian. Pass --engine wp4_native_pilot_v3.py to use repaired compactor.',
        'polar_cost_outputs':'records/<hash>/results.parquet, receipt.json, raw_outputs.tar.zst; native Parquet schema and paired_cost details; metadata and per-job stratified statistics.',
        'formal_native_pilot_complete':False}
path=here.parent/'reports/wp4_native_v3_cost_readiness.json'
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
