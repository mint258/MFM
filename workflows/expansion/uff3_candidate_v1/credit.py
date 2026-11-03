"""Incremental immutable closed-output accounting, no growing-tree scans."""
from __future__ import annotations
from decimal import Decimal
import os
from pathlib import Path
import sqlite3
import stat


class ClosedLedger:
    def __init__(self,path):
        self.path=Path(path)
        self.db=sqlite3.connect(self.path,timeout=120)
        self.db.executescript('''PRAGMA journal_mode=DELETE;
          CREATE TABLE IF NOT EXISTS files(dev INTEGER,ino INTEGER,path TEXT UNIQUE,
            uid INTEGER,size INTEGER,blocks INTEGER,mtime INTEGER,ctime INTEGER,
            eligible INTEGER,credited INTEGER DEFAULT 0,PRIMARY KEY(dev,ino));
          CREATE INDEX IF NOT EXISTS credit_frontier ON files(credited,eligible);
          CREATE TABLE IF NOT EXISTS totals(singleton INTEGER PRIMARY KEY,
            logical INTEGER,allocated INTEGER,credit INTEGER,cutoff INTEGER);
          INSERT OR IGNORE INTO totals VALUES(1,0,0,0,0);
        ''')
        self.db.commit();self.pending={};self.pending_logical=0;self.pending_allocated=0
        self.promoted_rows_lastcall=0

    @staticmethod
    def is_mutable(path):
        name=Path(path).name
        return (name.endswith(('.sqlite','.sqlite-journal','.sqlite-wal','.sqlite-shm','.duckdb','.duckdb.wal','.lock'))
                or name.startswith('current_progress.'))

    @staticmethod
    def fact(path):
        path=Path(path).absolute();before=path.lstat();after=path.lstat()
        fields=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_size,s.st_blocks*512,s.st_mtime_ns,s.st_ctime_ns)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid()
                or fields(before)!=fields(after)):
            raise RuntimeError('STABLE_OWN_CLOSED_REGULAR_OUTPUT_REQUIRED')
        dev,ino,uid,size,blocks,mtime,ctime=fields(before)
        return (dev,ino,str(path),uid,size,blocks,mtime,ctime,max(mtime,ctime))

    def register(self,path):
        if self.is_mutable(path):return False
        value=self.fact(path);key=value[:2]
        old=self.pending.get(key)
        if old is not None and old[3:]!=value[3:]:
            raise RuntimeError('CLOSED_INODE_CHANGED_BEFORE_REGISTRATION')
        if old is not None:return True
        old=self.db.execute('SELECT uid,size,blocks,mtime,ctime,eligible FROM files WHERE dev=? AND ino=?',key).fetchone()
        if old is not None:
            if old!=value[3:]:raise RuntimeError('IMMUTABLE_CLOSED_OUTPUT_CHANGED')
            return True
        previous=self.db.execute('SELECT dev,ino FROM files WHERE path=?',(value[2],)).fetchone()
        if previous is not None:raise RuntimeError('IMMUTABLE_CLOSED_OUTPUT_PATH_REPLACED')
        self.pending[key]=value
        self.pending_logical+=value[4];self.pending_allocated+=value[5]
        if len(self.pending)>=4096:self.flush()
        return True

    def flush(self):
        if not self.pending:return
        logical=allocated=0
        try:
            for value in self.pending.values():
                dev,ino,path,uid,size,blocks,mtime,ctime,eligible=value
                old=self.db.execute('SELECT dev,ino,path,uid,size,blocks,mtime,ctime,eligible FROM files WHERE path=?',(path,)).fetchone()
                if old is not None:
                    if old!=value:raise RuntimeError('IMMUTABLE_CLOSED_OUTPUT_CHANGED')
                    continue
                old=self.db.execute('SELECT uid,size,blocks,mtime,ctime,eligible FROM files WHERE dev=? AND ino=?',(dev,ino)).fetchone()
                if old is not None:
                    if old!=(uid,size,blocks,mtime,ctime,eligible):raise RuntimeError('CLOSED_HARDLINK_INODE_FACTS_CHANGED')
                    continue
                self.db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,0)',value)
                logical+=size;allocated+=blocks
            self.db.execute('UPDATE totals SET logical=logical+?,allocated=allocated+? WHERE singleton=1',(logical,allocated))
            self.db.commit();self.pending.clear();self.pending_logical=0;self.pending_allocated=0
        except Exception:
            self.db.rollback();raise

    def totals(self):
        logical,allocated,credit,cutoff=self.db.execute('SELECT logical,allocated,credit,cutoff FROM totals WHERE singleton=1').fetchone()
        return {'closed_logical_bytes':logical+self.pending_logical,'closed_allocated_bytes':allocated+self.pending_allocated,
                'eligible_old_own_allocated_bytes':credit,'credit_cutoff_ns':cutoff}

    def credit_before(self,query_start):
        """Return integer allocated bytes known closed before actual quota query."""
        self.flush()
        cutoff=int(Decimal(str(query_start))*Decimal(1000000000))
        old_credit,old_cutoff=self.db.execute('SELECT credit,cutoff FROM totals WHERE singleton=1').fetchone()
        removed=0
        if cutoff<old_cutoff:
            removed=self.db.execute('SELECT coalesce(sum(blocks),0) FROM files WHERE credited=1 AND eligible>?',(cutoff,)).fetchone()[0]
            self.db.execute('UPDATE files SET credited=0 WHERE credited=1 AND eligible>?',(cutoff,))
        added,count=self.db.execute('SELECT coalesce(sum(blocks),0),count(*) FROM files WHERE credited=0 AND eligible<=?',(cutoff,)).fetchone()
        if count:self.db.execute('UPDATE files SET credited=1 WHERE credited=0 AND eligible<=?',(cutoff,))
        credit=old_credit-removed+added
        if count or removed or cutoff!=old_cutoff:
            self.db.execute('UPDATE totals SET credit=?,cutoff=? WHERE singleton=1',(credit,cutoff));self.db.commit()
        self.promoted_rows_lastcall=count
        return credit

    def close(self):
        self.flush();self.db.close()
