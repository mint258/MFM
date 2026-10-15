"""Close the 10,000-molecule pilot and apply the user's two numeric full-run gates."""
import argparse,concurrent.futures as cf,collections,json,os,subprocess,time
from pathlib import Path
import numpy as np
from prepare import ROOT,POP,save,sha
STAGE='pilot_v4'

def quantiles(values):
    a=np.array(values,dtype=float)
    return {str(p):float(np.quantile(a,p)) for p in [0,.25,.5,.75,.9,.95,.99,1]} if len(a) else None

def read_group(group):
    import pyarrow as pa
    import pyarrow.parquet as pq
    out=ROOT/STAGE;receipt=json.loads((out/f'receipt_group{group}.json').read_text())
    for ref in receipt['references']:
        path=Path(ref['path'])
        assert path.stat().st_size==ref['bytes'] and sha(path)==ref['sha256']
    m=pq.read_table(out/f'molecules_group{group}.parquet').to_pylist()
    c=pq.read_table(out/f'conformers_group{group}.parquet',columns=['molecule_id','sprime_conf_idx','converged','nearest_pm7_rmsd_A']).to_pylist()
    assert len(m)==2000 and len({r['molecule_id'] for r in m})==2000
    assert len(c)==receipt['conformers'] and len({(r['molecule_id'],r['sprime_conf_idx']) for r in c})==len(c)
    assert sum(r['generated_conformers'] for r in m)==len(c)
    coord_type=pq.read_schema(out/f'conformers_group{group}.parquet').field('coordinates').type
    assert pa.types.is_float64(coord_type.value_type.value_type)
    assert all(r['status'] not in {'UNPROCESSED','IMPLEMENTATION_ERROR'} for r in m)
    return receipt,m,c

def main():
    global STAGE
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='pilot_v5');a=ap.parse_args();STAGE=a.stage
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import duckdb
    db=duckdb.connect();db.execute('SET threads=16')
    manifest=json.loads((POP/'manifest.json').read_text())
    source_counts={g['file_group']:g['molecules'] for g in manifest['file_groups']}
    with cf.ThreadPoolExecutor(max_workers=16) as pool: groups=list(pool.map(read_group,range(1,6)))
    all_m=[];all_c=[];reports=[];allocated_coreh=0.;science_coreh=0.;storage=0.;weighted_failures=0.
    accounting=json.loads((ROOT/'reports/pilot_accounting.json').read_text())
    reproduction=json.loads((ROOT/'reports/pilot_reproduction100.json').read_text())
    assert reproduction['status']=='PASS' and reproduction['molecules']==100
    assert all(receipt['source_sha256']==reproduction['source_sha256'] for receipt,_,_ in groups)
    for group,(receipt,m,c) in enumerate(groups,1):
        jid=receipt['job_id'];ac=accounting[jid]
        assert ac['State']=='COMPLETED' and ac['ExitCode']=='0:0'
        healthy={'SUCCESS','INSUFFICIENT_UNIQUE_CONFORMERS'}
        failed=sum(r['status'] not in healthy for r in m)
        ratio=source_counts[group]/len(m)
        actual_coreh=int(ac['AllocCPUS'])*int(ac['ElapsedRaw'])/3600
        if 'baseline_receipt' in receipt:
            prior=receipt['baseline_receipt']['job_id']
            prior_ac=accounting[prior]
            assert prior_ac['State']=='COMPLETED' and prior_ac['ExitCode']=='0:0'
            actual_coreh+=int(prior_ac['AllocCPUS'])*int(prior_ac['ElapsedRaw'])/3600
        allocated_coreh+=actual_coreh*ratio
        science_coreh+=sum(r['elapsed_seconds'] for r in m)/3600*ratio
        output_bytes=sum(ref['bytes'] for ref in receipt['references']);storage+=output_bytes*ratio
        weighted_failures+=failed*ratio
        reports.append({'file_group':group,'pilot_molecules':len(m),'population_molecules':source_counts[group],'status_counts':dict(collections.Counter(r['status'] for r in m)),'failure_rate':failed/len(m),'molecules_with_any_geometry':sum(r['generated_conformers']>0 for r in m),'insufficient_N':sum(r['generated_conformers']<r['expected_conformers'] for r in m),'selected_nonconverged':sum(r['nonconverged_selected'] for r in m),'seconds_per_molecule_quantiles':quantiles([r['elapsed_seconds'] for r in m]),'mean_seconds_per_molecule':float(np.mean([r['elapsed_seconds'] for r in m])),'rmsd_A_quantiles':quantiles([r['nearest_pm7_rmsd_A'] for r in c]),'pm7_covered':sum(r['covered_pm7_conformers'] for r in m),'pm7_total':sum(r['expected_conformers'] for r in m),'actual_allocated_core_hours':actual_coreh,'predicted_allocated_core_hours':actual_coreh*ratio,'predicted_science_core_hours':sum(r['elapsed_seconds'] for r in m)/3600*ratio,'pilot_output_bytes':output_bytes,'predicted_output_bytes':output_bytes*ratio,'receipt':receipt})
        all_m.extend(m);all_c.extend(c)
    assert len(all_m)==10000 and len({r['molecule_id'] for r in all_m})==10000
    db.execute(f"CREATE VIEW selected AS SELECT * FROM read_parquet('{ROOT/'prepared/pilot_molecules.parquet'}')")
    import pyarrow as pa
    db.register('actual',pa.Table.from_pylist(all_m))
    assert db.execute('SELECT count(*) FROM selected s FULL JOIN actual a USING(molecule_id) WHERE s.molecule_id IS NULL OR a.molecule_id IS NULL').fetchone()[0]==0
    failed=sum(r['status'] not in {'SUCCESS','INSUFFICIENT_UNIQUE_CONFORMERS'} for r in all_m)
    sample_rate=failed/10000;weighted_rate=weighted_failures/manifest['formal_molecules']
    # Include real Slurm allocation/startup/waiting cost, not just active UFF CPU time.
    allowed=allocated_coreh<5000 and max(sample_rate,weighted_rate)<.01
    result={'status':'FULL_RUN_ELIGIBLE' if allowed else 'USER_CONFIRMATION_REQUIRED_BY_A7','stage':STAGE,'rmsd_mapping':'source_atom_index_heavy_atoms','alignment':'proper_rotation_Kabsch','pilot_molecules':10000,'pilot_conformers':len(all_c),'status_counts':dict(collections.Counter(r['status'] for r in all_m)),'failure_definition':'molecule status other than SUCCESS or INSUFFICIENT_UNIQUE_CONFORMERS; includes selected UFF nonconvergence and all graph/stereo failures','sample_failure_rate':sample_rate,'population_weighted_failure_rate':weighted_rate,'predicted_allocated_core_hours':allocated_coreh,'predicted_active_science_core_hours':science_coreh,'predicted_output_bytes':storage,'predicted_storage_GiB':storage/(1<<30),'pm7_coverage_fraction':sum(r['covered_pm7_conformers'] for r in all_m)/sum(r['expected_conformers'] for r in all_m),'nearest_pm7_rmsd_A_quantiles':quantiles([r['nearest_pm7_rmsd_A'] for r in all_c]),'stereo_sources':dict(collections.Counter(r['stereo_source'] or 'UNRESOLVED' for r in all_m)),'insufficient_N_molecules':sum(r['generated_conformers']<r['expected_conformers'] for r in all_m),'groups':reports,'accounting_source':str(ROOT/'reports/pilot_accounting.json'),'sha_manifest':[ref for receipt,_,_ in groups for ref in receipt['references']],'original_lmdb_written':False,'new_lmdb_created':False}
    all_work=json.loads((ROOT/'reports/all_work_accounting.json').read_text())
    result.update(embedding_max_attempts_per_conformer=200,
        pilot_actual_allocated_core_hours=sum(r['actual_allocated_core_hours'] for r in reports),
        all_work_actual_allocated_core_hours_as_of_snapshot=all_work['actual_core_hours_all_work'],
        accounting_snapshot_timestamp=all_work['timestamp'],
        reproduction100={k:v for k,v in reproduction.items() if k!='results'},
        guide_sha256=sha(ROOT/'configs/user_guide.md'),
        source_sha256=groups[0][0]['source_sha256'])
    save(ROOT/'reports/pilot_summary.json',result)
    save(ROOT/'reports/pilot_sha_manifest.json',result['sha_manifest'])
    text=['# S′ 10000 分子试跑报告','',f"全量门禁：{result['status']}。",f"失败率：样本 {sample_rate:.3%}，按正式五组人口加权 {weighted_rate:.3%}。",f"全量外推：实配核时 {allocated_coreh:.1f}，实际科学核时 {science_coreh:.1f}；输出 {storage/(1<<30):.2f} GiB。",f"S′ 构象 {len(all_c):,}；不足原 N 的分子 {result['insufficient_N_molecules']:,}；PM7 构象覆盖率 {result['pm7_coverage_fraction']:.3%}。",'','|组|试跑分子|失败率|平均秒/分子|外推实配核时|','|---|---:|---:|---:|---:|']
    for r in reports:text.append(f"|{r['file_group']}|{r['pilot_molecules']}|{r['failure_rate']:.3%}|{r['mean_seconds_per_molecule']:.3f}|{r['predicted_allocated_core_hours']:.1f}|")
    text+=['','详细状态、RMSD 分位数、立体来源和源文件 SHA 见 pilot_summary.json。',
        f"相同种子独立重跑 100 分子：{reproduction['status']}；有坐标分子 {reproduction['molecules_with_coordinates']}，逐字节核对 float64 构象 {reproduction['conformers_tested']} 个；无数值容差。该验收针对试跑，不能替代未来全人口随机 100 分子的验收。",
        'RMSD 按原记录的重原子序号一一匹配，使用不含反射的 Kabsch 刚体对齐；最近 PM7 RMSD 的最小值在原 S 构象之间选取。',
        '未生成足够唯一构象的分子按真实结果保留，不复制补齐。UFF 非收敛计入失败门禁。',
        '本次固定每个候选的 ETKDG 嵌入尝试上限为 200，默认方式失败后仍只进行一次随机初始坐标重试；候选 3N、UFF 上限 2000 均保持。固定次数预算保证同种子复现，不使用依赖机器负载的秒级超时。',
        f"本版五组试跑实配核时 {result['pilot_actual_allocated_core_hours']:.2f}；截至记账快照全部本轮作业（含旧版、取消、失败、诊断与小测试）实配核时 {all_work['actual_core_hours_all_work']:.2f}，见 all_work_accounting.json。",
        '实际核时来自 Slurm 父作业 AllocCPUS×ElapsedRaw，外推包括进程启动及尾部等待；旧版成本未混入本版全量外推，也未从实际成本中删除。',
        '外推是五组分层点估计，并非已运行全量的成本。已准备的全量实现采用共享任务队列、大分子优先及有界进程池以减少尾部等待；该改进的全量收益尚未实测，未据此下调门禁外推。',
        '按 [用户指南 A7](../configs/user_guide.md)，外推核时严格小于 5000 且失败率严格小于 1% 才自动全量；否则报告并等确认。非等比例分层试跑同时报告样本失败率和按正式人口加权的失败率，门禁采用其中较高值。',
        '优化迭代数等于每步快照数，依据 [RDKit BFGS 2025.09.5 源码](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/Numerics/Optimizer/BFGSOpt.h)。']
    (ROOT/'reports/pilot_report.md').write_text('\n'.join(text)+'\n')
    # Standalone scientific figures. Font/cache work stays on node-local scratch.
    import tempfile,shutil
    scratch=Path(tempfile.mkdtemp(prefix='sprime_plot_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    os.environ['MPLCONFIGDIR']=str(scratch)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for group,(_,m,c) in enumerate(groups,1):
        distances=np.sort([r['nearest_pm7_rmsd_A'] for r in c])
        if len(distances):axes[0].plot(distances,np.arange(1,len(distances)+1)/len(distances),label=f'Group {group}')
    axes[0].set(xlabel='Nearest PM7 heavy-atom RMSD (A)',ylabel='Cumulative fraction');axes[0].axvline(.5,color='grey',ls='--');axes[0].legend()
    axes[1].bar([r['file_group'] for r in reports],[r['failure_rate']*100 for r in reports]);axes[1].axhline(1,color='grey',ls='--');axes[1].set(xlabel='File group',ylabel='Molecule failure rate (%)');fig.tight_layout()
    fig.savefig(ROOT/'reports/sprime_pilot_geometry.svg');fig.savefig(ROOT/'reports/sprime_pilot_geometry.png',dpi=180)
    first=["S-prime generation and S convergence: current results",f"1. Is one epoch sufficient? Pending: frozen_protocol.json has not been identified.","2. Denoising versus 0.042 A lookup baseline: no new training result yet.","3. Single-epoch training duration: no new throughput measurement yet.",f"4. S-prime pilot: {1-sample_rate:.2%} success; PM7 coverage {result['pm7_coverage_fraction']:.2%}; median RMSD {result['nearest_pm7_rmsd_A_quantiles']['0.5']:.3f} A.",f"5. Decisions: {result['status']}; provide the frozen training configuration path."]
    page=plt.figure(figsize=(8.27,11.69));page.text(.08,.92,first[0],fontsize=15,weight='bold')
    import textwrap
    y=.82
    for item in first[1:]:page.text(.08,y,textwrap.fill(item,width=76),fontsize=11,va='top');y-=.13
    with PdfPages(ROOT/'reports/summary_report.pdf') as pdf:pdf.savefig(page);pdf.savefig(fig)
    plt.close(page);plt.close(fig);shutil.rmtree(scratch)
    summary_lines=['# S′ 生成与 S 收敛检验：当前总结','', '- 1 个 epoch 是否足够及依据：B 尚未启动，缺指南引用的冻结配置路径。','- 去噪头是否超过 0.042 Å 查表基线：本轮尚无训练实测。','- 单 epoch 训练时长：本轮尚无吞吐实测。',f"- S′：试跑成功率 {1-sample_rate:.3%}；与 S 的 RMSD 中位数 {result['nearest_pm7_rmsd_A_quantiles']['0.5']:.3f} Å；S 构象覆盖率 {result['pm7_coverage_fraction']:.3%}。",f"- 待决定事项：{result['status']}；补充冻结训练配置路径。"]
    (ROOT/'reports/summary_report.md').write_text('\n'.join(summary_lines)+'\n')
    print(json.dumps({k:result[k] for k in ['status','sample_failure_rate','population_weighted_failure_rate','predicted_allocated_core_hours','predicted_storage_GiB']}),flush=True)

if __name__=='__main__':main()
