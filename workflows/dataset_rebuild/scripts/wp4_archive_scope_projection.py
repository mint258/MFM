"""Read-only WP4 archive-scope projections; no QM, LMDB, repacking or deletion.

All parsed scientific labels remain available on every original conformer.
The proposed 420 GB parsed-label ceiling is a decision proposal, not an applied
change to the original 200 GB budget. Scientific values are not transformed.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
BENCHMARK = ROOT/'wp4_storage_benchmark/job_4513016'
DEPS = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
POLICIES = ('SUCCESS_B_MINIMUM_OTHER_OUTPUTS_UNCHANGED', 'ALL_ORDINARY_SUCCESS_MINIMUM_ALL_FAILURES_KEPT')
MODELS = ('EXPECTED_SAME_SIZE_PACK_FACTOR', 'CONSERVATIVE_DIRECT_PER_CALL_COMPRESSED_SUM')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1 << 20),b''): result.update(block)
    return result.hexdigest()


def save(path, value):
    pending = Path(str(path)+'.pending')
    pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    pending.replace(path)


def arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError:
        sys.path.insert(0,str(DEPS))
        import pyarrow as pa
        import pyarrow.parquet as pq
    return pa,pq


def initialize(barrier):
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    pa,_ = arrow(); pa.set_cpu_count(1); pa.set_io_thread_count(1)
    barrier.wait(timeout=180)


def read_molecule(source):
    _,pq = arrow()
    receipt = read_json(source['receipt_path'])
    if sha(source['receipt_path']) != source['receipt_sha256']:
        raise ValueError('Source receipt SHA differs: '+source['receipt_path'])
    if receipt.get('status') != 'COMPLETE_WITH_RECORDED_OUTCOMES': raise ValueError('Native molecule not closed')
    ref = source['parquet']
    if receipt['parquet'] != ref or Path(ref['path']).stat().st_size != ref['bytes'] or sha(ref['path']) != ref['sha256']:
        raise ValueError('Original result Parquet binding differs: '+ref['path'])
    archive = receipt.get('archive')
    if archive and Path(archive['path']).stat().st_size != archive['bytes']: raise ValueError('Closed archive byte binding differs')
    counts, record_ids, slots = Counter(), set(), set()
    totals = defaultdict(Counter); missing = []
    minimum = receipt.get('minimum_original_energy_record_id')
    if minimum != source.get('minimum_original_energy_record_id') or minimum not in source['record_ids']:
        raise ValueError('Original energy minimum identity differs')
    all_launched = 0; call_bytes = 0
    columns = ['record_id','molecule_id','task','status','size_stratum','archive_bytes','details_json']
    for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=32,columns=columns,use_threads=False):
        for row in batch.to_pylist():
            record,task,status = row['record_id'],row['task'],row['status']
            if (record,task) in slots: raise ValueError('Duplicate final outcome')
            slots.add((record,task)); counts[task] += 1; record_ids.add(record)
            if row['molecule_id'] != source['molecule_id'] or row['size_stratum'] != source['size_stratum']:
                raise ValueError('Source molecule/stratum differs')
            detail = json.loads(row['details_json'])
            # Only operational/archive metadata is consumed. Parsed scientific
            # values remain untouched in the original and tested typed files.
            detail.pop('values',None)
            if detail.get('record_id') != record or detail.get('task') != task or detail.get('status') != status:
                raise ValueError('Outcome identity/status differs from original detail')
            launched = bool(detail.get('argv')) and not status.startswith(('SKIPPED_','Q03_SOURCE','NOT_STARTED_'))
            all_launched += launched
            percall = detail.get('archive',{}).get('per_call_compressed_bytes',row['archive_bytes'])
            if percall is None:
                if launched:
                    missing.append({'record_id':record,'task':task,'reason':'Launched outcome has no compressed output measurement'})
                percall = 0  # Only explicit non-launched outcomes are measured zero.
            elif type(percall) is not int or percall < 0:
                raise ValueError('Invalid per-call archive byte measurement')
            call_bytes += percall
            value = totals[task]
            value['rows'] += 1; value['launched'] += launched; value['all_percall_bytes'] += percall
            value['success_rows'] += status=='SUCCESS'
            value['failure_or_skip_rows'] += status!='SUCCESS'
            value['timeout_rows'] += status=='TIMEOUT'
            if status == 'SUCCESS':
                value['success_percall_bytes'] += percall
                if record == minimum:
                    value['minimum_success_rows'] += 1
                    value['minimum_success_percall_bytes'] += percall
            else:
                value['failure_or_skip_percall_bytes'] += percall
            if task == 'xtb_hessian' and record != minimum: raise ValueError('Hessian not on original molecular minimum')
    if counts != Counter(source['task_counts']) or len(slots) != receipt['requested_outcomes']:
        raise ValueError('Requested final task slots differ')
    if record_ids != set(source['record_ids']) or len(record_ids) != receipt['records']:
        raise ValueError('Closed native records differ from formal population')
    closed_bytes = archive['bytes'] if archive else (0 if all_launched==0 else None)
    if closed_bytes is None: missing.append({'molecule_id':source['molecule_id'],'reason':'No closed archive for launched molecule'})
    return {'source_id':source['source_id'],'molecule_id':source['molecule_id'],'size_stratum':source['size_stratum'],
        'records':len(record_ids),'slots':len(slots),'closed_archive_bytes':closed_bytes,
        'percall_archive_bytes':call_bytes,'tasks':{key:dict(value) for key,value in totals.items()},
        'missing':missing,'worker_pid':os.getpid()}


def quota(path):
    if not Path(path).is_file(): return {'remaining_bytes':None,'reason':'Quota snapshot unavailable'}
    raw = read_json(path); entry = raw.get('quota',{})
    if entry.get('exit_code',entry.get('rc')) != 0: return {'remaining_bytes':None,'reason':'Quota query failed'}
    for line in entry.get('stdout','').splitlines():
        tokens = line.split()
        if len(tokens)<4 or not tokens[0].startswith('/'): continue
        try: used,soft,hard = [int(item.rstrip('*')) for item in tokens[1:4]]
        except ValueError: continue
        limits = [value for value in (soft,hard) if value>0]
        remaining = (min(limits)-used)*1024 if limits else None
        return {'path':str(path),'sha256':sha(path),'time_UTC':raw.get('time_UTC'),
            'remaining_bytes':remaining,'planning_budget_bytes':min(2_000_000_000_000,remaining) if remaining is not None else None}
    return {'remaining_bytes':None,'reason':'Quota line unrecognized'}


def projections(manifest, molecules, benchmark, quota_info):
    weights = {row['size_stratum']:row for row in manifest['strata']}
    strata, tasks = [], []
    for key,weight in weights.items():
        group = [item for item in molecules if item['size_stratum']==key]
        rw,mw = weight['record_population_weight'],weight['molecule_population_weight']
        if len(group)!=weight['molecules'] or sum(item['records'] for item in group)!=weight['records']:
            raise ValueError('Formal stratum sample denominator differs')
        missing = [issue for item in group for issue in item['missing']]
        closed = sum(item['closed_archive_bytes'] or 0 for item in group)
        percall = sum(item['percall_archive_bytes'] for item in group)
        factor = closed/percall if not missing and percall else None
        by_task = defaultdict(Counter)
        for item in group:
            for task,value in item['tasks'].items(): by_task[task].update(value)
        baseline = p1 = p2 = hessian = 0.0
        for task,value in sorted(by_task.items()):
            if task == 'xtb_hessian':
                hessian = value['all_percall_bytes']*mw
                tasks.append({'size_stratum':key,'task':task,'sample':dict(value),'scope':'Molecular minimum; separate subset fraction',
                    'full_minimum_percall_bytes':hessian,'full_minimum_expected_bytes':hessian*factor if factor is not None else None})
                continue
            base = value['all_percall_bytes']*rw
            failures = value['failure_or_skip_percall_bytes']*rw
            minimum_success = value['minimum_success_percall_bytes']*mw
            retained = failures+minimum_success
            baseline += base; p1 += retained if task=='pm7_B' else base; p2 += retained
            tasks.append({'size_stratum':key,'task':task,'sample':dict(value),
                'baseline_percall_bytes':base,'kept_all_failure_percall_bytes':failures,
                'kept_minimum_success_percall_bytes':minimum_success,'policy_2_percall_bytes':retained,
                'policy_2_expected_bytes':retained*factor if factor is not None else None,
                'weight_method':'All non-SUCCESS outcomes weighted by records; successful original minima weighted by molecules. Explicit non-launched skips have measured zero output.'})
        strata.append({'size_stratum':key,'sample_molecules':len(group),'sample_records':sum(item['records'] for item in group),
            'record_population_weight':rw,'molecule_population_weight':mw,'closed_archive_bytes':closed,
            'percall_compressed_bytes':percall,'archive_pack_factor':factor,'missing_measurements':missing,
            'baseline_nonhessian_percall_bytes':baseline,'policy_1_nonhessian_percall_bytes':p1,
            'policy_2_nonhessian_percall_bytes':p2,'hessian_full_minimum_percall_bytes':hessian})
    complete = all(not row['missing_measurements'] and row['archive_pack_factor'] is not None for row in strata)
    old_storage = benchmark['storage']
    typed_nonhessian = sum(row['estimated_all_conformer_typed_Parquet_bytes_excluding_hessian']+
        row['estimated_input_recipe_bytes']+row['estimated_source_reference_manifest_bytes'] for row in old_storage['strata'])
    typed_hessian = sum(row['estimated_minimum_hessian_typed_Parquet_bytes'] for row in old_storage['strata'])
    # Reuse the measured benchmark's final label+provenance totals exactly;
    # do not repeat typed conversion, schemas, precision changes or roundtrip.
    known_base = next(plan['parsed_labels_and_provenance_bytes'] for plan in old_storage['budget_plans'] if plan['hessian_molecule_fraction']==0)
    known_full = old_storage['estimated_all_labels_recipes_and_manifest_bytes_full_hessian']
    if abs(known_base+typed_hessian-known_full)>1:
        raise ValueError('Frozen typed benchmark Hessian/label accounting inconsistent')
    budget = quota_info.get('planning_budget_bytes')
    new_parser_ceiling = 420_000_000_000
    reserved = new_parser_ceiling+600_000_000_000+400_000_000_000
    archive_allowance = budget-reserved if budget is not None else None
    estimates = []
    policy_fields = {POLICIES[0]:'policy_1_nonhessian_percall_bytes',POLICIES[1]:'policy_2_nonhessian_percall_bytes'}
    for policy,field in policy_fields.items():
        for model in MODELS:
            calibrated = model==MODELS[0]
            base = sum(row[field]*(row['archive_pack_factor'] if calibrated else 1) for row in strata) if complete else None
            hessian = sum(row['hessian_full_minimum_percall_bytes']*(row['archive_pack_factor'] if calibrated else 1) for row in strata) if complete else None
            baseline = sum(row['baseline_nonhessian_percall_bytes']*(row['archive_pack_factor'] if calibrated else 1) for row in strata) if complete else None
            for fraction in (0,.001,.01,.05,.1,1):
                archive = base+hessian*fraction if complete else None
                total = reserved+archive if archive is not None else None
                measured_labels = known_base+typed_hessian*fraction
                estimates.append({'policy':policy,'archive_model':model,'hessian_molecule_fraction':fraction,
                    'all_parsed_scientific_labels_retained':True,'measured_model_label_and_provenance_bytes':measured_labels,
                    'proposed_parsed_label_ceiling_bytes':new_parser_ceiling,'original_parsed_label_ceiling_bytes':200_000_000_000,
                    'parsed_budget_change_applied':False,'fits_proposed_420GB_label_ceiling':measured_labels<=new_parser_ceiling,
                    'nonhessian_archive_bytes':base,'hessian_archive_bytes':hessian*fraction if complete else None,
                    'total_archive_bytes':archive,'saved_nonhessian_archive_bytes':baseline-base if complete else None,
                    'lmdb_reservation_bytes':600_000_000_000,'scratch_and_margin_reservation_bytes':400_000_000_000,
                    'proposed_total_forward_budget_bytes':total,'account_remaining_budget_bytes':budget,
                    'archive_allowance_after_proposed_reservations_bytes':archive_allowance,
                    'headroom_bytes':budget-total if total is not None and budget is not None else None,
                    'fits_account_with_proposed_420GB_ceiling':total<=budget if total is not None and budget is not None else None})
    ref = old_storage.get('estimated_expected_baseline_archive_bytes_excluding_hessian')
    previous = next(plan['archive_bytes'] for plan in old_storage['budget_plans']
        if plan['hessian_molecule_fraction']==0 and plan['model']=='EXPECTED_SAME_PACK_FACTOR')
    newly = next(row['nonhessian_archive_bytes'] for row in estimates
        if row['policy']==POLICIES[0] and row['archive_model']==MODELS[0] and row['hessian_molecule_fraction']==0)
    check = {'existing_B_minimum_expected_archive_bytes':previous,'new_read_only_B_minimum_expected_archive_bytes':newly,
        'difference_bytes':newly-previous if newly is not None else None,
        'agrees_with_frozen_benchmark_within_1_byte':abs(newly-previous)<1 if newly is not None else None}
    if complete and not check['agrees_with_frozen_benchmark_within_1_byte']:
        raise ValueError('Policy 1 does not reproduce frozen storage benchmark')
    return {'complete':complete,'strata':strata,'task_components':tasks,'estimates':estimates,'policy_1_crosscheck':check,
        'original_200GB_limit_exceeded_by_existing_lossless_model':known_full>200_000_000_000,
        'proposed_420GB_limit_is_not_authorized_or_applied':True,
        'fixed_reservations_after_proposed_change_bytes':reserved,'maximum_archive_allowance_bytes':archive_allowance,
        'scientific_coverage':'Every parsed label and QC stays on every original conformer. SUCCESS means exact original status == SUCCESS; PROPERTY_FAILED, CALCULATION_FAILED, TIMEOUT and every other non-SUCCESS available output are retained.',
        'raw_retention':'Policy 1 keeps complete existing successful B output only on original molecular minima; all other task outputs unchanged. Policy 2 keeps complete existing output of each successful non-hessian task only on the original molecular minimum; every non-SUCCESS output remains retained on every conformer. Hessian scope is a separate molecular subset.',
        'no_minimum_substitution':'If a molecular-minimum task failed, that failed output is retained under the failure rule. No successful non-minimum record is substituted for it.',
        'calibration_limit':'Expected model reuses each size stratum closed/per-call pack factor. Selecting outputs can change this factor. Direct sums of already compressed per-call outputs are an independent conservative planning model, not a mathematical bound on future framing/compression. Entire retained call archives (including sampled AUX/stdout) count; no isolated .out sizes are invented.',
        'historical_attempt_limit':'Historical attempt overhead, if any, enters the closed/per-call pack factor. Direct per-call model covers final recorded outcomes; retained historical-failure bytes are not independently separable from those final metrics.',
        'budget_proposal':'Propose increasing parsed-label allocation from 200 to 420 GB while preserving all lossless labels, 600 GB LMDB reservation and 400 GB scratch/margin. Raw allowance is the actual remaining account budget minus 1.420 TB. User decision is required; this script applies no budget or retention changes.',
        'units':'GB and TB decimal, quota KiB converted to bytes.'}


def markdown(report):
    projection = report['projection']
    def gb(value): return '待测' if value is None else f'{value/1e9:.3f}'
    def tb(value): return '待测' if value is None else f'{value/1e12:.3f}'
    selected = [row for row in projection['estimates'] if row['hessian_molecule_fraction']==0]
    lines = ['保留全构象的全部已解析科学标签；仅比较原输出归档范围。', '',
        f"只读核验 {report['records']:,} records / {report['molecules']:,} molecules / {report['slots']:,} outcomes，实际 reader worker {len(report['actual_worker_pids'])}。未重复数值规整、roundtrip 或 QM。", '',
        f"预算调整建议（未应用）：解析存储 200 → 420 GB，LMDB 600 GB、scratch/margin 400 GB；当前账户可用 {tb(report['quota'].get('planning_budget_bytes'))} TB，允许归档最多 {gb(projection['maximum_archive_allowance_bytes'])} GB。", '',
        '| 原输出保留策略 | 归档估算模型 | 非 Hessian 归档 GB | 含预算预留总 TB | 配额余量 GB | 满足配额 |',
        '|---|---|---:|---:|---:|---|']
    for row in selected:
        policy = '① 成功 B 仅最低，其他原样' if row['policy']==POLICIES[0] else '② 所有普通成功任务仅最低'
        model = '同层 pack 期望' if row['archive_model']==MODELS[0] else '独立 per-call 相加保守值'
        lines.append(f"| {policy} | {model} | {gb(row['nonhessian_archive_bytes'])} | {tb(row['proposed_total_forward_budget_bytes'])} | {gb(row['headroom_bytes'])} | {row['fits_account_with_proposed_420GB_ceiling']} |")
    lines += ['', '所有失败、属性失败、超时原输出保持；成功原最低能构象的整个既有 call archive（含已存 stdout/AUX）计入保留量。原生科学失败和 POLAR 不对称值/QC不变。', '',
        '| Hessian 分子子集比例 | ②归档模型 | Hessian 新增 GB | ②归档合计 GB | 含预留总 TB | 配额余量 GB |',
        '|---|---|---:|---:|---:|---:|']
    for row in projection['estimates']:
        if row['policy']!=POLICIES[1]: continue
        model = '同层 pack 期望' if row['archive_model']==MODELS[0] else 'per-call 相加'
        lines.append(f"| {row['hessian_molecule_fraction']:.3g} | {model} | {gb(row['hessian_archive_bytes'])} | {gb(row['total_archive_bytes'])} | {tb(row['proposed_total_forward_budget_bytes'])} | {gb(row['headroom_bytes'])} |")
    lines += ['', '①与原 benchmark 的同层 pack 估算差值 '+gb(projection['policy_1_crosscheck']['difference_bytes'])+' GB。', '',
        '方法：全构象失败与仍按全构象保留的任务采用 record_population_weight；成功最低构象及 Hessian 采用 molecule_population_weight。最低构象失败不会用其它构象的成功结果替代。', '',
        'pack 期望不代表实际重新归档后的压缩率，独立 per-call 相加值用于保守规划。选择影响归档范围，不影响科学标签覆盖。所有数据和归档均只读。420 GB 新解析上限与归档范围须交用户决定；原 200 GB 上限未被修改。']
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prototype-manifest',default=str(BENCHMARK/'prototype_manifest.json'))
    parser.add_argument('--benchmark-summary',default=str(BENCHMARK/'benchmark_summary.json'))
    parser.add_argument('--capacity',default=str(ROOT/'reports/wp5_capacity_snapshot.json'))
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--output')
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text())
        print(json.dumps({'status':'AST_PASS','data_read':False,'QM_started':False,'LMDB_opened_or_written':False}))
        return 0
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:
        raise RuntimeError('At least 16 allocated Slurm CPUs and actual metadata workers required')
    if not args.output: raise ValueError('New independent --output required')
    output = Path(args.output).absolute()
    if not output.is_relative_to(ROOT) or output==ROOT or output.exists(): raise ValueError('Fresh analysis output under phase root required')
    started = time.monotonic()
    prototype = read_json(args.prototype_manifest); benchmark = read_json(args.benchmark_summary)
    if benchmark['status']!='TEST_LOSSLESS_STORAGE_BENCHMARK_COMPLETE' or benchmark.get('issues'):
        raise ValueError('Closed tested lossless benchmark required')
    if prototype['roundtrip_status']!='ALL_SCIENTIFIC_AND_FULL_DETAIL_LEAVES_EXACT_PASS' or benchmark['roundtrip']['rows_pass']!=benchmark['slots']:
        raise ValueError('Existing scientific roundtrip closure missing; no rerun is performed')
    formal = prototype['formal_manifest']; manifest = formal['data']
    if sha(formal['path'])!=formal['sha256'] or manifest['target_records']<10000:
        raise ValueError('Formal WP4 manifest binding differs')
    sources = prototype['source_results']
    if len(sources)!=manifest['molecules']: raise ValueError('Formal closed molecule count differs')
    context = multiprocessing.get_context('spawn'); barrier = context.Barrier(args.workers)
    print(json.dumps({'stage':'READ_CLOSED_ARCHIVE_METADATA','molecules':len(sources),'workers':args.workers}),flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
            initializer=initialize,initargs=(barrier,)) as pool:
        result = list(pool.map(read_molecule,sources,chunksize=1))
    pids = sorted({item['worker_pid'] for item in result})
    if len(pids)<16: raise RuntimeError('Fewer than 16 actual metadata reader workers')
    if sum(item['slots'] for item in result)!=benchmark['slots'] or sum(item['records'] for item in result)!=manifest['actual_records']:
        raise ValueError('All formal outcomes were not read exactly once')
    quota_info = quota(args.capacity)
    projection = projections(manifest,result,benchmark,quota_info)
    report = {'status':'READ_ONLY_ARCHIVE_SCOPE_PROJECTION_COMPLETE' if projection['complete'] else 'INCOMPLETE_ARCHIVE_MEASUREMENTS',
        'scope':'USER_DECISION_PROPOSAL_ALL_SCIENTIFIC_CONFORMER_LABELS_RETAINED',
        'job_id':os.environ.get('SLURM_JOB_ID'),'hostname':socket.gethostname(),'python_logical_entry':sys.executable,
        'script_sha256':sha(__file__),'benchmark_summary':{'path':args.benchmark_summary,'sha256':sha(args.benchmark_summary)},
        'prototype_manifest':{'path':args.prototype_manifest,'sha256':sha(args.prototype_manifest)},
        'records':manifest['actual_records'],'molecules':len(result),'slots':sum(item['slots'] for item in result),
        'requested_workers':args.workers,'actual_worker_pids':pids,'quota':quota_info,'projection':projection,
        'seconds':time.monotonic()-started,'QM_started':False,'LMDB_opened_or_written':False,
        'scientific_values_transformed':False,'typed_roundtrip_repeated':False,'raw_repacked_or_deleted':False,
        'original_budget_limits_modified':False}
    output.mkdir(parents=True)
    save(output/'archive_scope_projection.json',report)
    (output/'archive_scope_projection.md').write_text(markdown(report),encoding='utf-8')
    print(json.dumps({'status':report['status'],'output':str(output),'workers':len(pids),'seconds':report['seconds']}),flush=True)
    return 0 if projection['complete'] else 1


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
