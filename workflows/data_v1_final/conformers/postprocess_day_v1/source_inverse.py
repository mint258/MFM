"""Actual CPU only: inverse complete bodies and direct scientific object proofs."""
import ast,inspect,pathlib
from . import contract as C,common,math_bridge,worker
from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import finalize as ORIGINAL
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import inheritance as H
from workflows.data_v1_final.conformers.pm7_multinode_compat32_v1.compute import inverse_proof
COMMON_EDITS=[
    "def finalize_common(args,value,proof,config_reference):",
    "def build(ctx,index_reference):",
    "    a=args;index_reference=R.input_ref(args.root_preflight,args.completion_index);index=C.read(index_reference)",
    "    value,proof,config_reference,IO=ctx.value,ctx.proof,ctx.plan[\u0027original_config_reference\u0027],ctx\n    a=ctx.args;index=ctx.read(index_reference);a.completion_index=Path(index_reference[\u0027path\u0027])",
    "\u0027cpus\u0027:16",
    "\u0027cpus\u0027:ctx.cpus",
    "index[\"schema\"]==C.SCHEMAS[\"completion\"]",
    "index[\"schema\"]==\"PACKED_SPRIME_EXACT_OUTCOME_INDEX_V1\"",
    "R.authorized(proof,",
    "ctx.authorized(",
    "with cf.ThreadPoolExecutor(max_workers=16) as pool:",
    "with cf.ThreadPoolExecutor(max_workers=ctx.cpus) as pool:",
    "pool.map(normalize_package,source_refs)",
    "pool.map(lambda ref:normalize_package(ref,value),source_refs)",
    "binding=attempt_binding(packet,value,imports_by_id)",
    "binding=ctx.attempt_binding(packet,value,imports_by_id)",
    "roles_ref,role_refs=authority_roles(value)",
    "roles_ref,role_refs=ctx.roles(value)",
    "db.execute(\"SET threads=16\")",
    "db.execute(\"SET threads=\"+str(ctx.cpus))",
    "out=R.OUT",
    "out=ctx.common_out",
    "formal=M.formal_source(value,proof,args.source_mapping_review)",
    "formal=ctx.formal_reference",
    "max_workers=16,mp_context",
    "max_workers=ctx.cpus,mp_context",
    "\"schema\":\"COMMON_POPULATION_V1_FROZEN\",\"status\":\"COMMON_POPULATION_V1_FROZEN\"",
    "\"schema\":\"COMMON_POPULATION_PRODUCER_V1\",\"status\":\"PENDING_ACTUAL_PARENT_C0_AND_INDEPENDENT_ROOT_REVIEW\""
]
WORKER_EDITS=[
    "def process_molecule(task):",
    "def d7(task,cache,science):",
    "raw = {rid: SCIENCE.read(row) for rid, row in by_record.items()}\n    anchor = raw[next(iter(anchors))]",
    "anchor = science.read(by_record[next(iter(anchors))])",
    "for rid in sorted(raw):\n        other, z, coordinates = SCIENCE.graph(raw[rid])\n        if not np.array_equal(numbers, z) or SCIENCE.ordered_graph(other) != graph_signature:\n            raise ValueError(\"D7_SOURCE_GRAPH_OR_ATOM_SEQUENCE_MISMATCH\")\n        hof = task[\"hof\"][rid]\n        pm7.append({\"conformer_id\": rid, \"coordinates\": coordinates.tolist(),\n                    \"energy\": hof[\"value_kcal_mol\"] if hof[\"valid\"] else None,\n                    \"geometry_sha256\": IO.geometry_sha(numbers, coordinates)})",
    "cached={row[\u0027conformer_id\u0027]:row for row in cache[\u0027pm7\u0027]}\n    C.need(set(cached)==set(by_record) and cache[\u0027atomic_numbers\u0027]==numbers.tolist()\n      and cache[\u0027atom_order_sha256\u0027]==atom_sha and cache[\u0027graph_sha256\u0027]==C.F.sha_value(graph_signature),\n      \u0027EXACT_ALREADY_VALIDATED_PM7_NATIVE_RECORD_GRAPH_ATOMS\u0027)\n    for rid in sorted(cached):\n        row=cached[rid];hof=task[\u0027hof\u0027][rid]\n        C.need(IO.geometry_sha(numbers,row[\u0027coordinates\u0027])==row[\u0027geometry_sha256\u0027]\n          and row[\u0027energy\u0027]==(hof[\u0027value_kcal_mol\u0027] if hof[\u0027valid\u0027] else None),\u0027EXACT_CACHED_FLOAT64_GEOMETRY_AND_CANONICAL_HOF\u0027)\n        pm7.append(row)",
    "orders = {\"pm7\": geometry_orders(pm7, distance, mid, \"pm7\"),\n              \"uff_sprime\": geometry_orders(uff, distance, mid, \"uff_sprime\")}\n    unique = {\"pm7\": unique_representatives(pm7, orders[\"pm7\"][\"fixed_random\"], distance),\n              \"uff_sprime\": unique_representatives(uff, orders[\"uff_sprime\"][\"fixed_random\"], distance)}",
    "orders = {\"pm7\": cache[\u0027orders\u0027],\n              \"uff_sprime\": geometry_orders(uff, distance, mid, \"uff_sprime\")}\n    unique = {\"pm7\": cache[\u0027unique_representatives\u0027],\n              \"uff_sprime\": unique_representatives(uff, orders[\"uff_sprime\"][\"fixed_random\"], distance)}",
    "SCIENCE.",
    "science."
]

def function(text,name):
    tree=ast.parse(text);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
    C.need(len(nodes)==1,'ONE_EXACT_SOURCE_FUNCTION:'+name);n=nodes[0]
    return ''.join(text.splitlines(keepends=True)[n.lineno-1:n.end_lineno]).strip()
def edited(text,edits):
    C.need(len(edits)%2==0,'FINITE_EXPLICIT_CONTEXT_EDIT_PAIRS')
    for old,new in zip(edits[::2],edits[1::2]):C.need(old in text,'EXACT_SOURCE_CONTEXT_DELTA_PRESENT:'+old);text=text.replace(old,new)
    return text

def proof():
    old=pathlib.Path(ORIGINAL.__file__).read_text();new=pathlib.Path(common.__file__).read_text();oldbody=function(old,'finalize_common');newbody=function(new,'build')
    C.need(edited(oldbody,COMMON_EDITS)==newbody,'FULL_ORIGINAL_COMMON_BODY_ONLY_ENUMERATED_CONTEXT_METADATA_DELTAS')
    restored=newbody
    for before,after in reversed(list(zip(COMMON_EDITS[::2],COMMON_EDITS[1::2]))):restored=restored.replace(after,before)
    C.need(restored==oldbody and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(oldbody),include_attributes=False),'FULL_COMMON_SOURCE_AND_AST_INVERSE')
    for name in ('merge_counts','membership','exclusion_gates','scaffold_chunk'):C.need(getattr(math_bridge,name) is getattr(ORIGINAL,name),'DIRECT_ORIGINAL_PURE_FINALIZER_OBJECT:'+name)
    norm=function(pathlib.Path(math_bridge.__file__).read_text(),'normalize_package')
    expected=function(old,'normalize_package').replace('def normalize_package(ref):','def normalize_package(ref,value):').replace('packet=R.read_packet(ref,R.VALUE)','packet=R.read_packet(ref,value)')
    C.need(norm==expected,'ONLY_EXPLICIT_PACKET_READER_CONFIG_ARGUMENT')
    profile=(H.C.PROFILE/'run_profile.py').read_text();d7=function(profile,'process_molecule');newd7=function(pathlib.Path(worker.__file__).read_text(),'d7')
    C.need(edited(d7,WORKER_EDITS)==newd7,'FULL_D7_BODY_ONLY_EXPLICIT_CONTEXT_AND_VERIFIED_PM7_CACHE_REUSE')
    tree=ast.parse(pathlib.Path(worker.__file__).read_text());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
      and n.func.attr in ('process_task','EmbedMultipleConfs','UFFGetMoleculeForceField','MinimizeTrajectory','invoke')]
    C.need(not calls,'NO_GEOMETRY_GENERATION_OPTIMIZATION_OR_QM_IN_POSTPROCESS')
    return {'status':'ACTUAL_SOURCE_FULL_INVERSE_AND_DIRECT_OBJECTS','common_complete_inverse_bytes_AST':True,
      'old_common_math_SQL_merge_exclusion_sparse_physical_ID_logic_unchanged':True,'packet_reader_only_explicit_value':True,
      'D7_only_local_science_context_and_previously_verified_PM7_record_matrix_reuse':True,'old_pm7_source_inheritance':H.proof(),
      'pm7_context_inverse':inverse_proof(),'original_parent64_and_old_parent16_both_truthful':True,'Root_release_or_DATA_read_claimed':False}
