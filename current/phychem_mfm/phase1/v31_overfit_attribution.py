"""Compose the requested diagnostic plans/results from closed producer outputs."""
import csv
import json
import math
from pathlib import Path


def load_run(directory):
    directory=Path(directory)
    path=directory/'summary.json'
    if not path.is_file():
        return None
    value=json.loads(path.read_text())
    value['_directory']=str(directory)
    value['_metrics']={r['field']:r for r in value['all_133_final_metrics']}
    return value


def complete(run,updates):
    return run is not None and run['status']=='CONTROLLED_RUN_COMPLETE' and run['actual_updates']==updates


def passed(metric):
    return metric is not None and metric.get('R2') is not None and metric['R2']>=.95


def save(path,value):
    from .v2_disk import save_metadata_json
    save_metadata_json(value,path)


def plan_families(phase0,e2_directories,output):
    """Keep clip1 as the controlled chain; clip10 is its additional contrast."""
    phase0=Path(phase0);output=Path(output)
    with (phase0/'phase0_fields.csv').open() as file:
        fields=list(csv.DictReader(file))
    runs=[load_run(p) for p in e2_directories]
    if len(runs)!=2 or not all(complete(r,30000) for r in runs):
        raise ValueError('Wait for both actual E2 30000-update results')
    canonical=next(r for r in runs if r['clip']==1.)
    families={};dispositions=[]
    for field in fields:
        name=field['field']
        if field['original_pass']=='True' or any(passed(r['_metrics'].get(name)) for r in runs):
            continue
        best=max(runs,key=lambda r:r['_metrics'][name]['R2'] if r['_metrics'][name]['R2'] is not None else -math.inf)
        trajectory=next(r for r in best['E2_trajectory'] if r['field']==name)
        item=dict(field=name,family=field['family'],best_joint_run=best['_directory'],**{k:v for k,v in trajectory.items() if k!='field'})
        dispositions.append(item)
        if trajectory['disposition']=='PLATEAU_ELIGIBLE_FOR_E3':
            families.setdefault(field['family'],[]).append(name)
    order=sorted(families,key=lambda family:(-len(families[family]),family))
    output.mkdir(parents=True,exist_ok=False)
    planned=[]
    for index,family in enumerate(order[:12],1):
        configuration=dict(fixed_path=canonical['fixed_set'],
            output=str(output.parent/f'M2_DIAG_E3_F{index:02d}_20261108'),experiment='E3',updates=10000,
            output_parameterization=canonical['output_parameterization'],clip=1.,lr=3e-4,
            head_hidden_dim=64,family=family)
        path=output/f'E3_F{index:02d}.json'
        save(path,configuration)
        planned.append(dict(index=index,family=family,target_fields=families[family],
            E3_configuration=str(path),E3_output=configuration['output']))
    plan=dict(phase0=str(phase0),E2_directories=[str(p) for p in e2_directories],families=planned,
        E2_dispositions=dispositions,unrun_cap_families=order[12:],
        priority='Number of still-failed plateau target fields descending; family name for ties; at most12',
        E3_recipe='Original clip1 chain, fresh seed0, original family definitions; no automatic M3 recipe change',
        eligibility='Originally failed; no E2 terminal pass; best E2 variant final5k gain<.005',
        fields_outside_eligibility='Report unresolved; do not infer label-side failure')
    save(output/'plan.json',plan)
    print(json.dumps(dict(E3_families=len(planned),E3_target_fields=sum(len(x['target_fields']) for x in planned),
                         cap_unrun=len(order[12:]))),flush=True)
    return plan


def plan_probe(plan_path,index):
    path=Path(plan_path);plan=json.loads(path.read_text())
    family=next(f for f in plan['families'] if f['index']==index)
    run=load_run(family['E3_output'])
    if not complete(run,10000):
        raise ValueError('A completed10000-update E3 result is required')
    remaining=[n for n in family['target_fields'] if not passed(run['_metrics'][n])]
    if not remaining:
        return None
    configuration=dict(fixed_path=run['fixed_set'],
        output=str(path.parent.parent/f'M2_DIAG_E4_F{index:02d}_20261108'),
        experiment='E4',updates=30000,output_parameterization=run['output_parameterization'],
        clip=run['clip'],lr=1e-3,head_hidden_dim=512,family=run['family'])
    destination=path.parent/f'E4_F{index:02d}.json'
    save(destination,configuration)
    print(json.dumps(dict(index=index,family=run['family'],remaining_target_fields=remaining,
                          configuration=str(destination),output=configuration['output'])),flush=True)
    return configuration


def build_attribution(plan_path,output):
    """Never turn an unrun/timeboxed probe into a label-side allegation."""
    from .v31_overfit_diagnosis import write_rows
    plan=json.loads(Path(plan_path).read_text());phase0=Path(plan['phase0'])
    with (phase0/'phase0_fields.csv').open() as file:
        fields=list(csv.DictReader(file))
    with (Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_overfit_4526238')/'per_head_metrics.csv').open() as file:
        baseline={r['field']:r for r in csv.DictReader(file)}
    e2=[load_run(p) for p in plan['E2_directories']]
    if not all(complete(r,30000) for r in e2):
        raise ValueError('Both E2 terminal results are required')
    e2.sort(key=lambda r:r['clip'])
    family_runs={}
    for entry in plan['families']:
        e3=load_run(entry['E3_output'])
        e4=load_run(Path(entry['E3_output']).with_name(f"M2_DIAG_E4_F{entry['index']:02d}_20261108"))
        family_runs[entry['family']]=(entry,e3,e4)
    rows=[];label_side={};pending=[]
    for field in fields:
        name=field['field'];base=baseline[name]
        best=max(e2,key=lambda r:r['_metrics'][name]['R2'] if r['_metrics'][name]['R2'] is not None else -math.inf)
        metric=best['_metrics'][name];evidence=best['_directory'];category='过拟合未解决';reason='E2仍未收敛或家族运行上限'
        variant='';scope='unresolved';original_pass=base['passed']=='True'
        if original_pass:
            score=float(base['R2']);rmse=math.sqrt(max(0.,1-score))*float(field['label_std'])
            proposal=(None if int(field['valid_components'])<200 or int(field['unique_values'])<=10
                      else rmse<=metric['proposed_RMSE_threshold'])
            metric=dict(metric,R2=score,RMSE=rmse,proposed_pass=proposal)
            category='基线已达标';evidence='M2_overfit_4526238';scope='baseline';reason='原联合过拟合已达原阈值'
        else:
            success=next((r for r in e2 if passed(r['_metrics'][name])),None)
            if success:
                category='预算不足';metric=success['_metrics'][name];evidence=success['_directory'];scope='optimization'
                variant='clip1' if success['clip']==1 else 'clip10_only'
                reason=('E2原clip1预算扩展达标' if success['clip']==1 else
                        '按指南E2桶归类；仅clip10对照达标，不能单独归因于步数')
            elif field['family'] in family_runs:
                entry,e3,e4=family_runs[field['family']]
                if name in entry['target_fields']:
                    if complete(e3,10000):
                        metric=e3['_metrics'][name];evidence=e3['_directory']
                        if passed(metric):
                            category='多任务干扰';scope='model';reason='原clip1联合30k未达标，同配方单家族10k达标'
                        elif complete(e4,30000):
                            metric=e4['_metrics'][name];evidence=e4['_directory']
                            if passed(metric):
                                scope='model_unresolved';reason='E4探针已可学；同时改lr与头容量，模型侧细分原因未定'
                            elif field['C_flag']=='True' and metric.get('proposed_pass'):
                                category='判据不适用';scope='criterion_proposal';reason='修正提案达标，仅并列诊断，未经批准仍不算正式验收通过'
                            else:
                                category='标签侧待查';scope='label_review';reason='E4完整30k仍未达标，不自行判定标签正误'
                                residual=json.loads((Path(e4['_directory'])/'residual_top20.json').read_text())
                                label_side[name]=residual['fields'][name]
                        else:
                            if ((e4 is not None and e4['status'].startswith('OVERFIT_UNRESOLVED'))
                                    or entry.get('E4_unresolved_reason')):
                                reason=entry.get('E4_unresolved_reason','E4达到用户诊断时间盒，未完成计划预算')
                            else:
                                pending.append(dict(field=name,required='E4',family=field['family']))
                    else:
                        if ((e3 is not None and e3['status'].startswith('OVERFIT_UNRESOLVED'))
                                or entry.get('E3_unresolved_reason')):
                            reason=entry.get('E3_unresolved_reason','E3达到用户诊断时间盒，未完成计划预算')
                        else:
                            pending.append(dict(field=name,required='E3',family=field['family']))
            if category=='过拟合未解决' and field['C_flag']=='True' and metric.get('proposed_pass'):
                category='判据不适用';scope='criterion_proposal';reason='修正提案达标，仅并列报告，原阈值仍失败'
        rows.append(dict(field=name,family=field['family'],attribution=category,evidence_run=evidence,
            final_R2=metric.get('R2'),RMSE=metric.get('RMSE'),original_R2=base['R2'],baseline_passed=original_pass,
            latest_joint_R2=best['_metrics'][name]['R2'],optimization_variant=variant,
            proposed_criterion_result=metric.get('proposed_pass'),proposed_criterion_approved=False,
            epsilon_abs=metric.get('epsilon_abs'),epsilon_source=metric.get('epsilon_source'),
            conclusion_scope=scope,reason=reason))
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_rows(output/'attribution.csv',rows)
    if label_side:
        save(output/'label_side_residual_top20.json',dict(fields=label_side,
            missing_numeric_encoding='null with original boolean mask; original fixed MID/conformer identities retained'))
    categories=('基线已达标','管线不一致','输出参数化','多任务干扰','预算不足','判据不适用','标签侧待查','过拟合未解决')
    counts={name:sum(r['attribution']==name for r in rows) for name in categories}
    summary=dict(status='INCOMPLETE_REQUIRED_PROBES' if pending else 'DIAGNOSIS_RESULTS_COMPOSED',
        fields=len(rows),attribution_counts=counts,label_side_fields=list(label_side),
        pending=pending,formal_criterion_changed=False,all_M2_fields_formally_passed=False,
        E1='SKIPPED_BY_GUIDE_PHASE0_RULE',E4_learnable_unresolved=sum(r['conclusion_scope']=='model_unresolved' for r in rows),
        clip10_only_E2=sum(r['optimization_variant']=='clip10_only' for r in rows))
    save(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary
