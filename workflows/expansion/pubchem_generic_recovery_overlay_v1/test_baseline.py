"""Compare full corrected population ranking with exact incremental topK."""
import hashlib
import json
import unittest
from .baseline_sql import choose,DOMAIN,SEED


class Native(unittest.TestCase):
    def test_full_population_oracle_insertion_and_representative_change(self):
        import duckdb
        rank=lambda key:hashlib.sha256(json.dumps([DOMAIN,SEED,key],separators=(',',':')).encode('ascii')).hexdigest()
        old={chr(65+i):10*(i+1) for i in range(7)};old_top=sorted(old,key=lambda k:(rank(k),k,old[k]))[:3]
        possible=['NEW'+str(i) for i in range(10000)]
        before=next(k for k in possible if rank(k)<rank(old_top[0]))
        between=next(k for k in possible if rank(old_top[0])<rank(k)<rank(old_top[1]))
        outside=next(k for k in possible if rank(k)>rank(old_top[-1]))
        additions=[(101,before),(102,between),(103,outside)];corrected=dict(old);corrected[old_top[0]]=1
        corrected.update({k:cid for cid,k in additions})
        expected=sorted(corrected,key=lambda k:(rank(k),k,corrected[k]))[:3]
        db=duckdb.connect()
        try:
            db.execute('CREATE TABLE old_membership(cid BIGINT,full_key VARCHAR,sample_ordinal BIGINT)')
            db.executemany('INSERT INTO old_membership VALUES (?,?,?)',[(old[k],k,i) for i,k in enumerate(old_top)])
            db.execute('CREATE TABLE replacements(full_key VARCHAR,old_cid BIGINT,new_cid BIGINT)')
            db.execute('INSERT INTO replacements VALUES (?,?,?)',[old_top[0],old[old_top[0]],1])
            db.execute('CREATE TABLE new_keys(cid BIGINT,full_key VARCHAR)');db.executemany('INSERT INTO new_keys VALUES (?,?)',additions)
            changes,n=choose(db,size=3)
            actual=db.execute('SELECT cid,full_key,sample_ordinal FROM chosen ORDER BY sample_ordinal').fetchall()
            self.assertEqual(actual,[(corrected[k],k,i) for i,k in enumerate(expected)])
            self.assertEqual(changes,dict(old_keys_removed=2,new_full_keys_added=2,representative_CIDs_changed=1))
            self.assertEqual(n,6)
        finally:db.close()
