"""Small anchored native evidence; no scientific parser or thresholds replaced."""
import collections,hashlib,json,re
from decimal import Decimal
from fractions import Fraction as F
from . import contract as C
SCF=C.N.SCF
FLOAT=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
HEADER=re.compile(r'^\s*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?\s*=\s*(.*)$')


def lexeme(t):
    v=Decimal(t.replace('D','E').replace('d','e'));return F(v),F(Decimal(1).scaleb(v.as_tuple().exponent))/2
def overlap(a,b):
    x,hx=lexeme(a);y,hy=lexeme(b);return abs(x-y)<=hx+hy
def line(name,sha,n,text):return {'file':name,'file_sha256':sha,'line_1_based':n,'text':text[:1024],'line_characters':len(text),'shortened':len(text)>1024}


def aux(text,name,sha):
    inventory=[];fields=[];active=None
    for n,s in enumerate(text.splitlines(),1):
        hit=HEADER.match(s)
        if hit:
            key,count,tail=hit.groups();key=key.strip();active=None;inventory.append({'key':key,'declared_count':int(count) if count else None,'line':n})
            if key in {'ATOM_EL','ATOM_X_OPT:ANGSTROMS','DIP_VEC:DEBYE','GRADIENTS:KCAL/MOL/ANGSTROM','HEAT_OF_FORMATION:KCAL/MOL','ENERGY_ELECTRONIC:EV','ENERGY_NUCLEAR:EV','DIPOLE:DEBYE'} or 'CHARGE' in key:
                active={'key':key,'declared_count':int(count) if count else None,'header':line(name,sha,n,s),'tokens':[],'token_line_numbers':[]};fields.append(active)
                values=tail.split() if key=='ATOM_EL' else re.findall(FLOAT,tail)
            else:continue
        elif active is not None and not s.lstrip().startswith('#'):values=s.split() if active['key']=='ATOM_EL' else re.findall(FLOAT,s)
        else:continue
        active['tokens'].extend(values);active['token_line_numbers'].extend([n]*len(values))
        C.Q.need(len(active['tokens'])<=4096,'FINITE_SELECTED_AUX_ARRAY_BOUND_NO_TRUNCATION')
    return {'all_header_occurrences':inventory,'selected_native_fields_all_occurrences':fields,'duplicate_keys':dict(collections.Counter(v['key'] for v in fields)),
        'all_repeated_fields_retained':True,'new_parser_choice_or_property_status':False}


def stdout(text,name,sha,xtb):
    selected=[];tables=[];current=None;dipoles=[];dipole=False
    labels=re.compile(r'energy|heat of formation|HOMO|LUMO|Fermi|electronic temp|accuracy|integral|SCF convergence|wf\. convergence|restarted\?|Broyden|Hamiltonian|max\. iterations|GRADIENT NORM|CARTESIAN COORDINATES|POINT-CHG|HYBRID|^\s*SUM\s|CHARGE',re.I)
    setup=re.compile(r'accuracy|electronic temp|integral cutoff|integral neglect|SCF convergence|wf\. convergence|restarted\?|Broyden|Hamiltonian|max\. iterations',re.I);settings=[]
    for n,s in enumerate(text.splitlines(),1):
        item=line(name,sha,n,s)
        if labels.search(s) and len(selected)<96:selected.append(item)
        if setup.search(s):settings.append(item)
        if SCF.TABLE_HEADER.search(s):
            current={'header':item,'rows':0,'last3_rows':[],'row_SHA256':hashlib.sha256()};tables.append(current)
        elif current and SCF.TABLE_ROW.match(s):
            current['rows']+=1;current['last3_rows'].append(item);current['last3_rows']=current['last3_rows'][-3:];current['row_SHA256'].update((s+'\n').encode())
        if 'molecular dipole:' in s.lower():dipole=True
        elif dipole and re.search(r'^\s*(q only|full)\s*:',s):
            tokens=re.findall(FLOAT,s.split(':',1)[1]);dipoles.append({**item,'branch':'full' if re.match(r'^\s*full',s) else 'q only','tokens':tokens,
                'component_unit_basis':'OFFICIAL_XTB_V6.7.1_molmom_SOURCE; FIRST3_AU_ONLY_TOTAL_DEBYE',
                'component_units':['a.u.']*min(3,len(tokens))+(['Debye'] if len(tokens)==4 else [])})
        elif dipole and 'molecular quadrupole' in s.lower():dipole=False
    for t in tables:t['row_SHA256']=t['row_SHA256'].hexdigest()
    return {'selected_native_lines_at_most96':selected,'selected_lines_may_be_bounded_examples':True,'actual_setup_lines':settings,
        'iteration_tables':tables,'xTB_dipole_native_rows':dipoles,'SCF_count_not_inferred_from_table_limit':True}


def engrad(text,name,sha,natoms):
    blocks=[];label=[];active=None
    for n,s in enumerate(text.splitlines(),1):
        if s.lstrip().startswith('#'):
            if active is not None:blocks.append(active);active=None;label=[]
            if s.lstrip('# ').strip():label.append(s.lstrip('# ').strip())
        elif s.strip():
            if active is None:active={'header':' '.join(label),'first_numeric_line':n,'tokens':[],'source_file':name,'source_file_sha256':sha}
            active['tokens'].extend(re.findall(FLOAT,s));C.Q.need(len(active['tokens'])<=4096,'BOUNDED_ENGRAD_BLOCK')
    if active is not None:blocks.append(active)
    grad=[b for b in blocks if 'gradient' in b['header'].lower() and 'eh/bohr' in b['header'].lower()]
    return {'blocks':blocks,'gradient_exact3N_and_unique':len(grad)==1 and len(grad[0]['tokens'])==3*natoms,
        'gradient_tokens':grad[0]['tokens'] if len(grad)==1 and len(grad[0]['tokens'])==3*natoms else None,
        'unit':'Eh/bohr' if len(grad)==1 else None,'unanchored_or_ambiguous_block_is_UNKNOWN':True}


def json_fields(text):
    pairs=json.loads(text,object_pairs_hook=lambda p:('OBJECT',p),parse_float=str,parse_int=str)
    if not(type(pairs) is tuple and pairs[0]=='OBJECT'):return {'status':'UNKNOWN_NONOBJECT_JSON'}
    rows=[]
    def flat(v):
        if type(v) is list:
            result=[]
            for x in v:result.extend(flat(x))
            return result
        return [v]
    for index,(key,value) in enumerate(pairs[1]):
        if re.search('energy|charge|dipole|orbital|occupation|gap',key,re.I):
            values=flat(value);numeric=all(type(v) is str and re.fullmatch(FLOAT,v) for v in values)
            rows.append({'key':key,'assignment_index':index,'flat_values':values if numeric and len(values)<=1024 else None,
                'flat_count':len(values),'flat_values_omitted_or_unknown':not numeric or len(values)>1024,
                'units':'a.u. EXPLICIT_KEY' if 'a.u.' in key else 'UNKNOWN_UNLESS_FROZEN_PARSER_OR_EXPLICIT_FORMAT_BINDS',
                'semantics_not_inferred_from_magnitude':True})
    return {'top_level_key_inventory':[k for k,v in pairs[1]],'selected_key_occurrences':rows,'charges_only_reconstruction_of_full_dipole':False}


def observe(files,record,parser,config):
    text={f['name']:f['data'].decode('utf-8',errors='replace') for f in files};sha={f['name']:hashlib.sha256(f['data']).hexdigest() for f in files};n=len(record['case']['symbols']);xtb=record['case']['calc_type'].startswith('xtb_')
    result={'original_SCF_extractor':SCF.extract_scf(record['case']['calc_type'],files),'original_terminal_evidence':C.N.terminal_evidence(record['case']['calc_type'],files),
        'native_member_inventory':[{'name':f['name'],'bytes':len(f['data']),'sha256':sha[f['name']]} for f in files],
        'stdout':{},'independent_representation_checks':{},'hypothesis_support':{'SCF_cause_proven':False,'missing_or_ambiguous_evidence':'UNKNOWN'}}
    for name in ('process.out','input.out'):
        if name in text:result['stdout'][name]=stdout(text[name],name,sha[name],xtb)
    if 'input.aux' in text:result['AUX_all_occurrences']=aux(text['input.aux'],'input.aux',sha['input.aux'])
    scalars=[]
    aliases={'HEAT_OF_FORMATION:KCAL/MOL':('heat_of_formation_kcal_mol','kcal/mol'),'ENERGY_ELECTRONIC:EV':('energy_electronic_eV','eV'),'ENERGY_NUCLEAR:EV':('energy_nuclear_eV','eV')}
    for f in result.get('AUX_all_occurrences',{}).get('selected_native_fields_all_occurrences',[]):
        if f['key'] in aliases and len(f['tokens'])==1:
            key,unit=aliases[f['key']];scalars.append({'field':key,'units':unit,'token':f['tokens'][0],'source':f['header'],'field_header':f['key']})
    patterns=[('energy_Eh','Eh',re.compile(r'\bTOTAL ENERGY\s+('+FLOAT+r')\s+Eh',re.I)),('heat_of_formation_kcal_mol','kcal/mol',re.compile(r'FINAL HEAT OF FORMATION\s*=\s*('+FLOAT+r')\s*KCAL',re.I))]
    for name in ('process.out','input.out'):
        if name in text:
            for number,s in enumerate(text[name].splitlines(),1):
                for key,unit,pattern in patterns:
                    hit=pattern.search(s)
                    if hit:scalars.append({'field':key,'units':unit,'token':hit[1],'source':line(name,sha[name],number,s),'field_header':hit[0]})
    result['same_named_native_energy_tokens_all_occurrences']=scalars
    if 'input.engrad' in text:
        e=engrad(text['input.engrad'],'input.engrad',sha['input.engrad'],n);result['engrad']=e
        parsed=record['independent_raw_readback'].get('xtb_gradient',{}).get('gradient_Eh_bohr')
        if e['gradient_tokens'] is not None and parsed is not None:
            actual=[float(t.replace('D','E').replace('d','e')) for t in e['gradient_tokens']];expected=[v for row in parsed for v in row]
            result['independent_representation_checks']['engrad_vs_frozen_gradient_binary64_equal']=actual==expected
            rows=[(i,s.split()) for i,s in enumerate(text.get('gradient','').splitlines(),1) if len(s.split())==3 and all(re.fullmatch(FLOAT,t) for t in s.split())]
            native=[t for i,row in rows for t in row]
            if len(native)==3*n:result['independent_representation_checks']['engrad_vs_gradient_native_print_interval_overlap']=[overlap(a,b) for a,b in zip(e['gradient_tokens'],native)]
            result['gradient_native_token_source']={'file':'gradient','sha256':sha.get('gradient'),'line_numbers':[i for i,row in rows],'tokens':native,
                'unit_basis':'ORIGINAL_FROZEN_XTB_GRADIENT_FORMAT_Eh_PER_BOHR','no_float_repr_precision_guess':True}
    if 'xtbout.json' in text:
        result['JSON_selected_native_fields']=json_fields(text['xtbout.json']);jsondip=record['independent_raw_readback'].get('xtb_dipole')
        candidates=[row for v in result['stdout'].values() for row in v['xTB_dipole_native_rows'] if row['branch']=='full' and len(row['tokens'])==4]
        # process.out is the one authoritative xTB stdout; no duplicate-file vote.
        candidates=result['stdout'].get('process.out',{}).get('xTB_dipole_native_rows',[]);candidates=[v for v in candidates if v['branch']=='full' and len(v['tokens'])==4]
        if len(candidates)==1 and jsondip is not None:
            top=json.loads(text['xtbout.json'],parse_float=str,parse_int=str).get('dipole / a.u.')
            result['independent_representation_checks']['stdout_full_components_vs_JSON_native_print_intervals']=[overlap(a,b) for a,b in zip(candidates[0]['tokens'][:3],top)] if type(top) is list and len(top)==3 else 'UNKNOWN'
    return result
