"""Unchanged chemistry package plus original audit/funnel/typed serialization."""
import ast,copy,hashlib,json,os,time,traceback
from pathlib import Path
from types import SimpleNamespace
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C
from .runtime import Stop
shared=SimpleNamespace(need=Q.need)
files=SimpleNamespace(CooperativeStop=Stop)
STOP=None
INITIALIZATION={}

def initialize(stop,barrier,log_root=None):
    global STOP,INITIALIZATION
    STOP=stop;began=time.monotonic();cpu=time.process_time()
    if log_root is not None:
        directory=Q.literal(log_root);directory.mkdir(parents=True,exist_ok=True)
        path=directory/('worker_%d.log'%os.getpid());fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
    from pubchem_science_frozen_v1 import features_legacy_compatible_v2 as compatible
    compatible.rdkit_modules()
    INITIALIZATION={'pid':os.getpid(),'elapsed_seconds':time.monotonic()-began,'CPU_seconds':time.process_time()-cpu,'chemical':True}
    barrier.wait(timeout=180)
FLOAT_FEATURES = ("molecular_weight_Da", "tpsa_A2", "logp")
INT_FEATURES = ("heavy_atoms", "isotopic_atoms", "rings", "aromatic_rings", "rotatable_bonds", "hbd", "hba", "stereocenters")
TEXT_FEATURES = ("isomeric_smiles", "full_key", "wp5_key", "non_h_composition", "element_combination", "generic_murcko", "ecfp4_2048_hex")
FEATURE_KEYS = {"cid", "ordinal", "reasons", "source_smiles", "elements", "generic_ring_systems",
                *FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES}

def funnel(result, audit_flags, audit_parse, errors, original):
    """Preserve legacy reasons; undefined parse X bits never become false flags."""
    codes = list(errors)
    if not isinstance(result, dict) or type(result.get("reasons")) is not list:
        return "technicalUnresolved", [*codes, "DISPATCHER_RESULT_OR_REASONS_UNAVAILABLE"]
    if result.get("cid") != int(original["cid_source_ascii"]) or result.get("ordinal") != original["ordinal"]:
        codes.append("DISPATCHER_SOURCE_IDENTITY_MISMATCH")
    reasons = result["reasons"]
    full_boolean_audit = set(audit_flags) == {"X01", "X02", "X03", "X04", "X05"} and all(
        type(value) is bool for value in audit_flags.values())
    if reasons and all(reason in ("X01", "X02", "X03", "X04", "X05") for reason in reasons):
        expected = [name for name in ("X01", "X02", "X03", "X04", "X05") if audit_flags.get(name) is True]
        if audit_parse is not True or not full_boolean_audit or reasons != expected:
            codes.append("AUDIT_DISPATCHER_X_REASONS_CONFLICT")
        return ("technicalUnresolved", codes) if codes else ("chemReject", [])
    if reasons:
        return "technicalUnresolved", [*codes, "LEGACY_NON_X_REASON_PRESERVED:" + ",".join(map(str, reasons))]
    if audit_parse is not True or not full_boolean_audit or any(audit_flags.values()):
        codes.append("AUDIT_DISPATCHER_PARSE_OR_X_CONFLICT")
    if set(result) != FEATURE_KEYS or result.get("source_smiles") != original["source_smiles"]:
        codes.append("FULL_FEATURE_OR_SOURCE_FIELDS_DIFFER")
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError):
        codes.append("NONFINITE_OR_NONJSON_FEATURE_RESULT")
    return ("technicalUnresolved", codes) if codes else ("accepted", [])

def chemical_task(original):
    if STOP.is_set():
        raise files.CooperativeStop("STOP_BEFORE_NEXT_CHEMICAL_RECORD")
    from pubchem_science_frozen_v1 import features_legacy_compatible_v2 as compatible
    audit_flags, audit_parse, result, errors = {}, None, None, {}
    started, cpu = time.monotonic(), time.process_time()
    try:
        # The frozen signature is chemical_flags(smiles: str), not a Mol.
        molecule, audit_flags = compatible.chemical_flags(original["source_smiles"])
        audit_parse = molecule is not None
        del molecule
    except Exception as exc:
        errors["INDEPENDENT_X_AUDIT_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    audit_wall, audit_cpu = time.monotonic() - started, time.process_time() - cpu
    started, cpu = time.monotonic(), time.process_time()
    try:
        # This exact597 wrapper already includes original parse/X via legacy features.
        result = compatible.features_candidate(int(original["cid_source_ascii"]), original["source_smiles"], original["ordinal"])
    except Exception as exc:
        errors["COMPATIBLE_DISPATCHER_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    dispatch_wall, dispatch_cpu = time.monotonic() - started, time.process_time() - cpu
    category, codes = funnel(result, audit_flags, audit_parse, errors, original)
    value = {"input": original, "category": category, "technical_codes": codes,
        "audit_parse_succeeded": audit_parse, "audit_flags": audit_flags,
        "legacy_dispatcher_result": result, "errors": errors,
        "audit_wall_seconds": audit_wall, "audit_CPU_seconds": audit_cpu,
        "dispatcher_wall_seconds_includes_legacy_X_parse": dispatch_wall,
        "dispatcher_CPU_seconds_includes_legacy_X_parse": dispatch_cpu,
        "worker_pid": os.getpid(), "worker_initialization": INITIALIZATION}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=True).encode()
    shared.need(len(raw) <= C.CONTAINER_CAP // 32, "RESULT_CONTAINER_STOP_NO_FEATURE_TRUNCATION")
    return value

def output_schema():
    import pyarrow as pa
    fields = [(name, pa.string()) for name in ("sample_group", "cid_source_ascii", "source_smiles", "source_smiles_sha256",
        "source_part_reference_json", "category", "audit_flags_json", "full_dispatcher_result_json", "error_evidence_json")]
    fields += [("ordinal", pa.int64()), ("worker_pid", pa.int64()), ("audit_parse_succeeded", pa.bool_()),
        ("technical_codes", pa.list_(pa.string())), ("legacy_reasons", pa.list_(pa.string()))]
    fields += [("audit_" + name, pa.bool_()) for name in ("X01", "X02", "X03", "X04", "X05")]
    fields += [(name, pa.float64()) for name in (*FLOAT_FEATURES, "audit_wall_seconds", "audit_CPU_seconds",
        "dispatcher_wall_seconds_includes_legacy_X_parse", "dispatcher_CPU_seconds_includes_legacy_X_parse")]
    fields += [(name, pa.int64()) for name in INT_FEATURES] + [(name, pa.string()) for name in TEXT_FEATURES]
    fields += [("elements", pa.list_(pa.int32())), ("generic_ring_systems", pa.list_(pa.string()))]
    return pa.schema(fields)


def parquet_row(value, group):
    original, feature = value["input"], value["legacy_dispatcher_result"] or {}
    encoded = {"sample_group": group, "ordinal": original["ordinal"], "cid_source_ascii": original["cid_source_ascii"],
        "source_smiles": original["source_smiles"], "source_smiles_sha256": original["source_smiles_sha256"],
        "source_part_reference_json": json.dumps(original["source_part"], sort_keys=True), "category": value["category"],
        "audit_parse_succeeded": value["audit_parse_succeeded"], "audit_flags_json": json.dumps(value["audit_flags"], sort_keys=True),
        "technical_codes": value["technical_codes"], "legacy_reasons": feature.get("reasons"),
        "full_dispatcher_result_json": json.dumps(value["legacy_dispatcher_result"], ensure_ascii=False, allow_nan=True),
        "error_evidence_json": json.dumps(value["errors"], ensure_ascii=False), "worker_pid": value["worker_pid"]}
    for name in ("X01", "X02", "X03", "X04", "X05"):
        encoded["audit_" + name] = value["audit_flags"].get(name)
    for name in (*FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES, "elements", "generic_ring_systems"):
        encoded[name] = feature.get(name)
    for name in ("audit_wall_seconds", "audit_CPU_seconds", "dispatcher_wall_seconds_includes_legacy_X_parse",
                 "dispatcher_CPU_seconds_includes_legacy_X_parse"):
        encoded[name] = value[name]
    return encoded

def verify_source(plan):
    from pubchem_science_frozen_v1 import features_legacy_compatible_v2 as compatible,screen,common,features_generic_candidate_v1 as generic
    manifest=Q.load_ref(plan['frozen_manifest_reference'])
    for row in manifest['files']:
        observed=Q.ref(row['target_reference']['path']);Q.need(observed==row['target_reference']
            and all(observed[k]==row['origin_reference'][k] for k in ('bytes','sha256')),'EXACT_ORIGINAL_SOURCE_BYTES_REQUIRED')
    for module,name in ((compatible,'features_legacy_compatible_v2.py'),(screen,'screen.py'),(common,'common.py'),(generic,'features_generic_candidate_v1.py')):
        Q.need(Path(module.__file__).absolute()==C.FROZEN/name,'EXACT_ISOLATED_FROZEN_SOURCE_PACKAGE_REQUIRED')
    proof=compatible.source_scope_proof();normalized=copy.deepcopy(proof)
    Q.need(normalized['frozen_old_ring_site']['path']==str(C.FROZEN/'screen.py'),'ONLY_DECLARED_PROOF_METADATA_PATH_RELOCATION')
    normalized['frozen_old_ring_site']['path']=manifest['original_module_root']+'/screen.py'
    prior=Q.load_ref(plan['main_evidence_references']['compat597'])
    Q.need(prior['job_id']=='4520597' and normalized==prior['source_scope_proof'],'ACTUAL597_COMPOSITIONAL_PROOF_METADATA_EQUIVALENCE_REQUIRED')
    old=ast.parse((C.FROZEN/'raw_uniform_cost_source.py').read_text());new=ast.parse(Path(__file__).read_text())
    originals={node.name:node for node in old.body if isinstance(node,ast.FunctionDef)}
    current={node.name:node for node in new.body if isinstance(node,ast.FunctionDef)}
    for name in ('funnel','output_schema','parquet_row'):
        Q.need(ast.dump(originals[name],include_attributes=False)==ast.dump(current[name],include_attributes=False),'ORIGINAL_FUNNEL_AND_TYPED_SERIALIZATION_AST_UNCHANGED:'+name)
    rewritten=ast.parse(ast.unparse(current['chemical_task']).replace('from pubchem_science_frozen_v1 import features_legacy_compatible_v2 as compatible',
        'from .. import features_legacy_compatible_v2 as compatible').replace('C.CONTAINER_CAP // 32','policy.CONTAINER_CAP // policy.PENDING')).body[0]
    Q.need(ast.dump(originals['chemical_task'],include_attributes=False)==ast.dump(rewritten,include_attributes=False),'CHEMICAL_TASK_ONLY_IMPORT_AND_RESOURCE_ALIAS_CHANGE')
    return {'status':'EXACT_ORIGINAL_SOURCE_COPY_AND597_DISPATCH_PROOF','actual_Alpha_source_scope_proof':proof,
        'Main_comparable_proof_metadata':normalized,'scientific_source_bytes_modified':False,'cross_host_object_identity_claimed':False,
        'within_Alpha_old_success_returns_original_object':True,'other_exceptions_not_caught_by_fallback':True,
        'task_alias_changes_only':['relative chemistry import uses isolated byte-identical package','same 1GiB/32pending container resource aliases'],
        'repair_applied':False,'pool_modified':False}
