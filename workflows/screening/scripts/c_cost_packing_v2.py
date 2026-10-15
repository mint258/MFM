"""C1 full scenario matrix and C2 whole-molecule cost packing, analysis only."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,heapq,itertools,json,math,multiprocessing,os,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
CD={'pm7_water','pm7_octanol','pm7_cation','pm7_anion'}
def save(path,v):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.pending');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def init(barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);barrier.wait(timeout=120)
def scan(path):
    import pyarrow.parquet as pq
    receipt=json.loads(Path(path).read_text());rows=pq.read_table(receipt['parquet']['path'],columns=['record_id','molecule_id','size_stratum','natoms','heavy_atoms','task','status','elapsed_seconds','details_json'],use_threads=False).to_pylist();out=[]
    for r in rows:
        detail=json.loads(r.pop('details_json'));r['job_id']=str(detail.get('job_id',receipt.get('job_id')));v=detail.get('values',{});getter=v.get('mulliken_overlap_qc',{}).get('elapsed_seconds',0)
        r['getter_seconds']=getter if finite(getter) else 0.;r['service_seconds']=(r['elapsed_seconds'] or 0)+r['getter_seconds'];r['qc_codes']=detail.get('qc_codes',[]);r['diagnostic_lines']=detail.get('diagnostic_lines',[])
        out.append(r)
    return out,os.getpid()
def stats(values):
    import numpy as np
    a=np.asarray([v for v in values if finite(v)],float)
    if not len(a):return {'n':0}
    return {'n':len(a),'min':float(a.min()),'p50':float(np.quantile(a,.5)),'p90':float(np.quantile(a,.9)),'p99':float(np.quantile(a,.99)),'max':float(a.max()),'mean':float(a.mean())}
def bins(n):
    return '0_10' if n<=10 else '11_20' if n<=20 else '21_30' if n<=30 else '31_50' if n<=50 else '51_75' if n<=75 else '76_100' if n<=100 else 'above_100'
def weighted_fresh(mode,task,plan):
    import pyarrow.parquet as pq
    samplepath=ROOT/'b_quantum/plan'/('hessian_100.parquet' if mode=='hessian' else 'esp_200.parquet');sample={r['record_id']:r for r in pq.read_table(samplepath).to_pylist()}
    dirs=list((ROOT/'b_quantum'/mode).glob('job_*'));refs=sorted(dirs[0].glob('records/*/receipt.json')) if len(dirs)==1 else []
    expected=100 if mode=='hessian' else 200
    if len(refs)!=expected:raise RuntimeError('FRESH_COST_NOT_CLOSED_'+mode)
    if mode=='hessian':
        weights={(g['group'],w['stratum'][0],w['stratum'][1]):w['weight'] for g in plan['hessian']['sampling_weights'] for w in g['strata']}
    else:weights={(w['stratum'][0],w['stratum'][1]):w['weight'] for w in plan['ESP']['sampling_weights']}
    totals=collections.defaultdict(lambda:collections.defaultdict(float));details=[]
    for path in refs:
        receipt=json.loads(path.read_text());row=sample[receipt['record_id']]
        if mode=='hessian':key=(row['original_imaginary_group'],row['size_stratum'],row['original_frequency_band'])
        else:key=(row['esp_failure_reason'],row['size_stratum'])
        w=weights[key]
        for r in pq.read_table(receipt['parquet']['path'],columns=['task','status','elapsed_seconds','details_json'],use_threads=False).to_pylist():
            if r['task']!=task:continue
            d=json.loads(r['details_json']);elapsed=d.get('elapsed_seconds',0) or 0;getter=d.get('values',{}).get('mulliken_overlap_qc',{}).get('elapsed_seconds',0) or 0
            totals[row['size_stratum']]['weighted_service']+=w*(elapsed+getter);totals[row['size_stratum']]['weight']+=w;totals[row['size_stratum']]['sample']+=1;totals[row['size_stratum']]['weighted_timeouts']+=w*(r['status']=='TIMEOUT')
            details.append({'record_id':row['record_id'],'size_stratum':row['size_stratum'],'weight':w,'status':r['status'],'service_seconds':elapsed+getter})
    return {s:{'mean_service_seconds':v['weighted_service']/v['weight'],'weighted_population':v['weight'],'samples':int(v['sample']),'timeout_fraction':v['weighted_timeouts']/v['weight']} for s,v in totals.items()},details

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=32);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_NO_LMDB');return
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import numpy as np,pyarrow as pa,pyarrow.parquet as pq,duckdb
    pa.set_cpu_count(a.workers);pa.set_io_thread_count(8);start=time.monotonic();out=ROOT/'c_engineering/cost_packing_v2';out.mkdir(parents=True,exist_ok=False)
    panel=pq.read_table(OLD/'wp4_native_panel/pilot_panel.parquet').to_pylist();byid={r['record_id']:r for r in panel}
    paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'))
    if len(paths)!=1441 or len(panel)!=10020:raise ValueError('MANIFEST_NATIVE_COUNT_MISMATCH')
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=init,initargs=(barrier,)) as pool:results=list(pool.map(scan,[str(p) for p in paths],chunksize=1))
    calls=[r for rows,pid in results for r in rows]
    if len(calls)!=131701:raise ValueError('MANIFEST_NATIVE_OUTCOME_MISMATCH')
    old_report=json.loads((OLD/'reports/wp4_final_pilot_accounted/wp4_pilot_report.json').read_text());factor=old_report['projections']['pilot_allocated_to_observed_service_factor']
    ratios={s:v['service_without_to_with_ratio']['mean'] for s,v in old_report['projections']['POLAR_paired_probe_by_stratum'].items()}
    population=json.loads((ROOT/'a_retained/population_by_stratum.json').read_text());plan=json.loads((ROOT/'b_quantum/plan/manifest.json').read_text())
    hess,hess_calls=weighted_fresh('hessian','b3_xtb_hess',plan);ohess,ohess_calls=weighted_fresh('hessian','b3_xtb_ohess',plan)
    esp,esp_calls=weighted_fresh('esp','b1_ESP_alone',plan);fallback,fallback_calls=weighted_fresh('esp','b1_ESP_WILLIAMS',plan)
    groups=collections.defaultdict(list)
    for r in calls:groups[(r['task'],r['size_stratum'])].append(r)
    tasks=sorted({r['task'] for r in calls if r['task']!='xtb_hessian'})
    means={(t,s,scope):float(np.mean([r['service_seconds'] for r in rows if scope=='all' or byid[r['record_id']]['molecule_lowest_energy_conformer']])) for (t,s),rows in groups.items() for scope in ('all','minimum')}
    sizes={s:len([r for r in panel if r['size_stratum']==s]) for s in ratios}
    esp_all={}
    for s in ratios:
        old=groups[('pm7_ESP',s)];success=[r['service_seconds'] for r in old if r['status']=='SUCCESS'];fail=sum(r['status']!='SUCCESS' for r in old)
        conditional=esp.get(s,{}).get('mean_service_seconds');esp_all[s]={'old_success_count':len(success),'old_failed_count':fail,'new_failure_retest_mean':conditional,'default_single_run_mean_seconds':(sum(success)+fail*conditional)/len(old) if conditional is not None else means[('pm7_ESP',s,'all')],'fallback_additional_mean_seconds':fail/len(old)*fallback.get(s,{}).get('mean_service_seconds',0),'old_source_success_mean':float(np.mean(success)) if success else None,'policy':'New default retiming applies only original failed population; original successful timings retained. Conditional retry cost shown separately. Missing failed stratum uses original timing.'}
    scenarios=[]
    for retained,polar,ESP,Hess,coverage in itertools.product(('strict','relaxed'),('keep','drop'),('single','drop'),('none','10pct_ohess','100pct_hess'),('all','minimum')):
        total=0.;components=[]
        for pop in population[retained]['strata']:
            s=pop['size_stratum']
            for task in tasks:
                if task=='pm7_ESP' and ESP=='drop':continue
                scope='minimum' if (task in CD or task=='pm7_ESP') and coverage=='minimum' else 'all'
                count=pop['molecules'] if scope=='minimum' else pop['records'];seconds=means[(task,s,scope)];source='native pilot measured scope'
                if task=='pm7_B':
                    if polar=='drop':
                        seconds*=ratios[s];component=seconds*pop['records'];source='paired35 no-POLAR B on all records'
                    elif coverage=='minimum':
                        component=means[(task,s,'all')]*ratios[s]*pop['records']+means[(task,s,'minimum')]*(1-ratios[s])*pop['molecules']
                        seconds=None;scope='core B all plus POLAR minimum';source='all-record no-POLAR core plus signed paired incremental POLAR on minima'
                    else:component=seconds*count
                elif task=='pm7_ESP':
                    if scope=='all':seconds=esp_all[s]['default_single_run_mean_seconds'];source='old successes plus failed-record weighted fresh retiming'
                    else:
                        scale=esp_all[s]['default_single_run_mean_seconds']/means[(task,s,'all')] if means[(task,s,'all')]>0 else 1.
                        seconds=means[(task,s,'minimum')]*scale;source='measured original molecular-minimum ESP timing scaled by all-record fresh retiming ratio; explicit minimum retiming model'
                    component=seconds*count
                else:component=seconds*count
                total+=component;components.append({'task':task,'size_stratum':s,'scope':scope,'calls':count,'mean_service_seconds':seconds,'projected_service_core_hours':component/3600,'source':source})
            if Hess!='none':
                measured=ohess if Hess=='10pct_ohess' else hess;fraction=.1 if Hess=='10pct_ohess' else 1;seconds=measured.get(s,{}).get('mean_service_seconds');origin='fresh matched100 weighted'
                if seconds is None:seconds=means[('xtb_hessian',s,'minimum')];origin='old native hess fallback, ohess not directly measured in this stratum'
                component=pop['molecules']*fraction*seconds;total+=component;components.append({'task':'xtb_'+Hess,'size_stratum':s,'scope':'minimum','calls':pop['molecules']*fraction,'mean_service_seconds':seconds,'projected_service_core_hours':component/3600,'source':origin})
        service=total/3600;scenarios.append({'retained':retained,'POLAR':polar,'ESP':ESP,'Hessian':Hess,'CD_scope':coverage,'xTB_nonhessian_scope':'all','service_core_hours':service,'allocated_core_hours_old_pilot_calibrated':service*factor,'wall_hours_at696_old_pilot_calibrated':service*factor/696,'ideal_wall_hours_at696':service/696,'components':components})
    C1={'status':'48_REQUIRED_SCENARIOS_MEASURED_AND_PROJECTED','scenarios':scenarios,'allocated_to_service_factor':factor,'capacity_scheduled_cpus':696,'physical_cores':600,'CD_scope_includes':['COSMO water','COSMO octanol','cation','anion','ESP if kept','POLAR response if kept'],'POLAR_no_to_with_ratio_by_stratum':ratios,'ESP_retiming_model':esp_all,'fresh_hess':hess,'fresh_ohess':ohess,'fresh_ohess_calls':ohess_calls,'fresh_hess_calls':hess_calls,'limitations':['Strict pilot reweighted to relaxed size strata; newly admitted stereochemistry and sizes up to252 heavy atoms not themselves native-QM piloted.','Hessian100 selection conditions on the1424 original successful Hessians; original17 timeout molecules not sampled. Times are run budgets; timeouts yield censored successful-completion costs.','100% means current --hess on each original minimum; 10% means independent-scratch --ohess. Alternative100%ohess cost is provided separately.','696 is scheduled CPUs including SMT, not600 physical cores; old actual allocated/service factor includes startup, read, parse, archive, SMT and tail. C3 measured factors are a separate sensitivity check, not substituted silently.','POLAR ratio from35 pairedcases is noisy and signed; it is not clipped to imply guaranteed speed savings.'],'100pct_ohess_additional_service_core_hours':{ret:sum(pop['molecules']*ohess.get(pop['size_stratum'],{}).get('mean_service_seconds',means[('xtb_hessian',pop['size_stratum'],'minimum')]) for pop in population[ret]['strata'])/3600 for ret in ('strict','relaxed')}}
    save(out/'C1_scenario_matrix.json',C1)
    # Sixteen closed real Slurm tasks: leave-one-job-out timing and allocation
    # calibration; this measures actual task elapsed, separate from molecule CV.
    accounting={str(j['job_id']):j for j in old_report['accounting']['jobs']}
    job_actual_service=collections.Counter()
    for r in calls:job_actual_service[r['job_id']]+=r['service_seconds']
    task_validation=[]
    for jid,j in accounting.items():
        selected=[r for r in calls if r['job_id']==jid]
        if not selected:continue
        train=collections.defaultdict(list)
        for r in calls:
            if r['job_id']!=jid:train[(r['task'],r['size_stratum'])].append(r['service_seconds'])
        avg={key:float(np.mean(value)) for key,value in train.items()}
        missing=[(r['task'],r['size_stratum']) for r in selected if (r['task'],r['size_stratum']) not in avg]
        if missing:
            task_validation.append({'job_id':jid,'prediction_available':False,'missing_training_cells':sorted(set(missing))});continue
        pred_service=sum(avg[(r['task'],r['size_stratum'])] for r in selected)
        allocated_other=sum(float(v['allocated_core_hours'])*3600 for key,v in accounting.items() if key!=jid)
        service_other=sum(value for key,value in job_actual_service.items() if key!=jid and key in accounting)
        training_factor=max(1.,allocated_other/service_other) if service_other>0 else None
        elapsed=float(j['ElapsedRaw']);cpus=int(j['AllocCPUS']);prediction=pred_service*training_factor/cpus
        task_validation.append({'job_id':jid,'prediction_available':True,'outcome_slots':len(selected),'AllocCPUS':cpus,'actual_elapsed_seconds':elapsed,'predicted_elapsed_seconds':prediction,'training_only_allocated_to_service_factor':training_factor,'signed_error_seconds':prediction-elapsed,'absolute_error_seconds':abs(prediction-elapsed),'actual_over_prediction':elapsed/prediction if prediction else None})
    task_validation_report={'source_scope':'Original16 completed real native-v4 Slurm jobs, including original Hessian and failed/timeout run budgets. Each job is held out both from stratum-task timing means and from allocated/service calibration.','jobs':task_validation,'actual_job_elapsed_seconds':stats([r.get('actual_elapsed_seconds') for r in task_validation]),'absolute_prediction_error_seconds':stats([r.get('absolute_error_seconds') for r in task_validation]),'actual_over_prediction':stats([r.get('actual_over_prediction') for r in task_validation]),'unaccounted_outcome_slots':sum(r['job_id'] not in accounting for r in calls),'candidate_configuration_measured':False}
    save(out/'C2_actual_task_validation.json',task_validation_report)
    # Predict service per molecule from each task's mean seconds per record at
    # its size stratum. Five-fold held-out molecules, never conformer leakage.
    mols=collections.defaultdict(list)
    for r in calls:
        if r['task']!='xtb_hessian':mols[r['molecule_id']].append(r)
    fold={m:int(hashlib.sha256(('C2|'+m).encode()).hexdigest()[:8],16)%5 for m in mols}
    fits={};residuals=[]
    for task in tasks:
        for s in ratios:
            rows=groups[(task,s)];xx=np.asarray([math.log(max(r['natoms'],1)) for r in rows]);yy=np.asarray([math.log(max(r['service_seconds'],.001)) for r in rows]);design=np.stack([np.ones(len(xx)),xx],axis=1)
            beta=np.linalg.lstsq(design,yy,rcond=None)[0];smear=float(np.mean(np.exp(yy-design@beta)));fits[(task,s)]=(beta.tolist(),smear,float(np.median([r['natoms'] for r in rows])))
    predictions={}
    for f in range(5):
        train=collections.defaultdict(list)
        for r in calls:
            if r['task']=='xtb_hessian' or fold[r['molecule_id']]==f:continue
            train[(r['task'],r['size_stratum'])].append(r['service_seconds'])
        avgs={k:float(np.mean(v)) for k,v in train.items()}
        for m,rows in mols.items():
            if fold[m]!=f:continue
            actual=sum(r['service_seconds'] for r in rows);pred=sum(avgs[(r['task'],r['size_stratum'])] for r in rows)
            residuals.append({'molecule_id':m,'heavy_atoms':max(r['heavy_atoms'] for r in rows),'records':len({r['record_id'] for r in rows}),'actual_service_seconds':actual,'predicted_service_seconds':pred,'signed_error_seconds':pred-actual,'absolute_error_seconds':abs(pred-actual),'actual_over_prediction':actual/pred if pred else None})
    pq.write_table(pa.Table.from_pylist(residuals),out/'C2_heldout_predictions.parquet',compression='zstd')
    holdout={'molecules':len(residuals),'folds':5,'split_unit':'molecule','prediction_model':'Stratum×task arithmetic mean from four training folds summed across the entire held-out molecule; complete original merged-POLAR13-call pipeline.','absolute_error_seconds':stats([r['absolute_error_seconds'] for r in residuals]),'relative_error_abs':stats([r['absolute_error_seconds']/r['actual_service_seconds'] for r in residuals if r['actual_service_seconds']>0]),'actual_over_prediction':stats([r['actual_over_prediction'] for r in residuals]),'actual_molecule_service_seconds':stats([r['actual_service_seconds'] for r in residuals]),'heavy_gt40_actual_molecule_service_seconds':stats([r['actual_service_seconds'] for r in residuals if r['heavy_atoms']>40]),'maximum_observed_molecule':max(residuals,key=lambda r:r['actual_service_seconds'])}
    inflation=max(1.,holdout['actual_over_prediction']['p90']);capacity=24*20*3600
    db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute("SET memory_limit='90GB'")
    qpath=str(ROOT/'a_retained/relaxed_quality_annotations.parquet').replace("'","''")
    table=db.execute(f"SELECT molecule_id,count(*) AS records,max(heavy_atoms) AS heavy_atoms,max(total_atoms) AS natoms,max(file_bin) AS file_bin,bool_or(split='unassigned') AS has_unassigned FROM read_parquet('{qpath}') WHERE retained GROUP BY molecule_id").fetch_arrow_table();db.close()
    popmols=table.to_pylist()
    if len(popmols)!=population['relaxed']['molecules'] or sum(r['records'] for r in popmols)!=population['relaxed']['records']:raise ValueError('MANIFEST_RELAXED_PACKING_COUNT_MISMATCH')
    # Candidate work packing only: POLARdrop/ESPdrop/CDminimum/xTBall/10%ohess.
    fresh_hess_sample=pq.read_table(ROOT/'b_quantum/plan/hessian_100.parquet',columns=['size_stratum','total_atoms']).to_pylist()
    ohess_max_natoms_by_stratum={s:max([r['total_atoms'] for r in fresh_hess_sample if r['size_stratum']==s],default=max(r['natoms'] for r in groups[('xtb_hessian',s)])) for s in ratios}
    max_natoms_by_task_stratum={key:max(c['natoms'] for c in rows) for key,rows in groups.items()}
    for r in popmols:
        s=bins(r['heavy_atoms']);service=0.
        for task in tasks:
            if task=='pm7_ESP':continue
            seconds=means[(task,s,'minimum' if task in CD else 'all')]
            if r['natoms']>max_natoms_by_task_stratum[(task,s)]:seconds*=max(1.,(r['natoms']/max_natoms_by_task_stratum[(task,s)])**3)
            if task=='pm7_B':seconds*=ratios[s]
            service+=seconds*(1 if task in CD else r['records'])
        include_hess=int(hashlib.sha256(('HESS10|20261011|'+r['molecule_id']).encode()).hexdigest()[:8],16)%10000<1000
        if include_hess:
            hess_seconds=ohess.get(s,{}).get('mean_service_seconds',means[('xtb_hessian',s,'minimum')])
            hess_seconds*=max(1.,(r['natoms']/ohess_max_natoms_by_stratum[s])**3)
            service+=hess_seconds
        r['hessian_10pct_selected']=include_hess;r['predicted_service_seconds']=service;r['planned_allocated_seconds']=service*factor*inflation;r['heavy_beyond_pilot']=r['heavy_atoms']>194
    popmols.sort(key=lambda r:r['planned_allocated_seconds'],reverse=True)
    assignments=[];jobs=[];lane_heap=[(0.,i) for i in range(24)];total=0.;jid=0;oversized=[]
    def close_job():
        if total>0:jobs.append({'task_id':jid,'molecules':sum(1 for r in assignments[-job_n:] if r['task_id']==jid),'planned_core_hours':total/3600,'planned_wall_hours_longest_lane':max(x[0] for x in lane_heap)/3600,'planned_wall_hours_ideal':total/24/3600})
    job_n=0
    fresh_hess_sample=pq.read_table(ROOT/'b_quantum/plan/hessian_100.parquet',columns=['size_stratum','total_atoms']).to_pylist()
    ohess_max_natoms_by_stratum={s:max([r['total_atoms'] for r in fresh_hess_sample if r['size_stratum']==s],default=max(r['natoms'] for r in groups[('xtb_hessian',s)])) for s in ratios}
    max_natoms_by_task_stratum={key:max(c['natoms'] for c in rows) for key,rows in groups.items()}
    for r in popmols:
        cost=r['planned_allocated_seconds']
        if cost>24*3600:
            oversized.append({k:r[k] for k in ('molecule_id','heavy_atoms','records','predicted_service_seconds','planned_allocated_seconds')});continue
        if total+cost>capacity and total>0:
            close_job();jid+=1;lane_heap=[(0.,i) for i in range(24)];total=0.;job_n=0
        load,lane=heapq.heappop(lane_heap)
        if load+cost>24*3600 and total>0:
            heapq.heappush(lane_heap,(load,lane));close_job();jid+=1;lane_heap=[(0.,i) for i in range(24)];total=0.;job_n=0;load,lane=heapq.heappop(lane_heap)
        heapq.heappush(lane_heap,(load+cost,lane));total+=cost;job_n+=1
        assignments.append({'task_id':jid,'lane':lane,**r})
    close_job()
    if len(assignments)+len(oversized)!=len(popmols):raise ValueError('MANIFEST_PACKING_ASSIGNMENT_MISMATCH')
    pq.write_table(pa.Table.from_pylist(assignments),out/'C2_relaxed_candidate_task_manifest.parquet',compression='zstd')
    save(out/'C2_job_distribution.json',{'candidate_configuration':{'retained':'relaxed','POLAR':'drop','ESP':'drop','CD':'minimum','xTB':'all','Hessian':'10%ohess deterministic molecule hash','k':24,'packing_target_hours':20,'wall_limit_hours':24,'formal_configuration_adopted':False},'prediction_validation':holdout,'p90_residual_inflation':inflation,'old_allocated_over_service_factor':factor,'tasks':len(jobs),'packed_molecules':len(assignments),'oversized_molecules_requiring_chunk_resume_or_intramolecule_parallelism':oversized,'all_candidate_whole_molecule_modelled_costs_below24h':not oversized,'24h_candidate_elapsed_bound_empirically_proven':False,'actual_task_validation_reference':str(out/'C2_actual_task_validation.json'),'planned_job_wall_hours':stats([r['planned_wall_hours_longest_lane'] for r in jobs]),'planned_job_core_hours':stats([r['planned_core_hours'] for r in jobs]),'jobs':jobs,'maximum_candidate_molecule':{k:popmols[0][k] for k in ('molecule_id','heavy_atoms','records','predicted_service_seconds','planned_allocated_seconds')},'relaxed_unpiloted_heavy_gt194_molecules':sum(r['heavy_beyond_pilot'] for r in popmols),'OHess_extrapolation_reference_max_natoms_by_stratum':ohess_max_natoms_by_stratum,'extrapolation':'Beyond observed maximum natoms in a stratum, cubic scaling is a planning assumption, not a validated runtime guarantee; source heavy max252 vs pilot194.','ordering':'Greedy descending molecule cost; lane LPT; whole molecules never split. Original split memberships retained, unassigned included only for cost projection.','task_manifest':str(out/'C2_relaxed_candidate_task_manifest.parquet')})
    supplement={'source':str(OLD/'reports/wp4_final_pilot_accounted/wp4_pilot_report.json'),'per_atom_perturb_forces':old_report['observations']['perturbation'],'SCF_ionic_failure_detail':old_report['observations']['ions'],'xTB_failure_details':[{'record_id':r['record_id'],'task':r['task'],'status':r['status'],'qc_codes':r['qc_codes'],'diagnostic_lines':r['diagnostic_lines']} for r in calls if r['task'].startswith('xtb_') and r['status']!='SUCCESS']}
    save(ROOT/'b_quantum/analysis/B4_supplement.json',supplement)
    report={'status':'C1_C2_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'actual_worker_pids':sorted({pid for rows,pid in results}),'seconds':time.monotonic()-start,'scenarios':len(scenarios),'candidate_jobs':len(jobs),'physical_records':population['all_physical_records'],'relaxed_records':population['relaxed']['records'],'new_QM_calls':0,'original_data_written':False,'lmdb_1_created':False}
    save(out/'manifest.json',report);print(json.dumps(report))
if __name__=='__main__':main()
