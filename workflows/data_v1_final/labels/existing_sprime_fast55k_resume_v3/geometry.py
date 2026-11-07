"""Same original geometry/statistics; only terminal prefix/cache and quota IO."""
import pathlib,types
from . import contract as C,cache
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import geometry as FAST
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.execution import finite_quota_observation_guard_v2 as QG2
cohort=FAST.cohort;schema_header=FAST.schema_header;build=FAST.build;metadata_children=FAST.metadata_children
WORKER=FAST.WORKER;STATISTICS=FAST.STATISTICS;ELIGIBILITY=FAST.ELIGIBILITY
CONTEXT={}
class ResourceBudget(FAST.ResourceBudget):
    def _observe(self):
        from .resource_census import current_root_future
        with current_root_future(self):
            if not getattr(self,'_resume_quota_bound',False):
                old=self.native_observe;namespace=dict(old.__globals__,QG=QG2)
                f=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__);f.__kwdefaults__=old.__kwdefaults__
                self.native_observe=f;self._resume_quota_bound=True
            return super()._observe()
def adopt(path,root):
    path=pathlib.Path(path);C.need(root in path.parents,'ONLY_EXPLICIT_OLD_C0_ROOT')
    ref=I.pin(path);I.allow(ref,origin=root);I.require(ref);return ref
def prepare(plan,proof,root,budget):
    review,old,oldproof=C.resume_authority(plan);oldroot=C.OLDROOT
    rr=adopt(oldroot/'receipt.json',oldroot);receipt=I.load_data(rr,8<<20)
    C.need(receipt['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1' and receipt['job_id']=='4525232'
      and receipt['status']=='DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION' and receipt['coverage_reference']is None
      and receipt['geometry_reference']is None and receipt['numeric_repetitions']==[] and receipt['held']is False and not receipt['errors'],
      'ONLY_ACTUAL_PREFIX_PHASE_PARTIAL_NOT_COMPLETED_D4')
    oldgate=receipt['fixture_gate'];I.allow(oldgate,origin=oldroot);gate=I.load_data(oldgate,8<<20)
    C.need(gate['status']=='PASS' and gate['tests']==6 and gate['failures']==gate['errors']==0,'ORIGINAL_ACTUAL_SIX_SOURCE_TESTS')
    pr=receipt['prefix_reference'];C.need(pr['path']==str(oldroot/'closed_scalar_preselection/native_inputs.json'),'ORIGINAL_FROZEN55K_PREFIX_LOCATOR')
    I.allow(pr,origin=oldroot);prefix=I.load_data(pr,8<<20)
    C.need(prefix['no_new_molecule_selection']is True and prefix['actual_parent_job_id']=='4525232','SAME_OLD_SCALAR55K')
    for key in ('preselection_reference','members_reference','native_catalog_reference'):
        I.allow(prefix[key],origin=oldroot);I.require(prefix[key])
    # Original closed producer config registration needed by original tasks().
    native=FAST.ORIGINAL
    for entry in C.projection_origins(plan)['projection_origins']:
        m=I.load_data(entry['manifest_reference'],512<<20);cfg=C.reference(m['config']);cfgpath=pathlib.Path(cfg['path'])
        C.need(C.RUN in cfgpath.parents and cfgpath.suffix=='.json' and 0<cfg['bytes']<=8<<20,'FINITE_READONLY_CLOSED_PRODUCER_CONFIG')
        C.need(str(m['job_id'])==str(C.meta(entry['proof_reference'])['job_id']),'ORIGINAL_CONFIG_PRODUCER')
        I.allow(cfg,origin=pathlib.Path(cfg['path']).parent);native.ACCEPTED_CONFIG_REFERENCES[cfg['path']]=cfg
    CONTEXT.clear();CONTEXT.update(oldroot=oldroot,prefix=prefix,receipt=receipt,oldproof=oldproof)
    cache.CONTEXT=CONTEXT
    I.save(root/'resume_stage_origin.json',{'schema':'CURRENT_PARENT_READONLY_FAST55K_PARTIAL_CACHE_RESUME_V1',
      'old_C0_partial_receipt_reference':rr,'old_prefix_reference':pr,'old_parent_registration':review['parent_registration'],
      'old_data_or_source_modified':False,'whole_D4_or_Common_accepted':False})
    return pr,prefix,{'output_directory':str(oldroot)},oldproof
class Coverage:
    build=staticmethod(cache.build)
COVERAGE=Coverage()
