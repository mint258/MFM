"""Run the registered C3 comparison in the last actual evaluation allocation."""
import fcntl,json,subprocess,sys
from pathlib import Path
plan_path=Path(sys.argv[1])
C=plan_path.parent
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
p=json.loads(plan_path.read_text())
if not all((Path(r['evaluation_output'])/'producer_complete.json').exists() for r in p['runs']):
    raise SystemExit(0)
with (C/'comparison.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    result=R/'results/model_v3_c3_views.json'
    page=R/'docs/model_v3/M3_C3_RESULTS.md'
    if result.exists() and page.exists():
        raise SystemExit(0)
    subprocess.run([sys.executable,'-B',str(R/'tools/model_v3/v3_score_followon.py'),
        '--manifest',str(C/'decision_manifest.json'),'--results',str(result),'--page',str(page)],
        cwd=R,check=True)
