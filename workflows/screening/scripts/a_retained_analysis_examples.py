"""A1 interpret 50 true connectivity changes using existing cached SMILES only."""
from __future__ import annotations
import argparse,concurrent.futures,collections,json,multiprocessing,os,sys,time
from pathlib import Path
from a_retained_analysis import ROOT,DEPS,BINS,q,rows,save,ref,copy,progress
def init():
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.*')
def chemistry(smiles):
    from rdkit import Chem
    mol=Chem.MolFromSmiles(smiles)
    if mol is None:raise ValueError('Cached SMILES cannot be parsed')
    heavy=[a for a in mol.GetAtoms() if a.GetAtomicNum()>1]
    expanded=Chem.AddHs(mol)
    counts=collections.Counter(a.GetSymbol() for a in expanded.GetAtoms())
    bonds=collections.Counter(str(b.GetBondType()) for b in mol.GetBonds())
    return {'elements_with_H':dict(sorted(counts.items())),'heavy_atoms':len(heavy),'total_atoms_with_H':expanded.GetNumAtoms(),
      'formal_charge':Chem.GetFormalCharge(mol),'radical_electrons':sum(a.GetNumRadicalElectrons() for a in mol.GetAtoms()),
      'fragments':len(Chem.GetMolFrags(mol)),'bond_orders':dict(sorted(bonds.items())),
      'isotopes':sorted((a.GetSymbol(),a.GetIsotope()) for a in mol.GetAtoms() if a.GetIsotope()),
      'canonical_no_stereo_smiles':Chem.MolToSmiles(mol,isomericSmiles=False)}
def analyze(row):
    r={'record':row,'source':None,'geometry':None,'change_categories':[],'error':None,'worker_pid':os.getpid()}
    try:
        s=chemistry(row['smiles']);g=chemistry(row['reidentified_smiles']);r.update(source=s,geometry=g)
        for field,label in [('elements_with_H','ELEMENT_OR_H_COMPOSITION'),('heavy_atoms','HEAVY_ATOM_COUNT'),
          ('formal_charge','FORMAL_CHARGE'),('radical_electrons','RADICAL_COUNT'),('fragments','FRAGMENT_COUNT'),
          ('bond_orders','BOND_ORDER_COMPOSITION'),('isotopes','ISOTOPE_CONTENT')]:
            if s[field]!=g[field]:r['change_categories'].append(label)
        if s['canonical_no_stereo_smiles']!=g['canonical_no_stereo_smiles']:
            r['change_categories'].append('NONSTEREO_GRAPH_REPRESENTATION')
        if not r['change_categories']:r['change_categories'].append('INCHI_CONNECTIVITY_DIFF_WITH_NO_COARSE_CHANGE')
    except Exception as exc:r['error']=type(exc).__name__+': '+str(exc)[:1000]
    return r
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'a_retained'));p.add_argument('--workers',type=int,default=16);p.add_argument('--memory-gb',type=int,default=8);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise RuntimeError('Slurm >=16 CPUs/effective workers required')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
    try:import duckdb;import pyarrow.parquet as pq
    except ModuleNotFoundError:sys.path.insert(0,str(DEPS));import duckdb;import pyarrow.parquet as pq
    out=Path(a.output).absolute();quality=out/'relaxed_quality_annotations.parquet'
    if not out.is_relative_to(ROOT):raise RuntimeError('Outputs must remain in new screening root')
    manifest=json.loads((out/'manifest.json').read_text())
    if pq.ParquetFile(quality).metadata.num_rows!=manifest['physical']['records']:raise RuntimeError('PHYSICAL_MANIFEST_COUNT_MISMATCH')
    db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute(f"SET memory_limit='{a.memory_gb}GB'")
    db.execute('CREATE VIEW quality AS SELECT * FROM read_parquet('+q(quality)+')')
    samples=rows(db,'''SELECT record_id,molecule_id,smiles,reidentified_smiles,stored_inchikey,reidentified_inchikey,
      heavy_atoms,elements,strict_retained,retained,protonation_mismatch,quality_codes FROM quality
      WHERE connectivity_mismatch IS TRUE ORDER BY sha256(record_id) LIMIT 50''')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn'),initializer=init) as pool:
        interpreted=list(pool.map(analyze,samples,chunksize=1))
    bysize=rows(db,f'''SELECT {BINS} AS size_stratum,count(*) AS records,count(DISTINCT molecule_id) AS molecules,
      count(*) FILTER(WHERE I01 IS TRUE) AS excluded_by_relaxed_I01 FROM quality WHERE connectivity_mismatch IS TRUE GROUP BY size_stratum ORDER BY min(heavy_atoms)''')
    byelement=rows(db,'''SELECT z,count(*) AS records,count(DISTINCT molecule_id) AS molecules
      FROM quality,unnest(list_distinct(elements)) u(z) WHERE connectivity_mismatch IS TRUE GROUP BY z ORDER BY z''')
    proton_only=rows(db,f'''SELECT {BINS} AS size_stratum,count(*) AS records,count(DISTINCT molecule_id) AS molecules
      FROM quality WHERE I01 IS TRUE AND connectivity_mismatch IS NOT TRUE AND protonation_mismatch IS TRUE GROUP BY size_stratum ORDER BY min(heavy_atoms)''')
    db.close()
    result={'status':'50_CONNECTIVITY_CHANGE_EXAMPLES_INTERPRETED_WITH_EXPLICIT_ERRORS','sample_records':len(samples),
      'effective_worker_PIDs':sorted({r['worker_pid'] for r in interpreted}),'change_category_counts':dict(collections.Counter(c for r in interpreted for c in r['change_categories'])),
      'unknown_examples':sum(r['error'] is not None for r in interpreted),'true_connectivity_by_size':bysize,'true_connectivity_by_element':byelement,
      'protonation_only_remaining_I01_by_size':proton_only,'examples':interpreted,'source_quality':ref(quality),'script':ref(__file__,True),
      'scope':'Coarse graph changes explain examples; no atom-mapped bond edit or optimization trajectory is claimed.',
      'LMDB_opened_or_written':False,'new_QM':False,'new_RDDetermineBonds':False}
    save(out/'A1_connectivity_changes50.json',result)
    lines=['# A1：50条骨架变化具体检查','', '| record | 变化类型 | source键 | geometry键 |','| --- | --- | --- | --- |']
    for r in interpreted:
        row=r['record'];labels=', '.join(r['change_categories']) if r['error'] is None else r['error']
        lines.append(f"| {row['record_id']} | {labels} | {row['stored_inchikey']} | {row['reidentified_inchikey']} |")
    lines += ['', '各例原始／几何SMILES、加氢元素组成、形式电荷、片段数和键阶组成差别均在同名JSON。仅检查已缓存的图表示；未声称观察到了具体优化路径。']
    (out/'A1_connectivity_changes50.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    progress('connectivity_examples_complete',records=len(samples),errors=result['unknown_examples']);return 0
if __name__=='__main__':raise SystemExit(main())
