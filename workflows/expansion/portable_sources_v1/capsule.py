"""Package/finalize unchanged original UFF source bodies; metadata operations only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from ..common import load,reference,verify,dump_new,require


ORIGINAL_RECIPE_SHA='cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a'


def prepare(output):
    require(os.getuid()==1278,'Original source packaging is Main metadata only')
    from ..no_pm7_uff_d_main_v1 import contract as original
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    recipe_ref=reference(original.RECIPE);require(recipe_ref['sha256']==ORIGINAL_RECIPE_SHA,'Original recipe bytes changed')
    recipe=load(original.RECIPE);roles=original.catalog_paths();roles['original_recipe']=original.RECIPE
    roles.update({'science_pin_'+str(i):Path(pin['path']) for i,pin in enumerate(recipe['science_source_pins'])})
    project=Path('/share/home/zixiao/descriptor_analysis');runtime=Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime')
    repo=original.Q.REPO
    auxiliary=set()
    for folder in (repo/'workflows/data_v1_final/labels',repo/'workflows/data_v1_final/labels/streaming_cpu_v1',
            repo/'workflows/wp5/scripts',runtime/'phychem_mfm'):
        auxiliary.update(folder.glob('*.py') if folder.name!='phychem_mfm' else folder.rglob('*.py'))
    for name in ('pilot_masks','canonical_reader','prepare_pilot_plan'):
        roles['label_'+name]=repo/'workflows/data_v1_final/labels'/(name+'.py')
    roles['label_common']=repo/'workflows/data_v1_final/labels/common.py'
    roles['label_support']=repo/'workflows/data_v1_final/labels/streaming_cpu_v1/support.py'
    roles['label_scan']=repo/'workflows/data_v1_final/labels/streaming_cpu_v1/scan_v2.py'
    paths=set(roles.values())|auxiliary;entries={}
    for path in sorted(paths):
        pin=reference(path)
        if path.is_relative_to(repo):relative=Path('repository')/path.relative_to(repo)
        elif path.is_relative_to(project):relative=Path('project')/path.relative_to(project)
        elif path.is_relative_to(runtime):relative=Path('runtime')/path.relative_to(runtime)
        else:raise ValueError('SOURCE_OUTSIDE_EXPLICIT_ORIGINAL_ROOTS:'+str(path))
        destination=root/'payload'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination);actual=reference(destination)
        require((actual['bytes'],actual['sha256'])==(pin['bytes'],pin['sha256']),'Source copy changed')
        entries[str(path)]={'origin_endpoint':'202.38.247.57:22','origin_uid':path.stat().st_uid,'source_reference':pin,'payload_relative_path':relative.as_posix()}
    result={'schema':'PUBCHEM_ORIGINAL_UFF_SOURCE_BUNDLE_V1','status':'PREPARED_SOURCE_BYTES_NOT_DESTINATION_DEPLOYMENT',
        'origin':{'endpoint':'202.38.247.57:22','uid':1278},'original_recipe_sha256':ORIGINAL_RECIPE_SHA,
        'roles':{name:str(path) for name,path in roles.items()},'sources':list(entries.values()),
        'original_science_pins':recipe['science_source_pins'],
        'no_scientific_functions_executed':True,'new_UFF_QM_calls':0}
    dump_new(root/'bundle.json',result);return result


def finalize(bundle_path,payload_root,output,endpoint,uid):
    require(os.getuid()==uid,'Actual destination UID differs; no imported proof substitutes for this UID')
    if endpoint=='218.192.171.238:22':
        require(uid==1264 and Path(payload_root).absolute().is_relative_to('/gfshome/alpha'),'Real Alpha UID/path required')
    elif endpoint=='202.38.247.57:22':require(uid==1278,'Real Main metadata/native fixture UID required')
    else:raise ValueError('EXPLICIT_AUTHORIZED_FREE_ENDPOINT_REQUIRED')
    bundle=load(bundle_path);require(bundle.get('schema')=='PUBCHEM_ORIGINAL_UFF_SOURCE_BUNDLE_V1'
        and bundle['original_recipe_sha256']==ORIGINAL_RECIPE_SHA,'Original source bundle required')
    replicas=[];by_origin={}
    for source in bundle['sources']:
        relative=Path(source['payload_relative_path']);require(not relative.is_absolute() and '..' not in relative.parts,'Safe source-relative path required')
        path=Path(payload_root)/relative;require(path.lstat().st_uid==uid and not path.is_symlink(),'Actual own source replica required')
        actual=reference(path);origin=source['source_reference']
        require((actual['bytes'],actual['sha256'])==(origin['bytes'],origin['sha256']),'Actual replica does not preserve source bytes')
        replicas.append({'origin_endpoint':source['origin_endpoint'],'origin_uid':source['origin_uid'],
            'source_reference':origin,'replica_reference':actual});by_origin[origin['path']]=actual
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    transport={'schema':'PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1','status':'VERIFIED_REPLICAS_CLOSED',
        'destination':{'endpoint':endpoint,'uid':uid},'replicas':replicas,'original_bundle_reference':reference(bundle_path)}
    dump_new(out/'source_transport.json',transport)
    manifest={'schema':'PUBCHEM_ORIGINAL_UFF_SOURCE_CAPSULE_V1','status':'ACTUAL_CLOSED_SOURCE_CAPSULE',
        'destination':{'endpoint':endpoint,'uid':uid},'origin':bundle['origin'],
        'roles':{name:{'original_reference':next(s['source_reference'] for s in bundle['sources'] if s['source_reference']['path']==origin),
            'replica_reference':by_origin[origin]} for name,origin in bundle['roles'].items()},
        'original_recipe_sha256':ORIGINAL_RECIPE_SHA,'original_science_pins':bundle['original_science_pins'],
        'runtime_import_root':str(Path(payload_root)/'runtime'),'source_transport_manifest':reference(out/'source_transport.json'),
        'no_scientific_functions_executed':True,'new_UFF_QM_calls':0,'native_portability_not_yet_validated':True}
    dump_new(out/'capsule.json',manifest);return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','finalize'))
    p.add_argument('--output',required=True,type=Path);p.add_argument('--bundle',type=Path);p.add_argument('--payload-root',type=Path)
    p.add_argument('--endpoint');p.add_argument('--uid',type=int);a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:finalize(a.bundle,a.payload_root,a.output,a.endpoint,a.uid)


if __name__=='__main__':main()
