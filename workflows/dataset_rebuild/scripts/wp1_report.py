"""Join disjoint geometry outputs and report the complete original physical WP1 population."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
import duckdb

EXCLUDE=['X01','X02','X03','X04','X05','G01','G02','G03','C02','C03','I01']
BINARY=EXCLUDE+['S01','B01','T01']

def q(v):return "'"+str(v).replace("'","''")+"'"

def rows(con,sql):
    cur=con.execute(sql);names=[c[0] for c in cur.description]
    return [dict(zip(names,row)) for row in cur.fetchall()]

def save(path,value):
    pending=path.with_name(path.name+'.pending')
    pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    pending.replace(path)

def geometry_files(arguments):
    result=[]
    for value in arguments:
        path=Path(value).absolute()
        if path.is_file():
            if path.suffix!='.parquet':raise ValueError('Closed .parquet geometry required: '+str(path))
            result.append(path)
        elif path.is_dir():
            selected=sorted(path.rglob('geometry_annotations.parquet')) or sorted(path.rglob('*.parquet'))
            if not selected:raise ValueError('No closed geometry Parquet: '+str(path))
            result.extend(selected)
        else:raise FileNotFoundError(path)
    return sorted(set(result))

def population(con,condition='TRUE'):
    return rows(con,f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
      count(*) FILTER(WHERE geometry_evaluated) AS geometry_records,
      count(*) FILTER(WHERE retained) AS retained_records,
      count(DISTINCT molecule_id) FILTER(WHERE retained) AS retained_molecules,
      count(*) FILTER(WHERE retained_confirmed) AS retained_confirmed_records,
      count(*) FILTER(WHERE retained AND NOT retained_confirmed) AS unresolved_retained_candidate_records,
      count(DISTINCT molecule_id) FILTER(WHERE retained AND NOT retained_confirmed) AS unresolved_retained_candidate_molecules
      FROM quality WHERE {condition}''')[0]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',required=True)
    p.add_argument('--geometry',required=True,nargs='+',action='append',help='Multiple files/directories; option may be repeated.')
    p.add_argument('--output',required=True);p.add_argument('--threads',type=int,default=16)
    p.add_argument('--memory-gb',type=int,default=40);p.add_argument('--temp-gb',type=int,default=64)
    p.add_argument('--seed',type=int,default=20261010);a=p.parse_args()
    allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.threads<=allocated:
        raise RuntimeError('Requires >=16 allocated Slurm CPUs and effective DuckDB threads within allocation.')
    files=geometry_files([v for group in a.geometry for v in group])
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);quality=out/'quality_annotations_v1.parquet'
    pending=quality.with_suffix('.parquet.pending')
    if quality.exists() or pending.exists():raise RuntimeError('Quality output exists; use a fresh report directory.')
    tmp=out/'tmp';tmp.mkdir(exist_ok=True);con=duckdb.connect();started=time.monotonic()
    con.execute(f'SET threads={a.threads}');con.execute(f"SET memory_limit='{a.memory_gb}GB'")
    con.execute(f"SET max_temp_directory_size='{a.temp_gb}GB'");con.execute('SET temp_directory='+q(tmp))
    con.execute('SET preserve_insertion_order=false')
    try:
        con.execute('CREATE VIEW idx AS SELECT * FROM read_parquet('+q(a.index)+')')
        con.execute('CREATE VIEW geo AS SELECT * FROM read_parquet(['+','.join(q(f) for f in files)+'],union_by_name=true)')
        columns={r[0] for r in con.execute('DESCRIBE idx').fetchall()}
        geo_columns={r[0] for r in con.execute('DESCRIBE geo').fetchall()}
        index_required={'record_id','molecule_id','energy_raw','total_atoms','heavy_atoms','split','elements',
                        'member_train','member_full','member_routine','B01'}|set(EXCLUDE[:8])
        geo_required={'record_id','molecule_id','geometry_X01','X05','C02','C03','I01','T01','G01','G02','G03','B01',
                      'reidentified_smiles','reidentified_inchikey','reidentified_connectivity_key',
                      'connectivity_mismatch','stereo_only_key_mismatch','error','geometry_seconds'}
        if index_required-columns or geo_required-geo_columns:
            raise RuntimeError('Missing required columns: '+str({'index':sorted(index_required-columns),'geometry':sorted(geo_required-geo_columns)}))
        # Match the producer iterator exactly: known positive X codes skip a
        # record; unknown X fields still require an explicit geometry outcome.
        initial_x=' AND '.join('NOT coalesce('+c+',false)' for c in EXCLUDE[:5])
        con.execute('CREATE VIEW expected_geometry AS SELECT record_id,molecule_id FROM idx WHERE '+initial_x)
        con.execute('CREATE TEMP TABLE geo_keys AS SELECT record_id,count(*) AS n FROM geo GROUP BY record_id')
        validation={'index_records':con.execute('SELECT count(*) FROM idx').fetchone()[0],
          'required_post_X_records':con.execute('SELECT count(*) FROM expected_geometry').fetchone()[0],
          'geometry_records':con.execute('SELECT count(*) FROM geo').fetchone()[0],
          'duplicate_index_records':con.execute('SELECT count(*)-count(DISTINCT record_id) FROM idx').fetchone()[0],
          'null_geometry_record_ids':con.execute('SELECT count(*) FROM geo WHERE record_id IS NULL').fetchone()[0],
          'duplicate_geometry_keys':con.execute('SELECT count(*) FROM geo_keys WHERE n<>1').fetchone()[0],
          'duplicate_geometry_excess_rows':con.execute('SELECT coalesce(sum(n-1),0) FROM geo_keys WHERE n>1').fetchone()[0],
          'missing_required_geometry':con.execute('SELECT count(*) FROM expected_geometry e ANTI JOIN geo_keys g USING(record_id)').fetchone()[0],
          'extra_geometry_records':con.execute('SELECT count(*) FROM geo g ANTI JOIN expected_geometry e USING(record_id)').fetchone()[0],
          'geometry_molecule_id_mismatches':con.execute('''SELECT count(*) FROM geo g JOIN expected_geometry e USING(record_id)
              WHERE g.molecule_id IS DISTINCT FROM e.molecule_id''').fetchone()[0],
          'required_scope':'Every physical source record with no TRUE source-index X01-X05, including unknown X fields.',
          'geometry_files':[{'path':str(f),'bytes':f.stat().st_size} for f in files]}
        bad=any(validation[k] for k in ['duplicate_index_records','null_geometry_record_ids','duplicate_geometry_keys',
          'missing_required_geometry','extra_geometry_records','geometry_molecule_id_mismatches'])
        validation['status']='FAILED_EXACT_GEOMETRY_JOIN' if bad else 'EXACT_ONE_ROW_PER_REQUIRED_RECORD'
        if bad:
            validation['missing_examples']=rows(con,'SELECT e.* FROM expected_geometry e ANTI JOIN geo_keys g USING(record_id) ORDER BY record_id LIMIT 50')
            validation['extra_examples']=rows(con,'SELECT g.record_id,g.molecule_id FROM geo g ANTI JOIN expected_geometry e USING(record_id) ORDER BY record_id LIMIT 50')
            validation['duplicate_examples']=rows(con,'SELECT * FROM geo_keys WHERE n<>1 ORDER BY record_id LIMIT 50')
        save(out/'geometry_join_validation.json',validation)
        if bad:raise RuntimeError('Geometry must cover post-X records exactly once with no extras; see geometry_join_validation.json.')
        replace=[c for c in ['X01','X05','G01','G02','G03','B01','X01_geometry_checked','X_keep','pre_geometry_keep'] if c in columns]
        source_decisions=','.join('i.'+c+' AS source_'+c for c in ['X_keep','pre_geometry_keep'] if c in columns)
        if source_decisions:source_decisions+=','
        con.execute(f'''CREATE TABLE combined AS SELECT i.* EXCLUDE({','.join(replace)}),{source_decisions}
          CASE WHEN i.X01 IS TRUE OR g.geometry_X01 IS TRUE THEN TRUE ELSE coalesce(g.geometry_X01,i.X01) END AS X01,
          CASE WHEN i.X05 IS TRUE OR g.X05 IS TRUE THEN TRUE ELSE coalesce(g.X05,i.X05) END AS X05,
          coalesce(g.G01,i.G01) AS G01,coalesce(g.G02,i.G02) AS G02,coalesce(g.G03,i.G03) AS G03,
          coalesce(g.B01,i.B01) AS B01,g.geometry_X01 IS NOT NULL AS X01_geometry_checked,
          g.C02,g.C03,g.I01,g.T01,g.geometry_X01,g.record_id IS NOT NULL AS geometry_evaluated,
          g.reidentified_smiles,g.reidentified_inchikey,g.reidentified_connectivity_key,
          g.connectivity_mismatch,g.stereo_only_key_mismatch,g.error AS geometry_error,g.geometry_seconds
          FROM idx i LEFT JOIN geo g USING(record_id)''')
        final_x=' AND '.join('NOT coalesce('+c+',false)' for c in EXCLUDE[:5])
        no_positive=' AND '.join('NOT coalesce('+c+',false)' for c in EXCLUDE)
        known=' AND '.join(c+' IS NOT NULL' for c in EXCLUDE)
        con.execute('ALTER TABLE combined ADD COLUMN X_keep BOOLEAN');con.execute('UPDATE combined SET X_keep=('+final_x+')')
        con.execute('ALTER TABLE combined ADD COLUMN retained BOOLEAN')
        con.execute('UPDATE combined SET retained=geometry_evaluated AND ('+no_positive+')')
        con.execute('ALTER TABLE combined ADD COLUMN retained_confirmed BOOLEAN')
        con.execute('UPDATE combined SET retained_confirmed=retained AND ('+known+')')
        con.execute('''CREATE TABLE votes AS SELECT molecule_id,reidentified_inchikey,count(*) AS votes
          FROM combined WHERE X_keep AND reidentified_inchikey IS NOT NULL GROUP BY ALL''')
        con.execute('''CREATE TABLE vote_max AS SELECT molecule_id,max(votes) AS max_votes,sum(votes) AS total_votes,
          count(*) AS identified_graphs FROM votes GROUP BY molecule_id''')
        con.execute('''CREATE TABLE minima AS SELECT molecule_id,min(energy_raw) AS energy_min
          FROM combined WHERE X_keep AND energy_raw IS NOT NULL AND isfinite(energy_raw) GROUP BY molecule_id''')
        flags=','.join('CASE WHEN c.'+code+' IS TRUE THEN '+q(code)+' END' for code in EXCLUDE+['B01','T01'])
        unknown=','.join('CASE WHEN c.'+code+' IS NULL THEN '+q(code)+' END' for code in EXCLUDE)
        con.execute(f'''COPY (SELECT c.*,v.votes AS identity_votes,vm.max_votes,vm.total_votes,
          CASE WHEN v.votes IS NOT NULL THEN v.votes<vm.max_votes ELSE NULL END AS S01,
          c.energy_raw-m.energy_min AS S02_delta_energy_kcal_mol,
          list_filter([{flags},CASE WHEN v.votes<vm.max_votes THEN 'S01' END],x -> x IS NOT NULL) AS quality_codes,
          list_filter([{unknown}],x -> x IS NOT NULL) AS unassessed_exclusion_codes,
          CASE WHEN retained_confirmed THEN 'RETAINED_CONFIRMED' WHEN retained THEN 'UNRESOLVED_RETAIN_CANDIDATE'
               ELSE 'EXCLUDED' END AS screening_status
          FROM combined c LEFT JOIN votes v USING(molecule_id,reidentified_inchikey)
          LEFT JOIN vote_max vm USING(molecule_id) LEFT JOIN minima m USING(molecule_id))
          TO {q(pending)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)''')
        pending.replace(quality);con.execute('CREATE VIEW quality AS SELECT * FROM read_parquet('+q(quality)+')')
        physical=population(con)
        report={'status':'COMPLETE' if not physical['unresolved_retained_candidate_records'] else 'COMPLETE_WITH_ANNOTATIONS_TO_RESOLVE',
          'population':physical,'geometry_join':validation,
          'roles':{role:population(con,condition) for role,condition in [('train','member_train'),('full','member_full'),
              ('routine','member_routine'),('unassigned',"split='unassigned'")]},
          'membership_integrity':rows(con,'''SELECT count(*) FILTER(WHERE member_train AND member_full) AS train_full_overlap,
              count(*) FILTER(WHERE member_routine AND NOT member_full) AS routine_outside_full,
              count(*) FILTER(WHERE split='unassigned' AND (member_train OR member_full OR member_routine)) AS assigned_unassigned_rows FROM quality''')[0],
          'nonadditive_roles':'Global population is physical records once; routine is an additional FULL membership and is not added to FULL.',
          'seed':a.seed,'software':{'duckdb':duckdb.__version__},'job_id':os.environ['SLURM_JOB_ID'],
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'resources':{'threads':a.threads,'memory_limit_GB':a.memory_gb,'temporary_limit_GB':a.temp_gb},
          'I01':'Full InChIKey equality remains the exclusion rule, including stereo-only differences.',
          'T01':'Only stereochemistry explicitly specified by source SMILES is compared against geometry; annotation only.',
          'G03':'>=5 bonds and >25% outside covalent-radius ratio [0.75,1.3].',
          'H01':'abs(energy_raw)/total_atoms, observation only; no cutoff.',
          'S02':'Conformer energy minus molecular minimum among final-X survivors, before G/C/I exclusions; observation only.',
          'retention':'Only positive document exclusion codes remove records. Unknowns remain explicit unresolved candidates; retained_confirmed is separate and introduces no extra exclusion.',
          'codes':{},'overlap':{},'sequential':[]}
        report['unresolved_retained_candidates']=rows(con,'''SELECT split,source_family,shard_id,unassessed_exclusion_codes,
          count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE retained AND NOT retained_confirmed
          GROUP BY ALL ORDER BY split,shard_id''')
        report['unresolved_examples']=rows(con,'''SELECT record_id,molecule_id,sample_key,split,source_path,unassessed_exclusion_codes,
          geometry_error FROM quality WHERE retained AND NOT retained_confirmed ORDER BY record_id LIMIT 50''')
        report['stereo_identity']=rows(con,'''SELECT count(*) FILTER(WHERE I01 IS TRUE) AS fullkey_I01_records,
          count(*) FILTER(WHERE connectivity_mismatch IS TRUE) AS connectivity_mismatch_records,
          count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE) AS stereo_only_mismatch_records,
          count(*) FILTER(WHERE T01 IS TRUE) AS explicit_stereo_T01_records,
          count(*) FILTER(WHERE I01 IS TRUE AND T01 IS TRUE) AS I01_T01_overlap_records,
          count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE AND T01 IS TRUE) AS stereo_only_T01_overlap_records,
          count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE AND T01 IS NOT TRUE) AS stereo_only_without_explicit_T01_records,
          count(*) FILTER(WHERE T01 IS TRUE AND I01 IS NOT TRUE) AS T01_without_I01_records,
          count(*) FILTER(WHERE geometry_evaluated AND reidentified_inchikey IS NULL) AS missing_reidentified_identity_records FROM quality''')[0]
        report['stereo_identity_by_role']=rows(con,'''SELECT split,count(*) FILTER(WHERE I01 IS TRUE) AS I01_records,
          count(*) FILTER(WHERE connectivity_mismatch IS TRUE) AS connectivity_mismatch_records,
          count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE) AS stereo_only_mismatch_records,
          count(*) FILTER(WHERE T01 IS TRUE) AS T01_records,
          count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE AND T01 IS TRUE) AS stereo_only_T01_overlap_records
          FROM quality GROUP BY split ORDER BY split''')
        for code in BINARY:
            scope='TRUE' if code.startswith('X') else 'geometry_evaluated'
            report['codes'][code]=rows(con,f'''SELECT count(*) AS assessed_scope_records,count(*) FILTER(WHERE {code} IS TRUE) AS records,
              count(DISTINCT molecule_id) FILTER(WHERE {code} IS TRUE) AS molecules,count(*) FILTER(WHERE {code} IS NULL) AS unknown_records
              FROM quality WHERE {scope}''')[0]
            con.execute(f'''COPY (SELECT * FROM quality WHERE {code} IS TRUE ORDER BY sha256(record_id||'|{a.seed}'),record_id LIMIT 50)
              TO {q(out/(code+'_examples.parquet'))} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        for code,value in [('H01','H01_abs_energy_per_atom'),('S02','S02_delta_energy_kcal_mol')]:
            report['codes'][code]=rows(con,f'''SELECT count({value}) AS records,count(DISTINCT molecule_id) FILTER(WHERE {value} IS NOT NULL) AS molecules,
              count(*) FILTER(WHERE {value} IS NULL) AS unknown_records FROM quality WHERE X_keep''')[0]
            report['codes'][code]['count_kind']='Continuous observation among final-X survivors; no binary cutoff.'
            con.execute(f'''COPY (SELECT * FROM quality WHERE X_keep AND {value} IS NOT NULL ORDER BY {value} DESC,record_id LIMIT 50)
              TO {q(out/(code+'_examples.parquet'))} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        aggregate=','.join(f'count(*) FILTER(WHERE {c1} IS TRUE AND {c2} IS TRUE) AS "{c1}_{c2}"' for c1 in BINARY for c2 in BINARY)
        counts=rows(con,'SELECT '+aggregate+' FROM quality')[0]
        report['overlap']={c1:{c2:counts[c1+'_'+c2] for c2 in BINARY} for c1 in BINARY}
        keep=[]
        for code in EXCLUDE:
            keep.append('NOT coalesce('+code+',false)');known_so_far=' AND '.join(c+' IS NOT NULL' for c in EXCLUDE[:len(keep)])
            report['sequential'].append({'after':code,**rows(con,f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
              count(*) FILTER(WHERE NOT ({known_so_far})) AS unknown_code_candidates FROM quality WHERE {' AND '.join(keep)}''')[0]})
        report['H01_thresholds']={str(t):con.execute(f'SELECT count(*) FROM quality WHERE X_keep AND H01_abs_energy_per_atom>{t}').fetchone()[0] for t in [20,30,50,200]}
        report['retained_size']=rows(con,'SELECT heavy_atoms,count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE retained GROUP BY heavy_atoms ORDER BY heavy_atoms')
        report['size_quantiles']=rows(con,'''SELECT quantile_cont(total_atoms,[0,.25,.5,.75,.9,.99,1]) AS atom_quantiles,
          quantile_cont(heavy_atoms,[0,.25,.5,.75,.9,.99,1]) AS heavy_atom_quantiles FROM quality WHERE retained''')[0]
        report['S02_distribution']=rows(con,'''SELECT count(S02_delta_energy_kcal_mol) AS records,
          quantile_cont(S02_delta_energy_kcal_mol,[0,.5,.9,.99,.999,1]) AS quantiles FROM quality WHERE X_keep''')[0]
        report['element_distribution']=rows(con,'SELECT z,count(*) AS containing_records FROM quality,unnest(elements) AS u(z) WHERE retained GROUP BY z ORDER BY z')
        report['split_counts']=rows(con,'''SELECT split,count(*) AS records,count(DISTINCT molecule_id) AS molecules,count(*) FILTER(WHERE retained) AS retained_records,
          count(*) FILTER(WHERE retained_confirmed) AS confirmed_records,count(DISTINCT molecule_id) FILTER(WHERE retained) AS retained_molecules FROM quality GROUP BY split ORDER BY split''')
        report['molecules_crossing_membership_splits']=con.execute('SELECT count(*) FROM (SELECT molecule_id FROM quality GROUP BY molecule_id HAVING count(DISTINCT split)>1)').fetchone()[0]
        report['tied_identity_vote_molecules']=con.execute('''SELECT count(*) FROM (SELECT v.molecule_id FROM votes v JOIN vote_max m USING(molecule_id)
          WHERE v.votes=m.max_votes GROUP BY v.molecule_id HAVING count(*)>1)''').fetchone()[0]
        report['elapsed_seconds']=time.monotonic()-started;save(out/'screening_report.json',report)
        stereo=report['stereo_identity']
        text=['# WP1 筛选分析','',f"原始物理记录 {physical['records']:,}；分子 {physical['molecules']:,}。按正命中排除后剩余记录 {physical['retained_records']:,}；分子 {physical['retained_molecules']:,}。",'',
          f"几何严格覆盖 {validation['required_post_X_records']:,} 条整类筛选后的记录，无缺失、重复或多余行。仍需补齐未知代码的剩余候选 {physical['unresolved_retained_candidate_records']:,} 条。",'',
          '| 集合 | 原记录 | 剩余记录 | 剩余分子 |','| --- | ---: | ---: | ---: |']
        for role,value in report['roles'].items():text.append(f"| {role} | {value['records']:,} | {value['retained_records']:,} | {value['retained_molecules']:,} |")
        text+=['','routine 是 FULL 的附加成员关系，不相加；unassigned 保持未分配，不因旧 QA 原因自动删除。','',
          f"I01 完整键不一致 {stereo['fullkey_I01_records']:,} 条：连接层不一致 {stereo['connectivity_mismatch_records']:,}，仅立体层不一致 {stereo['stereo_only_mismatch_records']:,}。T01 与仅立体层差异重叠 {stereo['stereo_only_T01_overlap_records']:,} 条；完整 I01 删除规则保持。",'',
          'H01 与 S02 仅记录，不设删除阈值；原 LMDB 只读，没有创建或写入任何 LMDB。','','## 附录','',
          '各代码命中与未知数、重叠矩阵、顺序剩余数和分布见 screening_report.json；每项最多 50 条样例见同名 *_examples.parquet。','',
          '未知候选及来源单列在 unresolved_retained_candidates / unresolved_examples。retained_confirmed 区分明确通过与待补注释，未增加新的删除条件。']
        (out/'screening_report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
        print(json.dumps({'status':report['status'],**physical}),flush=True)
    finally:
        con.close()
        if tmp.exists() and not any(tmp.iterdir()):tmp.rmdir()

if __name__=='__main__':main()
