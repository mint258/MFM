"""Standalone full-generation report, figures and authentic scientific acceptance references."""
import json,os,tempfile,shutil
from pathlib import Path
import numpy as np
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import duckdb
    dataset=ROOT/'dataset';accepted=json.loads((dataset/'acceptance.json').read_text());assert accepted['status']=='FULL_DATASET_ACCEPTED'
    manifest=json.loads((dataset/'manifest.json').read_text());assert sha(dataset/'manifest.json')==accepted['dataset_manifest_sha256']
    closure=manifest['closure'];reproduction=json.loads((ROOT/'reports/full_reproduction100.json').read_text());assert reproduction['status']=='PASS'
    scratch=Path(tempfile.mkdtemp(prefix='spfullreport_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    os.environ['MPLCONFIGDIR']=str(scratch)
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'");db.execute(f"SET temp_directory='{scratch}'")
    db.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet('{dataset/'molecules_group*.parquet'}',union_by_name=true)")
    db.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{dataset/'conformers_group*.parquet'}',union_by_name=true)")
    statuses=dict(closure['statuses']);failed=sum(n for s,n in statuses.items() if s not in {'SUCCESS','INSUFFICIENT_UNIQUE_CONFORMERS'})
    counts=db.execute('SELECT count(*),sum(expected_conformers),sum(generated_conformers),sum(covered_pm7_conformers),sum(generated_conformers>0)::BIGINT FROM m').fetchone()
    assert counts[:3]==(1220466,11231854,closure['sprime_conformers'])
    group_stats=[];hist=[]
    edges=np.linspace(0,max(12.,float(db.execute('SELECT max(nearest_pm7_rmsd_A) FROM c').fetchone()[0])),121)
    for group in range(1,6):
        n,bad,mean,median,p99,maximum=db.execute("SELECT count(*),sum(status NOT IN ('SUCCESS','INSUFFICIENT_UNIQUE_CONFORMERS'))::BIGINT,avg(elapsed_seconds),quantile_cont(elapsed_seconds,.5),quantile_cont(elapsed_seconds,.99),max(elapsed_seconds) FROM m WHERE file_group=?",[group]).fetchone()
        distances=db.execute('SELECT c.nearest_pm7_rmsd_A FROM c JOIN m USING(molecule_id) WHERE m.file_group=?',[group]).fetchnumpy()['nearest_pm7_rmsd_A']
        bins,_=np.histogram(distances,bins=edges);hist.append(bins)
        group_stats.append({'file_group':group,'molecules':n,'failed':bad,'failure_rate':bad/n,'mean_seconds':mean,'median_seconds':median,'p99_seconds':p99,'max_seconds':maximum,'rmsd_A_quantiles':dict(zip(['0.25','0.5','0.75','0.9','0.95','0.99'],closure['groups'][group-1]['rmsd_A_quantiles'])),'coverage_fraction':closure['groups'][group-1]['pm7_coverage_fraction']})
    science_coreh=db.execute('SELECT sum(elapsed_seconds)/3600 FROM m').fetchone()[0]
    accounting=json.loads((ROOT/'reports/all_work_accounting.json').read_text())
    report={'status':'A_FULL_GENERATION_AND_REPRODUCTION_ACCEPTED','job_id':os.environ['SLURM_JOB_ID'],'molecules':counts[0],'source_S_conformers':counts[1],'sprime_conformers':counts[2],'covered_S_conformers':counts[3],'molecules_with_geometry':counts[4],'failure_rate':failed/counts[0],'failure_count':failed,'status_counts':statuses,'insufficient_N_molecules':closure['insufficient_N_molecules'],'stereo_sources':closure['stereo_sources'],'pm7_coverage_fraction':closure['pm7_coverage_fraction'],'rmsd_A_quantiles':dict(zip(['0.25','0.5','0.75','0.9','0.95','0.99'],closure['rmsd_A_quantiles'])),'science_core_hours_unique_population':science_coreh,'actual_all_work_allocated_core_hours_as_of_snapshot':accounting['actual_core_hours_all_work'],'accounting_snapshot_timestamp':accounting['timestamp'],'groups':group_stats,'data_references':manifest['references'],'reproduction100':{k:v for k,v in reproduction.items() if k!='results'},'B_training_status':'FROZEN_PROTOCOL_REFERENCE_PENDING','original_lmdb_written':False,'new_lmdb_created':False}
    save(ROOT/'reports/full_generation_summary.json',report)
    lines=['# S′ 正式全人口生成与复现验收报告','',f"状态：{report['status']}。",f"人口 {counts[0]:,} 分子 / {counts[1]:,} 源 S 构象；S′ {counts[2]:,} 构象。",f"失败率 {report['failure_rate']:.3%}；不足原 N 的分子 {closure['insufficient_N_molecules']:,}；S 覆盖 {counts[3]:,} / {counts[1]:,}（{report['pm7_coverage_fraction']:.3%}）。",f"RMSD 中位数 {report['rmsd_A_quantiles']['0.5']:.3f} Å；逐分子科学处理核时 {science_coreh:.2f}；实配核时截至快照 {accounting['actual_core_hours_all_work']:.2f}（含全部本轮旧版与失败/恢复成本）。",f"正式全人口随机 100 分子复现 {reproduction['status']}，有坐标 {reproduction['molecules_with_coordinates']} 分子、逐字节核对 {reproduction['conformers_tested']} 个构象。",'', '|状态|分子数|比例|','|---|---:|---:|']
    for s,n in closure['statuses']:lines.append(f'|{s}|{n:,}|{n/counts[0]:.3%}|')
    lines+=['','|组|分子|失败率|平均秒/分子|RMSD 中位数 Å|S 覆盖率|','|---|---:|---:|---:|---:|---:|']
    for g in group_stats:lines.append(f"|{g['file_group']}|{g['molecules']:,}|{g['failure_rate']:.3%}|{g['mean_seconds']:.3f}|{g['rmsd_A_quantiles']['0.5']:.3f}|{g['coverage_fraction']:.3%}|")
    lines+=['','原 LMDB/人口清单只读，没有创建新 LMDB。所有失败分子保留状态；不足 N 不复制补齐，不改用其他力场。','原子顺序、固定立体、ETKDGv3 3N 候选、确定性种子、固定 200 次嵌入尝试预算、一次随机坐标重试、UFF 2000 次和 0.5 Å 重原子去重沿用已验收试跑。','完整模型训练结果另见 B 报告；本报告仅验收 A，不据此判定 S 训练收敛。','','[数据 SHA 清单](../dataset/sha_manifest.json)、[全人口闭合](../dataset/closure.json)、[正式随机100复现](full_reproduction100.json)、[机器可读统计](full_generation_summary.json)。']
    (ROOT/'reports/full_generation_report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for i,bins in enumerate(hist):axes[0].plot(edges[1:],np.cumsum(bins)/bins.sum(),label=f'Group {i+1}')
    axes[0].set(xlabel='Nearest PM7 heavy-atom RMSD (A)',ylabel='Cumulative fraction');axes[0].axvline(.5,color='grey',ls='--');axes[0].legend()
    axes[1].bar(range(1,6),[g['failure_rate']*100 for g in group_stats]);axes[1].set(xlabel='File group',ylabel='Molecule failure rate (%)');fig.tight_layout()
    fig.savefig(ROOT/'reports/sprime_full_geometry.svg');fig.savefig(ROOT/'reports/sprime_full_geometry.png',dpi=180)
    page=plt.figure(figsize=(8.27,11.69));page.text(.08,.92,'S-prime generation and S convergence',fontsize=15,weight='bold')
    import textwrap
    first=['1. Is one epoch sufficient? Pending S training configuration reference.','2. Denoising versus 0.042 A lookup baseline: no new training conclusion.','3. Single-epoch training duration: not measured in this A report.',f"4. Full S-prime: {1-report['failure_rate']:.3%} success; {counts[2]:,} conformers; median RMSD {report['rmsd_A_quantiles']['0.5']:.3f} A; S coverage {report['pm7_coverage_fraction']:.3%}.",'5. Decisions: A full run accepted; resolve the frozen training configuration for B.']
    y=.82
    for item in first:page.text(.08,y,textwrap.fill(item,76),fontsize=11,va='top');y-=.13
    with PdfPages(ROOT/'reports/full_summary_report.pdf') as pdf:pdf.savefig(page);pdf.savefig(fig)
    plt.close(page);plt.close(fig);db.close();shutil.rmtree(scratch)
    print(json.dumps({k:v for k,v in report.items() if k not in ['groups','data_references','reproduction100']}),flush=True)

if __name__=='__main__':main()
