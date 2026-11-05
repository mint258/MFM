"""One complete scan; exact canonical composition key equality and overlapping source coverage."""


def query(db,compositions,expected):
    if len(compositions)!=3 or len({s for s,c in compositions})!=3:
        raise ValueError('All three unique physical composition source IDs')
    expressions=['CASE WHEN non_h_composition=? THEN '+str(1<<i)+' ELSE 0 END'
                 for i in range(3)]
    grouped=db.execute('SELECT ('+'+'.join(expressions)+') AS matched_mask,count(*) AS rows '
        'FROM candidates GROUP BY matched_mask ORDER BY matched_mask',[c for s,c in compositions]).fetchall()
    total=sum(n for mask,n in grouped);hit=sum(n for mask,n in grouped if mask)
    if total!=expected or not 0<=hit<total or any(not 0<=mask<8 or n<1 for mask,n in grouped):
        raise ValueError('Whole corrected candidate census and non-universal exact-composition union')
    per=[dict(source_id=s,composition_key=c,matching_candidates=sum(n for mask,n in grouped if mask&(1<<i)))
         for i,(s,c) in enumerate(compositions)]
    return dict(complete_candidate_pool=True,input_unique_molecules=total,
        excluded_by_coconut735_exact_compositions=hit,eligible_after_coconut735_rules=total-hit,
        per_source=per,grouped_source_match_masks=[dict(mask=m,rows=n) for m,n in grouped],
        overlaps_counted_once_in_union=sum(r['matching_candidates'] for r in per)-hit,
        no_universal_or_empty_bound=True,lower_bound_rules=0,scope_disposition_ids_are_chemical_vetos=False,
        impact_scope='ACCEPTED_COCONUT735_EXACT_COMPOSITION_RULES_ONLY',
        all11_filter_performed=False,eligible_after_all11_exclusions=None,full_pool_or_index_release=False)
