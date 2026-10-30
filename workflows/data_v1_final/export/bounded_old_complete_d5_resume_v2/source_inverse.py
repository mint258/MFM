"""Complete frozen-reader/function byte/AST inverse, direct scientific objects."""
import ast,hashlib,json
from pathlib import Path
from . import contract as C,produce as P,distributions as D
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import geometry as ORIGINAL_GEOMETRY
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.source_inverse import function_source
ORIGINS=json.loads(r'''[{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/d5_inputs_builder_v1/reader.py","bytes":7176,"sha256":"6d6c9a6ddac1099ea8b3caeaa9a9d82b116ece31c890ebaecf7d8bc5d4349bbb"},{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/postprocess_day_v1/worker.py","bytes":8794,"sha256":"62f8d7a0ca322afe2e22639c0d9872b7e54f7f99e416d731de117d8ba0f9d8e8"},{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/pipeline_v1/distributions.py","bytes":5389,"sha256":"042b91e545f7633b1def5cf664079a177c61efc6ef424de29f914ca49b425f55"}]''')

REVISION_ORIGINS=json.loads(r'''[
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/__init__.py",
        "sha256":  "63a7e9477cfbe665c0caef007eca42aa4f4f80fb24f435122273d896e1d3c747",
        "name":  "__init__.py",
        "bytes":  73
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/contract.py",
        "sha256":  "d6af3840e975a343bce2afa5638fbe697d0ba66c212c898e96ff5adfa2f92e12",
        "name":  "contract.py",
        "bytes":  8279
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/metadata.py",
        "sha256":  "a0c3f2f10fb0bdb476d5ddfbc7b78d2d60ae71069d6d22a398fcaf708f8f2fa5",
        "name":  "metadata.py",
        "bytes":  10243
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/adopt.py",
        "sha256":  "38020aa3e3323d19d02c3a84cf3bc1c299b2851a6daa4c31c2e3447516f9f3bf",
        "name":  "adopt.py",
        "bytes":  6528
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/produce.py",
        "sha256":  "d4f3e02a33c89737b99eef44290888585753ba194ce333de2c5fef5f1a9c4cee",
        "name":  "produce.py",
        "bytes":  21041
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/children.py",
        "sha256":  "0217320483efa8510898ee0cee271083c2ad0763cb881045fcd1e4ecc3cdb1f5",
        "name":  "children.py",
        "bytes":  2281
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/distributions.py",
        "sha256":  "19ce33960d0c75a71b328525c983f9364231f269b89938426ff74df4aa71fe80",
        "name":  "distributions.py",
        "bytes":  4094
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/run.py",
        "sha256":  "b076fb1f28e853cb51f817fdce986aab74994a0d6c9f85252a2c24d3ebb79636",
        "name":  "run.py",
        "bytes":  11303
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/source_inverse.py",
        "sha256":  "479ef11963a0d2f57456e1ec4d42c8430cbb6dbc48f133159dce2fb0d74a62cf",
        "name":  "source_inverse.py",
        "bytes":  4459
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/test_boundaries.py",
        "sha256":  "05ff5f20ed433bc103286ac4369bb84ed274a29177da9bbf87fb9e274b86543a",
        "name":  "test_boundaries.py",
        "bytes":  7085
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/README.md",
        "sha256":  "4bc065b5bafe11e70f5fcd5f9e86551b37c0bbe6903ff5e2b9419039397912b1",
        "name":  "README.md",
        "bytes":  12575
    },
    {
        "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/bounded_old_complete_d5_day_v1/resume.py",
        "sha256":  "10a3794287d32d94d9f4faddac092986e16bd2d2fb124d7045ee680d131ecec5",
        "name":  "resume.py",
        "bytes":  12192
    }
]''')

def proof():
    raw=[]
    for ref in ORIGINS:
        value=Path(ref['path']).read_bytes();C.need(len(value)==ref['bytes'] and hashlib.sha256(value).hexdigest()==ref['sha256'],'EXACT_FROZEN_ORIGINAL_SOURCE_BYTES')
        raw.append(value.decode())
    reader=raw[0].replace('def native_record(','def native_record_and_value(').replace('return mol,z,xyz','return mol,z,xyz,raw').replace('I.R.frame','NativeReader.I.R.frame')
    old_path="    project=pathlib.Path('/share/home/zixiao/descriptor_analysis');p=pathlib.Path(pointer['source_path'])\n    p=p if p.is_absolute() else project/p\n    C.need(project in p.parents and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'ORIGINAL_PROJECT_LITERAL_NATIVE_PATH')"
    C.need(reader.count(old_path)==1,'ONE_EXACT_LEGACY_WRAPPER_PATH_GUARD')
    reader=reader.replace(old_path,'    p=canonical_native_path(pointer);target=p.resolve(strict=True)')
    reader=reader.replace('before=p.lstat();','before=target.stat();').replace('NATIVE_FRAMES.setdefault(str(p),','NATIVE_FRAMES.setdefault(str(target),')
    reader=reader.replace('fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)','fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW)')
    reader=reader.replace("==NativeReader.I.R.frame(p.lstat()),'NATIVE_FRAME_AND_ATOM_COUNT_STABLE')","==NativeReader.I.R.frame(p.stat()) and p.resolve(strict=True)==target,'NATIVE_FRAME_AND_ATOM_COUNT_STABLE')")
    current=Path(P.__file__).read_bytes().decode()
    C.need(function_source(current,'native_record_and_value')==function_source(reader,'native_record_and_value'),
        'EXACT_DECLARED_CANONICAL_FORMAL_PATH_RESOLUTION_FD_SEAM_ORIGINAL_READ_GRAPH_AND_PAYLOAD_GUARDS')
    old=raw[1];a=old.index('    for row in sprime:');b=old.index('    distance =',a);block=old[a:b]
    C.need(block in current and current.count(block)==1,'ENTIRE_ORIGINAL_ACCEPTED_SPRIME_STEREO_F64_BLOCK_NOT_REIMPLEMENTED')
    expected=raw[2].replace('"D5_PARQUET_LISTS_FROZEN"','"BOUNDED_OLD_COMPLETE_D5_LISTS_CPU_VERIFIED_PENDING_ROOT"')
    C.need(function_source(Path(D.__file__).read_bytes().decode(),'run')==function_source(expected,'run'),
        'ENTIRE_ORIGINAL_DISTRIBUTION_RUN_ONLY_BOUNDED_INPUT_STATUS_BYTES_AND_AST')
    C.need(P.IO is P.G.OriginalWorker.IO and D.dimension_worker is D.Original.dimension_worker
        and P.G.metadata_children is ORIGINAL_GEOMETRY.metadata_children and P.G.OriginalMath.scaffold_chunk is P.G.OriginalMath.ORIGINAL.scaffold_chunk,
        'DIRECT_ORIGINAL_SHA_CHILD_RENDERER_SCAFFOLD_AND_DISTRIBUTION_WORKER_OBJECTS')
    from .adopt import H
    from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import hof_resume
    C.need(H.clone is hof_resume.clone and H.restore_priority is hof_resume.restore_priority,'DIRECT_ORIGINAL_CLOSED_BYTE_COPY_AND_FROZEN_SELECTION_SQL_READBACK')
    revision_sources={}
    for ref in REVISION_ORIGINS:
        value=Path(ref['path']).read_bytes()
        C.need(len(value)==ref['bytes'] and hashlib.sha256(value).hexdigest()==ref['sha256'],'OLD_D5_SOURCE12_CURRENT_BYTES_REMAIN_FROZEN_FOR_LIVE_D4_D3')
        revision_sources[Path(ref['path']).name]=value.decode()
    previous=revision_sources['produce.py']
    for name in ('canonical_native_path','native_record_and_value','checked_uff','feature_chunk','scalar_indices','schema_features','_rows','parquet_query'):
        C.need(function_source(previous,name)==function_source(current,name),'ORIGINAL_D5_SCIENCE_AND_FROZEN_SELECTION_FUNCTION_BYTES:'+name)
    C.need("CREATE TABLE selected(job TEXT PRIMARY KEY)"in previous and "CREATE TABLE selected(job INTEGER PRIMARY KEY)"in current,
        'EXPLICIT_OWNER_JOB_STORAGE_TYPE_ONLY_NOT_CANONICAL_ID_OR_CHILD_MATH_CHANGE')
    from . import adopt as A
    sentinel=object();private=A.child_function(sentinel);oldchild=ORIGINAL_GEOMETRY.metadata_children
    C.need(private.__code__ is oldchild.__code__ and private.__defaults__==oldchild.__defaults__
        and private.__closure__ is oldchild.__closure__ and private.__globals__['I'] is sentinel
        and set(private.__globals__)==set(oldchild.__globals__)
        and all(private.__globals__[k] is v for k,v in oldchild.__globals__.items() if k!='I'),
        'WHOLE_ORIGINAL_CHILD_CODE_ONLY_PRIVATE_RESOURCE_IO_BINDING_NOT_SHARED_GLOBAL_PATCH')
    C.need(A.NativeCensus.ResourceBudget.__bases__==(ORIGINAL_GEOMETRY.I.Budget,)
        and A.D3IO.NativeCensus is A.NativeCensus,'EXACT_FROZEN_NATIVE8_RESOURCE_BUDGET_AND_D3_R6_PRIVATE_IO_HELPER')
    worker=P.WORKER.proof()
    return {'status':'EXPLICIT_CANONICAL_POINTER_PATH_FD_SEAM_DIRECT_ORIGINAL_GRAPH_STEREO_CHILD_AND_RANDOM_OBJECTS',
      'resource_IO_r2':'exact Native8 ResourceBudget instance; bounded full census and private original report/event/child IO via frozen D3R6 helper; no shared globals changed',
      'resume_IO_semantic_delta':'fixed failed5160+5178 origin parts and complete tables; positive INTEGER owner job; no native rework; original child/math objects unchanged',
      'native_path_semantic_delta':'canonical whole-SHA formal locator authority; resolve same original path; readonly FD target/alias/frame retained','worker_context':worker,'old_globals_patched':False,'new_QM_UFF_or_RMSD_HOF_called':False,
      'accepted_training_Pprime_empty_not_global_native_calls_zero':True,'new_final_Common_or_D6_authority':False}
