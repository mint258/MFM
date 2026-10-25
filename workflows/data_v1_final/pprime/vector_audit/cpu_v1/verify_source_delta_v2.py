"""Stdlib-only frozen-v1 to visible-v2 inverse proof; never execute science."""
from __future__ import annotations
import argparse,ast,hashlib,json,pathlib
from verify_source_delta_v1 import verify as verify_original_to_v1

RUNTIME_PATH='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/cpu_analysis_v1/runtime_v2.py'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def require(value,message):
    if not value:
        raise ValueError(message)

def reference(path,raw):
    return {'path':str(path.absolute()),'bytes':len(raw),'sha256':sha(raw)}

def pinned_bytes(pin):
    raw=pathlib.Path(pin['path']).read_bytes()
    require(len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],
            'FROZEN_V1_REFERENCE_CHANGED:'+pin['path'])
    return raw

def functions(text):
    return {node.name:node for node in ast.walk(ast.parse(text))
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}

def exact_functions(old,new,names):
    before,after=functions(old),functions(new)
    rows=[]
    for name in names:
        require(name in before and name in after,'FUNCTION_MISSING:'+name)
        require(ast.dump(before[name],include_attributes=False)==
                ast.dump(after[name],include_attributes=False),
                'DIRECT_FUNCTION_AST_DIFFERS:'+name)
        require(ast.get_source_segment(old,before[name])==
                ast.get_source_segment(new,after[name]),
                'FUNCTION_SOURCE_BYTES_DIFFER:'+name)
        rows.append({'name':name,'original_source_bytes_identical':True,
                     'direct_AST_identical_without_control_removal':True})
    return rows

def verify(directory):
    directory=pathlib.Path(directory)
    repo=directory.parents[4]
    mapping=json.loads((directory/'edits_v2.json').read_bytes())
    require(mapping['schema']=='VECTOR_PREPARE_CPU_RUNTIME_DELTA_V2' and
            mapping['scope_key']=='vector_prepare_1000','EXACT_V2_DELTA_REQUIRED')
    for pin in mapping['unchanged_v1_references']:
        pinned_bytes(pin)
    rows=[]
    texts={}
    for variant in mapping['files']:
        pin=variant['baseline']
        old_raw=pinned_bytes(pin)
        candidate=repo/variant['candidate_relative_path']
        new_raw=candidate.read_bytes()
        old,new=old_raw.decode('utf-8'),new_raw.decode('utf-8')
        forward=old
        for edit in variant['edits']:
            require(edit['old'] and edit['new'] and
                    forward.count(edit['old'])==edit['occurrences'],
                    'DECLARED_FORWARD_ANCHOR_DIFFERS:'+edit['reason'])
            forward=forward.replace(edit['old'],edit['new'])
        require(forward.encode('utf-8')==new_raw,
                'UNDECLARED_V2_EDIT:'+str(candidate))
        reverse=new
        for edit in reversed(variant['edits']):
            require(reverse.count(edit['new'])==edit['occurrences'],
                    'DECLARED_REVERSE_ANCHOR_DIFFERS:'+edit['reason'])
            reverse=reverse.replace(edit['new'],edit['old'])
        require(reverse.encode('utf-8')==old_raw,
                'V2_INVERSE_FULL_FILE_BYTES_DIFFER:'+str(candidate))
        rows.append({'baseline_reference':pin,
                     'candidate_reference':reference(candidate,new_raw),
                     'forward_declared_edit_bytes_equal':True,
                     'inverse_full_file_bytes_equal':True})
        texts[candidate.name]=(old,new)
    require(set(texts)=={'prepare_cpu_v2.py','runtime_control_v2.py',
                        'vector_prepare_cpu_v2.json','test_cpu_boundary_v2.py'},
            'ONLY_THE_FOUR_DECLARED_V2_VARIANTS_ALLOWED')
    science=exact_functions(*texts['prepare_cpu_v2.py'],
                            mapping['science_functions'])
    controls=exact_functions(*texts['runtime_control_v2.py'],
                             ['checkpoint_iter','source_lineage','prepared_authority'])
    old_test,new_test=texts['test_cpu_boundary_v2.py']
    tests=[name for name in functions(old_test) if name.startswith('test_')]
    require(len(tests)==3,'ONLY_ORIGINAL_THREE_INCREMENTAL_BOUNDARIES')
    exact_functions(old_test,new_test,tests)
    old_metadata,new_metadata=map(json.loads,texts['vector_prepare_cpu_v2.json'])
    require(new_metadata.pop('runtime_path')==RUNTIME_PATH,
            'EXACT_V2_RUNTIME_METADATA_PATH_REQUIRED')
    require(old_metadata==new_metadata,
            'SCIENTIFIC_METADATA_OR_RESOURCE_ENVELOPE_CHANGED')
    original=verify_original_to_v1(directory)
    require(original['status']=='PASS','ORIGINAL_TO_V1_PROOF_REQUIRED')
    return {'schema':'VECTOR_PREPARE_CPU_RUNTIME_SOURCE_EQUIVALENCE_V2',
            'status':'PASS','variants':rows,
            'forward_declared_edit_bytes_equal':True,
            'inverse_full_file_bytes_equal':True,
            'unchanged_v1_reference_count':len(mapping['unchanged_v1_references']),
            'science_functions':science,'unchanged_control_functions':controls,
            'three_boundary_test_methods_source_and_AST_identical':True,
            'metadata_identical_except_runtime_path':True,
            'original_to_v1_source_proof':original,
            'scientific_modules_imported':[],
            'scientific_functions_executed':False,'data_bodies_read':False,
            'limits':'Source proof only. Actual v2 CPU allocation, three boundaries, rendered inputs, sixteen worker TIDs and durable monitor closure require Root evidence.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=pathlib.Path,
                        default=pathlib.Path(__file__).parent)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    result=verify(args.directory)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))

if __name__=='__main__':
    main()
