#!/usr/bin/env python3
"""16-worker B1/B3 result analysis, including actual archived failure text."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as futures
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tarfile
import time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stats(values):
    observed=sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    if not observed:return {'n':0}
    def quantile(q):
        pos=(len(observed)-1)*q;lo=int(pos);hi=min(lo+1,len(observed)-1)
        return observed[lo]+(observed[hi]-observed[lo])*(pos-lo)
    return {'n':len(observed),'mean':statistics.mean(observed),'p50':quantile(.5),'p90':quantile(.9),'p99':quantile(.99),'min':observed[0],'max':observed[-1],'sum':sum(observed)}
def causal_reason(detail,text):
    if detail['status'].startswith('SKIPPED_'):return detail['status']
    if detail['status']=='SUCCESS':return 'SUCCESS'
    if detail['status']=='TIMEOUT':return 'TIMEOUT'
    if re.search(r'ESP method does not work with .d. orbitals',text,re.I):return 'D_ORBITAL_UNSUPPORTED'
    if re.search(r'VECTOR LENGTH OF ZERO IN SURFAC|RADIUS.*(?:IS ZERO|NOT DEFINED)|SUPPLY A VALUE IN SUBROUTINE SURFAC',text,re.I):return 'SURFACE_OR_UNDEFINED_RADIUS'
    if re.search(r'SCF DOES NOT CONVERGE|SCF DID NOT CONVERGE|SCF NOT CONVERGED|SCF FAILED|FAILURE TO ACHIEVE SCF|UNABLE TO ACHIEVE SELF.CONSISTENCY|SCC IS NOT CONVERGED|SELF CONSISTENT CHARGE ITERATOR DID NOT CONVERGE',text,re.I):return 'CONFIRMED_SCF_FAILURE'
    if re.search(r'Errors detected in keywords|keyword.*(?:conflict|not recognized|unknown|unrecognized)',text,re.I):return 'KEYWORD_CONFLICT'
    if detail.get('missing_properties'):return 'MISSING_PROPERTY_WITHOUT_SPECIFIC_DIAGNOSIS'
    return detail.get('failure_code') or detail['status']
def read_case(item):
    import pyarrow.parquet as pq
    path,row,zstd=item;path=Path(path);receipt=json.loads(path.read_text());ref=receipt['parquet']
    if sha(ref['path'])!=ref['sha256']:raise ValueError('MANIFEST_PARQUET_SOURCE_DIFFERS')
    details=[json.loads(r['details_json']) for r in pq.read_table(ref['path'],columns=['details_json'],use_threads=False).to_pylist()]
    archives=collections.defaultdict(dict)
    for detail in details:
        ref=detail.get('archive')
        if ref and detail['status']!='SUCCESS':archives[ref['path']][ref['member_prefix']]=detail
    for archive_path,targets in archives.items():
        reference=next(iter(targets.values()))['archive']
        if sha(archive_path)!=reference['sha256']:raise ValueError('MANIFEST_ARCHIVE_SOURCE_DIFFERS')
        process=subprocess.Popen([zstd,'-d','-c',archive_path],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout,mode='r|') as files:
                for member in files:
                    if not member.isfile():continue
                    prefix,name=member.name.rsplit('/',1);detail=targets.get(prefix)
                    if detail is None or name not in ('input.out','process.out'):continue
                    data=files.extractfile(member).read();text=data.decode(errors='replace')
                    detail.setdefault('failure_text_sources',[]).append({'file':name,'sha256':hashlib.sha256(data).hexdigest(),
                       'diagnostic_lines':[line.strip() for line in text.splitlines() if re.search(r'not work|SURFAC|RADIUS|not converg|SCF.*fail|error|keyword',line,re.I)][-30:]})
                    previous=detail.get('actual_causal_reason')
                    classification=causal_reason(detail,text)
                    if previous is None or classification in ('D_ORBITAL_UNSUPPORTED','SURFACE_OR_UNDEFINED_RADIUS','CONFIRMED_SCF_FAILURE','KEYWORD_CONFLICT'):
                        detail['actual_causal_reason']=classification
        finally:
            while process.stdout.read(1<<20):pass
            process.stdout.close();error=process.stderr.read();code=process.wait()
        if code:raise RuntimeError('ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace'))
    for detail in details:
        detail.setdefault('actual_causal_reason',causal_reason(detail,' '.join(detail.get('diagnostic_lines',[]))))
    elements=row.get('elements',row.get('element_symbols',[]))
    if isinstance(elements,str):elements=[elements]
    return {'record_id':row['record_id'],'molecule_id':row['molecule_id'],'size_stratum':row['size_stratum'],
      'original_reason':row.get('esp_failure_reason'),'original_imaginary_group':row.get('original_imaginary_group'),
      'original_frequency_band':row.get('original_frequency_band'),
      'original_PM7_gradient_norm_kcal_mol_A':row.get('original_PM7_gradient_norm_kcal_mol_A'),
      'elements':elements,'details':details,'parquet_source':ref,'receipt_sha256':sha(path),'worker_pid':os.getpid()}
SIZE_STRATA=('0_10','11_20','21_30','31_50','51_75','76_100','above_100')
def weighted_service(cases,weights,task_names):
    """Observed single-thread service under the tested timeout/fallback policy.

    A skipped conditional variant costs zero. A nonlaunched requested primary
    call has no fresh measurement and makes that population estimate incomplete.
    Timeouts give measured capped service, but only a completion-time lower bound.
    """
    weighted_population=sum(weight for _,weight in weights)
    sums={'wall':0.,'cpu':0.};observed_weight=0.;cpu_weight=0.;timeout_weight=0.;missing_weight=0.
    launched=0;timeouts=0;statuses=collections.Counter();component={name:0. for name in task_names}
    for case,weight in weights:
        selected={row['task']:row for row in case['details']};wall=0.;cpu=0.;has_cpu=True;missing=False;censored=False
        for name in task_names:
            row=selected[name];statuses[name+':'+row['status']]+=1
            if row.get('argv'):
                launched+=1;value=row.get('elapsed_seconds')
                if value is None or not math.isfinite(float(value)):missing=True
                else:wall+=float(value);component[name]+=weight*float(value)
                value=row.get('qm_child_cpu_seconds')
                if value is None or not math.isfinite(float(value)):has_cpu=False
                else:cpu+=float(value)
                if row['status']=='TIMEOUT':censored=True;timeouts+=1
            elif row['status'].startswith('SKIPPED_') and name=='b1_ESP_WILLIAMS':
                pass
            else:missing=True
        if missing:missing_weight+=weight
        else:sums['wall']+=weight*wall;observed_weight+=weight
        if has_cpu and not missing:sums['cpu']+=weight*cpu;cpu_weight+=weight
        if censored:timeout_weight+=weight
    return {'sample_records':len(weights),'represented_population':weighted_population,'launched_calls':launched,
      'sample_statuses':dict(statuses),'observed_service_population_weight':observed_weight,
      'weighted_service_seconds_total':sums['wall'],'average_service_seconds_per_record':sums['wall']/observed_weight if observed_weight else None,
      'average_CPU_seconds_per_record':sums['cpu']/cpu_weight if cpu_weight else None,
      'CPU_measured_population_weight':cpu_weight,'component_seconds_total':component,
      'component_average_seconds_per_record':{name:value/observed_weight if observed_weight else None for name,value in component.items()},
      'timeout_calls':timeouts,'completion_time_censored_population_weight':timeout_weight,
      'completion_time_censored_population_fraction':timeout_weight/weighted_population if weighted_population else None,
      'missing_service_population_weight':missing_weight,'population_mean_available':missing_weight==0 and observed_weight>0,
      'unconstrained_completion_mean_identified':missing_weight==0 and timeout_weight==0 and observed_weight>0,
      'service_interpretation':'Actual elapsed single-thread QM service under this timeout and conditional-fallback policy; failures consume service too. For TIMEOUT, unrestricted completion time is right-censored and observed service is its lower bound.'}
def population_cells(cases,specs,key_fn,task_names):
    result=[]
    for key,population,selected,weight in specs:
        members=[case for case in cases if key_fn(case)==key]
        if len(members)!=selected:raise ValueError('MANIFEST_WEIGHT_CELL_COUNTS_DIFFER:'+str(key))
        result.append({'cell':list(key),'population':population,'selected':selected,'population_weight_per_sample':weight,
          'cost':weighted_service(members,[(case,weight) for case in members],task_names),
          'fresh_evidence_available':bool(members)})
    return result
def task_statistics(calls):
    result={}
    for task in sorted({r['task'] for r in calls}):
        rows=[r for r in calls if r['task']==task];launched=[r for r in rows if r.get('argv')]
        success=sum(r['status']=='SUCCESS' for r in launched)
        result[task]={'outcomes':len(rows),'launched':len(launched),'successes':success,'success_rate_launched':success/len(launched) if launched else None,
          'statuses':dict(collections.Counter(r['status'] for r in rows)),
          'actual_failure_causes':dict(collections.Counter(r['actual_causal_reason'] for r in rows if r['status']!='SUCCESS')),
          'QM_wall_seconds_all_attempts':stats(r['elapsed_seconds'] for r in launched),
          'QM_wall_seconds_successes':stats(r['elapsed_seconds'] for r in launched if r['status']=='SUCCESS'),
          'QM_CPU_seconds':stats(r.get('qm_child_cpu_seconds') for r in launched),
          'timeouts':sum(r['status']=='TIMEOUT' for r in launched)}
    return result
def esp_report(cases,manifest):
    weights={tuple(row['stratum']):row['weight'] for row in manifest['ESP']['sampling_weights'] if row['selected']}
    transitions=collections.Counter();by_reason={};by_size={};weighted_total=0.;weighted_solo=0.;weighted_any=0.
    for case in cases:
        tasks={row['task']:row for row in case['details']};solo=tasks['b1_ESP_alone'];variant=tasks['b1_ESP_WILLIAMS']
        solved=solo['status']=='SUCCESS' or variant['status']=='SUCCESS'
        weight=weights[(case['original_reason'],case['size_stratum'])];weighted_total+=weight
        weighted_solo+=weight*(solo['status']=='SUCCESS');weighted_any+=weight*solved
        transitions[(case['original_reason'],solo['actual_causal_reason'],variant['actual_causal_reason'])]+=1
        for grouping,key in ((by_reason,case['original_reason']),(by_size,case['size_stratum'])):
            row=grouping.setdefault(key,{'sample_records':0,'solo_successes':0,'any_successes':0})
            row['sample_records']+=1;row['solo_successes']+=solo['status']=='SUCCESS';row['any_successes']+=solved
    specs=[(tuple(row['stratum']),row['population'],row['selected'],row['weight']) for row in manifest['ESP']['sampling_weights']]
    names=('b1_ESP_alone','b1_ESP_WILLIAMS');getkey=lambda case:(case['original_reason'],case['size_stratum'])
    cells=population_cells(cases,specs,getkey,names)
    cost_by_size={}
    for size in SIZE_STRATA:
        members=[case for case in cases if case['size_stratum']==size]
        cost_by_size[size]=weighted_service(members,[(case,weights[getkey(case)]) for case in members],names)
    failed_population=manifest['ESP']['failed_population'];panel_population=manifest['panel']['records']
    element_scopes={}
    for task in names:
        reasons=sorted({row['actual_causal_reason'] for case in cases for row in case['details'] if row['task']==task})
        element_scopes[task]={}
        for reason in reasons:
            members=[case for case in cases if next(row for row in case['details'] if row['task']==task)['actual_causal_reason']==reason]
            element_scopes[task][reason]={'sample_records':len(members),
              'sample_element_presence_counts':dict(collections.Counter(str(element) for case in members for element in set(case['elements']))),
              'size_stratum_counts':dict(collections.Counter(case['size_stratum'] for case in members))}
    return {'records':len(cases),'sampling_population':f'The {failed_population} failed records of the original strict pilot; weights restore that pilot failure population only.',
      'weighted_population_total':weighted_total,'weighted_solo_recovery_rate':weighted_solo/weighted_total if weighted_total else None,
      'weighted_any_recipe_recovery_rate':weighted_any/weighted_total if weighted_total else None,
      'by_original_reason':by_reason,'by_size':by_size,
      'cause_transitions':[{'original_sampling_reason':key[0],'solo_actual_reason':key[1],'WILLIAMS_actual_reason':key[2],'records':count} for key,count in sorted(transitions.items())],
      'cost':{'weighting':'Within each original-failure-reason x size cell: population/selected. Restore failure population only.',
        'default200_plus_conditional_fallback':weighted_service(cases,[(case,weights[getkey(case)]) for case in cases],names),
        'by_size_stratum':cost_by_size,'population_sampling_cells':cells,
        'original_panel_records':panel_population,'original_failed_population':failed_population,
        'original_success_population_same_manifest':panel_population-failed_population,
        'unconditional_first_run_average_seconds':None,
        'unconditional_combination_formula':'(old_success_population * independently_measured_old_success_mean_seconds + original_failed_population * weighted_retimed_failure_baseline_mean_seconds) / original_panel_records. Conditional WILLIAMS cost is a separate optional component. This retest cannot identify the old-success term.',
        'fallback_policy':'Try WILLIAMS only after a failed standalone ESP, except confirmed d-orbital unsupported. Skipped variants contribute zero cost.'},
      'actual_reason_element_size_scopes':element_scopes,
      'element_encoding':'Atomic numbers when inherited panel elements are integers; presence counts count each element once per record, not atoms.',
      'interpretation':'Original SCF_FAILED sampling categories came from a broad metadata classifier. Confirmed causal reasons above require actual retained text; generic QM_EXIT_OR_SCF_FAILED is not evidence of SCF nonconvergence.',
      'recommended_decision_basis':'Use observed standalone recovery and conditional WILLIAMS recovery, failure element/size scope, and measured costs. D-basis refusal is intrinsic to this ESP path; surface generation cannot repair it.'}
def hessian_report(cases,manifest):
    groups={}
    for group in ('imaginary','no_imaginary'):
        members=[case for case in cases if case['original_imaginary_group']==group];methods={}
        for name in ('b3_xtb_hess','b3_xtb_ohess','b3_pm7_force'):
            calls=[next(r for r in case['details'] if r['task']==name) for case in members]
            usable=[r for r in calls if r['status']=='SUCCESS' and r.get('values',{}).get('frequencies_cm_inverse') is not None]
            imaginary=sum(r['values'].get('imaginary_count_below_minus20',0)>0 for r in usable)
            metrics=[m for r in usable for m in r['values'].get('mode_analysis',{}).get('negative_mode_metrics',[])]
            classified=sum(r['values'].get('mode_analysis',{}).get('status')=='AVAILABLE' for r in usable)
            methods[name]={'selected_molecules':len(members),'successful':len(usable),'imaginary_molecules':imaginary,
              'imaginary_rate_successful':imaginary/len(usable) if usable else None,
              'negative_frequency_mode_count_moderate':sum(r['values'].get('imaginary_count_minus100_to_minus20',0) for r in usable),
              'negative_frequency_mode_count_deep':sum(r['values'].get('imaginary_count_below_minus100',0) for r in usable),
              'mode_classification_available_molecules':classified,'negative_modes_classified':len(metrics),
              'torsion_dominant_negative_modes':sum(m['torsion_dominant_heuristic'] for m in metrics),
              'torsion_score_share':stats(m['torsion_score_share'] for m in metrics),
              'wall_seconds':stats(r['elapsed_seconds'] for r in calls if r.get('argv')),
              'RMSD_all_atoms_A':stats(r['values'].get('aligned_RMSD_all_atoms_A') for r in usable),
              'RMSD_heavy_atoms_A':stats(r['values'].get('aligned_RMSD_heavy_atoms_A') for r in usable),
              'optimized_minus_original_energy_Eh':stats(r['values'].get('optimized_minus_original_energy_Eh') for r in usable),
              'PM7_FORCE_start_gradient_kcal_mol_A':stats(r['values'].get('FORCE_start_gradient_norm_kcal_mol_A') for r in usable)}
        groups[group]=methods
    pairs=[]
    for case in cases:
        calls={r['task']:r for r in case['details']};flags={}
        for task,row in calls.items():
            freq=row.get('values',{}).get('frequencies_cm_inverse')
            flags[task]=sum(x<-20 for x in freq) if row['status']=='SUCCESS' and freq is not None else None
        pairs.append({'record_id':case['record_id'],'molecule_id':case['molecule_id'],'original_group':case['original_imaginary_group'],
          'size_stratum':case['size_stratum'],'original_PM7_gradient_norm':case['original_PM7_gradient_norm_kcal_mol_A'],
          'imaginary_mode_counts':flags,
          'supports_method_mismatch':flags.get('b3_xtb_hess',0) is not None and flags['b3_xtb_hess']>0 and flags.get('b3_pm7_force')==0,
          'both_PM7_and_GFN2_negative':flags.get('b3_xtb_hess',0) is not None and flags['b3_xtb_hess']>0 and flags.get('b3_pm7_force',0) is not None and flags['b3_pm7_force']>0})
    specs=[((group['group'],*row['stratum']),row['population'],row['selected'],row['weight'])
      for group in manifest['hessian']['sampling_weights'] for row in group['strata']]
    getkey=lambda case:(case['original_imaginary_group'],case['size_stratum'],case['original_frequency_band'])
    weights={key:weight for key,_,selected,weight in specs if selected}
    fresh_cost={};weighted_diagnostics={}
    for task in ('b3_xtb_hess','b3_xtb_ohess','b3_pm7_force'):
        cells=population_cells(cases,specs,getkey,(task,));by_size={};diag_size={}
        for size in SIZE_STRATA:
            members=[case for case in cases if case['size_stratum']==size]
            pairs_weight=[(case,weights[getkey(case)]) for case in members]
            by_size[size]=weighted_service(members,pairs_weight,(task,))
            population=sum(weight for _,weight in pairs_weight);successful=imaginary=0.
            for case,weight in pairs_weight:
                row=next(row for row in case['details'] if row['task']==task)
                freq=row.get('values',{}).get('frequencies_cm_inverse')
                if row['status']=='SUCCESS' and freq is not None:
                    successful+=weight;imaginary+=weight*any(value<-20 for value in freq)
            diag_size[size]={'represented_population':population,'successful_frequency_population_weight':successful,
              'imaginary_population_weight':imaginary,'imaginary_rate_successful_weighted':imaginary/successful if successful else None,
              'overall_imaginary_rate_lower_bound':imaginary/population if population else None,
              'overall_imaginary_rate_upper_bound':(imaginary+population-successful)/population if population else None}
        fresh_cost[task]={'by_size_stratum':by_size,'population_sampling_cells':cells,
          'overall':weighted_service(cases,[(case,weights[getkey(case)]) for case in cases],(task,)),
          'missing_fresh_evidence_cells':[row['cell'] for row in cells if not row['fresh_evidence_available'] or not row['cost']['population_mean_available']]}
        weighted_diagnostics[task]=diag_size
    return {'records':len(cases),'by_original_group':groups,'paired_mode_counts':pairs,
      'original1424_statistics':manifest['hessian'],
      'fresh_cost_components':fresh_cost,'weighted_frequency_diagnostics_by_size':weighted_diagnostics,
      'cost_population':'Original 1424 successful Hessian molecules only. The 17 original timeouts are outside this sampling frame; use retained old-native costs for those or an explicitly documented missing-evidence fallback. Do not invent fresh ohess/FORCE evidence for them.',
      'cost_weighting':'Within imaginary/no-imaginary x seven size_stratum x original frequency-band: population/selected. Costs include physical/SCF failures and capped timeout service; 50/50 raw averages are not population means.',
      'causality_limit':'PM7 FORCE negative modes/high starting gradient support a nonminimum PM7 geometry. GFN2negative with PM7nonnegative supports method mismatch. These are diagnostic comparisons, not a proof of a unique cause. FORCE LET does not optimize; ohess uses separate optimized geometry.',
      'torsion_limit':'Score shares are exploratory internal-coordinate change measures, not kinetic/potential energy percentages. Old1424 archive lacked mode vectors; no old torsion assignments are inferred from frequency alone.'}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-root',required=True);parser.add_argument('--mode',choices=('esp','hessian'),required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--workers',type=int,default=16);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());print('B_QUANTUM_REPORT_AST_PASS_NO_DATA');return 0
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_PARALLEL_WORKERS_REQUIRED')
    import pyarrow.parquet as pq
    root=Path(args.run_root);meta=json.loads((root/'metadata.json').read_text());manifest=meta['sample_manifest']
    name='esp_200.parquet' if args.mode=='esp' else 'hessian_100.parquet';sample=Path(manifest['samples'][name]['path'])
    if sha(sample)!=manifest['samples'][name]['sha256']:raise ValueError('MANIFEST_SAMPLE_SHA_DIFFERS')
    rows=pq.read_table(sample).to_pylist();expected=200 if args.mode=='esp' else 100
    paths=list((root/'records').glob('*/receipt.json'));byid={row['record_id']:row for row in rows}
    if len(rows)!=expected or len(paths)!=expected:raise ValueError('MANIFEST_CLOSED_RECORD_COUNTS_DIFFER')
    tasks=[]
    for path in paths:
        receipt=json.loads(path.read_text());tasks.append((path,byid[receipt['record_id']],meta['binding']['config']['zstd_executable']))
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);started=time.monotonic();cases=[];errors=[]
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as pool:
        pending={pool.submit(read_case,item):str(item[0]) for item in tasks}
        for future in futures.as_completed(pending):
            try:cases.append(future.result())
            except Exception as exc:errors.append({'receipt':pending[future],'error':str(exc)})
    if errors:(out/'errors.json').write_text(json.dumps(errors,indent=2));raise ValueError('MANIFEST_ANALYSIS_NOT_CLOSED')
    calls=[row for case in cases for row in case['details']]
    if len(calls)!=expected*(2 if args.mode=='esp' else 3):raise ValueError('MANIFEST_SLOT_COUNT_DIFFERS')
    report={'scope':'B1_ESP200_CLOSED_ANALYSIS' if args.mode=='esp' else 'B3_HESSIAN100_CLOSED_ANALYSIS',
      'job_id':os.environ['SLURM_JOB_ID'],'seed':20261011,'mode':args.mode,'run_metadata_sha256':sha(root/'metadata.json'),
      'script_sha256':sha(__file__),'actual_worker_pids':sorted({case['worker_pid'] for case in cases}),
      'elapsed_seconds':time.monotonic()-started,'task_statistics':task_statistics(calls),
      'analysis':esp_report(cases,manifest) if args.mode=='esp' else hessian_report(cases,manifest),
      'cases':cases,'QM_calls':0,'LMDB_opened':False,'original_outputs_modified':False}
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    stats_rows=report['task_statistics'];analysis=report['analysis']
    lines=['# B1 standalone ESP retest' if args.mode=='esp' else '# B3 Hessian comparison','',
      '|Task|Launched|Success|Success rate|Wall p50 / p90 seconds|','|---|---:|---:|---:|---:|']
    for name,row in stats_rows.items():
        times=row['QM_wall_seconds_all_attempts'];rate=row['success_rate_launched']
        lines.append(f"|{name}|{row['launched']}|{row['successes']}|{rate:.2%}|{times.get('p50',0):.3f} / {times.get('p90',0):.3f}|" if rate is not None else f'|{name}|0|0|NA|NA|')
    if args.mode=='esp':
        lines+=['',f"Weighted recovery in the original {analysis['weighted_population_total']:.0f} failed-record population: standalone {analysis['weighted_solo_recovery_rate']:.3%}; standalone plus conditional WILLIAMS {analysis['weighted_any_recipe_recovery_rate']:.3%}.",
          '', 'The sample was drawn only from previous failures. Unconditional first-run cost requires the old successful-population cost component.','',
          '|Size stratum|Represented failed population|Standalone service mean s|Conditional fallback mean s|Timeout weight fraction|','|---|---:|---:|---:|---:|']
        for size,row in analysis['cost']['by_size_stratum'].items():
            component=row['component_average_seconds_per_record']
            lines.append(f"|{size}|{row['represented_population']:.0f}|{component['b1_ESP_alone'] or 0:.3f}|{component['b1_ESP_WILLIAMS'] or 0:.3f}|{row['completion_time_censored_population_fraction'] or 0:.3%}|")
    else:
        lines+=['','Weighted costs restore imaginary group, size, and frequency-band population counts; the unweighted 50/50 mean is not the population mean. The 17 old Hessian timeouts lie outside the fresh sampling frame.','',
          '|Task|Size stratum|Represented population|Observed service mean s|Timeout weight fraction|Fresh population mean available|','|---|---|---:|---:|---:|---:|']
        for task,component in analysis['fresh_cost_components'].items():
            for size,row in component['by_size_stratum'].items():
                lines.append(f"|{task}|{size}|{row['represented_population']:.0f}|{row['average_service_seconds_per_record'] or 0:.3f}|{row['completion_time_censored_population_fraction'] or 0:.3%}|{row['population_mean_available']}|")
        lines+=['',analysis['torsion_limit'],analysis['causality_limit']]
    lines+=['','Full stratification, population weights, archived failure-text evidence, censored service observations, and paired values are recorded in report.json. No new QM or LMDB access.']
    (out/'appendix.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'B_QUANTUM_CLOSED_ANALYSIS_COMPLETE','mode':args.mode,'task_statistics':stats_rows}))
    return 0
if __name__=='__main__':raise SystemExit(main())
