"""Original V3 exclusion function ASTs; independent Alpha global bindings."""

import json,re

from types import SimpleNamespace

from ..alpha_runtime_v1.common import need as require

KEY_RE=re.compile(r'[A-Z]{14}-[A-Z]{10}-[A-Z]')

X02_ATOMIC_NUMBERS=frozenset([1,5,6,7,8,9,14,15,16,17,34,35,53])

REQUIRED = {"v1_all_roles_and_embargo", "expansionrx", "som_cyp", "som_az", "qm7", "qm9",
            "tdc_admet", "moleculenet", "marcel_drugs75k", "marcel_kraken", "coconut"}

legacy=SimpleNamespace(REQUIRED=REQUIRED)

INDEX_SCHEMA='expansion_exclusion_index_with_constraints_v3'

def wp5_key(key):
    require(isinstance(key, str) and KEY_RE.fullmatch(key) is not None, "Invalid full InChIKey")
    return key[:14] + ":" + key[-1]


def contamination(row, db):
    checks = [("full", row["full_key"]), ("wp5", wp5_key(row["full_key"])), ("composition", row["non_h_composition"])]
    result = set()
    for kind, key in checks:
        result.update((kind, item[0]) for item in db.execute("SELECT dataset FROM excluded WHERE kind=? AND key=?", (kind, key)))
    return sorted(result)


contamination_exact=contamination

def vector(value):
    require(isinstance(value, list) and value and
            all(isinstance(p, list) and len(p) == 2 and type(p[0]) is int and 2 <= p[0] <= 118
                and type(p[1]) is int and p[1] > 0 for p in value) and
            [p[0] for p in value] == sorted({p[0] for p in value}), 'Positive sorted non-H atom bound required')
    return dict(value)


def candidate_domain(row):
    value = json.loads(row['non_h_composition'])
    counts = vector(value)
    require(row['non_h_composition'] == json.dumps(value, separators=(',', ':')) and
            row['elements'] == sorted(counts) and set(counts) <= set(X02_ATOMIC_NUMBERS),
            'Every actual candidate must satisfy frozen original X02 composition domain')
    return counts


def rules(db):
    result = []
    for rid, dataset in db.execute('SELECT rule_id,dataset FROM constraints ORDER BY rule_id'):
        bound = [[z, n] for z, n in db.execute('SELECT z,n FROM constraint_atoms WHERE rule_id=? ORDER BY z', (rid,))]
        result.append((rid, dataset, vector(bound)))
    return result


def contamination(row, db, prepared_rules=None):
    counts = candidate_domain(row)
    hits = set(contamination_exact(row, db))
    for rid, dataset, bound in rules(db) if prepared_rules is None else prepared_rules:
        if all(counts.get(z, 0) >= n for z, n in bound.items()):
            hits.add(('composition_lower_bound:' + rid, dataset))
    return sorted(hits)


def index_header(index):
    require(index['schema'] == INDEX_SCHEMA and index['status'] == 'COMPLETE' and
            set(index['sources']) == legacy.REQUIRED and
            index['all_physical_source_rows_covered'] is True and
            index['original_graph_unknowns_retained'] is True and
            index['constraint_source_datasets'] == ['coconut', 'moleculenet'],
            'Actual complete all11 V3 index required; legacy or metadata-only proof is insufficient')
    return index
