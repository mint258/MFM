"""Bounded native-format metadata and CSV identity-only byte projection."""
from __future__ import annotations
import collections,hashlib,json,re

CSV_IDS=('hiv','muv','pcba','sider','tox21','toxcast')
TAR_IDS=('qm8_sdf','pdbbind_general','pdbbind_refined','pdbbind_core')
OPAQUE_ID_COLUMNS={'hiv':(), 'muv':('mol_id',), 'pcba':('mol_id',), 'sider':(),
 'tox21':('mol_id','id','ID','name','Name'), 'toxcast':('mol_id','id','ID','name','Name')}
HEADER_CAP=64<<10
RECORD_CAP=8<<20
IDENTITY_FIELD_CAP=1<<20
NATIVE_CAP=1<<20

class UnknownFormat(ValueError):pass

def ensure(value,message):
    if not value:raise UnknownFormat(message)

class CSVProjection:
    """RFC4180 state machine: assay bytes are traversed, never text-decoded."""
    def __init__(self,source_id):
        ensure(source_id in CSV_IDS,'EXACT_CSV_SOURCE_REQUIRED');self.source_id=source_id
        self.header=None;self.names=[];self.selected={};self.stats={};self.counts=collections.Counter(
          physical_data_records=0,field_count_matches_header=0,field_count_below_header=0,field_count_above_header=0)
        self.field=0;self.fields=[];self.buffer=bytearray();self.field_start=True;self.quoted=False;self.after_quote=False
        self.pending_cr=False;self.started=False;self.row_bytes=0;self.decoded_bytes=0;self.complete=False
    def keep(self):return self.header is None or self.field in self.selected
    def append(self,value):
        if self.keep():
            self.buffer.append(value)
            ensure(len(self.buffer)<=(HEADER_CAP if self.header is None else IDENTITY_FIELD_CAP),'SELECTED_FIELD_SOFTWARE_BOUND_UNKNOWN')
    def finish_field(self):
        if self.header is None:self.fields.append(bytes(self.buffer))
        elif self.field in self.selected:
            item=self.stats[str(self.field)];item['observed_fields']+=1
            try:
                text=bytes(self.buffer).decode('utf-8');item['blank_fields']+=not text.strip()
                item['nonblank_fields']+=bool(text.strip())
            except UnicodeDecodeError:item['invalid_UTF8_fields']+=1
        self.field+=1;self.buffer.clear();self.field_start=True;self.after_quote=False
    def finish_record(self):
        self.finish_field()
        if self.header is None:
            self.header=[value.decode('utf-8-sig' if i==0 else 'utf-8') for i,value in enumerate(self.fields)]
            self.fields=[];self.names=list(self.header)
            allowed={'smiles',*OPAQUE_ID_COLUMNS[self.source_id]}
            self.selected={i:name for i,name in enumerate(self.header) if name in allowed}
            self.stats={str(i):{'literal_column_name':name,'column_index':i,'observed_fields':0,'blank_fields':0,
              'nonblank_fields':0,'invalid_UTF8_fields':0} for i,name in self.selected.items()}
        else:
            self.counts['physical_data_records']+=1
            self.counts['field_count_matches_header']+=self.field==len(self.header)
            self.counts['field_count_below_header']+=self.field<len(self.header)
            self.counts['field_count_above_header']+=self.field>len(self.header)
        self.field=0;self.row_bytes=0;self.started=False
    def feed(self,data):
        for value in data:
            self.decoded_bytes+=1
            if self.pending_cr:
                self.pending_cr=False
                if value==10:continue
            self.row_bytes+=1;self.started=True
            ensure(self.row_bytes<=(HEADER_CAP if self.header is None else RECORD_CAP),'CSV_RECORD_SOFTWARE_BOUND_UNKNOWN')
            if self.quoted:
                if value==34:self.quoted=False;self.after_quote=True
                else:self.append(value)
                continue
            if self.after_quote:
                if value==34:self.append(34);self.quoted=True;self.after_quote=False;continue
                ensure(value in (44,10,13),'NON_RFC4180_POST_QUOTE_UNKNOWN')
            if value==44:self.finish_field()
            elif value in (10,13):
                self.finish_record();self.pending_cr=value==13
            elif value==34:
                ensure(self.field_start,'NON_RFC4180_BARE_QUOTE_UNKNOWN');self.quoted=True;self.field_start=False
            else:self.field_start=False;self.append(value)
    def finish(self):
        ensure(not self.quoted,'TRUNCATED_QUOTED_RECORD_UNKNOWN')
        if self.started:self.finish_record()
        ensure(self.header is not None,'EMPTY_CSV_HEADER_UNOBSERVED');self.complete=True
        return self.summary()
    def summary(self):
        header=self.header or [];duplicates={k:v for k,v in collections.Counter(header).items() if v>1}
        smiles=[i for i,name in enumerate(header) if name=='smiles']
        observed={key:dict(value,missing_fields_in_completed_records=max(0,self.counts['physical_data_records']-value['observed_fields'])) for key,value in self.stats.items()}
        return {'literal_header':header,'header_columns':len(header),'duplicate_literal_header_names':duplicates,
          'smiles_column_indices':smiles,'smiles_schema_state':'EXACT_LOADER_COLUMN_OBSERVED' if len(smiles)==1 else 'MISSING_OR_AMBIGUOUS_UNKNOWN',
          'opaque_source_ID_columns':[name for name in header if name in OPAQUE_ID_COLUMNS[self.source_id]],
          'source_ID_semantics':'loader_declares_PubChem_CID_literal_preserved' if self.source_id in ('muv','pcba') else 'opaque_only_no_CID_assumption',
          'selected_column_observations':observed,'selected_column_counts_may_include_partial_current_record':not self.complete and self.started,
          'record_counts':dict(self.counts),'CSV_EOF_complete':self.complete,
          'CSV_decoded_bytes_traversed':self.decoded_bytes,'identity_values_persisted':False,'assay_values_text_decoded':False,
          'assay_values_numeric_decoded':False,'chemical_keys_computed':False,'rows_filtered':False,'identity_coverage_accepted':False}

def classify_member(source_id,row):
    name=row['name'].replace('\\','/');base=name.rsplit('/',1)[-1];lower=base.lower()
    if row.get('regular_member_sha256') is None:return 'nonregular_type_'+row['type_hex']
    if source_id=='qm8_sdf':
        if base=='qm8.sdf':return 'qm8_native_SDF_candidate'
        if base=='qm8.sdf.csv':return 'qm8_companion_ID_CSV_candidate'
    if lower.endswith('_ligand.sdf'):return 'native_ligand_SDF_candidate'
    if lower.endswith('_ligand.mol2'):return 'native_ligand_MOL2_candidate'
    expected={'pdbbind_general':'INDEX_general_PL_data.2019','pdbbind_refined':'INDEX_refined_data.2019','pdbbind_core':'pdbbind_v2013_core.csv'}
    if base==expected.get(source_id):return 'official_loader_index_basename_candidate'
    if lower.endswith(('_protein.pdb','_pocket.pdb')):return 'protein_or_pocket_excluded_from_small_molecule_identity'
    if lower.endswith('_ligand.pdb'):return 'ligand_PDB_not_used_for_connectivity'
    if lower.endswith('.sdf'):return 'other_SDF_unknown_mapping'
    if lower.endswith('.mol2'):return 'other_MOL2_unknown_mapping'
    return 'other_or_unknown'

def inventory_summary(source_id,rows):
    ensure(source_id in TAR_IDS,'EXACT_TAR_SOURCE_REQUIRED');counts=collections.Counter();names=collections.Counter();selected={};total=0;regular_bytes=0
    for row in rows:
        ensure(row['ordinal']==total,'INVENTORY_PHYSICAL_ORDINAL_NOT_CONTIGUOUS');total+=1
        category=classify_member(source_id,row);counts[category]+=1;names[row['name']]+=1
        if row.get('regular_member_sha256') is not None:regular_bytes+=row['declared_bytes']
        kind='SDF' if category in ('qm8_native_SDF_candidate','native_ligand_SDF_candidate') else 'MOL2' if category=='native_ligand_MOL2_candidate' else None
        if kind and kind not in selected:selected[kind]=dict(row,observed_category=category)
    ensure(sum(counts.values())==total,'ALL_MEMBER_CLASSIFICATION_MASS')
    return {'members':total,'category_counts':dict(counts),'regular_member_bytes':regular_bytes,
      'duplicate_member_names':sum(n>1 for n in names.values()),'duplicate_name_extra_occurrences':sum(n-1 for n in names.values()),
      'first_candidate_members_in_physical_order':selected,'classification_is_filename_evidence_not_final_prefix_or_identity_mapping':True,
      'component_overlap_and_index_ID_reconciliation':'PENDING_SEPARATE_IDENTITY_STAGE'}

def integer(value):
    try:return int(value.strip() or b'0')
    except (ValueError,TypeError):raise UnknownFormat('INVALID_DECLARED_NATIVE_COUNT')

def sdf_metadata(raw):
    ensure(len(raw)<=NATIVE_CAP,'SDF_RECORD_BOUND_UNKNOWN');lines=raw.splitlines()
    ensure(any(line.strip()==b'$$$$' for line in lines),'NO_COMPLETE_SDF_RECORD_WITHIN_BOUND')
    ensure(len(lines)>=5 and any(line.strip()==b'M  END' for line in lines),'NATIVE_M_END_NOT_OBSERVED')
    end=next(i for i,line in enumerate(lines) if line.strip()==b'$$$$');lines=lines[:end]
    prop=[]
    for line in lines:
        match=re.match(br'^>\s*<([^>]+)>',line)
        if match:prop.append(match.group(1).decode('utf-8',errors='replace'))
    dimension=re.findall(br'\b[23]D\b',lines[1] if len(lines)>1 else b'')
    counts=lines[3];version='V3000' if b'V3000' in counts else 'V2000' if b'V2000' in counts else 'UNKNOWN'
    markers={'M_CHG':any(line.startswith(b'M  CHG') for line in lines),'M_ISO':any(line.startswith(b'M  ISO') for line in lines),
      'atom_charge_code':False,'atom_mass_difference':False,'atom_stereo_marker':False,'bond_stereo_marker':False,
      'V3000_CHG':False,'V3000_MASS':False,'V3000_CFG':False}
    declared_atoms=declared_bonds=observed_atoms=observed_bonds=None
    if version=='V2000':
        declared_atoms=integer(counts[:3]);declared_bonds=integer(counts[3:6]);ensure(declared_atoms>=0 and declared_bonds>=0,'NEGATIVE_NATIVE_COUNT')
        atom_lines=lines[4:4+declared_atoms];bond_lines=lines[4+declared_atoms:4+declared_atoms+declared_bonds]
        observed_atoms=sum(len(line)>=34 and not line.startswith(b'M  ') for line in atom_lines)
        observed_bonds=sum(len(line)>=9 and not line.startswith(b'M  ') for line in bond_lines)
        def nonzero(value):return value.strip() not in (b'',b'0',b'000')
        markers.update(atom_charge_code=any(nonzero(line[36:39]) for line in atom_lines),
          atom_mass_difference=any(nonzero(line[34:36]) for line in atom_lines),atom_stereo_marker=any(nonzero(line[39:42]) for line in atom_lines),
          bond_stereo_marker=any(nonzero(line[9:12]) for line in bond_lines))
    elif version=='V3000':
        section=None;observed_atoms=observed_bonds=0;pending=b''
        for line in lines:
            if not line.startswith(b'M  V30 '):continue
            value=pending+line[7:];pending=b''
            if value.endswith(b'-'):pending=value[:-1];continue
            words=value.split()
            if words[:1]==[b'COUNTS']:
                ensure(len(words)>=3,'V3000_COUNTS_UNKNOWN');declared_atoms=integer(words[1]);declared_bonds=integer(words[2])
            elif value==b'BEGIN ATOM':section='ATOM'
            elif value==b'BEGIN BOND':section='BOND'
            elif value.startswith(b'END '):section=None
            elif section=='ATOM':observed_atoms+=1
            elif section=='BOND':observed_bonds+=1
            markers['V3000_CHG']|=b'CHG=' in value;markers['V3000_MASS']|=b'MASS=' in value;markers['V3000_CFG']|=b'CFG=' in value
        ensure(not pending,'V3000_CONTINUATION_UNKNOWN')
    return {'format':'SDF','version':version,'complete_record_boundary':True,'record_bytes':len(raw),'record_sha256':hashlib.sha256(raw).hexdigest(),
      'declared_atoms':declared_atoms,'declared_bonds':declared_bonds,'observed_atom_table_records':observed_atoms,'observed_bond_table_records':observed_bonds,
      'count_match':declared_atoms is not None and declared_bonds is not None and (declared_atoms,declared_bonds)==(observed_atoms,observed_bonds),
      'native_property_names':prop,'dimension_header_markers':[x.decode() for x in dimension],'native_marker_presence':markers,
      'coordinates_or_property_values_decoded':False,'molecular_titles_persisted':False,'graph_keys_computed':False,'native_graph_identity_accepted':False}

def mol2_metadata(raw,member_complete):
    ensure(len(raw)<=NATIVE_CAP,'MOL2_RECORD_BOUND_UNKNOWN');lines=raw.splitlines();starts=[i for i,line in enumerate(lines) if line.strip()==b'@<TRIPOS>MOLECULE']
    ensure(starts,'MOL2_MOLECULE_MARKER_UNKNOWN');start=starts[0]
    ensure(len(starts)>1 or member_complete,'NO_COMPLETE_MOL2_RECORD_WITHIN_BOUND')
    lines=lines[start:starts[1] if len(starts)>1 else len(lines)];ensure(len(lines)>=5,'MOL2_HEADER_INCOMPLETE')
    words=lines[2].split();ensure(len(words)>=2,'MOL2_DECLARED_COUNTS_UNKNOWN');atoms=integer(words[0]);bonds=integer(words[1])
    section=None;counts=collections.Counter();markers=[];partial=False
    for line in lines:
        if line.startswith(b'@<TRIPOS>'):section=line[9:].decode('ascii',errors='replace');markers.append(section);continue
        if not line.strip() or line.lstrip().startswith(b'#'):continue
        if section in ('ATOM','BOND'):
            counts[section]+=1
            if section=='ATOM':partial|=len(line.split())>=9
    return {'format':'MOL2','complete_record_boundary':True,'record_bytes':len(raw),'record_sha256':hashlib.sha256(raw).hexdigest(),
      'declared_atoms':atoms,'declared_bonds':bonds,'observed_atom_table_records':counts['ATOM'],'observed_bond_table_records':counts['BOND'],
      'count_match':atoms>=0 and bonds>=0 and (atoms,bonds)==(counts['ATOM'],counts['BOND']),
      'TRIPOS_sections':markers,'molecule_type_SMALL_marker_present':lines[3].strip()==b'SMALL',
      'charge_model_NO_CHARGES_marker_present':lines[4].strip()==b'NO_CHARGES',
      'charge_model_USER_CHARGES_marker_present':lines[4].strip()==b'USER_CHARGES','partial_charge_column_present':partial,
      'UNITY_ATOM_ATTR_marker_present':'UNITY_ATOM_ATTR' in markers,'native_formal_charge_assignment':'UNKNOWN_NOT_INFERRED',
      'native_isotope_assignment':'UNOBSERVED_NOT_INFERRED','stereo_assignment':'UNKNOWN_NOT_ASSIGNED_FROM_3D',
      'RDKit_MOL2_parser_called':False,'coordinates_or_charge_values_decoded':False,'molecule_name_persisted':False,'graph_keys_computed':False,'native_graph_identity_accepted':False}

def mat_metadata(variables):
    rows=[{'name':name,'shape':[int(x) for x in shape],'MATLAB_class':kind} for name,shape,kind in variables]
    candidates=[r['name'] for r in rows if r['name'].lower() in {'z','r','smiles','inchi','graph','molecules','atoms','bonds'}]
    unknown_names=[r['name'] for r in rows if r['name'] not in {'X','T','names'} and r['name'] not in candidates]
    state='CANDIDATE_VARIABLE_NAMES_UNVERIFIED' if candidates else 'UNKNOWN_ADDITIONAL_VARIABLE_SEMANTICS' if unknown_names or not rows else 'NO_DIRECT_SOURCE_GRAPH_IDENTITY'
    x=next((row for row in rows if row['name']=='X'),None);universe=None
    if x and len(x['shape'])==3 and x['shape'][1]==x['shape'][2]:universe=x['shape'][0]
    return {'variables':rows,'matrix_row_universe_from_actual_X_shape':universe,
      'direct_source_graph_identity':state,'unknown_variable_names':unknown_names,
      'candidate_variable_names':candidates,'variable_arrays_materialized':False,'loadmat_called':False,'QM7_Z7165_adapter_called':False,
      'Coulomb_feature_inversion':False,'QM7_QM9_row_alignment_assumed':False,'property_names_used_as_molecule_IDs':False,'identity_coverage_accepted':False}
