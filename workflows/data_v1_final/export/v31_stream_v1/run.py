"""Shared MFM4 TRAIN/FULL writer; one producer-end sample check and compaction."""
import argparse,collections,importlib,json,os,pathlib,pickle,random,subprocess,time
import numpy as np
from ..pilot_v31_compact_v1.codec import encode,decode,encode_key
from ..pilot_v31_compact_v1.run import Writer,IDMap,identity_row,compact_once,load,save

P=pathlib.Path


def channel_codes(record,codebook,codes):
    if 'r73_codebook' in record:
        book=record['r73_codebook'];translation=[0]
        for word in book[1:]:
            if word not in codes:codes[word]=len(codebook);codebook.append(word)
            if codes[word]>65535:raise ValueError('R73_CHANNEL_CODE_UINT16_OVERFLOW')
            translation.append(codes[word])
        record['arrays'][32]=np.asarray(translation,dtype='<u2')[record['arrays'][32]]
        return
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
        for split,key,expected,mkey,mexpected,source_note in samples:
            if source_note is not None and not source_note['within_tolerance']:raise ValueError('SAMPLE_ORIGINAL_F64_TO_SINGLE_F32_VALUE_DIFFERS')
            with readers[split].begin() as transaction:
                raw=transaction.get(key);mraw=transaction.get(mkey)
            if raw is None or mraw is None:raise ValueError('SAMPLE_RECORD_MISSING')
            compare_arrays(decode(raw),expected);compare_arrays(decode(mraw),mexpected)
    finally:
        for reader in readers.values():reader.close()
    return {'samples':len(samples),'atol':1e-6,'rtol':1e-6,'NaN_positions_equal':True,
            'source':'original F64 Parquet/typed projection with final masks -> sole F32 cast -> compact MFM4; original v30 was historically deleted and is not recreated'
            ,'original_F64_cast_sample_records':sum(note is not None for *_,note in samples),
            'independent_source_reread':False}


def distribute(root,nodes,destination):
    completed=[]
    for node in nodes:
        subprocess.run(['ssh','-n','-o','BatchMode=yes',node,'mkdir -p '+destination],check=True)
        subprocess.run(['rsync','-a','--sparse','--protect-args','-e','ssh -o BatchMode=yes',str(root)+'/',node+':'+destination+'/'],check=True)
        completed.append({'node':node,'path':destination})
    return completed


def export(plan,molecules,schema):
    """Consume TRAIN then FULL; only one uncompressed split exists at a time.

    source_factory returns split->zero-argument iterator factory. Scratch and
    compact destinations may be on different filesystems. Only this run's
    newly created, closed scratch is reclaimed after its compact copy closes.
    """
    import shutil
    root=P(plan['output_root']);checkpoint=root/'producer_checkpoint.pkl';resume=checkpoint.is_file()
    root.mkdir(parents=True,exist_ok=resume)
    scratch=P(plan['working_root']);scratch.mkdir(parents=True,exist_ok=resume)
    schema=dict(schema);schema['D6']=True;schema['schema_shared_by']=['TRAIN','FULL']
    schema['role_codebook']={'TRAIN':0,'FULL':2,'VAL':1,'ROUTINE':1}
    schema['array_definitions']=dict(schema['array_definitions'])
    for key,name,meaning in ((15,'ROUTINE','Original ROUTINE membership retained independently of Common; use M16 for Common scope'),(16,'COMMON','1 for final Common population')):
        schema['array_definitions'][str(key)]={'id':key,'name':name,'dtype':'u1','shape':[],'record_kinds':['M'],'meaning':meaning}
    schema['array_definitions']['17']={'id':17,'name':'ordinary_sprime_membership','dtype':'u1','shape':['addressable_U_count'],'record_kinds':['M'],'meaning':'1 for ordinary S-prime; 0 for registered Pprime-only extras. Array6 counts addressable records; U order arrays index only entries marked1.'}
    schema['array_definitions']['18']={'id':18,'name':'Pprime_train_eligible','dtype':'u1','shape':['addressable_U_count'],'record_kinds':['M'],'meaning':'Exact final Pprime producer fit_eligible: Common TRAIN actual first2 minus actual D5. Independent of M17 ordinary membership and M14 holdout.'}
    schema['U_contains_original_Pprime_labels']=True
    schema['r73_channel_codebook']=['__ABSENT__'];codes={}
    indices=collections.Counter();counts=collections.Counter();seen=set();samples=[];conformers=0
    rng=random.Random(plan['sample_seed']);start=time.monotonic();roots={};files=[];scratch_cleanup=[];storage={}
    def save_checkpoint():
        value={'plan':plan,'schema':schema,'indices':indices,'counts':counts,'seen':seen,'samples':samples,'conformers':conformers,'roots':roots,'files':files,'scratch_cleanup':scratch_cleanup,'storage':storage}
        pending=checkpoint.with_suffix('.writing')
        with pending.open('wb') as target:pickle.dump(value,target,protocol=5)
        os.replace(pending,checkpoint)
    if resume:
        with checkpoint.open('rb') as source:state=pickle.load(source)
        if state['plan']!=plan:raise ValueError('RESUME_FROZEN_PRODUCER_INPUTS_CHANGED')
        schema=state['schema'];indices=state['indices'];counts=state['counts'];seen=state['seen'];samples=state['samples'];conformers=state['conformers']
        roots=state['roots'];files=state['files'];scratch_cleanup=state['scratch_cleanup'];storage=state['storage']
        codes={word:i for i,word in enumerate(schema['r73_channel_codebook']) if i}
    else:save_checkpoint()
    if not isinstance(molecules,dict):raise ValueError('SEQUENTIAL_SOURCE_REQUIRES_SPLIT_ITERATOR_FACTORIES')
    for split in ('TRAIN','FULL'):
        if split in roots:continue
        final=P(plan.get('compact_roots',{}).get(split,str(root/split)));final.parent.mkdir(parents=True,exist_ok=True)
        work=P(plan.get('working_roots',{}).get(split,str(scratch/split)));work.parent.mkdir(parents=True,exist_ok=True)
        idpath=root/('id_map_'+split+'.parquet');attempt=0
        original_work=work;original_final=final;original_id=idpath
        while work.exists() or final.exists() or idpath.exists():
            attempt+=1;work=original_work.with_name(original_work.name+'_attempt_%03d'%attempt)
            final=original_final.with_name(original_final.name+'_attempt_%03d'%attempt);idpath=original_id.with_name(original_id.stem+'_attempt_%03d.parquet'%attempt)
        writer=Writer(work,int(plan.get('estimated_split_bytes',{}).get(split,2<<30)));table=IDMap(idpath)
        try:
            source=molecules[split];source=source() if callable(source) else source
            for item in source:
                mid=item['mid'];actual,routine=split_role(item['role']);routine=bool(item.get('routine',routine))
                if actual!=split:raise ValueError('SOURCE_SPLIT_ALIGNMENT:'+mid)
                if mid in seen:raise ValueError('DUPLICATE_FINAL_MOLECULE:'+mid)
                seen.add(mid);mi=indices[split];indices[split]+=1
                arrays=item['m_arrays'];arrays[5]=np.asarray(0 if split=='TRAIN'else 2,dtype='u1')
                arrays[15]=np.asarray(routine,dtype='u1');arrays[16]=np.asarray(bool(item['common_population']),dtype='u1')
                p_records=item['p_records'];u_records=item['u_records']
                if tuple(arrays[6])!=(len(p_records),len(u_records)):raise ValueError('MOLECULE_CONFORMER_COUNTS_DIFFERS')
                if item.get('topology_differences'):raise ValueError('MOLECULE_CONFORMER_TOPOLOGY_DIFFERS:'+mid)
                encoded=[('M',mi,None,encode(arrays))];rows=[identity_row('M',mi,None,mid,{},False)]
                for kind,records,held_id in (('P',p_records,13),('U',u_records,14)):
                    for ci,record in enumerate(records):
                        channel_codes(record,schema['r73_channel_codebook'],codes)
                        body=record['arrays'];encoded.append((kind,mi,ci,encode(body)))
                        rows.append(identity_row(kind,mi,ci,mid,record,bool(arrays[held_id][ci])))
                        conformers+=1
                        note=record.get('source_F64_cast_comparison')
                        replace=(len(samples) if note is not None else 1000) if 'source_sample_keys' in plan else len(samples) if len(samples)<1000 else rng.randrange(conformers)
                        if replace<1000:
                            entry=(split,encode_key(kind,mi,ci),{k:v.copy() for k,v in body.items()},encode_key('M',mi),{k:v.copy() for k,v in arrays.items()},note)
                            if replace==len(samples):samples.append(entry)
                            else:samples[replace]=entry
                        counts[split+'_'+kind]+=1
                writer.put_many(encoded);table.append(rows)
                if indices[split]%1000==0:print(json.dumps({'phase':'EXPORT','split':split,'molecules':indices[split],'counts':dict(counts)}),flush=True)
        finally:writer.close();table.close()
        if indices[split]!=plan['expected_molecules'][split]:raise ValueError('FINAL_MOLECULE_COUNTS_DIFFERS:'+split)
        for kind in ('P','U'):
            key=split+'_'+kind
            if counts[key]!=plan['expected_conformers'][key]:raise ValueError('FINAL_CONFORMER_COUNTS_DIFFERS:'+key)
        compact_once(work,final);roots[split]=final
        shutil.move(str(idpath),str(final/'id_map.parquet'))
        storage[split]={'record_counts':dict(writer.count),'record_bytes':dict(writer.bytes)}
        for name in ('data.mdb','id_map.parquet'):
            path=final/name;files.append({'path':str(path),'bytes':path.stat().st_size,'records':table.rows})
        # work was created by Writer(exist_ok=False), is closed, and has just
        # produced its only compact copy. Never apply cleanup to old D3 paths.
        scratch_cleanup.append({'path':str(work),'bytes':sum(p.stat().st_size for p in work.iterdir() if p.is_file()),'closed_compact_copy':str(final)})
        shutil.rmtree(work);save_checkpoint()
    if 'source_sample_keys' in plan and len(samples)!=len(plan['source_sample_keys']):raise ValueError('EXACT_1000_PHYSICAL_SOURCE_SAMPLE_MISSING')
    check=sample_check(samples,roots);save(root/'schema.json',schema)
    path=root/'schema.json';files.append({'path':str(path),'bytes':path.stat().st_size,'records':1})
    manifest={'format':'v3.1/MFM4','data_version':plan['data_version'],'molecules':dict(indices),'conformers':dict(counts),
        'files':files,'split_roots':{s:str(p) for s,p in roots.items()},'storage':storage,'scratch_cleanup':scratch_cleanup,
        'producer_end_check':check,'normalization_by_source_condition':schema.get('normalization_by_source_condition'),
        'normalization_condition_contract':schema.get('normalization_condition_contract'),'normalization_applied':False,'export_seconds':time.monotonic()-start,'new_F64_copies':False,'new_content_hashes':False,
        'compact_copies_per_split':1,'full_source_dependencies':plan.get('source_dependencies',{})}
    save(root/'manifest.json',manifest)
    if plan.get('gpu_nodes'):
        manifest['distribution']=distribute_products(root,roots,plan['gpu_nodes'],plan['node_destination_root']);save(root/'manifest.json',manifest)
    return manifest


def distribute_products(root,roots,nodes,destination):
    result=[]
    for node in nodes:
        for split,path in roots.items():result.extend(distribute(path,[node],destination+'/'+split))
        for filename in ('schema.json','manifest.json'):
            subprocess.run(['rsync','-a','--sparse','--protect-args','-e','ssh -o BatchMode=yes',str(P(root)/filename),node+':'+destination+'/'],check=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();plan=load(args.plan)
    final=P(plan['output_root'])/'manifest.json'
    if final.is_file():
        manifest=load(final)
        manifest['distribution']=distribute_products(P(plan['output_root']),{s:P(p) for s,p in manifest['split_roots'].items()},plan['gpu_nodes'],plan['node_destination_root'])
        save(final,manifest)
        print(json.dumps(manifest,ensure_ascii=False),flush=True);return
    module,name=plan['source_factory'].split(':',1);factory=getattr(importlib.import_module(module),name)
    schema,molecules=factory(plan)
    print(json.dumps(export(plan,molecules,schema),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
