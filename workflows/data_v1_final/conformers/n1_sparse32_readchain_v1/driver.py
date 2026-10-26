"""Six synthetic checks and bounded16-worker read dispatch, without science calls."""
from __future__ import annotations
import concurrent.futures as cf,contextlib,importlib,io,json,multiprocessing as mp,os,pathlib,time,unittest
from . import common as U,source

def fixtures(root,source_references):
    name=__package__+'.test_readchain';module=importlib.import_module(name);reference=U.pin(module.__file__,True)
    U.need(reference in source_references,'ACTUAL_SYNTHETIC_SOURCE_PIN');loader=unittest.TestLoader();suite=loader.loadTestsFromModule(module)
    U.need(not loader.errors and suite.countTestCases()==6,'EXACT_SIX_READCHAIN_BOUNDARY_METHODS')
    transcript=io.StringIO()
    with contextlib.redirect_stdout(transcript),contextlib.redirect_stderr(transcript):result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    counts={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
      'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses)}
    passed=result.wasSuccessful() and counts['run']==6 and not any(v for k,v in counts.items() if k!='run') and U.pin(module.__file__,True)==reference
    report={'schema':'SPARSE32_READCHAIN_FIXTURE_GATE_V1','status':'PASS' if passed else 'FAIL_NO_DATA_READ',
      'source_reference':reference,'counts':counts,'transcript':transcript.getvalue(),'before_any_task_or_LMDB_data_body':True,'new_UFF_QM_calls':0}
    ref=U.save(root/'fixtures.json',report);print(transcript.getvalue(),end='',flush=True)
    U.need(passed,'SIX_BOUNDARY_FIXTURES_MUST_PASS_BEFORE_ANY_DATA_BODY');return ref

def read_pool(items,context,budget):
    U.need(len(items)==32,'EXACT_THIRTY_TWO_REAL_READ_TASKS');closed=[];active={};index=0
    spawn=mp.get_context('spawn');context=dict(context,dispatch_barrier=spawn.Barrier(16))
    groups=[items[i:i+2] for i in range(0,32,2)]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=spawn,initializer=source.init_worker,initargs=(context,)) as pool:
        while active or index<len(groups):
            budget.observe(list(pool._processes.values()))
            while budget.stop is None and index<len(groups) and len(active)<16:
                item=groups[index];active[pool.submit(source.read_pair,item)]=item;index+=1
            if not active:break
            done,_=cf.wait(active,timeout=.5,return_when=cf.FIRST_COMPLETED)
            for future in done:
                active.pop(future);closed.extend(future.result())
    U.need(len(closed)==32 and budget.stop is None,'READ32_INCOMPLETE_UNKNOWN_NO_EQUIVALENCE')
    U.need(len({r['record_id'] for r in closed})==32 and len({r['runtime']['pid'] for r in closed})==16,
        'EXACT_UNIQUE_CANONICAL32_RECORD_IDS_AND_SIXTEEN_REAL_WORKERS');return closed
