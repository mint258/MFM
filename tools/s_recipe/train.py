"""Real S training and existing readouts; bootstrap is deferred to CPU nodes."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from runtime import REPO, write
from s_training import train


def telemetry(c, stop):
    output = Path(c['output'])
    path = output/'gpu_telemetry.csv'
    while not stop.wait(30):
        try:
            with (output/'losses.csv').open('rb') as stream:
                stream.seek(max(0, stream.seek(0, 2)-8192))
                rows = list(csv.reader(stream.read().decode().splitlines()))
            row = next(row for row in reversed(rows) if len(row) == 9 and row[0].isdigit())
            if int(row[0]) >= c['samples']:
                return
            gpu = next(csv.reader(subprocess.check_output(['nvidia-smi', '--id='+c['gpu_uuid'],
                '--query-gpu=uuid,name,power.draw,utilization.gpu,memory.used',
                '--format=csv,noheader,nounits'], text=True, timeout=10).splitlines()))
            exists = path.exists()
            with path.open('a', newline='') as stream:
                writer = csv.writer(stream)
                if not exists:
                    writer.writerow(['timestamp', 'samples', 'training_seconds', 'gpu_uuid', 'gpu_name',
                                     'whole_card_power_watts', 'utilization_percent', 'memory_used_mib'])
                writer.writerow([time.time(), row[0], row[-1], *[v.strip() for v in gpu]])
        except Exception as error:
            print('S_TELEMETRY '+str(error), flush=True)


def main(c):
    started = time.monotonic()
    stop = threading.Event()
    monitor = threading.Thread(target=telemetry, args=(c, stop), daemon=True)
    monitor.start()
    try:
        result = train(c)
    finally:
        stop.set()
        monitor.join(timeout=12)
    if result.get('status') == 'HANDOFF_SAVED':
        return result
    spec = importlib.util.spec_from_file_location('existing_p_evaluate', REPO/'tools/p_recipe/evaluate.py')
    evaluate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluate)
    for samples in c['evaluation_samples']:
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
        output = Path(c['output'])/('readout' if samples == c['samples'] else 'readout_'+str(samples))
        if (output/'predictions.json').is_file():
            continue
        evaluation = dict(c, samples=samples, checkpoint=str(Path(c['output'])/('samples_'+str(samples)+'.pt')),
            features=str(output/'features'), output=str(output), persist_features=False,
            store=c['evaluation_store'], layer=6)
        evaluate.run(evaluation)
    result.update(status='GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS',
                  training_and_gpu_readout_seconds=time.monotonic()-started)
    write(Path(c['output'])/'summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', required=True)
    result = main(json.loads(Path(p.parse_args().configuration).read_text()))
    print(json.dumps(result), flush=True)
