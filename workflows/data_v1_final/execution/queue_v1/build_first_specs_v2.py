"""Concrete queue specs, preserving legacy SHA-only dictionary authorities."""
import pathlib,re
from .shared import ROOT,REPO,PY,load,need,on_login,pin,write_new

def unique(refs):
    result={}
    for r in refs:
        item={k:r[k] for k in ('path','bytes','sha256')}
        need(item['path'] not in result or result[item['path']]==item,'CONFLICTING_REF')
        result[item['path']]=item
    return list(result.values())

def split_frame_refs(refs):
    data=[];code=[];deferred=[]
    for item in refs:
        if all(k in item for k in ('path','bytes','sha256')):data.append(item);continue
        need(re.fullmatch(r'[a-f0-9]{64}',item['sha256']),'LEGACY_AUTHORITY_SHA_REQUIRED')
        suffix=pathlib.Path(item['path']).suffix
        if suffix=='.sbatch':
            actual=pin(item['path']);need(actual['sha256']==item['sha256'],'LEGACY_SMALL_CODE_CHANGED');code.append(actual)
        else:
            need(suffix=='.dict' and item.get('role')=='compression_dictionary','ONLY_ORIGINAL_SHA_ONLY_DICTIONARIES_DEFERRED')
            deferred.append(item)
    return unique(data),unique(code),deferred

def main():
    on_login();control=ROOT/'control/requests'
    dpath=control/'dv1_q_sprime_recovery_20261026_v1.dispatch.json';d=load(dpath)
    fmeta=load(ROOT/'control/pprime_frame_queue_materialized_20261026_v1.json');fpath=control/'dv1_q_pprime_frame_20261026_v1.plan.json';f=load(fpath)
    tpath=control/'dv1_q_pprime_retention_20261026_v1.plan.json';t=load(tpath)
    need(d['request_fields']['wall_seconds']==6900 and f['wall_seconds']==7200 and t['wall_seconds']==3600,'APPROVED_FINITE_STAGES')
    data,code,deferred=split_frame_refs(f['data_references'])
    retention_sources=[pin(p) for p in (REPO/'workflows/data_v1_final/pprime/queued_retention_v1').glob('*.py')]
    retention_sources += [pin(REPO/'workflows/data_v1_final/pprime/retention_v1/prepare_v1.py'),
        pin(REPO/'workflows/data_v1_final/pprime/retention_v1/prepare_cpu_queued_v2.py')]
    specs={
        'dv1_q_checks_20261026_v1':{'kind':'analysis','wall_seconds':600,'estimated_peak_output_bytes':96*1024**2,
            'execution_argv':[PY,'-B','-m','workflows.data_v1_final.execution.queue_v1.run_checks'],
            'source_references':unique([*d['source_references'],pin(dpath),*retention_sources]),'data_references':[],
            'scope':'12new queue +6new recovery +4new retention boundaries,22total. Zero scientific/corpus calls.'},
        'dv1_q_sprime_recovery_20261026_v1':{'kind':'conformer','wall_seconds':6900,
            'estimated_peak_output_bytes':d['request_fields']['estimated_peak_output_bytes'],'execution_argv':d['execution_argv'],
            'source_references':unique([*d['source_references'],pin(dpath)]),'data_references':unique(d['data_references']),
            'scope':'Two missing original tasks and14same-seed controls;334oldpackages and TIMEOUT preserved. Original96coreh gate unchanged.'},
        'dv1_q_pprime_frame_20261026_v1':{'kind':'qm','wall_seconds':7200,'estimated_peak_output_bytes':f['estimated_peak_output_bytes'],
            'execution_argv':fmeta['command_argv'],'source_references':unique([*f['source_references'],pin(fpath),*code]),
            'data_references':data,'deferred_authority_references':deferred,
            'deferred_validation':'Original engine validates these SHA-only compression dictionaries on compute. Byte sizes are not invented. Full original54 authority list remains bound by original plan hash.',
            'scope':'72real isolated frame controls plus evaluator; not2000pilot or all-corpus certification.'},
        'dv1_q_pprime_retention_20261026_v1':{'kind':'analysis','wall_seconds':3600,'estimated_peak_output_bytes':t['estimated_peak_output_bytes'],
            'execution_argv':t['command_argv'],'source_references':unique([*t['source_references'],pin(tpath)]),
            'data_references':unique(t['data_references']),
            'scope':'Read/rebind original2000UFF pairs and stable retention manifest, no UFF/QM or once-ledger mutation.'}}
    for name,obj in specs.items():
        obj.update(schema='ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1',pilot=True)
        path=control/(name+'.stage_spec.json');need(not path.exists(),'EXCLUSIVE_SPEC_OUTPUT')
    write_new(ROOT/'control/first_spec_translation_v2.json',{'schema':'LEGACY_SHA_ONLY_QUEUE_BINDING_V2',
        'failed_v1_source':pin(pathlib.Path(__file__).with_name('build_first_specs.py')),
        'v1_failed_before_any_spec_output':True,'reason':'Frame legacy authorities included missing bytes; no fabricated byte counts',
        'original_frame_plan':pin(fpath),'small_sbatch_code_pins_observed':code,'SHA_only_dictionaries_preserved_deferred':deferred,
        'scientific_data_bodies_read_hashed_or_stat_ed':False})
    for name,obj in specs.items():
        path=control/(name+'.stage_spec.json');write_new(path,obj)
        print(__import__('json').dumps({'stage_spec':pin(path),'sources':len(obj['source_references']),'data_locators':len(obj['data_references']),'deferred_authorities':len(obj.get('deferred_authority_references',[]))}))
if __name__=='__main__':main()
