"""Fresh-proof Alpha bounded SQL structure probe; never execute SQL or retain row values."""
import argparse,codecs,hashlib,json,os,re,stat,time,traceback,unittest
from pathlib import Path
from .contracts import ROOT,UID,KEY,SQL_BYTES,need,literal,frame,pin,write_new,startup,producer

PREFIX=16*1024**2;TAIL=65536;STATEMENT=1024**2
IDENTITY_NAMES={'id','identifier','smiles','canonical_smiles','inchi','standard_inchi','inchikey','inchi_key','standard_inchi_key',
    'molecule_id','structure_id','status','active','is_active','deleted','is_deleted','deleted_at','state'}

def parameters(rehash):
    return {'prefix_bytes':PREFIX,'tail_bytes':TAIL,'maximum_statement_retention_bytes':STATEMENT,
        'rehash_full_payload':rehash,'persist_arbitrary_prefix_or_row_values':False,'execute_SQL_or_database_import':False,
        'logical_rows_or_inactive_coverage_claimed':False,'algorithm_self_RSS_softcap_bytes':2*1024**3,
        'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def qualified(tokens,index):
    out=[]
    if index>=len(tokens) or tokens[index][0] not in ('ID','QID'):return None,index
    out.append(tokens[index][1]);index+=1
    while index+1<len(tokens) and tokens[index][1]=='.' and tokens[index+1][0] in ('ID','QID'):
        out.append(tokens[index+1][1]);index+=2
    return out,index

def words(tokens):return [value.upper() if kind=='ID' else value for kind,value in tokens]

def schema_statement(tokens,truncated):
    w=words(tokens);out={}
    if not w:return out
    if w[0]=='COPY':
        stdin=any(w[i:i+2]==['FROM','STDIN'] for i in range(len(w)-1))
        table,index=qualified(tokens,1)
        columns=[]
        if index<len(w) and w[index]=='(':
            index+=1
            while index<len(w) and w[index]!=')':
                if tokens[index][0] in ('ID','QID'):columns.append(tokens[index][1])
                elif w[index]!=',':return {'copy_header_unsupported':True,'enter_copy_data':stdin}
                index+=1
        return {'copy_header':{'table_identifiers':table,'columns':columns,'FROM_STDIN':stdin,'header_truncated':truncated},
                'enter_copy_data':stdin}
    if w[0]=='INSERT':
        at=2 if len(w)>1 and w[1]=='INTO' else 1
        table,_=qualified(tokens,at)
        return {'insert_header':{'table_identifiers':table,'record_values_not_retained':True}}
    if w[0]=='SET' and len(w)>2 and w[1]=='STANDARD_CONFORMING_STRINGS':
        value=next((x for x in w[2:] if x in ('ON','OFF')),None)
        return {'standard_conforming_strings':value}
    at=1
    if w[0]!='CREATE':return out
    if at<len(w) and w[at] in ('UNLOGGED','TEMP','TEMPORARY'):at+=1
    if at>=len(w) or w[at]!='TABLE':return out
    at+=1
    if w[at:at+3]==['IF','NOT','EXISTS']:at+=3
    table,at=qualified(tokens,at)
    if table is None or at>=len(w) or w[at]!='(' or truncated:return {'create_table_header_incomplete':True}
    at+=1;depth=0;columns=[];segment=[];closed=False
    stop={'DEFAULT','CONSTRAINT','NOT','NULL','COLLATE','GENERATED','REFERENCES','CHECK','PRIMARY','UNIQUE','EXCLUDE'}
    def column(part):
        if not part or part[0][0] not in ('ID','QID') or part[0][1].upper() in {'CONSTRAINT','PRIMARY','UNIQUE','FOREIGN','CHECK','EXCLUDE'}:return
        type_tokens=[]
        for kind,value in part[1:]:
            if kind=='ID' and value.upper() in stop:break
            if kind in ('ID','QID','NUM') or value in ('(',')',',','.','[',']'):type_tokens.append(value)
        columns.append({'name':part[0][1],'observed_type_tokens':type_tokens,
            'identity_state_or_link_name_candidate':part[0][1].lower() in IDENTITY_NAMES})
    while at<len(tokens):
        token=tokens[at];value=token[1]
        if value==')' and depth==0:column(segment);closed=True;break
        if value==',' and depth==0:column(segment);segment=[]
        else:
            segment.append(token)
            if value=='(':depth+=1
            elif value==')':depth-=1
        at+=1
    return {'table':{'table_identifiers':table,'columns':columns,'complete_CREATE_TABLE_in_bounded_region':closed}}

def inspect_prefix(raw,checkpoint=lambda:None):
    decoder=codecs.getincrementaldecoder('utf-8')('strict');text=decoder.decode(raw,final=False)
    result={'tables':[],'copy_headers':[],'insert_headers':[],'standard_conforming_strings_markers':[],
        'statement_count_in_prefix':0,'retention_limited_statements':0,'skipped_COPY_physical_lines_in_prefix_only':0,
        'COPY_data_block_cut_by_prefix':False,'incomplete_statement_at_prefix_end':False,
        'unsupported_or_incomplete_CREATE_headers':0,'unsupported_COPY_headers':0,'backslash_command_names':[],
        'pending_UTF8_boundary_bytes':len(decoder.getstate()[0]),'row_values_persisted':False}
    tokens=[];i=0;start=0;limited=False;copy=False;last_check=0
    while i<len(text):
        if i-last_check>=65536:checkpoint();last_check=i
        if copy:
            end=text.find('\n',i)
            if end<0:result['COPY_data_block_cut_by_prefix']=True;break
            line=text[i:end].rstrip('\r');i=end+1
            if line=='\\.':copy=False;start=i
            else:result['skipped_COPY_physical_lines_in_prefix_only']+=1
            continue
        c=text[i]
        if c.isspace():i+=1;continue
        if text.startswith('--',i):
            end=text.find('\n',i);i=len(text) if end<0 else end+1;continue
        if text.startswith('/*',i):
            depth=1;i+=2
            while i<len(text) and depth:
                if text.startswith('/*',i):depth+=1;i+=2
                elif text.startswith('*/',i):depth-=1;i+=2
                else:i+=1
            if depth:result['incomplete_statement_at_prefix_end']=True
            continue
        if c=='\\' and not tokens:
            end=text.find('\n',i);end=len(text) if end<0 else end
            command=re.match(r'\\([A-Za-z_]+)',text[i:end])
            if command:result['backslash_command_names'].append(command[1])
            i=end+1;continue
        if c==';':
            item=schema_statement(tokens,limited);result['statement_count_in_prefix']+=1
            if limited:result['retention_limited_statements']+=1
            for source,target in (('table','tables'),('copy_header','copy_headers'),('insert_header','insert_headers'),
                                  ('standard_conforming_strings','standard_conforming_strings_markers')):
                if source in item:result[target].append(item[source])
            result['unsupported_or_incomplete_CREATE_headers']+=int(item.get('create_table_header_incomplete',False))
            result['unsupported_COPY_headers']+=int(item.get('copy_header_unsupported',False))
            i+=1;tokens=[];limited=False;start=i
            if item.get('enter_copy_data'):
                end=text.find('\n',i)
                if end<0:result['COPY_data_block_cut_by_prefix']=True;break
                copy=True;i=end+1
            continue
        kind,value='SYM',c
        if c in "'\"":
            quote=c;j=i+1;pieces=[];closed=False
            while j<len(text):
                if text[j]==quote:
                    if j+1<len(text) and text[j+1]==quote:
                        if quote=='"':pieces.append(quote)
                        j+=2;continue
                    j+=1;closed=True;break
                if quote=="'" and text[j]=='\\':j+=2;continue
                if quote=='"':pieces.append(text[j])
                j+=1
            kind,value=('QID',''.join(pieces)) if quote=='"' else ('LIT','')
            i=j
            if not closed:result['incomplete_statement_at_prefix_end']=True
        elif c=='$' and (tag:=re.match(r'\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$',text[i:])):
            end=text.find(tag[0],i+len(tag[0]));kind,value='LIT',''
            if end<0:i=len(text);result['incomplete_statement_at_prefix_end']=True
            else:i=end+len(tag[0])
        elif c.isalpha() or c=='_':
            match=re.match(r'[A-Za-z_][A-Za-z_0-9$]*',text[i:])
            if match:kind,value='ID',match[0];i+=len(value)
            else:i+=1
        elif c.isdigit():
            match=re.match(r'[0-9]+',text[i:]);kind,value='NUM',match[0];i+=len(value)
        else:i+=1
        if i-start>STATEMENT or len(tokens)>=131072:limited=True
        if not limited:tokens.append((kind,value))
    if tokens:result['incomplete_statement_at_prefix_end']=True
    result['COPY_data_block_cut_by_prefix']|=copy
    result['backslash_command_names']=sorted(set(result['backslash_command_names']))
    result['PostgreSQL_dump_marker_observed']=b'PostgreSQL database dump' in raw
    result['full_schema_or_all_status_universe_proven']=False
    result['raw_SQL_or_literal_values_retained']=False
    return result

class ProbeMetadataFixtures(unittest.TestCase):
    def test_COPY_values_and_function_bodies_cannot_become_schema_observations(self):
        raw=b"SET standard_conforming_strings = on;\nCREATE TABLE public.molecules (id bigint, status text DEFAULT 'SECRET', smiles text);\nCOPY public.molecules (id,status,smiles) FROM stdin;\nCREATE TABLE stolen (secret text);\n\\.\nCREATE FUNCTION f() RETURNS void AS $$ CREATE TABLE hidden (x text); $$ LANGUAGE sql;\n"
        observed=inspect_prefix(raw);encoded=json.dumps(observed)
        self.assertEqual([t['table_identifiers'] for t in observed['tables']],[['public','molecules']])
        self.assertEqual(observed['copy_headers'][0]['columns'],['id','status','smiles'])
        for secret in ('SECRET','stolen','hidden'):self.assertNotIn(secret,encoded)
        unknown=inspect_prefix(b'COPY public.t (a[1]) FROM stdin;\nCREATE TABLE row_secret (x text);\n\\.\n')
        self.assertEqual(unknown['unsupported_COPY_headers'],1)
        self.assertNotIn('row_secret',json.dumps(unknown))

    def test_quoted_identifiers_nested_type_commas_and_cut_COPY_are_explicit(self):
        raw=b'CREATE TABLE "public"."structures" ("id" bigint, amount numeric(10,2), "is_active" boolean); COPY public.structures (id,is_active) FROM stdin;\n1\tt\n'
        observed=inspect_prefix(raw)
        self.assertEqual(len(observed['tables'][0]['columns']),3)
        self.assertTrue(observed['COPY_data_block_cut_by_prefix'])
        self.assertFalse(observed['full_schema_or_all_status_universe_proven'])

def memory():
    values={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
            if line.startswith(('MemAvailable:','MemTotal:'))}
    values['self_RSS_bytes']=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    need(values['MemTotal']>0 and 0<=values['MemAvailable']<=values['MemTotal'] and values['self_RSS_bytes']>=0,'INVALID_CURRENT_MEMORY')
    return values

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    a=p.parse_args();plan,proof=startup(a.plan,a.startup_proof,__file__)
    rehash=plan['scope_parameters'].get('rehash_full_payload')
    need(type(rehash) is bool and plan['scope_parameters']==parameters(rehash),'EXACT_BOUNDED_BYTE_AND_NO_ROW_RETENTION_SCOPE')
    payload,upstream=producer(plan)
    out=literal(plan['output_directory']);need(ROOT/'artifacts' in out.parents and not out.exists(),'NEW_READONLY_OUTPUT_REQUIRED')
    out.mkdir(parents=True);began=time.monotonic();last=[float('-inf')];samples=[];peak=[0];lowest=[None];lag=[0.]
    def checkpoint():
        need(time.monotonic()-began<plan['wall_seconds']-30,'WALL_STOP_NEW_READ_WORK_NO_SIGNALS')
        if time.monotonic()-last[0]>=1:
            start=time.monotonic();value=memory();elapsed=time.monotonic()-start;last[0]=time.monotonic()
            lag[0]=max(lag[0],elapsed);peak[0]=max(peak[0],value['self_RSS_bytes'])
            lowest[0]=value['MemAvailable'] if lowest[0] is None else min(lowest[0],value['MemAvailable'])
            if len(samples)<600:samples.append({'elapsed_seconds':time.monotonic()-began,'sample_seconds':elapsed,**value})
            need(value['self_RSS_bytes']<2*1024**3 and value['MemAvailable']>=value['MemTotal']*.15,'ACTUAL_RSS_OR_MEMAVAILABLE_STOP_NEW_READ')
    try:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(ProbeMetadataFixtures);need(suite.countTestCases()==2,'EXACT_TWO_NEW_METADATA_FIXTURES')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        tests={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'before_SQL_body_IO':True}
        write_new(out/'metadata_fixtures.json',tests);need(result.wasSuccessful() and result.testsRun==2 and not result.skipped,'FIXTURES_MUST_PASS_BEFORE_SQL_BODY')
        checkpoint();path=literal(payload['path']);hash_result={'performed':False,'CPU_seconds':0.,'wall_seconds':0.}
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_uid==UID and before.st_size==SQL_BYTES,'CURRENT_COMPLETE_OWNED_SQL_SIZE_REQUIRED')
            if rehash:
                start,cpu=time.monotonic(),time.process_time();digest=hashlib.sha256();total=0
                while True:
                    checkpoint();block=stream.read(1024**2)
                    if not block:break
                    digest.update(block);total+=len(block)
                need(total==SQL_BYTES and digest.hexdigest()==payload['sha256'],'CURRENT_FULL_SQL_SHA_DIFFERS')
                hash_result={'performed':True,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'sha256':digest.hexdigest()}
            checkpoint();stream.seek(0);prefix=stream.read(PREFIX)
            need(not prefix.startswith((b'PK',b'\x1f\x8b',b'PGDMP',b'BZh',b'\xfd7zXZ')),'OBSERVED_SQL_IS_NOT_PLAIN_TEXT')
            checkpoint();stream.seek(max(0,before.st_size-TAIL));tail=stream.read(TAIL)
            checkpoint();schema=inspect_prefix(prefix,checkpoint)
            after=os.fstat(stream.fileno())
        need(frame(before)==frame(after)==frame(path.stat()),'SQL_CHANGED_DURING_BOUNDED_PROBE')
        schema.update(actual_prefix_bytes=len(prefix),actual_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
            actual_tail_bytes=len(tail),actual_tail_sha256=hashlib.sha256(tail).hexdigest(),
            PostgreSQL_dump_complete_marker_in_tail=b'-- PostgreSQL database dump complete' in tail,
            current_full_payload_SHA_reverified=rehash,source_CRC='NOT_APPLICABLE_PLAIN_SQL')
        encoded=(json.dumps(schema,ensure_ascii=False,indent=2)+'\n').encode();need(len(encoded)+1024**2<=plan['output_cap_bytes'],'SCHEMA_METADATA_OUTPUT_CAP')
        checkpoint()
        target=out/'schema_observations.json'
        with target.open('xb') as stream:stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        schema_ref={'path':str(target),'bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest()}
        write_new(out/'receipt.json',{'schema':'SECONDARY_COCONUT_SQL_FORMAT_PROBE_RECEIPT_V1',
            'status':'BOUNDED_SQL_SCHEMA_OBSERVED_NO_LOGICAL_IDENTITY_ACCEPTANCE','endpoint':'218.192.171.238:22','uid':UID,
            'job_id':str(proof['job_id']),'node':plan['node'],'scope_key':KEY,'plan':pin(a.plan),'startup_proof':pin(a.startup_proof),
            'upstream_actual_SQL_authority':upstream,'input_SQL_reference_from_actual_producer':payload,
            'current_fstat_before':frame(before),'current_fstat_after':frame(after),'current_full_SHA':hash_result,
            'schema_observations':schema_ref,'metadata_fixtures':tests,'actual_memory_samples':samples,
            'peak_current_self_RSS_bytes':peak[0],'minimum_actual_MemAvailable_bytes':lowest[0],'maximum_sample_seconds_lag_only':lag[0],
            'allocated_cpus':16,'sixteen_parallel_parser_workers_claimed':False,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
            'algorithm_RSS_softcap_is_not_requested_or_allocated_memory':True,
            'actual_Slurm_memory_environment':proof['actual_memory_environment'],
            'memory_requested':False,'signals_sent':False,'wall_seconds':time.monotonic()-began,
            'logical_rows_or_active_inactive_coverage_proven':False,'SQL_executed_or_imported':False,
            'row_values_or_arbitrary_prefix_persisted':False,'identity_normalization_or_pool_release':False,
            'actual_parent_allocation_cost_pending_accounting':True})
    except BaseException as exc:
        write_new(out/'failure.json',{'status':'BOUNDED_SQL_PROBE_FAILED_NO_RELEASE','type':type(exc).__name__,
            'error':str(exc),'code_traceback':traceback.format_exc(),'signals_sent':False,'source_untouched':True})
        raise

if __name__=='__main__':main()
