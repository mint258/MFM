"""Root actual-C0 adoption into the existing full-selection regression gate."""
import argparse
from pathlib import Path
from ..common import load,reference,dump_new,require
from ..portable_sources_v1.transport import verify


def finalize(producer_path,review_path,output):
    pref=reference(producer_path);rref=reference(review_path);p=load(verify(pref));review=load(verify(rref));result=p['result']
    require(p['schema']=='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PRODUCER_V1' and p['status']=='BINDING_VERIFIED_PENDING_ACTUAL_ALPHA_C0'
      and result['passed'] is True and result['failed_checks']==[] and all(result['checks'].values())
      and p['uid']==1264 and p['new_chemical_evaluator_calls']==0 and p['original_4520414_receipt_modified'] is False,'Actual complete SQL-only producer required')
    require(review['schema']=='ROOT_COMMON_SELECTION_REGRESSION_BIND_ACTUAL_ACCEPTANCE_V1' and review['status']=='APPROVED_ACTUAL_FULL_COMMON_SELECTION_REGRESSION'
      and review['reviewer']=='root' and review['producer_receipt']==pref,'Actual Root Common regression review required')
    parent=review['actual_parent'];account=load(verify(review['actual_accounting_reference']))
    require(parent['endpoint']=='218.192.171.238:22' and parent['uid']==1264 and str(parent['JobIDRaw'])==str(p['job_id'])
      and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent in account['actual_parents'],'Fresh actual Alpha C0 accounting required')
    source=load(verify(p['source_tests']));require(source['tests']==5 and source['failures']==source['errors']==source['skips']==0,'Actual SQL semantic source fixtures required')
    metrics=result['metrics']
    value=dict(schema='pubchem_v1_complete_input_common_bound_regression_v1',status='PASS',mode='full',agreement=metrics['agreement'],
      unexplained_mismatches=metrics['boolean_counts']['unexplained'],full_v1_selection_regression_passed=True,common_population_scope_bound=True,
      final_training_or_full_expansion_gate_released=False,new_chemical_evaluator_calls=0,original_4520414_receipt_modified=False,
      original_full_regression_reference=result['original_regression_reference'],common_reference_manifest=result['common_reference_manifest'],
      actual_binding_producer=pref,actual_binding_accounting_reference=review['actual_accounting_reference'],root_review=rref,
      actual_all_original_records=metrics['original_records'],actual_all_original_molecules=metrics['original_molecules'],
      Common_census=result['actual_old_Common_census'],selection_comparisons=metrics,actual_checks=result['checks'])
    dump_new(output,value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('producer','root-review','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();finalize(a.producer,a.root_review,a.output)


if __name__=='__main__':main()
