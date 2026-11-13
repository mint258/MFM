import csv,json
from pathlib import Path
import numpy as np
R=Path('/share/home/zixiao/descriptor_analysis');out=R/'runs/p_recipe_20261113/P_clip.json'
if out.exists():print(out.read_text())
else:
 source=Path('/lfshome/zixiao/model_v31_20261105/P_C1_0_seed0_micro32_continuation_20261110/losses.csv')
 with source.open() as stream:rows=list(csv.DictReader(stream))
 norms=np.asarray([float(r['preclip_norm']) for r in rows],dtype=np.float64)
 result=dict(clip=float(np.quantile(norms,.99)),source_job=4529108,source=str(source),updates=len(norms),first_samples=int(rows[0]['samples']),last_samples=int(rows[-1]['samples']),rule='one p99 of complete job4529108 preclip log; fixed for every P arm; no per-arm refit')
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))