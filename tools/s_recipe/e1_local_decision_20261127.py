"""One final seed0 E1 delivery from already closed frozen/FT components."""
import json
from pathlib import Path

from cpu_execution_20261126 import execution_fields,native_record
from e1_reporting_20261126 import AUTHORITY,DECISION_AUTHORITY,KS,decide,markdown,original_p_algebra
from fullft_contrasts_20261127 import closed_delivery
from storage_20261122 import CONTROL as C,REPO as R,ROOT,write

read=lambda path:json.loads(Path(path).read_text())
POINTS={k:('S_R1_3M' if k==10 else f'S_E1_k{k}_3M') for k in KS}


def identity_comparison(mean):
    return dict(authority=DECISION_AUTHORITY,decision_authority=DECISION_AUTHORITY,
        threshold=max(.01,.05*mean),decision=dict(delta=0.0,ci_lower=0.0,ci_upper=0.0,verdict='tie'),
        identity_contrast=True,source='The same delivered k10 reference minus itself',
        original_draw_arrays_reopened=0,new_bootstrap_draws=0)


def run():
    native_record()
    marker=C/'E1_seed0_decision_delivery_20261127_COMPLETE.json'
    destination=R/'results/s_recipe/E1_seed0_decision_20261127.json'
    if marker.exists():
        print(json.dumps(dict(status='ALREADY_DELIVERED',delivery=read(marker))),flush=True)
        return 0
    if destination.exists() or (R/'configs/s_recipe/E1_k_star.json').exists():
        raise ValueError('Inspect an existing E1 delivery before repeating any decision algebra')
    points={k:closed_delivery(point) for k,point in POINTS.items()}
    frozen_paths={k:R/'results/s_recipe'/('S_R1_s0_3M.json' if k==10 else f'S_E1_k{k}_s0_3M.json') for k in KS}
    missing=[k for k in KS if points[k] is None or not frozen_paths[k].exists()]
    if missing:
        print(json.dumps(dict(status='WAITING_COMPLETE_E1_COMPONENTS',missing_ks=missing,
            k_star=None,new_fits=0,new_bootstrap_draws=0)),flush=True)
        return 0
    ledger=read(C/'execution.json')
    cells={}
    closed={}
    for k in KS:
        frozen=read(frozen_paths[k])
        expected='S_R1_s0_3M' if k==10 else f'S_E1_k{k}_s0_3M'
        if (frozen.get('run')!=expected or frozen.get('seed')!=0 or frozen.get('samples')!=3000000
                or frozen.get('layer')!=6 or frozen.get('source_training_budget',3000000)!=3000000
                or frozen.get('status')!=('COMPLETE' if k==10 else 'FROZEN_COMPLETE_FULL_FT_PENDING')
                or (k!=10 and (frozen.get('k')!=k or frozen.get('reference_run')!='S_R1_s0_3M'))
                or any(not frozen['readouts'][name].get('complete')
                    or frozen['readouts'][name].get('bootstrap_samples')!=1000
                    or frozen['readouts'][name].get('bootstrap_defined')!=1000 for name in ('R1','R3'))):
            raise ValueError('Exact delivered independent3M layer6 frozen source required')
        if k!=10:
            parent_path=Path(frozen['reporting_execution']['native_record'])
            parent=read(parent_path)
            if (parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
                    or read(parent_path.with_name('command_exit.json')).get('exit_code')!=0
                    or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
                raise ValueError('The original frozen-component reporting producer has not closed')
        delivery,cache=points[k]
        binding=delivery['source_binding']
        if (binding['run']!=expected or binding['samples']!=3000000
                or binding['source_training_budget']!=3000000):
            raise ValueError('E1 cannot use any9M trajectory prefix')
        fits=[]
        fit_configurations=[]
        for item in delivery['fits']:
            rows=[row for row in ledger['statistics'].values()
                if row.get('lifecycle_record')==item['lifecycle_record']
                and row.get('mode') in ('finetune','finetune_native') and row.get('resource_closed')
                and row.get('status')=='COMPLETE']
            if len(rows)!=1:raise ValueError('The exact completed fit source is ambiguous or missing')
            fits.append(read(rows[0]['configuration']))
            fit_configurations.append(rows[0]['configuration'])
        means={name:frozen['readouts'][name]['mean_normalized_improvement'] for name in ('R1','R3')}
        closed[k]=({name:identity_comparison(means[name]) for name in ('R1','R3')} if k==10
            else frozen['paired_frozen_vs_k10'])
        cells[k]=dict(native=read(frozen['source_configuration']),evaluation=frozen,
            summary=read(frozen['source_summary']),fits=fits,producer_closure_complete=True,
            frozen_means=means,full=read(cache),full_group=POINTS[k],
            sources=dict(frozen_delivery=str(frozen_paths[k]),full_delivery=str(
                R/'results/s_recipe/full_finetune'/(POINTS[k]+'.json')),
                retained_full_primary_delivery=str(cache),fit_configurations=fit_configurations))
    result=decide(dict(ready=True,authority=AUTHORITY),cells,original_p_algebra(ROOT/'MFM_p_recipe'),
        closed_frozen_comparisons=closed)
    result.update(reporting_execution=execution_fields(),original_frozen_score_files_reopened=0,
        original_prediction_files_read=0,full_components_from_closed_retained_deliveries=True)
    write(destination,result)
    write(R/'configs/s_recipe/E1_k_star.json',result)
    (R/'docs/s_recipe/E1_CONFORMERS.md').write_text(markdown(result))
    path=R/'docs/interfaces/STATUS.md'
    text=path.read_text()
    heading='## S E1：本线seed0构象数判定闭合（2026-11-27执行入口）'
    if heading in text:raise ValueError('Inspect an existing E1 notice before adding a duplicate')
    choice=(f"暂选k={result['provisional_k_star']}，触发的seed1确认尚待，本线k*未冻结"
        if result['conditional_seed1_required'] else f"本线k*={result['k_star']}")
    notice=('\n\n'+heading+'\n\n独立3M、seed0，各格正式层6冻结读出与四任务×三微调种子均已闭合。'+choice+
        '。冻结部分直接复用已交付配对结果，full部分仅对原保留seed-mean抽样做代数；没有重抽、重拟合或回读原预测/冻结原始分数。'+
        '按S任务书4.4选两种判定均非LOSS的最小k，R1只作描述。结果见configs/s_recipe/E1_k_star.json与docs/s_recipe/E1_CONFORMERS.md。'+
        '原S配方与两条9M不重开；P/S共同k*取较大者仍须用户确认后写主线。其余A/B/C工作继续。\n')
    path.write_text(text+notice)
    write(marker,dict(status=result['status'],output=str(destination),k_star=result['k_star'],
        provisional_k_star=result['provisional_k_star'],conditional_seed1_required=result['conditional_seed1_required'],
        original_frozen_score_files_reopened=0,new_bootstrap_draws=0))
    print(json.dumps(dict(status=result['status'],k_star=result['k_star'],
        provisional_k_star=result['provisional_k_star'],conditional_seed1_required=result['conditional_seed1_required'])),flush=True)
    return 0
