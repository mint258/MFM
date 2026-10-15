"""A1--A4 core: immutable old quality -> relaxed I01 analysis, no LMDB/QM."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone

OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
PLAN=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/plan.json')
CODES=['X01','X02','X03','X04','X05','G01','G02','G03','C02','C03','I01']
BINS="CASE WHEN heavy_atoms<=10 THEN '0_10' WHEN heavy_atoms<=20 THEN '11_20' WHEN heavy_atoms<=30 THEN '21_30' WHEN heavy_atoms<=50 THEN '31_50' WHEN heavy_atoms<=75 THEN '51_75' WHEN heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END"
FIVE="CASE WHEN max_heavy_atoms<=20 THEN '01_le20' WHEN max_heavy_atoms<=25 THEN '02_21_25' WHEN max_heavy_atoms<=30 THEN '03_26_30' WHEN max_heavy_atoms<=40 THEN '04_31_40' ELSE '05_gt40' END"
KEY_VALID="regexp_full_match({x}, '[A-Z]{{14}}-[A-Z]{{10}}-[A-Z]')"

def q(x): return "'"+str(x).replace("'","''")+"'"
def rows(db,sql):
    cur=db.execute(sql); names=[x[0] for x in cur.description]
    return [dict(zip(names,r)) for r in cur.fetchall()]
def save(path,obj):
    path=Path(path); pending=path.with_name(path.name+'.pending')
    pending.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    pending.replace(path)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def ref(path,hash_file=False):
    path=Path(path); st=path.stat()
    r={'path':str(path.absolute()),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}
    if hash_file:r['sha256']=sha(path)
    return r
def copy(db,sql,path):
    path=Path(path); pending=path.with_name(path.name+'.pending')
    db.execute(f'COPY ({sql}) TO {q(pending)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)')
    pending.replace(path)
def progress(stage,**kw): print(json.dumps({'stage':stage,**kw}),flush=True)
def limits(args):
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text()); print('A_RETAINED_CORE_SYNTAX_PASS'); return False
    n=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=n: raise RuntimeError('Slurm >=16 effective workers required')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
    return True
def overlap(db,mode):
    masks='+'.join(f'(CASE WHEN {"I01_strict" if c=="I01" and mode=="strict" else c} IS TRUE THEN {1<<i} ELSE 0 END)' for i,c in enumerate(CODES))
    counts=rows(db,f'SELECT ({masks}) AS mask,count(*) AS records FROM quality GROUP BY mask ORDER BY records DESC')
    exact=[{'mask':r['mask'],'codes':[c for i,c in enumerate(CODES) if r['mask']&(1<<i)],'records':r['records']} for r in counts]
    matrix=[{'left':a,'right':b,'records':sum(r['records'] for r in counts if r['mask']&(1<<i) and r['mask']&(1<<j))} for i,a in enumerate(CODES) for j,b in enumerate(CODES)]
    filters=[]; funnel=[]
    for c in CODES:
        field='I01_strict' if mode=='strict' and c=='I01' else c
        filters.append(f'{field} IS NOT TRUE'); where=' AND '.join(filters)
        value=rows(db,f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
          count(*) FILTER(WHERE {field} IS NULL) AS current_code_unknown FROM quality WHERE {where}''')[0]
        funnel.append({'after':c,**value})
    return {'upset_exact_intersections':exact,'overlap_matrix':matrix,'sequential_funnel':funnel,
      'unknown_policy':'Only positive exclusion hits remove. Earlier-X removals do not imply subsequent G/C/I were assessed.'}
def population(db,mode):
    keep='strict_retained' if mode=='strict' else 'retained'
    counts=rows(db,f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
      count(*) FILTER(WHERE split='unassigned') AS unassigned_records,
      count(DISTINCT molecule_id) FILTER(WHERE split='unassigned') AS unassigned_molecules FROM quality WHERE {keep}''')[0]
    strata=rows(db,f'''SELECT {BINS} AS size_stratum,count(*) AS records,count(DISTINCT molecule_id) AS molecules
      FROM quality WHERE {keep} GROUP BY size_stratum ORDER BY min(heavy_atoms)''')
    files=rows(db,f'''SELECT file_bin,count(*) AS records,count(DISTINCT molecule_id) AS molecules,
      min(heavy_atoms) AS min_heavy_atoms,max(heavy_atoms) AS max_heavy_atoms,
      sum(total_atoms) AS atoms FROM quality WHERE {keep} GROUP BY file_bin ORDER BY file_bin''')
    return {**counts,'strata':strata,'five_analysis_files':files,'file_boundaries':[20,25,30,40],
      'file_policy':'Analysis baseline only; max physical-record heavy atom count per molecule; whole molecules remain together. No LMDB created.'}
def rates(db,mode):
    keep='strict_retained' if mode=='strict' else 'retained'
    bysize=rows(db,f'''SELECT {BINS} AS size_stratum,count(*) AS original_records,
      count(*) FILTER(WHERE {keep}) AS retained_records,count(DISTINCT molecule_id) AS original_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE {keep}) AS retained_molecules,
      count(*) FILTER(WHERE {keep})::DOUBLE/count(*) AS record_retention_rate FROM quality GROUP BY size_stratum ORDER BY min(heavy_atoms)''')
    elements=rows(db,f'''SELECT z,count(*) AS original_records,count(*) FILTER(WHERE {keep}) AS retained_records,
      count(DISTINCT molecule_id) AS original_molecules,count(DISTINCT molecule_id) FILTER(WHERE {keep}) AS retained_molecules,
      count(*) FILTER(WHERE {keep})::DOUBLE/count(*) AS record_retention_rate
      FROM quality,unnest(list_distinct(elements)) AS u(z) GROUP BY z ORDER BY z''')
    joint=rows(db,f'''SELECT z,{BINS} AS size_stratum,count(*) AS original_records,
      count(*) FILTER(WHERE {keep}) AS retained_records,
      count(*) FILTER(WHERE {keep})::DOUBLE/count(*) AS record_retention_rate
      FROM quality,unnest(list_distinct(elements)) AS u(z) GROUP BY z,size_stratum ORDER BY z,min(heavy_atoms)''')
    return {'by_heavy_atoms':bysize,'by_element':elements,'by_element_and_heavy_atoms':joint,
      'element_denominator':'Containing-record counts, one vote per element per physical record; element groups overlap.'}
def annotations(db,mode):
    keep='strict_retained' if mode=='strict' else 'retained'; out={}
    mapping={'H01':'H01_abs_energy_per_atom','S02':'S02_delta_energy_kcal_mol',
      'B01_bond_outlier_fraction':'bond_length_outlier_fraction','S01_vote_fraction':'identity_vote_fraction'}
    for name,col in mapping.items():
        out[name]=rows(db,f'''SELECT count(*) AS population_records,
          count(*) FILTER(WHERE {col} IS NOT NULL AND isfinite({col})) AS observed_records,
          count(*) FILTER(WHERE {col} IS NULL OR NOT isfinite({col})) AS unknown_records,
          quantile_cont({col},[0,.01,.25,.5,.75,.9,.95,.99,.999,1]) FILTER(WHERE isfinite({col})) AS quantiles
          FROM quality WHERE {keep}''')[0]
    for code in ('S01','S01_backbone','B01','T01','T01_original'):
        out[code]=rows(db,f'''SELECT count(*) AS population_records,count(*) FILTER(WHERE {code} IS TRUE) AS positive_records,
          count(*) FILTER(WHERE {code} IS FALSE) AS negative_records,count(*) FILTER(WHERE {code} IS NULL) AS unknown_records,
          quantile_cont(CASE WHEN {code} IS NOT NULL THEN CAST({code} AS INTEGER) END,[0,.5,.9,.99,1]) AS binary_quantiles
          FROM quality WHERE {keep}''')[0]
    out['thresholds_applied']=False
    out['S01_scope']='Original full-key minority vote preserved as S01; backbone-plus-proton vote separately annotated S01_backbone. Neither excludes.'
    return out
def leakage(db,out,mode):
    keep='strict_retained' if mode=='strict' else 'retained'; results=[]
    for origin,field in [('stored','stored_inchikey'),('reidentified','reidentified_inchikey')]:
        for kind,expr in [('full',field),('connectivity14',f'substr({field},1,14)'),('connectivity14_proton',f'substr({field},1,14)||right({field},1)')]:
            progress('split_key_audit',mode=mode,origin=origin,key=kind)
            db.execute(f'''CREATE OR REPLACE TEMP TABLE key_groups AS SELECT {expr} AS identity_key,
              bool_or(member_train) AS has_train,bool_or(member_full) AS has_full,bool_or(member_routine) AS has_routine,
              bool_or(split='unassigned') AS has_unassigned,count(*) AS records,count(DISTINCT molecule_id) AS molecules,
              count(*) FILTER(WHERE member_train) AS train_records,count(*) FILTER(WHERE member_full) AS full_records,
              count(*) FILTER(WHERE member_routine) AS routine_records,count(*) FILTER(WHERE split='unassigned') AS unassigned_records
              FROM quality WHERE {keep} AND {KEY_VALID.format(x=field)} GROUP BY identity_key''')
            stat=rows(db,'''SELECT count(*) AS unique_keys,
              count(*) FILTER(WHERE has_train AND has_full) AS train_full_shared_keys,
              count(*) FILTER(WHERE has_train AND has_routine) AS train_routine_shared_keys,
              count(*) FILTER(WHERE has_full AND has_routine) AS full_routine_design_inclusion_keys,
              count(*) FILTER(WHERE has_unassigned AND has_train) AS unassigned_train_shared_keys,
              count(*) FILTER(WHERE has_unassigned AND has_full) AS unassigned_full_shared_keys,
              sum(train_records) FILTER(WHERE has_train AND has_full) AS affected_train_records,
              sum(full_records) FILTER(WHERE has_train AND has_full) AS affected_full_records FROM key_groups''')[0]
            stat.update(origin=origin,key_kind=kind,mode=mode)
            stat['missing_identity_records']=db.execute(f'SELECT count(*) FROM quality WHERE {keep} AND NOT coalesce({KEY_VALID.format(x=field)},false)').fetchone()[0]
            path=out/f'leakage_{mode}_{origin}_{kind}_shared_keys.parquet'
            copy(db,"SELECT * FROM key_groups WHERE (has_train AND has_full) OR (has_unassigned AND (has_train OR has_full))",path)
            stat['shared_key_details']=ref(path)
            stat['examples']=rows(db,'SELECT * FROM key_groups WHERE has_train AND has_full ORDER BY identity_key LIMIT 50')
            results.append(stat)
    return results

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quality',default=str(OLD/'wp1_results/quality_annotations_v1.parquet'))
    p.add_argument('--index',default=str(OLD/'record_index.parquet'))
    p.add_argument('--strict-report',default=str(OLD/'wp1_results/screening_report.json'))
    p.add_argument('--source-plan',default=str(PLAN));p.add_argument('--output',default=str(ROOT/'a_retained'))
    p.add_argument('--workers',type=int,default=32);p.add_argument('--memory-gb',type=int,default=96)
    p.add_argument('--check',action='store_true');a=p.parse_args()
    if not limits(a):return 0
    try:import duckdb
    except ModuleNotFoundError:sys.path.insert(0,str(DEPS));import duckdb
    start=time.monotonic();out=Path(a.output).absolute()
    if not out.is_relative_to(ROOT):raise RuntimeError('New outputs must stay in this screening root')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():raise RuntimeError('Closed output exists; choose a fresh directory/version')
    strict_report=json.loads(Path(a.strict_report).read_text());plan=json.loads(Path(a.source_plan).read_text())
    db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute(f"SET memory_limit='{a.memory_gb}GB'")
    temp=out/('duckdb_tmp_'+os.environ['SLURM_JOB_ID']);temp.mkdir(exist_ok=True)
    db.execute('SET temp_directory='+q(temp));db.execute("SET max_temp_directory_size='80GB'")
    db.execute('CREATE VIEW old AS SELECT * FROM read_parquet('+q(a.quality)+')')
    db.execute('CREATE VIEW idx AS SELECT record_id,molecule_id FROM read_parquet('+q(a.index)+')')
    progress('validate_physical_manifest')
    physical=rows(db,'''SELECT count(*) AS records,count(DISTINCT record_id) AS unique_record_ids,
      count(DISTINCT molecule_id) AS molecules,count(*) FILTER(WHERE geometry_evaluated) AS geometry_records,
      count(*) FILTER(WHERE retained) AS strict_records,count(DISTINCT molecule_id) FILTER(WHERE retained) AS strict_molecules,
      count(*) FILTER(WHERE split='unassigned') AS unassigned_records,
      count(*) FILTER(WHERE retained AND split='unassigned') AS strict_unassigned_records FROM old''')[0]
    authoritative=strict_report['population']
    expected={'records':authoritative['records'],'molecules':authoritative['molecules'],
      'geometry_records':strict_report['geometry_join']['required_post_X_records'],
      'strict_records':authoritative['retained_records'],'strict_molecules':authoritative['retained_molecules'],
      'unassigned_records':strict_report['roles']['unassigned']['records'],
      'strict_unassigned_records':strict_report['roles']['unassigned']['retained_records']}
    mismatches={k:{'observed':physical[k],'expected':v} for k,v in expected.items() if physical[k]!=v}
    if physical['unique_record_ids']!=physical['records']:mismatches['duplicate_record_ids']=physical
    pointers=rows(db,'''SELECT count(*) AS rows,count(DISTINCT record_id) AS ids FROM idx''')[0]
    if pointers['rows']!=physical['records'] or pointers['ids']!=physical['records']:mismatches['index_counts']=pointers
    identity_diff=db.execute('''SELECT count(*) FROM old o FULL OUTER JOIN idx i USING(record_id)
      WHERE o.record_id IS NULL OR i.record_id IS NULL OR o.molecule_id IS DISTINCT FROM i.molecule_id''').fetchone()[0]
    if identity_diff:mismatches['index_quality_identity_difference']=identity_diff
    save(out/'input_count_validation.json',{'physical':physical,'expected':expected,'mismatches':mismatches})
    if mismatches:raise RuntimeError('PHYSICAL_MANIFEST_COUNT_MISMATCH:'+json.dumps(mismatches))
    valid_s=KEY_VALID.format(x='stored_inchikey');valid_g=KEY_VALID.format(x='reidentified_inchikey')
    db.execute(f'''CREATE VIEW identity AS SELECT *,
      CASE WHEN {valid_s} THEN substr(stored_inchikey,1,14)||right(stored_inchikey,1) END AS stored_backbone_proton_key,
      CASE WHEN {valid_g} THEN substr(reidentified_inchikey,1,14)||right(reidentified_inchikey,1) END AS reidentified_backbone_proton_key
      FROM old''')
    db.execute('''CREATE VIEW changed AS SELECT * EXCLUDE(I01,T01,retained,retained_confirmed,quality_codes,unassessed_exclusion_codes,screening_status),
      I01 AS I01_strict,T01 AS T01_original,retained AS strict_retained,retained_confirmed AS strict_retained_confirmed,
      CASE WHEN stored_backbone_proton_key IS NOT NULL AND reidentified_backbone_proton_key IS NOT NULL
        THEN stored_backbone_proton_key<>reidentified_backbone_proton_key ELSE NULL END AS I01,
      CASE WHEN stored_backbone_proton_key IS NOT NULL AND reidentified_backbone_proton_key IS NOT NULL
        THEN stored_inchikey<>reidentified_inchikey AND stored_backbone_proton_key=reidentified_backbone_proton_key ELSE NULL END AS I01_relaxed_to_T01,
      CASE WHEN stored_inchikey IS NOT NULL AND reidentified_inchikey IS NOT NULL THEN right(stored_inchikey,1)<>right(reidentified_inchikey,1) ELSE NULL END AS protonation_mismatch,
      identity_votes::DOUBLE/nullif(total_votes,0) AS identity_vote_fraction FROM identity''')
    db.execute('''CREATE TEMP TABLE molecule_shape AS SELECT molecule_id,max(heavy_atoms) AS max_heavy_atoms FROM old GROUP BY molecule_id''')
    db.execute(f'ALTER TABLE molecule_shape ADD COLUMN file_bin VARCHAR');db.execute(f'UPDATE molecule_shape SET file_bin={FIVE}')
    db.execute('''CREATE TEMP TABLE backbone_votes AS SELECT molecule_id,reidentified_backbone_proton_key,count(*) AS votes
      FROM changed WHERE X_keep AND reidentified_backbone_proton_key IS NOT NULL GROUP BY ALL''')
    db.execute('''CREATE TEMP TABLE backbone_max AS SELECT molecule_id,max(votes) AS max_votes,sum(votes) AS total_votes
      FROM backbone_votes GROUP BY molecule_id''')
    keep='geometry_evaluated AND '+' AND '.join(c+' IS NOT TRUE' for c in CODES)
    known=' AND '.join(c+' IS NOT NULL' for c in CODES)
    flags=','.join('CASE WHEN '+c+' IS TRUE THEN '+q(c)+' END' for c in CODES+['B01','T01'])
    unknown=','.join('CASE WHEN '+c+' IS NULL THEN '+q(c)+' END' for c in CODES)
    db.execute(f'''CREATE VIEW final_base AS SELECT c.*,m.file_bin,
      CASE WHEN c.T01_original IS TRUE OR c.I01_relaxed_to_T01 IS TRUE THEN TRUE
        WHEN c.T01_original IS NOT NULL AND c.I01_relaxed_to_T01 IS NOT NULL THEN FALSE ELSE NULL END AS T01,
      ({keep}) AS retained,({keep}) AND ({known}) AS retained_confirmed,
      CASE WHEN v.votes IS NOT NULL THEN v.votes<vm.max_votes ELSE NULL END AS S01_backbone,
      v.votes AS backbone_identity_votes,vm.max_votes AS backbone_max_votes,vm.total_votes AS backbone_total_votes
      FROM changed c JOIN molecule_shape m USING(molecule_id)
      LEFT JOIN backbone_votes v USING(molecule_id,reidentified_backbone_proton_key)
      LEFT JOIN backbone_max vm USING(molecule_id)''')
    pending=out/'relaxed_quality_annotations.parquet';progress('write_relaxed_quality')
    copy(db,f'''SELECT *,list_filter([{flags},CASE WHEN S01 IS TRUE THEN 'S01' END],x->x IS NOT NULL) AS quality_codes,
      list_filter([{unknown}],x->x IS NOT NULL) AS unassessed_exclusion_codes,
      CASE WHEN retained_confirmed THEN 'RETAINED_CONFIRMED' WHEN retained THEN 'UNRESOLVED_RETAIN_CANDIDATE' ELSE 'EXCLUDED' END AS screening_status
      FROM final_base''',pending)
    db.execute('CREATE VIEW quality AS SELECT * FROM read_parquet('+q(pending)+')')
    strict=population(db,'strict');relaxed=population(db,'relaxed')
    unresolved=db.execute('SELECT count(*) FROM quality WHERE retained AND NOT retained_confirmed').fetchone()[0]
    baseline_difference=db.execute('''SELECT count(*) FROM quality WHERE strict_retained IS DISTINCT FROM
      (geometry_evaluated AND X01 IS NOT TRUE AND X02 IS NOT TRUE AND X03 IS NOT TRUE AND X04 IS NOT TRUE AND X05 IS NOT TRUE
      AND G01 IS NOT TRUE AND G02 IS NOT TRUE AND G03 IS NOT TRUE AND C02 IS NOT TRUE AND C03 IS NOT TRUE AND I01_strict IS NOT TRUE)''').fetchone()[0]
    if baseline_difference:raise RuntimeError('PHYSICAL_MANIFEST_STRICT_RETENTION_CLOSURE_MISMATCH')
    if db.execute('SELECT count(*) FROM quality WHERE strict_retained AND NOT retained').fetchone()[0]:raise RuntimeError('PHYSICAL_MANIFEST_RELAXED_NOT_SUPERSET')
    role_integrity=rows(db,'''SELECT count(*) FILTER(WHERE member_train AND member_full) AS train_full_physical_overlap,
      count(*) FILTER(WHERE member_routine AND NOT member_full) AS routine_outside_full,
      count(*) FILTER(WHERE split='unassigned' AND (member_train OR member_full OR member_routine)) AS assigned_unassigned FROM quality''')[0]
    pop={'strict':strict,'relaxed':relaxed,'all_physical_records':physical['records'],'geometry_records':physical['geometry_records'],
      'unresolved_relaxed_retained_records':unresolved,'roles':{},'file_baseline':[20,25,30,40]}
    for role,condition in [('train','member_train'),('full','member_full'),('routine','member_routine'),('unassigned',"split='unassigned'")]:
        pop['roles'][role]=rows(db,f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
          count(*) FILTER(WHERE strict_retained) AS strict_records,count(DISTINCT molecule_id) FILTER(WHERE strict_retained) AS strict_molecules,
          count(*) FILTER(WHERE retained) AS relaxed_records,count(DISTINCT molecule_id) FILTER(WHERE retained) AS relaxed_molecules
          FROM quality WHERE {condition}''')[0]
    save(out/'population_by_stratum.json',pop)
    save(out/'manifest.json',{'status':'CORE_COMPLETE_WITH_UNKNOWN_ANNOTATIONS' if unresolved else 'CORE_COMPLETE',
      'created_UTC':datetime.now(timezone.utc).isoformat(),'job_id':os.environ['SLURM_JOB_ID'],'threads':a.workers,
      'source_quality':ref(a.quality),'source_index':ref(a.index),'source_strict_report':ref(a.strict_report,True),
      'script':ref(__file__,True),'output_quality':ref(pending),'physical':physical,'strict':strict,'relaxed':relaxed,
      'geometry_recomputed':False,'LMDB_opened_or_written':False,'unresolved_relaxed_retained_records':unresolved,
      'role_integrity':role_integrity,'I01_rule':'14-character connectivity block plus final protonation character equality; other identity layers annotate only.',
      'T01_rule':'Original specified-stereo T01 OR former full-key mismatch accepted by relaxed I01; detailed stereo/other layers in follow-up.'})
    progress('core_ready_for_downstream',strict=strict['records'],relaxed=relaxed['records'])
    a1=rows(db,'''SELECT count(*) FILTER(WHERE I01_strict) AS strict_I01_records,
      count(*) FILTER(WHERE connectivity_mismatch) AS true_connectivity_records,
      count(*) FILTER(WHERE stereo_only_key_mismatch) AS old_same_connectivity14_fullkey_mismatch_records,
      count(*) FILTER(WHERE protonation_mismatch) AS protonation_mismatch_records,
      count(*) FILTER(WHERE I01_relaxed_to_T01) AS accepted_fullkey_difference_records,
      count(*) FILTER(WHERE retained AND NOT strict_retained) AS newly_retained_records,
      count(DISTINCT molecule_id) FILTER(WHERE retained AND NOT strict_retained) AS newly_retained_molecules FROM quality''')[0]
    copy(db,'''SELECT record_id,molecule_id,smiles,reidentified_smiles,stored_inchikey,reidentified_inchikey,
      heavy_atoms,elements,protonation_mismatch,retained,strict_retained,quality_codes FROM quality
      WHERE I01 IS TRUE ORDER BY sha256(record_id) LIMIT 50''',out/'A1_remaining_I01_examples50.parquet')
    a1['remaining_I01_by_size']=rows(db,f'SELECT {BINS} AS size_stratum,count(*) AS records FROM quality WHERE I01 IS TRUE GROUP BY size_stratum ORDER BY min(heavy_atoms)')
    a1['remaining_I01_by_element']=rows(db,'SELECT z,count(*) AS records FROM quality,unnest(list_distinct(elements)) u(z) WHERE I01 IS TRUE GROUP BY z ORDER BY z')
    a1['stereo_only_details_status']='AWAIT_A_RETAINED_STEREO_SCRIPT'
    save(out/'A1_core.json',a1)
    a2={}
    for mode in ('strict','relaxed'):
        progress('funnel_overlap_rates',mode=mode);a2[mode]={**overlap(db,mode),'retention_rates':rates(db,mode)}
        final=a2[mode]['sequential_funnel'][-1]['records']
        if final!=pop[mode]['records']:raise RuntimeError('PHYSICAL_MANIFEST_FUNNEL_RETENTION_MISMATCH:'+mode)
    save(out/'A2_funnel_overlap_retention.json',a2)
    progress('unassigned_origin')
    a3={'authority':{role:plan['manifests'][role]['view'] for role in ('train','full','routine')},
      'semantic_mapping':{'train':'train','full':'validation_full','routine':'validation_monitor_subset','test':'NO_TEST_AUTHORITY_PRESENT'},
      'authority_code_evidence':{'path':str(PLAN.parent/'source_snapshot/scripts/train_phase1_full_corpus.py'),'lines':[320,342]},
      'routine_full_policy':'Monitor subset inclusion is intentional, not train/test leakage. No roles are reassigned.',
      'unassigned_origins':rows(db,'''SELECT source_family,shard_id,shard_name,legacy_QA_status,count(*) AS original_records,
        count(*) FILTER(WHERE strict_retained) AS strict_retained_records,count(*) FILTER(WHERE retained) AS relaxed_retained_records,
        count(*) FILTER(WHERE retained AND NOT strict_retained) AS relaxed_new_records,count(DISTINCT molecule_id) AS molecules
        FROM quality WHERE split='unassigned' GROUP BY ALL ORDER BY shard_id,legacy_QA_status'''),
      'unassigned_original_manifest_exclusion':'8259 excluded under old QA embargo/quarantine before TRAIN/FULL native views, not under this round relaxed screening.',
      'old_QA_history_evidence':ref(OLD/'unassigned_v2/unassigned_inventory.json',True),
      'key_leakage':[]}
    copy(db,'''SELECT record_id,sample_key,molecule_id,conformer_id,source_path,shard_id,real_index,record_payload_sha256,
      stored_inchikey,reidentified_inchikey,legacy_QA_status,legacy_QA_status_code,legacy_QA_error_metadata_json,
      legacy_QA_classification_path,legacy_QA_classification_offset,strict_retained,retained,quality_codes
      FROM quality WHERE split='unassigned' ORDER BY shard_id,real_index''',out/'A3_unassigned_trace.parquet')
    for mode in ('strict','relaxed'):a3['key_leakage']+=leakage(db,out,mode)
    save(out/'A3_split_unassigned.json',a3)
    save(out/'A4_annotations.json',{mode:annotations(db,mode) for mode in ('strict','relaxed')})
    # Only cached generated SMILES are examined later; no source LMDB or coordinates reread.
    progress('export_stereo_pair_cache')
    db.execute('''CREATE TEMP TABLE stereo_affected_molecules AS SELECT DISTINCT molecule_id FROM quality WHERE stereo_only_key_mismatch IS TRUE''')
    copy(db,'''SELECT DISTINCT sha256(coalesce(smiles,'')||chr(30)||coalesce(reidentified_smiles,'')) AS pair_id,
      smiles AS source_smiles,reidentified_smiles FROM quality JOIN stereo_affected_molecules USING(molecule_id)
      WHERE reidentified_smiles IS NOT NULL AND smiles IS NOT NULL''',out/'stereo_pairs_input.parquet')
    db.close()
    save(out/'core_complete.json',{'status':'A_CORE_COMPLETE','seconds':time.monotonic()-start,
      'stereo_pair_input':ref(out/'stereo_pairs_input.parquet'),'pending':['Detailed chirality/EZ/other layer and within-molecule consistency summary'],
      'computed_QM':False,'new_geometry_determination':False})
    progress('done',seconds=time.monotonic()-start)
    return 0
if __name__=='__main__':raise SystemExit(main())
