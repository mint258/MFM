"""One ordinary-only day parent; closed Common and failed-cache components reused."""
import argparse,concurrent.futures as cf,json,multiprocessing as mp,pathlib,time,traceback
from . import io as I,reuse
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C,cache,hof,worker,statistics


def claim(ctx,task,d7):
    key=C.F.sha_value(['ORDINARY_READONLY_CONTINUATION_V1',task['cache_key'],ctx.plan['closed_common_manifest_reference']])
    value=dict(schema='ORDINARY_READONLY_CONTINUATION_CLAIM_V1',key=key,cache_key=task['cache_key'],molecule_id=task['meta']['molecule_id'],
        job_id=ctx.job_id,uid=1278,node=ctx.plan['node'],plan_reference=ctx.plan_ref,output_directory=str(ctx.out),
        closed_common_component_reference=ctx.plan['closed_common_manifest_reference'],ordinary_D7=d7 is not None,
        original_records_SHA=C.F.sha_value(task['records']),canonical_HOF_SHA=C.F.sha_value(task['hof']),Native_once_written=False,new_UFF_or_QM=False)
    return key,ctx.write_json_new(ctx.out/'claims'/(key+'.json'),value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','root-preflight','output'):parser.add_argument('--'+name,type=pathlib.Path,required=True)
    a=parser.parse_args();p=C.G.load(a.plan);proof=I.admit(a,p);out=pathlib.Path(a.output)
    C.need(I.BASE in out.parents and out.is_absolute() and '..' not in out.parts and not out.exists()
        and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_NEW_ORDINARY_OUTPUT_NO_OLD_WRITES')
    out.mkdir(mode=0o700,parents=True)
    for name in ('molecules','starts','progress','orders','geometry_witnesses','checkpoints','duckdb_tmp','quota_events','claims','catalog_parts'):(out/name).mkdir()
    ctx=db=collector=None;active={};unknown=[];catalog=[];catalog_refs=[];cursor=None;fatal=None;stats=None
    try:
        # No extra test layer. Public original functions are the live callables.
        C.need(worker.pm7_compute is __import__('workflows.data_v1_final.conformers.postprocess_day_v1.math_bridge',fromlist=['pm7_compute']).pm7_compute
            and worker.geometry_orders is __import__('workflows.data_v1_final.conformers.postprocess_day_v1.math_bridge',fromlist=['geometry_orders']).geometry_orders,
            'DIRECT_ORIGINAL_PM7_AND_ORDER_OBJECTS_NO_NUMERICAL_COPY')
        ctx=I.Context(p,proof,C.G.meta_pin(a.plan),out);ctx.authorized(p['source_references']);ctx.authorized(p['data_references'])
        C.need(ctx.observe(force=True) is None,'FRESH_CURRENT_V2_FUTURE100GB_BEFORE_DATA');ctx.start()
        delivered=ctx.read(p['D3_closed_export_reference'],32<<20)
        C.need(delivered['schema']=='BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1' and delivered['version']=='v1-pilot-provisional'
            and delivered['status']=='DELIVERED_PENDING_MODEL_LOADER_AND_HEAD_OVERFIT'
            and str(delivered['actual_parent_job_id'])=='4525880' and delivered['actual_root_C0_wrapper'] is True,
            'REAL_FORMAL_D3_4525880_DELIVERY_REQUIRED_NOT_BUDGET_RETIREMENT')
        native=delivered['actual_parent_accounting']
        C.need(all(str(native[k])==v for k,v in dict(JobIDRaw='4525880',State='COMPLETED',ExitCode='0:0',UID='1278',AllocCPUS='16',NodeList='compute-0-8').items()),
            'FORMAL_D3_ACTUAL_C0_UID_CPU_NODE')
        C.need(delivered['actual_export_receipt_reference']==p['D3_actual_export_receipt_reference'],
            'FORMAL_INDEX_EXACT_ORIGINAL_EXPORT_RECEIPT_REFERENCE')
        export=ctx.read(p['D3_actual_export_receipt_reference'],32<<20)
        C.need(export['schema']=='BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1' and str(export['job_id'])=='4525880'
            and export['uid']==1278 and export['node']=='compute-0-8' and export['actual_cpus']==16
            and export['status']=='ACTUAL55K_FIXED_RANDOM_FAMILY_AND_1K_SOURCE_QA_COMPLETE_PENDING_MODEL_LOADER'
            and export['errors']==[] and export['export_and_single1000_complete'] is True
            and export['all_Family_SQLite_Sidecar_and_spawn_reader_handles_closed'] is True
            and export['source_roundtrip_records']==1000 and export['pilot_counts']=={'TRAIN':50000,'VAL':5000}
            and export['new_QM_UFF_calls']==0,'ORIGINAL_COMPLETE_D3_RECEIPT_ALL_WRITERS_CLOSED')
        C.need(all(delivered[k]==export[k] for k in ('job_id','uid','node','actual_cpus','plan_reference','startup_proof_reference',
            'manifest_reference','verification_reference','pilot_counts','source_roundtrip_records','export_and_single1000_complete',
            'all_Family_SQLite_Sidecar_and_spawn_reader_handles_closed','errors','new_QM_UFF_calls','distribution'))
            and export['distribution']['status']=='COPIED_WITH_RSYNC_CHECKSUM' and export['distribution']['transfer']['returncode']==0,
            'SAME_CLOSED_EXPORT_AND_SUCCESSFUL_DISTRIBUTION_NO_MODEL_ACK_GATE')
        oldplan=C.meta(p['pm7_preparation_plan_reference']);base=C.meta(p['cache_plan_reference'])
        C.need(oldplan['base_cache_plan_reference']==p['cache_plan_reference'] and base['source_population_molecules']==1220466
            and base['source_population_records']==11231854,'EXACT_FROZEN_FULL_PM7_ROSTER_NOT_A_NEW_POPULATION')
        original=ctx.read(base['base_plan_reference']);I.PRE.canonical_source(ctx,base,original)
        import duckdb,pyarrow as pa
        db=duckdb.connect(str(ctx.local_out/'work.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='32GB'")
        db.execute('SET temp_directory='+C.q(ctx.local_out/'duckdb_tmp'));ctx.db=db
        common,expected_common=reuse.common_component(ctx,db)
        roles_ref,role_parts=ctx.roles(ctx.value)
        db.execute('CREATE VIEW all_roles AS SELECT * FROM read_parquet(['+','.join(C.q(r['path']) for r in role_parts)+'])')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM all_roles').fetchone()==(1220466,1220466),'ALL_ORIGINAL_FROZEN_ROLES')
        C.need(not p.get('pm7_precache_registered_parents') and not p.get('previous_postprocess_parents') and not p['cache_registered_parents'],
            'NO_IMPLICIT_PARENT_REASSIGNMENT_USE_DECLARED_CLOSED_COMPONENTS')
        descriptors=cache.setup(ctx,db,base);adoption=reuse.pm7_components(ctx,db,oldplan,base)
        h_ref=adoption['hof_projection_reference'];cache.project_old_uff(ctx,db)
        collector=statistics.Collector(ctx,db);dispatch=0
        def collect(pool,all_active=False):
            while active:
                ctx.observe([v.pid for v in pool._processes.values() if v.pid]);done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    key,mid,is_common,claim_ref=active.pop(future)
                    try:
                        r=future.result();ctx.register_closed_output(r['packet_reference']);ctx.written+=r['packet_reference']['bytes'];collector.add(r['packet_reference'],mid,is_common)
                        catalog.append(dict(r,claim_reference=claim_ref))
                        if r['status']=='READONLY_MOLECULE_UNKNOWN':
                            unknown.append(dict(molecule_id=mid,key=key,packet_reference=r['packet_reference']));ctx.stop=ctx.stop or 'READONLY_SOURCE_OR_SCIENTIFIC_UNKNOWN_HOLD'
                    except BaseException as exc:
                        unknown.append(dict(molecule_id=mid,key=key,error=repr(exc),traceback=traceback.format_exc()));ctx.stop=ctx.stop or 'READONLY_SOURCE_OR_SCIENTIFIC_UNKNOWN_HOLD'
                    finally:
                        for name in ('starts/'+key+'.json','progress/'+key+'.jsonl'):
                            path=out/name
                            if path.exists():ctx.written+=path.stat().st_size
                        ctx.release(key)
                if done and not all_active:return
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker.initialize,initargs=({'proof':proof},)) as pool:
            for ordinal,descriptor in enumerate(descriptors):
                if ctx.observe() is not None:break
                metas,by=cache.batch(ctx,db,descriptor);catalog=[];processed=0
                for meta in metas:
                    while len(active)>=16:collect(pool)
                    if ctx.observe() is not None:break
                    mid=meta['molecule_id'];role=db.execute('SELECT source_role,effective_role FROM all_roles WHERE molecule_id=?',[mid]).fetchone()
                    C.need(role is not None,'EXACT_SOURCE_AND_EFFECTIVE_ROLE_NOT_REASSIGNED');meta=dict(meta,split_role=role[0],effective_role=role[1])
                    task=cache.task(ctx,meta,by[mid],base,h_ref);old=reuse.reused_cache(ctx,db,task,base)
                    d7=cache.d7_task(ctx,db,meta,by[mid],task['hof'])
                    key=C.F.sha_value(['ORDINARY_READONLY_CONTINUATION_V1',task['cache_key'],p['closed_common_manifest_reference']])
                    reserve=min(256<<20,max(8<<20,2*task['software_bound']['packet_reserve_bytes']+(16<<20)))
                    try:ctx.reserve(key,reserve)
                    except ValueError as exc:
                        if str(exc)!='FULL_MOLECULE_DRAIN_OUTPUT_RESERVATION':raise
                        ctx.stop=ctx.stop or 'OUTPUT_DRAIN_RESERVATION_STOP_NEW_WORK';break
                    key,claim_ref=claim(ctx,task,d7)
                    future=pool.submit(worker.one,task,old,d7,str(out/'molecules'/(key+'.json.gz')),claim_ref)
                    active[future]=(key,mid,d7 is not None,claim_ref);dispatch+=1;processed+=1
                collect(pool,True)
                if catalog:catalog_refs.append(ctx.write_parquet_new(out/'catalog_parts'/('%03d.parquet'%ordinal),pa.Table.from_pylist(catalog)))
                cursor=dict(descriptor_ordinal=ordinal,descriptor=descriptor,attempted_current_parent=processed,descriptor_complete=processed==len(metas))
                ctx.write_json_new(out/'checkpoints'/('%03d.json'%ordinal),dict(cursor=cursor,actual_parent_job_id=ctx.job_id,
                    internal_checkpoint_is_not_a_child_C0=True,old_failed_and_resource_unknown_history_preserved=True))
                if ctx.stop is not None:break
        stats=collector.report(expected_common);stats_ref=ctx.write_json_new(out/'conformer_statistics.json',stats);ctx.finish()
        observations=ctx.write_json_new(out/'resource_observations.json',dict(samples=ctx.samples,report=ctx.report(),quota_guard_events=ctx.events))
        ctx.write_json_new(out/'receipt.json',dict(schema='ORDINARY_POSTPROCESS_RESUME_RECEIPT_V1',status='CLOSED_ORDINARY_COMPONENTS_PENDING_ACTUAL_PARENT_AND_ROOT_REVIEW',
            job_id=ctx.job_id,runtime=dict(uid=1278,node=p['node'],cpus=16),plan_reference=ctx.plan_ref,startup_proof_reference=C.G.meta_pin(a.root_preflight),
            closed_common_component_reference=p['closed_common_manifest_reference'],common_parent_accounting_reference=p['closed_common_accounting_reference'],
            original_Common_parent_state='FAILED',original_PM7_parent_state='FAILED',closed_PM7_component=adoption,
            original9_resource_UNKNOWN_preserved=True,statistics_reference=stats_ref,order_tables=stats['order_tables'],
            geometry_witness_tables=stats['geometry_readback_witness_tables'],catalog_part_references=catalog_refs,
            cursor=cursor,unknown=unknown,resource=ctx.report(),resource_observations_reference=observations,
            PM7_full_source_cache_complete=stats['PM7_full_source_cache_complete'],ordinary_Common_D7_geometry_complete=stats['ordinary_Common_D7_geometry_complete'],
            scope_three_orders_complete=stats['three_order_Common_release_eligible'],old_Common_manifest_unchanged=True,
            Common_or_D6_or_D7_final_release=False,N1_extra_geometry_included=False,Native_once_written=False,new_UFF_calls=0,new_QM_calls=0,
            new_parent_C0='PENDING_REAL_SACCT',all_actual_costs_preserved=True))
        return 1 if unknown else 0
    except BaseException as exc:
        fatal=dict(schema='ORDINARY_POSTPROCESS_RESUME_FAILURE_V1',error=repr(exc),traceback=traceback.format_exc(),job_id=str(proof['job_id']),
            original_components_unchanged=True,resource=ctx.report() if ctx else None,new_UFF_calls=0,new_QM_calls=0)
        I.OLD.save(out/'failure.json',fatal);raise
    finally:
        if ctx:ctx.finish()
        if db:db.close()
        if ctx:ctx.cleanup_local_workspace()


if __name__=='__main__':
    with I.PRE.single_parent():raise SystemExit(main())