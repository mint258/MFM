"""Same-Parent SOURCE-only exact proofs; never an author AST/PASS claim."""
import ast,hashlib,json
from . import contracts as C

def ast_text(text):return ast.dump(ast.parse(text),include_attributes=False)

def reverse(text,deltas):
    for d in reversed(deltas):
        C.need(text.count(d['new'])==d['count'],'EXACT_ONE_DECLARED_IO_SOURCE_REPLACEMENT');text=text.replace(d['new'],d['old'])
    return text

def proof():
    w=C.load(C.HERE/'frozen_sources.json');resource=w['resource'];startup=w['startup'];atoms=w['atoms']
    for row in w['Main_original_Source_witnesses']:
        raw=row['source_text'].encode();ref=row['reference']
        C.need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'ENTIRE_ROOT_SUPPLIED_ORIGINAL_MAIN_SOURCE_WITNESS')
    for ref in w['Alpha_original_resource_references']:C.q.verify(ref)
    controller=(C.HERE/'controller.py').read_text(encoding='utf-8-sig');restored=reverse(controller,resource['controller_replacements'])
    C.need(restored==resource['controller_original_source'] and ast_text(restored)==ast_text(resource['controller_original_source']),
        'ENTIRE_ORIGINAL_V7_CONTROLLER_BYTES_AST_ONLY_EXACT_SCOPE_LITERAL_CHANGED')
    adapter=(C.HERE/'adapters.py').read_text(encoding='utf-8-sig');suffix=adapter[adapter.index('def readonly('):]
    restored=reverse(suffix,resource['adapter_replacements']);C.need(restored==resource['adapter_original_suffix']
        and ast_text(restored)==ast_text(resource['adapter_original_suffix']),'ENTIRE_ORIGINAL_V7_READONLY_AND_STARTUP_PROOF_BYTES_AST')
    contract=(C.HERE/'contracts.py').read_text(encoding='utf-8-sig');current=contract[contract.index('def startup('):]
    C.need(current.endswith(startup['appended_startup_tail']),'EXACT_ADDITIONAL_NORM_PARENT_AND_FINITE_CAP_TAIL')
    restored=reverse(current[:-len(startup['appended_startup_tail'])],startup['replacements'])
    C.need(restored==startup['original_startup_prefix'] and ast_text(restored)==ast_text(startup['original_startup_prefix']),
        'ENTIRE_ORIGINAL_IDENTITY_RESOURCE_STARTUP_PREFIX_BYTES_AST')
    kernel=(C.HERE/'kernel.py').read_text(encoding='utf-8-sig');actual=kernel.split('# ORIGINAL_ATOMS_BEGIN\n',1)[1].split('# ORIGINAL_ATOMS_END',1)[0]
    C.need(actual==atoms['original_atoms_body'] and ast_text(actual)==ast_text(atoms['original_atoms_body']),
        'COMPLETE_ORIGINAL_ATOMS_ONLY_AND_COMPOSITION_FUNCTIONS_BYTES_AST')
    source=ast.parse(atoms['tdc_original_contracts_text']);assignment=[n for n in source.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='PARAMS' for t in n.targets)]
    C.need(len(assignment)==1 and ast.literal_eval(assignment[0].value)==C.PARAMS,'EXACT_ORIGINAL_UNSANITIZED_PARAMS_NO_REPAIR_FLAGS')
    for name,expected in w['frozen_identity_files'].items():
        actual=C.pin(C.HERE/'frozen'/name);C.need((actual['bytes'],actual['sha256'])==(expected['bytes'],expected['sha256']),
            'ENTIRE_ISOLATED_ORIGINAL_STRICT5_SOURCE_ASSET:'+name)
    return {'status':'FULL_BYTE_AST_RESOURCE_SCOPE_INVERSES_ORIGINAL_ATOMS_AND_STRICT5_ASSETS',
      'original_v7_scheduler_and_accounting_unchanged':True,'old_global_code_mutated':False,'new_graph_full_keys':False,
      'new_formula_parser_is_explicit_identity_IO_not_claimed_original_function':True,'DATA_read':False}
