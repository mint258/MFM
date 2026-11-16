"""Original atom/pair scalar conditional distances from the selected F64 cache."""
import collections,dataclasses,pickle,sqlite3,zlib,time
import numpy as np
from stage0_cohort import R,O,load,save,guard
from stage3_information import distance,statistics
B=R/'MFM_p_data_information'
def main():
 started=time.time();status=load(B/'results/p_data_information/source_local_authority.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];allnames=[f['field_key'] for f in fields];byname={f['field_key']:f for f in fields};names=sorted(status['fields']);panels=load(O/'panel.json');pairs=load(O/'pairs.json');result={};localout={};retention={};c=sqlite3.connect('file:'+str(O/'source_local_authority.sqlite')+'?mode=ro',uri=True);c.execute('PRAGMA cache_size=-65536')
 for role,rows in panels.items():
  bymid={r['molecule_id']:r for r in rows};pairmid=collections.defaultdict(list)
  for i,p in enumerate(pairs[role]['conformer']):pairmid[p['molecule_id']].append((i,p))
  matrix=np.full((len(pairs[role]['conformer']),len(names)),np.nan);units=[];acc=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list)));source_record_counts={n:collections.Counter() for n in names}
  for ri,row in enumerate(rows):
   guard();mid=row['molecule_id'];mi=row['pilot_index']
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:pilot=pickle.load(stream)
   samples={ci:dict(s,targets={}) for ci,s in pilot.items()}
   for ci,n,blob in c.execute('SELECT ci,name,payload FROM labels WHERE role=? AND mi=?',(role,mi)):
    payload=pickle.loads(zlib.decompress(blob));template=pilot[ci]['targets'][n];raw=np.where(payload['valid'],payload['raw'],np.nan);samples[ci]['targets'][n]=dataclasses.replace(template,raw=raw,valid=payload['valid'],values=None,pair_index=payload['pair_index']);source_record_counts[n]['comparable_valid_records']+=int(payload['valid'].any())
   for i,pair in pairmid[mid]:
    a,b=samples[pair['a']],samples[pair['b']]
    for j,n in enumerate(names):
     ta,tb=a['targets'].get(n),b['targets'].get(n)
     if ta is None or tb is None:continue
     d,_,_=distance(ta,tb,a,b,byname[n]);matrix[i,j]=d if d is not None else np.nan
     x,y=ta.raw,tb.raw
     if ta.pair_index is not None:
      ia={tuple(e):k for k,e in enumerate(ta.pair_index.tolist())};ib={tuple(e):k for k,e in enumerate(tb.pair_index.tolist())};ends=sorted(ia.keys()&ib.keys())
      if not ends:continue
      x=x[[ia[e] for e in ends]];y=y[[ib[e] for e in ends]];elements=np.full(len(x),-1)
     else:elements=a['Z']
     if x.shape!=y.shape:continue
     valid=np.isfinite(x).all(-1)&np.isfinite(y).all(-1);diff=np.sqrt(np.mean((x-y)**2,axis=-1))
     for z in np.unique(elements):
      good=valid&(elements==z)
      if not good.any():continue
      key=str(int(z)) if z>=0 else 'directed_pairs';v=diff[good];acc[n][key]['rms'].append((float(np.sqrt(np.mean(v*v))),mid));acc[n][key]['maximum'].append((float(v.max()),mid))
   if ri%500==0:print(role,'ORIGINAL_LOCAL_DISTANCES',ri,len(rows),flush=True)
  unitids=[p['molecule_id'] for p in pairs[role]['conformer']];norms=load(O/('normalizations_'+role+'.json'));summaries={};rates={};old=np.load(O/('distances_'+role+'.npz'))['conformer']
  for flag in ['core','enriched']:
   for geometry in ['all','near_duplicate','distinct']:
    ix=[i for i,p in enumerate(pairs[role]['conformer']) if bymid[p['molecule_id']][flag] and (geometry=='all' or (p['heavy_rmsd']<.5 if geometry=='near_duplicate' else p['heavy_rmsd']>=.5))];key=flag+'|'+geometry;fs={};rs={}
    for j,n in enumerate(names):
     v=matrix[ix,j];groups=[unitids[i] for i in ix];s=statistics(v,groups);scale=np.asarray(norms[n]['scale']);scalar=float(scale.flat[0]) if scale.size==1 else None;s.update(candidate_pairs=len(ix),comparable_pairs=int(np.isfinite(v).sum()),nonzero_original_numeric_pairs=int(np.count_nonzero(v[np.isfinite(v)])),median_D4_amplitude=s['median']/scalar if s['median'] is not None and scalar else None,scale=scalar,evidence_layer='Original F64 atom/pair scalars on common pilot masks; computation accuracy remains unbounded');fs[n]=s;oj=allnames.index(n);valid=np.isfinite(v)&np.isfinite(old[ix,oj]);nonzero=valid&(v>0);erased=nonzero&(old[ix,oj]==0);unitrate=collections.defaultdict(lambda:[0,0])
     for k,i in enumerate(ix):
      if nonzero[k]:unitrate[unitids[i]][0]+=int(erased[k]);unitrate[unitids[i]][1]+=1
     means=[a/b for a,b in unitrate.values() if b];rs[n]=dict(candidate_pairs=len(ix),common_pairs=int(valid.sum()),original_nonzero_numeric_pairs=int(nonzero.sum()),original_nonzero_to_pilot_zero=int(erased.sum()),independent_molecules=len(means),equal_molecule_mean_erasure_rate=float(np.mean(means)) if means else None,median_molecule_erasure_rate=float(np.median(means)) if means else None,physical_reliability='Numeric original-F64 difference, not a global calculation-error test')
    summaries[key]=fs;rates[key]=rs
  local={}
  for n,groups in acc.items():
   local[n]={}
   for element,metrics in groups.items():
    local[n][element]={flag:{metric:dict(statistics([v for v,mid in values if bymid[mid][flag]],[mid for v,mid in values if bymid[mid][flag]]),observed_max=max([v for v,mid in values if bymid[mid][flag]],default=None)) for metric,values in metrics.items()} for flag in ['core','enriched']}
  guard();np.savez_compressed(O/('source_local_distances_'+role+'.npz'),conformer=matrix);result[role]=summaries;localout[role]=local;retention[role]=rates
 c.close();save(B/'results/p_data_information/original_local_information.json',dict(roles=result,fields=names,record_projection=status,raw_to_pilot_numeric_retention=retention,bootstrap=dict(repetitions=1000,seed=20261025,unit='molecule',statistic='median of equal molecule mean fixed-pair distances'),elapsed_seconds=time.time()-started));save(B/'results/p_data_information/original_local_differences.json',dict(roles=localout,source='Original F64 coordinate-independent local scalar fields',pair_policy='Existing directed endpoint intersection; no new pair labels',mask_policy='Common existing pilot masks; raw finite values are not physical validity proof'));print('ORIGINAL_LOCAL_INFORMATION_DONE',flush=True)
if __name__=='__main__':main()