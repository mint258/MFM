"""Apply the registered quality and fleet-throughput rules to closed evidence."""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from phychem_mfm.phase1.p_recipe import paired_decision

REPO=Path(__file__).resolve().parents[2]
PROTOCOL=REPO/'configs/p_recipe/precision_20261115/protocol.json'


def paired_quality(candidate,baseline):
    results={}
    for readout in ('R3','R1'):
        a,b=candidate[readout],baseline[readout]
        if a['included_tasks']!=b['included_tasks']:raise ValueError('Scoring task populations differ')
        ab,bb=a['paired_bootstrap'],b['paired_bootstrap']
        if any(ab[key]!=bb[key] for key in ('groups','seed','samples','confidence')):
            raise ValueError('Molecular bootstrap draws differ')
        if ab['seed']!=20261025 or ab['samples']!=1000:raise ValueError('Wrong P taskbook bootstrap protocol')
        if any(value is None for value in ab['values']+bb['values']):raise ValueError('Undefined bootstrap sample')
        results[readout]=paired_decision(a['mean_normalized_improvement'],b['mean_normalized_improvement'],ab['values'],bb['values'])
    return results


def select(speeds,qualified,protocol):
    weights=protocol['hardware_expected']
    totals={mode:sum(weights[card]*speeds[(card,mode,32)] for card in weights) for mode in qualified}
    if not totals:raise ValueError('No qualified scheme')
    best=max(totals.values())
    candidates={mode for mode,value in totals.items() if best-value<=protocol['higher_precision_tolerance']*best}
    chosen=next(mode for mode in ('fp32','tf32_islands','bf16_islands') if mode in candidates)
    return dict(chosen=chosen,expected_aggregate_samples_per_second=totals,
        maximum_aggregate_samples_per_second={mode:2*value for mode,value in totals.items()},
        tie_rule='Within 10% of the fastest qualified fleet throughput, prefer FP32 > TF32 > BF16')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--candidate',action='append',nargs=2,metavar=('MODE','SCORES'),required=True)
    p.add_argument('--speed-root',action='append',required=True);p.add_argument('--finite-quality',action='append',default=[]);p.add_argument('--output',required=True)
    a=p.parse_args();baseline=json.loads(Path(a.baseline).read_text());protocol=json.loads(PROTOCOL.read_text())
    quality={mode:paired_quality(json.loads(Path(path).read_text()),baseline) for mode,path in a.candidate}
    # A finite, complete 3M training/evaluation closure is required separately;
    # the caller supplies only arms whose raw histories have no divergence.
    qualified=['fp32']+[mode for mode in quality if mode in a.finite_quality and quality[mode]['R3']['verdict']!='loss']
    speeds={}
    for root in a.speed_root:
        for path in Path(root).glob('**/benchmark.json'):
            record=json.loads(path.read_text());card=next((name for name in protocol['hardware_expected'] if name in record['gpu']),None)
            if card is None:continue
            key=(card,record['precision'],record['batch_size'])
            if key in speeds:raise ValueError('Multiple closed benchmarks for '+str(key)+'; explicitly select the controlled run')
            if record['measured_updates']!=1000 or record['updates']!=1100:raise ValueError('Incomplete speed protocol')
            speeds[key]=record['samples_per_second']
    required={(card,mode,batch) for card in protocol['hardware_expected'] for mode in protocol['modes'] for batch in (32,128)}
    missing=sorted(required-set(speeds))
    result=dict(quality=quality,qualified=qualified,missing_speeds=missing)
    if missing:result['status']='WAITING_FOR_CLOSED_SPEED_GRID'
    else:result.update(select(speeds,qualified,protocol),status='COMPLETE')
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
