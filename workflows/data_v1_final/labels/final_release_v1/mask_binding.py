"""Actual field-level geometry claims; original compact wire is only partitioned."""
import collections,importlib,json,sqlite3
from pathlib import Path
from . import contract as C,originals as O
from workflows.data_v1_final.labels.common_train_normalization_day_v1 import io as I,audit as U
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity

def complete_counts(counts,expected):
    C.need(not set(counts)-set(expected),'NO_UNREGISTERED_FIELD_CLAIM_COUNT')
    observed={key:counts.get(key,0) for key in expected}
    C.need(observed==expected,'FULL_COMMON_FIELD_MASK_BINDING_DENOMINATORS_NOT_ONLY_EXPORT_PILOT')
    return observed

def subset(row,ids,compact):
    """Intersect original bitsets; never assign a field cause to every leaf."""
    keep=set(ids);out={k:v for k,v in row.items()}
    for key in ('in_scope_fields','source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields'):
        out[key]=compact.bits(keep&set(compact.unpack(row[key])))
    for key in ('source_reason_groups','new_reason_groups','review_groups'):
        out[key]=[dict(g,fields=compact.bits(keep&set(compact.unpack(g['fields'])))) for g in row[key] if keep&set(compact.unpack(g['fields']))]
    out['leaf_exceptions']=[dict(v) for v in row['leaf_exceptions'] if v['field_id'] in keep]
    return out

def current_claims(d,proof,root):
    C.need(d.get('runtime_actual_field_claims_reference'),'NO_FUTURE_CLAIM_REF_CURRENT_CPU_PRODUCER_REQUIRED')
    ref=d['runtime_actual_field_claims_reference'];obj=I.load_data(ref,16<<20);req=proof['request']
    C.need(obj['schema']=='FAMILY_ACTUAL_FIELD_GEOMETRY_CLAIMS_V1' and obj['status']=='COMPLETE_COMMON_FIELD_GEOMETRY_CLAIMS_NOT_FINAL_RELEASE'
      and obj['uid']==1278 and obj['actual_parent_job_id']==str(proof['job_id']) and obj['actual_node']==req['node']
      and obj['startup_proof_reference']==C.Q.pin(req['startup_proof_path']) and obj['current_parent_C0_claimed'] is False
      and obj['unknown_field_claims']==0 and obj['expected_Common_field_counts']==obj['observed_Common_field_counts']
      and obj['coverage_scope']=='ALL_FINAL_COMMON_ACTUAL_CELLS_BY_FIELD_NOT_TASK_NAME','REAL_CURRENT_PARENT_COMPLETE_FIELD_CLAIMS_NOT_TASK_ALIAS')
    C.need(obj['source_entry_reference'] in req['source_references'] and obj['D5_components_reference']==d['d5_components_acceptance_reference'],
      'ACTUAL_CLAIM_BUILDER_SOURCE_D5_BINDING')
    parent=Path(root).parent;C.need(parent in Path(ref['path']).parents and parent in Path(obj['database_reference']['path']).parents,
      'DERIVED_CLAIMS_IN_THIS_PARENT_OUTPUT_NOT_UNDECLARED_EXTERNAL_DATA')
    I.ALLOWED[obj['database_reference']['path']]=obj['database_reference'];I.require(obj['database_reference'])
    module=importlib.import_module('workflows.data_v1_final.export.family_export_day_v1.project')
    C.need(C.Q.pin(Path(module.__file__).absolute())==obj['source_entry_reference'],'EXACT_ORIGINAL_FIELD_CLAIM_LOOKUP_SOURCE_OBJECT')
    return obj,module

def bind(d,proof,root,audit,fields,claims,module,budget):
    import pyarrow as pa,pyarrow.parquet as pq
    registry,reduce,series,compact,masks=O.objects();out=Path(root);out.mkdir();counts=collections.Counter();unbound=collections.Counter();refs=[];groups=[]
    dbpath=I.require(claims['database_reference']);before=identity(dbpath);db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    seen=sqlite3.connect(out/'bound_unique.sqlite');seen.execute('CREATE TABLE keys(gid TEXT,task INTEGER,PRIMARY KEY(gid,task)) WITHOUT ROWID')
    sidepath=I.require(d['_eligibility_reference']);side=sqlite3.connect(sidepath.as_uri()+'?mode=ro',uri=True)
    schema=compact.arrow_schema().append(pa.field('geometry_id',pa.string()))
    try:
        for gr in audit['group_reports']:
            budget.check();group=I.load_data(gr,16<<20);sink=U.Sink(out,'bound_group_%04d'%group['group_index'],schema)
            # Each accepted claim covers Common only. Outside-Common original masks stay retained separately.
            source_job=str(group['source_job_id']);rows=[]
            for pr in group['masks']:
                path=I.require(pr);frame=identity(path);handle=pq.ParquetFile(path,pre_buffer=False)
                try:
                    for batch in handle.iter_batches(batch_size=128,use_threads=False):
                        budget.check()
                        for row in batch.to_pylist():
                            present=db.execute('SELECT 1 FROM source_cells WHERE group_key=? AND record_ordinal=? AND task_code=? LIMIT 1',
                              (source_job,row['record_ordinal'],row['task_code'])).fetchone()
                            fids=compact.unpack(row['in_scope_fields'])
                            owner=side.execute('SELECT mid,common_population FROM eligibility WHERE ordinal=?',(row['record_ordinal'],)).fetchone()
                            C.need(owner is not None,'EXACT_ORIGINAL_MASK_OWNER_POPULATION')
                            if present is None:
                                C.need(owner[1]==0,'MISSING_COMMON_FIELD_GEOMETRY_CLAIM_NOT_OUTSIDE_POPULATION')
                                for fid in fids:unbound[str(fid)]+=1
                                continue
                            C.need(owner[1]==1,'OUTSIDE_COMMON_CANNOT_DILUTE_BOUND_FIELD_COVERAGE')
                            geometries=collections.defaultdict(list)
                            for fid in fids:
                                claim=module.mask_claim_for(db,source_job,row['record_ordinal'],row['task_code'],fid)
                                C.need(claim['binding_status']=='ACTUAL_DOUBLE_HASH_OR_NATIVE_PAYLOAD_BOUND'
                                  and claim['geometry_id'] and claim['record_ordinal']==row['record_ordinal']
                                  and claim['task_code']==row['task_code'] and claim['group_key']==source_job,
                                  'EXACT_ACTUAL_FIELD_INPUT_GEOMETRY_BINDING_NOT_NAME_OR_BASE_FALLBACK')
                                C.need(claim['molecule_id']==owner[0],'ACTUAL_FIELD_CLAIM_MOLECULE_BINDING')
                                geometries[claim['geometry_id']].append(fid);counts[str(fid)]+=1
                            for gid,ids in geometries.items():
                                seen.execute('INSERT INTO keys VALUES(?,?)',(gid,row['task_code']))
                                rows.append(dict(subset(row,ids,compact),geometry_id=gid))
                            if len(rows)>=128:sink.add(rows);rows=[]
                finally:handle.close();C.need(identity(path)==frame,'ORIGINAL_MASK_CHANGED_DURING_FIELD_BINDING')
            sink.add(rows);parts=sink.finish();refs.extend(parts);seen.commit()
            groups.append({'group_index':group['group_index'],'source_job_id':source_job,'mask_tables':parts,'rows':sink.rows})
        observed=complete_counts(counts,claims['expected_Common_field_counts'])
    finally:db.close();seen.close();side.close();C.need(identity(dbpath)==before,'ACTUAL_FIELD_CLAIM_DATABASE_CHANGED')
    return I.save(out/'manifest.json',{'schema':'FINAL_GEOMETRY_BOUND_VALIDITY_MASK_CANDIDATE_V1',
      'status':'EXACT_ORIGINAL_MASKS_BOUND_TO_ACCEPTED_D5_TARGETS','mask_tables':refs,'groups':groups,'field_map_reference':claims['field_map_reference'],
      'geometry_id_task_code_unique':True,
      'source_full_population_audit_reference':d['_audit_reference'],'original_mask_group_reports':audit['group_reports'],
      'actual_field_claim_reference':d['runtime_actual_field_claims_reference'],'actual_claim_database_reference':claims['database_reference'],
      'D5_components_reference':d['d5_components_acceptance_reference'],'bound_Common_counts':observed,'unbound_outside_Common_counts':dict(unbound),
      'reason_codebook_source_reference':C.Q.pin(C.REPO/'workflows/data_v1_final/labels/streaming_v1/compact.py'),
      'original_source_new_review_bits_and_sparse_causes_preserved':True,'raw_masks_outside_Common_retained_not_anomaly_exclusions':True,
      'current_parent_independent_C0_claimed':False,'final_consumer_release':False})
