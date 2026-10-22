"""CPU report of actual sampled TRAIN losses; distinct from FULL validation metrics."""
import argparse,csv,hashlib,json,math,os,socket
from pathlib import Path
from stage3_gate_v4 import query_parents
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
def ref(p):
    p=Path(p);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phases',nargs='+',required=True);ap.add_argument('--parent-snapshot',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]]
    assert a.output_dir.is_absolute() and a.output_dir.is_relative_to(R/'reports') and not a.output_dir.exists()
    inputs=[ref(a.parent_snapshot),ref(__file__)];ledger={};curves={};configs={};flat=[]
    binding=R/'configs/D3_source_binding_v4.json'
    for row in json.loads(binding.read_text())['files']:assert ref(row['path'])['sha256']==row['sha256']
    inputs.append(ref(binding))
    for phase in a.phases:
        cp=R/'control'/phase;st=json.loads((cp/'status.json').read_text());assert st['status'] in ['D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE','D3_MESSAGE_LAYER_CAPABILITY_FAILED']
        for key,job in json.loads((cp/'jobs.json').read_text()).items():assert key not in ledger;ledger[key]=job
    actual=query_parents({job['job_id'] for job in ledger.values()},a.parent_snapshot)
    for key,job in ledger.items():
        cfgp=Path(job['configuration']);assert ref(cfgp)['sha256']==job['configuration_sha256'];cfg=json.loads(cfgp.read_text());configs[key]=cfg
        folder=R/'diagnostics'/key/('job_'+job['job_id']);rp=folder/'result.json';result=json.loads(rp.read_text())
        assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000 and result['runtime']['job_id']==job['job_id'] and result['configuration_sha256']==job['configuration_sha256']
        journal=folder/'metrics.jsonl';rows=[json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
        samples=[row for row in rows if 'optimizer_update' in row]
        assert [row['optimizer_update'] for row in samples]==list(range(32,4001,32)),key
        for row in samples:
            for name,value in row.items():
                if name.startswith('train_raw/') or name in ['train_total_loss','lr','gradient_norm_before_clip']:assert isinstance(value,(int,float)) and math.isfinite(value)
            flat.append(dict(condition=cfg['condition'],seed=cfg['seed'],job_id=job['job_id'],**row))
        curves[key]=samples;inputs.extend([ref(cfgp),ref(rp),ref(journal)])
    a.output_dir.mkdir(parents=True);columns=list(dict.fromkeys(k for row in flat for k in row))
    with (a.output_dir/'D3_TRAIN_batch_snapshots.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(flat)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    groups=list(dict.fromkeys(configs[key]['condition'] for key in ledger));colors={g:plt.get_cmap('tab10')(i%10) for i,g in enumerate(groups)}
    fig,axes=plt.subplots(2,3,figsize=(13,8.4),layout='constrained')
    specs=[('train_raw/denoise_eps_mse','TRAIN normalized noise MSE','denoise_eps_mse',True),
        ('train_raw/distance','TRAIN legacy log-Morse distance loss','distance',True),
        ('train_raw/element','TRAIN smoothed element loss (original objective)','element',True),
        ('train_raw/bond_order','TRAIN bond-order loss (original objective)','bond_order',True),
        ('lr','Learning rate',None,False),('gradient_norm_before_clip','Pre-clip gradient norm: all parameters',None,True)]
    for ax,(metric,title,task,log) in zip(axes.ravel(),specs):
        for group in groups:
            cc=[configs[group+'_seed'+str(s)] for s in [0,1]]
            if task and any(task not in (c['loss_policy'].get('structural_tasks') or ['element',c['geometry_task'],'bond_order']) for c in cc):continue
            paired=[{row['optimizer_update']:row[metric] for row in curves[group+'_seed'+str(s)] if metric in row} for s in [0,1]]
            common=sorted(set(paired[0])&set(paired[1]));assert len(common) in [0,125]
            if not common:continue
            values=[[p[t] for p in paired] for t in common];assert all(all(math.isfinite(v) and (v>0 if log else True) for v in vv) for vv in values)
            ax.plot(common,[math.fsum(v)/2 for v in values],color=colors[group],label=group,linewidth=1.2)
            ax.fill_between(common,[min(v) for v in values],[max(v) for v in values],color=colors[group],alpha=.13)
        if metric=='gradient_norm_before_clip':ax.axhline(1,color='black',linestyle=':',label='Clip threshold 1')
        if log:ax.set_yscale('log')
        ax.set_title(title);ax.set_xlabel('Optimizer updates');ax.grid(alpha=.2)
    # Build the legend from groups, including legacy-only groups absent from the noise panel.
    from matplotlib.lines import Line2D
    handles=[Line2D([0],[0],color=colors[g],label=g) for g in groups]
    fig.legend(handles=handles,loc='outside lower center',ncol=min(5,len(groups)),fontsize=8)
    fig.suptitle('S denoising repair: TRAIN batch snapshots, distinct from FULL2000 validation\nOne recorded batch every 32 updates; two-seed mean and min-max; no temporal smoothing.',fontsize=11)
    fig.savefig(a.output_dir/'D3_TRAIN_loss_curves.pdf');fig.savefig(a.output_dir/'D3_TRAIN_loss_curves.png',dpi=140);plt.close(fig)
    doc=dict(status='ACTUAL_CLOSED_D3_TRAIN_SNAPSHOTS_RENDERED',job_id=os.environ['SLURM_JOB_ID'],phases=a.phases,
        sampling='Exactly 125 single-batch snapshots per run at updates32,64,...,4000, not averages of the intervening 32 batches.',
        plotting='Two-seed mean/min-max at matched update. Inactive task losses omitted. Legacy distance and noise losses use separate axes.',
        clip_scope='Plotted pre-clip norms are sampled; reported clipping fraction in result.json covers all4000 updates.',
        source_references=inputs,actual_parents=actual,artifacts=[ref(p) for p in sorted(a.output_dir.iterdir())])
    with (a.output_dir/'training_render_receipt.json').open('x') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=doc['status'],output=str(a.output_dir))))
if __name__=='__main__':main()
