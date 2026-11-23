"""Render closed F-table observations; no fitting, resampling or new statistics."""
import argparse,csv
from pathlib import Path

TASKS=('qm9.U0_atom','qm9.homo','exp.LogD','exp.LogS')
TITLES={'qm9.U0_atom':'QM9: U0 per atom','qm9.homo':'QM9: HOMO','exp.LogD':'ExpansionRx: LogD','exp.LogS':'ExpansionRx: LogS'}
POINT='scratch_improvement_seed_mean'
SPREAD='scratch_improvement_seed_std'

def render(table,output_directory):
    with Path(table).open() as stream:rows=list(csv.DictReader(stream))
    index={}
    for row in rows:
        key=(row['condition'],row['task'])
        if key in index:raise ValueError('Duplicate closed F-table key')
        index[key]=row
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'P_F_T2_20261123'})
    fig,axes=plt.subplots(2,2,figsize=(12.8,8.2),sharex=True)
    handles=[];labels=[];used=[]
    for ax,task in zip(axes.flat,TASKS):
        for mode,colour,marker,style,name in [
            ('full','#1764ab','o','-','Full: 3 fine-tuning seeds'),
            ('frozen','#d77913','D','--','Frozen: original readout seed 0'),
            ('top2','#8655a4','s','none','Top2: 3 fine-tuning seeds; endpoints')]:
            budgets=(1,9) if mode=='top2' else (1,3,6,9)
            selected=[index[(f'{mode}_T2_{n}M',task)] for n in budgets]
            expected=1 if mode=='frozen' else 3
            if any(int(row['seed_count'])!=expected or row['point_normalization']!='shared_three_seed_scratch_mean_mae' for row in selected):
                raise ValueError('Closed observation protocol differs')
            values=[float(row[POINT]) for row in selected]
            spread=None if mode=='frozen' else [float(row[SPREAD]) for row in selected]
            handle=ax.errorbar(budgets,values,yerr=spread,color=colour,marker=marker,
                               linestyle=style,linewidth=1.6,markersize=5,capsize=3)
            if task==TASKS[0]:handles.append(handle);labels.append(name)
            used.extend({'condition':row['condition'],'task':task,'point':row[POINT],'seed_std':row[SPREAD],'seed_count':row['seed_count']} for row in selected)
        ax.axhline(0,color='#68727c',linewidth=.9,linestyle=':',zorder=0)
        ax.set_title(TITLES[task],loc='left',fontweight='bold')
        ax.set_xticks([1,3,6,9]);ax.set_xlim(.6,9.4)
        ax.grid(axis='y',alpha=.18)
        ax.set_ylabel('Improvement vs shared scratch mean MAE')
        ax.set_xlabel('Samples at checkpoint in the original T2 9M run (millions)')
    fig.suptitle('Frozen and fine-tuned observations along the T2 9M trajectory',fontsize=16,y=.985)
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.952),ncol=3,frameon=False,fontsize=9)
    fig.subplots_adjust(left=.075,right=.985,bottom=.16,top=.865,wspace=.24,hspace=.34)
    fig.text(.075,.090,'Error bars: mean +/- 1 SD across fine-tuning seeds 0,1,2; not confidence intervals. Pretraining seed 0 is fixed.',fontsize=9)
    fig.text(.075,.060,'Four registered tasks; only 1/3/6/9M observations. Lines are guides; top2 has only 1M and 9M observations.',fontsize=9)
    fig.text(.075,.030,'Frozen: original 30-epoch constant-lr R3. Full/top2: registered 50-epoch cosine protocol. Source: closed F.csv.',fontsize=9)
    output_directory=Path(output_directory);output_directory.mkdir(parents=True,exist_ok=True)
    png=output_directory/'F_T2_full_frozen_trajectories.png'
    svg=output_directory/'F_T2_full_frozen_trajectories.svg'
    fig.savefig(png,dpi=160);fig.savefig(svg,metadata={'Date':None});plt.close(fig)
    return dict(source=str(table),source_rows=len(rows),display_rows=len(used),displayed_observations=used,
                figures=[str(png),str(svg)],new_model_fits=0,new_bootstrap_draws=0,
                uncertainty='Existing fine-tuning seed SD; not an ensemble bootstrap confidence interval')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--table',type=Path,required=True);parser.add_argument('--output-directory',type=Path,required=True)
    args=parser.parse_args();import json;print(json.dumps(render(args.table,args.output_directory)))
