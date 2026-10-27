"""CPU-only global ordinary locator roster; no LMDB/packet/child body is opened."""
from __future__ import annotations
import json,pathlib
from . import contract as C,io as I


def run(plan,common,formal,hof,out,budget,job):
    import duckdb
    import pyarrow as pa
    declared=plan['data_references'];projection=C.meta(hof['projection_receipt_reference'])
    # Hash the finite 16+32 tables and original canonical/owner/catalog DATA.
    frames={}
    for ref in declared:
        with I.held(ref,declared,budget.check) as (_,_,frame):
            frames[ref['path']]=frame
            if ref==formal:
                review=C.meta(plan['ordinary_source_review_reference']);v=C.meta(review['canonical_node13_source_validation_reference'])
                prior=next(r for r in v['inputs'] if r['reference']==formal)
                C.need((frame[0],frame[1],frame[2],frame[3],frame[5])==
                    (prior['device'],prior['inode'],formal['bytes'],prior['mtime_ns'],prior['uid']),
                    'CURRENT_CANONICAL_NODE13_DEVICE_INODE_SIZE_TIME_UID_MATCH_REAL_PRIOR_CPU')
    source_files=I.json_body(projection['source_files'],declared,budget.check)
    C.need(type(source_files) is list,'ORIGINAL_CLOSED_HOF_FILE_CATALOG_LIST')
    for ref in source_files:C.reference(ref)
    db=duckdb.connect(str(out/'prepare.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='3GB'")
    scratch=out/'sql_tmp';scratch.mkdir(exist_ok=True);db.execute('SET temp_directory='+Dquote(scratch))
    paths=lambda refs:'['+','.join(Dquote(r['path']) for r in refs)+']'
    try:
        db.execute('CREATE TABLE members AS SELECT * FROM read_parquet('+paths(common['membership_tables'])+')')
        C.need(db.execute('SELECT count(*)=count(DISTINCT molecule_id) AND count(*)>0 FROM members').fetchone()[0], 'WHOLE_UNIQUE_FINAL_COMMON_ROSTER')
        db.execute('CREATE TABLE roster AS SELECT *,row_number() OVER(ORDER BY molecule_id)-1 AS logical_ordinal FROM members WHERE common_population')
        # The 32 source schemas differ. union_by_name retains each literal
        # source provenance column, without decoding arrays or renumbering IDs.
        db.execute('CREATE TABLE physical AS SELECT * FROM read_parquet('+paths(common['physical_geometry_tables'])+',union_by_name=true)')
        C.need(db.execute('SELECT count(*)=count(DISTINCT geometry_id) FROM physical').fetchone()[0], 'ALL32_DISTINCT_ORDINARY_PHYSICAL_IDS')
        db.execute('CREATE INDEX physical_mid ON physical(molecule_id)')
        columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')
        db.execute('CREATE TABLE native AS SELECT '+','.join('r.'+v for v in columns)+' FROM read_parquet('+Dquote(formal['path'])+') r JOIN roster USING(molecule_id)')
        db.execute('CREATE INDEX native_mid ON native(molecule_id)')
        db.execute('CREATE TABLE owners AS SELECT o.* FROM read_parquet('+Dquote(hof['latest_owner_reference']['path'])+") o JOIN roster USING(molecule_id) WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
        C.need(db.execute('SELECT count(*)=count(DISTINCT molecule_id) FROM owners').fetchone()[0],'NO_DUPLICATE_CURRENT_HOF_OWNER')
        db.execute('CREATE INDEX owners_mid ON owners(molecule_id)')
        n=db.execute('SELECT count(*) FROM roster').fetchone()[0];C.need(n>0,'NONEMPTY_TRUE_ORDINARY_COMMON')
        ranges=[];pages=[];parts=out/'ranges';parts.mkdir();step=plan['logical_partition_molecules']
        for lo in range(0,n,step):
            budget.check();hi=min(n,lo+step);descriptors=[];refs=[]
            mids=db.execute('SELECT molecule_id,logical_ordinal,S_conformers,effective_role,source_role FROM roster WHERE logical_ordinal>=? AND logical_ordinal<? ORDER BY logical_ordinal',[lo,hi]).fetchall()
            for mid,ordinal,expected,role,source_role in mids:
                records=db.execute('SELECT * FROM native WHERE molecule_id=? ORDER BY record_id',[mid]).fetch_arrow_table().to_pylist()
                physical=db.execute('SELECT * FROM physical WHERE molecule_id=? ORDER BY geometry_source,geometry_id',[mid]).fetch_arrow_table().to_pylist()
                pm=[r for r in physical if r['geometry_source']=='pm7'];uff=[r for r in physical if r['geometry_source']=='uff_sprime']
                C.need(len(records)==len(pm)==expected and len(uff)>=expected and {r['record_id'] for r in records}=={r['native_record_id'] for r in pm},'ALL_ORIGINAL_N_PHYSICAL_PM7_AND_ORDINARY_UFF_NO_N1_INFLATION')
                owner=db.execute('SELECT * FROM owners WHERE molecule_id=?',[mid]).fetch_arrow_table().to_pylist()
                C.need(len(owner)<=1,'UNIQUE_OR_MISSING_ACTUAL_HOF_OWNER')
                by={r['record_id']:r for r in records}
                for r in physical:
                    if r['geometry_source']=='pm7':
                        p=by[r['native_record_id']]
                        C.need(all(r[k]==p[k] for k in ('molecule_id','source_path','real_index','record_payload_sha256')),'CANONICAL_PM7_MAP_POINTER_AND_PAYLOAD_SHA')
                    else:
                        C.need(r['native_anchor_record_id'] in by,'UFF_ANCHOR_IS_ACTUAL_SAME_MOLECULE_NATIVE_RECORD')
                        refs.append(C.reference({'path':r['source_path'],'bytes':r['source_bytes'],'sha256':r['source_sha256']}))
                        if r.get('once_ledger_path') is not None:
                            refs.append(C.reference({'path':r['once_ledger_path'],'bytes':r['once_ledger_bytes'],'sha256':r['once_ledger_sha256']}))
                candidates=[r for r in source_files if owner and r['family']=='pm7_neutral' and r['source_job_id']==owner[0]['job_id']
                    and r['source_file_group'] in {p['file_group'] for p in records}]
                refs += [C.reference(r) for r in candidates]
                descriptors.append({'schema':'D5_INPUTS_WHOLE_MOLECULE_DESCRIPTOR_V1','molecule_id':mid,'logical_ordinal':ordinal,
                    'expected_PM7_N':expected,'effective_role':role,'source_role':source_role,'records':records,'ordinary_physical_rows':physical,
                    'canonical_HOF_owner':owner[0] if owner else None,'canonical_HOF_files':candidates,
                    'native_reader_authority':'actual closed canonical population and physical map; each pointer payload SHA; no whole LMDB SHA originally available',
                    'child_coordinates_or_input_hashes_invented':False})
            raw=b''.join((json.dumps(d,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode() for d in descriptors)
            descriptor=I.bytes_new(parts/('range_%08d.jsonl'%lo),raw,budget)
            manifest={'schema':'D5_INPUTS_ACTUAL_RANGE_LOCATORS_V1','job_id':str(job),'logical_range':[lo,hi],'molecules':hi-lo,
                'descriptor_reference':descriptor,'data_references':C.unique(refs),'packet_LMDB_or_child_bodies_opened':0}
            ranges.append(C.Q.write_new(parts/('range_%08d.locators.json'%lo),manifest))
            if len(ranges)==512:
                pages.append(C.Q.write_new(parts/('registry_page_%06d.json'%len(pages)),{'schema':'D5_INPUTS_RANGE_REGISTRY_PAGE_V1','job_id':str(job),'range_manifest_references':ranges}));ranges=[]
        if ranges:pages.append(C.Q.write_new(parts/('registry_page_%06d.json'%len(pages)),{'schema':'D5_INPUTS_RANGE_REGISTRY_PAGE_V1','job_id':str(job),'range_manifest_references':ranges}))
        for ref in declared:C.need(I.R.frame(pathlib.Path(ref['path']).lstat())==frames[ref['path']],'ALL_PREPARATION_SOURCE_FRAMES_STABLE_AFTER_SQL')
        return {'range_registry_page_references':pages,'logical_range':[0,n],'molecules':n,'held_molecules':0,
            'packet_LMDB_or_child_bodies_opened':0,'whole_source_catalogue_and_maps_SHA_verified':True,'table_domain':'LOCATORS_ONLY'}
    finally:db.close()


def Dquote(value):return "'"+str(value).replace("'","''")+"'"
