"""One original day allocation, continuing the closed5455 SQLite prefix."""
import pathlib,types
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v7 import run as OLD
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL
I=OLD.I

class ParentIO:
    def __getattr__(self,name):return getattr(I,name)
    def new_root(self,path):
        root=pathlib.Path(path)
        marker=root/'root_prepared_checkpoint.json'
        C.need(root.is_dir() and root.lstat().st_uid==1278 and marker.is_file(),
          'ONLY_ROOT_PREPARED_SINGLE_CHECKPOINT_OUTPUT')
        value=I.load(marker)
        C.need(value['schema']=='ROOT_PREPARED5455_METADATA_CHECKPOINT_V1'
          and value['reviewer']=='root' and value['new_output_root']==str(root)
          and value['old_job_id']=='4525455','EXACT_STAGED_OUTPUT_OWNER')
        C.need({p.name for p in root.iterdir()}=={'actual_input_children','root_prepared_checkpoint.json'}
          and {p.name for p in (root/'actual_input_children').iterdir()}=={'geometry.sqlite'},
          'NO_OLD_RUN_OR_AMBIGUOUS_OUTPUT_REPLAY')
        return root

def fixtures(root):
    ref=OLD.fixtures(root)
    I.save(root/'checkpoint_resume_source_proof.json',G.proof())
    return ref
def execute(plan,proof,root,gate,budget):
    C.need(G.STATISTICS is OLD.G.STATISTICS and G.ELIGIBILITY is OLD.G.ELIGIBILITY,
      'ORIGINAL_STATS_ELIGIBILITY_OBJECTS_UNCHANGED')
    f=ORIGINAL.execute;g=dict(f.__globals__,C=C,G=G,V=G.COVERAGE)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan,proof,root,gate,budget)
def main():
    f=ORIGINAL.main;g=dict(f.__globals__,C=C,G=G,I=ParentIO(),fixtures=fixtures,
      execute=execute,__file__=__file__)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)()
if __name__=='__main__':raise SystemExit(main())
