"""Taskbook-v3 downstream decisions from closed paired panel summaries only."""
from __future__ import annotations

from .v3_selection import paired_difference, select_candidate, convergence_budget


def lambda_k(panels):
    """Compare both prescribed settings to default; ties retain default."""
    if set(panels) != {'default', 'lambda03', 'k16'} or any(set(p) != {'S', 'P'} for p in panels.values()):
        raise ValueError('Require exactly default and two prescribed S/P settings')
    comparisons = {name + '_vs_default': paired_difference(panels[name], panels['default'])
                   for name in ('lambda03', 'k16')}
    winners = [name for name in ('lambda03', 'k16') if comparisons[name + '_vs_default']['A_wins']]
    selected = winners[0] if len(winners) == 1 else 'default'
    if len(winners) == 2:
        comparison = paired_difference(panels['lambda03'], panels['k16'])
        comparisons['lambda03_vs_k16'] = comparison
        selected = 'lambda03' if comparison['A_wins'] else 'k16' if comparison['B_wins'] else 'default'
    parameters = {'default': (.1, 8), 'lambda03': (.3, 8), 'k16': (.1, 16)}
    weight, k = parameters[selected]
    return dict(status='LAMBDA_K_SELECTED_FRESH_CONFIRMATION_REQUIRED', selected=selected,
        reconstruction_weight=weight, k=k, comparisons=comparisons,
        tie_rule='retain_default_lambda0.1_k8', module_finally_confirmed=False)


def fresh_confirmation(new, original, provisional_latent):
    if provisional_latent not in ('pma', 'lite_rec') or set(new) != {'S', 'P'}:
        raise ValueError('Only an adopted A1/A3 with both actual fresh S/P results is confirmable')
    comparison = paired_difference(new, original)
    adopted = comparison['A_wins']
    return dict(status='FRESH_CONFIRMATION_COMPLETE', provisional_latent=provisional_latent,
        selected_latent=provisional_latent if adopted else 'none', new_module_wins=adopted,
        comparison=comparison, new_primary='R2z', original_primary='R3',
        retained_original_for_simplicity=not adopted, module_finally_confirmed=adopted,
        report_in_daily_first_line_if_original_retained=not adopted,
        report_only_finetunes_required=True)


def candidate_set(panels, simplicity_order, *, comparison):
    required = {
        'views': {'S', 'SDP'}, 'heads': {'P', 'D', 'SDP'},
        'pooling': {'P'}, 'learning_rate': {'S', 'P'},
        'batch': {'S', 'P'}, 'schedule': {'S', 'P'}}
    if comparison not in required:
        raise ValueError('Bind the registered follow-on comparison')
    if (not panels or any(set(value) != required[comparison] for value in panels.values())
            or len(simplicity_order) != len(set(simplicity_order))
            or set(panels) != set(simplicity_order)):
        raise ValueError('Every declared candidate and required condition must be complete')
    fixed_orders = {'views': ['two', 'three'], 'heads': ['H1', 'H2', 'H3'],
                    'pooling': ['registry', 'learned']}
    if comparison in fixed_orders and list(simplicity_order) != fixed_orders[comparison]:
        raise ValueError('Keep the taskbook simplicity order')
    return dict(status='CANDIDATE_GROUP_SELECTED', comparison=comparison,
        **select_candidate(panels, simplicity_order))


def full_budget(curves):
    if set(curves) != {'S', 'P'}:
        raise ValueError('Both full D6 S/P curves are required')
    checkpoints = {1_000_000, 2_000_000, 4_000_000, 8_000_000, 16_000_000, 32_000_000, 64_000_000}
    if any(set(curve) - checkpoints for curve in curves.values()):
        raise ValueError('Use only the registered doubling endpoints')
    ordered = sorted(checkpoints)
    if any(set(curve) != set(ordered[:len(curve)]) for curve in curves.values()):
        raise ValueError('A sequential curve prefix is required to identify the earliest plateau')
    conditions = {name: convergence_budget(curve) for name, curve in curves.items()}
    known = all(value['budget'] is not None for value in conditions.values())
    return dict(status='B_STAR_OBSERVED' if known else 'B_STAR_UNDETERMINED',
        B_star=max(value['budget'] for value in conditions.values()) if known else None,
        conditions=conditions, schedule_budget=64_000_000,
        observation_complete=all(value['status'] in ('OBSERVED_PLATEAU',
            'CEILING_REACHED_WITHOUT_OBSERVED_PLATEAU') for value in conditions.values()),
        all_ceiling_checkpoints_available=all(set(curve) == checkpoints for curve in curves.values()),
        endpoint='before_doubling', ceiling_is_not_plateau=True)
