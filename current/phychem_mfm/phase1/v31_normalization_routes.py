"""Translate published dataset/physical-target routes without fitting statistics."""
from copy import deepcopy

SCHEMA = 'WINDOW2_D4_MODEL_NORMALIZATION_ROUTES_V1'


def resolve_normalization_routes(payload, fields, *, dataset='P_D'):
    """Return the existing field-key interface using only explicit ready routes.

    A flat mapping remains supported for existing callers. Pending/disabled
    routes never acquire a fabricated center, scale or another dataset's fit.
    """
    if payload.get('schema') != SCHEMA:
        if 'datasets' in payload:
            raise ValueError('Unknown D4 normalization route schema')
        return payload
    selected = payload.get('datasets', {}).get(dataset, {})
    if selected.get('status') != 'BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS':
        raise ValueError('D4 independent dataset parameters are not ready: ' + dataset)
    targets = selected.get('targets', {})
    result = {}
    for field in fields:
        name = field.get('name') or field['field_key']
        key = field.get('field_key', name)
        direct = targets.get(field.get('target_id'), {})
        candidates = [route for route in targets.values()
                      if key in route.get('members', [])
                      and route.get('status') != 'RAW_CONTAINER_STATISTICS_ONLY']
        if key in direct.get('members', []) and direct.get('status') != 'RAW_CONTAINER_STATISTICS_ONLY':
            route = direct
        elif len(candidates) == 1:
            route = candidates[0]
        else:
            raise ValueError('D4 field route missing or ambiguous: ' + dataset + '/' + key)
        if route.get('normalizer_ready') is not True or route.get('status') != 'NORMALIZER_AVAILABLE':
            raise ValueError('D4 field parameters are not ready: ' + key + ': ' + str(route.get('status')))
        specification = {parameter: deepcopy(route[parameter]) for parameter in ('center', 'scale')}
        specification.update(fit_role='TRAIN', dataset=dataset,
                             target_id=route['target_id'], training_labels_clipped=False,
                             source_route_status=route['status'],
                             loss_enabled=route.get('original_loss_enabled', True),
                             source_loss_policy=deepcopy(route.get('source_loss_policy', {})))
        if 'element_reference' in route:
            specification['element_reference'] = deepcopy(route['element_reference'])
        result[name] = specification
    return result


def inherit_source_loss_policy(payload, fields, *, dataset='P_D'):
    """Selection, numerical binding and physical-loss exposure are independent."""
    if payload.get('schema') != SCHEMA:
        return
    targets = payload.get('datasets', {}).get(dataset, {}).get('targets', {})
    for field in fields:
        key = field.get('field_key', field['name'])
        routes = [r for r in targets.values() if key in r.get('members', [])
                  and r.get('status') != 'RAW_CONTAINER_STATISTICS_ONLY']
        disabled = [r for r in routes if r.get('original_loss_enabled') is False]
        if disabled:
            field['loss_enabled'] = False
            field['source_loss_policy'] = deepcopy(disabled[0].get('source_loss_policy', {}))
