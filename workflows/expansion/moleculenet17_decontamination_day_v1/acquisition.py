"""Only exact27 original missing rows may request official entry-linked ligands."""
import hashlib,json,os,re,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1.projection import strict_json
from workflows.expansion.secondary_missing11_identity_format_probe_v1.formats import sdf_metadata
from . import contract as C,projection as P,runtime as I

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Official:
    def __init__(self,authority,out,budget):
        self.a,self.out,self.budget=authority,Path(out),budget;self.out.mkdir();self.n=self.bytes=0;self.cache={}
        self.opener=urllib.request.build_opener(NoRedirect());self.log=I.Lines(self.out/'http_evidence.DATA.jsonl',budget)
    def get(self,url):
        if url in self.cache:return self.cache[url]
        u=urllib.parse.urlsplit(url);C.need(u.scheme=='https' and u.hostname in self.a['allowed_hosts'] and u.username is None
          and u.password is None and u.fragment=='' and len(url)<=16384,'ONLY_BOUNDED_OFFICIAL_HTTPS_NO_REDIRECT')
        C.need((u.hostname=='data.rcsb.org' and u.path=='/graphql') or (u.hostname=='files.rcsb.org'
          and re.fullmatch(r'/ligands/download/[A-Z0-9]{1,5}_ideal\.sdf',u.path) and not u.query),'ONLY_ENTRY_LIGAND_QUERY_OR_EXACT_CCD_STRUCTURE')
        C.need(self.n<self.a['maximum_requests'],'FINITE_REMOTE_REQUEST_BOUND_NO_RETRY');self.n+=1
        self.budget.check();p=self.out/('response_%03d.DATA.bin'%self.n);h=hashlib.sha256();size=0;status=None;headers={};error=None;complete=False
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'data-v1-MoleculeNet27-source-audit/1','Accept-Encoding':'identity'})
            try:response=self.opener.open(request,timeout=30)
            except urllib.error.HTTPError as exc:response=exc
            with response,p.open('xb') as out:
                status=response.status;headers=dict(response.headers);C.need(response.geturl()==url,'NO_REDIRECT_OR_SILENT_SOURCE_REPLACEMENT')
                C.need(response.headers.get('Content-Encoding','identity')=='identity','ONLY_IDENTITY_RESPONSE_BYTES')
                started=time.monotonic()
                while True:
                    self.budget.check();C.need(time.monotonic()-started<=120,'FINITE_PER_RESPONSE_WALL')
                    block=response.read(1<<16)
                    if not block:complete=True;break
                    C.need(size+len(block)<=self.a['maximum_response_bytes'] and self.bytes+len(block)<=self.a['maximum_total_bytes'],
                      'BOUNDED_RESPONSE_AND_TOTAL_BYTES_HOLD_NOT_TRUNCATED_ACCEPTANCE')
                    self.budget.charge(len(block));out.write(block);h.update(block);size+=len(block);self.bytes+=len(block)
                length=response.headers.get('Content-Length')
                C.need(length is None or (length.isdigit() and int(length)==size),'FULL_HTTP_CONTENT_LENGTH_NO_PREFIX_ACCEPTANCE')
                out.flush();os.fsync(out.fileno())
        except Exception as exc:
            error={'type':type(exc).__name__,'message':str(exc)}
            if self.budget.stop_new is not None:raise
        ref={'path':str(p),'bytes':size,'sha256':h.hexdigest()} if size else None
        result={'url':url,'HTTP_status':status,'response_headers':headers,'response_reference':ref,'complete_EOF':complete,
          'error':error,'new_actual_CPU_response_not_preexisting_pin':True,'automatic_retry':False}
        self.log.append(result);self.cache[url]=result;return result
    def finish(self):
        ref=self.log.close()
        return {'requests':self.n,'response_bytes':self.bytes,'evidence_reference':ref if ref['bytes'] else None,
          'actual_response_references':[v['response_reference'] for v in self.cache.values() if v['response_reference'] is not None]}

def index_ligand(raw,event):
    C.need(event['source_id']=='pdbbind_general' and event['graph_identity_charge_stereo']=='UNKNOWN'
      and event['missing_structure_reason']=='UNKNOWN' and raw[:4].decode('ascii')==event['original_ID']['text'],
      'EXACT_ORIGINAL27_ID_AND_OPAQUE_ROW')
    # All affinity/reference columns remain opaque. A name is not a CCD unless
    # the official entry independently contains that exact nonpolymer component.
    m=re.search(br'\(([A-Za-z0-9]{1,5})\)\s*$',raw)
    C.need(m is not None,'ORIGINAL_LIGAND_NAME_NOT_ONE_LITERAL_CCD_CODE_HOLD')
    comp=m.group(1).decode('ascii').upper();C.need(comp not in ('UNK','UNL','HOH'),'AMBIGUOUS_OR_NON_LIGAND_ORIGINAL_CODE_HOLD')
    pdb=raw[:4].decode('ascii');C.need(re.fullmatch('[A-Za-z0-9]{4}',pdb),'EXACT_FOUR_CHARACTER_ORIGINAL_PDB_LOCATOR')
    return pdb,comp

def component(reply,pdb,code):
    C.need(reply.get('errors') in (None,[]) and type(reply.get('data'))is dict,'OFFICIAL_QUERY_ERRORS_HOLD')
    entry=reply['data']['entry'];C.need(entry is not None and entry['rcsb_id']==pdb.upper(),'EXACT_REQUESTED_ENTRY_NO_REPLACEMENT')
    rows=entry.get('nonpolymer_entities');C.need(type(rows)is list and 0<len(rows)<=256,'BOUNDED_OFFICIAL_NONPOLYMER_ENTITIES')
    matches=[v['nonpolymer_comp'] for v in rows if v.get('nonpolymer_comp',{}).get('chem_comp',{}).get('id')==code]
    C.need(matches and all(v==matches[0] for v in matches),'EXACT_ORIGINAL_CCD_IN_THIS_ENTRY_NO_ARBITRARY_LIGAND_SELECTION')
    return matches[0]

def resolve(event,raw,official,Chem):
    pdb,code=index_ligand(raw,event)
    query='{entry(entry_id:"'+pdb.upper()+'") {rcsb_id nonpolymer_entities {nonpolymer_comp {chem_comp {id formula} rcsb_chem_comp_descriptor {InChIKey} pdbx_chem_comp_descriptor {descriptor type program}}}}}'
    response=official.get('https://data.rcsb.org/graphql?'+urllib.parse.urlencode({'query':query}))
    C.need(response['HTTP_status']==200 and response['complete_EOF'] and response['error'] is None,'OFFICIAL_ENTRY_RESPONSE_HOLD')
    ref=response['response_reference'];C.reference(ref)
    with I.held(ref,[official.out],[ref]) as (stream,_):parsed=strict_json(stream.read())
    value=component(parsed,pdb,code)
    structure=official.get('https://files.rcsb.org/ligands/download/'+code+'_ideal.sdf')
    C.need(structure['HTTP_status']==200 and structure['complete_EOF'] and structure['error'] is None,'OFFICIAL_LIGAND_STRUCTURE_NOT_AVAILABLE_HOLD')
    sr=structure['response_reference']
    with I.held(sr,[official.out],[sr]) as (stream,_):body=stream.read()
    C.need(body.count(b'$$$$')==1,'ONE_COMPLETE_OFFICIAL_CCD_STRUCTURE_NOT_HTML_OR_MULTIRECORD')
    structure_metadata=sdf_metadata(body)
    C.need(structure_metadata['declared_atoms']>0 and structure_metadata['observed_atom_table_records']==structure_metadata['declared_atoms'],
      'COMPLETE_OFFICIAL_CCD_ORIGINAL_ATOM_TABLE')
    keys=[];stored=value.get('rcsb_chem_comp_descriptor') or {};key=stored.get('InChIKey')
    if key is not None:
        valid,invalid=P.full_keys([key],strict=False);C.need(not invalid and valid,'OFFICIAL_STORED_INCHIKEY_SYNTAX');keys.extend(valid)
    descriptors=value.get('pdbx_chem_comp_descriptor') or [];C.need(type(descriptors)is list and len(descriptors)<=64,'BOUNDED_ALL_OFFICIAL_DESCRIPTOR_VARIANTS')
    observed=[]
    for d in descriptors:
        if d.get('type') not in ('SMILES','SMILES_CANONICAL'):continue
        text=d['descriptor'];C.need(type(text)is str and 0<len(text)<=1<<20,'COMPLETE_PUBLISHED_SMILES_VARIANT')
        computed,errors=P.source_smiles_keys({'official_'+str(len(observed)):text});keys.extend(computed)
        observed.append({'descriptor':d,'computed_keys':computed,'original_errors':errors})
    comp=P.formula(value['chem_comp']['formula'],Chem)
    row=P.strict('PDBbind',P.locator('MoleculeNet','PDBbind','original_general27',event['original_index_ordinal'],event['original_ID']),sorted(set(keys)),comp)
    return row,{'original_event':event,'original_line_sha256':hashlib.sha256(raw).hexdigest(),'exact_entry_CCD_match':True,
      'entry_response':response,'CCD_ideal_structure_response':structure,'all_published_SMILES_variant_observations':observed,
      'CCD_original_format_metadata':structure_metadata,
      'official_component_formula':value['chem_comp']['formula'],'original_bound_graph_or_pose_claimed':False,
      'conservative_official_exact_ligand_non_H_evidence':True,'same_PDB_ID_alone_was_not_accepted':True,
      'original_missing_reason_and_graph_state':'UNKNOWN_UNCHANGED','official_current_revision_is_not_original2019_structure_claim':True}
