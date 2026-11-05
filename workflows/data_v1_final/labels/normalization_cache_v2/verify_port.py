"""Root-only stdlib source comparison; no fixtures/data/import of producer code."""
import argparse,ast,hashlib,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    here=Path(__file__).absolute().parent;old=here.with_name('normalization_cache_v1');rows=[]
    inverse={
      'run.py':{'source_train_typed_cache_512_profile_v2':'source_train_typed_cache_512_profile_v1',
        'suite.countTestCases()==3':'suite.countTestCases()==6','EXACT_THREE_BASE_METADATA_BOUNDARIES':'EXACT_SIX_NEW_CACHE_ADAPTER_BOUNDARIES',
        'result.testsRun==3':'result.testsRun==6','three_base_projection_fixtures_seconds':'six_new_fixtures_seconds'},
      'materialize.py':{'normalization_cache_v2':'normalization_cache_v1','source_train_typed_cache_512_profile_v2':'source_train_typed_cache_512_profile_v1'}}
    for name in ('profile.py','run.py','materialize.py'):
        before=(old/name).read_bytes();after=(here/name).read_bytes();text=after.decode()
        if name=='materialize.py':
            text=text.replace("    from .parents import failed_parent\n",'')
            text=text.replace("    for key in ('prior-failed-proof','prior-failed-accounting','prior-fixture-gate'):p.add_argument('--'+key,required=True)\n",'')
            text=text.replace("    failed_refs=failed_parent(a.prior_failed_proof,a.prior_failed_accounting,a.prior_fixture_gate)\n",'')
            text=text.replace("*failed_refs,",'')
            text=text.replace("      +[pin(REPO/'workflows/data_v1_final/labels/normalization_cache_v1/reader.py')]\n",'')
        for x,y in inverse.get(name,{}).items():text=text.replace(x,y)
        actual=text.encode();ok=actual==before
        rows.append({'name':name,'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':hashlib.sha256(after).hexdigest(),
          'inverse_bytes_equal':ok,'inverse_AST_equal':ast.dump(ast.parse(text),include_attributes=False)==ast.dump(ast.parse(before),include_attributes=False)})
    if not all(r['inverse_bytes_equal'] and r['inverse_AST_equal'] for r in rows):raise ValueError('SOURCE_BINDING_INVERSE_COMPARISON_FAILED')
    result={'schema':'SOURCE_TRAIN_CACHE_V2_SOURCE_PORT_PROOF_V1','status':'SOURCE_EQUIVALENCE_ONLY_NOT_SCIENCE_ACCEPTANCE',
      'files':rows,'profile_full_bytes_unchanged':rows[0]['inverse_bytes_equal'],
      'new_base_metadata_projection_and_three_incremental_fixtures':'INTENTIONAL_EXPLICIT_CHANGE',
      'original_f64_rebase_or_calibration_math_changed':False}
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')

if __name__=='__main__':main()
