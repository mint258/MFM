"""Temporary bare-name isolation for the original P-prime bootstrap only."""
import contextlib,pathlib,sys


@contextlib.contextmanager
def pprime_bootstrap(repository,*,native_engine=False):
    root=pathlib.Path(repository)/'workflows/data_v1_final/pprime'
    # These are the actual bare imports of formal_common.prepare_v1/common_v1,
    # close_pilot and retention_policy_v1/prepare_pilot. Existing unrelated
    # modules (including conformers.common) are put back exactly afterward.
    names=('common','common_v1','close_pilot','prepare_pilot','retention_policy_v1')
    if native_engine:
        # Pprime.common.load_engine itself inserts the frozen WP5 engine source
        # directory. Do not force a Pprime module into the native WP5 namespace.
        # Native/WIRE lifecycle modules are imported by original pinned paths;
        # these four are WP5's actual bare imports and retain their own globals.
        names+=('wp5_archive_v5','wp5_archive_v4','wp5_scf_metadata_v2','wp5_registry_coverage_v2')
    absent=object();previous={name:sys.modules.get(name,absent)for name in names};paths=list(sys.path)
    try:
        for name in names:sys.modules.pop(name,None)
        sys.path[:0]=[str(root/'formal_common_v1'),str(root),str(root/'retention_v1')]
        yield
    finally:
        for name,value in previous.items():
            if value is absent:sys.modules.pop(name,None)
            else:sys.modules[name]=value
        sys.path[:]=paths