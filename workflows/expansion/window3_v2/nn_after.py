"""Fixed1M NN against an explicitly configured full reference.

Reuse the existing validated integer native kernel. Fork inherits its sealed
reference; each process has its own COW order cache and query workspace. The
closed all-graph result is reused. The stereo supplement adds one explicit
3D-member reference, preserving the whole v1 prefix and original fingerprints.
No chemistry, new fingerprints, artifact digests or QA pass.
"""
import argparse
from array import array
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
from itertools import zip_longest
import json
import math
import multiprocessing
import os
from pathlib import Path
import time
from .capacity import protect

WIDTH=256
NATIVE=CACHE=None
REF_COUNT=0


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path=Path(path); temporary=path.with_suffix(path.suffix+'.pending')
    temporary.write_text(json.dumps(value,allow_nan=False)+'\n')
    os.replace(temporary,path)


def pack(inputs, out, base_count=1196122, added_count=2500000, members_path=None, config=None):
    """Original ordinals are a byte-copied prefix; additions keep source order."""
    done=out/'reference.json'
    if done.exists(): return read(done)
    fp=out/'reference.bin'; keys=out/'reference.keys'
    base_fp=inputs/'before_fingerprints.bin'; base_keys=inputs/'before_keys.ascii'
    if base_fp.stat().st_size!=base_count*WIDTH or base_keys.stat().st_size!=base_count*28:
        raise ValueError('ORIGINAL_REFERENCE_CARDINALITY')
    guard = config or {}
    members = None
    if members_path is not None:
        with Path(members_path).open() as source:
            members = {json.loads(line)['molecule_id'] for line in source}
        if len(members) != added_count:
            raise ValueError('EXACT_3D_MEMBER_POPULATION_REQUIRED')
    for source_path,target_path in ((base_fp,fp),(base_keys,keys)):
        protect(guard)
        with source_path.open('rb') as src, target_path.open('wb') as dst:
            for raw in iter(lambda:src.read(8<<20),b''):
                protect(guard); dst.write(raw)
    count=0
    with (inputs/'addition_projection.jsonl').open() as source, fp.open('ab') as f, keys.open('ab') as k:
        for line in source:
            row=json.loads(line)
            if members is not None:
                if row['molecule_id'] not in members: continue
                members.remove(row['molecule_id'])
            raw=bytes.fromhex(row['ecfp4_2048_hex']); key=row['full_key'].encode('ascii')
            if len(raw)!=WIDTH or len(key)!=27: raise ValueError('REFERENCE_FP_KEY_SHAPE')
            f.write(raw); k.write(key+b'\n'); count+=1
            if count % 4096 == 0: protect(guard)
    if members: raise ValueError('3D_MEMBER_MISSING_FROM_ORIGINAL_PROJECTION')
    if count!=added_count: raise ValueError('FULL_SELECTED_ADDITION_REQUIRED')
    value={'molecules':base_count+count,'original_prefix':base_count,'added':count,
           'fingerprints':str(fp),'keys':str(keys),'fingerprint_recipe':'ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',
           'members_path':str(members_path) if members_path is not None else None}
    save(done,value); return value


def load_native(binary, fingerprints, expected):
    global NATIVE,CACHE,REF_COUNT
    name='_ecfp4_inverted_kernel_v1'
    spec=importlib.util.spec_from_file_location(name,binary)
    NATIVE=importlib.util.module_from_spec(spec); spec.loader.exec_module(NATIVE)
    if NATIVE.build_info()['implementation']!='INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1':
        raise ValueError('EXISTING_VALIDATED_KERNEL_REQUIRED')
    # The C API requires a positive uint64. Its representable maximum disables
    # the old artificial RSS gate; physical allocation failures stay real.
    CACHE=NATIVE.create((1<<64)-1)
    count=0
    with Path(fingerprints).open('rb',buffering=8<<20) as source:
        for raw in iter(lambda:source.read(WIDTH),b''):
            if len(raw)!=WIDTH: raise ValueError('INCOMPLETE_REFERENCE_WORDS')
            NATIVE.append(CACHE,raw); count+=1
    if count!=expected: raise ValueError('WHOLE_REFERENCE_REQUIRED')
    NATIVE.seal(CACHE)
    if NATIVE.stats(CACHE)['reference_records_loaded']!=expected: raise ValueError('NATIVE_REFERENCE_COUNT')
    REF_COUNT=expected


def ready():
    return os.getpid(),NATIVE.stats(CACHE)['reference_records_loaded']


def batch(task):
    index, rows=task; results=[]
    for fp_id,raw in rows:
        value=NATIVE.nearest(CACHE,raw)
        n,d=value['score_numerator'],value['score_denominator']; ordinal=value['reference_ordinal']
        if (value['reference_molecules']!=REF_COUNT or
            value['evaluated_references']+value['strictly_bound_pruned_references']!=REF_COUNT or
            not 0<=ordinal<REF_COUNT or not 0<=n<=d or not 1<=d<=2048):
            raise ValueError('EXACT_NATIVE_INTEGER_ACCOUNTING')
        results.append((fp_id,n,d,ordinal))
    return index,results


def queries(inputs, expected=1000000):
    records=[]; unique=[]; ids={}
    with (inputs/'sample_query.jsonl').open() as query, (inputs/'before_coverage.jsonl').open() as before:
        for ordinal,pair in enumerate(zip_longest(query,before)):
            if None in pair: raise ValueError('FIXED_QUERY_BEFORE_ROW_ALIGNMENT')
            q,b=map(json.loads,pair)
            if (b['sample_ordinal']!=ordinal or q['cid']!=b['cid'] or q['full_key']!=b['full_key']):
                raise ValueError('FIXED_QUERY_BEFORE_ID_ALIGNMENT')
            raw=bytes.fromhex(q['ecfp4_2048_hex']); old=b['nearest_reference_tanimoto']
            if len(raw)!=WIDTH or not math.isfinite(old) or not 0<=old<=1: raise ValueError('QUERY_SCORE_SHAPE')
            fp_id=ids.get(raw)
            if fp_id is None:
                fp_id=len(unique); ids[raw]=fp_id; unique.append(raw)
            records.append((q['cid'],q['full_key'],fp_id,old))
    if len(records)!=expected: raise ValueError('EXACT_FIXED_ONE_MILLION_QUERIES')
    return records,unique


def run(config):
    protect(config)
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<config['workers']:
        raise RuntimeError('ACTUAL_CPU_SLURM_ALLOCATION_REQUIRED')
    out=Path(config['output']); out.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(out/'producer.lock').open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'summary.json').exists():
        print('Existing completed fixed1M result retained; no new NN calls',flush=True)
        return
    inputs=Path(config['inputs']); started=time.monotonic()
    added_count=config.get('added_reference_molecules',2500000)
    members_path=config.get('members_path')
    scope=config.get('reference_scope','all_source_graphs')
    if (scope not in {'all_source_graphs','pubchem_with_3D'} or
            (scope=='pubchem_with_3D') != bool(members_path) or
            (members_path and not config.get('disk_checks'))):
        raise ValueError('EXPLICIT_REFERENCE_SCOPE_AND_DISK_PROTECTION_REQUIRED')
    reference=pack(inputs,out,added_count=added_count,members_path=members_path,config=config)
    reference_count=1196122+added_count
    if (reference['molecules']!=reference_count or reference['original_prefix']!=1196122
            or reference['added']!=added_count or reference.get('members_path')!=members_path):
        raise ValueError('ORIGINAL_PREFIX_PLUS_WHOLE_FIRST_BATCH')
    load_native(config['binary'],reference['fingerprints'],reference['molecules'])
    print('Loaded sealed full reference',reference['molecules'],flush=True)
    # Fork before importing Arrow or creating any other parent threads. Only
    # the sealed native reference is inherited, not the 1M Python record table.
    context=multiprocessing.get_context('fork')
    with ProcessPoolExecutor(max_workers=config['workers'],mp_context=context) as pool:
        ready_values=[f.result() for f in [pool.submit(ready) for _ in range(config['workers'])]]
        if any(n!=reference_count for _,n in ready_values): raise ValueError('FULL_REFERENCE_WORKERS')
        records,raws=queries(inputs)
        if len(raws)!=990134: raise ValueError('FROZEN_BASELINE_DISTINCT_FINGERPRINT_COUNT')
        print('Fixed query rows',len(records),'distinct fingerprints',len(raws),flush=True)
        import pyarrow as pa
        import pyarrow.parquet as pq
        numerators=array('H',[0])*len(raws); denominators=array('H',[0])*len(raws)
        ordinals=array('I',[0])*len(raws)
        blocks=out/'score_blocks'; blocks.mkdir(exist_ok=True)
        schema=pa.schema([('fp_id',pa.int32()),('numerator',pa.int16()),('denominator',pa.int16()),('reference_ordinal',pa.int32())])
        def consume(index, values, write):
            if write:
                protect(config)
                path=blocks/('%06d.parquet'%index)
                pq.write_table(pa.Table.from_pylist([dict(zip(schema.names,row)) for row in values],schema=schema),path,compression='zstd')
                save(blocks/('%06d.done.json'%index),{'rows':len(values),'path':str(path)})
            for fp_id,n,d,ordinal in values:
                numerators[fp_id]=n; denominators[fp_id]=d; ordinals[fp_id]=ordinal
        waiting=set(); closed=0; chunk=config.get('query_batch',512)
        for index,offset in enumerate(range(0,len(raws),chunk)):
            done=blocks/('%06d.done.json'%index)
            if done.exists():
                saved=read(done)
                # Resume consumes only already closed scores, with no NN retry.
                table=pq.read_table(saved['path']); values=list(zip(*(table[n].to_pylist() for n in schema.names)))
                consume(index,values,False); closed+=len(values); continue
            if (out/'DRAIN_FOR_WINDOW2').exists(): break
            waiting.add(pool.submit(batch,(index,list(enumerate(raws[offset:offset+chunk],offset)))))
            if len(waiting)>=2*config['workers']:
                future=next(as_completed(waiting)); waiting.remove(future)
                i,values=future.result(); consume(i,values,True); closed+=len(values)
                save(out/'progress.json',{'closed_distinct_fingerprints':closed,'expected_distinct_fingerprints':len(raws),
                     'queries':len(records),'reference_molecules':reference_count,'wall_seconds':time.monotonic()-started,
                     'job_id':os.environ['SLURM_JOB_ID']})
        for future in as_completed(waiting):
            i,values=future.result(); consume(i,values,True); closed+=len(values)
        if closed!=len(raws):
            print('Drained for window two; closed scores retained',closed,flush=True); return
    if any(d==0 for d in denominators): raise ValueError('MISSING_NATIVE_QUERY_RESULT')
    from ..distribution_report_v1.aggregate import Moments
    before_m=Moments('nearest_tanimoto'); after_m=Moments('nearest_tanimoto')
    keys=Path(reference['keys']).read_bytes()
    if len(keys)!=reference_count*28: raise ValueError('REFERENCE_KEY_ORDINAL_ALIGNMENT')
    identities=set(keys.splitlines()); counts=Counter(); files=[]; buffer=[]
    result_schema=pa.schema([('sample_ordinal',pa.int64()),('cid',pa.int64()),('full_key',pa.string()),
        ('before_tanimoto',pa.float64()),('nearest_reference_tanimoto',pa.float64()),('gain',pa.float64()),
        ('reference_ordinal',pa.int64()),('nearest_reference_key',pa.string()),('reference_identity_present',pa.bool_()),
        ('fingerprint_self_match',pa.bool_()),('nearest_identity_self_match',pa.bool_()),('reference_role',pa.string())])
    def flush():
        if not buffer:return
        protect(config)
        path=out/('coverage_%04d.parquet'%len(files))
        pq.write_table(pa.Table.from_pylist(buffer,schema=result_schema),path,compression='zstd')
        files.append({'path':str(path),'size':path.stat().st_size,'rows':len(buffer)}); buffer.clear()
    for sample,(cid,key,fp_id,old) in enumerate(records):
        score=numerators[fp_id]/denominators[fp_id]; ordinal=ordinals[fp_id]
        if score+1e-12+1e-12*abs(old)<old: raise ValueError('AUGMENTED_SCORE_BELOW_ORIGINAL_PREFIX')
        nearest=keys[ordinal*28:ordinal*28+27].decode('ascii')
        identity=key.encode('ascii') in identities
        before_m.add(old); after_m.add(score)
        counts['identity_present']+=identity; counts['score_one']+=score==1.; counts['nearest_identity_equal']+=key==nearest
        counts['strict_improvement']+=score>old; counts['zero_gain']+=score==old
        for name,threshold in [('0.4',.4),('0.6',.6),('0.8',.8)]:
            counts['before_below_'+name]+=old<threshold; counts['after_below_'+name]+=score<threshold
        buffer.append({'sample_ordinal':sample,'cid':cid,'full_key':key,'before_tanimoto':old,
            'nearest_reference_tanimoto':score,'gain':score-old,'reference_ordinal':ordinal,'nearest_reference_key':nearest,
            'reference_identity_present':identity,'fingerprint_self_match':score==1.,
            'nearest_identity_self_match':key==nearest,'reference_role':'after'})
        if len(buffer)==10000:flush()
    flush()
    if sum(f['rows'] for f in files)!=1000000: raise ValueError('FULL_FROZEN_QUERY_OUTPUT_COUNT')
    save(out/'manifest.json',files)
    summary={'queries':1000000,'distinct_query_fingerprints':len(raws),'reference_molecules':reference_count,
        'original_reference_prefix':1196122,'added_reference_molecules':added_count,'query_membership_and_order':'original1885183 sample_ordinal ASC',
        'fingerprint_recipe':reference['fingerprint_recipe'],'native_binary':config['binary'],
        'before':dict(zip(('n','mean','population_std','min','max'),before_m.summary())),
        'after':dict(zip(('n','mean','population_std','min','max'),after_m.summary())),
        'before_histogram':before_m.result(),'after_histogram':after_m.result(),'counts':dict(counts),
        'wall_seconds':time.monotonic()-started,'job_id':os.environ['SLURM_JOB_ID'],'workers':config['workers'],
        'new_fingerprints_computed':0,'reference_scope':scope,
        'new_nn_scope':'original fixed1M against full configured reference; all-graph result reused for stereo supplement'}
    save(out/'summary.json',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    run(read(parser.parse_args().config))
