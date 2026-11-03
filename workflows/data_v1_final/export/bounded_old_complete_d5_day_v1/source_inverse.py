"""Complete frozen-reader/function byte/AST inverse, direct scientific objects."""
import ast,hashlib,json
from pathlib import Path
from . import contract as C,produce as P,distributions as D
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import geometry as ORIGINAL_GEOMETRY
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.source_inverse import function_source
ORIGINS=json.loads(r'''[{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/d5_inputs_builder_v1/reader.py","bytes":7176,"sha256":"6d6c9a6ddac1099ea8b3caeaa9a9d82b116ece31c890ebaecf7d8bc5d4349bbb"},{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/postprocess_day_v1/worker.py","bytes":8794,"sha256":"62f8d7a0ca322afe2e22639c0d9872b7e54f7f99e416d731de117d8ba0f9d8e8"},{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/pipeline_v1/distributions.py","bytes":5389,"sha256":"042b91e545f7633b1def5cf664079a177c61efc6ef424de29f914ca49b425f55"}]''')

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
    worker=P.WORKER.proof()
    return {'status':'EXPLICIT_CANONICAL_POINTER_PATH_FD_SEAM_DIRECT_ORIGINAL_GRAPH_STEREO_CHILD_AND_RANDOM_OBJECTS',
      'native_path_semantic_delta':'canonical whole-SHA formal locator authority; resolve same original path; readonly FD target/alias/frame retained','worker_context':worker,'old_globals_patched':False,'new_QM_UFF_or_RMSD_HOF_called':False,
      'accepted_training_Pprime_empty_not_global_native_calls_zero':True,'new_final_Common_or_D6_authority':False}
