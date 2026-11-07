"""Explicit original-X H-only domain extension; constraint vectors stay strict."""
from ..alpha_runtime_v1.common import need
from . import filter_core as original_core
from . import science_v3 as original

EXTENSION = 'ORIGINAL_X_VALID_EMPTY_NON_H_CANDIDATE_V1'


def candidate_domain(row):
    if row['non_h_composition'] == '[]':
        need(row['elements'] == [] and type(row['heavy_atoms']) is int and row['heavy_atoms'] == 0, 'Only a canonical original-X H-only candidate may have an empty non-H vector')
        return {}
    return original.candidate_domain(row)


def contamination(row, db, prepared_rules=None):
    # Existing nonempty candidate behavior calls the unchanged original function.
    if row['non_h_composition'] != '[]':
        return original.contamination(row, db, prepared_rules)
    counts = candidate_domain(row); hits = set(original.contamination_exact(row, db))
    for rid, dataset, bound in original.rules(db) if prepared_rules is None else prepared_rules:
        need(bound and all(n > 0 for n in bound.values()), 'Source constraints remain nonempty positive atom bounds')
        if all(counts.get(z, 0) >= n for z, n in bound.items()):
            hits.add(('composition_lower_bound:' + rid, dataset))
    return sorted(hits)


class ExtendedDomainConnection:
    """Adapt only the original validation SQL; all filter/output SQL is intact."""
    def __init__(self, db):self.db = db
    def __getattr__(self, name):return getattr(self.db, name)
    def execute(self, sql, *args, **kwargs):
        if sql.startswith('CREATE VIEW vectors AS SELECT cid,full_key,wp5_key,non_h_composition,elements,'):
            sql = sql.replace('non_h_composition,elements,', 'non_h_composition,elements,heavy_atoms,', 1)
        elif sql.startswith('SELECT count(*) FROM vectors WHERE '):
            need(sql.count('OR len(v)=0') == 1 and sql.count('OR NOT coalesce(list_bool_and') == 1 and sql.count(',false) OR wp5_key') == 1, 'Original validation SQL changed; review the explicit H-only extension')
            sql = sql.replace('OR len(v)=0', 'OR (len(v)=0 AND (heavy_atoms IS NULL OR heavy_atoms<>0 OR elements<>[]))', 1)
            sql = sql.replace('OR NOT coalesce(list_bool_and', 'OR (len(v)>0 AND NOT coalesce(list_bool_and', 1)
            sql = sql.replace(',false) OR wp5_key', ',false)) OR wp5_key', 1)
        return self.db.execute(sql, *args, **kwargs)


def filter_core(*args, **kwargs):
    connection = original_core.connection
    original_core.connection = lambda *a, **k: ExtendedDomainConnection(connection(*a, **k))
    try:return original_core.filter_core(*args, **kwargs)
    finally:original_core.connection = connection
