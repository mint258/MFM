"""Only a fresh recovery book is mutable. Old leases are never opened writable."""
import json,os,sqlite3,stat
from pathlib import Path
from urllib.parse import quote
from . import contract as C
from workflows.data_v1_final.labels.full_projection_v1.control import DispatchBook as OriginalBook


class Book(OriginalBook):
    def __init__(self,path,create=False,*,files=(),review=None,master_ref=None,review_ref=None,summary_ref=None,
                 selected_cursors=None,holds=None):
        p=Path(path).absolute()
        C.need(C.RUN in p.parents and p!=C.OLDBOOK and C.OLD not in p.parents and p.suffix=='.sqlite'
          and not any(q.is_symlink() for q in (p,*p.parents)),'NEW_BOOK_NEVER_OLD_BOOK_OR_ALIAS')
        if create:
            C.need(not p.exists() and review is not None and summary_ref is not None,'ONE_NEW_CPU_SEED_ONLY')
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
            values=C.budget(review)
            super().__init__(p,True,files=files,cap=values['production'],inodes=review['approved_whole_cache_inode_cap'],
              master_reference=master_ref,review_reference=review_ref)
            self.db.execute('CREATE TABLE recovery_hold(file_id INTEGER PRIMARY KEY,reasons TEXT NOT NULL)')
            for k,v in {'recovery_schema':C.SUMMARY,'recovery_summary_reference':summary_ref,'recovery_budget':values}.items():
                self.db.execute('INSERT INTO meta VALUES(?,?)',(k,json.dumps(v,sort_keys=True)))
            self.db.execute('BEGIN IMMEDIATE')
            try:
                for fid,pos in (selected_cursors or {}).items():self.db.execute('UPDATE source SET cursor=? WHERE file_id=?',(pos,fid))
                self.db.executemany('INSERT INTO recovery_hold VALUES(?,?)',[(fid,json.dumps(reasons,sort_keys=True)) for fid,reasons in (holds or {}).items()])
                self.db.execute('COMMIT')
            except BaseException:self.db.execute('ROLLBACK');raise
        else:
            st=p.lstat();C.need(stat.S_ISREG(st.st_mode) and st.st_uid==1278 and st.st_nlink==1,'OWN_SINGLE_LINK_EXISTING_NEW_BOOK')
            check=sqlite3.connect('file:'+quote(str(p),safe='/')+'?mode=ro',uri=True)
            try:
                row=check.execute("SELECT value FROM meta WHERE key='recovery_schema'").fetchone()
                C.need(row is not None and json.loads(row[0])==C.SUMMARY,'NO_WRITABLE_OPEN_OF_UNRECOGNIZED_OR_OLD_BOOK')
            finally:check.close()
            super().__init__(p)
        C.need(self.metadata().get('recovery_schema')==C.SUMMARY,'ONLY_THIS_NEW_RECOVERY_NAMESPACE')
        from . import io as I
        summary=I.load(I.require(self.metadata()['recovery_summary_reference']))
        actual={str(fid):json.loads(reasons) for fid,reasons in self.db.execute('SELECT file_id,reasons FROM recovery_hold')}
        C.need(summary['new_book_path']==str(p) and summary['origin']==C.ORIGIN and actual==summary['source_holds'],
          'FROZEN_SOURCE_HOLDS_NO_DELETE_OR_UNREVIEWED_UNHOLD')

    def pending(self,partition):
        blocked={r[0] for r in self.db.execute('SELECT file_id FROM recovery_hold')}
        return [r for r in super().pending(partition) if r['file_id'] not in blocked]

    def claim(self,name,selectors,cap,inodes,config_reference):
        blocked={r[0] for r in self.db.execute('SELECT file_id FROM recovery_hold')}
        C.need(not any(s['file_id'] in blocked for s in selectors),'NO_REDISPATCH_UNRESOLVED_CONSUMED_SOURCE')
        super().claim(name,selectors,cap,inodes,config_reference)

    def assert_claim(self,name,config_reference,selectors):
        C.need(not any(self.db.execute('SELECT 1 FROM recovery_hold WHERE file_id=?',(s['file_id'],)).fetchone() for s in selectors),
          'HOLD_RECHECK_BEFORE_ORIGINAL_WORKER_START')
        super().assert_claim(name,config_reference,selectors)

    def snapshot(self):
        out=super().snapshot();out['recovery_holds']=[{'file_id':i,'reasons':json.loads(r)} for i,r in self.db.execute('SELECT * FROM recovery_hold ORDER BY file_id')]
        out['adoption_summary_reference']=out['metadata']['recovery_summary_reference']
        return out