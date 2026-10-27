"""Author's direct SDMolSupplier API; original full-key and WP5 functions."""
import os,socket,tempfile,time
from pathlib import Path
from workflows.expansion.marcel_drugs_keys_main_v1.kernel import load
from . import contract as C,reader as V
FUNCTIONS=None


def graph_file(path,source,cached,functions):
    from rdkit import Chem
    expected=source['details'];observed={};issues=list(expected['issues']);key=None;atom_count=None
    if expected['format_state']!='SELECTED_SOURCE_FIELDS_OBSERVED':issues.append('ORIGINAL_SOURCE_RECORD_FORMAT_UNKNOWN')
    with Chem.SDMolSupplier(str(path),removeHs=False) as supplier:
        if len(supplier)!=1:raise ValueError('EXACT_SINGLE_ORIGINAL_SDF_RECORD_REQUIRED')
        mol=supplier[0]
        if mol is None:issues.append('AUTHOR_DEFAULT_SANITIZE_STRICT_PARSER_RETURNED_NONE_GRAPH_UNKNOWN')
        else:
            atom_count=mol.GetNumAtoms()
            for name in ('ID','smiles','_Name'):
                raw_expected=[V.V.token(v) for v in expected['properties'][name]] if name!='_Name' else [V.V.token(expected['title_name'])]
                try:literal=mol.GetProp(name) if mol.HasProp(name) else None;observed[name]=V.P.encoded(None if literal is None else literal.encode('utf-8'))
                except Exception as exc:observed[name]={'state':'RDKIT_PROPERTY_UNRESOLVED','error':type(exc).__name__+': '+str(exc)};issues.append(name+'_LITERAL_PROPERTY_UNKNOWN');continue
                if len(raw_expected)!=1 or raw_expected[0] is None or literal is None or literal.encode('utf-8')!=raw_expected[0]:issues.append(name+'_RAW_VS_AUTHOR_PROPERTY_BINDING_UNKNOWN')
            if expected['properties']['_Name']:issues.append('EXPLICIT_NAME_PROPERTY_VS_TITLE_AMBIGUOUS_UNKNOWN')
            candidate=Chem.MolToInchiKey(mol);valid,invalid=functions['full_keys']([candidate],strict=False)
            if invalid or len(valid)!=1:issues.append('NATIVE_GRAPH_FULL_INCHIKEY_UNKNOWN')
            else:key=valid[0]
    native_pairs=[] if key is None else [[key,functions['wp5_key'](key)]];source_pairs=cached['full_key_and_WP5_pairs'];source_keys={v[0] for v in source_pairs}
    mismatch=None if key is None or cached['has_any_unknown'] else {key}!=source_keys
    variants=[{'original_variant_index':v['original_variant_index'],'source_full_InChIKeys':v['full_InChIKeys'],
        'equals_native_graph_key':None if key is None or v['state']!='FULL_KEYS_DERIVED' else set(v['full_InChIKeys'])=={key}} for v in cached['variant_observations']]
    return {'source':source,'identity_state':'NATIVE_GRAPH_KEY_WITH_BINDING_UNKNOWN' if key and issues else 'NATIVE_GRAPH_FULL_KEY_DERIVED' if key else 'NATIVE_GRAPH_UNRESOLVED',
        'native_graph_full_key_and_WP5_pairs':native_pairs,'cached_source_SMILES_observation':cached,'conservative_all_observed_full_key_and_WP5_pairs':sorted({tuple(v) for v in [*native_pairs,*source_pairs]}),
        'has_any_unknown':bool(issues) or key is None or cached['has_any_unknown'],'native_graph_vs_source_key_set_mismatch':mismatch,'source_variant_comparisons':variants,
        'literal_author_properties':observed,'author_reader_atom_count_including_explicit_H':atom_count,'issues':issues,
        'author_reader':'Chem.SDMolSupplier(single_record_file,removeHs=False); sanitize/strictParsing default',
        'original_source_bytes_or_graph_edited':False,'representative_or_SMILES_fallback_used':False,'composition_fallback_claimed':False,
        'unknown_is_chemical_exclusion':False,'full_or_pool_release':False}


def initialize(source_refs):
    global FUNCTIONS
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    FUNCTIONS,_=load(source_refs)


def work(payload):
    started=time.process_time();source=payload['source'];cached=payload['cached_source_keys'];ref=payload['raw_record_reference']
    try:
        session=payload['allocation'];C.Q.need(os.getuid()==1278 and os.getppid()==session['parent_pid']
            and Path('/proc/'+str(os.getppid())+'/stat').read_text().rsplit(')',1)[1].split()[19]==session['parent_ticks']
            and os.environ.get('SLURM_JOB_ID')==session['job_id'] and socket.gethostname().split('.')[0]==session['node']
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],'SAME_LIVE_ADMITTED_PARENT_FOR_BOUNDED_GRAPH_READER')
        raw=V.segment(ref);V.bind_raw(raw,source);free=os.statvfs('/tmp')
        C.Q.need(free.f_bavail*free.f_frsize>=len(raw)+(1<<30),'NODE_LOCAL_SINGLE_RECORD_WITH1GiB_RESERVE')
        with tempfile.TemporaryDirectory(prefix='marcel_drugs_native_',dir='/tmp') as directory:
            path=Path(directory)/'original_record.sdf'
            with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            result=graph_file(path,source,cached,FUNCTIONS)
    except Exception as exc:result={'source':source,'identity_state':'TECHNICAL_NATIVE_GRAPH_UNRESOLVED','has_any_unknown':True,'native_graph_full_key_and_WP5_pairs':[],
        'cached_source_SMILES_observation':cached,'conservative_all_observed_full_key_and_WP5_pairs':cached['full_key_and_WP5_pairs'],
        'native_graph_vs_source_key_set_mismatch':None,'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False,
        'representative_or_SMILES_fallback_used':False,'full_or_pool_release':False}
    result['raw_record_reference']=ref
    return {'result':result,'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-started}
