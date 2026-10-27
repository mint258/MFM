"""One Alpha SOURCE_CODE_ASSET snapshot protocol, fixed27 pure and stdlib port."""
import re
from pathlib import Path,PurePosixPath
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_source_snapshot_v2'
FILES=('__init__.py','contracts.py','guard.py','assets.py','run.py','test_v1.py','adapters.py','materialize.py','controller.py','README.md')
KEY='main_repository_exact_source_snapshot_alpha_v2';MODULE='secondary_source_snapshot_v2.run'
PLAN='ROOT_ALPHA_EXACT_SOURCE_SNAPSHOT_PLAN_V2_REVISION2';PROOF='ACTUAL_ALPHA_EXACT_SOURCE_SNAPSHOT_STARTUP_V2_REVISION2'
STAGE='MAIN_EXACT_SOURCE_SNAPSHOT_CHECKER_AND27_PURE_NO_SCIENCE';SCOPE='EXACT_MAIN_SOURCE_SNAPSHOT_ONLY_NO_MAIN_RUNTIME_OR_SCIENTIFIC_ACCEPTANCE'
CAP=2<<30;WALL=600;MAX_SOURCE=1<<30;MAX_ARCHIVE=512<<20;MAX_MEMBER=2<<20
PARAMETERS={'asset_kind':'SOURCE_CODE_ASSET','new_pure_methods':3,'all3_before_asset_body_and_Budget':True,'source_snapshot_full_bytes_equal':True,
 'original_check_repository':True,'verify_export':False,'server_sources_verified_is_unit_count':False,'normalization_cache_v2_stdlib_verify_port':True,
 'original_pure_groups':8,'original_pure_methods':27,'original_pure_group_method_counts':[3,3,3,3,6,3,3,3],'strict_adapter3':'DEFERRED_MAIN_ABSOLUTE_ENGINE_SOURCE_NOT_RUN',
 'no_constants_or_imports_modified':True,'no_Main_path_alias_or_mock':True,'new_native_invoke_UFF_QM_calls':0,
 'whole_output_cap_bytes':CAP,'wall_seconds':WALL,'allocated_cpus':16,'mode':'inventory','new_queue_algorithm':False}
PURE_MODULES=('workflows.data_v1_final.pprime.strict_numerics_qa_proposal_v1.test_v1',
 'workflows.data_v1_final.execution.sprime_wave2_recovery96_v1.test_contract',
 'workflows.data_v1_final.execution.sprime_wave2_controller_v4.test_recovery',
 'workflows.data_v1_final.execution.sprime_resource_epoch_v1.test_contract',
 'workflows.data_v1_final.labels.full_recovery_book_v1.test_recovery',
 'workflows.data_v1_final.labels.normalization_typed_cache_v1.test_boundaries',
 'workflows.expansion.common_molecular_fp_candidate_v1.test_boundaries',
 'workflows.data_v1_final.pprime.n1_geometry_domains_candidate_v1.test_boundaries')
PURE_METHOD_COUNTS=(3,3,3,3,6,3,3,3)
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
 'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')
GIT={ 'bin/native-git':3960424, 'lib/libpcre2-8.so.0':637880, 'lib/libz.so.1':102552, 'lib/libcrypto.so.3':4478832, 'lib/libc.so.6':2387248, 'lib/ld-linux-x86-64.so.2':842896}


def unique(refs):
    result={}
    for r in refs:
        Q.normalized(r);Q.need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_METADATA_REFS');result[r['path']]=r
    return [result[k] for k in sorted(result)]


def safe_relative(value):
    Q.need(type(value) is str and value and not any(c in value for c in ('\\','\0','\r','\n',':')),'LITERAL_POSIX_RELATIVE_SOURCE_PATH')
    p=PurePosixPath(value)
    Q.need(not p.is_absolute() and p.as_posix()==value and all(x not in ('','.','..','.git') for x in value.split('/')),
      'NO_ABSOLUTE_DOTDOT_DOTGIT_OR_NORMALIZED_ALIAS')
    return value


def entries(manifest,universe=None,git=False):
    Q.need(manifest['schema']==('ROOT_GIT2393_EXACT_SIX_ISOLATED_SOURCE_CHECK_ASSETS_V1' if git else 'ROOT_MAIN_GIT_LISTED_SOURCE_SNAPSHOT_ASSETS_V1'),
      'EXPLICIT_SOURCE_ASSET_MANIFEST')
    Q.need(manifest['origin_endpoint']=='202.38.247.57:22' and manifest['origin_uid']==1278,'ACTUAL_MAIN_SOURCE_ORIGIN_NOT_ALPHA_RESULT')
    rows={}
    for raw in manifest['files']:
        p=safe_relative(raw['relative_path']);r=raw['origin_reference']
        Q.need(p not in rows and type(r['bytes']) is int and 0<=r['bytes']<=(16<<20 if git else MAX_MEMBER)
          and re.fullmatch('[0-9a-f]{64}',r['sha256']),'UNIQUE_BOUNDED_SOURCE_FILE_BYTES_SHA')
        if not git:Q.need(manifest['origin_source_root']=='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository' and Path(r['path'])==Path(manifest['origin_source_root'])/p,'ORIGINAL_REPO_SOURCE_PATH_NOT_EXTERNAL_ASSET')
        mode=raw.get('git_mode','100644');Q.need(mode in ('100644','100755'),'REGULAR_SOURCE_FILES_ONLY')
        rows[p]={'path':p,'bytes':r['bytes'],'sha256':r['sha256'],'git_mode':mode,'origin_reference':r}
    Q.need(rows and sum(r['bytes'] for r in rows.values())<=(32<<20 if git else MAX_SOURCE),'FINITE_SOURCE_ASSET_TOTAL')
    if git:
        Q.need(set(rows)==set(GIT) and all(r['bytes']==GIT[p] for p,r in rows.items())
          and manifest['expected_git_version']=='git version 2.39.3' and manifest['binary_relative_path']=='bin/native-git'
          and manifest['loader_relative_path']=='lib/ld-linux-x86-64.so.2' and manifest['library_relative_path']=='lib'
          and manifest['original_wrapper_is_not_relocated_or_run'] is True,'EXACT_SIX_ORIGINAL_NATIVE_GIT_ASSETS')
    else:
        Q.need(universe['schema']=='MAIN_GIT_LISTED_SOURCE_UNIVERSE_V1' and universe['source_endpoint']=='202.38.247.57:22'
          and universe['uid']==1278 and universe['git_list_returncode']==0 and universe['git_list_argv']==['git','ls-files','--cached','--others','--exclude-standard','-z'],
          'INDEPENDENT_ACTUAL_MAIN_GIT_LIST_UNIVERSE')
        paths=universe['paths'];Q.need(type(paths) is list and len(paths)==len(set(paths)) and all(safe_relative(p)==p for p in paths)
          and set(paths)==set(rows),'NO_GIT_LISTED_SOURCE_OMITTED_OR_ADDED')
        Q.need('tools/check_repository.py' in rows and 'docs/SOURCE_MANIFEST.json' in rows,'ORIGINAL_CHECKER_AND_EXPORTED_MANIFEST_REQUIRED')
        forbidden={'.env','.netrc','.npmrc'};heavy={'.lmdb','.mdb','.parquet','.sqlite','.sqlite3','.pt','.pth','.ckpt','.npy','.npz','.sdf','.mol2','.pkl','.pickle','.zip','.gz','.tar','.7z','.csv','.bin','.arrow','.feather','.mol','.xyz','.db','.h5','.hdf5','.safetensors','.onnx','.bz2','.xz'}
        Q.need(all(PurePosixPath(p).name not in forbidden and PurePosixPath(p).suffix.lower() not in heavy for p in rows),'NO_SCIENTIFIC_DATA_ARCHIVE_OR_CREDENTIAL_AS_SOURCE')
    return rows

def inputs(plan):
    refs=[plan[k] for k in ('source_manifest_reference','source_universe_reference','git_manifest_reference','main_export_reference','native_git_transport_reference')]
    for r in refs:Q.need(r in plan['source_references'] and r in plan['parent_evidence_references'],'ALL_SMALL_TRANSITIVE_SOURCE_AUTHORITIES_DECLARED');Q.verify(r)
    sm,un,gm,export,transport=(Q.load_ref(r) for r in refs)
    source_rows=entries(sm,un);git_rows=entries(gm,git=True)
    Q.need(all(module.replace('.','/')+'.py' in source_rows for module in PURE_MODULES),
      'ALL_EIGHT_FIXED_ORIGINAL_TEST_MODULES_IN_MAIN_SOURCE_MANIFEST')
    Q.need(export['schema']=='ROOT_MAIN_SOURCE_SNAPSHOT_BYTE_EXPORT_V1'
      and export['source_endpoint']=='202.38.247.57:22' and export['uid']==1278 and export['scientific_DATA_files']==0 and export['AST_or_tests_run'] is False
      and export['git_metadata_or_credentials_in_archive'] is False and export['source_files']==len(source_rows)
      and export['source_bytes']==sum(r['bytes'] for r in source_rows.values()),'ACTUAL_MAIN_SOURCE_EXPORT_PROVENANCE_NOT_ALPHA_C0')
    for name,reference in (('manifest_reference',refs[0]),('universe_reference',refs[1])):
        origin=export[name];Q.need((origin['bytes'],origin['sha256'])==(reference['bytes'],reference['sha256']),'RELOCATED_METADATA_BYTE_EQUALITY')
    Q.need(transport['schema']=='ROOT_SOURCE_CHECK_GIT_SOFTWARE_ASSET_TRANSPORT_COMPLETED_V2'
      and transport['six_source_bytes_unchanged'] is True and transport['scientific_DATA_read'] is False,
      'ACTUAL_CLOSED_SIX_FILE_SOURCE_ASSET_PACKAGE')
    origin=transport['asset_manifest_reference'];Q.need((origin['bytes'],origin['sha256'])==(refs[2]['bytes'],refs[2]['sha256']),
      'ORIGINAL_GIT_MANIFEST_RELOCATED_WITH_IDENTICAL_BYTES')
    archives=[plan['source_archive_reference'],plan['git_archive_reference']]
    Q.need(plan['data_references']==archives and plan['source_code_asset_references']==archives,'ONLY_TWO_SOURCE_CODE_ASSET_TRANSPORT_SLOTS')
    for r in archives:
        Q.need(type(r) is dict and set(r)=={'path','bytes','sha256'} and type(r['bytes']) is int and re.fullmatch('[0-9a-f]{64}',r['sha256']),'EXACT_ARCHIVE_SOURCE_ASSET_TRIPLE');p=Q.literal(r['path']);Q.need(0<r['bytes']<=MAX_ARCHIVE and ROOT in p.parents,'BOUNDED_SOURCE_CODE_ASSET_ARCHIVE')
        info=p.stat();Q.need(p.is_file() and not p.is_symlink() and info.st_uid==1264 and info.st_size==r['bytes'],'ACTUAL_TRANSFERRED_SOURCE_ASSET_STAT_ONLY_NOT_SHA_CLAIM')
    for r,origin in ((archives[0],export['archive_reference']),(archives[1],transport['software_zip_reference'])):
        Q.need((r['bytes'],r['sha256'])==(origin['bytes'],origin['sha256']),'RELOCATED_ARCHIVE_SOURCE_BYTES_NOT_FUTURE_PIN')
    for r in plan['parent_evidence_references']:Q.need(r in plan['source_references'],'PARENT_IS_ACTUAL_SMALL_SOURCE_METADATA');Q.verify(r)
    return source_rows,git_rows
