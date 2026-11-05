"""Only exact JSON decoding and literal source observations; no chemistry."""
import hashlib
import json
from .support import need

SECTIONS = ('original', 'standardized', 'parent')
SQL_FIELDS = ('canonical_smiles', 'standardized_canonical_smiles', 'parent_canonical_smiles')
PLACEHOLDER = 'Not computed, enable for computing'


def text_reference(text):
    if text is None:
        return dict(state='NULL', bytes_utf8=None, sha256=None)
    need(isinstance(text, str), 'ORIGINAL_STRING_OR_NULL_ONLY')
    raw = text.encode('utf-8')
    return dict(state='EMPTY' if text == '' else 'PLACEHOLDER' if text == PLACEHOLDER
                else 'PRESENT_WHOLE_STRING', bytes_utf8=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def lexical(text):
    if not isinstance(text, str):
        return dict(state='ABSENT')
    return dict(state='WHOLE_LITERAL_TEXT_NOT_REPAIRED', chars=len(text),
                preview_first_240=text[:240], preview_truncated=len(text) > 240,
                comma_positions=[i for i, x in enumerate(text) if x == ','][:32],
                quote_positions=[i for i, x in enumerate(text) if x == '"'][:32],
                whitespace_positions=[i for i, x in enumerate(text) if x.isspace()][:32],
                URL_marker_present=('http://' in text or 'https://' in text),
                prefix_or_CSV_cell_extracted=False, source_string_changed=False)


def extract(record):
    need(record['original_UNKNOWN_unchanged'] is True
         and record['new_authoritative_keys'] is False
         and record['native_formula_exclusion_accepted'] is False,
         'ORIGINAL_UNKNOWN_NOT_UPGRADED')
    source = record['source']; identity = json.loads(source['identity_fields_json'])
    need(source['source_table'] == 'entries' and source['copy_block'] == 1,
         'ORIGINAL_ENTRIES_PHYSICAL_SOURCE')
    ref = record['opaque_original_row_reference']
    need(ref['bytes'] == source['source_bytes'] and ref['sha256'] == source['source_row_sha256'],
         'SOURCE_ROW_AND_OPAQUE_REFERENCE_MATCH')
    native = record['supplemental_original_fields']
    cm = None if native['cm_data'] in (None, '') else json.loads(native['cm_data'])
    meta = None if native['meta_data'] in (None, '') else json.loads(native['meta_data'])
    variants = []

    def add(name, kind, value, container, pointer):
        variants.append(dict(variant_id=name, representation=kind, text=value,
                             source_pointer=pointer, decoded_container=container,
                             text_reference=text_reference(value),
                             opaque_original_row_reference=ref,
                             physical_source_locator={k:source[k] for k in
                                 ('source_table', 'copy_block', 'source_row_ordinal',
                                  'source_offset', 'source_bytes', 'source_row_sha256')}))

    for name in SQL_FIELDS:
        add('SQL/' + name, 'SMILES', identity[name], 'source.identity_fields_json', '/' + name)
    add('meta_data/m/smi', 'SMILES', None if meta is None else meta['m']['smi'],
        'supplemental_original_fields.meta_data', '/m/smi')
    add('meta_data/m/mol', 'MOL', None if meta is None else meta['m']['mol'],
        'supplemental_original_fields.meta_data', '/m/mol')
    availability = {}
    for section in SECTIONS:
        rep = {} if cm is None else cm[section]['representations']
        for key, kind in [('canonical_smiles', 'SMILES'), ('2D_MOL', 'MOL')]:
            add('cm_data/' + section + '/' + key, kind, rep.get(key),
                'supplemental_original_fields.cm_data', '/' + section + '/representations/' + key)
        for key in ('standard_inchi', 'standard_inchikey', '3D_MOL', 'murko_framework'):
            availability[section + '/' + key] = text_reference(rep.get(key))
        descriptors = None if cm is None else cm[section].get('descriptors')
        availability[section + '/descriptors'] = descriptors
    comparisons = {}
    for key in ('canonical_smiles', '2D_MOL'):
        comparisons['cm_original_vs_standardized_' + key + '_literal_equal'] = (
            None if cm is None else cm['original']['representations'][key]
            == cm['standardized']['representations'][key])
    mixed = None
    if identity.get('id') == '174178':
        mixed = dict(original_id='174178', whole_source_lexical_observation=lexical(identity['canonical_smiles']),
                     classification='CSV_LIKE_MARKERS_IN_WHOLE_ORIGINAL_FIELD_NOT_REPAIRED',
                     classification_is_lexical_not_graph_or_validity=True,
                     full_field_reference=text_reference(identity['canonical_smiles']),
                     opaque_original_row_reference=ref)
    return dict(source=source, original_id=identity['id'], opaque_original_row_reference=ref,
                native735_source_record_reference=record.get('native735_source_record_reference'),
                variants=variants, other_cached_field_availability=availability,
                literal_comparisons=comparisons, mixed_CSV_observation=mixed)
