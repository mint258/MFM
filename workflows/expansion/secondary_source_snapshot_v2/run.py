"""Actual Alpha source-byte checker. Original checker/port/27 pure sources stay exact."""
import argparse,io,json,os,shlex,subprocess,sys,time,traceback,unittest
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from . import contracts as C,guard as G,assets as S
Q=C.Q
HARNESS=r'''import io,json,sys,unittest
expected=int(sys.argv[2]);suite=unittest.defaultTestLoader.loadTestsFromName(sys.argv[1]);declared=suite.countTestCases();stream=io.StringIO()
r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
v={'tests_run':r.testsRun,'declared_methods':declared,'expected_methods':expected,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue()}
v['status']='PASS' if r.wasSuccessful() and r.testsRun==expected and declared==expected and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses) else 'FAIL'
print('SOURCE_SNAPSHOT_PURE_RESULT='+json.dumps(v,sort_keys=True));sys.exit(0 if v['status']=='PASS' else 3)
'''


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW_SOURCE3')
    log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':log.getvalue(),
      'before_SOURCE_CODE_ASSET_body_and_Budget':True,'status':'PASS' if r.wasSuccessful() else 'FAIL'}
    Q.write_new(out/'fixtures3.json',value)
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'NEW3_MUST_PASS_BEFORE_ASSET_AND_MONITOR')
    return value


def imports(plan):
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if name.startswith('secondary_') and p and Path(p).suffix=='.py':
            Q.need(C.ROOT/'code' in Path(p).absolute().parents and Q.ref(p) in plan['source_references'],'EVERY_ACTUAL_TRANSITIVE_IMPORT_PIN:'+name)


def command(label,argv,cwd,env,out,budget,input_bytes=None):
    budget.check();stdout=out/(label+'.stdout');stderr=out/(label+'.stderr');began=time.monotonic()
    with stdout.open('xb') as so,stderr.open('xb') as se:
        child=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
          stdout=so,stderr=se,start_new_session=True)
        Q.write_new(out/(label+'.launch.json'),{'argv':argv,'cwd':str(cwd),'actual_pid':child.pid,'endpoint':Q.ENDPOINT,'uid':1264,
          'signals_sent':False,'actual_parent_terminal_accounting':'PENDING_ROOT'})
        if input_bytes is not None:
            try:child.stdin.write(input_bytes);child.stdin.close()
            except BrokenPipeError:pass
        while child.poll() is None:
            # Original Budget stops later dispatch. This consumer never kills a source-check child.
            time.sleep(.2)
    elapsed=time.monotonic()-began
    Q.need(stdout.stat().st_size<=Q.SMALL and stderr.stat().st_size<=Q.SMALL,'BOUNDED_CHECK_LOGS')
    row={'label':label,'argv':argv,'cwd':str(cwd),'returncode':child.returncode,'elapsed_seconds':elapsed,
      'stdout_reference':Q.ref(stdout),'stderr_reference':Q.ref(stderr),'signals_sent':False}
    Q.write_new(out/(label+'.command.json'),row)
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan,proof=G.require_startup(a.plan,a.startup_proof);source_rows,git_rows=C.inputs(plan)
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'FRESH_SOURCE_ONLY_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=None;fx=None;commands=[];results={};failure=None;before=after=None
    try:
        fx=fixtures(out);imports(plan);budget=Budget(plan,proof,out)
        # Source tree plus independent Git index must fit the same2GiB cap.
        Q.need(2*sum(v['bytes'] for v in source_rows.values())+sum(v['bytes'] for v in git_rows.values())+(128<<20)<C.CAP,
          'SOURCE_PLUS_NEW_GIT_INDEX_AND_LOGS_MUST_FIT_2GIB')
        sm=Q.load_ref(plan['source_manifest_reference']);gm=Q.load_ref(plan['git_manifest_reference'])
        snapshot=out/'snapshot';software=out/'software'
        source_integrity=S.extract(plan['source_archive_reference'],sm,source_rows,snapshot,budget)
        git_integrity=S.extract(plan['git_archive_reference'],gm,git_rows,software,budget,git=True)
        before=S.verify_tree(snapshot,source_rows,budget);Q.write_new(out/'snapshot_before.json',before)
        wrapper=out/'isolated_git/bin';wrapper.mkdir(parents=True);script=wrapper/'git'
        text='#!/bin/sh\nexec '+shlex.quote(str(software/'lib/ld-linux-x86-64.so.2'))+' --library-path '+shlex.quote(str(software/'lib'))+' '+shlex.quote(str(software/'bin/native-git'))+' "$@"\n'
        with script.open('x') as f:f.write(text);f.flush();os.fsync(f.fileno())
        script.chmod(0o555);wrapper_ref=Q.ref(script)
        empty=out/'git_empty_config';empty.write_text('# isolated source snapshot Git only\n');template=out/'git_empty_template';template.mkdir();tmp=out/'tmp';tmp.mkdir()
        env=dict(os.environ,PYTHONPATH=str(snapshot),PYTHONDONTWRITEBYTECODE='1',PATH=str(wrapper)+os.pathsep+os.environ.get('PATH',''),
          GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=str(empty),GIT_ATTR_NOSYSTEM='1',TMPDIR=str(tmp),GIT_TERMINAL_PROMPT='0',GIT_PAGER='cat')
        row=command('git_version',[str(script),'--version'],snapshot,env,out,budget);commands.append(row)
        Q.need(row['returncode']==0 and Path(row['stdout_reference']['path']).read_text().strip()=='git version 2.39.3','ACTUAL_ALPHA_NATIVE_GIT2393_EXECUTION')
        for label,argv,data in (('git_init',[str(script),'init','--quiet','--template='+str(template)],None),
          ('git_index',[str(script),'add','-f','--pathspec-from-file=-','--pathspec-file-nul'],b''.join(p.encode()+b'\0' for p in sorted(source_rows))),
          ('git_census',[str(script),'ls-files','--cached','--others','--exclude-standard','-z'],None)):
            row=command(label,argv,snapshot,env,out,budget,data);commands.append(row);Q.need(row['returncode']==0,'ISOLATED_GIT_COMMAND_FAILED:'+label)
        actual=Path(commands[-1]['stdout_reference']['path']).read_bytes().split(b'\0')
        names=[p.decode() for p in actual if p];Q.need(len(names)==len(set(names)) and set(names)==set(source_rows),'EXACT_SOURCE_GIT_INDEX_CENSUS')
        checker=[plan['python'],'-B',str(snapshot/'tools/check_repository.py'),'--root',str(snapshot),'--output',str(out/'repository_check.json')]
        row=command('repository_checker',checker,snapshot,env,out,budget);commands.append(row)
        results['repository_checker']=dict(row,result=Q.load(out/'repository_check.json') if (out/'repository_check.json').exists() else None,
          verify_export=False,server_sources_verified_is_unit_count=False)
        port=[plan['python'],'-B','-m','workflows.data_v1_final.labels.normalization_cache_v2.verify_port','--output',str(out/'cache_port.json')]
        row=command('cache_source_port',port,snapshot,env,out,budget);commands.append(row)
        results['normalization_source_port']=dict(row,result=Q.load(out/'cache_port.json') if (out/'cache_port.json').exists() else None)
        groups=[]
        for index,(module,expected) in enumerate(zip(C.PURE_MODULES,C.PURE_METHOD_COUNTS)):
            row=command('pure_group_'+str(index),[plan['python'],'-B','-c',HARNESS,module,str(expected)],snapshot,env,out,budget);commands.append(row)
            text=Path(row['stdout_reference']['path']).read_text();lines=[v for v in text.splitlines() if v.startswith('SOURCE_SNAPSHOT_PURE_RESULT=')]
            value=json.loads(lines[0].split('=',1)[1]) if len(lines)==1 else {'status':'FAIL','tests_run':0,'reason':'NO_UNIQUE_ORIGINAL_UNIT_RESULT'}
            groups.append(dict(row,module=module,expected_methods=expected,original_result=value))
        results['original_pure_groups']=groups
        results['strict_adapter3']={'status':'DEFERRED_MAIN_ABSOLUTE_ENGINE_SOURCE_NOT_RUN','methods_not_run':3,
          'reason':'ROOT_PLANNED_SCOPE_BEFORE_EXECUTION','Main_path_alias_or_mock_added':False,'not_counted_in27':True}
        after=S.verify_tree(snapshot,source_rows,budget,expected_frames=before['frames'],allow_git=True)
        S.verify_tree(software,git_rows,budget,expected_frames={r['relative_path']:r['actual_frame'] for r in git_integrity['files']})
        Q.write_new(out/'snapshot_after.json',after);budget.sample();budget.check()
        passed=results['repository_checker']['returncode']==0 and results['repository_checker']['result'] is not None
        passed=passed and results['repository_checker']['result'].get('status')=='PASS' and results['normalization_source_port']['returncode']==0
        passed=passed and results['normalization_source_port']['result'] is not None and results['normalization_source_port']['result'].get('status')=='SOURCE_EQUIVALENCE_ONLY_NOT_SCIENCE_ACCEPTANCE'
        passed=passed and len(groups)==8 and sum(C.PURE_METHOD_COUNTS)==27 and all(g['returncode']==0 and g['original_result'].get('status')=='PASS'
          and g['original_result'].get('expected_methods')==g['expected_methods']==g['original_result'].get('declared_methods')==g['original_result'].get('tests_run') for g in groups)
        receipt={'schema':'ACTUAL_ALPHA_EXACT_SOURCE_SNAPSHOT_CHECK_RECEIPT_V2_REVISION2','status':'EXACT_SOURCE_CHECK_PORT27_PASS_NOT_MAIN_OR_SCIENCE' if passed else 'SOURCE_CHECK_OR_PURE_FAILURE_RETAINED',
          'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'job_id':str(proof['job_id']),'plan_reference':Q.ref(a.plan),'startup_proof_reference':Q.ref(a.startup_proof),
          'fixtures':fx,'results':results,'original_pure_methods_run':sum(g['original_result'].get('tests_run',0) for g in groups),
          'original_pure_methods_expected':27,'original_pure_group_method_counts':list(C.PURE_METHOD_COUNTS),
          'source_asset_integrity':source_integrity,'git_asset_integrity':git_integrity,'isolated_Alpha_git_wrapper_reference':wrapper_ref,
          'source_full_hash_before_and_after_equal':True,'source_files':len(source_rows),'git_index_only_created_in_fresh_snapshot':True,
          'original_source_imports_constants_or_bytes_changed':False,'global_LD_or_scientific_environment_modified':False,
          'runtime':budget.receipt(),'actual_terminal_accounting_pending_Root':True,'Main_C0_or_Main17_environment_or_UFF16_claimed':False,
          'new_scientific_DATA_UFF_QM_calls':0,'D1_or_masks_or_quality_release':False}
        Q.write_new(out/'receipt.json',receipt);return 0 if passed else 3
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        Q.write_new(out/'failure.json',{'schema':'ALPHA_SOURCE_SNAPSHOT_PARTIAL_FAILURE_V2_REVISION2','endpoint':Q.ENDPOINT,'uid':1264,'job_id':str(proof['job_id']),
          'failure':failure,'fixtures':fx,'results':results,'commands':commands,'runtime':budget.receipt() if budget else None,
          'source_before_reference':Q.ref(out/'snapshot_before.json') if (out/'snapshot_before.json').exists() else None,
          'completed_source_equality_claimed':False,'partial_files_retained':True,'signals_sent':False,'actual_terminal_accounting_pending_Root':True})
        raise
    finally:
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
