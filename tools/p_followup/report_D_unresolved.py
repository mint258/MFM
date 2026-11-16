from resources import REPO,CONTROL,MEAN,load,save
c=load(REPO/'configs/p_followup/C_dedup.json');fields=[v['field'] for v in load(REPO/'results/p_followup/B_field_selection.json')['fields'] if v['field'] not in c['p_recipe']['excluded_fields']]
assert len(fields)==33
result=dict(status='UNRESOLVED',reason='Two failed D1 implementation attempts; taskbook total rule6 conservative default',selected_fields=[],candidate_fields=fields,
 fields={n:dict(status='UNRESOLVED',decompose=False) for n in fields},attempts=[dict(job_id=4535151,status='FAILED',exit_code='1:0',reason='split_metadata received str instead of Path'),dict(job_id=4535152,status='CANCELLED',reason='Own CPU producer cancelled before completion to remove duplicate traversal; no accepted output'),dict(job_id=4535153,status='FAILED',exit_code='1:0',reason='uint64 count sum cannot add into int64 in TrainMoments')],
 partial_outputs=str(MEAN),accepted_mean_table=False,source_values='current F32 -> F64',C_unchanged=True,D_training_started=False,D_evaluation='No distinct D arm:conservative fallback equals C; no duplicate model training',A_H6='MISSING',retry_authorized=False)
save(REPO/'results/p_followup/D_unresolved.json',result);save(MEAN/'manifest.json',result)
(REPO/'docs/p_followup/D_CONFORMER_DECOMPOSITION.md').write_text('''# D：构象分解侧线

状态：UNRESOLVED。D0科学定义与选择阈值已在结果前注册；D1尚未产生可接受的完整均值表或TRAIN尺度，因此没有任何字段获准分解。

两次实际失败分别为4535151（路径类型）和4535153（计数累加类型）；中间4535152为自有CPU产物生成器的工程取消，防止重复遍历。日志与部分均值/计数表保留于runs/p_followup_20261116，未被当作完整产物使用。按任务书总规则6的连续两次失败上限停止修复，不追加重试。

保守默认是所有33个候选字段不分解，D退回C配方。没有启动额外的重复3M训练，没有可报告的独立D−C/D−M1比较、逐字段构象差MAE或A-H6；这些结果记为缺失而非零效应。C的训练及B的补存工作继续。此项不能用来判断构象分解科学假设是否有效。

未来只有用户重新授权才恢复D1及后续D2/D3；原失败记录保留。
''')
print('D_UNRESOLVED_RECORDED',len(fields))