"""Original same-FD reader and stable writer, with this parent's explicit cap."""
import pathlib,threading
from workflows.data_v1_final.pprime.strict20_readback_v1.io import held,body,value,fresh,Store as OriginalStore

class Store(OriginalStore):
    def __init__(self,root,check,cap):
        self.root=pathlib.Path(root);self.charged=0;self.lock=threading.Lock();self.check=check
        self.cap=cap;self.reserve=256<<20;self.references=[]
    def write(self,path,body,*,failure=False):
        ref=super().write(path,body,failure=failure)
        with self.lock:self.references.append(ref)
        return ref
