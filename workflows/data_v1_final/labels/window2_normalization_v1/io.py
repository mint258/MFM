"""Producer IO: no content hashes, receipts or artificial resource stops."""
import json,os,pathlib
P=pathlib.Path


def require(reference,content=False):
    path=P(reference['path'])
    if path.stat().st_size!=reference['bytes']:raise ValueError('SOURCE_SIZE_CHANGED:'+str(path))
    return path


def load(path,*unused):
    with P(path).open(encoding='utf-8-sig') as source:return json.load(source)


def load_data(reference,*unused):return load(require(reference))


def ref(path):
    path=P(path);return {'path':str(path),'bytes':path.stat().st_size}


def save(path,value):
    path=P(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.writing')
    with temp.open('w',encoding='utf-8') as target:json.dump(value,target,ensure_ascii=False,sort_keys=True,allow_nan=False);target.write('\n')
    os.replace(temp,path);return ref(path)


def register_part(reference,parent):pass


class ParquetSink:
    def __init__(self,schema,buffer):self.schema=schema;self.rows=[]
    def add(self,rows):self.rows.extend(rows)
    def close(self,path,*unused):
        import pyarrow as pa,pyarrow.parquet as pq
        writer=pq.ParquetWriter(path,self.schema,compression='zstd')
        try:
            for start in range(0,len(self.rows),8192):writer.write_table(pa.Table.from_pylist(self.rows[start:start+8192],schema=self.schema))
        finally:writer.close()
        return dict(ref(path),records=len(self.rows))
