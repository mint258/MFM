"""Window-two training view: one TRAIN scan, exact mode and TRAIN moments."""
from __future__ import annotations
import argparse, collections, concurrent.futures as cf, json, math, multiprocessing as mp, os
from pathlib import Path
import numpy as np
from workflows.data_v1_final.export.pilot_v31_compact_v1.codec import decode, encode_key
ARRAYS={'d20':4,'mol_labels':23,'atom_labels':24,'atom_vectors':25,'pair_labels':27}

def load(path):
    with open(path,encoding='utf-8') as f:return json.load(f)

def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.writing')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');os.replace(tmp,path)

def channel_groups(codebook):
    """Only the same symmetry block contributes to each requested target."""
    groups={}
    for i,name in enumerate(codebook):
        if name.endswith('-SIGMA'):groups[i]='sigma'
        elif name.endswith('-PI'):groups[i]='pi'
        else:groups[i]=None
    return groups

def r73_pair_targets(arrays,codebook):
    """Sum each stored atom-pair block; no zero fill for missing/invalid entries."""
    pairs=np.asarray(arrays.get(31,[]),dtype=np.int64)
    vals=np.asarray(arrays.get(34,[]),dtype=np.float64)
    codes=np.asarray(arrays.get(32,np.empty((0,3))),dtype=np.int64)
    n=len(arrays.get(26,[]));answer=np.full((n,2),np.nan,dtype=np.float64)
    groups=channel_groups(codebook);counts=collections.Counter()
    for column,name in enumerate(('sigma','pi')):
        selected=np.array([groups.get(int(a))==groups.get(int(b))==name for a,b in codes[:,:2]],dtype=bool)
        if not np.any(selected):continue
        rows=pairs[selected];values=vals[selected]
        sums=np.bincount(rows,weights=np.where(np.isfinite(values),values,0),minlength=n)
        have=np.bincount(rows,minlength=n)>0
        invalid=np.bincount(rows,weights=(~np.isfinite(values)).astype(int),minlength=n)>0
        answer[have&~invalid,column]=sums[have&~invalid]
    for a,b in codes[:,:2]:
        ga,gb=groups.get(int(a)),groups.get(int(b))
        if ga!=gb:counts['mixed_symmetry_entries']+=1
        elif ga is None:counts['delta_or_other_entries']+=1
    return answer,counts

def specifications(schema):
    result={}
    for array_name,columns in schema['columns'].items():
        for column_index,c in enumerate(columns):
            if c.get('registry_id')==674:continue
            key=c['field_key']
            if key not in result:result[key]={'field_key':key,'registry_id':c.get('registry_id'),'group':c.get('group',array_name),'unit':c.get('unit'),'target_id':c['target_id'],'selectors':[]}
            result[key]['selectors'].append([ARRAYS[array_name],column_index,array_name])
    r73=next(x for x in schema['fields']if x.get('registry_id')==73)
    for name in ('sigma','pi'):
        key=r73['field_key']+'.'+name
        result[key]={'field_key':key,'source_field':r73['field_key'],'registry_id':73,'group':r73.get('group','P'),'unit':r73.get('unit'),'target_id':r73['target_id'],'aggregation':'sum_same_symmetry_block_per_stored_atom_pair','selectors':[[34,0 if name=='sigma'else 1,'r73']]}
    return list(result.values())

def scan_shard(task):
    source,schema_path,start,end,scratch,number=task
    import lmdb
    schema=load(schema_path);specs=specifications(schema)
    folder=Path(scratch)/('scan_%02d'%number);folder.mkdir(parents=True,exist_ok=True)
    handles={};counts=collections.Counter();channels=collections.Counter()
    env=lmdb.open(source,readonly=True,lock=False,readahead=True,max_readers=128)
    def emit(i,a):
        a=np.asarray(a).reshape(-1);a=a[np.isfinite(a)]
        if not len(a):return
        # +0 and -0 represent the same valid numerical value for the mode.
        a=np.asarray(a,dtype='<f4');a[a==0]=0
        if i not in handles:handles[i]=(folder/('%03d.f4'%i)).open('ab',buffering=1<<20)
        handles[i].write(a.tobytes());counts[str(i)]+=len(a)
    try:
        with env.begin(buffers=True)as tx:
            cur=tx.cursor()
            if cur.set_range(encode_key('M',start)):
                while True:
                    key,raw=cur.item();key=bytes(key)
                    if key[:1]!=b'M' or int.from_bytes(key[1:5],'big')>=end:break
                    arrays=decode(raw,copy=False);mi=int.from_bytes(key[1:5],'big');counts['M']+=1
                    hold=np.asarray(arrays.get(13,[]));nconf=int(arrays[6][0])
                    for i,spec in enumerate(specs):
                        for aid,col,name in spec['selectors']:
                            if aid==4:emit(i,arrays[4][col])
                    for ci in range(nconf):
                        if len(hold)>ci and hold[ci]:continue
                        rawp=tx.get(encode_key('P',mi,ci))
                        if rawp is None:raise ValueError('missing PM7 key')
                        a=decode(rawp,copy=False);counts['P']+=1
                        reduced,observed=r73_pair_targets(a,schema['r73_channel_codebook']);channels.update(observed)
                        for i,spec in enumerate(specs):
                            for aid,col,name in spec['selectors']:
                                if aid==4:continue
                                if name=='r73':values=reduced[:,col]
                                elif aid==23:values=a[aid][col]
                                elif aid in (24,27):values=a[aid][:,col]
                                elif aid==25:values=a[aid][:,col,:]
                                emit(i,values)
                    if not cur.next():break
    finally:
        for h in handles.values():h.close()
        env.close()
    result={'range':[start,end],'counts':dict(counts),'r73_observations':dict(channels),'directory':str(folder)}
    save(folder/'progress.json',result)
    print(json.dumps({'scan_complete':number,'M':counts['M'],'P':counts['P']}),flush=True)
    return result

def summarize_field(task):
    i,spec,parts,scratch=task
    paths=[Path(p['directory'])/('%03d.f4'%i)for p in parts]
    n=sum(p.stat().st_size//4 for p in paths if p.exists())
    if not n:return dict(spec,enabled=True,statistics={'valid_values':0},reason='no_valid_observations_no_coverage_exclusion')
    target=Path(scratch)/('field_%03d.f4'%i)
    values=np.memmap(target,mode='w+',dtype='<f4',shape=(n,));at=0
    count=0;mean=0.;m2=0.;sum2=0.
    for path in paths:
        if not path.exists():continue
        with path.open('rb')as f:
            while True:
                chunk=np.fromfile(f,dtype='<f4',count=1<<20)
                if not len(chunk):break
                values[at:at+len(chunk)]=chunk;at+=len(chunk)
                x=chunk.astype(np.float64);cn=len(x);cm=float(x.mean());delta=cm-mean
                m2+=float(np.dot(x-cm,x-cm))+delta*delta*count*cn/(count+cn)
                mean+=delta*cn/(count+cn);count+=cn;sum2+=float(np.dot(x,x))
    std=math.sqrt(max(0,m2/n));scale=math.sqrt(sum2/n)
    # Sorting a newly produced statistics workspace is part of this producer's
    # calculation; the input LMDB is never reopened or checked a second time.
    values.sort();values.flush();best_count=0;best_value=None;last=None;carry=0
    for begin in range(0,n,1<<20):
        chunk=np.asarray(values[begin:begin+(1<<20)])
        starts=np.r_[0,np.flatnonzero(chunk[1:]!=chunk[:-1])+1];ends=np.r_[starts[1:],len(chunk)]
        for j,(a,b)in enumerate(zip(starts,ends)):
            val=float(chunk[a]);c=int(b-a)
            if j==0 and last==val:c+=carry
            if c>best_count:best_count,best_value=c,val
            last,carry=val,c
    del values
    reasons=[]
    if best_count*100>95*n:reasons.append('mode_fraction_gt_0.95')
    if std<1e-6*max(abs(mean),scale):reasons.append('std_below_relative_scale')
    return dict(spec,enabled=not reasons,exclusion_reasons=reasons,statistics={'valid_values':n,'mean':mean,'std_population':std,'typical_scale_rms':scale,'mode':best_value,'mode_count':best_count,'mode_fraction':best_count/n})

def run(plan):
    schema=load(plan['schema']);specs=specifications(schema)
    scratch=Path(plan['scratch']);scratch.mkdir(parents=True,exist_ok=True)
    cpus=int(os.environ.get('SLURM_CPUS_PER_TASK',16));n=50000
    tasks=[(plan['train_store'],plan['schema'],n*k//cpus,n*(k+1)//cpus,str(scratch),k)for k in range(cpus)]
    with cf.ProcessPoolExecutor(cpus,mp_context=mp.get_context('spawn'))as pool:parts=list(pool.map(scan_shard,tasks))
    if sum(p['counts']['M']for p in parts)!=n:raise ValueError('TRAIN must contain exactly 50000 M records')
    with cf.ProcessPoolExecutor(min(4,cpus),mp_context=mp.get_context('spawn'))as pool:
        fields=list(pool.map(summarize_field,[(i,s,parts,str(scratch))for i,s in enumerate(specs)]))
    excluded674=[dict(field_key=f['field_key'],registry_id=674,reason='taskbook_r674_excluded')for f in schema['fields']if f.get('registry_id')==674]
    groups=channel_groups(schema['r73_channel_codebook'])
    obj={'version':'training_view_v1','status':'FROZEN_BEFORE_STAGE5_PD','fit_role':'TRAIN','fit_molecules':n,'source_schema':plan['schema'],'source_store':plan['train_store'],'fields':fields,'explicit_exclusions':excluded674,'group_weighting':'equal_weight_per_enabled_field_within_group','coverage_checks_performed':False,'redundancy_processing_performed':False,'numeric_precision':'statistics_F64_over_single_export_F32','typical_scale_definition':'RMS of valid pilot TRAIN values, in the original field unit','vector_fields':'pool component observations only when the registry field_key itself is one vector; distinct component field_keys stay distinct','r73':{'source_arrays':[26,31,32,33,34],'codebook':schema['r73_channel_codebook'],'code_to_symmetry':{str(k):v for k,v in groups.items()},'sigma':'sum entries where basis_i and basis_j both end with -SIGMA, by the original pair_index row','pi':'sum entries where basis_i and basis_j both end with -PI, by the original pair_index row','mixed_or_delta':'outside requested sigma/pi blocks; original raw r73 records remain unchanged','missingness':'any invalid selected term masks that pair/channel; no selected entries gives NaN; never zero fill','directions_onsite_duplicates':'original pair direction, onsite rows and duplicate entries are retained in their sums','observed_other_entries':dict(sum((collections.Counter(p['r73_observations'])for p in parts),collections.Counter()))},'source_scans':1,'independent_QA_or_readback':False,'new_hashes':False}
    obj['r73'].update(code_mapping_source='Resolve schema.r73_channel_codebook by label; pilot integer codes are descriptive, not universal.',symmetry_by_label_suffix={'-SIGMA':'sigma','-PI':'pi','other':None},target_storage='Prefer schema.derived_r73_pair_targets: original F64 pure-block sums then one F32 cast. Historical D3 without that map uses original raw F32 K aggregation; no re-export.')
    for field in fields:
        if field.get('registry_id')==73:
            field['preferred_schema_selector']={'mapping':'derived_r73_pair_targets','target':field['field_key'].rsplit('.',1)[-1],'array_index':27,'column_key':'column_index','label':'pair_labels','fallback_to_original_selectors_if_absent':True}
    save(plan['output'],obj)
    included=[f['field_key']for f in fields if f['enabled']];excluded=[f for f in fields if not f['enabled']]
    text='# Training view v1: frozen before Stage 5 P/D\n\nAll '+str(len(included))+' enabled fields are listed in configs/data_v1/training_view_v1.json; equal weight within group. Only frozen50,000 TRAIN and non-held-out conformers are fitted. Mode>95% or population std<1e-6*max(abs(mean),RMS) excludes a field; no coverage or redundancy filtering.\n\nr73 sums only same-symmetry SIGMA/SIGMA and PI/PI blocks by original directed pair; mixed/delta stay in complete raw r73. Invalid selected entries or no selected entry give NaN. D6 uses original F64 sums then one F32 cast via schema.derived_r73_pair_targets; historical D3 may aggregate raw F32 K.\n\nAll r674 components excluded. Degenerate fields:\n'+''.join('- '+f['field_key']+': '+', '.join(f['exclusion_reasons'])+'\n'for f in excluded)
    Path(plan['description']).write_text(text,encoding='utf-8')
    save(plan['manifest'],{'files':[{'path':plan['output'],'bytes':Path(plan['output']).stat().st_size,'records':len(fields)+len(excluded674)},{'path':plan['description'],'bytes':Path(plan['description']).stat().st_size,'records':1}],'molecules':50000,'enabled_fields':len(included),'excluded_fields':len(excluded)+len(excluded674)})
    print(json.dumps({'complete':True,'enabled_fields':len(included),'excluded_fields':len(excluded)+len(excluded674)}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();run(load(a.plan))