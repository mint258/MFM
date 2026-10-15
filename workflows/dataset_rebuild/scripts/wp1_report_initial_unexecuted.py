"""Join independent record annotations and produce the WP1 analysis deliverables."""
import argparse, hashlib, json, os, time
from pathlib import Path
import duckdb

EXCLUDE=['X01','X02','X03','X04','X05','G01','G02','G03','C02','C03','I01']
OBSERVE=['H01','S01','S02','B01','T01']

def q(value):return "'"+str(value).replace("'","''")+"'"
def rows(con,sql):
    cur=con.execute(sql);cols=[c[0] for c in cur.description]
    return [dict(zip(cols,row)) for row in cur.fetchall()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--index',required=True)
    p.add_argument('--geometry',required=True);p.add_argument('--output',required=True)
    p.add_argument('--threads',type=int,default=16);args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(str(out/'quality_work.duckdb'))
    con.execute(f'SET threads={args.threads}');con.execute("SET memory_limit='40GB'")
    con.execute(f'SET temp_directory={q(out/"tmp")}')
    con.execute(f'CREATE OR REPLACE VIEW idx AS SELECT * FROM read_parquet({q(args.index)})')
    con.execute(f'CREATE OR REPLACE VIEW geo AS SELECT * FROM read_parquet({q(args.geometry)})')
    columns={r[0] for r in con.execute('DESCRIBE idx').fetchall()}
    con.execute(f'''CREATE OR REPLACE TABLE combined AS
      SELECT i.* EXCLUDE (G01,G02,G03,B01),
        coalesce(g.G01,i.G01,false) AS G01,coalesce(g.G02,i.G02,false) AS G02,
        coalesce(g.G03,i.G03,false) AS G03,coalesce(g.B01,i.B01,false) AS B01,
        g.C02,g.C03,g.I01,g.T01,g.geometry_X01,
        g.record_id IS NOT NULL AS geometry_evaluated,
        g.reidentified_smiles,g.reidentified_inchikey,g.reidentified_connectivity_key,
        g.connectivity_mismatch,g.stereo_only_key_mismatch,g.error AS geometry_error,
        g.geometry_seconds
      FROM idx i LEFT JOIN geo g USING(record_id)''')
    con.execute('UPDATE combined SET X01=true WHERE geometry_X01')
    duplicate=con.execute('SELECT count(*)-count(DISTINCT record_id) FROM combined').fetchone()[0]
    if duplicate:raise RuntimeError(f'Duplicate geometry/index records: {duplicate}')
    # Missing annotation is unknown, not a pass, for a record surviving X filters.
    con.execute('ALTER TABLE combined ADD COLUMN retained BOOLEAN')
    cond=' AND '.join('NOT coalesce('+x+',false)' for x in EXCLUDE)
    con.execute(f'UPDATE combined SET retained=geometry_evaluated AND ({cond})')
    con.execute('''CREATE OR REPLACE TABLE votes AS
      SELECT molecule_id,reidentified_inchikey,count(*) AS votes
      FROM combined WHERE reidentified_inchikey IS NOT NULL
      GROUP BY molecule_id,reidentified_inchikey''')
    con.execute('''CREATE OR REPLACE TABLE vote_max AS
      SELECT molecule_id,max(votes) AS max_votes,sum(votes) AS total_votes FROM votes GROUP BY molecule_id''')
    energy='energy_raw' if 'energy_raw' in columns else 'energy'
    xcond=' AND '.join('NOT coalesce('+x+',false)' for x in EXCLUDE[:5])
    con.execute(f'''CREATE OR REPLACE TABLE minima AS
      SELECT molecule_id,min({energy}) AS energy_min FROM combined WHERE {xcond} GROUP BY molecule_id''')
    quality=out/'quality_annotations_v1.parquet'
    con.execute(f'''COPY (SELECT c.*,v.votes AS identity_votes,vm.max_votes,
      coalesce(v.votes < vm.max_votes,false) AS S01,
      c.{energy}-m.energy_min AS S02_delta_energy_kcal_mol,
      list_filter([{','.join('CASE WHEN coalesce(c.'+code+',false) THEN '+q(code)+' END' for code in EXCLUDE+['B01','T01'])},
         CASE WHEN v.votes < vm.max_votes THEN 'S01' END],x -> x IS NOT NULL) AS quality_codes
      FROM combined c LEFT JOIN votes v USING(molecule_id,reidentified_inchikey)
      LEFT JOIN vote_max vm USING(molecule_id) LEFT JOIN minima m USING(molecule_id))
      TO {q(quality)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
    con.execute(f'CREATE OR REPLACE VIEW quality AS SELECT * FROM read_parquet({q(quality)})')
    population=rows(con,'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,
        count(*) FILTER(WHERE retained) AS retained_records,
        count(DISTINCT molecule_id) FILTER(WHERE retained) AS retained_molecules,
        count(*) FILTER(WHERE NOT geometry_evaluated AND NOT (X01 OR X02 OR X03 OR X04 OR X05)) AS missing_required_geometry
        FROM quality''')[0]
    report={'status':'COMPLETE' if population['missing_required_geometry']==0 else 'INCOMPLETE_GEOMETRY',
        'population':population,'codes':{},'overlap':{},'sequential':[],'seed':20261010,
        'software':{'duckdb':duckdb.__version__},'job_id':os.environ.get('SLURM_JOB_ID'),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'I01':'Full InChIKey equality. Stereo-only disagreements also recorded separately.',
        'G03':'Prior measured order_suspected_from_bond_lengths: >=5 bonds and >25% outliers against covalent-radius ratio [0.75,1.3].',
        'H01':'Absolute stored heat of formation / atom count; observation only, no cutoff applied.',
        'S02':'Stored conformer energy minus molecular minimum among records surviving X filters; observation only.'}
    for code in EXCLUDE+['S01','B01','T01']:
        report['codes'][code]=rows(con,f'SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE coalesce({code},false)')[0]
        con.execute(f'COPY (SELECT * FROM quality WHERE coalesce({code},false) ORDER BY record_id LIMIT 50) TO {q(out/(code+"_examples.parquet"))} (FORMAT PARQUET,COMPRESSION ZSTD)')
    for code,value in [('H01','H01_abs_energy_per_atom'),('S02','S02_delta_energy_kcal_mol')]:
        report['codes'][code]=rows(con,f'SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE {value} IS NOT NULL')[0]
        report['codes'][code]['count_kind']='available continuous observation; no binary cutoff'
        con.execute(f'COPY (SELECT * FROM quality WHERE {value} IS NOT NULL ORDER BY {value} DESC,record_id LIMIT 50) TO {q(out/(code+"_examples.parquet"))} (FORMAT PARQUET,COMPRESSION ZSTD)')
    for a in EXCLUDE+['S01','B01','T01']:
        report['overlap'][a]={b:con.execute(f'SELECT count(*) FROM quality WHERE coalesce({a},false) AND coalesce({b},false)').fetchone()[0] for b in EXCLUDE+['S01','B01','T01']}
    keep=[]
    for code in EXCLUDE:
        keep.append('NOT coalesce('+code+',false)')
        report['sequential'].append({'after':code,**rows(con,'SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE '+' AND '.join(keep))[0]})
    report['H01_thresholds']={str(t):con.execute(f'SELECT count(*) FROM quality WHERE {xcond} AND H01_abs_energy_per_atom > {t}').fetchone()[0] for t in [20,30,50,200]}
    report['retained_size']=rows(con,'''SELECT heavy_atoms,count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM quality WHERE retained GROUP BY heavy_atoms ORDER BY heavy_atoms''')
    report['size_quantiles']=rows(con,'''SELECT quantile_cont(total_atoms,[0,.25,.5,.75,.9,.99,1]) AS atom_quantiles,quantile_cont(heavy_atoms,[0,.25,.5,.75,.9,.99,1]) AS heavy_atom_quantiles FROM quality WHERE retained''')[0]
    report['S02_distribution']=rows(con,'''SELECT count(S02_delta_energy_kcal_mol) AS records,quantile_cont(S02_delta_energy_kcal_mol,[0,.5,.9,.99,.999,1]) AS quantiles FROM quality''')[0]
    report['element_distribution']=rows(con,'''SELECT z,count(*) AS containing_records FROM quality,unnest(elements) AS u(z) WHERE retained GROUP BY z ORDER BY z''')
    report['split_counts']=rows(con,'''SELECT split,count(*) AS records,count(DISTINCT molecule_id) AS molecules,count(*) FILTER(WHERE retained) AS retained_records,count(DISTINCT molecule_id) FILTER(WHERE retained) AS retained_molecules FROM quality GROUP BY split''')
    (out/'screening_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    lines=['# WP1 筛选分析','',f"记录 {population['records']:,}；分子 {population['molecules']:,}；保留记录 {population['retained_records']:,}；保留分子 {population['retained_molecules']:,}。",'',
      f"尚缺必需几何检查：{population['missing_required_geometry']:,} 条。",'',
      '各代码命中数、重叠矩阵、累计保留数、元素与大小分布详见 screening_report.json；每个布尔代码最多50条样例为同名 *_examples.parquet。','',
      'H01 和 S02 仅记录连续数值，不设置删除阈值。原 LMDB 只读，未创建或写入任何 LMDB。','',
      '## 附录','', 'I01 按完整 InChIKey 比较；立体层不同而连接层相同的情况单列 stereo_only_key_mismatch，可在正式轮前评估与 T01 的重叠。']
    (out/'screening_report.md').write_text('\n'.join(lines)+'\n')
    con.close();print(json.dumps({'status':report['status'],**population}))

if __name__=='__main__':main()
