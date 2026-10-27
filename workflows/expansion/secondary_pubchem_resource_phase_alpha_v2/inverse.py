"""CPU-only exact source inverse and direct object identity; no scientific DATA."""
import ast,hashlib
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import run as OLD,guard as OLD_GUARD,runtime as OLD_RUNTIME
from . import phase as A
RUN_OLD='        budget=Budget(plan,proof,out);tests=fixtures(out);scope_proof=kernel.verify_source(plan)\n'
RUN_NEW='        tests,resource_tests,budget=A.startup_phase(lambda:fixtures(out),lambda:A.fixtures3(out),lambda:Budget(plan,proof,out));scope_proof=kernel.verify_source(plan)\n'
QA_BRANCH="        if A.phase(plan)=='QA0':return A.close_qa0(plan,proof,out,tests,resource_tests,scope_proof,budget,started)\n"
BASE_AUDIT="        base.update(resource_phase=A.phase(plan),resource_fixtures=resource_tests,source_inverse_proof=source_inverse())\n"
FAIL_AUDIT="            'resource_phase':A.phase(plan),'resource_phase_observation_failure':A.failure_details(exc,budget),\n"
RUN_HEADER='''"""Resource-phase entry; original scientific helper objects are direct."""
import argparse,json,math,multiprocessing as mp,os,struct,time,traceback,unittest
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import run as ORIGINAL,contracts as C,source,kernel,journal,materialize_shards
from secondary_pubchem_screening_alpha_v1.runtime import Budget,Stop,owned_bytes
from .guard import require_startup
from . import phase as A
from .inverse import proof as source_inverse
fixtures=ORIGINAL.fixtures
reference_rows=ORIGINAL.reference_rows
differences=ORIGINAL.differences
scientific=ORIGINAL.scientific
run_group=ORIGINAL.run_group
validate_requested_parts=ORIGINAL.validate_requested_parts


'''
GUARD_EDITS=(
 ("spec=C.MODES[mode];primary=C.HERE/'run.py';wall=plan['wall_seconds'];cap=plan['output_cap_bytes']", "spec=A.spec(A.phase(plan));primary=A.primary(A.phase(plan));wall=plan['wall_seconds'];cap=plan['output_cap_bytes']"),
 ("params=C.parameters(mode,*([plan[k] for k in ('first_part','last_part','first_ordinal','last_ordinal')] if mode=='full_shard' else []))", "params=A.parameters(plan)"),
 ("argv=[plan['python'],'-B','-m',C.MODULE,", "argv=[plan['python'],'-B','-m',A.module(A.phase(plan)),"),
 ("plan['data_references']==[data['source_index']] and review.get", "plan['data_references']==([] if A.phase(plan)=='QA0' else [data['source_index']]) and review.get"),
 ("len(limits)==1 and limits[0]['wall_seconds']==wall and limits[0]['output_cap_bytes']==cap", "len(limits)==1 and (A.phase(plan)=='QA0' or (limits[0]['wall_seconds']==wall and limits[0]['output_cap_bytes']==cap))"),
 ("    return plan,proof\n", "    A.validate(plan)\n    return plan,proof\n"))
GUARD_HEADER='''"""Fresh original guard with only explicit resource-phase primary/scope delta."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C,guard as ORIGINAL
from . import phase as A
account=ORIGINAL.account
main_authority=ORIGINAL.main_authority


'''


def replace_once(text,before,after):
    Q.need(text.count(before)==1,'EXACT_SINGLE_SOURCE_EDIT:'+before[:100]);return text.replace(before,after)


def expected(kind,old):
    if kind=='run':
        tail=old[old.index('def main():'):];tail=replace_once(tail,RUN_OLD,RUN_NEW)
        tail=replace_once(tail,"        mode=plan['mode'];base=",QA_BRANCH+"        mode=plan['mode'];base=")
        tail=replace_once(tail,"        if mode=='inventory':\n",BASE_AUDIT+"        if mode=='inventory':\n")
        tail=replace_once(tail,"            'mode':plan['mode'],'error':",FAIL_AUDIT+"            'mode':plan['mode'],'error':")
        return RUN_HEADER+tail
    tail=old[old.index('def require_startup('):]
    for before,after in GUARD_EDITS:tail=replace_once(tail,before,after)
    return GUARD_HEADER+tail


def proof():
    from . import run as NEW,guard as NEW_GUARD
    rows={}
    for kind,origin in (('run',OLD),('guard',OLD_GUARD)):
        old=Path(origin.__file__).read_text();new=(A.HERE/(kind+'.py')).read_text();Q.need(new==expected(kind,old),'ONLY_DECLARED_RESOURCE_PHASE_SOURCE_DELTA:'+kind)
        if kind=='run':
            restored=new[len(RUN_HEADER):].replace(RUN_NEW,RUN_OLD).replace(QA_BRANCH,'').replace(BASE_AUDIT,'').replace(FAIL_AUDIT,'')
            restored=old[:old.index('def main():')]+restored
        else:
            restored=new[len(GUARD_HEADER):]
            for before,after in reversed(GUARD_EDITS):restored=replace_once(restored,after,before)
            restored=old[:old.index('def require_startup(')]+restored
        Q.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'EXACT_SOURCE_AND_EXECUTABLE_AST_INVERSE:'+kind)
        rows[kind]={'origin':str(Path(origin.__file__).absolute()),'origin_text_sha256':hashlib.sha256(old.encode()).hexdigest(),'adapted_text_sha256':hashlib.sha256(new.encode()).hexdigest()}
    for name in ('fixtures','reference_rows','differences','scientific','run_group','validate_requested_parts'):
        Q.need(getattr(NEW,name) is getattr(OLD,name),'DIRECT_UNCHANGED_ORIGINAL_FUNCTION_OBJECT:'+name)
    for name in ('source','kernel','journal','materialize_shards'):Q.need(getattr(NEW,name) is getattr(OLD,name),'DIRECT_UNCHANGED_ORIGINAL_SCIENCE_MODULE:'+name)
    Q.need(NEW.Budget is OLD_RUNTIME.Budget and NEW.Stop is OLD_RUNTIME.Stop and NEW.owned_bytes is OLD_RUNTIME.owned_bytes
        and NEW_GUARD.account is OLD_GUARD.account and NEW_GUARD.main_authority is OLD_GUARD.main_authority,'ORIGINAL_RUNTIME_AND_AUTHORITY_OBJECTS_NOT_PATCHED')
    old_controller=A.QUEUE.parent/'secondary_cpu_readonly_queue_v13/controller.py';new_controller=A.QUEUE/'controller.py'
    Q.need(old_controller.read_bytes()==new_controller.read_bytes()
        and ast.dump(ast.parse(old_controller.read_text()),include_attributes=False)==ast.dump(ast.parse(new_controller.read_text()),include_attributes=False),
        'THIN_CONTROLLER_BYTE_IDENTICAL_V13_ONLY_RELATIVE_NEW_ADAPTER_NAMESPACE')
    return {'status':'EXACT_RESOURCE_PHASE_MAIN_INVERSE_AST_AND_BYTES','sources':rows,'original_science_runtime_objects_direct':True,
        'thin_controller_byte_identical_v13':True,
        'original5_fixture_bodies_unchanged':True,'resource_change_only':'five+three pure complete before original Budget construction; explicit new primary/scope and QA0 early return',
        'historical_failure_exact_cause':'UNKNOWN_NOT_PERSISTED','scientific_DATA_read':False,'old_global_monkeypatch':False}
