"""Opt-in S E1 reporting from closed original primaries, using P algebra.

No training, prediction fitting, molecular resampling or checkpoint loading.
The caller supplies already closed producer metadata and original score JSON.
"""
import importlib.util
import math
from copy import deepcopy
from pathlib import Path
import sys
import types

AUTHORITY = 'docs/s_recipe/USER_DIRECTIVE_20261123.md'
TIMEBOX = 'docs/interfaces/TIMEBOX_RULE_20261125.md'
KS = (1, 2, 5, 10)
TASKS = ('qm9.U0_atom', 'qm9.homo', 'exp.LogD', 'exp.LogS')
DECISION_AUTHORITY = 'docs/s_recipe/TASKBOOK.md section4.4 (frozen S rule)'


def apply_s_verdict(comparison):
    """Keep P's retained-draw arithmetic; apply the already frozen S verdict.

    S LOSS is CI upper<0 without an additional effect-size requirement.
    """
    value=deepcopy(comparison)
    decision=value['decision']
    value.setdefault('retained_draw_provider_authority',value.get('authority'))
    value.setdefault('original_provider_verdict',decision['verdict'])
    decision['verdict']=('win' if decision['ci_lower']>0 and decision['delta']>=value['threshold']
        else 'loss' if decision['ci_upper']<0 else 'tie')
    value.update(authority=DECISION_AUTHORITY,decision_authority=DECISION_AUTHORITY)
    return value


def original_p_algebra(p_repo):
    """Load the actual P functions without replacing S's cached modules."""
    p_repo = Path(p_repo)
    package_name = '_s_e1_original_p_20261126'
    package = types.ModuleType(package_name)
    package.__path__ = [str(p_repo/'current/phychem_mfm/phase1')]
    previous_package = sys.modules.get(package_name)
    previous = {key: sys.modules.get(key) for key in
                ('finetune_statistics', 'phychem_mfm.phase1.p_recipe_seed_policy')}
    sys.modules[package_name] = package

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    try:
        policy = load(package_name+'.p_recipe_seed_policy',
                      p_repo/'current/phychem_mfm/phase1/p_recipe_seed_policy.py')
        statistics = load(package_name+'.statistics',
                          p_repo/'tools/p_recipe/finetune_statistics.py')
        aliases = {'finetune_statistics': statistics,
                   'phychem_mfm.phase1.p_recipe_seed_policy': policy}
        sys.modules.update(aliases)
        return load(package_name+'.e1_decision', p_repo/'tools/p_recipe/e1_decision.py')
    finally:
        for key, value in previous.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
        for key in tuple(sys.modules):
            if key.startswith(package_name+'.'):
                sys.modules.pop(key)
        if previous_package is None:
            sys.modules.pop(package_name, None)
        else:
            sys.modules[package_name] = previous_package


def validate_source(k, native, evaluation, summary, fits):
    """Bind own3M sources; a9M trajectory's3M snapshot is ineligible."""
    expected_run = 'S_R1_s0_3M' if k == 10 else f'S_E1_k{k}_s0_3M'
    if (k not in KS or native.get('run') != expected_run
            or native.get('samples') != 3000000 or native.get('seed') != 0
            or native.get('conformer_cap', 10) != k or native.get('budget_curve')):
        raise ValueError('E1 requires the registered independent3M seed0 source')
    if (evaluation.get('samples') != 3000000
            or evaluation.get('source_training_budget', 3000000) != 3000000
            or evaluation.get('source_run', evaluation.get('run')) != expected_run
            or evaluation.get('layer', 6) != 6
            or evaluation.get('representation', 'H0') != 'H0'
            or evaluation.get('readout_seed', 0) != 0):
        raise ValueError('Frozen E1 source must be own3M, layer6 H0, readout seed0')
    if (summary.get('status') != 'COMPLETE' or summary.get('samples') != 3000000
            or summary.get('updates') != 93750):
        raise ValueError('Original3M endpoint is not closed')
    checkpoint = str(Path(native['output'])/'samples_3000000.pt')
    seen = []
    for fit in fits:
        binding = fit['source_binding']
        if (fit.get('ready') is not True or fit.get('mode') != 'full'
                or fit.get('pretraining_seed') != 0
                or binding.get('run') != expected_run
                or binding.get('checkpoint') != checkpoint
                or binding.get('samples') != 3000000
                or binding.get('source_training_budget') != 3000000):
            raise ValueError('Full FT must bind the same independent3M source')
        seen.append((fit['task'], fit['seed']))
    if len(seen) != 12 or set(seen) != {(t, s) for t in TASKS for s in (0, 1, 2)}:
        raise ValueError('Exactly four tasks and three FT seeds are required')


def validate_missing(k, timebox):
    if k == 10:
        raise ValueError('The original k10 reference cannot be missing')
    if (timebox.get('authority') != TIMEBOX
            or timebox.get('failure_class') != 'scientific_method'
            or not timebox.get('same_root_cause')
            or not timebox.get('root_cause')
            or not (timebox.get('unsuccessful_repairs', 0) >= 2
                    or timebox.get('active_diagnosis_repair_seconds', 0) >= 14400)):
        raise ValueError('Engineering/queue failures remain pending under Nov25 rule')


def _frozen_comparison(k,readout,cell,baseline,algebra,closed):
    if closed is None:
        return apply_s_verdict(algebra.compare_frozen(cell['frozen'],baseline['frozen'],readout))
    value=closed[k][readout]
    decision=value['decision']
    expected=cell['frozen_means'][readout]-baseline['frozen_means'][readout]
    numbers=[decision[key] for key in ('delta','ci_lower','ci_upper')]+[value['threshold'],
        cell['frozen_means'][readout],baseline['frozen_means'][readout]]
    if (value.get('authority')!=DECISION_AUTHORITY or not all(math.isfinite(x) for x in numbers)
            or abs(decision['delta']-expected)>1e-12 or value['threshold']<=0
            or decision['ci_lower']>decision['ci_upper']
            or (k==10 and any(decision[key]!=0 for key in ('delta','ci_lower','ci_upper')))):
        raise ValueError('Delivered frozen comparison differs from its exact original k10 source')
    return apply_s_verdict(value)


def decide(configuration, cells, algebra, *, closed_frozen_comparisons=None):
    """Pure decision; selected WIN remains provisional until seed1 confirms."""
    if configuration.get('ready') is not True or configuration.get('authority') != AUTHORITY:
        raise ValueError('S E1 reporting defaults off until actual primaries close')
    if set(cells) != set(KS):
        raise ValueError('All four registered cells must be accounted for')
    if cells[10].get('missing'):
        raise ValueError('The original k10 reference cannot be missing')
    if (closed_frozen_comparisons is not None and set(closed_frozen_comparisons)
            != {k for k in KS if not cells[k].get('missing')}):
        raise ValueError('Delivered frozen components must cover the exact nonmissing E1 cells')
    rows = {}
    for k in KS:
        cell = cells[k]
        if cell.get('missing'):
            validate_missing(k, cell['timebox'])
            rows[k] = dict(k=k, missing=True, timebox=cell['timebox'])
            continue
        validate_source(k, cell['native'], cell['evaluation'], cell['summary'], cell['fits'])
        if cell.get('producer_closure_complete') is not True:
            raise ValueError('Original training, readout and full FT producers must close first')
        baseline = cells[10]
        rows[k] = dict(k=k,
            frozen_R1=_frozen_comparison(k,'R1',cell,baseline,algebra,closed_frozen_comparisons),
            frozen_R3=_frozen_comparison(k,'R3',cell,baseline,algebra,closed_frozen_comparisons),
            full=apply_s_verdict(algebra.compare_full(cell['full'], baseline['full'],
                                     cell['full_group'], baseline['full_group'])),
            full_task_rows=[r for r in cell['full']['rows'] if r['condition'] == cell['full_group']],
            sources=cell['sources'])
    choice = algebra.choose_k(rows)
    required = choice['conditional_seed1_required_for_adoption']
    return dict(schema='S_E1_SEED0_DECISION_20261126_V1', authority=AUTHORITY,
        status='WAITING_CONDITIONAL_SEED1' if required else 'COMPLETE',decision_authority=DECISION_AUTHORITY,
        k_star=None if required else choice['provisional_k_star'],
        provisional_k_star=choice['provisional_k_star'],
        conditional_seed1_required=required, conditional_seed1_complete=False,
        shared_P_S_adoption_requires_user_confirmation=True,
        results=[rows[k] for k in KS], original_draws_resampled=0,
        new_bootstrap_draws=0, new_fits=0,
        frozen_components_reused_from_delivery=closed_frozen_comparisons is not None,
        interpretation='Local S choice; original3M recipe decisions remain unchanged')


def markdown(result):
    lines = ['# S E1 构象数结果', '',
        '独立3M、seed0，第6层H0；k=10复用S-R1原3M。Δ与CI由P既有函数读取原1000次配对抽样计算；判定沿用S任务书4.4，CI上界<0即LOSS。', '',
        '| k | frozen R1 Δ / 95% CI / τ / 判定 | frozen R3 Δ / 95% CI / τ / 判定 | full FT Δ / 95% CI / τ / 判定 |',
        '| --- | --- | --- | --- |']
    def format_comparison(value):
        d = value['decision']
        return f"{d['delta']:.6f} / [{d['ci_lower']:.6f}, {d['ci_upper']:.6f}] / {value['threshold']:.6f} / {d['verdict'].upper()}"
    for row in result['results']:
        if row.get('missing'):
            lines.append(f"| {row['k']} | 同根因科学失败达到时间盒，缺失 | 缺失 | 缺失 |")
        else:
            lines.append(f"| {row['k']} | {format_comparison(row['frozen_R1'])} | {format_comparison(row['frozen_R3'])} | {format_comparison(row['full'])} |")
    if result['conditional_seed1_required']:
        lines += ['', f"暂选k={result['provisional_k_star']}，尚待触发的seed1确认；k*未冻结。"]
    else:
        lines += ['', f"S本线k*={result['k_star']}。"]
    lines += ['', 'P/S共同k*仍待用户确认。本结果不改写原3M配方判定；3M下每分子平均约2.5次曝光。', '']
    return '\n'.join(lines)
