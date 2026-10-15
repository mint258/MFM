"""Current combined status and curves, distinguishing acceptance from running."""
import csv,json,os,time,datetime,subprocess
from pathlib import Path
from prepare import ROOT,save,sha
from s_epoch_estimate_v1 import estimate_epochs

def joint_judgment(loss_results,probes):
    primary=[row for row in probes if row['included_in_primary_judgment']]
    assert len(loss_results)==3 and len(primary)==32
    # A known failure of either required criterion disproves sufficiency,
    # even if a different probe endpoint has an unavailable cell.
    if any(not row['both_below_2_percent'] for row in loss_results) or any(row['criterion_met'] is False for row in primary):
        return 'ONE_EPOCH_INSUFFICIENT_UNDER_PREDECLARED_RULE'
    if any(row['criterion_met'] is None for row in primary):
        return 'NOT_ESTABLISHED_DUE_TO_UNAVAILABLE_PROBE_CELLS'
    assert all(row['criterion_met'] is True for row in primary)
    return 'ONE_EPOCH_SUFFICIENT_UNDER_PREDECLARED_RULE'

def wait_for_actual_publication(owned,deadline):
    """Wait for the real Sonmi publisher when a new registered segment races us."""
    while True:
        publication=json.loads((ROOT/'formal_s/report_accounting_latest.json').read_text())
        assert publication['status']=='ACTUAL_SONMI_REGISTERED_S_PARENT_TIMING_PUBLISHED'
        assert publication['publisher_uid']==1278 and publication['publisher_hostname'].split('.')[0]=='sonmi'
        assert publication['publisher_source_sha256']==sha(ROOT/'scripts/s_report_accounting_publish_v1.py')
        age=time.time()-publication['timestamp']
        if -5<=age<=900 and set(owned)<=set(publication['parents']):return publication
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('ACTUAL_SONMI_PUBLICATION_NOT_FRESH_OR_MISSING_REGISTERED_PARENTS_AFTER_BOUNDED_WAIT')
        print(json.dumps({'status':'WAITING_FOR_REAL_SONMI_PUBLICATION','missing_registered_parents':sorted(set(owned)-set(publication['parents'])),'publication_age_seconds':age,'remaining_bounded_wait_seconds':remaining}),flush=True)
        time.sleep(min(30.,remaining))

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    os.environ['TZ']='Asia/Shanghai';time.tzset()
    publication_deadline=time.monotonic()+1200
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages
    output=ROOT/'reports/current_experiment';output.mkdir(exist_ok=True)
    a_path=ROOT/'reports/full_generation_summary.json'
    a=json.loads(a_path.read_text()) if a_path.exists() else None
    a_state=json.loads((ROOT/'reports/full_coordinator_v7_status.json').read_text())
    b_state=json.loads((ROOT/'formal_s/root_coordinator_v1_status.json').read_text())
    conditions={};curves={};table=[];epoch_timing={};discarded_tails=[];cuts={}
    for path in ROOT.glob('cuda_recovery_v*/continuation_gate.json'):
        gate=json.loads(path.read_text())
        assert gate['status']=='ROOT_REVIEWED_THIS_CUDA_FAILURE_CONTINUATION_ALLOWED'
        assert sha(gate['failed_summary']['path'])==gate['failed_summary']['sha256']
        assert sha(gate['checkpoint_reference']['path'])==gate['checkpoint_reference']['sha256']
        cuts['segment_'+gate['failed_job_id']]={'cutoff':gate['checkpoint_reference']['consumed_records'],
            'gate_path':str(path),'gate_sha256':sha(path),'checkpoint_reference':gate['checkpoint_reference']}
    for name in ['B1_seed0','B1_seed1','B3_seed0']:
        records=[];validations=[];summaries=[]
        folder=ROOT/'s_training'/name
        for segment in sorted(folder.glob('segment_*')):
            journal=segment/'metrics.jsonl'
            if journal.exists():
                discarded=[]
                for line in journal.read_text().splitlines():
                    row=json.loads(line)
                    if any(k.startswith('train/raw_') for k in row):
                        if segment.name in cuts and row['consumed_records']>cuts[segment.name]['cutoff']:discarded.append(row)
                        else:records.append(row)
                if discarded:
                    discarded_tails.append({'condition':name,'segment':segment.name,'excluded_logged_rows':len(discarded),
                        'last_abandoned_logged_records':discarded[-1]['consumed_records'],
                        'last_abandoned_logged_optimizer_updates':discarded[-1]['optimizer_updates'],
                        'original_journal_path':str(journal),'original_journal_sha256':sha(journal),**cuts[segment.name]})
            path=segment/'summary.json'
            if path.exists():
                value=json.loads(path.read_text());summaries.append(value);validations+=value.get('validation_history',[])
            live_roles={}
            for role in ['full','routine']:
                path=segment/('validation_'+role+'_complete.json')
                if path.exists():
                    value=json.loads(path.read_text())
                    assert value['status']=='VALIDATION_ROLE_COMPLETE'
                    live_roles.setdefault(value['consumed_training_records'],{})[role]=value['result']
            validations += [{'consumed_records':count,'values':values} for count,values in live_roles.items()]
        unique_validations={}
        for value in validations:
            count=value['consumed_records']
            destination=unique_validations.setdefault(count,{'consumed_records':count,'values':{}})
            for role,result in value['values'].items():
                previous=destination['values'].get(role)
                assert previous is None or previous==result,'Duplicate validation endpoint differs'
                destination['values'][role]=result
        validations=[unique_validations[count] for count in sorted(unique_validations)]
        records.sort(key=lambda r:r['consumed_records']);curves[name]=records
        last=max(summaries,key=lambda d:d.get('consumed_records',0)) if summaries else None
        conditions[name]={'actual_committed_records_latest_journal':records[-1]['consumed_records'] if records else 0,
            'actual_terminal_records':last.get('consumed_records') if last else None,
            'complete_epochs':last.get('completed_epochs',[]) if last else [],
            'status':last['status'] if last else b_state['conditions'][name]['state'],'validations':validations,
            'observed_loader_wait_fraction':records[-1].get('loader_wait_fraction') if records else None,
            'observed_records_per_second_including_startup':records[-1].get('segment_records_per_second') if records else None,
            'terminal_segment_hardware':[{'job_id':r['job_id'],'node':r['node'],'gpu_uuid':r['gpu_uuid'],'gpu_model':r['gpu_model'],
                'gpu_protection':r['gpu_protection'],'segment_wall_seconds':r['elapsed_seconds']} for r in summaries]}
        owned=[]
        for registration in (ROOT/'submission').glob('formal_s_'+name+'_*.json'):
            entry=json.loads(registration.read_text())
            if entry.get('job_id'):owned.append(entry['job_id'])
        if owned:
            publication=wait_for_actual_publication(owned,publication_deadline)

            raw='\n'.join('|'.join([job,'zixiao',publication['parents'][job]['start'],publication['parents'][job]['end'],str(publication['parents'][job]['elapsed_seconds'])]) for job in owned)
            intervals=[]
            for line in raw.splitlines():
                cols=line.split('|')
                if cols[0] not in owned:continue
                assert cols[1]=='zixiao'
                if cols[2] in ['Unknown','None']:continue
                begin=datetime.datetime.fromisoformat(cols[2]).timestamp()
                end=None if cols[3] in ['Unknown','None'] else datetime.datetime.fromisoformat(cols[3]).timestamp()
                intervals.append((begin,end,int(cols[4])))
            for epoch in range(1,(3 if name=='B3_seed0' else 1)+1):
                refs=list(folder.glob('segment_*/epoch_'+str(epoch)+'.json'))
                if not refs or not intervals:continue
                checkpoint=max(refs,key=lambda p:p.stat().st_mtime)
                ref=json.loads(checkpoint.read_text());assert ref['consumed_records']==11104772*epoch
                finish=checkpoint.stat().st_mtime
                start=min(i[0] for i in intervals)
                previous=epoch_timing.get(name,{}).get(str(epoch-1),{}).get('endpoint_timestamp',start)
                active=sum(max(0.,min(finish,e if e is not None else finish)-max(previous,b)) for b,e,_ in intervals if b<finish)
                epoch_timing.setdefault(name,{})[str(epoch)]={'epoch':epoch,'endpoint_timestamp':finish,
                    'calendar_wall_seconds_since_previous_endpoint':finish-previous,'active_allocation_seconds_including_startup_validation_checkpoints':active,
                    'checkpoint_reference_sha256':sha(checkpoint),'basis':'actual Slurm start/end intersected with actual endpoint-reference write timestamp'}
        for validation in validations:
            for role,values in validation['values'].items():
                table.append({'condition':name,'epoch':validation['consumed_records']/11104772,'role':role,
                    **values['raw_losses'],'local_rmse_A':values['geometry_local_pair_A_rmse'],
                    'element_accuracy':values['element_accuracy'],'bond_order_accuracy':values['bond_order_accuracy']})
    loss_results=[];probes=[];judgment='NOT_YET_EVALUABLE'
    all_training_complete=b_state['status']=='ALL_THREE_TRAINING_RUNS_COMPLETE_AWAITING_H0_PROBES'
    required=['B1_seed0_e1','B1_seed1_e1','B3_seed0_e0p25','B3_seed0_e0p5','B3_seed0_e1','B3_seed0_e2','B3_seed0_e3']
    probe_files=[ROOT/'probe_results_v2'/point/'receipt.json' for point in required]
    probes_closed=all(path.exists() and json.loads(path.read_text())['status']=='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED' for path in probe_files)
    all_probe_rows=[]
    for point,path in zip(required,probe_files):
        if path.exists():
            value=json.loads(path.read_text())
            assert value['status']=='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED'
            all_probe_rows += [{'checkpoint':point,**row} for row in value['aggregate']]
    if all_training_complete:
        final={}
        for name in conditions:
            values=conditions[name]['validations']
            last=max(values,key=lambda d:d['consumed_records']);assert 'full' in last['values']
            final[name]=last['values']['full']
        for task in ['element','distance','bond_order']:
            reference=final['B3_seed0']['raw_losses'][task]
            gaps={name:abs(final[name]['raw_losses'][task]-reference)/abs(reference) for name in ['B1_seed0','B1_seed1']}
            loss_results.append({'task':task,'relative_gaps':gaps,'both_below_2_percent':all(v<.02 for v in gaps.values())})
        if probes_closed:
            endpoints={point:json.loads(path.read_text()) for point,path in zip(required,probe_files)}
            lookup={point:{(r['dataset'],r['task']):r for r in value['aggregate']} for point,value in endpoints.items()}
            for key in lookup['B3_seed0_e3']:
                vals=[lookup[p][key]['primary_metric'] for p in ['B1_seed0_e1','B1_seed1_e1','B3_seed0_e3']]
                delta=abs((vals[0]+vals[1])/2-vals[2]) if all(v is not None for v in vals) else None
                spread=abs(vals[0]-vals[1]) if all(v is not None for v in vals) else None
                probes.append({'dataset':key[0],'task':key[1],'B1_seed0':vals[0],'B1_seed1':vals[1],'B3_epoch3':vals[2],
                    'B1_mean_vs_B3_difference':delta,'B1_two_seed_spread':spread,
                    'included_in_primary_judgment':lookup['B3_seed0_e3'][key]['included_in_primary_judgment'],
                    'criterion_met':delta<spread if delta is not None else None})
            judgment=joint_judgment(loss_results,probes)
    integer={}
    if all_training_complete:
        for validation in conditions['B3_seed0']['validations']:
            epoch=validation['consumed_records']/11104772
            if epoch in [1.,2.,3.] and 'full' in validation['values']:integer[int(epoch)]=validation['values']['full']['raw_losses']
    marginal_estimate=estimate_epochs(integer)
    estimated_epochs=marginal_estimate['estimated_epochs'];estimate_basis=marginal_estimate['basis']
    if (ROOT/'formal_s/scientific_stop.json').exists():judgment='GUIDE_STOP_BEFORE_FULL_EPOCH_COMPARISON'
    status={'status':'CURRENT_EXPERIMENT_STATUS_NOT_FULL_ACCEPTANCE','timestamp':time.time(),'job_id':os.environ['SLURM_JOB_ID'],
        'A_accepted':a_state['status']=='A_FULL_DATASET_AND_REPORT_ACCEPTED','A':a,'A_queue':a_state.get('queue'),
        'B_status':b_state['status'],'conditions':conditions,'one_epoch_judgment':judgment,
        'loss_comparisons':loss_results,'probe_comparisons':probes,'all_required_probes_closed':probes_closed,
        'epoch_wall_timing':epoch_timing,'estimated_epochs_for_sub2_percent_marginal_gain':estimated_epochs,'epoch_estimate_basis':estimate_basis,
        'protocol_resolution':json.loads((ROOT/'formal_s/protocol_resolution_v3.json').read_text()),
        'report_source_sha256':sha(__file__)}
    status['marginal_epoch_estimate']=marginal_estimate
    status['marginal_epoch_estimator_source_sha256']=sha(ROOT/'scripts/s_epoch_estimate_v1.py')
    status['abandoned_failed_tail_metrics_excluded_from_committed_training_curves']=discarded_tails
    status['failed_attempt_compute_cost_retained']=True
    status['downstream_policy']=json.loads((ROOT/'configs/s_probe_protocol_v2.json').read_text())
    status['downstream_policy_sha256']=sha(ROOT/'configs/s_probe_protocol_v2.json')
    status['explicit_frozen_reference_user_confirmation']=json.loads((ROOT/'formal_s/user_frozen_reference_confirmation_20261014_v2.json').read_text())
    status['formal_training_hardware']={'observed_gpu_models':sorted({r['gpu_model'] for value in conditions.values() for r in value['terminal_segment_hardware']}),
        'distinct_observed_training_gpu_uuids':sorted({r['gpu_uuid'] for value in conditions.values() for r in value['terminal_segment_hardware']}),
        'count_basis':'Unique physical GPU UUIDs in actual terminal formal segment receipts; no inference GPUs counted',
        'eligible_node_policy':['compute-0-20','compute-0-21','compute-0-22'],
        'per_training_job_requested_cpus':16,'per_training_job_declared_memory_GiB':64,
        'accounting_reference_sha256':sha(ROOT/'formal_s/report_accounting_latest.json')}
    status['epoch1_denoising_lookup_checks']=[]
    for name,value in conditions.items():
        endpoint=[r for r in value['validations'] if r['consumed_records']==11104772 and 'full' in r['values']]
        if endpoint:
            measured=endpoint[-1]['values']['full']['geometry_local_pair_A_rmse']
            status['epoch1_denoising_lookup_checks'].append({'condition':name,'FULL_local_pair_RMSE_A':measured,
                'historical_lookup_reference_A':.042,'strictly_better_than_lookup':measured<.042,
                'interpretation':'Investigate denoising head or noise settings before attributing this to data volume' if measured>=.042 else 'Epoch1 FULL local pair-distance RMSE below the declared historical lookup reference'})
    overlap_path=ROOT/'reports/s_probe_pretraining_overlap_v1.json'
    if overlap_path.exists():
        overlap=json.loads(overlap_path.read_text())
        assert overlap['status']=='FIVE_BENCHMARK_CONNECTIVITY_INCHIKEY14_OVERLAP_REPORTED'
        status['pretraining_overlap']=overlap;status['pretraining_overlap_reference_sha256']=sha(overlap_path)
    if status['A_accepted'] and all_training_complete and probes_closed and overlap_path.exists() and all('1' in epoch_timing.get(name,{}) for name in conditions):
        status['status']='FULL_COMPUTATIONS_AND_REPORT_GENERATED_AWAITING_REVIEW'
    save(output/'summary.json',status)
    if table:
        with (output/'validation_metrics.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    if probes:
        with (output/'checkpoint_probe_comparison.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(probes[0]));writer.writeheader();writer.writerows(probes)
    if all_probe_rows:
        fields=list(dict.fromkeys(key for row in all_probe_rows for key in row))
        with (output/'all_checkpoint_probe_metrics.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(all_probe_rows)
    fig,axes=plt.subplots(2,2,figsize=(10,7))
    for name,rows in curves.items():
        if not rows:continue
        x=[r['epoch'] for r in rows]
        for axis,task in zip(axes.ravel()[:3],['element','distance','bond_order']):
            axis.plot(x,[r.get('train/raw_'+task,np.nan) for r in rows],label=name);axis.set_title('TRAIN raw '+task);axis.set_xlabel('Committed TRAIN epochs')
        axes[1,1].plot(x,[r.get('train/geometry_local_pair_A_rmse',np.nan) for r in rows],label=name)
    axes[1,1].axhline(.141,color='gray',ls='--',label='Noisy reference0.141 A');axes[1,1].axhline(.042,color='black',ls=':',label='Historical lookup0.042 A')
    axes[1,1].set_title('TRAIN local pair-distance RMSE (A)');axes[1,1].set_xlabel('Committed TRAIN epochs')
    for axis in axes.ravel():axis.legend(fontsize=7);axis.grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'training_curves.png',dpi=180);fig.savefig(output/'training_curves.svg');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(10,7))
    for name in conditions:
        for role in ['full','routine']:
            rows=[row for row in table if row['condition']==name and row['role']==role]
            for axis,task in zip(axes.ravel()[:3],['element','distance','bond_order']):
                axis.plot([r['epoch'] for r in rows],[r[task] for r in rows],marker='.',label=name+' '+role)
                axis.set_title('Validation raw '+task);axis.set_xlabel('Committed TRAIN epochs')
            axes[1,1].plot([r['epoch'] for r in rows],[r['local_rmse_A'] for r in rows],marker='.',label=name+' '+role)
    axes[1,1].axhline(.141,color='gray',ls='--',label='Noisy reference0.141 A');axes[1,1].axhline(.042,color='black',ls=':',label='Historical lookup0.042 A')
    axes[1,1].set_title('Validation local pair-distance RMSE (A)');axes[1,1].set_xlabel('Committed TRAIN epochs')
    for axis in axes.ravel():axis.legend(fontsize=6);axis.grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'validation_curves.png',dpi=180);fig.savefig(output/'validation_curves.svg');plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(10,10))
    runtime_metrics=[('train/element_accuracy','TRAIN masked-element accuracy'),('train/bond_order_accuracy','TRAIN bond-order accuracy'),
        ('gradient_norm_before_clip','Gradient norm before clipping'),('segment_records_per_second','Records/s including segment startup'),
        ('gpu_peak_allocated_bytes','GPU peak allocated GiB'),('loader_wait_fraction','Loader wait fraction')]
    for name,rows in curves.items():
        if not rows:continue
        for axis,(key,title) in zip(axes.ravel(),runtime_metrics):
            axis.plot([r['epoch'] for r in rows],[r.get(key,np.nan)/(1<<30) if key=='gpu_peak_allocated_bytes' else r.get(key,np.nan) for r in rows],label=name)
            axis.set_title(title);axis.set_xlabel('Committed TRAIN epochs')
        axes[2,0].plot([r['epoch'] for r in rows],[r.get('gpu_peak_reserved_bytes',np.nan)/(1<<30) for r in rows],ls='--',label=name+' reserved')
    for axis in axes.ravel():axis.legend(fontsize=6);axis.grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'runtime_curves.png',dpi=180);fig.savefig(output/'runtime_curves.svg');plt.close(fig)
    full_denoise=[]
    for name,value in conditions.items():
        finals=[r for r in value['validations'] if r['consumed_records']>=11104772 and 'full' in r['values']]
        if finals:full_denoise.append(name+': '+str(finals[-1]['values']['full']['geometry_local_pair_A_rmse']))
    a_text=('accepted; success '+format(100*(1-a['failure_rate']),'.3f')+'%; median heavy RMSD '+format(a['rmsd_A_quantiles']['0.5'],'.3f')+' A; PM7 coverage '+format(100*a['pm7_coverage_fraction'],'.3f')+'%') if status['A_accepted'] and a else 'running; '+str(a_state.get('queue',{}).get('molecules_including_pilot',0))+' molecules closed'
    evidence=''
    if loss_results:
        evidence='; maximum FULL relative loss gap '+format(100*max(gap for row in loss_results for gap in row['relative_gaps'].values()),'.3f')+'%'
    if probes:evidence+='; '+str(sum(row['criterion_met'] is True for row in probes if row['included_in_primary_judgment']))+'/32 primary probe tasks meet the paired seed-spread criterion (QM9 A/B/C auxiliary)'
    denoise_text='; '.join(row['condition']+' epoch1 '+format(row['FULL_local_pair_RMSE_A'],'.6f')+' A' for row in status['epoch1_denoising_lookup_checks'])
    if status['epoch1_denoising_lookup_checks']:
        denoise_text+='; '+('all at or above0.042 A; review denoising head/noise settings' if all(not row['strictly_better_than_lookup'] for row in status['epoch1_denoising_lookup_checks']) else 'see individual epoch1 lookup checks')
    decision_text='Choose denoising-head/noise revision before planning later eight-condition/data-size studies.' if status['status']=='FULL_COMPUTATIONS_AND_REPORT_GENERATED_AWAITING_REVIEW' else 'required runs/checks continue; no additional authorization requested'
    first=['1. One epoch sufficient: '+judgment+evidence,
        '2. Denoiser vs lookup0.042 A: '+(denoise_text if denoise_text else 'No epoch1 FULL endpoint yet; no claim.'),
        '3. Single-epoch wall time: '+('; '.join(name+' '+str(round(value['1']['active_allocation_seconds_including_startup_validation_checkpoints']/3600,3))+' active hours' for name,value in epoch_timing.items() if '1' in value) if epoch_timing else 'not measured through a complete epoch yet'),
        '4. S-prime generation: '+a_text,
        '5. User decisions: '+('guide scientific stop requires a decision on continuation' if judgment=='GUIDE_STOP_BEFORE_FULL_EPOCH_COMPARISON' else decision_text)]
    import textwrap
    with PdfPages(output/'report.pdf') as pdf:
        page=plt.figure(figsize=(8.27,11.69));y=.91
        for item in first:
            lines=textwrap.wrap(item,82)
            page.text(.07,y,'\n'.join(lines),fontsize=11,va='top');y-=.024*len(lines)+.07
        pdf.savefig(page);plt.close(page)
        page=plt.figure(figsize=(8.27,11.69));axis=page.add_axes([.04,.17,.92,.65]);axis.imshow(plt.imread(output/'validation_curves.png'));axis.axis('off')
        page.text(.05,.91,'FULL and ROUTINE raw losses and local pair-distance RMSE.',fontsize=10)
        pdf.savefig(page);plt.close(page)
        page=plt.figure(figsize=(8.27,11.69));axis=page.add_axes([.04,.17,.92,.65]);axis.imshow(plt.imread(output/'training_curves.png'));axis.axis('off')
        page.text(.05,.91,'Actual current evidence; epoch convergence requires the complete prescribed runs.',fontsize=10)
        pdf.savefig(page);plt.close(page)
        page=plt.figure(figsize=(8.27,11.69));axis=page.add_axes([.04,.10,.92,.78]);axis.imshow(plt.imread(output/'runtime_curves.png'));axis.axis('off')
        page.text(.05,.93,'Actual accuracy, gradients, throughput, GPU memory and loader waits.',fontsize=10)
        pdf.savefig(page);plt.close(page)
        page=plt.figure(figsize=(8.27,11.69));page.text(.05,.94,'Measured epoch cost and marginal-gain estimate',fontsize=12)
        cost_rows=[]
        for name,values in epoch_timing.items():
            for epoch,row in sorted(values.items(),key=lambda item:int(item[0])):
                active=row['active_allocation_seconds_including_startup_validation_checkpoints'];calendar=row['calendar_wall_seconds_since_previous_endpoint']
                cost_rows.append([name,epoch,format(active/3600,'.3f'),format(calendar/3600,'.3f'),format(11104772/active,'.1f')])
        if cost_rows:
            axis=page.add_axes([.06,.66,.88,.22]);axis.axis('off');display=axis.table(cellText=cost_rows,colLabels=['Condition','Epoch','Active h','Calendar h','Records/s'],loc='upper center');display.auto_set_font_size(False);display.set_fontsize(8);display.scale(1,1.5)
        hardware='Observed formal training hardware: '+', '.join(status['formal_training_hardware']['observed_gpu_models'])+'; '+str(len(status['formal_training_hardware']['distinct_observed_training_gpu_uuids']))+' distinct training GPU UUIDs. Each job16 CPU/64 GiB.'
        page.text(.06,.62,'\n'.join(textwrap.wrap(hardware,100)),fontsize=8,va='top')
        page.text(.06,.54,'B3 S-curve estimate: '+(str(estimated_epochs) if estimated_epochs is not None else 'not identifiable')+'; lower bound: '+str(marginal_estimate['lower_bound_epochs']),fontsize=10)
        page.text(.06,.50,'\n'.join(textwrap.wrap(estimate_basis,95)),fontsize=9,va='top')
        page.text(.06,.34,'\n'.join(textwrap.wrap(marginal_estimate['scope'],100)),fontsize=8,va='top')
        page.text(.06,.27,'Active cost includes startup, validation and checkpointing; calendar time also includes scheduling gaps.',fontsize=8)
        page.text(.06,.23,'Per-task losses, observed gains and fit diagnostics are in summary.json/marginal_epoch_estimate.',fontsize=8)
        pdf.savefig(page);plt.close(page)
        if probes:
            for offset in range(0,len(probes),18):
                batch=probes[offset:offset+18]
                page=plt.figure(figsize=(8.27,11.69));axis=page.add_axes([.04,.12,.92,.76]);axis.axis('off')
                rows=[[row['dataset']+' / '+row['task']+(' (aux)' if not row['included_in_primary_judgment'] else ''),*[(format(row[key],'.5g') if row[key] is not None else 'unavailable') for key in ['B1_seed0','B1_seed1','B3_epoch3','B1_mean_vs_B3_difference','B1_two_seed_spread']],str(row['criterion_met'])] for row in batch]
                display=axis.table(cellText=rows,colLabels=['Dataset / task','B1 seed0','B1 seed1','B3 e3','Difference','Seed spread','Pass'],loc='upper center',colWidths=[.34,.11,.11,.11,.11,.11,.10])
                display.auto_set_font_size(False);display.set_fontsize(6);display.scale(1,1.6)
                page.text(.05,.93,'Frozen H0 linear probes: final checkpoint comparison.',fontsize=11)
                page.text(.05,.08,'Graph tasks: MAE in original units. Atom tasks: molecule hit@1. No overlap deletion.',fontsize=8)
                pdf.savefig(page);plt.close(page)
    print(json.dumps({'status':status['status'],'A_accepted':status['A_accepted'],'B_status':status['B_status'],'judgment':judgment}),flush=True)

if __name__=='__main__':main()
