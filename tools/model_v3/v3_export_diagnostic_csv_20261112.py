"""CSV copies of the three already exported diagnostic Parquet families."""
import argparse,csv,gzip,importlib.util,json,math,os,time
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path('/share/home/zixiao/descriptor_analysis');REPO=ROOT/'MFM_model_v3'
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
base=REPO/'results/model_v3_diagnostics_20261112'
manifest=json.loads((base/'DELIVERY_MANIFEST.json').read_text())
sources=[f for f in manifest['files'] if f['path'].endswith('.parquet') and
 any(c in ('predictions','curves','features','features_observed') for c in Path(f['path']).parts)]
out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('existing_csv_capacity',REPO/'tools/model_v3/v2_diagnosis_disk.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
def capacity():
 allocated,future=guard.model_growth_forecast()
 guard.m.require_capacity(guard.m.filesystem_status('/'),0,0)
 guard.m.require_capacity(guard.m.filesystem_status(out),future,1000)
 guard.m.quota_headroom(guard.CONTROL/'lustre_quota_available_v2_20261107.json','/lfshome',future,guard.remaining_d6()+6000000000)
def value(v):
 if v is None:return r'\N'
 if isinstance(v,str):return '\\'+v if v.startswith('\\') else v
 if isinstance(v,(list,tuple,dict)):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
 if isinstance(v,bool):return 'true' if v else 'false'
 if isinstance(v,float):
  if math.isnan(v):return 'NaN'
  if math.isinf(v):return 'Infinity' if v>0 else '-Infinity'
  return repr(v)
 return str(v)
files=[];tables=[];last=0
class Parts:
 def __init__(self,path):self.path=path;self.stream=None;self.current=0;self.parts=[]
 def write(self,data):
  offset=0
  while offset<len(data):
   if self.stream is None:
    self.current+=1;target=Path(str(self.path)+'.part'+str(self.current).zfill(2))
    self.stream=target.open('xb');self.parts.append(dict(path=str(target.relative_to(out)),bytes=0))
   take=min(len(data)-offset,3145728-self.parts[-1]['bytes'])
   self.stream.write(data[offset:offset+take]);self.parts[-1]['bytes']+=take;offset+=take
   if self.parts[-1]['bytes']==3145728:self.stream.close();self.stream=None
  return len(data)
 def flush(self):
  if self.stream:self.stream.flush()
 def close(self):
  if self.stream:self.stream.close();self.stream=None
for item in sources:
 if time.monotonic()-last>5:capacity();last=time.monotonic()
 relative=Path(item['path']).with_suffix('.csv');target=out/relative;target.parent.mkdir(parents=True,exist_ok=True)
 parquet=pq.ParquetFile(Path('/lfshome/zixiao/model_v31_20261105/DIAGNOSTICS_20261112')/item['path']);names=parquet.schema_arrow.names;count=0
 with target.open('x',encoding='utf-8-sig',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(names)
  for batch in parquet.iter_batches(batch_size=4096,use_threads=False):
   for row in batch.to_pylist():writer.writerow([value(row[k]) for k in names]);count+=1
   if time.monotonic()-last>5:capacity();last=time.monotonic()
 size=target.stat().st_size
 table=dict(source=item['path'],csv=str(relative),rows=count,bytes=size,
  columns=[dict(name=f.name,arrow_type=str(f.type),nullable=f.nullable) for f in parquet.schema_arrow])
 if size>50000000:
  sink=Parts(Path(str(target)+'.gz'))
  with target.open('rb') as source,gzip.GzipFile(fileobj=sink,mode='wb',mtime=0,compresslevel=6) as gz:
   while True:
    data=source.read(1024**2)
    if not data:break
    gz.write(data)
    if time.monotonic()-last>5:capacity();last=time.monotonic()
  sink.close();files.extend(sink.parts);table['uploaded_as']='gzip_3MiB_parts';table['parts']=sink.parts
 else:files.append(dict(path=str(relative),bytes=size));table['uploaded_as']='csv'
 tables.append(table)
 print(json.dumps(dict(source=item['path'],rows=count,csv_bytes=size)),flush=True)
result=dict(schema='MODEL_V3_DIAGNOSTICS_CSV_DELIVERY_V1',status='COMPLETE',selection_use=False,
 source_scope='Existing three diagnostic Parquet families including nested controls, observed-feature statistics and reconstructed predictions',
 csv_tables=len(tables),files=files,tables=tables,encoding='UTF-8 with BOM',delimiter=',',
 null_token=r'\N',backslash_string_rule='A scalar string beginning with backslash gets one extra leading backslash; remove it when interpreting a string column.',
 nested_values='JSON in one CSV cell',float_rule='Shortest round-trip representation of the original Arrow scalar; NaN/Infinity/-Infinity preserved as tokens',
 scientific_recomputation=False,export_review_or_second_readback=False,
 total_upload_bytes=sum(f['bytes'] for f in files))
(out/'CSV_MANIFEST.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(status=result['status'],tables=len(tables),files=len(files),bytes=result['total_upload_bytes'])),flush=True)
