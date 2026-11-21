"""Recover an empty failed feature producer without changing downstream model identities."""
import ast
import copy
import re

TERMINAL_FAILURES=frozenset({"FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED","DEADLINE"})
ORIGINAL_FEATURE_JOB=4537149
NAMESPACE="C1_Pprime_reference_features/job_4537149"
META_KEYS=frozenset({"original_feature_job","output_namespace_job","native_producer_identity_is_report_job","recovery_declaration"})

def continuation_decision(state,exit_code,output_exists):
    state=state.split()[0].rstrip("+")
    if state=="COMPLETED":
        if exit_code!="0:0":raise ValueError("A successful producer requires actual zero native exit")
        return "NO_OP_SUCCESS"
    if state not in TERMINAL_FAILURES:raise ValueError("Never retry an active or unknown producer")
    return "PARTIAL_OUTPUT_REQUIRES_SCOPED_RECOVERY" if output_exists else "RETRY_EMPTY_FAILED_OUTPUT"

def _body(raw):
    if not raw.startswith("#!"):raise ValueError("A captured raw native batch source is required")
    return raw.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]

def prepare_legacy_namespace_continuation(raw):
    body=_body(raw);tree=ast.parse(body)
    if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
           and n.func.attr in {"fit","predict","predict_proba","create_default_for_version"}
           for n in ast.walk(tree)):
        raise ValueError("This recovery is for feature preparation, never a fitted model")
    outputs=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=="out" for t in n.targets)]
    reports=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=="report" for t in n.targets)]
    if len(outputs)!=1 or len(reports)!=1:raise ValueError("One original output and producer report required")
    out=outputs[0];report=reports[0]
    expected=ast.parse("b1/'C1_Pprime_reference_features'/('job_'+os.environ['SLURM_JOB_ID'])",mode="eval").body
    if ast.dump(out.value)!=ast.dump(expected):raise ValueError("The original feature output route differs")
    if (not isinstance(report.value,ast.Call) or not isinstance(report.value.func,ast.Name)
        or report.value.func.id!="dict"):raise ValueError("The original named producer report is required")
    job=[k.value for k in report.value.keywords if k.arg=="job"]
    native=ast.parse("os.environ['SLURM_JOB_ID']",mode="eval").body
    if len(job)!=1 or ast.dump(job[0])!=ast.dump(native):raise ValueError("Keep actual native producer identity")
    mkdir=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
           and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
           and n.func.value.id=="out" and n.func.attr=="mkdir"]
    if len(mkdir)!=1 or any(k.arg=="exist_ok" and not (isinstance(k.value,ast.Constant) and k.value.value is False) for k in mkdir[0].keywords):
        raise ValueError("The namespace must retain exclusive first creation, with no overwrite")
    original_out=copy.deepcopy(out.value)
    out.value=ast.parse("b1/"+repr(NAMESPACE),mode="eval").body
    report.value.keywords.extend([
        ast.keyword(arg="original_feature_job",value=ast.Constant(value=ORIGINAL_FEATURE_JOB)),
        ast.keyword(arg="output_namespace_job",value=ast.Constant(value=ORIGINAL_FEATURE_JOB)),
        ast.keyword(arg="native_producer_identity_is_report_job",value=ast.Constant(value=True)),
        ast.keyword(arg="recovery_declaration",value=ast.parse("os.environ['BENCHMARK_FEATURE_RECOVERY_DECLARATION']",mode="eval").body)])
    ast.fix_missing_locations(tree)
    result=ast.unparse(tree)+"\n";compile(result,"original_feature_namespace_continuation","exec")
    restored=copy.deepcopy(tree)
    for n in ast.walk(restored):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="out" for t in n.targets):n.value=copy.deepcopy(original_out)
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="report" for t in n.targets):
            n.value.keywords=[k for k in n.value.keywords if k.arg not in META_KEYS]
    if ast.dump(restored,include_attributes=False)!=ast.dump(ast.parse(body),include_attributes=False):
        raise ValueError("Scientific feature preparation changed beyond output identity and provenance")
    header=raw.split("<<'PY'\n",1)[0]+"<<'PY'\n"
    header,count=re.subn(r"(?m)^#SBATCH --exclude=.*$","#SBATCH --exclude=compute-0-[0-7,14,18,20-22]",header)
    if count!=1 or "#SBATCH --partition=cpu" not in header or "--exclusive" in header:
        raise ValueError("Keep the original CPU allocation and demand-based execution")
    header=re.sub(r"(?m)^#SBATCH --job-name=.*$","#SBATCH --job-name=C1-reference-features-empty-startup-continuation",header)
    return header+result+"\nPY\n"
