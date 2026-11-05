"""First-stream raw channel binding and cached F64 derived r73 observations."""
import json,pickle,sqlite3
from pathlib import Path
from ..window2_r73_views_v1.kernel import derive_entries
from ..normalization_compact_runtime_v3 import codec as K
from ..common import decode_cell


class ForwardRaw:
    def __init__(self,path,columns=None):
        import pyarrow.parquet as pq
        self.file=pq.ParquetFile(path,pre_buffer=False)
        self.iterator=self.file.iter_batches(batch_size=16,columns=columns,use_threads=False)
        self.batch=None;self.lo=0;self.hi=0;self.last=-1
    def get(self,index):
        if index<=self.last:raise ValueError('SOURCE_ROW_MUST_BE_FORWARD')
        while self.batch is None or index>=self.hi:
            self.batch=next(self.iterator);self.lo=self.hi;self.hi+=self.batch.num_rows
        self.last=index;return self.batch.slice(index-self.lo,1).to_pylist()[0]
    def close(self):self.file.close()


class Derived:
    def __init__(self,cfg,group,fields):
        self.first=cfg['statistics_purpose']=='element_reference';self.raw={};self.fields=[f for f in fields if f['field_id']>=146]
        if self.first:
            self.path=Path(cfg['group_output_root'])/'r73_derived.sqlite';self.db=sqlite3.connect(self.path)
            self.db.execute('CREATE TABLE derived(rid TEXT PRIMARY KEY,entries BLOB)');self.count=0
        else:
            manifest=json.loads(Path(cfg['r73_derived_reference']['path']).read_text())
            ref=next(r for r in manifest['files'] if r['group_index']==group['group_index'])
            self.path=Path(ref['path']);self.db=sqlite3.connect('file:'+str(self.path)+'?mode=ro',uri=True)
    def entries(self,row,source,original):
        if self.first:
            path=source['path']
            if path not in self.raw:self.raw[path]=ForwardRaw(path,['record_id','molecule_id','values'])
            raw=self.raw[path].get(row['physical_row'])
            if raw['record_id']!=row['record_id']:raise ValueError('R73_ORIGINAL_RAW_TYPED_RECORD_ALIGNMENT')
            cell=next((c for c in raw.get('values',[]) if c['registry_id']==73),None)
            native=decode_cell(cell) if original['values_float64'] else []
            # Explicit NULL/empty original containers produce no selected terms.
            entries=derive_entries([] if native is None or not original['values_float64'] else native,original,field_map=self.fields)
            packed=K.pack_entries(entries);packed['r73_pair_indices']=entries[0]['pair_indices']
            self.db.execute('INSERT INTO derived VALUES(?,?)',(row['record_id'],pickle.dumps(packed,protocol=5)));self.count+=1
            if self.count%1024==0:self.db.commit()
            return entries
        hit=self.db.execute('SELECT entries FROM derived WHERE rid=?',(row['record_id'],)).fetchone()
        if hit is None:raise ValueError('R73_DERIVED_CACHE_RECORD_MISSING')
        packed=pickle.loads(hit[0]);entries=K.unpack_entries(packed,{f['field_id']:f for f in self.fields})
        if 'r73_pair_indices' in packed:
            for entry in entries:entry['pair_indices']=packed['r73_pair_indices']
        return entries
    def close(self):
        for raw in self.raw.values():raw.close()
        if self.first:self.db.commit()
        self.db.close()