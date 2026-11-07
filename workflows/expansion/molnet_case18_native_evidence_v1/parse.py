"""Strict small CIF/field observations for three fixed peptide source entries."""
import collections
import hashlib
import re

SEQUENCE=('PHE','SER','HIS','PRO','GLN','ASN','THR')
COMPOSITION=[[6,36],[7,11],[8,12]]


def need(value,message):
    if not value:raise ValueError(message)


def exact(raw,ref):
    need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'EXACT_BOUND_BYTES_AND_SHA')
    return raw


def tokens(text):
    """CIF1 quoted/bare/semicolon text; quoted control-looking values stay values."""
    i=0;line=1;n=len(text)
    while i<n:
        c=text[i]
        if c.isspace():
            line+=c=='\n';i+=1;continue
        if c=='#':
            j=text.find('\n',i);i=n if j<0 else j;continue
        startline=line
        if c==';' and (i==0 or text[i-1]=='\n'):
            j=text.find('\n;',i+1);need(j>=0,'CLOSED_CIF_SEMICOLON_TEXT')
            end=j+2;need(end==n or text[end] in '\r\n','CIF_TEXT_DELIMITER_ALONE')
            value=text[i+1:j];line+=text[i:end].count('\n');i=end
            yield value,startline,True;continue
        if c in ('"',"'"):
            quote=c;j=i+1
            while j<n:
                need(text[j] not in '\r\n','CIF_QUOTE_CANNOT_CROSS_LINE')
                if text[j]==quote and (j+1==n or text[j+1].isspace()):break
                j+=1
            need(j<n,'CLOSED_CIF_QUOTED_VALUE');yield text[i+1:j],startline,True;i=j+1;continue
        j=i
        while j<n and not text[j].isspace():j+=1
        yield text[i:j],startline,False;i=j


def cif(raw):
    text=raw.decode('utf-8');ts=list(tokens(text));i=0;tables=collections.defaultdict(list);scalars={};blocks=[]
    def control(t):
        v,_,quoted=t
        return not quoted and (v.startswith('_') or v.lower()=='loop_' or v.lower().startswith(('data_','save_')) or v.lower()=='stop_')
    while i<len(ts):
        v,ln,q=ts[i];lower=v.lower()
        if not q and lower.startswith('data_'):blocks.append(v[5:]);i+=1;continue
        if not q and lower=='loop_':
            i+=1;columns=[]
            while i<len(ts) and not ts[i][2] and ts[i][0].startswith('_'):
                columns.append(ts[i][0]);i+=1
            need(columns and len(columns)==len(set(columns)),'CIF_LOOP_UNIQUE_COLUMNS')
            category=columns[0].split('.',1)[0]
            need(all(c.split('.',1)[0]==category for c in columns),'SINGLE_CIF_LOOP_CATEGORY')
            values=[]
            while i<len(ts) and not control(ts[i]):values.append(ts[i]);i+=1
            need(len(values)%len(columns)==0,'COMPLETE_CIF_LOOP_ROWS')
            if category in ('_entity_poly','_entity_poly_seq','_struct_asym','_atom_site','_struct_conn','_pdbx_struct_mod_residue'):
                names=[c.split('.',1)[1] for c in columns]
                for off in range(0,len(values),len(columns)):
                    row=dict(zip(names,[x[0] for x in values[off:off+len(columns)]]))
                    row['_source_line1']=values[off][1];tables[category].append(row)
            continue
        if not q and v.startswith('_'):
            need(i+1<len(ts) and not control(ts[i+1]) and v not in scalars,'CIF_UNIQUE_COMPLETE_SCALAR')
            scalars[v]=ts[i+1][0];i+=2;continue
        if not q and lower=='stop_':i+=1;continue
        raise ValueError('UNEXPECTED_CIF_TOKEN_LINE_'+str(ln))
    need(len(blocks)==1,'EXACT_SINGLE_ENTRY_CIF_BLOCK')
    return blocks[0],dict(tables),scalars


def atom_groups(rows,declared):
    grouped=collections.defaultdict(list)
    required=('label_entity_id','label_asym_id','auth_asym_id','label_seq_id','label_comp_id','label_atom_id',
              'label_alt_id','type_symbol','pdbx_PDB_model_num')
    for row in rows:
        need(all(k in row for k in required),'NAMED_ATOM_IDENTITY_COLUMNS')
        if row['label_entity_id']=='2':
            grouped[(row['pdbx_PDB_model_num'],row['label_asym_id'],row['auth_asym_id'])].append(row)
    out=[]
    for (model,chain,auth),allrows in sorted(grouped.items()):
        alts=sorted({r['label_alt_id'] for r in allrows}-{'.','?'}) or ['.']
        for alt in alts:
            chosen=[r for r in allrows if r['label_alt_id'] in ('.','?',alt)]
            sites=[(r['label_seq_id'],r['label_atom_id']) for r in chosen]
            need(len(sites)==len(set(sites)),'UNIQUE_SITES_WITH_SHARED_DOT_ONCE_PER_MODEL_ALT')
            need(all(r['label_seq_id'] in declared and r['label_comp_id']==declared[r['label_seq_id']] for r in chosen),
                 'OBSERVED_ATOM_RESIDUE_EQUALS_DECLARED_MONOMER')
            elements=collections.Counter(r['type_symbol'] for r in chosen if r['type_symbol'] not in ('H','D','T'))
            residues=sorted({int(r['label_seq_id']) for r in chosen})
            terminal=[dict(atom_id=r['label_atom_id'],seq_id=r['label_seq_id'],monomer=r['label_comp_id'],
                original_alt=r['label_alt_id'],source_line1=r['_source_line1'])
                for r in chosen if (r['label_seq_id']=='1' and r['label_atom_id'] in ('N','H1','H2','H3'))
                or (r['label_seq_id']=='7' and r['label_atom_id']=='OXT')]
            out.append(dict(model=model,label_asym_id=chain,auth_asym_id=auth,alternative=alt,
                shared_dot_counted_once=True,physical_atom_sites=len(chosen),observed_nonH_sites=sum(elements.values()),
                nonH_element_counts=dict(sorted(elements.items())),observed_residue_positions=residues,
                all_seven_declared_residue_positions_observed=residues==list(range(1,8)),
                observed59_nonH_and_seven_positions=(sum(elements.values())==59 and residues==list(range(1,8))),
                complete_chemical_graph_claimed=False,source_correspondence_or_termini_adopted=False,
                terminal_site_records=terminal))
    return out


def observe_cif(raw,entry):
    block,tables,scalars=cif(raw);need(block.upper()==entry,'EXACT_OFFICIAL_ENTRY_BLOCK')
    poly=[r for r in tables.get('_entity_poly',[]) if r['entity_id']=='2']
    need(len(poly)==1,'UNIQUE_DECLARED_ENTITY2')
    seq=sorted((r for r in tables.get('_entity_poly_seq',[]) if r['entity_id']=='2'),key=lambda r:int(r['num']))
    need([int(r['num']) for r in seq]==list(range(1,8)),'EXACT_SEVEN_SOURCE_MONOMER_POSITIONS')
    declared={r['num']:r['mon_id'] for r in seq}
    groups=atom_groups(tables.get('_atom_site',[]),declared)
    lines=raw.splitlines(keepends=True);offsets=[];offset=0
    for line in lines:offsets.append(offset);offset+=len(line)
    for g in groups:
        for site in g['terminal_site_records']:
            line1=site['source_line1'];line=lines[line1-1]
            site.update(offset=offsets[line1-1],bytes=len(line),line_sha256=hashlib.sha256(line).hexdigest())
    return dict(entry=entry,declared_polymer=poly[0],declared_sequence=[r['mon_id'] for r in seq],
        declared_monomer_rows=seq,declared_struct_asym=[r for r in tables.get('_struct_asym',[]) if r['entity_id']=='2'],
        groups=groups,struct_conn_records=tables.get('_struct_conn',[]),
        modification_records=tables.get('_pdbx_struct_mod_residue',[]),
        absent_category_does_not_prove_no_unreported_modification=True,
        coordinate_or_charge_values_decoded=False,graph_or_identity_adopted=False)


def formula_field(raw):
    lines=raw.splitlines(keepends=True)
    need(lines and lines[-1].strip()==b'$$$$','EXACT_COMPLETE_SDF_RECORD_BOUNDARY')
    found=[];offset=0
    for i,line in enumerate(lines):
        if line.rstrip(b'\r\n')==b'> <MOLECULAR_FORMULA>':
            value=[];j=i+1
            while j<len(lines) and lines[j].strip(b'\r\n'):
                value.append(lines[j]);j+=1
            found.append(dict(header_line1=i+1,header_offset=offset,
                whole_value=b''.join(value).rstrip(b'\r\n').decode('ascii'),
                value_raw_bytes=sum(map(len,value)),value_raw_sha256=hashlib.sha256(b''.join(value)).hexdigest()))
        offset+=len(line)
    need(len(found)==1 and found[0]['whole_value']=='C36H51N11O12','EXACT_WHOLE_FORMULA_FIELD_NO_PREFIX_OR_MULTIPLE_FIELDS')
    return found[0]
