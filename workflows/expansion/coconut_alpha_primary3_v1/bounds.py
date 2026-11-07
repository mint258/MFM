"""Pure metadata antichain of existing observations; never candidate filtering."""
import collections
import ast
import json
from workflows.expansion.coconut_alpha_cached735_v1 import support as S

WHITELIST = (1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 34, 35, 53)


def summarize(records):
    vectors = {}; rows = set(); counts = collections.Counter()
    for record in records:
        source = record['source']; original_id = record['original_id']
        sid = 'entries:' + original_id + ':' + str(source['copy_block']) + ':' + str(source['source_row_ordinal'])
        S.need(record['original_UNKNOWN_unchanged'] is True and record['strict5_written'] is False,
               'LOWER_BOUND_OBSERVATIONS_NOT_ACCEPTED_ROWS')
        counts['rows'] += 1
        for item in record['variants']:
            vector = item.get('unsanitized_atom_observation', {}).get(
                'positive_known_non_H_atom_lower_bound_observation')
            if not vector: continue
            S.need(all(type(z) is int and 1 <= z <= 118 and z != 1 and type(n) is int and n > 0
                       for z,n in vector), 'ORIGINAL_POSITIVE_NON_H_OBSERVATION_DOMAIN')
            key = tuple(tuple(p) for p in vector)
            S.need(key == tuple(sorted(set(key))), 'SORTED_UNIQUE_VECTOR')
            counts['variant_positive_observations'] += 1; rows.add(sid)
            refs = vectors.setdefault(key, {})
            ref = refs.setdefault(sid, dict(original_id=original_id, source_id=sid,
                source_row_sha256=source['source_row_sha256'], variant_ids=[]))
            ref['variant_ids'].append(item['variant_id'])
    inside = {v:r for v,r in vectors.items() if all(z in WHITELIST for z,n in v)}
    outside = {v:r for v,r in vectors.items() if any(z not in WHITELIST for z,n in v)}
    minimal = []
    for v in sorted(inside, key=lambda v:(sum(n for z,n in v), len(v), v)):
        d = dict(v)
        if not any(all(d.get(z, 0) >= n for z,n in a) for a in minimal): minimal.append(v)
    def report(v, refs): return dict(vector=v, original_source_witnesses=list(refs.values()))
    return dict(schema='COCONUT_CACHED729_LOWER_BOUND_METADATA_ANTICHAIN_V1', counts=dict(counts),
        rows_with_positive_observations=len(rows), unique_vectors=len(vectors),
        original_X_whitelist=list(WHITELIST), in_X_vectors=len(inside), out_of_X_vectors=len(outside),
        global_union_minimal_antichain=[report(v, inside[v]) for v in minimal],
        single_atom_total_count1=[report(v, inside[v]) for v in inside if sum(n for z,n in v) == 1],
        out_of_X_vectors_not_projected_to_smaller_bounds=[report(v,r) for v,r in outside.items()],
        comparison_rule='A_DOMINATES_B_IFF_ALL_COUNTS_OF_A_ARE_LE_COUNTS_OF_B;_OR_UNION_KEEPS_MINIMAL_A',
        production_candidates_read=0, production_filter_ran=False, bounds_accepted=False,
        graph_association_or_scientific_exception_accepted=False)


def from_receipt(plan):
    receipt = S.load(plan['cached735_receipt_reference'])
    S.need(receipt['schema'] == 'COCONUT_ALPHA_CACHED735_PRODUCER_V1'
           and receipt['profile_admission']['job_id'] == '1885150'
           and receipt['profile_admission']['endpoint'] == '218.192.171.238:22'
           and receipt['profile_admission']['uid'] == 1264
           and receipt['result']['original_graph_UNKNOWN735_retained'] is True,
           'ACTUAL_UNACCEPTED_CACHED735_DIAGNOSTIC_PARENT')
    accounting=S.load(plan['cached735_actual_accounting_reference'])
    parents=accounting.get('actual_parents',[accounting.get('actual_parent',{})])
    found=[p for p in parents if str(p.get('JobIDRaw'))=='1885150']
    S.need(accounting['endpoint']=='218.192.171.238:22' and accounting['uid']==1264
           and accounting['query_returncode']==0 and len(found)==1
           and found[0]['State']=='COMPLETED' and found[0]['ExitCode']=='0:0'
           and str(found[0]['UID'])=='1264','CACHED735_ACTUAL_TERMINAL_C0_NOT_SELF_ACCEPTANCE')
    raw_screen=S.read(plan['original_X_screen_reference'],2<<20)
    assignments=[]
    for node in ast.parse(raw_screen).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WHITELIST' for t in node.targets):
            assignments.append(ast.literal_eval(node.value))
    S.need(len(assignments)==1 and set(assignments[0])==set(WHITELIST),
           'ACTUAL_ORIGINAL_X_SCREEN_WHITELIST_SOURCE_AST_NOT_A_NEW_DOMAIN')
    ref = receipt['result']['DATA']; raw = S.read(ref, 64 << 20)
    S.need(raw.endswith(b'\n'), 'CLOSED_CACHED735_JSONL')
    records = [json.loads(line) for line in raw.splitlines()]
    S.need(len(records) == ref['rows'] == 735, 'ALL735_METADATA_NOT_SUBSAMPLE')
    result = summarize(records)
    result['DATA_reference'] = ref; result['producer_receipt_reference'] = plan['cached735_receipt_reference']
    result['actual_accounting_reference']=plan['cached735_actual_accounting_reference']
    result['original_X_screen_reference']=plan['original_X_screen_reference']
    return result
