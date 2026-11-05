"""Shared MFM4 TRAIN/FULL writer; one producer-end sample check and compaction."""
import argparse,collections,importlib,json,os,pathlib,random,subprocess,time
import numpy as np
from ..pilot_v31_compact_v1.codec import encode,decode,encode_key
from ..pilot_v31_compact_v1.run import Writer,IDMap,identity_row,compact_once,load,save

P=pathlib.Path


def channel_codes(record,codebook,codes):
    rows=[]
    for triple in record.get('r73_channels',[]):
        packed=[]
        for word in triple:
            if word is None:packed.append(0);continue
            if word not in codes:codes[word]=len(codebook);codebook.append(word)
            if codes[word]>65535:raise ValueError('R73_CHANNEL_CODE_UINT16_OVERFLOW')
            packed.append(codes[word])
        rows.append(packed)
    record['arrays'][32]=np.asarray(rows,dtype='<u2').reshape((-1,3))


def split_role(role):
    role=str(role).upper()
    if role=='TRAIN':return 'TRAIN',False
    if role in ('VAL','ROUTINE'):return 'FULL',True
    if role=='FULL':return 'FULL',False
    raise ValueError('UNEXPECTED_FINAL_EFFECTIVE_ROLE:'+role)


def compare_arrays(actual,expected):
    if set(actual)!=set(expected):raise ValueError('SAMPLE_ARRAY_SET_DIFFERS')
    for key,value in expected.items():
        value=np.asarray(value);observed=actual[key]
        if observed.shape!=value.shape or observed.dtype!=value.dtype:raise ValueError('SAMPLE_LAYOUT_DIFFERS:'+str(key))
        if value.dtype.kind=='f':
            if not np.array_equal(np.isnan(value),np.isnan(observed)):raise ValueError('SAMPLE_NAN_MASK_DIFFERS:'+str(key))
            valid=~np.isnan(value)
            if not np.all(np.isfinite(value[valid])) or not np.all(np.isfinite(observed[valid])):raise ValueError('SAMPLE_NONFINITE_VALID_VALUE')
            delta=np.abs(observed[valid].astype('f8')-value[valid].astype('f8'))
            if not np.all(delta<=1e-6+1e-6*np.abs(value[valid].astype('f8'))):raise ValueError('SAMPLE_VALUE_DIFFERS:'+str(key))
        elif not np.array_equal(value,observed):raise ValueError('SAMPLE_INDEX_DIFFERS:'+str(key))


def sample_check(samples,roots):
    import lmdb
    readers={split:lmdb.open(str(path),readonly=True,create=False,lock=False) for split,path in roots.items()}
    try:
        for split,key,expected,mkey,mexpected in samples:
            with readers[split].begin() as transaction:
                raw=transaction.get(key);mraw=transaction.get(mkey)
            if raw is None or mraw is None:raise ValueError('SAMPLE_RECORD_MISSING')
            compare_arrays(decode(raw),expected);compare_arrays(decode(mraw),mexpected)
    finally:
        for reader in readers.values():reader.close()
    return {'samples':len(samples),'atol':1e-6,'rtol':1e-6,'NaN_positions_equal':True,
            'source':'producer original scientific projection before MFM4 encoding',
            'independent_source_reread':False}


def distribute(root,nodes,destination):
    completed=[]
    for node in nodes:
        subprocess.run(['ssh','-n','-o','BatchMode=yes',node,'mkdir -p '+destination],check=True)
        subprocess.run(['rsync','-a','--sparse','--protect-args','-e','ssh -o BatchMode=yes',str(root)+'/',node+':'+destination+'/'],check=True)
        completed.append({'node':node,'path':destination})
    return completed


def export(plan,molecules,schema):
    """Consume original projected whole molecules; no source/format recomputation.

    Each item is emitted by `assemble_entries` or `assemble_molecule` with full
    U labels enabled. The source producer owns physical selection/masks. This
    writer checks its output once against those same source projection values.
    """
    root=P(plan['output_root']);scratch=P(plan['working_root'])
    root.mkdir(parents=True,exist_ok=False);scratch.mkdir(parents=True,exist_ok=False)
    schema=dict(schema);schema['D6']=True;schema['schema_shared_by']=['TRAIN','FULL']
    schema['role_codebook']={'TRAIN':0,'FULL':2}
    schema['array_definitions']=dict(schema['array_definitions'])
    schema['array_definitions']['15']={'id':15,'name':'ROUTINE','dtype':'u1','shape':[],
        'record_kinds':['M'],'meaning':'1 only for original ROUTINE/VAL molecules in FULL'}
    schema['U_contains_original_Pprime_labels']=True
    schema['r73_channel_codebook']=['__ABSENT__'];codes={}
    estimates=plan.get('estimated_split_bytes',{})
    writers={split:Writer(scratch/split,int(estimates.get(split,2<<30))) for split in ('TRAIN','FULL')}
    maps={split:IDMap(root/('id_map_'+split+'.parquet')) for split in writers}
    indices=collections.Counter();counts=collections.Counter();seen=set();samples=[];conformers=0
    rng=random.Random(plan['sample_seed']);start=time.monotonic()
    try:
        for item in molecules:
            mid=item['mid']
            if mid in seen:raise ValueError('DUPLICATE_FINAL_MOLECULE:'+mid)
            seen.add(mid);split,routine=split_role(item['role']);mi=indices[split];indices[split]+=1
            arrays=item['m_arrays'];arrays[5]=np.asarray(0 if split=='TRAIN'else 2,dtype='u1');arrays[15]=np.asarray(routine,dtype='u1')
            p_records=item['p_records'];u_records=item['u_records']
            if tuple(arrays[6])!=(len(p_records),len(u_records)):raise ValueError('MOLECULE_CONFORMER_COUNTS_DIFFERS')
            if item.get('topology_differences'):raise ValueError('MOLECULE_CONFORMER_TOPOLOGY_DIFFERS:'+mid)
            encoded=[('M',mi,None,encode(arrays))];rows=[identity_row('M',mi,None,mid,{},False)]
            for kind,records,held_id in (('P',p_records,13),('U',u_records,14)):
                for ci,record in enumerate(records):
                    channel_codes(record,schema['r73_channel_codebook'],codes)
                    body=record['arrays'];encoded.append((kind,mi,ci,encode(body)))
                    rows.append(identity_row(kind,mi,ci,mid,record,bool(arrays[held_id][ci])))
                    conformers+=1;replace=len(samples) if len(samples)<1000 else rng.randrange(conformers)
                    if replace<1000:
                        entry=(split,encode_key(kind,mi,ci),{k:v.copy() for k,v in body.items()},encode_key('M',mi),{k:v.copy() for k,v in arrays.items()})
                        if replace==len(samples):samples.append(entry)
                        else:samples[replace]=entry
                    counts[split+'_'+kind]+=1
            writers[split].put_many(encoded);maps[split].append(rows)
            if sum(indices.values())%1000==0:
                print(json.dumps({'phase':'EXPORT','molecules':sum(indices.values()),'counts':dict(counts)}),flush=True)
    finally:
        for writer in writers.values():writer.close()
        for table in maps.values():table.close()
    expected=plan['expected_molecules']
    if dict(indices)!=expected:raise ValueError('FINAL_COMMON_COUNTS_DIFFERS:'+repr((dict(indices),expected)))
    for name,value in plan['expected_conformers'].items():
        if counts[name]!=value:raise ValueError('FINAL_CONFORMER_COUNTS_DIFFERS:'+name)
    roots={split:root/split for split in writers}
    for split in writers:compact_once(scratch/split,roots[split])
    check=sample_check(samples,roots)
    save(root/'schema.json',schema)
    files=[]
    for split in roots:
        os.rename(root/('id_map_'+split+'.parquet'),roots[split]/'id_map.parquet')
        for filename in ('data.mdb','id_map.parquet'):
            path=roots[split]/filename
            files.append({'path':str(path),'bytes':path.stat().st_size,'records':maps[split].rows})
    path=root/'schema.json';files.append({'path':str(path),'bytes':path.stat().st_size,'records':1})
    manifest={'format':'v3.1/MFM4','data_version':plan['data_version'],'molecules':dict(indices),
        'conformers':dict(counts),'files':files,'producer_end_check':check,
        'export_seconds':time.monotonic()-start,'new_F64_copies':False,'new_content_hashes':False,
        'compact_copies_per_split':1,'full_source_dependencies':plan.get('source_dependencies',{})}
    save(root/'manifest.json',manifest)
    if plan.get('gpu_nodes'):
        manifest['distribution']=distribute(root,plan['gpu_nodes'],plan['node_destination_root'])
        save(root/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();plan=load(args.plan)
    final=P(plan['output_root'])/'manifest.json'
    if final.is_file():
        manifest=load(final)
        manifest['distribution']=distribute(P(plan['output_root']),plan['gpu_nodes'],plan['node_destination_root'])
        save(final,manifest)
        print(json.dumps(manifest,ensure_ascii=False),flush=True);return
    module,name=plan['source_factory'].split(':',1);factory=getattr(importlib.import_module(module),name)
    schema,molecules=factory(plan)
    print(json.dumps(export(plan,molecules,schema),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
