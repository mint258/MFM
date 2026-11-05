"""Exact seven-field permutation, streaming order witness and full multiset proof."""
import hashlib
import json
import os
from pathlib import Path
import re
from ..alpha_runtime_v1 import common as Q

FIELDS=('cid','full_key','heavy_atoms','element_combination','generic_murcko','generic_ring_systems','ecfp4_2048_hex')
TYPES={'cid':'BIGINT','full_key':'VARCHAR','heavy_atoms':'BIGINT','element_combination':'VARCHAR',
  'generic_murcko':'VARCHAR','generic_ring_systems':'VARCHAR[]','ecfp4_2048_hex':'VARCHAR'}
PRODUCER='PUBCHEM_FULL_FP_ORDERED_TYPED_QUERY_V1'
ORDER='ecfp4_2048_hex_ASC_full_key_ASC_cid_ASC'


def population_scope(filtered,pool):
    Q.need(filtered.get('schema')=='expansion_filtered_columnar_pool_v1' and filtered.get('status')=='COMPLETE'
      and filtered.get('population_version')==pool['population_version']
      and pool['unique_full_keys']==109875599 and filtered['counts']['input_unique_molecules']==pool['unique_full_keys']
      and filtered['counts']['eligible_molecules']+filtered['counts']['excluded_molecules']==pool['unique_full_keys']
      and type(filtered['counts']['eligible_molecules']) is int and filtered['counts']['eligible_molecules']>=10000000,
      'Complete corrected all11 source with at least10M eligible identities; never baseline/cost/prefix input')


def row_contract(row):
    Q.need(set(row)==set(FIELDS),'Exactly the seven original query fields; sample_ordinal/targets/extra fields forbidden')
    Q.need(type(row['cid']) is int and row['cid']>0 and type(row['heavy_atoms']) is int and row['heavy_atoms']>=0,
      'Exact integer CID and original heavy0+ domain required')
    Q.need(all(type(row[k]) is str for k in ('full_key','element_combination','generic_murcko','ecfp4_2048_hex'))
      and re.fullmatch('[A-Z]{14}-[A-Z]{10}-[A-Z]',row['full_key']) is not None
      and re.fullmatch('[0-9a-f]{512}',row['ecfp4_2048_hex']) is not None,'Original key and512 lower-hex FP bytes required')
    Q.need(re.fullmatch('[0-9]+(,[0-9]+)*',row['element_combination']) is not None
      or (row['heavy_atoms']==0 and row['element_combination']==''),'Preserve the original explicit H-only domain extension')
    Q.need(type(row['generic_ring_systems']) is list and all(type(x) is str for x in row['generic_ring_systems']),
      'Original ordered string-list ring field required')


class Audit:
    def __init__(self):self.n=0;self.previous=None;self.sha=hashlib.sha256()
    def add(self,row,raw):
        row_contract(row);key=(row['ecfp4_2048_hex'],row['full_key'],row['cid'])
        Q.need(self.previous is None or self.previous<key,'Every identity appears once in strict FP/fullkey/CID order')
        self.previous=key;self.n+=1;self.sha.update(raw)


def write_projection(db,path,expected,check):
    actual={r[0]:r[1] for r in db.execute('DESCRIBE SELECT '+','.join(FIELDS)+' FROM candidates').fetchall()}
    Q.need(actual==TYPES,'The selected source must have the exact original seven SQL field types')
    audit=Audit();cursor=db.execute('SELECT '+','.join(FIELDS)+' FROM candidates ORDER BY ecfp4_2048_hex,full_key,cid')
    with Path(path).open('xb') as stream:
        while True:
            batch=cursor.fetchmany(8192)
            if not batch:break
            check()
            for values in batch:
                row=dict(zip(FIELDS,values));raw=(json.dumps(row,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
                audit.add(row,raw);stream.write(raw)
        stream.flush();os.fsync(stream.fileno())
    Q.need(audit.n==expected,'No limit, prefix, FP DISTINCT or identity omission permitted')
    return dict(path=str(Path(path).absolute()),bytes=Path(path).stat().st_size,sha256=audit.sha.hexdigest(),rows=audit.n),dict(
      order=ORDER,strict_adjacent_order_checks=max(0,audit.n-1),all_serialized_rows_type_and_field_validated=audit.n,
      every_row_serialized_with_original_field_order=True,source_SQL_types=actual)


def prove(db,path,expected,check):
    # DuckDB reads all rows with declared types; the native writer separately
    # witnesses exact JSON fields/types/order and hashes every emitted byte.
    db.read_json(str(path),format='newline_delimited',columns=TYPES).create_view('observed')
    counts=db.execute('SELECT count(*),count(DISTINCT cid),count(DISTINCT full_key) FROM observed').fetchone()
    Q.need(counts==(expected,expected,expected),'Full row/uniqueCID/fullkey census differs')
    fields=','.join(FIELDS);difference={}
    for left,right in (('candidates','observed'),('observed','candidates')):
        check();n=db.execute('SELECT count(*) FROM (SELECT '+fields+' FROM '+left+' EXCEPT ALL SELECT '+fields+' FROM '+right+')').fetchone()[0]
        difference[left+'_minus_'+right]=int(n)
    Q.need(not any(difference.values()),'Seven-field bidirectional EXCEPT ALL must match every original candidate')
    return dict(rows=expected,unique_CIDs=counts[1],unique_full_keys=counts[2],seven_field_multiset_differences=difference,
      FP_duplicate_identity_rows_preserved=True,FP_distinct_selection_performed=False,all_source_rows_proved=True)
