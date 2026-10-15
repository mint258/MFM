"""Refresh Root storage snapshot and document the approved v7 full execution."""
import json, os, socket, subprocess, time
from pathlib import Path
from prepare import ROOT, save, sha

def main():
    assert os.getuid() == 1278 and socket.gethostname().split('.')[0] == 'sonmi'
    summary_path = ROOT / 'reports/pilot_summary.json'
    summary = json.loads(summary_path.read_text())
    assert summary['reproduction100']['status'] == 'PASS'
    authorization_path = ROOT / 'reports/full_run_user_decision.json'
    authorization = json.loads(authorization_path.read_text())
    assert authorization['status'] == 'APPROVED_BY_USER'
    assert authorization['pilot_summary_sha256'] == sha(summary_path)
    q = subprocess.run(['quota', '-w', '-u', 'zixiao'], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=30)
    assert q.returncode == 0, (q.returncode, q.stderr)
    entries = [line.split() for line in q.stdout.splitlines() if line.strip().startswith('/dev/sda1 ')]
    assert len(entries) == 1, q.stdout
    used_kib, soft_kib, hard_kib = [int(v.rstrip('*')) for v in entries[0][1:4]]
    assert hard_kib > 0 and used_kib <= hard_kib
    available = (hard_kib - used_kib) * 1024
    # Parts plus final Parquet, compact pointers, future training/checkpoint allowance,
    # and margin for the existing WP5 tasks on the same project quota.
    required = 2 * summary['predicted_output_bytes'] + (4 + 400 + 300) * (1 << 30)
    stamp = time.time()
    result = {'timestamp': stamp, 'valid_until_epoch': stamp + 1800,
        'valid_for_submission': available >= required, 'a7_authorization': 'APPROVED_BY_USER',
        'authorization_path': str(authorization_path), 'authorization_sha256': sha(authorization_path),
        'quota_query_returncode': q.returncode, 'quota_query_stdout': q.stdout,
        'used_kib': used_kib, 'hard_limit_kib': hard_kib, 'available_bytes': available,
        'required_peak_and_reserve_bytes': required,
        'budget': {'parts_and_final_bytes': 2 * summary['predicted_output_bytes'],
                   'pointer_allowance_GiB': 4, 'training_checkpoint_allowance_GiB': 400,
                   'shared_WP5_margin_GiB': 300},
        'pilot_summary_sha256': sha(summary_path)}
    save(ROOT / 'reports/full_quota_preflight.json', result)
    scripts = ['prepare_full_v7.sbatch', *[f'full_worker_v7_node{n}.sbatch' for n in [2, 8, 9, 10, 11]],
               'finalize_full_v7.sbatch', 'reproduce100_full_v7.sbatch', 'recover_full_v7.sbatch', 'report_full_v7.sbatch']
    source_refs = [{'path': str(ROOT / 'scripts' / name), 'sha256': sha(ROOT / 'scripts' / name)}
                   for name in ['sprime_v6.py', 'full_dataset_v7.py', 'finalize_full_v7.py',
                                'reproduce100_full_v7.py', 'recover_full_v7.py', 'report_full_v7.py', *scripts]]
    save(ROOT / 'reports/full_run_execution_sources_v7.json', source_refs)
    lines = ['# S′ 已获授权的全量执行资源快照', '',
        '用户已明确要求“请你完成全量实验”。授权记录与试跑 SHA 已核对；本快照更新资源信息，不重新请求 A7 授权。',
        f"试跑失败率：样本 {summary['sample_failure_rate']:.3%}，人口加权 {summary['population_weighted_failure_rate']:.3%}。",
        f"全量外推：实配核时 {summary['predicted_allocated_core_hours']:.1f}；科学处理核时 {summary['predicted_active_science_core_hours']:.1f}；输出 {summary['predicted_storage_GiB']:.2f} GiB。", '',
        '正式人口 1,220,466 个分子、11,231,854 条源记录。保留本版已通过核对的 10,000 个试跑分子，剩余 1,210,466 个按相同科学配置生成。所有失败分子仍有状态，不删除、不复制构象补数、不换力场。', '',
        '|节点|科学 worker / 实配 CPU|声明内存|单次 Slurm 上限|', '|---|---:|---:|---:|',
        '|compute-0-2|31 / 32|64 GiB|48 h|', '|compute-0-8|63 / 64|64 GiB|48 h|',
        '|compute-0-9|63 / 64|64 GiB|48 h|', '|compute-0-10|63 / 64|64 GiB|48 h|', '|compute-0-11|63 / 64|64 GiB|48 h|', '',
        '合计 283 个科学 worker，另有 5 个父进程，实配 288 CPU。提交时重新检查全部用户队列、空闲核数和 85% 声明内存预算；不占 WP5 的 12–19 节点。队列预处理与最终闭合/随机 100 重算另用 16 CPU 作业。', '',
        '共享任务队列按估计成本分派分子块；块内大分子先计算。中间 scratch 放节点本地；共享只写块级 parquet、少量进度与队列 metadata，最终合并为五组构象 parquet 和五组分子状态 parquet。原 LMDB 与原人口清单只读，不建新 LMDB。', '',
        '科学配置与本版试跑一致：原记录原子和键顺序；SMILES 指定立体优先、其余取最低能 PM7；ETKDGv3 的 molecule_id 确定种子、3N 候选、固定 200 次嵌入尝试预算、随机坐标重试一次；UFF 最大 2000 次；重原子按源原子序号 Kabsch 对齐、0.5 Å 去重和覆盖判定。', '',
        f"实际配额余量 {available / (1 << 30):.1f} GiB；本方案峰值与预留 {required / (1 << 30):.1f} GiB；存储快照有效性 {result['valid_for_submission']}。该快照仅 30 分钟有效，执行前重测；不能用整盘 df 空间代替账户配额。", '',
        '实际全量已提交，作业与队列最新状态以 submission 回执和 full_coordinator_v7_status.json 为准。完整验收须所有分子状态闭合、源记录计数一致、键唯一且构象数匹配、坐标 float64、SHA 与读回通过，再从正式全人口随机 100 个分子重新生成并严格核对坐标；试跑的 100 个不代替全量的 100 个。', '',
        '执行脚本及 SHA 见 full_run_execution_sources_v7.json；原待审报告保留为历史证据。入口继续核对与本版 pilot_summary SHA 绑定的实际用户授权。B 训练的冻结配置文件对应关系仍待确定，已有 B1/B3 运行授权保持有效。']
    (ROOT / 'reports/full_run_execution_review_v7.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: result[k] for k in ['valid_for_submission', 'available_bytes', 'required_peak_and_reserve_bytes']}))

if __name__ == '__main__':
    main()
