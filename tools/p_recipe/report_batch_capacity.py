"""Summarize the user-requested batch sweep without replaying measurements."""
import csv,json
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis')
C=R/'runs/p_recipe_20261113'
REPO=Path(__file__).resolve().parents[2]

def main():
 rows=[]
 for node,name in [('compute-0-5','4530482'),('compute-0-20','batch_sweep_4090'),('compute-0-22','batch_sweep_5090')]:
  source=C/('batch_capacity_'+name+'.json');result=json.loads(source.read_text());baseline=32*16/result['records'][0]['seconds']
  for item in result['records']:
   seconds=item.get('seconds');batch=item['batch_size'];speed=batch*16/seconds if seconds else None
   rows.append(dict(gpu=result['device'],node=node,batch_size=batch,status=item['status'],headroom_pass=item['headroom_pass'],optimizer_steps=16 if seconds else '',samples=batch*16 if seconds else '',seconds=seconds if seconds else '',samples_per_second=speed if seconds else '',seconds_per_step=seconds/16 if seconds else '',throughput_vs_B32=speed/baseline if seconds else '',peak_allocated_bytes=item.get('peak_allocated_bytes',''),peak_reserved_bytes=item.get('peak_reserved_bytes',''),max_atoms=item.get('max_atoms',''),source=str(source),scope='preloaded samples; 8 fixed batches twice; includes initial allocations; FP32 noTF32; H3+projector+PMA+B4; no validation/checkpoint'))
 path=REPO/'results/p_recipe/diagnostics/batch_capacity.csv'
 with path.open('w',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 print(json.dumps(rows,indent=2),flush=True)
if __name__=='__main__':main()