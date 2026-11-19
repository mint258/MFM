"""Only directive-authorized layer6 M2/Dprime/C3 geometry; reuse M2's closed forward."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import time

# Respect the actual CPU allocation, including a smaller available CPU slot.
_CPU_THREADS = max(1, min(16, int(os.environ.get('SLURM_CPUS_PER_TASK', '16'))))
for _thread_variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_thread_variable] = str(_CPU_THREADS)

import numpy as np
import torch

from resources import REPO, R, CONTROL, guard, load, save
from collapse_composition import setup, load_representation_encoder, representation_layers
from composition_statistics import bootstrap_weights, ridge_oof, cev_values, cvf_values, summary
from phychem_mfm.phase1.v31_loader import MFM4Dataset, collate_samples
from checkpoint_paths import evaluation_checkpoint

RESULT = REPO / 'results/p_followup/Dprime_C3_geometry.json'


def reuse_m2(panel):
    source = R / 'MFM_p_heads_20261117/results/p_heads/H/H1_geometry.json'
    payload = load(source)
    value = payload['conditions']['M2']
    expected = evaluation_checkpoint(load(REPO / 'configs/p_followup/M2_reference.json'), 3000000)
    if value['status'] != 'COMPLETE' or Path(value['checkpoint']).resolve() != expected.resolve():
        raise ValueError('Existing M2 geometry is not the exact M2 reference checkpoint')
    if value['molecules'] != len(panel['indices']) or value['conformers'] != len(panel['rows']):
        raise ValueError('Existing M2 geometry panel differs')
    if payload['bootstrap'] != dict(repetitions=1000, seed=20261025, unit='molecule', paired=True, refit=False):
        raise ValueError('Existing M2 geometry bootstrap differs')
    # The H1 producer imports work A.setup and the same composition_statistics.
    return dict(status='COMPLETE', reused_from=str(source), checkpoint=value['checkpoint'],
                checkpoint_samples=3000000, molecules=value['molecules'], conformers=value['conformers'],
                layer6=value['layers']['6'], additional_forward=False)


def geometry(name, configuration, panel, weights, device):
    started = time.monotonic()
    checkpoint = evaluation_checkpoint(configuration, 3000000)
    encoder, payload = load_representation_encoder(checkpoint, device=device)
    if payload['clock']['samples_consumed'] != 3000000:
        raise ValueError('Directive geometry requires an exact3M endpoint')
    checkpoint_configuration = payload.get('configuration', {})
    if checkpoint_configuration.get('seed') != 0:
        raise ValueError('Directive descriptive geometry uses seed0')
    data = MFM4Dataset(panel['base']['root'], split='FULL', geometry_only=True, k=10,
                      molecule_indices=panel['indices'])
    path = CONTROL / ('A_directive_mean_' + name + '.npy')
    guard()
    means = np.lib.format.open_memmap(path, mode='w+', dtype=np.float32,
                                     shape=(len(panel['rows']), 512))
    with torch.no_grad():
        for start in range(0, len(panel['rows']), 32):
            samples = [data.read(mi, ci) for mi, ci in panel['rows'][start:start + 32]]
            batch = collate_samples(samples, device=device)
            features = representation_layers(encoder, batch)[3].detach().cpu().double().numpy()
            ptr = batch.ptr.cpu().tolist()
            for index, (a, b) in enumerate(zip(ptr, ptr[1:])):
                means[start + index] = features[a:b].mean(0).astype(np.float32)
            if start % 1024 == 0:
                guard();means.flush();print('DIRECTIVE_LAYER6', name, start, len(means), flush=True)
    means.flush();data.close();del encoder, payload
    if device == 'cuda':
        torch.cuda.empty_cache()
    first = np.asarray(means[panel['first']], dtype=np.float64)
    prediction, alphas = ridge_oof(panel['X'], first)
    cev = cev_values(first, prediction, weights)
    cvf, residual = cvf_values(np.asarray(means, dtype=np.float64), panel['owners'], prediction, weights)
    result = dict(status='COMPLETE', checkpoint=str(checkpoint), checkpoint_samples=3000000,
                  checkpoint_configuration={key:checkpoint_configuration.get(key) for key in
                    ('seed', 'samples', 'p_recipe', 'conformer_decomposition', 'mean_labels')},
                  molecules=len(panel['indices']), conformers=len(panel['rows']),
                  layer6=dict(CEV=summary(cev), CVF=summary(cvf), CVF_res=summary(residual)),
                  selected_alphas=alphas, seconds=time.monotonic() - started)
    del means
    path.unlink()  # Work A explicitly authorizes disposal of its own temporary mean(H).
    return result


def deliver(results):
    c3 = load(R / 'MFM_p_recipe/configs/p_recipe/fixed_20261115/round3/C3.json')
    score_path = Path(c3['output']) / 'readout/scores.json'
    scores = None
    if score_path.exists():
        existing = load(score_path)
        scores = dict(source=str(score_path), run=c3['run'], **{readout:{key:existing[readout][key]
            for key in ('mean_normalized_improvement', 'bootstrap_ci')} for readout in ('R1', 'R3')})
    payload = dict(conditions=results, C3_scores=scores, descriptive_only=True,
        bootstrap=dict(repetitions=1000, seed=20261025, unit='molecule', paired=True, refit=False),
        panel='Existing work A5000VAL/allowedk10; same setup, no new molecule selection',
        representation='Layer6 out_norm mean(H), before any shared projector or PMA head')
    save(RESULT, payload)
    lines = ['# M2、D′与分子平均标签C3：第6层描述性几何', '',
        '固定使用工作A的5000 VAL及全部实际允许构象、out_norm后mean(H)、相同五外折/五内折ridge组成OOF预测与F64统计。M2直接复用head线H1对同一检查点/面板的已关闭结果，不重跑前向。D′和C3只做第6层；CVF为同分子构象方差占比，CVF_res减去固定组成OOF预测后再计算该比例。1000次MID bootstrap保留全部构象，不重拟合；这里只描述，不增加方向性假设、PCA、阈值或训练。', '',
        '|条件|构象数|CVF|95%CI|CVF_res|95%CI|', '|---|---:|---:|---|---:|---|']
    for name, value in results.items():
        metrics = value['layer6'];cvf, residual = metrics['CVF'], metrics['CVF_res']
        lines.append(f"|{name}|{value['conformers']}|{cvf['value']}|{cvf['ci95']}|{residual['value']}|{residual['ci95']}|")
    if scores:
        lines += ['', f"C3已完成运行{scores['run']}：R1={scores['R1']['mean_normalized_improvement']}，R3={scores['R3']['mean_normalized_improvement']}；仅引用配方线现有分数，未追加探针。"]
    else:
        lines += ['', 'C3最终R1/R3尚未可用，保留待补；不以中途分数替代。']
    (REPO / 'docs/p_followup/DPRIME_C3_GEOMETRY.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--conditions', nargs='+', choices=['Dprime', 'C3'], default=['Dprime', 'C3'])
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    if args.report_only:
        deliver(load(RESULT)['conditions']);return
    guard(force=True);torch.set_num_threads(min(4, _CPU_THREADS) if args.device == 'cuda' else _CPU_THREADS)
    torch.backends.cuda.matmul.allow_tf32 = False;torch.backends.cudnn.allow_tf32 = False
    lock = None
    if args.device == 'cuda':
        gpu = os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
        used, total = map(float, subprocess.check_output(['nvidia-smi', '--id=' + gpu,
            '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], text=True).strip().split(','))
        if used / total > .30:
            raise RuntimeError('GPU admission changed')
        lock = (R / 'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks' / (gpu + '.lock')).open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    panel = setup();weights = np.vstack([np.ones((1, 5000)), bootstrap_weights(5000)])
    results = load(RESULT)['conditions'] if RESULT.exists() else {}
    if 'M2' not in results:
        results['M2'] = reuse_m2(panel)
    configurations = dict(Dprime=REPO / 'configs/p_followup/Dprime_M2_seed0_continued.json',
                          C3=R / 'MFM_p_recipe/configs/p_recipe/fixed_20261115/round3/C3.json')
    for name in args.conditions:
        if results.get(name, {}).get('status') == 'COMPLETE':
            continue
        configuration = load(configurations[name])
        try:
            evaluation_checkpoint(configuration, 3000000)
        except FileNotFoundError:
            print('WAITING_FOR_EXACT3M', name, flush=True);continue
        results[name] = geometry(name, configuration, panel, weights, args.device)
        deliver(results)
    deliver(results)


if __name__ == '__main__':
    main()
