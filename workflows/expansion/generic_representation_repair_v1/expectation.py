"""Route stored native evidence through the exact original global fallback.

No chemistry call and no relaxation of the eventual full-feature comparison.
"""


def need(value,message):
    if not value:raise ValueError(message)


def generic_key(event):
    original=event['official_MakeScaffoldGeneric']
    if original['status']=='PASS':
        return original['result']['key'],'ORIGINAL_OFFICIAL_GENERIC_SUCCESS_PASSTHROUGH'
    need(original['exception_type']=='AtomValenceException','Only actual generic AtomValence failure has representation candidate authority')
    candidate=event['diagnostic_deferred_sanitize_candidate']
    need(candidate['status']=='PASS' and candidate['heavy_adjacency_and_allC_SINGLE_invariant'] is True,
      'Actual exact native deferred representation proof required')
    return candidate['key'],'WITNESSED_GENERIC_ATOMVALENCE_DEFERRED_REPRESENTATION'


def ring_keys(native):
    fragments=native['ring_fragments'];errors=[]
    for fragment in fragments:
        event=fragment['exact_original_fragment_sanitize']
        if event['status']=='ERROR':
            need(event['exception_type']=='KekulizeException','Original ring compatibility accepts only exact KekulizeException')
            errors.append(dict(fragment_index=fragment['fragment_index'],exception_type=event['exception_type'],
              message=event.get('message'),exact_traceback=event.get('exact_traceback')))
    global_fallback=bool(errors);keys=[];routes=[]
    for fragment in fragments:
        route='generic_stages_on_uncorrupted_fragment' if global_fallback else 'generic_stages_after_original_fragment_sanitize'
        need(route in fragment,'Complete original global ring-route evidence required')
        key,operation=generic_key(fragment[route]);keys.append(key)
        routes.append(dict(fragment_index=fragment['fragment_index'],native_evidence_route=route,
          generic_operation_route=operation,exact_reference_key=key))
    return sorted(keys),dict(global_original_Kekulize_compatibility_fallback=global_fallback,
      original_Kekulize_evidence=errors,all_fragment_routes=routes,
      per_fragment_hybrid_route_used=False,comparison_tolerance_added=False)
