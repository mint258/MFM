"""Plot closed NN histogram counts, including the exact-score-one endpoint mass."""
import argparse,csv,hashlib,io,json,math,os,pathlib,socket,sys,time

def frame(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)

def reference(path):
    path=pathlib.Path(path);raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def points(rows,expected_queries,expected_score_one):
    """Use original bins: the final finite bin includes1; overflow must be empty."""
    rows=sorted(rows,key=lambda r:int(r['bin']));xs=[0.0];ys=[0.0];total=0;last_finite=None;overflow=None
    for row in rows:
        count=int(row['count']);left=float(row['left']);right=float(row['right'])
        if count<0:raise ValueError('Negative count')
        total+=count
        if total!=int(row['cumulative_count']):raise ValueError('Cumulative mass differs')
        if left==-math.inf:
            if right!=0.0 or count:raise ValueError('Invalid negative Tanimoto mass')
        elif right==math.inf:
            if left!=1.0 or overflow is not None or count:raise ValueError('No score above1 is valid')
            overflow=count
        else:
            if not 0<=left<right<=1:raise ValueError('Invalid finite score bin')
            xs.append(right);ys.append(total/expected_queries)
            if right==1.0:last_finite=count
    if total!=expected_queries or last_finite is None or overflow!=0 or not 0<=expected_score_one<=last_finite:raise ValueError('Whole query/terminal-bin mass differs')
    xs.append(1.0);ys.append(1.0)
    if any(a>b for a,b in zip(xs,xs[1:]))or any(a>b for a,b in zip(ys,ys[1:])):raise ValueError('Nonmonotone binned ECDF')
    return xs,ys

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',required=True,type=pathlib.Path);a=ap.parse_args()
    if not sys.flags.isolated:raise ValueError('Use isolated server Python')
    wall=time.perf_counter();cpu=time.process_time();config=json.loads(a.config.read_text())
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':raise ValueError('Authorized Main20 metadata renderer only')
    if os.environ.get('SLURM_JOB_ID'):raise ValueError('This invocation records actual direct metadata execution, not Slurm')
    replica=config['histogram_replica_reference'];path=pathlib.Path(replica['path']);before=path.stat()
    if replica['bytes']>2<<20 or reference(path)!=replica:raise ValueError('Bounded whole-SHA histogram replica')
    with path.open('rb')as f:
        opened=os.fstat(f.fileno());raw=f.read((2<<20)+1);closed=os.fstat(f.fileno())
    if frame(opened)!=frame(closed) or frame(path.stat())!=frame(before) or hashlib.sha256(raw).hexdigest()!=replica['sha256']:raise ValueError('Stable same-FD histogram required')
    groups={}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8'))):
        if row['field']=='nearest_tanimoto':groups.setdefault(row['population_or_comparison'],[]).append(row)
    expected=config['comparisons']
    if set(groups)!=set(expected):raise ValueError('Exactly the declared complete comparisons')
    plotted={name:points(groups[name],item['queries'],item['score_one'])for name,item in expected.items()}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','svg.hashsalt':'pubchem_closed_nn_ecdf_v1'})
    output=pathlib.Path(config['output_directory']);output.mkdir(parents=True,exist_ok=False)
    fig,ax=plt.subplots(figsize=(8,4.8),constrained_layout=True)
    for name,(xs,ys)in plotted.items():
        ax.step(xs,ys,where='post',label=expected[name]['label'],linewidth=1.8)
        ax.plot([1.0],[1.0],marker='o',markersize=3,color=ax.lines[-1].get_color())
    ax.set(xlabel='Exact nearest ECFP4 Tanimoto',ylabel='Fixed-bin cumulative fraction',xlim=(0,1.015),ylim=(0,1.025))
    ax.grid(alpha=.2);ax.legend(loc='upper left');artifacts=[]
    for ext in('svg','png','pdf'):
        path=output/('exact_nearest_coverage_baseline.'+ext)
        metadata={'Date':None}if ext=='svg'else({'CreationDate':None,'ModDate':None}if ext=='pdf'else None)
        fig.savefig(path,dpi=180,metadata=metadata)
        if path.stat().st_size>2<<20:raise ValueError('Bounded report figure required')
        artifacts.append(reference(path))
    plt.close(fig)
    result=dict(schema='CLOSED_NEAREST_BIN_ECDF_FIGURES_V1',histogram_origin_reference=config['histogram_origin_reference'],histogram_replica_reference=replica,
        original_report_reference=config['original_report_reference'],comparison_mass_checks=expected,artifacts=artifacts,
        binning_changed=False,chemistry_or_NN_recomputed=False,score_one_endpoint_included=True,unbinned_ECDF_claimed=False,
        source=reference(__file__),config=reference(a.config),execution=dict(endpoint='202.38.247.57:22',uid=os.getuid(),node=socket.gethostname(),pid=os.getpid(),argv=sys.argv,
        slurm_job_id=None,wall_seconds=time.perf_counter()-wall,process_CPU_seconds=time.process_time()-cpu,matplotlib_version=matplotlib.__version__))
    (output/'manifest.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True),flush=True)
if __name__=='__main__':main()
