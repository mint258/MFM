"""Small exact-key source disposition and SQL; no chemistry or composition veto."""
import hashlib
import json
import re

KEY = re.compile(r'[A-Z]{14}-[A-Z]{10}-[A-Z]')
FIELDS = {'source_id', 'role', 'subdataset', 'inchikeys', 'non_h_composition'}
POLICY = {
    'identity_kinds': ['full', 'wp5'],
    'wp5_definition': 'InChIKey[:14]+":"+InChIKey[-1]',
    'removed_subdatasets': {'moleculenet': ['PDBbind']},
    'unresolved_structure': 'NO_STRUCTURAL_VETO_AND_EXCLUDED_FROM_DOWNSTREAM_EVALUATION',
    'composition_veto': False, 'lower_bound_veto': False, 'wildcard_veto': False,
}
REQUIRED = {'v1_all_roles_and_embargo', 'expansionrx', 'som_cyp', 'som_az', 'qm7', 'qm9',
            'tdc_admet', 'moleculenet', 'marcel_drugs75k', 'marcel_kraken', 'coconut'}


def need(value, message):
    if not value:
        raise ValueError(message)


def wp5(key):
    need(type(key) is str and KEY.fullmatch(key) is not None, 'Actual valid full InChIKey required')
    return key[:14] + ':' + key[-1]


def disposition(dataset, row, unresolved_ids=frozenset()):
    need(dataset in REQUIRED and type(row) is dict and set(row) <= FIELDS,
         'Only original strict identity fields; no targets or new chemistry')
    need(type(row.get('source_id')) is str and row['source_id'] and row.get('role'),
         'Exact source ID and original role required')
    keys = row.get('inchikeys', [])
    need(type(keys) is list and len(keys) == len(set(keys)), 'Original distinct full-key list required')
    for key in keys:
        wp5(key)
    if dataset == 'moleculenet' and row.get('subdataset') == 'PDBbind':
        return 'PDBBIND_NOT_IN_DOWNSTREAM_PLAN', []
    if (dataset, row['source_id']) in unresolved_ids:
        return 'AUDITED_UNRESOLVED_STRUCTURE_NO_VETO_OR_EVALUATION', []
    if not keys:
        return 'NO_FULL_KEY_NO_STRUCTURAL_VETO_OR_EVALUATION', []
    # Original composition fields are deliberately never interpreted or indexed.
    return 'EXACT_KEYED', [(kind, value, dataset) for key in keys
                           for kind, value in (('full', key), ('wp5', wp5(key)))]


def candidate_census_sql():
    return '''SELECT count(*), count(DISTINCT cid), count(DISTINCT full_key),
 count(*) FILTER (WHERE cid IS NULL OR full_key IS NULL OR wp5_key IS NULL
 OR NOT regexp_full_match(full_key,'[A-Z]{14}-[A-Z]{10}-[A-Z]')
 OR wp5_key<>substr(full_key,1,14)||':'||right(full_key,1)) FROM candidates'''


def eligible_sql():
    # ANTI JOIN retains every original column, never multiplies identity rows.
    return '''SELECT c.* FROM candidates c
 ANTI JOIN keys_full f ON c.full_key=f.key
 ANTI JOIN keys_wp5 w ON c.wp5_key=w.key'''


def locator(source, reference, replica, ordinal, offset, raw, row):
    return dict(dataset=source['dataset'], source_id=row['source_id'], role=row['role'],
                subdataset=row.get('subdataset', ''), source_reference=reference,
                actual_replica_reference=replica, row_ordinal_1based=ordinal,
                source_byte_offset=offset, source_record_bytes=len(raw),
                source_record_sha256=hashlib.sha256(raw).hexdigest())


def json_line(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode() + b'\n'
