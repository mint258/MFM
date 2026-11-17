"""One frozen-panel producer check before implementing T2 constrained heads."""
import collections,json,pathlib,pickle,time
import numpy as np
from h_resources import R,REPO,guard,watchdog,load,save

IDS={68:0,210:-1,279:1,346:0,413:0,64:0,668:0,44:1,45:1,46:1,712:1}
def main():
    watchdog();O=R/'runs/p_data_information_20261115_v1'
    panel=load(O/'panel.json');view=load(R/'runs/data_v1_20261025/repository/configs/data_v1/training_view_v1.json')
    selected={f.get('name',f.get('field_key')):f for f in view['fields'] if f.get('registry_id') in IDS}
    records=collections.defaultdict(list);incomplete=collections.Counter();seen=0
    for role,rows in panel.items():
        for i,row in enumerate(rows):
            with (O/'samples'/role/(str(row['pilot_index'])+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
            for ci in row['allowed_conformers']:
                s=samples[ci];seen+=1
                for name,f in selected.items():
                    t=s['targets'].get(name)
                    if t is None or not t.valid.all() or not np.isfinite(t.raw).all():
                        incomplete[name]+=1;continue
                    x=t.raw.astype(np.float64).reshape(-1)
                    records[name].append((float(x.sum()),float(np.abs(x).sum()),len(x)))
            if i%250==0:print(role,i,len(rows),'records',seen,flush=True);guard()
    result={}
    for name,f in selected.items():
        a=np.asarray(records[name],dtype=np.float64).reshape(-1,3)
        assumed=IDS[f['registry_id']]
        q=1 if f['registry_id'] in (44,45,46,712) else (int(np.rint(np.median(a[:,0]))) if len(a) else assumed)
        tolerance=np.maximum(a[:,2]*5e-5,a[:,1]*1e-3)
        fraction=float(np.mean(np.abs(a[:,0]-q)<=tolerance)) if len(a) else 0.
        result[name]=dict(registry_id=f['registry_id'],expected_Q=assumed,measured_Q=q,
            observed_records=len(a),incomplete_or_missing=incomplete[name],pass_fraction=fraction,
            constraint_enabled=fraction>=.999,maximum_absolute_residual=float(np.max(np.abs(a[:,0]-q))) if len(a) else None)
    if seen!=42961:raise ValueError('Frozen panel record membership changed')
    save(REPO/'results/p_heads/T/label_constraints.json',dict(panel=str(O/'panel.json'),records=seen,fields=result,
        tolerance='max(N*5e-5,1e-3*sum(abs(y)))',minimum_pass_fraction=.999))
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
