"""One original CPU day from closed5494 metadata, with allocated-file accounting."""
import pathlib,types
from . import contract as C,geometry as G
from .resource import SafeIO
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import run as OLD
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL
I=SafeIO()
class ParentIO(SafeIO):
    def new_root(self,path):
        root=pathlib.Path(path);marker=root/'root_prepared_checkpoint.json'
        C.need(root.is_dir() and root.lstat().st_uid==1278 and marker.is_file(),'ONLY_ROOT_PREPARED5494_CHECKPOINT')
        value=I.load(marker)
        C.need(value['schema']=='ROOT_PREPARED5494_METADATA_CHECKPOINT_V1' and value['reviewer']=='root'
          and value['new_output_root']==str(root) and value['old_job_id']=='4525494','EXACT_STAGED5494_OUTPUT')
        C.need({p.name for p in root.iterdir()}=={'actual_input_children','root_prepared_checkpoint.json'}
          and {p.name for p in (root/'actual_input_children').iterdir()}==
            {'geometry.sqlite',*G.PARQUET_IO.COMPLETE,*G.PARQUET_IO.PARTIALS},
          'FRESH_ROOT_EXACT_SIX_CLOSED_DERIVED_FILES')
        return root
def fixtures(root):
    ref=OLD.fixtures(root);I.save(root/'journal_safe_IO_and_prefix_reuse_source_proof.json',G.proof());return ref
def execute(plan,proof,root,gate,budget):
    C.need(G.STATISTICS is OLD.G.STATISTICS and G.ELIGIBILITY is OLD.G.ELIGIBILITY,'ORIGINAL_SCIENCE_OBJECTS')
    f=ORIGINAL.execute;g=dict(f.__globals__,C=C,G=G,I=I,V=G.COVERAGE)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan,proof,root,gate,budget)
def main():
    f=ORIGINAL.main;g=dict(f.__globals__,C=C,G=G,I=ParentIO(),fixtures=fixtures,execute=execute,__file__=__file__)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)()
if __name__=='__main__':raise SystemExit(main())
