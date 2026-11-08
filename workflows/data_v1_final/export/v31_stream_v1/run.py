"""Shared MFM4 TRAIN/FULL writer; one producer-end sample check and compaction."""
import argparse,collections,importlib,json,os,pathlib,pickle,random,subprocess,time
import numpy as np
from ..pilot_v31_compact_v1.codec import encode,decode,encode_key
from ..pilot_v31_compact_v1.run import Writer,IDMap,identity_row,compact_once,load,save
from .disk_guard import from_plan
from .block_checkpoint import BlockWriter,IDFragments,consume_id_fragments,id_fragment_root
from .state_journal import Journals

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


def closed_sample_check(samples,roots,root,guard=None):
    marker=P(root)/'producer_end_check.pkl'
    if marker.is_file():
        with marker.open('rb') as source:closed=pickle.load(source)
        if closed['roots']!=roots:raise ValueError('CLOSED_PRODUCER_CHECK_ROOTS_CHANGED')
        return closed['check']
    if guard:guard.wait(root,inodes_needed=4)
    check=sample_check(samples,roots)
    pending=marker.with_suffix('.writing')
    with pending.open('wb') as target:pickle.dump({'roots':roots,'check':check},target,protocol=5)
    os.replace(pending,marker)
    return check


def distribute(root,nodes,destination):
    completed=[]
    for node in nodes:
        subprocess.run(['ssh','-n','-o','BatchMode=yes',node,'mkdir -p '+destination],check=True)
        subprocess.run(['rsync','-a','--sparse','--protect-args','-e','ssh -o BatchMode=yes',str(root)+'/',node+':'+destination+'/'],check=True)
        completed.append({'node':node,'path':destination})
    return completed


def validate_source_task_resume(previous,current,active):
    from .source_bridge import source_task_layout,SOURCE_TASK_NUMBER_STRIDE
    cursor=None if active is None else active.get('source_cursor')
    if cursor is not None and cursor>=SOURCE_TASK_NUMBER_STRIDE and previous.get('source_task_molecules')!=current.get('source_task_molecules'):
        raise ValueError('ENCODED_SOURCE_CURSOR_CHUNK_HINT_CHANGED')
    width,prefix,whole=source_task_layout(current,cursor)
    if cursor is not None and cursor>=SOURCE_TASK_NUMBER_STRIDE:
        old_width,old_prefix,old_whole=source_task_layout(previous)
        group=cursor//SOURCE_TASK_NUMBER_STRIDE
        if (old_width is None or group<old_prefix or group in old_whole)!=(group in whole):
            raise ValueError('ENCODED_SOURCE_CURSOR_WHOLE_MODE_CHANGED')


def export(plan,molecules,schema):
    """Consume TRAIN then FULL; only one uncompressed split exists at a time.

    source_factory returns split->iterator factory with optional start_after. Scratch and
    compact destinations may be on different filesystems. Only this run's
    newly created, closed scratch is reclaimed after its compact copy closes.
    """
    import shutil
    if plan.get('gpu_nodes'):raise ValueError('SHARED_SINGLE_COPY_REQUIRES_NO_NODE_DISTRIBUTION')
    guard=from_plan(plan)
    root=P(plan['output_root']);checkpoint=root/'producer_checkpoint.pkl';resume=checkpoint.is_file()
    if guard:guard.wait(root,inodes_needed=4);guard.wait(plan['working_root'],inodes_needed=4)
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
    rng=random.Random(plan['sample_seed']);start=time.monotonic();roots={};files=[];scratch_cleanup=[];storage={};active=None;idmaps={};journals=None
    def save_checkpoint():
        journal_state=journals.flush(len(seen),len(samples))
        value={'plan':plan,'schema':schema,'indices':indices,'counts':counts,'journal_state':journal_state,'conformers':conformers,'roots':roots,'files':files,'scratch_cleanup':scratch_cleanup,'storage':storage,'active':active,'rng_state':rng.getstate(),'id_map_physical_paths':idmaps}
        if guard:guard.wait(root,inodes_needed=2)
        pending=checkpoint.with_suffix('.writing')
        with pending.open('wb') as target:
            pickle.dump(value,target,protocol=5);target.flush();os.fsync(target.fileno())
        os.replace(pending,checkpoint)
    if resume:
        with checkpoint.open('rb') as source:state=pickle.load(source)
        frozen=lambda p:{k:v for k,v in p.items() if k not in ('disk_protection','streaming_buffer_blocks','workers','metadata_working_root','chunk_compaction','id_map_storage','source_spool_root','id_fragment_working_root','cache_index_working_root','source_task_molecules','source_spool_compression','source_task_prefix_groups','source_task_whole_groups')}
        if frozen(state['plan'])!=frozen(plan):raise ValueError('RESUME_FROZEN_PRODUCER_INPUTS_CHANGED')
        validate_source_task_resume(state['plan'],plan,state.get('active'))
        schema=state['schema'];indices=state['indices'];counts=state['counts'];conformers=state['conformers']
        if 'journal_state' in state:journals,seen,samples=Journals.restore(root,state['journal_state'],guard)
        else:
            seen=state['seen'];samples=state['samples'];journals=Journals.migrate(root,seen,samples,guard)
        roots=state['roots'];files=state['files'];scratch_cleanup=state['scratch_cleanup'];storage=state['storage']
        idmaps=state.get('id_map_physical_paths',{})
        active=state.get('active');rng.setstate(state.get('rng_state',rng.getstate()))
        codes={word:i for i,word in enumerate(schema['r73_channel_codebook']) if i}
        if 'journal_state' not in state:save_checkpoint()
    else:
        journals=Journals(root,guard);save_checkpoint()
    if not isinstance(molecules,dict):raise ValueError('SEQUENTIAL_SOURCE_REQUIRES_SPLIT_ITERATOR_FACTORIES')
    for split in ('TRAIN','FULL'):
        if split in roots:continue
        if active is None:
            final=P(plan.get('compact_roots',{}).get(split,str(root/split)));final.parent.mkdir(parents=True,exist_ok=True)
            work=P(plan.get('working_roots',{}).get(split,str(scratch/split)));work.parent.mkdir(parents=True,exist_ok=True)
            idpath=root/('id_map_'+split+'.parquet');attempt=0
            original_work=work;original_final=final;original_id=idpath
            while work.exists() or final.exists() or idpath.exists() or id_fragment_root(plan,root,work).exists():
                attempt+=1;work=original_work.with_name(original_work.name+'_attempt_%03d'%attempt)
                final=original_final.with_name(original_final.name+'_attempt_%03d'%attempt);idpath=original_id.with_name(original_id.stem+'_attempt_%03d.parquet'%attempt)
            active={'split':split,'phase':'writing','work':str(work),'final':str(final),'idpath':str(idpath),
                    'fragment_root':str(id_fragment_root(plan,root,work)),'id_fragments':[],'id_rows':0,
                    'writer':None,'source_cursor':None,'committed_molecules':indices[split]}
            save_checkpoint()
        if active['split']!=split:raise ValueError('ACTIVE_WRITER_SPLIT_DIFFERS')
        work=P(active['work']);final=P(active['final']);idpath=P(active['idpath'])
        if active['phase']=='writing':
            if guard:guard.wait(work,inodes_needed=4);guard.wait(active['fragment_root'],inodes_needed=4)
            estimate=int(plan.get('estimated_split_bytes',{}).get(split,2<<30));closed=active['writer']
            if closed is None and (work/'data.mdb').is_file():closed={'map_size':2*estimate,'count':{},'bytes':{}}
            elif closed is None and work.exists():
                # A crash between fresh mkdir and LMDB open has no closed data.
                # Preserve that empty/unknown attempt and choose a fresh one.
                original=work;attempt=0
                while work.exists():attempt+=1;work=original.with_name(original.name+'_bootstrap_attempt_%03d'%attempt)
                active['work']=str(work);save_checkpoint()
            writer=BlockWriter(work,estimate,closed,active['committed_molecules']);table=IDFragments(active['fragment_root'],active['id_fragments'],guard=guard)
            try:
                source=molecules[split]
                source=source(start_after=active['source_cursor']) if callable(source) and active['source_cursor'] is not None else source() if callable(source) else source
                for item in source:
                    mid=item['mid'];actual,routine=split_role(item['role']);routine=bool(item.get('routine',routine))
                    if actual!=split:raise ValueError('SOURCE_SPLIT_ALIGNMENT:'+mid)
                    if mid in seen:raise ValueError('DUPLICATE_FINAL_MOLECULE:'+mid)
                    seen.add(mid);journals.mark_seen(mid);mi=indices[split];indices[split]+=1
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
                                journals.sample(replace,entry)
                            counts[split+'_'+kind]+=1
                    if guard:
                        guard.wait(work,sum(len(raw) for *_,raw in encoded),2)
                        guard.wait(idpath,inodes_needed=2)
                    writer.put_many(encoded);table.append(rows)
                    if indices[split]%1000==0:print(json.dumps({'phase':'EXPORT','split':split,'molecules':indices[split],'counts':dict(counts)}),flush=True)
                    block=item.get('_source_block_end')
                    if block is not None:
                        table.close_block(block['number']);active['writer']=writer.snapshot()
                        active['source_cursor']=block['number'];active['committed_molecules']=indices[split]
                        active['id_fragments']=table.closed;active['id_rows']=table.rows
                        save_checkpoint();block['ack']['committed']=True
                if table.current is not None:table.close_block(None)
                active['writer']=writer.snapshot()
                active['id_fragments']=table.closed;active['id_rows']=table.rows
            finally:writer.close();table.close()
            if indices[split]!=plan['expected_molecules'][split]:raise ValueError('FINAL_MOLECULE_COUNTS_DIFFERS:'+split)
            for kind in ('P','U'):
                key=split+'_'+kind
                if counts[key]!=plan['expected_conformers'][key]:raise ValueError('FINAL_CONFORMER_COUNTS_DIFFERS:'+key)
            if guard:guard.wait(idpath,inodes_needed=2)
            idpath=table.finish(idpath);active['idpath']=str(idpath);active['idmap_file_bytes']=idpath.stat().st_size
            active['work_bytes']=sum(p.stat().st_size for p in work.iterdir() if p.is_file())
            active['phase']='raw_closed';save_checkpoint()
        if active['phase']=='raw_closed' and not active.get('id_fragments_consumed'):
            consume_id_fragments(active);active['id_fragments_consumed']=True;save_checkpoint()
        if active['phase']=='raw_closed':
            chunked=bool(plan.get('chunk_compaction',{}).get('enabled')) and split in plan['chunk_compaction'].get('splits',['TRAIN'])
            if 'chunk_catalog' not in active:
                attempt=0;original_final=final
                while final.exists():attempt+=1;final=original_final.with_name(original_final.name+'_compact_attempt_%03d'%attempt)
                active['final']=str(final)
                if chunked:active['chunk_catalog']=str(root/(work.name+'_compact_chunks.json'))
                save_checkpoint()
            if chunked or 'chunk_catalog' in active:
                from . import chunk_compaction as chunks
                if guard is None:raise ValueError('CHUNK_COMPACTION_REQUIRES_ACTUAL_DISK_GUARD')
                chunks.compact(plan,work,active['chunk_catalog'],guard)
                active['phase']='chunks_closed';save_checkpoint()
            else:
                if guard:
                    guard.wait(final,active['work_bytes'],4);final.mkdir(exist_ok=False)
                    binary=shutil.which('mdb_copy') or '/share/apps/softwares/anaconda3/bin/mdb_copy'
                    guard.run([binary,'-c',str(work),str(final)],final)
                else:compact_once(work,final)
                active['phase']='compacted';save_checkpoint()
        if active['phase']=='chunks_closed':
            from . import chunk_compaction as chunks
            catalog=chunks.read(active['chunk_catalog'])
            if catalog['phase'] not in ('CHUNKS_CLOSED','CONCATENATING','COMPLETE') or catalog['source']!=str(work):raise ValueError('FULL_C0_CHUNKS_REQUIRED_BEFORE_RAW_LIFECYCLE')
            if work.exists():shutil.rmtree(work) # only this checkpoint-owned fresh raw, all chunks C0
            active['raw_reclaimed_after_chunks_C0']=True;save_checkpoint()
            chunks.concatenate(active['chunk_catalog'],final/'data.mdb',guard)
            active['phase']='compacted';save_checkpoint()
        if active['phase']=='compacted' and active.get('chunk_catalog'):
            from . import chunk_compaction as chunks
            if not chunks.read(active['chunk_catalog']).get('chunks_consumed'):chunks.cleanup(active['chunk_catalog'],guard)
        if active['phase']!='compacted':raise ValueError('UNKNOWN_OWNED_WRITER_PHASE')
        if plan.get('id_map_storage','in_split')=='external_symlink':
            if not idpath.is_file():raise ValueError('CLOSED_EXTERNAL_IDMAP_MISSING')
            link=final/'id_map.parquet';physical=str(idpath.resolve())
            if link.is_symlink():
                if os.readlink(link)!=physical:raise ValueError('EXISTING_IDMAP_LINK_TARGET_DIFFERS')
            elif link.exists():raise ValueError('EXTERNAL_IDMAP_MUST_NOT_OVERWRITE_EXISTING_FILE')
            else:
                if guard:guard.wait(link,inodes_needed=2)
                os.symlink(physical,link)
            idmaps[split]=physical
        elif plan.get('id_map_storage','in_split')!='in_split':raise ValueError('UNKNOWN_IDMAP_STORAGE_MODE')
        elif idpath.is_file():
            if guard:
                guard.wait(final,idpath.stat().st_size,2)
                if idpath.stat().st_dev==final.stat().st_dev:os.replace(idpath,final/'id_map.parquet')
                else:
                    partial=final/'id_map.parquet.partial'
                    guard.run(['rsync','-a','--sparse','--',str(idpath),str(partial)],partial,idpath.stat().st_size,2)
                    os.replace(partial,final/'id_map.parquet');idpath.unlink()
            else:shutil.move(str(idpath),str(final/'id_map.parquet'))
        elif not (final/'id_map.parquet').is_file():raise ValueError('CLOSED_FINAL_IDMAP_MISSING')
        roots[split]=final;storage[split]={'record_counts':active['writer']['count'],'record_bytes':active['writer']['bytes']}
        for name in ('data.mdb','id_map.parquet'):
            path=final/name;files.append({'path':str(path),'bytes':path.stat().st_size,'records':active['id_rows']})
        scratch_cleanup.append({'path':str(work),'bytes':active['work_bytes'],'closed_compact_copy':str(final)})
        # Only this checkpoint-owned fresh scratch, after its compact C0.
        if work.exists():shutil.rmtree(work)
        active=None;save_checkpoint()
    if 'source_sample_keys' in plan and len(samples)!=len(plan['source_sample_keys']):raise ValueError('EXACT_1000_PHYSICAL_SOURCE_SAMPLE_MISSING')
    check=closed_sample_check(samples,roots,root,guard)
    if guard:guard.wait(root,inodes_needed=4)
    save(root/'schema.json',schema)
    path=root/'schema.json';files.append({'path':str(path),'bytes':path.stat().st_size,'records':1})
    manifest={'format':'v3.1/MFM4','data_version':plan['data_version'],'molecules':dict(indices),'conformers':dict(counts),
        'files':files,'split_roots':{s:str(p) for s,p in roots.items()},'id_map_physical_paths':idmaps,'storage':storage,'scratch_cleanup':scratch_cleanup,
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
        if plan.get('gpu_nodes'):raise ValueError('SHARED_SINGLE_COPY_REQUIRES_NO_NODE_DISTRIBUTION')
        print(json.dumps(manifest,ensure_ascii=False),flush=True);return
    from_plan(plan,required=True)
    module,name=plan['source_factory'].split(':',1);factory=getattr(importlib.import_module(module),name)
    schema,molecules=factory(plan)
    print(json.dumps(export(plan,molecules,schema),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
