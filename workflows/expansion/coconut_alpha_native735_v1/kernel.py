"""Decode original opaque COPY rows and observe the original formula function."""
import hashlib,importlib,io,json,re,sys
from pathlib import Path

OLD=('id','canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles','molecule_id','collection_id','status','is_invalid')
NATIVE=('molecular_formula','coconut_id','reference_id','doi','link','mol_filename','structural_comments','errors','error_code','cm_data','meta_data')
STATE={}


def need(ok,message):
    if not ok:raise ValueError(message)


def columns(header):
    # Deliberately narrow grammar for the witnessed original unquoted header.
    text=header.decode('ascii');match=re.fullmatch(r'COPY public\.entries \(([a-z_, ]+)\) FROM stdin;\n',text)
    need(match is not None,'EXACT_ORIGINAL_ENTRIES_COPY_HEADER')
    names=match[1].split(', ')
    need(len(names)==len(set(names)) and set(OLD+NATIVE)<=set(names),'COMPLETE_UNIQUE_COPY_COLUMNS')
    return names


def decode(raw,row,names,copy_text,field_cap):
    need(len(raw)==row['source_bytes'] and hashlib.sha256(raw).hexdigest()==row['source_row_sha256'],'SAME_OPAQUE_WHOLE_ROW_BYTES')
    wanted={i:name for i,name in enumerate(names) if name in OLD+NATIVE}
    reader=copy_text.Input(io.BytesIO(raw),lambda:None)
    value=copy_text.row(reader,len(names),wanted,field_cap)
    need(not value['end'] and value['bytes']==len(raw) and value['row_sha256']==row['source_row_sha256'],'WHOLE_ORIGINAL_COPY_ROW_WIDTH_AND_BOUNDARY')
    fields={name:value['fields'][i] for i,name in wanted.items()};original=json.loads(row['identity_fields_json'])
    need(set(original)==set(OLD) and all(fields[k]==original[k] for k in OLD),'ALL_EIGHT_ORIGINAL_IDENTITY_FIELDS_EXACT')
    need(row['source_table']=='entries' and row['copy_block']==1 and fields['molecule_id'] is None,'ORIGINAL_NULL_FK_NOT_REPARENTED')
    return {k:fields[k] for k in NATIVE}


def initialize(plan):
    from . import support as S
    root=Path(plan['original_source_root'])
    for ref in plan['original_source_references']:S.verify(ref)
    sys.path.append(str(root))
    import workflows.expansion as expansion
    old=str(root/'workflows/expansion');new_paths=list(expansion.__path__)
    kernel=importlib.import_module('secondary_coconut_strict5_day_v1.kernel')
    copy_text=importlib.import_module('secondary_coconut_sql_identity_v1.copy_text')
    # Only the original identity package/common imports use this search scope.
    # Restore the new workflow path before multiprocessing spawns the CLI.
    expansion.__path__[:]=[old,*[p for p in new_paths if p!=old]]
    try:projection=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    finally:expansion.__path__[:]=new_paths
    from rdkit import Chem,rdBase
    import numpy
    need(sys.version_info[:3]==(3,11,14) and rdBase.rdkitVersion=='2025.09.5' and numpy.__version__=='2.2.6','ORIGINAL_CHEMICAL_ENVIRONMENT')
    declared={r['path']:r for r in plan['original_source_references']}
    for name,module in list(sys.modules.items()):
        if name.startswith(('secondary_coconut_','secondary_cpu_queue_v1')) or name in ('workflows.expansion.common','workflows.expansion.identity_v2.projection_v2','workflows.expansion.identity_v2.readers_v2'):
            file=getattr(module,'__file__',None)
            if file and file.endswith('.py'):need(declared.get(str(Path(file).absolute()))==S.pin(file),'PINNED_ORIGINAL_IMPORTED_SOURCE:'+name)
    kernel.STATE.update(Chem=Chem,native=projection.native_composition)
    STATE.update(kernel=kernel,copy_text=copy_text)


def work(item):
    diagnosis,opaque,raw,names,cap=item
    row=opaque['source'];need(diagnosis['norm_observation']['source']==row,'SAME_DIAGNOSIS_AND_OPAQUE_SOURCE')
    need(diagnosis['original_UNKNOWN_unchanged'] is True and diagnosis['new_authoritative_keys'] is False
      and diagnosis['strict5_written'] is False and diagnosis['replay']['covered'] is False
      and diagnosis['norm_observation']['has_any_valid_full_key'] is False,'ORIGINAL_UNACCEPTED_UNKNOWN_NOT_UPGRADED')
    native=decode(raw,row,names,STATE['copy_text'],cap)
    formula=STATE['kernel'].formula(native['molecular_formula'])
    return dict(source=row,original_diagnosis=diagnosis,opaque_original_row_reference=opaque['opaque_original_row_reference'],
      supplemental_original_fields=native,native_formula_observation=formula,
      original_UNKNOWN_unchanged=True,graph_identity_repaired=False,new_authoritative_keys=False,
      native_formula_exclusion_accepted=False,official_reference_association_accepted=False,all11_ready=False)
