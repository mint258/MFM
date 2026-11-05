"""One finite existing whole-molecule shard/range; no UFF/QM or new queue."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,csv,io,json,multiprocessing as mp,pathlib,sys,time
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import contract as C,io as I,worker
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as PC
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.prepare32 import canonical_hof
from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1.run import provenance


def parent(account_ref,jid,proof,require_C0=False):
    account=I.read(account_ref);I.authorized(proof,[account['raw_sacct_reference']])
    parents=I.F.accounting(account_ref,[jid]);row=parents[str(jid)]
    C.need(account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and int(row['alloc_cpus'])==16,'ACTUAL_MAIN_CPU16_PARENT')
    if require_C0:
        C.need(row['state']=='COMPLETED' and row['exit_code']=='0:0','ACTUAL_REQUIRED_PARENT_C0')
        raw=I.F.pinned(account['raw_sacct_reference'],8<<20).read_text()
        native=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r.get('JobIDRaw')==str(jid)]
        C.need(len(native)==1 and native[0].get('UID')=='1278' and native[0].get('NodeList')=='compute-0-13','ACTUAL_RAW_MAIN_UID_AND_NODE13')
    return parents


def inputs(plan,proof,out):
    prepared=I.read(plan['population_prepared_reference']);authority=I.read(prepared['source_authority_reference'])
    C.need(prepared['schema']=='PM7_CACHE32_PREPARED_V1' and prepared['job_id']=='4521593'
        and prepared['status']=='ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED','ORIGINAL_REAL_POPULATION_PREPARATION')
    parent(plan['population_prepare_accounting_reference'],prepared['job_id'],proof,True)
    base=I.read(plan['base_plan_reference']);C.need(base['formal_source']==plan['formal_source'] and base['per_molecule']==plan['per_molecule']
        and authority['formal_source']==plan['formal_source'] and authority['per_molecule']==plan['per_molecule']
        and authority['whole_molecule_roster']==prepared['whole_molecule_roster']==plan['whole_molecule_roster']
        and authority['future_shards']==prepared['future_shards']==plan['future_shards_reference']
        and authority['population_molecules']==C.POPULATION_MOLECULES and authority['population_records']==C.POPULATION_RECORDS
        and authority['Sprime_SUCCESS_used_as_eligibility'] is False,'EXACT_FULL_POPULATION_NO_STATUS_FILTER')
    hof=I.read(plan['hof_authority_review']);C.need(hof['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' and hof['reviewer']=='root'
        and hof['endpoint']=='202.38.247.57:22' and hof['uid']==1278 and hof['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER'
        and hof['registry_id']==60 and hof['unit']=='kcal/mol' and hof['native_energy_fallback_allowed'] is False,'REAL_CANONICAL_HOF_AUTHORITY')
    I.P.formal_source(base,proof,out);I.source_check(plan['per_molecule']);I.source_check(plan['whole_molecule_roster'])
    shards=I.read(plan['future_shards_reference']);C.need(shards['roster_reference']==plan['whole_molecule_roster']
        and sum(r['molecules'] for r in shards['descriptors'])==C.POPULATION_MOLECULES
        and sum(r['records'] for r in shards['descriptors'])==C.POPULATION_RECORDS,'EXACT_EXISTING247_SHARD_UNION')
    s=plan['selection'];matches=[r for r in shards['descriptors'] if (r['file_group'],r['shard_index'])==(s['file_group'],s['shard_index'])]
    C.need(len(matches)==1 and s['offset']+s['limit']<=matches[0]['molecules'],'EXISTING_SHARD_EXACT_RANGE')
    import duckdb,pyarrow as pa
    pa.set_cpu_count(16);pa.set_io_thread_count(2)
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
    (out/'duckdb_tmp').mkdir();db.execute('SET temp_directory='+C.q(out/'duckdb_tmp'))
    try:
        db.execute('CREATE VIEW roster AS SELECT * FROM read_parquet('+C.q(plan['whole_molecule_roster']['path'])+')')
        C.need(db.execute('SELECT count(*),sum(records),count(DISTINCT molecule_id) FROM roster').fetchone()==
            (C.POPULATION_MOLECULES,C.POPULATION_RECORDS,C.POPULATION_MOLECULES),'ACTUAL_ROSTER_FULL_COUNT')
        metas=db.execute('SELECT * FROM roster WHERE file_group=? AND shard_index=? ORDER BY molecule_hash,molecule_id LIMIT ? OFFSET ?',
            [s['file_group'],s['shard_index'],s['limit'],s['offset']]).fetch_arrow_table().to_pylist()
        C.need(len(metas)==s['limit'] and sum(r['records'] for r in metas)<=C.MAX_RECORDS,'BOUNDED_WHOLE_MOLECULE_BATCH')
        C.need(all(r['records']==r['original_pm7_count'] and r['records']>0 for r in metas),'NO_PARTIAL_OR_NEW_N')
        db.register('wanted',pa.table({'molecule_id':[r['molecule_id'] for r in metas]}))
        columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')
        records=db.execute('SELECT '+','.join('r.'+n for n in columns)+' FROM read_parquet('+C.q(plan['formal_source']['path'])+
            ') r JOIN wanted USING(molecule_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
    finally:db.close()
    C.need(len(records)==sum(m['records'] for m in metas)==len({r['record_id'] for r in records}),'EXACT_RECORD_UNION_NO_ENERGY_RAW')
    grouped={m['molecule_id']:[] for m in metas}
    for row in records:grouped[row['molecule_id']].append(row)
    C.need(all(len(grouped[m['molecule_id']])==m['records'] and all(r['file_group']==s['file_group'] for r in grouped[m['molecule_id']]) for m in metas),'WHOLE_MOLECULE_SOURCE_POINTERS')
    I.source_check(plan['whole_molecule_roster']);I.source_check(plan['formal_source']);I.source_check(plan['per_molecule'])
    return base,prepared,metas,records,grouped


def controls(plan,proof):
    geometry=I.read(plan['geometry32_receipt_reference']);hof=I.read(plan['hof32_receipt_reference'])
    parent(plan['geometry32_accounting_reference'],geometry['job_id'],proof,True)
    parent(plan['hof32_accounting_reference'],hof['job_id'],proof,True)
    C.need(geometry['job_id']=='4521602' and geometry['geometry_complete']==geometry['completed_packets']==32
        and geometry['golden_geometry_equal_count']==16 and not geometry['errors'],'REAL_CLOSED_GEOMETRY32')
    C.need(hof['job_id']=='4521643' and hof['complete_molecules']==hof['completed_packets']==32 and hof['records']==hof['valid_hof_records']==203
        and not hof['errors'],'REAL_CLOSED_CANONICAL_HOF32')
    old_hof_plan=I.read(hof['plan_reference']);C.need(old_hof_plan['hof_authority_review']==plan['hof_authority_review'],'IMPORT32_SAME_CANONICAL_HOF_AUTHORITY')
    g={r['molecule_id']:r for r in geometry['packets']};h={r['molecule_id']:r for r in hof['packets']}
    C.need(set(g)==set(h) and len(g)==32,'EXACT32_IMPORT_UNION')
    return g,h


def validate_packet(task,claim,claim_ref):
    out=pathlib.Path(claim['output_root']);key=task['cache_key']
    C.need(C.BASE in out.parents and '..' not in out.parts and not any(p.is_symlink() for p in (out,*out.parents)),'ONLY_FIXED_NAMESPACE_PREVIOUS_OUTPUT')
    finished=I.read(I.ref(out/'finished'/(key+'.json')))
    C.need(finished['cache_key']==key and finished['molecule_id']==task['meta']['molecule_id'] and finished['claim_reference']==claim_ref,'DURABLE_FINISHED_IDENTITY')
    C.need(finished['packet_reference']['path']==str(out/'molecules'/(key+'.json.gz')) and
        finished['worker_start_reference']['path']==str(out/'starts'/(key+'.json')),'DETERMINISTIC_PACKET_AND_START_LEAVES')
    packet=I.P.read_packet(finished['packet_reference']);start=I.read(finished['worker_start_reference']);old_task=I.read(claim['task_reference'])
    C.need(packet['cache_key']==key and packet['source_records']==task['records'] and packet['hof_by_record']==task['hof']
        and packet['task_reference']==finished['task_reference']==start['task_reference']==claim['task_reference']
        and old_task['cache_key']==key and old_task['records']==task['records'] and old_task['hof']==task['hof']
        and packet['claim_reference']==start['claim_reference']==claim_ref and packet['runtime']==start['runtime']==finished['runtime']
        and packet['runtime']['job_id']==claim['job_id'] and packet['runtime']['uid']==1278
        and packet['runtime']['node']=='compute-0-13' and packet['molecule_id']==task['meta']['molecule_id'],'ACTUAL_NATIVE_TASK_SOURCE_FLOAT64_AND_PRODUCER')
    return finished,packet


def imported32(task,g,h,out):
    mid=task['meta']['molecule_id'];p=I.P.read_packet(g['packet_reference']);derived=I.read(h['packet_reference'])
    C.need(p['molecule_id']==derived['molecule_id']==mid and p['source_records']==task['records']
        and derived['geometry_packet_reference']==g['packet_reference'] and derived['records']==len(task['records'])
        and derived['hof_by_record']==task['hof'] and derived['hof_range_complete'] is True
        and derived['hof_float64_bit_signatures']=={rid:I.HC.bits(v['value_kcal_mol']) for rid,v in task['hof'].items()}
        and derived['geometry_hashes']=={r['conformer_id']:r['geometry_sha256'] for r in p['pm7']},'REAL32_GEOMETRY_AND_HOF_IMPORT_NO_OPTIMIZER')
    return {'state':'IMPORTED_EXISTING32','geometry_status':p['status'],'hof_valid_count':derived['hof_valid_count'],
        'geometry_validated_records':len(p['pm7']),'geometry_packet_reference':g['packet_reference'],
        'hof_packet_reference':h['packet_reference'],'orders_and_HOF_reference':h['packet_reference'],
        'cache_layout':'ORIGINAL_GEOMETRY_WITH_CANONICAL_HOF_ATTACHMENT','original_geometry_producer_runtime':p['runtime'],
        'original_HOF_producer_runtime':derived['runtime'],'new_LMDB_reads':0,'new_RMSD_calls':0}


def geometry_diagnostics(packet):
    errors=packet.get('source_errors',[]);reasons=collections.Counter()
    for value in errors:
        text=value.get('error',value.get('status','UNKNOWN_SOURCE_VALIDATION_ERROR')) if isinstance(value,dict) else str(value)
        # Bounded exception-class histograms; complete frozen error messages
        # remain in each original packet, never promoted to a new root cause.
        reasons[C.error_reason(text)]+=1
    if packet.get('error'):reasons['COMPUTE_EXCEPTION:'+C.error_reason(packet['error'])]+=1
    return {'geometry_record_error_reason_counts':dict(reasons),'known_source_failed_records':len(errors),
        'geometry_validated_records':len(packet.get('pm7',[])),
        'original_record_read_attempts_observed':packet.get('records_attempted'),
        'completed_original_RMSD_calls_observed':packet.get('actual_original_RMSD_calls')}


def claim_value(task,task_ref,plan_ref,session,out,action):
    return {'schema':'PM7_POPULATION_CACHE_CLAIM_V1','cache_key':task['cache_key'],'molecule_id':task['meta']['molecule_id'],
        'job_id':session['job_id'],'uid':1278,'node':'compute-0-13','output_root':str(out),'plan_reference':plan_ref,
        'task_reference':task_ref,'proof_reference':session['proof_reference'],'source_fingerprint':session['source_fingerprint'],
        'action':action,'worker_start_not_inferred':True,'automatic_retry':False}


def previous_outputs(plan,previous,proof):
    roots={}
    for reference in plan['previous_submission_references']:
        submission=I.read(reference);request=I.read(submission['request_reference']);I.authorized(proof,[submission['request_reference']])
        jid=str(submission['job_id']);argv=request['execution_argv']
        C.need(submission['schema']=='CPU_AUTO_MEMORY_SUBMISSION_V1' and submission['uid']==1278 and submission['sbatch_returncode']==0
            and submission['request']==request and jid in previous and previous[jid]['alloc_cpus']==16
            and request['scope_key']==C.SCOPE and request['node']=='compute-0-13' and request['cpus']==16
            and argv[:3]==['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B',str(C.HERE/'run.py')],
            'REAL_TERMINAL_PREVIOUS_PRODUCER_SUBMISSION_AND_FULL_PRIMARY')
        declared={r['path']:r for r in request['source_references']}
        C.need(all(declared.get(r['path'])==r for r in I.sources()),'PRIOR_REQUEST_EXACT_FROZEN_SOURCE_SET')
        C.need(len(argv)==11 and argv[3::2]==['--plan','--root-preflight','--quota-reuse-review','--output'],'PREVIOUS_EXACT_ORDERED_OPTIONS')
        out=pathlib.Path(argv[-1]);C.need(C.BASE in out.parents and '..' not in out.parts,'PREVIOUS_OWN_OUTPUT_PREFIX')
        roots[str(out)]=jid
    return roots


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in C.OPTIONS:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    args=parser.parse_args();plan,plan_ref,proof,session=I.admit(__file__,args);out=I.new_output(args.output)
    budget=None;rows=[];errors=[];selected=[];fixtures=None;fatal=None;started=time.monotonic();external_bytes=0
    claims={};tasks={};by_meta={};hof={};observations_ref=None
    try:
        budget=I.P.budget(proof,session,out);budget.start_monitor()
        C.need(budget.observe() is None,'FRESH_QUOTA_BEFORE_BODY');fixtures=I.fixtures(out)
        base,prepared,metas,records,grouped=inputs(plan,proof,out);selected=[m['molecule_id'] for m in metas];by_meta={m['molecule_id']:m for m in metas}
        g,h=controls(plan,proof);previous={}
        for account in plan['previous_parent_accounting_references']:
            value=I.read(account);I.authorized(proof,[value['raw_sacct_reference']]);parents=I.F.accounting(account)
            C.need(value['endpoint']=='202.38.247.57:22' and value['uid']==1278,'PREVIOUS_MAIN_ACCOUNTING')
            for jid,p in parents.items():C.need(jid not in previous or previous[jid]==p,'CONFLICTING_ACTUAL_PARENT_COST');previous[jid]=p
        prior_outputs=previous_outputs(plan,previous,proof)
        compute_plan=dict(base,hof_mode='CANONICAL_VERIFIED',hof_authority_review=plan['hof_authority_review'])
        new_records=[r for r in records if r['molecule_id'] not in g]
        try:hof,observations=canonical_hof(compute_plan,new_records,proof,out,budget) if new_records else ({},[])
        except Exception as exc:
            hof={r['record_id']:PC.missing_hof('CANONICAL_HOF_BATCH_READER_REJECTED') for r in new_records}
            observations=[{'status':'HOF_PENDING_READER_EXCEPTION_GEOMETRY_NOT_EXCLUDED','error':repr(exc)[:16000]}]
        for mid in selected:
            if mid not in h:continue
            prior=I.read(h[mid]['packet_reference']);ids={r['record_id'] for r in grouped[mid]}
            C.need(prior['molecule_id']==mid and set(prior['hof_by_record'])==ids and prior['hof_range_complete'] is True,'EXACT_EXISTING32_HOF_NATIVE_IDS')
            for rid,value in prior['hof_by_record'].items():PC.validate_hof(value);hof[rid]=value
            observations.append({'status':'EXISTING32_HOF_CACHE_IMPORTED_NO_PROJECTION','molecule_id':mid,'packet_reference':h[mid]['packet_reference']})
        C.need(set(hof)=={r['record_id'] for r in records},'ALL_SELECTED_HOF_STATES_NO_DROP')
        try:owner_provenance=provenance(compute_plan,new_records,proof) if new_records else {}
        except Exception as exc:
            observations.append({'status':'OWNER_PROVENANCE_REJECTED','error':repr(exc)[:16000]})
            owner_provenance={r['record_id']:{'provenance_state':'PENDING_CANONICAL_SOURCE_PROVENANCE'} for r in new_records}
        for mid in selected:
            if mid in h:
                for row in grouped[mid]:owner_provenance[row['record_id']]={'provenance_state':'EXISTING32_CANONICAL_ATTACHMENT_AUTHORITY','attachment_reference':h[mid]['packet_reference']}
        source_sets={};compact={}
        for rid,value in owner_provenance.items():
            candidates=value.get('source_file_candidates',[]);source_set=C.digest(candidates);source_sets[source_set]=candidates
            compact[rid]={'canonical_owner':value.get('canonical_owner'),'source_candidate_set':source_set,
                'provenance_state':value['provenance_state'],'attachment_reference':value.get('attachment_reference')}
        observations_ref=I.json_new(out/'hof_source_observations.json',{'hof_reader_observations':observations,
            'canonical_hof_by_record':hof,'owner_and_file_provenance':compact,'source_candidate_sets':source_sets,
            'original_native_pointers_in_exact_tasks':True,'hof_authority_review':plan['hof_authority_review']},out)
        task_refs={};active={};queue=[]
        for meta in metas:
            mid=meta['molecule_id'];source_rows=grouped[mid];key=C.task_key(plan['formal_source'],plan['hof_authority_review'],source_rows)
            task={'schema':'PM7_POPULATION_CACHE_TASK_V1','cache_key':key,'meta':meta,'records':source_rows,
                'hof':{r['record_id']:hof[r['record_id']] for r in source_rows},'hof_mode':'CANONICAL_VERIFIED',
                'software_bound':PC.software_bound(meta['records'],meta['maximum_total_atoms']),
                'source_population_authority':prepared['source_authority_reference'],'hof_source_provenance_reference':observations_ref,'golden_packet_reference':None}
            tasks[mid]=task;common={'molecule_id':mid,'records':meta['records'],'cache_key':key,
                'hof_valid_count':sum(v['valid'] for v in task['hof'].values()),
                'hof_missing_reason_counts':dict(collections.Counter(v['reason'] for v in task['hof'].values() if not v['valid'])),
                'hof_convergence_null_review_records':sum(bool(v['convergence_null_review']) for v in task['hof'].values())}
            ledger=C.LEDGER/(key+'.json')
            if ledger.exists():
                claim_ref=I.ref(ledger);claim=I.read(claim_ref);state=C.classify_claim(claim,previous.get(str(claim['job_id'])))
                try:
                    C.need(claim['cache_key']==key and claim['source_fingerprint']==session['source_fingerprint'],'EXACT_FROZEN_CACHE_PRODUCER_SOURCE')
                    C.need(state!='UNKNOWN_PARENT_ACCOUNTING_REQUIRED','ACTUAL_TERMINAL_PARENT_COST_REQUIRED_FOR_CONSUMED_CLAIM')
                    C.need(claim['uid']==1278 and claim['node']=='compute-0-13' and prior_outputs.get(claim['output_root'])==claim['job_id'],
                        'CLAIM_MUST_BIND_REAL_REGISTERED_TERMINAL_PARENT_OUTPUT')
                    if claim['action']=='IMPORT32':result=imported32(task,g[mid],h[mid],out)
                    else:
                        finished,packet=validate_packet(task,claim,claim_ref);result={'state':'DURABLE_PACKET_RECOVERED',
                            'geometry_status':packet['status'],**geometry_diagnostics(packet),**{k:finished[k] for k in ('packet_reference','worker_start_reference','runtime')},
                            'geometry_packet_reference':finished['packet_reference'],'orders_and_HOF_reference':finished['packet_reference'],
                            'cache_layout':'SINGLE_GEOMETRY_AND_HOF_PACKET'}
                    rows.append({**common,**result,'claim_reference':claim_ref,'previous_parent_actual_accounting':previous[claim['job_id']]})
                except Exception as exc:rows.append({**common,'state':state if state=='UNKNOWN_PARENT_ACCOUNTING_REQUIRED' else 'UNKNOWN_CONSUMED_NO_COMPLETE_PACKET',
                    'claim_reference':claim_ref,'error':repr(exc)[:16000],'evidence_preserved':True})
                continue
            orphan=[]
            for root in prior_outputs:
                for directory,suffix in (('starts','.json'),('molecules','.json.gz'),('finished','.json'),('progress','.jsonl')):
                    p=pathlib.Path(root)/directory/(key+suffix)
                    if p.exists() or p.is_symlink():orphan.append(str(p))
            if orphan:
                rows.append({**common,'state':C.classify_claim(None,None,evidence_exists=True),'evidence_locators':orphan,
                    'evidence_preserved':True,'automatic_retry':False});continue
            if budget.observe() is not None:continue
            if I.usage(out)+2*C.reserve(meta)+C.RESERVE>C.CAP:budget.stop=budget.stop or 'OUTPUT_RESERVATION_STOP';continue
            task_ref=I.json_new(out/'tasks'/(key+'.json'),task,out);task_refs[mid]=task_ref
            if mid in g:
                value=claim_value(task,task_ref,plan_ref,session,out,'IMPORT32');claim_ref=I.claim(key,value,out)
                if claim_ref is None:rows.append({**common,'state':'UNKNOWN_CONCURRENT_CLAIM_NO_REDISPATCH'});continue
                external_bytes+=claim_ref['bytes'];claims[mid]=claim_ref
                try:rows.append({**common,**imported32(task,g[mid],h[mid],out),'claim_reference':claim_ref})
                except Exception as exc:rows.append({**common,'state':'UNKNOWN_IMPORT32_VALIDATION_FAILED','claim_reference':claim_ref,'error':repr(exc)[:16000]})
            else:queue.append(mid)
        # Only this new immutable cache ledger is opened; no production/UFF/QM once domain.
        index=0
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker.initialize,initargs=(session,)) as pool:
            while active or index<len(queue):
                budget.observe(list(pool._processes.values()))
                while budget.stop is None and index<len(queue) and len(active)<16:
                    mid=queue[index]
                    if I.usage(out)+2*sum(C.reserve(by_meta[m]) for m in [*active.values(),mid])+C.RESERVE>C.CAP:
                        budget.stop='OUTPUT_RESERVATION_STOP';break
                    task=tasks[mid];value=claim_value(task,task_refs[mid],plan_ref,session,out,'COMPUTE')
                    claim_ref=I.claim(task['cache_key'],value,out);index+=1
                    if claim_ref is None:
                        rows.append({'molecule_id':mid,'records':by_meta[mid]['records'],'cache_key':task['cache_key'],
                            'state':'UNKNOWN_CONCURRENT_CLAIM_NO_REDISPATCH'});continue
                    external_bytes+=claim_ref['bytes'];claims[mid]=claim_ref
                    # Atomic durable claim immediately before submit. Prepared
                    # tasks left by a resource STOP are still proven unstarted.
                    try:active[pool.submit(worker.one,tasks[mid],task_refs[mid],claims[mid])]=mid
                    except Exception as exc:errors.append({'molecule_id':mid,'phase':'POOL_SUBMIT','error':repr(exc)[:16000]})
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    mid=active.pop(future);task=tasks[mid];common={'molecule_id':mid,'records':by_meta[mid]['records'],'cache_key':task['cache_key'],
                        'hof_valid_count':sum(v['valid'] for v in task['hof'].values()),
                        'hof_missing_reason_counts':dict(collections.Counter(v['reason'] for v in task['hof'].values() if not v['valid'])),
                        'hof_convergence_null_review_records':sum(bool(v['convergence_null_review']) for v in task['hof'].values())}
                    try:
                        record=future.result();claim=I.read(claims[mid]);finished,packet=validate_packet(task,claim,claims[mid])
                        C.need(all(record[k]==finished[k] for k in ('cache_key','molecule_id','packet_reference','worker_start_reference','runtime','status')),
                            'ACTUAL_RETURN_MUST_EQUAL_DURABLE_FINISHED')
                        rows.append({**common,'state':'DURABLE_PACKET','geometry_status':packet['status'],
                            **geometry_diagnostics(packet),**record,'claim_reference':claims[mid],
                            'geometry_packet_reference':record['packet_reference'],'orders_and_HOF_reference':record['packet_reference'],
                            'cache_layout':'SINGLE_GEOMETRY_AND_HOF_PACKET'})
                    except Exception as exc:rows.append({**common,'state':'UNKNOWN_CONSUMED_NO_COMPLETE_PACKET','claim_reference':claims[mid],
                        'error':repr(exc)[:16000],'durable_evidence_preserved':True})
        present={r['molecule_id'] for r in rows}
        for mid in claims:
            if mid not in present:rows.append({'molecule_id':mid,'records':by_meta[mid]['records'],'cache_key':tasks[mid]['cache_key'],
                'state':'UNKNOWN_CLAIMED_NOT_CLOSED','claim_reference':claims[mid],'hof_valid_count':sum(v['valid'] for v in tasks[mid]['hof'].values()),
                'hof_missing_reason_counts':dict(collections.Counter(v['reason'] for v in tasks[mid]['hof'].values() if not v['valid']))})
        I.source_check(plan['formal_source']);I.source_check(plan['whole_molecule_roster']);I.source_check(plan['per_molecule'])
    except BaseException as exc:fatal=repr(exc)[:16000];errors.append({'phase':'PARENT','error':fatal,'all_durable_claims_and_outputs_preserved':True})
    finally:
        if budget is not None:budget.close_monitor()
        present={r['molecule_id'] for r in rows}
        for mid,claim_ref in claims.items():
            if mid not in present:rows.append({'molecule_id':mid,'records':by_meta[mid]['records'],'cache_key':tasks[mid]['cache_key'],
                'state':'UNKNOWN_CLAIMED_NOT_CLOSED','claim_reference':claim_ref,'durable_evidence_preserved':True})
        unstarted=C.conservation(selected,rows);unknown=[r['molecule_id'] for r in rows if r['state'].startswith('UNKNOWN')]
        complete=[r for r in rows if r.get('geometry_status','').startswith('PM7_GEOMETRY_CACHE_COMPLETE')]
        closed=len(rows)==len(selected)>0 and not unknown and fatal is None and budget is not None and budget.stop is None
        for row in rows:
            if row.get('error'):
                if len(row['error'])>4096:errors.append({'phase':'FULL_CATALOG_ERROR','molecule_id':row['molecule_id'],'error':row['error']})
                row['error']=row['error'][:4096]
        catalog_body=b''.join(C.canonical(r)+b'\n' for r in sorted(rows,key=lambda r:r['molecule_id']))
        C.need(len(catalog_body)<=32<<20,'FINITE_BATCH_CATALOG32MIB')
        catalog=I.write(out/'molecule_catalog.jsonl.gz',__import__('gzip').compress(catalog_body,mtime=0),out,final=True)
        error_ref=I.write(out/'parent_errors.jsonl.gz',__import__('gzip').compress(b''.join(C.canonical(r)+b'\n' for r in errors),mtime=0),out,final=True)
        resource=budget.report() if budget is not None else {'stop_new_dispatch':'BUDGET_CONSTRUCTOR_FAILED_BEFORE_BODY',
            'actual_memory_observations':[],'actual_quota_observations':[],'observation_failure':{'error':fatal},
            'cost_policy':'REPORT_AND_CONTINUE','full_forecast_core_hours':None,'wall_dispatch_cutoff_seconds':None,
            'signals_sent_to_science':False,'natural_drain':True,'whole_wave_output_reserved_bytes':None,'publisher_reserved_bytes':None}
        resource_ref=I.write(out/'resource_observations.json.gz',__import__('gzip').compress(C.canonical(resource),mtime=0),out,final=True)
        budget_summary={k:resource[k] for k in ('stop_new_dispatch','cost_policy','full_forecast_core_hours','wall_dispatch_cutoff_seconds',
            'signals_sent_to_science','natural_drain','whole_wave_output_reserved_bytes','publisher_reserved_bytes')}
        budget_summary.update(full_observations_reference=resource_ref,observation_failure=resource['observation_failure'],
            memory_observation_count=len(resource['actual_memory_observations']),quota_observation_count=len(resource['actual_quota_observations']))
        next_index=next((i for i,mid in enumerate(selected) if mid in set(unstarted)),len(selected))
        report={'schema':'PM7_POPULATION_CACHE_BATCH_RECEIPT_V1','status':'SELECTION_DURABLY_CLOSED_ROOT_REVIEW_REQUIRED' if closed else 'PARTIAL_OR_UNKNOWN_NO_FULL_CLAIM',
            'job_id':session['job_id'],'plan_reference':plan_ref,'startup_proof_reference':session['proof_reference'],'fixtures_reference':fixtures,
            'selection':plan['selection'],'selected_molecules':len(selected),'selected_records':sum(r['records'] for r in rows)+sum(by_meta[m]['records'] for m in unstarted) if selected else None,
            'catalog_reference':catalog,'durable_classified_molecules':len(rows),'geometry_complete_molecules':len(complete),
            'geometry_complete_records':sum(r['records'] for r in complete),'geometry_validated_records':sum(r.get('geometry_validated_records',0) for r in rows),
            'geometry_pending_or_unresolved_molecules':len(selected)-len(complete),
            'geometry_record_error_reason_counts':dict(sum((collections.Counter(r.get('geometry_record_error_reason_counts',{})) for r in rows),collections.Counter())),
            'known_source_failed_records':sum(r.get('known_source_failed_records',0) for r in rows),
            'hof_valid_records_independent_of_geometry':sum(r.get('hof_valid_count',0) for r in rows),
            'hof_missing_reason_counts':dict(sum((collections.Counter(r.get('hof_missing_reason_counts',{})) for r in rows),collections.Counter())),
            'hof_NULL_convergence_review_records':sum(r.get('hof_convergence_null_review_records',0) for r in rows),
            'selected_HOF_reader_records':len(hof),'selected_HOF_reader_valid_records':sum(v['valid'] for v in hof.values()),
            'selected_HOF_reader_missing_reason_counts':dict(collections.Counter(v['reason'] for v in hof.values() if not v['valid'])),
            'selected_HOF_NULL_convergence_review_records':sum(bool(v['convergence_null_review']) for v in hof.values()),
            'hof_source_observations_reference':observations_ref,
            'state_counts':dict(collections.Counter(r['state'] for r in rows)),
            'geometry_status_counts':dict(collections.Counter(r.get('geometry_status','UNKNOWN_OR_NOT_COMPUTED') for r in rows)),
            'unknown_molecules':len(unknown),'unknown_molecules_definition':'CONSUMED_WITHOUT_VALIDATED_COMPLETE_PACKET; NOT_THE_GEOMETRY_QC_AXIS',
            'consumed_without_validated_packet_molecules':len(unknown),'unstarted_molecules':len(unstarted),
            'next_first_unstarted_ordinal_in_shard':plan['selection']['offset']+next_index,
            'unknown_keys_are_not_retryable':True,'partial_cursor_is_not_full_population_claim':True,'budget':budget_summary,
            'error_count':len(errors),'errors':[{k:(v[:512] if k=='error' else v) for k,v in r.items()} for r in errors[:8]],
            'full_parent_errors_reference':error_ref,'errors_summary_only':bool(errors),
            'elapsed_seconds':time.monotonic()-started,'whole_output_cap_bytes':C.CAP,'charged_bytes':I.usage(out),'new_external_claim_bytes':external_bytes,
            'legacy_budget_owned_disk_soft_stop_bytes':8<<30,'effective_disk_soft_stop_bytes':min(8<<30,C.CAP),
            '64GIB_is_ceiling_not_available_write_guarantee':True,
            'actual_parent_accounting_append_required':True,'actual_parent_cost':None,'source_population_molecules':C.POPULATION_MOLECULES,
            'population_counts_basis':'EXISTING4521593_FROZEN_AUTHORITY_NOT_NEW_FULL_POPULATION_SCAN',
            'source_population_records':C.POPULATION_RECORDS,'common':False,'full_cache_release':False,'physical_int64_or_D7_order_release':False,
            'new_QM_calls':0,'new_UFF_calls':0,'Sprime_cross_RMSD_and_final_D7':'SEPARATE_NOT_COMPUTED'}
        I.json_new(out/'receipt.json',report,out,final=True)
    return 0 if closed else 3


if __name__=='__main__':raise SystemExit(main())
