"""Copy existing final CYP/VAL producer rows to small JSON and Markdown; no evaluation."""
import argparse,csv,pathlib
from h_resources import REPO,CONTROL,guard,load,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args();guard(force=True)
    c=load(a.configuration);run=c['run'];arm=c['arm']
    score_source=CONTROL/'scores.csv'
    val_source=CONTROL/'runtime/results/p_recipe/training'/run/'VAL_original_units_3000000.csv'
    with score_source.open() as stream:
        cyp=[dict(readout=r['readout'],task=r['task'],error=float(r['error']),E_ref=float(r['E_ref']),
            score=float(r['score']),excluded_from_mean=r['excluded_from_mean'].lower()=='true')
            for r in csv.DictReader(stream) if r['run']==run and int(r['samples'])==3000000 and r['task'].startswith('cyp.')]
    with val_source.open() as stream:
        val=[dict(field=r['field'],MAE_original_units=float(r['MAE_original_units']),observations=int(r['observations']),unit=r['unit']) for r in csv.DictReader(stream)]
    payload=dict(arm=arm,run=run,samples=3000000,seed=c['seed'],
        reuse='Existing producer CSV rows copied only; no reevaluation, refitting, bootstrap or MAE recomputation',
        CYP_source=str(score_source),VAL_source=str(val_source),CYP=cyp,VAL=val)
    save(REPO/'results/p_heads/T'/(arm+'_descriptions.json'),payload)
    lines=['# '+arm+' 生产者描述性字段附表','',
        '运行：`'+run+'`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。','',
        'CYP来源：`'+str(score_source)+'`。CYP不进入七任务主分。','',
        '| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |','| --- | --- | ---: | ---: | ---: | --- |']
    lines += ['| '+r['readout']+' | '+r['task']+' | '+str(r['error'])+' | '+str(r['E_ref'])+' | '+str(r['score'])+' | '+str(r['excluded_from_mean'])+' |' for r in cyp]
    lines += ['', '逐字段原单位VAL来源：`'+str(val_source)+'`。','',
        '| 字段 | 原单位MAE | 观察数 | 单位 |','| --- | ---: | ---: | --- |']
    lines += ['| '+r['field']+' | '+str(r['MAE_original_units'])+' | '+str(r['observations'])+' | '+r['unit'].replace('|','\\|')+' |' for r in val]
    guard(force=True);(REPO/'docs/p_heads'/(arm+'_FIELDS.md')).write_text('\n'.join(lines)+'\n')
    print(dict(arm=arm,run=run,CYP_rows=len(cyp),VAL_fields=len(val)),flush=True)
if __name__=='__main__':main()