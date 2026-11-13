"""Summarize closed speed runs, without numerical equivalence checks."""
import csv,json
from pathlib import Path
base=Path('/lfshome/zixiao/model_v3_perf_20261112')
rows=[]
for label,name in (('baseline5090','baseline5090_4530313'),('no_recomputation','opt1_no_recompute_4530314')):
    root=base/name
    with (root/'baseline/losses.csv').open() as file:losses=list(csv.DictReader(file))
    with (root/'baseline_telemetry.csv').open() as file:telemetry=list(csv.DictReader(file))
    train=[row for row in telemetry if row['training_started']=='1']
    last=max(i for i,row in enumerate(train) if i==0 or row['losses_bytes']!=train[i-1]['losses_bytes'])
    train=train[:last+1]
    result=dict(name=label,job=name.rsplit('_',1)[1],updates=len(losses),
        samples_per_second=(int(losses[-1]['samples'])-int(losses[0]['samples']))/(float(losses[-1]['seconds'])-float(losses[0]['seconds'])))
    for field in ('main_cpu_percent','gpu_power_watts','gpu_memory_MiB'):
        values=[float(row[field]) for row in train if row[field]]
        result[field+'_mean']=sum(values)/len(values)
        if field=='gpu_memory_MiB':result[field+'_max']=max(values)
    rows.append(result)
output=dict(runs=rows,speedup=rows[1]['samples_per_second']/rows[0]['samples_per_second'],
            baseline_parent_status='FAILED_RESOURCE_GUARD_AFTER_1000_UPDATES',candidate_parent_status='COMPLETED_0_0',
            correctness_acceptance='FAIL_REJECTED',acceptance_job='4530319',
            parameter_relative_l2=0.0012234179502054808,parameter_relative_l2_limit=1e-5,
            violation_count=365,candidate_retained=False,
            same_gpu='GPU-c35f2434-9137-9723-1af5-dc69b6295243')
print(json.dumps(output,indent=2))
