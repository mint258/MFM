"""Main Source-only staging; existing Alpha science7/bridge are not regenerated."""
import argparse,pathlib
from . import contract as C


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--staging-directory',type=pathlib.Path,required=True)
    p.add_argument('--target-code-root',type=pathlib.Path,required=True);a=p.parse_args()
    out=C.literal(a.staging_directory);C.need(not out.exists(),'FRESH_SOURCE_STAGE');out.mkdir(parents=True)
    target=C.literal(a.target_code_root);C.need(C.ALPHA in target.parents,'OWN_NEW_ALPHA_CODE_ROOT')
    rows=[]
    def copy_source(path,relative):
        original=C.ref(path,2<<20);body=C.verify(original,2<<20).read_bytes();stage=C.exclusive(out/relative,body)
        rows.append({'origin_reference':original,'staging_reference':stage,'target_locator':{**stage,'path':str(target/relative)},'actual_target_installed':False})
    here=pathlib.Path(__file__).absolute().parent
    for path in sorted(here.glob('*.py')):copy_source(path,'portable_n1_source_remaining_v1/'+path.name)
    original=C.MAIN/'repository/workflows/data_v1_final/conformers/n1_pprime2_source_full_v1'
    relative='workflows/data_v1_final/conformers/n1_pprime2_source_full_v1'
    for name in ('__init__.py','core.py','contract.py'):
        r=C.ref(original/name,2<<20)
        if name=='core.py':C.need((r['bytes'],r['sha256'])==C.N1_CORE,'ORIGINAL_FULL_CORE')
        if name=='contract.py':C.need((r['bytes'],r['sha256'])==C.N1_CONTRACT,'ORIGINAL_FULL_PURE_CONTRACT')
        copy_source(original/name,relative+'/'+name)
    for relative in ('workflows/__init__.py','workflows/data_v1_final/__init__.py','workflows/data_v1_final/conformers/__init__.py'):
        stage=C.exclusive(out/relative,b'');rows.append({'origin_reference':None,'staging_reference':stage,
            'target_locator':{**stage,'path':str(target/relative)},'actual_target_installed':False})
    C.save(out/'source_stage.json',{'schema':'N1_PORTABLE_ORIGINAL_SOURCE_STAGE_V1','status':'SOURCE_ONLY_NOT_TRANSFERRED_OR_EXECUTED',
        'copies':rows,'new_UFF_QM_calls':0,'old_Alpha_science7_or_bridge_regenerated':False,'scientific_functions_modified':False,
        'required_existing_Alpha_top_level_packages':['portable_secondary_uff_v1','secondary_cpu_queue_v1'],
        'pythonpath_new_root_first':str(target),'old_registered_sources_changed':False})
    return 0


if __name__=='__main__':raise SystemExit(main())
