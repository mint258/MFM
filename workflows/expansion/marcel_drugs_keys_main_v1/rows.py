"""Validate producer tokens/rows without repairing or discarding native identity."""
import base64,collections,json,sqlite3
from . import contract as C


def token(value):
    state=value['state'];n=value['bytes']
    if state=='MISSING':C.Q.need(n is None and 'text' not in value,'EXACT_MISSING_TOKEN');return None
    if state=='INVALID_UTF8_UNKNOWN':
        raw=base64.b64decode(value['base64'],validate=True)
        try:raw.decode('utf-8')
        except UnicodeError:pass
        else:raise ValueError('INVALID_UTF8_CLAIM_MUST_ACTUALLY_BE_INVALID')
    else:
        C.Q.need(state in ('LITERAL_UTF8','EMPTY_PRESERVED') and isinstance(value['text'],str),'ORIGINAL_UTF8_TOKEN_STATE')
        raw=value['text'].encode('utf-8');C.Q.need((raw==b'')==(state=='EMPTY_PRESERVED'),'EXACT_EMPTY_TOKEN')
    C.Q.need(type(n) is int and len(raw)==n and n<=1<<20,'ORIGINAL_TOKEN_EXACT_BYTE_COUNT');return raw


def validate(row):
    C.Q.need(set(row)=={'source_id','member','physical_ordinal','name_pairing_basis','details','chemical_key_computed'}
        and row['source_id']=='marcel_drugs_zip' and row['member'] in ('Drugs.csv','Drugs.sdf')
        and type(row['physical_ordinal']) is int and row['physical_ordinal']>=0 and row['chemical_key_computed'] is False
        and row['name_pairing_basis']=='EXACT_UNNORMALIZED_BYTES','EXACT_ORIGINAL_PRODUCER_IDENTITY_ROW')
    d=row['details']
    if row['member']=='Drugs.csv':
        C.Q.need(set(d)=={'name_fields','mapping_state','physical_fields','header_fields'},'EXACT_CSV_IDENTITY_ONLY_DETAILS')
        values=[token(v) for v in d['name_fields']];return values[0] if len(values)==1 else None
    C.Q.need(set(d)=={'title_name','properties','record_sha256','record_bytes','terminated','M_END_observed','format_state','issues','graph_and_stereo_verified'}
        and set(d['properties'])=={'ID','smiles','_Name'} and d['graph_and_stereo_verified'] is False,'EXACT_ORIGINAL_SDF_SELECTED_FIELDS_NOT_GEOMETRY')
    for values in d['properties'].values():
        C.Q.need(isinstance(values,list),'ORIGINAL_ALL_PROPERTY_VARIANTS')
        for v in values:token(v)
    return token(d['title_name'])


class Relations:
    def __init__(self,out,budget):
        self.out,self.budget=out,budget;self.db=sqlite3.connect(out/'new_identity_relationships.sqlite')
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA temp_store=FILE');self.db.execute('PRAGMA cache_size=-65536')
        self.db.executescript('CREATE TABLE csv_names(ordinal INTEGER PRIMARY KEY,name BLOB,details TEXT);'
            'CREATE TABLE conformers(ordinal INTEGER PRIMARY KEY,name BLOB,ids TEXT,smiles TEXT,record_sha TEXT,record_bytes INTEGER,format_state TEXT);'
            'CREATE TABLE native_ids(ordinal INTEGER,variant INTEGER,value BLOB);'
            'CREATE TABLE source_smiles(ordinal INTEGER,variant INTEGER,name BLOB,value BLOB);'
            'CREATE TABLE results(ordinal INTEGER PRIMARY KEY,state TEXT,unknown INTEGER);'
            'CREATE TABLE keys(ordinal INTEGER,full_key TEXT,wp5 TEXT,PRIMARY KEY(ordinal,full_key));')
        self.next=collections.Counter();self.counts=collections.Counter();self.batch=0
    def add(self,row):
        name=validate(row);member=row['member'];ordinal=row['physical_ordinal'];d=row['details']
        C.Q.need(ordinal==self.next[member],'CONTIGUOUS_ORIGINAL_MEMBER_PHYSICAL_ORDINALS');self.next[member]+=1
        if member=='Drugs.csv':self.db.execute('INSERT INTO csv_names VALUES(?,?,?)',(ordinal,name,json.dumps(d,separators=(',',':'))))
        else:
            self.db.execute('INSERT INTO conformers VALUES(?,?,?,?,?,?,?)',(ordinal,name,json.dumps(d['properties']['ID']),json.dumps(d['properties']['smiles']),d['record_sha256'],d['record_bytes'],d['format_state']))
            for i,v in enumerate(d['properties']['ID']):self.db.execute('INSERT INTO native_ids VALUES(?,?,?)',(ordinal,i,token(v)))
            for i,v in enumerate(d['properties']['smiles']):self.db.execute('INSERT INTO source_smiles VALUES(?,?,?,?)',(ordinal,i,name,token(v)))
        self.counts[member]+=1;self.batch+=1
        if self.batch>=512:self.db.commit();self.batch=0;self.budget.check()
    def result(self,result):
        row=result['source'];d=row['details'];ordinal=row['physical_ordinal'];unknown=result['has_any_unknown']
        self.db.execute('INSERT INTO results VALUES(?,?,?)',(ordinal,result['identity_state'],int(unknown)))
        for full,wp5 in result['full_key_and_WP5_pairs']:self.db.execute('INSERT INTO keys VALUES(?,?,?)',(ordinal,full,wp5))
    def context(self):
        self.db.commit()
        for sql in ('CREATE INDEX conf_name ON conformers(name)','CREATE INDEX smiles_name ON source_smiles(name,value)',
                    'CREATE INDEX ids_value ON native_ids(value)','CREATE INDEX csv_name ON csv_names(name)'):
            self.budget.check(False);self.db.execute(sql)
        self.db.commit()
        def n(sql):self.budget.check(False);return self.db.execute(sql).fetchone()[0]
        result={'all_source_rows':sum(self.counts.values()),'CSV_rows':self.counts['Drugs.csv'],'SDF_rows':self.counts['Drugs.sdf'],
            'CSV_duplicate_name_groups':n('SELECT count(*) FROM (SELECT name FROM csv_names GROUP BY name HAVING count(*)>1)'),
            'CSV_missing_or_empty_names':n("SELECT count(*) FROM csv_names WHERE name IS NULL OR name=x''"),
            'SDF_duplicate_ID_groups':n('SELECT count(*) FROM (SELECT value FROM native_ids WHERE value IS NOT NULL GROUP BY value HAVING count(DISTINCT ordinal)>1)'),
            'SDF_without_CSV_name':n('SELECT count(*) FROM conformers s WHERE s.name IS NULL OR NOT EXISTS(SELECT 1 FROM csv_names c WHERE c.name=s.name)'),
            'CSV_without_SDF_name':n('SELECT count(*) FROM csv_names c WHERE c.name IS NULL OR NOT EXISTS(SELECT 1 FROM conformers s WHERE s.name=c.name)'),
            'source_multi_SMILES_name_groups':n('SELECT count(*) FROM (SELECT name FROM source_smiles GROUP BY name HAVING count(DISTINCT value)>1)')}
        C.Q.need(result['CSV_rows']==C.CSV_N and result['SDF_rows']==C.N and result['all_source_rows']==C.CSV_N+C.N
            and all(result[k]==0 for k in ('CSV_duplicate_name_groups','CSV_missing_or_empty_names','SDF_duplicate_ID_groups','SDF_without_CSV_name','CSV_without_SDF_name'))
            and result['source_multi_SMILES_name_groups']==290,'FULL_ORIGINAL_RELATIONSHIP_CONTEXT_MATCHES_4521750')
        return result
    def export(self,writer,full):
        self.db.commit();counts=collections.Counter()
        cursor=self.db.execute('SELECT ordinal,name,details FROM csv_names ORDER BY ordinal')
        for ordinal,name,details in cursor:
            self.budget.check(False)
            total=self.db.execute('SELECT count(*) FROM conformers WHERE name=?',(name,)).fetchone()[0]
            selected,unknown=self.db.execute('SELECT count(*),coalesce(sum(r.unknown),0) FROM results r JOIN conformers s USING(ordinal) WHERE s.name=?',(name,)).fetchone()
            source_variants=self.db.execute('SELECT count(DISTINCT value) FROM source_smiles WHERE name=?',(name,)).fetchone()[0]
            pairs=self.db.execute('SELECT DISTINCT k.full_key,k.wp5 FROM keys k JOIN conformers s USING(ordinal) WHERE s.name=? ORDER BY k.full_key',(name,)).fetchall()
            state='ALL_CONFORMERS_NORMALIZED_WITH_UNKNOWNS_RETAINED' if selected==total else 'PROFILE_PARTIAL_CONFORMER_COVERAGE'
            if full:C.Q.need(selected==total,'FULL_NAME_MUST_INCLUDE_EVERY_ORIGINAL_CONFORMER')
            writer({'source_id':'marcel_drugs_zip','original_CSV_physical_ordinal':ordinal,'original_name_fields':json.loads(details)['name_fields'],
                'source_conformers':total,'selected_conformers_with_durable_results':selected,'unknown_selected_conformers':unknown,
                'distinct_original_SMILES_byte_variants':source_variants,'multiple_original_SMILES_status':source_variants>1,
                'conservative_full_InChIKey_union':[p[0] for p in pairs],'conservative_WP5_key_union':sorted({p[1] for p in pairs}),
                'observed_multiple_full_keys':len(pairs)>1,'normalization_coverage_state':state,
                'all_native_ID_and_physical_ordinal_links_in_job_relationship_index':True,'representative_SMILES_selected':False,
                'native_graph_or_stereo_or_pool_accepted':False})
            counts['names']+=1;counts['source_multi_SMILES_names']+=source_variants>1;counts['observed_multiple_full_key_names']+=len(pairs)>1
            counts['names_with_unknown_selected_conformers']+=unknown>0;counts['partial_names']+=selected!=total
        C.Q.need(counts['names']==C.CSV_N and counts['source_multi_SMILES_names']==290,'ALL_CSV_MEMBERSHIPS_AND290_MULTISMILES_GROUPS_RETAINED')
        return dict(counts)
