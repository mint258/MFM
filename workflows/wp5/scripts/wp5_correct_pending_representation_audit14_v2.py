import hashlib,json,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
p=root/'reports/continuation14_actual78_first_scheduling_audit_v1.json';old=json.loads(p.read_text())
m=json.loads(Path(old['manifest']['path']).read_text());expected={str(r['job_id']):r['node'] for r in m['main']+m['cleanup']}
assert hashlib.sha256(Path(old['manifest']['path']).read_bytes()).hexdigest()==old['manifest']['sha256']
for issue in old['issues']:
    f=issue['fields']
    assert issue['issue']=='actual_node_differs' and f['JobState']=='PENDING'
    assert 'NodeList' not in f and f['ReqNodeList']==expected[issue['job_id']]
out=root/'reports/continuation14_actual78_first_scheduling_audit_v2.json'
proof={'schema':'WP5_CONTINUATION14_ACTUAL78_SCHEDULING_AUDIT_CORRECTED_V2','status':'PASS','time':time.time(),'previous_actual_snapshot':{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},'manifest':old['manifest'],'actual_states':old['actual_states'],'actual78_resources_and_requested_nodes_valid':True,'corrected_pending_representation':'Pending unassigned jobs omit NodeList. Their exact requested node is bound by ReqNodeList; a missing assigned NodeList is not a different assigned node.','pending_unassigned_nodes_corrected':len(old['issues']),'new_Slurm_query_or_submission':False,'science_queue_modified':False}
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'status':'PASS','actual_states':old['actual_states'],'corrected_pending_rows':len(old['issues']),'report':str(out)}))
