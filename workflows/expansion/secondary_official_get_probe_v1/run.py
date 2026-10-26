"""Fresh Alpha allocation -> five pure seams -> three serial bounded official GETs."""
import argparse,contextlib,hashlib,io,json,os,stat,sys,time,unittest
from pathlib import Path
from . import contracts as C,http as H

class Budget:
    def __init__(self,out,wall):self.out=out;self.until=time.monotonic()+wall-120;self.stop=None;self.samples=[];self.max_rss=0;self.min_available=None
    def tick(self):
        try:
            available=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
            rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE');used=0
            for p in (self.out,*self.out.rglob('*')):
                s=p.lstat();C.q.need(s.st_uid==1264 and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),'OWN_REGULAR_OUTPUT_ONLY');used+=max(s.st_size,s.st_blocks*512)
            self.max_rss=max(self.max_rss,rss);self.min_available=available if self.min_available is None else min(self.min_available,available)
            if available<4<<30 or rss>2<<30:self.stop=self.stop or 'RSS_OR_MEMAVAILABLE_STOP_NEW_REQUEST'
            if used+(2<<20)>C.CAP:self.stop=self.stop or 'WHOLE256MIB_STOP_NEW_REQUEST'
            if time.monotonic()>=self.until:self.stop=self.stop or 'WALL_RESERVE_STOP_NEW_REQUEST'
            row={'unix':time.time(),'RSS':rss,'MemAvailable':available,'output_allocated_bytes':used}
            if len(self.samples)<1024:self.samples.append(row)
            else:self.samples[-1]=row
        except Exception as exc:self.stop=self.stop or 'OBSERVATION_UNAVAILABLE:'+type(exc).__name__
        return self.stop is not None
    def report(self):return {'stop':self.stop,'maximum_RSS':self.max_rss,'minimum_MemAvailable':self.min_available,'samples':self.samples,
        'scheduler_memory_requested':False,'forced_signals_sent':False,'automatic_retry':False,'natural_response_close':True}

def fixtures(out,plan):
    from . import test_probe
    source=C.q.ref(test_probe.__file__);C.q.need(source in plan['source_references'],'ACTUAL_TEST_SOURCE_PIN')
    loader=unittest.TestLoader();suite=loader.loadTestsFromModule(test_probe);C.q.need(not loader.errors and suite.countTestCases()==5,'EXACT_FIVE_HTTP_SEAMS')
    transcript=io.StringIO()
    with contextlib.redirect_stdout(transcript),contextlib.redirect_stderr(transcript):result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    counts={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses)}
    passed=result.wasSuccessful() and counts['run']==5 and not any(v for k,v in counts.items() if k!='run') and C.q.ref(test_probe.__file__)==source
    pin=C.q.write_new(out/'fixtures.json',{'schema':'OFFICIAL_GET_PROBE_FIVE_SEAMS_V1','status':'PASS' if passed else 'FAIL_NO_NETWORK',
        'counts':counts,'source_reference':source,'transcript':transcript.getvalue(),'actual_network_requests_before_gate':0})
    print(transcript.getvalue(),end='',flush=True);C.q.need(passed,'FIVE_SEAMS_MUST_PASS_BEFORE_ANY_NETWORK');return pin

def body_reference(path):
    if not path.exists():return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        a=os.fstat(f.fileno())
        for block in iter(lambda:f.read(64<<10),b''):h.update(block)
        b=os.fstat(f.fileno())
    C.q.need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'SAVED_RESPONSE_CHANGED')
    return {'path':str(path),'bytes':b.st_size,'sha256':h.hexdigest()}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    a=p.parse_args();plan,proof=C.startup(a.plan,a.startup_proof);out=C.q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    budget=Budget(out,plan['wall_seconds']);gate=fixtures(out,plan);results=[];fatal=None
    try:
        import requests
        with requests.Session() as session:
            session.trust_env=False;session.auth=None;session.proxies.clear();session.max_redirects=5
            session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
            for spec in C.SPECS:
                path=out/(spec['source_id']+'.response.bin')
                if budget.tick():results.append({'source_id':spec['source_id'],'status':'NOT_STARTED_AFTER_SOFT_STOP','body_reference':None});continue
                started=time.monotonic()
                try:
                    observation=H.fetch(spec,session,path,budget.tick);body=body_reference(path)
                    if body is not None:C.q.need(body['bytes']==observation['bytes_saved'] and body['sha256']==observation['body_sha256'],'ACTUAL_SAVED_ENTITY_READBACK')
                    row={'source_id':spec['source_id'],'original_official_URL':spec['url'],'byte_cap':spec['cap_bytes'],
                        'elapsed_seconds':time.monotonic()-started,'observation':observation,'body_reference':body,
                        'identity_or_population_or_stereo_coverage_accepted':False}
                except Exception as exc:
                    # Exception strings/tracebacks may contain a signed redirect
                    # URL or headers. Persist only its type and the opaque body.
                    row={'source_id':spec['source_id'],'original_official_URL':spec['url'],'status':'GET_FAILED_NO_RETRY',
                        'error_type':type(exc).__name__,'elapsed_seconds':time.monotonic()-started,'body_reference':body_reference(path),
                        'archive_complete':False,'partial_body_only_if_present':True,'exception_URL_or_headers_recorded':False}
                results.append(row);C.q.write_new(out/(spec['source_id']+'.json'),row)
    except Exception as exc:fatal=type(exc).__name__
    bad=fatal is not None or budget.stop is not None or len(results)!=3
    for row in results:
        observed=row.get('observation',{});status=observed.get('status_code')
        bad=bad or row.get('status') in ('GET_FAILED_NO_RETRY','NOT_STARTED_AFTER_SOFT_STOP') or not isinstance(status,int) or not 200<=status<300
        if row['source_id']=='tdc_admet_group_zip':bad=bad or not observed.get('archive_complete',False)
    receipt={'schema':'OFFICIAL_THREE_URL_BOUNDED_GET_PROBE_RECEIPT_V1','status':'OBSERVED_FAILURE_OR_PENDING_NO_RETRY' if bad else 'BOUNDED_GET_PROBE_CLOSED_NOT_IDENTITY_ACCEPTANCE',
        'endpoint':C.q.ENDPOINT,'uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
        'plan_reference':C.q.ref(a.plan),'startup_proof_reference':C.q.ref(a.startup_proof),'fixture_reference':gate,'sources':results,
        'fatal_error_type':fatal,'requests_version':getattr(sys.modules.get('requests'),'__version__',None),'resource_evidence':budget.report(),
        'new_UFF_QM_calls':0,'CSV_or_identity_decoded':False,'all_split_identity_coverage_accepted':False,'automatic_retry':False,
        'MARCEL_archivecomplete_or_wholearchiveSHA_claimed':False,'official_HEAD_failure_implies_GET_failure_claimed':False,
        'method_semantics_same_as_official_GET_stream_not_identical_HTTP_bytes_claimed':True,'full_followup_GET_authorized':False}
    result=C.q.write_new(out/'receipt.json',receipt);C.q.need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<=C.CAP,'WHOLE_OUTPUT256MIB')
    print(json.dumps({'receipt':result,'failed_or_pending':bool(bad),'new_UFF_QM_calls':0}),flush=True);return 3 if bad else 0

if __name__=='__main__':sys.exit(main())
