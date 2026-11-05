"""Exact production score shape, full-reference key map and bitwise overlap checks."""
import struct
FIELDS={'ecfp4_2048_hex','nearest_v1_key','nearest_v1_tanimoto','reference_ordinal','score_numerator','score_denominator','evaluated_references','strictly_bound_pruned_references','reference_molecules'}
INTS=FIELDS-{'ecfp4_2048_hex','nearest_v1_key','nearest_v1_tanimoto'}

def need(value,message):
    if not value:raise ValueError(message)

def bits(value):return struct.pack('<d',value)

def prefix_sql(values):
    need(type(values)is list and values==sorted(set(values))and values and all(type(v)is str and len(v)==1 and v in '0123456789abcdef'for v in values),'Literal canonical MD5 prefixes')
    return 'substr(md5(ecfp4_2048_hex),1,1)IN('+','.join("'"+v+"'"for v in values)+')'

def schema(value):
    need(set(value.names)==FIELDS and len(value.names)==len(FIELDS),'Exactly original nine score columns')
    need(str(value.field('nearest_v1_tanimoto').type)=='double','Original binary64 score column')
    need(all(str(value.field(k).type).startswith(('int','uint'))for k in INTS),'Original integral counters')
    need(all(str(value.field(k).type)in('string','large_string')for k in('ecfp4_2048_hex','nearest_v1_key')),'Original text identities')

def install(db):db.create_function('alpha_import_f64_bits',bits,return_type='BLOB')

def validate(db,table,prefixes,n,expected_rows=None):
    need(table in('incoming','existing')and type(n)is int and n>0,'Bounded explicit score view/full reference')
    rowcount,unique=db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM '+table).fetchone()
    need(rowcount==unique and(expected_rows is None or rowcount==expected_rows),'Exact unique closed score mass')
    nulls=' OR '.join('s.'+k+' IS NULL'for k in sorted(FIELDS))
    invalid=f'''{nulls} OR NOT regexp_full_match(s.ecfp4_2048_hex,'[0-9a-f]{{512}}')
        OR NOT({prefix_sql(prefixes)}) OR s.reference_molecules<>{n}
        OR s.reference_ordinal<0 OR s.reference_ordinal>={n}
        OR s.score_denominator<1 OR s.score_denominator>2048
        OR s.score_numerator<0 OR s.score_numerator>s.score_denominator
        OR s.evaluated_references<0 OR s.strictly_bound_pruned_references<0
        OR s.evaluated_references+s.strictly_bound_pruned_references<>{n}
        OR NOT isfinite(s.nearest_v1_tanimoto)
        OR alpha_import_f64_bits(s.nearest_v1_tanimoto)<>alpha_import_f64_bits(s.score_numerator::DOUBLE/s.score_denominator::DOUBLE)'''
    need(db.execute('SELECT count(*)FROM '+table+' s WHERE '+invalid).fetchone()[0]==0,'All exact FP/F64/unreduced count/full-reference fields valid')
    need(db.execute('SELECT count(*)FROM '+table+' s LEFT JOIN ref_keys k ON s.reference_ordinal=k.ordinal WHERE s.nearest_v1_key IS DISTINCT FROM k.full_key').fetchone()[0]==0,'Every nearest key matches original full-reference ordinal')
    return rowcount

def overlap_and_new(db):
    count,unique=db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM existing').fetchone()
    need(count==unique,'No duplicate old overlapping result')
    tests=['m.'+k+' IS DISTINCT FROM e.'+k for k in sorted(FIELDS-{'ecfp4_2048_hex','nearest_v1_tanimoto'})]
    tests.append('alpha_import_f64_bits(m.nearest_v1_tanimoto)IS DISTINCT FROM alpha_import_f64_bits(e.nearest_v1_tanimoto)')
    need(db.execute('SELECT count(*)FROM incoming m JOIN existing e USING(ecfp4_2048_hex)WHERE '+' OR '.join(tests)).fetchone()[0]==0,'Every overlapping result equals all9 fields and exact F64 bits')
    db.execute('CREATE TABLE new_scores AS SELECT m.*FROM incoming m ANTI JOIN existing e USING(ecfp4_2048_hex)')
    new=db.execute('SELECT count(*)FROM new_scores').fetchone()[0]
    total=db.execute('SELECT count(*)FROM incoming').fetchone()[0]
    need(count+new==total,'All incoming rows overlap once or are new once')
    return count,new