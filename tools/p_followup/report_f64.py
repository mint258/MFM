"""B4 render only producer/actual-loader evidence; never reread labels or hash sources."""
from resources import REPO,load,guard


def main():
    guard(force=True);m=load(REPO/'configs/p_followup/B_sidecar_manifest.json');b=load(REPO/'results/p_followup/B3_acceptance.json')
    if b['status'] not in ['COMPLETE','UNRESOLVED_FIELDS']:raise ValueError('B3 is not terminal')
    lines=['# B：大数值能量字段F64补存','','状态：B0、B1、B2及B3已执行；逐字段是否接受见下表。生产sidecar覆盖D6的TRAIN/FULL全部P/U记录，验收限既有冻结42961记录。','','B0只用冻结TRAIN核心的原F64缓存：r=|Δ_F32−Δ_F64|/|Δ_F64|，e=|Δ_F32−Δ_F64|。中位r>1e-4且中位e/D4scale>1e-6，或源非零对归零率≥0.001时入选。共4个字段；规则未随结果调整。','','B1只读既有物理索引与原common.task_components。CELL标量投影保留原kind/f64等叶；需要数组kind时读取该源行完整CELL。源路由只在内存，不创建新的全源索引或改写LMDB。按D6顺序存MI、CI、7字节LMDB句柄（由id_map的kind/MI/CI生成）及F64列，全部mask无效值为NaN。写出时唯一一次逐值核对f32(source)与D6的位模式，不匹配写NaN，loader回退原F32；错配/缺源超过0.01%则整字段UNRESOLVED。','','B2新增p_f64_sidecar可选路径，默认None。只有有限sidecar值覆盖有效graph scalar raw；F64 raw在归一化及元素参考相减时保持F64，最终输出F32。A1及状态差自动继承base read。原11-07/D4和A1参数均未重拟合。','','B3在同一冻结物理记录上分别运行11-07与A1，逐记录读取当前p-recipe实际loader作为关闭开关的109字段基准。源非零构象对的归一化差必须非零，且与源F64直接差/scale相比满足1e-6+1e-5|参考差|。未入选字段开/关逐位一致。下列是固定数值验收，无统计显著性或阈值扫描。','','|字段|D6有效值|B1错配/缺源|11-07归零/非零对|A1归零/非零对|数值失败(两路径)|最终状态|','|---|---:|---:|---|---|---:|---|']
    for n in m['requested_fields']:
        s=m['field_status'][n];a=b['recipes']['D4']['fields'][n];z=b['recipes']['A1']['fields'][n]
        lines.append(f"|{n}|{s['D6_valid_values']}|{s['mismatch']+s['missing_source']}|{a['normalized_zero_pairs']}/{a['source_nonzero_pairs']}|{z['normalized_zero_pairs']}/{z['source_nonzero_pairs']}|{a['numerical_failures']+z['numerical_failures']}|{'COMPLETE' if n in b['accepted_fields'] else 'UNRESOLVED'}|")
    lines+=['','|路径|实际验收记录|关闭开关与主线不一致记录|未入选字段开/关不一致记录|','|---|---:|---:|---:|']
    for n,r in b['recipes'].items():
        k=r['checks'];lines.append(f"|{n}|{k['records']}|{k['baseline_off_mismatch_records']}|{k['nonselected_on_mismatch_records']}|")
    lines+=['','CPU吞吐只作报告：同一固定20000记录，A1路径，开/关各一次，不作为通过门槛。','','|开关|样本/秒|秒|','|---|---:|---:|']
    for n,r in b['throughput'].items():lines.append(f"|{n}|{r['samples_per_second']}|{r['seconds']}|")
    lines+=['','|split|记录数|实际携带入选字段记录|values bytes|values SHA256|offsets SHA256|','|---|---:|---:|---:|---|---|']
    for n,r in m['splits'].items():lines.append(f"|{n}|{r['records']}|{r['records_carrying_selected']}|{r['values_bytes']}|{r['values_SHA256']}|{r['molecule_offsets_SHA256']}|")
    lines+=['','文件路径与字段清单详见configs/p_followup/B_sidecar_manifest.json。SHA来自B1最终文件的一次性计算，此报告不重新读取sidecar或源文件。原始F64的数值精度不等于量化方法的物理准确性，F32最终输出仍可能使极小的非零差不可分辨；若实际违反零归零要求，保留原标准并把该字段设为UNRESOLVED，不过滤小差。','','本书不将sidecar接入C、D或主线，配置默认仍None。是否启用已通过字段由用户决定。']
    (REPO/'docs/p_followup/B_F64_SIDECAR.md').write_text('\n'.join(lines)+'\n');print('B4_REPORT_READY',b['accepted_fields'])
if __name__=='__main__':main()