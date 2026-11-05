"""Fresh Main CPU structural evidence; reused original archive reader, no keys."""
import argparse,hashlib,io,json,os,sys,traceback,unittest,zipfile
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_identity_format_probe_v1 import run as M
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from . import contract as C,primitive as P,structure as S
Q=C.Q


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_PRIMITIVE_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'before_archive_and_inventory_bodies':True}
    Q.write_new(out/'fixtures3.json',value);Q.need(r.wasSuccessful() and r.testsRun==3
        and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ORIGINAL_BODIES');return value


def observe(plan,parent,out,budget):
    arc=plan['archive_reference'];inv=plan['inventory_reference'];fr=M.verify_file(arc,budget.check);ifr=M.verify_file(inv,budget.check)
    Q.need(inv['bytes']<=64<<10,'SMALL_PRODUCER_INVENTORY_AFTER_FIXTURES')
    with Path(inv['path']).open('rb') as f:
        Q.need(M.frame(os.fstat(f.fileno()))==ifr,'SAME_PRODUCER_INVENTORY_FRAME');raw=f.read((64<<10)+1)
        Q.need(len(raw)==inv['bytes'] and hashlib.sha256(raw).hexdigest()==inv['sha256']
            and M.frame(os.fstat(f.fileno()))==ifr==M.frame(Path(inv['path']).lstat()),'PARSED_EXACT_PRODUCER_INVENTORY')
    rows=[json.loads(line) for line in raw.splitlines()];Q.need(len(rows)==1 and rows[0]['name']=='Kraken.pickle'
        and rows[0]['decoded_bytes']==94805786 and rows[0]['EOF_CRC_passed'] is True,'EXACT_ONE_BOOTSTRAP_MEMBER')
    row=rows[0];decoded=None;shape=None;problem=None
    with Path(arc['path']).open('rb') as f:
        Q.need(M.frame(os.fstat(f.fileno()))==fr,'CURRENT_HASHED_ARCHIVE_FRAME');pre=A.preflight(f,arc['bytes']);f.seek(0)
        with zipfile.ZipFile(f,'r') as z:
            infos,total=A.directory(z,pre,row['decoded_bytes']);Q.need(len(infos)==1,'ONE_ORIGINAL_MEMBER');info=infos[0]
            Q.need(not info.is_dir() and info.filename==row['name'] and info.file_size==row['decoded_bytes']
                and info.compress_size==row['compressed_bytes'] and info.CRC==row['CRC32_observed'],'EXACT_BOOTSTRAP_MEMBER_DIRECTORY')
            with z.open(info) as original:
                stream=M.Member(original,row,budget.check)
                try:
                    root,decoded=P.Reader(stream,budget.check,row['decoded_bytes']).decode()
                    Q.need(decoded['opcode_counts']==parent['result']['observation']['opcode_counts'],'CURRENT_EXACT_COUNTS_EQUAL_ACTUAL_OPCODE_PARENT')
                    shape=S.inspect(root);del root
                except P.UnknownPrimitive as exc:problem=type(exc).__name__+': '+str(exc)
                while stream.read(1<<20):budget.check()
                member=stream.finish()
        Q.need(M.frame(os.fstat(f.fileno()))==fr==M.frame(Path(arc['path']).lstat()),'UNCHANGED_ARCHIVE_AFTER_FULL_PRIMITIVE_READ')
    Q.write_new(out/'structure_observation.json',{'schema':'MARCEL_KRAKEN_PRIMITIVE_STRUCTURE_OBSERVATION_V1',
        'status':'UNKNOWN_HOLD' if problem else shape['status'],'decoder_problem':problem,'decoder':decoded,'structure':shape,
        'member_current_EOF_CRC_SHA':member,'archive_reference':arc,'producer_inventory_reference':inv,
        'source_semantics_and_normalized_identity_accepted':False,'pool_release':False})
    return {'structure_observation_reference':Q.pin(out/'structure_observation.json'),'decoder_problem':problem,
        'structure_status':None if shape is None else shape['status'],'source_graph_stereo_population_and_key_acceptance':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);parent,parents=C.inputs(plan);Q.need(plan['schema']=='MARCEL_KRAKEN_PRIMITIVE_STRUCTURE_PLAN_V1'
        and plan['scope_parameters']==C.PARAMETERS and plan['mode']=='kraken_opcodes','EXACT_NEW_STRUCTURE_ONLY_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.M.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=3600 and plan['wall_seconds']%60==0
        and req['estimated_peak_output_bytes']==C.CAP and req['data_references']==[plan['archive_reference'],plan['inventory_reference']]
        and not req.get('deferred_authority_references'),'EXACT_CPU16_ANALYSIS_NO_MEM_BOUNDED_STRUCTURE_RESOURCES')
    review=C.M.meta(req['scope']['review']);Q.need(review['nonexecuting_primitive_structure_only_authorized'] is True,'INDEPENDENT_ROOT_STRUCTURE_ONLY_REVIEW')
    cost=C.M.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_QUALITY_AUTHORITY')
    for p in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(p) in req['source_references'],'ALL_NEW_AND_EXACT_REUSED_MODULE_PINS')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_FULL_ARGV')
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_STRUCTURE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=M.Budget(plan,proof,out);gate=None
    try:
        gate=fixtures(out);budget.check(True);result=observe(plan,parent,out,budget);budget.check(True)
        held=bool(result['decoder_problem']) or result['structure_status']!='ALL_SOURCE_ASSIGNMENTS_STRUCTURALLY_OBSERVED_SEMANTICS_PENDING'
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_KRAKEN_PRIMITIVE_STRUCTURE_RECEIPT_V1',
            'status':'PRIMITIVE_STRUCTURE_UNKNOWN_HOLD' if held else 'STRUCTURE_EVIDENCE_COMPLETE_SEMANTICS_AND_KEYS_PENDING',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22',
            'accepted_opcode_receipt_reference':plan['accepted_opcode_receipt_reference'],'accepted_opcode_accounting_reference':plan['accepted_opcode_accounting_reference'],
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'fixtures':gate,'result':result,
            'actual_RSS_peak_bytes':budget.peak,'actual_minimum_MemAvailable_bytes':budget.minimum,'actual_python_version':sys.version,
            'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE','normalized_key_calls':0,
            'source_ligand_conformer_identity_graph_stereo_or_pool_accepted':False})
        return 3 if held else 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'MARCEL_KRAKEN_PRIMITIVE_STRUCTURE_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'partial_outputs_retained':True,'source_or_pool_accepted':False,'actual_cost':'PENDING_ROOT_ACCOUNTING'})
        raise


if __name__=='__main__':raise SystemExit(main())
