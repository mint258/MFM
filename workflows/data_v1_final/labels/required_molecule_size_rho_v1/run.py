"""Original weighted Spearman on every view required by frozen definitions.

All 146 fields still pass the original typed reader and mask parity checks.
Closed scalar correlations are reused; only missing views enter new histograms.
"""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,time
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import contract as C,io as I,domain as D,configuration as G,frame_mapping as M
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import reader as R,bindings as B,io as BI,originals
CTX=None

def initialize(context):
    global CTX
    CTX=context
    C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==context['job_id']
      and os.uname().nodename==context['node'],'ACTUAL_D3_CPU_PARENT_SIZE_WORKER')
    BI.ALLOWED={r['path']:r for r in context['registered_references']}
    BI.ORIGINS=context['reader_origins'];BI.ROOT=pathlib.Path(context['root']);BI.CAP=context['cap']
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'

def check():
    I.F.worker_check(CTX['control'])

def histogram(item):
    import pyarrow as pa,pyarrow.parquet as pq
    key,group,directory=item;root=pathlib.Path(directory);root.mkdir()
    schema=pa.schema([('field_id',pa.uint16()),('value',pa.float64()),('heavy_atoms',pa.uint16()),('n',pa.uint64())])
    selected=set(CTX['source_field_ids']);series=CTX['series_ids'];buffer=[];references=[];counts=collections.Counter();records=0
    def flush():
        if not buffer:return
        check();path=root/('part_%06d.parquet'%len(references));aggregated=collections.Counter(buffer)
        table=pa.Table.from_pylist([dict(field_id=fid,value=value,heavy_atoms=heavy,n=n)
          for (fid,value,heavy),n in sorted(aggregated.items())],schema=schema)
        pq.write_table(table,path,compression='zstd')
        with path.open('rb')as stream:os.fsync(stream.fileno())
        references.append(BI.pin(path));buffer.clear();check()
    for owner,numbers,entries,row,source in R.records(CTX['cfg'],group,CTX['fields']):
        check();records+=1
        if owner['new_role']!='TRAIN' or not owner['fit_eligible']:continue
        # Physical norms use all original components and the original masks.
        values,_=B.views([e for e in entries if e['field_id']in selected],numbers,CTX['physical_groups'],CTX['models'])
        heavy=sum(z>1 for z in numbers);C.need(0<=heavy<65536,'ORIGINAL_RHO_HEAVY_COUNT_TYPE')
        for name,actual in values.items():
            if name not in series:continue
            C.need(len(actual)<=1,'REQUIRED_SINGLE_MOLECULE_SCALAR_OR_PHYSICAL_INVARIANT')
            counts[name]+=len(actual)
            for value in actual:buffer.append((series[name],float(value),heavy))
        if len(buffer)>=65536:flush()
    flush()
    return dict(key=key,source_job_id=group['source_job_id'],pid=os.getpid(),records=records,
      histogram_references=references,series_counts=dict(counts))

def correlations(item):
    import duckdb
    rows,files,directory=item;root=pathlib.Path(directory);root.mkdir()
    db=duckdb.connect();db.execute('SET threads=1');db.execute("SET memory_limit='1GB'")
    db.execute('SET temp_directory='+BI.sqlstr(root));db.execute("SET max_temp_directory_size='1GiB'")
    reducer=originals.objects()[1];result={}
    try:
        for row in rows:
            check();result[row['key']]=reducer.rho_external(db,files,row['field_id'])
    finally:db.close()
    return result

def build(plan,components,cfg,fields,output,budget):
    """Return an actual DATA reference; called only by the admitted D3 parent."""
    C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
      and os.uname().nodename==plan['node'],'REQUIRED_RHO_ONLY_IN_ACTUAL_D3_CPU_PARENT')
    root=pathlib.Path(output);C.need(not root.exists() and BI.ROOT in root.parents,'FRESH_D3_REQUIRED_RHO_OUTPUT');root.mkdir()
    bounded=C.meta(plan['bounded_export_review_reference']);review,definitions,_,_=G.review(plan,bounded)
    resolved=G.resolve_definitions(definitions,fields,cfg['element_basis'],C.meta(review['task_protocol_reference']),C.Q.pin(M.POLICY))
    required={f['field_id']:resolved['size_rules_by_field'][f['field_key']] for f in fields
      if resolved['size_rules_by_field'][f['field_key']]['method']=='ORIGINAL_VIEW_WEIGHTED_SPEARMAN'}
    scalar={f['field_id']:required[f['field_id']]for f in fields if f['level']=='molecule'}
    C.need(len(scalar)==69,'ACTUAL_FROZEN_69_MOLECULE_SCALAR_FIELDS_UNCHANGED')
    keys={v['series_key']for v in required.values()};scalar_keys={v['series_key']for v in scalar.values()}
    original_catalog,physical=B.inventory(dict(fields=fields,plan=dict(element_basis=cfg['element_basis'])))
    catalog=[row for row in original_catalog if row['key']in keys]
    C.need(len(catalog)==len(keys)==76 and len(scalar_keys)==69,
      'ALL_FROZEN_REQUIRED_76_ORIGINAL_CATALOG_VIEWS_NO_REENUMERATION')
    roots=bounded['transitive_closed_output_roots'];numeric=D.read(components['numeric_repetitions'][0],roots,256<<20)
    groups=C.B.logical(D.read(cfg['logical_group_plan_reference'],roots,8<<20)['groups'])
    resumed_reference=None;resumed={};old_histograms=[];old_worker_pids=[]
    locator=plan.get('required_size_rho_resume_locator')
    if locator is not None:
        C.need(type(locator)is str and pathlib.Path(locator).is_absolute()and '..'not in pathlib.Path(locator).parts
          and bounded.get('CPU_first_closed_partial_rho_hash_authorized')is True
          and bounded.get('required_size_rho_resume_locator')==locator,
          'EXPLICIT_ROOT_CPU_FIRST_CLOSED_PARTIAL_RHO_LOCATION_AND_HASH_AUTHORITY')
        # The actual CPU parent creates the first positive ref. Historical
        # histogram parts stay provenance and are never reread or reduced.
        budget.check();resumed_reference=D.register(I.pin(locator),roots);I.require(resumed_reference)
        previous=I.load_data(resumed_reference,64<<20)
        canonical={r['key']:r for r in catalog};prior_catalog=previous['catalog']
        C.need(previous['schema']=='PROVISIONAL_TRAIN_ORIGINAL_SERIES_SIZE_RHO_V1'
          and previous['required_scalar_fields']==69 and previous['source_fields_validated_by_original_reader']==146
          and previous['required_molecule_scalar_series_only']is True
          and previous['original_function']=='streaming_v1.reduce.rho_external'
          and previous['threshold_abs_rho']==.95
          and previous['fit_population_reference']==components['population_reference']
          and previous['statistics_reference']==components['numeric_repetitions'][0]
          and previous['actual_source_groups']==len(groups)==171
          and len(prior_catalog)==69 and {r['key']for r in prior_catalog}==scalar_keys
          and set(previous['series'])==scalar_keys
          and all(row==canonical[row['key']]for row in prior_catalog),
          'ACTUAL_CLOSED69_SAME_POPULATION_STATISTICS_AND_CANONICAL_ORIGINAL_SERIES')
        resumed=dict(previous['series']);old_histograms=previous['histogram_references']
        old_worker_pids=previous.get('actual_worker_pids',[])
    missing=keys-set(resumed);new_catalog=[row for row in catalog if row['key']in missing]
    selected_physical=[group for group in physical
      if any(row['physical_group']==group['key']for row in new_catalog)]
    selected_ids={row['source_field_id']for row in new_catalog}
    selected_ids.update(fid for group in selected_physical for fid in group['field_ids'])
    context=dict(job_id=os.environ['SLURM_JOB_ID'],node=plan['node'],root=str(BI.ROOT),cap=BI.CAP,
      registered_references=list(BI.ALLOWED.values()),reader_origins=dict(BI.ORIGINS),control=budget.control,
      cfg=cfg,fields=fields,source_field_ids=sorted(selected_ids),physical_groups=selected_physical,
      series_ids={r['key']:r['field_id']for r in new_catalog},models=numeric['models'])
    counts=collections.Counter();reports=[];histograms=[];started=time.monotonic();pool=None
    try:
        pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(context,))
        pending={};cursor=iter(groups);done=False
        while pending or not done:
            while not done and len(pending)<32:
                budget.check()
                try:group=next(cursor)
                except StopIteration:done=True;break
                key=hashlib.sha256(json.dumps(group,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                I.append(root/'dispatch.jsonl',dict(group_key=key,source_job_id=group['source_job_id']))
                pending[pool.submit(histogram,(key,group,str(root/key)))]=key
            if pending:
                ready,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in ready:
                    key=pending.pop(future);result=future.result();C.need(result['key']==key,'EXACT_REQUIRED_RHO_GROUP_RESULT')
                    for ref in result['histogram_references']:I.add(ref);I.require(ref);histograms.append(ref)
                    counts.update(result['series_counts']);reports.append(result);I.append(root/'closed_groups.jsonl',result)
        C.need(len(reports)==len(groups) and len({r['key']for r in reports})==len(groups),'ALL_REQUIRED_RHO_GROUPS_ONCE')
        files=[r['path']for r in histograms];C.need(files,'ACTUAL_NONEMPTY_REQUIRED_RHO_HISTOGRAMS')
        pending={pool.submit(correlations,(new_catalog[i::16],files,str(root/('reduce_%02d'%i)))):i for i in range(16)
          if new_catalog[i::16]}
        rhos={}
        while pending:
            budget.check();ready,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in ready:
                pending.pop(future);part=future.result();C.need(not set(part)&set(rhos),'UNIQUE_REQUIRED_RHO_REDUCTIONS');rhos.update(part)
        C.need(set(rhos)==missing and all(rhos[k]['pair_n']==counts[k]for k in missing),
          'EXACT_ORIGINAL_NEW_REQUIRED_VIEW_RANK_MASS')
        C.need(not set(rhos)&set(resumed),'NO_RECOMPUTED_OR_REPLACED_CLOSED_SCALAR_SERIES')
        rhos.update(resumed);C.need(set(rhos)==keys,'ALL76_FROZEN_REQUIRED_SIZE_SERIES_PRESENT')
        procs=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False);pool=None
        C.need(all(p.exitcode==0 for p in procs),'ACTUAL_REQUIRED_RHO_WORKERS_CLOSED')
        return I.save(root/'original_series_weighted_size_rho.json',dict(schema='PROVISIONAL_TRAIN_ORIGINAL_SERIES_SIZE_RHO_V1',
          catalog=catalog,series=rhos,histogram_references=[*old_histograms,*histograms],fit_population_reference=components['population_reference'],
          original_function='streaming_v1.reduce.rho_external',threshold_abs_rho=.95,undefined_kept_explicit=True,
          required_molecule_scalar_series_only=False,source_fields_validated_by_original_reader=146,required_scalar_fields=69,
          required_series_count=76,resumed_scalar_component_reference=resumed_reference,
          resumed_series_count=len(resumed),newly_computed_series_count=len(missing),
          resumed_scalar_values_unchanged=True,historical_histogram_parts_reread_or_reduced=False,
          original_physical_view_groups=selected_physical,
          non_molecule_size_policy='FROZEN_PER_FIELD_RULES_INCLUDING_REQUIRED_PHYSICAL_INVARIANTS',
          actual_D3_job_id=os.environ['SLURM_JOB_ID'],actual_source_groups=len(reports),actual_worker_pids=sorted({r['pid']for r in reports}),
          resumed_scalar_worker_pids=old_worker_pids,
          HOF_uses_actual_first_complete_TRAIN_element_reference_residual=True,statistics_reference=components['numeric_repetitions'][0],
          final_target_size_classification_or_normalizer_released=False,elapsed_seconds=time.monotonic()-started))
    finally:
        if pool is not None:pool.shutdown(wait=True,cancel_futures=False)
