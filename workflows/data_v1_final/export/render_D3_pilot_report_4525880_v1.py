"""Render the delivered 4525880 pilot report from small formal JSON only."""
import collections
import json
import os
import pathlib
import stat
import tempfile

R = pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO = R / 'repository'
FORMAL = REPO / 'configs/data_v1/v1-pilot-provisional'
JOB = '4525880'
REPORT = REPO / 'docs/data_v1/training_export_v1_pilot_provisional.md'


def need(value, message):
    if not value:
        raise ValueError(message)


def read_json(path, reference=None):
    path = pathlib.Path(path)
    need(path.is_absolute() and '..' not in path.parts and path.suffix == '.json', 'LITERAL_JSON_ONLY')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'NO_METADATA_SYMLINK')
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 1278 and before.st_size <= 32 << 20,
         'SMALL_OWN_FORMAL_METADATA_ONLY')
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_ino, after.st_size, after.st_mtime_ns), 'METADATA_CHANGED_DURING_READ')
    if reference is not None:
        need(reference['path'] == str(path) and reference['bytes'] == len(raw), 'EXACT_METADATA_REFERENCE')
    # SHA strings below are existing published values. No hashes are recomputed.
    return json.loads(raw)


def formal(ref):
    need(isinstance(ref, dict) and all(k in ref for k in ('path', 'bytes', 'sha256')), 'PUBLISHED_REFERENCE_REQUIRED')
    return read_json(ref['path'], ref)


def cell(value):
    if value is None:
        return '未记录'
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]])


def render():
    d3_path = FORMAL / 'D3_export.json'
    d3 = read_json(d3_path)
    need(d3['version'] == 'v1-pilot-provisional' and str(d3['actual_parent_job_id']) == JOB
         and d3['status'] == 'DELIVERED_PENDING_MODEL_LOADER_AND_HEAD_OVERFIT'
         and d3['actual_root_C0_wrapper'] is True, 'DELIVERED_D3_4525880_REQUIRED')
    native = d3['actual_parent_accounting']
    need(all(str(native[k]) == v for k, v in
             dict(JobIDRaw=JOB, State='COMPLETED', ExitCode='0:0', UID='1278', AllocCPUS='16').items()),
         'FORMALLY_RECORDED_NATIVE_C0_REQUIRED')
    receipt = formal(d3['actual_export_receipt_reference'])
    manifest = formal(d3['manifest_reference'])
    bound_ref = d3['D5_diagnostic_payload_reference']
    need(bound_ref['path'] == str(FORMAL / ('D5_diagnostic_payload_D3_job' + JOB + '_bound.json')),
         'EXACT_SAME_D3_PARENT_BOUND_D5_INDEX_REQUIRED')
    d5 = formal(bound_ref)
    need(d5['version'] == d3['version'] and str(d5['actual_D3_parent_job_id']) == JOB
         and d5['actual_D3_seen_status'] == 'ACTUAL_D3_PAYLOAD_CLOSED_SAME_FROZEN_TRAIN_ROSTER'
         and d5['actual_D3_receipt_reference'] == d3['actual_export_receipt_reference']
         and d5['actual_D3_manifest_reference'] == d3['manifest_reference']
         and d5['actual_root_C0_wrapper'] is True and d5['training_excluded'] is True,
         'D5_ACTUALLY_BOUND_TO_DELIVERED_4525880_REQUIRED')
    need(receipt['schema'] == 'BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1'
         and str(receipt['job_id']) == JOB and receipt['uid'] == 1278
         and receipt['actual_cpus'] == 16 and receipt['export_and_single1000_complete'] is True,
         'CLOSED_EXPORT_RECEIPT_REQUIRED')
    need(receipt['manifest_reference'] == receipt['verification_reference'] == d3['manifest_reference']
         and manifest['schema'] == 'D3_SINGLE_EXPORT_MANIFEST_V1'
         and receipt['pilot_counts'] == d3['pilot_counts'] == manifest['pilot_counts'] == {'TRAIN': 50000, 'VAL': 5000}
         and receipt['source_roundtrip_records'] == manifest['source_roundtrip_records'] == 1000
         and manifest['single_final_count_and_source_sample_pass'] is True, 'ORIGINAL_ONCE_COUNT_AND_1000_PASS_REQUIRED')
    need(all(v.get(k) is False for v in (d3, d5) for k in ('Model_ACK', 'Model_payload_ACK')),
         'REPORT_IS_PENDING_ACTUAL_MODEL_ACCEPTANCE')
    distribution = receipt['distribution']
    need(d3['distribution'] == distribution and distribution['status'] == 'COPIED_WITH_RSYNC_CHECKSUM'
         and distribution['checksum_method'] == 'rsync --checksum'
         and distribution['transfer']['returncode'] == 0, 'ORIGINAL_SUCCESSFUL_CHECKSUM_COPY_REQUIRED')
    stores = manifest['stores']
    by_kind = collections.Counter()
    for item in stores:
        by_kind[item['kind']] += item['records']
    lmdb_bytes = sum(v['data_reference']['bytes'] for v in stores)
    f64_bytes = sum(v['F64_reference']['bytes'] for v in stores)
    store_manifest_bytes = sum(v['manifest_reference']['bytes'] for v in stores)
    benchmark = receipt['benchmark']
    tmp = distribution.get('tmp', {})
    refs = [('D3 原始收据', d3['actual_export_receipt_reference']), ('D3 唯一导出清单', d3['manifest_reference']),
            ('D3 实际计划', receipt['plan_reference']), ('试点人口/组件入口', receipt['pilot_acceptance_reference']),
            ('原闭合投影分片目录', receipt['source_resume_closed_log_reference']), ('同父绑定 D5', bound_ref),
            ('D5 原始交付组件', d5['original_D5_component_reference']), ('D5 唯一校验结果', d5['verification_reference'])]
    refs.extend((key, value) for key, value in receipt['actual_configuration_references'].items())
    if receipt.get('actual_original_series_size_rho_reference'):
        refs.append(('原始序列尺寸相关性', receipt['actual_original_series_size_rho_reference']))
    reference_table = table(['输入/证据', '路径', '字节', '已公布 SHA256'],
                            [(name, ref['path'], ref['bytes'], ref['sha256']) for name, ref in refs])
    counts = table(['项目', '正式元数据值'], [
        ('TRAIN 分子', manifest['pilot_counts']['TRAIN']), ('ROUTINE VAL 分子', manifest['pilot_counts']['VAL']),
        ('关闭子库', len(stores)), ('几何记录（含输入视图/子几何）', by_kind['geometry']),
        ('标签家族记录', by_kind['labels']), ('全部导出记录', manifest['exported_records']),
        ('训练 LMDB 字节', lmdb_bytes), ('共享永久 F64 字节', f64_bytes),
        ('子库清单字节', store_manifest_bytes), ('清单定义的总 payload 字节', manifest['total_payload_bytes']),
        ('原 Parquet 抽样记录', manifest['source_roundtrip_records']),
        ('D5 已见 TRAIN 分子/未见构象诊断', d5['actual_seen_D5_intersection_MIDs']),
        ('D5 几何记录', d5['selected_geometries']), ('D5 标签记录', d5['available_label_records']),
        ('D5 关闭子库', d5['closed_store_count'])])
    performance = table(['项目', '正式元数据值'], [
        ('复制状态', distribution['status']), ('目标节点', distribution['node']),
        ('目标目录', distribution['directory']), ('实际复制字节', distribution['logical_copy_bytes']),
        ('复制文件数', distribution['file_count']), ('复制前 /tmp 可用字节', tmp.get('tmp_available_bytes')),
        ('复制所需字节', tmp.get('required_copy_bytes')), ('保留余量字节', tmp.get('reserve_bytes')),
        ('单次 benchmark 状态', benchmark['status']), ('请求测量秒数', benchmark.get('requested_seconds')),
        ('实际测量秒数', benchmark.get('duration_seconds')), ('CPU reader workers', benchmark.get('workers')),
        ('分子/秒', benchmark.get('molecules_per_second')), ('记录/秒', benchmark.get('records_per_second')),
        ('随机 MID 窗口', benchmark.get('distinct_sample_MIDs')), ('重试次数', benchmark.get('retry_count')),
        ('cache 状态', benchmark.get('cache_state')), ('GPU 计算', benchmark.get('GPU_used'))])
    exceptions = []
    if receipt.get('errors'):
        exceptions.append('原收据异常：' + cell(receipt['errors']))
    if benchmark['status'] != 'COMPLETE':
        execution = benchmark.get('execution', {})
        exceptions.append('单次读取测量未通过：' + cell(benchmark['status']) + '；throughput 仅按原元数据报告。' +
                          cell(benchmark.get('error') or execution.get('stderr', '')[-1000:]))
    if benchmark.get('duration_seconds', 0) > 300:
        exceptions.append('原元数据实际测量时长超过五分钟；保留实测值，不重测。')
    if not exceptions:
        exceptions.append('正式收据未记录导出错误；此前作业失败不在本次元数据中推算或计为成功。')
    return '\n\n'.join([
        '# 训练导出：v1-pilot-provisional',
        '重建本报告：`python -B workflows/data_v1_final/export/render_D3_pilot_report_4525880_v1.py`。仅使用本轮正式元数据。',
        '## 1. 目的',
        '交付固定试点 TRAIN 与 ROUTINE VAL 的 D-1 v3.0 家族 LMDB，并将已关闭 D5 诊断载荷绑定到实际 D3 父作业。'
        '本报告只读取正式 JSON 元数据，不读取 LMDB/SQLite/Parquet 正文，不执行新 QA、哈希、复制或性能测量。',
        '## 2. 输入数据及其哈希',
        '正式入口：`' + str(d3_path) + '`。实际导出父作业 `' + JOB + '`；正式记载原生状态 `' +
        native['State'] + '/' + native['ExitCode'] + '`，节点 `' + native['NodeList'] + '`，分配 CPU `' + native['AllocCPUS'] + '`。'
        '下表沿用正式引用中的 SHA256，不重新计算；源分片、几何和统计组件由试点组件入口及实际计划追溯。',
        reference_table,
        '## 3. 规则和参数',
        '按家族拆分 float32 LMDB，几何与标签分库，使用原 MFM3 数组编码及原 mask/原因域，不使用 pickle。'
        '本试点包含 PM7 几何 S、D/P 标签及已有 UFF S′ 几何；不包含 UFF D′/P′ 标签。'
        '固定 TRAIN/ROUTINE VAL 人口，D5 为 TRAIN_UNSEEN_CONFORMATION，排除于训练。'
        '永久 F64 权威与完整来源 metadata 保留在共享存储；训练连续值仅做原编码器的一次 F32 转换。'
        'r73 保持完整有序条目，r674 保持 LOSS_DISABLED，原值和 mask 保留。',
        '本次复用已闭合源分片 `' + cell(receipt['reused_closed_source_groups']) + '` 组；本父新增 QM/UFF 调用 `' +
        cell(receipt['new_QM_UFF_calls']) + '`；writer 数 `' + cell(receipt['parallel_store_workers']) + '`。'
        '可用构象顺序 `' + cell(receipt.get('available_orders')) + '`；不可用顺序 `' +
        cell(receipt.get('unavailable_orders')) + '`。',
        '验收按用户最终简化规则：末尾一次计数与随机 1000 条原 Parquet 逐字段对照、一次总清单 SHA；'
        '不执行独立重放、16-reader 复核或全量 F64 二次扫描。分发只用一次 `rsync --checksum`，不追加复制后哈希；'
        '读取测量只有一次，目标窗口不超过五分钟，不重试。',
        '## 4. 统计结果',
        counts,
        '全部数字来自正式清单/收据。几何记录包括实际输入视图及子几何，不能当作去重后的普通构象数。'
        '总 payload 为原清单口径，不包含历史源缓存、临时路由、目录块和复制副本，不等于账户总占用。',
        performance,
        '唯一 export manifest SHA256：`' + d3['manifest_reference']['sha256'] + '`。'
        '单次 F32 抽样比较摘要：`' + cell(manifest.get('original_once_F32_cast_digest')) + '`。'
        '训练 LMDB 与清单复制到节点本地；F64 是否复制：`' + cell(distribution.get('F64_authority_copied_to_gpu')) +
        '`，范围 `' + cell(distribution.get('node_local_copy_scope')) + '`。共享 F64 路径/引用保持原值。',
        '## 5. 异常情况及处理方式',
        '\n'.join('- ' + value for value in exceptions),
        'benchmark 失败/超时时保留原状态与空缺吞吐，不补跑，不替代已完成的导出、原 Parquet QA 和 checksum 分发。',
        '## 6. 已知限制',
        '`Model_ACK=false`，`Model_payload_ACK=false`。实际 Model loader 与逐 head overfit 是后续真正模型验收；'
        '本报告及数据父作业 C0 不代填该 ACK。D-6 未放行，最终 Common、完整三种构象顺序及全量统计不由本试点冒充。'
        '归一化仅沿用当前试点版本，无新拟合。读测仅为单节点有限随机 MID 窗口，且在单次 rsync 后运行，'
        '不能解释为冷缓存、全库或多节点吞吐。共享 F64 权威读取仍依赖其原共享路径。',
    ]) + '\n'


def main():
    need(os.getuid() == 1278, 'MAIN_UID1278_REQUIRED')
    data = render().encode('utf-8')
    if REPORT.exists():
        need(REPORT.read_bytes() == data, 'EXISTING_DIFFERENT_REPORT_PRESERVED_FOR_ROOT_REVIEW')
        print(json.dumps(dict(status='UNCHANGED',report_path=str(REPORT),actual_parent_job_id=JOB)))
        return
    fd, name = tempfile.mkstemp(prefix=REPORT.name + '.', suffix='.pending', dir=REPORT.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, REPORT)  # Never overwrite a report created concurrently.
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(dict(status='CREATED',report_path=str(REPORT),actual_parent_job_id=JOB)))


if __name__ == '__main__':
    main()
