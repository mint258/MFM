"""Native tiny closed SQLite fixture, never an actual population authority."""
import sqlite3
import tempfile
from pathlib import Path
import unittest
from .state import clone,digest,stamp


class CommonClone(unittest.TestCase):
    def test_private_clone_removes_old_baseline_only_and_preserves_source_FD_and_Common_JSON(self):
        with tempfile.TemporaryDirectory()as directory:
            source=Path(directory)/'source.sqlite';target=Path(directory)/'target.sqlite'
            db=sqlite3.connect(source)
            db.executescript('''CREATE TABLE populations(name TEXT PRIMARY KEY,manifest TEXT,expected INT,complete INT);
            CREATE TABLE required_members(population TEXT,identity TEXT,PRIMARY KEY(population,identity));
            CREATE TABLE seen(population TEXT,identity TEXT,heavy_bin TEXT,element_combination TEXT,scaffold TEXT,full_key TEXT,PRIMARY KEY(population,identity));
            CREATE TABLE counts(population TEXT,kind TEXT,key TEXT,n INT,PRIMARY KEY(population,kind,key));
            CREATE TABLE moments(population TEXT,field TEXT,state TEXT,PRIMARY KEY(population,field));
            CREATE TABLE comparisons(name TEXT PRIMARY KEY,manifest TEXT,query_population TEXT,expected INT,complete INT);
            CREATE TABLE nearest(comparison TEXT,identity TEXT,value REAL);''')
            # Real headers are represented only to exercise routing. Three tiny
            # fixture rows are not coverage and cannot pass the actual Root gate.
            for name,n in [('pubchem_1m',1000000),('v1_common',1196122)]:
                db.execute('INSERT INTO populations VALUES(?,?,?,1)',(name,'FIXTURE_ONLY',n))
                db.execute('INSERT INTO required_members VALUES(?,?)',(name,'fixture'))
                db.execute('INSERT INTO seen VALUES(?,?,?,?,?,?)',(name,'fixture','10','6','','fixture'))
                db.execute('INSERT INTO counts VALUES(?,?,?,?)',(name,'functional_matches','fr_fixture',2))
                db.execute('INSERT INTO moments VALUES(?,?,?)',(name,'fixture','{"mean":0.10000000000000002,"m2":3.0}'))
            db.commit();before=digest(db,'v1_common',lambda:None);db.close()
            expected=stamp(source.stat());expected['st_dev']+=100 # explicitly different client-local device
            proof=clone(source,expected,target,lambda:None)
            self.assertEqual(proof['source_FD_SHA_before'],proof['source_FD_SHA_after'])
            self.assertEqual(proof['Common_logical_digest'],before)
            db=sqlite3.connect(target)
            self.assertEqual(db.execute("SELECT count(*) FROM populations WHERE name='pubchem_1m'").fetchone()[0],0)
            db.execute('INSERT INTO populations VALUES(?,?,?,1)',('pubchem_1m','NEW_FIXTURE',1000000));db.commit()
            self.assertEqual(digest(db,'v1_common',lambda:None),before);db.close()
            db=sqlite3.connect(source)
            self.assertEqual(db.execute("SELECT manifest FROM populations WHERE name='pubchem_1m'").fetchone()[0],'FIXTURE_ONLY');db.close()


if __name__=='__main__':unittest.main()
