"""One bounded curl GET with inherited proxy environment, no retries or signals."""
from __future__ import annotations
import fcntl,hashlib,json,os,pathlib,re,shutil,subprocess,threading,time,urllib.parse
from contracts import need,pin
HEADER_KEYS={'content-length','content-type','content-range','content-encoding','transfer-encoding','etag','last-modified','accept-ranges'}


class PipeCapture:
    def __init__(self,fd,limit,output=None):
        self.fd=fd;self.limit=limit;self.output=pathlib.Path(output) if output else None
        self.total=0;self.kept=0;self.digest=hashlib.sha256();self.prefix=bytearray();self.error=None;self.truncated=False
        self.thread=threading.Thread(target=self.run,daemon=True)
    def run(self):
        target=None
        try:
            if self.output:
                try:target=self.output.open('xb')
                except Exception as exc:self.error=repr(exc)
            with os.fdopen(self.fd,'rb',buffering=0) as source:
                while True:
                    block=source.read(1024**2)
                    if not block:break
                    self.total+=len(block);self.digest.update(block)
                    keep=block[:max(0,self.limit-self.kept)]
                    if len(keep)<len(block):self.truncated=True
                    if keep:
                        if target is not None:
                            try:target.write(keep);self.kept+=len(keep)
                            except Exception as exc:self.error=repr(exc);target.close();target=None;self.truncated=True
                        elif self.output is None:self.prefix.extend(keep);self.kept+=len(keep)
                if target is not None:target.flush();os.fsync(target.fileno())
        except Exception as exc:self.error=repr(exc)
        finally:
            if target is not None:target.close()
    def summary(self):
        return {'bytes_observed':self.total,'bytes_kept':self.kept,'sha256_of_observed_stream':self.digest.hexdigest(),
            'truncated':self.truncated,'error':self.error,'thread_closed':not self.thread.is_alive()}


def parse_headers(raw):
    blocks=[];current=None
    for line in raw.decode('iso-8859-1').replace('\r\n','\n').split('\n'):
        match=re.match(r'^HTTP/\S+\s+(\d{3})(?:\s|$)',line)
        if match:current={'http_status':int(match.group(1)),'headers':{}};blocks.append(current);continue
        if current is None or not line or ':' not in line:continue
        key,value=line.split(':',1);key=key.lower().strip()
        if key in HEADER_KEYS:current['headers'].setdefault(key,[]).append(value.strip())
    need(blocks,'NO_ACTUAL_HTTP_RESPONSE_HEADER_BLOCK')
    return blocks


def validate_response(source,blocks,http_code,actual_bytes):
    last=blocks[-1];headers=last['headers']
    if http_code in (403,429) or last['http_status'] in (403,429):raise ValueError('HTTP403_OR429_STOP_NO_RETRY_OR_ALTERNATE_ROUTE')
    need(http_code==last['http_status']==200,'FULL_GET_REQUIRES_HTTP200_NO_REDIRECT_OR_RANGE')
    need('content-range' not in headers,'UNREQUESTED_CONTENT_RANGE_REJECTED')
    def single(key):
        values=headers.get(key,[]);need(len(values)==1,'SINGLE_GET_HEADER_REQUIRED:'+key);return values[0]
    need(single('content-length').isdecimal() and int(single('content-length'))==source['expected_content_length']==actual_bytes,'HEAD_GET_ACTUAL_LENGTH_MUST_ALL_AGREE')
    need(single('etag')==source['etag'] and single('last-modified')==source['last_modified'],'HEAD_GET_VALIDATOR_DRIFT_STOP')
    need(single('content-type').split(';',1)[0].strip().lower()==source['content_type'].lower(),'GET_CONTENT_TYPE_CHANGED')
    need(headers.get('content-encoding',[]) in ([],['identity']),'UNREQUESTED_TRANSFER_CONTENT_ENCODING_REJECTED')
    return {'status':'ACTUAL_FULL_GET_METADATA_VALIDATED','bytes':actual_bytes,'etag_is_SHA256':False,'range_used':False}


def binary_reference(path):
    logical=pathlib.Path(path).absolute();result=pin(logical,small=False)
    result.update(logical_executable_path=str(logical),is_symlink=logical.is_symlink())
    return result


def network_environment():
    keys=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy',
          'CURL_CA_BUNDLE','SSL_CERT_FILE','SSL_CERT_DIR','CURL_HOME')
    return {key:{'present':key in os.environ,'value_sha256':hashlib.sha256(os.environ[key].encode()).hexdigest() if key in os.environ else None}
            for key in keys}


def full_get(plan,out,observe_only=None):
    source=plan['source'];url=source['url'];host=urllib.parse.urlsplit(url).hostname
    curl=shutil.which('curl');need(curl is not None,'CURL_EXECUTABLE_REQUIRED')
    version=subprocess.run([curl,'--version'],stdin=subprocess.DEVNULL,capture_output=True,check=True).stdout
    need(len(version)<=65536,'BOUNDED_CURL_VERSION_OUTPUT')
    software={'curl':binary_reference(curl),'curl_version_text':version.decode('utf-8','replace')}
    lock_root=pathlib.Path(plan['run_root'])/'control/http_host_slots';lock_root.mkdir(parents=True,exist_ok=True)
    held=None;slot=None
    for index in range(2):
        candidate=(lock_root/(hashlib.sha256(host.encode()).hexdigest()+'.'+str(index)+'.lock')).open('a+b')
        try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB);held=candidate;slot=index;break
        except BlockingIOError:candidate.close()
    need(held is not None,'SECONDARY_ROOT_MAX2_PER_HOST_ALREADY_ACTIVE_NO_REQUEST_SENT')
    body_read,body_write=os.pipe();header_read,header_write=os.pipe()
    payload=pathlib.Path(out)/('payload.zip.part' if plan['stage']=='CSV_ZIP_PROFILE' else 'payload.sql.part')
    argv=[curl,'-q','--silent','--show-error','--connect-timeout','30','--max-time',str(plan['curl_max_time_seconds']),
        '--retry','0','--max-filesize',str(source['expected_content_length']),'--proto','=https',
        '--header','If-Match: '+source['etag'],'--dump-header','/proc/self/fd/'+str(header_write),
        '--output','/proc/self/fd/'+str(body_write),'--write-out',
        '%{http_code}\n%{size_download}\n%{url_effective}\n%{content_type}\n%{time_total}\n%{num_redirects}\n',url]
    started=time.monotonic();process=None;captures=[];timeout_notice=False
    result={'command_argv':argv,'source_url':url,'network_configuration_changed':False,'environment':network_environment(),
        'normal_proxy_environment_inherited':True,'curlrc_implicit_extra_transfers_disabled':True,'no_proxy_or_CA_override':True,
        'retry_count_requested':0,'range_requested':False,'redirect_follow_requested':False,'maximum_host_concurrency_secondary_root':2,
        'host_lock_slot':slot,'network_worker_processes':1,'allocated_CPUs_are_not_16_parallel_curls':True,'software':software}
    try:
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            pass_fds=(body_write,header_write),env=os.environ.copy())
        os.close(body_write);body_write=None;os.close(header_write);header_write=None
        body=PipeCapture(body_read,source['expected_content_length'],payload);body_read=None
        headers=PipeCapture(header_read,1024**2);header_read=None
        meta=PipeCapture(os.dup(process.stdout.fileno()),65536)
        stderr=PipeCapture(os.dup(process.stderr.fileno()),65536);captures=[body,headers,meta,stderr]
        for capture in captures:capture.thread.start()
        while process.poll() is None:
            if time.monotonic()-started>plan['curl_max_time_seconds']+30 and not timeout_notice:
                timeout_notice=True
                with (pathlib.Path(out)/'curl_time_overrun.json').open('x') as f:json.dump({'pid':process.pid,'signals_sent':False,
                    'action':'Continue observing the same live child; curl timeout is not assumed to be an absolute OS wall guarantee.'},f)
            if observe_only is not None:observe_only()
            time.sleep(.25)
        for capture in captures:capture.thread.join()
        result.update(curl_returncode=process.returncode,download_wall_seconds_observed=time.monotonic()-started,
            process_pid=process.pid,curl_timeout_overrun_observed=timeout_notice,signals_sent=False,
            body_stream=body.summary(),headers_stream=headers.summary(),metadata_stream=meta.summary(),stderr_stream=stderr.summary(),
            stderr_plaintext_persisted=False,raw_unredacted_response_headers_persisted=False)
        result['payload_reference']=pin(payload,small=False) if payload.exists() else None
        need(all(not c.thread.is_alive() and c.error is None for c in captures),'TRANSPORT_CAPTURE_OR_STORAGE_FAILURE')
        need(not any(c.truncated for c in captures),'BOUNDED_TRANSPORT_CAPTURE_LIMIT_EXCEEDED')
        blocks=parse_headers(bytes(headers.prefix));result['selected_response_header_blocks']=blocks
        fields=bytes(meta.prefix).decode('utf-8','strict').strip().split('\n')
        need(len(fields)==6 and fields[0].isdecimal(),'ACTUAL_CURL_WRITEOUT_REQUIRED')
        http_code=int(fields[0]);result['http_status']=http_code
        if http_code in (403,429):raise ValueError('HTTP403_OR429_STOP_NO_RETRY_OR_ALTERNATE_ROUTE')
        need(process.returncode==0,'CURL_TRANSPORT_FAILED_NO_AUTOMATIC_RETRY')
        need(fields[2]==url and fields[5]=='0','NO_REDIRECT_OR_ALTERNATE_ENDPOINT_ALLOWED')
        actual=result['payload_reference']['bytes']
        need(body.total==body.kept==actual and int(float(fields[1]))==actual,'PHYSICAL_STREAM_AND_CURL_LENGTH_DIFFER')
        result['full_get_validation']=validate_response(source,blocks,http_code,actual)
        result['physical_SHA256_is_actual_payload_bytes']=True;result['payload_download_complete']=True
    except Exception as exc:
        result.update(payload_download_complete=False,error={'type':type(exc).__name__,'message':str(exc)},
            download_wall_seconds_observed=time.monotonic()-started,signals_sent=False)
        if payload.exists():result['payload_reference']=pin(payload,small=False)
    finally:
        for fd in (body_read,body_write,header_read,header_write):
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
        if process is not None:
            # No timeout cancellation, terminate, kill or signal calls. Existing child drains naturally.
            if process.poll() is None:process.wait()
            for capture in captures:
                if capture.thread.is_alive():capture.thread.join()
        held.close()
    return result
