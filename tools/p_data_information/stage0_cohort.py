"""Stage 0 producer: pilot-only identity metadata, no P record payloads."""
import collections,hashlib,json,os,pathlib,sys,time
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
R=pathlib.Path('/share/home/zixiao/descriptor_analysis');D=R/'runs/data_v1_20261025/repository';O=R/'runs/p_data_information_20261115_v1'
P=pathlib.Path('/lfshome/zixiao/data_v1_20261025/D3_v31_pilot_20261105_v1')
sys.path.insert(0,str(R/'MFM_p_recipe/current'))
from phychem_mfm.phase1.v31_loader import MFM4Dataset
pa.set_cpu_count(4);pa.set_io_thread_count(2)
def load(p):return json.loads(pathlib.Path(p).read_text())
def guard():
 for p in ['/',str(O)]:
  s=os.statvfs(p);reserve=max(10*1024**3,s.f_blocks*s.f_frsize//10) if p=='/' else 100_000_000_000
  if s.f_bavail*s.f_frsize<reserve+16*1024**3 or s.f_favail<20000:raise OSError('Actual filesystem/inode reserve insufficient')
 q=load(R/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json')
 if q['uid']!=os.getuid() or not 0<=time.time()-q['observed_time']<30 or q['available_bytes']<100_000_000_000+23_179_869_184+18_000_000_000+16*1024**3+1024**3:raise OSError('Actual NFS UID quota unavailable/insufficient')
def save(p,a):
 guard();p=pathlib.Path(p);p.write_text(json.dumps(a,indent=2,allow_nan=False)+'\n')
def main():
 started=time.time();guard();delivery=load(D/'configs/data_v1/D5_v1_pilot_provisional_delivery.json');excluded=set(load(R/'runs/p_recipe_20261113/D6_identity.json')['overlapping_molecules']);members={}
 for role in ['TRAIN','VAL']:
  rows=pq.read_table(delivery['components']['subsets']['pilot_'+role.lower()]['path']).to_pylist();assert len(rows)==(50000 if role=='TRAIN' else 5000)
  assert len({x['molecule_id'] for x in rows})==len(rows)
  members[role]=sorted(rows,key=lambda x:x['selection_rank'])
 mids=set(x['molecule_id'] for rows in members.values() for x in rows);current={}
 for ref in load('/lfshome/zixiao/data_v1_20261025/window2_final_population_20261105_v1/manifest.json')['membership_tables']:
  rows=pq.read_table(ref['path'],columns=['molecule_id','effective_role','common_population_v1'],filters=[('molecule_id','in',sorted(mids))]).to_pylist()
  for row in rows:
   assert row['molecule_id'] not in current;current[row['molecule_id']]=row
 print('CURRENT_JOIN',len(current),flush=True)
 # Read only source identity metadata for the fixed 55k, never energy/labels.
 formal=R/'runs/phase1_wp5_20261011/population/formal_record_index.parquet'
 columns=['molecule_id','record_id','formal_charge','element_counts','isomeric_smiles','canonical_smiles','stored_inchikey','reidentified_inchikey','source_family','retained_confirmed']
 identities={};conflicts=set()
 t=pq.read_table(formal,columns=columns,filters=[('molecule_id','in',sorted(mids))])
 for batch in t.to_batches(max_chunksize=16384):
  for row in batch.to_pylist():
   mid=row['molecule_id']
   if not row['retained_confirmed']:continue
   signature=(row['formal_charge'],tuple(row['element_counts'] or []),row['canonical_smiles'])
   if mid in identities and signature!=identities[mid]['signature']:conflicts.add(mid)
   else:identities.setdefault(mid,dict(row,signature=signature))
 del t
 print('SOURCE_IDENTITIES',len(identities),'CONFLICTS',len(conflicts),flush=True)
 from rdkit import Chem
 cohort={};summary={}
 for role,rows in members.items():
  counts=collections.Counter();out=[];im=pq.read_table(P/('v31_pilot_'+role)/'id_map.parquet',columns=['record_kind','molecule_id','molecule_index'],filters=[('record_kind','=','M')]);mapping={x['molecule_id']:x['molecule_index'] for x in im.to_pylist()}
  assert len(mapping)==len(rows)
  for row in rows:
   mid=row['molecule_id'];why=None;cur=current.get(mid);ident=identities.get(mid)
   if mid in excluded:why='current_overlap_exclusion'
   elif cur is None or not cur['common_population_v1']:why='not_current_common'
   elif cur['effective_role']!=role:why='role_conflict'
   elif mid not in mapping or ident is None:why='identity_unavailable'
   elif mid in conflicts:why='identity_conflict'
   graph=None;stereo=None;formula=None
   if why is None:
    mol=Chem.MolFromSmiles(ident['isomeric_smiles'] or ident['canonical_smiles'])
    if mol is None:why='graph_unavailable'
    else:
     graph=Chem.MolToSmiles(mol,canonical=True,isomericSmiles=False);stereo=Chem.MolToSmiles(mol,canonical=True,isomericSmiles=True)
     formula=json.dumps([sorted(ident['element_counts']),ident['formal_charge']],separators=(',',':'))
   counts[why or 'eligible']+=1
   out.append(dict(molecule_id=mid,role=role,selection_rank=row['selection_rank'],pilot_index=mapping.get(mid),status=why or 'eligible',graph=graph,stereo=stereo,formula_charge=formula,formal_charge=ident['formal_charge'] if ident else None,source_family=ident['source_family'] if ident else None))
  cohort[role]=out;summary[role]=dict(original=len(rows),**counts)
 save(O/'mother_metadata.json',cohort);save(O/'cohort_summary.json',dict(roles=summary,elapsed_seconds=time.time()-started,numeric_P_payloads_read=0,source_identity_metadata_records='filtered to fixed55k only'))
 print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
