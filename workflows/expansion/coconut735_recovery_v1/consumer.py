"""Constraint-aware exclusion primitives for actual all11 V3 pool execution.

The full-key/WP5/exact-composition function objects remain the original ones.
Only named source-bound positive atom lower bounds add conservative vetoes.
No downstream properties or scores enter this module.
"""
import json
from .. import decontamination as legacy
from .kernel import require, X02_ATOMIC_NUMBERS

identity_keys = legacy.identity_keys
contamination_exact = legacy.contamination
INDEX_SCHEMA = 'expansion_exclusion_index_with_constraints_v3'


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


def install_tables(db):
    db.execute('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset)) WITHOUT ROWID')
    db.execute('CREATE TABLE constraints(rule_id TEXT PRIMARY KEY,dataset TEXT,binding TEXT NOT NULL) WITHOUT ROWID')
    db.execute('CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER,PRIMARY KEY(rule_id,z)) WITHOUT ROWID')


def insert_constraint(db, rule, *, expected_dataset, accepted_physical_bindings):
    require(rule['kind'] == 'NON_H_ATOM_COUNT_LOWER_BOUND' and
            rule['dataset'] == expected_dataset in ('moleculenet', 'coconut') and
            isinstance(rule['rule_id'], str) and rule['rule_id'] and
            rule['binding'] in accepted_physical_bindings,
            'Each rule must bind actual independently accepted source evidence')
    bound = vector(rule['bound'])
    require(set(bound) <= set(X02_ATOMIC_NUMBERS), 'Out-of-domain source is disjoint, not an invented candidate rule')
    db.execute('INSERT INTO constraints VALUES(?,?,?)',
               (rule['rule_id'], expected_dataset, json.dumps(rule['binding'], sort_keys=True)))
    db.executemany('INSERT INTO constraint_atoms VALUES(?,?,?)',
                   [(rule['rule_id'], z, n) for z, n in bound.items()])


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
