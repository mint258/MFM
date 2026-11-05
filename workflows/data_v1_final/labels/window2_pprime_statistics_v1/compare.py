"""P/P-prime descriptive distributions and same-MID field mean correlations.

Consumes summaries emitted by the existing normalization_moments streams;
never rereads original scientific label or geometry files.
"""
import argparse,json,math
from pathlib import Path
from ..window2_normalization_v1 import io as I
from .projection import need
from . import temporary as Temp


def finite_or_none(value):
    return float(value)if value is not None and math.isfinite(value)else None


def merged_mean_sql(view):
    # A molecule may span multiple original source groups; use valid-leaf
    # weighting rather than an unweighted mean of group means.
    return 'SELECT molecule_id,field_id,sum("sum")/sum(n) AS value,sum(n) AS valid_leaves FROM '+view+' GROUP BY molecule_id,field_id'


def distributions(pm7,pprime):
    a=I.load_data(pm7['statistics']['winsorized_statistics_reference'])
    b=I.load_data(pprime['statistics']['winsorized_statistics_reference'])
    left={r['key']:r for r in a['series']};right={r['key']:r for r in b['series']};rows=[]
    for key in sorted(set(left)&set(right)):
        p,u=left[key],right[key]
        rows.append({'series_key':key,'field_key':p['source_field_key'],'view':p['view'],'unit':p['unit'],
            'PM7':{name:p.get(name)for name in('n','lower','upper','mean','std_ddof0')},
            'Pprime':{name:u.get(name)for name in('n','lower','upper','mean','std_ddof0')}})
    return rows


def compare(pm7_path,pprime_path,output,temporary_plan=None):
    pm7=I.load(pm7_path);pprime=I.load(pprime_path)
    plan=I.load(temporary_plan) if isinstance(temporary_plan,(str,Path)) else temporary_plan
    plan=plan or pprime.get('compare_temporary_runtime')
    need(plan is not None,'EXPLICIT_SAFE_COMPARE_TEMPORARY_PLAN_REQUIRED')
    runtime=Temp.activate(plan)
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    need(pm7['fit_role']==pprime['fit_role']=='TRAIN','TRAIN_ONLY_COMPARISON_SUMMARIES')
    pfiles=I.load_data(pm7['statistics']['molecule_field_means_reference'])['files']
    ufiles=I.load_data(pprime['statistics']['molecule_field_means_reference'])['files']
    root=Path(output);runtime.guard.target(root);runtime.wait(root)
    db=duckdb.connect()
    try:
        with runtime.duckdb(db):
            db.execute('SET threads='+str(int(__import__('os').environ.get('SLURM_CPUS_PER_TASK',16))))
            db.read_parquet([r['path']for r in pfiles]).create_view('pm7_parts')
            db.read_parquet([r['path']for r in ufiles]).create_view('pprime_parts')
            db.execute('CREATE TEMP VIEW pm7 AS '+merged_mean_sql('pm7_parts'))
            db.execute('CREATE TEMP VIEW pp AS '+merged_mean_sql('pprime_parts'))
            db.execute('CREATE TEMP TABLE paired AS SELECT p.molecule_id,p.field_id,p.value AS PM7_value,u.value AS Pprime_value,p.valid_leaves AS PM7_valid_leaves,u.valid_leaves AS Pprime_valid_leaves FROM pm7 p JOIN pp u USING(molecule_id,field_id)')
            table=db.execute('''WITH ranks AS(
        SELECT *,rank()OVER(PARTITION BY field_id ORDER BY PM7_value)+(count(*)OVER(PARTITION BY field_id,PM7_value)-1)/2.0 AS PM7_rank,
        rank()OVER(PARTITION BY field_id ORDER BY Pprime_value)+(count(*)OVER(PARTITION BY field_id,Pprime_value)-1)/2.0 AS Pprime_rank FROM paired)
        SELECT field_id,count(*) AS matched_molecules,corr(PM7_value,Pprime_value) AS pearson,corr(PM7_rank,Pprime_rank) AS spearman,
        avg(PM7_value) AS PM7_matched_mean,avg(Pprime_value) AS Pprime_matched_mean FROM ranks GROUP BY field_id ORDER BY field_id''').fetch_arrow_table()
    finally:db.close()
    runtime.wait(root);root.mkdir(parents=True,exist_ok=True)
    results=[]
    for row in table.to_pylist():
        for key in('pearson','spearman','PM7_matched_mean','Pprime_matched_mean'):row[key]=finite_or_none(row[key])
        row['correlation_status']='DEFINED'if row['pearson']is not None and row['spearman']is not None else'UNDEFINED_CONSTANT_OR_INSUFFICIENT_MATCHES'
        results.append(row)
    path=root/'P_vs_Pprime_same_MID_correlations.parquet';pq.write_table(pa.Table.from_pylist(results),path,compression='zstd')
    distribution_rows=distributions(pm7,pprime)
    dist=I.save(root/'P_vs_Pprime_distributions.json',{'series':distribution_rows,'fit_role':'TRAIN','same_existing_masks':True})
    result={'schema':'P_AND_PPRIME_TRAIN_DESCRIPTIVE_COMPARISON_V1','status':'COMPLETE','fit_role':'TRAIN',
        'correlation':dict(I.ref(path),records=len(results)),'distributions':dict(dist,records=len(distribution_rows)),
        'matching':'same molecule_id and original field_id; valid raw leaves averaged within molecule; group means merged using leaf counts',
        'coordinate_dependent_components':'Raw vector/tensor components are descriptive in their stored frames; correlation is not a claim of rotational equivalence or a new scientific normalization policy.',
        'geometry_difference':'PM7 all usable non-heldout conformers versus selected first-two UFF; no fabricated one-to-one conformer pairing',
        'source_label_or_geometry_files_reopened':False,'new_content_hashes':False}
    I.save(root/'manifest.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pm7',required=True);p.add_argument('--pprime',required=True);p.add_argument('--output',required=True)
    p.add_argument('--temporary-plan');a=p.parse_args()
    print(json.dumps(compare(a.pm7,a.pprime,a.output,a.temporary_plan)),flush=True)
