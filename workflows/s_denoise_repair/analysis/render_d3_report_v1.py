"""Render actual complete/partial D3 curves; never upgrade partial results."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def mean(values):return math.fsum(values)/len(values)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phases',nargs='+',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--gate',type=Path)
    parser.add_argument('--require-complete',action='store_true')
    args=parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    assert args.output_dir.is_absolute() and args.output_dir.is_relative_to(ROOT/'reports')
    binding=json.loads((ROOT/'configs/D3_source_binding_v4.json').read_text())
    for item in binding['files']:assert sha(item['path'])==item['sha256']
    ledger={}
    for phase in args.phases:
        control=ROOT/'control'/phase
        status=json.loads((control/'status.json').read_text())
        if args.require_complete:assert status['status']=='D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE'
        for key,value in json.loads((control/'jobs.json').read_text()).items():
            assert key not in ledger,'Duplicate condition identity'
            ledger[key]=value
    parent_text=subprocess.check_output(['sacct','-X','-j',','.join(v['job_id'] for v in ledger.values()),
        '-n','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],text=True,stdin=subprocess.DEVNULL,timeout=60)
    parents={row[0]:row[1:] for row in (line.split('|') for line in parent_text.splitlines()) if row[0] in {v['job_id'] for v in ledger.values()}}
    rows,curves,inputs=[],{},[]
    for key,entry in ledger.items():
        cfg_path=Path(entry['configuration']);assert sha(cfg_path)==entry['configuration_sha256']
        cfg=json.loads(cfg_path.read_text());job=entry['job_id']
        folder=ROOT/'diagnostics'/key/('job_'+job)
        curve_path=folder/'curve.json'
        if not curve_path.exists():
            assert not args.require_complete;continue
        curve=json.loads(curve_path.read_text());inputs.append(dict(path=str(curve_path),sha256=sha(curve_path)))
        curves[key]=curve
        final_path=folder/'result.json'
        actual=parents.get(job,['UNKNOWN','','0','0'])
        complete=final_path.exists() and actual[:2]==['COMPLETED','0:0']
        result=json.loads(final_path.read_text()) if complete else None
        if result:
            assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000
            assert result['configuration_sha256']==entry['configuration_sha256']
            inputs.append(dict(path=str(final_path),sha256=sha(final_path)))
        elif args.require_complete:raise ValueError('Condition incomplete: '+key)
        last=curve[-1]
        row=dict(condition=cfg['condition'],seed=cfg['seed'],job_id=job,actual_parent_state=actual[0],
            status='COMPLETE' if complete else 'PARTIAL_NOT_ACCEPTED',optimizer_update=last['optimizer_update'],
            LR=cfg['optimizer']['lr'],message_layers=cfg['model']['head'].get('geometry_message_layers',0),
            local_rmse_A=last['local_rmse_A'],bond_rmse_A=last['bond_rmse_A'],noise_mse_normalized=last['noise_mse_normalized'],
            masked_element_accuracy=last['masked_element_accuracy'],masked_element_nll=last['masked_element_nll'],
            bond_order_accuracy=last['bond_order_accuracy'])
        for k,v in enumerate(last['bond_order_recall']):row['bond_recall_class_'+str(k)]=v
        if result:
            row.update(records_per_second=result['training_records_per_second'],
                GPU_model=result['runtime']['gpu_model'],peak_allocated_MiB=result['gpu_peak_allocated_bytes']/2**20,
                peak_reserved_MiB=result['gpu_peak_reserved_bytes']/2**20,clip_trigger_fraction=result['clip_trigger_fraction'],
                allocated_GPU_hours=int(actual[2])/3600,allocated_CPU_core_hours=int(actual[2])*int(actual[3])/3600)
            gs=result['final_gradient_rows']; assert len(gs)==20
            for task in ['element',cfg['geometry_task'],'bond_order']:
                row['gradient_fraction_'+task]=mean([x['diagnostics']['fractions_of_sum_of_norms'][task] for x in gs])
        rows.append(row)
    gate=json.loads(args.gate.read_text()) if args.gate else None
    lookup=None
    lookup_ref=ROOT/'reports/lookup_latest.json'
    if lookup_ref.exists():
        ref=json.loads(lookup_ref.read_text());assert sha(ref['path'])==ref['sha256']
        lookup=json.loads(Path(ref['path']).read_text());inputs.append(ref)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with (args.output_dir/'D3_conditions.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    report=dict(status='D3_COMPLETE_MEASUREMENTS' if all(r['status']=='COMPLETE' for r in rows) and args.require_complete else 'D3_PARTIAL_NOT_ACCEPTED',
        rows=rows,scientific_inputs=inputs,actual_parent_raw=parent_text,guide_sha256=sha(ROOT/'user_repair_guide.md'),
        plotting='Each solid line is the two-seed mean. Shading is min-to-max across exactly two seeds, not a confidence interval.',
        lookup=lookup,gate=gate,full_training_results_present=False)
    save(args.output_dir/'measurements.json',report)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    groups=list(dict.fromkeys(row['condition'] for row in rows))
    color={g:plt.get_cmap('tab10')(i%10) for i,g in enumerate(groups)}
    fig,axes=plt.subplots(2,3,figsize=(13,8.4),layout='constrained')
    specs=[('local_rmse_A','Local pair-distance RMSE (A)',True),('bond_rmse_A','Bond-distance RMSE (A)',True),
        ('noise_mse_normalized','Normalized noise MSE',True),('masked_element_accuracy','Masked element accuracy',False),
        ('masked_element_nll','Masked element NLL, T=1, unsmoothed',True),('bond_order_accuracy','Bond-order accuracy',False)]
    for axis,(metric,title,log) in zip(axes.ravel(),specs):
        for group in groups:
            paired=[curves.get(group+'_seed'+str(seed),[]) for seed in [0,1]]
            maps=[{r['optimizer_update']:r[metric] for r in curve} for curve in paired]
            common=sorted(set(maps[0])&set(maps[1]))
            if common:
                values=[[maps[s][x] for s in [0,1]] for x in common]
                axis.plot(common,[mean(v) for v in values],color=color[group],label=group)
                axis.fill_between(common,[min(v) for v in values],[max(v) for v in values],color=color[group],alpha=.14)
            for seed,mapping in enumerate(maps):
                tail=sorted(set(mapping)-set(common))
                if tail:axis.plot(tail,[mapping[x] for x in tail],linestyle=':',color=color[group],alpha=.6,
                    label=group+' s'+str(seed)+' (unpaired)')
        if metric=='local_rmse_A':
            axis.axhline(.042,color='gray',linestyle=':',label='Historical 0.042 A')
            if lookup:axis.axhline(lookup['metrics']['D3_FULL2000']['lookup_rmse_A'],color='black',linestyle='--',label='New TRAIN lookup / FULL2000')
        if log:axis.set_yscale('log')
        axis.set_title(title);axis.set_xlabel('Optimizer updates');axis.grid(alpha=.2)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=min(5,len(labels)),fontsize=8)
    fig.suptitle('S denoising repair: D3 fixed-step controls'+(' - COMPLETE' if args.require_complete else ' - PARTIAL, NOT ACCEPTED'),fontsize=14)
    fig.savefig(args.output_dir/'D3_curves.pdf');fig.savefig(args.output_dir/'D3_curves.png',dpi=140);plt.close(fig)
    table=['| Group | Seed | Updates | Local RMSE (A) | Bond RMSE (A) | Noise MSE | Masked acc. | Bond acc. | Status |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in rows:
        table.append('| '+f"{row['condition']} | {row['seed']} | {row['optimizer_update']} | {row['local_rmse_A']:.6f} | {row['bond_rmse_A']:.6f} | {row['noise_mse_normalized']:.6f} | {row['masked_element_accuracy']:.6f} | {row['bond_order_accuracy']:.6f} | {row['status']} |")
    (args.output_dir/'D3_table.md').write_text('\n'.join(table)+'\n')
    print(json.dumps(dict(status=report['status'],conditions=len(rows),output=str(args.output_dir))))


if __name__=='__main__':main()
