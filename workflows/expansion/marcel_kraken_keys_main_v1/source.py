"""Reuse original archive gates and safe primitive decoder; never pickle.load."""
import hashlib,json,os,random,zipfile
from pathlib import Path
from workflows.expansion.marcel_kraken_primitive_structure_v1 import primitive as P,structure as S
from workflows.expansion.marcel_identity_format_probe_v1 import run as M
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from . import contract as C
Q=C.Q


def token(text):
    Q.need(type(text) is str,'ORIGINAL_NATIVE_UNICODE_TOKEN');raw=text.encode('utf-8',errors='surrogatepass')
    try:text.encode('utf-8');valid=True
    except UnicodeError:valid=False
    return {'text':text,'UTF8_surrogatepass_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'strict_UTF8_valid':valid}


def selected(mode):return set(random.Random(C.SEED).sample(range(C.CONF_N),C.PILOT_N)) if mode=='profile' else None


def decode(plan,old_observation,budget):
    arc=plan['archive_reference'];inv=plan['inventory_reference'];fr=M.verify_file(arc,budget.check);ifr=M.verify_file(inv,budget.check)
    Q.need(inv['bytes']<=64<<10,'BOUNDED_ORIGINAL_INVENTORY_AFTER_FIXTURES')
    with Path(inv['path']).open('rb') as f:
        Q.need(M.frame(os.fstat(f.fileno()))==ifr,'CURRENT_INVENTORY_FRAME');raw=f.read((64<<10)+1)
        Q.need(len(raw)==inv['bytes'] and hashlib.sha256(raw).hexdigest()==inv['sha256']
            and M.frame(os.fstat(f.fileno()))==ifr==M.frame(Path(inv['path']).lstat()),'CURRENT_INVENTORY_COMPLETE_SHA_FRAME')
    rows=[json.loads(line) for line in raw.splitlines()];Q.need(len(rows)==1 and rows[0]['name']=='Kraken.pickle'
        and rows[0]['decoded_bytes']==94805786 and rows[0]['EOF_CRC_passed'] is True,'EXACT_BOOTSTRAP_MEMBER')
    row=rows[0]
    with Path(arc['path']).open('rb') as f:
        Q.need(M.frame(os.fstat(f.fileno()))==fr,'CURRENT_ARCHIVE_FRAME');pre=A.preflight(f,arc['bytes']);f.seek(0)
        with zipfile.ZipFile(f,'r') as z:
            infos,_=A.directory(z,pre,row['decoded_bytes']);Q.need(len(infos)==1,'EXACT_ONE_MEMBER');info=infos[0]
            Q.need(not info.is_dir() and info.filename==row['name'] and info.file_size==row['decoded_bytes']
                and info.compress_size==row['compressed_bytes'] and info.CRC==row['CRC32_observed'],'CURRENT_EXACT_MEMBER_DIRECTORY')
            with z.open(info) as original:
                stream=M.Member(original,row,budget.check);root,decoded=P.Reader(stream,budget.check,row['decoded_bytes']).decode()
                while stream.read(1<<20):budget.check()
                member=stream.finish()
        Q.need(M.frame(os.fstat(f.fileno()))==fr==M.frame(Path(arc['path']).lstat()),'UNCHANGED_ARCHIVE_AFTER_EOF')
    shape=S.inspect(root)
    Q.need(decoded==old_observation['decoder'] and decoded['PROTO']==4 and decoded['STOP_at_EOF'] is True,'EXACT_FULL_NEW_DECODER_METADATA_EQUALS_ACTUAL1767')
    for field in ('status','root_type','root_mapping','primitive_graph','top_source_assignments','top_value_shape_counts','top_tuple3_values',
                  'secondary_source_assignments','secondary_value_shape_counts','secondary_tuple3_expected_type_matches','shape_issue_counts',
                  'matches_author_loader_expected_tuple_positions'):
        Q.need(shape[field]==old_observation['structure'][field],'CURRENT_EXACT_STRUCTURE_FIELD:'+field)
    return root,{'decoder':decoded,'member_current_EOF_CRC_SHA':member,'structure_status':shape['status'],
        'all_source_relationships':C.ROOT_N+C.CONF_N,'literal_examples_repeated_in_report':False}


def records(root):
    Q.need(type(root) is P.AssignmentMap and len(root.entries)==C.ROOT_N,'ALL_NATIVE_ROOT_ASSIGNMENTS');conf=0
    for ordinal,(native,value) in enumerate(root.entries):
        Q.need(type(native) is str and type(value) is tuple and len(value)==3,'EXACT_ROOT_SOURCE_SHAPE');smiles,_,conformers=value
        Q.need(type(smiles) is str and type(conformers) is P.AssignmentMap,'EXACT_NATIVE_ROOT_SOURCE_FIELDS')
        yield {'kind':'root_SMILES','root_assignment_ordinal':ordinal,'native_root_ID':token(native),
            'source_string':token(smiles),'source_tuple_position':0,'all_original_conformer_relationships':len(conformers.entries)}
        for subordinal,(native_conf,triplet) in enumerate(conformers.entries):
            Q.need(type(native_conf) is str and type(triplet) is tuple and len(triplet)==3 and type(triplet[0]) is str,'EXACT_NATIVE_CONFORMER_SOURCE_FIELDS')
            yield {'kind':'conformer_MolBlock','root_assignment_ordinal':ordinal,'native_root_ID':token(native),
                'secondary_assignment_ordinal':subordinal,'global_conformer_assignment_ordinal':conf,'native_conformer_ID':token(native_conf),
                'source_string':token(triplet[0]),'source_tuple_position':0}
            conf+=1
    Q.need(conf==C.CONF_N,'ALL_NATIVE_CONFORMER_ASSIGNMENTS_NO_CUTOFF')


def relationship(row,chosen):
    value=dict(row);text=value.pop('source_string');value['source_string_metadata']={k:v for k,v in text.items() if k!='text'}
    if row['kind']=='root_SMILES':value['original_root_SMILES']=text
    value.update(selected_for_key_projection=chosen,original_MolBlock_text_retained_in_pinned_archive=True,
        original_native_assignment_IDs_and_ordinals_unchanged=True,new_role_or_source_acceptance=False)
    return value
