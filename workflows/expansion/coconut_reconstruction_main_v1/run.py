"""Replay exact original scientific objects with Main resources and provenance."""
import collections, concurrent.futures as cf, hashlib, importlib, json, multiprocessing as mp, os, sqlite3, stat, sys, time
from pathlib import Path
from workflows.expansion.expansion_common_reference_v1 import runtime as R

SQL_BYTES=37876914074
SQL_SHA='bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29'
IDENTITY_SHA='9f188ee1722dffcb0c3f42b6177454200a3d2ec42899e74dcbebfd086e6ed850'
ROLE='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN'
TABLES={'citables':844850,'citations':124776,'collection_molecule':2446522,'collections':72,'entries':1799004,
 'geo_location_molecule':78235,'geo_locations':2847,'molecule_organism':1384191,'molecule_related':50003,'molecules':1140133,
 'organisms':73137,'properties':1140133,'structures':1140133,'taggables':25,'tags':17}
COUNTERS={'rows':2939137,'no_key':2207,'present_unresolved':2970,'missing':3777,'disagreement':30}
WORKER={}


def sources(plan):
    """No monkeypatch of original Alpha roots, proof or scientific constants."""
    source=Path(plan['original_source_root']).absolute()
    R.need(source.is_dir() and not source.is_symlink(),'EXACT_ORIGINAL_SOURCE_WITNESS_ROOT')
    if str(source) not in sys.path:sys.path.append(str(source))
    for ref in plan['original_source_references']:R.verify(ref)
    declared={r['sha256'] for r in plan['original_source_references']}
    modules={name:importlib.import_module(name) for name in (
      'secondary_coconut_sql_inventory_v1.probe','secondary_coconut_sql_identity_v1.run',
      'secondary_coconut_identity_norm_profile_v1.run','secondary_coconut_strict5_day_v1.kernel',
      'secondary_coconut_strict5_day_v1.frozen.decontamination',
      'workflows.expansion.identity_v2.projection_v2','workflows.expansion.common')}
    for name,module in list(sys.modules.items()):
        if name.startswith(('secondary_coconut_','secondary_cpu_')) or name in (
          'workflows.expansion.common','workflows.expansion.identity_v2.projection_v2','workflows.expansion.identity_v2.readers_v2'):
            file=getattr(module,'__file__',None)
            if file and file.endswith('.py'):R.need(R.pin(file)['sha256'] in declared,'UNPINNED_ORIGINAL_IMPORTED_SOURCE:'+name)
    from rdkit import Chem,rdBase
    import numpy,pyarrow
    R.need(sys.version_info[:3]==(3,11,14) and numpy.__version__=='2.2.6' and rdBase.rdkitVersion=='2025.09.5','EXACT_ORIGINAL_CHEMICAL_SOFTWARE')
    projection=modules['workflows.expansion.identity_v2.projection_v2'];common=modules['workflows.expansion.common']
    functions=dict(full_keys=projection.full_keys,source_smiles_keys=projection.source_smiles_keys,wp5_key=common.wp5_key)
    kernel=modules['secondary_coconut_strict5_day_v1.kernel'];consumer=modules['secondary_coconut_strict5_day_v1.frozen.decontamination'].identity_keys
    kernel.STATE.update(functions=functions,Chem=Chem,consumer=consumer,native=projection.native_composition)
    WORKER.update(normalize=modules['secondary_coconut_identity_norm_profile_v1.run'].normalize,functions=functions,kernel=kernel)
    return modules,dict(python=sys.version.split()[0],numpy=numpy.__version__,RDKit=rdBase.rdkitVersion,pyarrow=pyarrow.__version__,
      original_Alpha_Parquet_byte_equivalence_claimed=False,scientific_functions={k:dict(name=f.__module__+'.'+f.__qualname__,file=f.__code__.co_filename,line=f.__code__.co_firstlineno) for k,f in functions.items()})


def normalize_batch(rows):return [WORKER['normalize'](row,WORKER['functions']) for row in rows]
def project_batch(rows):return WORKER['kernel'].work(rows)


def original_fixtures(out,modules):
    """Reuse ten original scientific cases; Alpha-owned I/O case is inapplicable."""
    import tempfile,unittest
    root=out/'fixture_scratch';root.mkdir();tempfile.tempdir=str(root)
    probe=modules['secondary_coconut_sql_inventory_v1.probe'];sql=modules['secondary_coconut_sql_identity_v1.run']
    norm=modules['secondary_coconut_identity_norm_profile_v1.run'];norm.KernelFixtures.functions=WORKER['functions']
    strict_test=importlib.import_module('secondary_coconut_strict5_day_v1.test_v1')
    suite=unittest.TestSuite()
    for cls in (probe.ProbeMetadataFixtures,sql.KernelFixtures,norm.KernelFixtures):suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    for case in ('test_union_disagreement_full_keys_and_original_strict5_rejection','test_original_atoms_formula_conflict_and_orphan_stays_unknown'):suite.addTest(strict_test.Boundaries(case))
    R.need(suite.countTestCases()==10,'TEN_ORIGINAL_SCIENTIFIC_CASES')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    ref=R.save(out/'original_scientific_fixtures.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),before_SQL_DATA_IO=True,Alpha_owned_IO_case_not_reused=True))
    R.need(result.wasSuccessful() and result.testsRun==10 and not result.skipped,'ORIGINAL_SCIENTIFIC_CASES_REQUIRED');return ref


class Budget(R.Budget):
    def capacity(self,n):
        self.check(force=True);R.need(self.used()+n<=self.plan['output_cap_bytes'],'RESERVED_NEXT_WRITE_OUTPUT_CAP')


def parquet(ref,budget,expected):
    import pyarrow.parquet as pq
    path=R.verify(ref,lambda:budget.check());before=R.stamp(path.stat());seen=0
    with pq.ParquetFile(path) as file:
        R.need(file.metadata.num_rows==expected,'EXACT_ORIGINAL_RAW_ROW_COUNT')
        for batch in file.iter_batches(batch_size=256,use_threads=False):
            budget.check();R.need(batch.nbytes<=128<<20,'COMPLETE_BATCH_RESOURCE_BOUND');rows=batch.to_pylist();seen+=len(rows);yield rows
    R.need(seen==expected and before==R.stamp(path.stat()),'IMMUTABLE_COMPLETE_RAW_SOURCE')


def norm_batches(ref,budget,expected):
    pending=[]
    for rows in parquet(ref,budget,expected):
        pending.extend(rows)
        if len(pending)>=4096:yield pending;pending=[]
    if pending:yield pending


def inventory(plan,out,budget,modules):
    old=modules['secondary_coconut_sql_identity_v1.run'];probe=modules['secondary_coconut_sql_inventory_v1.probe']
    source=Path(plan['SQL_reference']['path']);ref=plan['SQL_reference']
    observed=source.lstat()
    R.need(ref['bytes']==SQL_BYTES and ref['sha256']==SQL_SHA and stat.S_ISREG(observed.st_mode) and observed.st_uid==1278 and observed.st_nlink==1 and observed.st_size==SQL_BYTES and not any(p.is_symlink() for p in (source,*source.parents)),'ORIGINAL_COMPLETE_OWNED_OCTOBER_SQL_PIN')
    profile=plan['mode']=='inventory_profile';root=out/('inventory_profile' if profile else 'inventory');root.mkdir();before=R.stamp(source.stat())
    with os.fdopen(os.open(source,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        R.need(before==R.stamp(os.fstat(stream.fileno())),'ACTUAL_STABLE_SQL_FD')
        prefix=stream.read(16<<20);schema=probe.inspect_prefix(prefix,lambda:budget.check())
        schema.update(actual_prefix_bytes=len(prefix),actual_prefix_sha256=hashlib.sha256(prefix).hexdigest())
        R.need(len(schema['tables'])==15 and all(t['complete_CREATE_TABLE_in_bounded_region'] for t in schema['tables']) and schema['standard_conforming_strings_markers']==['ON'],'ORIGINAL_EXACT_ALL15_DDL_IN_PREFIX')
        R.save(root/'schema_observations.json',schema);stream.seek(0)
        mode='profile' if profile else 'full';limit=plan['profile_limit_bytes'] if profile else 0
        shape=dict(mode=mode,scope_parameters=old.c.parameters(mode,limit),data_references=[ref])
        sink=old.Sink(root,lambda:budget.check())
        try:
            value=old.inventory(stream,shape,schema,sink,lambda:budget.check(),lambda v:print(json.dumps(dict(stage='inventory',**v)),flush=True))
        finally:sink.db.close()
    R.need(before==R.stamp(source.stat()),'ACTUAL_SQL_IMMUTABLE')
    if not profile:R.need(value['physical_COPY_rows_by_table']==TABLES and value['read_region_SHA256']==SQL_SHA and value['full_EOF_and_all_tables_proven'],'SAME_ORIGINAL_FULL_SQL_AND_ALL_PHYSICAL_COUNTS')
    raw={table:dict(R.pin(root/(table+'.raw_identity.parquet'),lambda:budget.check()),rows=n) for table,n in value['reconciliation']['projected_rows_by_table'].items()}
    return R.save(out/'inventory.receipt.json',dict(schema='COCONUT_MAIN_RECONSTRUCTED_INVENTORY_V1',status='BOUNDED_PROFILE_NOT_FULL_SOURCE' if profile else 'ORIGINAL_SQL_ALL_PHYSICAL_ROWS_RECONSTRUCTED',source=ref,original_inventory=value,raw=raw,
      source_roles_or_statuses_filtered=False,source_file_frame=before,Main_parent_C0_pending_root_readback=True))


def normalized(plan,out,budget,parent):
    source=R.read(parent,16<<20);R.need(source['schema']=='COCONUT_MAIN_RECONSTRUCTED_INVENTORY_V1' and source['status']=='ORIGINAL_SQL_ALL_PHYSICAL_ROWS_RECONSTRUCTED','ACTUAL_MAIN_CLOSED_FULL_INVENTORY')
    root=out/'norm';root.mkdir(exist_ok=True);parts=[];counts=collections.Counter()
    ctx=mp.get_context('spawn')
    with cf.ProcessPoolExecutor(max_workers=plan['cpus'],mp_context=ctx,initializer=sources,initargs=(plan,)) as pool:
        for table in ('molecules','entries'):
            pending=collections.deque();part=0;start=0
            def collect():
                future,rows,number,first=pending.popleft();values=future.result();R.need(len(values)==len(rows),'NO_NORM_WORKER_ROW_DROP')
                target=root/('%s_%06d_job%s.jsonl'%(table,number,budget.proof['job_id']));writer=R.Writer(target,budget)
                for raw,observation in zip(rows,values):
                    R.need(observation['source']==raw,'EXACT_ORIGINAL_LOCATOR_AND_ALLOWLIST_RETAINED');writer.write(observation)
                writer.close();ref=dict(writer.reference(),rows=len(rows),table=table,first=first)
                closure=dict(schema='COCONUT_MAIN_CLOSED_NORM_PART_V1',input=source['raw'][table],original_sources=plan['original_source_references'],part=ref)
                R.save(root/('%s_%06d.closed.json'%(table,number)),closure);return ref
            # Each closed source batch is independently reusable; no retry of a closed chemistry observation.
            for rows in norm_batches(source['raw'][table],budget,TABLES[table]):
                close=root/('%s_%06d.closed.json'%(table,part))
                if close.exists():
                    while pending:parts.append(collect())
                    closure=json.loads(close.read_text());ref=closure['part']
                    R.need(closure['schema']=='COCONUT_MAIN_CLOSED_NORM_PART_V1' and closure['input']==source['raw'][table] and closure['original_sources']==plan['original_source_references'] and ref['table']==table and ref['first']==start and ref['rows']==len(rows),'EXACT_CLOSED_PART_RESUME_BINDING')
                    R.verify(ref,lambda:budget.check());parts.append(ref)
                else:
                    pending.append((pool.submit(normalize_batch,rows),rows,part,start))
                    if len(pending)>=2*plan['cpus']:parts.append(collect())
                start+=len(rows);part+=1
            while pending:parts.append(collect())
    for part in parts:
        with Path(part['path']).open('rb') as stream:
            for raw in stream:
                budget.check();o=json.loads(raw);counts.update(rows=1,no_key=int(not o['has_any_valid_full_key']),present_unresolved=o['unresolved_present_variants'],missing=o['missing_variants'],disagreement=int(o['stored_vs_computed_disagreement']))
    R.need(dict(counts)==COUNTERS,'EXACT_ORIGINAL_ALL_VARIANT_COUNTERS')
    return R.save(out/'norm.receipt.json',dict(schema='COCONUT_MAIN_RECONSTRUCTED_NORM_V1',inventory=parent,parts=parts,counters=dict(counts),original_function_object_replay=True,original_UNKNOWN_preserved=True,Main_parent_C0_pending_root_readback=True))


def strict(plan,out,budget,parent):
    norm=R.read(parent,16<<20);R.need(norm['schema']=='COCONUT_MAIN_RECONSTRUCTED_NORM_V1','ACTUAL_CLOSED_MAIN_FULL_NORM')
    inventory=R.read(norm['inventory'],16<<20)
    R.need(inventory['source']==plan['SQL_reference'] and list(R.stamp(Path(plan['SQL_reference']['path']).stat()))==inventory['source_file_frame'],'SAME_CURRENT_WHOLE_SHA_VALIDATED_SQL_SOURCE')
    root=out/'strict';root.mkdir();scratch=root/'sqlite_tmp';scratch.mkdir();os.environ['SQLITE_TMPDIR']=str(scratch)
    db=sqlite3.connect(root/'identity_links.sqlite');db.executescript('PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL;PRAGMA cache_size=-65536;PRAGMA temp_store=FILE;CREATE TABLE properties(mid TEXT,payload TEXT);CREATE INDEX property_mid ON properties(mid);CREATE TABLE molecules(mid TEXT PRIMARY KEY,payload TEXT);CREATE TABLE seen(t TEXT,b INTEGER,o INTEGER,PRIMARY KEY(t,b,o)) WITHOUT ROWID;')
    ident=R.Writer(root/'identities.jsonl',budget);unknown=R.Writer(root/'unknown735_original_rows.DATA.jsonl',budget);audit=R.Writer(root/'physical_audit.DATA.jsonl',budget)
    counts=collections.Counter();tables=collections.Counter();original=collections.Counter();consumer=WORKER['kernel'].STATE['consumer'];pending=collections.deque()
    for rows in parquet(inventory['raw']['properties'],budget,TABLES['properties']):
        for row in rows:
            fields=json.loads(row['identity_fields_json']);R.need(set(fields)=={'id','molecule_id','molecular_formula'},'EXACT_ORIGINAL_FORMULA_ALLOWLIST')
            payload=dict(value=fields['molecular_formula'],locator=dict(reference=inventory['raw']['properties'],source_table='properties',copy_block=row['copy_block'],source_row_ordinal=row['source_row_ordinal'],source_row_sha256=row['source_row_sha256']))
            db.execute('INSERT INTO properties VALUES(?,?)',(fields['molecule_id'],json.dumps(payload,separators=(',',':'))))
        db.commit()
    ctx=mp.get_context('spawn')
    def collect():
        future,observations=pending.popleft();values=future.result();R.need(len(values)==len(observations),'NO_STRICT_PHYSICAL_ROW_DROP')
        for value,o in zip(values,observations):
            row=o['source'];table=value['table'];db.execute('INSERT INTO seen VALUES(?,?,?)',(table,value['copy_block'],value['ordinal']));tables[table]+=1;original.update(value['original_norm_counters']);counts['FK_'+value['FK_state']]+=1
            if table=='molecules':db.execute('INSERT INTO molecules VALUES(?,?)',(value['molecule_id'],json.dumps(dict(molecule_id=value['molecule_id'],keys=value['keys'],compositions=value['all_native_compositions'],locator=row),separators=(',',':'))))
            base=dict(source_id=value['source_id'],role=ROLE,subdataset=table,inchikeys=value['keys'],non_h_composition=None)
            if value['keys']:consumer(base);ident.write(base);counts['strict_rows']+=1
            for j,comp in enumerate(value['compositions']):
                item=dict(base,source_id=value['source_id']+':composition:'+str(j),inchikeys=[],non_h_composition=comp);consumer(item);ident.write(item);counts['strict_rows']+=1;counts['composition_rows']+=1
            if not value['covered']:
                fields=json.loads(row['identity_fields_json'])
                R.need(table=='entries' and fields['molecule_id'] is None and o['has_any_valid_full_key'] is False,'EXACT_ORIGINAL735_NULL_FK_UNKNOWN_CLASS')
                # Same original scientific observation, new Main reconstruction
                # provenance. This is not the absent Alpha diagnosis byte body.
                unknown.append(dict(source=row,norm_observation=o,original_unresolved=dict(locator=row),strict_projection=value,
                  original_UNKNOWN_unchanged=True,new_authoritative_keys=False,graph_identity_repaired=False,
                  reconstruction_origin='EXACT_ORIGINAL_SQL_REPLAY_ON_MAIN_NOT_ALPHA_DIAGNOSIS_BYTE_REPLICA'))
                counts['unknown']+=1
            audit.write(dict(source=row,strict_projection=value,graph_identity_repaired=False))
        db.commit()
    try:
        with cf.ProcessPoolExecutor(max_workers=plan['cpus'],mp_context=ctx,initializer=sources,initargs=(plan,)) as pool:
            for table in ('molecules','entries'):
                for part in [p for p in norm['parts'] if p['table']==table]:
                    R.verify(part,lambda:budget.check());observations=[]
                    with Path(part['path']).open('rb') as stream:
                        for raw in stream:observations.append(json.loads(raw))
                    R.need(len(observations)==part['rows'],'ALL_CLOSED_PART_ROWS');items=[]
                    for o in observations:
                        fields=json.loads(o['source']['identity_fields_json'])
                        if table=='molecules':formulas=[json.loads(r[0]) for r in db.execute('SELECT payload FROM properties WHERE mid=?',(fields['id'],))];parent_molecule=None
                        else:
                            formulas=[];hit=db.execute('SELECT payload FROM molecules WHERE mid=?',(fields['molecule_id'],)).fetchone();parent_molecule=json.loads(hit[0]) if hit else None
                        items.append((o,formulas,parent_molecule))
                    budget.check();pending.append((pool.submit(project_batch,items),observations))
                    if len(pending)>=2*plan['cpus']:collect()
                while pending:collect()
        R.need(dict(tables)=={'molecules':1140133,'entries':1799004} and dict(original)==COUNTERS,'ALL_ORIGINAL_ROWS_AND_UNKNOWN_COUNTERS')
        R.need(counts['FK_NULL']==2454 and counts['FK_ORPHAN']==26 and counts['FK_MATCHED']==1796524 and counts['composition_rows']==1496 and counts['strict_rows']==2938431 and counts['unknown']==735,'EXACT_ORIGINAL_STRICT_COVERAGE_COUNTS')
        R.need(db.execute('SELECT count(*) FROM properties p LEFT JOIN molecules m ON p.mid=m.mid WHERE m.mid IS NULL').fetchone()[0]==0,'ORIGINAL_FORMULA_FK_COMPLETE')
    finally:
        db.commit();db.close();ident.close();unknown.close();audit.close()
    refs=dict(identities=ident.reference(),unknown735=unknown.reference(),audit=audit.reference())
    R.need(refs['identities']['bytes']==551607405 and refs['identities']['sha256']==IDENTITY_SHA,'EXACT_ORIGINAL_STRICT_IDENTITIES_WHOLE_BYTES_REQUIRED')
    replay=0
    with Path(refs['identities']['path']).open('rb') as stream:
        for raw in stream:budget.check();consumer(json.loads(raw));replay+=1
    R.need(replay==2938431,'ORIGINAL_CONSUMER_COMPLETE_READBACK')
    rawroot=root/'unknown735_original_SQL_rows';rawroot.mkdir();raw_refs=[];sql=Path(plan['SQL_reference']['path']);stamp=R.stamp(sql.stat())
    with sql.open('rb') as source,Path(refs['unknown735']['path']).open('rb') as stream:
        for i,raw in enumerate(stream):
            budget.check();item=json.loads(raw);row=item['source'];source.seek(row['source_offset']);data=source.read(row['source_bytes'])
            R.need(len(data)==row['source_bytes'] and hashlib.sha256(data).hexdigest()==row['source_row_sha256'],'ORIGINAL_OPAQUE_ROW_CURRENT_SQL_BYTES')
            target=rawroot/('row_%06d.DATA.raw'%i)
            with target.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            raw_refs.append(dict(R.pin(target),table=row['source_table'],block=row['copy_block'],ordinal=row['source_row_ordinal'],source_offset=row['source_offset']))
    R.need(stamp==R.stamp(sql.stat()) and len(raw_refs)==735,'OPAQUE_ALL735_ORIGINAL_SQL_IMMUTABLE')
    return R.save(out/'strict.receipt.json',dict(schema='COCONUT_MAIN_RECONSTRUCTED_STRICT5_V1',status='EXACT_ORIGINAL_STRICT_IDENTITIES_RECOVERED_735_UNKNOWN_RETAINED',norm=parent,outputs=refs,opaque_source_rows=raw_refs,counters=dict(counts),original_norm_counters=dict(original),Main_parent_C0_pending_root_readback=True,
      all11_decontamination_ready=False,global_pool_release=False,graph_identity_repaired=False,new_QM_UFF_calls=0))


def main():
    import argparse,traceback
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text());req=proof['request']
    R.need(plan['schema']=='COCONUT_MAIN_ORIGINAL_RECONSTRUCTION_PLAN_V1' and plan['mode'] in ('source','inventory_profile','inventory','norm','strict','all'),'EXACT_RECONSTRUCTION_PLAN')
    # The independent controller records actual Main identity; original Alpha proof is never synthesized.
    R.need(req['scope_key']=='coconut_main_original_reconstruction_v1' and req['producer_plan_reference']==R.pin(a.plan),'INDEPENDENT_EXACT_MAIN_REQUEST')
    R.need(req['execution_argv']==[plan['python'],'-B','-m','workflows.expansion.coconut_reconstruction_main_v1.run','--plan',str(a.plan),'--startup-proof',str(a.startup_proof)],'ORDERED_FULL_MAIN_ARGV')
    R.need(os.getuid()==1278 and proof['node']==plan['node']==os.uname().nodename.split('.')[0] and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==plan['cpus']>=16,'ACTUAL_MAIN_CPU_ALLOCATION')
    R.need(proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_MAIN_BOOT_AND_RESOURCE_POLICY')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    declared={r['path']:r for r in req['source_references']}
    for module in (Path(__file__).parent,R.__file__):
        files=Path(module).glob('*.py') if Path(module).is_dir() else [Path(module)]
        for source in files:R.need(declared.get(str(source.absolute()))==R.pin(source),'ACTUAL_RECONSTRUCTION_AND_RUNTIME_SOURCE_PINS')
    out=Path(plan['output_directory']);out.mkdir(exist_ok=plan['mode']=='norm');budget=Budget(plan,proof,out)
    modules,environment=sources(plan);R.save(out/('environment_%s.json'%proof['job_id']),environment)
    try:
        # This source suite precedes DATA for a new producer; a resumed norm uses the already closed gate.
        if (out/'original_scientific_fixtures.json').exists():
            fixture=json.loads((out/'original_scientific_fixtures.json').read_text());R.need(fixture['tests']==10 and fixture['failures']==fixture['errors']==fixture['skips']==0,'ACTUAL_PREVIOUS_SOURCE_GATE')
        else:original_fixtures(out,modules)
        if plan['mode']=='source':
            R.save(out/('producer_%s.receipt.json'%proof['job_id']),dict(status='ORIGINAL_SOURCE_CASES_ONLY_NO_SQL_BODY_READ',runtime=budget.receipt(),Main_parent_C0_pending_root_readback=True));return
        inv=inventory(plan,out,budget,modules) if plan['mode'] in ('inventory_profile','inventory','all') else plan.get('inventory_reference')
        norm=normalized(plan,out,budget,inv) if plan['mode'] in ('norm','all') else plan.get('norm_reference')
        result=strict(plan,out,budget,norm) if plan['mode'] in ('strict','all') else norm or inv
        R.save(out/('producer_%s.receipt.json'%proof['job_id']),dict(schema='COCONUT_MAIN_ORIGINAL_RECONSTRUCTION_PRODUCER_V1',plan=R.pin(a.plan),startup_proof=R.pin(a.startup_proof),stage_result=result,runtime=budget.receipt(),Main_parent_C0_pending_root_readback=True,all11_ready=False))
    except BaseException as exc:
        R.save(out/('failure_%s.json'%proof['job_id']),dict(status='TECHNICAL_HOLD_NO_SCIENTIFIC_RELEASE',error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,no_chemical_retry=True));raise


if __name__=='__main__':main()
