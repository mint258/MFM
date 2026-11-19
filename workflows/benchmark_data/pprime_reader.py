"""Read shared downstream P-prime outcomes and original parsed fields in place."""
from collections import OrderedDict
from pathlib import Path
import sqlite3
from urllib.parse import quote
import zlib
from .pprime_store import unpack
from .shared_access import check_access


def readonly(path):
    return sqlite3.connect('file:'+quote(str(path),safe='/')+'?mode=ro',uri=True,isolation_level=None,timeout=10)


class PprimeReader:
    def __init__(self,queue):
        self.path=Path(queue).absolute();self.access=check_access(self.path)
        self.db=readonly(self.path);self.lanes=OrderedDict()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):
        for db in self.lanes.values():db.close()
        self.lanes.clear();self.db.close()

    def lane(self,path):
        path=Path(path).absolute()
        if not path.is_relative_to(self.path.parent) or path.is_symlink():raise ValueError('Lane outside declared shared output root')
        if path in self.lanes:
            db=self.lanes.pop(path);self.lanes[path]=db;return db
        if len(self.lanes)>=4:self.lanes.popitem(last=False)[1].close()
        db=readonly(path);self.lanes[path]=db;return db

    def get(self,mid,conformer_id):
        if self.access is not None and not self.access.get('immutable'):check_access(self.path)
        rid=mid+':sprime:'+str(int(conformer_id))
        row=self.db.execute('SELECT state,result,worker_pid,job,error FROM tasks WHERE record_id=?',(rid,)).fetchone()
        if row is None:return {'record_id':rid,'state':'NOT_YET_QUEUED','result':None,'Pprime_ready':False,'P_ready':False}
        state,payload,pid,job,error=row
        summary=unpack(payload) if payload is not None else {}
        path=summary.get('lane_store') or (str(self.path.parent/('lane_'+str(job)+'_'+str(pid)+'.sqlite')) if pid is not None else None)
        tasks=[]
        if path is not None and Path(path).is_file():
            for calc,kept,encoded in self.lane(path).execute(
                    'SELECT calc_type,output_retained,detail FROM calls WHERE record_id=? ORDER BY calc_type',(rid,)).fetchall():
                metadata=unpack(encoded);detail=metadata['parsed_detail']
                detail['raw_ref']={'container_path':path,'record_id':rid,'calc_type':calc,'output_retained':bool(kept)}
                detail['archive']=detail['raw_ref']
                if calc=='pm7_B' and 'derived_same_geometry' in summary:
                    detail.setdefault('values',{})['derived_from_same_geometry_charged_states']=summary['derived_same_geometry']
                tasks.append(detail)
        return {'record_id':rid,'state':state,'error':error,'summary':summary,'tasks':tasks,
            'Pprime_ready':state=='PPRIME_READY','P_ready':False,'source_database':str(self.path),
            'local_database_copy_created':False}

    def raw_outputs(self,mid,conformer_id,task):
        result=self.get(mid,conformer_id)
        detail=next((d for d in result['tasks'] if d['task']==task),None)
        if detail is None:raise KeyError((mid,conformer_id,task))
        ref=detail['raw_ref']
        if not ref['output_retained']:return []
        rows=self.lane(ref['container_path']).execute('SELECT name,raw_bytes,frame FROM outputs WHERE record_id=? AND calc_type=? ORDER BY name',
            (result['record_id'],task)).fetchall()
        return [{'name':name,'declared_bytes':n,'data':zlib.decompress(frame)} for name,n,frame in rows]
