"""Read the existing P-prime identity schema; no labels or new source index."""
import sqlite3
p='/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/identity.sqlite'
c=sqlite3.connect('file:'+p+'?mode=ro',uri=True)
for name,sql in c.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall():
 print('TABLE',name,sql,flush=True)
 for row in c.execute('SELECT * FROM "'+name+'" LIMIT 2'):
  print('EXAMPLE',str(row)[:600],flush=True)
c.close()