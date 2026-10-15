"""Read actual failed smoke evidence and inspect raw source identity metadata."""
import csv,json,os,re
from pathlib import Path
from prepare import ROOT,save

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(16)
    result={'job_id':os.environ['SLURM_JOB_ID'],'failed_smoke_job':'4515110','errors':{},'cyp_identity_metadata':[]}
    for dataset in ['qm7','qm9']:
        rows=pq.read_table(ROOT/'probe_data_development'/(dataset+'.parquet')).to_pylist()
        result['errors'][dataset]=[{k:r[k] for k in ['record_id','geometry_status','error','annotation_status']} for r in rows[:4]]
    table=Path('/share/home/zixiao/benchmark_dataset/scaffold_split/cyp_isoform/fold_assignments.csv')
    with table.open(newline='') as stream:members=list(csv.DictReader(stream))
    raw=Path('/share/home/zixiao/benchmark_dataset/cyp_isoform/raw/1A2.sdf').read_bytes()
    frames=[];start=0
    for match in re.finditer(rb'(?m)^\$\$\$\$(?:\r?\n|$)',raw):
        frames.append(raw[start:match.end()]);start=match.end()
    for member in members[:8]:
        ordinal=int(member['sample_uid'].rsplit('::',1)[1])
        result['cyp_identity_metadata'].append({'member':member['sample_uid'],'compound':member['compound_id'],
            'declared_ordinal':ordinal,'raw_title_at_ordinal':frames[ordinal-1].splitlines()[0].decode('utf-8',errors='replace'),
            'raw_title_next':frames[ordinal].splitlines()[0].decode('utf-8',errors='replace') if ordinal<len(frames) else None})
    save(ROOT/'reports/s_probe_smoke_failure_audit_v1.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
