"""Three new metadata-only boundaries; no filesystem fixtures or observer."""
import json,sqlite3,unittest
from . import contract as C,reader as I

class Boundaries(unittest.TestCase):
    def database(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE records(record_id,calc_type,execution_id,molecule_id,dict_id,source_status,scope_status,'
            'retention_reason,input_bundle_sha256,raw_sha256,raw_bytes,metadata_bytes,raw_frame,metadata_frame)')
        db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            ('r','pm7_B','complete','m','d','SUCCESS','SUCCESS','AUDIT','i',b'0'*32,999,2,b'SCIENTIFIC_BODY_MUST_NOT_BE_RETURNED',b'{}'))
        return db

    def test_explicit_metadata_projection_never_returns_raw_or_staged_BLOB(self):
        db=self.database()
        try:
            observed=[];db.set_trace_callback(observed.append);row=I.scalar_row(db,('r','pm7_B','complete'))
            self.assertEqual(row['raw_frame_bytes'],len(b'SCIENTIFIC_BODY_MUST_NOT_BE_RETURNED'))
            self.assertNotIn('raw_frame',row);self.assertNotIn('metadata_frame',row)
            self.assertNotIn('SCIENTIFIC_BODY',json.dumps(row));self.assertEqual(observed[0].split(' FROM ')[0],I.ROW_SQL.split(' FROM ')[0])
            self.assertNotIn('SELECT *',I.ROW_SQL);self.assertNotIn('parsed_molecules',I.ROW_SQL)
        finally:db.close()

    def test_no_partial_or_latest_fallback_and_no_undeclared_archive_open(self):
        db=self.database()
        try:
            self.assertIsNone(I.scalar_row(db,('r','pm7_B','partial')))
            with self.assertRaisesRegex(ValueError,'EXPLICIT_EXECUTION'):I.scalar_row(db,('r','pm7_B',''))
            ref={'path':'/never_open_this_archive.sqlite','bytes':1,'sha256':'0'*64}
            with self.assertRaisesRegex(ValueError,'DECLARED_BEFORE_ANY_OPEN'):I.declared(ref,[])
        finally:db.close()

    def test_metadata_caps_dictionary_identity_and_duplicate_json_before_acceptance(self):
        calls=[]
        def identity(data,n):calls.append((len(data),n));return data
        self.assertEqual(I.decode_metadata(b'{}',2,identity),{})
        for raw,size in ((b'{}',C.METADATA_CAP+1),(b'x'*(C.FRAME_CAP+1),2)):
            before=len(calls)
            with self.assertRaisesRegex(ValueError,'CAP_BEFORE_DECOMPRESS'):I.decode_metadata(raw,size,identity)
            self.assertEqual(len(calls),before)
        with self.assertRaisesRegex(ValueError,'DUPLICATED_METADATA'):I.decode_metadata(b'{"a":1,"a":2}',13,identity)
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        try:
            db.execute('CREATE TABLE metadata(key,value)')
            db.executemany('INSERT INTO metadata VALUES(?,?)',[('format','WP5_OUTPUT_ONLY_DICT_ZSTD_V2'),
                ('policy','FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'),('input_bodies_saved','false'),
                ('dictionary_manifest_sha256','wrong'),('audit_membership_sha256','audit')])
            with self.assertRaisesRegex(ValueError,'DICTIONARY_AND_ORIGINAL_AUDIT'):
                I.archive_header(db,{'input_authority_references':{'dictionary_manifest':{'sha256':'right'},'audit_membership':{'sha256':'audit'}}},{})
        finally:db.close()