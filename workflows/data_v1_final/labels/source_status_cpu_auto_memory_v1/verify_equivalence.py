"""Stdlib inverse-byte and AST proof; does not import producers or read science."""
from __future__ import annotations
import argparse, ast, hashlib, json
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository')
OLD='workflows/data_v1_final/labels/source_status_v1'
NEW='workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1'

def pin(path):
    raw=path.read_bytes()
    if len(raw)>2<<20:raise ValueError('SOURCE_PIN_TOO_LARGE')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def function(source,name):
    node=next(x for x in ast.parse(source).body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name)
    return node, ''.join(source.splitlines(keepends=True)[node.lineno-1:node.end_lineno])

def inverse(old,new,name):
    if name=='support.py':
        for target in ('guard','rss'):
            _,original=function(old,target);_,changed=function(new,target)
            if new.count(changed)!=1:raise ValueError('AMBIGUOUS_RESOURCE_FUNCTION')
            new=new.replace(changed,original,1)
    elif name=='scan.py':
        prefix='from .resource_runtime import run_file_pool\n'
        if new.count(prefix)!=1:raise ValueError('RESOURCE_IMPORT_COUNT')
        new=new.replace(prefix,'',1)
        start=old.index('        with concurrent.futures.ProcessPoolExecutor(')
        end=old.index('        need(len(receipts)==len(items)',start)
        call='        run_file_pool(items,cfg,str(index),raw,names,stop,barrier,receipts,initialize,scan_file)\n'
        if new.count(call)!=1:raise ValueError('RESOURCE_DISPATCH_CALL_COUNT')
        new=new.replace(call,old[start:end],1)
    return new

def verify(repository):
    result=[]
    for name in ('prepare.py','scan.py','reduce.py','support.py'):
        oldpath=repository/OLD/name;newpath=repository/NEW/name
        before=oldpath.read_bytes();after=newpath.read_bytes();old=before.decode();new=after.decode()
        restored=inverse(old,new,name)
        if restored.encode()!=before:raise ValueError('INVERSE_FULL_BYTES_DIFFER:'+name)
        if ast.dump(ast.parse(restored),include_attributes=False)!=ast.dump(ast.parse(old),include_attributes=False):raise ValueError('INVERSE_AST_DIFFER:'+name)
        exemptions={'support.py':{'guard','rss'},'scan.py':{'run'}}.get(name,set())
        direct=[]
        for node in ast.parse(old).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name not in exemptions:
                newnode,_=function(new,node.name)
                if ast.dump(node,include_attributes=False)!=ast.dump(newnode,include_attributes=False):raise ValueError('NONRESOURCE_FUNCTION_AST_DIFFER:'+name+':'+node.name)
                direct.append(node.name)
        result.append({'old':pin(oldpath),'new':pin(newpath),'inverse_full_bytes_equal':True,'inverse_full_AST_equal':True,
            'actual_file_bytes_equal':before==after,'directly_identical_function_AST':direct,
            'actual_AST_resource_exemptions':sorted(exemptions)})
    return {'schema':'SOURCE_STATUS_CPU_AUTO_MEMORY_EQUIVALENCE_V1','status':'PASS','sources':result,
      'actual_all_AST_identical_claimed':False,'changes':['support.guard: new v2 startup API and real memory observer','support.rss: same worker software cap, latched new-dispatch STOP instead of abort','scan.run: only bounded dispatch/drain block and its import'],
      'mathematical_label_schema_selection_and_statistical_functions_changed':False,
      'old_semantic_fixtures_cloned_or_rerun':False,'scientific_data_bodies_read':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.repository!=ROOT:raise ValueError('ACTUAL_ROOT_REPOSITORY_REQUIRED')
    result=verify(a.repository)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'status':result['status'],'files':len(result['sources'])}))
if __name__=='__main__':main()