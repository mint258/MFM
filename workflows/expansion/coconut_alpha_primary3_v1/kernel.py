"""Borrow exact pinned cached735 original-object loader and explicitly new MOL seam."""
from workflows.expansion.coconut_alpha_cached735_v1 import kernel as K, support as S
from workflows.expansion.coconut_alpha_cached735_v1.extract import text_reference


def initialize(plan):
    proof = K.initialize(plan)
    # Populate only the worker's runtime state required by the unchanged original
    # source-formula function; never change its code/defaults or acceptance policy.
    K.STATE['original'].STATE.update(Chem=K.STATE['Chem'], native=K.STATE['projection'].native_composition)
    objects = dict(proof['objects'])
    f = K.STATE['original'].formula
    objects['original_formula'] = dict(qualified_name=f.__module__ + '.' + f.__qualname__,
        filename=f.__code__.co_filename, first_line=f.__code__.co_firstlineno)
    return dict(proof, objects=objects, source_formula_observations_accepted=False)


def work(item):
    source, primary = item
    variants = []
    for v in primary.pop('variants'):
        observation = K.observe_variant(dict(variant_id=v['name'], representation=v['kind'], text=v['text'],
            text_reference=text_reference(v['text']), source_pointer=v['locator'],
            decoded_container='EXACT_UPSTREAM_PRIMARY_SOURCE',
            upstream_source_reference=v['upstream_file_reference'],
            original_SQL_row_reference=source['opaque_original_row_reference']))
        variants.append(observation)
    formulas = []
    for value in primary.pop('formulas'):
        try: observation = K.STATE['original'].formula(value['value'])
        except Exception as exc: observation = dict(state='DIAGNOSTIC_EXCEPTION_UNKNOWN_RETAINED',
                                                    exception=K.exception(exc), composition=None)
        formulas.append(dict(value, text_reference=text_reference(value['value']),
            original_formula_function_observation=observation, composition_accepted=False,
            source_graph_charge_stereo_proven=False))
    normalized = K.STATE['norm'].normalize(source['source'], K.STATE['functions'])
    S.need(normalized['source'] == source['source'], 'ORIGINAL_SQL_ROW_NOT_SYNTHETICALLY_REPLACED')
    return dict(primary, original_SQL_source=source['source'],
        original_opaque_row_reference=source['opaque_original_row_reference'],
        variants=variants, formulas=formulas, original_normalize_function_observation=normalized,
        original_UNKNOWN_unchanged=True, original_SQL_or_cached_fields_changed=False,
        upstream_source_association_observed=True, upstream_graph_association_accepted=False,
        new_authoritative_keys=False, formula_compositions_accepted=False,
        strict5_written=False, all11_ready=False, global_pool_release=False)
