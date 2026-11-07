"""Native dual-population clone preserves source and detects population mutation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from . import state


class Source(unittest.TestCase):
    def test_clone_retains_both_population_partitions_and_only_allows_new_NN_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.sqlite';destination=Path(directory)/'private.sqlite'
            db=sqlite3.connect(source)
            db.executescript('''CREATE TABLE populations(name TEXT,manifest TEXT,expected INTEGER,complete INTEGER);
              CREATE TABLE required_members(population TEXT,identity TEXT);
              CREATE TABLE seen(population TEXT,identity TEXT,heavy_bin TEXT,element_combination TEXT,scaffold TEXT,full_key TEXT);
              CREATE TABLE counts(population TEXT,kind TEXT,key TEXT,n INTEGER);
              CREATE TABLE moments(population TEXT,field TEXT,state TEXT);
              CREATE TABLE comparisons(name TEXT,manifest TEXT,query_population TEXT,expected INTEGER,complete INTEGER);
              CREATE TABLE nearest(comparison TEXT,identity TEXT,value REAL);''')
            expected={name:({'path':name+'.json','bytes':1,'sha256':'synthetic'},n,1)
              for name,n in [('pubchem_1m',1),('v1_common',2)]}
            for name,(ref,n,complete) in expected.items():
                db.execute('INSERT INTO populations VALUES(?,?,?,?)',(name,json.dumps(ref),n,complete))
                for i in range(n):
                    identity=name+str(i)
                    db.execute('INSERT INTO required_members VALUES(?,?)',(name,identity))
                    db.execute('INSERT INTO seen VALUES(?,?,?,?,?,?)',(name,identity,'10','6','ACYCLIC',identity))
                db.execute('INSERT INTO counts VALUES(?,?,?,?)',(name,'scaffold','ACYCLIC',n))
                db.execute('INSERT INTO moments VALUES(?,?,?)',(name,'heavy_atoms',json.dumps({'n':n})))
            db.commit();db.close();raw=hashlib.sha256(source.read_bytes()).hexdigest()
            proof=state.clone(source,state.stamp(source.stat()),destination,expected,lambda:None)
            self.assertEqual(proof['source_FD_SHA_before'],raw)
            self.assertEqual(proof['source_FD_SHA_after'],raw)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),raw)
            db=sqlite3.connect(destination)
            try:
                self.assertEqual(state.digests(db,lambda:None),proof['population_logical_digests'])
                db.execute("INSERT INTO moments VALUES('NN:pubchem_to_v1','nearest_tanimoto','{}')")
                db.execute("INSERT INTO nearest VALUES('pubchem_to_v1','pubchem_1m0',0.75)")
                db.commit();self.assertEqual(state.digests(db,lambda:None),proof['population_logical_digests'])
                db.execute("UPDATE moments SET state='changed' WHERE population='pubchem_1m'")
                self.assertNotEqual(state.digests(db,lambda:None),proof['population_logical_digests'])
            finally:db.close()
            db=sqlite3.connect(source)
            db.execute("INSERT INTO nearest VALUES('unexpected','pubchem_1m0',0.5)");db.commit();db.close()
            with self.assertRaises(ValueError):
                state.clone(source,state.stamp(source.stat()),Path(directory)/'forbidden.sqlite',expected,lambda:None)


if __name__=='__main__':unittest.main()
