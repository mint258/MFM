"""Exact source/container extraction, retaining text and complete source pins."""
import csv
import base64
import hashlib
import importlib
import io
import json
import os
import re
import stat
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from workflows.expansion.coconut_alpha_cached735_v1 import support as S

IDS = ('707929', '174911', '174178')


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(); self.cells = []; self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'td': self.current = []

    def handle_data(self, data):
        if self.current is not None: self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.current is not None:
            self.cells.append(''.join(self.current)); self.current = None

    def next_cell(self, exact_label):
        found = [(i, self.cells[i+1]) for i, cell in enumerate(self.cells[:-1])
                 if ''.join(cell.split()) == exact_label]
        S.need(len(found) == 1, 'EXACT_UNIQUE_HTML_TABLE_LABEL:' + exact_label)
        i, raw = found[0]
        return dict(label_cell_ordinal0=i, value_cell_ordinal0=i+1,
                    raw_text_nodes=raw, display_whitespace_collapsed=''.join(raw.split()))


class ProductFields(HTMLParser):
    """Exact official HTML element IDs; concatenate text nodes including subscripts."""
    IDS = ('ContentSection_lbl_SMILES', 'ContentSection_lbl_mFormula')

    def __init__(self):
        super().__init__(); self.values = {}; self.active = None; self.depth = 0

    def handle_starttag(self, tag, attrs):
        if self.active is not None:
            self.depth += 1
        else:
            key = dict(attrs).get('id')
            if key in self.IDS:
                S.need(key not in self.values, 'UNIQUE_OFFICIAL_PRODUCT_FIELD_ID')
                self.active = key; self.values[key] = []; self.depth = 1

    def handle_endtag(self, tag):
        if self.active is not None:
            self.depth -= 1
            if self.depth == 0: self.active = None

    def handle_data(self, text):
        if self.active is not None: self.values[self.active].append(text)

    def complete(self):
        S.need(self.active is None and set(self.values) == set(self.IDS), 'COMPLETE_TWO_OFFICIAL_FIELDS')
        return {k:''.join(v) for k,v in self.values.items()}


def csv_record(raw, identifier):
    try: text = raw.decode('utf-8-sig'); encoding = 'utf-8-sig'
    except UnicodeDecodeError: text = raw.decode('cp1252'); encoding = 'cp1252'
    reader = csv.DictReader(io.StringIO(text), strict=True); selected = []; previous = 1
    for logical, row in enumerate(reader, 1):
        S.need(None not in row and all(v is not None for v in row.values()), 'COMPLETE_CSV_FIELDS')
        if row.get('CyanoMetDB_Identifier') == identifier:
            selected.append(dict(row=row, logical_data_record_1based=logical,
                physical_text_line_start_1based=previous+1,
                physical_text_line_end_1based=reader.line_num, text_decoding=encoding))
        previous = reader.line_num
    S.need(len(selected) == 1, 'EXACT_PRIMARY_IDENTIFIER_OCCURS_ONCE')
    return selected[0]


def original_fields(record):
    return json.loads(record['source']['identity_fields_json']), record['supplemental_original_fields']


def source_check(record, expected_id, expected_reference, dois):
    identity, native = original_fields(record)
    S.need(identity['id'] == expected_id and native['reference_id'] == expected_reference,
           'EXACT_ORIGINAL735_ENTRY_AND_UPSTREAM_REFERENCE_ID')
    actual = set((native.get('doi') or '').lower().split('##')) - {''}
    S.need(actual == {d.lower() for d in dois}, 'BOTH_ORIGINAL_DOIS_NO_NAME_ONLY_ASSOCIATION')
    return identity, native


def variant(name, kind, text, ref, locator):
    return dict(name=name, kind=kind, text=text, upstream_file_reference=ref, locator=locator)


def cyano(record, E):
    identity,native=source_check(record, '707929', 'CyanoMetDB_0661', ('10.1021/ja00195a084', '10.1021/np980553b'))
    S.need(identity['canonical_smiles']=='n.a.','ACTUAL_ORIGINAL_MISSING_ISOMERIC_MARKER_NOT_REPLACED')
    versions = []; variants = []; formulas = []
    for filename in ('CyanoMetDB_WR_Feb2021.csv', 'CyanoMetDB_V03_2024.csv'):
        selected = csv_record(E.read(filename), 'CyanoMetDB_0661'); row = selected['row']
        S.need({row['DOI_No1'].lower(), row['DOI_No2'].lower()} ==
               {'10.1021/ja00195a084', '10.1021/np980553b'}, 'EXACT_CYANO_PRIMARY_ROW_DOI_BINDING')
        ref = E.ref(filename); versions.append(dict(file_reference=ref, **selected))
        for field in ('SMILES', 'SMILES_canonical', 'SMILES_isomeric'):
            variants.append(variant(filename + '/' + field, 'SMILES', row[field], ref,
                dict(logical_data_record_1based=selected['logical_data_record_1based'], field=field)))
        formulas.append(dict(value=row['MolecularFormula'], upstream_file_reference=ref,
                             locator=dict(logical_data_record_1based=selected['logical_data_record_1based'],
                                          field='MolecularFormula')))
    S.need(versions[0]['row']['MolecularFormula'] == versions[1]['row']['MolecularFormula'],
           'CROSS_VERSION_EXACT_PRIMARY_FORMULA_LITERAL_AGREEMENT')
    return dict(original_entry_id='707929', association_basis='EXACT_CyanoMetDB_0661_AND_BOTH_ORIGINAL_DOIS',
        versions=versions, variants=variants, formulas=formulas,
        caveats=dict(stereochemistry_not_reported=all('reference does not report stereochemistry' in
            v['row'].get('Notes ', '') for v in versions), missing_isomeric_marker_not_repaired=True,
            original_SQL_n_a_replaced=False, unavailable_stereo_not_invented=True))


def inpac(record, E):
    source_check(record, '174911', 'ACD0092', ('10.1016/s0378-8741(02)00099-5', '10.1016/j.canlet.2005.10.044'))
    collection_name='coconut_collection21_original_metadata_20261103_v1.json'
    collection=json.loads(E.read(collection_name));native_plan=E.native735_original_plan
    S.need(collection['schema']=='COCONUT_COLLECTION_NATIVE_METADATA_RANGE_WITNESS_V1'
           and collection['endpoint']=='218.192.171.238:22' and collection['uid']==1264
           and collection['original_SQL_reference']==native_plan['original_SQL_reference']
           and collection['original_A_receipt_reference']==native_plan['original_A_receipt_reference'],
           'ORIGINAL_COCONUT_COLLECTION_SOURCE_CHAIN_NOT_A_NAME_ONLY_DATABASE_GUESS')
    raw_parts={}
    path=Path(collection['original_SQL_reference']['path'])
    S.need(not any(x.is_symlink() for x in (path,*path.parents)),'NO_ORIGINAL_SQL_SYMLINK')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        S.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264
               and before.st_size==collection['original_SQL_reference']['bytes'],'EXACT_ORIGINAL_SQL_FRAME')
        for name in ('header','row'):
            ref=collection[name]
            S.need(0<ref['bytes']<8192,'BOUNDED_COLLECTION_HEADER_ROW_ONLY')
            raw=os.pread(fd,ref['bytes'],ref['offset'])
            S.need(raw==base64.b64decode(ref['raw_base64'],validate=True)
                   and hashlib.sha256(raw).hexdigest()==ref['sha256'],'SAME_FD_ORIGINAL_COLLECTION_RANGE_SHA')
            raw_parts[name]=raw
        S.need(S.frame(before)==S.frame(os.fstat(fd))==S.frame(path.stat()),'IMMUTABLE_ORIGINAL_SQL_RANGE')
    finally:os.close(fd)
    header=raw_parts['header'].decode('ascii')
    S.need(header.startswith('COPY public.collections (') and header.endswith(') FROM stdin;\n'),
           'ORIGINAL_COLLECTION_COPY_HEADER')
    names=header[len('COPY public.collections ('):-len(') FROM stdin;\n')].split(', ')
    S.need(collection['original_copy_text_source_reference'] in native_plan['original_source_references'],
           'ORIGINAL_COPY_DECODER_ALREADY_NATIVE735_PINNED')
    S.read(collection['original_copy_text_source_reference'],2<<20)
    copy_text=importlib.import_module('secondary_coconut_sql_identity_v1.copy_text')
    S.need(S.pin(copy_text.__file__)==collection['original_copy_text_source_reference'],
           'ACTUAL_ORIGINAL_COPY_DECODER_OBJECT')
    decoded=copy_text.row(copy_text.Input(io.BytesIO(raw_parts['row']),lambda:None),
                          len(names),dict(enumerate(names)),8<<20)
    S.need(not decoded['end'] and decoded['bytes']==len(raw_parts['row'])
           and decoded['row_sha256']==collection['row']['sha256'],'WHOLE_COLLECTION_COPY_ROW_BOUNDARY')
    fields={name:decoded['fields'][i] for i,name in enumerate(names)}
    S.need(fields==collection['decoded_fields'] and fields['id']=='21'
           and fields['identifier']=='CNPC0021' and fields['title']=='InPACdb'
           and fields['url']=='https://github.com/inpacdb/Indian-Plant-Anticancer-Compound-DB-inpacdb-/blob/master/inpacdb_latest.rar'
           and collection['row']['source_row_ordinal']==36,'EXACT_CLOSED_SOURCE_COLLECTION21_TO_UPSTREAM_URL')
    # The original author archive, Git commit and blob are retained, not a name lookup.
    archive = E.read('inpacdb_latest.rar'); metadata = json.loads(E.read('InPACdb_author_archive_metadata.json'))
    commit = json.loads(E.read('InPACdb_author_commit.json'))
    blob = hashlib.sha1(b'blob ' + str(len(archive)).encode() + b'\0' + archive).hexdigest()
    S.need(commit['sha'] == '856e45f836ff88d6c389107f05cedcd75fb086bd'
           and commit['commit']['author']['email'] == 'vumashankar@gmail.com'
           and blob == metadata['sha'] and len(archive) == metadata['size']
           and any(f['filename'] == 'inpacdb_latest.rar' and f['sha'] == blob for f in commit['files']),
           'ORIGINAL_AUTHOR_COMMIT_AND_COMPLETE_ARCHIVE_GIT_BLOB')
    witness = json.loads(E.read('InPACdb_exact_ACD0092_archive_witness.json'))
    S.need(witness['archive_sha256'] == hashlib.sha256(archive).hexdigest()
           and witness['exact_original_identifier_directory'] == 'inpacdb_latest/acd0092',
           'EXACT_ARCHIVE_MEMBER_LOCATOR_WITNESS')
    names = {'HTML':('InPACdb_ACD0092_acd0092.htm', 'inpacdb_latest/acd0092/acd0092.htm'),
             'MOL':('InPACdb_ACD0092_ACD0092.mol', 'inpacdb_latest/acd0092/ACD0092.mol')}
    bodies = {}; bindings = {}
    for key, (filename, member) in names.items():
        raw = E.read(filename); expected = witness['members'][member]
        S.need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
               'EXACT_PINNED_AUTHOR_ARCHIVE_MEMBER_BYTES')
        bodies[key] = raw; bindings[key] = dict(file_reference=E.ref(filename), archive=E.ref('inpacdb_latest.rar'),
                                             exact_archive_member=member, archive_member_witness=expected)
    cells = Cells(); cells.feed(bodies['HTML'].decode('cp1252'))
    accession = cells.next_cell('Accessionnumber'); formula = cells.next_cell('MolecularFormula')
    smiles = cells.next_cell('SMILESnotation'); pubchem = cells.next_cell('PubchemId')
    S.need(accession['display_whitespace_collapsed'] == 'ACD0092'
           and pubchem['display_whitespace_collapsed'] == 'SID:214549'
           and '12127233' in ''.join(cells.cells) and '16338066' in ''.join(cells.cells),
           'ORIGINAL_AUTHOR_HTML_EXACT_ID_SID_AND_TWO_LITERATURE_PMIDS')
    variants = [variant('AUTHOR_ACD0092.mol', 'MOL', bodies['MOL'].decode('ascii'), bindings['MOL'],
                        dict(whole_member=True))]
    # Do not remove HTML display whitespace or mend a bracket to manufacture source SMILES.
    variants.append(variant('AUTHOR_HTML_SMILES_TEXT_NODES_UNCHANGED', 'SMILES', smiles['raw_text_nodes'],
                            bindings['HTML'], smiles))
    return dict(original_entry_id='174911', association_basis='EXACT_AUTHOR_ARCHIVE_ACD0092_HTML_MOL_AND_PMIDS',
        author_commit_reference=E.ref('InPACdb_author_commit.json'), author_commit=commit['sha'],
        original_collection21_metadata_witness_reference=E.ref(collection_name),
        original_collection21_redecoded_fields=fields,
        current_SQL_range_read_bytes=sum(len(v) for v in raw_parts.values()),
        current_whole_SQL_SHA_recomputed=False,
        variants=variants, formulas=[dict(value=formula['display_whitespace_collapsed'],
            upstream_file_reference=bindings['HTML'], locator=formula,
            decoding='HTML_TEXT_NODE_CONCATENATION_AND_DISPLAY_WHITESPACE_ONLY')],
        exact_identifier_witness=accession, caveats=dict(original_HTML_SMILES_not_mended=True,
            original_malformed_SQL_not_changed=True, upstream_MOL_is_separate_original_source=True,
            original_author_generated_tautomers_stereoisomers_not_used_as_observed_originals=True,
            literature_list_not_claimed_to_prove_same_graph=True),
        original_HTML_reference_cells=[c for c in cells.cells if '12127233' in c or '16338066' in c])


def sdf_fields(raw):
    text = raw.decode('ascii'); fields = {}
    for match in re.finditer(r'^>\s*<([^>]+)>\r?\n([^\r\n]*)', text, re.M):
        S.need(match[1] not in fields, 'UNIQUE_SDF_PROPERTY'); fields[match[1]] = match[2]
    return fields


def indofine(record, E):
    identity, native = original_fields(record)
    text = identity['canonical_smiles']
    S.need(identity['id'] == '174178' and native['reference_id'] is None
           and '06-022' in text and 'NOBILETIN, 20% (Technical Grade)' in text
           and 'https://www.indofinechemical.com/details.aspx?Sku=06-022' in text,
           'EXACT_ORIGINAL_MALFORMED_FIELD_SKU_URL_AND_GRADE_NOT_PREFIX_GRAPH_PARSE')
    archive = E.read('indofine_natural_products.zip'); z = zipfile.ZipFile(io.BytesIO(archive))
    S.need(z.namelist() == ['Natural Products.sdf'], 'EXACT_OFFICIAL_CATEGORY_SDF_MEMBER')
    body = z.read('Natural Products.sdf'); selected = []; start = 0
    for ordinal, part in enumerate(body.split(b'$$$$'), 1):
        fields = sdf_fields(part)
        if fields.get('Catalog #') == '06-022':
            selected.append((ordinal, start, part, fields))
        start += len(part) + 4
    S.need(len(selected) == 1, 'ONE_EXACT_SKU_NOT_SIMILAR_06_022N')
    ordinal, start, part, fields = selected[0]
    S.need(fields['CAS#'] == '478-01-3' and fields['MFCD'] == 'MFCD03273560'
           and fields['PURITY'] == "'20%" and fields['Name'] == '"NOBILETIN, 20% (Technical Grade)"',
           'EXACT_OFFICIAL_SKU_GRADE_CAS_MFCD')
    split = part.find(b'\n>')
    S.need(split > 0, 'COMPLETE_SDF_RECORD_MOL_AND_PROPERTIES')
    # Only remove the source SDF record delimiter's preceding separator newline.
    # This is a declared container boundary extraction; no atom/bond/charge edit.
    mol = part[:split+1]
    if start > 0:
        S.need(mol.startswith(b'\n'), 'EXACT_SDF_RECORD_SEPARATOR_NEWLINE')
        mol = mol[1:]
    page = E.read('indofine_06-022.html').decode('utf-8')
    S.need('06-022' in page and 'NOBILETIN, 20% (Technical Grade)' in page
           and '478-01-3' in page and 'SMILES:' in page, 'EXACT_OFFICIAL_PRODUCT_PAGE_ANCHORS')
    product = ProductFields(); product.feed(page); values = product.complete()
    smi = values['ContentSection_lbl_SMILES']; formula = values['ContentSection_lbl_mFormula']
    locator = dict(archive_reference=E.ref('indofine_natural_products.zip'), member='Natural Products.sdf',
        member_bytes=len(body), member_sha256=hashlib.sha256(body).hexdigest(),
        record_1based=ordinal, record_start_offset0=start, whole_record_bytes=len(part)+4,
        whole_record_sha256=hashlib.sha256(part+b'$$$$').hexdigest(), properties=fields,
        MOL_boundary_extraction='SDF_MEMBER_RECORD_MOL_BEFORE_PROPERTY_HEADER_AND_RECORD_SEPARATOR_NEWLINE')
    return dict(original_entry_id='174178', association_basis='EXACT_ORIGINAL_SKU_URL_GRADE_AND_OFFICIAL_SDF_SKU',
        variants=[variant('OFFICIAL_SDF_SKU_06_022_MOL', 'MOL', mol.decode('ascii'),
                          E.ref('indofine_natural_products.zip'), locator),
                  variant('OFFICIAL_PRODUCT_PAGE_WHOLE_SMILES', 'SMILES', smi,
                          E.ref('indofine_06-022.html'), dict(HTML_element_id='ContentSection_lbl_SMILES',
                                                          text_nodes_concatenated_without_trimming=True))],
        formulas=[dict(value=formula, upstream_file_reference=E.ref('indofine_06-022.html'),
                       locator=dict(HTML_element_id='ContentSection_lbl_mFormula', markup_only_decoding=True))],
        caveats=dict(purity_literal='20%', named_component_is_not_all_material_components=True,
                     exact_SKU_not_99_percent_06_022N=True, original_SQL_CSV_not_cropped=True))
