"""Full candidate closure producer: saved evidence only, no scientific calls."""
import collections
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
from ..alpha_runtime_v1 import common as Q
from ..uff3_candidate_v1 import core as C,run as G
from ..uff3_alpha_runtime_v1.quality_authority import accepted,read
from ..uff3_alpha_runtime_v1.terminal import parent as terminal_parent
from ..uff3_alpha_runtime_v1.quality_budget import QualityBudget
from ..pubchem_closed500_bulk_v2.merge import literal
from . import closed,validation as V,storage,families

N=2500000


def actual_inputs(plan):
    accepted(plan['quality_reference_review'])
    qa=read(plan['qa_report_reference'])
    terminal_parent(qa['runtime'],plan['qa_actual_accounting_reference'])
    Q.need(qa['schema']=='PUBCHEM_UFF3_VALIDITY_REVIEW_V1'and qa['mode']=='full'
        and qa['status']=='COMPLETE_ORIGINAL_MASK_AND_ROBUST_REVIEW_REPORT'
        and qa['source_molecules_by_stream']=={'R':1250000,'N':1250000}
        and qa['quality_reference_review']==plan['quality_reference_review']and qa['generation_receipts']==plan['generation_receipts']
        and qa['source_capsule_reference']==plan['source_capsule_reference']
        and qa['new_R_N_TRAIN_fit']is False and qa['source_missing_NA_not_counted_as_new_mask']is True
        and qa['one_percent_action']=='REPORT_USER_ONLY_MASK_LABELS_KEEP_ALL_RECORDS'
        and qa['technical_unknown_sources_preserved_not_fabricated_as_valid']is True,
        'Actual complete producer QA/robust review, all sources kept; no per-job Root approval')
    accounts=[read(ref)for ref in plan['generation_actual_accounting_references']]
    parents=[]
    for a in accounts:
        Q.need(a['endpoint']==Q.ENDPOINT and a['uid']==Q.UID,'Actual Alpha generation accounting')
        Q.verify(a['raw_sacct_reference']);parents.extend(a['actual_parents'])
    receipts=[read(ref)for ref in plan['generation_receipts']]

    shards=[]
    for r in receipts:
        p=[p for p in parents if str(p['JobIDRaw'])==str(r['runtime']['job_id'])]
        Q.need(r['schema']=='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'
            and r['status']=='COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE'and r['mode']=='full'
            and r['source_manifest']==plan['source_manifest']and r['source_total_molecules']==N
            and r['maximum_conformers']==3 and r['recipe_sha256']==C.recipe_sha()
            and r['quality_reference_review']==plan['quality_reference_review']and r['new_QM_calls']==0
            and r['runtime']['endpoint']==Q.ENDPOINT and r['runtime']['uid']==Q.UID
            and len(p)==1 and p[0]['State']=='COMPLETED'and p[0]['ExitCode']=='0:0'and int(p[0]['UID'])==Q.UID,
            'Every adopted full/shard result is actual completed Alpha candidate production')
        Q.need(r['source_capsule_reference']==plan['source_capsule_reference'],
               'Same actual frozen scientific source capsule, no manual execution-review wrapper')
        for ref in r['execution_metadata'].values():
            if ref:Q.verify(ref)
        matches=[ref for ref,a in zip(plan['generation_actual_accounting_references'],accounts)if any(str(p['JobIDRaw'])==str(r['runtime']['job_id'])for p in a['actual_parents'])]
        Q.need(len(matches)==1,'One actual machine accounting reference per producer')
        terminal_parent(r['runtime'],matches[0])
        shards.append((r['shard_index'],r['shard_count']))
    Q.need(bool(shards)and len({n for i,n in shards})==1 and sorted(i for i,n in shards)==list(range(shards[0][1])),
           'Exactly all disjoint complete full shards, no duplicated or missing shard')
    return qa,receipts


def source_table(db,manifest,guard):
    Q.need(manifest['schema']=='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'and manifest['molecules']==N
        and manifest['molecules_by_stream']=={'R':1250000,'N':1250000},'Full true frozen2.5M source')
    db.execute('CREATE TABLE source(mid VARCHAR,identity VARCHAR,cid BIGINT,full_key VARCHAR,stream VARCHAR,rank BIGINT,version VARCHAR,row_sha VARCHAR,once_key VARCHAR)')
    rows=[]
    for row in G.source_rows(manifest):
        raw=dict(row);declared=raw.pop('source_row_sha256')
        Q.need(C.sha(C.canonical(raw))==declared,'Frozen exact source row SHA')
        identity=C.source_identity(row);rows.append((C.molecule_id(row),identity,row['cid'],row['full_key'],row['stream'],row['stream_rank'],row['pubchem_version'],declared,C.sha(C.canonical([C.recipe_sha(),identity]))))
        if len(rows)>=10000:
            db.executemany('INSERT INTO source VALUES(?,?,?,?,?,?,?,?,?)',rows);rows=[];guard.check()
    if rows:db.executemany('INSERT INTO source VALUES(?,?,?,?,?,?,?,?,?)',rows)
    Q.need(db.execute('SELECT count(*),count(DISTINCT mid),count(DISTINCT cid),count(DISTINCT full_key),count(DISTINCT(stream,rank))FROM source').fetchone()==(N,N,N,N,N),'Every full frozen molecule/CID/key/rank exactly once')
    Q.need(db.execute('SELECT stream,count(*),min(rank),max(rank)FROM source GROUP BY stream ORDER BY stream').fetchall()==[('N',1250000,1,1250000),('R',1250000,1,1250000)],'Both complete frozen stream ranks')


def items(plan,receipts,db,file_refs,batch_refs,guard):
    for receipt_ref,receipt in zip(plan['generation_receipts'],receipts):
        root=Path(receipt_ref['path']).parent;index=root/'index.sqlite'
        Q.need(not any(Path(str(index)+suffix).exists()for suffix in ('-wal','-journal')),'Closed generation index without active WAL/journal')
        before=closed.frame(index.lstat());s=sqlite3.connect(index.as_uri()+'?mode=ro',uri=True)
        try:
            meta=dict(s.execute('SELECT key,value FROM meta'))
            Q.need(meta['source_census_complete']=='true'and meta['source_manifest_sha']==C.sha(C.canonical(plan['source_manifest']))
                and s.execute('SELECT count(*)FROM source').fetchone()[0]==N,'Closed index exact frozen source census')
            shard=receipt['shard_index'];count=receipt['shard_count']
            Q.need(s.execute('SELECT count(*)FROM done WHERE ordinal%?<>?',(count,shard)).fetchone()[0]==0,
                   'No outside-shard pilot results silently regenerated or dropped; explicit cache redistribution is not this producer')
            expected=s.execute('SELECT count(*)FROM source WHERE ordinal%?=?',(count,shard)).fetchone()[0]
            Q.need(expected==receipt['expected_molecules']==receipt['closed_family_export_molecules']==s.execute('SELECT count(*)FROM done').fetchone()[0],
                   'Actual complete selected shard includes sparse/failed/unknown results')
            emitted=0
            for path,body in s.execute('SELECT path,body FROM batches ORDER BY path'):
                b=json.loads(body);ref=Q.reference(path);actual=closed.document(ref,plan['maximum_metadata_input_bytes'])
                Q.need(C.canonical(actual)==C.canonical(b)and b['schema']=='PUBCHEM_UFF3_CLOSED_FAMILY_BATCH_V1'
                    and b['maximum_delivered_conformers']==3 and b['quality_reference_review']==plan['quality_reference_review'],
                    'Same actual immutable batch body/three-conformer/189 source')
                Q.need(path not in batch_refs,'No duplicated batch across adopted input shards');batch_refs[path]=ref
                for f in b['family_files']:
                    old=file_refs.get(f['path']);Q.need(old is None or old==f,'Same family path cannot have two bodies')
                    file_refs[f['path']]=f
                for m in b['molecules']:
                    row=s.execute('SELECT x.body,d.manifest,d.batch_manifest,d.status FROM source x JOIN done d USING(ordinal)WHERE ordinal=?',(m['ordinal'],)).fetchone()
                    Q.need(row is not None and json.loads(row[1])==m['manifest']and row[2]==path and row[3]==m['state']
                        and m['ordinal']%count==shard,'Exact index/batch/physical MID membership and actual worker evidence')
                    emitted+=1;yield(m['ordinal'],json.loads(row[0]),m['manifest'],m['worker_pid'],m['closed_reused'],plan['maximum_molecule_artifact_bytes'])
                guard.check()
            Q.need(emitted==expected,'All and only source results appear in closed batches')
        finally:
            s.close();Q.need(before==closed.frame(index.lstat()),'No active/mutated source index while closing')
        # Root can hash this closed SQL index once; it is metadata evidence, not
        # part of the4x persistent UFF/D data forecast.
        storage.add(db,[storage.fact(index,'GENERATION_RUNTIME_SQL_METADATA')])


def save_fact(db,result,out):
    source=result['source'];mid=result['molecule_id'];pkt=result['packet_reference']
    values=(mid,result['source_identity_sha256'],source['cid'],source['full_key'],source['stream'],source['stream_rank'],source['pubchem_version'],source['source_row_sha256'],result['once_key'],pkt['sha256'],
        result['D20_hash'],C.canonical(result['D20_names']).decode(),C.canonical(result['D20_valid_mask']).decode(),result['status_hash'],result['actual_conformers'],result['delivered_conformers'],result['D20_state'],result['state'],source.get('wp5_key',source['full_key'][:14]+':'+source['full_key'][-1]))
    db.execute('INSERT INTO facts VALUES('+','.join('?'for _ in values)+')',values)
    rows=[(mid,r['record_id'],r['conformer_id'],r['D3_hash'],r['geometry_sha256'],r['energy_hash'],r['native_candidate_id'],r['atom_order_sha256'])for r in result['conformers']]
    if rows:db.executemany('INSERT INTO expected_conformers VALUES(?,?,?,?,?,?,?,?)',rows)
    out.write(C.canonical(result)+b'\n')
    native=[storage.fact(ref['path'],'SAVED_MOLECULE_EVIDENCE')for ref in result['artifacts']]
    m=closed.document(result['manifest_reference'],1<<20)
    directory=Path(m['output_directory'])if m['schema']=='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1'else Path(result['manifest_reference']['path']).parent
    native.append(storage.fact(directory,'MOLECULE_DIRECTORY_METADATA'));storage.add(db,native)


def logical_membership(db):
    Q.need(db.execute('SELECT count(*),count(DISTINCT mid),count(DISTINCT identity),count(DISTINCT once_key)FROM facts').fetchone()==(N,N,N,N),'No source/once-key dropped or scientifically duplicated')
    cols='mid,identity,cid,full_key,stream,rank,version,row_sha,once_key'
    facts='mid,identity,cid,full_key,stream,stream_rank,pubchem_version,row_sha,once_key'
    Q.need(db.execute('SELECT count(*)FROM((SELECT '+cols+' FROM source EXCEPT SELECT '+facts+' FROM facts)UNION ALL(SELECT '+facts+' FROM facts EXCEPT SELECT '+cols+' FROM source))').fetchone()[0]==0,
           'Bidirectional full source/CID/key/stream/rank/version/SHA/once-key closure')


def mask_membership(db,refs,qa,plan):
    paths=[r['path']for r in refs if r['family']=='validity_masks'];Q.need(bool(paths),'Original actual masks retained')
    db.read_parquet(paths,union_by_name=False).create_view('masks')
    review,_,_=accepted(plan['quality_reference_review'])
    fields=read(review['actual_field_map_and_mask_replicas']['field_map_reference'])
    selected=[(str(f['field_id']),f['task'])for f in fields if f['task']in('D20','D3')]
    Q.need(len(selected)==27,'Same original20+7 field map')
    db.execute('CREATE TABLE field_tasks(field_id VARCHAR,task VARCHAR)');db.executemany('INSERT INTO field_tasks VALUES(?,?)',selected)
    Q.need(db.execute('SELECT count(*)FROM masks m LEFT JOIN facts f ON m.molecule_id=f.mid WHERE f.mid IS NULL OR m.stream<>f.stream OR m.producer_packet_sha256<>f.packet_sha OR m.dataset_version<>\'v2_candidate\'').fetchone()[0]==0,
           'Every mask belongs to a retained source and actual saved packet')
    Q.need(db.execute('SELECT count(*)FROM masks m LEFT JOIN field_tasks t USING(field_id)LEFT JOIN expected_conformers e ON m.record_id=e.record_id AND m.molecule_id=e.mid WHERE t.task IS NULL OR(t.task=\'D20\'AND m.record_id<>m.molecule_id||\':graph\')OR(t.task=\'D3\'AND e.record_id IS NULL)').fetchone()[0]==0,
           'Original task/record/physical actual-conformer mask domains')
    Q.need(db.execute('SELECT count(*)FROM(SELECT field_id,record_id FROM masks GROUP BY ALL HAVING count(*)<>1)').fetchone()[0]==0,'No duplicate mask record/field')
    expected_conf=db.execute('SELECT count(*)FROM expected_conformers').fetchone()[0]
    counts=dict(db.execute('SELECT field_id,count(*)FROM masks GROUP BY field_id').fetchall())
    Q.need(all(counts.get(field,0)==(N if task=='D20'else expected_conf)for field,task in selected),'Every original graph/actual-D3 field represented, including failed source NA')
    actual={Q.canonical({k:r[k]for k in('path','bytes','sha256')})for r in refs}
    accepted_files={Q.canonical({k:r[k]for k in('path','bytes','sha256')})for r in qa['all_family_file_references']}
    Q.need(actual==accepted_files,'Exactly the full independently accepted QA input files')
    return counts

def scratch(db,receipts,qa,plan,guard):
    # Small top-level runtime namespaces and closed QA scope only. Essential
    # per-MID/family data were already counted by their current verified FDs.
    for ref in plan['generation_receipts']:
        root=Path(ref['path']).parent
        rows=[]
        for path in root.iterdir():
            if path.is_file():rows.append(storage.fact(path,'GENERATION_RUNTIME_SQL_METADATA'))
            elif path.name in('molecules','families','interrupted'):
                rows.append(storage.fact(path,'GENERATION_ROUTING_METADATA'))
                if path.name=='molecules':
                    rows.extend(storage.fact(p,'GENERATION_ROUTING_METADATA')for p in path.iterdir()if p.is_dir())
                elif path.name=='families':
                    for folder in path.iterdir():
                        if not (folder/'manifest.json').exists():
                            for base,dirs,files in os.walk(folder,followlinks=False):
                                rows.append(storage.fact(base,'RETAINED_UNCOMMITTED_FAMILY_SCRATCH'))
                                rows.extend(storage.fact(Path(base)/n,'RETAINED_UNCOMMITTED_FAMILY_SCRATCH')for n in files)
            else:Q.need(not path.is_symlink(),'No unexpected generation routing symlink')
        storage.add(db,rows);guard.check()
    qa_root=Path(plan['qa_report_reference']['path']).parent
    for base,dirs,files in os.walk(qa_root,followlinks=False):
        storage.add(db,[storage.fact(p,'QA_ANALYSIS_AND_SQL_SCRATCH')for p in [Path(base),*(Path(base)/n for n in files)]])
        Q.need(not any((Path(base)/n).is_symlink()for n in dirs),'QA scope symlink');guard.check()
    shared=[]
    for ref in plan['shared_input_references']:
        # Metadata observation, no duplicate full-Common/raw/calibration scans.
        # Keep actual immutable input SHA authority refs separate from this stat.
        f=storage.fact(ref['path'],'SHARED_READ_ONLY_INPUT')
        Q.need(f[4]==ref['bytes'],'Actual local shared-input size differs')
        storage.add(db,[f]);shared.append(ref)
    return shared


def run(plan,actual):
    import duckdb
    root=Path(plan['output_directory']);Q.need(root==Path(plan['output_scope_root']),'Small private closure SQL scope only')
    guard=QualityBudget(plan,root)
    try:qa,receipts=actual_inputs(plan);manifest=read(plan['source_manifest'])
    except BaseException:
        guard.close();raise
    Q.need(plan.get('expected_molecules',N)==N and plan['maximum_conformers']==3,
           'This producer cannot close a pilot/prefix or future4+ as the full candidate dataset')
    db=duckdb.connect(str(root/'closure.duckdb'));guard.configure(db,literal)
    db.execute('CREATE TABLE facts(mid VARCHAR,identity VARCHAR,cid BIGINT,full_key VARCHAR,stream VARCHAR,stream_rank BIGINT,pubchem_version VARCHAR,row_sha VARCHAR,once_key VARCHAR,packet_sha VARCHAR,d20_hash VARCHAR,d20_names VARCHAR,d20_mask VARCHAR,status_hash VARCHAR,actual_conf BIGINT,delivered BIGINT,d20_state VARCHAR,state VARCHAR,wp5_key VARCHAR)')
    db.execute('CREATE TABLE expected_conformers(mid VARCHAR,record_id VARCHAR,conformer_id BIGINT,d3_hash VARCHAR,geometry_sha VARCHAR,energy_hash VARCHAR,native_id BIGINT,atom_order_sha VARCHAR)')
    storage.initialize(db);file_refs={};batch_refs={};saved=0;unknown=0;append4=0;has_cache=0
    catalog=root/'molecule_saved_evidence.jsonl'
    try:
        db.execute('BEGIN TRANSACTION');source_table(db,manifest,guard);db.execute('COMMIT')
        db.execute('BEGIN TRANSACTION')
        with catalog.open('xb')as out,ProcessPoolExecutor(max_workers=plan['workers'],mp_context=multiprocessing.get_context('spawn'))as pool:
            pending=collections.deque()
            def accept(future):
                nonlocal saved,unknown,append4,has_cache
                guard.check();r=future.result();save_fact(db,r,out);saved+=1
                unknown+=r['actual_conformers']is None;has_cache+=r['cache_available']is True
                append4+=r['saved_cache_supports_at_least_four_total']is True
                if saved%4096==0:guard.check(True)
            for item in items(plan,receipts,db,file_refs,batch_refs,guard):
                guard.check();pending.append(pool.submit(closed.read_one,item))
                if len(pending)>=2*plan['workers']:accept(pending.popleft())
            while pending:accept(pending.popleft())
            out.flush();os.fsync(out.fileno())
        db.execute('COMMIT');Q.need(saved==N,'Every frozen source has one retained saved evidence record')
        logical_membership(db)
        refs=list(file_refs.values());families.scan(db,refs,guard);families.compare(db)
        masks=mask_membership(db,refs,qa,plan);shared=scratch(db,receipts,qa,plan,guard)
        footprint=storage.summarize(db)
        actual_states=dict(db.execute('SELECT state,count(*)FROM facts GROUP BY state').fetchall())
        Q.need(actual_states==qa['source_state_counts'],'Independently accepted QA status census equals actual retained packets, including unknown')
        stats=dict(source_molecules=N,molecules_by_stream=dict(db.execute('SELECT stream,count(*)FROM facts GROUP BY stream').fetchall()),
            source_state_counts=dict(db.execute('SELECT state,count(*)FROM facts GROUP BY state').fetchall()),
            D20_evidence_state_counts=dict(db.execute('SELECT d20_state,count(*)FROM facts GROUP BY d20_state').fetchall()),
            actual_exported_conformers=db.execute('SELECT sum(delivered)FROM facts').fetchone()[0],
            unknown_actual_export_count_molecules=unknown,unknown_delivery_is_not_claimed_scientific_zero=True,
            scientific_generation_total_not_inferred_from_delivery=True,
            verified_closed_cache_molecules=has_cache,saved_cache_supports_at_least_four_total_molecules=append4,
            every_source_has_extendable_cache_claimed=False,D20_family_rows=N,
            D20_native_success_or_call_count_inferred_from_source_presence=False,mask_rows_by_field=masks)
        db.execute('CREATE TABLE batch_catalog(path VARCHAR,bytes BIGINT,sha256 VARCHAR)')
        db.executemany('INSERT INTO batch_catalog VALUES(?,?,?)',[(r['path'],r['bytes'],r['sha256'])for r in batch_refs.values()])
        outputs={}
        for name,query in [('molecules','SELECT *FROM facts ORDER BY stream,stream_rank'),
                           ('conformers','SELECT *FROM expected_conformers ORDER BY mid,conformer_id'),
                           ('family_files','SELECT *FROM family_catalog ORDER BY family,path'),
                           ('batches','SELECT *FROM batch_catalog ORDER BY path'),
                           ('physical_storage','SELECT *FROM physical ORDER BY category,path')]:
            p=root/(name+'.parquet');db.execute('COPY('+query+')TO '+literal(p)+'(FORMAT PARQUET,COMPRESSION ZSTD)');outputs[name]=Q.reference(p)
        db.execute('CHECKPOINT');guard.check(True)
    finally:
        guard.stop_sql_monitor();db.close();guard.close()
    # SQL is terminal before its final physical metadata census. This is own
    # closure scratch, excluded from the10M persistent dataset extrapolation.
    finalizer_blocks=sum(storage.fact(p,'FINALIZER_SQL_AND_CATALOG_OUTPUT')[5]
        for base,dirs,files in os.walk(root)for p in [Path(base),*(Path(base)/n for n in files)])
    result=dict(schema='PUBCHEM_UFF3_CANDIDATE_STORAGE_CLOSURE_V1',status='COMPLETE_CANDIDATE_DATASET_NOT_TRAINING_RELEASE',
        dataset_version='v2_candidate',population_version=manifest.get('population_version'),pubchem_version=manifest['pubchem_version'],
        source_manifest=plan['source_manifest'],source_population_receipt=manifest.get('source_pool_receipt'),
        generation_receipts=plan['generation_receipts'],generation_actual_accounting_references=plan['generation_actual_accounting_references'],
        actual_parent=actual,recipe_sha256=C.recipe_sha(),maximum_delivered_conformers=3,
        quality_reference_review=plan['quality_reference_review'],qa_report_reference=plan['qa_report_reference'],
        qa_actual_accounting_reference=plan['qa_actual_accounting_reference'],
        source_capsule_reference=plan['source_capsule_reference'],logical_census_and_saved_evidence=stats,
        full_source_bidirectional_identity_and_rank_closure=True,all_sparse_failed_unknown_sources_preserved=True,
        saved_D20_D3_and_coordinate_F64_bits_equal_delivered_families=True,three_saved_order_permutations_bound=True,
        molecule_saved_evidence_reference=Q.reference(catalog),catalogs=outputs,closed_batch_manifest_catalog=outputs['batches'],
        storage=footprint,finalizer_own_closed_sql_and_catalog_allocated_bytes=finalizer_blocks,
        shared_input_references=shared,shared_input_whole_DATA_SHA_repeated=False,
        append4_or_later_scientific_execution_started=False,training_eligible=False,new_QM_calls=0,
        no_new_D20_D3_UFF_embedding_or_TRAIN_fit_calls=True,
        finalizer_current_resource_receipt=guard.latest)
    return result