"""Count stored R/N graph features and existing NN scores; no similarity calls."""
import argparse
import csv
import json
import os
from pathlib import Path
from .producer import read, save
from ..distribution_report_v1.functional_groups import NUMERIC_FIELDS
from ..distribution_report_v1.aggregate import edges_for


def write_csv(path, names, rows):
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(names); writer.writerows(rows)


def run(config):
    import duckdb
    if not os.environ.get('SLURM_JOB_ID'): raise RuntimeError('SLURM_REQUIRED')
    out = Path(config['output']); out.mkdir(parents=True, exist_ok=True)
    source = read(config['source_manifest']); rank = read(source['ranking_receipt']['path'])
    pool = read(rank['filtered_pool']['path']); novelty = read(rank['novelty_receipt']['path'])
    db = duckdb.connect(str(out / 'counted.duckdb'))
    db.execute('SET threads=' + str(config['workers']))
    db.read_parquet(rank['batch1']['path']).create_view('batch1')
    db.read_parquet([r['path'] for r in pool['candidates']]).create_view('pool')
    columns = ','.join('p.' + n for n in NUMERIC_FIELDS)
    db.execute('CREATE TABLE IF NOT EXISTS selected AS SELECT b.stream,b.stream_rank,p.full_key,p.cid,' + columns +
               ',p.element_combination,p.elements,p.generic_murcko,p.generic_ring_systems FROM pool p JOIN batch1 b USING(cid,full_key)')
    counts = dict(db.execute('SELECT stream,count(*) FROM selected GROUP BY stream').fetchall())
    if counts != {'R': 1250000, 'N': 1250000}: raise ValueError('R_N_FEATURE_COVERAGE')
    db.read_parquet([r['path'] for r in novelty['projection_parts']]).create_view('novelty')
    db.execute('CREATE TABLE IF NOT EXISTS scores AS SELECT b.stream,n.nearest_v1_tanimoto,n.v1_scaffold_count,n.v1_ring_system_count '
               'FROM novelty n JOIN batch1 b USING(cid,full_key)')
    if dict(db.execute('SELECT stream,count(*) FROM scores GROUP BY stream').fetchall()) != counts:
        raise ValueError('STORED_NN_ID_ALIGNMENT')
    numeric, histograms = [], []
    for name in NUMERIC_FIELDS:
        numeric.extend((stream, name, n, mean, std, lo, hi) for stream, n, mean, std, lo, hi in
                       db.execute(f'SELECT stream,count({name}),avg({name}),stddev_pop({name}),min({name}),max({name}) FROM selected GROUP BY stream').fetchall())
        edges = edges_for(name)
        cases = ' '.join(f'WHEN {name}<{edge} THEN {i}' for i, edge in enumerate(edges))
        # Match the pre-existing rightmost finite bin, including its endpoint.
        cases += f' WHEN {name}={edges[-1]} THEN {len(edges)-1}'
        bins = db.execute(f'SELECT stream,CASE {cases} ELSE {len(edges)} END AS bin,count(*) FROM selected GROUP BY ALL ORDER BY stream,bin').fetchall()
        histograms.extend((stream, name, index, '-inf' if index == 0 else edges[index-1],
                           'inf' if index == len(edges) else edges[index], n) for stream, index, n in bins)
    write_csv(out/'numeric_summary.csv', ['population','field','n','mean','population_std','min','max'], numeric)
    write_csv(out/'histograms.csv', ['population','field','bin','left','right','count'], histograms)
    coverage = db.execute('SELECT stream,count(*) n,avg(nearest_v1_tanimoto),stddev_pop(nearest_v1_tanimoto),'
        'avg((nearest_v1_tanimoto<0.4)::INT),avg((nearest_v1_tanimoto<0.6)::INT),avg((nearest_v1_tanimoto<0.8)::INT),'
        'avg((v1_scaffold_count=0)::INT),avg((v1_ring_system_count=0)::INT) FROM scores GROUP BY stream ORDER BY stream').fetchall()
    write_csv(out/'coverage.csv', ['stream','molecules','mean_NN_to_v1','std_NN_to_v1','fraction_below_0.4',
        'fraction_below_0.6','fraction_below_0.8','novel_scaffold_fraction','novel_ring_system_fraction'], coverage)
    categorical = ' UNION ALL '.join(f"SELECT stream,'{field}' kind,cast({field} AS VARCHAR) category,count(*) n FROM selected GROUP BY stream,{field}"
                                      for field in ('heavy_atoms','element_combination','generic_murcko','generic_ring_systems'))
    db.execute('COPY ('+categorical+") TO '"+str(out/'categorical_counts.parquet')+"' (FORMAT PARQUET,COMPRESSION ZSTD)")
    summary = {'molecules_by_stream': counts, 'coverage_to_v1': coverage,
        'coverage_change_query_population': 'The fixed selected 2500000 structures; query self is included after addition',
        'after_addition_nearest_Tanimoto_on_these_same_queries': 1.0,
        'new_direct_structure_coverage_count': 2500000, 'filtered_pool_molecules': rank['pool_molecules'],
        'directly_added_fraction_of_filtered_pool': 2500000/rank['pool_molecules'],
        'new_NN_or_similarity_computations': 0,
        'remaining_pool_or_fixed1M_augmented_NN_distribution': 'Not computed under taskbook v2; not inferred from these queries',
        'numeric': [dict(zip(('population','field','n','mean','population_std','min','max'), row)) for row in numeric]}
    save(out/'summary.json', summary)
    print(json.dumps(summary), flush=True)
    db.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--config', required=True)
    run(read(parser.parse_args().config))
