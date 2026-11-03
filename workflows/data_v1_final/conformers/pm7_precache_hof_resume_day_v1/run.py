"""One24h CPU parent over all247 frozen descriptors; original PM7 worker only."""
import argparse,collections,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,time,traceback,unittest
from . import metadata as M,io as I,hof_resume as HOF_RESUME
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare as PRIORITY,run as ORIGINAL_RUN

def preflight(out):
    from . import test_boundaries
    old=ORIGINAL_RUN.preflight(out);test_boundaries.WORKSPACE=out
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_boundaries.Boundaries)
    M.need(suite.countTestCases()==3,'EXACT_NEW3_IN_SAME_PARENT_AFTER_ORIGINAL20')
    transcript=io.StringIO();result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    ref=I.POPIO.json_new(out/'hof_resume_preflight3.json',{'schema':'PM7_HOF_RESUME_DAY_PREFLIGHT_V1','tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses),'transcript':transcript.getvalue(),'original20_reference':old,
        'source_proof':HOF_RESUME.source_proof(),'original_compute_direct_object_and_worker_IO_context_proof':I.WORKER.proof(),
        'DATA_opened':False,'new_QM_calls':0,'new_UFF_calls':0},out)
    M.need(result.testsRun==3 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'ORIGINAL20_PLUS_NEW3_PASS_BEFORE_DATA')
    return ref

def validate_population(ctx,base):
    prepared=ctx.read(base['population_prepared_reference']);authority=ctx.read(prepared['source_authority_reference'])
    M.need(prepared['schema']=='PM7_CACHE32_PREPARED_V1' and prepared['job_id']=='4521593'
        and prepared['status']=='ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED','ACTUAL_OLD32_PREPARED_DATA_NOT_REWRITTEN_FULL_GRANT')
    for key,jid in (('population_prepare_accounting_reference','4521593'),('geometry32_accounting_reference','4521602'),('hof32_accounting_reference','4521643')):
        I.POP.parent(base[key],jid,ctx.proof,True)
    original=ctx.read(base['base_plan_reference'])
    M.need(authority['formal_source']==original['formal_source']==base['formal_source'] and authority['per_molecule']==base['per_molecule']
        and authority['whole_molecule_roster']==prepared['whole_molecule_roster']==base['whole_molecule_roster']
        and authority['future_shards']==prepared['future_shards']==base['future_shards_reference']
        and authority['population_molecules']==1220466 and authority['population_records']==11231854
        and authority['Sprime_SUCCESS_used_as_eligibility']is False,'ORIGINAL_FULL_ROSTER_NO_SPRIME_OR_COMMON_FILTER')
    I.canonical_source(ctx,base,original)
    ctx.controls=I.POP.controls(base,ctx.proof);return prepared

def conservative_cursor(metas,rows):
    present={r['molecule_id'] for r in rows};M.need(len(present)==len(rows) and present<={m['molecule_id'] for m in metas},'EXACT_WHOLE_MOLECULE_CHECKPOINT_UNION')
    return next((i for i,m in enumerate(metas) if m['molecule_id'] not in present),len(metas))
def artifact_absence(root,key):
    evidence=[]
    for name,suffix in (('starts','.json'),('molecules','.json.gz'),('finished','.json'),('progress','.jsonl')):
        path=pathlib.Path(root)/name/(key+suffix)
        if path.exists() or path.is_symlink():evidence.append(str(path))
    return evidence

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('plan','root-preflight','output'):parser.add_argument('--'+n,type=pathlib.Path,required=True)
    a=parser.parse_args();p,base,registered,proof=I.admit(a);out=I.own_setup(a.output);plan_ref=M.pin(a.plan)
    ctx=None;db=None;gate=None;fatal=None;unknown=[];catalogs=[];counts=collections.Counter();geometry=collections.Counter();hof_reasons=collections.Counter()
    active={};descriptor_cursor={'descriptor_ordinal':0,'first_unstarted_offset':0};all_done=False;started=time.monotonic();current_rows=[]
    try:
        with I.single_parent():
            gate=preflight(out);ctx=I.Context(p,proof,plan_ref,out)
            ctx.authorized([*p['source_references'],*p['data_references']]);ctx.check();ctx.start()
            prepared=validate_population(ctx,base)
            for key in ('formal_source','per_molecule','whole_molecule_roster'):ctx.require(base[key])
            import duckdb,pyarrow as pa,pyarrow.parquet as pq
            reuse_review,old_qa,old_origin,clone_ref=HOF_RESUME.adopt(ctx,base,registered)
            db=duckdb.connect(str(out/'work.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
            db.execute('SET temp_directory='+I.PC.q(out/'duckdb_tmp'));ctx.db=db;ctx.cache_plan=base
            shard_body=ctx.read(base['future_shards_reference'])
            M.need(shard_body['roster_reference']==base['whole_molecule_roster'],'SAME_ORIGINAL_ROSTER_DESCRIPTORS')
            descriptors=shard_body['descriptors']
            M.need(len(descriptors)==247,'FROZEN247_DESCRIPTOR_COUNT')
            origins=I.registered_origins(p,proof);claim_census,prior_unknown=I.census_claims(ctx,origins);unknown.extend(prior_unknown)
            ctx.formal_reference=base['formal_source'];ctx.cache_registered={};ctx.day_registered={}
            for entry in p['cache_registered_parents']:
                origin=M.registration(entry,'legacy');M.need(origin['entry']==origins[origin['job_id']]['entry']
                    and origin['actual']['state']=='COMPLETED' and origin['actual']['exit_code']=='0:0'
                    and origin['receipt']['unknown_molecules']==origin['receipt']['unstarted_molecules']==0,
                    'ORIGINAL_LEGACY_CACHE_RUNTIME_CONTEXT_REBOUND_TO_REAL_C0_REGISTRATIONS')
                ctx.cache_registered[origin['job_id']]={'request':origin['request'],'submission':origin['submission'],'accounting':origin['actual']}
            M.need(db.execute('SELECT count(*) FROM prior_day').fetchone()[0]==0,
                'FAILED_PM7_PRODUCER_HAS_NO_UNREGISTERED_POSTPROCESS_DAY_TABLE_ORIGIN')
            old_notes,remaining_sources,needed_sources=HOF_RESUME.validate_db(ctx,db,base,reuse_review,old_qa)
            priority_ref,priority_mids,diagnostic_mids,work_segments=HOF_RESUME.restore_priority(ctx,db,base,reuse_review,descriptors)
            adoption_ref=ctx.write_json_new(out/'closed_HOF_prefix_adoption.json',{
                'schema':'PM7_ACTUAL_FAILED_HOF_PREFIX_CURRENT_PARENT_ADOPTION_V1','Root_review_reference':p['hof_closed_prefix_reuse_review_reference'],
                'old_actual_parent_job_id':old_origin['job_id'],'old_state':old_origin['actual']['state'],
                'old_reader_complete':False,'old_closed_state_reference':reuse_review['closed_state_reference'],
                'working_database_initial_copy_observation':{'locator':clone_ref['path'],'bytes_observed':clone_ref['bytes'],
                    'sha256_observed':clone_ref['sha256'],'mutable_work_database_not_immutable_input_reference':True},
                'old_sources_adopted':180,'old_HOF_rows_not_reprojected':10277940,
                'remaining_needed_sources':len(remaining_sources),'current_actual_parent_job_id':str(proof['job_id']),
                'old_parent_promoted_C0':False,'new_QM_UFF_calls':0})
            h_ref,hof_complete=HOF_RESUME.project_remaining(ctx,db,base,old_notes,remaining_sources)
            if not hof_complete:ctx.stop=ctx.stop or 'HOF_PROJECTION_RESOURCE_PARTIAL_NO_NEW_MOLECULES'
            session={'proof_reference':M.pin(a.root_preflight),'main_source':M.pin(M.HERE/'run.py'),
                'execution_argv':proof['request']['execution_argv'],'parent_pid':os.getpid(),'parent_start_ticks':I.POPIO.R.proc_ticks(os.getpid()),
                'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),'output_root':str(out),'source_references':I.sources(),
                'source_fingerprint':I.PC.digest(I.sources())}
            current_origin={'job_id':str(proof['job_id']),'kind':'day','root':str(out),'request':proof['request'],'proof':proof}
            origins[str(proof['job_id'])]=current_origin
            def classify(row,task):
                row=dict(row);row.update(hof_valid_count=sum(v['valid'] for v in task['hof'].values()),
                    hof_missing_reason_counts=dict(collections.Counter(v['reason'] for v in task['hof'].values() if not v['valid'])),
                    hof_NULL_review_records=sum(bool(v['convergence_null_review']) for v in task['hof'].values()))
                counts[row['state']]+=1;geometry[row.get('geometry_status','UNKNOWN')]+=1;hof_reasons.update(row['hof_missing_reason_counts']);current_rows.append(row)
            def collect(pool,all_active=False):
                while active:
                    ctx.observe([proc.pid for proc in pool._processes.values() if proc.pid]);done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        task,claim_ref=active.pop(future);key=task['cache_key'];mid=task['meta']['molecule_id']
                        try:
                            result=future.result();claim=I.BI.read(claim_ref);row,packet=I.packet_from_claim(ctx,task,claim,claim_ref,origins)
                            M.need(row['geometry_packet_reference']==result['packet_reference'],'RETURN_EQUALS_DURABLE_ORIGINAL_PACKET')
                            M.need(result['status']=='DURABLE_READONLY_MOLECULE_RESULT','NO_UNKNOWN_WRAPPER_PROMOTED_TO_COMPLETE_CACHE')
                            row.update(state='DURABLE_PACKET',origin_kind='DAY_PACKET');classify(row,task)
                        except Exception as exc:
                            unknown.append({'molecule_id':mid,'error':repr(exc)});ctx.stop=ctx.stop or 'CONSUMED_UNKNOWN_HOLD_NO_RETRY'
                            classify({'molecule_id':mid,'records':len(task['records']),'cache_key':key,'claim_reference':claim_ref,
                                'state':'UNKNOWN_CONSUMED_NO_COMPLETE_PACKET','error':repr(exc),'origin_job_id':str(proof['job_id'])},task)
                        finally:I.charge_worker(ctx,key);ctx.release(key)
                    if done and not all_active:return
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=I.WORKER.initialize,initargs=({'proof':proof},)) as pool:
                for segment_ordinal,segment in enumerate(work_segments):
                    if ctx.observe()is not None:break
                    ordinal=segment['descriptor_ordinal'];descriptor=descriptors[ordinal]
                    original_metas,original_by=I.CACHE.batch(ctx,db,descriptor)
                    metas,by=HOF_RESUME.select_scheduled(original_metas,original_by,priority_mids,diagnostic_mids,segment['phase'])
                    M.need(len(metas)==segment['molecules'],'EXACT_PRIORITY_PARTITION_NOT_NEW_TASK_POPULATION')
                    current_rows=[];descriptor_cursor={'descriptor_ordinal':ordinal,'selection_phase':segment['phase'],'segment_ordinal':segment_ordinal,'first_unstarted_offset':0}
                    for meta in metas:
                        while len(active)>=16:collect(pool)
                        if ctx.observe()is not None:break
                        task=I.CACHE.task(ctx,meta,by[meta['molecule_id']],base,h_ref);key=task['cache_key']
                        old_ledger=I.PC.LEDGER/(key+'.json');day_ledger=I.DAY_LEDGER/(key+'.json')
                        M.need(not(old_ledger.exists() and day_ledger.exists()),'CONFLICTING_OLD_NEW_TECHNICAL_CLAIM_NO_SILENT_OWNER_CHOICE')
                        ledger=old_ledger if old_ledger.exists() else day_ledger
                        if ledger.exists():
                            lr=None
                            try:
                                lr=I.ref(ledger);claim=I.BI.read(lr);row,packet=I.packet_from_claim(ctx,task,claim,lr,origins)
                                row.update(state='DURABLE_PACKET_RECOVERED',origin_kind='LEGACY_PACKET' if origins[str(claim['job_id'])]['kind']=='legacy' else 'DAY_PACKET');classify(row,task)
                            except Exception as exc:
                                unknown.append({'molecule_id':meta['molecule_id'],'error':repr(exc)});ctx.stop=ctx.stop or 'EXISTING_CONSUMED_CACHE_UNKNOWN_HOLD'
                                classify({'molecule_id':meta['molecule_id'],'records':meta['records'],'cache_key':key,'state':'UNKNOWN_EXISTING_CACHE_EVIDENCE',
                                    'claim_reference':lr,'error':repr(exc)},task)
                            continue
                        orphan=[path for origin in origins.values() for path in artifact_absence(origin['root'],key)]
                        if orphan:
                            unknown.append({'molecule_id':meta['molecule_id'],'orphan_evidence':orphan});ctx.stop=ctx.stop or 'ORPHAN_CACHE_EVIDENCE_HOLD'
                            classify({'molecule_id':meta['molecule_id'],'records':meta['records'],'cache_key':key,'state':'UNKNOWN_ORPHAN_EVIDENCE','evidence_locators':orphan},task);continue
                        # No original key is claimed before exact old attempt census.
                        if meta['molecule_id'] in ctx.controls[0]:
                            g,h=ctx.controls;result=I.POP.imported32(task,g[meta['molecule_id']],h[meta['molecule_id']],out)
                            classify(dict(result,molecule_id=meta['molecule_id'],records=meta['records'],cache_key=key,state='IMPORTED_EXISTING32',origin_kind='LEGACY32'),task);continue
                        ctx.reserve(key,2*I.PC.reserve(meta));task_ref=I.POPIO.json_new(out/'tasks'/(key+'.json'),task,out)
                        lr=I.new_claim(ctx,task,task_ref)
                        if lr is None:
                            ctx.release(key);ctx.stop=ctx.stop or 'CONCURRENT_CLAIM_UNKNOWN_NO_REDISPATCH';unknown.append({'molecule_id':meta['molecule_id'],'state':'UNKNOWN_CONCURRENT_CLAIM'})
                            classify({'molecule_id':meta['molecule_id'],'records':meta['records'],'cache_key':key,'state':'UNKNOWN_CONCURRENT_CLAIM'},task);break
                        try:active[pool.submit(I.WORKER.one,task,None,None,out/'molecules'/(key+'.json.gz'),lr)]=(task,lr)
                        except Exception as exc:
                            ctx.release(key);ctx.stop=ctx.stop or 'SUBMISSION_CONSUMED_UNKNOWN';unknown.append({'molecule_id':meta['molecule_id'],'claim_reference':lr,'error':repr(exc)})
                            classify({'molecule_id':meta['molecule_id'],'records':meta['records'],'cache_key':key,'claim_reference':lr,
                                'state':'UNKNOWN_CLAIMED_NOT_CLOSED','error':repr(exc)},task);break
                    collect(pool,True)
                    next_offset=conservative_cursor(metas,current_rows);descriptor_cursor={'descriptor_ordinal':ordinal,'selection_phase':segment['phase'],'segment_ordinal':segment_ordinal,'first_unstarted_offset':next_offset}
                    table=pa.table({'molecule_id':[r['molecule_id'] for r in current_rows],'row_json':[M.canonical(r).decode() for r in current_rows]})
                    catalog=ctx.write_parquet_new(out/'catalog_parts'/('%03d.parquet'%segment_ordinal),table);catalogs.append(catalog)
                    ctx.write_json_new(out/'checkpoints'/('%03d.json'%segment_ordinal),{'descriptor_ordinal':ordinal,'descriptor':descriptor,'selection_phase':segment['phase'],'segment_ordinal':segment_ordinal,'closed_rows':len(current_rows),
                        'catalog_reference':catalog,'cursor':descriptor_cursor,'internal_checkpoint_is_not_Slurm_C0':True,'unknown_retained':len(unknown)})
                    if ctx.stop is not None:break
                    M.need(next_offset==len(metas),'NO_SILENT_UNCONSUMED_WHOLE_MOLECULE_GAP')
                    if segment['phase']=='PILOT_PRIORITY' and (segment_ordinal+1==len(work_segments) or work_segments[segment_ordinal+1]['phase']!='PILOT_PRIORITY'):
                        M.need(sum(counts.values())==55000 and not unknown,'ALL55K_PRIOR_CACHE_OR_REAL_PACKET_CLOSURE_NOT_NEW_C0')
                        priority_prefix_ref=ctx.write_json_new(out/'pilot_cache_prefix.json',{'schema':'CURRENT_PARENT_PM7_PILOT_CACHE_PREFIX_V1',
                            'status':'DURABLE55K_PREFIX_WITHIN_RUNNING_PARENT_NOT_C0_OR_COMMON','job_id':str(proof['job_id']),
                            'plan_reference':plan_ref,'startup_proof_reference':M.pin(a.root_preflight),'preselection_reference':priority_ref,
                            'catalog_part_references':list(catalogs),'molecules':55000,'state_counts':dict(counts),'geometry_status_counts':dict(geometry),
                            'hof_missing_reason_counts':dict(hof_reasons),'scientific_geometry_pending_is_not_success':True,
                            'future_parent_accounting_and_independent_Root_acceptance_required':True,'D3_D4_D5_or_Common_release':False})
                    if ((segment['phase']=='DIAGNOSTIC_CANDIDATE_PRIORITY' and
                          (segment_ordinal+1==len(work_segments) or work_segments[segment_ordinal+1]['phase']!='DIAGNOSTIC_CANDIDATE_PRIORITY'))
                        or (segment['phase']=='PILOT_PRIORITY' and not(diagnostic_mids-priority_mids) and
                          (segment_ordinal+1==len(work_segments) or work_segments[segment_ordinal+1]['phase']!='PILOT_PRIORITY'))):
                        M.need(sum(counts.values())==len(priority_mids|diagnostic_mids) and not unknown,
                            'EXACT55K_UNION_FROZEN20K_CANDIDATE_CACHE_PREFIX_NO_UNKNOWN')
                        diagnostic_prefix_ref=ctx.write_json_new(out/'diagnostic_candidate_cache_prefix.json',{
                            'schema':'CURRENT_PARENT_PM7_DIAGNOSTIC_CANDIDATE_CACHE_PREFIX_V1',
                            'status':'DURABLE_FROZEN20K_CANDIDATE_CACHE_NOT_D5_ELIGIBILITY_OR_ACCEPTANCE',
                            'job_id':str(proof['job_id']),'plan_reference':plan_ref,'startup_proof_reference':M.pin(a.root_preflight),
                            'preselection_reference':priority_ref,'pilot55k_prefix_reference':priority_prefix_ref,
                            'catalog_part_references':list(catalogs),'frozen_diagnostic_candidates':20000,
                            'candidates_additional_to55k':len(diagnostic_mids-priority_mids),
                            'union_molecules':len(priority_mids|diagnostic_mids),'state_counts':dict(counts),
                            'two_source_geometries_at_least_two_and_orders_postvalidation_required':True,
                            'future_parent_accounting_and_independent_Root_acceptance_required':True,
                            'D3_D4_D5_or_Common_release':False})
                all_done=ctx.stop is None and descriptor_cursor.get('segment_ordinal')==len(work_segments)-1 and descriptor_cursor['first_unstarted_offset']==len(metas)
                if all_done:M.need(sum(counts.values())==1220466,'ALL_ORIGINAL_MOLECULES_REMAIN_AFTER_PILOT_PRIORITY')
            for key in ('formal_source','per_molecule','whole_molecule_roster'):ctx.require(base[key],drain=True)
    except BaseException as exc:fatal={'error':repr(exc),'traceback':traceback.format_exc()}
    finally:
        if ctx is not None:ctx.finish()
        if db is not None:db.execute('CHECKPOINT');db.close()
        state=I.ref(out/'work.duckdb') if (out/'work.duckdb').exists() else None
        report={'schema':'PM7_PRECACHE_DAY_RECEIPT_V1','scope_key':M.KEY,'status':'UNKNOWN_OR_FAILED_NO_CACHE_ACCEPTANCE' if fatal or unknown else
            ('FULL_ROSTER_TECHNICAL_CACHE_ROOT_REVIEW_REQUIRED' if all_done else 'ACTUAL_DAY_DURABLE_PARTIAL_PREFIX_NOT_FULL'),
            'job_id':str(proof['job_id']),'plan_reference':plan_ref,'startup_proof_reference':M.pin(a.root_preflight),'source_plan_reference':p['base_cache_plan_reference'],
            'preflight_reference':gate,'catalog_part_references':catalogs,'closed_state_reference':state,'cursor':descriptor_cursor,'prior_claim_census_reference':locals().get('claim_census'),
            'state_counts':dict(counts),'geometry_status_counts':dict(geometry),'hof_missing_reason_counts':dict(hof_reasons),
            'pilot_preselection_reference':locals().get('priority_ref'),'pilot_priority_only_no_Common_or_D5_release':True,
            'pilot_cache_prefix_reference':locals().get('priority_prefix_ref'),
            'diagnostic_candidate_cache_prefix_reference':locals().get('diagnostic_prefix_ref'),
            'failed_HOF_prefix_adoption_reference':locals().get('adoption_ref'),
            'unknown':unknown,'fatal':fatal,'HOF_projection_complete':locals().get('hof_complete',False),'hof_projection_reference':locals().get('h_ref'),
            'all_population_coverage':all_done,'common':False,'full_cache_release':False,'physical_ID_or_final_D7_release':False,
            'population_molecules':1220466,'population_records':11231854,'output_cap_bytes':M.CAP,'resource':None if ctx is None else ctx.report(),
            'elapsed_monotonic_seconds':time.monotonic()-started,'new_UFF_calls':0,'new_QM_calls':0,'source_parent_cost':'PENDING_REAL_TERMINAL_ACCOUNTING'}
        # Original reserve is usable for this final small metadata, never for new work.
        I.POPIO.json_new(out/'receipt.json',report,out,final=True)
    return 1 if fatal or unknown else 0
if __name__=='__main__':raise SystemExit(main())
