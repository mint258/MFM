"""One final count and 1000 actual original-Parquet field comparison pass."""
import collections,concurrent.futures as cf,hashlib,json
from . import contract as C,io as I,verify as V,writer as W,wire,payload_io
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import parquet_qa
S=V.S

def target_arrays(arrays,compiled,tid):
    target=compiled['physical_targets'].get(tid)or compiled['ordered_record_targets'][tid]
    fields={m['field_key']for m in target['members']}
    direct={'values/'+tid,'valid/'+tid,'reason/'+tid,'pairs/'+tid}
    reasons={prefix+'/'+key for prefix in ('reason_fields_source','reason_fields_new','reason_fields_review','reason_leaf_index','reason_leaf_code')for key in fields}
    return {key:value for key,value in arrays.items()if key in direct or key in reasons
      or key.startswith('transport/'+tid+'/')or key.startswith('valid/transport/'+tid+'/')}

def run(db,stores,root,context,pool,budget):
    db.create_function('sample_rank',2,lambda store,gid:V.O.rank_hash(20261025,store,gid),deterministic=True)
    samples=db.execute("SELECT store,gid,parts FROM exported WHERE kind='labels' ORDER BY sample_rank(store,gid),store,gid LIMIT 1000").fetchall()
    C.need(len(samples)==1000,'ONE_RANDOM1000_SOURCE_SAMPLE')
    bystore=collections.defaultdict(list)
    for row in samples:bystore[row['store']].append(row)
    cast_digest=hashlib.sha256();counts=[];tasks={};total_records=0;total_bytes=0
    roles=dict(db.execute('SELECT role,count(*) FROM molecules GROUP BY role').fetchall())
    C.need(roles==C.COUNTS,'EXACT_FROZEN_PILOT_COUNTS')
    for reference in stores:
        budget.check();manifest=I.load_data(reference,8<<20);side=manifest['f64_authority']['reference']
        authority=I.connect(side['path'],True)
        try:
            with W.Reader(manifest['path'])as reader:
                planned=db.execute('SELECT count(*) FROM exported WHERE store=?',(manifest['name'],)).fetchone()[0]
                C.need(reader.count==manifest['records']==planned and reader.molecule_count==manifest['molecules']
                  and authority.execute('SELECT count(*) FROM authority').fetchone()[0]==planned,'EXPORT_COUNTS_AGREE')
                for row in bystore.get(manifest['name'],[]):
                    budget.check();metadata,arrays=reader.get(row['gid'])
                    C.need(metadata['effective_role']in C.COUNTS,'FROZEN_TRAIN_OR_ROUTINE_VAL_ROLE')
                    saved=authority.execute('SELECT metadata,payload,sha FROM authority WHERE rid=?',(row['gid'],)).fetchone()
                    C.need(saved is not None and saved['sha']==metadata['permanent_F64_sidecar_record']['payload_sha256'],'SAMPLED_AUTHORITY_REFERENCE')
                    actual_f64=S.unpack(payload_io.decode_payload(saved['payload']));actual_metadata=json.loads(payload_io.decode_metadata(saved['metadata']))
                    annotations=actual_metadata['source_projection_annotations'];granularity=actual_metadata['reason_granularity']
                    for tid in json.loads(row['parts']):
                        expected=target_arrays(actual_f64,context['compiled'],tid)
                        note=dict(annotations[tid]);note[tid]=granularity[tid]
                        locator=actual_metadata['permanent_source_locators'][tid];part=locator['typed_part_reference']
                        task=tasks.setdefault(part['path'],(part,[]))
                        task[1].append(dict(locator=locator,n=metadata['n_atoms'],tid=tid,packed=S.pack(expected,note)))
                    cast_digest.update(wire.original_cast_compare(actual_f64,arrays).encode())
                counts.append(dict(name=manifest['name'],kind=manifest['kind'],records=planned,molecules=reader.molecule_count,
                  data_reference=manifest['data'],manifest_reference=manifest['manifest_reference'],F64_reference=side))
                total_records+=planned;total_bytes+=manifest['data']['bytes']+manifest['manifest_reference']['bytes']+side['bytes']
        finally:authority.close()
    results=[];pending={};work=iter(tasks.values());done=False
    while pending or not done:
        while not done and len(pending)<32:
            budget.check()
            try:item=next(work)
            except StopIteration:done=True;break
            pending[pool.submit(parquet_qa.replay,item,context=context)]=True
        if pending:
            ready,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in ready:pending.pop(future);results.append(future.result())
    C.need(sum(r['pieces']for r in results)==sum(len(json.loads(r['parts']))for r in samples),'ALL_SAMPLED_FIELDS_COMPARED_WITH_ORIGINAL_PARQUET')
    summary=dict(schema='D3_SINGLE_EXPORT_MANIFEST_V1',version='v1-pilot-provisional',pilot_counts=roles,
      stores=counts,exported_records=total_records,total_payload_bytes=total_bytes,source_roundtrip_records=1000,
      original_parquet_results=results,original_once_F32_cast_digest=cast_digest.hexdigest(),
      single_final_count_and_source_sample_pass=True,domain_numerical_self_comparison=False,
      full_F64_second_scan=False,independent_replay=False,independent_16reader_pass=False,
      preproduction_Source_tests_run=0,Model_ACK=False)
    return I.save(root/'export_manifest.json',summary),summary
