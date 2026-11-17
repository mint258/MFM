"""B4 render only producer/actual-loader evidence; never reread labels or hash sources."""
from resources import REPO,load,guard


def main():
    guard(force=True);m=load(REPO/'configs/p_followup/B_sidecar_manifest.json');b=load(REPO/'results/p_followup/B3_acceptance.json')
    if b['status'] not in ['COMPLETE','UNRESOLVED_FIELDS']:raise ValueError('B3 is not terminal')
    lines=['# B：大数值能量字段F64补存','','状态：B0、B1、B2及B3已执行；逐字段是否接受见下表。生产sidecar覆盖D6的TRAIN/FULL全部P/U记录，验收限既有冻结42961记录。','','B0只用冻结TRAIN核心的原F64缓存：r=|Δ_F32−Δ_F64|/|Δ_F64|，e=|Δ_F32−Δ_F64|。中位r>1e-4且中位e/D4scale>1e-6，或源非零对归零率≥0.001时入选。共4个字段；规则未随结果调整。','','B1只读既有物理索引与原common.task_components。CELL标量投影保留原kind/f64等叶；需要数组kind时读取该源行完整CELL。源路由只在内存，不创建新的全源索引或改写LMDB。按D6顺序存MI、CI、7字节LMDB句柄（由id_map的kind/MI/CI生成）及F64列，全部mask无效值为NaN。写出时唯一一次逐值核对f32(source)与D6的位模式，不匹配写NaN，loader回退原F32；错配/缺源超过0.01%则整字段UNRESOLVED。','','B2新增p_f64_sidecar可选路径，默认None。只有有限sidecar值覆盖有效graph scalar raw；F64 raw在归一化及元素参考相减时保持F64，最终输出F32。A1及状态差自动继承base read。原11-07/D4和A1参数均未重拟合。','','B3在同一冻结物理记录上分别运行11-07与A1，逐记录读取当前p-recipe实际loader作为关闭开关的109字段基准。源非零构象对的归一化差必须非零，且与源F64直接差/scale相比满足1e-6+1e-5|参考差|。未入选字段开/关逐位一致。下列是固定数值验收，无统计显著性或阈值扫描。','','|字段|D6有效值|B1错配/缺源|11-07归零/非零对|A1归零/非零对|数值失败(两路径)|最终状态|','|---|---:|---:|---|---|---:|---|']
    for n in m['requested_fields']:
        s=m['field_status'][n];a=b['recipes']['D4']['fields'][n];z=b['recipes']['A1']['fields'][n]
        lines.append(f"|{n}|{s['D6_valid_values']}|{s['mismatch']+s['missing_source']}|{a['normalized_zero_pairs']}/{a['source_nonzero_pairs']}|{z['normalized_zero_pairs']}/{z['source_nonzero_pairs']}|{a['numerical_failures']+z['numerical_failures']}|{'COMPLETE' if n in b['accepted_fields'] else 'UNRESOLVED'}|")
    if not m['enabled_fields']:
        lines+=['','本次B1没有可启用字段：已定位源值的记录单次F32 cast错配为0，但每字段约19.07万条D6有效记录未能经指定物理索引定位原F64，缺源率约1.406%，超过预注册0.01%上限，因此四字段整体UNRESOLVED。保留既有索引与完整P/U范围，不缩成P-only、不另建全源索引、不放宽阈值。',
            '', '因此本次B3的打开开关路径对这四字段仍回退原F32；表中的归零和数值失败描述的是回退路径，不能用来判断完整覆盖的F64读取是否有效，也不能与64MID工程smoke的F64覆盖结果混为一谈。当前没有通过验收、可建议启用的字段。']
    lines+=['','B1实际分配成本包含工程失败及恢复：原扫描4535157为5CPU×25723秒，句柄检查失败4535380为4CPU×15秒，参考缓存恢复4535384为4CPU×4422秒，源值续接4535385为4CPU×9605秒；合计51.329 CPU-h。未执行的依赖作业不计CPU成本。manifest.seconds=9593.85秒只属于最后一次源值调用，不代表B1总耗时或总成本。B3作业4535386为COMPLETED/0，2CPU×3352秒，即1.862 CPU-h；B1+B3上述分配合计53.191 CPU-h。不重复算SHA或源标签。']
    lines+=['','|路径|实际验收记录|关闭开关与主线不一致记录|未入选字段开/关不一致记录|','|---|---:|---:|---:|']
    for n,r in b['recipes'].items():
        k=r['checks'];lines.append(f"|{n}|{k['records']}|{k['baseline_off_mismatch_records']}|{k['nonselected_on_mismatch_records']}|")
    lines+=['','CPU吞吐只作报告：同一固定20000记录，A1路径，固定先off后on各一次，不作为通过门槛。两次共享操作系统缓存且本次enabled_fields为空，不能将差异解释为F64读取加速或做受控速度比较。','','|开关|样本/秒|秒|','|---|---:|---:|']
    for n,r in b['throughput'].items():lines.append(f"|{n}|{r['samples_per_second']}|{r['seconds']}|")
    lines+=['','|split|记录数|实际携带入选字段记录|values bytes|values SHA256|offsets SHA256|','|---|---:|---:|---:|---|---|']
    for n,r in m['splits'].items():lines.append(f"|{n}|{r['records']}|{r['records_carrying_selected']}|{r['values_bytes']}|{r['values_SHA256']}|{r['molecule_offsets_SHA256']}|")
    lines+=['','文件路径与字段清单详见configs/p_followup/B_sidecar_manifest.json。SHA来自B1最终文件的一次性计算，此报告不重新读取sidecar或源文件。原始F64的数值精度不等于量化方法的物理准确性，F32最终输出仍可能使极小的非零差不可分辨；若实际违反零归零要求，保留原标准并把该字段设为UNRESOLVED，不过滤小差。','','本书不将sidecar接入C、D或主线，配置默认仍None。本次没有可建议启用的字段；不以扩大源索引或修改准入规则追加任务。']
    (REPO/'docs/p_followup/B_F64_SIDECAR.md').write_text('\n'.join(lines)+'\n');print('B4_REPORT_READY',b['accepted_fields'])
if __name__=='__main__':main()