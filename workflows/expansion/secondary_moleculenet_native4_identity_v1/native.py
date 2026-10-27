"""Read source tables only; MOL2 graph/charge/stereo are never inferred."""
import base64,collections,hashlib,importlib,json,os,random,re,tempfile,time
from pathlib import Path,PurePosixPath
from secondary_missing11_identity_format_probe_v1 import formats as F
from secondary_coconut_identity_norm_profile_v1.run import load_kernel
from . import contracts as C
Q=C.Q;FUNCTIONS=None


def token(raw):
    if raw is None:return {'state':'MISSING','bytes':None}
    try:text=raw.decode('utf-8')
    except UnicodeError:return {'state':'INVALID_UTF8_UNKNOWN','bytes':len(raw),'base64':base64.b64encode(raw).decode()}
    return {'state':'EMPTY_PRESERVED' if not raw else 'LITERAL_UTF8','bytes':len(raw),'text':text}


def load(plan):
    f,proof=load_kernel(plan);projection=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    f={**f,'native_composition':projection.native_composition};proof={**proof,'native_composition_source':{'filename':projection.native_composition.__code__.co_filename,'first_line':projection.native_composition.__code__.co_firstlineno}}
    return f,proof


def sample(source,n):
    seed=int(hashlib.sha256(('20261026|native4|'+source).encode()).hexdigest(),16)
    return sorted(random.Random(seed).sample(range(n),min(n,1000)))


def records(stream,kind,emit,check):
    raw=bytearray();ordinal=0;started=False
    while True:
        check();line=stream.readline(C.NATIVE_CAP+1)
        if not line:break
        Q.need(len(line)<=C.NATIVE_CAP,'NATIVE_LINE_SOFTWARE_CAP_STOP_NOT_CHEMICAL_EXCLUSION')
        if kind=='MOL2' and line.strip()==b'@<TRIPOS>MOLECULE':
            if started:emit(ordinal,bytes(raw),True);ordinal+=1;raw.clear()
            started=True
        raw.extend(line);Q.need(len(raw)<=C.NATIVE_CAP,'NATIVE_RECORD_SOFTWARE_CAP_STOP_WITH_SOURCE_RETAINED')
        if kind=='SDF' and line.strip()==b'$$$$':emit(ordinal,bytes(raw),True);ordinal+=1;raw.clear()
    if raw:emit(ordinal,bytes(raw),kind=='MOL2' and started);ordinal+=1
    return ordinal


def elements(raw,kind,functions):
    """Elements only, from complete original tables; no coordinates/charge values."""
    from rdkit import Chem
    symbols=[];ids=[];lines=raw.splitlines();meta=None
    if kind=='SDF':
        try:meta=F.sdf_metadata(raw)
        except F.UnknownFormat:
            # Do not append a fake delimiter. A complete V2000 atom table can
            # still supply literal elements while record termination is unknown.
            Q.need(len(lines)>=5 and b'V2000' in lines[3] and any(v==b'M  END' for v in lines),'NATIVE_ATOM_TABLE_UNAVAILABLE')
            n=F.integer(lines[3][:3]);atoms=lines[4:4+n]
            meta={'version':'V2000','declared_atoms':n,'observed_atom_table_records':sum(len(v)>=34 and not v.startswith(b'M  ') for v in atoms),
                'complete_record_boundary':False,'fallback_basis':'COMPLETE_ORIGINAL_UNALTERED_ATOM_TABLE_ONLY_NO_DELIMITER_INSERTED'}
        Q.need(meta['declared_atoms'] is not None and meta['declared_atoms']>0 and meta['observed_atom_table_records']==meta['declared_atoms'],'COMPLETE_ORIGINAL_SDF_ATOM_TABLE_REQUIRED')
        if meta['version']=='V2000':symbols=[x[31:34].strip().decode('ascii') for x in lines[4:4+meta['declared_atoms']]]
        elif meta['version']=='V3000':
            section=None;pending=b''
            for line in lines:
                if not line.startswith(b'M  V30 '):continue
                value=pending+line[7:];pending=b''
                if value.endswith(b'-'):pending=value[:-1];continue
                if value==b'BEGIN ATOM':section='ATOM'
                elif value.startswith(b'END '):section=None
                elif section=='ATOM':
                    words=value.split();Q.need(len(words)>=2,'COMPLETE_V3000_ATOM_SYMBOL');ids.append(int(words[0]));symbols.append(words[1].decode('ascii'))
            Q.need(not pending and len(set(ids))==len(ids),'UNIQUE_COMPLETE_V3000_ATOM_ROWS')
        else:raise ValueError('UNKNOWN_NATIVE_CTAB_VERSION')
    else:
        meta=F.mol2_metadata(raw,True);Q.need(meta['declared_atoms']>0 and meta['observed_atom_table_records']==meta['declared_atoms'],'COMPLETE_ORIGINAL_MOL2_ATOM_TABLE_REQUIRED')
        section=None
        for line in lines:
            if line.startswith(b'@<TRIPOS>'):section=line[9:];continue
            if section!=b'ATOM' or not line.strip() or line.lstrip().startswith(b'#'):continue
            words=line.split();Q.need(len(words)>=6,'ORIGINAL_MOL2_ATOM_TYPE_COLUMN_REQUIRED');ids.append(int(words[0]));symbols.append(words[5].split(b'.',1)[0].decode('ascii'))
        Q.need(len(set(ids))==len(ids),'UNIQUE_ORIGINAL_MOL2_ATOM_IDS')
    Q.need(len(symbols)==meta['declared_atoms'],'ALL_ORIGINAL_ATOMS_COUNTED_WITHOUT_DROPS');table=Chem.GetPeriodicTable();pairs=collections.Counter()
    for symbol in symbols:
        # Do not discard pseudo/query atoms, infer from atom names, normalize case,
        # strip a charge suffix, or treat LP as an ordinary chemical element.
        z=table.GetAtomicNumber(symbol);Q.need(1<=z<=118 and table.GetElementSymbol(z)==symbol,'EXACT_LITERAL_ELEMENT_SYMBOL_OR_UNKNOWN');pairs[z]+=1
    return functions['native_composition'](dict(pairs)),meta


def project(source,member,member_ordinal,record_ordinal,source_ordinal,kind,raw,complete,functions):
    lines=raw.splitlines();title=lines[0] if lines else None;properties=collections.defaultdict(list)
    if kind=='MOL2':
        starts=[i for i,v in enumerate(lines) if v.strip()==b'@<TRIPOS>MOLECULE'];title=lines[starts[0]+1] if starts and len(lines)>starts[0]+1 else None
    else:
        current=None;parts=[];after=False
        def close():
            if current is not None:properties[current].append(token(b'\n'.join(parts)))
        allowed={b'ID',b'_Name',b'smiles',b'canonical_smiles',b'isomeric_smiles',b'reidentified_smiles'}
        for line in lines[1:]:
            if not after:
                if line==b'M  END':after=True
                continue
            m=re.match(br'^>[^<]*<([^<>]+)>',line)
            if m:close();current=m[1].decode() if m[1] in allowed else None;parts=[]
            elif line in (b'',b'$$$$'):close();current=None;parts=[]
            elif current is not None:parts.append(line)
        close()
    comp=None;metadata=None;error=None
    try:comp,metadata=elements(raw,kind,functions)
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    p=PurePosixPath(member);pdb=None
    if source!='qm8_sdf':
        suffix='_ligand.'+kind.lower();stem=p.name[:-len(suffix)] if p.name.endswith(suffix) else ''
        if re.fullmatch('[A-Za-z0-9]{4}',stem) and p.parent.name==stem and p.parts[0]==C.PREFIX[source]:pdb=stem
    return {'source_id':source,'member_name':member,'member_ordinal':member_ordinal,'record_ordinal':record_ordinal,'source_format_ordinal':source_ordinal,'format':kind,
        'raw_record_bytes':len(raw),'raw_record_sha256':hashlib.sha256(raw).hexdigest(),'complete_record_boundary':complete,'native_title':token(title),
        'literal_identity_properties':dict(properties),'native_PDB_path_ID':pdb,'native_non_H_composition_evidence':comp,'native_table_metadata':metadata,
        'non_H_fallback_candidate_for_unresolved_MOL2_variant':comp if kind=='MOL2' else None,
        'native_table_error':error,'role':'ALL_ORIGINAL_SOURCE_MEMBERS','native_graph_state':'MOL2_FORMAL_CHARGE_STEREO_UNKNOWN' if kind=='MOL2' else 'NOT_YET_EXAMINED',
        'MOL2_partial_charge_is_formal_charge':False,'automatic_composition_exclusion':False}


class IDCSV(F.CSVProjection):
    """Same feed/append/finish grammar; callback selects one proven ID field only."""
    def __init__(self,column,emit):
        super().__init__('hiv');self.column=column;self.emit=emit;self.values={};self.ordinal=0
    def finish_field(self):
        if self.header is None:self.fields.append(bytes(self.buffer))
        elif self.field in self.selected:self.values[self.field]=bytes(self.buffer)
        self.field+=1;self.buffer.clear();self.field_start=True;self.after_quote=False
    def finish_record(self):
        self.finish_field()
        if self.header is None:
            self.header=[v.decode('utf-8-sig' if i==0 else 'utf-8') for i,v in enumerate(self.fields)];self.fields=[]
            positions=[0] if self.column==0 and self.header else [i for i,v in enumerate(self.header) if v==self.column]
            self.selected={i:'OPAQUE_ID' for i in positions}
        else:
            fields=[self.values.get(i) for i in self.selected];self.emit(self.ordinal,fields[0] if len(fields)==1 else None,
                {'original_ID_fields':[token(v) for v in fields],'row_width':self.field,'header_width':len(self.header),'unambiguous_literal_ID_column':len(fields)==1})
            self.ordinal+=1
        self.values={};self.field=0;self.row_bytes=0;self.started=False
    def summary(self):return {'literal_header':self.header,'selected_ID_columns':list(self.selected),'physical_rows':self.ordinal,'EOF_complete':self.complete,'assay_values_explicitly_decoded':False}


def initialize(plan):
    global FUNCTIONS
    Q.need(os.getuid()==1264 and os.environ.get('SLURM_CPUS_PER_TASK')=='16','ACTUAL_ALPHA_ALLOCATED_NATIVE_WORKER')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
    FUNCTIONS,_=load(plan)


def key_work(row,raw):
    from rdkit import Chem
    Q.need(row['format']=='SDF','MOL2_GRAPH_READER_FORBIDDEN')
    started=time.process_time();keys=set();native_keys=[];errors=[];kwargs={'sanitize':True,'removeHs':False,'strictParsing':False if row['source_id']=='qm8_sdf' else True}
    if not row['complete_record_boundary']:errors.append({'axis':'native_record','error':'SOURCE_RECORD_BOUNDARY_UNKNOWN_NOT_REPAIRED'})
    phase='source_byte_verification'
    try:
        Q.need(hashlib.sha256(raw).hexdigest()==row['raw_record_sha256'] and len(raw)==row['raw_record_bytes'],'EXACT_PROFILE_SOURCE_BYTES')
        phase='temporary_record_IO'
        with tempfile.TemporaryDirectory(prefix='native4_identity_',dir='/tmp') as directory:
            p=Path(directory)/'original.sdf';p.write_bytes(raw)
            phase='native_SDF_graph'
            with Chem.SDMolSupplier(str(p),**kwargs) as supplier:
                Q.need(len(supplier)==1,'EXACT_SINGLE_ORIGINAL_RECORD');mol=supplier[0]
                Q.need(mol is not None,'SOURCE_SDF_PARSER_NONE_UNKNOWN');key=Chem.MolToInchiKey(mol)
                valid,invalid=FUNCTIONS['full_keys']([key],strict=False);Q.need(valid and not invalid,'SOURCE_NATIVE_GRAPH_KEY_UNKNOWN');native_keys=valid;keys.update(valid)
    except Exception as exc:errors.append({'axis':phase,'error':type(exc).__name__+': '+str(exc)})
    variants=[]
    for name,values in row['literal_identity_properties'].items():
        if name not in ('smiles','canonical_smiles','isomeric_smiles','reidentified_smiles'):continue
        for i,value in enumerate(values):
            observed=[];problems=[]
            if value['state']=='LITERAL_UTF8' and value['text']:observed,problems=FUNCTIONS['source_smiles_keys']({name+':'+str(i):value['text']})
            else:problems=[{'error':'ORIGINAL_PRESENT_SMILES_EMPTY_OR_INVALID_UTF8_UNKNOWN'}]
            keys.update(observed);variants.append({'field':name,'variant':i,'original':value,'full_keys':observed,'errors':problems})
    return {'source':row,'native_SDF_full_keys':native_keys,'observed_full_key_union':sorted(keys),'WP5_key_union':sorted({FUNCTIONS['wp5_key'](k) for k in keys}),
        'variant_observations':variants,'native_graph_errors':errors,'has_unknown':bool(errors) or any(v['errors'] for v in variants),
        'source_only_reader_kwargs':kwargs,'PDB_source_only_seam_equals_author_repair_loader':False,
        'unresolved_native_graph_composition_evidence':row['native_non_H_composition_evidence'] if any(v['axis']=='native_SDF_graph' for v in errors) else None,
        'native_non_H_fallback_without_any_key':row['native_non_H_composition_evidence'] if any(v['axis']=='native_SDF_graph' for v in errors) and not keys else None,
        'technical_execution_is_chemical_exclusion':False,
        'composition_is_native_table_not_SMILES':True,'automatic_composition_exclusion_for_known_keys':False,'full_or_pool_release':False,
        'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-started}
