"""Select descriptive examples from closed counted tables, never molecular data."""
import argparse,csv,hashlib,heapq,io,json,os,pathlib,socket,time

def ref(path):
    path=pathlib.Path(path);raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--tables',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':raise ValueError('Authorized Main20 metadata analysis only')
    start=time.perf_counter();manifest=a.tables/'producer_manifest.json';producer=json.loads(manifest.read_text());original=producer['original_distribution_report']
    if producer['status']!='COMPLETE' or producer['report_scope']!='TASK2_1_BASELINE':raise ValueError('Actual closed baseline report only')
    refs={pathlib.Path(r['path']).name:r for r in original['artifacts']};used=[]
    def load(name):
        path=a.tables/name;source=refs[name];before=path.stat();raw=path.read_bytes()
        frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)
        if len(raw)>64<<20 or len(raw)!=source['bytes'] or hashlib.sha256(raw).hexdigest()!=source['sha256'] or frame(path.stat())!=frame(before):raise ValueError('Bounded immutable whole-SHA counted table')
        used.append(dict(origin_reference=source,replica_reference=dict(source,path=str(path))))
        return raw.decode('utf-8')
    summary=json.loads(load('summary.json'));descriptive={}
    for name in('coverage_heavy_bin.csv','coverage_element_combination.csv','coverage_scaffold.csv'):
        rows=csv.DictReader(io.StringIO(load(name)))
        selected=(r for r in rows if int(r['pubchem_molecules'])>=100 and(r['absent_in_v1']=='1' or r['descriptive_at_least_2x_underrepresentation']=='1'))
        descriptive[name]=heapq.nlargest(8,selected,key=lambda r:int(r['pubchem_molecules']))
    rows=csv.DictReader(io.StringIO(load('exact_nearest_v1_by_size_element_stratum.csv')))
    low=heapq.nsmallest(8,(r for r in rows if int(r['queries'])>=1000),key=lambda r:float(r['mean_exact_similarity']))
    histogram=[r for r in csv.DictReader(io.StringIO(load('fixed_histograms_and_bin_ecdf.csv')))if r['population_or_comparison']=='NN:pubchem_to_v1' and r['field']=='nearest_tanimoto']
    n=sum(int(r['count'])for r in histogram)
    if n!=1000000:raise ValueError('Complete same1M histogram required')
    below={str(t):sum(int(r['count'])for r in histogram if float(r['right'])<=t)/n for t in(.4,.6,.8)}
    quantiles={name:next(dict(left=r['left'],right=r['right'])for r in histogram if int(r['cumulative_count'])>=target)for name,target in [('p10',100000),('p50',500000),('p90',900000)]}
    value=dict(schema='COUNTED_BASELINE_DESCRIPTIVE_NOTES_V1',producer_replica_reference=ref(manifest),table_replicas=used,summary=summary,
        largest_underrepresented_categories_with_at_least100_sample_molecules=descriptive,lowest_mean_NN_strata_with_at_least1000_queries=low,
        fraction_strictly_below_internal_bin_edges=below,quantile_containing_bins_not_exact_quantiles=quantiles,
        descriptive_only_not_selection=True,chemistry_or_NN_recomputed=False,source=ref(__file__),execution=dict(uid=os.getuid(),node=socket.gethostname(),pid=os.getpid(),slurm_job_id=os.environ.get('SLURM_JOB_ID'),wall_seconds=time.perf_counter()-start))
    with a.output.open('x')as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(dict(output=str(a.output),queries=n,fraction_strictly_below=below,quantile_bins=quantiles)),flush=True)
if __name__=='__main__':main()
