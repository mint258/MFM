"""Resource-neutral complete-owned cost selection; source-only draft."""
import csv,hashlib,io,json,os,re,stat
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
COST_GATE=345600

def need(ok,message):
    if not ok:raise ValueError(message)


def read(path):
    p=Path(path);need(p.is_absolute() and not p.is_symlink(),'REGULAR_SMALL_SOURCE_REQUIRED')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size<=2<<20,'SMALL_OWNED_SOURCE_REQUIRED')
        raw=f.read((2<<20)+1);after=os.fstat(f.fileno())
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and len(raw)==before.st_size,'SOURCE_CHANGED')
    return raw


def ref(path):
    raw=read(path);return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _argv_domain(argv,refs,depth=0):
    need(depth<=8,'FINITE_REVIEWED_STAGE_NESTING_REQUIRED')
    if not isinstance(argv,list) or len(argv)<2:return None,'no_explicit_primary'
    tokens=argv[1:]
    while tokens and tokens[0] in ('-B','-u'):tokens=tokens[1:]
    if not tokens:return None,'no_explicit_primary'
    if tokens[0]=='-m':
        need(len(tokens)>1,'PRIMARY_MODULE_MISSING');entry=tokens[1];tail=tokens[2:]
    else:entry=tokens[0];tail=tokens[1:]
    if entry.startswith('workflows.data_v1_final.conformers.') or '/workflows/data_v1_final/conformers/' in entry:
        return True,'primary_conformer_execution'
    other=('pprime','labels','export','normalization')
    is_other=lambda value:any(str(value).startswith('workflows.data_v1_final.'+d) or '/workflows/data_v1_final/'+d+'/' in str(value) for d in other) or str(value).startswith('workflows.expansion.') or '/workflows/expansion/' in str(value)
    if is_other(entry):return False,'explicit_other_data_line_primary_domain'
    if entry=='unittest':
        if any('workflows.data_v1_final.conformers.' in str(v) or '/workflows/data_v1_final/conformers/' in str(v) for v in tail):
            return True,'explicit_conformer_boundary_suite'
        if any(is_other(v) for v in tail):return False,'explicit_other_domain_boundary_suite'
    if entry.endswith('.run_stages_v1') or entry.endswith('/run_stages_v1.py'):
        need(tail.count('--stages')==1 and tail.index('--stages')+1<len(tail),'UNAMBIGUOUS_STAGE_FILE_OPTION_REQUIRED')
        path=tail[tail.index('--stages')+1];need(path in refs,'EXECUTED_STAGE_FILE_MUST_BE_PINNED')
        stage=load_pin(refs[path]);need(isinstance(stage.get('stages'),list) and 1<=len(stage['stages'])<=4,'FINITE_EXACT_STAGE_LIST_REQUIRED')
        domains=[_argv_domain(v['argv'],refs,depth+1) for v in stage['stages']]
        if any(value is True for value,_ in domains):return True,'reviewed_stage_executes_conformer_domain'
        if all(value is False for value,_ in domains):return False,'reviewed_stages_are_explicit_other_domains'
        return None,'unclassified_reviewed_stage_requires_scope_review'
    return None,'unclassified_primary_requires_scope_review'


def _related(record,path):
    """Use actual primary/stages; inherited code source pins are not execution."""
    jid=str(record.get('job_id',''))
    if jid in {'4520364','4520527'}:return True,'fixed_original_pilot_or_partial_audit'
    req=record.get('request',{});refs={v['path']:v for v in req.get('source_references',[])}
    selected,reason=_argv_domain(req.get('execution_argv',[]),refs)
    if selected is True:return True,reason
    scope=str(req.get('scope_key',''))
    if re.search(r'sprime|conformer|recovery|recovered',scope,re.I):return True,'explicit_domain_specific_reviewed_scope'
    if selected is False:return False,reason
    if re.search(r'sprime|conformer|recovery|recovered',Path(path).name,re.I):return True,'legacy_or_opaque_named_conformer_work'
    return None,reason


def _legacy_scope_review(classification_ref):
    """Root may classify exact opaque legacy receipts, never a future job/name."""
    if classification_ref is None:return {},[]
    body=load_pin(classification_ref)
    need(body.get('schema')=='ROOT_LEGACY_OWNED_JOB_SCOPE_CLASSIFICATION_V1' and
         body.get('status')=='APPROVED_FOR_EXACT_RECEIPTS' and body.get('reviewer')=='root' and
         body.get('cost_domain')=='SPRIME336_RECOVERY_ORIGINAL_96_CORE_HOURS',
         'EXACT_ROOT_LEGACY_SCOPE_CLASSIFICATION_REQUIRED')
    rows=body.get('classifications');need(isinstance(rows,list) and 1<=len(rows)<=128,'FINITE_LEGACY_SCOPE_CLASSIFICATION_REQUIRED')
    classified={};evidence={}
    for row in rows:
        jid=row.get('job_id')
        need(isinstance(jid,str) and jid.isdecimal() and jid not in classified and
             type(row.get('related_to_sprime_pilot')) is bool and isinstance(row.get('reason'),str) and row['reason'].strip(),
             'EXACT_LEGACY_JOB_ID_BOOLEAN_AND_REASON_REQUIRED')
        verify(row['submission_reference'])
        pins=row.get('evidence_references')
        need(isinstance(pins,list) and 1<=len(pins)<=16,'ACTUAL_SMALL_LEGACY_SBATCH_OR_SOURCE_EVIDENCE_REQUIRED')
        for pin in pins:
            verify(pin);pin=normalized(pin)
            need(pin['path'] not in evidence or evidence[pin['path']]==pin,'CONFLICTING_LEGACY_SCOPE_EVIDENCE')
            evidence[pin['path']]=pin
        classified[jid]=row
    return classified,list(evidence.values())

def owned_related_selection(owned_ref,*,current_job_id=None,require_complete_now=False,classification_ref=None):
    """Match a whole-owned snapshot to on-disk actual receipts before selecting."""
    master=load_pin(owned_ref)
    need(master['schema']=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and master['query_returncode']==0,'COMPLETE_OWNED_ACCOUNTING_POINT_REQUIRED')
    raw=read(verify(master['raw_sacct_reference'])).decode();reader=csv.DictReader(io.StringIO(raw),delimiter='|')
    need(reader.fieldnames is not None and {'JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS'}<=set(reader.fieldnames),'OWNED_RAW_HEADER')
    rawparents={}
    for row in reader:
        jid=row['JobIDRaw']
        if not jid.isdecimal():continue
        need(jid not in rawparents,'DUPLICATE_OWNED_RAW_PARENT');rawparents[jid]=row
    rows={row['JobIDRaw']:row for row in master['actual_parents']}
    need(len(rows)==len(master['actual_parents']) and set(rows)==set(rawparents),'OWNED_RAW_MASTER_SET_DIFFERS')
    classified,classification_evidence=_legacy_scope_review(classification_ref)
    applied=set();actual={};rejected=[];reasons={}
    for path in sorted((ROOT/'control/submissions').glob('*.json')):
        body=json.loads(read(path))
        if not isinstance(body,dict) or not isinstance(body.get('request'),dict):continue
        related,reason=_related(body,path)
        if body.get('job_id') and body.get('sbatch_returncode')==0:
            jid=str(body['job_id']);need(jid.isdecimal() and jid not in actual and body.get('uid')==1278,'UNIQUE_OWNED_ACTUAL_RECEIPT_REQUIRED')
            actual_ref=ref(path)
            if jid in classified:
                row=classified[jid]
                need(related is None and normalized(row['submission_reference'])==actual_ref,
                     'LEGACY_CLASSIFICATION_MUST_BIND_EXACT_UNCLASSIFIED_RECEIPT')
                related=row['related_to_sprime_pilot'];reason='root_pinned_legacy_scope_classification: '+row['reason'];applied.add(jid)
            actual[jid]={'reference':actual_ref,'body':body,'related':related,'reason':reason}
        elif related is not False and 'sbatch_argv' in body:
            need(body.get('sbatch_returncode') not in (None,0),'UNRESOLVED_RELATED_OR_UNCLASSIFIED_SUBMISSION_OUTCOME')
            if related is True:rejected.append(ref(path))
    need(set(classified)==applied,'CLASSIFICATION_MUST_CONTAIN_ONLY_CURRENT_EXACT_UNCLASSIFIED_RECEIPTS')
    need(set(rows)<=set(actual),'OWNED_MASTER_RECEIPT_DISAPPEARED')
    if require_complete_now:need(set(rows)==set(actual),'MASTER_DOES_NOT_COVER_ALL_CURRENT_ACTUAL_SUBMISSIONS')
    for jid,row in rows.items():
        need(normalized(row['receipt_reference'])==actual[jid]['reference'],'OWNED_RECEIPT_CHANGED_OR_MASTER_REF_DIFFERS')
        observed=rawparents[jid]
        need(all(str(row[key])==str(observed[key]) for key in ('State','ExitCode','ElapsedRaw','AllocCPUS')) and
             row['allocated_core_seconds_observed']==int(observed['ElapsedRaw'])*int(observed['AllocCPUS']),
             'OWNED_MASTER_ROW_DIFFERS_FROM_ACTUAL_RAW')
        if actual[jid]['related'] is True and jid!=str(current_job_id):reasons[jid]=actual[jid]['reason']
    selected_now={jid for jid,v in actual.items() if v['related'] is True and jid!=str(current_job_id)}
    need(selected_now==set(reasons),'NEW_RELATED_PARENT_REQUIRES_FRESH_COMPLETE_COST_METADATA')
    return {'related_parent_ids':sorted(reasons,key=int),'selection_reasons':reasons,
        'selected_parent_rows':[{'job_id':jid,'state':rows[jid]['State'].split()[0],'exit_code':rows[jid]['ExitCode'],
            'elapsed_raw_seconds':int(rows[jid]['ElapsedRaw']),'alloc_cpus':int(rows[jid]['AllocCPUS']),
            'allocated_core_seconds':rows[jid]['allocated_core_seconds_observed']} for jid in sorted(reasons,key=int)],
        'selected_receipt_references':[actual[jid]['reference'] for jid in sorted(reasons,key=int)],
        'all_snapshot_receipt_references':[actual[jid]['reference'] for jid in sorted(rows,key=int)],
        'owned_snapshot_parent_count':len(rows),'owned_raw_sacct_reference':master['raw_sacct_reference'],
        'known_rejected_related_submission_references':rejected,
        'rule':'ACTUAL_PRIMARY_OR_PINNED_REVIEWED_STAGE_DOMAIN; source-only provenance excluded; explicit domain scope/legacy name fallback',
        'all_owned_scope_decisions':{jid:{'related':actual[jid]['related'],'reason':actual[jid]['reason']} for jid in sorted(actual,key=int)},
        'unclassified_scope_parent_ids_for_root_review':[jid for jid in sorted(actual,key=int) if actual[jid]['related'] is None],
        'legacy_scope_classification_reference':normalized(classification_ref) if classification_ref is not None else None,
        'legacy_scope_evidence_references':classification_evidence,
        'current_validator_or_closure_job_excluded_only_as_pending_self':str(current_job_id) if current_job_id is not None else None}



def normalized(pin):return {key:pin[key] for key in ('path','bytes','sha256')}


def verify(pin):
    need(ref(Path(pin['path']))==normalized(pin),'SMALL_METADATA_PIN_DIFFERS:'+pin['path']);return Path(pin['path'])


def load_pin(pin):return json.loads(read(verify(pin)))


