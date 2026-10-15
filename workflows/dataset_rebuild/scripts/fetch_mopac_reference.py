"""Fetch small official source references for an output-parser audit only."""
import hashlib,json,urllib.request
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/mopac_reference')
root.mkdir(parents=True,exist_ok=True)
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'descriptor-analysis-parser-review'})
 with urllib.request.urlopen(req,timeout=30) as response:return response.read()
report={}
for tag in ['v23.0.3','main']:
 try:
  url=f'https://api.github.com/repos/openmopac/mopac/git/trees/{tag}?recursive=1'
  data=json.loads(get(url));paths=[x['path'] for x in data['tree'] if 'mullik' in x['path'].lower()]
  report[tag]={'tree_commit':data['sha'],'paths':paths,'files':[]}
  for path in paths:
   source=f'https://raw.githubusercontent.com/openmopac/mopac/{tag}/{path}'
   content=get(source);target=root/(tag+'_'+Path(path).name);target.write_bytes(content)
   report[tag]['files'].append({'path':str(target),'source':source,'sha256':hashlib.sha256(content).hexdigest()})
 except Exception as exc:report[tag]={'error':str(exc)}
(root/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
