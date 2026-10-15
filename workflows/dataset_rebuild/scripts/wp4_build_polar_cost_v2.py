#!/usr/bin/env python3
"""Copy the cost probe and change only frozen-v4 snapshot interfaces."""
from pathlib import Path
import ast
import hashlib
import json

here=Path(__file__).absolute().parent
old=here/'wp4_polar_cost_probe.py'; new=here/'wp4_polar_cost_probe_v2.py'
body=old.read_text()
def change(anchor,replacement):
    global body
    if body.count(anchor)!=1: raise ValueError('Nonunique cost source anchor:'+anchor)
    body=body.replace(anchor,replacement,1)

change('output/\'source_snapshot/wp4_native_pilot_v2.py\'',
       "output/'source_snapshot'/config['_engine_snapshot_name']")
change("output/'source_snapshot/wp4_parsers.py'", "output/'source_snapshot'/config['_parser_snapshot_name']")
change("default=str(HERE/'wp4_native_pilot_v2.py')", "default=str(HERE/'wp4_native_pilot_v4.py')")
change("default=str(HERE/'wp4_native_v2_config.json')", "default=str(HERE/'wp4_native_v4_config.json')")
change("engine=import_engine(args.engine)\n    config=json.loads(Path(args.config).read_text())",
       "engine=import_engine(args.engine)\n"
       "    config=json.loads(Path(args.config).read_text())\n"
       "    engine_path=Path(args.engine).absolute()\n"
       "    getter_path=engine_path.parent/'wp4_mulliken_pairs_v3.py'\n"
       "    parser_path=engine_path.parent/'wp4_parsers.py'\n"
       "    if 'wp4_mulliken_pairs_v3.py' not in engine_path.read_text(): raise ValueError('FROZEN_NATIVE_V4_GETTER_INTERFACE_REQUIRED')\n"
       "    config['_engine_snapshot_name']=engine_path.name\n"
       "    config['_parser_snapshot_name']=parser_path.name\n"
       "    config['_getter_snapshot_name']=getter_path.name")
change("'getter_sha256':engine.sha(HERE/'wp4_mulliken_pairs_v2.py'),'parser_sha256':engine.sha(HERE/'wp4_parsers.py'),",
       "'engine_snapshot_name':engine_path.name,'getter_sha256':engine.sha(getter_path),'parser_sha256':engine.sha(parser_path),\n"
       "             'getter_snapshot_name':getter_path.name,'parser_snapshot_name':parser_path.name,")
change("((Path(__file__),'wp4_polar_cost_probe.py'),(Path(args.engine),'wp4_native_pilot_v2.py'),\n                         (HERE/'wp4_parsers.py','wp4_parsers.py'),(HERE/'wp4_mulliken_pairs_v2.py','wp4_mulliken_pairs_v2.py'))",
       "((Path(__file__),'wp4_polar_cost_probe_v2.py'),(engine_path,engine_path.name),\n"
       "                         (parser_path,parser_path.name),(getter_path,getter_path.name))")
change("assert len(config['tasks'])==1 and config['tasks'][0]['name']=='pm7_B'",
       "assert len(config['tasks'])==1 and config['tasks'][0]['name']=='pm7_B'\n"
       "        ast.parse(getter_path.read_text()); ast.parse(parser_path.read_text())\n"
       "        assert config['_engine_snapshot_name']==engine_path.name and config['_getter_snapshot_name']=='wp4_mulliken_pairs_v3.py'")
ast.parse(body)
if new.exists(): raise ValueError('Do not replace an existing cost-probe-v2 source')
new.write_text(body,encoding='utf-8',newline='\n')
report={'status':'COST_V2_SNAPSHOT_INTERFACE_AST_PASS','old_cost_source_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
        'new_cost_source_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),
        'new_default_engine':'wp4_native_pilot_v4.py','new_default_getter':'wp4_mulliken_pairs_v3.py',
        'new_default_config':'wp4_native_v4_config.json','QM_selection_or_keywords_changed':False,
        'paired_roots':'--paired-pilot-root accepts each actual bucket directory containing its own metadata.json'}
(here.parent/'reports/wp4_polar_cost_v2_static_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
