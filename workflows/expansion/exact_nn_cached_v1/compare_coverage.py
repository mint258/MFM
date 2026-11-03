"""Exact fixed-sample before/after coverage report, with explicit self matches."""
import argparse
from pathlib import Path
from ..common import load,reference,require,dump_new
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from .engine import RECIPE
from .sql_runtime import SqlGuard,configure,literal


def comparison(db,expected_molecules=1000000):
    for table in ('before','after'):
        require(db.execute('SELECT count(*),count(DISTINCT sample_ordinal),count(DISTINCT full_key),count(DISTINCT cid) FROM '+table).fetchone()
            ==(expected_molecules,expected_molecules,expected_molecules,expected_molecules),'Both complete fixed-sample projections required')
    for left,right in (('before','after'),('after','before')):
        require(db.execute('SELECT count(*) FROM '+left+' ANTI JOIN '+right+' USING(sample_ordinal,cid,full_key)').fetchone()[0]==0,
            'Before/after sample identity or order changed')
    db.execute('''CREATE VIEW delta AS SELECT b.sample_ordinal,b.cid,b.full_key,
        b.nearest_reference_tanimoto AS before_score,a.nearest_reference_tanimoto AS after_score,
        a.nearest_reference_tanimoto-b.nearest_reference_tanimoto AS gain,
        b.reference_identity_present AS before_identity_self,a.reference_identity_present AS after_identity_self,
        b.fingerprint_self_match AS before_fingerprint_self,a.fingerprint_self_match AS after_fingerprint_self,
        b.reference_ordinal AS before_ordinal,a.reference_ordinal AS after_ordinal,
        b.nearest_reference_key AS before_key,a.nearest_reference_key AS after_key
        FROM before b JOIN after a USING(sample_ordinal,cid,full_key)''')
    require(db.execute('SELECT count(*) FROM delta WHERE after_score<before_score').fetchone()[0]==0,
        'A true augmented full reference cannot decrease exact coverage')
    require(db.execute('SELECT count(*) FROM delta WHERE before_score=after_score AND (before_ordinal<>after_ordinal OR before_key<>after_key)').fetchone()[0]==0,
        'Equal scores must preserve earliest original reference ordinal')
    columns=['molecules','improved','unchanged','mean_before','mean_after','mean_gain','gain_p50','gain_p90','gain_p99','maximum_gain',
        'before_identity_self','after_identity_self','before_fingerprint_self','after_fingerprint_self']
    sql='''SELECT count(*),count(*) FILTER(WHERE gain>0),count(*) FILTER(WHERE gain=0),
        avg(before_score),avg(after_score),avg(gain),quantile_cont(gain,.5),quantile_cont(gain,.9),quantile_cont(gain,.99),max(gain),
        count(*) FILTER(WHERE before_identity_self),count(*) FILTER(WHERE after_identity_self),
        count(*) FILTER(WHERE before_fingerprint_self),count(*) FILTER(WHERE after_fingerprint_self) FROM delta'''
    return {'all_fixed_sample':dict(zip(columns,db.execute(sql).fetchone())),
        'identities_absent_from_both_references':dict(zip(columns,db.execute(sql+' WHERE NOT before_identity_self AND NOT after_identity_self').fetchone()))}


def run(plan_path):
    import duckdb
    plan=load(plan_path);require(plan.get('schema')=='PUBCHEM_EXACT_COVERAGE_COMPARISON_PLAN_V1','Wrong coverage comparison plan')
    bind_plan(plan)
    before=load(verify(plan['before_receipt']));after=load(verify(plan['after_receipt']))
    for item,role in ((before,'before'),(after,'after')):
        require(item.get('schema')=='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1' and item.get('status')=='COMPLETE'
            and item.get('reference_role')==role and item.get('queries')==1000000 and item.get('nearest_similarity_exact') is True
            and item.get('fingerprint_recipe')==RECIPE,'Complete scientific before/after receipts required')
    require(before['baseline_receipt']==after['baseline_receipt'],'Identical frozen PRE-decon1M baseline must be reused')
    augmented=load(verify(after['reference_manifest']))
    require(augmented['base_reference_manifest']==before['reference_manifest'],'After reference must extend this exact full Common reference')
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.exists(),'Fresh coverage comparison output required')
    root.mkdir(parents=True);guard=SqlGuard(plan,root);db=duckdb.connect(str(root/'coverage.duckdb'))
    try:
        configure(db,plan,root/'spill');guard.start(db)
        db.read_json(str(verify(before['projection'])),format='newline_delimited').create_view('before')
        db.read_json(str(verify(after['projection'])),format='newline_delimited').create_view('after')
        summary=comparison(db)
        db.execute('COPY (SELECT * FROM delta ORDER BY sample_ordinal) TO '+literal(root/'coverage_delta.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        db.execute('COPY (SELECT floor(before_score*100)::INTEGER AS score_percent_bin,count(*) AS molecules FROM delta GROUP BY ALL ORDER BY ALL) TO '+literal(root/'before_histogram.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        db.execute('COPY (SELECT floor(after_score*100)::INTEGER AS score_percent_bin,count(*) AS molecules FROM delta GROUP BY ALL ORDER BY ALL) TO '+literal(root/'after_histogram.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        db.execute('CHECKPOINT')
    finally:
        guard.done.set()
        if hasattr(guard,'thread'):guard.thread.join()
        db.close()
    guard.close()
    result={'schema':'EXPANSION_EXACT_FIXED1M_COVERAGE_COMPARISON_V1','status':'COMPLETE',
        'before_receipt':plan['before_receipt'],'after_receipt':plan['after_receipt'],'baseline_receipt':before['baseline_receipt'],
        'same_complete_fixed_sample_reused':True,'all_reference_rows_exact':True,'self_matches_reported_not_removed_from_full_sample':True,
        'summary':summary,'delta':reference(root/'coverage_delta.parquet'),
        'before_histogram':reference(root/'before_histogram.parquet'),'after_histogram':reference(root/'after_histogram.parquet'),
        'new_UFF_QM_calls':0,'training_release_authorized':False,'resource_plan':reference(plan_path)}
    result['endpoint_execution']=provenance(plan)
    dump_new(root/'receipt.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);run(p.parse_args().plan)


if __name__=='__main__':main()
