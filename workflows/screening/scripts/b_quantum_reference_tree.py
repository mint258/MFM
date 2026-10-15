#!/usr/bin/env python3
"""Locate/fetch official pinned FORTRAN reference text, without executing it."""
from pathlib import Path
import json
import hashlib
import urllib.request

root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/official_references')
tree=json.loads((root/'mopac_v23_tree.json').read_text())
names={'force.F90','esp.F90','esp1.F90','run_mopac.F90','mopac.F90','check.F90','check_keywords.F90'}
paths=[row['path'] for row in tree['tree'] if row['path'].rsplit('/',1)[-1] in names]
print(json.dumps(paths))
for path in paths:
    url='https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/'+path
    target=root/(path.replace('/','__'))
    if not target.exists():target.write_bytes(urllib.request.urlopen(url,timeout=30).read())
    print(json.dumps({'source':url,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
