#!/usr/bin/env python3
"""Create v3 with only decoder-EOF and snapshot-filename changes."""
from pathlib import Path
import ast
import hashlib
import json

here=Path(__file__).absolute().parent
v2=here/'wp4_native_pilot_v2.py'; v3=here/'wp4_native_pilot_v3.py'
old=v2.read_text()
anchor='decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()'
replacement=('while decoder.stdout.read(1<<20): pass\n'
             '                        decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()')
assert old.count(anchor)==1 and old.count('(Path(__file__),"wp4_native_pilot_v2.py")')==1
new=old.replace(anchor,replacement,1).replace('(Path(__file__),"wp4_native_pilot_v2.py")','(Path(__file__),"wp4_native_pilot_v3.py")',1)
assert new.replace(replacement,anchor,1).replace('(Path(__file__),"wp4_native_pilot_v3.py")','(Path(__file__),"wp4_native_pilot_v2.py")',1)==old
ast.parse(new)
if v3.exists(): raise ValueError('Do not replace an existing native-v3 source')
v3.write_text(new,encoding='utf-8',newline='\n')
report={'status':'V3_AST_PASS_ARCHIVE_ONLY_CHANGE','v2_sha256':hashlib.sha256(v2.read_bytes()).hexdigest(),
        'v3_sha256':hashlib.sha256(v3.read_bytes()).hexdigest(),
        'only_source_changes':['Drain zstd decoder stdout to EOF before closing/waiting.',
                               'Snapshot runner filename v2 -> v3.'],
        'reverse_patch_exactly_equals_v2_source':True,'QM_argv_and_keywords_changed':False}
(here.parent/'reports/wp4_native_v3_archive_patch.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
