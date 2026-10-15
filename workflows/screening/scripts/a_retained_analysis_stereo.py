"""A1 stereo-layer details and final A1--A4 report from closed cached SMILES."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, multiprocessing, os, sys, time
from pathlib import Path
from datetime import datetime, timezone
HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
from a_retained_analysis import ROOT,DEPS,CODES,q,rows,ref,save,copy,limits,progress

def initialize():
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.*')

def inchi_parts(inchi):
    parts={};last_prefix=None
    for piece in inchi.split('/')[1:]:
        prefix=piece[:1]
        # Repeated layer letters can occur after /i; retain isotope sublayers separately.
        if prefix=='i':last_prefix='isotope'
        key=(last_prefix+'_'+prefix) if last_prefix and prefix in ('t','b','m','s','h') else prefix
        parts[key]=piece
    return parts

def parse_one(item):
    from rdkit import Chem
    pair_id,source_smiles,generated_smiles=item
    r={'pair_id':pair_id,'source_smiles':source_smiles,'reidentified_smiles':generated_smiles,
      'source_inchikey_from_smiles':None,'generated_inchikey_from_smiles':None,
      'source_has_chiral':None,'source_has_ez':None,'generated_chiral_signature':None,
      'generated_ez_signature':None,'source_chiral_signature':None,'source_ez_signature':None,
      'chirality_changed':None,'ez_changed':None,'other_layer_changed':None,
      'difference_class':'UNRESOLVED','parse_error':None}
    try:
        source=Chem.MolFromSmiles(source_smiles);generated=Chem.MolFromSmiles(generated_smiles)
        if source is None or generated is None:raise ValueError('Source or cached geometry SMILES cannot be parsed')
        Chem.AssignStereochemistry(source,cleanIt=True,force=True)
        r['source_has_chiral']=any(a.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED for a in source.GetAtoms())
        r['source_has_ez']=any(str(b.GetStereo()) in ('STEREOE','STEREOZ','STEREOCIS','STEREOTRANS') for b in source.GetBonds())
        sinchi=Chem.MolToInchi(source);ginchi=Chem.MolToInchi(generated)
        if not sinchi or not ginchi:raise ValueError('Source or cached geometry SMILES produced no InChI')
        r['source_inchikey_from_smiles']=Chem.InchiToInchiKey(sinchi)
        r['generated_inchikey_from_smiles']=Chem.InchiToInchiKey(ginchi)
        sp=inchi_parts(sinchi);gp=inchi_parts(ginchi)
        stereo_keys={'t','m','s','b'}
        sch='|'.join(sp.get(k,'') for k in ('t','m','s'));gch='|'.join(gp.get(k,'') for k in ('t','m','s'))
        # Empty signatures have no stereo, rather than the artificial string '||'.
        if not any(sp.get(k) for k in ('t','m','s')):sch=''
        if not any(gp.get(k) for k in ('t','m','s')):gch=''
        r.update(source_chiral_signature=sch,generated_chiral_signature=gch,
          source_ez_signature=sp.get('b',''),generated_ez_signature=gp.get('b',''),
          chirality_changed=sch!=gch,ez_changed=sp.get('b','')!=gp.get('b',''),
          other_layer_changed={k:v for k,v in sp.items() if k not in stereo_keys}!={k:v for k,v in gp.items() if k not in stereo_keys})
        ch=r['chirality_changed'];ez=r['ez_changed'];other=r['other_layer_changed']
        r['difference_class']='OTHER_LAYER_PRESENT' if other else 'CHIRAL_AND_EZ' if ch and ez else 'CHIRAL_ONLY' if ch else 'EZ_ONLY' if ez else 'NO_INCHI_LAYER_DIFFERENCE'
    except Exception as exc:r['parse_error']=type(exc).__name__+': '+str(exc)[:1000]
    return r

def parse_batch(items):return os.getpid(),[parse_one(item) for item in items]

def parse_pairs(a,out):
    try:import pyarrow as pa;import pyarrow.parquet as pq
    except ModuleNotFoundError:sys.path.insert(0,str(DEPS));import pyarrow as pa;import pyarrow.parquet as pq
    source=out/'stereo_pairs_input.parquet';target=out/'stereo_pair_classification.parquet'
    if target.exists():return {'reused_closed_pair_classification':ref(target),'new_parsing':False}
    pf=pq.ParquetFile(source);fields={
      'pair_id':pa.string(),'source_smiles':pa.string(),'reidentified_smiles':pa.string(),
      'source_inchikey_from_smiles':pa.string(),'generated_inchikey_from_smiles':pa.string(),
      'source_has_chiral':pa.bool_(),'source_has_ez':pa.bool_(),'generated_chiral_signature':pa.string(),
      'generated_ez_signature':pa.string(),'source_chiral_signature':pa.string(),'source_ez_signature':pa.string(),
      'chirality_changed':pa.bool_(),'ez_changed':pa.bool_(),'other_layer_changed':pa.bool_(),
      'difference_class':pa.string(),'parse_error':pa.string()}
    schema=pa.schema(list(fields.items()));pending=target.with_name(target.name+'.pending')
    writer=pq.ParquetWriter(pending,schema,compression='zstd');seen=set();count=0;start=time.monotonic()
    iterator=iter(pf.iter_batches(batch_size=1024,columns=['pair_id','source_smiles','reidentified_smiles'],use_threads=False))
    def batch_items(batch):return [(r['pair_id'],r['source_smiles'],r['reidentified_smiles']) for r in batch.to_pylist()]
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize) as pool:
            pending_futures={}
            for _ in range(2*a.workers):
                try:b=next(iterator)
                except StopIteration:break
                pending_futures[pool.submit(parse_batch,batch_items(b))]=True
            last_log=0
            while pending_futures:
                done,_=concurrent.futures.wait(pending_futures,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    del pending_futures[future];pid,results=future.result();seen.add(pid);count+=len(results)
                    writer.write_table(pa.Table.from_pylist(results,schema=schema))
                    try:b=next(iterator)
                    except StopIteration:continue
                    pending_futures[pool.submit(parse_batch,batch_items(b))]=True
                if time.monotonic()-last_log>60:
                    progress('stereo_cached_smiles',pairs=count,total_pairs=pf.metadata.num_rows,worker_pids=len(seen));last_log=time.monotonic()
    finally:writer.close()
    if count!=pf.metadata.num_rows:raise RuntimeError('PAIR_MANIFEST_COUNT_MISMATCH')
    pending.replace(target)
    meta={'status':'ALL_CACHED_SMILES_PAIRS_CLASSIFIED_WITH_EXPLICIT_ERRORS','input':ref(source),'output':ref(target),
      'pairs':count,'effective_worker_PIDs':sorted(seen),'workers':a.workers,'seconds':time.monotonic()-start,
      'RDDetermineBonds_called':False,'LMDB_opened_or_written':False,'new_QM':False,'script':ref(__file__,True)}
    save(out/'stereo_parser_manifest.json',meta);return meta

def plots(out,a2):
    try:
        import matplotlib
        matplotlib.use('Agg');import matplotlib.pyplot as plt
    except ModuleNotFoundError:return {'status':'PLOT_DEPENDENCY_UNAVAILABLE','exact_intersection_data':'A2_funnel_overlap_retention.json'}
    targets=[]
    for mode in ('strict','relaxed'):
        intersections=[r for r in a2[mode]['upset_exact_intersections'] if r['mask']][:25]
        fig=plt.figure(figsize=(14,7));grid=fig.add_gridspec(2,1,height_ratios=[2,3]);bar=fig.add_subplot(grid[0]);dot=fig.add_subplot(grid[1],sharex=bar)
        bar.bar(range(len(intersections)),[r['records'] for r in intersections],color='#436a9c');bar.set_ylabel('Physical records');bar.tick_params(labelbottom=False)
        for x,row in enumerate(intersections):
            active=[i for i,c in enumerate(CODES) if c in row['codes']]
            dot.scatter([x]*len(CODES),range(len(CODES)),color='#e2e2e2',s=15)
            dot.scatter([x]*len(active),active,color='#222222',s=24)
            if active:dot.plot([x,x],[min(active),max(active)],color='#222222',lw=1)
        dot.set_yticks(range(len(CODES)),CODES);dot.invert_yaxis();dot.set_xticks(range(len(intersections)),range(1,len(intersections)+1));dot.set_xlabel('Top 25 nonempty exact exclusion intersections; all intersections in JSON')
        fig.suptitle(mode+' screening UpSet');fig.tight_layout();path=out/f'A2_upset_{mode}.svg';fig.savefig(path);plt.close(fig);targets.append(ref(path))
    return {'status':'COMPLETE_TOP25_NONEMPTY_INTERSECTIONS','artifacts':targets}

def report(db,out,parse_meta):
    db.execute('CREATE VIEW quality AS SELECT * FROM read_parquet('+q(out/'relaxed_quality_annotations.parquet')+')')
    db.execute('CREATE VIEW pairs AS SELECT * FROM read_parquet('+q(out/'stereo_pair_classification.parquet')+')')
    db.execute('''CREATE VIEW affected AS SELECT q.*,p.* EXCLUDE(pair_id,source_smiles,reidentified_smiles),
      p.pair_id IS NOT NULL AS pair_classified,
      p.source_inchikey_from_smiles=stored_inchikey AND p.generated_inchikey_from_smiles=reidentified_inchikey AS keys_reproduced,
      CASE WHEN p.pair_id IS NULL OR p.parse_error IS NOT NULL THEN 'UNRESOLVED'
        WHEN p.source_inchikey_from_smiles IS DISTINCT FROM stored_inchikey OR p.generated_inchikey_from_smiles IS DISTINCT FROM reidentified_inchikey
        THEN 'KEY_REPRODUCTION_MISMATCH' ELSE p.difference_class END AS audited_difference_class
      FROM quality q LEFT JOIN pairs p ON sha256(coalesce(q.smiles,'')||chr(30)||coalesce(q.reidentified_smiles,''))=p.pair_id
      WHERE q.molecule_id IN (SELECT DISTINCT molecule_id FROM quality WHERE stereo_only_key_mismatch IS TRUE)''')
    a1=json.loads((out/'A1_core.json').read_text())
    a1['old_1681976_scope']='Original first14-equal/fullkey-different class. Protonation and other layers are explicitly separated; not all such keys prove pure stereo.'
    a1['stereo_classes']=rows(db,'''SELECT audited_difference_class,count(*) AS records,count(DISTINCT molecule_id) AS molecules,
      count(*) FILTER(WHERE I01_relaxed_to_T01) AS accepted_by_relaxed_I01,
      count(*) FILTER(WHERE retained AND NOT strict_retained) AS newly_retained,
      count(*) FILTER(WHERE source_has_chiral) AS source_has_chiral_records,
      count(*) FILTER(WHERE source_has_ez) AS source_has_ez_records,
      count(*) FILTER(WHERE source_has_chiral OR source_has_ez) AS source_has_any_stereo_records,
      count(*) FILTER(WHERE source_has_chiral IS NULL OR source_has_ez IS NULL) AS source_stereo_unknown_records
      FROM affected WHERE stereo_only_key_mismatch IS TRUE GROUP BY audited_difference_class ORDER BY records DESC''')
    a1['stereo_presence_matrix']=rows(db,'''SELECT source_has_chiral,source_has_ez,chirality_changed,ez_changed,other_layer_changed,
      count(*) AS records,count(DISTINCT molecule_id) AS molecules FROM affected WHERE stereo_only_key_mismatch IS TRUE GROUP BY ALL ORDER BY records DESC''')
    total=sum(r['records'] for r in a1['stereo_classes'])
    if total!=a1['old_same_connectivity14_fullkey_mismatch_records']:raise RuntimeError('STEREO_PHYSICAL_MANIFEST_COUNT_MISMATCH')
    db.execute('''CREATE TEMP TABLE affected_molecule_counts AS SELECT molecule_id,count(*) AS physical_conformers,
      count(*) FILTER(WHERE stored_inchikey IS NOT NULL AND reidentified_inchikey IS NOT NULL) AS identity_observed_conformers,
      count(*) FILTER(WHERE stereo_only_key_mismatch IS TRUE) AS same14_fullkey_mismatch_conformers,
      count(*) FILTER(WHERE I01_strict IS TRUE) AS any_fullkey_mismatch_conformers,
      count(*) FILTER(WHERE source_has_chiral OR source_has_ez) AS source_explicit_stereo_conformers,
      count(*) FILTER(WHERE source_has_chiral IS NULL OR source_has_ez IS NULL) AS source_stereo_unobserved_conformers
      FROM affected GROUP BY molecule_id''')
    a1['whole_vs_partial_mismatch']=rows(db,'''SELECT
      same14_fullkey_mismatch_conformers=physical_conformers AS all_physical_conformers_mismatch,
      same14_fullkey_mismatch_conformers=identity_observed_conformers AS all_identity_observed_conformers_mismatch,
      identity_observed_conformers=physical_conformers AS all_physical_conformers_have_identity,
      count(*) AS molecules,sum(physical_conformers) AS physical_records,sum(same14_fullkey_mismatch_conformers) AS mismatching_records
      FROM affected_molecule_counts GROUP BY ALL ORDER BY molecules DESC''')
    db.execute('''CREATE TEMP TABLE stereo_consistency AS SELECT molecule_id,reidentified_backbone_proton_key,
      count(*) AS observed_conformers,count(*) FILTER(WHERE keys_reproduced) AS keys_reproduced_conformers,
      count(DISTINCT reidentified_inchikey) AS full_geometry_key_variants,
      count(DISTINCT generated_chiral_signature) FILTER(WHERE keys_reproduced AND generated_chiral_signature<>'') AS defined_chiral_variants,
      count(DISTINCT generated_ez_signature) FILTER(WHERE keys_reproduced AND generated_ez_signature<>'') AS defined_ez_variants,
      count(*) FILTER(WHERE keys_reproduced AND generated_chiral_signature='') AS unspecified_chiral_conformers,
      count(*) FILTER(WHERE keys_reproduced AND generated_ez_signature='') AS unspecified_ez_conformers,
      count(*) FILTER(WHERE NOT coalesce(keys_reproduced,false)) AS unresolved_conformers
      FROM affected WHERE reidentified_backbone_proton_key IS NOT NULL GROUP BY ALL''')
    a1['within_molecule_stereo_consistency']=rows(db,'''SELECT
      count(DISTINCT molecule_id) FILTER(WHERE defined_chiral_variants>1) AS contradictory_defined_chiral_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE defined_ez_variants>1) AS contradictory_defined_ez_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE defined_chiral_variants>1 AND defined_ez_variants>1) AS both_contradictory_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE full_geometry_key_variants>1) AS varying_full_geometry_key_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE defined_chiral_variants>0 AND unspecified_chiral_conformers>0) AS defined_vs_unspecified_chiral_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE defined_ez_variants>0 AND unspecified_ez_conformers>0) AS defined_vs_unspecified_ez_molecules,
      count(DISTINCT molecule_id) FILTER(WHERE unresolved_conformers>0) AS molecules_with_unresolved_layer_comparisons FROM stereo_consistency''')[0]
    a1['consistency_scope']='Affected molecules only; compare cached geometry stereo within identical 14+proton identity. Defined-vs-unspecified is separate from multiple distinct defined signatures. No coordinates/reoptimization examined; differences alone do not establish optimization flipping.'
    copy(db,'SELECT * FROM affected_molecule_counts ORDER BY molecule_id',out/'A1_affected_molecule_counts.parquet')
    copy(db,'SELECT * FROM stereo_consistency ORDER BY molecule_id,reidentified_backbone_proton_key',out/'A1_stereo_consistency.parquet')
    copy(db,'''SELECT record_id,molecule_id,smiles,reidentified_smiles,stored_inchikey,reidentified_inchikey,
      audited_difference_class,parse_error,protonation_mismatch,chirality_changed,ez_changed,other_layer_changed
      FROM affected WHERE stereo_only_key_mismatch AND audited_difference_class IN ('UNRESOLVED','KEY_REPRODUCTION_MISMATCH','OTHER_LAYER_PRESENT')
      ORDER BY sha256(record_id) LIMIT 50''',out/'A1_stereo_other_unresolved_examples50.parquet')
    a1['stereo_only_details_status']='COMPLETE_WITH_EXPLICIT_OTHER_AND_UNRESOLVED';a1['parser']=parse_meta
    save(out/'A1_stereo_details.json',a1)
    a2=json.loads((out/'A2_funnel_overlap_retention.json').read_text());a3=json.loads((out/'A3_split_unassigned.json').read_text());a4=json.loads((out/'A4_annotations.json').read_text());pop=json.loads((out/'population_by_stratum.json').read_text())
    plotmeta=plots(out,a2)
    leakage=[r for r in a3['key_leakage'] if r['mode']=='relaxed' and r['origin']=='stored' and r['key_kind'] in ('full','connectivity14')]
    table=[{'item':'A1','key_numbers':{'strict_records':pop['strict']['records'],'relaxed_records':pop['relaxed']['records'],
        'strict_molecules':pop['strict']['molecules'],'relaxed_molecules':pop['relaxed']['molecules'],'stereo_classes':a1['stereo_classes']},
        'options':['strict full InChIKey','14-character connectivity + final protonation character'],'decision':'I01 rule'},
      {'item':'A2','key_numbers':{'original_records':pop['all_physical_records'],'strict_retention_rate':pop['strict']['records']/pop['all_physical_records'],
        'relaxed_retention_rate':pop['relaxed']['records']/pop['all_physical_records']},'options':['strict','relaxed'],'decision':'I01 and chemical-population retention'},
      {'item':'A3','key_numbers':{'strict_unassigned_records':pop['strict']['unassigned_records'],'relaxed_unassigned_records':pop['relaxed']['unassigned_records'],'relaxed_split_overlap':leakage},
        'options':['keep unassigned pending final split decision'],'decision':'Split integrity; no new split assigned'},
      {'item':'A4','key_numbers':{'relaxed_annotations':a4['relaxed']},'options':['observe annotations without thresholds'],'decision':'No threshold set this round'}]
    final={'status':'A1_A4_ANALYSIS_COMPLETE','created_UTC':datetime.now(timezone.utc).isoformat(),'decision_table':table,
      'population':pop,'A1':a1,'A2':a2,'A3':a3,'A4':a4,'plots':plotmeta,'script':ref(__file__,True),
      'job_id':os.environ['SLURM_JOB_ID'],'new_QM':False,'RDDetermineBonds_recomputed':False,'LMDB_opened_or_written':False}
    save(out/'a_retained_report.json',final)
    lines=['# A1–A4 保留集筛查','', '| 项目 | 关键数字 | 可选方案 | 配置决策 |','| --- | --- | --- | --- |',
      f"| A1 | 严格 {pop['strict']['records']:,} 条／{pop['strict']['molecules']:,} 分子；放宽 {pop['relaxed']['records']:,} 条／{pop['relaxed']['molecules']:,} 分子 | 完整键；14位＋质子化字符 | I01 |",
      f"| A2 | 原始 {pop['all_physical_records']:,}；严格保留率 {pop['strict']['records']/pop['all_physical_records']:.2%}；放宽 {pop['relaxed']['records']/pop['all_physical_records']:.2%} | 严格／放宽；分元素和大小保留率见附表 | I01与结构覆盖 |",
      f"| A3 | 严格未归属 {pop['strict']['unassigned_records']:,}；放宽未归属 {pop['relaxed']['unassigned_records']:,}；独立test authority不存在 | 继续保留未归属；不补造划分 | 划分完整性 |",
      '| A4 | H01/S01/S02/B01/T01 有效数、未知数、分位数见 A4_annotations.json | 只标注，无阈值 | 后续质量配置 |','', '\\newpage','',
      '## A1 立体层拆分','', '| 差异类别 | 记录 | 分子 | 放宽新增保留 |','| --- | --- | --- | --- |']
    for r in a1['stereo_classes']:lines.append(f"| {r['audited_difference_class']} | {r['records']:,} | {r['molecules']:,} | {r['newly_retained']:,} |")
    lines += ['', '第一段相同不自动证明只差立体。质子化、同位素／其他层和未解析分别记录；放宽删除规则仍只比较14位骨架与末位质子化字符。',
      '分子内比较仅复用已有重识别SMILES。已定义立体状态不同、定义与未定义混合分别统计，不能单凭这些统计断言优化发生了翻转。','',
      '## A2 漏斗与重叠','', 'A2_funnel_overlap_retention.json 保存全部精确交集、两两重叠矩阵、逐代码剩余数和原始分母上的分元素／大小保留率；SVG展示前25个非空交集。']
    for mode in ('strict','relaxed'):
        lines += ['',f'### {mode}','', '| 步骤后 | 记录 | 分子 |','| --- | --- | --- |']
        for r in a2[mode]['sequential_funnel']:lines.append(f"| {r['after']} | {r['records']:,} | {r['molecules']:,} |")
    lines += ['', '## A3 未归属与划分','', '原8259条在旧QA的embargo／identity quarantine阶段未进入原TRAIN/FULL视图；历史原因不充当本轮删除条件。每条source shard、real_index、payloadSHA、历史分类文件和偏移在A3_unassigned_trace.parquet。',
      'TRAIN为训练集；FULL和ROUTINE均是validation，ROUTINE是FULL监控子集；未发现独立test authority，因此不伪称完成train/val/test三分法。完整键、14位骨架、14位＋质子化字符，各按存储与重识别身份、严格与放宽检查。', '',
      '| 模式 | 身份来源 | 键 | TRAIN–FULL共享键 | 未归属–TRAIN共享键 | 未归属–FULL共享键 |','| --- | --- | --- | --- | --- | --- |']
    for r in a3['key_leakage']:lines.append(f"| {r['mode']} | {r['origin']} | {r['key_kind']} | {r['train_full_shared_keys']:,} | {r['unassigned_train_shared_keys']:,} | {r['unassigned_full_shared_keys']:,} |")
    lines += ['', '## A4 标注与五文件基准','', 'H01/S02提供有效数、未知数及分位数；S01/B01/T01提供true/false/unknown，不设阈值。S01完整键投票保留原义，骨架＋质子化投票另列。',
      '五文件仅为20／25／30／40重原子边界的分析基准；按整个分子最大重原子数分配。没有创建LMDB或改动原始记录。population_by_stratum.json同时提供严格、放宽五文件计数，字节均衡由C4另行决定。']
    path=out/'a_retained_report.md';temp=path.with_name(path.name+'.pending');temp.write_text('\n'.join(lines)+'\n',encoding='utf-8');temp.replace(path)
    save(out/'analysis_complete.json',{'status':'A1_A4_COMPLETE','report':ref(path,True),'population_manifest':ref(out/'manifest.json',True),
      'pair_classification_rows':db.execute('SELECT count(*) FROM pairs').fetchone()[0],'effective_parser_worker_PIDs':parse_meta.get('effective_worker_PIDs',[])})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default=str(ROOT/'a_retained'))
    p.add_argument('--workers',type=int,default=32);p.add_argument('--memory-gb',type=int,default=96);p.add_argument('--check',action='store_true');a=p.parse_args()
    if not limits(a):
        import ast
        ast.parse(Path(__file__).read_text());print('A_RETAINED_STEREO_SOURCE_SYNTAX_PASS');return 0
    out=Path(a.output).absolute()
    if not out.is_relative_to(ROOT):raise RuntimeError('New outputs must stay in this screening root')
    if (out/'analysis_complete.json').exists():raise RuntimeError('Closed analysis exists; use new output version')
    if not (out/'core_complete.json').is_file():raise RuntimeError('Core stage must close before stereo report')
    meta=parse_pairs(a,out)
    try:import duckdb
    except ModuleNotFoundError:sys.path.insert(0,str(DEPS));import duckdb
    db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute(f"SET memory_limit='{a.memory_gb}GB'")
    temp=out/('stereo_duckdb_tmp_'+os.environ['SLURM_JOB_ID']);temp.mkdir(exist_ok=True);db.execute('SET temp_directory='+q(temp));db.execute("SET max_temp_directory_size='80GB'")
    report(db,out,meta);db.close();progress('A1_A4_complete');return 0
if __name__=='__main__':raise SystemExit(main())
