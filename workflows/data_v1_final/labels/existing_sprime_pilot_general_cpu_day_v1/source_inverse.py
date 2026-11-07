"""CPU-before-DATA exact full-module/source and scientific-object witnesses."""
import ast,hashlib,json
from pathlib import Path
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import bindings as B,geometry as OLD,source_inverse as ORIGINAL_INVERSE
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.source_inverse import function_source
ORIGIN=json.loads(r'''{"schema":"EXISTING_SPRIME_GENERAL_CPU_RESOURCE_SOURCE_WITNESS_V1","origins":[{"name":"contract.py","reference":{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/existing_sprime_pilot_day_v1/contract.py","bytes":12196,"sha256":"4967738facb0233120aa4960b9fd80b538fe54a121c61ffa32a6064073c97287"},"replacements":[{"old":"labels/existing_sprime_pilot_day_v1","new":"labels/existing_sprime_pilot_general_cpu_day_v1"},{"old":"KEY=\u0027existing_complete_sprime_pilot_day_v1\u0027","new":"KEY=\u0027existing_sprime_pilot_general_cpu_day_v1\u0027"},{"old":"labels.existing_sprime_pilot_day_v1.run","new":"labels.existing_sprime_pilot_general_cpu_day_v1.run"},{"old":"EXISTING_COMPLETE_SPRIME_PILOT_DAY_PLAN_V1","new":"EXISTING_SPRIME_PILOT_GENERAL_CPU_DAY_PLAN_V1"},{"old":"FILES=(\u0027__init__.py\u0027,\u0027contract.py\u0027,\u0027bindings.py\u0027,\u0027memory.py\u0027,\u0027io.py\u0027,\u0027reader.py\u0027,\u0027coverage.py\u0027,\u0027geometry.py\u0027,\u0027eligibility.py\u0027,\u0027loss.py\u0027,\n    \u0027statistics.py\u0027,\u0027run.py\u0027,\u0027metadata.py\u0027,\u0027source_inverse.py\u0027,\u0027test_boundaries.py\u0027,\u0027frozen_source_witness.json\u0027,\u0027README.md\u0027,\u0027originals.py\u0027)\n","new":"FILES=(\u0027__init__.py\u0027,\u0027contract.py\u0027,\u0027run.py\u0027,\u0027metadata.py\u0027,\u0027geometry.py\u0027,\u0027source_inverse.py\u0027,\u0027test_boundaries.py\u0027,\u0027README.md\u0027)\r\n"},{"old":"artifacts/labels/source_status_v1/existing_sprime_pilot_day_v1","new":"artifacts/labels/source_status_v1/existing_sprime_pilot_general_cpu_day_v1"}]},{"name":"run.py","reference":{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/existing_sprime_pilot_day_v1/run.py","bytes":14148,"sha256":"e63b71a26ce16192deafac394a19d8fc1544e6ed499189a073519b06c8d9cf7c"},"replacements":[{"old":"from . import contract as C,io as I,bindings as B,coverage as V,geometry as G,eligibility as E,statistics as T,loss as L","new":"from . import contract as C,geometry as G\r\nfrom workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,bindings as B,coverage as V,eligibility as E,statistics as T,loss as L"}]},{"name":"metadata.py","reference":{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/existing_sprime_pilot_day_v1/metadata.py","bytes":15003,"sha256":"d88919a55b8ee858be6a741b78d9a298af7845e84fe70d3c12ba1ffc46d1abc4"},"replacements":[{"old":"ROOT_REQUESTED_EXISTING_COMPLETE_SPRIME_PILOT_DAY_V1","new":"ROOT_REQUESTED_EXISTING_SPRIME_PILOT_GENERAL_CPU_DAY_V1"},{"old":"EXISTING_COMPLETE_SPRIME_PILOT_DAY_PLAN_V1","new":"EXISTING_SPRIME_PILOT_GENERAL_CPU_DAY_PLAN_V1"},{"old":"    result.extend(P.source_paths())","new":"    result.extend(P.source_paths())\r\n    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import metadata as OLD\r\n    result.extend(OLD.source_paths())"},{"old":"    result.extend(OLD.source_paths())","new":"    result.extend(OLD.source_paths())\r\n    from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import metadata as GENERAL_WORKER\r\n    result.extend(GENERAL_WORKER.source_paths())"}]},{"name":"geometry.py","reference":{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/existing_sprime_pilot_day_v1/geometry.py","bytes":33381,"sha256":"60b8b7e344ecbd28c78fc2ae83ad2a41cd58541d36ab711469c08e83f19d2f25"}}],"geometry_resource_preamble":"\"\"\"Truthful general CPU native context; all original numerical objects retained.\"\"\"\nimport collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat,struct,socket\nfrom . import contract as C\nfrom workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,geometry as OLD\nfrom workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import worker_context as WORKER\nCacheIO=OLD.CacheIO;CacheMeta=OLD.CacheMeta;OriginalWorker=OLD.OriginalWorker;OriginalMath=OLD.OriginalMath\nChild=OLD.Child;Wire=OLD.Wire;Geometry=OLD.Geometry;PC=OLD.PC\nsqlite_ro=OLD.sqlite_ro;lookup_batch=OLD.lookup_batch;classify_owner=OLD.classify_owner\nCacheContext=OLD.CacheContext;gid=OLD.gid;metadata_children=OLD.metadata_children\n\ndef validate_worker_identity(proof,facts):\n    req=proof[\u0027request\u0027];C.need(facts[\u0027uid\u0027]==1278 and facts[\u0027node\u0027]==req[\u0027node\u0027] and req[\u0027node\u0027] in WORKER.I.M.ANALYSIS_NODES\n        and req[\u0027cpus\u0027]==16 and facts[\u0027cpus\u0027]==16 and facts[\u0027job_id\u0027]==str(proof[\u0027job_id\u0027])\n        and facts[\u0027partition\u0027]==\u0027cpu\u0027 and facts[\u0027cuda_visible_devices\u0027]==\u0027\u0027 and facts[\u0027boot_id\u0027]==proof[\u0027boot_id\u0027],\n        \u0027TRUTHFUL_GENERAL_CPU16_CURRENT_WORKER_NOT_FAKE_OLD14_OR18\u0027)\n\ndef original_worker_init(proof):\n    facts={\u0027uid\u0027:os.getuid(),\u0027node\u0027:socket.gethostname().split(\u0027.\u0027)[0],\u0027cpus\u0027:int(os.environ.get(\u0027SLURM_CPUS_PER_TASK\u0027,\u00270\u0027)),\n        \u0027job_id\u0027:os.environ.get(\u0027SLURM_JOB_ID\u0027),\u0027partition\u0027:os.environ.get(\u0027SLURM_JOB_PARTITION\u0027),\n        \u0027cuda_visible_devices\u0027:os.environ.get(\u0027CUDA_VISIBLE_DEVICES\u0027),\u0027boot_id\u0027:pathlib.Path(\u0027/proc/sys/kernel/random/boot_id\u0027).read_text().strip()}\n    validate_worker_identity(proof,facts)\n    WORKER.initialize({\u0027proof\u0027:proof})\n\r\n","compute_context_old":"native=OriginalWorker.SCIENCE","compute_context_new":"native=WORKER.SCIENCE"}''')

def proof():
    results={};raws={}
    for item in ORIGIN['origins']:
        ref=item['reference'];raw=Path(ref['path']).read_bytes()
        C.need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],
            'EXACT_FROZEN_OLD_D4_ROOT_MODULE_NOT_HOTPATCHED:'+item['name'])
        raws[item['name']]=raw
        if item['name']=='geometry.py':continue
        expected=raw.decode('utf-8')
        for delta in item['replacements']:expected=expected.replace(delta['old'],delta['new'])
        current=(C.HERE/item['name']).read_bytes()
        C.need(current==expected.encode('utf-8'),'WHOLE_MODULE_ONLY_DECLARED_GENERAL_RESOURCE_NAMESPACE_DELTA:'+item['name'])
        C.need(ast.dump(ast.parse(current),include_attributes=False)==ast.dump(ast.parse(expected),include_attributes=False),
            'WHOLE_MODULE_RESOURCE_INVERSE_AST:'+item['name'])
        results[item['name']]='EXACT_COMPLETE_MODULE_INVERSE_BYTES_AND_AST'
    old=raws['geometry.py'].decode('utf-8')
    # Match the original full source sections, including whitespace between functions.
    begin=old.index('def compute(');end=old.index('def metadata_children(')
    section=old[begin:end]
    C.need(section.count(ORIGIN['compute_context_old'])==1,'ONLY_ONE_EXPLICIT_NATIVE_WORKER_CONTEXT_BINDING')
    expected=ORIGIN['geometry_resource_preamble']+section.replace(ORIGIN['compute_context_old'],ORIGIN['compute_context_new'])
    current=(C.HERE/'geometry.py').read_bytes()
    C.need(current==expected.encode('utf-8'),'WHOLE_GEOMETRY_ONLY_EXPLICIT_RESOURCE_PREAMBLE_AND_NATIVE_GLOBAL_CONTEXT')
    source=current.decode('utf-8')
    C.need(function_source(source,'build')==function_source(old,'build'),'ENTIRE_ORIGINAL_GEOMETRY_BUILD_BYTES_AND_AST')
    C.need(function_source(source,'compute')==function_source(old.replace(ORIGIN['compute_context_old'],ORIGIN['compute_context_new']),'compute'),
        'ENTIRE_ORIGINAL_GEOMETRY_COMPUTE_ONLY_NATIVE_CONTEXT_BYTES_AND_AST')
    C.need(G.gid is OLD.gid and G.CacheContext is OLD.CacheContext and G.metadata_children is OLD.metadata_children,
        'DIRECT_ORIGINAL_GEOMETRY_ID_CACHE_CONTEXT_AND_EXACT_INPUT_CHILD_OBJECTS')
    C.need(G.OriginalWorker is OLD.OriginalWorker and G.OriginalMath is OLD.OriginalMath
        and G.WORKER.d7 is OLD.OriginalWorker.d7 and G.WORKER.pm7_compute is OLD.OriginalWorker.pm7_compute,
        'DIRECT_ORIGINAL_D7_PM7_MATH_OBJECTS_NO_ORIGINAL_GLOBAL_WRITES')
    C.need(G.WORKER is not G.OriginalWorker and G.WORKER.I is not G.OriginalWorker.I,
        'ISOLATED_REAL_GENERAL_CPU_CONTEXT_NOT_FAKE_OLD_WORKER_IDENTITY')
    B.verify();original=ORIGINAL_INVERSE.proof();worker=G.WORKER.proof()
    return {'status':'EXACT_GENERAL_CPU_RESOURCE_MODULE_INVERSES_AND_DIRECT_ORIGINAL_SCIENTIFIC_OBJECTS',
        'module_inverses':results,'geometry_build':'ENTIRE_ORIGINAL_BYTES_AND_AST',
        'geometry_compute_delta':'ONLY_NATIVE_EQUALS_GENERAL_WORKER_SCIENCE',
        'original_D4_source_inverse':original,'validated_general_worker_inverse':worker,
        'original_TSQR_chunk':256,'original_QR_reduction':'ORIGINAL_LOGICAL_OWNER_GROUP_ORDERED_LEFT_FOLD',
        'scientific_math_recipe_seed_threshold_changed':False,'old_globals_patched':False,
        'old_source_or_book_or_claim_written':False,'scientific_DATA_read_or_native_called':False}