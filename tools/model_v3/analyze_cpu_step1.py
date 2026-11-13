"""Read completed step-1 evidence; no training or data rereads."""
from collections import Counter
from pathlib import Path
import csv,html,json,re
root=Path('/lfshome/zixiao/model_v3_perf_20261112/step1_4530262')
svg=(root/'flame.svg').read_text()
rows=[]
for title in re.findall(r'<title>(.*?)</title>',svg):
    text=html.unescape(title)
    match=re.search(r'\(([\d,]+) samples?, ([\d.]+)%\)',text)
    if match:
        rows.append((float(match[2]),text))
print('LARGEST FLAME FRAMES')
for percent,text in sorted(rows,reverse=True)[:35]: print(text)
print('HEAD/LOSS/BACKWARD FRAMES')
for percent,text in sorted(rows,reverse=True):
    if percent>=.4 and any(s in text for s in ('v3_heads','v3_losses','autograd','Backward','backward','v31_training','v31_experiments')): print(text)
for mode in ('baseline','profile'):
    with (root/mode/'losses.csv').open() as file: losses=list(csv.DictReader(file))
    with (root/(mode+'_telemetry.csv')).open() as file: telemetry=list(csv.DictReader(file))
    train=[r for r in telemetry if r.get('training_started')=='1']
    if train:
        last_growth=max(i for i,r in enumerate(train) if i==0 or r['losses_bytes']!=train[i-1]['losses_bytes'])
        train=train[:last_growth+1]
    dt=float(losses[-1]['seconds'])-float(losses[0]['seconds'])
    result=dict(mode=mode,rows=len(losses),steady_samples_per_second=(int(losses[-1]['samples'])-int(losses[0]['samples']))/dt)
    for col in ('main_cpu_percent','gpu_power_watts','gpu_memory_MiB'):
        values=[float(r[col]) for r in train if r[col]]
        result[col+'_sample_mean']=sum(values)/len(values) if values else None
    print(json.dumps(result))
