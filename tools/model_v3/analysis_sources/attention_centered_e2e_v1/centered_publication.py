"""Metadata-only same-tree registration for the independent experiment branch."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_attention_centering_v1')
BASE_LOCAL = '4068623cc455915a34a4aacae4f0df5c56f691b7'
PARENT_PUBLIC = '5cdb2772dfa51e1cc72098c659fb741440219772'
BRANCH = 'model-v3-attention-centering-20261027-v1'
OLD_METADATA_EOL = frozenset(('docs/model_v3/numeric_stability_v1_SOURCE_PINS.json',
                             'docs/model_v3/numeric_stability_v1_VALIDATION_REQUEST.json'))
CRITICAL = frozenset(('current/phychem_mfm/model/attention.py','current/phychem_mfm/model/backbone.py',
    'current/phychem_mfm/model/shared.py','current/phychem_mfm/model/v3_architecture.py',
    'current/phychem_mfm/model/v3_attention_numerics.py','current/phychem_mfm/model/v3_numeric_stability.py',
    'current/phychem_mfm/model/v3_heads.py','current/phychem_mfm/model/v3_performance.py'))

def need(value,message):
    if not value:raise ValueError(message)

def reference(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2<<20,'Bounded source/metadata required')
    raw = path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def bound(value):
    need(reference(value['path']) == value,'Original publication/input raw reference differs')
    return json.loads(Path(value['path']).read_bytes())

def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def verify_publication(request):
    need(request['status'] == 'FINAL_BOUND_PUBLIC_EXPERIMENT_REQUEST'
        and request['repository'] == str(ROOT) and request['execution_branch'] == BRANCH
        and request['base_local_commit'] == BASE_LOCAL and request['parent_public_commit'] == PARENT_PUBLIC,
        'Only the independently published candidate branch may execute; a draft/reporting tree is not execution code')
    publication = bound(request['publication_receipt'])
    need(publication['schema'] == 'model_v3_numeric_candidate_publication_actual_v1'
        and publication['status'] == 'PUBLISHED_INDEPENDENT_PREREGISTRATION_BRANCH_READ_BACK'
        and publication['public_commit'] == request['public_commit']
        and publication['local_commit'] == request['local_commit']
        and publication['exact_shared_tree'] == request['exact_shared_tree']
        and publication['files'] == request['public_files'],'Actual independent public/local same-tree registration differs')
    paths = [x['path'] for x in request['public_files']]
    need(len(paths) == len(set(paths)) and set(paths) == set(request['required_public_paths'])
        and CRITICAL <= set(paths),'Required changed/critical candidate source registration incomplete')
    sources = {x['path']:x for x in request['source_refs']}
    rows = []
    for item in request['public_files']:
        rel = Path(item['path'])
        need(not rel.is_absolute() and '..' not in rel.parts,'Public source must stay inside candidate tree')
        path = ROOT/rel
        need(str(path) in sources and reference(path) == sources[str(path)],'Current raw runtime source differs')
        raw = path.read_bytes();projection = 'exact_raw';registered = raw
        if not (len(raw) == item['bytes'] and git_blob(raw) == item['git_blob_sha']):
            need(item['path'] in OLD_METADATA_EOL and raw.count(b'\r\n') > 0
                and raw.count(b'\r') == raw.count(b'\r\n'),'Only the two inherited metadata CRLF projections are allowed')
            registered = raw.replace(b'\r\n',b'\n');projection = 'registered_metadata_CRLF_to_LF'
        need(len(registered) == item['bytes'] and git_blob(registered) == item['git_blob_sha'],
             'Actual candidate file differs from registered Git blob')
        rows.append({'path':item['path'],'working_bytes':len(raw),'working_sha256':hashlib.sha256(raw).hexdigest(),
            'Git_projection':projection,'registered_Git_bytes':len(registered),'registered_Git_blob_sha':git_blob(registered)})
    # QA refs are preserved raw actual evidence supplied by Root after completion;
    # no fictitious parent C0 or guessed QA schema is manufactured by this writer.
    need(request['candidate_QA_evidence'],'Actual Root-reviewed candidate QA evidence refs required')
    for value in request['candidate_QA_evidence']:bound(value)
    return rows
