"""Record the explicit user correction and retain the superseded failure report."""
from resources import REPO,CONTROL,MEAN,load,save,guard
if __name__=='__main__':
 guard(force=True);old=MEAN/'manifest.json'
 if old.exists():
  value=load(old)
  if value['status']!='UNRESOLVED':raise ValueError('Do not replace an accepted mean table')
  history=CONTROL/'D1_original_failure_disposition.json'
  if history.exists():raise FileExistsError('Resumption already recorded')
  old.rename(history)
 p=REPO/'results/p_followup/D_unresolved.json';value=load(p)
 value.update(original_status=value['status'],status='RESUMED_ENGINEERING_REPAIR',retry_authorized=True,
  user_correction='2026-11-17: D是正常的工程错误，请你完成D部分',
  current_scope='Complete original D1/D2/D3 including seed0 3M; prior implementation failures retained as history')
 save(p,value)
 path=REPO/'docs/p_followup/D_CONFORMER_DECOMPOSITION.md'
 text=path.read_text();path.write_text('''# D：构象分解侧线

当前状态：工程修复后继续D1、D2、D3。用户2026-11-17明确指示“D是正常的工程错误，请你完成D部分”，覆盖此前因这两次实现错误而停止D的处置。D0科学定义、阈值与训练预算不变：以C为基底、原F32→F64、sidecar关闭，仅seed0、3M。

路径类型已修复，uint8计数在累加前显式转int64，并用实际流式计数类型检验总体尺度与入选条件。D1恢复生成一次完整可接受均值表，并由生成器按原定seed抽1000 MID经实际read核对。原失败日志、处置与部分scratch保留；恢复不是构象分解假设的阴性结果。

以下为已被用户纠正的历史处置，不能作为当前D状态或科学结论：

'''+text)
 print('D_RESUMPTION_RECORDED')