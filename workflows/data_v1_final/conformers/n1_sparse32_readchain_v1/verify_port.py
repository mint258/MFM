"""Source-only proof: original sources are loaded, rather than science rewritten."""
from __future__ import annotations
import argparse,ast,json,pathlib
from . import common as U
from .signatures import canonical,sha

def verify(catalog_reference):
    catalog=U.load(catalog_reference);refs=catalog['references']
    sources={'common':refs['io'],'legacy':refs['graph_stereo_rmsd'],'prepare':refs['legacy_prepare_import']}
    source_refs={name:U.pin(U.require(ref,True),True) for name,ref in sources.items()}
    here=pathlib.Path(__file__).absolute().parent;new={path.name:U.pin(path,True) for path in here.iterdir() if path.suffix in ('.py','.md')}
    trees={name:ast.parse(U.require(ref,True).read_text(encoding='utf-8')) for name,ref in new.items() if name.endswith('.py')}
    assignments=[];forbidden=[]
    for name,tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name) and target.value.id in {'legacy','original','core','science'}:
                        assignments.append({'file':name,'target':ast.unparse(target)})
            if isinstance(node,ast.Call):
                fn=ast.unparse(node.func)
                if fn in {'pickle.dump','pickle.dumps'} or any(word in fn for word in ('UFFOptimize','UFFGetMoleculeForceField','EmbedMolecule','MinimizeTrajectory')):
                    forbidden.append({'file':name,'call':fn})
    U.need(not assignments and not forbidden,'NO_FROZEN_GLOBAL_MONKEYPATCH_REPICKLE_OR_NATIVE_GENERATION_CALLS')
    tree=trees['source.py'];functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    read_calls=[ast.unparse(n.func) for n in ast.walk(functions['read_one']) if isinstance(n,ast.Call)]
    U.need("WORK['legacy'].read" in read_calls,'ACTUAL_ORIGINAL_READ_CALL_NOT_A_REPLACEMENT')
    original_tree=ast.parse(U.require(sources['legacy'],True).read_text(encoding='utf-8'))
    original_functions={n.name:n for n in original_tree.body if isinstance(n,ast.FunctionDef)}
    names=('read','graph','fix_stereo','ordered_graph','worker_init')
    return {'schema':'N1_SPARSE32_READCHAIN_SOURCE_ONLY_PROOF_V1','status':'PASS_SOURCE_ONLY_NOT_ACTUAL_READ_ACCEPTANCE',
        'catalog_reference':catalog_reference,'frozen_original_sources':source_refs,'new_sources':new,
        'original_function_AST_sha256':{name:sha(ast.dump(original_functions[name],include_attributes=False).encode()) for name in names},
        'original_sources_rewritten':False,'science_functions_copied_and_modified':False,'original_read_call_present':True,
        'frozen_module_attribute_assignments':assignments,'repickle_or_native_generation_calls':forbidden,
        'deployment_verification':'Main export and Alpha startup require full source-file bytes/SHA equality; only separate recipe source locator paths/output root change',
        'actual_LMDB_or_pickle_body_read':False,'actual_synthetic_tests_run':False,'actual_Alpha_field_equality_proven':False,
        'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--catalog',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path)
    args=parser.parse_args();report=verify(U.pin(args.catalog,True));print(json.dumps(U.save(args.output,report)))

if __name__=='__main__':main()
