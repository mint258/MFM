import argparse,json,os,threading,time
from pathlib import Path
from phychem_mfm.phase1.p_recipe_training import train
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args();c=json.loads(Path(a.configuration).read_text());started=time.monotonic()
 stop=threading.Event();monitor=None
 if c['round']==1:
  from native_run import record_gpu_telemetry
  telemetry=dict(c,training_budget=c['samples'],gpu_uuid=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0])
  def capture():
   while not stop.is_set():
    try:record_gpu_telemetry(telemetry)
    except Exception as error:print('GPU telemetry unavailable: '+str(error),flush=True)
    stop.wait(30)
  monitor=threading.Thread(target=capture,daemon=True);monitor.start()
 try:summary=train(c)
 finally:
  stop.set()
  if monitor:monitor.join(timeout=12)
 if summary.get('status')=='HANDOFF_SAVED':
  print(json.dumps(summary),flush=True);raise SystemExit(0)
 if c.get('speed_calibration',False):
  import csv,socket,torch
  rows=[];segment=c;segments=[]
  while True:
   path=Path(segment['output']);segments.append(str(path))
   with (path/'losses.csv').open() as stream:rows.extend(csv.DictReader(stream))
   if not segment.get('resume_from_output'):break
   segment=json.loads((Path(segment['resume_from_output'])/'configuration.json').read_text())
  rows.sort(key=lambda row:int(row['updates']))
  if summary['updates']!=1000 or summary['samples']!=1000*c['batch_size']:
   raise RuntimeError('Speed calibration requires exactly1000 optimizer updates')
  if len(rows)!=1000 or len({row['updates'] for row in rows})!=1000:
   raise RuntimeError('Speed calibration training log does not cover1000 unique updates')
  first,last=rows[0],rows[-1]
  summary.update(status='COMPLETE',calibration='1000-update throughput only; no readout',
   activation_checkpointing=c['activation_checkpointing'],
   timed_samples=int(last['samples'])-int(first['samples']),
   timed_seconds=float(last['seconds'])-float(first['seconds']),
   steady_samples_per_second=(int(last['samples'])-int(first['samples']))/(float(last['seconds'])-float(first['seconds'])),
   samples_per_second=summary['samples']/summary['seconds'],throughput_segments=segments,
   gpu_name=torch.cuda.get_device_name(0),gpu_uuid=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0],node=socket.gethostname().split('.')[0])
  (Path(c['output'])/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
  print(json.dumps(summary),flush=True);raise SystemExit(0)
 from evaluate import run,score,REPO
 for evaluated_samples in c.get('evaluation_samples',[c['samples']]):
  import gc,torch
  gc.collect();torch.cuda.empty_cache()
  checkpoint=str(Path(c['output'])/('samples_'+str(evaluated_samples)+'.pt'))
  evaluation={**c,'samples':evaluated_samples,'checkpoint':checkpoint,'features':str(Path(c['output'])/('features_'+str(evaluated_samples))),
   'output':str(Path(c['output'])/('readout' if evaluated_samples==c['samples'] else 'readout_'+str(evaluated_samples))),'persist_features':False,
   'store':'/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json',
   'reference_manifest':'/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json'}
  if not (Path(evaluation['output'])/'scores.json').is_file():
   run(evaluation);score(Path(evaluation['output'])/'predictions.json',evaluation['reference_manifest'],REPO/'results/p_recipe/scores.csv')
 summary.update(status='COMPLETE',training_and_evaluation_seconds=time.monotonic()-started)
 (Path(c['output'])/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
