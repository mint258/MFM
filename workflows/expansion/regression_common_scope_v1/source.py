"""Verify the unchanged original common-mask and compact-bit semantics."""
import ast


def need(value,message):
    if not value:raise ValueError(message)


def assignments(function):
    return {node.targets[0].id:node.value for node in ast.walk(function) if isinstance(node,ast.Assign)
      and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)}


def prove(v1,v2,v3,boolean_order):
    trees=[ast.parse(text) for text in (v1,v2,v3)]
    evaluate=next(n for n in trees[0].body if isinstance(n,ast.FunctionDef) and n.name=='evaluate');values=assignments(evaluate)
    expected={'common':'row.get("common_member", True)','old_final':'row["formal_member"] and common','new_final':'predicted_retained and assigned and common'}
    for name,text in expected.items():need(ast.dump(values[name],include_attributes=False)==ast.dump(ast.parse(text,mode='eval').body,include_attributes=False),'ORIGINAL_COMMON_MASK_EXPRESSION:'+name)
    fields=next(ast.literal_eval(n.value) for n in trees[1].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BOOL_FIELDS' for t in n.targets))
    need(list(fields)==boolean_order,'ORIGINAL_V2_BOOLEAN_ORDER_EQUALS_CLOSED_FULL_RECEIPT')
    compact=next(n for n in trees[2].body if isinstance(n,ast.FunctionDef) and n.name=='compact_result')
    value=assignments(compact)['bits'];expected_bits=ast.parse('sum(int(result[k]) << i for i, k in enumerate(BOOL_FIELDS))',mode='eval').body
    need(ast.dump(value,include_attributes=False)==ast.dump(expected_bits,include_attributes=False),'ORIGINAL_COMPACT_BIT_ENCODING')
    return dict(original_common_default=True,old_final_and_common=True,conditional_new_final_and_common=True,
      original_boolean_order=boolean_order,original_compact_bit_encoding_checked=True,new_chemical_evaluator_calls=0)
