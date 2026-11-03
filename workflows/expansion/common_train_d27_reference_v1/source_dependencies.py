"""AST-only imported-source closure; no project imports, native jobs or data IO."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOTS={
 'codec':'workflows.data_v1_final.labels.normalization_compact_runtime_v3.codec',
 'calibration':'workflows.data_v1_final.labels.streaming_v1.calibration',
 'compact':'workflows.data_v1_final.labels.streaming_v1.compact',
 'projection':'workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection',
 'owner_support':'workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support'}
EXACT=('__init__.py','engine.py','cache.py','alpha_common.py','alpha_common_repaired.py','test_alpha_common.py')


def need(ok,message):
    if not ok:raise ValueError(message)


def pin(path):
    path=Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Immutable source changed')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),raw


def module_file(repo,module):
    base=repo.joinpath(*module.split('.'))
    if base.with_suffix('.py').is_file():return base.with_suffix('.py')
    if(base/'__init__.py').is_file():return base/'__init__.py'
    return None


def imported_nodes(tree):
    # Import-time closure only. Old CLI/worker bodies are not executed on import.
    def visit(node):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)):return
        if isinstance(node,ast.If)and '__name__'in ast.unparse(node.test):return
        yield node
        for child in ast.iter_child_nodes(node):yield from visit(child)
    yield from visit(tree)


def collect(repository,catalog_path,output):
    repo=Path(repository).resolve();need(os.getuid()==1278,'Actual Main source metadata only')
    files={};pending=list(ROOTS.values());edges=[];external=[];calls=[];namespace=set()
    def add(module):
        path=module_file(repo,module)
        if path is not None and module not in files and module not in pending:pending.append(module)
        return path
    while pending:
        module=pending.pop()
        if module in files:continue
        path=module_file(repo,module);need(path is not None,'Missing actual original source:'+module)
        ref,raw=pin(path);tree=ast.parse(raw,filename=str(path))
        files[module]=dict(module=module,relative_path=str(path.relative_to(repo)),source_reference=ref)
        parts=module.split('.')
        for i in range(1,len(parts)):
            package='.'.join(parts[:i]);init=module_file(repo,package)
            if init is not None:add(package)
            else:namespace.add(package)
        package=module if path.name=='__init__.py'else module.rsplit('.',1)[0]
        for node in imported_nodes(tree):
            names=[]
            if isinstance(node,ast.Import):names=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                base=importlib.util.resolve_name('.'*node.level+(node.module or ''),package)if node.level else node.module
                if base:
                    names=[base]+[base+'.'+a.name for a in node.names if a.name!='*']
            elif isinstance(node,ast.Call):
                text=ast.unparse(node.func)
                if any(token in text for token in('read_text','read_bytes','open','import_module','spec_from_file_location')):
                    calls.append(dict(module=module,line=node.lineno,expression=ast.unparse(node)[:300]))
            for name in names:
                if name.startswith('workflows.'):
                    if add(name) is not None:edges.append(dict(importer=module,imported=name,line=node.lineno))
                elif '.'not in name:external.append(dict(importer=module,name=name,line=node.lineno))
    catalog_ref,catalog_raw=pin(catalog_path);catalog=json.loads(catalog_raw)
    configs=[]
    for ref in catalog['origin_manifest_references']:
        actual,raw=pin(ref['path']);need(actual==ref,'Original closed origin pin differs')
        cfgref=json.loads(raw)['config'];actual,raw=pin(cfgref['path']);need(actual==cfgref,'Original source config pin differs')
        configs.append(dict(config_reference=cfgref,original_scientific_source_pins=json.loads(raw)['science']['adapter_source_pins']))
    maskpins={}
    for cfg in configs:
        for ref in cfg['original_scientific_source_pins']:
            actual,_=pin(ref['path']);need(actual==ref,'Original scientific binding changed')
            relative=str(Path(ref['path']).relative_to(Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository')))
            deployed,_=pin(repo/relative);need((deployed['bytes'],deployed['sha256'])==(ref['bytes'],ref['sha256']),'Original scientific bytes differ in selected repository')
            maskpins[ref['path']]=dict(original_reference=ref,repository_reference=deployed,relative_path=relative)
    exact=[]
    for name in EXACT:
        path=repo/'workflows/expansion/exact_nn_cached_v1'/name;ref,_=pin(path)
        exact.append(dict(relative_path=str(path.relative_to(repo)),source_reference=ref))
    need(not calls,'Import-time source IO/dynamic import requires explicit review before capsule publication')
    rows=sorted(files.values(),key=lambda r:r['relative_path'])
    result=dict(schema='PUBCHEM_D27_IMPORTED_SOURCE_CAPSULE_INVENTORY_V1',status='AST_SOURCE_CLOSURE_ONLY_NATIVE_IMPORT_PENDING',
        repository=str(repo),origin_endpoint='202.38.247.57:22',origin_uid=1278,scientific_module_roots=ROOTS,
        scientific_source_references={key:files[module]['source_reference']for key,module in ROOTS.items()},
        imported_source_files=rows,imported_source_bytes=sum(row['source_reference']['bytes']for row in rows),
        import_edges=edges,namespace_packages_without_source_init=sorted(namespace),
        nonproject_import_names=sorted({row['name']for row in external}),import_time_source_IO_or_dynamic_calls=calls,
        exact_overlay_required_files=exact,original_source_catalog_reference=catalog_ref,
        five_origin_source_bindings=configs,original_scientific_pins=list(maskpins.values()),
        no_scientific_module_imported=True,no_label_geometry_or_QM_data_opened=True,
        old_function_local_legacy_paths_not_executed=True,
        actual_Alpha_capsule_refs_and_science_load_identity_proof='PENDING_ROOT_NATIVE_SOURCE_FIXTURE',
        source_modules_must_keep_relative_package_paths=True,transport_blob_paths_are_not_importable_source_pins=True)
    with Path(output).open('x',encoding='utf-8')as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    return pin(output)[0]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('repository','catalog','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();print(json.dumps(collect(a.repository,a.catalog,a.output),sort_keys=True),flush=True)


if __name__=='__main__':main()
