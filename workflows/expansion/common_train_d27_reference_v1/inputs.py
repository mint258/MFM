"""Full Common effectiveTRAIN, exact accepted D5 IDs and canonical owner sidecars."""
import collections
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
from ..common import load,reference,require,dump_new
from ..portable_sources_v1.transport import verify
from .inventory import need
from . import science
N=11231854


def rows(ref,columns=None):
    import pyarrow.parquet as pq
    p=verify(ref);before=p.stat()
    with pq.ParquetFile(p)as table:
        for batch in table.iter_batches(batch_size=4096,columns=columns,use_threads=False):yield from batch.to_pylist()
    after=p.stat();need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Immutable Parquet source changed')


def authorities(plan):
    from ..exact_nn_cached_v1.alpha_common import validate_manifest
    from ..alpha_common_graph_continuation_v1.transport import inputs
    full=plan.get('common_reference_manifest');membership_only=plan.get('common_membership_acceptance_reference')
    need(bool(full)!=bool(membership_only),'Choose one explicit actual full-graph or membership-only Common authority')
    if full:
        c=load(verify(full))
        if c.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
            from ..exact_nn_cached_v1.alpha_common_repaired import validate_manifest as validate_repaired
            validate_repaired(c);p=load(verify(c['original_full_source_receipt_reference']))
            common_kind='ACCEPTED_FULL_GRAPH_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
        else:
            validate_manifest(c);p=load(verify(c['actual_full_receipt_reference']))
            common_kind='ACCEPTED_FULL_GRAPH_REFERENCE'
        common_authority=full
    else:
        from .membership import accepted
        p,component,review=accepted(membership_only)
        common_kind='ROOT_ACCEPTED_COMPLETE_MEMBERSHIP_ONLY_NO_GRAPH_REFERENCE';common_authority=membership_only
    origin,header,members,role_refs,formal,mapping=inputs(load(verify(p['plan'])))
    membership={};roles={}
    for ref in members:
        for row in rows(ref,['molecule_id','common_population']):
            mid=row['molecule_id'];need(mid not in membership and type(row['common_population'])is bool,'Unique explicit Common membership required')
            membership[mid]=row['common_population']
    for ref in role_refs:
        for row in rows(ref,['molecule_id','effective_role']):
            mid=row['molecule_id'];role=row['effective_role'];need(mid not in roles and role in('TRAIN','VAL','FULL','EMBARGO'),'Unique frozen whole-molecule effective role required')
            roles[mid]=role
    count=collections.Counter(roles[mid]for mid,yes in membership.items()if yes)
    need(count=={'TRAIN':1188592,'VAL':7530},'Exact full Common TRAIN/VAL scope required')
    delivery=load(verify(plan['diagnostic_delivery_reference']))
    need(delivery['schema']=='DATA_V1_D5_PROVISIONAL_DELIVERY_V1' and delivery.get('scope_version')=='D5_OLD_COMPLETE_FROZEN_RANDOM_20261029_V1',
        'Actual frozen old-complete D5 components required, not a fabricated full Common D5')
    acceptance=load(verify(delivery['actual_acceptance_reference']))
    need(acceptance['schema']=='ROOT_ACCEPTED_BOUNDED_OLD_COMPLETE_D5_COMPONENTS_V1'
        and acceptance['status']=='ACTUAL_C0_OLD_COMPLETE_D5_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON'
        and acceptance['reviewer']=='root','Real independent old D5 acceptance retained')
    parent=acceptance['actual_parent'];account=load(verify(parent['accounting']))
    need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'and account['endpoint']=='202.38.247.57:22'
        and account['uid']==1278 and account['raw_sacct_reference']==parent['raw']
        and len(account['parents'])==1 and account['parents'][0]['job_id']=='4525184'
        and account['parents'][0]['state']=='COMPLETED'and account['parents'][0]['exit_code']=='0:0',
        'Original actual Main D5 C0 accounting required; no Alpha parent fabrication')
    verify(parent['manifest']);verify(parent['proof']);verify(parent['raw'])
    comp=delivery['components'];base={};targets=set();physical={}
    for row in rows(comp['diagnostic_base_reference']):
        key=(row['molecule_id'],row['geometry_source'],row['geometry_id']);need(key not in base,'Duplicate actual diagnostic base')
        base[key]=row
    for row in rows(comp['diagnostic_targets_reference']):
        key=(row['molecule_id'],row['geometry_source'],row['geometry_id']);need(key not in targets,'Duplicate actual base/child target')
        targets.add(key)
    need(len(base)==40000 and set(base)<=targets,'All40000 real held bases and actual child targets required')
    mids={source:{key[0]for key in base if key[1]==source}for source in('pm7','uff_sprime')}
    need(mids['pm7']==mids['uff_sprime']and len(mids['pm7'])==20000
        and all(membership.get(mid)is True and roles.get(mid)=='TRAIN'for mid in mids['pm7']),
        'The unchanged20000 diagnostic molecules must be actual new Common TRAIN; no re-selection')
    for row in rows(comp['actual_heldout_geometry_reference'],
            ['molecule_id','geometry_source','geometry_id','native_record_id','sprime_conf_idx','parent_geometry_id']):
        key=(row['molecule_id'],row['geometry_source'],row['geometry_id'])
        if key in base:
            need(row['parent_geometry_id']is None and key not in physical,'Actual unique base geometry required')
            physical[key]=row
    need(set(physical)==set(base),'All actual diagnostic base physical IDs required')
    held=set()
    for key,row in physical.items():
        if key[1]=='pm7':
            need(row['native_record_id']and row['sprime_conf_idx']is None,'PM7 native ID cannot be inferred from geometry ID')
            held.add((key[0],row['native_record_id']))
        else:need(row['native_record_id']is None and type(row['sprime_conf_idx'])is int and row['sprime_conf_idx']>=0,'Independent S-prime physical index required')
    need(len(held)==20000,'Exact actual PM7 held native keys required')
    proof={'common_authority_kind':common_kind,'common_authority_reference':common_authority,'original_D5_delivery':plan['diagnostic_delivery_reference'],
        'original_D5_acceptance_reference':delivery['actual_acceptance_reference'],'diagnostic_bases':40000,
        'diagnostic_molecules':20000,'diagnostic_targets':len(targets),'PM7_held_native_keys':20000,
        'D5_provisional_scope_not_relabelled_full_Common':True,'old_train_all_not_used_as_fit_population':True,'original_Main_D5_parent':parent,
        'historic_large_input_binding_SQLite_reopened_or_transported':False,
        'Common_role_molecules':dict(count),'membership_references':members,'role_references':role_refs,
        'D5_component_references':{k:comp[k]for k in('diagnostic_base_reference','diagnostic_targets_reference','actual_heldout_geometry_reference','actual_field_input_binding_reference')}}
    return membership,roles,held,proof


def eligibility(plan,root,groups,guard,codec,support):
    import numpy as np
    members,roles,held,proof=authorities(plan)
    root=Path(root);directory=root/'eligibility';directory.mkdir(exist_ok=False)
    arrays={'fit':np.memmap(directory/'fit.u8',dtype='u1',mode='w+',shape=(N,)),
        'owner':np.memmap(directory/'owner.bytes32',dtype='u1',mode='w+',shape=(N,32)),
        'role':np.memmap(directory/'role.u8',dtype='u1',mode='w+',shape=(N,)),
        'atoms':np.memmap(directory/'atoms.u32',dtype='<u4',mode='w+',shape=(N,)),
        'group':np.memmap(directory/'group.u16',dtype='<u2',mode='w+',shape=(N,))}
    jobs={str(g['source_job_id']):g['group_index']for g in groups};need(len(jobs)==171,'Original171 distinct logical owner groups required')
    dbpath=verify(plan['canonical_index']);db=sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True)
    from ..exact_nn_cached_v1.cache import parent_sqlite_runtime
    sqlite_runtime=parent_sqlite_runtime(db,plan.get('sqlite_cache_bytes'))
    cursor=db.execute('SELECT '+','.join(support.RECORD_COLUMNS)+' FROM records ORDER BY record_ordinal')
    counts=collections.Counter();matched=set();fit_atoms=0;total=0
    try:
        for raw in cursor:
            owner=dict(zip(support.RECORD_COLUMNS,raw));i=owner['record_ordinal'];mid=owner['molecule_id'];rid=owner['record_id']
            need(i==total and i<N and mid in roles and str(owner['job_id'])in jobs,'Complete original canonical owner order/role/job coverage required')
            role=roles[mid];need(role==owner['new_role'],'Frozen effective roles must match original canonical owner')
            if role in('TRAIN','VAL'):need(mid in members,'No missing Common membership can silently become an exclusion')
            key=(mid,rid);held_here=key in held;matched.update([key]if held_here else [])
            yes=members.get(mid,False);fit=(role=='TRAIN'and yes and not held_here)
            reason='ROLE_'+role if role!='TRAIN'else 'OUTSIDE_COMMON'if not yes else 'D5_HELD_BASE'if held_here else 'FIT'
            counts[reason]+=1;fit_atoms+=owner['total_atoms']if fit else 0
            arrays['fit'][i]=fit;arrays['owner'][i]=np.frombuffer(codec.owner_signature(owner),dtype='u1')
            arrays['role'][i]=support.ROLES[role];arrays['atoms'][i]=owner['total_atoms'];arrays['group'][i]=jobs[str(owner['job_id'])]
            total+=1
            if total%8192==0:guard.check()
        need(total==N and matched==held,'All canonical records and every exact PM7 diagnostic key required')
        need(counts['FIT']==10953084 and counts['D5_HELD_BASE']==20000,'Actual Common TRAIN10973084 minus20000 PM7 base records required')
        for array in arrays.values():
            array.flush()
            with Path(array.filename).open('rb')as stream:os.fsync(stream.fileno())
    finally:db.close()
    refs={key:reference(array.filename)for key,array in arrays.items()}
    result={'schema':'PUBCHEM_COMMON_TRAIN_D27_ELIGIBILITY_V1','status':'COMPLETE_CPU_OWNER_ROLE_AND_D5_ANTI_JOIN',
        'canonical_sqlite_runtime':sqlite_runtime,'original_all_role_records':N,'reason_counts':dict(counts),'fit_records':counts['FIT'],'fit_atom_upper_bound':fit_atoms,
        'valid_leaf_output_upper_bound_bytes':8*(26*counts['FIT']+fit_atoms),'arrays':refs,'authority_proof':proof,
        'PM7_all_tasks_of_exact_held_base_excluded':True,'D27_are_original_base_tasks_not_invented_perturbed_children':True}
    dump_new(directory/'manifest.json',result);return result,reference(directory/'manifest.json')
