"""Metadata AST bridge only: never imports or executes either runtime."""
import argparse,ast,hashlib,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",type=Path,required=True);p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--output",type=Path)
    a=p.parse_args();old_raw=a.original.read_bytes();new_raw=a.candidate.read_bytes()
    old=ast.parse(old_raw);new=ast.parse(new_raw)
    def nodes(tree):return {item.name:item for item in tree.body if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
    left,right=nodes(old),nodes(new);unchanged=[];changed=[];allowed={"sqlite_lock_error","BusyConnection","connection","Queue"}
    for name,item in left.items():
        if name not in right:raise AssertionError("Original symbol removed: "+name)
        same=ast.dump(item,include_attributes=False)==ast.dump(right[name],include_attributes=False)
        (unchanged if same else changed).append(name)
        if not same and name not in allowed:raise AssertionError("Non-metadata AST changed: "+name)
    oldq={m.name:m for m in left["Queue"].body if isinstance(m,ast.FunctionDef)}
    newq={m.name:m for m in right["Queue"].body if isinstance(m,ast.FunctionDef)}
    changed_methods=[]
    for name,item in oldq.items():
        if name not in newq:raise AssertionError("Queue method removed: "+name)
        if ast.dump(item,include_attributes=False)!=ast.dump(newq[name],include_attributes=False):
            changed_methods.append(name)
            if name not in {"__init__","claim","publish_export"}:raise AssertionError("Extra Queue method changed: "+name)
    report={"schema":"WP5_R12_METADATA_AST_BRIDGE_V1","status":"METADATA_ONLY_AST_BRIDGE_PASS",
        "original":{"path":str(a.original),"sha256":hashlib.sha256(old_raw).hexdigest()},
        "candidate":{"path":str(a.candidate),"sha256":hashlib.sha256(new_raw).hexdigest()},
        "unchanged_original_symbols":unchanged,"changed_metadata_symbols":changed,
        "changed_queue_methods":changed_methods,"new_metadata_symbols":sorted(set(right)-set(left)),
        "QM_started":False,"queue_opened":False,"candidate_executed":False}
    text=json.dumps(report,indent=2)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
    print(text)
if __name__=="__main__":main()
