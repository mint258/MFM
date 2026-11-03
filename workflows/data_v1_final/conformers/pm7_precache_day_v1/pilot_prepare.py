"""CPU-only old-baseline scalar pilot preselection; never final Common or D5.

All original PM7 molecules remain scheduled. The old complete-Sprime subset
only changes which original whole-molecule tasks reach the unchanged pool first.
The old accepted authority supplies strict-usable counts; no new count is
invented from status, file names, missing claims, or an in-progress parent.
"""
import importlib,pathlib,sys
from . import metadata as M

POLICY='ROOT_OLD_COMPLETE_SPRIME_PRIORITY_POLICY_V1'
APPROVED='APPROVED_CPU_SCALAR_PRESELECTION_NOT_COMMON'
SIZES=(120000,240000,600000)
JOIN_SQL='SELECT p.molecule_id,p.S_conformers,p.S_usable_conformers,p.Sprime_conformers,p.Sprime_status,p.elements_atomic_numbers,p.heavy_atoms,r.effective_role,r.source_role,r.records,r.file_group,r.legacy_routine_molecule,p.Sprime_conformers AS merged_uff_count,NULL::VARCHAR AS fill_status FROM pilot_original_p p JOIN pilot_original_roles r USING(molecule_id) ORDER BY molecule_id'

def ranking_module():
    # This is the original exporter import convention, not a replacement or a
    # monkeypatch of any scientific function/global.
    export=M.REPO/'workflows/data_v1_final/export'
    if str(export) not in sys.path:sys.path.insert(0,str(export))
    module=importlib.import_module('pipeline_v1.io')
    M.need(pathlib.Path(module.__file__).absolute()==export/'pipeline_v1/io.py','DIRECT_ORIGINAL_D5_RANK_HASH_OBJECT')
    return module

def policy(reference,base):
    """Only small, explicitly declared policy/authority metadata, even on login."""
    if reference is None:return None,[],[]
    v=M.meta(reference)
    M.need(v['schema']==POLICY and v['status']==APPROVED and v['reviewer']=='root'
        and type(v['seed']) is int and 0<=v['seed']<2**63-2 and v['seed']==20261025
        and v['nested_train_counts']==list(SIZES) and v['pilot_train']==50000 and v['pilot_val']==5000
        and v['strict_usable_counts_from_original_accepted_audit']is True
        and v['old_geometry_and_records_not_replaced']is True and v['scheduling_priority_only']is True
        and v['full_Common_or_D4_D5_D3_release']is False and type(v['root_reason'])is str and bool(v['root_reason'].strip()),'ROOT_EXPLICIT_BOUNDED_PILOT_POLICY_NOT_FULL_COMMON')
    config=M.meta(v['original_config_reference']);roles=M.meta(config['roles_authority'])
    role_manifest=M.meta(roles['source_role_manifest']);old=M.meta(config['sprime_manifest'])
    M.need(config['schema']=='DATA_V1_SPRIME_FORMAL_CPU_AUTO_V3'
        and config['per_molecule']==base['per_molecule']
        and config['sprime_manifest']==v['old_sprime_manifest_reference']
        and config['roles_authority']==v['roles_authority_reference']
        and roles['status']=='FROZEN' and roles['validation_source']=='ROUTINE' and roles['all_conformers_same_role']is True
        and role_manifest['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','EXACT_OLD_BASELINE_AND_ALL_FROZEN_ROLES')
    # The Root review supplies the independently accepted historical baseline
    # chain. This routine checks its actual small bytes, without reading DATA.
    M.meta(v['old_complete_Sprime_acceptance_reference'])
    role_refs=[{k:r[k] for k in ('path','bytes','sha256')} for r in role_manifest['outputs'] if '/molecule_roles/' in r['path']]
    old_refs=[{k:r[k] for k in ('path','bytes','sha256')} for r in old['references'] if r['kind']=='conformers']
    M.need(len(role_refs)==16 and len(old_refs)==5,'ALL16_ROLE_AND_FIVE_OLD_SPRIME_SOURCE_LOCATORS')
    sources=M.unique([reference,v['original_config_reference'],v['old_complete_Sprime_acceptance_reference'],config['roles_authority'],
        config['sprime_manifest'],roles['source_role_manifest'],roles['actual_closure'],*v['evidence_references']])
    for ref in sources:M.need(M.pin(ref['path'])==ref,'ACTUAL_DECLARED_SMALL_PILOT_SOURCE')
    data=M.unique([config['per_molecule'],*role_refs,*old_refs])
    return dict(v,config=config,role_refs=role_refs,old_refs=old_refs),sources,data

def rank_members(rows,seed):
    """Exact original D5 role/domain/hash/ID tie break, no size/runtime filter."""
    rank=ranking_module().rank_hash;seen=set();groups={'TRAIN':[],'VAL':[]}
    for row in rows:
        mid,role=row['molecule_id'],row['effective_role']
        M.need(type(mid)is str and mid and mid not in seen and role in groups,'UNIQUE_COMPLETE_OLD_MOLECULE_AND_ORIGINAL_ROLE')
        seen.add(mid);groups[role].append(mid)
    return {role:sorted(mids,key=lambda mid:(rank(seed,role,mid),mid)) for role,mids in groups.items()}

def segments(descriptors,priority_counts):
    """Two disjoint passes over the original descriptors; no new task identity."""
    result=[]
    M.need(set(priority_counts)<=set(range(len(descriptors))),'PRIORITY_DESCRIPTOR_MUST_BE_ORIGINAL')
    for phase in ('PILOT_PRIORITY','ORIGINAL_REMAINDER'):
        for ordinal,d in enumerate(descriptors):
            n=priority_counts.get(ordinal,0)
            M.need(type(n)is int and 0<=n<=d['molecules'],'BOUNDED_PRIORITY_COUNT')
            count=n if phase=='PILOT_PRIORITY' else d['molecules']-n
            if count:result.append({'descriptor_ordinal':ordinal,'phase':phase,'molecules':count})
    M.need(sum(s['molecules'] for s in result)==sum(d['molecules'] for d in descriptors),'PRIORITY_AND_REMAINDER_EXACT_UNION')
    return result

def select_phase(metas,by,priority,phase):
    M.need(phase in ('PILOT_PRIORITY','ORIGINAL_REMAINDER','ORIGINAL_ALL'),'EXACT_SCHEDULING_PHASE')
    selected=metas if phase=='ORIGINAL_ALL' else [m for m in metas if (m['molecule_id'] in priority)==(phase=='PILOT_PRIORITY')]
    # Preserve all original metadata, record arrays, per-descriptor native order.
    return selected,{m['molecule_id']:by[m['molecule_id']] for m in selected}

def build(ctx,db,base,descriptors):
    """After actual allocation/fixtures, before the first native geometry math."""
    reference=ctx.plan.get('pilot_priority_review_reference')
    if reference is None:
        return None,set(),[{'descriptor_ordinal':i,'phase':'ORIGINAL_ALL','molecules':d['molecules']} for i,d in enumerate(descriptors)]
    v,sources,data=policy(reference,base);ctx.authorized([*sources,*data]);ctx.check()
    from workflows.data_v1_final.conformers.postprocess_day_v1.math_bridge import membership,exclusion_gates
    import pyarrow as pa
    for ref in (v['config']['per_molecule'],*v['role_refs']):ctx.require(ref)
    q=lambda value:"'"+str(value).replace("'","''")+"'"
    db.execute('CREATE VIEW pilot_original_p AS SELECT * FROM read_parquet('+q(base['per_molecule']['path'])+')')
    db.execute('CREATE VIEW pilot_original_roles AS SELECT * FROM read_parquet(['+','.join(q(r['path']) for r in v['role_refs'])+'])')
    M.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM pilot_original_p').fetchone()==(1220466,1220466)
        and db.execute('SELECT count(*),count(DISTINCT molecule_id),sum(records) FROM pilot_original_roles').fetchone()==(1220466,1220466,11231854),'EXACT_COMPLETE_ORIGINAL_MOTHER_AND_ROLE_CENSUS')
    M.need(db.execute('SELECT count(*) FROM (SELECT molecule_id FROM pilot_original_p EXCEPT SELECT molecule_id FROM pilot_original_roles)').fetchone()[0]==0,'NO_MOLECULE_LOST_IN_FULL_ROLE_JOIN')
    source_rows=db.execute(JOIN_SQL).fetch_arrow_table().to_pylist()
    role_counts={r[0]:{'molecules':r[1],'records':r[2]} for r in db.execute('SELECT effective_role,count(*),sum(records) FROM pilot_original_roles GROUP BY effective_role').fetchall()}
    M.need(role_counts==M.meta(v['config']['roles_authority'])['roles'],'ALL_ORIGINAL_TRAIN_VAL_FULL_ROLES_PRESERVED')
    rows=[];eligible=[]
    for row in source_rows:
        row.update(membership(row))
        item={k:row[k] for k in ('molecule_id','effective_role','source_role','records','S_conformers','S_usable_conformers','Sprime_conformers','Sprime_status','merged_uff_count','elements_atomic_numbers','heavy_atoms','common_population','exclusion_reasons','pprime_two_conformers_pending')}
        item['scalar_complete_old_Sprime']=item.pop('common_population');rows.append(item)
        item['pending_availability_reasons']=[r for r in item['exclusion_reasons'] if r=='INSUFFICIENT_ACCEPTED_SPRIME']
        item['scientific_exclusion_reasons']=[r for r in item['exclusion_reasons'] if r not in ('INSUFFICIENT_ACCEPTED_SPRIME','OUTSIDE_TRAIN_ROUTINE_VAL')]
        if item['scalar_complete_old_Sprime']:eligible.append(item)
    # Original threshold report is retained, including a failed overall gate.
    # Nonselection in a bounded pilot is not relabeled a chemical exclusion.
    gates=exclusion_gates(source_rows);M.need(gates['mother_molecules']==1214218,'ORIGINAL_TRAIN_VAL_GATE_DENOMINATOR')
    ranked=rank_members(eligible,v['seed'])
    pilot_ready=len(ranked['TRAIN'])>=50000 and len(ranked['VAL'])>=5000
    db.register('pilot_scalar_rows',pa.Table.from_pylist(rows));db.execute('CREATE TABLE pilot_scalar_membership AS SELECT * FROM pilot_scalar_rows');db.unregister('pilot_scalar_rows')
    ranking=[{'molecule_id':mid,'effective_role':role,'selection_rank':i} for role in ('TRAIN','VAL') for i,mid in enumerate(ranked[role])]
    rank_schema=pa.schema([('molecule_id',pa.string()),('effective_role',pa.string()),('selection_rank',pa.int64())])
    db.register('pilot_ranks',pa.Table.from_pylist(ranking,schema=rank_schema));db.execute('CREATE TABLE pilot_complete_old_ranked AS SELECT m.*,r.selection_rank FROM pilot_scalar_membership m JOIN pilot_ranks r USING(molecule_id,effective_role)');db.unregister('pilot_ranks')
    db.execute("CREATE TABLE pilot_priority AS SELECT molecule_id,effective_role,selection_rank FROM pilot_complete_old_ranked WHERE "+("(effective_role='TRAIN' AND selection_rank<50000) OR (effective_role='VAL' AND selection_rank<5000)" if pilot_ready else 'FALSE'))
    priority={r[0] for r in db.execute('SELECT molecule_id FROM pilot_priority').fetchall()};M.need(len(priority)==(55000 if pilot_ready else 0),'NO_PARTIAL55K_COUNT_DOWNGRADE')
    M.need(db.execute('SELECT count(*) FROM (SELECT molecule_id FROM pilot_priority EXCEPT SELECT molecule_id FROM roster)').fetchone()[0]==0,'ALL_PILOT_MIDS_IN_UNFILTERED_ORIGINAL_ROSTER')
    root=ctx.out/'pilot_preselection';root.mkdir()
    def save(name,query):
        ctx.check();return ctx.write_parquet_new(root/(name+'.parquet'),db.execute(query).fetch_arrow_table())
    refs={'full_population_membership':save('full_population_membership','SELECT * FROM pilot_scalar_membership ORDER BY molecule_id'),
        'complete_old_mother':save('complete_old_mother','SELECT * FROM pilot_complete_old_ranked ORDER BY effective_role,selection_rank')}
    pending=[]
    if pilot_ready:refs['pilot55k']=save('pilot55k','SELECT * FROM pilot_priority ORDER BY effective_role,selection_rank')
    else:pending.append({'component':'pilot55k','required':{'TRAIN':50000,'VAL':5000},'reason':'PENDING_OLD_COMPLETE_SPRIME_AVAILABILITY_NO_DOWNSIZE_OR_BACKGROUND_STOP'})
    # These are exact preselected MID lists, not final geometry anti-join lists.
    for n in SIZES:
        if len(ranked['TRAIN'])>=n:refs['train_'+str(n)]=save('train_'+str(n),"SELECT molecule_id,effective_role,selection_rank FROM pilot_complete_old_ranked WHERE effective_role='TRAIN' AND selection_rank<"+str(n)+' ORDER BY selection_rank')
        else:pending.append({'component':'train_'+str(n),'required':n,'reason':'PENDING_OLD_COMPLETE_SPRIME_AVAILABILITY_NO_COUNT_DOWNGRADE'})
    diagnostic=[r['molecule_id'] for r in eligible if r['effective_role']=='TRAIN' and r['S_conformers']>=2 and r['merged_uff_count']>=2]
    rank_hash=ranking_module().rank_hash
    diagnostic=sorted(diagnostic,key=lambda mid:(rank_hash(v['seed'],'diagnostic',mid),mid))[:20000]
    if len(diagnostic)==20000:refs['diagnostic20k_molecule_preselection']=ctx.write_parquet_new(root/'diagnostic20k_molecule_preselection.parquet',pa.table({'molecule_id':diagnostic}))
    else:pending.append({'component':'diagnostic20k_molecule_preselection','required':20000,'reason':'PENDING_TWO_SOURCE_COUNT_AVAILABILITY_NO_COUNT_DOWNGRADE'})
    priority_counts={}
    for i,d in enumerate(descriptors):
        count=db.execute('SELECT count(*) FROM roster r JOIN pilot_priority p USING(molecule_id) WHERE r.file_group=? AND r.shard_index=?',[d['file_group'],d['shard_index']]).fetchone()[0]
        if count:priority_counts[i]=count
    work=segments(descriptors,priority_counts);M.need(sum(priority_counts.values())==(55000 if pilot_ready else 0),'EXACT_AVAILABLE55K_OR_ZERO_PRIORITY_DESCRIPTOR_COVERAGE')
    summary={'schema':'EXISTING_COMPLETE_SPRIME_PILOT_PRESELECTION_V1','status':'SCALAR_MOTHER_AND_ORIGINAL_RANKS_FROZEN_PENDING_GRAPH_ORDER_MASKS_AND_ROOT',
        'actual_parent_job_id':str(ctx.proof['job_id']),'startup_proof_reference':M.pin(ctx.proof['request']['execution_argv'][ctx.proof['request']['execution_argv'].index('--root-preflight')+1]),
        'plan_reference':ctx.plan_ref,'Root_policy_reference':reference,'old_sprime_manifest_reference':v['config']['sprime_manifest'],
        'original_per_molecule_reference':base['per_molecule'],'roles_authority_reference':v['config']['roles_authority'],
        'old_complete_Sprime_acceptance_reference':v['old_complete_Sprime_acceptance_reference'],'source_role_counts':role_counts,
        'eligible_role_counts':{k:len(ids) for k,ids in ranked.items()},'pilot_ready_scalar_only':pilot_ready,
        'pilot_counts':{'TRAIN':50000,'VAL':5000} if pilot_ready else None,'requested_pilot_counts':{'TRAIN':50000,'VAL':5000},
        'requested_nested_train_counts':list(SIZES),'pending_availability':pending,
        'diagnostic_molecule_preselection_count':20000 if len(diagnostic)==20000 else None,'diagnostic_geometry_targets_materialized':False,
        'seed':v['seed'],'ranking_algorithm':'original pipeline_v1.io.rank_hash; effective_role/diagnostic domain; MID tie break',
        'membership_function':'original postprocess_day_v1.math_bridge.membership','original_full_mother_exclusion_gates':gates,
        'global_gate_interpretation':'ORIGINAL_DENOMINATOR_REPORT_PENDING_SPRIME_COMPLETION_NOT_FINAL_COMMON_FAILURE_OR_CACHE_STOP',
        'tables':refs,'old_Sprime_coordinate_source_references':v['old_refs'],'old_coordinates_opened_by_preselection':False,
        'strict_usable_counts_basis':'Root-bound original accepted full audit, not new status-only inference',
        'priority_changes_global_cache_eligibility':False,'remaining_full_roster_retained':True,'diagnostic_actual_geometry_exclusion':'PENDING_REAL_TWO_SOURCE_ORDERS_AND_CHILD_LINEAGE',
        'graph_stereo_RMSD_HOF_and_three_orders':'PENDING_ACTUAL_NATIVE_CACHE_READBACK',
        'final_Common':False,'D4_statistics_or_normalizer':False,'D3_export_complete':False,'D5_geometry_or_diagnostic_release':False,
        'N1_second_UFF_not_fabricated':True,'new_QM_calls':0,'new_UFF_calls':0}
    result=ctx.write_json_new(root/'preselection.json',summary)
    for ref in (v['config']['per_molecule'],*v['role_refs']):ctx.require(ref)
    return result,priority,work
