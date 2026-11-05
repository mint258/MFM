"""Explicit overlay binding for the unchanged original V3/H-only filter body."""
import argparse
from pathlib import Path
import traceback
from types import FunctionType
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..alpha_closed500_handoff_v1 import filter_core as original_core,empty_domain,science_v3,scientific_contract
from .runtime import VERSION,admit,read
from .reader import validate_header,bind,finish

RELATION='PUBCHEM_LOGICAL_MINCID_OVERLAY_RELATION_V1'


class RegisteredRelation:
    def create_view(self,name):
        Q.need(name=='candidates','Only the explicit logical candidate binding is adapted')
        return self


class Connection(empty_domain.ExtendedDomainConnection):
    def __init__(self,db,pool,check,witnesses,candidate_binder):
        super().__init__(db);self.pool,self.check,self.witnesses,self.candidate_binder=pool,check,witnesses,candidate_binder
    def read_parquet(self,source,*args,**kwargs):
        Q.need(source==RELATION and not args and not kwargs,'Exact logical relation token, never a fabricated Parquet file')
        self.witnesses.extend(self.candidate_binder(self.db,self.pool,self.check))
        return RegisteredRelation()


def run_core(pool,index_path,out,workers,memory_bytes,check,*,candidate_binder=bind):
    witnesses=[];connection=original_core.connection;scope=dict(vars(original_core))
    scope['connection']=lambda *a,**k:Connection(connection(*a,**k),pool,check,witnesses,candidate_binder)
    function=FunctionType(original_core.filter_core.__code__,scope,original_core.filter_core.__name__,
        original_core.filter_core.__defaults__,original_core.filter_core.__closure__)
    Q.need(function.__code__ is original_core.filter_core.__code__ and original_core.connection is connection,
        'Original filter scientific code object/global connection remain unchanged')
    result=function(RELATION,index_path,out,workers,memory_bytes,check)
    finish(witnesses)
    Q.need(original_core.connection is connection,'No original module monkeypatch')
    return result


def sources(plan):
    from ..portable_sources_v1.transport import verify
    pool=validate_header(read(plan['source_pool_receipt_reference']))
    index_ref=plan['exclusion_index_receipt'];index=science_v3.index_header(Q.load(verify(index_ref)))
    review=Q.load(verify(plan['root_index_acceptance_reference']))
    Q.need(review['schema']=='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='APPROVED_COMPLETE_ALL11_INDEX' and review['reviewer']=='root'
        and review['index_receipt']==index_ref and review['all_sources_all_splits_verified'] is True
        and review['original_graph_unknowns_retained'] is True,'Actual all11 all-split/source-scope accepted index')
    account=Q.load(verify(review['actual_accounting_reference']));parent=review['actual_parent']
    Q.need(parent['State']=='COMPLETED' and parent['ExitCode']=='0:0'
        and str(parent['JobIDRaw'])==str(index['producer_parent_binding']['job_id'])
        and parent in account['actual_parents'],'Original all11 producer actual C0, not metadata-ready substitution')
    verify(index['source_manifest_reference']);path=verify(index['database'])
    Q.need(all(not Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')),'Closed immutable all11 index')
    regression=Q.load(verify(plan['regression_reference']))
    Q.need(regression['status']=='PASS' and regression['agreement']>=.999 and regression['unexplained_mismatches']==0
        and regression['full_v1_selection_regression_passed'] is True,'Unchanged original full-selection regression gate')
    return pool,path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    authority=admit(plan,proof,a.plan,a.startup_proof,'PUBCHEM_ALPHA_GENERIC_RECOVERY_FILTER_PLAN_V1','pubchem_alpha_generic_recovery_filter_v1')
    from ..portable_sources_v1.transport import bind_plan
    bind_plan(plan);scientific_contract.verify()
    refs=proof['request']['source_references']
    for path in [Path(m.__file__) for m in (original_core,empty_domain,science_v3,scientific_contract)]+[Path(scientific_contract.__file__).with_name('original_function_contract.json')]:
        Q.need(Q.reference(path) in refs,'Actual original V3/H-only science source pin')
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        import io,unittest
        from .test_filter import Native
        log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Native))
        testref=Q.write(out/'source_test.json',dict(tests=tests.testsRun,errors=len(tests.errors),failures=len(tests.failures),skips=len(tests.skipped),transcript=log.getvalue()))
        Q.need(tests.wasSuccessful() and tests.testsRun==1 and not tests.skipped,'Native overlay binding/original V3/H-only filter parity')
        pool,index=sources(plan);before=Q.frame(index)
        selected,hits,counts=run_core(pool,index,out,plan['workers'],plan['duckdb_memory_bytes'],guard.check)
        Q.need(counts['input_unique_molecules']==pool['unique_full_keys']
            and counts['eligible_molecules']+counts['excluded_molecules']==pool['unique_full_keys']
            and Q.frame(index)==before,'Complete new population/filter mass and stable index')
        Q.write(out/'receipt.json',dict(schema='expansion_filtered_columnar_pool_v1',status='COMPLETE',population_version=VERSION,
            source_endpoint='218.192.171.238:22',source_uid=1264,source_pool_receipt=plan['source_pool_receipt_reference'],
            exclusion_index_receipt=plan['exclusion_index_receipt'],root_index_acceptance_reference=plan['root_index_acceptance_reference'],
            regression_reference=plan['regression_reference'],parent_transport_manifest=plan['parent_transport_manifest'],
            counts=counts,candidates=selected,contamination_hits=hits,aliases_relation=pool['aliases_relation'],
            source_aliases_preserved_by_reference=True,all_sources_all_splits_verified=True,original_graph_unknowns_retained=True,
            downstream_targets_consumed=False,candidate_domain_extension=empty_domain.EXTENSION,
            original_filter_code_object_unchanged=True,original_module_globals_not_modified=True,
            scope=dict(source_pool_receipt=plan['source_pool_receipt_reference'],population_version=VERSION,
                exclusion_index_receipt=plan['exclusion_index_receipt'],root_index_acceptance_reference=plan['root_index_acceptance_reference'],
                regression_reference=plan['regression_reference'],parent_transport_manifest=plan['parent_transport_manifest'],
                candidate_domain_extension=empty_domain.EXTENSION),
            actual_parent=authority,actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING',
            source_test=testref,resource_plan=Q.reference(a.plan),startup_proof_reference=Q.reference(a.startup_proof),runtime=guard.receipt()))
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,old_sources_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
